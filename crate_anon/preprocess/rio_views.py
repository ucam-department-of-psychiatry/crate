#!/usr/bin/env python

"""
crate_anon/preprocess/rio_views.py

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

**Constants that define RiO views we want to create.**

"""

from collections import OrderedDict

from cardinal_pythonlib.dicts import merge_dicts

from crate_anon.common.sql import sql_fragment_cast_to_int
from crate_anon.preprocess.rio_constants import (
    VIEW_ADDRESS_WITH_GEOGRAPHY,
)
from crate_anon.preprocess.rio_view_func import (
    add_index_only,
    rio_add_bay_lookup,
    rio_add_carespell_lookup,
    rio_add_consultant_lookup,
    rio_add_diagnosis_lookup,
    rio_add_gp_lookup,
    rio_add_gp_practice_lookup,
    rio_add_ims_event_lookup,
    rio_add_location_lookup,
    rio_add_org_contact_lookup,
    rio_add_team_lookup,
    rio_add_user_lookup,
    rio_amend_standard_noncore,
    rio_noncore_yn,
    simple_lookup_join,
    simple_view_expr,
    # simple_view_where,
    standard_rio_code_lookup,
    standard_rio_code_lookup_with_national_code,
    where_allergies_current,
    where_clindocs_current,
    where_not_deleted_flag,
    where_prognotes_current,
)


# =============================================================================
# RiO view creators: collection
# =============================================================================

# Quickest way to develop these: open
# 1. RiO information schema
#    SELECT *
#    FROM <databasename>.information_schema.columns
#    -- +/- WHERE column_name NOT LIKE 'crate_%'
#    ORDER BY table_name, ordinal_position
# 2. RiO data model reference guide
# 3. RCEP information schema

DEFAULT_NONCORE_RENAMES = {
    # Identifiers:
    'ClientID': None,  # we have crate_rio_number instead
    'NHSNum': None,  # not needed and would have to scrub

    # System:
    'system_ValidationData': 'system_Validation_Data',
    'ServRef': None,  # e.g. "I6337", "R47800"; ?internal reference
    'formref': None,

    # Relevant:
    'type12_NoteID': 'Note_ID',
    'type12_OriginalNoteID': 'Original_Note_ID',
    'type12_DeletedDate': 'Deleted_Date',  # also filtered on
    'type12_UpdatedBy': None,  # user lookup
    'type12_UpdatedDate': 'Updated_Date',

    # Common to all assessments:
    'AssessmentDate': 'Assessment_Date',

    # For subtables:
    'type12_RowID': 'Row_ID',
    'type12_OriginalRowID': 'Original_Row_ID',
}

