#!/usr/bin/env python

"""
crate_anon/anonymise/patient.py

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

**Patient class for CRATE anonymiser. Represents patient-specific information
like ID values and scrubbers.**

"""

import logging
from typing import AbstractSet, Any, Generator, List, Union

from sqlalchemy.sql import column, select, table

from crate_anon.anonymise.config_singleton import config
from crate_anon.anonymise.constants import SCRUBSRC
from crate_anon.anonymise.models import PatientInfo
from crate_anon.anonymise.scrub import PersonalizedScrubber

log = logging.getLogger(__name__)


# =============================================================================
# Generate identifiable values for a patient
# =============================================================================

def gen_all_values_for_patient(
        dbname: str,
        tablename: str,
        fields: List[str],
        pid: Union[int, str]) -> Generator[List[Any], None, None]:
    """
    Generate all sensitive (``scrub_src``) values for a given patient, from a
    given source table. Used to build the scrubber.

    Args:

        dbname: source database name
        tablename: source table
        fields: list of source fields containing ``scrub_src`` information
        pid: patient ID

    Yields:
         rows, where each row is a list of values that matches ``fields``.
    """
    cfg = config.sources[dbname].srccfg
    if not cfg.ddgen_per_table_pid_field:
        return
        # return in a generator: http://stackoverflow.com/questions/13243766
    log.debug(
        f"gen_all_values_for_patient: PID {pid}, "
        f"table {dbname}.{tablename}, fields: {','.join(fields)}")
    session = config.sources[dbname].session
    query = (
        select([column(f) for f in fields]).
        where(column(cfg.ddgen_per_table_pid_field) == pid).
        select_from(table(tablename))
    )
    result = session.execute(query)
    for row in result:
        log.debug(f"... yielding row: {row}")
        yield row


# =============================================================================
# Patient class, which hosts the patient-specific scrubber
# =============================================================================

