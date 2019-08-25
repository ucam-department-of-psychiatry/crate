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

.. todo:: cloud_parser: handle new ``tabular_schema`` info from server

"""

from copy import copy
from http.cookiejar import CookieJar
import json
import logging
import sys
from typing import Any, Dict, List, Tuple, Generator, Optional, Type
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
from sqlalchemy.schema import Column, Index
from sqlalchemy import types as sqlatypes

from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
from crate_anon.common.memsize import getsize
from crate_anon.common.stringfunc import does_text_contain_word_chars
from crate_anon.nlp_manager.nlp_definition import (
    NlpDefinition,
)
from crate_anon.nlp_manager.constants import (
    FN_NLPDEF,
    FN_WHEN_FETCHED,
    full_sectionname,
    GateResultKeys,
    NlpConfigPrefixes,
    ProcessorConfigKeys,
    NlpDefValues,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlprp.api import (
    json_get_array,
    json_get_int,
    JsonValueType,
    JsonObjectType,
    make_nlprp_dict,
    make_nlprp_request,
    nlprp_datetime_to_datetime_utc_no_tzinfo,
)
from crate_anon.nlprp.constants import (
    HttpStatus,
    NlprpCommands,
    NlprpKeys as NKeys,
    NlprpValues,
)
from crate_anon.nlp_manager.base_nlp_parser import TableMaker

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


def to_json_str(json_structure: JsonValueType) -> str:
    """
    Converts a Python object to a JSON string.
    """
    return json.dumps(json_structure, default=str,
                      separators=JSON_SEPARATORS_COMPACT)
    # This needs 'default=str' to deal with non-JSON-serializable
    # objects that may occur, such as datetimes in the metadata.


# =============================================================================
# Cloud class for cloud-based processsors
# =============================================================================

class Cloud(TableMaker):
    """
    Class to hold information on remote processors and create the relavant
    tables.
    """
    # Index for anonymous tables
    i = 0

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the config section for the processor
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(nlpdef, cfgsection, commit)
        self.processor_dict = None  # type: Optional[Dict[str, Any]]
        sectionname = full_sectionname(NlpConfigPrefixes.PROCESSOR,
                                       cfgsection)
        self.procname = nlpdef.opt_str(
            sectionname, ProcessorConfigKeys.PROCESSOR_NAME,
            required=True)
        self.procversion = nlpdef.opt_str(
            sectionname, ProcessorConfigKeys.PROCESSOR_VERSION,
            default=None)
        self.tablename = nlpdef.opt_str(sectionname,
                                        ProcessorConfigKeys.DESTTABLE,
                                        default=None)  # not required
        self.format = nlpdef.opt_str(
            sectionname,
            ProcessorConfigKeys.PROCESSOR_TYPE,
            default=NlpDefValues.FORMAT_STANDARD)
        self.schema_type = None
        self.sql_dialect = None
        self.schema = None  # type: Optional[Dict[str, Any]]
        self.available_remotely = False  # update later if available

    @staticmethod
    def get_coltype_parts(coltype_str: str) -> List[str]:
        """
        Get root column type and parameter, i.e. for VARCHAR(50)
        root column type is VARCHAR and parameter is 50.
        """
        parts = [x.strip() for x in coltype_str.replace(")", "").split("(")]
        if len(parts) == 1:
            col_str = parts[0]
            parameter = ""
        else:
            try:
                col_str, parameter = parts
            except ValueError:
                log.error(f"Invalid column type in response: {coltype_str}")
                raise
            try:
                # Turn the parameter into an integer if it's supposed to be one
                parameter = int(parameter)
            except ValueError:
                pass
        return [col_str, parameter]

    @staticmethod
    def str_to_coltype_general(
            coltype_str: str) -> Type[sqlatypes.TypeEngine]:
        """
        Get the sqlalchemy column type class which fits with the column type.
        """
        coltype = getattr(sqlatypes, coltype_str)
        # Check if 'coltype' is really an sqlalchemy column type
        if issubclass(coltype, sqlatypes.TypeEngine):
            return coltype

    @classmethod
    def unique_identifier(cls) -> str:
        """
        Create a unique (for this run) identifier for the output table. Only
        used if the remote processor has an empty string for the tablename,
        and no name is specified by the user.
        """
        cls.i += 1
        return f"anon_table{cls.i}"

    def is_tabular(self) -> bool:
        """
        Is the format of the schema information given by the remote processor
        tabular?
        """
        return self.schema_type == NlprpValues.TABULAR

    def confirm_available(self, available: bool = True) -> None:
        """
        Set the attribute 'available_remotely', which indicates whether
        a requested processor is actually available from the specified server.
        """
        self.available_remotely = available

    def set_procinfo_if_correct(self, processor_dict: Dict[str, Any]) -> None:
        """
        Checks if a processor dictionary, with all the nlprp specified info
        a processor should have, belongs to this processor. If it does, then
        we add the information from the procesor dictionary.
        """
        if self.procname != processor_dict[NKeys.NAME]:
            return
        if ((self.procversion is None and
                processor_dict[NKeys.IS_DEFAULT_VERSION]) or
                (self.procversion == processor_dict[NKeys.VERSION])):
            self.set_processor_info(processor_dict)

    def set_processor_info(self, processor_dict: Dict[str, Any]) -> None:
        """
        Add the information from a processor dictionary. If it contains
        table information, this allows us to create the correct tables when
        the time comes.
        """
        # This won't be called unless the remote processor is available
        self.confirm_available()
        self.processor_dict = processor_dict
        # self.name = processor_dict[NKeys.NAME]
        self.schema_type = processor_dict.get(NKeys.SCHEMA_TYPE)
        if self.is_tabular():
            self.schema = processor_dict[NKeys.TABULAR_SCHEMA]
            self.sql_dialect = processor_dict[NKeys.SQL_DIALECT]

    def str_to_coltype(self, data_type_str: str) -> sqlatypes.TypeEngine:
        """
        This is supposed to get column types depending on the sql dialect
        used by the server, but it's not implemented yet.
        """
        raise NotImplementedError
        # if self.sql_dialect == SqlDialects.MSSQL:
        #     return self.str_to_coltype_mssql(data_type_str)
        # elif self.sql_dialect == SqlDialects.MYSQL:
        #     return self.str_to_coltype_mysql(data_type_str)
        # elif self.sql_dialect == SqlDialects.ORACLE:
        #     return self.str_to_coltype_oracle(data_type_str)
        # elif self.sql_dialect == SqlDialects.POSTGRES:
        #     return self.str_to_coltype_postgres(data_type_str)
        # elif self.sql_dialect == SqlDialects.SQLITE:
        #     return self.str_to_coltype_sqlite(data_type_str)
        # else:
        #     pass

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        """
        Gets the destination tables and their columns, currently using just
        the remote processor information, but will soon be ammended to
        have the option of using user-specified table definitions.
        """
        tables = {}
        for table, columns in self.schema.items():
            identifier = table if table else self.unique_identifier()
            self.tablename = self.tablename if self.tablename else identifier
            column_objects = []
            for column in columns:
                col_str, parameter = self.get_coltype_parts(
                    column[NKeys.COLUMN_TYPE])
                data_type_str = column[NKeys.DATA_TYPE]
                coltype = self.str_to_coltype_general(data_type_str)
                column_objects.append(Column(
                    column[NKeys.COLUMN_NAME],
                    coltype if not parameter else coltype(parameter),
                    comment=column[NKeys.COLUMN_COMMENT],
                    nullable=column[NKeys.IS_NULLABLE]
                ))
            tables[self.tablename] = column_objects
        return tables

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        """
        Not implemented yet.
        """
        return {}


# =============================================================================
# CloudRequest
# =============================================================================

class CloudRequest(object):
    """
    Class to send requests to the cloud processors and process the results.
    """
    # Set up standard information for all requests
    HTTP_HEADERS = {
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
                List of remote processor names (expected to have been
                pre-checked for validity). If ``None``, the
                :meth:'add_processor'` method checks for validity using the
                :meth:'list_processors' method. When doing many requests all
                with the same set of processors it is best to test validity
                outside class and specify this parameter.
            procs_auto_add:
                add procs automatically if not provided
        """
        self._nlpdef = nlpdef
        self._cloudcfg = nlpdef.get_cloud_config_or_raise()
        self._nlpdef_sectionname = full_sectionname(NlpConfigPrefixes.NLPDEF,
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
        self.nlp_data = None  # type: Optional[JsonObjectType]  # the JSON response  # noqa
        self.queue_id = None  # type: Optional[str]

        # self.mirror_processors = {}  # type: Dict[str, BaseNlpParser]
        self.cookies = None  # type: Optional[CookieJar]
        self.request_failed = False

        # Of the form:
        #     {cfgsection for processor: 'Cloud' object}
        self.requested_processors = self._cloudcfg.remote_processors  # type: Dict[Tuple[str, Optional[str]], Cloud]  # noqa
        self._remote_processors_full_info = None  # type: Optional[List[Dict[str, Any]]]

        # This fails if it's above the setting of 'self.cookies'
        if procs_auto_add:
            self.add_all_processors()

    @classmethod
    def set_rate_limit(cls, rate_limit_hz: int) -> None:
        """
        Creates new methods which are rate limited. Only use this once per run.
        """
        if rate_limit_hz > 0:
            # Rate-limited
            cls._ratelimited_send_process_request = rate_limited(
                rate_limit_hz)(cls._internal_send_process_request)
            cls._ratelimited_try_fetch = rate_limited(
                rate_limit_hz)(cls._internal_try_fetch)
        else:
            # No limits!
            cls._ratelimited_send_process_request = \
                cls._internal_send_process_request
            cls._ratelimited_try_fetch = cls._internal_try_fetch

    def process_request_too_long(self, max_length: Optional[int]) -> bool:
        """
        Is the number of bytes in the outbound JSON request more than the
        permitted maximum?

        Args:
            max_length:
                the maximum length, or ``None`` for no limit

        Notes:

        The JSON method was found to be slow.

        Specimen methods:

        .. code-block:: python

            import timeit
            setup = '''
            import json
            from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
            from crate_anon.common.memsize import getsize
            stringlength = 100000  # 100 kb
            testdict = {'a': 1, 'b': {'c': [2,3,4, 'x' * stringlength]}}
            '''
            v1 = "len(json.dumps(testdict, separators=JSON_SEPARATORS_COMPACT).encode('utf-8'))"
            timeit.timeit(v1, setup=setup, number=1000)
            # ... answer is total time in s, and therefore per-call time in milliseconds
            # v1 gives e.g. 0.39ms
            
            v2 = "getsize(testdict)"
            timeit.timeit(v2, setup=setup, number=1000)
            # v2 gives 0.006 ms

        In general, long strings (which is the thing we're watching out for)
        make :func:`json.dumps` particularly slow.

        But also, in general, Python objects seem to take up more space than
        their JSON representation; e.g. compare
        
        .. code-block:: python

            import json
            from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
            from crate_anon.common.memsize import getsize
            from typing import Any
            
            def compare(x: Any) -> None:
                json_utf8_length = len(
                    json.dumps(x, separators=JSON_SEPARATORS_COMPACT).encode('utf-8')
                )
                python_length = getsize(x)
                print(f"{x!r} -> JSON-UTF8 {json_utf8_length}, Python {python_length}")
            
                
            compare("a")  # JSON-UTF8 3, Python 50
            compare(1)  # JSON-UTF8 1, Python 28
            compare({"a": 1, "b": [2, 3, "xyz"]})  # JSON-UTF8 23, Python 464
            
        It can be quite a big overestimate, so we probably shouldn't chuck
        out requests just because the Python size looks too big.  

        """  # noqa
        if max_length is None:
            return False  # no maximum; not too long
        # Fast, apt to overestimate size a bit (as above)
        length = getsize(self.request_process)

        if length <= max_length:  # test the Python length
            # Because the Python length is an overestimate of the JSON, if that
            # is not more than the max, we can stop.
            return False  # not too long

        # The Python size is too long. So now we recalculate using the slow but
        # accurate way.
        length = utf8len(to_json_str(self.request_process))

        # Is it too long?
        return length > max_length

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
                    headers=self.HTTP_HEADERS,
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
                       may_fail: bool = False) -> Optional[JsonObjectType]:
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
            assert isinstance(json_response, dict)
            return json_response
        except json.decoder.JSONDecodeError:
            log.error("Reply was not JSON")
            raise
        except AssertionError:
            log.error("Reply was JSON but not a JSON object (dict)")
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

        status = json_get_int(json_response, NKeys.STATUS)
        if not HttpStatus.is_good_answer(status):
            errors = json_get_array(json_response, NKeys.ERRORS)
            for err in errors:
                log.error(f"Error received: {err!r}")
            raise HTTPError(f"Response status was: {status}")
        self._remote_processors_full_info = json_response[NKeys.PROCESSORS]
        self._remote_processors_available = [
            proc[NKeys.NAME] for proc in self._remote_processors_full_info
        ]
        return self._remote_processors_available

    def set_cloud_processor_info(self) -> None:
        self.get_remote_processors()
        for processor in self.requested_processors.values():
            for proc_dict in self._remote_processors_full_info:
                # This is a bit messy, but I wasn't sure how to do it otherwise
                processor.set_procinfo_if_correct(proc_dict)

    def add_processor(self, procname: str, procversion: str) -> None:
        """
        Add a remote processor to the list of processors that we will request
        results from.

        Args:
            procname: name of processor on the server
            procversion: version of processor on the server
        """
        remote_processors_available = self.get_remote_processors()
        if procname not in remote_processors_available:
            log.warning(f"Unknown processor, skipping {procname}")
        else:
            info = {NKeys.NAME: procname}
            if procversion:
                info[NKeys.VERSION] = procversion
            self.request_process[NKeys.ARGS][NKeys.PROCESSORS].append(info)

    def get_confirmed_processors(self):
        confirmed = []  # type: List[Cloud]
        for processor in self.requested_processors.values():
            if processor.available_remotely:
                confirmed.append(processor)
        return confirmed

    def add_all_processors(self) -> None:
        """
        Add all user-specified remote processors to the list of processors
        that we will request results from.
        """
        for processor in self.get_confirmed_processors():
            self.add_processor(processor.procname, processor.procversion)

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
        content_key = NKeys.CONTENT  # local copy for fractional speedup
        old_content = copy(args[content_key])
        args[content_key].append(new_content)
        max_length = self._cloudcfg.max_content_length
        # Slow -- is there a way to get length without having to serialize?
        # At least -- do it only once (forgiveness not permission, etc.).
        if self.process_request_too_long(max_length):
            # Too long. Restore the previous state!
            args[content_key] = old_content
            return False
        # Success.
        return True

    def send_process_request(self, queue: bool,
                             cookies: CookieJar = None,
                             include_text_in_reply: bool = True) -> None:
        """
        Sends a request to the server to process the text we have stored.

        Args:
            queue:
                queue the request for back-end processing (rather than waiting
                for an immediate reply)?
            cookies:
                optional :class:`http.cookiejar.CookieJar`
            include_text_in_reply:
                should the server include the source text in the reply?
        """
        self._ratelimited_send_process_request(
            queue=queue,
            cookies=cookies,
            include_text_in_reply=include_text_in_reply
        )

    def _internal_send_process_request(
            self,
            queue: bool,
            cookies: CookieJar = None,
            include_text_in_reply: bool = True) -> None:
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
        self.request_process[NKeys.ARGS][NKeys.INCLUDE_TEXT] = include_text_in_reply  # noqa
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

    def try_fetch(self, cookies: CookieJar = None) -> Optional[JsonObjectType]:
        """
        Tries to fetch the response from the server. Assumes queued mode.
        Returns the JSON response.
        """
        return self._ratelimited_try_fetch(cookies=cookies)

    def _internal_try_fetch(self, cookies: CookieJar = None) \
            -> Optional[JsonObjectType]:
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
        # todo: ... should it? We're sending to an NLPRP server, so it should?

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
        # todo: ... should it? We're sending to an NLPRP server, so it should?

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
        For GATE remote processors, get a map from annotation types to
        tablenames and also annotation type returned to what the user wants
        to call it in the database.

        Args:
            processor: which GATE processor to find the mapping for?

        Returns:
            a dictionary mapping annotation types to tableanmes, and
            a dictionary mapping annotaion types to
            :class:`crate_anon.nlp_manager.output_user_config.OutputUserConfig`
            for the purpose of renaming keys

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

    @staticmethod
    def get_nlp_values_internal(
            processor_data: Dict[str, Any],
            processor: Cloud,
            metadata: Dict[str, Any]) -> Generator[Tuple[
                str, Dict[str, Any], str], None, None]:
        """
        Get result values from processed data from a CRATE server-side.

        Args:
            processor_data: nlprp results for one processor
            processor: the remote CRATE processor used
            metadata:
                the metadata for a particular document - it would have been
                sent with the document and the server would have sent it back

        Yields ``(output_tablename, formatted_result, processor_name)``.

        """
        # procname = self.requested_processors[processor]
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {processor} failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
            return
        for result in processor_data[NKeys.RESULTS]:
            result.update(metadata)
            yield result, processor

    def get_nlp_values_gate(
            self,
            processor_data: Dict[str, Any],
            processor: Cloud,
            metadata: Dict[str, Any],
            text: str = "") -> Generator[Tuple[
                Dict[str, Any], Cloud], None, None]:
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

        Yields ``(output_tablename, formatted_result, processor_name)``.
        """  # noqa
        type_to_tablename, outputtypemap = self.get_tablename_map(
            processor.procname)
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {processor.procname} failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
                # in some cases the GATE 'errors' value was a string rather
                # than a list - will check if still applies
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
            formatted_result.update(metadata)
            # Return procname as well, so we find the right database
            yield formatted_result, processor

    def get_nlp_values(self) -> Generator[Tuple[Dict[str, Any], Cloud],
                                          None, None]:
        """
        Yields ``(tablename, results, processorname)`` for each set of results.
        """
        # Method should only be called if we already have the nlp data
        assert self.nlp_data, ("Method 'get_nlp_values' must only be called "
                               "after nlp_data is obtained")
        for result in self.nlp_data[NKeys.RESULTS]:
            metadata = result[NKeys.METADATA]
            text = result.get(NKeys.TEXT)
            for processor_data in result[NKeys.PROCESSORS]:
                name = processor_data[NKeys.NAME]
                version = processor_data[NKeys.VERSION]
                # is_default_version = processor_data[NKeys.IS_DEFAULT_VERSION]
                # processor = self.get_proc_by_name_version(name, version)
                try:
                    processor = self.requested_processors[(name, version)]
                except KeyError:
                    # if is_default_version:
                    try:
                        processor = self.requested_processors.get(
                            (name, None))
                    except KeyError:
                        log.error(f"Server returned processor {name} "
                                  "version {version}, but this processor "
                                  "was not requested.")
                        raise
                    # else:
                    #     raise err(f"Server returned processor {name} "
                    #                "version {version}, but this processor "
                    #                "was not requested.")
                if processor.format == NlpDefValues.FORMAT_GATE:
                    for t, r, p in self.get_nlp_values_gate(processor_data,
                                                            processor,
                                                            metadata,
                                                            text):
                        yield t, r, p
                else:
                    for r, p in self.get_nlp_values_internal(
                            processor_data, processor, metadata):
                        yield r, p

    def process_all(self) -> None:
        """
        Puts the NLP data into the database. Very similar to
        :meth:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser.process`,
        but deals with all relevant processors at once.
        """
        nlpname = self._nlpdef.get_name()

        for nlp_values, processor in self.get_nlp_values():
            nlp_values[FN_NLPDEF] = nlpname
            session = processor.get_session()
            sqla_table = processor.get_table(processor.tablename)
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
