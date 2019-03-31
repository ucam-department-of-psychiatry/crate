#!/usr/bin/env python

r"""
crate_anon/nlp_web/views.py

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
"""

import datetime
import json
from typing import Any, Dict, List
import uuid

from celery.result import AsyncResult
from pyramid.view import view_config, view_defaults
from pyramid.request import Request
from pyramid.response import Response
from sqlalchemy import and_
import transaction

from crate_anon.nlp_web.security import (
    check_password,
    get_auth_credentials,
    encrypt_password,
)
from crate_anon.nlprp.constants import (
    NlprpCommands,
    NlprpKeys as NKeys, 
    NlprpValues,
)
from crate_anon.nlprp.version import NLPRP_VERSION_STRING
from crate_anon.nlp_web.manage_users import get_users
from crate_anon.nlp_web.models import DBSession, Document, DocProcRequest
from crate_anon.nlp_web.procs import Processor
from crate_anon.nlp_web.constants import (
    GATE_BASE_URL,
    SERVER_NAME,
    SERVER_VERSION,
)
from crate_anon.nlp_web.tasks import (
    app,
    process_nlp_text,
    process_nlp_text_immediate,
)


class Error(object):
    """
    Represents an HTTP (and NLPRP) error.
    """
    def __init__(self,
                 http_status: int,
                 code: int,
                 message: str,
                 description: str) -> None:
        self.http_status = http_status
        self.code = code
        self.message = message
        self.description = description


BAD_REQUEST = Error(
    400, 400, "Bad request", "Request was malformed")
UNAUTHORIZED = Error(
    401, 401, "Unauthorized",
    "The username/password combination given is incorrect")


