#!/usr/bin/env python

r"""
crate_anon/nlp_web/constants.py

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

Constants for CRATE's implementation of an NLPRP server.

"""

import os

from pyramid.paster import get_appsettings
from pyramid.config import Configurator

from crate_anon.nlprp.constants import NlprpKeys as NKeys

KEY_PROCTYPE = "proctype"
PROCTYPE_GATE = "GATE"
PYTHONPROCSVERSION = "1.0"
VALIDATOR_DESCR = (
    "The validator will find fields that refer to the variable, "
    "whether or not they contain a valid value.")


# We could have gotten the internal Python processors from the subclasses of
# BaseNlpParser (and descriptions from their docstrings) but that would include
# ones which should not be used directly
PROCESSORS = [
    {
        NKeys.NAME: "medication",
        NKeys.TITLE: "SLAM BRC GATE-based medication finder",
        NKeys.VERSION: "1.2.0",
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds drug names",
        KEY_PROCTYPE: PROCTYPE_GATE
    },
    {
        NKeys.NAME: "diagnosis",
        NKeys.TITLE: "Test title",
        NKeys.VERSION: "0.1",
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Test description",
        KEY_PROCTYPE: PROCTYPE_GATE
    },
    {
        NKeys.NAME: "Ace",
        NKeys.TITLE: "Addenbrooke's Cognitive Examination",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Addenbrooke's Cognitive Examination (ACE, "
                           "ACE-R, ACE-III) total score."
    },
    {
        NKeys.NAME: "AceValidator",
        NKeys.TITLE: "Validator for Ace",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Basophils",
        NKeys.TITLE: "Basophil count",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Basophil count (absolute)."
    },
    {
        NKeys.NAME: "BasophilsValidator",
        NKeys.TITLE: "Validator for Basophils",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Bmi",
        NKeys.TITLE: "Body Mass Index",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds body mass index (BMI) (in kg / m^2)."
    },
    {
        NKeys.NAME: "BmiValidator",
        NKeys.TITLE: "Validator for Bmi",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Bp",
        NKeys.TITLE: "Blood Pressure",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds blood pressure, in mmHg. (Systolic and "
                           "diastolic.)"
    },
    {
        NKeys.NAME: "BpValidator",
        NKeys.TITLE: "Validator for Bp",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Crp",
        NKeys.TITLE: "C-reactive protein (CRP)",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: ""
    },
    {
        NKeys.NAME: "CrpValidator",
        NKeys.TITLE: "Validator for Crp",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Eosinophils",
        NKeys.TITLE: "Eosinophil count",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Eosinophil count (absolute)."
    },
    {
        NKeys.NAME: "EosinophilsValidator",
        NKeys.TITLE: "Validator for Eosinophils",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Esr",
        NKeys.TITLE: "Erythrocyte sedimentation rate (ESR)",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: ""
    },
    {
        NKeys.NAME: "EsrValidator",
        NKeys.TITLE: "Validator for Esr",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Height",
        NKeys.TITLE: "Height Finder",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Height. Handles metric (e.g. '1.8m') and "
                           "imperial (e.g. '5 ft 2 in')."
    },
    {
        NKeys.NAME: "HeightValidator",
        NKeys.TITLE: "Validator for Height",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Lithium",
        NKeys.TITLE: "Lithium Finder",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Lithium (Li) levels (for blood tests, not doses)."
    },
    {
        NKeys.NAME: "LithiumValidator",
        NKeys.TITLE: "Validator for Lithium",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Lymphocytes",
        NKeys.TITLE: "Lymphocyte Count",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Lymphocyte count (absolute)."
    },
    {
        NKeys.NAME: "LymphocytesValidator",
        NKeys.TITLE: "Validator for Lymphocytes",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "MiniAce",
        NKeys.TITLE: "Mini-Addenbrooke's Cognitive Examination (M-ACE).",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Mini-Addenbrooke's Cognitive Examination "
                           "(M-ACE) score."
    },
    {
        NKeys.NAME: "MiniAceValidator",
        NKeys.TITLE: "Validator for MiniAce",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Mmse",
        NKeys.TITLE: "Mini-mental state examination (MMSE)",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Mini-mental state examination (MMSE)."
    },
    {
        NKeys.NAME: "MmseValidator",
        NKeys.TITLE: "Validator for Mmse",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Moca",
        NKeys.TITLE: "Montreal Cognitive Assessment (MOCA)",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Montreal Cognitive Assessment (MOCA)."
    },
    {
        NKeys.NAME: "MocaValidator",
        NKeys.TITLE: "Validator for Moca",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Monocytes",
        NKeys.TITLE: "Monocyte count",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Monocyte count (absolute)."
    },
    {
        NKeys.NAME: "MonocytesValidator",
        NKeys.TITLE: "Validator for Monocytes",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Neutrophils",
        NKeys.TITLE: "Neutrophil count",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds Neutrophil count (absolute)."
    },
    {
        NKeys.NAME: "NeutrophilsValidator",
        NKeys.TITLE: "Validator for Neutrophils",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Sodium",
        NKeys.TITLE: "Sodium Finder",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Sodium (Na) levels (for blood tests, not doses)."
    },
    {
        NKeys.NAME: "SodiumValidator",
        NKeys.TITLE: "Validator for Sodium",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Tsh",
        NKeys.TITLE: "Thyroid-stimulating hormone (TSH)",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds levels of Thyroid-stimulating hormone (TSH)."
    },
    {
        NKeys.NAME: "TshValidator",
        NKeys.TITLE: "Validator for Tsh",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Wbc",
        NKeys.TITLE: "White cell count (WBC, WCC)",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Finds white cell count (WBC, WCC)."
    },
    {
        NKeys.NAME: "WbcValidator",
        NKeys.TITLE: "Validator for Wbc",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
    {
        NKeys.NAME: "Weight",
        NKeys.TITLE: "Weight Finder",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: "Weight. Handles metric (e.g. '57kg') and "
                           "imperial (e.g. '10 st 2 lb')."
    },
    {
        NKeys.NAME: "WeightValidator",
        NKeys.TITLE: "Validator for Weight",
        NKeys.VERSION: PYTHONPROCSVERSION,
        NKeys.IS_DEFAULT_VERSION: True,
        NKeys.DESCRIPTION: VALIDATOR_DESCR
    },
]

# Not doing the following because then the procs won't be in correct order:

# for proc in PROCESSORS:
#     proctype = proc.get('proctype')
#     if not procypte:
#         PROCESSORS.append({
#             NK.NAME: "{}Validator".format(proc[name])
#             NK.TITLE: "Validator for {}".format(proc[name])
#             NK.VERSION: PYTHONPROCSVERSION,
#             NK.IS_DEFAULT_VERSION: True,
#             NK.DESCRIPTION: "The validator will find fields that refer to "
#                             "the variable, whether or not they contain a valid "  # noqa
#                             "value."
#         })

GATE_BASE_URL = "https://nhsta-api.slam-services.gate.ac.uk/process-document"
SERVER_NAME = 'test_server'
SERVER_VERSION = '0.1'
NLP_WEB_CONFIG_ENVVAR = "CRATE_NLP_WEB_CONFIG"
SETTINGS_PATH = os.getenv(NLP_WEB_CONFIG_ENVVAR)
assert NLP_WEB_CONFIG_ENVVAR, (
    "Missing environment variable {}".format(NLP_WEB_CONFIG_ENVVAR))
SETTINGS = get_appsettings(SETTINGS_PATH)
CONFIG = Configurator(settings=SETTINGS)

DEMO_CONFIG = """
[app:main]
use = egg:crate_anon
pyramid.reload_templates = true
# pyramid.includes =
#     pyramid_debugtoolbar
nlp_web.secret = changethis
sqlalchemy.url = mysql://username:password@localhost/dbname?charset=utf8

# Absolute path of users file
users_file = /home/.../nlp_web_users/users.txt

# urls for queueing
broker_url = amqp://@localhost:3306/testbroker
backend_url = db+mysql://username:password@localhost/backenddbname?charset=utf8

[server:main]
use = egg:waitress#main
listen = localhost:6543
"""
