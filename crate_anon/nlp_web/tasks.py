from celery import Celery
import requests
import transaction
import logging

from sqlalchemy import engine_from_config
from pyramid.paster import (
    get_appsettings,
#    setup_logging,
)
from typing import Optional, Tuple, Any, List, Dict

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
# from crate_anon.nlp_manager.all_processors import make_processor
from crate_anon.nlp_web.models import DBSession, DocProcRequest
from crate_anon.nlp_web.procs import Processor
from crate_anon.nlp_web.constants import SETTINGS, CONFIG

log = logging.getLogger(__name__)

try:
    broker_url = SETTINGS['broker_url']
except KeyError:
    log.error("broker_url value missing from config file.")
try:
    backend_url = SETTINGS['backend_url']
except KeyError:
    log.error("backend_url value missing from config file.")

def get_gate_results(results_dict: Dict[str, Any]) -> List[Any]:
    results = []
    # See https://cloud.gate.ac.uk/info/help/online-api.html
    # for format of response from processor
    text = results_dict['text']
    entities = results_dict['entities']
    for annottype, values in entities.items():
        # One annotation type will have a list of dictionaries
        # with each dictionary being the set of features for one
        # result, or 'hit'
        for featureset in values:
            # There must be a more efficient way to do this:
            features = {x: featureset[x] for x in featureset if x != "indices"}#
            features['_type'] = annottype
            start, end = featureset['indices']
            content = text[start: end]
            features['_start'] = start
            features['_end'] = end
            features['_content'] = content
            results.append(features)
    print(results)
    print()
    return results

# app = Celery('tasks', backend=backend_url, broker=broker_url)
app = Celery('tasks', backend=backend_url, broker='pyamqp://')

log = logging.getLogger(__name__)

@app.task(bind=True, name='tasks.process_nlp_text')
def process_nlp_text(
        self,
        docprocrequest_id: str,
        url: Optional[str] = None,
        username: Optional[str] = "",
        password: Optional[str] = "") -> Optional[Tuple[
            bool, List[Any], str, str]]:
    """
    Task to send text to the relevant processor.
    """
    # Can't figure out how not to have to do this everytime
    engine = engine_from_config(SETTINGS, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    query = DBSession.query(DocProcRequest).get(docprocrequest_id)
    # The above is probably wrong, but if we use a different session, the
    # data doesn't always reach the database in time
    if not query:
        log.error("Docprocrequest: {} does not exist: ".format(
                  query.docprocrequest_id))
        return None
    text = query.doctext
    processor_id = query.processor_id
    processor = Processor.processors[processor_id]
    # Delete docprocrequest from database
    DBSession.delete(query)
    transaction.commit()
    if processor.proctype.upper() == "GATE":
        return process_nlp_gate(text, processor, url, username, password)
    else:
        if not processor.parser:
            processor.set_parser()
        return process_nlp_internal(text=text, parser=processor.parser)

def process_nlp_text_immediate(
        text: str,
        processor: Processor,
        url: Optional[str] = None,
        username: Optional[str] = "",
        password: Optional[str] = "") -> Optional[Tuple[
            bool, List[Any], str, str]]:
    """
    Function to send text immediately to the relevant processor.
    """
    if processor.proctype.upper() == "GATE":
        return process_nlp_gate(text, processor, url, username, password)
    else:
        if not processor.parser:
            processor.set_parser()
        return process_nlp_internal(text=text, parser=processor.parser)

def process_nlp_gate(text: str, processor: Processor, url: str,
                     username: str, password: str) -> Tuple[
            bool, List[Any], str, str]:
    """
    Send text to a chosen GATE processor and returns a Tuple in the format
    (sucess, results, error code, error message) where success is True or
    False, results is None if sucess is False and error code and error message
    are None if success is True.
    """
    headers = {
        'Content-Type': 'text/plain',
        'Accept': 'application/gate+json',
        # Content-Encoding: gzip?,
        'Expect': '100-continue',  # - see https://cloud.gate.ac.uk/info/help/online-api.html
        'charset': 'utf8'
    }
    text = text.encode('utf-8')
    try:
        response = requests.post(url + '/' + processor.name,
                                 data=text,
                                 headers=headers,
                                 auth=(username, password))  # basic auth
        print(response)
    except requests.exceptions.RequestException as e:
        log.error(e)
        return (
            False,
            [],
            e.response.status_code,
            "The GATE processor returned the error: " + e.response.reason
        )
    if response.status_code != 200:
        return (
            False,
            [],
            response.status_code,
            "The GATE processor returned the error: " + response.reason
        )
    try:
        json_response = response.json()
    except json.decoder.JSONDecodeError:
        return (
            False,
            [],
            502,  # 'Bad Gateway' - not sure if correct error code
            "The GATE processor did not return json"
        )
    results = get_gate_results(json_response)
    print(results)
    return (True, results, None, None)

def process_nlp_internal(text: str, parser: BaseNlpParser) -> Tuple[
            bool, List[Any], str, str]:
    """
    Send text to a chosen Python processor and returns a Tuple in the format
    (sucess, results, error code, error message) where success is True or
    False, results is None if sucess is False and error code and error message
    are None if success is True.
    """
    # processor = make_processor(processor_type=processor,
    #                            nlpdef=None, cfgsection=None)
    try:
        parsed_text = parser.parse(text)
    except AttributeError:
        # 'parser' is not actual parser - must have happened internally
        return (
            False,
            [],
            500,  # 'Internal Server Error'
            "Internal Server Error"
        )
    # Get second element of each element in parsed text as first is tablename
    # which will have no meaning here
    return (True, [x[1] for x in parsed_text], None, None)











