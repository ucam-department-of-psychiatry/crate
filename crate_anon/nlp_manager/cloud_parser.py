#!/usr/bin/env python
# crate_anon/nlp_manager/base_cloud_parser.py

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

# todo: rationalise so that there isn't repeated code to check if reply is
#       json etc.

from copy import deepcopy
import json
import logging
import sys
# import uuid
from typing import Any, Dict, List, Tuple, Generator, Optional

from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.dicts import (
    rename_keys_in_dict,
    set_null_values_in_dict,
)
from cardinal_pythonlib.timing import MultiTimerContext, timer
import requests
from requests.exceptions import HTTPError

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.constants import FN_NLPDEF
from crate_anon.nlp_manager.nlp_definition import (
    full_sectionname,
    NlpConfigPrefixes,
    NlpDefinition,
)
from crate_anon.nlp_manager.parse_gate import (
    # FN_TYPE,
    GateConfigKeys,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlprp.api import make_nlprp_dict, make_nlprp_request
from crate_anon.nlprp.constants import (
    HttpStatus,
    NlprpCommands,
    NlprpKeys as NKeys,
)

log = logging.getLogger(__name__)

CLOUD_NLP_SECTION = "Cloud_NLP"
TIMING_INSERT = "CloudRequest_sql_insert"

START_GATE = 'start'
END_GATE = 'end'
FEATURES_GATE = 'features'
TYPE_GATE = 'type'
SET_GATE = 'set'


class CloudNlpConfigKeys(object):
    USERNAME = "username"
    PASSWORD = "password"
    PROCESSORS = "processors"
    URL = "cloud_url"
    REQUEST_DATA_DIR = "request_data_dir"
    MAX_LENGTH = "max_content_length"


class CloudRequest(object):
    """
    Class to send requests to the cloud processors and process the results.
    """
    # Set up standard information for all requests
    STANDARD_INFO = make_nlprp_dict()
    HEADERS = {
        'charset': 'utf-8',
        'Content-Type': 'application/json'
    }

    def __init__(self,
                 nlpdef: NlpDefinition,
                 url: str,
                 username: str = "",
                 password: str = "",
                 max_length: int = 0,
                 commit: bool = False,
                 client_job_id: str = None,
                 allowable_procs: Optional[List[str]] = None,
                 verify_ssl: bool = True,
                 procs_auto_add: bool = True) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            url:
                the url to send requests to
            username:
                the username for accessing cloud nlp services
            password:
                the password for accessing cloud nlp services
            max_length:
                maximum content-length of a request
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
            client_job_id:
                optional string used to group together results into one job.
            allowable_procs:
                List of processors expected to be pre-checked for validity.
                If None, the 'add_processor' method checks for validity using
                the 'list_processors' method. When doing many requests all with
                the same set of processors it is best to test validity outside
                class and specify this parameter.
            verify_ssl:
                whether to verify the ssl certificate of the server or not
            procs_auto_add:
                add_procs_automatically if not provided
        """
        self._nlpdef = nlpdef
        self._sectionname = full_sectionname(NlpConfigPrefixes.NLPDEF,
                                             self._nlpdef.get_name())
        self._commit = commit
        # self._destdbs = {}  # type: Dict[str, DatabaseHolder]
        self.url = url
        self.username = username
        self.password = password
        self.auth = (self.username, self.password)
        self.fetched = False
        self.verify_ssl = verify_ssl
        if client_job_id:
            self.client_job_id = client_job_id
        else:
            # self.client_job_id = "test_" + str(uuid.uuid4())
            self.client_job_id = ""

        # Set up processing request
        self.request_process = deepcopy(self.STANDARD_INFO)
        self.request_process[NKeys.COMMAND] = NlprpCommands.PROCESS
        self.request_process[NKeys.ARGS] = {
            NKeys.PROCESSORS: [],
            NKeys.QUEUE: True,
            NKeys.CLIENT_JOB_ID: self.client_job_id,
            NKeys.INCLUDE_TEXT: False,
            NKeys.CONTENT: []
        }
        # Set up fetch_from_queue request
        self.fetch_request = deepcopy(self.STANDARD_INFO)
        self.fetch_request[NKeys.COMMAND] = NlprpCommands.FETCH_FROM_QUEUE

        self.allowable_procs = allowable_procs
        self.nlp_data = None
        self.queue_id = None

        self.procs = {}  # type: Dict[str, str]
        if procs_auto_add:
            self.add_all_processors()

        self.mirror_processors = {}
        self.max_length = max_length
        self.cookies = None

    @staticmethod
    def utf8len(text):
        return len(text.encode('utf-8'))

    @classmethod
    def list_processors(cls,
                        url: str,
                        username: str = "",
                        password: str = "",
                        verify_ssl: bool = True) -> List[str]:
        auth = (username, password)
        list_procs_request = deepcopy(cls.STANDARD_INFO)
        list_procs_request[NKeys.COMMAND] = NlprpCommands.LIST_PROCESSORS
        request_json = json.dumps(list_procs_request)
        # print(request_json)
        response = requests.post(url, data=request_json,
                                 auth=auth, headers=cls.HEADERS,
                                 verify=verify_ssl)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.error("Reply was not JSON")
            raise
        # cls.cookies = response.cookies
        # print(json_response)
        procs = [proc[NKeys.NAME] for proc in json_response[NKeys.PROCESSORS]]
        return procs

    def add_processor(self, processor: str) -> None:
        # Make sure we don't send request to list processors twice for
        # same request
        if self.allowable_procs is None:
            self.allowable_procs = self.list_processors(
                                       self.url,
                                       self.username,
                                       self.password,
                                       verify_ssl=self.verify_ssl)
        if processor not in self.allowable_procs:
            log.warning(f"Unknown processor, skipping {processor}")
        else:
            self.request_process[NKeys.ARGS][NKeys.PROCESSORS].append({
                NKeys.NAME: processor
            })

    def add_all_processors(self) -> None:
        processorpairs = self._nlpdef.opt_strlist(
            self._sectionname, CloudNlpConfigKeys.PROCESSORS,
            required=True, lower=False)
        self.procs = {}
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
        Tests the size of the request if the text and metadata was added,
        then adds it if it doesn't go over the size limit. Returns True
        if successfully added, False if not.
        """
        # srcfield = other_values[FN_SRCFIELD]
        # pkval = other_values[FN_SRCPKVAL]
        # pkstr = other_values[FN_SRCPKSTR]
        # pk = pkstr if pkstr else pkval
        # new_values = {
        #                  "metadata": {"field": self.srcfield, "pk": pk}
        #                  "text": text
        #              }
        # self.request_process['args']['content'].append(new_values)

        new_content = {
            NKeys.METADATA: other_values,
            NKeys.TEXT: text
        }
        # Add all the identifying information
        # Slow - is there a way to get length without having to serialize?
        if ((not self.max_length) or
            self.utf8len(json.dumps(new_content, default=str))
                + self.utf8len(json.dumps(
                    self.request_process, default=str)) < self.max_length):
            self.request_process[NKeys.ARGS][NKeys.CONTENT].append(new_content)
            return True
        else:
            return False

    def send_process_request(self, queue: bool,
                             cookies: List[Any] = None) -> None:
        """
        Sends a request to the server to process the text.
        """
        # Don't send off an empty request
        if not self.request_process[NKeys.ARGS][NKeys.CONTENT]:
            log.warning("Request empty - not sending.")
            return
        self.request_process[NKeys.ARGS][NKeys.QUEUE] = queue
        # This needs 'default=str' to deal with non-json-serializable
        # objects such as datetimes in the metadata
        request_json = json.dumps(self.request_process, default=str)
        # print(request_json)
        # print()
        if not cookies:
            response = requests.post(self.url, data=request_json, 
                                     auth=self.auth, headers=self.HEADERS,
                                     verify=self.verify_ssl)
        else:
            response = requests.post(self.url, data=request_json, 
                                     auth=self.auth, headers=self.HEADERS,
                                     cookies=cookies, verify=self.verify_ssl)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.error("Reply was not JSON")
            raise
        status = json_response[NKeys.STATUS]
        # print(status)
        if queue:
            if status == HttpStatus.ACCEPTED:
                self.queue_id = json_response[NKeys.QUEUE_ID]
                self.fetched = False
                self.cookies = response.cookies
            else:
                log.error(f"Response from server: {json_response}")
                raise HTTPError(f"Got HTTP status code {status}.")
        else:
            if status == HttpStatus.OK:
                self.nlp_data = json_response
                # print(self.nlp_data)
                # print()
                self.fetched = True
                self.cookies = response.cookies
            else:
                raise HTTPError(f"Response status was: {status}")

    def set_queue_id(self, queue_id: str) -> None:
        """
        Sets the queue_id. To be used when you're not actually sending a
        request this time.
        """
        self.queue_id = queue_id

    def try_fetch(self, cookies: List[Any] = None) -> Dict[str, Any]:
        """
        Tries to fetch the response from the server. Assumes queued mode.
        Returns the json response.
        """
        self.fetch_request[NKeys.ARGS] = {NKeys.QUEUE_ID: self.queue_id}
        request_json = json.dumps(self.fetch_request)
        if not cookies:
            response = requests.post(self.url, data=request_json,
                                     auth=self.auth, headers=self.HEADERS,
                                     verify=self.verify_ssl)
        else:
            response = requests.post(self.url, data=request_json,
                                     auth=self.auth, headers=self.HEADERS,
                                     cookies=cookies, verify=self.verify_ssl)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.error("Reply was not JSON")
            raise
        self.cookies = response.cookies
        return json_response

    def check_if_ready(self, cookies: List[Any] = None) -> bool:
        """
        Checks if the data is ready yet. Assumes queued mode. If the data is
        ready, collect it and return True, else return False.
        """
        if self.queue_id is None:
            log.warning("Tried to fetch from queue before sending request.")
            return False
        if self.fetched:
            return False
        json_response = self.try_fetch(cookies)
        # print(json_response)
        # print()
        status = json_response[NKeys.STATUS]
        if status == HttpStatus.OK:
            self.nlp_data = json_response
            self.fetched = True
            return True
        elif status == HttpStatus.PROCESSING:
            return False
        elif status == HttpStatus.NOT_FOUND:
            print(json_response)
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
        dictionary as returned according to the nlprp.
        """
        show_request = make_nlprp_request(
            command=NlprpCommands.SHOW_QUEUE
        )
        request_json = json.dumps(show_request)
        response = requests.post(self.url, data=request_json,
                                 auth=self.auth, headers=self.HEADERS,
                                 verify=self.verify_ssl)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.error("Reply was not JSON")
            raise
        status = json_response[NKeys.STATUS]
        if status == HttpStatus.OK:
            try:
                queue = json_response[NKeys.QUEUE]
            except KeyError:
                log.error("Response did not contain key 'queue'.")
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
        request_json = json.dumps(delete_request)
        response = requests.post(self.url, data=request_json,
                                 auth=self.auth, headers=self.HEADERS,
                                 verify=self.verify_ssl)
        # The GATE server-side doesn't send back JSON for this
        # try:
        #     json_response = response.json()
        # except json.decoder.JSONDecodeError:
        #     log.error("Reply was not JSON")
        #     raise
        # print(json_response)
        # status = json_response[NKeys.STATUS]
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
        request_json = json.dumps(delete_request)
        response = requests.post(self.url, data=request_json,
                                 auth=self.auth, headers=self.HEADERS,
                                 verify=self.verify_ssl)
        # try:
        #     json_response = response.json()
        # except json.decoder.JSONDecodeError:
        #     log.error("Reply was not JSON")
        #     raise
        # status = json_response[NKeys.STATUS]
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
        proc_section = full_sectionname(NlpConfigPrefixes.PROCESSOR, processor)
        typepairs = self._nlpdef.opt_strlist(
            proc_section, GateConfigKeys.OUTPUTTYPEMAP,
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
        tablename = self._nlpdef.opt_str(
            full_sectionname(NlpConfigPrefixes.PROCESSOR, procname),
            'desttable', required=True)
        if not processor_data[NKeys.SUCCESS]:
            log.warning(
                f"Processor {proctype} failed for this document. Errors:")
            errors = processor_data[NKeys.ERRORS]
            for error in errors:
                log.warning(f"{error[NKeys.CODE]} - {error[NKeys.MESSAGE]}")
        for result in processor_data[NKeys.RESULTS]:
            result.update(metadata)
            yield tablename, result, proctype

    def get_nlp_values_gate(
            self,
            processor_data: Dict[str, Any],
            procname: str,
            metadata: Dict[str, Any]) -> Generator[Tuple[
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
            log.warning(f"Processor {procname} failed for this document.\n"
                        "Status: {processor_data[NKeys.STATUS]}\n"
                        "Message: {processor_data[NKeys.MESSAGE]}")
        for result in processor_data[NKeys.RESULTS]:
            # Assuming each set of results says what annotation type
            # it is
            # annottype = result[FN_TYPE].lower()
            annottype = result[TYPE_GATE]
            features = result[FEATURES_GATE]
            formatted_result = {
                '_type': annottype,
                '_set': result[SET_GATE],
                '_start': result[START_GATE],
                '_end': result[END_GATE]
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
        Yields tablename, results and processorname for each set of results.
        """
        # if not self.nlp_data:
        #     self.nlp_data = self.send_process_request()

        # Method should only be called if we already have the nlp data
        assert self.nlp_data, ("Method 'get_nlp_values' must only be called "
                               "after nlp_data is obtained")
        for result in self.nlp_data[NKeys.RESULTS]:
            metadata = result[NKeys.METADATA]
            for processor_data in result[NKeys.PROCESSORS]:
                procidentifier = processor_data[NKeys.NAME]
                mirror_proc = self.mirror_processors[procidentifier]
                if mirror_proc.get_parser_name().upper() == 'GATE':
                    for t, r, p in self.get_nlp_values_gate(processor_data,
                                                            procidentifier,
                                                            metadata):
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
                proctype = proc.get_parser_name()
                if proctype.upper() == 'GATE':
                    self.mirror_processors[proc.get_cfgsection()] = proc
                else:
                    self.mirror_processors[proctype] = proc
        else:
            for proc in self._nlpdef.get_processors():
                proctype = proc.get_parser_name()
                if proctype.upper() == 'GATE':
                    self.mirror_processors[proc.get_cfgsection()] = proc
                else:
                    self.mirror_processors[proctype] = proc

    def process_all(self) -> None:
        """
        Puts the NLP data into the database. Very similar to 'process' from
        BaseNlpParser, but deals with all relevant processors at once.
        """
        # procs_to_sessions = self.get_sessions_for_all_processors()
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
            final_values = {k: v for k, v in nlp_values.items()
                            if k in column_names}
            insertquery = sqla_table.insert().values(final_values)
            with MultiTimerContext(timer, TIMING_INSERT):
                session.execute(insertquery)
            self._nlpdef.notify_transaction(
                session, n_rows=1, n_bytes=sys.getsizeof(final_values),
                force_commit=self._commit)


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
