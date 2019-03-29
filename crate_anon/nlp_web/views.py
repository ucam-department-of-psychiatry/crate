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
from typing import Dict, Any
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
from crate_anon.nlp_web.manage_users import get_users
from crate_anon.nlp_web.models import DBSession, Document, DocProcRequest
from crate_anon.nlp_web.procs import Processor
from crate_anon.nlp_web.constants import (
    GATE_BASE_URL,
    NLPRP_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
)
from crate_anon.nlp_web.tasks import (
    app,
    process_nlp_text,
    process_nlp_text_immediate,
)

BAD_REQUEST = {
    'status': 400,
    'code': 400,
    'message': 'Bad request',
    'default_descr': 'Request was malformed'
}
UNAUTHORIZED = {
    'status': 401,
    'code': 401,
    'message': 'Unauthorized',
    'default_descr': 'The username/password combination given is incorrect'
}


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
        response_dict = {'status': status, 'protocol': {
            'name': 'nlprp',
            'version': NLPRP_VERSION
        }, 'server_info': {
            'name': SERVER_NAME,
            'version': SERVER_VERSION
        }}
        response_dict.update(extra_info)
        return response_dict

    def create_error_response(self,
                              error: Dict[str, Any],
                              description: str) -> Dict[str, Any]:
        """
        Returns an HTTP response for a given error and description of the error
        """
        error_info = {'errors': {
            'code': error['code'],
            'message': error['message'],
            'description': description
        }}
        return self.create_response(error['status'], error_info)

    def key_missing_error(self, key: str = "",
                          is_args: bool = False) -> Dict[str, Any]:
        """
        Returns a '400: Bad Request' error response stating that a key is
        missing from 'args' in the request, or the key 'args' itself is missing
        """
        error = BAD_REQUEST
        self.request.response.status = error['status']
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
            self.request.response.status = error['status']
            description = (
                "Credentials were absent or not in the correct format")
            # noinspection PyTypeChecker
            return self.create_error_response(error, description)
        # See if the user exists
        users = get_users()
        username = self.credentials['username']
        try:
            hashed_pw = users[username]
        except KeyError:
            error = UNAUTHORIZED
            self.request.response.status = error['status']
            # noinspection PyTypeChecker
            return self.create_error_response(error, error['default_descr'])
        # Check if password is correct
        pw = self.credentials['password']
        # pw = 'testpass'
        if check_password(pw, hashed_pw):
            self.username = username
            self.password = pw
        else:
            error = UNAUTHORIZED
            self.request.response.status = error['status']
            # noinspection PyTypeChecker
            return self.create_error_response(error, error['default_descr'])
        # Get JSON from request if it is in this from, otherwise return
        # error message
        try:
            body = self.request.json
        except json.decoder.JSONDecodeError:
            error = BAD_REQUEST
            self.request.response.status = error['status']
            description = "Request body was absent or not in JSON format"
            # noinspection PyTypeChecker
            return self.create_error_response(error, description)
        self.body = body
        command = self.body['command']
        if command == 'list_processors':
            # noinspection PyTypeChecker
            return self.list_processors()
        elif command == 'process':
            if not self.body['args']['queue']:
                # noinspection PyTypeChecker
                return self.process_now()
            else:
                # noinspection PyTypeChecker
                return self.put_in_queue()
        elif command == 'show_queue':
            # noinspection PyTypeChecker
            return self.show_queue()
        elif command == 'fetch_from_queue':
            # noinspection PyTypeChecker
            return self.fetch_from_queue()
        elif command == 'delete_from_queue':
            # noinspection PyTypeChecker
            return self.delete_from_queue()

    def list_processors(self) -> Dict[str, Any]:
        """
        Returns an HTTP response listing the available NLP processors.
        """
        self.request.response.status = 200
        return self.create_response(
            status=200,
            extra_info={'processors': [
                proc.dict for proc in Processor.processors.values()]})

    def process_now(self) -> Dict[str, Any]:
        """
        Processes the text supplied by the user immediately, without putting
        it in the queue.
        """
        try:
            args = self.body['args']
        except KeyError:
            return self.key_missing_error(is_args=True)
        try:
            content = args['content']
        except KeyError:
            return self.key_missing_error(key='content')
        try:
            processors = args['processors']
        except KeyError:
            return self.key_missing_error(key='processors')
        include_text = self.body.get('include_text', False)
        response_info = {
            'client_job_id': self.body.get('client_job_id', ""),
            'results': [None]*len(content)
        }
        for i, document in enumerate(content):
            metadata = document['metadata']
            text = document['text']
            processor_data = []  # so we can modify this easily later on
            if include_text:
                response_info['results'][i] = {
                    'metadata': metadata,
                    'processors': processor_data,
                    'text': text
                }
            else:
                response_info['results'][i] = {
                    'metadata': metadata,
                    'processors': processor_data
                }
            for processor in processors:
                proc_obj = None
                for proc in Processor.processors.values():
                    if 'version' in processor:
                        if (proc.name == processor['name']
                                and proc.version == processor['version']):
                            proc_obj = proc
                            break
                    else:
                        if (proc.name == processor['name']
                                and proc.is_default_version):
                            proc_obj = proc
                            break
                if not proc_obj:
                    error = BAD_REQUEST
                    self.request.response.status = error['status']
                    description = "Processor {} does not exist \
in the version specified".format(processor['name'])
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
                    'name': proc_obj.name,
                    'title': proctitle,
                    'version': proc_obj.version,
                    'results': processed_text,
                    'success': success
                }
                if not success:
                    proc_dict['errors'] = [{
                        'code': errcode,
                        'message': errmsg
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
                # proc_dict['success'] = success

                processor_data.append(proc_dict)
        self.request.response.status = 200
        return self.create_response(status=200, extra_info=response_info)

    def put_in_queue(self) -> Dict[str, Any]:
        """
        Puts the document-processor pairs specified by the user into a celery
        queue to be processed.
        """
        try:
            args = self.body['args']
        except KeyError:
            return self.key_missing_error(is_args=True)
        try:
            content = args['content']
        except KeyError:
            return self.key_missing_error(key='content')
        try:
            processors = args['processors']
        except KeyError:
            return self.key_missing_error(key='processors')
        include_text = self.body.get('include_text', False)
        # Generate unique queue_id for whole client request
        queue_id = str(uuid.uuid4())
        # Encrypt password using reversible encryption for passing to the
        # processors
        crypt_pass = encrypt_password(self.password)
        # We must pass the password as a string to the task because it won;t
        # let us pass a bytes object
        crypt_pass = crypt_pass.decode()
        for document in content:
            # print(document['metadata']['brcid'])
            doc_id = str(uuid.uuid4())
            metadata = json.dumps(document.get('metadata', ""))
            try:
                doctext = document['text']
            except KeyError:
                error = BAD_REQUEST
                self.request.response.status = error['status']
                description = "Missing key 'text' in 'content'"
                return self.create_error_response(error, description)
            result_ids = []  # result ids for all procs for this doc
            proc_ids = []
            for processor in processors:
                proc_obj = None
                for proc in Processor.processors.values():
                    if 'version' in processor:
                        if (proc.name == processor['name']
                                and proc.version == processor['version']):
                            proc_obj = proc
                            break
                    else:
                        if (proc.name == processor['name']
                                and proc.is_default_version):
                            proc_obj = proc
                            break
                if not proc_obj:
                    error = BAD_REQUEST
                    self.request.response.status = error['status']
                    description = (
                        "Processor {} does not exist in the version "
                        "specified".format(processor['name'])
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
            #     self.request.response.status = error['status']
            #     description = "'include_text' must be boolean"
            #     return self.create_error_response(error, description)
            doc = Document(
                document_id=doc_id,
                doctext=doctext,
                client_job_id=self.body.get('client_job_id', ""),
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
        response_info = {'queue_id': queue_id}
        return self.create_response(status=status, extra_info=response_info)

    def fetch_from_queue(self) -> Dict[str, Any]:
        """
        Fetches requests for all document-processor pairs for the queue_id
        supplied by the user.
        """
        try:
            args = self.body['args']
        except KeyError:
            return self.key_missing_error(is_args=True)
        try:
            # Don't know how trailing whitespace got introduced at the client
            # end but it was there - hence '.strip()'
            queue_id = args['queue_id'].strip()
        except KeyError:
            return self.key_missing_error(key='queue_id')
        query = DBSession.query(Document).filter(
            and_(Document.queue_id == queue_id,
                 Document.username == self.username)
        )
        document_rows = query.all()
        if document_rows:
            response_info = {
                'client_job_id': document_rows[0].client_job_id,
                'results': [None]*len(document_rows)
            }
            include_text = document_rows[0].include_text
        else:
            response_info = {
                'client_job_id': "",
                'results': []
            }
            self.request.response.status = 200
            return self.create_response(status=200, extra_info=response_info)
        for j, doc in enumerate(document_rows):
            metadata = json.loads(doc.client_metadata)
            processor_data = []  # data for *all* the processors for this doc
            proc_ids = json.loads(doc.processor_ids)
            if include_text:
                response_info['results'][j] = {
                    'metadata': metadata,
                    'processors': processor_data,
                    'text': doc.doctext
                }
            else:
                response_info['results'][j] = {
                    'metadata': metadata,
                    'processors': processor_data
                }
            result_ids = json.loads(doc.result_ids)
            # More efficient than append? Should we do this wherever possible?
            results = [None]*len(result_ids)
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
                    self.request.response.status = error['status']
                    description = (
                        "Processor '{}', version {} does not exist".format(
                            procname, procversion))
                    return self.create_error_response(error, description)

                success, processed_text, errcode, errmsg, time = result.get()
                result.forget()
                proc_dict = {
                    'name': procname,
                    'title': proctitle,
                    'version': procversion,
                    'results': processed_text,
                    'success': success
                }
                if not success:
                    proc_dict['errors'] = [{
                        'code': errcode,
                        'message': errmsg
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
        client_job_id = self.body['args'].get('client_job_id', "")
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
                'queue_id': queue_id,
                'client_job_id': client_job_id,
                'status': "busy" if busy else "ready",
                'datetime_submitted': qid_recs[0].datetime_submitted,
                'datetime_completed': None if busy else max_time
            })
        return self.create_response(status=200, extra_info={'queue', queue})

    def delete_from_queue(self) -> Dict[str, Any]:
        """
        Deletes from the queue all entries specified by the client.
        """
        args = self.body.get('args')
        if args:
            delete_all = args.get('delete_all')
            if delete_all:
                docs = DBSession.query(Document).filter(
                    Document.username == self.username
                ).all()
            else:
                docs = []
                client_job_ids = args.get('client_job_ids')
                for cj_id in client_job_ids:
                    docs.append(DBSession.query(Document).filter(
                        and_(Document.username == self.username,
                             Document.client_job_id == cj_id)
                    ).all())
                queue_ids = args.get('queue_ids')
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
