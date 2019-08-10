#!/usr/bin/env python

r"""
crate_anon/nlp_web/tasks.py

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

from celery import Celery
import requests
import transaction
import logging
import datetime
import json

from cryptography.fernet import Fernet
from sqlalchemy import engine_from_config
from typing import Any, List, Dict
from sqlalchemy.orm import scoped_session
from sqlalchemy.exc import SQLAlchemyError

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.constants import (
    GateApiKeys,
    GateResultKeys,
)
from crate_anon.nlp_webserver.models import Session, DocProcRequest
from crate_anon.nlp_webserver.procs import Processor
from crate_anon.nlp_webserver.constants import (
    NlpServerConfigKeys,
    PROCTYPE_GATE,
    SQLALCHEMY_COMMON_OPTIONS,
)
from crate_anon.nlp_webserver.security import decrypt_password
from crate_anon.nlp_webserver.settings import SETTINGS
from crate_anon.nlprp.api import NlprpKeys
from crate_anon.nlprp.constants import HttpStatus

log = logging.getLogger(__name__)

# =============================================================================
# SQLAlchemy and Celery setup
# =============================================================================

TaskSession = scoped_session(Session)
engine = engine_from_config(SETTINGS,
                            NlpServerConfigKeys.SQLALCHEMY_URL_PREFIX,
                            **SQLALCHEMY_COMMON_OPTIONS)
TaskSession.configure(bind=engine)

try:
    broker_url = SETTINGS[]
except KeyError:
    log.error(f"{NlpServerConfigKeys.BROKER_URL} value "
              f"missing from config file.")
    raise
try:
    backend_url = SETTINGS[NlpServerConfigKeys.BACKEND_URL]
except KeyError:
    log.error(f"{NlpServerConfigKeys.BACKEND_URL} value "
              f"missing from config file.")
    raise

key = SETTINGS[NlpServerConfigKeys.ENCRYPTION_KEY]
# Turn key into bytes object
key = key.encode()
CIPHER_SUITE = Fernet(key)

# Set expiry time to 90 days in seconds
expiry_time = 60 * 60 * 24 * 90
app = Celery('tasks', backend=backend_url, broker=broker_url,
             result_expires=expiry_time)
app.conf.database_engine_options = SQLALCHEMY_COMMON_OPTIONS


# =============================================================================
# NlpServerResult
# =============================================================================

class NlpServerResult(object):
    """
    Object to represent the server-side results of processing some text.
    """
    def __init__(self,
                 success: bool,
                 time: datetime.datetime = None,
                 results: List[Dict[str, Any]] = None,
                 errcode: int = None,
                 errmsg: str = None) -> None:
        self.success = success
        self.time = time or datetime.datetime.utcnow()
        self.results = results or []  # type: List[Dict[str, Any]]
        self.errcode = errcode
        self.errmsg = errmsg

    def nlprp_processor_dict(self, processor: Processor) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for use as one of the elements of the
        ``response["results"]["processors"] array; see :ref:`NLPRP <nlprp>`.

        Args:
            processor: a :class:`crate_anon.nlp_webserver.procs.Processor`

        Returns:
            dict: as above
        """
        proc_dict = {
            NlprpKeys.NAME: processor.name,
            NlprpKeys.TITLE: processor.title,
            NlprpKeys.VERSION: processor.version,
            NlprpKeys.RESULTS: self.results,
            NlprpKeys.SUCCESS: self.success
        }
        if not self.success:
            proc_dict[NlprpKeys.ERRORS] = [{
                NlprpKeys.CODE: self.errcode,
                NlprpKeys.MESSAGE: self.errmsg,
                NlprpKeys.DESCRIPTION: self.errmsg,
            }]
        return proc_dict


# =============================================================================
# Convert GATE JSON results (from GATE's own API) to our internal format
# =============================================================================

