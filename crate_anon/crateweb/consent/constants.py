#!/usr/bin/env python

"""
crate_anon/crateweb/consent/constants.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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

**Constants for the consent-to-contact system.**

"""

from dataclasses import dataclass


@dataclass
class EthicsDocInfo:
    title: str
    version: str
    date: str


class EthicsInfo:
    IRAS_NUMBER = "?"
    REC_REFERENCE = "?"

    # People/entities:
    # - C clinician
    # - R researcher
    # - P patient
    # - D research database manager or automatic (CRATE)
    # LTR letter: next elements are from, to, subject.
    # In sequence (per IRAS):
    LTR_PT_FIRST_TRAFFIC_LIGHT = "letter_patient_first_traffic_light"
    FORM_TRAFFIC_GENERIC = "traffic_light_decision_form_generic"
    FORM_TRAFFIC_PERSONALIZED = "traffic_light_decision_form_personalized"
    LTR_D_P_CONFIRM_TRAFFIC = "letter_patient_confirm_traffic"
    LTR_C_P_STUDY = "letter_patient_from_clinician_re_study"
    FORM_STUDY = "decision_form_to_patient_re_study"
    LTR_D_R_APPROVAL = "letter_researcher_approve"
    LTR_R_P_STUDY_TEMPLATE = (
        "letter_researcher_to_patient_cover_letter_template"
    )
    LTR_D_R_WITHDRAWAL = "letter_researcher_withdraw"

    def get_docinfo(self, doccode: str) -> EthicsDocInfo:
        raise NotImplementedError


class CPFTEthics2022(EthicsInfo):
    """
    Values for CPFT's ethics approval of the CPFT Research Database. Of no
    interest to others! Reason: all patient-facing documentation should have
    a footer including

    - IRAS number
    - NHS REC number
    - Title
    - Version number
    - Date
    """

    # 2022 approvals:
    IRAS_NUMBER = "319851"
    REC_REFERENCE = "22/EE/0264"

    _DATE_MOST = "2022-09-18"
    _DATE = "2022-10-10"  # submission date

    def __init__(self) -> None:
        self._docinfo = {
            # Titles from IRAS.
            self.LTR_PT_FIRST_TRAFFIC_LIGHT: EthicsDocInfo(
                # IRAS doc #09
                title="Clinician to patient cover letter re traffic light",
                version="1",
                date=self._DATE_MOST,
            ),
            self.FORM_TRAFFIC_GENERIC: EthicsDocInfo(
                # IRAS doc #10
                title="Traffic light decision form",
                version="2",
                date="2022-10-06",
            ),
            self.FORM_TRAFFIC_PERSONALIZED: EthicsDocInfo(
                # IRAS doc #11
                title="Traffic light decision form (personalised)",
                version="2",
                date="2022-10-06",
            ),
            self.LTR_D_P_CONFIRM_TRAFFIC: EthicsDocInfo(
                # IRAS doc #12
                title="RDBM to patient confirming traffic light choice",
                version="1",
                date=self._DATE_MOST,
            ),
            self.LTR_C_P_STUDY: EthicsDocInfo(
                # IRAS docs #16, #17
                title="Clinician to patient cover letter for a specific study",
                version="1",
                date=self._DATE_MOST,
            ),
            self.FORM_STUDY: EthicsDocInfo(
                # IRAS docs #18, 19
                title="Decision form about a specific study",
                version="1",
                date=self._DATE_MOST,
            ),
            self.LTR_D_R_APPROVAL: EthicsDocInfo(
                # IRAS doc #20
                title="RDBM to researcher giving permission to contact",
                version="1",
                date=self._DATE_MOST,
            ),
            self.LTR_R_P_STUDY_TEMPLATE: EthicsDocInfo(
                # IRAS doc #21
                title="Researcher cover letter to patient",
                version="1",
                date=self._DATE_MOST,
            ),
            self.LTR_D_R_WITHDRAWAL: EthicsDocInfo(
                # IRAS doc #22
                title="RDBM to researcher when patient withdraws consent",
                version="1",
                date=self._DATE_MOST,
            ),
        }

    def get_docinfo(self, doccode: str) -> EthicsDocInfo:
        return self._docinfo[doccode]
