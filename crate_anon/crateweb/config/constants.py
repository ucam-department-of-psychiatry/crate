#!/usr/bin/env python

"""
crate_anon/crateweb/config/constants.py

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

**Configuration constants for the CRATE web interface.**

"""

CRATEWEB_CONFIG_ENV_VAR = 'CRATE_WEB_LOCAL_SETTINGS'
CHERRYPY_EXTRA_ARGS_ENV_VAR = 'CRATE_CHERRYPY_ARGS'
CELERY_APP_NAME = 'crate_anon.crateweb.consent'


class ResearchDbInfoKeys(object):
    """
    Keys for each dictionary within ``settings.RESEARCH_DB_INFO``, representing
    a description of a research database that CRATE will provide a view on.
    """
    NAME = 'name'
    DESCRIPTION = 'description'

    DATABASE = 'database'
    SCHEMA = 'schema'

    PID_PSEUDO_FIELD = 'pid_pseudo_field'
    MPID_PSEUDO_FIELD = 'mpid_pseudo_field'
    TRID_FIELD = 'trid_field'
    RID_FIELD = 'rid_field'
    RID_FAMILY = 'rid_family'
    MRID_TABLE = 'mrid_table'
    MRID_FIELD = 'mrid_field'

    PID_DESCRIPTION = 'pid_description'
    MPID_DESCRIPTION = 'mpid_description'
    RID_DESCRIPTION = 'rid_description'
    MRID_DESCRIPTION = 'mrid_description'
    TRID_DESCRIPTION = 'trid_description'

    SECRET_LOOKUP_DB = 'secret_lookup_db'

    DATE_FIELDS_BY_TABLE = 'date_fields_by_table'
    DEFAULT_DATE_FIELDS = 'default_date_fields'
    UPDATE_DATE_FIELD = 'update_date_field'


SOURCE_DB_NAME_MAX_LENGTH = 20


class ClinicalDatabaseType(object):
    """
    Possible source clinical database types that CRATE knows about, and can
    look up patient details for the consent-to-contact system.
    """
    # NB the following strings mustn't be longer than SOURCE_DB_NAME_MAX_LENGTH
    DUMMY_CLINICAL = 'dummy_clinical'
    CPFT_CRS = 'cpft_crs'
    CPFT_PCMIS = 'cpft_pcmis'
    CPFT_RIO_CRATE_PREPROCESSED = 'cpft_rio_crate'
    CPFT_RIO_DATAMART = 'cpft_rio_datamart'
    CPFT_RIO_RAW = 'cpft_rio_raw'
    CPFT_RIO_RCEP = 'cpft_rio_rcep'

    # For Django fields, using the above:
    DATABASE_CHOICES = (
        # First key must match a database entry in Django local settings.
        (DUMMY_CLINICAL,
         'Dummy clinical database for testing'),
        # (ClinicalDatabaseType.CPFT_PCMIS,
        #  'CPFT Psychological Wellbeing Service (IAPT) PC-MIS'),
        (CPFT_CRS,
         'CPFT Care Records System (CRS) 2005-2012'),
        (CPFT_RIO_RCEP,
         'CPFT RiO 2013- (preprocessed by Servelec RCEP tool)'),
        (CPFT_RIO_RAW,
         'CPFT RiO 2013- (raw)'),
        (CPFT_RIO_CRATE_PREPROCESSED,
         'CPFT RiO 2013- (preprocessed by CRATE)'),
        (CPFT_RIO_DATAMART,
         'CPFT RiO 2013- (data warehouse processed version)'),
    )