def get_gate_results(results_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert results in GATE JSON format to results in our internal format.

    Args:
        results_dict: see :class:`crate_anon.nlp_manager.constants.GateApiKeys`
            or https://cloud.gate.ac.uk/info/help/online-api.html

    Returns:
        list of dictionaries; see
        :class:`crate_anon.nlp_manager.constants.GateApiKeys`
    """
    results = []  # type: List[Dict[str, Any]]
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
@app.task(bind=True, name='tasks.process_nlp_text')
def process_nlp_text(
        self,
        docprocrequest_id: str,
        url: str = None,
        username: str = "",
        crypt_pass: str = "") -> NlpServerResult:
    """
    Task to send text to the relevant processor.
    """
    # time.sleep(0.2)
    # Can't figure out how not to have to do this everytime
    # engine = engine_from_config(SETTINGS, 'sqlalchemy.')
    # TaskSession.configure(bind=engine)

    # noinspection PyUnresolvedReferences
    query = TaskSession.query(DocProcRequest).get(docprocrequest_id)
    # The above is probably wrong, but if we use a different session, the
    # data doesn't always reach the database in time
    if not query:
        log.error(f"Docprocrequest: {docprocrequest_id} does not exist")
        return NlpServerResult(
            False,
            errcode=HttpStatus.INTERNAL_SERVER_ERROR,
            errmsg="Internal Server Error: Docprocrequest does not exist"
        )
    # Turn the password back into bytes and decrypt
    password = decrypt_password(crypt_pass.encode(), CIPHER_SUITE)
    text = query.doctext
    processor_id = query.processor_id
    processor = Processor.processors[processor_id]
    # Delete docprocrequest from database

    # noinspection PyUnresolvedReferences
    TaskSession.delete(query)
    try:
        transaction.commit()
    except SQLAlchemyError:
        # noinspection PyUnresolvedReferences
        TaskSession.rollback()
    if processor.proctype == PROCTYPE_GATE:
        return process_nlp_gate(text, processor, url, username, password)
    else:
        if not processor.parser:
            processor.set_parser()
        return process_nlp_internal(text=text, parser=processor.parser)


def process_nlp_text_immediate(
        text: str,
        processor: Processor,
        url: str = None,
        username: str = "",
        password: str = "") -> NlpServerResult:
    """
    Function to send text immediately to the relevant processor.
    """
    if processor.proctype == PROCTYPE_GATE:
        return process_nlp_gate(text, processor, url, username, password)
    else:
        if not processor.parser:
            processor.set_parser()
        return process_nlp_internal(text=text, parser=processor.parser)


def process_nlp_gate(text: str, processor: Processor, url: str,
                     username: str, password: str) -> NlpServerResult:
    """
    Send text to a chosen GATE processor (via an HTTP connection) and returns a
    :class:`NlpServerResult`.
    """
    headers = {
        'Content-Type': 'text/plain',
        'Accept': 'application/gate+json',
        # Content-Encoding: gzip?,
        'Expect': '100-continue',
        # ... see https://cloud.gate.ac.uk/info/help/online-api.html
        'charset': 'utf8'
    }
    text = text.encode('utf-8')
    try:
        response = requests.post(url + '/' + processor.name,
                                 data=text,
                                 headers=headers,
                                 auth=(username, password))  # basic auth
    except requests.exceptions.RequestException as e:
        log.error(e)
        return NlpServerResult(
            False,
            errcode=e.response.status_code,
            errmsg=(
                "The GATE processor returned the error: " + e.response.reason
            ),
        )
    if response.status_code != HttpStatus.OK:
        return NlpServerResult(
            False,
            errcode=response.status_code,
            errmsg="The GATE processor returned the error: " + response.reason
        )
    try:
        json_response = response.json()
    except json.decoder.JSONDecodeError:
        return NlpServerResult(
            False,
            errcode=HttpStatus.BAD_GATEWAY,
            errmsg="Bad Gateway: The GATE processor did not return json"
        )
    results = get_gate_results(json_response)
    return NlpServerResult(True, results=results)


def process_nlp_internal(text: str, parser: BaseNlpParser) -> NlpServerResult:
    """
    Send text to a chosen Python NLP processor and return a
    :class:`NlpServerResult`.
    """
    try:
        parsed_text = parser.parse(text)
    except AttributeError:
        # 'parser' is not actual parser - must have happened internally
        return NlpServerResult(
            False,
            errcode=HttpStatus.INTERNAL_SERVER_ERROR,  # 'Internal Server Error'
            errmsg=(
                "Internal Server Error: parser is not type 'BaseNlpProcessor"
            )
        )
    # Get second element of each element in parsed text as first is tablename
    # which will have no meaning here
    return NlpServerResult(True, results=[x[1] for x in parsed_text])
