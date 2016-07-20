#!/usr/bin/env python
# crate_anon/preprocess/rio_ddgen.py

import logging

from crate_anon.common.lang import (
    get_case_insensitive_dict_key,
)
from crate_anon.common.sql import (
    add_indexes,
    drop_indexes,
)
from crate_anon.preprocess.rio_constants import (
    RIO_COL_PATIENT_ID,
    VIEW_ADDRESS_WITH_GEOGRAPHY,
)

log = logging.getLogger(__name__)


# =============================================================================
# DDHint class
# =============================================================================

class DDHint(object):
    def __init__(self):
        self._suppressed_tables = set()
        self._index_requests = {}  # dict of dicts

    def suppress_table(self, table):
        self._suppressed_tables.add(table)

    def suppress_tables(self, tables):
        for t in tables:
            self.suppress_table(t)

    def get_suppressed_tables(self):
        return sorted(self._suppressed_tables)

    def add_source_index_request(self, table, columns):
        if isinstance(columns, str):
            columns = [columns]
        assert table, "Bad table: {}".format(repr(table))
        assert columns, "Bad columns: {}".format(repr(columns))
        index_name = 'crate_idx_' + '_'.join(columns)
        if table not in self._index_requests:
            self._index_requests[table] = {}
            if index_name not in self._index_requests[table]:
                self._index_requests[table][index_name] = {
                    'index_name': index_name,
                    'column': ', '.join(columns),
                    'unique': False,
                }

    def add_bulk_source_index_request(self, table_columns_list):
        for table, columns in table_columns_list:
            assert table, ("Bad table; table={}, table_columns_list={}".format(
                repr(table), repr(table_columns_list)))
            assert columns, (
                "Bad table; columns={}, table_columns_list={}".format(
                    repr(columns), repr(table_columns_list)))
            self.add_source_index_request(table, columns)

    def add_indexes(self, engine, metadata):
        for tablename, tabledict in self._index_requests.items():
            indexdictlist = []
            for indexname, indexdict in tabledict.items():
                indexdictlist.append(indexdict)
            tablename_casematch = get_case_insensitive_dict_key(
                metadata.tables, tablename)
            if not tablename_casematch:
                log.warning("add_indexes: Skipping index as table {} "
                            "absent".format(tablename))
                continue
            table = metadata.tables[tablename_casematch]
            add_indexes(engine, table, indexdictlist)

    def drop_indexes(self, engine, metadata):
        for tablename, tabledict in self._index_requests.items():
            index_names = list(tabledict.keys())
            tablename_casematch = get_case_insensitive_dict_key(
                metadata.tables, tablename)
            if not tablename_casematch:
                log.warning("add_indexes: Skipping index as table {} "
                            "absent".format(tablename))
                continue
            table = metadata.tables[tablename_casematch]
            drop_indexes(engine, table, index_names)


# =============================================================================
# Default settings for CRATE anonymiser "ddgen_*" fields, for RiO
# =============================================================================

