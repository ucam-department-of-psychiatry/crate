#!/usr/bin/env python

r"""
crate_anon/nlp_manager/prepare_umls_for_bioyodie.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Prepare UMLS data for Bio-YODIE.**

- In a UMLS download file, e.g. ``umls-2017AA-full.zip``, the directory
  structure is:

  .. code-block:: none

    2017AA-full/
        2017aa-1-meta.nlm
        2017aa-2-meta.nlm
        2017aa-otherks.nlm
        2017AA.CHK
        2017AA.MD5
        Copyright_Notice.txt
        mmsys.zip
        README.txt

- This structure is not in Docker image ``wormtreat/metamap-2018``.
- What about ``aehrc/quickumls-rest``
  (https://hub.docker.com/r/aehrc/quickumls-rest)? No.

- So, preprocess it from a user-supplied UMLS download (we can't autodownload
  this).

Then, within the Bio-YODIE preprocessing program, it clearly expects:

  .. code-block:: none

    srcs/umls/2015AB/META/MRCOLS.RRF

and similar. However, those files appear not to be in ``umls-2017AA-full.zip``.
Nonetheless, they are apparently available as outputs from the MetamorphoSys
program (https://www.ncbi.nlm.nih.gov/books/NBK9685/;
https://www.ncbi.nlm.nih.gov/books/NBK9683/). Batch runs of MetamorphoSys are
described at
https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMetaMorphoSys.html.

"""  # noqa

import argparse
import logging
import sys
import os
from os.path import join
import shutil
import tempfile

from cardinal_pythonlib.fileops import mkdir_p, pushd
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.network import download

from crate_anon.common.sysops import check_call_verbose, die

log = logging.getLogger(__name__)

DEFAULT_JAVA_HOME = os.path.abspath(join(shutil.which("java"), os.pardir, os.pardir))


def get_default_java_home() -> str:
    """
    Returns a suitable default for the JAVA_HOME environment variable.
    """
    java = shutil.which("java")
    if not java:
        die("Can't find command: java")
    return os.path.abspath(join(shutil.which("java"), os.pardir, os.pardir))


