#!/usr/bin/env python

"""
crate_anon/preprocess/rio_constants.py

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

**Constants used for Servelec RiO/RCEP databases.**

"""

# Tables in RiO v6.2 Core:
RIO_TABLE_MASTER_PATIENT = "ClientIndex"
RIO_TABLE_ADDRESS = "ClientAddress"
RIO_TABLE_PROGRESS_NOTES = "PrgProgressNote"
RIO_TABLE_CLINICAL_DOCUMENTS = "ClientDocument"
# Columns in RiO Core:
RIO_COL_PATIENT_ID = "ClientID"  # RiO 6.2: VARCHAR(15)
RIO_COL_NHS_NUMBER = "NNN"  # RiO 6.2: CHAR(10) ("National NHS Number")
RIO_COL_POSTCODE = "PostCode"  # ClientAddress.PostCode
RIO_COL_DEFAULT_PK = "SequenceID"  # INT
RIO_COL_USER_ASSESS_DEFAULT_PK = "type12_NoteID"

# Tables in RiO CRIS Extract Program (RCEP) output database:
RCEP_TABLE_MASTER_PATIENT = "Client_Demographic_Details"
RCEP_TABLE_ADDRESS = "Client_Address_History"
RCEP_TABLE_PROGRESS_NOTES = "Progress_Notes"
# Columns in RCEP extract:
RCEP_COL_PATIENT_ID = "Client_ID"  # RCEP: VARCHAR(15)
RCEP_COL_NHS_NUMBER = "NHS_Number"  # RCEP: CHAR(10)
RCEP_COL_POSTCODE = "Post_Code"  # RCEP: NVARCHAR(10)
# ... general format (empirically): "XX12 3YY" or "XX1 3YY"; "ZZ99" for unknown
# This matches the ONPD "pdcs" format.
RCEP_COL_MANGLED_KEY = "Document_ID"

# CPFT hacks (RiO tables added to RCEP output):
CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES = "Progress_Notes_II"

# Columns in ONS Postcode Database (from CRATE import):
ONSPD_TABLE_POSTCODE = "postcode"
DEFAULT_GEOG_COLS = [
    "pcon", "pct", "nuts", "lea", "statsward", "casward",
    "lsoa01", "msoa01", "ur01ind", "oac01", "lsoa11",
    "msoa11", "parish", "bua11", "buasd11", "ru11ind",
    "oac11", "imd",
]

# Columns added:
CRATE_COL_PK = "crate_pk"
# Do NOT use 'id'; this appears in RiO ClientAlternativeId /
# RCEP Client_Alternative_ID. "pk" is OK for RCEP + RiO, but clarity is good
CRATE_COL_RIO_NUMBER = "crate_rio_number"
# "rio_number" is OK for RCEP + RiO, but clarity is good
CRATE_COL_NHS_NUMBER = "crate_nhs_number_int"
# "nhs_number_int" is OK for RCEP + RiO, but again...
# For RCEP, in SQL Server, check existing columns with:
#   USE database;
#   SELECT column_name, table_name
#       FROM information_schema.columns
#       WHERE column_name = 'something';
# For RiO, for now, check against documented table structure.

# For progress notes:
CRATE_COL_MAX_SUBNUM = "crate_max_subnum_for_notenum"
CRATE_COL_LAST_NOTE = "crate_last_note_in_edit_chain"
# For clinical documents:
CRATE_COL_MAX_DOCVER = "crate_max_docver_for_doc"
CRATE_COL_LAST_DOC = "crate_last_doc_in_chain"

# Indexes added... generic:
CRATE_IDX_PK = "crate_idx_pk"  # for any patient table
CRATE_IDX_RIONUM = "crate_idx_rionum"  # for any patient table
# For progress notes:
CRATE_IDX_RIONUM_NOTENUM = "crate_idx_rionum_notenum"
CRATE_IDX_MAX_SUBNUM = "crate_idx_max_subnum"
CRATE_IDX_LAST_NOTE = "crate_idx_last_note"
# For clinical documents:
CRATE_IDX_RIONUM_SERIALNUM = "crateidx_rionum_serialnum"
CRATE_IDX_MAX_DOCVER = "crate_idx_max_docver"
CRATE_IDX_LAST_DOC = "crate_idx_last_doc"

# Views added:
VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT = "progress_notes_current_crate"
VIEW_ADDRESS_WITH_GEOGRAPHY = "client_address_with_geography"