RIO_VIEWS = OrderedDict([
    # An OrderedDict in case you wanted to make views from views.
    # But that is a silly idea.

    # -------------------------------------------------------------------------
    # Template
    # -------------------------------------------------------------------------

    # ('XXX', {
    #     'basetable': 'XXX',
    #     'rename': {
    #         'XXX': 'XXX',  #
    #         'XXX': None,  #
    #     },
    #     'add': [
    #         {
    #             'function': simple_view_expr,
    #             'kwargs': {
    #                 'expr': 'XXX',
    #                 'alias': 'XXX',
    #             },
    #         },
    #         {
    #             'function': simple_lookup_join,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'lookup_table': 'XXX',
    #                 'lookup_pk': 'XXX',
    #                 'lookup_fields_aliases': {
    #                     'XXX': 'XXX',
    #                 },
    #                 'internal_alias_prefix': 'XXX',
    #             }
    #         },
    #         {
    #             'function': standard_rio_code_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'lookup_table': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': standard_rio_code_lookup_with_national_code,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'lookup_table': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             }
    #         },
    #         {
    #             'function': rio_add_user_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_consultant_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_team_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_carespell_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_diagnosis_lookup,
    #             'kwargs': {
    #                 'basecolumn_scheme': 'XXX',
    #                 'basecolumn_code': 'XXX',
    #                 'alias_scheme': 'XXX',
    #                 'alias_code': 'XXX',
    #                 'alias_description': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             }
    #         },
    #         {
    #             'function': rio_add_ims_event_lookup,
    #             'kwargs': {
    #                 'basecolumn_event_num': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_gp_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_bay_lookup,
    #             'kwargs': {
    #                 'basecolumn_ward': 'XXX',
    #                 'basecolumn_bay': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_location_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': simple_view_where,
    #             'kwargs': {
    #                 'where_clause': 'XXX',
    #                 'index_cols': [],
    #             },
    #         },
    #         {
    #             'function': add_index_only,
    #             'kwargs': {
    #                 'table': 'XXX',
    #                 'column_or_columns': 'XXX',  # or ['aaa', 'bbb', ...]
    #             },
    #         },
    #     ],
    #     'suppress_basetable': True,
    #     'suppress_other_tables': [],
    #     'enforce_same_n_rows_as_base': True,
    # }),

    # -------------------------------------------------------------------------
    # Core: views provided by RCEP (with some extensions)
    # -------------------------------------------------------------------------

    # 'assessmentsCRISSpec' is RCEP internal for CRIS tree/form/field/... info

    ('Care_Plan_Index', {
        'basetable': 'CarePlanIndex',
        'rename': {
            'CarePlanID': 'Care_Plan_ID',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'StartUserID': None,  # user lookup
            'EndUserID': None,  # user lookup
            'EndReason': None,  # "Obsolete field"
            'CarePlanType': None,  # lookup below
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'StartUserID',
                    'column_prefix': 'Start_User',  # RCEP
                    'internal_alias_prefix': 'su',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'EndUserID',
                    'column_prefix': 'End_User',  # RCEP
                    'internal_alias_prefix': 'eu',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'CarePlanType',
                    'lookup_table': 'CarePlanType',
                    'column_prefix': 'Care_Plan_Type',  # RCEP
                    'internal_alias_prefix': 'cpt',
                },
            },
        ],
    }),

    ('Care_Plan_Interventions', {
        'basetable': 'CarePlanInterventions',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'ProblemID': 'Problem_FK_Care_Plan_Problems',  # RCEP: Problem_Key
            'InterventionID': 'Intervention_Key',  # RCEP; non-unique
            'Box1': 'Box_1',  # not in RCEP
            'Box2': 'Box_2',  # not in RCEP
            'Box3': 'Box_3',  # not in RCEP
            'Box4': 'Box_4',  # not in RCEP
            'Box5': 'Box_5',  # not in RCEP
            'Box6': 'Box_6',  # not in RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'UserID': None,  # user lookup
            'EntryDate': 'Entry_Date',  # RCEP
            'InterventionType': None,  # lookup below
            'OutCome': None,  # lookup below
            # Comment: unchanged
            'Picklist1Code': 'Picklist_1_Code',  # not in RCEP
            'Picklist1Description': 'Picklist_1_Description',  # not in RCEP
            'Picklist2Code': 'Picklist_2_Code',  # not in RCEP
            'Picklist2Description': 'Picklist_2_Description',  # not in RCEP
            'Picklist3Code': 'Picklist_3_Code',  # not in RCEP
            'Picklist3Description': 'Picklist_3_Description',  # not in RCEP
            'DateField1': 'Date_Field_1',  # not in RCEP
            'DateField2': 'Date_Field_2',  # not in RCEP
            'LibraryID': 'Library_ID',  # not in RCEP
            'LibraryEdited': 'Library_Edited',  # not in RCEP
            'SequenceID': 'Unique_Key',  # RCEP
            'InterventionCategory': None,  # lookup below
            'CheckBox1': 'Check_Box_1',  # not in RCEP
            'CheckBox2': 'Check_Box_2',  # not in RCEP
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'UserID',
                    'column_prefix': 'User',  # RCEP
                    'internal_alias_prefix': 'u',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'InterventionType',
                    'lookup_table': 'CarePlanInterventionTypes',
                    'column_prefix': 'Intervention_Type',
                    # ... RCEP, except RCEP had InterventionType_Code
                    'internal_alias_prefix': 'it',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Outcome',
                    'lookup_table': 'CarePlanInterventionOutcomes',
                    'column_prefix': 'Outcome',  # RCEP
                    'internal_alias_prefix': 'od',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'InterventionCategory',
                    'lookup_table': 'CarePlanInterventionCategory',
                    'column_prefix': 'Intervention_Category',  # RCEP
                    'internal_alias_prefix': 'ic',
                },
            },
        ],
    }),

    ('Care_Plan_Problems', {
        'basetable': 'CarePlanProblems',
        'rename': {
            'ProblemID': 'Problem_ID',  # RCEP
            'CarePlanID': 'Care_Plan_ID_FK_Care_Plan_Index',  # RCEP: was Care_Plan_ID  # noqa
            'Text': 'Text',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'UserID': None,  # user lookup
            'EntryDate': 'Entry_Date',  # RCEP
            'ProblemType': None,  # lookup below
            'OutCome': None,  # lookup below
            # Comment: unchanged
            'LibraryID': 'Library_ID',  # not in RCEP
            'LibraryEdited': 'Library_Edited',  # not in RCEP
            'SequenceID': 'Unique_Key',  # RCEP
            'ProblemCategory': None,  # lookup below
            'ProblemDate': 'Problem_Date',  # RCEP; not in RiO 6.2 docs
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'UserID',
                    'column_prefix': 'User',  # RCEP
                    'internal_alias_prefix': 'u',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ProblemType',
                    'lookup_table': 'CarePlanProblemTypes',
                    'column_prefix': 'Problem_Type',  # RCEP
                    'internal_alias_prefix': 'pt',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'OutCome',
                    'lookup_table': 'CarePlanProblemOutcomes',
                    'column_prefix': 'Outcome',  # RCEP
                    'internal_alias_prefix': 'oc',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ProblemCategory',
                    'lookup_table': 'CarePlanProblemCategory',
                    'column_prefix': 'Problem_Category',  # RCEP
                    'internal_alias_prefix': 'pc',
                },
            },
        ],
    }),

    ('Client_Address_History', {
        'basetable': VIEW_ADDRESS_WITH_GEOGRAPHY,  # original: 'ClientAddress'
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'FromDate': 'Address_From_Date',  # RCEP
            'ToDate': 'Address_To_Date',  # RCEP
            'AddressLine1': 'Address_Line_1',  # RCEP
            'AddressLine2': 'Address_Line_2',  # RCEP
            'AddressLine3': 'Address_Line_3',  # RCEP
            'AddressLine4': 'Address_Line_4',  # RCEP
            'AddressLine5': 'Address_Line_5',  # RCEP
            'PostCode': 'Post_Code',  # RCEP
            'ElectoralWard': None,  # lookup below
            'MailsortCode': 'Mailsort_Code',  # RCEP
            'PrimaryCareGroup': None,  # lookup below
            'HealthAuthority': None,  # lookup below
            'SequenceID': 'Unique_Key',  # RCEP
            'LastUpdated': 'Last_Updated',  # RCEP
            'AddressType': None,  # lookup below
            'AccommodationType': None,  # lookup below
            'AddressGroup': 'Address_Group',  # RCEP; ?nature; RiO docs wrong
            'PAFKey': None,  # NHS Spine interaction field
            'SpineID': None,  # NHS Spine interaction field
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ElectoralWard',
                    'lookup_table': 'GenElectoralWard',
                    'column_prefix': 'Electoral_Ward',
                    'internal_alias_prefix': 'ew',
                    # ... RCEP: code was Electoral_Ward and description absent
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'PrimaryCareGroup',
                    'lookup_table': 'GenPCG',
                    'column_prefix': 'Primary_Care_Group',
                    # ... RCEP: code was Primary_Care_Group and descr. absent
                    'internal_alias_prefix': 'pcg',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'HealthAuthority',
                    'lookup_table': 'GenHealthAuthority',
                    'column_prefix': 'Health_Authority',
                    # ... RCEP: code was Health_Authority and descr. absent
                    'internal_alias_prefix': 'ha',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AddressType',
                    'lookup_table': 'GenAddressType',
                    'column_prefix': 'Address_Type',  # RCEP
                    'internal_alias_prefix': 'adt',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'AccommodationType',
                    'lookup_table': 'GenAccommodationType',
                    'column_prefix': 'Accommodation_Type',
                    # ... RCEP, though National_Code added
                    'internal_alias_prefix': 'act',
                },
            },
        ],
    }),

    ('Client_Alternative_ID', {
        # IDs on other systems
        'basetable': 'ClientAlternativeID',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'SystemID': None,  # lookup below
            'ID': 'ID',  # RCEP; this is the foreign ID
            'SequenceID': 'Unique_Key',  # RCEP
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SystemID',
                    'lookup_table': 'GenOtherSystem',
                    'column_prefix': 'System',
                    'internal_alias_prefix': 'sys',
                    # RCEP: was SystemID (code), System (description)
                },
            },
        ],
    }),

    ('Client_Allergies', {
        'basetable': 'EPClientAllergies',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'ReactionID': 'Unique_Key',  # RCEP; INT
            'UserID': None,  # user lookup; VARCHAR(15)
            # Substance: unchanged, RCEP; VARCHAR(255)
            'ReactionType': 'Reaction_Type_ID',  # and lookup below; INT
            # Reaction: unchanged, RCEP; VARCHAR(255)
            'ReactionSeverity': 'Reaction_Severity_ID',  # not RCEP; lookup below; INT  # noqa
            'ReportedBy': 'Reported_By_ID',  # and lookup below; INT
            'Name': 'Name',  # RCEP; think this is "reported by" name; VARCHAR(50)  # noqa
            'WitnessingHCP': 'Witnessing_HCP',  # RCEP; VARCHAR(50)
            'YearOfIdentification': 'Year_Of_Identification',  # RCEP; INT
            # Comment: unchanged, RCEP; VARCHAR(500)
            # Deleted: unchanged, RCEP; BIT
            'DeletionReason': 'Deletion_Reason_ID',  # not in RCEP; INT
            'DeletedBy': None,  # user lookup; VARCHAR(15)
            'RemovalDate': 'Removal_Date',  # RCEP; DATETIME
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'UserID',
                    'column_prefix': 'Entered_By',  # RCEP
                    'internal_alias_prefix': 'eb',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReactionType',
                    'lookup_table': 'EPReactionType',
                    'lookup_pk': 'ReactionID',
                    'lookup_fields_aliases': {
                        'Code': 'Reaction_Type_Code',
                        'CodeDescription': 'Reaction_Type_Description',
                        # ... all RCEP
                    },
                    'internal_alias_prefix': 'rt',
                }
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReactionSeverity',
                    'lookup_table': 'EPSeverity',
                    'lookup_pk': 'SeverityID',
                    'lookup_fields_aliases': {
                        'Code': 'Reaction_Severity_Code',
                        'CodeDescription': 'Reaction_Severity_Description',
                        # ... all RCEP
                    },
                    'internal_alias_prefix': 'rs',
                }
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReportedBy',
                    # RCEP code is Reported_By; NB error in RiO docs AND RCEP;
                    # code is INT ranging from 1-4
                    'lookup_table': 'EPReportedBy',
                    'lookup_pk': 'ReportedID',  # not Code!
                    'lookup_fields_aliases': {
                        'Code': 'Reported_By_Code',
                        'CodeDescription': 'Reported_By_Description',
                    },
                    'internal_alias_prefix': 'rb',
                }
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'DeletionReason',
                    'lookup_table': 'EPClientAllergyRemovalReason',
                    'lookup_pk': 'RemovalID',
                    'lookup_fields_aliases': {
                        'Code': 'Deletion_Reason_Code',  # not in RCEP
                        'Reason': 'Deletion_Reason_Description',  # not in RCEP
                    },
                    'internal_alias_prefix': 'dr',
                }
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'DeletedBy',
                    'column_prefix': 'Deleted_By',  # RCEP
                    'internal_alias_prefix': 'db',
                },
            },
            {
                # Restrict to current allergies only?
                'function': where_allergies_current,
            },
        ],
    }),

    ('Client_Communications_History', {
        'basetable': 'ClientTelecom',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'ClientTelecomID': 'Unique_Key',  # RCEP
            'Detail': 'Contact_Details',  # RCEP; may be phone no. or email addr
            'ContactMethod': None,  # lookup below
            'Context': None,  # lookup below
            'StartDate': 'Valid_From',  # RCEP
            'EndDate': 'Valid_To',  # RCEP
            'SpineID': None,  # omitted in RCEP
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ContactMethod',
                    'lookup_table': 'GenTelecomContactMethod',
                    'column_prefix': 'Method',  # RCEP
                    'internal_alias_prefix': 'cm',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Context',
                    'lookup_table': 'GenTelecomContext',
                    'column_prefix': 'Context',  # RCEP
                    'internal_alias_prefix': 'cx',
                },
            },
            # Extras for CRATE anonymisation:
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CASE WHEN (ContactMethod = 1 OR ContactMethod = 2'
                            ' OR ContactMethod = 4) THEN Detail ELSE NULL END',
                    # 1 = telephone; 2 = fax; 4 = minicom/textphone
                    'alias': 'crate_telephone',
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CASE WHEN ContactMethod = 3 THEN Detail '
                            'ELSE NULL END',
                    'alias': 'crate_email_address',
                },
            },
        ],
    }),

    ('Client_CPA', {
        'basetable': 'CPAClientCPA',
        'rename': {
            'SequenceID': 'Unique_Key',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'ChangedBy': None,  # user lookup
            'EndReason': 'End_Reason_Code',  # RCEP
            'NextReviewDate': 'Next_CPA_Review_Date',  # RCEP
            'CPALevel': None,  # lookup below
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ChangedBy',
                    'column_prefix': 'Changed_By',  # RCEP
                    'internal_alias_prefix': 'cb',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'EndReason',
                    'lookup_table': 'CPAReviewOutcomes',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'End_Reason_Description',
                        'NationalCode': 'End_Reason_National_Code',
                        'DischargeFromCPA': 'End_Reason_Is_Discharge',
                        # ... all RCEP
                    },
                    'internal_alias_prefix': 'er',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'CPALevel',
                    'lookup_table': 'CPALevel',
                    'column_prefix': 'CPA_Level',
                    'internal_alias_prefix': 'lv',
                }
            },
        ],
    }),

    ('Client_Demographic_Details', {
        'basetable': 'ClientIndex',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'NNN': 'NHS_Number',  # RCEP
            # RCEP: Shared_ID = hashed NHS number (CRATE does this); skipped
            'NNNStatus': None,  # lookup below
            'AlternativeID': 'Alternative_RiO_Number',  # may always be NULL
            'Surname': None,  # always NULL; see ClientName instead
            'SurnameSoundex': None,  # always NULL; see ClientName instead
            'Firstname': None,  # always NULL; see ClientName instead
            'FirstnameSoundex': None,  # always NULL; see ClientName instead
            'Title': None,  # always NULL; see ClientName instead
            'Gender': None,  # lookup below
            # RCEP: CAMHS_National_Gender_Code: ?source
            'DateOfBirth': 'Date_Of_Birth',  # RCEP
            # Truncated_Date_of_Birth (RCEP): ignored (CRATE does this)
            'EstimatedDOB': 'Estimated_Date_Of_Birth',  # 0/1 flag
            'DaytimePhone': 'Daytime_Phone',  # not in RCEP
            'EveningPhone': 'Evening_Phone',  # not in RCEP
            'Occupation': 'Occupation',  # RCEP
            'PartnerOccupation': 'Partner_Occupation',  # RCEP
            'MaritalStatus': None,  # lookup below
            'Ethnicity': None,  # lookup below
            'Religion': None,  # lookup below
            'Nationality': None,  # lookup below
            'DateOfDeath': 'Date_Of_Death',  # RCEP
            # RCEP: comment: ?source
            'OtherAddress': None,  # Not in RCEP. Occasional (0.34%) confused mismash e.g. "Temporary Address: 1 Thing Lane, ..."; so unhelpful for anon. but identifying  # noqa
            'MotherLink': None,  # Not in RCEP. ?Always NULL. See ClientFamilyLink instead  # noqa
            'FatherLink': None,  # Not in RCEP. ?Always NULL. See ClientFamilyLink instead  # noqa
            'DateRegistered': 'Date_Registered',  # RCEP
            'EMailAddress': None,  # always NULL; see ClientTelecom instead
            'MobilePhone': None,  # always NULL; see ClientTelecom instead
            'FirstLanguage': None,  # lookup below
            'School': None,  # always NULL; see ClientSchool instead
            'NonClient': 'Non_Client',  # RCEP; 0/1 indicator
            'DiedInHospital': 'Died_In_Hospital',  # RCEP
            'MainCarer': None,  # see CAST below
            'NINumber': 'National_Insurance_Number',  # RCEP
            'DeathFlag': 'Death_Flag',  # RCEP; 0/1 indicator
            'TimeStamps': None,  # RiO internal system record-locking field (!)
            'FirstCareDate': 'Date_Of_First_Mental_Health_Care',  # RCEP
            'NNNLastTape': None,  # Not in RCEP. May refer to tape storage of NHS numbers, i.e. system internal; see NNNTape.  # noqa
            'OtherCarer': None,  # see CAST below
            'LastUpdated': 'Last_Updated',  # RCEP
            'ReportsFile': 'Reports_File',  # RCEP; 0/1 flag
            'SENFile': 'SEN_File',  # RCEP; 0/1 flag
            'Interpreter': 'Interpreter_Required',  # RCEP; 0/1 flag
            'OutPatMedAdminRecord': 'Outpatient_Medical_Admin_Record',  # 0/1 flag; RCEP was OutPatMedAdminRecord  # noqa
            'SpineID': None,  # omitted from RCEP
            'SpineSyncDate': None,  # omitted from RCEP
            'SensitiveFlag': 'Sensitive_Flag',  # RCEP
            'DeathDateNational': 'Death_Date_National',  # RCEP
            'DeathDateStatus': 'Death_Date_Status',  # RCEP
            'SupersedingNNN': 'Superseding_NHS_Number',  # RCEP
            'Deleted': 'Deleted_Flag',  # RCEP
            'PersonRole': None,  # lookup below
            'Exited': 'Exited_NHS_Care',  # RCEP was Exited; 0/1 flag
        },
        'add': [
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': sql_fragment_cast_to_int('MainCarer'),
                    'alias': 'Main_Carer',
                    # RCEP; RiO number CROSS-REFERENCE
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': sql_fragment_cast_to_int('OtherCarer'),
                    'alias': 'Other_Carer',
                    # RCEP; RiO number CROSS-REFERENCE
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'NNNStatus',
                    'lookup_table': 'NNNStatus',
                    'column_prefix': 'NNN_Status',
                    # ... RCEP except code was NNN_Status
                    'internal_alias_prefix': 'ns',
                },
                # PROBLEM HERE 2017-01-23: RiO has multiple entries in the
                # NNNStatus table for some Code values, differing by
                # NationalCode (but Code is what's looked up from ClientIndex).
                # They all have the same CodeDescription. So we only want the
                # first, or we get duplicate rows from the LEFT JOIN.
                # See standard_rio_code_lookup, thus modified.
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Gender',
                    'lookup_table': 'GenGender',
                    'column_prefix': 'Gender',  # RCEP
                    'internal_alias_prefix': 'gd',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'MaritalStatus',
                    'lookup_table': 'GenMaritalStatus',
                    'column_prefix': 'Marital_Status',
                    # RCEP, except national was National_Marital_Status_Code
                    'internal_alias_prefix': 'ms',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Ethnicity',
                    'lookup_table': 'GenEthnicity',
                    'column_prefix': 'Ethnicity',
                    # RCEP, except national was National_Ethnicity_Code
                    'internal_alias_prefix': 'et',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Religion',
                    'lookup_table': 'GenReligion',
                    'column_prefix': 'Religion',
                    # RCEP, except national was National_Religion_Code
                    'internal_alias_prefix': 're',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Nationality',
                    'lookup_table': 'GenNationality',
                    'column_prefix': 'Nationality',  # RCEP
                    'internal_alias_prefix': 'nt',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'FirstLanguage',
                    'lookup_table': 'GenLanguage',
                    'column_prefix': 'First_Language',
                    # RCEP, except national was National_Language_Code
                    'internal_alias_prefix': 'la',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'PersonRole',
                    'lookup_table': 'ClientPersonRole',
                    'column_prefix': 'Person_Role',  # RCEP
                    'internal_alias_prefix': 'pr',
                },
            },
        ],
    }),

    # Ignored: ClientFamily, which has a single field (comment), with
    # probably-identifying and hard-to-anonymise-with information.

    ('Client_Family', {
        'basetable': 'ClientFamilyLink',
        'rename': {
            'RelatedClientID': None,  # see CAST below
            'Relationship': None,  # lookup below
            'ParentalResponsibility': None,  # lookup below
            'LegalStatus': None,  # lookup below
            'TempVal': None,  # Temporary_Value in RCEP, but who cares!?
            # RCEP: Comment: ?the comment from ClientFamily -- ignored
        },
        'add': [
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': sql_fragment_cast_to_int('RelatedClientID'),
                    'alias': 'Related_Client_ID',
                    # RCEP; RiO number CROSS-REFERENCE
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Relationship',
                    'lookup_table': 'GenFamilyRelationship',
                    'column_prefix': 'Relationship',  # RCEP
                    'internal_alias_prefix': 'rl',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ParentalResponsibility',
                    'lookup_table': 'GenFamilyParentalResponsibility',
                    'column_prefix': 'Parental_Responsibility',  # RCEP
                    'internal_alias_prefix': 'pr',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'LegalStatus',
                    'lookup_table': 'GenFamilyLegalStatus',
                    'column_prefix': 'Legal_Status',  # RCEP
                    'internal_alias_prefix': 'ls',
                }
            },
        ],
    }),

    ('Client_GP_History', {
        # Ignored: ClientGPMerged = ?old data
        # RiO docs say ClientHealthCareProvider supersedes ClientGP
        'basetable': 'ClientHealthCareProvider',
        'rename': {
            'GPCode': None,  # lookup below
            'PracticeCode': None,  # lookup below
            'FromDate': 'GP_From_Date',  # RCEP
            'ToDate': 'GP_To_Date',  # RCEP
            # Allocation: RCEP; unchanged - but what is it?
            'PersonHCPProviderID': 'Person_HCP_Provider_ID',  # RCEP
            'LastUpdated': 'Last_Updated',  # RCEP
            # RCEP Care_Group: PCG marked defunct in RiO GenGPPractice
            'HCProviderTypeID': None,  # lookup below
            # HCProviderID: not in RCEP; unchanged
        },
        'add': [
            {
                'function': rio_add_gp_lookup,
                'kwargs': {
                    'basecolumn': 'GPCode',
                    'column_prefix': 'GP',  # RCEP with some modifications
                    'internal_alias_prefix': 'gp',
                },
            },
            {
                'function': rio_add_gp_practice_lookup,
                'kwargs': {
                    'basecolumn': 'PracticeCode',
                    'column_prefix': 'GP_Practice',  # RCEP with extras
                    'internal_alias_prefix': 'prac',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'HCProviderTypeID',
                    'lookup_table': 'GenHealthCareProviderType',
                    'column_prefix': 'Provider_Type',  # RCEP
                    'internal_alias_prefix': 'pt',
                },
            },
        ],
    }),

    ('Client_Medication', {
        # UNTESTED as no data in CPFT
        'basetable': 'EPClientMedication',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'SequenceID': 'Unique_Key',  # RCEP
            'EventNumber': 'Event_Number',  # RCEP
            'EventSequenceID': 'Event_ID',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'RoutePrescribed': 'Route_Prescribed',  # RCEP
            'Frequency': 'Frequency_Code',  # RCEP; also lookup below
            'Units': None,  # lookup below
            'DosageComment': 'Dosage_Comment',  # RCEP
            'AdminInstructions': 'Admin_Instructions',  # CEP
            'MedicationType': None,  # lookup below
            'EndDate': 'End_Date',  # RCEP: was EndDate
            # Incomplete: unchanged, in RCEP
            'EndDateCommit': 'End_Date_Commit',  # RCEP: was EndDateCommit; 1/0
            'StartBy': None,  # user lookup
            'EndBy': None,  # user lookup
            'MinDose': 'Min_Dose',  # RCEP
            'MaxDose': 'Max_Dose',  # RCEP
            'AdminTime': 'Admin_Time',  # RCEP
            'AdminNumber': 'Admin_Number',  # RCEP
            'ConfirmText': 'Confirm_Text',  # RCEP
            'HourlyStartTime': 'Hourly_Start_Time',  # RCEP
            'DRCWarning': 'DRC_Warning',  # RCEP
            'DailyFrequency': 'Daily_Frequency_Code',  # RCEP; also lookup
            'ReasonID': 'DRC_Override_Reason_ID',  # INT; not RCEP; also lookup
            'AdministeredInError': 'Administered_In_Error_Flag',  # RCEP
            # Deleted: unchanged, in RCEP
            # Confirmed: unchanged, in RCEP
            'NumOfDays': 'Num_Of_Days',  # in RCEP
            'VTMFormulation': 'VTMFormulation',  # RCEP; VTM = Virtual Therapeutic Moieties  # noqa
        },
        'add': [
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'Frequency',
                    'lookup_table': 'EPMedicationFrequency',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'Frequency_Description',
                        'Depot': 'Frequency_Is_Depot',
                        'AdminNum': 'Frequency_Admin_Number',
                        'DayInterval': 'Frequency_Day_Interval',
                        # ... all RCEP
                    },
                    'internal_alias_prefix': 'fr',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Units',
                    'lookup_table': 'EPMedicationBaseUnits',
                    'column_prefix': 'Units',
                    # RiO docs: EPClientMedication.Units is VARCHAR(100) but
                    # also FK to EPMedicationBaseUnits.Code; is 100 a typo for
                    # 10?
                    # RCEP: Units VARCHAR(200) so who knows.
                    'internal_alias_prefix': 'un',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'MedicationType',
                    'lookup_table': 'EPMedicationType',
                    'column_prefix': 'Medication_Type',  # RCEP
                    'internal_alias_prefix': 'mt',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'StartBy',
                    'column_prefix': 'Start_By',  # RCEP
                    'internal_alias_prefix': 'sb',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'EndBy',
                    'column_prefix': 'End_By',  # RCEP
                    'internal_alias_prefix': 'eb',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'DailyFrequency',
                    'lookup_table': 'EPMedicationDailyFrequency',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'Daily_Frequency_Description',
                        'AdminNum': 'Daily_Frequency_Admin_Number',
                        'AdvancedMed': 'Daily_Frequency_Advanced_Med_Flag',
                        'HourlyMed': 'Daily_Frequency_Hourly_Med_Flag',
                        'HourlyMedIntervalMinutes': 'Daily_Frequency_Hourly_Med_Interval_Minutes',  # noqa
                        # 'DisplayOrder': 'Daily_Frequency_Display_Order',
                        # ... all RCEP except AdminNum, DisplayOrder not RCEP
                        # DisplayOrder just governs order in picklist
                    },
                    'internal_alias_prefix': 'df',
                }
            },
            {  # DRC = dose range checking [override]
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReasonID',
                    'lookup_table': 'EPDRCOverride',  # not EPDRCOverRide
                    'lookup_pk': 'ReasonID',  # not Code (also present)
                    'lookup_fields_aliases': {
                        'Code': 'DRC_Override_Reason_Code',
                        'Reason': 'DRC_Override_Reason_Description',
                        # ... all RCEP
                        # ReasonID is INT; Code is VARCHAR(10)
                    },
                    'internal_alias_prefix': 'drc',
                }
            },
        ],
    }),

    ('Client_Name_History', {
        'basetable': 'ClientName',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'Surname': 'Family_Name',  # RCEP
            'ClientNameID': 'Unique_Key',  # RCEP
            'EffectiveDate': 'Effective_Date',  # RCEP
            'Deleted': 'Deleted_Flag',  # RCEP
            'AliasType': None,  # lookup below
            'EndDate': 'End_Date',  # RCEP: was End_Date_
            'SpineID': None,  # not in RCEP
            'Prefix': 'Title',  # RCEP
            'Suffix': 'Suffix',  # RCEP
            'GivenName1': 'Given_Name_1',  # RCEP
            'GivenName2': 'Given_Name_2',  # RCEP
            'GivenName3': 'Given_Name_3',  # RCEP
            'GivenName4': 'Given_Name_4',  # RCEP
            'GivenName5': 'Given_Name_5',  # RCEP
            'GivenName1Soundex': None,  # not in RCEP
            'GivenName2Soundex': None,  # not in RCEP
            'GivenName3Soundex': None,  # not in RCEP
            'GivenName4Soundex': None,  # not in RCEP
            'GivenName5Soundex': None,  # not in RCEP
            'SurnameSoundex': None,  # not in RCEP
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AliasType',
                    'lookup_table': 'ClientAliasType',
                    'column_prefix': 'Name_Type',  # RCEP
                    'internal_alias_prefix': 'al',
                },
            },
        ],
    }),

    ('Client_Personal_Contacts', {
        'basetable': 'ClientContact',
        'rename': {
            'SequenceID': 'Unique_Key',  # RCEP
            'ContactType': None,  # lookup below
            'Surname': 'Family_Name',  # RCEP
            'Firstname': 'Given_Name',  # RCEP
            'Title': 'Title',  # RCEP
            'AddressLine1': 'Address_Line_1',  # RCEP
            'AddressLine2': 'Address_Line_2',  # RCEP
            'AddressLine3': 'Address_Line_3',  # RCEP
            'AddressLine4': 'Address_Line_4',  # RCEP
            'AddressLine5': 'Address_Line_5',  # RCEP
            'PostCode': 'Post_Code',  # RCEP
            'MainPhone': 'Main_Phone',  # RCEP
            'OtherPhone': 'Other_Phone',  # RCEP
            'EMailAddress': 'Email_Address',  # RCEP was Email (inconsistent)
            'Relationship': 'Contact_Relationship_Code',  # RCEP + lookup
            'ContactComment': 'Comment',  # RCEP
            'Organisation': 'Organisation',  # VARCHAR(40); SEE NOTE 1.
            'Deleted': 'Deleted_Flag',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'LanguageCommunication': None,  # lookup below
            'LanguageProficiencyLevel': None,  # lookup below
            'PreferredContactMethod': None,  # lookup below
            'NHSNumber': 'NHS_Number',  # RCEP
            'SpineID': None,  # not in RCEP; spine interaction field
            'PAFKey': None,  # not in RCEP; spine interaction field [2]
            'PositionNumber': 'Position_Number',  # RCEP
            'MainContactMethod': None,  # lookup below
            'MainContext': None,  # lookup below
            'OtherContactMethod': None,  # lookup below
            'OtherContext': None,  # lookup below
            # [1] RiO's ClientContact.Organisation is VARCHAR(40).
            #   Unclear what it links to.
            #   Typical data: NULL, 'CPFT', 'Independent Living Service',
            #       'Solicitors'  - which makes it look like free text.
            #   RCEP has:
            #       - Organisation_ID VARCHAR(40)  -- looks like the link field
            #       - Organisation_Name VARCHAR(80) } all NULL in our snapshot
            #       - Organisation_Code VARCHAR(20) }
            #   Candidate RiO lookup tables are
            #       - GenOrganisation  -- only content maps RT1 to "Cambrigeshire and Peterborough..."  # noqa
            #       - OrgOrganisation  -- empty for us
            #   So I think they've screwed it up, and it's free text that
            #   RCEP is incorrectly trying to link.
            # [2] PAF Key = PAF address key, postal address file key
            #   = unique ID keyed to Royal Mail PAF Directory
            #   http://systems.hscic.gov.uk/demographics/spineconnect/spineconnectpds.pdf  # noqa
        },
        'add': [
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'ContactType',
                    'lookup_table': 'ClientContactType',
                    'column_prefix': 'Contact_Type',  # RCEP
                    'internal_alias_prefix': 'ct',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'Relationship',
                    'lookup_table': 'ClientContactRelationship',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'Contact_Relationship_Description',
                        'NationalCode': 'Contact_Relationship_National_Code',
                        'FamilyRelationship': 'Family_Relationship_Flag',
                        # ... all RCEP except was
                        # National_Contact_Relationship_Code
                    },
                    'internal_alias_prefix': 'cr',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'LanguageCommunication',
                    'lookup_table': 'GenLanguage',
                    'column_prefix': 'Language',
                    # ... RCEP except was National_Language_Code
                    'internal_alias_prefix': 'la',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'LanguageProficiencyLevel',
                    'lookup_table': 'GenLanguageProficiencyLevel',
                    'column_prefix': 'Language_Proficiency',
                    # ... RCEP: code = Language_Proficiency, desc absent
                    'internal_alias_prefix': 'la',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'PreferredContactMethod',
                    'lookup_table': 'GenPreferredContactMethod',
                    'column_prefix': 'Preferred_Contact_Method',  # RCEP
                    'internal_alias_prefix': 'pcm',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'MainContactMethod',
                    'lookup_table': 'GenTelecomContactMethod',
                    'column_prefix': 'Main_Phone_Method',  # RCEP
                    'internal_alias_prefix': 'mcm',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'MainContext',
                    'lookup_table': 'GenTelecomContext',
                    'column_prefix': 'Main_Phone_Context',  # RCEP
                    'internal_alias_prefix': 'mcx',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'OtherContactMethod',
                    'lookup_table': 'GenTelecomContactMethod',
                    'column_prefix': 'Other_Phone_Method',  # RCEP
                    'internal_alias_prefix': 'ocm',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'OtherContext',
                    'lookup_table': 'GenTelecomContext',
                    'column_prefix': 'Other_Phone_Context',  # RCEP
                    'internal_alias_prefix': 'ocx',
                }
            },
        ],
    }),

    ('Client_Physical_Details', {
        'basetable': 'ClientPhysicalDetail',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            # RCEP: From_Date: ?source
            # RCEP: Last_Updated: ?source
            'Height': 'Height_m',  # RCEP was Height; definitely not cm...
            'Weight': 'Weight_kg',  # RCEP was Weight
            'Comment': 'Extra_Comment',  # RCEP
            'BloodGroup': None,  # lookup below
            'SequenceID': 'Unique_Key',  # RCEP
            'BSA': 'BSA',  # RCEP
            'BMI': 'BMI',  # RCEP
            'HeadCircumference': 'Head_Circumference',  # RCEP: HeadCircumference  # noqa
            'RecordedBy': None,  # user lookup
            'Area': None,  # lookup below
            'DateTaken': 'Date_Taken',  # RCEP
            'DateRecorded': 'Date_Recorded',  # RCEP
            'DateDeleted': 'Date_Deleted',  # RCEP
            'ParentSeqID': 'Preceding_Entry_Key',  # RCEP: ParentSeqID [1]
            'FieldName': 'System_Field_Name',  # RCEP: Field_Name
            'BSAFormulaID': 'BSA_Formula_ID',  # RCEP
            'BSAFormulaAlterationReasonID': 'BSA_Formula_Alteration_Reason_ID',  # RCEP # noqa
            # [1] ParentSeqID a silly name because (a) we've named SequenceID
            #     to UniqueKey, so users won't know what "SeqID" is, and
            #     (b) because "preceding" isn't a "parent" relationship.
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'BloodGroup',
                    'lookup_table': 'GenBloodGroup',
                    'column_prefix': 'Blood_Group',  # RCEP
                    'internal_alias_prefix': 'bg',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'RecordedBy',
                    'column_prefix': 'Recorded_By',
                    # RCEP: Recorded_By_User_Code but rest User_*
                    'internal_alias_prefix': 'rb',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Area',
                    'lookup_table': 'MasterTableAreaCode',
                    'column_prefix': 'System_Area',
                    # RCEP: code = Area, description absent
                    'internal_alias_prefix': 'bg',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'BSAFormulaID',
                    'lookup_table': 'EPBSAFormula',
                    'lookup_pk': 'SequenceID',
                    'lookup_fields_aliases': {
                        'Description': 'BSA_Formula_Description',
                        'Formula': 'BSA_Formula',
                        # ... all RCEP
                    },
                    'internal_alias_prefix': 'bsaf',
                }
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'BSAFormulaAlterationReasonID',
                    'lookup_table': 'EPBSAFormulaAlterationReason',
                    # ... documentation error in RiO 6.2 docs
                    'lookup_pk': 'SequenceID',
                    'lookup_fields_aliases': {
                        'Reason': 'BSA_Formula_Alteration_Reason',  # RCEP
                    },
                    'internal_alias_prefix': 'bsaf',
                }
            },
        ],
    }),

    ('Client_Prescription', {
        'basetable': 'EPClientPrescription',
        'rename': {
            'PrescriptionID': 'Unique_Key',  # RCEP
            'IssueDate': 'Issue_Date',  # RCEP
            'CourseStartDate': 'Course_Start_Date',  # RCEP
            'NumberOfDays': 'Number_Of_Days',  # RCEP
            'IssueMethod': 'Issue_Method',  # RCEP [1]
            'IssuedBy': None,  # user lookup
            'ReferralCode': 'ReferralCode',  # RCEP [2]
            'HCPCode': None,  # user lookup
            'NonIssueReason': None,  # lookup below
            'ReprintReason': 'Reprint_Reason',  # RCEP
            # 'Prescriber': None,  # user lookup
            # [1] Looks like it should be an FK, but can't see any link.
            # [2] ? FK to Referral? Unclear and not in docs.
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'IssuedBy',
                    'column_prefix': 'HCP',  # RCEP uses HCP_User_*
                    'internal_alias_prefix': 'ib',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'HCPCode',
                    'column_prefix': 'Issued_By',  # RCEP
                    'internal_alias_prefix': 'ihcp',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'NonIssueReason',
                    'lookup_table': 'EPPrescriptionsNonIssueReasons',
                    'column_prefix': 'Non_Issue_Reason',  # RCEP
                    'internal_alias_prefix': 'nir',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'Prescriber',
                    'column_prefix': 'Prescriber',  # RCEP
                    # .. keys to GenPerson and GenUser should be equivalent,
                    # I think
                    'internal_alias_prefix': 'pr',
                },
            },
        ],
    }),

    ('Client_Professional_Contacts', {
        'basetable': 'DemClientOtherContact',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'SequenceID': 'Unique_Key',  # RCEP
            'OrgContactID': None,  # lookup below
            'OrgContactRelationshipID': None,  # lookup below
            'FromDate': 'Effective_From_Date',  # RCEP
            'ToDate': 'Effective_To_Date',  # RCEP
            'Deleted': 'Deleted_Flag',  # RCEP
            'ClosedByDeletion': 'Closed_By_Deletion_Flag',  # RCEP
            'ContactGroup': 'Contact_Group',  # RCEP
        },
        'add': [
            {
                'function': rio_add_org_contact_lookup,
                'kwargs': {
                    'basecolumn': 'OrgContactID',
                    'column_prefix': 'Contact',
                    # ... renamed prefix from RCEP for several
                    'internal_alias_prefix': 'c',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'OrgContactRelationshipID',
                    'lookup_table': 'OrgContactRelationshipType',
                    'column_prefix': 'Relationship_Type',
                    # RCEP except description was Relationship
                    'internal_alias_prefix': 'rt',
                },
            },
        ],
    }),

    ('Client_School', {
        'basetable': 'ClientSchool',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'SequenceID': 'Unique_Key',  # RCEP
            'FromDate': 'School_From_Date',  # RCEP
            'ToDate': 'School_To_Date',  # RCEP
            'SchoolCode': 'School_Code',  # RCEP
            'ChangeReason': 'Change_Reason',  # RCEP
        },
        'add': [
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'SchoolCode',
                    'lookup_table': 'GenSchool',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'School_Name',
                        'Address': 'School_Address',
                    },
                    'internal_alias_prefix': 'sc',
                }
            },
        ],
    }),

    ('CPA_Care_Coordinator', {  # RCEP: was CPA_CareCoordinator
        'basetable': 'CPACareCoordinator',
        'rename': {
            'CareCoordinatorID': None,  # user lookup below
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'EndReason': None,  # lookup below
            'CPASequenceID': 'CPA_Key',  # RCEP
            'SequenceID': 'Unique_Key',  # RCEP
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'CareCoordinatorID',
                    'column_prefix': 'Care_Coordinator',
                    'internal_alias_prefix': 'cc',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'EndReason',
                    'lookup_table': 'CPAReviewCareSpellEnd',
                    'column_prefix': 'End_Reason',  # RCEP
                    'internal_alias_prefix': 'er',
                }
            },
            {
                'function': add_index_only,
                'kwargs': {
                    'table': 'CPACareCoordinator',
                    'column_or_columns': 'ClientID',
                },
            },
        ],
    }),

    ('CPA_Review', {
        'basetable': 'CPAReviewDate',
        'rename': {
            # Created_Date: RCEP; ?source
            # Updated_Date: RCEP; ?source
            'ReviewDate': 'Review_Date',  # RCEP
            'CurrentFlag': 'Is_Current_Flag',  # RCEP
            'EndReason': None,  # lookup below
            'CPASequenceID': 'CPA_Key',  # RCEP
            'CPAReviewOutcome': 'CPA_Review_Outcome_Code',  # RCEP
            'FullHoNOS': 'Full_HoNOS',  # not in RCEP
            'ReviewType': 'Review_Type',  # RCEP
            'SWInvolved': 'Social_Worker_Involved_Flag',  # RCEP
            'DayCentreInvolved': 'Day_Centre_Involved_Flag',  # RCEP
            'ShelteredWorkInvolved': 'Sheltered_Work_Involved_Flag',  # RCEP
            'NonNHSResAccom': 'Non_NHS_Residential_Accommodation',  # RCEP
            'DomicilCareInvolved': 'Domicile_Care_Involved',  # RCEP
            'ReviewDiagnosis1': 'Review_Diagnosis_1_FK_Diagnosis',  # in RCEP, Review_Diagnosis_1, etc.  # noqa
            'ReviewDiagnosis2': 'Review_Diagnosis_2_FK_Diagnosis',
            'ReviewDiagnosis3': 'Review_Diagnosis_3_FK_Diagnosis',
            'ReviewDiagnosis4': 'Review_Diagnosis_4_FK_Diagnosis',
            'ReviewDiagnosis5': 'Review_Diagnosis_5_FK_Diagnosis',
            'ReviewDiagnosis6': 'Review_Diagnosis_6_FK_Diagnosis',
            'ReviewDiagnosis7': 'Review_Diagnosis_7_FK_Diagnosis',
            'ReviewDiagnosis8': 'Review_Diagnosis_8_FK_Diagnosis',
            'ReviewDiagnosis9': 'Review_Diagnosis_9_FK_Diagnosis',
            'ReviewDiagnosis10': 'Review_Diagnosis_10_FK_Diagnosis',
            'ReviewDiagnosis11': 'Review_Diagnosis_11_FK_Diagnosis',
            'ReviewDiagnosis12': 'Review_Diagnosis_12_FK_Diagnosis',
            'ReviewDiagnosis13': 'Review_Diagnosis_13_FK_Diagnosis',
            'ReviewDiagnosis14': 'Review_Diagnosis_14_FK_Diagnosis',
            'ReviewDiagnosisConfirmed': 'Review_Diagnosis_Confirmed_Date',  # RCEP  # noqa
            'ReviewDiagnosisBy': None,  # user lookup
            'ReferralSource': None,  # lookup below
            'CareSpellEndCode': None,  # lookup below
            'SequenceID': 'Unique_Key',  # RCEP
            'CareTeam': None,  # team lookup below
            'LastReviewDate': 'Last_Review_Date',  # RCEP
            'OtherReviewOutcome': None,  # lookup below
            'ReviewLength': 'Review_Length',  # RCEP was ReviewLength
            'Validated': 'Validated',  # RCEP
            'ThirdPartyInformation': 'Third_Party_Information',  # RCEP: was ThirdPartyInformation  # noqa
            'Text1': 'Notes_Text_1',  # not in RCEP
            'Text2': 'Notes_Text_2',  # not in RCEP
            'Text3': 'Notes_Text_3',  # not in RCEP
            'Text4': 'Notes_Text_4',  # not in RCEP
            'Text5': 'Notes_Text_5',  # not in RCEP
            'Text6': 'Notes_Text_6',  # not in RCEP
            'Text7': 'Notes_Text_7',  # not in RCEP
            'Text8': 'Notes_Text_8',  # not in RCEP
            'Text9': 'Notes_Text_9',  # not in RCEP
            'Text10': 'Notes_Text_10',  # not in RCEP
            'ScheduledRecord': 'Scheduled_Record',  # RCEP was ScheduledRecord
            'LastUpdatedBy': None,  # user lookup
            'LastUpdatedDate': 'Last_Updated_Date',  # RCEP
            'ParentSequenceID': 'Parent_Key',  # RCEP
            'AppointmentSequenceID': 'Appointment_Key',  # RCEP
            'CPAReviewPackFilename': 'CPA_Review_Pack_Filename',  # RCEP
            'LocationDescription': 'Location_Description_Text',  # RCEP
            'Section117StartDate': 'Section117_Start_Date',  # RCEP
            'Section117Continue': 'Section117_Continue',  # RCEP
            'Section117Decision': 'Section117_Decision',  # RCEP
            'ProgSequenceID': 'Progress_Note_Key',  # RCEP: was Progress__Note_Key  # noqa
            'CancellationDateTime': 'Cancellation_Date_Time',  # RCEP
            'CancellationReason': None,  # lookup below
            'CancellationBy': None,  # user lookup
            'EmploymentStatus': None,  # lookup below
            'WeeklyHoursWorked': None,  # lookup below
            'AccommodationStatus': None,  # lookup below
            'SettledAccommodationIndicator': None,  # lookup below
            'Location': None,  # location lookup
            'Section117EndDate': 'Section117_End_Date',  # RCEP
            'Section117Eligibility': 'Section117_Eligibility',  # RCEP
        },
        'add': [
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'EndReason',
                    'lookup_table': 'CPAReviewOutcomes',
                    'column_prefix': 'End_Reason',
                    # ... RCEP code was End_Reason; lookup added
                    'internal_alias_prefix': 'er',
                }
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'CPAReviewOutcome',
                    'lookup_table': 'CPAReviewCareSpellEnd',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'CPA_Review_Outcome_Description',
                        'NationalCode': 'CPA_Review_Outcome_National_Code',
                        'DischargeFromCPA': 'CPA_Review_Outcome_Is_Discharge',
                        # ... all RCEP
                    },
                    'internal_alias_prefix': 'ro',
                }
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ReviewDiagnosisBy',
                    'column_prefix': 'Review_Diagnosis_By',
                    'internal_alias_prefix': 'rdb',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'ReferralSource',
                    'lookup_table': 'AmsReferralSource',
                    'column_prefix': 'Referral_Source',  # RCEP
                    'internal_alias_prefix': 'rs',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'CareSpellEndCode',
                    'lookup_table': 'CPAReviewCareSpellEnd',
                    'column_prefix': 'Care_Spell_End',  # RCEP
                    'internal_alias_prefix': 'cse',
                }
            },
            {
                'function': rio_add_team_lookup,
                'kwargs': {
                    'basecolumn': 'CareTeam',
                    'column_prefix': 'Care_Team',
                    'internal_alias_prefix': 'tm',
                    # ... all RCEP, except REP has Care_Team_Code and
                    # Team* for others; this has Care_Team_*
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'OtherReviewOutcome',
                    'lookup_table': 'CPAReviewOutcomes',
                    'column_prefix': 'Other_Review_Outcome',  # RCEP
                    'internal_alias_prefix': 'oro',
                }
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'LastUpdatedBy',
                    'column_prefix': 'Last_Updated_By',
                    'internal_alias_prefix': 'lub',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'CancellationReason',
                    # 'lookup_table': 'CPACancellationReasons',
                    # CPACancellationReasons has a single column, Code, which
                    # is a key to GenCancellationReason, thus making it
                    # entirely pointless (except, presumably, as a filter for
                    # data entry).
                    'lookup_table': 'GenCancellationReason',
                    'column_prefix': 'Cancellation_Reason',  # RCEP
                    'internal_alias_prefix': 'cr',
                }
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'CancellationBy',
                    'column_prefix': 'Cancellation_By',
                    'internal_alias_prefix': 'cb',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'EmploymentStatus',
                    'lookup_table': 'GenEmpStatus',
                    'column_prefix': 'Employment_Status',  # RCEP
                    'internal_alias_prefix': 'es',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'WeeklyHoursWorked',
                    'lookup_table': 'GenWeeklyHoursWorked',
                    'column_prefix': 'Weekly_Hours_Worked',  # not in RCEP
                    # RCEP code was Weekly_Hours_Worked
                    'internal_alias_prefix': 'whw',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'AccommodationStatus',
                    'lookup_table': 'GenAccommodationStatus',
                    'column_prefix': 'Accommodation_Status',  # RCEP
                    'internal_alias_prefix': 'as',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'SettledAccommodationIndicator',
                    'lookup_table': 'GenSettledAccommodation',
                    'column_prefix': 'Settled_Accommodation_Indicator',  # RCEP
                    'internal_alias_prefix': 'sa',
                }
            },
            {
                'function': rio_add_location_lookup,
                'kwargs': {
                    'basecolumn': 'Location',
                    'column_prefix': 'Location',  # RCEP
                    'internal_alias_prefix': 'loc',
                },
            },
        ],
    }),

    ('Diagnosis', {
        'basetable': 'DiagnosisClient',
        'rename': {
            # Comment: unchanged
            # RemovalComment: unchanged
            'CodingScheme': None,  # put back in below
            'Diagnosis': None,  # becomes 'Diagnosis_Code' below
            'DiagnosisEndDate': 'Diagnosis_End_Date',  # RCEP
            'DiagnosisStartDate': 'Diagnosis_Start_Date',  # RCEP
            'EntryBy': None,  # RCEP; is user code
            'EntryDate': 'Entry_Date',
            'RemovalBy': None,  # RCEP; is user code
            'RemovalDate': 'Removal_Date',
            'RemovalReason': None,  # lookup below
        },
        'add': [
            {
                'function': rio_add_diagnosis_lookup,
                'kwargs': {
                    'basecolumn_scheme': 'CodingScheme',
                    'basecolumn_code': 'Diagnosis',
                    'alias_scheme': 'Coding_Scheme',  # RCEP: CodingScheme
                    'alias_code': 'Diagnosis_Code',  # RCEP
                    'alias_description': 'Diagnosis',  # RCEP
                    'internal_alias_prefix': 'd',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'RemovalReason',
                    'lookup_table': 'DiagnosisRemovalReason',
                    'column_prefix': 'Removal_Reason',  # RCEP
                    'internal_alias_prefix': 'rr',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'EntryBy',
                    'column_prefix': 'Entered_By',
                    'internal_alias_prefix': 'eb',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'RemovalBy',
                    'column_prefix': 'Removal_By',
                    'internal_alias_prefix': 'rb',
                },
            },
        ],
    }),

    ('Inpatient_Stay', {
        'basetable': 'ImsEvent',
        'rename': {
            # Created_Date: RCEP; ?source
            # Referrer: unchanged
            # Updated_Date: RCEP; ?source
            'AdministrativeCategory': None,  # lookup below
            'AdmissionAllocation': None,  # lookup below
            'AdmissionDate': 'Admission_Date',  # RCEP
            'AdmissionMethod': None,  # lookup below
            'AdmissionSource': None,  # lookup below
            'ClientClassification': None,  # lookup below
            'DecideToAdmitDate': 'Decide_To_Admit_Date',  # RCEP
            'DischargeAddressLine1': 'Discharge_Address_Line_1',  # RCEP
            'DischargeAddressLine2': 'Discharge_Address_Line_2',  # RCEP
            'DischargeAddressLine3': 'Discharge_Address_Line_3',  # RCEP
            'DischargeAddressLine4': 'Discharge_Address_Line_4',  # RCEP
            'DischargeAddressLine5': 'Discharge_Address_Line_5',  # RCEP
            'DischargeAllocation': None,  # lookup below
            'DischargeAwaitedReason': None,  # lookup below
            'DischargeComment': 'Discharge_Comment',  # RCEP
            'DischargeDate': 'Discharge_Date',  # RCEP
            'DischargeDestination': None,  # lookup below
            'DischargeDiagnosis1': 'Discharge_Diagnosis_1_FK_Diagnosis',  # in RCEP, DischargeDiagnosis1, etc.  # noqa
            'DischargeDiagnosis10': 'Discharge_Diagnosis_10_FK_Diagnosis',
            'DischargeDiagnosis11': 'Discharge_Diagnosis_11_FK_Diagnosis',
            'DischargeDiagnosis12': 'Discharge_Diagnosis_12_FK_Diagnosis',
            'DischargeDiagnosis13': 'Discharge_Diagnosis_13_FK_Diagnosis',
            'DischargeDiagnosis14': 'Discharge_Diagnosis_14_FK_Diagnosis',
            'DischargeDiagnosis2': 'Discharge_Diagnosis_2_FK_Diagnosis',
            'DischargeDiagnosis3': 'Discharge_Diagnosis_3_FK_Diagnosis',
            'DischargeDiagnosis4': 'Discharge_Diagnosis_4_FK_Diagnosis',
            'DischargeDiagnosis5': 'Discharge_Diagnosis_5_FK_Diagnosis',
            'DischargeDiagnosis6': 'Discharge_Diagnosis_6_FK_Diagnosis',
            'DischargeDiagnosis7': 'Discharge_Diagnosis_7_FK_Diagnosis',
            'DischargeDiagnosis8': 'Discharge_Diagnosis_8_FK_Diagnosis',
            'DischargeDiagnosis9': 'Discharge_Diagnosis_9_FK_Diagnosis',
            'DischargeDiagnosisBy': None,  # user lookup
            'DischargeDiagnosisConfirmed': 'Discharge_Diagnosis_Confirmed_Date',  # RCEP  # noqa
            'DischargeMethod': None,  # lookup below
            'DischargePostCode': 'Discharge_Post_Code',  # RCEP
            'DischargeReadyDate': 'Discharge_Ready_Date',  # RCEP
            'EventNumber': 'Event_Number',  # RCEP
            'FirstInSeries': 'First_In_Series',  # RCEP
            'HighSecurityCategory': 'High_Security_Category',  # RCEP
            'IntendedDischargeDate': 'Intended_Discharge_Date',  # RCEP
            'IntendedManagement': None,  # lookup below
            'LegalStatus': None,  # lookup below
            'ReferralID': 'Referral_ID_FK_Referral',  # Referral_ID in RCEP
            'ReferralReason': 'Referral_Reason',  # RCEP
            'ReferralRequest': None,  # present in RCEP but "no longer used" in docs  # noqa
            'ReferralSource': None,  # lookup below
            'ReferringConsultant': None,  # not in RCEP; see lookup below
            'ReferringGP': None,  # see lookup below
            'WaitingStartDateA': 'Waiting_Start_Date_A',  # RCEP
            'WaitingStartDateB': 'Waiting_Start_Date_B',  # RCEP
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AdmissionMethod',
                    'lookup_table': 'ImsAdmissionMethod',
                    'column_prefix': 'Admission_Method',
                    # ... in RCEP, code absent, desc = Admission_Method
                    'internal_alias_prefix': 'am',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AdmissionSource',
                    'lookup_table': 'ImsAdmissionSource',
                    'column_prefix': 'Admission_Source',
                    # ... in RCEP, code absent, desc = Admission_Source
                    'internal_alias_prefix': 'as',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ClientClassification',
                    'lookup_table': 'ImsClientClassification',
                    'column_prefix': 'Client_Classification',
                    # ... in RCEP, code absent, desc = Client_Classification
                    'internal_alias_prefix': 'cc',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeAwaitedReason',
                    'lookup_table': 'ImsClientClassification',
                    'column_prefix': 'Discharge_Awaited_Reason',
                    # ... in RCEP, code absent, desc = Discharge_Awaited_Reason
                    'internal_alias_prefix': 'dar',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeDestination',
                    'lookup_table': 'ImsDischargeDestination',
                    'column_prefix': 'Discharge_Destination',
                    # ... in RCEP, code absent, desc = Discharge_Destination
                    'internal_alias_prefix': 'dd',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeMethod',
                    'lookup_table': 'ImsDischargeMethod',
                    'column_prefix': 'Discharge_Method',
                    # ... in RCEP, code absent, desc = Discharge_Method
                    'internal_alias_prefix': 'dm',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'IntendedManagement',
                    'lookup_table': 'ImsIntendedManagement',
                    'column_prefix': 'Intended_Management',
                    # ... in RCEP, code absent, desc = Intended_Management
                    'internal_alias_prefix': 'im',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AdministrativeCategory',
                    'lookup_table': 'GenAdministrativeCategory',
                    'column_prefix': 'Administrative_Category',
                    # ... in RCEP, code absent, desc = Administrative_Category
                    'internal_alias_prefix': 'ac',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ReferralSource',
                    'lookup_table': 'AmsReferralSource',
                    'column_prefix': 'Referral_Source',
                    # ... in RCEP, code absent, desc = Referral_Source
                    'internal_alias_prefix': 'rs',
                },
            },
            {
                'function': rio_add_gp_practice_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringGP',
                    'column_prefix': 'Referring_GP',
                    # RCEP + slight renaming + GP practice extras
                    'internal_alias_prefix': 'rgp',
                },
            },
            # Look up the same field two ways.
            {  # If AmsReferralSource.Behaviour = 'CS'...
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringConsultant',
                    'column_prefix': 'Referring_Consultant_Cons',
                    'internal_alias_prefix': 'rcc',
                },
            },
            {  # If AmsReferralSource.Behaviour = 'CH'...
                'function': rio_add_consultant_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringConsultant',
                    'column_prefix': 'Referring_Consultant_HCP',
                    'internal_alias_prefix': 'rch',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AdmissionAllocation',
                    'lookup_table': 'GenPCG',
                    'column_prefix': 'Admission_Allocation_PCT',
                    # ... in RCEP, code = Admission_Allocation, desc absent
                    'internal_alias_prefix': 'aa',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeAllocation',
                    'lookup_table': 'GenPCG',
                    'column_prefix': 'Discharge_Allocation_PCT',
                    # ... in RCEP, code = Discharge_Allocation, desc absent
                    'internal_alias_prefix': 'da',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'LegalStatus',
                    'lookup_table': 'ImsLegalStatusClassification',
                    'column_prefix': 'Legal_Status',
                    # ... in RCEP, code = Legal_Status, desc absent
                    'internal_alias_prefix': 'ls',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeDiagnosisBy',
                    'column_prefix': 'Discharge_Diagnosis_By',  # RCEP
                    'internal_alias_prefix': 'eb',
                },
            },
        ],
        'suppress_basetable': True,
        'suppress_other_tables': [],
    }),

    ('Inpatient_Leave', {
        'basetable': 'ImsEventLeave',
        'rename': {
            # Created_Date: RCEP ?source
            # Escorted: unchanged  # RCEP
            # Updated_Date: RCEP ?source
            'AddressLine1': 'Address_Line_1',  # RCEP
            'AddressLine2': 'Address_Line_2',  # RCEP
            'AddressLine3': 'Address_Line_3',  # RCEP
            'AddressLine4': 'Address_Line_4',  # RCEP
            'AddressLine5': 'Address_Line_5',  # RCEP
            'Deleted': 'Deleted_Flag',  # RCEP
            'EndDateTime': 'End_Date_Time',  # RCEP
            'EndedByAWOL': 'Ended_By_AWOL',  # RCEP
            'EventNumber': 'Event_Number',
            # ... RCEP; event number within this admission? Clusters near 1.
            'ExpectedReturnDateTime': 'Expected_Return_Date_Time',  # RCEP
            'LeaveEndReason': None,  # lookup below
            'LeaveType': None,  # lookup below
            'OtherInformation': 'Other_Information',  # RCEP
            'PlannedStartDateTime': 'Planned_Start_Date_Time',  # RCEP
            'PostCode': 'Post_Code',  # RCEP
            'SequenceID': 'Leave_Instance_Number',  # I think... RCEP
            'StartDateTime': 'Start_Date_Time',  # RCEP
            'UniqueSequenceID': 'Unique_Key',
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'LeaveType',
                    'lookup_table': 'ImsLeaveType',
                    'column_prefix': 'Leave_Type',  # RCEP
                    # RCEP except code was LeaveType_Code
                    'internal_alias_prefix': 'lt',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'LeaveEndReason',
                    'lookup_table': 'ImsLeaveEndReason',
                    'column_prefix': 'Leave_End_Reason',  # RCEP
                    'internal_alias_prefix': 'lt',
                },
            },
            {
                'function': where_not_deleted_flag,
                'kwargs': {
                    'basecolumn': 'Deleted',
                },
            },
            {
                'function': rio_add_ims_event_lookup,
                'kwargs': {
                    'basecolumn_event_num': 'EventNumber',
                    'column_prefix': 'Admission',
                    'internal_alias_prefix': 'ad',
                },
            },
        ],
    }),

    ('Inpatient_Movement', {
        'basetable': 'ImsEventMovement',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'EventNumber': 'Event_Number',  # RCEP
            'SequenceID': 'Movement_Key',  # RCEP
            'StartDateTime': 'Start_Date',  # RCEP
            'EndDateTime': 'End_Date',  # RCEP
            'WardCode': None,  # Ward_Code (RCEP) is from bay lookup
            'BayCode': None,  # Bay_Code (RCEP) is from bay lookup
            'BedNumber': 'Bed',  # RCEP
            'IdentitySequenceID': 'Unique_Key',  # RCEP
            'EpisodeType': None,  # lookup below
            'PsychiatricPatientStatus': None,  # lookup below
            'Consultant': None,  # user lookup
            'Specialty': None,  # lookup below
            'OtherConsultant': None,  # user lookup
            'MovementTypeFlag': 'Movement_Type_Flag',  # RCEP
            # RCEP: Initial_Movement_Flag ?source ?extra bit flag in new RiO
            'Diagnosis1': 'Diagnosis_1_FK_Diagnosis',  # in RCEP, DischargeDiagnosis1, etc.  # noqa
            'Diagnosis10': 'Diagnosis_10_FK_Diagnosis',
            'Diagnosis11': 'Diagnosis_11_FK_Diagnosis',
            'Diagnosis12': 'Diagnosis_12_FK_Diagnosis',
            'Diagnosis13': 'Diagnosis_13_FK_Diagnosis',
            'Diagnosis14': 'Diagnosis_14_FK_Diagnosis',
            'Diagnosis2': 'Diagnosis_2_FK_Diagnosis',
            'Diagnosis3': 'Diagnosis_3_FK_Diagnosis',
            'Diagnosis4': 'Diagnosis_4_FK_Diagnosis',
            'Diagnosis5': 'Diagnosis_5_FK_Diagnosis',
            'Diagnosis6': 'Diagnosis_6_FK_Diagnosis',
            'Diagnosis7': 'Diagnosis_7_FK_Diagnosis',
            'Diagnosis8': 'Diagnosis_8_FK_Diagnosis',
            'Diagnosis9': 'Diagnosis_9_FK_Diagnosis',
            'DiagnosisConfirmed': 'Diagnosis_Confirmed_Date_Time',  # RCEP
            'DiagnosisBy': None,  # user lookup
            'Service': None,  # lookup below
            'ServiceChargeRate': 'Service_Charge_Rate',  # RCEP
        },
        'add': [
            {
                'function': rio_add_bay_lookup,
                'kwargs': {
                    'basecolumn_ward': 'WardCode',
                    'basecolumn_bay': 'BayCode',
                    'column_prefix': '',
                    # Ward_Code, Ward_Description,
                    # Bay_Code, Bay_Description as per RCEP
                    'internal_alias_prefix': 'bay',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'EpisodeType',
                    'lookup_table': 'ImsEpisodeType',
                    'column_prefix': 'Episode_Type',
                    # in RCEP, code = Episode_Type, desc absent
                    'internal_alias_prefix': 'et',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'PsychiatricPatientStatus',
                    'lookup_table': 'ImsPsychiatricPatientStatus',
                    'column_prefix': 'Psychiatric_Patient_Status',
                    # in RCEP, code = Psychiatric_Patient_Status, desc absent
                    'internal_alias_prefix': 'pp',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'Consultant',
                    'column_prefix': 'Consultant',  # RCEP
                    'internal_alias_prefix': 'co',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'OtherConsultant',
                    'column_prefix': 'Other_Consultant',  # RCEP
                    'internal_alias_prefix': 'oc',
                },
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Specialty',
                    'lookup_table': 'GenSpecialty',
                    'column_prefix': 'Specialty',  # RCEP
                    'internal_alias_prefix': 'sp',
                }
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    # http://stackoverflow.com/questions/7778444
                    'expr': 'CAST((MovementTypeFlag & 1) AS BIT)',
                    'alias': 'Consultant_Change_Flag',
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CAST((MovementTypeFlag & 2) AS BIT)',
                    'alias': 'Bed_Change_Flag',
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CAST((MovementTypeFlag & 4) AS BIT)',
                    'alias': 'Bay_Change_Flag',
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CAST((MovementTypeFlag & 8) AS BIT)',
                    'alias': 'Ward_Change_Flag',
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CAST((MovementTypeFlag & 16) AS BIT)',
                    'alias': 'Service_Change_Flag',
                },
            },
            {
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CAST((MovementTypeFlag & 32) AS BIT)',
                    'alias': 'Nurse_Change_Flag',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'DiagnosisBy',
                    'column_prefix': 'Diag_Confirmed_By',  # RCEP
                    'internal_alias_prefix': 'dcb',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Service',
                    'lookup_table': 'GenService',
                    'column_prefix': 'Service',  # RCEP
                    'internal_alias_prefix': 'sv',
                },
            },
        ],
    }),

    ('Inpatient_Named_Nurse', {
        'basetable': 'ImsEventNamedNurse',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'EventNumber': 'Event_Number',  # RCEP
            'GenHCPCode': 'Named_Nurse_User_Code',  # RCEP
            'StartDateTime': 'Start_Date_Time',  # RCEP
            'EndDateTime': 'End_Date_Time',  # RCEP
            'SequenceID': 'Unique_Key',  # RCEP
            'EventMovementID': 'Key_To_Associated_Movement',  # RCEP
            'EndedOnDeath': 'Ended_On_Death_Flag',  # RCEP
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'GenHCPCode',
                    'column_prefix': 'User',
                    # ... RCEP is a bit confused, with
                    #   GenHCPCode -> Named_Nurse_User_Code
                    # and User_* for the other fields.
                    # Still, stick with it for now...
                    'internal_alias_prefix': 'nn',
                },
            },
        ],
    }),

    ('Inpatient_Sleepover', {
        'basetable': 'ImsEventSleepover',
        'rename': {
            # RCEP: Created_Date: see our Audit_Created_Date
            # RCEP: Updated_Date: see our Audit_Updated_Date
            'SequenceID': 'Event_Key',  # RCEP; not sure this one is worthwhile
            'EventID': 'Event_ID',  # RCEP
            'StartDate': 'Start_Date',  # StartDate in RCEP
            'ExpectedEndDate': 'Expected_End_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'WardCode': None,  # Ward_Code (RCEP) is from bay lookup
            'BayCode': None,  # Bay_Code (RCEP) is from bay lookup
            'BedNumber': 'Bed',  # RCEP
            # Comment: unchanged  # RCEP
            'EndedOnDeath': 'Ended_On_Death_Flag',  # RCEP
        },
        'add': [
            {
                'function': rio_add_bay_lookup,
                'kwargs': {
                    'basecolumn_ward': 'WardCode',
                    'basecolumn_bay': 'BayCode',
                    'column_prefix': '',
                    # Ward_Code, Ward_Description,
                    # Bay_Code, Bay_Description as per RCEP
                    'internal_alias_prefix': 'bay',
                },
            },
        ],
    }),

    # 'LSOA_buffer' is RCEP internal, cf. my ONS PD geography database

    ('Referral', {  # was Main_Referral_Data
        'basetable': 'AmsReferral',
        'rename': {
            # EnquiryNumber: unchanged
            # Referrer: unchanged; not in RCEP; missing?
            # Referral_Reason_National_Code: RCEP; ?source. Only AmsReferralSource.NationalCode  # noqa
            'AdministrativeCategory': None,  # lookup below
            'CABReferral': 'CAB_Referral',  # RCEP
            'ClientCareSpell': None,  # see lookup below
            'DischargeAddressLine1': 'Discharge_Address_Line_1',  # RCEP
            'DischargeAddressLine2': 'Discharge_Address_Line_2',  # RCEP
            'DischargeAddressLine3': 'Discharge_Address_Line_3',  # RCEP
            'DischargeAddressLine4': 'Discharge_Address_Line_4',  # RCEP
            'DischargeAddressLine5': 'Discharge_Address_Line_5',  # RCEP
            'DischargeAllocation': 'Discharge_Allocation',  # RCEP
            'DischargeComment': 'Discharge_Comment',  # RCEP
            'DischargeDateTime': 'Discharge_DateTime',  # not in RCEP; missing?
            'DischargedOnAdmission': 'Discharged_On_Admission',  # RCEP
            'DischargeHCP': None,  # RCEP; user lookup
            'DischargePostCode': 'Discharge_Post_Code',  # RCEP
            'DischargeReason': 'Discharge_Reason',  # not in RCEP; missing?
            'ExternalReferralId': 'External_Referral_Id',
            # ... RCEP (field is not VARCHAR(8000) as docs suggest; 25 in RiO,
            #     50 in RCEP)
            'HCPAllocationDate': 'HCP_Allocation_Date',  # RCEP
            'HCPReferredTo': None,  # not in RCEP; lookup added below
            'IWSComment': 'IWS_Comment',  # RCEP
            'IWSHeld': 'IWS_Held',  # RCEP
            'LikelyFunder': 'Likely_Funder',  # RCEP
            'LikelyLegalStatus': 'Likely_Legal_Status',  # RCEP
            'PatientArea': None,  # lookup below
            'ReferralAcceptedDate': 'Referral_Accepted_Date',  # RCEP
            'ReferralActionDate': 'Referral_ActionDate',  # not in RCEP; missing?  # noqa
            'ReferralAllocation': 'Referral_Allocation',  # RCEP
            'ReferralComment': 'Referral_Comment',  # not in RCEP; missing?
            'ReferralDateTime': 'Referral_DateTime',  # not in RCEP; missing?
            'ReferralNumber': 'Referral_Number',  # RCEP
            'ReferralReason': 'Referral_Reason_Code',  # RCEP, + lookup below
            'ReferralReceivedDate': 'Referral_Received_Date',  # RCEP
            'ReferralSource': 'Referral_Source',  # RCEP
            'ReferredConsultant': None,  # RCEP; user lookup
            'ReferredWard': 'Referred_Ward_Code',  # RCEP
            'ReferrerOther': 'Referrer_Other',  # RCEP
            'ReferringConsultant': None,  # tricky lookup; see below
            'ReferringGP': 'Referring_GP_Code',  # RCEP
            'ReferringGPPracticeCode': 'Referring_GP_Practice_Code',  # RCEP
            'RemovalCode': 'Removal_Code',  # RCEP
            'RemovalDateTime': 'Removal_DateTime',  # RCEP
            'RemovalUser': None,  # RCEP; user lookup
            'RTTCode': 'RTT_Code',  # RCEP; FK to RTTPathwayConfig.RTTCode (ignored)  # noqa
            'ServiceReferredTo': None,  # lookup below
            'SpecialtyReferredTo': None,  # lookup below
            'TeamReferredTo': None,  # not in RCEP; lookup added below
            'Urgency': None,  # lookup below
            'WaitingListID': 'Waiting_List_ID',  # RCEP; FK to WLConfig.WLCode (ignored)  # noqa
        },
        'add': [
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Urgency',
                    'lookup_table': 'GenUrgency',
                    'column_prefix': 'Urgency',
                    # not in RCEP; missing?
                    'internal_alias_prefix': 'ur',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'PatientArea',
                    'lookup_table': 'AmsPatientArea',
                    'column_prefix': 'Patient_Area',  # RCEP
                    # in RCEP, code = Patient_Area
                    'internal_alias_prefix': 'pa',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AdministrativeCategory',
                    'lookup_table': 'GenAdministrativeCategory',
                    'column_prefix': 'Administrative_Category',
                    # ... RCEP
                    'internal_alias_prefix': 'ac',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReferralReason',
                    'lookup_table': 'GenReferralReason',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'Referral_Reason_Description',
                        'NationalCode_CIDS': 'Referral_Reason_National_Code_CIDS',  # noqa
                        'NationalCode_CAMHS': 'Referral_Reason_National_Code_CAMHS',  # noqa
                        # ... RCEP, except Referral_Reason_National_Code;
                        # unsure which it refers to! Probably *_CIDS;
                        # http://www.datadictionary.nhs.uk/data_dictionary/messages/clinical_data_sets/data_sets/community_information_data_set_fr.asp?shownav=1  # noqa
                    },
                    'internal_alias_prefix': 'rr',
                }
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReferredWard',
                    'lookup_table': 'ImsWard',
                    'lookup_pk': 'WardCode',
                    'lookup_fields_aliases': {
                        'WardDescription': 'Referred_Ward_Description',  # RCEP
                    },
                    'internal_alias_prefix': 'rw',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeHCP',
                    'column_prefix': 'Discharge_HCP',  # RCEP
                    'internal_alias_prefix': 'dhcp',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ReferredConsultant',
                    'column_prefix': 'Referred_Consultant',  # RCEP
                    'internal_alias_prefix': 'rc',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'RemovalUser',
                    'column_prefix': 'Removal_User',  # RCEP
                    'internal_alias_prefix': 'ru',
                },
            },
            {
                'function': rio_add_carespell_lookup,
                'kwargs': {
                    'basecolumn': 'ClientCareSpell',
                    'column_prefix': 'Care_Spell',  # RCEP
                    'internal_alias_prefix': 'cs',
                },
            },
            {  # not in RCEP
                'function': rio_add_team_lookup,
                'kwargs': {
                    'basecolumn': 'TeamReferredTo',
                    'column_prefix': 'Team_Referred_To',
                    'internal_alias_prefix': 'trt',
                },
            },
            {  # not in RCEP
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'HCPReferredTo',
                    'column_prefix': 'HCP_Referred_To',
                    'internal_alias_prefix': 'hrt',
                },
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SpecialtyReferredTo',
                    'lookup_table': 'GenSpecialty',
                    'column_prefix': 'Specialty_Referred_To',
                    'internal_alias_prefix': 'sprt',
                }
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ServiceReferredTo',
                    'lookup_table': 'GenService',
                    'column_prefix': 'Service_Referred_To',
                    'internal_alias_prefix': 'sert',
                }
            },
            # Look up the same field two ways.
            {  # If AmsReferralSource.Behaviour = 'CS'...
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringConsultant',
                    'column_prefix': 'Referring_Consultant_Cons',
                    'internal_alias_prefix': 'rcc',
                },
            },
            {  # If AmsReferralSource.Behaviour = 'CH'...
                'function': rio_add_consultant_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringConsultant',
                    'column_prefix': 'Referring_Consultant_HCP',
                    # ... RCEP: Referring_Consultant_User
                    'internal_alias_prefix': 'rch',
                },
            },
        ],
    }),

    ('Progress_Notes', {
        'basetable': 'PrgProgressNote',
        'rename': {
            # create:
            'DateAndTime': 'Created_Date',  # RCEP; RCEP synonym: 'Date'
            'UserID': None,  # RCEP; user lookup
            # update:
            'EnterDatetime': 'Updated_Date',  # RCEP; later than DateAndTime
            'EnteredBy': None,  # not in RCEP; user lookup
            # verify:
            'VerifyDate': 'Verified_Date',  # RCEP was: Validate_This_Note
            'VerifyUserID': None,  # RCEP; user lookup
            # other:
            # 'HTMLIncludedFlag': None,  # RCEP
            # 'NoteNum': None,  # RCEP
            # 'Significant': 'This_Is_A_Significant_Event',  # RCEP
            # 'SubNum': None,  # RCEP
            'EnteredInError': 'Entered_In_Error',  # RCEP
            'NoteText': 'Text',  # RCEP
            'NoteType': None,  # lookup below
            'Problem': None,  # RCEP; "obsolete"
            'RiskRelated': 'Risk_Related',  # RCEP was: Add_To_Risk_History
            'RiskType': None,  # lookup below
            'SubNoteType': None,  # lookup below
            'ThirdPartyInfo': 'Third_Party_Info',
            # ... RCEP was: This_Note_Contains_Third_Party_Information
            'ClinicalEventType': None,  # lookup below
            'SpecialtyID': None,  # lookup below
        },
        'add': [
            {  # not in RCEP
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CASE WHEN {basetable}.VerifyDate IS NULL THEN 0 '
                            'ELSE 1 END',
                    'alias': 'validated',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'NoteType',
                    'lookup_table': 'GenUserPrgNoteType',
                    'column_prefix': 'Note_Type',
                    # in RCEP, code absent, desc = Note_Type
                    'internal_alias_prefix': 'nt',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SubNoteType',
                    'lookup_table': 'GenUserPrgNoteSubType',
                    'column_prefix': 'Sub_Note_Type',
                    # in RCEP, code absent, desc = Sub_Note_Type
                    'internal_alias_prefix': 'snt',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'RiskType',
                    'lookup_table': 'RskRiskType',
                    'column_prefix': 'Risk_Type',
                    # in RCEP, code absent, desc = Risk_Type
                    'internal_alias_prefix': 'rt',
                }
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ClinicalEventType',
                    'lookup_table': 'GenClinicalEventType',
                    'column_prefix': 'Clinical_Event_Type',
                    'internal_alias_prefix': 'cet',
                }
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SpecialtyID',
                    'lookup_table': 'GenSpecialty',
                    'column_prefix': 'Specialty',
                    'internal_alias_prefix': 'spec',
                }
            },
            {  # not in RCEP
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'RoleID',
                    'lookup_table': 'GenUserType',
                    'lookup_pk': 'UserTypeID',
                    'lookup_fields_aliases': {
                        'RoleDescription': 'Role_Description',
                    },
                    'internal_alias_prefix': 'rl',
                }
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'UserID',
                    'column_prefix': 'Originating_User',
                    # ... RCEP: was originator_user
                    'internal_alias_prefix': 'ou',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'EnteredBy',
                    'column_prefix': 'Updating_User',  # not in RCEP
                    'internal_alias_prefix': 'uu',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'VerifyUserID',
                    'column_prefix': 'Verifying_User',
                    # ... RCEP: was verified_by_user
                    'internal_alias_prefix': 'vu',
                },
            },
            {
                # Restrict to current progress notes using CRATE extra info?
                'function': where_prognotes_current,
            },
        ],
    }),

    ('Referral_Staff_History', {
        'basetable': 'AmsReferralAllocation',
        'rename': {
            # Comment: unchanged
            'CurrentAtDischarge': 'Current_At_Discharge',
            'EndDate': 'End_Date',  # RCEP
            'HCPCode': None,  # RCEP was HCPCode but this is in user lookup
            'ReferralID': 'Referral_Key',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'TransferDate': 'Transfer_Date',  # RCEP
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'HCPCode',
                    'column_prefix': 'HCP',  # RCEP uses HCP_User_*
                    'internal_alias_prefix': 'hu',
                },
            },
        ],
        'suppress_basetable': True,
        'suppress_other_tables': [],
    }),

    ('Referral_Team_History', {
        'basetable': 'AmsReferralTeam',
        'rename': {
            # Comment - unchanged
            'CurrentAtDischarge': 'Current_At_Discharge',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'ReferralID': 'Referral_Key',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'TeamCode': None,  # Team_Code (as per RCEP) from lookup below
        },
        'add': [
            {
                'function': rio_add_team_lookup,
                'kwargs': {
                    'basecolumn': 'TeamCode',
                    'column_prefix': 'Team',  # RCEP
                    'internal_alias_prefix': 't',
                },
            },
        ],
    }),

    ('Referral_Waiting_Status_History', {
        'basetable': 'AmsReferralListWaitingStatus',
        'rename': {
            'ChangeBy': None,  # RCEP; user lookup
            'ChangeDateTime': 'Change_Date_Time',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'ReferralID': 'Referral_Key',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'WaitingStatus': None,  # lookup below
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'WaitingStatus',
                    'lookup_table': 'GenReferralWaitingStatus',
                    'column_prefix': 'Waiting_Status',
                    # in RCEP, code absent, desc = Waiting_Status
                    'internal_alias_prefix': 'ws',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ChangeBy',
                    'column_prefix': 'Changed_By',  # RCEP
                    'internal_alias_prefix': 'cb',
                },
            },
        ],
    }),

    # -------------------------------------------------------------------------
    # Core: important things missed out by RCEP
    # -------------------------------------------------------------------------

    ('Clinical_Documents', {
        'basetable': 'ClientDocument',
        'rename': {
            # ClientID: ignored; CRATE_COL_RIO_NUMBER instead
            # SequenceID: ignored; CRATE_COL_PK instead
            'UserID': None,  # user lookup
            'Type': None,  # lookup below
            'DateCreated': 'Date_Created',
            'SerialNumber': 'Serial_Number',  # can repeat across ClientID
            'Path': 'Path',  # ... no path, just filename (but CONTAINS ID)
            # ... filename format is e.g.:
            #   46-1-20130903-XXXXXXX-OC.pdf
            # where 46 = SerialNumber; 1 = RevisionID; 20130903 = date;
            # XXXXXXX = RiO number; OC = Type
            'Description': 'Description',
            'Title': 'Title',
            'Author': 'Author',
            'DocumentDate': 'Document_Date',
            'InsertedDate': 'Inserted_Date',
            'RevisionID': 'Document_Version',  # starts from 1 for each
            'FinalRevFlag': 'Is_Final_Version',  # 0 (draft) or 1 (final)
            'DeletedDate': 'Deleted_Date',
            'DeletedBy': None,  # user lookup
            'DeletedReason': None,  # lookup below
            'FileSize': 'File_Size',
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'UserID',
                    'column_prefix': 'Storing_User',
                    'internal_alias_prefix': 'su',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Type',
                    'lookup_table': 'GenDocumentType',
                    'column_prefix': 'Type',
                    'internal_alias_prefix': 'ty',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'DeletedBy',
                    'column_prefix': 'Deleting_User',
                    'internal_alias_prefix': 'du',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'DeletedReason',
                    'lookup_table': 'GenDocumentRemovalReason',
                    'column_prefix': 'Deleted_Reason',
                    'internal_alias_prefix': 'dr',
                },
            },
            {
                # Restrict to current progress notes using CRATE extra info?
                'function': where_clindocs_current,
            },
        ],
    }),


    # -------------------------------------------------------------------------
    # Non-core: CPFT
    # -------------------------------------------------------------------------

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # CPFT Core Assessment v2
    #
    # 1. Getting form and table names (prepend 'UserAssess' to table names):
    #
    #    USE rio_data_raw;
    #
    #    SELECT *
    #    FROM AssessmentFormGroupsIndex afgi
    #    INNER JOIN AssessmentFormGroupsStructure afgs
    #      ON afgs.name = afgi.Name
    #    INNER JOIN AssessmentFormsIndex afi
    #      ON afi.name = afgs.FormName
    #    WHERE afgi.deleted = 0
    #    AND afgi.Description = 'Core Assessment v2'
    #    ORDER BY afgs.FormOrder, afgs.FormName, afgs.FormgroupVersion;
    #
    # 2. Getting field descriptions: explore the front end
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ('CPFT_Core_Assessment_v2_Presenting_Problem', {
        'basetable': 'UserAssesscoreasspresprob',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'ReasonRef': 'Reasons_For_Referral',
            'HistProb': 'History_Of_Presenting_Problem',
            'CurrInt': 'Current_Interventions_Medication',
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
        ],
    }),

    ('CPFT_Core_Assessment_v2_PPH_PMH_Allergies_Frailty', {
        'basetable': 'UserAssesscoreassesspastpsy',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'PastPsyHist': 'Past_Psychiatric_History',
            'PhyHealth': 'Physical_Health_Medical_History',
            'Allergies': 'Allergies',
        }),
        'add': [
            {
                # Rockwood frailty score
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'frailty',
                    'lookup_table': 'UserMasterfrailty',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'Frailty_Description',
                    },
                    'internal_alias_prefix': 'fr',
                }
            },
            {'function': rio_amend_standard_noncore},
        ],
    }),

    ('CPFT_Core_Assessment_v2_Background_History', {
        'basetable': 'UserAssesscoreassessbackhist',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'FamPersHist': 'Family_Personal_History',
            'ScoHist': 'Social_History',  # sic (Sco not Soc)
            'DruAlc': 'Drugs_Alcohol',
            'ForHist': 'Forensic_History',
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
        ],
    }),

    ('CPFT_Core_Assessment_v2_Mental_State', {
        'basetable': 'UserAssesscoreassesmentstate',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'MentState': 'Mental_State_Examination',
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
        ],
    }),

    ('CPFT_Core_Assessment_v2_Capacity_Safeguarding_Risk', {
        'basetable': 'UserAssesscoreassescapsafrisk',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'CapIssCon': 'Capacity_Issues_Consent',
            'Safeguard': 'Safeguarding',
            # "Please indicate whether any issues were identified..."
            'sovayn': 'Risk_SOVA',
            'childprotyn': 'Risk_Child_Protection',
            'sshyn': 'Risk_Suicide_Self_Harm',
            'violyn': 'Risk_Violence',
            'negvulyn': 'Risk_Neglect_Vulnerability',
            'fallsyn': 'Risk_Falls',
            'CurrDL2': 'Current_Driving_Licence',
            'Riskida': 'Risk_Impaired_Driving',
            'Risk': 'Risk_Screen',
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
        ],
    }),

    ('CPFT_Core_Assessment_v2_Summary_Initial_Plan', {
        'basetable': 'UserAssesscoreasssumminitplan',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'ServStre': 'Service_User_Strengths_Needs_Expectations',
            'CareView': 'Carer_Views_Needs',
            'SummForm': 'Summary_Formulation',
            'Plan1': 'Initial_Plan',
            # PLAN is an SQL Server reserved word:
            # https://msdn.microsoft.com/en-us/library/ms189822.aspx
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
        ],
    }),

    ('CPFT_Core_Assessment_v2_Social_Circumstances_Employment', {
        'basetable': 'UserAssesscoresocial1',
        # no free text
        # bad field names!
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'Social06': None,  # lookup below
            'Social07': None,  # lookup below
            'Social16': None,  # lookup below
            'Social17': None,  # lookup below
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Social06',
                    # ... range 1-50, and field order
                    'lookup_table': 'GenAccommodationStatus',
                    'column_prefix': 'Accommodation_Status',  # RCEP
                    'internal_alias_prefix': 'as',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Social07',
                    # ... range 1-5, and field order
                    'lookup_table': 'GenSettledAccommodation',
                    'column_prefix': 'Settled_Accommodation_Indicator',  # RCEP
                    'internal_alias_prefix': 'sa',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Social16',
                    # ... range 1-12, and field order
                    'lookup_table': 'GenEmpStatus',
                    'column_prefix': 'Employment_Status',  # RCEP
                    'internal_alias_prefix': 'es',
                }
            },
            {
                'function': standard_rio_code_lookup_with_national_code,
                'kwargs': {
                    'basecolumn': 'Social17',
                    # ... by elimination, and field order
                    'lookup_table': 'GenWeeklyHoursWorked',
                    'column_prefix': 'Weekly_Hours_Worked',  # not in RCEP
                    # RCEP code was Weekly_Hours_Worked
                    'internal_alias_prefix': 'whw',
                }
            },
        ],
    }),

    ('CPFT_Core_Assessment_v2_Keeping_Children_Safe_Assessment', {
        # Stem was kcsahyper, so you'd expect the table to be
        # UserAssesskcsahyper; however, that doesn't exist. For '%kcsa%', there
        # are:
        # - UserAssesstfkcsa
        #       ... this is the main one
        # - UserAssesstfkcsa_childs
        #       ... this is the list of children in current household
        # - UserAssesstfkcsa_childprev
        #       ... this is the list of children from prev. relationships
        'basetable': 'UserAssesstfkcsa',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            # - Does SU live in household where there are children?
            # - Please specify relationship?
            # - Is SU expecting a baby?
            # - If so, what is the EDD?
            # - Children in household:
            #   - List of: {name of child, date of birth, gender}
            #     (with minimum list size, with child name = "N/A" if none)
            # - Does the SU have contact with children (not living in the same
            #   household) from previous relationships?
            #   - If yes, specify (LIST as above)
            # - Comments
            # - Does the SU have significant contact with other children?
            # - If yes, please specify
            #
            # [FAMILY/ENVIRONMENTAL FACTORS]
            # - Does the SU experience any family and environmental
            #   difficulties that could impact on their ability to care for
            #   children?
            # - Please use this space to support your assessment outcome
            # [PARENTING CAPACITY]
            # - "Consider the outcomes of the adult assessment. Can the service
            #   user demonstrate their ability to care for children or do they
            #   require any additional support with parenting?"
            #   ... Exceptionally bad phrasing! Field is "DemAb"
            # - comments
            # [CHILD DEVELOPMENTAL NEEDS]
            # - Does info suggest there could be... difficulties with child's
            #   developmental needs?
            # - comments
            # [DOMESTIC ABUSE]
            # - Is this person affected by domestic abuse?
            # - comments
            # [SUBSTANCE MISUSE#
            # - Any concerns in relation to substance misuse?
            # - comments
            # [MENTAL HEALTH, DELUSIONAL IDEATION, SUICIDE PLANNING]
            # - does risk profile indicate delusional beliefs involving
            #   children?
            # - does... indicat suicidal ideation and/or suicide plan involving
            #   children?
            # - are there any other MH concerns which may impact on SU's
            #   ability to care for children?
            # - comments
            #
            # - CURRENT RISK/NEED STATUS (1 low to 4 serious+imminent)

            'ChildHous': None,  # transform below
            'Relation': 'Children_In_Household_Relationship',
            'expectQ': None,  # transform below
            'dodv': 'Estimated_Delivery_Date',
            'ChildCon': None,  # transform below
            'commts': 'Comments',
            'SigCon': None,  # transform below
            'SigConSpec': 'Significant_Contact_Other_Children_Specify',
            'EnvDiff': None,  # transform below
            'EnvDiffSpec': 'Family_Environment_Difficulty_Specify',
            'DemAb': None,  # transform below
            'DemAbSpec': 'Demonstrate_Ability_Care_Children_Specify',
            'DevNeeds': None,  # transform below
            'DevNeedsSpec': 'Child_Developmental_Needs_Specify',
            'domab1': None,  # transform below
            'DomAbSpec': 'Domestic_Abuse_Specify',
            'SubMis': None,  # transform below
            'SubMisSpec': 'Substance_Misuse_Specify',
            'Q1': None,  # transform below
            'Q2': None,  # transform below
            'Q3': None,  # transform below
            'QSpec': 'Mental_Health_Specify',
            'CRNS': None,  # lookup below
        }),
        'add': [
            {'function': rio_amend_standard_noncore},
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'ChildHous',
                    'result_alias': 'Children_In_Household',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'expectQ',
                    'result_alias': 'Pregnant',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'ChildCon',
                    'result_alias': 'Contact_Children_Prev_Relationship_Other_Household',  # noqa
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'SigCon',
                    'result_alias': 'Significant_Contact_Other_Children',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'EnvDiff',
                    'result_alias': 'Family_Environment_Difficulty_Concern',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'DemAb',
                    'result_alias': 'Demonstrate_Ability_Care_Children_Or_Requires_Support',  # noqa
                    #  ... not safe to fail to allude to ambiguity of this
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'DevNeeds',
                    'result_alias': 'Child_Developmental_Needs_Concern',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'domab1',
                    'result_alias': 'Domestic_Abuse_Concern',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'SubMis',
                    'result_alias': 'Substance_Misuse_Concern',
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'Q1',
                    'result_alias': 'Mental_Health_Delusional_Beliefs_Re_Children',  # noqa
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'Q2',
                    'result_alias': 'Mental_Health_Suicidal_Or_Suicide_Plan_Re_Children',  # noqa
                },
            },
            {
                'function': rio_noncore_yn,
                'kwargs': {
                    'basecolumn': 'Q3',
                    'result_alias': 'Mental_Health_Other_Concern_Affecting_Child_Care',  # noqa
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'CRNS',
                    'lookup_table': 'UserMasterCRNS',
                    'column_prefix': 'Current_Risk_Need_Status',
                    'internal_alias_prefix': 'crns',
                },
            },
        ],
    }),

    ('CPFT_Core_Assessment_v2_KCSA_Children_In_Household', {
        'basetable': 'UserAssesstfkcsa_childs',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'type12_NoteID': 'KCSA_Note_ID',
            'NOC': 'Child_Name',
            'DOB': 'Child_Date_Of_Birth',
            'Gender': None,  # lookup below
        }),
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Gender',
                    'lookup_table': 'UserMasterGender',
                    'column_prefix': 'Child_Gender',
                    'internal_alias_prefix': 'cg',
                },
            },
        ],
    }),

    ('CPFT_Core_Assessment_v2_KCSA_Children_Previous_Relationships', {
        'basetable': 'UserAssesstfkcsa_childprev',
        'rename': merge_dicts(DEFAULT_NONCORE_RENAMES, {
            'type12_NoteID': 'KCSA_Note_ID',
            'chname': 'Child_Name',
            'chdob': 'Child_Date_Of_Birth',
            'chgend': None,  # lookup below
        }),
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'chgend',
                    'lookup_table': 'UserMasterGender',
                    'column_prefix': 'Child_Gender',
                    'internal_alias_prefix': 'cg',
                },
            },
        ],
    }),
])