@view_defaults(renderer='json')
class NlpWebViews(object):
    def __init__(self, request: Request) -> None:
        self.request = request
        # Assign this later so we can return error to client if problem
        self.body = None
        # Get username and password
        self.credentials = get_auth_credentials(self.request)
        # Assign these later after authentication
        self.username = None
        self.password = None

    @staticmethod
    def create_response(status: int,
                        extra_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a JSON HTTP response with some standard information for a given
        HTTP status and extra information to add to the response.
        """
        response_dict = {
            NKeys.STATUS: status,
            NKeys.PROTOCOL: {
                NKeys.NAME: NlprpValues.NLPRP_PROTOCOL_NAME,
                NKeys.VERSION: NLPRP_VERSION_STRING
            }, 
            NKeys.SERVER_INFO: {
                NKeys.NAME: SERVER_NAME,
                NKeys.VERSION: SERVER_VERSION
            }
        }
        response_dict.update(extra_info)
        return response_dict

    def create_error_response(self, error: Error,
                              description: str = None) -> Dict[str, Any]:
        """
        Returns an HTTP response for a given error and description of the error
        """
        error_info = {
            NKeys.ERRORS: {
                NKeys.CODE: error.code,
                NKeys.MESSAGE: error.message,
                NKeys.DESCRIPTION: description or error.description
            }
        }
        return self.create_response(error.http_status, error_info)

    def key_missing_error(self, key: str = "",
                          is_args: bool = False) -> Dict[str, Any]:
        """
        Returns a '400: Bad Request' error response stating that a key is
        missing from 'args' in the request, or the key 'args' itself is missing
        """
        error = BAD_REQUEST
        self.request.response.status = error.http_status
        if is_args:
            description = "Request did not contain top-level key 'args'"
        else:
            description = "Args did not contain key '{}'".format(key)
        return self.create_error_response(error, description)

    @view_config(route_name='index')
    def index(self) -> Response:
        """
        The main function. Authenticates user and checks the request is not
        malformed, then calls the function relating to the command specified
        by the user.
        """
        # Authenticate user
        if self.credentials is None:
            error = BAD_REQUEST
            # Put status in headers
            self.request.response.status = error.http_status
            description = (
                "Credentials were absent or not in the correct format")
            # noinspection PyTypeChecker
            return self.create_error_response(error, description)
        # See if the user exists
        users = get_users()
        username = self.credentials.username
        try:
            hashed_pw = users[username]
        except KeyError:
            error = UNAUTHORIZED
            self.request.response.status = error.http_status
            # noinspection PyTypeChecker
            return self.create_error_response(error)
        # Check if password is correct
        pw = self.credentials.password
        # pw = 'testpass'
        if check_password(pw, hashed_pw):
            self.username = username
            self.password = pw
        else:
            error = UNAUTHORIZED
            self.request.response.status = error.http_status
            # noinspection PyTypeChecker
            return self.create_error_response(error)
        # Get JSON from request if it is in this from, otherwise return
        # error message
        try:
            body = self.request.json
        except json.decoder.JSONDecodeError:
            error = BAD_REQUEST
            self.request.response.status = error.http_status
            description = "Request body was absent or not in JSON format"
            # noinspection PyTypeChecker
            return self.create_error_response(error, description)
        self.body = body
        command = self.body[NKeys.COMMAND]
        if command == NlprpCommands.LIST_PROCESSORS:
            # noinspection PyTypeChecker
            return self.list_processors()
        elif command == NlprpCommands.PROCESS:
            if not self.body[NKeys.ARGS][NKeys.QUEUE]:
                # noinspection PyTypeChecker
                return self.process_now()
            else:
                # noinspection PyTypeChecker
                return self.put_in_queue()
        elif command == NlprpCommands.SHOW_QUEUE:
            # noinspection PyTypeChecker
            return self.show_queue()
        elif command == NlprpCommands.FETCH_FROM_QUEUE:
            # noinspection PyTypeChecker
            return self.fetch_from_queue()
        elif command == NlprpCommands.DELETE_FROM_QUEUE:
            # noinspection PyTypeChecker
            return self.delete_from_queue()

    def list_processors(self) -> Dict[str, Any]:
        """
        Returns an HTTP response listing the available NLP processors.
        """
        self.request.response.status = 200
        return self.create_response(
            status=200,
            extra_info={
                NKeys.PROCESSORS: [
                    proc.dict for proc in Processor.processors.values()
                ]
            }
        )

    def process_now(self) -> Dict[str, Any]:
        """
        Processes the text supplied by the user immediately, without putting
        it in the queue.
        """
        try:
            args = self.body[NKeys.ARGS]
        except KeyError:
            return self.key_missing_error(is_args=True)
        try:
            content = args[NKeys.CONTENT]
        except KeyError:
            return self.key_missing_error(key=NKeys.CONTENT)
        try:
            processors = args[NKeys.PROCESSORS]
        except KeyError:
            return self.key_missing_error(key=NKeys.PROCESSORS)
        include_text = self.body.get(NKeys.INCLUDE_TEXT, False)
        response_info = {
            NKeys.CLIENT_JOB_ID: self.body.get(NKeys.CLIENT_JOB_ID, ""),
            NKeys.RESULTS: [None] * len(content)  # type: List[Dict[str, Any]]
        }
        for i, document in enumerate(content):
            metadata = document[NKeys.METADATA]
            text = document[NKeys.TEXT]
            processor_data = []  # so we can modify this easily later on
            if include_text:
                response_info[NKeys.RESULTS][i] = {
                    NKeys.METADATA: metadata,
                    NKeys.PROCESSORS: processor_data,
                    NKeys.TEXT: text
                }
            else:
                response_info[NKeys.RESULTS][i] = {
                    NKeys.METADATA: metadata,
                    NKeys.PROCESSORS: processor_data
                }
            for processor in processors:
                proc_obj = None
                for proc in Processor.processors.values():
                    if NKeys.VERSION in processor:
                        if (proc.name == processor[NKeys.NAME]
                                and proc.version == processor[NKeys.VERSION]):
                            proc_obj = proc
                            break
                    else:
                        if (proc.name == processor[NKeys.NAME]
                                and proc.is_default_version):
                            proc_obj = proc
                            break
                if not proc_obj:
                    error = BAD_REQUEST
                    self.request.response.status = error.http_status
                    description = (
                        "Processor {} does not exist in the version "
                        "specified".format(processor[NKeys.NAME])
                    )
                    return self.create_error_response(error, description)
                # Send the text off for processing
                # processor_id = proc_obj.processor_id
                result = process_nlp_text_immediate(
                    text=text,
                    url=GATE_BASE_URL,
                    processor=proc_obj,
                    username=self.username,
                    password=self.password
                )
                proctitle = proc_obj.title
                success, processed_text, errcode, errmsg, time = result
                proc_dict = {
                    NKeys.NAME: proc_obj.name,
                    NKeys.TITLE: proctitle,
                    NKeys.VERSION: proc_obj.version,
                    NKeys.RESULTS: processed_text,
                    NKeys.SUCCESS: success
                }
                if not success:
                    proc_dict[NKeys.ERRORS] = [{
                        NKeys.CODE: errcode,
                        NKeys.MESSAGE: errmsg
                    }]

                # try:
                #     json_response = response.json()
                # except json.decoder.JSONDecodeError:
                #     success = False
                # if processed_text.status_code != 200:  # will success always be 200?  # noqa
                #     success = False
                # else:
                #     success = True
                    # See https://cloud.gate.ac.uk/info/help/online-api.html
                    # for format of response from processor
                    # entities = processed_text['entities']
                    # for annottype, values in entities.items():
                    #     for features in values:
                    #         # Add annotation type, start position and end position  # noqa
                    #         # and remove 'indices' - the rest of 'features' should  # noqa
                    #         # just be actual features
                    #         features['_type'] = annottype
                    #         start, end = features['indices']
                    #         features['_start'] = start
                    #         features['_end'] = end
                    #         del features['indices']
                    #         proc_dict['results'].append(features)
                    # ABOVE IS INCORRECT FORMAT
                    # CORRECTION: Above actually was correct format, but dealt
                    # with in 'tasks'
                # proc_dict[NKeys.SUCCESS] = success

                processor_data.append(proc_dict)
        self.request.response.status = 200
        return self.create_response(status=200, extra_info=response_info)

    def put_in_queue(self) -> Dict[str, Any]:
        """
        Puts the document-processor pairs specified by the user into a celery
        queue to be processed.
        """
        try:
            args = self.body[NKeys.ARGS]
        except KeyError:
            return self.key_missing_error(is_args=True)
        try:
            content = args[NKeys.CONTENT]
        except KeyError:
            return self.key_missing_error(key=NKeys.CONTENT)
        try:
            processors = args[NKeys.PROCESSORS]
        except KeyError:
            return self.key_missing_error(key=NKeys.PROCESSORS)
        include_text = self.body.get(NKeys.INCLUDE_TEXT, False)
        # Generate unique queue_id for whole client request
        queue_id = str(uuid.uuid4())
        # Encrypt password using reversible encryption for passing to the
        # processors
        crypt_pass = encrypt_password(self.password)
        # We must pass the password as a string to the task because it won;t
        # let us pass a bytes object
        crypt_pass = crypt_pass.decode()
        for document in content:
            # print(document[NKeys.METADATA]['brcid'])
            doc_id = str(uuid.uuid4())
            metadata = json.dumps(document.get(NKeys.METADATA, ""))
            try:
                doctext = document[NKeys.TEXT]
            except KeyError:
                error = BAD_REQUEST
                self.request.response.status = error.http_status
                description = "Missing key {!r} in {!r}".format(
                    NKeys.TEXT, NKeys.CONTENT)
                return self.create_error_response(error, description)
            result_ids = []  # result ids for all procs for this doc
            proc_ids = []
            for processor in processors:
                proc_obj = None
                for proc in Processor.processors.values():
                    if NKeys.VERSION in processor:
                        if (proc.name == processor[NKeys.NAME]
                                and proc.version == processor[NKeys.VERSION]):
                            proc_obj = proc
                            break
                    else:
                        if (proc.name == processor[NKeys.NAME]
                                and proc.is_default_version):
                            proc_obj = proc
                            break
                if not proc_obj:
                    error = BAD_REQUEST
                    self.request.response.status = error.http_status
                    description = (
                        "Processor {} does not exist in the version "
                        "specified".format(processor[NKeys.NAME])
                    )
                    return self.create_error_response(error, description)
                docprocreq_id = str(uuid.uuid4())
                processor_id = proc_obj.processor_id
                docprocreq = DocProcRequest(
                    docprocrequest_id=docprocreq_id,
                    document_id=doc_id,
                    doctext=doctext,
                    processor_id=processor_id
                )
                proc_ids.append(processor_id)
                # Could put 'with transaction.manager' outside loop so
                # only commit once
                with transaction.manager:
                    DBSession.add(docprocreq)
                result = process_nlp_text.delay(
                    docprocrequest_id=docprocreq_id,
                    url=GATE_BASE_URL,
                    username=self.username,
                    crypt_pass=crypt_pass
                )
                result_ids.append(result.id)
                # Get the signature of the task. Have to be *really* careful
                # about remembering the order here
                # docproc_tasks.append(process_nlp_text.s(
                #     docprocrequest_id=docprocreq_id,
                #     url=URL,
                #     username=self.username,
                #     password=self.password
                # ))
            # if include_text not in (True, False):
            #     error = BAD_REQUEST
            #     self.request.response.status = error.http_status
            #     description = "'include_text' must be boolean"
            #     return self.create_error_response(error, description)
            doc = Document(
                document_id=doc_id,
                doctext=doctext,
                client_job_id=self.body.get(NKeys.CLIENT_JOB_ID, ""),
                queue_id=queue_id,
                username=self.username,
                processor_ids=json.dumps(proc_ids),
                client_metadata=metadata,
                result_ids=json.dumps(result_ids),
                include_text=include_text
            )
            with transaction.manager:
                DBSession.add(doc)
        # Put all tasks in queue and get the job's id
        # job = group(docproc_tasks)
        # result = job.apply_async()
        # with transaction.manager:
        #     for doc in docs:
        #         doc.result_id = result.id
        #         DBSession.add(doc)
        # Don't need this as using transaction manager:
        # Actually, apparantly we do
        # transaction.commit()

        status = 202  # accepted
        self.request.response.status = status
        response_info = {NKeys.QUEUE_ID: queue_id}
        return self.create_response(status=status, extra_info=response_info)

    def fetch_from_queue(self) -> Dict[str, Any]:
        """
        Fetches requests for all document-processor pairs for the queue_id
        supplied by the user.
        """
        try:
            args = self.body[NKeys.ARGS]
        except KeyError:
            return self.key_missing_error(is_args=True)
        try:
            # Don't know how trailing whitespace got introduced at the client
            # end but it was there - hence '.strip()'
            queue_id = args[NKeys.QUEUE_ID].strip()
        except KeyError:
            return self.key_missing_error(key=NKeys.QUEUE_ID)
        query = DBSession.query(Document).filter(
            and_(Document.queue_id == queue_id,
                 Document.username == self.username)
        )
        document_rows = query.all()
        if document_rows:
            response_info = {
                NKeys.CLIENT_JOB_ID: document_rows[0].client_job_id,
                NKeys.RESULTS: [None] * len(document_rows)  # type: List[Dict[str, Any]]  # noqa
            }
            include_text = document_rows[0].include_text
        else:
            response_info = {
                NKeys.CLIENT_JOB_ID: "",
                NKeys.RESULTS: []
            }
            self.request.response.status = 200
            return self.create_response(status=200, extra_info=response_info)
        for j, doc in enumerate(document_rows):
            metadata = json.loads(doc.client_metadata)
            processor_data = []  # data for *all* the processors for this doc
            proc_ids = json.loads(doc.processor_ids)
            if include_text:
                response_info[NKeys.RESULTS][j] = {
                    NKeys.METADATA: metadata,
                    NKeys.PROCESSORS: processor_data,
                    NKeys.TEXT: doc.doctext
                }
            else:
                response_info[NKeys.RESULTS][j] = {
                    NKeys.METADATA: metadata,
                    NKeys.PROCESSORS: processor_data
                }
            result_ids = json.loads(doc.result_ids)
            # More efficient than append? Should we do this wherever possible?
            results = [None] * len(result_ids)  # type: List[AsyncResult]
            for i, result_id in enumerate(result_ids):
                # get result for this doc-proc pair
                result = AsyncResult(id=result_id, app=app)
                if not result.ready():
                    # Can't return JSON with 102
                    self.request.response.status = 200
                    return self.create_response(102, {})
                results[i] = result
            # Unfortunately we have to loop twice to avoid doing a lot for
            # nothing if it turns out a later result is not ready
            for i, result in enumerate(results):
                # Split on the last occurance of '_' - procs will be in correct
                # order
                procname, sep, procversion = proc_ids[i].rpartition("_")
                if not procversion:
                    for proc in Processor.processors.values():
                        if proc.name == procname and proc.is_default_version:
                            procversion = proc.version
                            break
                proctitle = None
                for proc in Processor.processors.values():
                    if (proc.name == procname
                            and proc.version == procversion):
                        proctitle = proc.title
                        break
                if not proctitle:
                    error = BAD_REQUEST
                    self.request.response.status = error.http_status
                    description = (
                        "Processor '{}', version {} does not exist".format(
                            procname, procversion))
                    return self.create_error_response(error, description)

                success, processed_text, errcode, errmsg, time = result.get()
                result.forget()
                proc_dict = {
                    NKeys.NAME: procname,
                    NKeys.TITLE: proctitle,
                    NKeys.VERSION: procversion,
                    NKeys.RESULTS: processed_text,
                    NKeys.SUCCESS: success
                }
                if not success:
                    proc_dict[NKeys.ERRORS] = [{
                        NKeys.CODE: errcode,
                        NKeys.MESSAGE: errmsg
                    }]
                    # See https://cloud.gate.ac.uk/info/help/online-api.html
                    # for format of response from processor
                    # entities = json_response['entities']
                    # for annottype, values in entities.items():
                    #     for features in values:
                    #         # Add annotation type, start position and end position  # noqa
                    #         # and remove 'indices' - the rest of 'features' should  # noqa
                    #         # just be actual features
                    #         features['_type'] = annottype
                    #         start, end = features['indices']
                    #         features['_start'] = start
                    #         features['_end'] = end
                    #         del features['indices']
                    #         proc_dict['results'].append(features)
                    # ABOVE IS INCORRECT FORMAT
                processor_data.append(proc_dict)
            # TEST PROPERLY!
            subquery = DBSession.query(DocProcRequest).filter(
                DocProcRequest.document_id == doc.document_id)
            DBSession.query(Document).filter(
                and_(Document.document_id == doc.document_id,
                     ~subquery.exists())
            ).delete(synchronize_session='fetch')
        transaction.commit()
        self.request.response.status = 200
        return self.create_response(status=200, extra_info=response_info)

    def show_queue(self) -> Dict[str, Any]:
        """
        Finds the queue entries associated with the client, optionally
        restricted to one client job id.
        """
        client_job_id = self.body[NKeys.ARGS].get(NKeys.CLIENT_JOB_ID, "")
        if not client_job_id:
            query = DBSession.query(Document).filter(
                Document.username == self.username
            )
        else:
            query = DBSession.query(Document).filter(
                and_(Document.username == self.username,
                     Document.client_job_id == client_job_id)
            )
        records = query.all()
        queue = []
        queue_ids = set([x.queue_id for x in records])
        for queue_id in queue_ids:
            busy = False
            qid_recs = [x for x in records if x.queue_id == queue_id]
            max_time = datetime.datetime.min
            for record in qid_recs:
                result_ids = json.loads(record.result_ids)
                for result_id in result_ids:
                    result = AsyncResult(id=result_id, app=app)
                    if not result.ready():
                        busy = True
                        break
                    else:
                        # First 3 are throwaways
                        x, y, z, time = result.get()
                        max_time = max(max_time, time)
            queue.append({
                NKeys.QUEUE_ID: queue_id,
                NKeys.CLIENT_JOB_ID: client_job_id,
                NKeys.STATUS: NlprpValues.BUSY if busy else NlprpValues.READY,
                NKeys.DATETIME_SUBMITTED: qid_recs[0].datetime_submitted,
                NKeys.DATETIME_COMPLETED: None if busy else max_time
            })
        return self.create_response(status=200,
                                    extra_info={NKeys.QUEUE: queue})

    def delete_from_queue(self) -> Dict[str, Any]:
        """
        Deletes from the queue all entries specified by the client.
        """
        args = self.body.get(NKeys.ARGS)
        if args:
            delete_all = args.get(NKeys.DELETE_ALL)
            if delete_all:
                docs = DBSession.query(Document).filter(
                    Document.username == self.username
                ).all()
            else:
                docs = []
                client_job_ids = args.get(NKeys.CLIENT_JOB_IDS)
                for cj_id in client_job_ids:
                    docs.append(DBSession.query(Document).filter(
                        and_(Document.username == self.username,
                             Document.client_job_id == cj_id)
                    ).all())
                queue_ids = args.get(NKeys.QUEUE_IDS)
                for q_id in queue_ids:
                    # Clumsy way of making sure we don't have same doc twice
                    docs.append(DBSession.query(Document).filter(
                        and_(
                            Document.username == self.username,
                            Document.queue_id == q_id,
                            Document.client_job_id not in [
                                x.client_job_id for x in docs
                            ]
                        )
                    ).all())
            for doc in docs:
                result_ids = json.loads(doc.result_ids)
                # Remove from celery queue
                for res_id in result_ids:
                    result = AsyncResult(id=res_id, app=app)
                    result.revoke()
                # Remove from docprocrequests
                dpr_query = DBSession.query(DocProcRequest).filter(
                    DocProcRequest.document_id == doc.document_id)
                DBSession.delete(dpr_query)
            # Remove from documents
            DBSession.delete(docs)
            transaction.commit()
            # Return response
            self.request.response.status = 200
            return self.create_response(status=200, extra_info={})
        else:
            return self.key_missing_error(is_args=True)
