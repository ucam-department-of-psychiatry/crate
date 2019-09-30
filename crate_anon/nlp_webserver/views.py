#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/views.py

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

Pyramid views making up the CRATE NLPRP web server.

"""

from contextlib import contextmanager
import datetime
import logging
import json
from typing import Dict, Generator, List, Optional, Tuple, Any
import redis

from cardinal_pythonlib.sqlalchemy.core_query import fetch_all_first_values
from celery.result import AsyncResult, ResultSet
from pyramid.view import view_config, view_defaults
from pyramid.request import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import and_, ClauseElement, select
import transaction

from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
from crate_anon.nlp_webserver.security import (
    check_password,
    get_auth_credentials,
    encrypt_password,
)
# from crate_anon.common.profiling import do_cprofile
from crate_anon.nlprp.api import (
    json_get_array,
    json_get_array_of_str,
    json_get_bool,
    json_get_str,
    json_get_toplevel_args,
    json_get_value,
    JsonArrayType,
    JsonObjectType,
    JsonValueType,
    pendulum_to_nlprp_datetime,
)
from crate_anon.nlprp.constants import (
    HttpStatus,
    NlprpCommands,
    NlprpKeys as NKeys,
    NlprpValues,
)
from crate_anon.nlprp.errors import (
    BAD_REQUEST,
    INTERNAL_SERVER_ERROR,
    key_missing_error,
    NlprpError,
    mkerror,
    NOT_FOUND,
    UNAUTHORIZED,
)
from crate_anon.nlprp.version import NLPRP_VERSION_STRING
from crate_anon.nlp_webserver.manage_users import get_users
from crate_anon.nlp_webserver.models import (
    dbsession,
    Document,
    DocProcRequest,
    make_unique_id,
)
from crate_anon.nlp_webserver.procs import ServerProcessor
from crate_anon.nlp_webserver.constants import (
    SERVER_NAME,
    SERVER_VERSION,
    NlpServerConfigKeys,
)
from crate_anon.nlp_webserver.tasks import (
    celery_app,
    process_nlp_text,
    process_nlp_text_immediate,
    TaskSession,
    start_task_session,
)
from crate_anon.nlp_webserver.settings import SETTINGS

log = logging.getLogger(__name__)


# =============================================================================
# Debugging settings
# =============================================================================

DEBUG_SHOW_REQUESTS = False


if DEBUG_SHOW_REQUESTS:
    log.warning("Debugging options enabled! Turn off for production.")


# =============================================================================
# Constants
# =============================================================================

COOKIE_SESSION_TOKEN = 'session_token'

DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379  # https://redis.io/topics/quickstart
DEFAULT_REDIS_DB_NUMBER = 0  # https://redis.io/commands/select

REDIS_HOST = SETTINGS.get(NlpServerConfigKeys.REDIS_HOST, DEFAULT_REDIS_HOST)
REDIS_PORT = SETTINGS.get(NlpServerConfigKeys.REDIS_PORT, DEFAULT_REDIS_PORT)
REDIS_DB_NUMBER = SETTINGS.get(NlpServerConfigKeys.REDIS_DB_NUMBER,
                               DEFAULT_REDIS_DB_NUMBER)
REDIS_PASSWORD = SETTINGS.get(NlpServerConfigKeys.REDIS_PASSWORD, None)
# If the redis server doesn't require a password, it's fine to pass
# 'password=None' to StrictRedis.

REDIS_SESSIONS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT,
                                   db=REDIS_DB_NUMBER,
                                   password=REDIS_PASSWORD)

SESSION_TOKEN_EXPIRY_S = 300


# =============================================================================
# SQLAlchemy context
# =============================================================================

@contextmanager
def sqla_transaction_commit():
    try:
        yield
        transaction.commit()
    except SQLAlchemyError as e:
        log.critical(f"SQLAlchemy error: {e}")
        dbsession.rollback()
        raise INTERNAL_SERVER_ERROR


# =============================================================================
# NlprpProcessRequest
# =============================================================================

class NlprpProcessRequest(object):
    """
    Represents an NLPRP :ref:`process <nlprp_process>` command. Takes the
    request JSON, and offers efficient views on it.

    Uses the global :class:`crate_anon.nlp_server.procs.Processors` class to
    find processors.
    """
    def __init__(self, nlprp_request: JsonObjectType) -> None:
        """
        Args:
            nlprp_request: dictionary from the (entire) JSON NLPRP request

        Raises:
            :exc:`NlprpError` for malformed requests
        """
        self.nlprp_request = nlprp_request

        args = json_get_toplevel_args(nlprp_request)

        # The processors being requested. We fetch all of them now, so they
        # can be iterated through fast for each document.
        requested_processors = json_get_array(args, NKeys.PROCESSORS,
                                              required=True)
        self.processors = [ServerProcessor.get_processor_nlprp(d)
                           for d in requested_processors]

        # Queue?
        self.queue = json_get_bool(args, NKeys.QUEUE, default=False)

        # Client job ID
        self.client_job_id = json_get_str(args, NKeys.CLIENT_JOB_ID,
                                          default="")

        # Include the source text in the reply?
        self.include_text = json_get_bool(args, NKeys.INCLUDE_TEXT)

        # Content: list of objects (each with text and metadata)
        self.content = json_get_array(args, NKeys.CONTENT, required=True)

    def processor_ids(self) -> List[str]:
        """
        Return the IDs of all processors.
        """
        return [p.processor_id for p in self.processors]

    def processor_ids_jsonstr(self) -> str:
        """
        Returns the IDs of all processors as a string of JSON-encoded IDs.
        """
        return json.dumps(self.processor_ids(),
                          separators=JSON_SEPARATORS_COMPACT)

    def gen_text_metadataobj(self) -> Generator[Tuple[str, JsonValueType],
                                                None, None]:
        """
        Generates text and metadata pairs from the request, with the metadata
        in JSON object (Python dictionary) format.

        Yields:
            tuple: ``(text, metadata)``, as above
        """
        for document in self.content:
            text = json_get_str(document, NKeys.TEXT, required=True)
            metadata = json_get_value(document, NKeys.METADATA,
                                      default=None, required=False)
            yield text, metadata

    def gen_text_metadatastr(self) -> Generator[Tuple[str, str],
                                                None, None]:
        """
        Generates text and metadata pairs from the request, with the metadata
        in string (serialized JSON) format.

        Yields:
            tuple: ``(text, metadata)``, as above
        """
        try:
            for document in self.content:
                text = json_get_str(document, NKeys.TEXT, required=True)
                metadata = json_get_value(document, NKeys.METADATA,
                                          default=None, required=False)
                metadata_str = json.dumps(metadata,
                                          separators=JSON_SEPARATORS_COMPACT)
                yield text, metadata_str
        except KeyError:
            raise key_missing_error(key=NKeys.TEXT)


# =============================================================================
# NlpWebViews
# =============================================================================

@view_defaults(renderer='json')  # all views can now return JsonObjectType
class NlpWebViews(object):
    """
    Class to provide HTTP views (via Pyramid) for our NLPRP server.
    """

    # -------------------------------------------------------------------------
    # Constructor
    # -------------------------------------------------------------------------

    def __init__(self, request: Request) -> None:
        """
        Args:
            request: a :class:`pyramid.request.Request`
        """
        self.request = request
        # Assign this later so we can return error to client if problem
        self.body = None  # type: Optional[JsonObjectType]
        # Get username and password
        self.credentials = get_auth_credentials(self.request)
        # Assign these later after authentication
        self.username = None  # type: Optional[str]
        self.password = None  # type: Optional[str]
        # Start database sessions
        dbsession()
        start_task_session()

    # -------------------------------------------------------------------------
    # Responses and errors
    # -------------------------------------------------------------------------

    def set_http_response_status(self, status: int) -> None:
        """
        Sets the HTTP status code for our response.

        Args:
            status: HTTP status code
        """
        self.request.response.status = status

    def create_response(self,
                        status: int,
                        extra_info: JsonObjectType = None) -> JsonObjectType:
        """
        Returns a JSON HTTP response with some standard information for a given
        HTTP status and extra information to add to the response.

        Ensures the HTTP status matches the NLPRP JSON status.
        """
        # Put status in HTTP header
        self.set_http_response_status(status)
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
        if extra_info is not None:
            response_dict.update(extra_info)
        dbsession.remove()
        TaskSession.remove()
        return response_dict

    def create_error_response(self, error: NlprpError) -> JsonObjectType:
        """
        Returns an HTTP response for a given error and description of the error
        """
        # Turned 'errors' into array
        # Should this allow for multiple errors?
        error_info = {
            NKeys.ERRORS: [{
                NKeys.CODE: error.code,
                NKeys.MESSAGE: error.message,
                NKeys.DESCRIPTION: error.description
            }]
        }
        return self.create_response(error.http_status, error_info)

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------

    def check_token(self) -> bool:
        """
        Checks to see if the user has given the correct token for the current
        session connected to their username.
        """
        try:
            redis_token = REDIS_SESSIONS.get(self.username)
        except redis.exceptions.ConnectionError:
            log.critical(
                f"Could not connect to Redis (host={REDIS_HOST!r}, "
                f"port={REDIS_PORT!r}, password not shown)")
            raise
        if redis_token:
            redis_token = redis_token.decode()
        token = self.request.cookies.get(COOKIE_SESSION_TOKEN)
        if token and token == redis_token:
            return True
        else:
            return False

    # -------------------------------------------------------------------------
    # Main view
    # -------------------------------------------------------------------------

    # @do_cprofile
    @view_config(route_name='index')
    def index(self) -> JsonObjectType:
        """
        The top-level "index" view. Passes all the work to
        :meth:`handle_nlprp_request`, except for error handling.
        """
        try:
            return self.handle_nlprp_request()
        except NlprpError as error:
            return self.create_error_response(error)

    def _authenticate(self) -> None:
        """
        Authenticates the user, or raise an :exc:`NlprpError`.
        """
        if self.credentials is None:
            raise mkerror(
                BAD_REQUEST,
                "Credentials were absent or not in the correct format")
        # See if the user exists
        users = get_users()
        self.username = self.credentials.username
        try:
            hashed_pw = users[self.username]
        except KeyError:
            raise UNAUTHORIZED
        # Check if password is correct
        pw = self.credentials.password
        # pw = 'testpass'
        if self.check_token():
            self.password = pw
        elif check_password(pw, hashed_pw):
            self.password = pw
            token = make_unique_id()
            self.request.response.set_cookie(name=COOKIE_SESSION_TOKEN,
                                             value=token)
            REDIS_SESSIONS.set(self.username, token)
            REDIS_SESSIONS.expire(self.username, SESSION_TOKEN_EXPIRY_S)
        else:
            raise UNAUTHORIZED

    def _set_body_json_from_request(self) -> None:
        """
        Get JSON from request if it is in this form, otherwise raise an
        :exc:`NlprpError`.
        """
        try:
            body = self.request.json
            assert isinstance(body, dict)
        except (json.decoder.JSONDecodeError, AssertionError):
            raise mkerror(
                BAD_REQUEST,
                "Request body was absent or not in JSON object format")
        self.body = body  # type: JsonObjectType

    def handle_nlprp_request(self) -> JsonObjectType:
        """
        The main function. Authenticates user and checks the request is not
        malformed, then calls the function relating to the command specified
        by the user.
        """
        self._authenticate()
        self._set_body_json_from_request()
        command = json_get_str(self.body, NKeys.COMMAND, required=True)
        log.debug(f"NLPRP request received from {self.request.remote_addr}: "
                  f"username={self.username}, command={command}")
        if DEBUG_SHOW_REQUESTS:
            log.debug(f"Request: {self.body!r}")
        return self.parse_command(command)

    def parse_command(self, command: str) -> JsonObjectType:
        """
        Parse the NLPRP command.
        """
        if command == NlprpCommands.LIST_PROCESSORS:
            return self.list_processors()
        elif command == NlprpCommands.PROCESS:
            process_request = NlprpProcessRequest(self.body)
            if process_request.queue:
                return self.put_in_queue(process_request)
            else:
                return self.process_now(process_request)
        elif command == NlprpCommands.SHOW_QUEUE:
            return self.show_queue()
        elif command == NlprpCommands.FETCH_FROM_QUEUE:
            return self.fetch_from_queue()
        elif command == NlprpCommands.DELETE_FROM_QUEUE:
            return self.delete_from_queue()

    # -------------------------------------------------------------------------
    # NLPRP command handlers
    # -------------------------------------------------------------------------

    def list_processors(self) -> JsonObjectType:
        """
        Returns an HTTP response listing the available NLP processors.
        """
        return self.create_response(
            status=HttpStatus.OK,
            extra_info={
                NKeys.PROCESSORS: [
                    proc.infodict
                    for proc in ServerProcessor.processors.values()
                ]
            }
        )

    def process_now(self, process_request: NlprpProcessRequest) \
            -> JsonObjectType:
        """
        Processes the text supplied by the user immediately, without putting
        it in the queue.

        Args:
            process_request: a :class:`NlprpProcessRequest`
        """
        results = []  # type: JsonArrayType
        for text, metadata in process_request.gen_text_metadataobj():
            processor_data = []  # type: JsonArrayType
            for processor in process_request.processors:
                # Send the text off for processing
                procresult = process_nlp_text_immediate(
                    text=text,
                    processor=processor,
                    username=self.username,
                    password=self.password
                )
                # proc_dict = procresult.nlprp_processor_dict(processor)
                if procresult[NKeys.NAME] is None:
                    procresult[NKeys.NAME] = processor.name
                    procresult[NKeys.TITLE] = processor.title
                    procresult[NKeys.VERSION] = processor.version
                processor_data.append(procresult)

            doc_result = {
                NKeys.METADATA: metadata,
                NKeys.PROCESSORS: processor_data
            }
            if process_request.include_text:
                doc_result[NKeys.TEXT] = text
            results.append(doc_result)

        response_info = {
            NKeys.CLIENT_JOB_ID: process_request.client_job_id,
            NKeys.RESULTS: results,
        }
        return self.create_response(status=HttpStatus.OK,
                                    extra_info=response_info)

    def put_in_queue(self,
                     process_request: NlprpProcessRequest) -> JsonObjectType:
        """
        Puts the document-processor pairs specified by the user into a celery
        queue to be processed.

        Args:
            process_request: a :class:`NlprpProcessRequest`
        """
        # Generate unique queue_id for whole client request
        queue_id = make_unique_id()

        # Encrypt password using reversible encryption for passing to the
        # processors.
        # We must pass the password as a string to the task because it won't
        # let us pass a bytes object
        crypt_pass = encrypt_password(self.password).decode()

        docprocrequest_ids = []  # type: List[str]
        with transaction.manager:  # one COMMIT for everything inside this
            # Iterate through documents...
            for doctext, metadata in process_request.gen_text_metadatastr():
                doc_id = make_unique_id()
                # PyCharm doesn't like the "deferred" columns, so:
                # noinspection PyArgumentList
                doc = Document(
                    document_id=doc_id,
                    doctext=doctext,
                    client_job_id=process_request.client_job_id,
                    queue_id=queue_id,
                    username=self.username,
                    client_metadata=metadata,
                    include_text=process_request.include_text
                )
                dbsession.add(doc)  # add to database
                # Iterate through processors...
                for processor in process_request.processors:
                    # The combination of a document and a processor gives us
                    # a docproc.
                    docprocreq_id = make_unique_id()
                    docprocreq = DocProcRequest(
                        docprocrequest_id=docprocreq_id,
                        document_id=doc_id,
                        processor_id=processor.processor_id
                    )
                    dbsession.add(docprocreq)  # add to database
                    docprocrequest_ids.append(docprocreq_id)

        # Now everything's in the database and committed, we can fire off
        # back-end jobs:
        for dpr_id in docprocrequest_ids:
            process_nlp_text.apply_async(
                # unlike delay(), this allows us to specify task_id, and
                # then the Celery task ID is the same as the DocProcRequest
                # ID.
                args=(dpr_id, ),  # docprocrequest_id
                kwargs=dict(
                    username=self.username,
                    crypt_pass=crypt_pass,
                ),
                task_id=dpr_id,  # for Celery
            )

        response_info = {NKeys.QUEUE_ID: queue_id}
        return self.create_response(status=HttpStatus.ACCEPTED,
                                    extra_info=response_info)

    def fetch_from_queue(self) -> JsonObjectType:
        """
        Fetches requests for all document-processor pairs for the queue_id
        supplied by the user (if complete).
        """
        # ---------------------------------------------------------------------
        # Args
        # ---------------------------------------------------------------------
        args = json_get_toplevel_args(self.body)
        queue_id = json_get_str(args, NKeys.QUEUE_ID, required=True)

        # ---------------------------------------------------------------------
        # Start with the DocProcRequests, because if some are still busy,
        # we will return a "busy" response.
        # ---------------------------------------------------------------------
        q_dpr = (
            dbsession.query(DocProcRequest)
            .join(Document)
            .filter(Document.username == self.username)
            .filter(Document.queue_id == queue_id)
        )
        q_doc = (
            dbsession.query(Document)
            .filter(Document.username == self.username)
            .filter(Document.queue_id == queue_id)
        )
        dprs = list(q_dpr.all())  # type: List[DocProcRequest]
        if not dprs:
            raise mkerror(NOT_FOUND, "The queue_id given was not found")
        busy = not all([dpr.done for dpr in dprs])
        if busy:
            response = self.create_response(HttpStatus.PROCESSING, {})
            # todo: is it correct (from previous comments) that we can't
            # return JSON via Pyramid with a status of HttpStatus.PROCESSING?
            # If that's true, we have to force as below, but then we need to
            # alter the NLPRP docs (as these state the JSON code and HTTP code
            # should always be the same).
            self.set_http_response_status(HttpStatus.OK)
            return response

        # ---------------------------------------------------------------------
        # Make it easy to look up processors
        # ---------------------------------------------------------------------

        processor_cache = {}  # type: Dict[str, ServerProcessor]

        def get_processor_cached(_processor_id: str) -> ServerProcessor:
            """
            Cache lookups for speed. (All documents will share the same set
            of processors, so there'll be a fair bit of duplication.)
            """
            nonlocal processor_cache
            try:
                return processor_cache[_processor_id]
            except KeyError:
                _processor = ServerProcessor.get_processor_from_id(_processor_id)  # may raise  # noqa
                processor_cache[_processor_id] = _processor
                return _processor

        # ---------------------------------------------------------------------
        # Collect results by document
        # ---------------------------------------------------------------------

        doc_results = []  # type: JsonArrayType
        client_job_id = None  # type: Optional[str]
        docs = set(dpr.document for dpr in dprs)
        for doc in docs:
            if client_job_id is None:
                client_job_id = doc.client_job_id
            processor_data = []  # type: JsonArrayType
            # ... data for *all* the processors for this doc
            for dpr in doc.docprocrequests:
                procresult = json.loads(dpr.results)  # type: Dict[str, Any]
                if procresult[NKeys.NAME] is None:
                    processor = get_processor_cached(dpr.processor_id)
                    procresult[NKeys.NAME] = processor.name
                    procresult[NKeys.TITLE] = processor.title
                    procresult[NKeys.VERSION] = processor.version
                processor_data.append(procresult)
            metadata = json.loads(doc.client_metadata)
            doc_result = {
                NKeys.METADATA: metadata,
                NKeys.PROCESSORS: processor_data
            }
            if doc.include_text:
                doc_result[NKeys.TEXT] = doc.doctext
            doc_results.append(doc_result)

        # ---------------------------------------------------------------------
        # Delete leftovers
        # ---------------------------------------------------------------------

        with sqla_transaction_commit():
            q_doc.delete(synchronize_session=False)
            # ... will also delete the DocProcRequests via a cascade

        response_info = {
            NKeys.CLIENT_JOB_ID: (
                client_job_id if client_job_id is not None else ""
            ),
            NKeys.RESULTS: doc_results
        }
        return self.create_response(status=HttpStatus.OK,
                                    extra_info=response_info)

    # @do_cprofile
    def show_queue(self) -> JsonObjectType:
        """
        Finds the queue entries associated with the client, optionally
        restricted to one client job id.
        """
        args = json_get_toplevel_args(self.body, required=False)
        if args:
            client_job_id = json_get_str(args, NKeys.CLIENT_JOB_ID,
                                         default="", required=False)
        else:
            client_job_id = ""

        # Queue IDs that are of interest
        queue_id_wheres = [Document.username == self.username]  # type: List[ClauseElement]  # nopep8
        if client_job_id:
            queue_id_wheres.append(Document.client_job_id == client_job_id)
        # noinspection PyUnresolvedReferences
        queue_ids = fetch_all_first_values(
            dbsession,
            select([Document.queue_id])
            .select_from(Document.__table__)
            .where(and_(*queue_id_wheres))
            .distinct()
            .order_by(Document.queue_id)
        )  # type: List[str]

        queue_answer = []  # type: JsonArrayType
        for queue_id in queue_ids:
            # DocProcRequest objects that are of interest
            dprs = list(
                dbsession.query(DocProcRequest)
                .join(Document)
                .filter(Document.queue_id == queue_id)
                .all()
            )  # type: List[DocProcRequest]
            busy = not all([dpr.done for dpr in dprs])
            if busy:
                max_time = datetime.datetime.min
            else:
                max_time = max([dpr.when_done_utc for dpr in dprs])
            assert dprs, "No DocProcRequests found; bug?"
            dt_submitted = dprs[0].document.datetime_submitted_pendulum

            queue_answer.append({
                NKeys.QUEUE_ID: queue_id,
                NKeys.CLIENT_JOB_ID: client_job_id,
                NKeys.STATUS: NlprpValues.BUSY if busy else NlprpValues.READY,
                NKeys.DATETIME_SUBMITTED: pendulum_to_nlprp_datetime(
                    dt_submitted, to_utc=True),
                NKeys.DATETIME_COMPLETED: (
                    None if busy else pendulum_to_nlprp_datetime(
                        max_time, to_utc=True)
                )
            })
        return self.create_response(status=HttpStatus.OK,
                                    extra_info={NKeys.QUEUE: queue_answer})

    def delete_from_queue(self) -> JsonObjectType:
        """
        Deletes from the queue all entries specified by the client.
        """
        args = json_get_toplevel_args(self.body)
        delete_all = json_get_bool(args, NKeys.DELETE_ALL, default=False)
        client_job_ids = json_get_array_of_str(args, NKeys.CLIENT_JOB_IDS)

        # Establish what to cancel/delete
        q_dpr = (
            dbsession.query(DocProcRequest)
            .join(Document)
            .filter(Document.username == self.username)
        )
        if not delete_all:
            q_dpr = q_dpr.filter(Document.client_job_id.in_(client_job_ids))

        # Remove from Celery queue (cancel ongoing jobs)
        task_ids_to_cancel = [
            dpr.docprocrequest_id
            for dpr in q_dpr.all()
        ]
        # Quicker to use ResultSet than forget them all separately
        results = []  # type: List[AsyncResult]
        for task_id in task_ids_to_cancel:
            results.append(AsyncResult(id=task_id, app=celery_app))
        res_set = ResultSet(results=results, app=celery_app)
        log.debug("About to revoke jobs...")
        res_set.revoke()  # will hang if backend not operational
        log.debug("... jobs revoked.")

        q_docs = (
            dbsession.query(Document)
            .filter(Document.username == self.username)
        )
        if not delete_all:
            q_docs = q_docs.filter(Document.client_job_id.in_(client_job_ids))

        with sqla_transaction_commit():
            # Delete the Document objects, which will cascade-delete the
            # DocProcRequest objects.
            q_docs.delete(synchronize_session=False)

        # Return response
        return self.create_response(status=HttpStatus.OK)