def get_propfile_text(metadir: str) -> str:
    return """

# Configuration Properties File 

mmsys_output_stream=gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.remove_obsolete_data=false
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.confirm_selections=true
install_lvg=false
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.calculate_md5s=false
release_version=2017AA
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.subset_dir=/tmp/crate_tmp/blah/2017AA/META
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.suppressed_sabttys=ALT|AB;CCPSS|TC;CDT|OP;CPT|AB;FMA|AB;FMA|OP;GO|IS;GO|MTH_IS;GO|MTH_OET;GO|MTH_OP;GO|OET;GO|OP;HCDT|AB;HCDT|OA;HCDT|OP;HCPCS|AB;HCPCS|AM;HCPCS|OA;HCPCS|OAM;HCPCS|OM;HCPCS|OP;HCPT|AB;HCPT|AM;HCPT|OA;HCPT|OP;HL7V3.0|ONP;HL7V3.0|OP;HPO|IS;HPO|OET;HPO|OP;ICD10|HS;ICD10|PS;ICD10AE|HS;ICD10AE|PS;ICD10AM|PS;ICD10AMAE|PS;ICD10CM|AB;ICD10PCS|AB;ICD10PCS|HS;ICD9CM|AB;ICPC|CS;ICPC|PS;ICPC2EENG|AB;ICPC2P|MTH_OP;ICPC2P|MTH_OPN;ICPC2P|MTH_PT;ICPC2P|OP;ICPC2P|OPN;LNC|LO;LNC|MTH_LO;LNC|OLC;LNC|OOSN;LNC-DE-AT|LO;LNC-DE-CH|OOSN;LNC-DE-DE|LO;LNC-EL-GR|LO;LNC-ES-AR|LO;LNC-ES-AR|OOSN;LNC-ES-CH|OOSN;LNC-ES-ES|LO;LNC-ET-EE|LO;LNC-FR-BE|LO;LNC-FR-CA|LO;LNC-FR-CH|OOSN;LNC-FR-FR|LO;LNC-FR-FR|OLC;LNC-IT-CH|OOSN;LNC-IT-IT|LO;LNC-KO-KR|LO;LNC-NL-NL|LO;LNC-PT-BR|LO;LNC-PT-BR|OLC;LNC-PT-BR|OOSN;LNC-RU-RU|LO;LNC-TR-TR|LO;LNC-ZH-CN|LO;MDR|AB;MDR|MTH_OL;MDR|OL;MDRCZE|AB;MDRCZE|OL;MDRDUT|AB;MDRDUT|OL;MDRFRE|AB;MDRFRE|OL;MDRGER|AB;MDRGER|OL;MDRHUN|AB;MDRHUN|OL;MDRITA|AB;MDRITA|OL;MDRJPN|OL;MDRJPN|OLJKN;MDRJPN|OLJKN1;MDRPOR|AB;MDRPOR|OL;MDRSPA|AB;MDRSPA|OL;MSH|DEV;MSH|DSV;MSH|QAB;MSH|QEV;MSH|QSV;MSHGER|DSV;MSHNOR|DSV;MTHICPC2EAE|AB;NCBI|AUN;NCBI|UAUN;NCI|OP;NCI_NICHD|OP;NEU|ACR;NEU|IS;NEU|OP;PDQ|IS;PDQ|OP;RCD|AA;RCD|AB;RCD|AS;RCD|IS;RCD|OA;RCD|OP;RCDAE|AA;RCDAE|AB;RCDAE|IS;RCDAE|OA;RCDAE|OP;RCDSA|AB;RCDSA|IS;RCDSA|OA;RCDSA|OP;RCDSY|AB;RCDSY|IS;RCDSY|OA;RCDSY|OP;SCTSPA|IS;SCTSPA|MTH_IS;SCTSPA|MTH_OAF;SCTSPA|MTH_OAP;SCTSPA|MTH_OAS;SCTSPA|MTH_OF;SCTSPA|MTH_OP;SCTSPA|OAF;SCTSPA|OAP;SCTSPA|OAS;SCTSPA|OF;SCTSPA|OP;SNMI|HX;SNMI|PX;SNMI|SX;SNOMEDCT_US|IS;SNOMEDCT_US|MTH_IS;SNOMEDCT_US|MTH_OAF;SNOMEDCT_US|MTH_OAP;SNOMEDCT_US|MTH_OAS;SNOMEDCT_US|MTH_OF;SNOMEDCT_US|MTH_OP;SNOMEDCT_US|OAF;SNOMEDCT_US|OAP;SNOMEDCT_US|OAS;SNOMEDCT_US|OF;SNOMEDCT_US|OP;SNOMEDCT_VET|IS;SNOMEDCT_VET|OAF;SNOMEDCT_VET|OAP;SNOMEDCT_VET|OAS;SNOMEDCT_VET|OF;SNOMEDCT_VET|OP
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.remove_mth_only=false
install_net=true
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.build_indexes=true
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.remove_selected_sources=true
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.enforce_family_selection=true
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.add_unicode_bom=false
meta_destination_uri=/tmp/crate_tmp/blah/2017AA/META
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.ip_associations=
default_subset_config_uri=/tmp/crate_tmp/umls/config/2017AA/user.a.prop
versioned_output=false
install_umls=true
install_lex=true
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.database=
mmsys_input_stream=gov.nih.nlm.umls.mmsys.io.NLMFileMetamorphoSysInputStream
meta_source_uri=/tmp/crate_tmp/umls
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.base_url=http\://www.nlm.nih.gov/research/umls/sourcereleasedocs/
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.max_field_length=4000
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.versioned_output=false
install_meta=true
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.remove_editor_suppressible_data=false
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.remove_source_tty_suppressible_data=false
umls_destination_uri=/tmp/crate_tmp/blah
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.selected_sources=ALT|ALT;BI|BI;CCC|CCC;CCPSS|CCPSS;CDT|CDT;CPM|CPM;CPTSP|CPT;CPT|CPT;DDB|DDB;DMDICD10|ICD10;DMDUMD|UMD;DSM-5|DSM-5;GS|GS;HCDT|HCPCS;HCPT|CPT;HLREL|HLREL;ICD10AE|ICD10;ICD10AMAE|ICD10AM;ICD10AM|ICD10AM;ICD10CM|ICD10CM;ICD10DUT|ICD10;ICD10|ICD10;ICF-CY|ICF;ICF|ICF;ICNP|ICNP;ICPC2EDUT|ICPC2EENG;ICPC2EENG|ICPC2EENG;ICPC2ICD10DUT|ICPC2ICD10ENG;ICPC2ICD10ENG|ICPC2ICD10ENG;ICPC2P|ICPC2P;JABL|JABL;KCD5|KCD5;MDDB|MDDB;MDR|MDR;MDRCZE|MDR;MDRDUT|MDR;MDRFRE|MDR;MDRGER|MDR;MDRHUN|MDR;MDRITA|MDR;MDRJPN|MDR;MDRPOR|MDR;MDRSPA|MDR;MEDCIN|MEDCIN;MMSL|MMSL;MMX|MMX;MSHCZE|MSH;MSHDUT|MSH;MSHFIN|MSH;MSHFRE|MSH;MSHGER|MSH;MSHITA|MSH;MSHJPN|MSH;MSHLAV|MSH;MSHNOR|MSH;MSHPOL|MSH;MSHPOR|MSH;MSHRUS|MSH;MSHSCR|MSH;MSHSPA|MSH;MSHSWE|MSH;MTHICPC2EAE|ICPC2EENG;MTHICPC2ICD10AE|ICPC2ICD10ENG;NANDA-I|NANDA-I;NDDF|NDDF;NEU|NEU;NIC|NIC;NOC|NOC;NUCCPT|NUCCPT;OMS|OMS;PCDS|PCDS;PNDS|PNDS;PPAC|PPAC;PSY|PSY;RCD|RCD;RCDAE|RCD;RCDSA|RCD;RCDSY|RCD;SCTSPA|SNOMEDCT;SNM|SNM;SNMI|SNMI;SNOMEDCT_US|SNOMEDCT;SNOMEDCT_VET|SNOMEDCT;ULT|ULT;UMD|UMD;WHO|WHO;WHOFRE|WHO;WHOGER|WHO;WHOPOR|WHO;WHOSPA|WHO
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.truncate=false
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.character_encoding=UTF-8
active_filters=gov.nih.nlm.umls.mmsys.filter.SourceListFilter;gov.nih.nlm.umls.mmsys.filter.PrecedenceFilter;gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter
gov.nih.nlm.umls.mmsys.filter.PrecedenceFilter.precedence=MTH|PN;RXNORM|MIN;MSH|MH;MSH|TQ;MSH|PEP;MSH|ET;MSH|XQ;MSH|PXQ;MSH|NM;MTHCMSFRF|PT;RXNORM|SCD;RXNORM|SBD;RXNORM|SCDG;RXNORM|SBDG;RXNORM|IN;RXNORM|PSN;RXNORM|SCDF;RXNORM|SBDF;RXNORM|SCDC;RXNORM|DFG;RXNORM|DF;RXNORM|SBDC;RXNORM|BN;RXNORM|PIN;RXNORM|BPCK;RXNORM|GPCK;RXNORM|SY;RXNORM|TMSY;SNOMEDCT_US|PT;SNOMEDCT_US|FN;SNOMEDCT_US|SY;SNOMEDCT_US|PTGB;SNOMEDCT_US|SYGB;SNOMEDCT_US|MTH_PT;SNOMEDCT_US|MTH_FN;SNOMEDCT_US|MTH_SY;SNOMEDCT_US|MTH_PTGB;SNOMEDCT_US|MTH_SYGB;SNOMEDCT_US|SB;SNOMEDCT_US|XM;SNOMEDCT_VET|PT;SNOMEDCT_VET|FN;SNOMEDCT_VET|SY;SNOMEDCT_VET|SB;HPO|PT;HPO|SY;HPO|ET;HPO|OP;HPO|IS;HPO|OET;NCBI|SCN;MTHSPL|MTH_RXN_DP;MTHSPL|DP;MTHSPL|SU;ATC|RXN_PT;ATC|PT;VANDF|PT;VANDF|CD;VANDF|IN;MDDB|CD;USPMG|HC;USPMG|PT;MMX|MTH_RXN_CD;MMX|MTH_RXN_BD;MMX|CD;MMX|BD;DRUGBANK|IN;DRUGBANK|SY;DRUGBANK|FSY;MSH|N1;MSH|PCE;MSH|CE;CPM|PT;NEU|PT;NEU|ACR;NEU|SY;NEU|OP;NEU|IS;FMA|PT;FMA|SY;FMA|AB;FMA|OP;UWDA|PT;UWDA|SY;UMD|PT;UMD|SY;UMD|ET;UMD|RT;GS|CD;MMSL|CD;GS|MTH_RXN_BD;GS|BD;MMSL|MTH_RXN_BD;MMSL|BD;MMSL|SC;MMSL|MS;MMSL|GN;MMSL|BN;ATC|RXN_IN;ATC|IN;MMSL|IN;VANDF|AB;GS|MTH_RXN_CD;VANDF|MTH_RXN_CD;NDDF|MTH_RXN_CDC;NDDF|CDC;NDDF|CDD;NDDF|CDA;NDDF|IN;NDDF|DF;NDFRT|MTH_RXN_RHT;NDFRT|HT;NDFRT|FN;NDFRT|PT;NDFRT|SY;NDFRT|AB;SPN|PT;MDR|PT;MDR|MTH_PT;MDR|HG;MDR|MTH_HG;MDR|OS;MDR|MTH_OS;MDR|HT;MDR|MTH_HT;MDR|LLT;MDR|MTH_LLT;MDR|SMQ;MDR|MTH_SMQ;MDR|AB;CPT|PT;CPT|SY;CPT|ETCLIN;CPT|POS;CPT|GLP;CPT|ETCF;CPT|MP;HCPT|PT;HCPCS|PT;CDT|PT;CDT|OP;MVX|PT;CVX|PT;CVX|RXN_PT;CVX|AB;HCDT|PT;HCPCS|MP;HCPT|MP;ICD10AE|PT;ICD10|PT;ICD10AE|PX;ICD10|PX;ICD10AE|PS;ICD10|PS;ICD10AMAE|PT;ICD10AM|PT;ICD10AMAE|PX;ICD10AM|PX;ICD10AMAE|PS;ICD10AM|PS;OMIM|PT;OMIM|PHENO;OMIM|PHENO_ET;OMIM|PTAV;OMIM|PTCS;OMIM|ETAL;OMIM|ET;OMIM|HT;OMIM|ACR;MEDCIN|PT;MEDCIN|FN;MEDCIN|XM;MEDCIN|SY;HGNC|PT;HGNC|ACR;HGNC|MTH_ACR;HGNC|NA;HGNC|SYN;ICNP|PT;ICNP|MTH_PT;ICNP|XM;PNDS|PT;PNDS|HT;PDQ|PT;PDQ|HT;PDQ|PSC;PDQ|SY;PDQ|MTH_SY;CHV|PT;MEDLINEPLUS|PT;NCI|PT;NCI|SY;NCI_BioC|SY;NCI_PI-RADS|PT;NCI_CareLex|PT;NCI_CareLex|SY;NCI_CDC|PT;NCI_CDISC|PT;NCI_CDISC|SY;NCI|CSN;NCI_DCP|PT;NCI_DCP|SY;NCI|DN;NCI_DTP|PT;NCI_DTP|SY;NCI|FBD;NCI_FDA|AB;NCI_FDA|PT;NCI_FDA|SY;NCI|HD;NCI_GENC|PT;NCI_GENC|CA2;NCI_GENC|CA3;NCI_CRCH|PT;NCI_CRCH|SY;NCI_DICOM|PT;NCI_BRIDG|PT;NCI_RENI|DN;NCI_BioC|PT;NCI|CCN;NCI_CTCAE|PT;NCI_CTEP-SDC|PT;NCI_CTEP-SDC|SY;NCI|CCS;NCI_JAX|PT;NCI_JAX|SY;NCI_KEGG|PT;NCI_ICH|AB;NCI_ICH|PT;NCI_NCI-HL7|AB;NCI_NCI-HL7|PT;NCI_UCUM|AB;NCI_UCUM|PT;NCI_KEGG|AB;NCI_KEGG|SY;NCI_NICHD|PT;NCI_NICHD|SY;NCI_PID|PT;NCI_NCPDP|PT;NCI_GAIA|PT;NCI_GAIA|SY;NCI_ZFin|PT;NCI_NCI-GLOSS|PT;NCI_ICH|SY;NCI_NCI-HL7|SY;NCI_UCUM|SY;NCI_NCPDP|SY;NCI_ZFin|SY;NCI_NCI-GLOSS|SY;NCI|OP;NCI_NICHD|OP;NCI|AD;NCI|CA2;NCI|CA3;NCI|BN;NCI|AB;MTHICPC2EAE|PT;ICPC2EENG|PT;MTHICPC2ICD10AE|PT;SOP|PT;ICF|HT;ICF|PT;ICF|MTH_HT;ICF|MTH_PT;ICF-CY|HT;ICF-CY|PT;ICF-CY|MTH_HT;ICF-CY|MTH_PT;ICPC2ICD10ENG|PT;ICPC|PX;ICPC|PT;ICPC|PS;ICPC|PC;ICPC|CX;ICPC|CP;ICPC|CS;ICPC|CC;ICPC2EENG|CO;ICPC|CO;MTHICPC2EAE|AB;ICPC2EENG|AB;ICPC2P|PTN;ICPC2P|MTH_PTN;ICPC2P|PT;ICPC2P|MTH_PT;ICPC2P|OPN;ICPC2P|MTH_OPN;ICPC2P|OP;ICPC2P|MTH_OP;AOT|PT;AOT|ET;HCPCS|OP;HCDT|OP;HCPT|OP;HCPCS|OM;HCPCS|OAM;GO|PT;GO|MTH_PT;GO|ET;GO|MTH_ET;GO|SY;GO|MTH_SY;GO|OP;GO|MTH_OP;GO|OET;GO|MTH_OET;GO|IS;GO|MTH_IS;PDQ|ET;PDQ|CU;PDQ|MTH_LV;PDQ|LV;PDQ|MTH_AB;PDQ|MTH_ACR;PDQ|ACR;PDQ|AB;PDQ|BD;PDQ|FBD;PDQ|OP;PDQ|CCN;PDQ|CHN;PDQ|MTH_CHN;PDQ|IS;PDQ|MTH_BD;NCBI|USN;NCBI|USY;NCBI|SY;NCBI|UCN;NCBI|CMN;NCBI|UE;NCBI|EQ;NCBI|AUN;NCBI|UAUN;LNC|LN;LNC|MTH_LN;LNC|OSN;LNC|CN;LNC|MTH_CN;LNC|LPN;LNC|LPDN;LNC|HC;LNC|HS;LNC|OLC;LNC|LC;LNC|XM;LNC|LS;LNC|LO;LNC|MTH_LO;LNC|OOSN;LNC|LA;ICD10CM|PT;ICD9CM|PT;ICD10CM|XM;MDR|OL;MDR|MTH_OL;ICD10CM|HT;ICD9CM|HT;CCS_10|HT;CCS_10|MD;CCS_10|MV;CCS_10|SD;CCS_10|SP;CCS_10|XM;CCS|HT;CCS|MD;CCS|SD;CCS|MV;CCS|SP;CCS|XM;ICPC2ICD10ENG|XM;ICD10AE|HT;ICD10PCS|PT;ICD10PCS|PX;ICD10PCS|HX;ICD10PCS|MTH_HX;ICD10PCS|HT;ICD10PCS|XM;ICD10PCS|HS;ICD10PCS|AB;ICD10|HT;ICD10AE|HX;ICD10|HX;ICD10AE|HS;ICD10|HS;ICD10AMAE|HT;ICD10AM|HT;UMD|HT;ICPC|HT;NUCCPT|PT;HL7V3.0|CSY;HL7V3.0|PT;HL7V2.5|PT;HL7V3.0|CDO;HL7V3.0|VS;HL7V3.0|BR;HL7V3.0|CPR;HL7V3.0|CR;HL7V3.0|NPT;HL7V3.0|OP;HL7V3.0|ONP;HL7V2.5|HTN;CPT|HT;CDT|HT;MTHHH|HT;CCC|PT;CCC|HT;NIC|IV;NIC|HC;NANDA-I|PT;NANDA-I|HT;NANDA-I|HC;NANDA-I|RT;OMS|MTH_SI;OMS|PR;OMS|TG;OMS|HT;OMS|PQ;OMS|IVC;OMS|SI;OMS|SCALE;NIC|AC;NOC|OC;NOC|MTH_ID;NOC|ID;NIC|HT;NOC|HT;NOC|HC;CCC|MTH_HT;CCC|MP;ALT|PT;ALT|HT;MTH|CV;MTH|XM;MTH|PT;MTH|SY;MTH|RT;ICD10CM|ET;MTHICD9|ET;ICD10CM|AB;ICD9CM|AB;PSY|PT;PSY|HT;PSY|ET;MEDLINEPLUS|ET;MEDLINEPLUS|SY;MEDLINEPLUS|HT;LCH_NW|PT;LCH|PT;MSH|HT;MSH|HS;MSH|DEV;MSH|DSV;MSH|QAB;MSH|QEV;MSH|QSV;MSH|PM;LCH_NW|XM;CPT|AB;HCPT|AB;HCPCS|AB;WHO|PT;WHO|OS;WHO|HT;WHO|IT;SNMI|PT;SNMI|PX;SNMI|HT;SNMI|HX;SNMI|RT;SNMI|SY;SNMI|SX;SNMI|AD;SNM|PT;SNM|RT;SNM|HT;SNM|SY;SNM|RS;RCD|PT;RCD|OP;RCD|SY;RCD|IS;RCD|AT;RCD|AS;RCD|AB;RCDSA|PT;RCDSY|PT;RCDAE|PT;RCDSA|SY;RCDSY|SY;RCDAE|SY;RCDSA|OP;RCDSY|OP;RCDAE|OP;RCDSA|IS;RCDSY|IS;RCDAE|IS;RCDAE|AT;RCDSA|AB;RCDSY|AB;RCDAE|AB;RCDSA|OA;RCDSY|OA;RCDAE|OA;RCD|OA;RCDAE|AA;RCD|AA;CSP|PT;CSP|SY;CSP|ET;CSP|AB;MTH|DT;HCPT|OA;HCPT|AM;HCPCS|OA;HCPCS|AM;HCDT|AB;ALT|AB;HCDT|OA;CHV|SY;RXNORM|ET;SNOMEDCT_VET|OAP;SNOMEDCT_VET|OP;SNOMEDCT_US|OAP;SNOMEDCT_US|OP;SNOMEDCT_VET|OAF;SNOMEDCT_VET|OF;SNOMEDCT_US|OAF;SNOMEDCT_US|OF;SNOMEDCT_VET|OAS;SNOMEDCT_VET|IS;SNOMEDCT_US|OAS;SNOMEDCT_US|IS;SNOMEDCT_US|MTH_OAP;SNOMEDCT_US|MTH_OP;SNOMEDCT_US|MTH_OAF;SNOMEDCT_US|MTH_OF;SNOMEDCT_US|MTH_OAS;SNOMEDCT_US|MTH_IS;DSM-5|DC10;DSM-5|DC9;DXP|DI;DXP|FI;DXP|SY;RAM|PT;RAM|RT;ULT|PT;BI|PT;BI|AB;BI|SY;BI|RT;PCDS|GO;PCDS|OR;PCDS|PR;PCDS|CO;PCDS|HX;PCDS|HT;MTHMST|PT;MTHMST|SY;DDB|PT;DDB|SY;CST|PT;COSTAR|PT;CST|SC;CST|HT;CST|GT;CCPSS|TX;CCPSS|TC;CCPSS|PT;CCPSS|MP;AOD|DE;AOD|DS;AOD|XD;AOD|FN;AOD|ET;AOD|ES;AOD|EX;AOD|NP;AOD|NS;AOD|NX;QMR|PT;JABL|PC;JABL|PT;JABL|SS;JABL|SY;AIR|FI;AIR|DI;AIR|SY;AIR|HT;PPAC|DO;PPAC|CL;PPAC|AC;PPAC|ST;PPAC|TA;MCM|PT;MCM|RT;SCTSPA|PT;SCTSPA|FN;SCTSPA|SY;SCTSPA|MTH_PT;SCTSPA|MTH_FN;SCTSPA|MTH_SY;SCTSPA|SB;SCTSPA|OP;SCTSPA|OAF;SCTSPA|OAP;SCTSPA|OAS;SCTSPA|OF;SCTSPA|IS;SCTSPA|MTH_OP;SCTSPA|MTH_OAF;SCTSPA|MTH_OAP;SCTSPA|MTH_OAS;SCTSPA|MTH_OF;SCTSPA|MTH_IS;MSHPOR|MH;MSHPOR|PEP;MSHPOR|ET;MSHSPA|MH;MSHSPA|PEP;MSHSPA|ET;MSHCZE|MH;MSHCZE|PEP;MSHCZE|ET;MSHDUT|MH;MSHSWE|MH;MSHSWE|TQ;MSHNOR|MH;MSHGER|MH;MSHNOR|PEP;MSHGER|PEP;MSHNOR|DSV;MSHGER|DSV;MSHNOR|ET;MSHGER|ET;MSHFIN|MH;MSHLAV|MH;MSHSCR|MH;MSHFRE|MH;MSHLAV|PEP;MSHSCR|PEP;MSHFRE|PEP;MSHLAV|EP;MSHSCR|ET;MSHFRE|ET;MSHITA|MH;MSHITA|PEP;MSHITA|ET;MSHJPN|PT;MSHPOL|MH;MSHRUS|MH;MSHJPN|SY;KCD5|HT;TKMT|PT;KCD5|PT;MSHPOL|SY;MSHRUS|SY;MSHDUT|SY;MDRSPA|PT;MDRSPA|HG;MDRSPA|HT;MDRSPA|LLT;MDRSPA|OS;MDRSPA|SMQ;MDRSPA|OL;MDRSPA|AB;MDRDUT|PT;MDRDUT|HG;MDRDUT|HT;MDRDUT|LLT;MDRDUT|OS;MDRDUT|SMQ;MDRDUT|OL;MDRDUT|AB;MDRFRE|PT;MDRFRE|HG;MDRFRE|HT;MDRFRE|LLT;MDRFRE|SMQ;MDRFRE|OS;MDRFRE|OL;MDRFRE|AB;MDRGER|PT;MDRGER|HG;MDRGER|HT;MDRGER|LLT;MDRGER|SMQ;MDRGER|OS;MDRGER|OL;MDRGER|AB;MDRITA|PT;MDRITA|HG;MDRITA|HT;MDRITA|LLT;MDRITA|SMQ;MDRITA|OS;MDRITA|OL;MDRITA|AB;MDRJPN|PT;MDRJPN|PTJKN;MDRJPN|PTJKN1;MDRJPN|HG;MDRJPN|HGJKN;MDRJPN|HGJKN1;MDRJPN|HT;MDRJPN|HTJKN;MDRJPN|HTJKN1;MDRJPN|LLT;MDRJPN|LLTJKN;MDRJPN|LLTJKN1;MDRJPN|OS;MDRJPN|SMQ;MDRJPN|OL;MDRJPN|OLJKN;MDRJPN|OLJKN1;MDRCZE|PT;MDRHUN|PT;MDRPOR|PT;MDRCZE|HG;MDRHUN|HG;MDRPOR|HG;MDRCZE|HT;MDRHUN|HT;MDRPOR|HT;MDRCZE|LLT;MDRHUN|LLT;MDRPOR|LLT;MDRCZE|OS;MDRHUN|OS;MDRPOR|OS;MDRCZE|SMQ;MDRHUN|SMQ;MDRPOR|SMQ;MDRCZE|OL;MDRHUN|OL;MDRPOR|OL;MDRCZE|AB;MDRHUN|AB;MDRPOR|AB;MDRJPN|OSJKN;MDRJPN|OSJKN1;WHOFRE|HT;WHOGER|HT;WHOPOR|HT;WHOSPA|HT;LNC-DE-CH|OSN;LNC-DE-CH|OOSN;LNC-DE-DE|LN;LNC-DE-DE|LO;LNC-EL-GR|LN;LNC-EL-GR|LO;LNC-ES-AR|LN;LNC-ES-AR|OSN;LNC-ES-AR|LO;LNC-ES-AR|OOSN;LNC-ES-CH|OSN;LNC-ES-CH|OOSN;LNC-ES-ES|LN;LNC-ES-ES|LO;LNC-ET-EE|LN;LNC-ET-EE|LO;LNC-FR-BE|LN;LNC-FR-BE|LO;LNC-FR-CA|LN;LNC-FR-CA|LO;LNC-FR-CH|OSN;LNC-FR-CH|OOSN;LNC-FR-FR|LN;LNC-FR-FR|LC;LNC-FR-FR|OLC;LNC-FR-FR|LO;LNC-IT-CH|OSN;LNC-IT-CH|OOSN;LNC-IT-IT|LN;LNC-IT-IT|LO;LNC-KO-KR|LN;LNC-KO-KR|LO;LNC-NL-NL|LN;LNC-NL-NL|LO;LNC-PT-BR|LN;LNC-PT-BR|OSN;LNC-PT-BR|LC;LNC-PT-BR|OLC;LNC-PT-BR|LO;LNC-PT-BR|OOSN;LNC-RU-RU|LN;LNC-RU-RU|LO;LNC-TR-TR|LN;LNC-TR-TR|LO;LNC-ZH-CN|LN;LNC-ZH-CN|LO;LNC-DE-AT|LN;LNC-DE-AT|LO;WHOFRE|PT;WHOGER|PT;WHOPOR|PT;WHOSPA|PT;WHOFRE|IT;WHOGER|IT;WHOPOR|IT;WHOSPA|IT;WHOFRE|OS;WHOGER|OS;WHOPOR|OS;WHOSPA|OS;CPTSP|PT;DMDUMD|PT;DMDUMD|ET;DMDUMD|RT;DMDICD10|PT;DMDICD10|HT;ICPCBAQ|PT;ICPCDAN|PT;ICPC2EDUT|PT;ICD10DUT|PT;ICD10DUT|HT;ICPC2ICD10DUT|PT;ICPCDUT|PT;ICPCFIN|PT;ICPCFRE|PT;ICPCGER|PT;ICPCHEB|PT;ICPCHUN|PT;ICPCITA|PT;ICPCNOR|PT;ICPCPOR|PT;ICPCSPA|PT;ICPCSWE|PT;ICPCBAQ|CP;ICPCDAN|CP;ICPCDUT|CP;ICPCFIN|CP;ICPCFRE|CP;ICPCGER|CP;ICPCHEB|CP;ICPCHUN|CP;ICPCITA|CP;ICPCNOR|CP;ICPCPOR|CP;ICPCSPA|CP;ICPCSWE|CP;MTHMSTFRE|PT;MTHMSTITA|PT;SRC|RPT;SRC|RHT;SRC|RAB;SRC|RSY;SRC|VPT;SRC|VAB;SRC|VSY;SRC|SSN;
gov.nih.nlm.umls.mmsys.io.NLMFileMetamorphoSysInputStream.meta_source_uri=/tmp/crate_tmp/umls
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.confirm_default_suppressible_sabttys=HPO|OP;HPO|IS;HPO|OET;NEU|ACR;NEU|OP;NEU|IS;FMA|AB;FMA|OP;MDR|AB;CDT|OP;ICD10AE|PS;ICD10|PS;ICD10AMAE|PS;ICD10AM|PS;NCI|OP;NCI_NICHD|OP;ICPC|PS;ICPC|CS;MTHICPC2EAE|AB;ICPC2EENG|AB;ICPC2P|MTH_PT;ICPC2P|OPN;ICPC2P|MTH_OPN;ICPC2P|OP;ICPC2P|MTH_OP;HCPCS|OP;HCDT|OP;HCPT|OP;HCPCS|OM;HCPCS|OAM;GO|OP;GO|MTH_OP;GO|OET;GO|MTH_OET;GO|IS;GO|MTH_IS;PDQ|OP;PDQ|IS;NCBI|AUN;NCBI|UAUN;LNC|OLC;LNC|LO;LNC|MTH_LO;LNC|OOSN;MDR|OL;MDR|MTH_OL;ICD10PCS|HS;ICD10PCS|AB;ICD10AE|HS;ICD10|HS;HL7V3.0|OP;HL7V3.0|ONP;ICD10CM|AB;ICD9CM|AB;MSH|DEV;MSH|DSV;MSH|QAB;MSH|QEV;MSH|QSV;CPT|AB;HCPT|AB;HCPCS|AB;SNMI|PX;SNMI|HX;SNMI|SX;RCD|OP;RCD|IS;RCD|AS;RCD|AB;RCDSA|OP;RCDSY|OP;RCDAE|OP;RCDSA|IS;RCDSY|IS;RCDAE|IS;RCDSA|AB;RCDSY|AB;RCDAE|AB;RCDSA|OA;RCDSY|OA;RCDAE|OA;RCD|OA;RCDAE|AA;RCD|AA;HCPT|OA;HCPT|AM;HCPCS|OA;HCPCS|AM;HCDT|AB;ALT|AB;HCDT|OA;SNOMEDCT_VET|OAP;SNOMEDCT_VET|OP;SNOMEDCT_US|OAP;SNOMEDCT_US|OP;SNOMEDCT_VET|OAF;SNOMEDCT_VET|OF;SNOMEDCT_US|OAF;SNOMEDCT_US|OF;SNOMEDCT_VET|OAS;SNOMEDCT_VET|IS;SNOMEDCT_US|OAS;SNOMEDCT_US|IS;SNOMEDCT_US|MTH_OAP;SNOMEDCT_US|MTH_OP;SNOMEDCT_US|MTH_OAF;SNOMEDCT_US|MTH_OF;SNOMEDCT_US|MTH_OAS;SNOMEDCT_US|MTH_IS;CCPSS|TC;SCTSPA|OP;SCTSPA|OAF;SCTSPA|OAP;SCTSPA|OAS;SCTSPA|OF;SCTSPA|IS;SCTSPA|MTH_OP;SCTSPA|MTH_OAF;SCTSPA|MTH_OAP;SCTSPA|MTH_OAS;SCTSPA|MTH_OF;SCTSPA|MTH_IS;MSHNOR|DSV;MSHGER|DSV;MDRSPA|OL;MDRSPA|AB;MDRDUT|OL;MDRDUT|AB;MDRFRE|OL;MDRFRE|AB;MDRGER|OL;MDRGER|AB;MDRITA|OL;MDRITA|AB;MDRJPN|OL;MDRJPN|OLJKN;MDRJPN|OLJKN1;MDRCZE|OL;MDRHUN|OL;MDRPOR|OL;MDRCZE|AB;MDRHUN|AB;MDRPOR|AB;LNC-DE-CH|OOSN;LNC-DE-DE|LO;LNC-EL-GR|LO;LNC-ES-AR|LO;LNC-ES-AR|OOSN;LNC-ES-CH|OOSN;LNC-ES-ES|LO;LNC-ET-EE|LO;LNC-FR-BE|LO;LNC-FR-CA|LO;LNC-FR-CH|OOSN;LNC-FR-FR|OLC;LNC-FR-FR|LO;LNC-IT-CH|OOSN;LNC-IT-IT|LO;LNC-KO-KR|LO;LNC-NL-NL|LO;LNC-PT-BR|OLC;LNC-PT-BR|LO;LNC-PT-BR|OOSN;LNC-RU-RU|LO;LNC-TR-TR|LO;LNC-ZH-CN|LO;LNC-DE-AT|LO
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.enforce_dep_source_selection=true

"""  # noqa


