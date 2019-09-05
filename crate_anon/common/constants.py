#!/usr/bin/env python

"""
crate_anon/common/constants.py

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

**Constants used throughout CRATE.**

"""

import os


# =============================================================================
# Plain constants
# =============================================================================

CRATE_DOCS_URL = "https://crateanon.readthedocs.io/"

ENVVAR_RUN_WITHOUT_CONFIG = "CRATE_RUN_WITHOUT_LOCAL_SETTINGS"

JSON_SEPARATORS_COMPACT = (',', ':')
# ... see https://docs.python.org/3/library/json.html

LOWER_CASE_STRINGS_MEANING_TRUE = ['true', '1', 't', 'y', 'yes']

# Is this program running on readthedocs.org?
ON_READTHEDOCS = os.environ.get('READTHEDOCS') == 'True'

# Will we run without a config file?
RUNNING_WITHOUT_CONFIG = (
    ON_READTHEDOCS or
    (ENVVAR_RUN_WITHOUT_CONFIG in os.environ and
     os.environ[ENVVAR_RUN_WITHOUT_CONFIG].lower() in
     LOWER_CASE_STRINGS_MEANING_TRUE)
)


# =============================================================================
# HelpUrl
# =============================================================================

class HelpUrl(object):
    """
    Makes help URLs, for an approximation to context-sensitive help within the
    web site.

    Note that in Django's template syntax,

    .. code-block:: none

        {{ HelpUrl.main }}

    gets translated to

    .. code-block:: python

        HelpUrl.main()

    i.e. further brackets are unnecessary (and an error). See:
    
    - https://docs.djangoproject.com/en/2.2/topics/templates/#variables
    
    ... "If a variable resolves to a callable, the template system will call it
    with no arguments and use its result instead of the callable."

    """  # noqa

    @staticmethod
    def make_url(location: str, language: str = "en",
                 version: str = "latest") -> str:
        """
        Make a CRATE help URL.

        Args:
            location: location within docs
            language: language (default ``en``)
            version: version (default ``latest``)
        """
        return f"{CRATE_DOCS_URL}{language}/{version}/{location}"

    @classmethod
    def main(cls) -> str:
        return cls.make_url("")

    @classmethod
    def website(cls) -> str:
        return cls.make_url("website_using/index.html")

    @classmethod
    def find_text_anywhere(cls) -> str:
        return cls.make_url("website_using/clinician_privileged.html#clinician-privileged-find-text-anywhere")  # noqa

    @classmethod
    def clinician_lookup_rid(cls) -> str:
        return cls.make_url("website_using/clinician_privileged.html#look-up-research-id-from-patient-id")  # noqa

    @classmethod
    def clinician_submit_contact_request(cls) -> str:
        return cls.make_url("website_using/clinician_privileged.html#submit-patient-contact-request")  # noqa

    @classmethod
    def querybuilder(cls) -> str:
        return cls.make_url("website_using/research_queries.html#query-builder")  # noqa

    @classmethod
    def sql(cls) -> str:
        return cls.make_url("website_using/research_queries.html#research-query-sql")  # noqa

    @classmethod
    def highlighting(cls) -> str:
        return cls.make_url("website_using/research_queries.html#highlighting-text-in-results")  # noqa

    @classmethod
    def results(cls) -> str:
        return cls.make_url("website_using/research_queries.html#results-table-view")  # noqa

    @classmethod
    def patient_explorer(cls) -> str:
        return cls.make_url("website_using/patient_explorer.html")

    @classmethod
    def sqlhelper_find_text_anywhere(cls) -> str:
        return cls.make_url("website_using/sql_helpers.html#find-text-anywhere")  # noqa

    @classmethod
    def sqlhelper_find_drugs_anywhere(cls) -> str:
        return cls.make_url("website_using/sql_helpers.html#find-drugs-of-a-given-type-anywhere")  # noqa

    @classmethod
    def sitewide_queries(cls) -> str:
        return cls.make_url("website_using/site_queries.html")

    @classmethod
    def research_db_structure(cls) -> str:
        return cls.make_url("website_using/database_structure.html")

    @classmethod
    def submit_contact_request(cls) -> str:
        return cls.make_url("website_using/contact_patients.html#submit-a-contact-request")  # noqa

    @classmethod
    def rdbm(cls) -> str:
        return cls.make_url("website_using/rdbm_admin.html")

    @classmethod
    def developer(cls) -> str:
        return cls.make_url("website_using/developer_admin.html")

    @classmethod
    def user_settings(cls) -> str:
        return cls.make_url("website_using/clinician_researcher_overview.html#your-settings")  # noqa

    @classmethod
    def about_crate(cls) -> str:
        return cls.make_url("website_using/clinician_researcher_overview.html#about-crate")  # noqa

    @classmethod
    def archive(cls) -> str:
        return cls.make_url("website_using/archive.html")
