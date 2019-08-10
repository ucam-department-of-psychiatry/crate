#!/usr/bin/env python
# crate_anon/nlp_manager/cloud_parser.py

"""
===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

This module is for sending JSON requests to the NLP Cloud server and
receiving responses.

"""

from copy import copy
from http.cookiejar import CookieJar
import json
import logging
import sys
from typing import Any, Dict, List, Tuple, Generator, Optional
import time

from cardinal_pythonlib.rate_limiting import rate_limited
from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.dicts import (
    rename_keys_in_dict,
    set_null_values_in_dict,
)
from cardinal_pythonlib.timing import MultiTimerContext, timer
from requests import post, Response
from requests.exceptions import HTTPError, RequestException
from urllib3.exceptions import NewConnectionError

from crate_anon.common.stringfunc import does_text_contain_word_chars
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.constants import (
    CloudNlpConfigKeys,
    FN_NLPDEF,
    FN_WHEN_FETCHED,
    GateResultKeys,
    NlpConfigPrefixes,
    ProcessorConfigKeys,
)
from crate_anon.nlp_manager.nlp_definition import (
    full_sectionname,
    NlpDefinition,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlprp.api import (
    make_nlprp_dict,
    make_nlprp_request,
    nlprp_datetime_to_datetime_utc_no_tzinfo,
)
from crate_anon.nlprp.constants import (
    HttpStatus,
    NlprpCommands,
    NlprpKeys as NKeys,
)

log = logging.getLogger(__name__)

TIMING_INSERT = "CloudRequest_sql_insert"


# =============================================================================
# Helper functions
# =============================================================================

def utf8len(text: str) -> int:
    """
    Returns the length of text once encoded in UTF-8.
    """
    return len(text.encode('utf-8'))


def to_json_str(json_structure: Dict[str, Any]) -> str:
    """
    Converts a Python dict to a JSON string.
    """
    return json.dumps(json_structure, default=str)
    # This needs 'default=str' to deal with non-JSON-serializable
    # objects that may occur, such as datetimes in the metadata.


# =============================================================================
# CloudRequest
# =============================================================================

class CloudRequest(object):
    """
    Class to send requests to the cloud processors and process the results.
    """
    # Set up standard information for all requests
    HEADERS = {
        'charset': 'utf-8',
        'Content-Type': 'application/json'
    }

    def __init__(self,
                 nlpdef: NlpDefinition,
                 commit: bool = False,
                 client_job_id: str = None,
                 remote_processors_available: Optional[List[str]] = None,
                 procs_auto_add: bool = True) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
            client_job_id:
                optional string used to group together results into one job.
            remote_processors_available:
                List of remote processor names (expected to be pre-checked for
                validity). If ``None``, the :meth:'add_processor'` method
                checks for validity using the :meth:'list_processors' method.
                When doing many requests all with the same set of processors it
                is best to test validity outside class and specify this
                parameter.
            procs_auto_add:
                add procs automatically if not provided
        """
        self._nlpdef = nlpdef
        self._cloudcfg = nlpdef.get_cloud_config_or_raise()
        self._sectionname = full_sectionname(NlpConfigPrefixes.NLPDEF,
                                             self._nlpdef.get_name())
        self._commit = commit
        self.auth = (self._cloudcfg.username, self._cloudcfg.password)
        self.fetched = False
        self.client_job_id = client_job_id or ""

        # Set up processing request
        self.request_process = make_nlprp_dict()
        self.request_process[NKeys.COMMAND] = NlprpCommands.PROCESS
        self.request_process[NKeys.ARGS] = {
            NKeys.PROCESSORS: [],  # type: List[str]
            NKeys.QUEUE: True,
            NKeys.CLIENT_JOB_ID: self.client_job_id,
            NKeys.INCLUDE_TEXT: False,
            NKeys.CONTENT: []  # type: List[str]
        }
        # Set up fetch_from_queue request
        self.fetch_request = make_nlprp_dict()
        self.fetch_request[NKeys.COMMAND] = NlprpCommands.FETCH_FROM_QUEUE

        self._remote_processors_available = remote_processors_available
        self.nlp_data = None  # type: Optional[Dict[str, Any]]  # the JSON response  # noqa
        self.queue_id = None  # type: Optional[str]

        self.procs = {}  # type: Dict[str, str]
        if procs_auto_add:
            self.add_all_processors()

        self.mirror_processors = {}  # type: Dict[str, BaseNlpParser]
        self.cookies = None  # type: Optional[CookieJar]
        self.request_failed = False

        # Rate-limited functions
        rate_limit_hz = self._cloudcfg.rate_limit_hz
        if rate_limit_hz > 0:
            # Rate-limited
            self._ratelimited_send_process_request = rate_limited(
                rate_limit_hz)(self._internal_send_process_request)
            self._ratelimited_try_fetch = rate_limited(
                rate_limit_hz)(self.try_fetch)
        else:
            # No limits!
            self._ratelimited_send_process_request = \
                self._internal_send_process_request
            self._ratelimited_try_fetch = self.try_fetch

    def _post(self, request_json: str,
              may_fail: bool = None) -> Optional[Response]:
        """
        Submits an HTTP POST request to the remote.
        Tries up to a certain number of times.

        Args:
            request_json: JSON (string) request.
            may_fail: may the request fail? Boolean, or ``None`` to use the
                value from the cloud NLP config

        Returns:
            :class:`requests.Response`, or ``None`` for failure (if failure is
            permitted by ``may_fail``).

        Raises:
            - :exc:`RequestException` if max retries exceeded and we are
              stopping on failure
        """
        if may_fail is None:
            may_fail = not self._cloudcfg.stop_at_failure
        tries = 0
        success = False
        response = None
        while (not success) and tries <= self._cloudcfg.max_tries:
            try:
                tries += 1
                response = post(
                    url=self._cloudcfg.url,
                    data=request_json,
                    auth=self.auth,
                    headers=self.HEADERS,
                    cookies=self.cookies,
                    verify=self._cloudcfg.verify_ssl
                )
                self.cookies = response.cookies
                success = True
            except (RequestException, NewConnectionError) as e:
                self._sleep_for_remote(e)
        if not success:
            # Failure
            msg = "Max tries exceeded. Request has failed."
            log.error(msg)
            if may_fail:
                self.request_failed = True
                return None
            else:
                raise RequestException(msg)
        # Success
        return response

    def _post_get_json(self, request_json: str,
                       may_fail: bool = False) -> Optional[Dict[str, Any]]:
        """
        Executes :meth:`_post`, then parses the result as JSON.

        Args:
            request_json: JSON (string) request.
            may_fail: may the request fail?

        Returns:
            dict: JSON object, or ``None`` upon failure if ``may_fail`` is
                ``True``

        Raises:
            - :exc:`RequestException` if max retries exceeded and we are
              stopping on failure
            - :exc:`JSONDecodeError` for bad JSON
        """
        response = self._post(request_json, may_fail=may_fail)
        if response is None and may_fail:
            return None
        try:
            # noinspection PyUnboundLocalVariable
            json_response = response.json()
            return json_response
        except json.decoder.JSONDecodeError:
            log.error("Reply was not JSON")
            raise

    def _sleep_for_remote(self, exc: Exception) -> None:
        """
        Wait for a while, because the remote is unhappy for some reason.

        Args:
            exc: exception that caused us to wait.
        """
        log.error(exc)
        time_s = self._cloudcfg.wait_on_conn_err
        log.warning(f"Retrying in {time_s} seconds.")
        time.sleep(time_s)

    def get_remote_processors(self) -> Optional[List[str]]:
        """
        Returns the list of available processors from the remote. If that list
        has not already been fetched, or unless it was pre-specified upon
        construction, fetch it from the server.
        """
        if self._remote_processors_available is not None:
            # Prespecified or already fetched.
            return self._remote_processors_available

        # Need to fetch...

        # Make request
        list_procs_request = make_nlprp_dict()
        list_procs_request[NKeys.COMMAND] = NlprpCommands.LIST_PROCESSORS
        request_json = to_json_str(list_procs_request)

        # Send request, get response
        json_response = self._post_get_json(request_json, may_fail=False)

        status = json_response[NKeys.STATUS]
        if status != HttpStatus.OK:
            errors = json_response.get(NKeys.ERRORS)
            if errors:
                if isinstance(errors, list):
                    for err in errors:
                        if isinstance(err, str):
                            log.error(err)
                        else:
                            for key in err:
                                log.error(f"{key}: {err[key]}")
                else:
                    log.error(str(errors))
            raise HTTPError(f"Response status was: {status}")
        self._remote_processors_available = [
            proc[NKeys.NAME] for proc in json_response[NKeys.PROCESSORS]
        ]
        return self._remote_processors_available

    def add_processor(self, processor: str) -> None:
        """
        Add a remote processor to the list of processors that we will request
        results from.

        Args:
            processor: name of processor on the server
        """
        remote_processors_available = self.get_remote_processors()
        if processor not in remote_processors_available:
            log.warning(f"Unknown processor, skipping {processor}")
        else:
            self.request_process[NKeys.ARGS][NKeys.PROCESSORS].append({
                NKeys.NAME: processor
            })

    def add_all_processors(self) -> None:
        """
        todo: docs
        """
        processorpairs = self._nlpdef.opt_strlist(
            self._sectionname, CloudNlpConfigKeys.PROCESSORS,
            required=True, lower=False)
        self.procs = {}  # type: Dict[str, str]
        for proctype, procname in chunks(processorpairs, 2):
            if proctype.upper() == "GATE":
                # GATE processor - use procname
                self.add_processor(procname)
            else:
                # CRATE Python processor - use proctype
                self.add_processor(proctype)
            # Save procnames for later to get tablenames
            self.procs[procname] = proctype

    def add_text(self, text: str, other_values: Dict[str, Any]) -> bool:
        """
        Adds text for analysis to the NLP request, with associated metadata.

        Tests the size of the request if the text and metadata was added, then
        adds it if it doesn't go over the size limit and there are word
        characters in the text.

        Args:
            text: the text
            other_values: the metadata

        Returns:
            bool: ``True`` if successfully added, ``False`` if not.
        """
        if not does_text_contain_word_chars(text):
            log.warning(f"No word characters found in text: {text!r}")
            return False

        new_content = {
            NKeys.METADATA: other_values,
            NKeys.TEXT: text
        }
        # Add all the identifying information.
        args = self.request_process[NKeys.ARGS]
        content_key = NKeys.CONTENT
        old_content = copy(args[content_key])
        args[content_key].append(new_content)
        max_length = self._cloudcfg.max_content_length
        # Slow -- is there a way to get length without having to serialize?
        # At least -- do it only once (forgiveness not permission, etc.).
        if (max_length and
                utf8len(to_json_str(self.request_process)) > max_length):
            # Too long. Restore the previous state!
            args[content_key] = old_content
            return False
        # Success.
        return True

    def send_process_request(self, queue: bool,
                             cookies: CookieJar = None,
                             include_text: bool = True) -> None:
        """
        Sends a request to the server to process the text.

        Args:
            queue: todo: XXX
            cookies: optional :class:`http.cookiejar.CookieJar`
            include_text: todo: XXX
        """
        self._ratelimited_send_process_request(
            queue=queue,
            cookies=cookies,
            include_text=include_text
        )

    def _internal_send_process_request(self, queue: bool,
                                       cookies: CookieJar = None,
                                       include_text: bool = True) -> None:
        """
        See :meth:`send_process_request`. This is the internal main function,
        to which rate limiting may be applied.
        """
        # Don't send off an empty request
        if not self.request_process[NKeys.ARGS][NKeys.CONTENT]:
            log.warning("Request empty - not sending.")
            return

        # Create request
        if cookies:
            self.cookies = cookies
        self.request_process[NKeys.ARGS][NKeys.QUEUE] = queue
        self.request_process[NKeys.ARGS][NKeys.INCLUDE_TEXT] = include_text
        request_json = to_json_str(self.request_process)

        # Send request; get response
        json_response = self._post_get_json(request_json)

        status = json_response[NKeys.STATUS]
        if queue and status == HttpStatus.ACCEPTED:
            self.queue_id = json_response[NKeys.QUEUE_ID]
            self.fetched = False
        elif (not queue) and status == HttpStatus.OK:
            self.nlp_data = json_response
            self.fetched = True
        else:
            log.error(f"Got HTTP status code {status}.")
            log.error(f"Response from server: {json_response}")
            if self._cloudcfg.stop_at_failure:
                raise HTTPError
            else:
                self.request_failed = True
                return

    def set_queue_id(self, queue_id: str) -> None:
        """
        Sets the queue_id. To be used when you're not actually sending a
        request this time.
        """
        self.queue_id = queue_id

    def try_fetch(self, cookies: CookieJar = None) -> Optional[Dict[str, Any]]:
        """
        Tries to fetch the response from the server. Assumes queued mode.
        Returns the JSON response.
        """
        return self._ratelimited_try_fetch(cookies=cookies)

    def _internal_try_fetch(self, cookies: CookieJar = None) \
            -> Optional[Dict[str, Any]]:
        """
        See :meth:`try_fetch`. This is the internal main function, to which
        rate limiting may be applied.
        """
        # Create request
        if cookies:
            self.cookies = cookies
        self.fetch_request[NKeys.ARGS] = {NKeys.QUEUE_ID: self.queue_id}
        request_json = to_json_str(self.fetch_request)

        # Send request; get response
        json_response = self._post_get_json(request_json)
        return json_response

    def check_if_ready(self, cookies: CookieJar = None) -> bool:
        """
        Checks if the data is ready yet. Assumes queued mode (so
        :meth:`set_queue_id` should have been called first). If the data is
        ready, collect it and return ``True``, else return ``False``.
        """
        if self.queue_id is None:
            log.warning("Tried to fetch from queue before sending request.")
            return False
        if self.fetched:
            return False  # todo: check with FS; is that the right response?
        json_response = self.try_fetch(cookies)
        if not json_response:
            return False
        status = json_response[NKeys.STATUS]
        if status == HttpStatus.OK:
            self.nlp_data = json_response
            self.fetched = True
            return True
        elif status == HttpStatus.PROCESSING:
            return False
        elif status == HttpStatus.NOT_FOUND:
            # print(json_response)
            log.error(f"Got HTTP status code {HttpStatus.NOT_FOUND} - "
                      f"queue_id {self.queue_id} does not exist")
            return False
        else:
            log.error(
                f"Got HTTP status code {status} for queue_id {self.queue_id}.")
            return False

    def show_queue(self) -> Optional[List[Dict[str, Any]]]:
        """
        Returns a list of the user's queued requests. Each list element is a
        dictionary as returned according to the :ref:`NLPRP <nlprp>`.
        """
        show_request = make_nlprp_request(
            command=NlprpCommands.SHOW_QUEUE
        )
        request_json = to_json_str(show_request)
        json_response = self._post_get_json(request_json, may_fail=False)

        status = json_response[NKeys.STATUS]
        if status == HttpStatus.OK:
            try:
                queue = json_response[NKeys.QUEUE]
            except KeyError:
                log.error(f"Response did not contain key {NKeys.QUEUE!r}.")
                raise
            return queue
        else:
            # Is this the right error to raise?
            raise ValueError(f"Response status was: {status}")

    def delete_all_from_queue(self) -> None:
        """
        Delete ALL pending requests from the server's queue. Use with caution.
        """
        delete_request = make_nlprp_request(
            command=NlprpCommands.DELETE_FROM_QUEUE,
            command_args={NKeys.DELETE_ALL: True}
        )
        request_json = to_json_str(delete_request)
        response = self._post(request_json, may_fail=False)
        # The GATE server-side doesn't send back JSON for this
        # todo: ... should it?

        status = response.status_code
        if status == HttpStatus.NOT_FOUND:
            log.warning("Queued request(s) not found. May have been cancelled "
                        "already.")
        elif status != HttpStatus.OK and status != HttpStatus.NO_CONTENT:
            raise HTTPError(f"Response status was: {status}")

    def delete_from_queue(self, queue_ids: List[str]) -> None:
        """
        Delete pending requests from the server's queue for queue_ids
        specified.
        """
        delete_request = make_nlprp_request(
            command=NlprpCommands.DELETE_FROM_QUEUE,
            command_args={NKeys.QUEUE_IDS: queue_ids}
        )
        request_json = to_json_str(delete_request)
        response = self._post(request_json, may_fail=False)
        # ... not (always) a JSON response?
        # todo: ... should it be?

        status = response.status_code
        if status == HttpStatus.NOT_FOUND:
            log.warning("Queued request(s) not found. May have been cancelled "
                        "already.")
        elif status != HttpStatus.OK and status != HttpStatus.NO_CONTENT:
            raise HTTPError(f"Response status was: {status}")
        self.cookies = response.cookies

    def get_tablename_map(self, processor: str) -> Tuple[Dict[str, str],
                                                         Dict[str,
                                                         OutputUserConfig]]:
        """
        todo:: docs

        Args:
            processor:

        Returns:

        """
        proc_section = full_sectionname(NlpConfigPrefixes.PROCESSOR, processor)
        typepairs = self._nlpdef.opt_strlist(
            proc_section, ProcessorConfigKeys.OUTPUTTYPEMAP,
            required=True, lower=False)

        outputtypemap = {}  # type: Dict[str, OutputUserConfig]
        type_to_tablename = {}  # type: Dict[str, str]
        for c in chunks(typepairs, 2):
            annottype = c[0]
            outputsection = c[1]
            # annottype = annottype.lower()
            otconfig = OutputUserConfig(self._nlpdef.get_parser(),
                                        outputsection)
            outputtypemap[annottype] = otconfig
            type_to_tablename[annottype] = otconfig.get_tablename()

        return type_to_tablename, outputtypemap

    def get_nlp_values_internal(
            self,
            processor_data: Dict[str, Any],
            proctype: str,
            procname: str,
            metadata: Dict[str, Any]) -> Generator[Tuple[
                str, Dict[str, Any], str], None, None]:
        """
        todo:: docs

        Args:
            processor_data:
            proctype:
            procname:
            metadata:

        Returns:

        """
        tablename = self._nlpdef.opt_str(
            full_sectionname(NlpConfigPrefixes.PROCESSOR, procname),
            'desttable', required=True)
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {proctype} failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
            return
        for result in processor_data[NKeys.RESULTS]:
            result.update(metadata)
            yield tablename, result, proctype

    def get_nlp_values_gate(
            self,
            processor_data: Dict[str, Any],
            procname: str,
            metadata: Dict[str, Any],
            text: str = "") -> Generator[Tuple[
                str, Dict[str, Any], str], None, None]:
        """
        Gets result values from processed GATE data which will originally
        be in the following format:
        
        .. code-block:: none
        
            {
                'set': set the results belong to (e.g. 'Medication'),
                'type': annotation type,
                'start': start index,
                'end': end index,
                'features': {a dictionary of features e.g. 'drug', 'frequency', etc}
            }

        Yields output tablename, formatted result and processor name.
        """  # noqa
        type_to_tablename, outputtypemap = self.get_tablename_map(
            procname)
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {procname} failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
            return
        for result in processor_data[NKeys.RESULTS]:
            # Assuming each set of results says what annotation type
            # it is
            # annottype = result[FN_TYPE].lower()
            annottype = result[GateResultKeys.TYPE]
            features = result[GateResultKeys.FEATURES]
            start = result[GateResultKeys.START]
            end = result[GateResultKeys.END]
            formatted_result = {
                '_type': annottype,
                '_set': result[GateResultKeys.SET],
                '_start': start,
                '_end': end,
                '_content': "" if not text else text[start:end]
            }
            formatted_result.update(features)
            c = outputtypemap[annottype]
            rename_keys_in_dict(formatted_result, c.renames())
            set_null_values_in_dict(formatted_result, c.null_literals())
            tablename = type_to_tablename[annottype]
            formatted_result.update(metadata)
            # Return procname as well, so we find the right database
            yield tablename, formatted_result, procname

    def get_nlp_values(self) -> Generator[Tuple[str, Dict[str, Any], str],
                                          None, None]:
        """
        Yields ``(tablename, results, processorname)`` for each set of results.
        """
        # Method should only be called if we already have the nlp data
        assert self.nlp_data, ("Method 'get_nlp_values' must only be called "
                               "after nlp_data is obtained")
        for result in self.nlp_data[NKeys.RESULTS]:
            metadata = result[NKeys.METADATA]
            text = result[NKeys.TEXT]
            for processor_data in result[NKeys.PROCESSORS]:
                procidentifier = processor_data[NKeys.NAME]
                mirror_proc = self.mirror_processors[procidentifier]
                if mirror_proc.get_parser_name().upper() == 'GATE':
                    for t, r, p in self.get_nlp_values_gate(processor_data,
                                                            procidentifier,
                                                            metadata,
                                                            text):
                        yield t, r, p
                else:
                    procname = mirror_proc.get_cfgsection()
                    for t, r, p in self.get_nlp_values_internal(
                            processor_data, procidentifier,
                            procname, metadata):
                        yield t, r, p

    def set_mirror_processors(
            self,
            procs: List[BaseNlpParser] = None) -> None:
        """
        Sets 'mirror_processors'. The purpose of mirror_processors is so that
        we can easily access the sessions that come with the processors.
        """
        if procs:
            assert isinstance(procs, list), (
                "Argument 'procs' must be a list")
            for proc in procs:
                assert isinstance(proc, BaseNlpParser), (
                    "Each element of 'procs' must be from a subclass "
                    "of BaseNlpParser")
                # proctype = proc.get_parser_name()
                # Use 'proc.__name__' instead, to handle case sensitivity
                proctype = type(proc).__name__
                if proctype.upper() == 'GATE':
                    self.mirror_processors[proc.get_cfgsection()] = proc
                else:
                    self.mirror_processors[proctype] = proc
        else:
            for proc in self._nlpdef.get_processors():
                # proctype = proc.get_parser_name()
                # Use 'proc.__name__' instead, to handle case sensitivity
                proctype = type(proc).__name__
                if proctype.upper() == 'GATE':
                    self.mirror_processors[proc.get_cfgsection()] = proc
                else:
                    self.mirror_processors[proctype] = proc

    def process_all(self) -> None:
        """
        Puts the NLP data into the database. Very similar to
        :meth:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser.process`,
        but deals with all relevant processors at once.
        """
        nlpname = self._nlpdef.get_name()

        for tablename, nlp_values, procidentifier in self.get_nlp_values():
            mirror_proc = self.mirror_processors[procidentifier]
            nlp_values[FN_NLPDEF] = nlpname
            # Doesn't matter if we do this more than once for the same database
            # as it just returns the database object, rather than starting a
            # new connection
            session = mirror_proc.get_session()
            sqla_table = mirror_proc.get_table(tablename)
            column_names = [c.name for c in sqla_table.columns]
            # Convert string datetime back into datetime, using UTC
            for key in nlp_values:
                if key == FN_WHEN_FETCHED:
                    nlp_values[key] = (
                        nlprp_datetime_to_datetime_utc_no_tzinfo(
                            nlp_values[key]))
            final_values = {k: v for k, v in nlp_values.items()
                            if k in column_names}
            insertquery = sqla_table.insert().values(final_values)
            with MultiTimerContext(timer, TIMING_INSERT):
                session.execute(insertquery)
            self._nlpdef.notify_transaction(
                session, n_rows=1, n_bytes=sys.getsizeof(final_values),
                force_commit=self._commit)

# todo: delete what's below?

#            # REMEMBER TO FIX THIS!
#            session = procs_to_sessions[procname][1]
#            destdb_name = procs_to_sessions[procname][0]
#            destdb = self._destdbs[destdb_name]
#            engine = destdb.engine
#            if not engine.dialect.has_table(engine, tablename):
#                sqla_table = self.get_table(tablename)
#            else:
#                metadata = MetaData(engine, reflect=True)
#                sqla_table = metadata.tables[tablename]
#            column_names = [c.name for c in sqla_table.columns]
#            final_values = {k: v for k, v in nlp_values.items()
#                            if k in column_names}
#            insertquery = sqla_table.insert().values(final_values)
#            with MultiTimerContext(timer, TIMING_INSERT):
#                session.execute(insertquery)
#
#            self._nlpdef.notify_transaction(
#                session, n_rows=1, n_bytes=sys.getsizeof(final_values),
#                force_commit=self._commit)
