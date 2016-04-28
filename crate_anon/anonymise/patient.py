#!/usr/bin/env python3
# crate_anon/anonymise/anon_patient.py

"""
Patient class for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 22 Nov 2015
Last update: 9 Mar 2016

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
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

from sqlalchemy.sql import column, select, table

from crate_anon.anonymise.config import config
from crate_anon.anonymise.constants import (
    SCRUBSRC,
    SRCFLAG,
)
from crate_anon.anonymise.models import PatientInfo
from crate_anon.anonymise.scrub import PersonalizedScrubber

log = logging.getLogger(__name__)


# =============================================================================
# Generate identifiable values for a patient
# =============================================================================

def gen_all_values_for_patient(dbname, tablename, fields, pid):
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
    cfg = config.sources[dbname].srccfg
    if not cfg.ddgen_per_table_pid_field:
        return
        # http://stackoverflow.com/questions/13243766
    log.debug(
        "gen_all_values_for_patient: PID {p}, table {d}.{t}, "
        "fields: {f}".format(
            d=dbname, t=tablename, f=",".join(fields), p=pid))
    session = config.sources[dbname].session
    query = (
        select([column(f) for f in fields]).
        where(column(cfg.ddgen_per_table_pid_field) == pid).
        select_from(table(tablename))
    )
    result = session.execute(query)
    for row in result:
        log.debug("... yielding row: {}".format(row))
        yield row


# =============================================================================
# Patient class, which hosts the patient-specific scrubber
# =============================================================================

class Patient(object):
    """Class representing a patient-specific information, such as PIDs, RIDs,
    and scrubbers."""

    def __init__(self, pid, debug=False):
        """
        Build the scrubber based on data dictionary information.

            sources: dictionary
                key: db name
                value: rnc_db database object
            pid: integer patient identifier
        """
        self.pid = pid
        self.session = config.admindb.session

        # Fetch or create PatientInfo object
        self.info = self.session.query(PatientInfo).get(pid)
        if self.info is None:
            self.info = PatientInfo(pid=pid)
            self.info.ensure_rid()
            self.info.ensure_trid(self.session)
            self.session.add(self.info)
            self.session.commit()
            # prompt commit after insert operations, to ensure no locks

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
            for values in gen_all_values_for_patient(src_db, src_table,
                                                     fields, pid):
                for i, val in enumerate(values):
                    self.scrubber.add_value(val,
                                            scrub_methods[i],
                                            is_patient[i])
                    if is_mpid[i] and self.get_mpid():
                        # We've come across the master ID.
                        self.set_mpid(val)

        self._unchanged = self.get_scrubber_hash() == self.info.scrubber_hash
        self.info.set_scrubber_info(self.scrubber)
        self.session.commit()
        # Commit immediately, because other processes may need this table
        # promptly. Otherwise, might get:
        #   Deadlock found when trying to get lock; try restarting transaction

    def get_pid(self):
        """Return the patient ID (PID)."""
        return self.info.pid

    def get_mpid(self):
        """Return the master patient ID (MPID)."""
        return self.info.mpid

    def set_mpid(self, mpid):
        self.info.set_mpid(mpid)

    def get_rid(self):
        """Returns the RID (encrypted PID)."""
        return self.info.rid

    def get_mrid(self):
        """Returns the master RID (encrypted MPID)."""
        return self.info.mrid

    def get_trid(self):
        """Returns the transient integer RID (TRID)."""
        return self.info.trid

    def get_scrubber_hash(self):
        return self.scrubber.get_hash()

    def scrub(self, text):
        return self.scrubber.scrub(text)

    def unchanged(self):
        """
        Has the scrubber changed, compared to the previous hashed version in
        the admin database?
        """
        return self._unchanged
