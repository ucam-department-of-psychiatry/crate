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
"""

import os

from pyramid.paster import get_appsettings
from pyramid.config import Configurator

PYTHONPROCSVERSION = "1.0"
VALIDATOR_DESCR = (
    "The validator will find fields that refer to the variable, "
    "whether or not they contain a valid value.")


# We could have gotten the internal Python processors from the subclasses of
# BaseNlpParser (and descriptions from their docstrings) but that would include
# ones which should not be used directly
PROCESSORS = [
    {
        'name': "medication",
        'title': "SLAM BRC GATE-based medication finder",
        'version': "1.2.0",
        'is_default_version': True,
        'description': "Finds drug names",
        'proctype': "GATE"
    },
    {
        'name': "diagnosis",
        'title': "Test title",
        'version': "0.1",
        'is_default_version': True,
        'description': "Test description",
        'proctype': "GATE"
    },
    {
        'name': "Ace",
        'title': "Addenbrooke's Cognitive Examination",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': ("Finds Addenbrooke's Cognitive Examination (ACE, "
                        "ACE-R, ACE-III) total score.")
    },
    {
        'name': "AceValidator",
        'title': "Validator for Ace",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Basophils",
        'title': "Basophil count",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds Basophil count (absolute)."
    },
    {
        'name': "BasophilsValidator",
        'title': "Validator for Basophils",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Bmi",
        'title': "Body Mass Index",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds body mass index (BMI) (in kg / m^2)."
    },
    {
        'name': "BmiValidator",
        'title': "Validator for Bmi",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Bp",
        'title': "Blood Pressure",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds blood pressure, in mmHg. (Systolic and "
                        "diastolic.)"
    },
    {
        'name': "BpValidator",
        'title': "Validator for Bp",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Crp",
        'title': "C-reactive protein (CRP)",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': ""
    },
    {
        'name': "CrpValidator",
        'title': "Validator for Crp",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Eosinophils",
        'title': "Eosinophil count",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds Eosinophil count (absolute)."
    },
    {
        'name': "EosinophilsValidator",
        'title': "Validator for Eosinophils",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Esr",
        'title': "Erythrocyte sedimentation rate (ESR)",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': ""
    },
    {
        'name': "EsrValidator",
        'title': "Validator for Esr",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Height",
        'title': "Height Finder",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': ("Height. Handles metric (e.g. '1.8m') and "
                        "imperial (e.g. '5 ft 2 in').")
    },
    {
        'name': "HeightValidator",
        'title': "Validator for Height",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Lithium",
        'title': "Lithium Finder",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Lithium (Li) levels (for blood tests, not doses)."
    },
    {
        'name': "LithiumValidator",
        'title': "Validator for Lithium",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Lymphocytes",
        'title': "Lymphocyte Count",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds Lymphocyte count (absolute)."
    },
    {
        'name': "LymphocytesValidator",
        'title': "Validator for Lymphocytes",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "MiniAce",
        'title': "Mini-Addenbrooke's Cognitive Examination (M-ACE).",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': ("Finds Mini-Addenbrooke's Cognitive Examination "
                        "(M-ACE) score.")
    },
    {
        'name': "MiniAceValidator",
        'title': "Validator for MiniAce",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Mmse",
        'title': "Mini-mental state examination (MMSE)",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Mini-mental state examination (MMSE)."
    },
    {
        'name': "MmseValidator",
        'title': "Validator for Mmse",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Moca",
        'title': "Montreal Cognitive Assessment (MOCA)",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Montreal Cognitive Assessment (MOCA)."
    },
    {
        'name': "MocaValidator",
        'title': "Validator for Moca",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Monocytes",
        'title': "Monocyte count",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds Monocyte count (absolute)."
    },
    {
        'name': "MonocytesValidator",
        'title': "Validator for Monocytes",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Neutrophils",
        'title': "Neutrophil count",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds Neutrophil count (absolute)."
    },
    {
        'name': "NeutrophilsValidator",
        'title': "Validator for Neutrophils",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Sodium",
        'title': "Sodium Finder",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Sodium (Na) levels (for blood tests, not doses)."
    },
    {
        'name': "SodiumValidator",
        'title': "Validator for Sodium",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Tsh",
        'title': "Thyroid-stimulating hormone (TSH)",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds levels of Thyroid-stimulating hormone (TSH)."
    },
    {
        'name': "TshValidator",
        'title': "Validator for Tsh",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Wbc",
        'title': "White cell count (WBC, WCC)",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': "Finds white cell count (WBC, WCC)."
    },
    {
        'name': "WbcValidator",
        'title': "Validator for Wbc",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
    {
        'name': "Weight",
        'title': "Weight Finder",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': ("Weight. Handles metric (e.g. '57kg') and "
                        "imperial (e.g. '10 st 2 lb').")
    },
    {
        'name': "WeightValidator",
        'title': "Validator for Weight",
        'version': PYTHONPROCSVERSION,
        'is_default_version': True,
        'description': VALIDATOR_DESCR
    },
]

# Not doing the following because then the procs won't be in correct order:

#for proc in PROCESSORS:
#    proctype = proc.get('proctype')
#    if not procypte:
#        PROCESSORS.append({
#            'name': "{}Validator".format(proc[name])
#            'title': "Validator for {}".format(proc[name])
#            'version': PYTHONPROCSVERSION,
#            'is_default_version': True,
#            'desrciption': "The validator will find fields that refer to "
#                           "the variable, whether or not they contain a valid "  # noqa
#                           "value."
#        })

GATE_BASE_URL = "https://nhsta-api.slam-services.gate.ac.uk/process-document"
NLPRP_VERSION = '0.1.0'
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