def prepare_umls_for_bioyodie(umls_zip: str,
                              dest_dir: str,
                              tmp_dir: str,
                              java_home: str = None) -> None:
    """
    Prepare downloaded UMLS data for Bio-YODIE, according to the instructions
    at https://github.com/GateNLP/bio-yodie-resource-prep.

    Args:
        umls_zip: ZIP file of UMLS data
        dest_dir: output directory
        tmp_dir: temporary directory to use
        java_home: value for JAVA_HOME environment variable
    """
    # URLs
    repo_url = "https://github.com/GateNLP/bio-yodie-resource-prep"
    scala_url = "https://downloads.lightbend.com/scala/2.11.7/scala-2.11.7.tgz"

    # Directories
    repo_dir = join(tmp_dir, "bio-yodie-resource-prep")
    db_dir = join(repo_dir, "databases")
    output_dir = join(repo_dir, "output")
    scala_dir = join(repo_dir, "scala")
    tmpdata_dir = join(repo_dir, "tmpdata")
    umls_unzipped_dir = join(repo_dir, "umls_unzipped")
    umls_to_tool_dir = join(repo_dir, "srcs", "umls", "2015AB")  # hardcoded

    # Files
    scala_tgz = join(scala_dir, "scala.tgz")
    builder_script = join(repo_dir, "bin", "all.sh")
    mmsys_zip = join(umls_unzipped_dir, "mmsys.zip")

    # Checks
    if os.path.exists(dest_dir):
        die(f"Directory already exists: {dest_dir}")

    # Environment variables
    os.environ["JAVA_HOME"] = java_home or get_default_java_home()

    # Actions
    log.info("Cloning repository...")
    check_call_verbose(["git", "clone", repo_url, repo_dir])

    log.info("Making directories...")
    mkdir_p(db_dir)
    mkdir_p(output_dir)
    mkdir_p(scala_dir)
    mkdir_p(tmpdata_dir)
    mkdir_p(umls_to_tool_dir)
    mkdir_p(dest_dir)

    log.info("Fetching/building Scala...")
    download(scala_url, scala_tgz)
    with pushd(scala_dir):
        check_call_verbose(["tar", "-xzvf", scala_tgz])
        check_call_verbose(["ant"])

    log.info("Unzipping UMLS data...")
    check_call_verbose(["unzip", "-j", umls_zip, "-d", umls_unzipped_dir])
    # -j: junk paths (extract "flat" into the specified directory)

    log.info("Unzipping UMLS MetamorphoSys program...")
    check_call_verbose(["unzip", mmsys_zip, "-d", umls_unzipped_dir])
    # "To ensure proper functionality users must unzip mmsys.zip to the same
    # directory as the other downloaded files."
    # -- https://www.ncbi.nlm.nih.gov/books/NBK9683/

    log.info("Running MetamorphoSys in batch mode...")
    # https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMetaMorphoSys.html  # noqa
    metadir = umls_unzipped_dir
    mm_destdir = join(metadir, "METASUBSET")
    mmsys_home = metadir
    classpath = ":".join([mmsys_home, join(mmsys_home, "lib", "jpf-boot.jar")])
    config_file = join(metadir, "config.properties")
    with open(config_file, "wt") as cf:
        cf.write(get_propfile_text(
            XXX
        ))
    with pushd(mmsys_home):
        check_call_verbose([
            join(java_home, "bin", "java"),
            "-classpath", classpath,
            "-Djava.awt.headless=true",
            f"-Djpf.boot.config={mmsys_home}/etc/subset.boot.properties",
            f"-Dlog4j.configuration={mmsys_home}/etc/subset.log4j.properties",
            f"-Dinput.uri={metadir}",
            f"-Doutput.uri={mm_destdir}",
            f"-Dmmsys.config.uri={config_file}",
            "-Xms300M",
            "-Xmx1000M",
            "org.java.plugin.boot.Boot"
        ])

    log.info("Converting UMLS data to Bio-YODIE format...")
    with pushd(repo_dir):
        check_call_verbose([builder_script])

    log.info(f"Copying Bio-YODIE data to destination directory: {dest_dir}")
    for f in os.listdir(output_dir):
        shutil.move(join(output_dir, f), dest_dir)


