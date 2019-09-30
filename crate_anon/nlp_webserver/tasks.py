#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/tasks.py

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

Tasks to process text for an NLPRP server (and be scheduled via Celery).

"""

import datetime
import json
import logging
import requests
import transaction

from celery import Celery
# from celery.app.task import Task  # see "def delay", "def apply_async"
from cryptography.fernet import Fernet
from sqlalchemy import engine_from_config
from sqlalchemy.orm import scoped_session
from sqlalchemy.exc import SQLAlchemyError

from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
from crate_anon.nlp_manager.constants import (
    GateApiKeys,
    GateResultKeys,
)
from crate_anon.nlp_webserver.models import Session, DocProcRequest
from crate_anon.nlp_webserver.procs import ServerProcessor
from crate_anon.nlp_webserver.constants import (
    NlpServerConfigKeys,
    PROCTYPE_GATE,
    SQLALCHEMY_COMMON_OPTIONS,
)
from crate_anon.nlp_webserver.security import decrypt_password
from crate_anon.nlp_webserver.settings import SETTINGS
from crate_anon.nlprp.api import JsonArrayType, JsonObjectType, NlprpKeys
from crate_anon.nlprp.constants import HttpStatus

log = logging.getLogger(__name__)


# =============================================================================
# SQLAlchemy and Celery setup
# =============================================================================

TaskSession = scoped_session(Session)
engine = engine_from_config(SETTINGS,
                            NlpServerConfigKeys.SQLALCHEMY_PREFIX,
                            **SQLALCHEMY_COMMON_OPTIONS)
TaskSession.configure(bind=engine)

try:
    broker_url = SETTINGS[NlpServerConfigKeys.BROKER_URL]
except KeyError:
    log.error(f"{NlpServerConfigKeys.BROKER_URL} value "
              f"missing from config file.")
    raise
backend_url = SETTINGS.get(NlpServerConfigKeys.BACKEND_URL) or None

key = SETTINGS[NlpServerConfigKeys.ENCRYPTION_KEY]
# Turn key into bytes object
key = key.encode()
CIPHER_SUITE = Fernet(key)

# Set expiry time to 90 days in seconds
expiry_time = 60 * 60 * 24 * 90
celery_app = Celery('tasks',
                    broker=broker_url,
                    backend=backend_url,
                    result_expires=expiry_time)
NLP_WEBSERVER_CELERY_APP_NAME = "crate_anon.nlp_webserver.tasks"
celery_app.conf.database_engine_options = SQLALCHEMY_COMMON_OPTIONS


# =============================================================================
# Helper functions
# =============================================================================

def nlprp_processor_dict(
        success: bool,
        processor: ServerProcessor = None,
        results: JsonArrayType = None,
        errcode: int = None,
        errmsg: str = None) -> JsonObjectType:
    """
    Returns a dictionary suitable for use as one of the elements of the
    ``response["results"]["processors"]`` array; see :ref:`NLPRP <nlprp>`.

    Args:
        success:
            did the request succeed?
        processor:
            a :class:`crate_anon.nlp_webserver.procs.Processor`, or ``None``
        results:
            a JSON array of results
        errcode:
            (if not ``success``) an integer error code
        errmsg:
            (if not ``success``) an error message

    Returns:
        a JSON object in NLPRP format
    """
    proc_dict = {
        NlprpKeys.RESULTS: results or [],
        NlprpKeys.SUCCESS: success
    }
    if processor:
        proc_dict[NlprpKeys.NAME] = processor.name
        proc_dict[NlprpKeys.TITLE] = processor.title
        proc_dict[NlprpKeys.VERSION] = processor.version
    if not success:
        proc_dict[NlprpKeys.ERRORS] = [{
            NlprpKeys.CODE: errcode,
            NlprpKeys.MESSAGE: errmsg,
            NlprpKeys.DESCRIPTION: errmsg,
        }]
    return proc_dict


def internal_error(msg: str,
                   processor: ServerProcessor = None) -> JsonObjectType:
    """
    Log an error message, and raise a corresponding :exc:`NlprpError` for
    an internal server error.

    Args:
        msg: the error message
        processor: the :class:`Processor` object to be used
    """
    log.error(msg)
    return nlprp_processor_dict(
        success=False,
        processor=processor,
        errcode=HttpStatus.INTERNAL_SERVER_ERROR,
        errmsg=f"Internal Server Error: {msg}"
    )


def gate_api_error(msg: str,
                   processor: ServerProcessor = None) -> JsonObjectType:
    """
    Return a "GATE failed" error.

    Args:
        msg: description of the error
        processor: the :class:`Processor` object to be used
    """
    log.error(f"GATE API error: {msg}")
    return nlprp_processor_dict(
        success=False,
        processor=processor,
        errcode=HttpStatus.BAD_GATEWAY,
        errmsg=f"Bad Gateway: {msg}"
    )


# =============================================================================
# Convert GATE JSON results (from GATE's own API) to our internal format
# =============================================================================

def get_gate_results(results_dict: JsonObjectType) -> JsonArrayType:
    """
    Convert results in GATE JSON format to results in our internal format.

    Args:
        results_dict: see :class:`crate_anon.nlp_manager.constants.GateApiKeys`
            or https://cloud.gate.ac.uk/info/help/online-api.html

    Returns:
        list of dictionaries; see
        :class:`crate_anon.nlp_manager.constants.GateApiKeys`
    """
    results = []  # type: JsonArrayType
    entities = results_dict[GateApiKeys.ENTITIES]
    for annottype, values in entities.items():
        for features in values:
            start, end = features[GateApiKeys.INDICES]
            del features[GateApiKeys.INDICES]
            results.append({
                GateResultKeys.TYPE: annottype,
                GateResultKeys.START: start,
                GateResultKeys.END: end,
                GateResultKeys.SET: None,  # CHECK WHAT THIS SHOULD BE!!
                GateResultKeys.FEATURES: features
            })
    return results


# =============================================================================
# Task session management
# =============================================================================

def start_task_session() -> None:
    """
    Starts a session for the tasks. To be called at the start of a web request.
    """
    TaskSession()


# =============================================================================
# NLP server processing functions
# =============================================================================

# noinspection PyUnusedLocal
@celery_app.task(bind=True, name='tasks.process_nlp_text')
def process_nlp_text(
        self,
        docprocrequest_id: str,
        username: str = "",
        crypt_pass: str = "") -> None:
    """
    Task to process a single ``DocProcRequest`` by sending text to the relevant
    processor.

    Args:
        self:
            the :class:`celery.Task`
        docprocrequest_id:
            the :class:`crate_anon.nlp_webserver.models.DocProcRequest` ID
        username:
            username in use
        crypt_pass:
            encrypted password
    """

    # noinspection PyUnresolvedReferences
    dpr = (
        TaskSession.query(DocProcRequest).get(docprocrequest_id)
    )  # type: Optional[DocProcRequest]
    if not dpr:
        log.error(f"DocProcRequest {docprocrequest_id} does not exist")
    if dpr.done:
        log.error(f"DocProcRequest {docprocrequest_id} already processed")
        return

    # Turn the password back into bytes and decrypt
    password = decrypt_password(crypt_pass.encode(), CIPHER_SUITE)
    text = dpr.doctext

    # Get the processor
    processor_id = dpr.processor_id

    try:
        # Fetch the processor
        try:
            processor = ServerProcessor.processors[processor_id]  # may raise
            # Run the NLP
            results = process_nlp_text_immediate(
                text, processor, username, password)

        except KeyError:
            results = internal_error(f"No such processor: {processor_id!r}")

        dpr.done = True
        dpr.when_done_utc = datetime.datetime.utcnow()
        dpr.results = json.dumps(results,
                                 separators=JSON_SEPARATORS_COMPACT)
        transaction.commit()
    except SQLAlchemyError:
        # noinspection PyUnresolvedReferences
        TaskSession.rollback()


def process_nlp_text_immediate(
        text: str,
        processor: ServerProcessor,
        username: str = "",
        password: str = "") -> JsonObjectType:
    """
    Function to send text immediately to the relevant processor.

    Args:
        text:
            text to run the NLP over
        processor:
            NLP processor; a class:`crate_anon.nlp_webserver.procs.Processor`
        username:
            username in use
        password:
            plaintext password

    Returns:
        a :class:`NlpServerResult`
    """
    if processor.proctype == PROCTYPE_GATE:
        return process_nlp_gate(text, processor, username, password)
    else:
        if not processor.parser:
            processor.set_parser()
        return process_nlp_internal(text=text, processor=processor)


def process_nlp_gate(text: str,
                     processor: ServerProcessor,
                     username: str,
                     password: str) -> JsonObjectType:
    """
    Send text to a chosen GATE processor (via an HTTP connection, using the
    GATE JSON API; see https://cloud.gate.ac.uk/info/help/online-api.html).

    Args:
        text:
            text to run the NLP over
        processor:
            NLP processor; a class:`crate_anon.nlp_webserver.procs.Processor`
        username:
            username in use
        password:
            plaintext password

    Returns:
        a :class:`NlpServerResult`

    API failure is handled by returning a failure code/message to our client.
    """
    headers = {
        'Content-Type': 'text/plain',
        'Accept': 'application/gate+json',
        # Content-Encoding: gzip?,
        'Expect': '100-continue',
        # ... see https://cloud.gate.ac.uk/info/help/online-api.html
        'charset': 'utf8'
    }
    try:
        response = requests.post(processor.base_url + '/' + processor.name,
                                 data=text.encode('utf-8'),
                                 headers=headers,
                                 auth=(username, password))  # basic auth
    except requests.exceptions.RequestException as e:
        return gate_api_error(
            f"The GATE processor returned the error: {e.response.reason} "
            f"(with status code {e.response.status_code})",
            processor=processor
        )
    if response.status_code != HttpStatus.OK:
        return gate_api_error(
            f"The GATE processor returned the error: {response.reason} "
            f"(with status code {response.status_code})",
            processor=processor
        )
    try:
        json_response = response.json()
    except json.decoder.JSONDecodeError:
        return gate_api_error(
            "Bad Gateway: The GATE processor did not return JSON",
            processor=processor
        )
    results = get_gate_results(json_response)
    return nlprp_processor_dict(success=True,
                                processor=processor,
                                results=results)


def process_nlp_internal(text: str,
                         processor: ServerProcessor) -> JsonObjectType:
    """
    Send text to a chosen CRATE Python NLP processor and return a
    :class:`NlpServerResult`.
    """
    parser = processor.parser
    try:
        tablename_valuedict_generator = parser.parse(text)
    except AttributeError:
        return internal_error(
            f"parser is not a CRATE Python NLP parser; is {parser!r}")
    # Get second element of each element in parsed text as first is tablename
    # which will have no meaning here
    return nlprp_processor_dict(
        True,
        processor,
        results=[x[1] for x in tablename_valuedict_generator]
    )
