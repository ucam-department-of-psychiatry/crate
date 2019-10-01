#!/usr/bin/env python
# crate_anon/nlp_manager/cloud_request.py

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
from typing import Any, Dict, List, Tuple, Generator, Optional, TYPE_CHECKING
import time

from cardinal_pythonlib.compression import gzip_string
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

from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
from crate_anon.common.memsize import getsize
from crate_anon.common.stringfunc import does_text_contain_word_chars
from crate_anon.nlp_manager.cloud_parser import Cloud
from crate_anon.nlp_manager.constants import (
    FN_NLPDEF,
    FN_WHEN_FETCHED,
    full_sectionname,
    GateResultKeys,
    NlpConfigPrefixes,
    ProcessorConfigKeys,
    NlpDefValues,
)
from crate_anon.nlp_manager.nlp_definition import (
    NlpDefinition,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlprp.api import (
    json_get_array,
    json_get_int,
    JsonArrayType,
    JsonObjectType,
    JsonValueType,
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
from crate_anon.nlp_webserver.procs import ServerProcessor

if TYPE_CHECKING:
    from crate_anon.nlp_manager.cloud_run_info import CloudRunInfo


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

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    def __init__(self, nlpdef: NlpDefinition) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        """
        self._nlpdef = nlpdef
        self._cloudcfg = nlpdef.get_cloud_config_or_raise()
        self._nlpdef_sectionname = full_sectionname(NlpConfigPrefixes.NLPDEF,
                                                    self._nlpdef.get_name())
        self._auth = (self._cloudcfg.username, self._cloudcfg.password)
        self._post = self._internal_post

        self.cookies = None  # type: Optional[CookieJar]

    # -------------------------------------------------------------------------
    # HTTP
    # -------------------------------------------------------------------------

    @classmethod
    def set_rate_limit(cls, rate_limit_hz: int) -> None:
        """
        Creates new methods which are rate limited. Only use this once per run.

        Note that this is a classmethod and must be so; if it were
        instance-based, you could create multiple requests and each would
        individually be rate-limited, but not collectively.
        """
        if rate_limit_hz > 0:
            # Rate-limited
            cls._post = rate_limited(rate_limit_hz)(cls._internal_post)
        else:
            # No limits!
            cls._post = cls._internal_post

    def _internal_post(self, request_json: str,
                       may_fail: bool = None) -> Optional[Response]:
        """
        Submits an HTTP POST request to the remote.
        Tries up to a certain number of times.

        Notes:

        - The Python ``requests`` library automatically applies
          ``Accept-Encoding: gzip, deflate`` to outbound HTTP requests, and
          automatically gzip-decodes responses.
        - However, we have to do outbound compression manually.

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
        if self._cloudcfg.compress:
            headers = self.HTTP_HEADERS.copy()
            headers["Content-Encoding"] = "gzip"
            data = gzip_string(request_json)
        else:
            headers = self.HTTP_HEADERS
            data = request_json
        while (not success) and tries <= self._cloudcfg.max_tries:
            try:
                tries += 1
                response = post(
                    url=self._cloudcfg.url,
                    data=data,
                    auth=self._auth,
                    headers=headers,
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


# =============================================================================
# CloudRequestListProcessors
# =============================================================================

class CloudRequestListProcessors(CloudRequest):
    """
    Request to get processors from the remote.
    """

    def __init__(self, nlpdef: NlpDefinition) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        """
        super().__init__(nlpdef=nlpdef)

    def get_remote_processors(self) -> List[ServerProcessor]:
        """
        Returns the list of available processors from the remote. If that list
        has not already been fetched, or unless it was pre-specified upon
        construction, fetch it from the server.
        """
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

        processors = []  # type: List[ServerProcessor]
        proclist = json_response[NKeys.PROCESSORS]  # type: JsonArrayType
        for procinfo in proclist:
            proc = ServerProcessor(
                # Mandatory:
                name=procinfo[NKeys.NAME],
                title=procinfo[NKeys.TITLE],
                version=procinfo[NKeys.VERSION],
                is_default_version=procinfo[NKeys.IS_DEFAULT_VERSION],
                description=procinfo[NKeys.DESCRIPTION],
                # Optional:
                schema_type=procinfo.get(NKeys.SCHEMA_TYPE,
                                         NlprpValues.UNKNOWN),
                sql_dialect=procinfo.get(NKeys.SQL_DIALECT, ""),
                tabular_schema=procinfo.get(NKeys.TABULAR_SCHEMA)
            )
            processors.append(proc)
        return processors


# =============================================================================
# CloudRequestProcess
# =============================================================================

class CloudRequestProcess(CloudRequest):
    """
    Request to process text.
    """

    def __init__(self,
                 crinfo: "CloudRunInfo" = None,
                 nlpdef: NlpDefinition = None,
                 commit: bool = False,
                 client_job_id: str = None) -> None:
        """
        Args:
            crinfo:
                a :class:`crate_anon.nlp_manager.cloud_run_info.CloudRunInfo`
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
            client_job_id:
                optional string used to group together results into one job.
        """
        assert nlpdef or crinfo
        if nlpdef is None:
            nlpdef = crinfo.nlpdef
        super().__init__(nlpdef=nlpdef)
        self._crinfo = crinfo
        self._commit = commit
        self._fetched = False
        self._client_job_id = client_job_id or ""

        # Set up processing request
        self._request_process = make_nlprp_dict()
        self._request_process[NKeys.COMMAND] = NlprpCommands.PROCESS
        self._request_process[NKeys.ARGS] = {
            NKeys.PROCESSORS: [],  # type: List[str]
            NKeys.QUEUE: True,
            NKeys.CLIENT_JOB_ID: self._client_job_id,
            NKeys.INCLUDE_TEXT: False,
            NKeys.CONTENT: []  # type: List[str]
        }
        # Set up fetch_from_queue request
        self._fetch_request = make_nlprp_dict()
        self._fetch_request[NKeys.COMMAND] = NlprpCommands.FETCH_FROM_QUEUE

        self.nlp_data = None  # type: Optional[JsonObjectType]  # the JSON response  # noqa
        self.queue_id = None  # type: Optional[str]

        self.request_failed = False

        # Of the form:
        #     {(procname, version): 'Cloud' object}
        self.requested_processors = self._cloudcfg.remote_processors  # type: Dict[Tuple[str, Optional[str]], Cloud]  # noqa

        if crinfo:
            self._add_all_processors_to_request()

    # -------------------------------------------------------------------------
    # Sending text to the server
    # -------------------------------------------------------------------------

    def _process_request_too_long(self, max_length: Optional[int]) -> bool:
        """
        Is the number of bytes in the outbound JSON request more than the
        permitted maximum?

        Args:
            max_length:
                the maximum length; 0 or ``None`` for no limit

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
        if not max_length:  # None or 0
            return False  # no maximum; not too long
        # Fast, apt to overestimate size a bit (as above)
        length = getsize(self._request_process)

        if length <= max_length:  # test the Python length
            # Because the Python length is an overestimate of the JSON, if that
            # is not more than the max, we can stop.
            return False  # not too long

        # The Python size is too long. So now we recalculate using the slow but
        # accurate way.
        length = utf8len(to_json_str(self._request_process))

        # Is it too long?
        return length > max_length

    def add_processor_to_request(self, procname: str, procversion: str) -> None:
        """
        Add a remote processor to the list of processors that we will request
        results from.

        Args:
            procname: name of processor on the server
            procversion: version of processor on the server
        """
        info = {NKeys.NAME: procname}
        if procversion:
            info[NKeys.VERSION] = procversion
        self._request_process[NKeys.ARGS][NKeys.PROCESSORS].append(info)

    def _add_all_processors_to_request(self) -> None:
        """
        Adds all requested processors.
        """
        for name_version, cloudproc in self.requested_processors.items():
            if cloudproc.available_remotely:
                name = name_version[0]
                version = name_version[1]
                self.add_processor_to_request(name, version)

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
            # log.warning(f"No word characters found in text: {text!r}")
            return False

        new_content = {
            NKeys.METADATA: other_values,
            NKeys.TEXT: text
        }
        # Add all the identifying information.
        args = self._request_process[NKeys.ARGS]
        content_key = NKeys.CONTENT  # local copy for fractional speedup
        old_content = copy(args[content_key])
        args[content_key].append(new_content)
        max_length = self._cloudcfg.max_content_length
        # Slow -- is there a way to get length without having to serialize?
        # At least -- do it only once (forgiveness not permission, etc.).
        if self._process_request_too_long(max_length):
            # log.warning("too long!")
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
        # Don't send off an empty request
        if not self._request_process[NKeys.ARGS][NKeys.CONTENT]:
            log.warning("Request empty - not sending.")
            return

        # Create request
        if cookies:
            self.cookies = cookies
        self._request_process[NKeys.ARGS][NKeys.QUEUE] = queue
        self._request_process[NKeys.ARGS][
            NKeys.INCLUDE_TEXT] = include_text_in_reply  # noqa
        request_json = to_json_str(self._request_process)

        # Send request; get response
        json_response = self._post_get_json(request_json)

        status = json_response[NKeys.STATUS]
        if queue and status == HttpStatus.ACCEPTED:
            self.queue_id = json_response[NKeys.QUEUE_ID]
            self._fetched = False
        elif (not queue) and status == HttpStatus.OK:
            self.nlp_data = json_response
            self._fetched = True
        else:
            log.error(f"Got HTTP status code {status}.")
            log.error(f"Response from server: {json_response}")
            if self._cloudcfg.stop_at_failure:
                raise HTTPError
            else:
                self.request_failed = True
                return

    # -------------------------------------------------------------------------
    # Queue management for processing requests
    # -------------------------------------------------------------------------

    def set_queue_id(self, queue_id: str) -> None:
        """
        Sets the queue_id. To be used when you're not actually sending a
        request this time.
        """
        self.queue_id = queue_id

    def _try_fetch(self, cookies: CookieJar = None) -> Optional[JsonObjectType]:
        """
        Tries to fetch the response from the server. Assumes queued mode.
        Returns the JSON response.
        """
        # Create request
        if cookies:
            self.cookies = cookies
        self._fetch_request[NKeys.ARGS] = {NKeys.QUEUE_ID: self.queue_id}
        request_json = to_json_str(self._fetch_request)

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
        if self._fetched:
            return False  # todo: check with FS; is that the right response?
        json_response = self._try_fetch(cookies)
        if not json_response:
            return False
        status = json_response[NKeys.STATUS]
        if status == HttpStatus.OK:
            self.nlp_data = json_response
            self._fetched = True
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

    # -------------------------------------------------------------------------
    # Results handling
    # -------------------------------------------------------------------------

    # Don't think we need this anymore?
    # def get_tablename_map(self, processor: str) \
    #         -> Tuple[Dict[str, str], Dict[str, OutputUserConfig]]:
    #     """
    #     For GATE remote processors, get a map from annotation types to
    #     tablenames and also annotation type returned to what the user wants
    #     to call it in the database.
    #
    #     Args:
    #         processor: which GATE processor to find the mapping for?
    #
    #     Returns:
    #         a dictionary mapping annotation types to tableanmes, and
    #         a dictionary mapping annotaion types to
    #         :class:`crate_anon.nlp_manager.output_user_config.OutputUserConfig`
    #         for the purpose of renaming keys
    # 
    #     """
    #     proc_section = full_sectionname(NlpConfigPrefixes.PROCESSOR, processor)
    #     typepairs = self._nlpdef.opt_strlist(
    #         proc_section, ProcessorConfigKeys.OUTPUTTYPEMAP,
    #         required=True, lower=False)
    # 
    #     outputtypemap = {}  # type: Dict[str, OutputUserConfig]
    #     type_to_tablename = {}  # type: Dict[str, str]
    #     for c in chunks(typepairs, 2):
    #         annottype = c[0]
    #         outputsection = c[1]
    #         # annottype = annottype.lower()
    #         otconfig = OutputUserConfig(self._nlpdef.get_parser(),
    #                                     outputsection)
    #         outputtypemap[annottype] = otconfig
    #         type_to_tablename[annottype] = otconfig.get_tablename()
    #
    #     return type_to_tablename, outputtypemap

    @staticmethod
    def get_nlp_values_internal(
            processor_data: Dict[str, Any],
            processor: Cloud,
            metadata: Dict[str, Any]) \
            -> Generator[Tuple[str, Dict[str, Any], str], None, None]:
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
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {processor} failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
            return
        for result in processor_data[NKeys.RESULTS]:
            result.update(metadata)
            yield result

    @staticmethod
    def get_nlp_values_gate(
            processor_data: Dict[str, Any],
            processor: Cloud,
            metadata: Dict[str, Any],
            text: str = "") \
            -> Generator[Tuple[Dict[str, Any], Cloud], None, None]:
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
        # type_to_tablename, outputtypemap = self.get_tablename_map(
        #     processor.procname)
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {processor.procname} "
                f"failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
                # in some cases the GATE 'errors' value was a string rather
                # than a list - will check if still applies
            return
        for result in processor_data[NKeys.RESULTS]:
            # Assuming each set of results says what annotation type
            # it is
            # (annotation type is stored as lower case)
            annottype = result[GateResultKeys.TYPE].lower()
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
            c = processor.get_otconf_from_type(annottype)
            rename_keys_in_dict(formatted_result, c.renames())
            set_null_values_in_dict(formatted_result, c.null_literals())
            formatted_result.update(metadata)
            tablename = processor.get_tablename_from_type(annottype)
            yield tablename, formatted_result

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
                try:
                    processor = self.requested_processors[(name, version)]
                except KeyError:
                    # if is_default_version:  # GATE doesn't send this info
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
                    for t, r in self.get_nlp_values_gate(processor_data,
                                                         processor,
                                                         metadata,
                                                         text):
                        yield t, r, processor
                else:
                    for res in self.get_nlp_values_internal(
                            processor_data, processor, metadata):
                        # For non-GATE processors ther will only be one table
                        # name
                        yield processor.tablename, res, processor

    def process_all(self) -> None:
        """
        Puts the NLP data into the database. Very similar to
        :meth:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser.process`,
        but deals with all relevant processors at once.
        """
        nlpname = self._nlpdef.get_name()

        for tablename, nlp_values, processor in self.get_nlp_values():
            nlp_values[FN_NLPDEF] = nlpname
            session = processor.get_session()
            sqla_table = processor.get_table(tablename)
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


# =============================================================================
# CloudRequestQueueManagement
# =============================================================================

class CloudRequestQueueManagement(CloudRequest):
    """
    Request to manage the queue in some way.
    """

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