class Patient(object):
    """
    Class representing a patient-specific information, such as PIDs, RIDs, and
    scrubbers.
    """

    def __init__(self, pid: Union[int, str], debug: bool = False) -> None:
        """
        Build the scrubber based on data dictionary information, found via
        our singleton :class:`crate_anon.anonymise.config.Config`.

        Args:
            pid: integer or string (usually integer) patient identifier
            debug: turn on scrubber debugging?
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
            anonymise_numbers_at_numeric_boundaries_only=(
                config.anonymise_numbers_at_numeric_boundaries_only),
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
            alternatives=config.phrase_alternative_words,
        )
        # Database
        # Construction. We go through all "scrub-from" fields in the data
        # dictionary. We collect all values of those fields from the source
        # database.
        log.debug("Building scrubber")
        self._db_table_pair_list = config.dd.get_scrub_from_db_table_pairs()
        self._mandatory_scrubbers_unfulfilled = \
            config.dd.get_mandatory_scrubber_sigs().copy()
        self._build_scrubber(pid,
                             depth=0,
                             max_depth=config.thirdparty_xref_max_depth)
        self._unchanged = self.get_scrubber_hash() == self.info.scrubber_hash
        self.info.set_scrubber_info(self.scrubber)
        self.session.commit()
        # Commit immediately, because other processes may need this table
        # promptly. Otherwise, might get:
        #   Deadlock found when trying to get lock; try restarting transaction

    def _build_scrubber(self,
                        pid: Union[int, str],
                        depth: int,
                        max_depth: int) -> None:
        """
        Build the scrubber for this patient.

        We do this by finding all this patient's values within the "scrub from"
        columns of the source database, and adding them to our patient scrubber
        (or third-party scrubber as the case may be, for information about
        relatives etc.), according to the scrub method defined in the data
        dictionary row.

        Args:
            pid: integer or string (usually integer) patient identifier
            depth: current recursion depth for third-party information
            max_depth: maximum recursion depth for third-party information
        """
        if depth > 0:
            log.debug(f"Building scrubber recursively: depth = {depth}")
        # ---------------------------------------------------------------------
        # For all source tables...
        # ---------------------------------------------------------------------
        for (src_db, src_table) in self._db_table_pair_list:
            # -----------------------------------------------------------------
            # Build a list of scrub-from fields for this table.
            # -----------------------------------------------------------------
            ddrows = config.dd.get_scrub_from_rows(src_db, src_table)
            fields = [ddr.src_field for ddr in ddrows]
            # Precalculate things; we might being going through a lot of values
            scrub_method = [
                PersonalizedScrubber.get_scrub_method(ddr.src_datatype,
                                                      ddr.scrub_method)
                for ddr in ddrows
            ]
            is_patient = [depth == 0 and ddr.scrub_src is SCRUBSRC.PATIENT
                          for ddr in ddrows]
            is_mpid = [depth == 0 and ddr.master_pid for ddr in ddrows]
            recurse = [depth < max_depth and
                       ddr.scrub_src is SCRUBSRC.THIRDPARTY_XREF_PID
                       for ddr in ddrows]
            required_scrubber = [ddr.required_scrubber for ddr in ddrows]
            sigs = [ddr.get_signature() for ddr in ddrows]
            # -----------------------------------------------------------------
            # Collect the actual patient-specific values for this table.
            # -----------------------------------------------------------------
            for values in gen_all_values_for_patient(src_db, src_table,
                                                     fields, pid):
                for i, val in enumerate(values):
                    # ---------------------------------------------------------
                    # Add a value to the scrubber
                    # ---------------------------------------------------------
                    self.scrubber.add_value(val, scrub_method[i],
                                            patient=is_patient[i])

                    if is_mpid[i] and self.get_mpid() is None:
                        # We've come across the master ID.
                        self.set_mpid(val)

                    if recurse[i]:
                        # -----------------------------------------------------
                        # We've come across a patient ID of another patient,
                        # whose information should be trawled and treated
                        # as third-party information
                        # -----------------------------------------------------
                        try:
                            related_pid = int(val)
                        except (ValueError, TypeError):
                            # TypeError: NULL value (None)
                            # ValueError: duff value, i.e. non-integer
                            continue
                        self._build_scrubber(related_pid, depth + 1, max_depth)

                    if val is not None and required_scrubber[i]:
                        self._mandatory_scrubbers_unfulfilled.discard(sigs[i])

    @property
    def mandatory_scrubbers_unfulfilled(self) -> AbstractSet[str]:
        """
        Returns a set of strings (each of the format ``db.table.column``) for
        all "required scrubber" fields that have not yet had information seen
        for them (for this patient), and are therefore unfulfilled.

        See also
        :meth:`crate_anon.anonymise.dd.DataDictionary.get_mandatory_scrubber_sigs`.
        """  # noqa
        return self._mandatory_scrubbers_unfulfilled

    def get_pid(self) -> Union[int, str]:
        """
        Return the patient ID (PID).
        """
        return self.info.pid

    def get_mpid(self) -> Union[int, str]:
        """
        Return the master patient ID (MPID).
        """
        return self.info.mpid

    def set_mpid(self, mpid: Union[int, str]) -> None:
        """
        Set the patient MPID.
        """
        self.info.set_mpid(mpid)

    def get_rid(self) -> str:
        """
        Returns the RID (encrypted PID).
        """
        return self.info.rid

    def get_mrid(self) -> str:
        """
        Returns the master RID (encrypted MPID).
        """
        return self.info.mrid

    def get_trid(self) -> int:
        """
        Returns the transient integer RID (TRID).
        """
        return self.info.trid

    def get_scrubber_hash(self) -> str:
        """
        Return the hash of our scrubber (for change detection).
        """
        return self.scrubber.get_hash()

    def scrub(self, text: str) -> str:
        """
        Use our scrubber to scrub text.

        Args:
            text: the raw text, potentially containing sensitive information

        Returns:
            the de-identified text
        """
        return self.scrubber.scrub(text)

    def unchanged(self) -> bool:
        """
        Has the scrubber changed, compared to the previous hashed version in
        the admin database?
        """
        return self._unchanged