def get_rio_dd_settings(ddhint):
    return """
ddgen_omit_by_default = True

ddgen_omit_fields =

ddgen_include_fields = #
    # -------------------------------------------------------------------------
    # RCEP core views:
    # -------------------------------------------------------------------------
    Care_Plan_Index.*
    Care_Plan_Interventions.*
    Care_Plan_Problems.*
    Client_Address_History.*
    Client_Alternative_ID.*
    Client_Allergies.*
    Client_Communications_History.*
    Client_CPA.*
    Client_Demographic_Details.*
    Client_Family.*
    Client_GP_History.*
    Client_Medication.*
    Client_Name_History.*
    Client_Personal_Contacts.*
    Client_Physical_Details.*
    Client_Prescription.*
    Client_Professional_Contacts.*
    Client_School.*
    CPA_CareCoordinator.*
    CPA_Review.*
    Diagnosis.*
    Inpatient_Stay.*
    Inpatient_Leave.*
    Inpatient_Movement.*
    Inpatient_Named_Nurse.*
    Inpatient_Sleepover.*
    Referral.*
    Progress_Notes.*
    Referral_Staff_History.*
    Referral_Team_History.*
    Referral_Waiting_Status_History.*
    # -------------------------------------------------------------------------
    # Non-core:
    # -------------------------------------------------------------------------
    Core_Assessment_PPH_PMH_Allergies_Frailty.*

ddgen_allow_no_patient_info = False

ddgen_per_table_pid_field = crate_rio_number

ddgen_add_per_table_pids_to_scrubber = False

ddgen_master_pid_fieldname = crate_nhs_number_int

ddgen_table_whitelist = #
    # -------------------------------------------------------------------------
    # Whitelist: Prefixes: groups of tables
    # -------------------------------------------------------------------------
    EPClientAllergy*  # Allergy details within EP module
    # -------------------------------------------------------------------------
    # Whitelist: Suffixes
    # -------------------------------------------------------------------------
    *_crate  # Views added by CRATE
    # -------------------------------------------------------------------------
    # Whitelist: Individual tables
    # -------------------------------------------------------------------------
    EPReactionType  # Allergy reaction type details within EP module

ddgen_table_blacklist = #
    # -------------------------------------------------------------------------
    # Blacklist: Prefixes: groups of tables; individual tables
    # -------------------------------------------------------------------------
    Agresso*  # Agresso [sic] module (comms to social worker systems)
    ADT*  # ?admit/discharge/transfer messages (see codes in ADTMessage)
    Ams*  # Appointment Management System (Ams) module
    Audit*  # RiO Audit Trail
    CDSContract*  # something to do with commissioner contracts
    Chd*  # Child development (interesting, but lots of tables and all empty)
    ClientAddressHistory  # defunct according to RIO 6.2 docs
    ClientAddressMerged  # defunct according to RIO 6.2 docs
    ClientChild*  # child info e.g. birth/immunisation (interesting, but several tables and all empty)
    ClientCommunityDomain # defunct according to RIO 6.2 docs
    ClientFamily  # contains only a comment; see ClientFamilyLink instead
    ClientMerge*  # record of admin events (merging of client records)
    ClientPhoto*  # no use to us or identifiable!
    ClientRestrictedRecord*  # ? but admin
    Con*  # Contracts module
    DA*  # Drug Administration within EP
    DgnDiagnosis  # "Obsolete"; see DiagnosisClient
    DS*  # Drug Service within EP
    EP*  # E-Prescribing (EP) module, which we don't have
    #   ... mostly we don't have it, but we may have EPClientAllergies etc.
    #   ... so see whitelist too
    ESRImport  # user-to-?role map? Small and system.
    ExternalSystem*  # system
    GenChd*  # lookup codes for Chd*
    GenCon*  # lookup codes for Con*
    GenDiagnosis  # "Obsolete"
    GenError*  # system
    GenExtract*  # details of reporting extracts
    GenHCPTemplateDetails  # HCP diary template
    GenIDSeed  # system (counters for different ID types)
    GenLicenseKeys  # system; NB shows what components are licensed!
    GenPrinter*  # printers
    GenToDoList  # user to-do list items/notifications
    KP90ErrorLog  # error log for KP90 report; http://www.hscic.gov.uk/datacollections/kp90
    LR*  # Legitimate Relationships module
    Meeting*  # Meetings module
    Mes*  # messaging
    MonthlyPlanner*  # system
    PSS*  # Prevention, Screening & Surveillance (PSS)
    RioPerformanceTimings  # system
    RR*  # Results Reporting (e.g. laboratories, radiology)
    #   ... would be great, but we don't have it
    RTT*  # RTT* = Referral-to-Treatment (RTT) data collection (see NHS England docs)
    SAF*  # SAF* = system; looks like details of tablet devices
    Scheduler*  # Scheduler* = Scheduler module (for RiO computing)
    Sec*  # Security? Definitely RiO internal stuff.
    SPINE*  # system
    SPRExternalNotification  # system?
    tbl*  # records of changes to tables?
    TeamPlanner*  # system
    Temp*  # system
    umt*  # system
    Wfl*  # workflow
    WL*  # Waiting lists (WL) module
    # -------------------------------------------------------------------------
    # Blacklist: Middle bits, suffixes
    # -------------------------------------------------------------------------
    *Access*  # system access controls
    *Backup  # I'm guessing backups...
    *Cache*  # system
    *Lock*  # system
    *Timeout*  # system
    # -------------------------------------------------------------------------
    # Blacklist: Views supersede
    # Below here, we have other tables suppressed because CRATE's views offer
    # more comprehensive alternatives
    # -------------------------------------------------------------------------
    {suppress_tables}

# USEFUL TABLES (IN CPFT INSTANCE) INCLUDE:
# =========================================
# Assessment* = includes maps of non-core assessments (see e.g. AssessmentIndex)
# CDL_OUTDATEDPATIENTS_TWI = map from TWI (trust-wide identifier) to old CPFT M number
# UserAssess* = non-core assessments themselves
# UserMaster* = lookup tables for non-core assessments

ddgen_field_whitelist =

ddgen_field_blacklist = #
    {RIO_COL_PATIENT_ID}  # replaced by crate_rio_number
    *Soundex  # identifying 4-character code; https://msdn.microsoft.com/en-us/library/ms187384.aspx
    Spine*  # NHS Spine identifying codes

ddgen_pk_fields = crate_pk

ddgen_constant_content = False

ddgen_constant_content_tables =

ddgen_nonconstant_content_tables =

ddgen_addition_only = False

ddgen_addition_only_tables = #
    UserMaster*  # Lookup tables for non-core - addition only?

ddgen_deletion_possible_tables =

ddgen_pid_defining_fieldnames = ClientIndex.crate_rio_number

ddgen_scrubsrc_patient_fields = # several of these:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    AmsReferral.DischargeAddressLine*  # superseded by view Referral
    AmsReferral.DischargePostCode  # superseded by view Referral
    ClientAddress.AddressLine*  # superseded by view Client_Address_History
    ClientAddress.PostCode  # superseded by view Client_Address_History
    ClientAlternativeID.ID  # superseded by view Client_Alternative_ID
    ClientIndex.crate_pk  # superseded by view Client_Demographic_Details
    ClientIndex.DateOfBirth  # superseded by view Client_Demographic_Details
    ClientIndex.DaytimePhone  # superseded by view Client_Demographic_Details
    ClientIndex.EMailAddress  # superseded by view Client_Demographic_Details
    ClientIndex.EveningPhone  # superseded by view Client_Demographic_Details
    ClientIndex.Firstname  # superseded by view Client_Demographic_Details
    ClientIndex.MobilePhone  # superseded by view Client_Demographic_Details
    ClientIndex.NINumber  # superseded by view Client_Demographic_Details
    ClientIndex.OtherAddress  # superseded by view Client_Demographic_Details
    ClientIndex.SpineID  # superseded by view Client_Demographic_Details
    ClientIndex.Surname  # superseded by view Client_Demographic_Details
    ClientName.GivenName*  # superseded by view Client_Name_History
    ClientName.Surname  # superseded by view Client_Name_History
    ClientTelecom.Detail  # superseded by view Client_Communications_History
    ImsEvent.DischargeAddressLine*  # superseded by view Inpatient_Stay
    ImsEvent.DischargePostCode*  # superseded by view Inpatient_Stay
    ImsEventLeave.AddressLine*  # superseded by view Inpatient_Leave
    ImsEventLeave.PostCode  # superseded by view Inpatient_Leave
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    Client_Address_History.Address_Line_*
    Client_Address_History.Post_Code
    Client_Alternative_ID.ID
    Client_Communications_History.crate_telephone
    Client_Communications_History.crate_email_address
    Client_Demographic_Details.crate_rio_number
    Client_Demographic_Details.NHS_Number
    Client_Demographic_Details.Firstname
    Client_Demographic_Details.Surname
    Client_Demographic_Details.Date_of_Birth
    Client_Demographic_Details.*Phone
    Client_Demographic_Details.Superseding_NHS_Number
    Client_Name_History.Given_Name_*
    Client_Name_History.Family_Name
    Inpatient_Leave.Address_Line*
    Inpatient_Leave.PostCode
    Inpatient_Stay.Discharge_Address_Line_*
    Inpatient_Stay.Discharge_Post_Code*
    Referral.Discharge_Address_Line_*
    Referral.Discharge_Post_Code*
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.AddressLine*  # superseded by other view Client_Address_History
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.PostCode  # superseded by other view Client_Address_History

ddgen_scrubsrc_thirdparty_fields = # several:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # ClientFamilyLink.RelatedClientID  # superseded by view Client_Family
    ClientContact.Surname  # superseded by view Client_Personal_Contacts
    ClientContact.Firstname  # superseded by view Client_Personal_Contacts
    ClientContact.AddressLine*  # superseded by view Client_Personal_Contacts
    ClientContact.PostCode  # superseded by view Client_Personal_Contacts
    ClientContact.*Phone  # superseded by view Client_Personal_Contacts
    ClientContact.EmailAddress  # superseded by view Client_Personal_Contacts
    ClientContact.NHSNumber  # superseded by view Client_Personal_Contacts
    # ClientIndex.MainCarer  # superseded by view Client_Demographic_Details
    # ClientIndex.OtherCarer  # superseded by view Client_Demographic_Details
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    Client_Personal_Contacts.Family_Name
    Client_Personal_Contacts.Given_Name
    Client_Personal_Contacts.Address_Line_*
    Client_Personal_Contacts.Post_Code
    Client_Personal_Contacts.*Phone
    Client_Personal_Contacts.Email_Address
    Client_Personal_Contacts.NHS_Number

ddgen_scrubsrc_thirdparty_xref_pid_fields = # several:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # none; these are not integer:
    # ClientFamilyLink.RelatedClientID  # superseded by view Client_Family
    # ClientIndex.MainCarer  # superseded by view Client_Demographic_Details
    # ClientIndex.OtherCarer  # superseded by view Client_Demographic_Details
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    Client_Demographic_Details.Main_Carer
    Client_Demographic_Details.Other_Carer
    Client_Family.Related_Client_ID

ddgen_scrubmethod_code_fields = # variants:
    *PostCode*
    *Post_Code*
    NINumber
    National_Insurance_Number
    ClientAlternativeID.ID
    Client_Alternative_ID.ID

ddgen_scrubmethod_date_fields = *Date*

ddgen_scrubmethod_number_fields = #
    *Phone*
    *NNN*
    *NHS_Number*

ddgen_scrubmethod_phrase_fields = *Address*

ddgen_safe_fields_exempt_from_scrubbing =

    # RiO mostly uses string column lengths of 4, 10, 20, 40, 80, 500,
    # unlimited. So what length is the minimum for "free text"?
    # Comments are 500. Lots of 80-length fields are lookup descriptions.
    # (Note that many scrub-SOURCE fields are of length 80, e.g. address
    # fields, but they need different special handling.)
ddgen_min_length_for_scrubbing = 81

ddgen_truncate_date_fields = ClientIndex.DateOfBirth

ddgen_filename_to_text_fields = Clinical_Documents.Path

ddgen_binary_to_text_field_pairs =

ddgen_skip_row_if_extract_text_fails_fields = Clinical_Documents.Path

ddgen_index_fields =

ddgen_allow_fulltext_indexing = True

ddgen_force_lower_case = False

ddgen_convert_odd_chars_to_underscore = True
    """.format(  # noqa
        suppress_tables="\n    ".join(ddhint.get_suppressed_tables()),
        RIO_COL_PATIENT_ID=RIO_COL_PATIENT_ID,
        VIEW_ADDRESS_WITH_GEOGRAPHY=VIEW_ADDRESS_WITH_GEOGRAPHY,
    )
