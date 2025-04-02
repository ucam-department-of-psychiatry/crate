"""
crate_anon/nlp_manager/cloud_request.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

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
from sqlalchemy.exc import DatabaseError

from cardinal_pythonlib.compression import gzip_string
from cardinal_pythonlib.rate_limiting import rate_limited
from cardinal_pythonlib.json.typing_helpers import (
    JsonArrayType,
    JsonObjectType,
    JsonValueType,
)
from cardinal_pythonlib.dicts import (
    rename_keys_in_dict,
    set_null_values_in_dict,
)
from cardinal_pythonlib.httpconst import HttpStatus
from cardinal_pythonlib.timing import MultiTimerContext, timer
from requests import post, Response
from requests.exceptions import HTTPError, RequestException
from semantic_version import Version
from urllib3.exceptions import NewConnectionError

from crate_anon.common.constants import (
    JSON_INDENT,
    JSON_SEPARATORS_COMPACT,
    NoneType,
)
from crate_anon.common.memsize import getsize
from crate_anon.common.stringfunc import does_text_contain_word_chars
from crate_anon.nlp_manager.cloud_parser import Cloud
from crate_anon.nlp_manager.constants import (
    FN_NLPDEF,
    FN_SRCPKSTR,
    FN_SRCPKVAL,
    FN_WHEN_FETCHED,
    GateFieldNames,
    GateResultKeys,
    NlpConfigPrefixes,
    NlpDefValues,
    full_sectionname,
)
from crate_anon.nlp_manager.models import FN_SRCHASH
from crate_anon.nlp_manager.nlp_definition import NlpDefinition

from crate_anon.nlprp.api import (
    json_get_array,
    json_get_int,
    make_nlprp_dict,
    make_nlprp_request,
    nlprp_datetime_to_datetime_utc_no_tzinfo,
)
from crate_anon.nlprp.constants import (
    NlprpCommands,
    NlprpKeys,
    NlprpValues,
    NlprpVersions,
)
from crate_anon.nlp_webserver.server_processor import ServerProcessor

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
    return len(text.encode("utf-8"))


def to_json_str(json_structure: JsonValueType) -> str:
    """
    Converts a Python object to a JSON string.
    """
    return json.dumps(
        json_structure, default=str, separators=JSON_SEPARATORS_COMPACT
    )
    # This needs 'default=str' to deal with non-JSON-serializable
    # objects that may occur, such as datetimes in the metadata.


def report_processor_errors(processor_data: Dict[str, Any]) -> None:
    """
    Should only be called if there has been an error. Reports the error(s) to
    the log.
    """
    name = processor_data[NlprpKeys.NAME]
    version = processor_data[NlprpKeys.VERSION]
    error_messages = "\n".join(
        f"{error[NlprpKeys.CODE]} - {error[NlprpKeys.MESSAGE]}: "
        f"{error[NlprpKeys.DESCRIPTION]}"
        for error in processor_data[NlprpKeys.ERRORS]
    )
    log.error(
        f"Processor {name!r} (version {version}) failed for this "
        f"document. Errors:\n{error_messages}"
    )


def extract_nlprp_top_level_results(nlp_data: JsonObjectType) -> List:
    """
    Checks that the top-level NLP response contains an appropriate "results"
    object, or raises KeyError or ValueError.

    Returns the list result, which is a list of results per document.
    """
    try:
        docresultlist = nlp_data[NlprpKeys.RESULTS]
    except KeyError:
        raise KeyError(
            "Top-level response does not contain key "
            f"{NlprpKeys.RESULTS!r}: {nlp_data!r}"
        )
    if not isinstance(docresultlist, list):
        raise ValueError(
            f"{NlprpKeys.RESULTS!r} value is not a list: {docresultlist!r}"
        )
    return docresultlist


def parse_nlprp_docresult_metadata(
    docresult: JsonObjectType,
) -> Tuple[Dict[str, Any], Optional[int], Optional[str], str]:
    """
    Check that this NLPRP document result validly contains metadata, and that
    metadata contains things we always send. Extract key components. Provide
    helpful error message on failure.

    Returns:
        tuple (metadata, pkval, pkstr, srchhash)

    """
    try:
        metadata = docresult[NlprpKeys.METADATA]
    except KeyError:
        raise KeyError(
            "Document result does not contain key "
            f"{NlprpKeys.METADATA!r}: {docresult!r}"
        )
    if not isinstance(metadata, dict):
        # ... expected type because that's what we sent; see add_text()
        raise KeyError(f"Document result metadata is not a dict: {metadata!r}")

    try:
        pkval = metadata[FN_SRCPKVAL]
    except KeyError:
        raise KeyError(
            "Document metadata does not contain key "
            f"{FN_SRCPKVAL!r}: {metadata!r}"
        )
    if not isinstance(pkval, (int, NoneType)):
        # ... expected type because that's what we sent; see add_text()
        raise KeyError(
            f"Document result metadata {FN_SRCPKVAL!r} is not null or int: "
            f"{pkval!r}"
        )

    try:
        pkstr = metadata[FN_SRCPKSTR]
    except KeyError:
        raise KeyError(
            "Document metadata does not contain key "
            f"{FN_SRCPKSTR!r}: {metadata!r}"
        )
    if not isinstance(pkstr, (str, NoneType)):
        raise KeyError(
            f"Document result metadata {FN_SRCPKVAL!r} is not null or str: "
            f"{pkstr!r}"
        )

    if pkval is None and pkstr is None:
        raise ValueError(
            f"In document result, both {FN_SRCPKVAL!r} and "
            f"{FN_SRCPKSTR!r} are null"
        )

    try:
        srchash = metadata[FN_SRCHASH]
    except KeyError:
        raise KeyError(
            "Document metadata does not contain key "
            f"{FN_SRCPKSTR!r}: {metadata!r}"
        )
    if not isinstance(srchash, str):
        raise KeyError(
            f"Document result metadata {FN_SRCPKSTR!r} is not str: "
            f"{srchash!r}"
        )

    return metadata, pkval, pkstr, srchash


def extract_processor_data_list(
    docresult: JsonObjectType,
) -> List[JsonObjectType]:
    """
    Check and extract a list of per-processor results from a single-document
    NLPRP result.
    """
    try:
        processor_data_list = docresult[NlprpKeys.PROCESSORS]
    except KeyError:
        raise KeyError(
            "Document result does not contain key "
            f"{NlprpKeys.PROCESSORS!r}: {docresult!r}"
        )
    if not isinstance(processor_data_list, list):
        raise ValueError(
            f"Document result's {NlprpKeys.PROCESSORS!r} element is not a "
            f"list: {processor_data_list!r}"
        )
    return processor_data_list


def parse_per_processor_data(processor_data: Dict[str, Any]) -> Tuple:
    """
    Return a tuple of mandatory results from NLPRP per-processor data, or raise
    KeyError.
    """
    if not isinstance(processor_data, dict):
        raise ValueError(f"Processor result is not a dict: {processor_data!r}")

    try:
        name = processor_data[NlprpKeys.NAME]
    except KeyError:
        raise KeyError(
            "Processor result does not contain key "
            f"{NlprpKeys.NAME!r}: {processor_data!r}"
        )

    try:
        version = processor_data[NlprpKeys.VERSION]
    except KeyError:
        raise KeyError(
            "Processor result does not contain key "
            f"{NlprpKeys.VERSION!r}: {processor_data!r}"
        )

    is_default_version = processor_data.get(NlprpKeys.IS_DEFAULT_VERSION, True)

    try:
        success = processor_data[NlprpKeys.SUCCESS]
    except KeyError:
        raise KeyError(
            "Processor result does not contain key "
            f"{NlprpKeys.SUCCESS!r}: {processor_data!r}"
        )

    try:
        processor_results = processor_data[NlprpKeys.RESULTS]
    except KeyError:
        raise KeyError(
            "Processor result does not contain key "
            f"{NlprpKeys.RESULTS!r}: {processor_data!r}"
        )

    return name, version, is_default_version, success, processor_results


# =============================================================================
# Exceptions
# =============================================================================


class RecordNotPrintable(Exception):
    pass


class RecordsPerRequestExceeded(Exception):
    pass


class RequestTooLong(Exception):
    pass


# =============================================================================
# CloudRequest
# =============================================================================


class CloudRequest:
    """
    Class to send requests to the cloud processors and process the results.
    """

    # Set up standard information for all requests
    HTTP_HEADERS = {"charset": "utf-8", "Content-Type": "application/json"}

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    def __init__(
        self,
        nlpdef: NlpDefinition,
        debug_post_request: bool = False,
        debug_post_response: bool = False,
    ) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        """
        self._nlpdef = nlpdef
        self._cloudcfg = nlpdef.get_cloud_config_or_raise()
        self._nlpdef_sectionname = full_sectionname(
            NlpConfigPrefixes.NLPDEF, self._nlpdef.name
        )
        self._auth = (self._cloudcfg.username, self._cloudcfg.password)
        self._post = self._internal_post

        self.cookies = None  # type: Optional[CookieJar]
        self._debug_post_request = debug_post_request
        self._debug_post_response = debug_post_response

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

    def _internal_post(
        self, request_json: str, may_fail: bool = None
    ) -> Optional[Response]:
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
                if self._debug_post_request:
                    formatted_request = json.dumps(
                        json.loads(request_json), indent=JSON_INDENT
                    )
                    log.debug(
                        f"Sending to {self._cloudcfg.url} :\n"
                        f"{formatted_request}"
                    )
                response = post(
                    url=self._cloudcfg.url,
                    data=data,
                    auth=self._auth,
                    headers=headers,
                    cookies=self.cookies,
                    verify=self._cloudcfg.verify_ssl,
                )
                if self._debug_post_response:
                    try:
                        formatted_response = json.dumps(
                            response.json(), indent=JSON_INDENT
                        )
                    except (AttributeError, json.decoder.JSONDecodeError):
                        formatted_response = ""
                    log.debug(
                        f"Received from {self._cloudcfg.url} :\n"
                        f"{response}\n"
                        f"{formatted_response}"
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

    def _post_get_json(
        self, request_json: str, may_fail: bool = False
    ) -> Optional[JsonObjectType]:
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

    def __init__(self, nlpdef: NlpDefinition, **kwargs) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        """
        super().__init__(nlpdef=nlpdef, **kwargs)

    def get_remote_processors(self) -> List[ServerProcessor]:
        """
        Returns the list of available processors from the remote. If that list
        has not already been fetched, or unless it was pre-specified upon
        construction, fetch it from the server.
        """
        # Make request
        list_procs_request = make_nlprp_dict()
        list_procs_request[NlprpKeys.COMMAND] = NlprpCommands.LIST_PROCESSORS
        request_json = to_json_str(list_procs_request)

        # Send request, get response
        json_response = self._post_get_json(request_json, may_fail=False)

        status = json_get_int(json_response, NlprpKeys.STATUS)
        if not HttpStatus.is_good_answer(status):
            errors = json_get_array(json_response, NlprpKeys.ERRORS)
            for err in errors:
                log.error(f"Error received: {err!r}")
            raise HTTPError(f"Response status was: {status}")

        processors = []  # type: List[ServerProcessor]
        try:
            proclist = json_response[
                NlprpKeys.PROCESSORS
            ]  # type: JsonArrayType
        except KeyError:
            raise KeyError(
                f"Server did not provide key {NlprpKeys.PROCESSORS!r} in its "
                f"response: {json_response!r}"
            )
        if not isinstance(proclist, list):
            raise ValueError(
                f"Server's value of {NlprpKeys.PROCESSORS!r} is not a list: "
                f"{proclist!r}"
            )
        for procinfo in proclist:
            if not isinstance(procinfo, dict):
                raise ValueError(
                    f"Server's procinfo object not a dict: {procinfo!r}"
                )
            # Any of the following may raise KeyError if missing:
            try:
                proc = ServerProcessor(
                    # Mandatory:
                    name=procinfo[NlprpKeys.NAME],
                    title=procinfo[NlprpKeys.TITLE],
                    version=procinfo[NlprpKeys.VERSION],
                    is_default_version=procinfo.get(
                        NlprpKeys.IS_DEFAULT_VERSION, True
                    ),
                    description=procinfo[NlprpKeys.DESCRIPTION],
                    # Optional:
                    schema_type=procinfo.get(
                        NlprpKeys.SCHEMA_TYPE, NlprpValues.UNKNOWN
                    ),
                    sql_dialect=procinfo.get(NlprpKeys.SQL_DIALECT, ""),
                    tabular_schema=procinfo.get(NlprpKeys.TABULAR_SCHEMA),
                )
            except KeyError:
                log.critical(
                    "NLPRP server's processor information is missing a "
                    "required field"
                )
                raise
            processors.append(proc)
        return processors


# =============================================================================
# CloudRequestProcess
# =============================================================================


class CloudRequestProcess(CloudRequest):
    """
    Request to process text.
    """

    def __init__(
        self,
        crinfo: "CloudRunInfo" = None,
        nlpdef: NlpDefinition = None,
        commit: bool = False,
        client_job_id: str = None,
        **kwargs,
    ) -> None:
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
        super().__init__(nlpdef=nlpdef, **kwargs)
        self._crinfo = crinfo
        self._commit = commit
        self._fetched = False
        self._client_job_id = client_job_id or ""
        # How many records have been added to this particular request?
        self.number_of_records = 0

        # Set up processing request
        self._request_process = make_nlprp_dict()
        self._request_process[NlprpKeys.COMMAND] = NlprpCommands.PROCESS
        self._request_process[NlprpKeys.ARGS] = {
            NlprpKeys.PROCESSORS: [],  # type: List[str]
            NlprpKeys.QUEUE: True,
            NlprpKeys.CLIENT_JOB_ID: self._client_job_id,
            NlprpKeys.INCLUDE_TEXT: False,
            NlprpKeys.CONTENT: [],  # type: List[str]
        }
        # Set up fetch_from_queue request
        self._fetch_request = make_nlprp_dict()
        self._fetch_request[NlprpKeys.COMMAND] = NlprpCommands.FETCH_FROM_QUEUE

        self.nlp_data = None  # type: Optional[JsonObjectType]
        # ... the JSON response
        self.queue_id = None  # type: Optional[str]

        self.request_failed = False

        # Of the form:
        #     {(procname, version): 'Cloud' object}
        self.requested_processors = (
            self._cloudcfg.remote_processors
        )  # type: Dict[Tuple[str, Optional[str]], Cloud]

        if crinfo:
            self._add_all_processors_to_request()  # may raise

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

        """  # noqa: E501
        if not max_length:  # None or 0
            return False  # no maximum; not too long
        # Fast, apt to overestimate size a bit (as above)
        if self._cloudcfg.test_length_function_speed:
            length = getsize(self._request_process, assume_none_denied=True)

            if length <= max_length:  # test the Python length
                # Because the Python length is an overestimate of the JSON, if
                # that is not more than the max, we can stop.
                return False  # not too long

        # The Python size is too long. So now we recalculate using the slow but
        # accurate way.
        length = utf8len(to_json_str(self._request_process))

        # Is it too long?
        return length > max_length

    def _add_processor_to_request(
        self, procname: str, procversion: str
    ) -> None:
        """
        Add a remote processor to the list of processors that we will request
        results from.

        Args:
            procname: name of processor on the server
            procversion: version of processor on the server
        """
        info = {NlprpKeys.NAME: procname}
        if procversion:
            info[NlprpKeys.VERSION] = procversion
        self._request_process[NlprpKeys.ARGS][NlprpKeys.PROCESSORS].append(
            info
        )

    def _add_all_processors_to_request(self) -> None:
        """
        Adds all requested processors.
        """
        bad = []  # type: List[str]
        for name_version, cloudproc in self.requested_processors.items():
            name = name_version[0]
            version = name_version[1]
            if cloudproc.available_remotely:
                self._add_processor_to_request(name, version)
            else:
                bad.append(f"- {name!r} (version {version})")
        if bad:
            raise RuntimeError(
                f"The following NLP processors are not available from the "
                f"NLPRP server at {self._crinfo.cloudcfg.url!r}:\n"
                + "\n".join(bad)
            )

    def add_text(self, text: str, metadata: Dict[str, Any]) -> None:
        """
        Adds text for analysis to the NLP request, with associated metadata.

        Tests the size of the request if the text and metadata was added, then
        adds it if it doesn't go over the size limit and there are word
        characters in the text. Also checks if we've reached the maximum
        records per request.

        Args:
            text: the text
            metadata: the metadata (which we expect to get back later)

        Raises:
            - :exc:`RecordNotPrintable` if the record contains no printable
              characters
            - :exc:`RecordsPerRequestExceeded` if the request has exceeded the
              maximum number of records per request
            - :exc:`RequestTooLong` if the request has exceeded the maximum
              length
        """
        if not does_text_contain_word_chars(text):
            raise RecordNotPrintable

        self.number_of_records += 1
        if self.number_of_records > self._cloudcfg.max_records_per_request:
            raise RecordsPerRequestExceeded

        new_content = {NlprpKeys.METADATA: metadata, NlprpKeys.TEXT: text}
        # Add all the identifying information.
        args = self._request_process[NlprpKeys.ARGS]
        content_key = NlprpKeys.CONTENT  # local copy for fractional speedup
        old_content = copy(args[content_key])
        args[content_key].append(new_content)
        max_length = self._cloudcfg.max_content_length
        # Slow -- is there a way to get length without having to serialize?
        # At least -- do it only once (forgiveness not permission, etc.).
        if self._process_request_too_long(max_length):
            # log.warning("too long!")
            # Too long. Restore the previous state!
            args[content_key] = old_content
            raise RequestTooLong

    def send_process_request(
        self,
        queue: bool,
        cookies: CookieJar = None,
        include_text_in_reply: bool = True,
    ) -> None:
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
        if not self._request_process[NlprpKeys.ARGS][NlprpKeys.CONTENT]:
            log.warning("Request empty - not sending.")
            return

        # Create request
        if cookies:
            self.cookies = cookies
        self._request_process[NlprpKeys.ARGS][NlprpKeys.QUEUE] = queue
        self._request_process[NlprpKeys.ARGS][
            NlprpKeys.INCLUDE_TEXT
        ] = include_text_in_reply
        request_json = to_json_str(self._request_process)

        # Send request; get response
        json_response = self._post_get_json(request_json)

        status = json_response[NlprpKeys.STATUS]
        if queue and status == HttpStatus.ACCEPTED:
            self.queue_id = json_response[NlprpKeys.QUEUE_ID]
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

    def _try_fetch(
        self, cookies: CookieJar = None
    ) -> Optional[JsonObjectType]:
        """
        Tries to fetch the response from the server. Assumes queued mode.
        Returns the JSON response.
        """
        # Create request
        if cookies:
            self.cookies = cookies
        self._fetch_request[NlprpKeys.ARGS] = {
            NlprpKeys.QUEUE_ID: self.queue_id
        }
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
        status = json_response[NlprpKeys.STATUS]
        pending_use_202 = (
            Version(json_response[NlprpKeys.VERSION])
            >= NlprpVersions.FETCH_Q_PENDING_RETURNS_202
        )
        if status == HttpStatus.OK:
            self.nlp_data = json_response
            self._fetched = True
            return True
        elif not pending_use_202 and status == HttpStatus.PROCESSING:
            # Old server version returning 102 (Processing) (deprecated).
            return False
        elif pending_use_202 and status == HttpStatus.ACCEPTED:
            # Newer server version returning 202 (Accepted).
            return False
        elif status == HttpStatus.NOT_FOUND:
            # print(json_response)
            log.error(
                f"Got HTTP status code {HttpStatus.NOT_FOUND} - "
                f"queue_id {self.queue_id} does not exist"
            )
            return False
        else:
            log.error(
                f"Got HTTP status code {status} for queue_id {self.queue_id}."
            )
            return False

    # -------------------------------------------------------------------------
    # Results handling
    # -------------------------------------------------------------------------

    @staticmethod
    def gen_nlp_values_generic_single_table(
        processor: Cloud,
        tablename: str,
        rows: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        column_renames: Dict[str, str] = None,
    ) -> Generator[Tuple[str, Dict[str, Any], Cloud], None, None]:
        """
        Get result values from processed data, where the results object is a
        list of rows (each row in dictionary format), all for a single table,
        such as from a remote CRATE server.

        Success should have been pre-verified.

        Args:
            processor:
                The processor object.
            tablename:
                The table name to use.
            rows:
                List of NLPRP results for one processor. Each result represents
                a row of a table and is in dictionary format.
            metadata:
                The metadata for a particular document - it would have been
                sent with the document and the server would have sent it back.
            column_renames:
                Column renames to apply.

        Yields ``(output_tablename, formatted_result, processor)``.

        """
        column_renames = column_renames or {}
        for row in rows:
            rename_keys_in_dict(row, column_renames)
            row.update(metadata)
            yield tablename, row, processor

    @staticmethod
    def gen_nlp_values_gate(
        processor: Cloud,
        processor_results: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        text: str = "",
    ) -> Generator[Tuple[str, Dict[str, Any], Cloud], None, None]:
        """
        Generates row values from processed GATE data.

        Success should have been pre-verified.

        Args:
            processor:
                The processor object:
            processor_results:
                A list of dictionaries (originally from JSON), each
                representing a row in a table, and each expected to have this
                format:

                .. code-block:: none

                    {
                        'set': set the results belong to (e.g. 'Medication'),
                        'type': annotation type,
                        'start': start index,
                        'end': end index,
                        'features': {
                            a dictionary of features, e.g. having keys 'drug',
                            'frequency', etc., with corresponding values
                        }
                    }

            metadata:
                The metadata for a particular document - it would have been
                sent with the document and the server would have sent it back.
            text:
                The source text itself (optional).

        Yields:

            tuples ``(output_tablename, formatted_result, processor)``

        Each instance of ``formatted_result`` has this format:

        .. code-block:: none

            {
                GateFieldNames.TYPE: annotation type,
                GateFieldNames.SET: set,
                GateFieldNames.STARTPOS: start index,
                GateFieldNames.ENDPOS: end index,
                GateFieldNames.CONTENT: text fragment,
                FEATURE1: VALUE1,
                FEATURE2: VALUE2,
                ...
            }
        """
        for row in processor_results:
            # Assuming each row says what annotation type it is (annotation
            # type is stored as lower case):
            annottype = row[GateResultKeys.TYPE].lower()
            features = row[GateResultKeys.FEATURES]
            start = row[GateResultKeys.START]
            end = row[GateResultKeys.END]
            formatted_result = {
                GateFieldNames.TYPE: annottype,
                GateFieldNames.SET: row[GateResultKeys.SET],
                GateFieldNames.STARTPOS: start,
                GateFieldNames.ENDPOS: end,
                GateFieldNames.CONTENT: text[start:end] if text else "",
            }
            formatted_result.update(features)
            c = processor.get_otconf_from_type(annottype)
            rename_keys_in_dict(formatted_result, c.renames)
            set_null_values_in_dict(formatted_result, c.null_literals)
            formatted_result.update(metadata)
            tablename = processor.get_tablename_from_type(annottype)
            yield tablename, formatted_result, processor

    def gen_nlp_values(
        self,
    ) -> Generator[Tuple[str, Dict[str, Any], Cloud], None, None]:
        """
        Process response data that we have already obtained from the server,
        generating individual NLP results.

        Yields:
             ``(tablename, result, processor)`` for each result.
             The ``tablename`` value is the actual destination database table.

        Raises:
            :exc:`KeyError` if an unexpected processor turned up in the results
        """
        # Method should only be called if we already have the nlp data
        assert self.nlp_data, (
            "Method 'get_nlp_values' must only be called "
            "after nlp_data is obtained"
        )
        docresultlist = extract_nlprp_top_level_results(self.nlp_data)
        for docresult in docresultlist:
            metadata, _, _, _ = parse_nlprp_docresult_metadata(docresult)
            text = docresult.get(NlprpKeys.TEXT)
            processor_data_list = extract_processor_data_list(docresult)
            for processor_data in processor_data_list:
                # Details of the server processor that has responded:
                (
                    name,
                    version,
                    is_default_version,
                    success,
                    processor_results,
                ) = parse_per_processor_data(processor_data)

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Check that the processor was one we asked for.
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                try:
                    # Retrieve the Python object corresponding to the server
                    # processor that has responded:
                    processor = self.requested_processors[(name, version)]
                except KeyError:
                    # We did not request this processor name/version.
                    failmsg = (
                        f"Server returned processor {name} version {version}, "
                        f"but this processor was not requested."
                    )  # we may use this message
                    if not is_default_version:
                        # The server's processor is not the default version, so
                        # we couldn't have obtained it by asking without a
                        # version number.
                        raise KeyError(failmsg)
                    try:
                        # Did we ask for this processor by name without caring
                        # about its version number, and obtain it that way (as
                        # default version)?
                        processor = self.requested_processors.get((name, None))
                    except KeyError:
                        # No.
                        raise KeyError(failmsg)

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # OK; we're happy with the processor. Was it happy?
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                if not success:
                    report_processor_errors(processor_data)
                    return

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # All well. Process the results.
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # See nlprp.rst, <nlprp_format_of_per_processor_results>.
                if isinstance(processor_results, dict):
                    # MULTI-TABLE FORMAT.
                    # This is a dictionary mapping tables to row lists.
                    if not processor.is_tabular():
                        raise RuntimeError(
                            f"Unsupported: processor {name!r} is returning "
                            f"multi-table results but hasn't provided a "
                            f"table schema"
                        )
                    tnames = processor.get_tabular_schema_tablenames()
                    for remote_tablename, rows in processor_results.items():
                        if remote_tablename not in tnames:
                            raise ValueError(
                                f"For processor {name!r}, data provided for "
                                f"table {remote_tablename!r}, but this was "
                                "not in the schema"
                            )
                        dest_tablename = processor.get_tablename_from_type(
                            remote_tablename
                        )
                        yield from self.gen_nlp_values_generic_single_table(
                            processor=processor,
                            tablename=dest_tablename,
                            rows=rows,
                            metadata=metadata,
                            column_renames=processor.get_otconf_from_type(
                                remote_tablename
                            ).renames,
                        )
                elif isinstance(processor_results, list):
                    # SINGLE TABLE FORMAT.
                    # This is a list of rows, where each row should be a
                    # dictionary mapping column names to values.
                    if processor.format == NlpDefValues.FORMAT_GATE:
                        # We have special knowledge of the "traditional" GATE
                        # format. The sub-function will work out the table
                        # name(s).
                        yield from self.gen_nlp_values_gate(
                            processor=processor,
                            processor_results=processor_results,
                            metadata=metadata,
                            text=text,
                        )
                    else:
                        # Potentially valid whether or not there is a
                        # tabular_schema. The results object is a generic list
                        # of column_name/value dictionaries.
                        if processor.is_tabular():
                            # Only valid here if there is a SINGLE table in
                            # the tabular_schema.
                            tnames = processor.get_tabular_schema_tablenames()
                            if len(tnames) != 1:
                                raise ValueError(
                                    f"Processor {name!r} returned results in "
                                    "list format, but this is only valid for "
                                    "a single table; its tables are "
                                    f"{tnames!r}"
                                )
                            remote_tablename = tnames[0]
                        else:
                            # We use the FIRST defined table name.
                            remote_tablename = processor.get_first_tablename()
                        dest_tablename = processor.get_tablename_from_type(
                            remote_tablename
                        )
                        yield from self.gen_nlp_values_generic_single_table(
                            processor=processor,
                            tablename=dest_tablename,
                            rows=processor_results,
                            metadata=metadata,
                            column_renames=processor.get_otconf_from_type(
                                remote_tablename
                            ).renames,
                        )
                else:
                    raise ValueError(
                        f"For processor {name!r}, bad results format: "
                        f"{processor_results!r}"
                    )

    # @do_cprofile
    def process_all(self) -> None:
        """
        Puts the NLP data into the database. Very similar to
        :meth:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser.process`,
        but deals with all relevant processors at once.
        """
        nlpname = self._nlpdef.name

        sessions = []

        for tablename, nlp_values, processor in self.gen_nlp_values():
            nlp_values[FN_NLPDEF] = nlpname
            session = processor.dest_session
            if session not in sessions:
                sessions.append(session)
            sqla_table = processor.get_table(tablename)
            column_names = [c.name for c in sqla_table.columns]
            # Convert string datetime back into datetime, using UTC
            for key in nlp_values:
                if key == FN_WHEN_FETCHED:
                    nlp_values[key] = nlprp_datetime_to_datetime_utc_no_tzinfo(
                        nlp_values[key]
                    )
            final_values = {
                k: v for k, v in nlp_values.items() if k in column_names
            }
            insertquery = sqla_table.insert().values(final_values)
            try:
                with MultiTimerContext(timer, TIMING_INSERT):
                    session.execute(insertquery)
            except DatabaseError as e:
                log.error(e)
                # ... but proceed.
            self._nlpdef.notify_transaction(
                session,
                n_rows=1,
                n_bytes=sys.getsizeof(final_values),
                force_commit=self._commit,
            )
        for session in sessions:
            session.commit()


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
        show_request = make_nlprp_request(command=NlprpCommands.SHOW_QUEUE)
        request_json = to_json_str(show_request)
        json_response = self._post_get_json(request_json, may_fail=False)

        status = json_response[NlprpKeys.STATUS]
        if status == HttpStatus.OK:
            try:
                queue = json_response[NlprpKeys.QUEUE]
            except KeyError:
                log.error(f"Response did not contain key {NlprpKeys.QUEUE!r}.")
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
            command_args={NlprpKeys.DELETE_ALL: True},
        )
        request_json = to_json_str(delete_request)
        response = self._post(request_json, may_fail=False)
        # The GATE server-side doesn't send back JSON for this
        # todo: ... should it? We're sending to an NLPRP server, so it should?

        status = response.status_code
        if status == HttpStatus.NOT_FOUND:
            log.warning(
                "Queued request(s) not found. May have been cancelled "
                "already."
            )
        elif status != HttpStatus.OK and status != HttpStatus.NO_CONTENT:
            raise HTTPError(f"Response status was: {status}")

    def delete_from_queue(self, queue_ids: List[str]) -> None:
        """
        Delete pending requests from the server's queue for queue_ids
        specified.
        """
        delete_request = make_nlprp_request(
            command=NlprpCommands.DELETE_FROM_QUEUE,
            command_args={NlprpKeys.QUEUE_IDS: queue_ids},
        )
        request_json = to_json_str(delete_request)
        response = self._post(request_json, may_fail=False)
        # ... not (always) a JSON response?
        # todo: ... should it? We're sending to an NLPRP server, so it should?

        status = response.status_code
        if status == HttpStatus.NOT_FOUND:
            log.warning(
                "Queued request(s) not found. May have been cancelled "
                "already."
            )
        elif status != HttpStatus.OK and status != HttpStatus.NO_CONTENT:
            raise HTTPError(f"Response status was: {status}")
        self.cookies = response.cookies
