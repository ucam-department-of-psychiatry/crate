#!/usr/bin/env python

"""
crate_anon/ancillary/timely_project/timely_filter_cpft_rio.py

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

Helper code for MRC TIMELY project (Moore, grant MR/T046430/1). Not of general
interest.

Information to filter CPFT RiO data dictionaries for TIMELY.

"""

# =============================================================================
# Imports
# =============================================================================

from crate_anon.ancillary.timely_project.dd_criteria import (
    add_field_criteria,
    add_table_criteria,
)
from crate_anon.ancillary.timely_project.timely_filter import TimelyDDFilter


# =============================================================================
# TimelyCPFTRiOFilter
# =============================================================================


class TimelyCPFTRiOFilter(TimelyDDFilter):
    """
    Filter a CPFT RiO data dictionary.
    """

    def __init__(self) -> None:
        super().__init__()

        # ---------------------------------------------------------------------
        # Generic exclusions
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.exclude_tables,
            stage=None,
            regex_strings=[
                "cpft_core_assessment_v2_kcsa_children_in_household",  #  about people other than the patient  # noqa
            ],
        )

        # ---------------------------------------------------------------------
        # Stage 1: demographics, problem lists, diagnoses, safeguarding,
        # contacts (e.g. referrals, contacts, discharge)
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.staged_include_tables,
            stage=1,
            regex_strings=[
                # Demographics
                "Client_Demographic_Details",  # basics
                "Client_Address_History",  # addresses blurred to LSOAs
                "Deceased",
                # Safeguarding
                "Client_Family",  # legal status codes, parental responsibility, etc.  # noqa
                "ClientAlert",
                # ClientAlertRemovalReason is an example of a system table -- it
                # doesn't relate to a patient. We include those automatically.
                "RskRelatedIncidents",  # BUT SEE field exclusions
                "RskRelatedIncidentsRiskType",
                # Basic contacts, e.g. start/end of care plan
                "Client_CPA",  # care plan start/end dates
                "Client_GP",  # GP practice registration
                "Client_School",  # school attended
                "ClientGPMerged",  # when GP practices merge, we think
                # Diagnosis/problems
                "ClientOtherSmoker",  # smoking detail
                "ClientSmoking",  # more smoking detail
                # ClientSocialFactor -- no data
                "Diagnosis",  # ICD-10 diagnoses
                "SNOMED.*",  # SNOMED-coded problems
                # Referrals (basic info)
                "Referral.*",  # includes ReferralCoding = diagnosis for referral (+ teams etc.)  # noqa
            ],
        )

        # Note that "UserAssess*" is where all the local custom additions to
        # RiO go. These are quite varied.

        # ---------------------------------------------------------------------
        # Stage 2: detailed information about all service contacts, including
        # professional types involved, procedures, outcome data, etc.
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.staged_include_tables,
            stage=2,
            regex_strings=[
                "Client_Professional_Contacts",
                "ClientHealthCareProviderAssumed",
                # Inpatient activity (IMS = inpatient management system)
                "Ims.*",
                "Inpatient.*",
                "IPAms.*",
                # Mnt = Mental Health Act
                "Mnt.*",
                "ParentGuardianImport",  # outcome data
            ],
        )

        # ---------------------------------------------------------------------
        # Stage 3: prescribing data
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.staged_include_tables,
            stage=3,
            regex_strings=[
                "Client_Allergies",  # for prescribing
                "Client_Medication",  # will be empty!
                "Client_Prescription",  # will be empty!
            ],
        )

        # ---------------------------------------------------------------------
        # Stage 4: test results, other health assessments, other clinical info
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.staged_include_tables,
            stage=4,
            regex_strings=[
                "Client_Physical_Details",  # e.g. head circumference
                "ClientMaternalDetail",  # patients who are mothers
                "ClientPhysicalDetailMerged",  # e.g. height, weight
            ],
        )

        # ---------------------------------------------------------------------
        # Stage 5: (structured) info on care plans etc.
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.staged_include_tables,
            stage=5,
            regex_strings=[
                # Care plans, Care Plan Approach, care coordination
                "Care_Plan.*",
                "CarePlan.*",
                "CareCoordinatorOccupation",
                "CPA.*",
            ],
        )

        # ---------------------------------------------------------------------
        # Stage 6: de-identified free text
        # ---------------------------------------------------------------------

        add_table_criteria(
            self.staged_include_tables,
            stage=6,
            regex_strings=[
                "Clinical_Documents",
                "CPFT_Core_Assessment.*",
                "Progress_Note",
                "RskRelatedIncidents",
                "UserAssessCAMH",  # CAMH-specific assessments (e.g. questionnaires) -- can have free-text comments.  # noqa
            ],
        )

        # ---------------------------------------------------------------------
        # Specific fields
        # ---------------------------------------------------------------------
        # Specific fields to exclude that would otherwise be included.
        # List of (tablename, fieldname) regex string tuples.

        add_field_criteria(
            self.staged_exclude_fields,
            stage=5,
            regex_tuples=[
                # "exclude at stage 5 or earlier"
                ("Client_School", "Change_Reason"),
                ("ClientAlert", "Comment"),
                ("ClientAlert", "RemovalComment"),
                ("Diagnosis", "Comment"),
                # NB Diagnosis.Diagnosis is fine -- ICD-10 text only
                ("Diagnosis", "RemovalComment"),
                ("Referral$", "Discharge_Comment"),
                ("Referral$", "IWS_Comment"),
                ("Referral$", "Referral_Comment"),
                ("Referral_Staff_History", "Comment"),
                ("Referral_Team_History", "Comment"),
                ("RskRelatedIncidents", "Text"),
                # SNOMED_Client.SC_Ass_ElementID: should not be free-text
                # SNOMED_Client.SC_Ass_FormName: should not be free-text
                ("SNOMED_Client", "SC_Comment"),
                (
                    "SNOMED_Client",
                    "SC_WrapperXML",
                ),  # unlikely to be free text but unsure  # noqa
                # More generally, anything that says "Comment" should be filtered:
                (".+", ".*Comment"),
            ],
        )