def prepare_umls_for_bioyodie_meta(umls_zip: str,
                                   dest_dir: str,
                                   keep_temp_dir: bool = False,
                                   java_home: str = None) -> None:
    """
    See :func:`prepare_umls_for_bioyodie`.

    Args:
        umls_zip: ZIP file of UMLS data
        dest_dir: output directory
        keep_temp_dir: preserve temporary directory (for debugging)
        java_home: value for JAVA_HOME environment variable
    """
    if keep_temp_dir:
        tmp_dir = tempfile.mkdtemp()
    else:
        tmp_dir_obj = tempfile.TemporaryDirectory()
        tmp_dir = tmp_dir_obj.name

    prepare_umls_for_bioyodie(umls_zip=umls_zip,
                              dest_dir=dest_dir,
                              tmp_dir=tmp_dir,
                              java_home=java_home)
    if keep_temp_dir:
        log.warning(f"Residual files are in {tmp_dir}")
    else:
        log.info("Cleaning up on exit...")


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Prepare UMLS data for BioYodie.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "umls_zip",
        help="Filename of ZIP file downloaded from "
             "https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html, "  # noqa
             "e.g. /path/to/umls-2017AA-full.zip . This can't be "
             "autodownloaded, as it requires a license/login."
    )
    parser.add_argument(
        "dest_dir",
        help="Destination directory to write."
    )
    parser.add_argument(
        "--keeptemp", action="store_true",
        help="Keep temporary directory on exit."
    )
    parser.add_argument(
        "--java_home",
        help="Value for JAVA_HOME environment variable.",
        default=get_default_java_home()
    )

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    prepare_umls_for_bioyodie_meta(umls_zip=args.umls_zip,
                                   dest_dir=args.dest_dir,
                                   keep_temp_dir=args.keeptemp,
                                   java_home=args.java_home)
    log.info("Done.")
    sys.exit(0)


if __name__ == "__main__":
    main()
