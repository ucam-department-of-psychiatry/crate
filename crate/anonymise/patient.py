#!/usr/bin/env python3
# crate/anonymise/anon_patient.py

"""
Patient class for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 22 Nov 2015
Last update: 9 Mar 2016

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

import logging
log = logging.getLogger(__name__)

import cardinal_pythonlib.rnc_db as rnc_db

from crate.anonymise.constants import (
    MAX_TRID,
    RAW_SCRUBBER_FIELDNAME_PATIENT,
    RAW_SCRUBBER_FIELDNAME_TP,
    SCRUBSRC,
    SRCFLAG,
    TRID_CACHE_PID_FIELDNAME,
    TRID_CACHE_TRID_FIELDNAME,
)
from crate.anonymise.hash import RandomIntegerHasher
from crate.anonymise.scrub import PersonalizedScrubber


# =============================================================================
# Generate identifiable values for a patient
# =============================================================================

def gen_all_values_for_patient(sources, dbname, table, fields, pid, config):
    """
    Generate all sensitive (scrub_src) values for a given patient, from a given
    source table. Used to build the scrubber.

        sources: dictionary
            key: db name
            value: rnc_db database object
        dbname: source database name
        table: source table
        fields: source fields containing scrub_src information
        pid: patient ID

    Yields rows, where each row is a list of values that matches "fields".
    """
    cfg = config.srccfg[dbname]
    if not cfg.ddgen_per_table_pid_field:
        return
        # http://stackoverflow.com/questions/13243766
    log.debug(
        "gen_all_values_for_patient: PID {p}, table {d}.{t}, "
        "fields: {f}".format(
            d=dbname, t=table, f=",".join(fields), p=pid))
    db = sources[dbname]
    sql = rnc_db.get_sql_select_all_fields_by_key(
        table, fields, cfg.ddgen_per_table_pid_field, delims=db.get_delims())
    args = [pid]
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    while row is not None:
        yield row
        row = cursor.fetchone()


# =============================================================================
# Patient class, which hosts the patient-specific scrubber
# =============================================================================

class Patient(object):
    """Class representing a patient-specific information, such as PIDs, RIDs,
    and scrubbers."""

    def __init__(self, sources, pid, admindb, config, debug=False):
        """
        Build the scrubber based on data dictionary information.

            sources: dictionary
                key: db name
                value: rnc_db database object
            pid: integer patient identifier
        """
        self.pid = pid
        self.admindb = admindb
        self.config = config

        # ID information
        self.mpid = None
        self.trid = None
        self.rid = config.primary_pid_hasher.hash(pid)
        self.mrid = None
        # Scrubber
        self.scrubber = PersonalizedScrubber(
            anonymise_codes_at_word_boundaries_only=(
                config.anonymise_codes_at_word_boundaries_only),
            anonymise_dates_at_word_boundaries_only=(
                config.anonymise_dates_at_word_boundaries_only),
            anonymise_numbers_at_word_boundaries_only=(
                config.anonymise_numbers_at_word_boundaries_only),
            anonymise_strings_at_word_boundaries_only=(
                config.anonymise_strings_at_word_boundaries_only),
            debug=debug,
            hasher=config.change_detection_hasher,
            min_string_length_for_errors=config.min_string_length_for_errors,
            min_string_length_to_scrub_with=(
                config.min_string_length_to_scrub_with),
            nonspecific_scrubber=config.nonspecific_scrubber,
            replacement_text_patient=config.replace_patient_info_with,
            replacement_text_third_party=config.replace_third_party_info_with,
            scrub_string_suffixes=config.scrub_string_suffixes,
            string_max_regex_errors=config.string_max_regex_errors,
            whitelist=config.whitelist,
        )
        # TRID generator
        self.tridgen = RandomIntegerHasher(
            admindb,
            table=config.secret_trid_cache_tablename,
            inputfield=TRID_CACHE_PID_FIELDNAME,
            outputfield=TRID_CACHE_TRID_FIELDNAME,
            min_value=0,
            max_value=MAX_TRID)
        # Database
        # Construction. We go through all "scrub-from" fields in the data
        # dictionary. We collect all values of those fields from the source
        # database.
        log.debug("Building scrubber")
        db_table_pair_list = config.dd.get_scrub_from_db_table_pairs()
        for (src_db, src_table) in db_table_pair_list:
            # Build a list of fields for this table, and corresponding lists of
            # scrub methods and a couple of other flags.
            ddrows = config.dd.get_scrub_from_rows(src_db, src_table)
            fields = []
            scrub_methods = []
            is_patient = []
            is_mpid = []
            for ddr in ddrows:
                fields.append(ddr.src_field)
                scrub_methods.append(PersonalizedScrubber.get_scrub_method(
                    ddr.src_datatype, ddr.scrub_method))
                is_patient.append(ddr.scrub_src == SCRUBSRC.PATIENT)
                is_mpid.append(SRCFLAG.MASTERPID in ddr.src_flags)
            # Collect the actual patient-specific values for this table.
            for vlist in gen_all_values_for_patient(sources, src_db, src_table,
                                                    fields, pid, config):
                for i in range(len(vlist)):
                    self.scrubber.add_value(vlist[i],
                                            scrub_methods[i],
                                            is_patient[i])
                    if self.mpid is None and is_mpid[i]:
                        # We've come across the master ID.
                        self.mpid = vlist[i]
                        self.mrid = config.master_pid_hasher.hash(self.mpid)

    def get_pid(self):
        """Return the patient ID (PID)."""
        return self.pid

    def get_mpid(self):
        """Return the master patient ID (MPID)."""
        return self.mpid

    def get_rid(self):
        """Returns the RID (encrypted PID)."""
        return self.rid

    def get_mrid(self):
        """Returns the master RID (encrypted MPID)."""
        return self.mrid

    def get_trid(self):
        """Returns the transient integer RID (TRID)."""
        if self.trid is None:
            self.fetch_trid()
        return self.trid

    def get_scrubber_hash(self):
        return self.scrubber.get_hash()

    def scrub(self, text):
        return self.scrubber.scrub(text)

    def unchanged(self):
        """
        Has the scrubber changed, compared to the hashed version in the admin
        database?
        """
        sql = """
            SELECT 1
            FROM {table}
            WHERE {patient_id_field} = ?
            AND {scrubber_hash_field} = ?
        """.format(
            table=self.config.secret_map_tablename,
            patient_id_field=self.config.mapping_patient_id_fieldname,
            scrubber_hash_field=self.config.source_hash_fieldname,
        )
        row = self.admindb.fetchone(sql,
                                    self.get_pid(),
                                    self.get_scrubber_hash())
        return True if row is not None and row[0] == 1 else False

    def patient_in_map(self):
        """
        Is the patient in the PID/RID mapping table already?
        """
        sql = """
            SELECT 1
            FROM {table}
            WHERE {patient_id_field} = ?
        """.format(
            table=self.config.secret_map_tablename,
            patient_id_field=self.config.mapping_patient_id_fieldname,
        )
        row = self.admindb.fetchone(sql, self.get_pid())
        return True if row is not None and row[0] == 1 else False

    def save_to_mapping_db(self):
        """
        Insert patient information (including PID, RID, MPID, RID, and scrubber
        hash) into the mapping database. Establish the TRID as well.
        """
        log.debug("Inserting patient into mapping table")
        pid = self.get_pid()
        rid = self.get_rid()
        mpid = self.get_mpid()
        mrid = self.get_mrid()
        scrubber_hash = self.get_scrubber_hash()
        if self.config.save_scrubbers:
            raw_pt = self.scrubber.get_patient_regex_string()
            raw_tp = self.scrubber.get_tp_regex_string()
        else:
            raw_pt = None
            raw_tp = None
        if self.patient_in_map():
            sql = """
                UPDATE {table}
                SET {master_id} = ?,
                    {master_research_id} = ?,
                    {scrubber_hash} = ?,
                    {RAW_SCRUBBER_FIELDNAME_PATIENT} = ?,
                    {RAW_SCRUBBER_FIELDNAME_TP} = ?
                WHERE {patient_id} = ?
            """.format(
                table=self.config.secret_map_tablename,
                master_id=self.config.mapping_master_id_fieldname,
                master_research_id=self.config.master_research_id_fieldname,
                scrubber_hash=self.config.source_hash_fieldname,
                patient_id=self.config.mapping_patient_id_fieldname,
                RAW_SCRUBBER_FIELDNAME_PATIENT=RAW_SCRUBBER_FIELDNAME_PATIENT,
                RAW_SCRUBBER_FIELDNAME_TP=RAW_SCRUBBER_FIELDNAME_TP,
            )
            args = [mpid, mrid, scrubber_hash, raw_pt, raw_tp, pid]
        else:
            self.trid = self.tridgen.hash(self.pid)
            sql = """
                INSERT INTO {table} (
                    {patient_id},
                    {research_id},
                    {tridfield},
                    {master_id},
                    {master_research_id},
                    {scrubber_hash},
                    {RAW_SCRUBBER_FIELDNAME_PATIENT},
                    {RAW_SCRUBBER_FIELDNAME_TP}
                )
                VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
            """.format(
                table=self.config.secret_map_tablename,
                patient_id=self.config.mapping_patient_id_fieldname,
                research_id=self.config.research_id_fieldname,
                tridfield=self.config.trid_fieldname,
                master_id=self.config.mapping_master_id_fieldname,
                master_research_id=self.config.master_research_id_fieldname,
                scrubber_hash=self.config.source_hash_fieldname,
                RAW_SCRUBBER_FIELDNAME_PATIENT=RAW_SCRUBBER_FIELDNAME_PATIENT,
                RAW_SCRUBBER_FIELDNAME_TP=RAW_SCRUBBER_FIELDNAME_TP,
            )
            args = [pid, rid, self.trid, mpid,
                    mrid, scrubber_hash, raw_pt, raw_tp]
        self.admindb.db_exec(sql, *args)
        self.admindb.commit()
        # Commit immediately, because other processes may need this table
        # promptly. Otherwise, get:
        #   Deadlock found when trying to get lock; try restarting transaction

    def fetch_trid(self):
        """Fetch TRID from database."""
        sql = """
            SELECT {trid_field}
            FROM {table}
            WHERE {patient_id_field} = ?
        """.format(
            trid_field=self.config.trid_fieldname,
            table=self.config.secret_map_tablename,
            patient_id_field=self.config.mapping_patient_id_fieldname,
        )
        row = self.admindb.fetchone(sql, self.get_pid())
        self.trid = row[0] if row is not None else None
