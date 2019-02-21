#!/usr/bin/env python

"""
crate_anon/preprocess/rio_pk.py

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

**Details of the names of primary keys in selected RiO tables.**

"""

__SUPERSEDED = """

RIO_6_2_ATYPICAL_PKS = {  # SUPERSEDED by better PK detection

    # These are table: pk_field mappings for PATIENT tables, i.e. those
    # containing the ClientID field, where that PK is not the default of
    # SequenceID.

    # -------------------------------------------------------------------------
    # RiO Core
    # -------------------------------------------------------------------------

    # Ams*: Appointment Management System
    'AmsAppointmentContactActivity': 'ActivitySequenceID',
    'AmsAppointmentOtherHCP': None,  # non-patient; non-unique SequenceID
    # ... SequenceID is non-unique and the docs also list it as an FK;
    #     ActivitySequenceID this is unique and a PK
    'AmsReferralDatesArchive': 'AMSSequenceID',
    # ... UNVERIFIED as no rows in our data; listed as a PK and an FK
    'AmsReferralListUrgency': None,
    'AmsReferralListWaitingStatus': None,
    'AmsStream': None,  # non-patient; non-unique SequenceID

    'CarePlanIndex': 'CarePlanID',
    'CarePlanProblemOrder': None,

    'ClientAddressMerged': None,  # disused table
    'ClientCareSpell': None,  # CareSpellNum is usually 1 for a given ClientID
    'ClientDocumentAdditionalClient': None,
    'ClientFamily': None,
    'ClientFamilyLink': None,
    'ClientGPMerged': None,
    'ClientHealthCareProvider': None,
    'ClientMerge': None,
    'ClientMerged': None,
    'ClientName': 'ClientNameID',
    'ClientOtherDetail': None,  # not in docs, but looks like Core
    'ClientPhoto': None,
    'ClientPhotoMerged': None,
    'ClientProperty': None,
    'ClientPropertyMerged': None,
    'ClientTelecom': 'ClientTelecomID',
    'ClientUpdatePDSCache': None,

    # Con*: Contracts
    'Contract': 'ContractNumber',
    'ConAdHocAwaitingApproval': 'SequenceNo',
    'ConClientInitialBedRate': None,
    'ConClinicHistory': 'SequenceNo',
    'ConLeaveDiscountHistory': 'SequenceNo',

    # Not documented, but looks like Core
    'Deceased': None,  # or possibly TrustWideID (or just ClientID!)

    'DemClientDeletedDetails': None,

    # EP: E-Prescribing
    # ... with DA: Drug Administration
    # ... with DS: Drug Service
    'EPClientConditions': 'RowID',
    'EPClientPrescription': 'PrescriptionID',
    'EPClientSensitivities': None,  # UNVERIFIED: None? Joint PK on ProdID?
    'EPDiscretionaryDrugClientLink': None,
    'EPVariableDosageDrugLink': 'HistoryID',  # UNVERIFIED
    'EPClientAllergies': 'ReactionID',
    'DAConcurrencyControl': None,
    'DAIPPrescription': 'PrescriptionID',
    'DSBatchPatientGroups': None,
    'DSMedicationBatchContinue': None,
    'DSMedicationBatchLink': None,

    # Ims*: Inpatient Management System
    'ImsEventLeave': 'UniqueSequenceID',  # SequenceID
    'ImsEventMovement': None,
    'ImsEventRefno': None,  # Not in docs but looks like Core.
    'ImsEventRefnoBAKUP': None,  # [Sic.] Not in docs but looks like Core.

    # LR*: Legitimate Relationships
    'LRIdentifiedCache': None,

    # Mes*: messaging
    'MesLettersGenerated': 'Reference',

    # Mnt*: Mental Health module (re MHA detention)
    'MntArtAttendee': None,  # SequenceID being "of person within a meeting"
    'MntArtOutcome': None,  # ditto
    'MntArtPanel': None,  # ditto
    'MntArtRpts': None,  # ditto
    'MntArtRptsReceived': None,  # ditto
    'MntClientEctSection62': None,
    'MntClientMedSection62': None,
    'MntClientSectionDetailCareCoOrdinator': None,
    'MntClientSectionDetailCourtAppearance': None,
    'MntClientSectionDetailFMR': None,
    'MntClientSectionReview': None,

    # NDTMS*: Nation(al?) Drug Treatment Monitoring System

    # SNOMED*: SNOMED
    'SNOMED_Client': 'SC_ID',

    # UserAssess*: user assessment (= non-core?) tables.
    # See other default PK below: type12:

    # -------------------------------------------------------------------------
    # Non-core? No docs available.
    # -------------------------------------------------------------------------
    # Chd*: presumably, child development
    'ChdClientDevCheckBreastFeeding': None,
    # ... guess; DevChkSeqID is probably FK to ChdClientDevCheck.SequenceID

    # ??? But it has q1-q30, qu2-14, home, sch, comm... assessment tool...
    'CYPcurrentviewImport': None,  # not TrustWideID (which is non-unique)

    'GoldmineIfcMapping': None,  # no idea, really, and no data to explore

    'KP90ErrorLog': None,

    'ReportsOutpatientWaitersHashNotSeenReferrals': None,
    'ReportsOutpatientWaitersNotSeenReferrals': None,

    'UserAssesstfkcsa_childprev': 'type12_RowID',  # Keeping Children Safe Assessment subtable  # noqa
    'UserAssesstfkcsa_childs': 'type12_RowID',  # Keeping Children Safe Assessment subtable  # noqa
}

"""

RIO_6_2_ATYPICAL_PATIENT_ID_COLS = {
    'SNOMED_Client': 'SC_ClientID',
}
