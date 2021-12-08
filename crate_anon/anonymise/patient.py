#!/usr/bin/env python

"""
crate_anon/anonymise/patient.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Patient class for CRATE anonymiser. Represents patient-specific information
like ID values and scrubbers.**

"""

import logging
from typing import AbstractSet, Any, Generator, List, Union

from sqlalchemy.orm.session import Session
from sqlalchemy.sql import column, select, table

from crate_anon.anonymise.config_singleton import config
from crate_anon.anonymise.dd import ScrubSourceFieldInfo
from crate_anon.anonymise.models import PatientInfo
from crate_anon.anonymise.scrub import PersonalizedScrubber

log = logging.getLogger(__name__)


# =============================================================================
# Generate identifiable values for a patient
# =============================================================================

def gen_all_values_for_patient(
        session: Session,
        tablename: str,
        scrub_src_fieldinfo: List[ScrubSourceFieldInfo],
        pid_field: str,
        pid: Union[int, str]) -> Generator[List[Any], None, None]:
    """
    Generate all sensitive (``scrub_src``) values for a given patient, from a
    given source table. Used to build the scrubber.

    Args:
        session:
            database session
        tablename:
            source table
        scrub_src_fieldinfo:
            list of information about the scrub-source fields
        pid_field:
            field to query for patient ID
        pid:
            patient ID

    Yields:
         rows, where each row is a list of values that matches
         ``scrub_src_fieldinfo``.
    """
    query = (
        select([column(i.value_fieldname) for i in scrub_src_fieldinfo])
        .where(column(pid_field) == pid)
        .select_from(table(tablename))
    )
    result = session.execute(query)
    for row in result:
        log.debug(f"... gen_all_values_for_patient yielding row: {row}")
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
        self._pid = pid
        self._session = config.admindb.session

        # Fetch or create PatientInfo object
        self._info = self._session.query(PatientInfo).get(pid)
        if self._info is None:
            self._info = PatientInfo(pid=pid)
            self._info.ensure_rid()
            self._info.ensure_trid(self._session)
            self._session.add(self._info)
            self._session.commit()
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
            allowlist=config.allowlist,
            alternatives=config.phrase_alternative_words,
        )

        # Add information to the scrubber from the database.
        # We go through all "scrub-from" fields in the data dictionary. We
        # collect all values of those fields from the source database.
        log.debug(f"Building scrubber: pid = {pid!r}")
        self._third_party_pids_seen = set()
        self._db_table_pair_list = config.dd.get_scrub_from_db_table_pairs()
        self._mandatory_scrubbers_unfulfilled = \
            config.dd.get_mandatory_scrubber_sigs().copy()
        self._build_scrubber(pid,
                             depth=0,
                             max_depth=config.thirdparty_xref_max_depth)
        self._unchanged = self.scrubber_hash == self._info.scrubber_hash
        self._info.set_scrubber_info(self.scrubber)
        self._session.commit()
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
            pid:
                Integer or string (usually integer) patient identifier.
            depth:
                Current recursion depth for third-party information. If this
                is greater than 0, we are dealing with third-party information.
            max_depth:
                Maximum recursion depth for third-party information.
        """
        if depth > 0:
            log.debug(f"Building scrubber recursively: depth = {depth}")
        # ---------------------------------------------------------------------
        # For all source tables with scrub-source information...
        # ---------------------------------------------------------------------
        for (src_db, src_table) in self._db_table_pair_list:
            session = config.sources[src_db].session
            # -----------------------------------------------------------------
            # Build a list of scrub-from fields for this table.
            # -----------------------------------------------------------------
            scrubsrc_infolist = config.dd.get_scrub_from_rows_as_fieldinfo(
                src_db=src_db,
                src_table=src_table,
                depth=depth,
                max_depth=max_depth,
            )
            pid_field = config.dd.get_pid_name(src_db, src_table)
            if not pid_field:
                # Shouldn't happen -- part of the data dictionary checks.
                raise ValueError(f"Scrub-source table {src_db}.{src_table} "
                                 f"has no identifiable patient ID field")
            # -----------------------------------------------------------------
            # Collect the actual patient-specific values for this table.
            # -----------------------------------------------------------------
            for values in gen_all_values_for_patient(
                    session=session,
                    tablename=src_table,
                    scrub_src_fieldinfo=scrubsrc_infolist,
                    pid_field=pid_field,
                    pid=pid):
                for i, val in enumerate(values):
                    # ---------------------------------------------------------
                    # Add a value to the scrubber
                    # ---------------------------------------------------------
                    info = scrubsrc_infolist[i]
                    self.scrubber.add_value(val, info.scrub_method,
                                            patient=info.is_patient)

                    if info.is_mpid and self.mpid is None:
                        # -----------------------------------------------------
                        # We've come across the MPID for the first time.
                        # -----------------------------------------------------
                        self.set_mpid(val)

                    if info.recurse:
                        # -----------------------------------------------------
                        # We've come across a patient ID of another patient,
                        # whose information should be trawled and treated as
                        # third-party information
                        # -----------------------------------------------------
                        try:
                            related_pid = int(val)
                        except (ValueError, TypeError):
                            # TypeError: NULL value (None)
                            # ValueError: duff value, i.e. non-integer
                            continue
                        if related_pid in self._third_party_pids_seen:
                            # Don't bother doing the same relative twice (if
                            # their ID occurs in more than one place in the
                            # patient's record); that's inefficient.
                            continue
                        self._third_party_pids_seen.add(related_pid)
                        # Go and explore that other patient's record:
                        self._build_scrubber(related_pid, depth + 1, max_depth)

                    # If this is a mandatory scrubber, note if its requirement
                    # has been fulfilled.
                    if val is not None and info.required_scrubber:
                        self._mandatory_scrubbers_unfulfilled.discard(
                            info.signature
                        )

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

    @property
    def pid(self) -> Union[int, str]:
        """
        Return the patient ID (PID).
        """
        return self._info.pid

    @property
    def mpid(self) -> Union[int, str]:
        """
        Return the master patient ID (MPID).
        """
        return self._info.mpid

    def set_mpid(self, mpid: Union[int, str]) -> None:
        """
        Set the patient MPID.
        """
        self._info.set_mpid(mpid)

    @property
    def rid(self) -> str:
        """
        Returns the RID (encrypted PID).
        """
        return self._info.rid

    @property
    def mrid(self) -> str:
        """
        Returns the master RID (encrypted MPID).
        """
        return self._info.mrid

    @property
    def trid(self) -> int:
        """
        Returns the transient integer RID (TRID).
        """
        return self._info.trid

    @property
    def scrubber_hash(self) -> str:
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

    def is_unchanged(self) -> bool:
        """
        Has the scrubber changed, compared to the previous hashed version in
        the admin database?
        """
        return self._unchanged
