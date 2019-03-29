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

import json
import logging
import requests
import sys
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Tuple, Generator, Optional

from cardinal_pythonlib.timing import MultiTimerContext, timer

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.nlp_definition import (
    full_sectionname,
    NlpDefinition,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.dicts import (
    rename_keys_in_dict,
    set_null_values_in_dict,
)
from crate_anon.nlp_manager.constants import (
    CLOUD_URL,
    NLPRPVERSION,
    FN_NLPDEF,
)

log = logging.getLogger(__name__)

TIMING_INSERT = "CloudRequest_sql_insert"


class CloudRequest(object):
    """
    Class to send requests to the cloud processors and process the results.
    """
    # Set up standard information for all requests
    STANDARD_INFO = {
        'protocol': {
            "name": "nlprp",
            "version": NLPRPVERSION
        }
    }
    URL = CLOUD_URL
    HEADERS = {
        'charset': 'utf-8',
        'Content-Type': 'application/json'
    }

    def __init__(self,
                 nlpdef: NlpDefinition,
                 max_length: int = 0,
                 commit: bool = False,
                 client_job_id: str = None,
                 allowable_procs: Optional[List[str]] = None) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
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
        """
        self._nlpdef = nlpdef
        self._sectionname = full_sectionname("nlpdef", self._nlpdef.get_name())
        self._commit = commit
        # self._destdbs = {}  # type: Dict[str, DatabaseHolder]
        config = self._nlpdef.get_parser()
        self.username = config.get_str(section="Cloud_NLP",
                                       option="username",
                                       default="")
        self.password = config.get_str(section="Cloud_NLP",
                                       option="password",
                                       default="")
        self.auth = (self.username, self.password)
        self.fetched = False
        if client_job_id:
            self.client_job_id = client_job_id
        else:
            self.client_job_id = "test_" + str(uuid.uuid4())

        # Set up processing request
        self.request_process = deepcopy(self.STANDARD_INFO)
        self.request_process['command'] = "process"
        self.request_process['args'] = {"processors": [],
                                        "queue": True,
                                        "client_job_id": self.client_job_id,
                                        "include_text": False,
                                        "content": []}
        # Set up fetch_from_queue request
        self.fetch_request = deepcopy(self.STANDARD_INFO)
        self.fetch_request['command'] = "fetch_from_queue"

        self.allowable_procs = allowable_procs
        self.nlp_data = None
        self.queue_id = None

        # if cfgsection:
        #     self.add_processor(cfgsection)
        #     self.procnames = [cfgsection]
        #     self.cfgsection = cfgsection
        # else:
        #     self.procnames = []
        #     self.cfgsection = None

        self.procnames = []  # type: List[str]  # *** check: unused? ***************
        self.procs = {}  # type: Dict[str, str]
        self.add_all_processors()

#        if nlpdef is not None:
#            for procname in self.procnames:
#                destdb_name = nlpdef.opt_str(procname, 'destdb',
#                                             required=True)
#                self._destdbs[destdb_name] = nlpdef.get_database(destdb_name)

        self.mirror_processors = {}
        self.max_length = max_length

    @staticmethod
    def utf8len(text):
        return len(text.encode('utf-8'))

    @classmethod
    def list_processors(cls, nlpdef) -> List[str]:
        config = nlpdef.get_parser()
        username = config.get_str(section="Cloud_NLP", option="username",
                                  default="")
        password = config.get_str(section="Cloud_NLP", option="password",
                                  default="")
        auth = (username, password)
        list_procs_request = deepcopy(cls.STANDARD_INFO)
        list_procs_request['command'] = "list_processors"
        request_json = json.dumps(list_procs_request)
        # print(request_json)
        response = requests.post(cls.URL, data=request_json,
                                 auth=auth, headers=cls.HEADERS)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.warning("Reply was not JSON")
            raise
        # print(json_response)
        procs = [proc['name'] for proc in json_response['processors']]
        return procs

    def add_processor(self, processor: str) -> None:
        # Make sure we don't send request to list processors twice for
        # same request
        if self.allowable_procs is None:
            self.allowable_procs = self.list_processors()
        if processor not in self.allowable_procs:
            log.warning("Unknown processor, skipping {}".format(processor))
        else:
            self.request_process['args']['processors'].append({
                "name": processor})

    def add_all_processors(self) -> None:
        processorpairs = self._nlpdef.opt_strlist(self._sectionname,
                                                  'processors', required=True,
                                                  lower=False)
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

        new_content = {'metadata': other_values,
                       'text': text}
        # Add all the identifying information
        # Slow - is there a way to get length without having to serialize?
        if (self.max_length and
            self.utf8len(json.dumps(new_content, default=str))
                + self.utf8len(json.dumps(
                    self.request_process, default=str))) < self.max_length:
            self.request_process['args']['content'].append(new_content)
            return True
        else:
            return False

    def send_process_request(self, queue: bool) -> None:
        """
        Sends a request to the server to process the text.
        """
        self.request_process['args']['queue'] = queue
        # This needs 'default=str' to deal with non-json-serializable
        # objects such as datetimes in the metadata
        request_json = json.dumps(self.request_process, default=str)
        # print(request_json)
        # print()
        response = requests.post(self.URL, data=request_json, 
                                 auth=self.auth, headers=self.HEADERS)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.warning("Reply was not JSON")
            raise
        # print(json_response)
        if queue:
            if json_response['status'] == 202:
                self.queue_id = json_response['queue_id']
                self.fetched = False
            else:
                log.warning("Got HTTP status code "
                            "{}.".format(json_response['status']))
        else:
            status = json_response['status']
            if status == 200:
                self.nlp_data = json_response
                # print(self.nlp_data)
                # print()
                self.fetched = True
            else:
                log.error("Response status was: {}".format(status))  # CHANGE

    def set_queue_id(self, queue_id: str) -> None:
        """
        Sets the queue_id. To be used when you're not actually sending a
        request this time.
        """
        self.queue_id = queue_id

    def try_fetch(self) -> Dict[str, Any]:
        """
        Tries to fetch the response from the server. Assumes queued mode.
        Returns the json response.
        """
        self.fetch_request['args'] = {'queue_id': self.queue_id}
        request_json = json.dumps(self.fetch_request)
        response = requests.post(self.URL, data=request_json, 
                                 auth=self.auth, headers=self.HEADERS)
        try:
            json_response = response.json()
        except json.decoder.JSONDecodeError:
            log.warning("Reply was not JSON")
            raise
        return json_response

    def check_if_ready(self) -> bool:
        """
        Checks if the data is ready yet. Assumes queued mode. If the data is
        ready, collect it and return True, else return False.
        """
        if self.queue_id is None:
            log.warning("Tried to fetch from queue before sending request.")
            return False
        if self.fetched:
            return False
        json_response = self.try_fetch()
        # print(json_response)
        # print()
        status = json_response['status']
        if status == 200:
            self.nlp_data = json_response
            self.fetched = True
            return True
        elif status == 102:
            return False
        elif status == 404:
            log.error("Got HTTP status code 404 - queue_id {} deos not "
                      "exist".format(self.queue_id))
            return False
        else:
            log.error("Got HTTP status code {} for queue_id "
                      "{}.".format(status, self.queue_id))
            return False

    def get_tablename_map(self, processor: str) -> Tuple[Dict[str, str],
                                                         Dict[str,
                                                         OutputUserConfig]]:
        proc_section = full_sectionname("processor", processor)
        typepairs = self._nlpdef.opt_strlist(proc_section, 'outputtypemap',
                                             required=True, lower=False)

        outputtypemap = {}  # type: Dict[str, OutputUserConfig]
        type_to_tablename = {}  # type: Dict[str, str]
        for c in chunks(typepairs, 2):
            annottype = c[0]
            outputsection = c[1]
            annottype = annottype.lower()
            otconfig = OutputUserConfig(self._nlpdef.get_parser(),
                                        outputsection)
            outputtypemap[annottype] = otconfig
            type_to_tablename[annottype] = otconfig.get_tablename()

        return type_to_tablename, outputtypemap

    def get_nlp_values_internal(
            self,
            processor_data: Dict[str, str],
            proctype: str,
            procname: str,
            metadata: Dict[str, Any]) -> Generator[Tuple[
                str, Dict[str, Any], str], None, None]:
        tablename = self._nlpdef.opt_str(
            full_sectionname("processor", procname), 'desttable', required=True)
        for result in processor_data['results']:
            result.update(metadata)
            yield tablename, result, proctype

    def get_nlp_values_gate(
            self,
            processor_data: Dict[str, str],
            procname: str,
            metadata: Dict[str, Any]) -> Generator[Tuple[
                str, Dict[str, Any], str], None, None]:
        type_to_tablename, outputtypemap = self.get_tablename_map(
            procname)
        for result in processor_data['results']:
            # Assuming each set of results says what annotation type
            # it is
            annottype = result['_type'].lower()
            c = outputtypemap[annottype]
            rename_keys_in_dict(result, c.renames())
            set_null_values_in_dict(result, c.null_literals())
            tablename = type_to_tablename[annottype]
            result.update(metadata)
            # Return procname as well, so we find the right database
            yield tablename, result, procname

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
        for result in self.nlp_data['results']:
            metadata = result['metadata']
            for processor_data in result['processors']:
                procidentifier = processor_data['name']
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

    def get_sessions_for_all_processors(self) -> Dict[str, List[any]]:
        # If cfgsection is set then this class was instantiated for one
        # specific processor name, so there's no chance we need more than one
        # destination database ...
        # if self.cfgsection:
        #     session = self.get_session()
        #     procs_to_sessions = {self.cfgsection: [self.get_dbname(), session]}  # noqa
        # ... Otherwise we may need more than one database
        # else:
        procs_to_sessions = {}
        for procname in self.procnames:
            if procname not in procs_to_sessions:
                destdb_name = self._nlpdef.opt_str(
                    full_sectionname("processor", procname),
                    'destdb', required=True)
                procs_to_sessions[procname] = [destdb_name,
                                               self._nlpdef.get_database(
                                                   destdb_name).session]
        return procs_to_sessions

    def set_mirror_processors(
            self,
            procs: Optional[Dict[str, BaseNlpParser]] = None) -> None:
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
