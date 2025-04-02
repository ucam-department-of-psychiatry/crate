#!/usr/bin/env python

r"""
crate_anon/nlp_manager/prepare_umls_for_bioyodie.py

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

**Prepare UMLS data for Bio-YODIE.**

In a UMLS download file, e.g. ``umls-2017AA-full.zip`` (4.5 GB), the directory
structure is:

  .. code-block:: none

    2017AA-full/                -- 4.5 GB total
        2017aa-1-meta.nlm       -- 1.6 GB
        2017aa-2-meta.nlm       -- 1.5 GB
        2017aa-otherks.nlm      -- 1.2 GB
        2017AA.CHK
        2017AA.MD5
        Copyright_Notice.txt
        mmsys.zip               -- 250 MB compressed, 611 MB uncompressed
        README.txt

- This structure is not in Docker image ``wormtreat/metamap-2018``.
- What about ``aehrc/quickumls-rest``
  (https://hub.docker.com/r/aehrc/quickumls-rest)? No.
- So, preprocess it from a user-supplied UMLS download (we can't autodownload
  this).

Then, the Bio-YODIE preprocessing program expects:

  .. code-block:: none

    srcs/umls/2015AB/META/
        MRCOLS.RRF
        MRCONSO.RRF
        ...

and similar. However, those files appear not to be in ``umls-2017AA-full.zip``.
Nonetheless, they are apparently available as outputs from the MetamorphoSys
program (https://www.ncbi.nlm.nih.gov/books/NBK9685/;
https://www.ncbi.nlm.nih.gov/books/NBK9683/). Batch runs of MetamorphoSys are
described at
https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMetaMorphoSys.html.
That's what we'll do.

MetamorphoSys produces output like:

  .. code-block:: none

    /some/dir               -- specified by "-Doutput.uri=..."; total ~17 GB
        CHANGE/
            DELETEDCUI.RRF
            ...
        indexes/
            AUI_MRCONSO.x
            ...
        mmsys.log
        AMBIGLUI.RRF
        ...
        MRCOLS.RRF
        MRHIER.RRF          -- 2.7 GB
        ...
        MRREL.RRF           -- 4.1 GB
        ...
        MRSAT.RRF           -- 4.2 GB
        ...
        release.dat

The Bio-YODIE preprocessor (a) was very slow, and (b) got itself killed by the
OS for using 36 GB of memory (on a 16 GB machine). See notes below (in the
source code). Fixed via some tweaks.

It creates a database (``umls.h2.db``) in ``databases/``, of ~33 GB. It then
moves things around. Final output from the Bio-YODIE preprocessor:

  .. code-block:: none

    databases/
        umls.h2.db                  -- 40 GB
        umls.trace.db
    output/
        databases/                  -- empty
        en/
            gazetteer-en-bio/
                cased-labels.def
                cased-labels.lst
                labels.lst
                uncased-labels.def
                uncased-labels.lst  -- 117 MB
            databases/
                labelinfo.h2.db     -- 1.8 GB
                labelinfo.trace.db

"""

import argparse
import logging
import sys
import os
from os.path import join
import shutil
import tempfile
from typing import Dict, List, NoReturn

from cardinal_pythonlib.fileops import mkdir_p, pushd
from cardinal_pythonlib.file_io import write_text
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.network import download
from cardinal_pythonlib.subproc import check_call_verbose
from cardinal_pythonlib.sysops import die
import regex
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.common.constants import (
    EnvVar,
    EXIT_SUCCESS,
)

_ = r"""

===============================================================================
My launch command:
===============================================================================

    crate_nlp_prepare_ymls_for_bioyodie \
        /rudolf_overflow/umls-2017AA-full.zip \
        /rudolf_overflow/umls_processed_for_bioyodie \
        --keeptemp


===============================================================================
Workflow for altering BioYODIE preprocessor code
===============================================================================

From the work directory containing "umls_output":

    # rm -rf bio-yodie-resource-prep
    git clone https://github.com/RudolfCardinal/bio-yodie-resource-prep
    cd bio-yodie-resource-prep
    mkdir databases
    mkdir tmpdata
    mkdir -p srcs/umls/2015AB
    mkdir output
    ln -s "${PWD}/../umls_output" srcs/umls/2015AB/META  # must use full path
    wget https://downloads.lightbend.com/scala/2.11.7/scala-2.11.7.tgz -O scala.tgz
    cd scala
    tar -xzvf ../scala.tgz
    ant
    cd ..

    bin/all.sh


===============================================================================
General notes
===============================================================================

- Note that the instructions seem out of date.
- There is source code distributed with ``mmsys`` (for the more cryptic error
  messages...).
- Tracing back:

  - ``Unexpected problem with mmsys.config.uri`` comes from
    ``plugins/gov.nih.nlm.umls.mmsys.subset/src/gov/nih/nlm/umls/mmsys/subset/SubsetPlugin.java``.
  - That does

    .. code-block:: java

        // ...
        import gov.nih.nlm.umls.mmsys.config.PropertyFileSubsetConfiguration;
        import gov.nih.nlm.umls.mmsys.config.SubsetConfiguration;
        // ...

        public final class SubsetPlugin extends ApplicationPlugin implements
                Application, ErrorHandler, RunnableListener {
            // ...
            private SubsetConfiguration subsetConfig = null;
            // ...

            protected Application initApplication(final ExtendedProperties config,
                    final String[] args) throws Exception {
                subsetConfig = new PropertyFileSubsetConfiguration();
                // ...
                String s = null;

                if ((s = System.getProperty("mmsys.config.uri")) != null) {
                    subsetConfig.open(s);
                } else {
                    throw new Exception("mmsys.config.uri property is required.");
                }

            }

            public void startApplication() {
                // ...

                    MetamorphoSysInputStream in = subsetConfig.getInputStream();
                    // This happens if something went wrong initializing the config file
                    if (in == null) {
                        throw new IOException("Unexpected problem with mmsys.config.uri");
                    }

                // ...
            }

        // ...
        }

  - Via
    ``plugins/gov.nih.nlm.umls.mmsys/src/gov/nih/nlm/umls/mmsys/config/PropertyFileSubsetConfiguration.java``:

    .. code-block:: java

        public class PropertyFileSubsetConfiguration extends
                AbstractPropertyFileConfiguration implements SubsetConfiguration {

            // ...
            private MetamorphoSysInputStream inputStream;
            // ...

            @Override
            public void loadProperties(Properties props) throws IOException {
                clearLoadWarnings();

                // Load the source paths
                if (props.containsKey("meta_source_uri")) {
                    setMetaSourceUri(props.getProperty("meta_source_uri"));
                } else {
                    setMetaSourceUri(null);
                }

                // ...

                if (props.containsKey("mmsys_input_stream")) {
                    String inputStreamName = props.getProperty("mmsys_input_stream");
                    // ... do useful stuff...
                    // ... including:
                        Class<?> InputStreamCls = classLoader.loadClass(inputStreamName);
                        setInputStream((MetamorphoSysInputStream) InputStreamCls
                                       .newInstance());
                } else {
                    setInputStream(null);
                }

            }

            @Override
            public MetamorphoSysInputStream getInputStream() {
                return inputStream;
            }

            // ...
        }

  - Via
    ``plugins/gov.nih.nlm.umls.mmsys/src/gov/nih/nlm/umls/mmsys/config/SubsetConfiguration.java``:

    - ``open()`` is a method here, but doesn't do much itself.

  - ``mmsys_input_stream=NLMFileMetamorphoSysInputStream``, so via
    ``plugins/gov.nih.nlm.umls.mmsys.io/src/gov/nih/nlm/umls/mmsys/io/NLMFileMetamorphoSysInputStream.java``:

Anything else useful at
https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMRCXTBuilder.html?

No. Anyway, we've got it working now.


===============================================================================
Out-of-memory problems whilst using DB.
===============================================================================

It's certainly possible for the Bio-YODIE preprocessor to run out of memory and
be killed. You may see ``Killed`` in the output, and if you use ``grep Kill
/var/log/syslog`` you may see output like:

  .. code-block:: none

    Sep 14 23:53:29 wombat kernel: [1316643.026824] oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=39077a0e645869e60c0eee667085a0381cd8e207c9cacd398dae6878335f36ac,mems_allowed=0,global_oom,task_memcg=/user.slice/user-1000.slice/user@1000.service,task=java,pid=1476208,uid=1000
    Sep 14 23:53:29 wombat kernel: [1316643.026902] Out of memory: Killed process 1476208 (java) total-vm:36432500kB, anon-rss:14884116kB, file-rss:0kB, shmem-rss:0kB, UID:1000 pgtables:50500kB oom_score_adj:0
    Sep 14 23:53:29 wombat kernel: [1316644.078094] oom_reaper: reaped process 1476208 (java), now anon-rss:0kB, file-rss:0kB, shmem-rss:0kB

So that's a process being killed when attempting to use 36 GB of memory. The
corresponding output from the main process was:

  .. code-block:: none

    INSERT INTO MRSAT SELECT * FROM CSVREAD(
    '/tmp/tmp_njjv8sg/bio-yodie-resource-prep/srcs/umls/2015AB/META/MRSAT.RRF',
    null,
    'charset=UTF-8 fieldSeparator=| escape= fieldDelimiter= ');
    /tmp/tmp_njjv8sg/bio-yodie-resource-prep/bin/runScala.sh: line 90: 1476208 Killed                  $JAVA_HOME/bin/java $JAVA_OPTS -Dfile.encoding=UTF-8 -Dconfig=$CONFIGFILE -cp "$SCALADIR"/lib/'*':$SCALADIR/prepare-scala.jar:\${GATE_HOME}/bin/gate.jar:${GATE_HOME}/lib/'*':${SCALA_HOME}/lib/'*' $class "$@"
    Finished loading tables ... Mon 14 Sep 23:53:31 BST 2020
    Create indexes ... Mon 14 Sep 23:53:31 BST 2020
    Exception in thread "main" org.h2.jdbc.JdbcSQLException: General error: "java.lang.NullPointerException" [50000-193]
        at org.h2.message.DbException.getJdbcSQLException(DbException.java:345)


E.g. 36 GB...

The scripts, e.g. bin/*.sh, use commands like

    $ROOTDIR/bin/runScala.sh ExecuteSql DATABASE_FILE SQL_FILE
                             ^^^^^^^^^^
                             class; see runScala.sh

That's using scala/classes/ExecuteSql.class.
That's from
https://github.com/GateNLP/bio-yodie-resource-prep/tree/master/scala/classes,
not from Scala itself. And therefore from
https://github.com/GateNLP/bio-yodie-resource-prep/blob/master/scala/src/main/scala/ExecuteSql.scala.

See tweaks in a forked version at
https://github.com/RudolfCardinal/bio-yodie-resource-prep, primarily:

- more efficient SQL for creating databases;
- set JVM limit to 10 GB (meaning it uses 13.9 GB) rather than 30 GB (making
  it thrash, use 36 GB, and get killed).

"""  # noqa: E501

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_JAVA_HOME = os.path.abspath(
    join(shutil.which("java"), os.pardir, os.pardir)
)
KVP_REGEX = regex.compile(r"^\s*(\S+)\s*=\s*(\S+)\s*$")

LOG4J_PROPERTIES_TEXT = """
# Minimal log4j config file. See https://gist.github.com/kdabir/2036771

log4j.rootLogger=ALL, CONSOLE
# ... level, logger name
# ... levels are: OFF, FATAL, ERROR, WARN, INFO, DEBUG, TRACE, ALL

# CONSOLE is set to be a ConsoleAppender using a PatternLayout
log4j.appender.CONSOLE=org.apache.log4j.ConsoleAppender
log4j.appender.CONSOLE.layout=org.apache.log4j.PatternLayout
log4j.appender.CONSOLE.layout.ConversionPattern=[%-5p] %m%n

# a more detailed PatternLayout: %d [%t] %-5p %c - %m%n
"""

# When the MMSYS GUI was told to install:
# - FROM /tmp/tmpg1z_uldg/umls_unzipped
# - TO   /tmp/tmpg1z_uldg/blah
# and using "include" rather than "exclude" mode, we got this:
_NOTES_WORKING_CONFIG_FROM_GUI = r"""
# Configuration Properties File
#Mon Sep 14 17:45:02 BST 2020
mmsys_output_stream=gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.remove_obsolete_data=false
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.confirm_selections=true
install_lvg=false
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.calculate_md5s=false
release_version=2017AA
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.subset_dir=/tmp/tmpg1z_uldg/blah/2017AA/META
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.suppressed_sabttys=ALT|AB;CCPSS|TC;CDT|OP;CPT|AB;FMA|AB;FMA|OP;GO|IS;GO|MTH_IS;GO|MTH_OET;GO|MTH_OP;GO|OET;GO|OP;HCDT|AB;HCDT|OA;HCDT|OP;HCPCS|AB;HCPCS|AM;HCPCS|OA;HCPCS|OAM;HCPCS|OM;HCPCS|OP;HCPT|AB;HCPT|AM;HCPT|OA;HCPT|OP;HL7V3.0|ONP;HL7V3.0|OP;HPO|IS;HPO|OET;HPO|OP;ICD10|HS;ICD10|PS;ICD10AE|HS;ICD10AE|PS;ICD10AM|PS;ICD10AMAE|PS;ICD10CM|AB;ICD10PCS|AB;ICD10PCS|HS;ICD9CM|AB;ICPC|CS;ICPC|PS;ICPC2EENG|AB;ICPC2P|MTH_OP;ICPC2P|MTH_OPN;ICPC2P|MTH_PT;ICPC2P|OP;ICPC2P|OPN;LNC|LO;LNC|MTH_LO;LNC|OLC;LNC|OOSN;LNC-DE-AT|LO;LNC-DE-CH|OOSN;LNC-DE-DE|LO;LNC-EL-GR|LO;LNC-ES-AR|LO;LNC-ES-AR|OOSN;LNC-ES-CH|OOSN;LNC-ES-ES|LO;LNC-ET-EE|LO;LNC-FR-BE|LO;LNC-FR-CA|LO;LNC-FR-CH|OOSN;LNC-FR-FR|LO;LNC-FR-FR|OLC;LNC-IT-CH|OOSN;LNC-IT-IT|LO;LNC-KO-KR|LO;LNC-NL-NL|LO;LNC-PT-BR|LO;LNC-PT-BR|OLC;LNC-PT-BR|OOSN;LNC-RU-RU|LO;LNC-TR-TR|LO;LNC-ZH-CN|LO;MDR|AB;MDR|MTH_OL;MDR|OL;MDRCZE|AB;MDRCZE|OL;MDRDUT|AB;MDRDUT|OL;MDRFRE|AB;MDRFRE|OL;MDRGER|AB;MDRGER|OL;MDRHUN|AB;MDRHUN|OL;MDRITA|AB;MDRITA|OL;MDRJPN|OL;MDRJPN|OLJKN;MDRJPN|OLJKN1;MDRPOR|AB;MDRPOR|OL;MDRSPA|AB;MDRSPA|OL;MSH|DEV;MSH|DSV;MSH|QAB;MSH|QEV;MSH|QSV;MSHGER|DSV;MSHNOR|DSV;MTHICPC2EAE|AB;NCBI|AUN;NCBI|UAUN;NCI|OP;NCI_NICHD|OP;NEU|ACR;NEU|IS;NEU|OP;PDQ|IS;PDQ|OP;RCD|AA;RCD|AB;RCD|AS;RCD|IS;RCD|OA;RCD|OP;RCDAE|AA;RCDAE|AB;RCDAE|IS;RCDAE|OA;RCDAE|OP;RCDSA|AB;RCDSA|IS;RCDSA|OA;RCDSA|OP;RCDSY|AB;RCDSY|IS;RCDSY|OA;RCDSY|OP;SCTSPA|IS;SCTSPA|MTH_IS;SCTSPA|MTH_OAF;SCTSPA|MTH_OAP;SCTSPA|MTH_OAS;SCTSPA|MTH_OF;SCTSPA|MTH_OP;SCTSPA|OAF;SCTSPA|OAP;SCTSPA|OAS;SCTSPA|OF;SCTSPA|OP;SNMI|HX;SNMI|PX;SNMI|SX;SNOMEDCT_US|IS;SNOMEDCT_US|MTH_IS;SNOMEDCT_US|MTH_OAF;SNOMEDCT_US|MTH_OAP;SNOMEDCT_US|MTH_OAS;SNOMEDCT_US|MTH_OF;SNOMEDCT_US|MTH_OP;SNOMEDCT_US|OAF;SNOMEDCT_US|OAP;SNOMEDCT_US|OAS;SNOMEDCT_US|OF;SNOMEDCT_US|OP;SNOMEDCT_VET|IS;SNOMEDCT_VET|OAF;SNOMEDCT_VET|OAP;SNOMEDCT_VET|OAS;SNOMEDCT_VET|OF;SNOMEDCT_VET|OP
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.remove_mth_only=false
install_net=true
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.build_indexes=true
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.remove_selected_sources=false
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.enforce_family_selection=true
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.add_unicode_bom=false
meta_destination_uri=/tmp/tmpg1z_uldg/blah/2017AA/META
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.ip_associations=
default_subset_config_uri=/tmp/tmpg1z_uldg/umls_unzipped/config/2017AA/user.a.prop
versioned_output=false
install_umls=true
install_lex=true
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.database=
mmsys_input_stream=gov.nih.nlm.umls.mmsys.io.NLMFileMetamorphoSysInputStream
meta_source_uri=/tmp/tmpg1z_uldg/umls_unzipped
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.base_url=http\://www.nlm.nih.gov/research/umls/sourcereleasedocs/
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.max_field_length=4000
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.versioned_output=false
install_meta=true
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.remove_editor_suppressible_data=false
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.remove_source_tty_suppressible_data=false
umls_destination_uri=/tmp/tmpg1z_uldg/blah
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.selected_sources=ALT|ALT;BI|BI;CCC|CCC;CCPSS|CCPSS;CDT|CDT;CPM|CPM;CPTSP|CPT;CPT|CPT;DDB|DDB;DMDICD10|ICD10;DMDUMD|UMD;DSM-5|DSM-5;GS|GS;HCDT|HCPCS;HCPT|CPT;HLREL|HLREL;ICD10AE|ICD10;ICD10AMAE|ICD10AM;ICD10AM|ICD10AM;ICD10CM|ICD10CM;ICD10DUT|ICD10;ICD10|ICD10;ICF-CY|ICF;ICF|ICF;ICNP|ICNP;ICPC2EDUT|ICPC2EENG;ICPC2EENG|ICPC2EENG;ICPC2ICD10DUT|ICPC2ICD10ENG;ICPC2ICD10ENG|ICPC2ICD10ENG;ICPC2P|ICPC2P;JABL|JABL;KCD5|KCD5;MDDB|MDDB;MDR|MDR;MDRCZE|MDR;MDRDUT|MDR;MDRFRE|MDR;MDRGER|MDR;MDRHUN|MDR;MDRITA|MDR;MDRJPN|MDR;MDRPOR|MDR;MDRSPA|MDR;MEDCIN|MEDCIN;MMSL|MMSL;MMX|MMX;MSHCZE|MSH;MSHDUT|MSH;MSHFIN|MSH;MSHFRE|MSH;MSHGER|MSH;MSHITA|MSH;MSHJPN|MSH;MSHLAV|MSH;MSHNOR|MSH;MSHPOL|MSH;MSHPOR|MSH;MSHRUS|MSH;MSHSCR|MSH;MSHSPA|MSH;MSHSWE|MSH;MTHICPC2EAE|ICPC2EENG;MTHICPC2ICD10AE|ICPC2ICD10ENG;NANDA-I|NANDA-I;NDDF|NDDF;NEU|NEU;NIC|NIC;NOC|NOC;NUCCPT|NUCCPT;OMS|OMS;PCDS|PCDS;PNDS|PNDS;PPAC|PPAC;PSY|PSY;RCD|RCD;RCDAE|RCD;RCDSA|RCD;RCDSY|RCD;SCTSPA|SNOMEDCT;SNM|SNM;SNMI|SNMI;SNOMEDCT_US|SNOMEDCT;SNOMEDCT_VET|SNOMEDCT;ULT|ULT;UMD|UMD;WHO|WHO;WHOFRE|WHO;WHOGER|WHO;WHOPOR|WHO;WHOSPA|WHO
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.truncate=false
gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream.character_encoding=UTF-8
active_filters=gov.nih.nlm.umls.mmsys.filter.SourceListFilter;gov.nih.nlm.umls.mmsys.filter.PrecedenceFilter;gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter
gov.nih.nlm.umls.mmsys.filter.PrecedenceFilter.precedence=MTH|PN;RXNORM|MIN;MSH|MH;MSH|TQ;MSH|PEP;MSH|ET;MSH|XQ;MSH|PXQ;MSH|NM;MTHCMSFRF|PT;RXNORM|SCD;RXNORM|SBD;RXNORM|SCDG;RXNORM|SBDG;RXNORM|IN;RXNORM|PSN;RXNORM|SCDF;RXNORM|SBDF;RXNORM|SCDC;RXNORM|DFG;RXNORM|DF;RXNORM|SBDC;RXNORM|BN;RXNORM|PIN;RXNORM|BPCK;RXNORM|GPCK;RXNORM|SY;RXNORM|TMSY;SNOMEDCT_US|PT;SNOMEDCT_US|FN;SNOMEDCT_US|SY;SNOMEDCT_US|PTGB;SNOMEDCT_US|SYGB;SNOMEDCT_US|MTH_PT;SNOMEDCT_US|MTH_FN;SNOMEDCT_US|MTH_SY;SNOMEDCT_US|MTH_PTGB;SNOMEDCT_US|MTH_SYGB;SNOMEDCT_US|SB;SNOMEDCT_US|XM;SNOMEDCT_VET|PT;SNOMEDCT_VET|FN;SNOMEDCT_VET|SY;SNOMEDCT_VET|SB;HPO|PT;HPO|SY;HPO|ET;HPO|OP;HPO|IS;HPO|OET;NCBI|SCN;MTHSPL|MTH_RXN_DP;MTHSPL|DP;MTHSPL|SU;ATC|RXN_PT;ATC|PT;VANDF|PT;VANDF|CD;VANDF|IN;MDDB|CD;USPMG|HC;USPMG|PT;MMX|MTH_RXN_CD;MMX|MTH_RXN_BD;MMX|CD;MMX|BD;DRUGBANK|IN;DRUGBANK|SY;DRUGBANK|FSY;MSH|N1;MSH|PCE;MSH|CE;CPM|PT;NEU|PT;NEU|ACR;NEU|SY;NEU|OP;NEU|IS;FMA|PT;FMA|SY;FMA|AB;FMA|OP;UWDA|PT;UWDA|SY;UMD|PT;UMD|SY;UMD|ET;UMD|RT;GS|CD;MMSL|CD;GS|MTH_RXN_BD;GS|BD;MMSL|MTH_RXN_BD;MMSL|BD;MMSL|SC;MMSL|MS;MMSL|GN;MMSL|BN;ATC|RXN_IN;ATC|IN;MMSL|IN;VANDF|AB;GS|MTH_RXN_CD;VANDF|MTH_RXN_CD;NDDF|MTH_RXN_CDC;NDDF|CDC;NDDF|CDD;NDDF|CDA;NDDF|IN;NDDF|DF;NDFRT|MTH_RXN_RHT;NDFRT|HT;NDFRT|FN;NDFRT|PT;NDFRT|SY;NDFRT|AB;SPN|PT;MDR|PT;MDR|MTH_PT;MDR|HG;MDR|MTH_HG;MDR|OS;MDR|MTH_OS;MDR|HT;MDR|MTH_HT;MDR|LLT;MDR|MTH_LLT;MDR|SMQ;MDR|MTH_SMQ;MDR|AB;CPT|PT;CPT|SY;CPT|ETCLIN;CPT|POS;CPT|GLP;CPT|ETCF;CPT|MP;HCPT|PT;HCPCS|PT;CDT|PT;CDT|OP;MVX|PT;CVX|PT;CVX|RXN_PT;CVX|AB;HCDT|PT;HCPCS|MP;HCPT|MP;ICD10AE|PT;ICD10|PT;ICD10AE|PX;ICD10|PX;ICD10AE|PS;ICD10|PS;ICD10AMAE|PT;ICD10AM|PT;ICD10AMAE|PX;ICD10AM|PX;ICD10AMAE|PS;ICD10AM|PS;OMIM|PT;OMIM|PHENO;OMIM|PHENO_ET;OMIM|PTAV;OMIM|PTCS;OMIM|ETAL;OMIM|ET;OMIM|HT;OMIM|ACR;MEDCIN|PT;MEDCIN|FN;MEDCIN|XM;MEDCIN|SY;HGNC|PT;HGNC|ACR;HGNC|MTH_ACR;HGNC|NA;HGNC|SYN;ICNP|PT;ICNP|MTH_PT;ICNP|XM;PNDS|PT;PNDS|HT;PDQ|PT;PDQ|HT;PDQ|PSC;PDQ|SY;PDQ|MTH_SY;CHV|PT;MEDLINEPLUS|PT;NCI|PT;NCI|SY;NCI_BioC|SY;NCI_PI-RADS|PT;NCI_CareLex|PT;NCI_CareLex|SY;NCI_CDC|PT;NCI_CDISC|PT;NCI_CDISC|SY;NCI|CSN;NCI_DCP|PT;NCI_DCP|SY;NCI|DN;NCI_DTP|PT;NCI_DTP|SY;NCI|FBD;NCI_FDA|AB;NCI_FDA|PT;NCI_FDA|SY;NCI|HD;NCI_GENC|PT;NCI_GENC|CA2;NCI_GENC|CA3;NCI_CRCH|PT;NCI_CRCH|SY;NCI_DICOM|PT;NCI_BRIDG|PT;NCI_RENI|DN;NCI_BioC|PT;NCI|CCN;NCI_CTCAE|PT;NCI_CTEP-SDC|PT;NCI_CTEP-SDC|SY;NCI|CCS;NCI_JAX|PT;NCI_JAX|SY;NCI_KEGG|PT;NCI_ICH|AB;NCI_ICH|PT;NCI_NCI-HL7|AB;NCI_NCI-HL7|PT;NCI_UCUM|AB;NCI_UCUM|PT;NCI_KEGG|AB;NCI_KEGG|SY;NCI_NICHD|PT;NCI_NICHD|SY;NCI_PID|PT;NCI_NCPDP|PT;NCI_GAIA|PT;NCI_GAIA|SY;NCI_ZFin|PT;NCI_NCI-GLOSS|PT;NCI_ICH|SY;NCI_NCI-HL7|SY;NCI_UCUM|SY;NCI_NCPDP|SY;NCI_ZFin|SY;NCI_NCI-GLOSS|SY;NCI|OP;NCI_NICHD|OP;NCI|AD;NCI|CA2;NCI|CA3;NCI|BN;NCI|AB;MTHICPC2EAE|PT;ICPC2EENG|PT;MTHICPC2ICD10AE|PT;SOP|PT;ICF|HT;ICF|PT;ICF|MTH_HT;ICF|MTH_PT;ICF-CY|HT;ICF-CY|PT;ICF-CY|MTH_HT;ICF-CY|MTH_PT;ICPC2ICD10ENG|PT;ICPC|PX;ICPC|PT;ICPC|PS;ICPC|PC;ICPC|CX;ICPC|CP;ICPC|CS;ICPC|CC;ICPC2EENG|CO;ICPC|CO;MTHICPC2EAE|AB;ICPC2EENG|AB;ICPC2P|PTN;ICPC2P|MTH_PTN;ICPC2P|PT;ICPC2P|MTH_PT;ICPC2P|OPN;ICPC2P|MTH_OPN;ICPC2P|OP;ICPC2P|MTH_OP;AOT|PT;AOT|ET;HCPCS|OP;HCDT|OP;HCPT|OP;HCPCS|OM;HCPCS|OAM;GO|PT;GO|MTH_PT;GO|ET;GO|MTH_ET;GO|SY;GO|MTH_SY;GO|OP;GO|MTH_OP;GO|OET;GO|MTH_OET;GO|IS;GO|MTH_IS;PDQ|ET;PDQ|CU;PDQ|MTH_LV;PDQ|LV;PDQ|MTH_AB;PDQ|MTH_ACR;PDQ|ACR;PDQ|AB;PDQ|BD;PDQ|FBD;PDQ|OP;PDQ|CCN;PDQ|CHN;PDQ|MTH_CHN;PDQ|IS;PDQ|MTH_BD;NCBI|USN;NCBI|USY;NCBI|SY;NCBI|UCN;NCBI|CMN;NCBI|UE;NCBI|EQ;NCBI|AUN;NCBI|UAUN;LNC|LN;LNC|MTH_LN;LNC|OSN;LNC|CN;LNC|MTH_CN;LNC|LPN;LNC|LPDN;LNC|HC;LNC|HS;LNC|OLC;LNC|LC;LNC|XM;LNC|LS;LNC|LO;LNC|MTH_LO;LNC|OOSN;LNC|LA;ICD10CM|PT;ICD9CM|PT;ICD10CM|XM;MDR|OL;MDR|MTH_OL;ICD10CM|HT;ICD9CM|HT;CCS_10|HT;CCS_10|MD;CCS_10|MV;CCS_10|SD;CCS_10|SP;CCS_10|XM;CCS|HT;CCS|MD;CCS|SD;CCS|MV;CCS|SP;CCS|XM;ICPC2ICD10ENG|XM;ICD10AE|HT;ICD10PCS|PT;ICD10PCS|PX;ICD10PCS|HX;ICD10PCS|MTH_HX;ICD10PCS|HT;ICD10PCS|XM;ICD10PCS|HS;ICD10PCS|AB;ICD10|HT;ICD10AE|HX;ICD10|HX;ICD10AE|HS;ICD10|HS;ICD10AMAE|HT;ICD10AM|HT;UMD|HT;ICPC|HT;NUCCPT|PT;HL7V3.0|CSY;HL7V3.0|PT;HL7V2.5|PT;HL7V3.0|CDO;HL7V3.0|VS;HL7V3.0|BR;HL7V3.0|CPR;HL7V3.0|CR;HL7V3.0|NPT;HL7V3.0|OP;HL7V3.0|ONP;HL7V2.5|HTN;CPT|HT;CDT|HT;MTHHH|HT;CCC|PT;CCC|HT;NIC|IV;NIC|HC;NANDA-I|PT;NANDA-I|HT;NANDA-I|HC;NANDA-I|RT;OMS|MTH_SI;OMS|PR;OMS|TG;OMS|HT;OMS|PQ;OMS|IVC;OMS|SI;OMS|SCALE;NIC|AC;NOC|OC;NOC|MTH_ID;NOC|ID;NIC|HT;NOC|HT;NOC|HC;CCC|MTH_HT;CCC|MP;ALT|PT;ALT|HT;MTH|CV;MTH|XM;MTH|PT;MTH|SY;MTH|RT;ICD10CM|ET;MTHICD9|ET;ICD10CM|AB;ICD9CM|AB;PSY|PT;PSY|HT;PSY|ET;MEDLINEPLUS|ET;MEDLINEPLUS|SY;MEDLINEPLUS|HT;LCH_NW|PT;LCH|PT;MSH|HT;MSH|HS;MSH|DEV;MSH|DSV;MSH|QAB;MSH|QEV;MSH|QSV;MSH|PM;LCH_NW|XM;CPT|AB;HCPT|AB;HCPCS|AB;WHO|PT;WHO|OS;WHO|HT;WHO|IT;SNMI|PT;SNMI|PX;SNMI|HT;SNMI|HX;SNMI|RT;SNMI|SY;SNMI|SX;SNMI|AD;SNM|PT;SNM|RT;SNM|HT;SNM|SY;SNM|RS;RCD|PT;RCD|OP;RCD|SY;RCD|IS;RCD|AT;RCD|AS;RCD|AB;RCDSA|PT;RCDSY|PT;RCDAE|PT;RCDSA|SY;RCDSY|SY;RCDAE|SY;RCDSA|OP;RCDSY|OP;RCDAE|OP;RCDSA|IS;RCDSY|IS;RCDAE|IS;RCDAE|AT;RCDSA|AB;RCDSY|AB;RCDAE|AB;RCDSA|OA;RCDSY|OA;RCDAE|OA;RCD|OA;RCDAE|AA;RCD|AA;CSP|PT;CSP|SY;CSP|ET;CSP|AB;MTH|DT;HCPT|OA;HCPT|AM;HCPCS|OA;HCPCS|AM;HCDT|AB;ALT|AB;HCDT|OA;CHV|SY;RXNORM|ET;SNOMEDCT_VET|OAP;SNOMEDCT_VET|OP;SNOMEDCT_US|OAP;SNOMEDCT_US|OP;SNOMEDCT_VET|OAF;SNOMEDCT_VET|OF;SNOMEDCT_US|OAF;SNOMEDCT_US|OF;SNOMEDCT_VET|OAS;SNOMEDCT_VET|IS;SNOMEDCT_US|OAS;SNOMEDCT_US|IS;SNOMEDCT_US|MTH_OAP;SNOMEDCT_US|MTH_OP;SNOMEDCT_US|MTH_OAF;SNOMEDCT_US|MTH_OF;SNOMEDCT_US|MTH_OAS;SNOMEDCT_US|MTH_IS;DSM-5|DC10;DSM-5|DC9;DXP|DI;DXP|FI;DXP|SY;RAM|PT;RAM|RT;ULT|PT;BI|PT;BI|AB;BI|SY;BI|RT;PCDS|GO;PCDS|OR;PCDS|PR;PCDS|CO;PCDS|HX;PCDS|HT;MTHMST|PT;MTHMST|SY;DDB|PT;DDB|SY;CST|PT;COSTAR|PT;CST|SC;CST|HT;CST|GT;CCPSS|TX;CCPSS|TC;CCPSS|PT;CCPSS|MP;AOD|DE;AOD|DS;AOD|XD;AOD|FN;AOD|ET;AOD|ES;AOD|EX;AOD|NP;AOD|NS;AOD|NX;QMR|PT;JABL|PC;JABL|PT;JABL|SS;JABL|SY;AIR|FI;AIR|DI;AIR|SY;AIR|HT;PPAC|DO;PPAC|CL;PPAC|AC;PPAC|ST;PPAC|TA;MCM|PT;MCM|RT;SCTSPA|PT;SCTSPA|FN;SCTSPA|SY;SCTSPA|MTH_PT;SCTSPA|MTH_FN;SCTSPA|MTH_SY;SCTSPA|SB;SCTSPA|OP;SCTSPA|OAF;SCTSPA|OAP;SCTSPA|OAS;SCTSPA|OF;SCTSPA|IS;SCTSPA|MTH_OP;SCTSPA|MTH_OAF;SCTSPA|MTH_OAP;SCTSPA|MTH_OAS;SCTSPA|MTH_OF;SCTSPA|MTH_IS;MSHPOR|MH;MSHPOR|PEP;MSHPOR|ET;MSHSPA|MH;MSHSPA|PEP;MSHSPA|ET;MSHCZE|MH;MSHCZE|PEP;MSHCZE|ET;MSHDUT|MH;MSHSWE|MH;MSHSWE|TQ;MSHNOR|MH;MSHGER|MH;MSHNOR|PEP;MSHGER|PEP;MSHNOR|DSV;MSHGER|DSV;MSHNOR|ET;MSHGER|ET;MSHFIN|MH;MSHLAV|MH;MSHSCR|MH;MSHFRE|MH;MSHLAV|PEP;MSHSCR|PEP;MSHFRE|PEP;MSHLAV|EP;MSHSCR|ET;MSHFRE|ET;MSHITA|MH;MSHITA|PEP;MSHITA|ET;MSHJPN|PT;MSHPOL|MH;MSHRUS|MH;MSHJPN|SY;KCD5|HT;TKMT|PT;KCD5|PT;MSHPOL|SY;MSHRUS|SY;MSHDUT|SY;MDRSPA|PT;MDRSPA|HG;MDRSPA|HT;MDRSPA|LLT;MDRSPA|OS;MDRSPA|SMQ;MDRSPA|OL;MDRSPA|AB;MDRDUT|PT;MDRDUT|HG;MDRDUT|HT;MDRDUT|LLT;MDRDUT|OS;MDRDUT|SMQ;MDRDUT|OL;MDRDUT|AB;MDRFRE|PT;MDRFRE|HG;MDRFRE|HT;MDRFRE|LLT;MDRFRE|SMQ;MDRFRE|OS;MDRFRE|OL;MDRFRE|AB;MDRGER|PT;MDRGER|HG;MDRGER|HT;MDRGER|LLT;MDRGER|SMQ;MDRGER|OS;MDRGER|OL;MDRGER|AB;MDRITA|PT;MDRITA|HG;MDRITA|HT;MDRITA|LLT;MDRITA|SMQ;MDRITA|OS;MDRITA|OL;MDRITA|AB;MDRJPN|PT;MDRJPN|PTJKN;MDRJPN|PTJKN1;MDRJPN|HG;MDRJPN|HGJKN;MDRJPN|HGJKN1;MDRJPN|HT;MDRJPN|HTJKN;MDRJPN|HTJKN1;MDRJPN|LLT;MDRJPN|LLTJKN;MDRJPN|LLTJKN1;MDRJPN|OS;MDRJPN|SMQ;MDRJPN|OL;MDRJPN|OLJKN;MDRJPN|OLJKN1;MDRCZE|PT;MDRHUN|PT;MDRPOR|PT;MDRCZE|HG;MDRHUN|HG;MDRPOR|HG;MDRCZE|HT;MDRHUN|HT;MDRPOR|HT;MDRCZE|LLT;MDRHUN|LLT;MDRPOR|LLT;MDRCZE|OS;MDRHUN|OS;MDRPOR|OS;MDRCZE|SMQ;MDRHUN|SMQ;MDRPOR|SMQ;MDRCZE|OL;MDRHUN|OL;MDRPOR|OL;MDRCZE|AB;MDRHUN|AB;MDRPOR|AB;MDRJPN|OSJKN;MDRJPN|OSJKN1;WHOFRE|HT;WHOGER|HT;WHOPOR|HT;WHOSPA|HT;LNC-DE-CH|OSN;LNC-DE-CH|OOSN;LNC-DE-DE|LN;LNC-DE-DE|LO;LNC-EL-GR|LN;LNC-EL-GR|LO;LNC-ES-AR|LN;LNC-ES-AR|OSN;LNC-ES-AR|LO;LNC-ES-AR|OOSN;LNC-ES-CH|OSN;LNC-ES-CH|OOSN;LNC-ES-ES|LN;LNC-ES-ES|LO;LNC-ET-EE|LN;LNC-ET-EE|LO;LNC-FR-BE|LN;LNC-FR-BE|LO;LNC-FR-CA|LN;LNC-FR-CA|LO;LNC-FR-CH|OSN;LNC-FR-CH|OOSN;LNC-FR-FR|LN;LNC-FR-FR|LC;LNC-FR-FR|OLC;LNC-FR-FR|LO;LNC-IT-CH|OSN;LNC-IT-CH|OOSN;LNC-IT-IT|LN;LNC-IT-IT|LO;LNC-KO-KR|LN;LNC-KO-KR|LO;LNC-NL-NL|LN;LNC-NL-NL|LO;LNC-PT-BR|LN;LNC-PT-BR|OSN;LNC-PT-BR|LC;LNC-PT-BR|OLC;LNC-PT-BR|LO;LNC-PT-BR|OOSN;LNC-RU-RU|LN;LNC-RU-RU|LO;LNC-TR-TR|LN;LNC-TR-TR|LO;LNC-ZH-CN|LN;LNC-ZH-CN|LO;LNC-DE-AT|LN;LNC-DE-AT|LO;WHOFRE|PT;WHOGER|PT;WHOPOR|PT;WHOSPA|PT;WHOFRE|IT;WHOGER|IT;WHOPOR|IT;WHOSPA|IT;WHOFRE|OS;WHOGER|OS;WHOPOR|OS;WHOSPA|OS;CPTSP|PT;DMDUMD|PT;DMDUMD|ET;DMDUMD|RT;DMDICD10|PT;DMDICD10|HT;ICPCBAQ|PT;ICPCDAN|PT;ICPC2EDUT|PT;ICD10DUT|PT;ICD10DUT|HT;ICPC2ICD10DUT|PT;ICPCDUT|PT;ICPCFIN|PT;ICPCFRE|PT;ICPCGER|PT;ICPCHEB|PT;ICPCHUN|PT;ICPCITA|PT;ICPCNOR|PT;ICPCPOR|PT;ICPCSPA|PT;ICPCSWE|PT;ICPCBAQ|CP;ICPCDAN|CP;ICPCDUT|CP;ICPCFIN|CP;ICPCFRE|CP;ICPCGER|CP;ICPCHEB|CP;ICPCHUN|CP;ICPCITA|CP;ICPCNOR|CP;ICPCPOR|CP;ICPCSPA|CP;ICPCSWE|CP;MTHMSTFRE|PT;MTHMSTITA|PT;SRC|RPT;SRC|RHT;SRC|RAB;SRC|RSY;SRC|VPT;SRC|VAB;SRC|VSY;SRC|SSN;
gov.nih.nlm.umls.mmsys.io.NLMFileMetamorphoSysInputStream.meta_source_uri=/tmp/tmpg1z_uldg/umls_unzipped
gov.nih.nlm.umls.mmsys.filter.SuppressibleFilter.confirm_default_suppressible_sabttys=HPO|OP;HPO|IS;HPO|OET;NEU|ACR;NEU|OP;NEU|IS;FMA|AB;FMA|OP;MDR|AB;CDT|OP;ICD10AE|PS;ICD10|PS;ICD10AMAE|PS;ICD10AM|PS;NCI|OP;NCI_NICHD|OP;ICPC|PS;ICPC|CS;MTHICPC2EAE|AB;ICPC2EENG|AB;ICPC2P|MTH_PT;ICPC2P|OPN;ICPC2P|MTH_OPN;ICPC2P|OP;ICPC2P|MTH_OP;HCPCS|OP;HCDT|OP;HCPT|OP;HCPCS|OM;HCPCS|OAM;GO|OP;GO|MTH_OP;GO|OET;GO|MTH_OET;GO|IS;GO|MTH_IS;PDQ|OP;PDQ|IS;NCBI|AUN;NCBI|UAUN;LNC|OLC;LNC|LO;LNC|MTH_LO;LNC|OOSN;MDR|OL;MDR|MTH_OL;ICD10PCS|HS;ICD10PCS|AB;ICD10AE|HS;ICD10|HS;HL7V3.0|OP;HL7V3.0|ONP;ICD10CM|AB;ICD9CM|AB;MSH|DEV;MSH|DSV;MSH|QAB;MSH|QEV;MSH|QSV;CPT|AB;HCPT|AB;HCPCS|AB;SNMI|PX;SNMI|HX;SNMI|SX;RCD|OP;RCD|IS;RCD|AS;RCD|AB;RCDSA|OP;RCDSY|OP;RCDAE|OP;RCDSA|IS;RCDSY|IS;RCDAE|IS;RCDSA|AB;RCDSY|AB;RCDAE|AB;RCDSA|OA;RCDSY|OA;RCDAE|OA;RCD|OA;RCDAE|AA;RCD|AA;HCPT|OA;HCPT|AM;HCPCS|OA;HCPCS|AM;HCDT|AB;ALT|AB;HCDT|OA;SNOMEDCT_VET|OAP;SNOMEDCT_VET|OP;SNOMEDCT_US|OAP;SNOMEDCT_US|OP;SNOMEDCT_VET|OAF;SNOMEDCT_VET|OF;SNOMEDCT_US|OAF;SNOMEDCT_US|OF;SNOMEDCT_VET|OAS;SNOMEDCT_VET|IS;SNOMEDCT_US|OAS;SNOMEDCT_US|IS;SNOMEDCT_US|MTH_OAP;SNOMEDCT_US|MTH_OP;SNOMEDCT_US|MTH_OAF;SNOMEDCT_US|MTH_OF;SNOMEDCT_US|MTH_OAS;SNOMEDCT_US|MTH_IS;CCPSS|TC;SCTSPA|OP;SCTSPA|OAF;SCTSPA|OAP;SCTSPA|OAS;SCTSPA|OF;SCTSPA|IS;SCTSPA|MTH_OP;SCTSPA|MTH_OAF;SCTSPA|MTH_OAP;SCTSPA|MTH_OAS;SCTSPA|MTH_OF;SCTSPA|MTH_IS;MSHNOR|DSV;MSHGER|DSV;MDRSPA|OL;MDRSPA|AB;MDRDUT|OL;MDRDUT|AB;MDRFRE|OL;MDRFRE|AB;MDRGER|OL;MDRGER|AB;MDRITA|OL;MDRITA|AB;MDRJPN|OL;MDRJPN|OLJKN;MDRJPN|OLJKN1;MDRCZE|OL;MDRHUN|OL;MDRPOR|OL;MDRCZE|AB;MDRHUN|AB;MDRPOR|AB;LNC-DE-CH|OOSN;LNC-DE-DE|LO;LNC-EL-GR|LO;LNC-ES-AR|LO;LNC-ES-AR|OOSN;LNC-ES-CH|OOSN;LNC-ES-ES|LO;LNC-ET-EE|LO;LNC-FR-BE|LO;LNC-FR-CA|LO;LNC-FR-CH|OOSN;LNC-FR-FR|OLC;LNC-FR-FR|LO;LNC-IT-CH|OOSN;LNC-IT-IT|LO;LNC-KO-KR|LO;LNC-NL-NL|LO;LNC-PT-BR|OLC;LNC-PT-BR|LO;LNC-PT-BR|OOSN;LNC-RU-RU|LO;LNC-TR-TR|LO;LNC-ZH-CN|LO;LNC-DE-AT|LO
gov.nih.nlm.umls.mmsys.filter.SourceListFilter.enforce_dep_source_selection=true
"""


# =============================================================================
# Helper functions
# =============================================================================


def require_external_tool(tool: str) -> str:
    """
    Checks that we have an external tool available, or raises.

    Args:
        tool: name of the tool, e.g. ``unzip``

    Returns:
         str: the full path to the executable
    """
    path = shutil.which(tool)
    if not path:
        die(f"Can't find command: {tool}")
    return path


def get_default_java_home() -> str:
    """
    Returns a suitable default for the JAVA_HOME environment variable.
    """
    if EnvVar.GENERATING_CRATE_DOCS:
        return "/path/to/java"

    if EnvVar.JAVA_HOME in os.environ:
        return os.environ[EnvVar.JAVA_HOME]
    java_executable = require_external_tool("java")
    return os.path.abspath(join(java_executable, os.pardir, os.pardir))


def get_default_gate_home() -> str:
    """
    Returns a suitable default for the GATE_HOME environment variable.
    """
    if EnvVar.GENERATING_CRATE_DOCS:
        return "/path/to/GATE/directory"

    return os.environ.get(EnvVar.GATE_HOME, "")


def read_config_and_replace_values(
    filename: str, new_values: Dict[str, str]
) -> str:
    """
    - Reads a config file of the Java "key=value" style.
    - Replaces any keys required.
    - Returns the entire text of the result.

    Args:
        filename:
            Filename to read
        new_values:
            Dictionary of key-value pairs.
    """
    # Read config file that we'll use as a starting point
    with open(filename, "r") as f:
        old_lines = [s.rstrip() for s in f.readlines()]

    # Replace
    new_lines = []  # type: List[str]
    for s in old_lines:
        m = KVP_REGEX.match(s)
        if m:
            key = m.group(1)
            old_value = m.group(2)
            if key in new_values.keys():
                new_value = new_values[key]
                if old_value != new_value:
                    # Old config file differs from what we want.
                    s = f"{key} = {new_value}"
        new_lines.append(s)

    # Done
    return "\n".join(new_lines) + "\n"


def get_mmsys_configfile_text(
    metadir: str, mmsys_home: str, release: str
) -> str:
    r"""
    Returns a config file suitable for use with the UMLS MetamorphoSys tool.

    Args:
        metadir: base directory of the UMLS distribution
        mmsys_home: directory containing the mmsys files
        release: UMLS release, e.g. "2017AA", "2018AB"

    Their command from
    https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMetaMorphoSys.html,
    edited so it works (but note that ``^sources`` isn't present in the 2017AA
    version):

    .. code-block:: bash

        export MMSYS_HOME=$PWD  # for example
        export UMLS_RELEASE=2017AA  # for example

        grep \
                "^gov.nih.nlm.umls.mmsys.filter.SourceListFilter.selected_sources" \
                "${MMSYS_HOME}/config/${UMLS_RELEASE}/user.a.prop" |
            perl -pe 's/gov.nih.nlm.umls.mmsys.filter.SourceListFilter.selected_sources=//; s/;/\n/g' |
            awk -F '\\|' '{print $1"|"$1}' |
            perl -pe 's/\n/;/g' \
            > /tmp/sab_list.txt
    """  # noqa: E501

    # Config file that we'll use as a starting point
    start_config_filename = join(mmsys_home, "config", release, "user.a.prop")

    # New values to set
    new_values = {
        "gov.nih.nlm.umls.mmsys.filter.SourceListFilter.remove_selected_sources": "false",  # noqa: E501
        "mmsys_input_stream": "gov.nih.nlm.umls.mmsys.io.NLMFileMetamorphoSysInputStream",  # noqa: E501
        "mmsys_output_stream": "gov.nih.nlm.umls.mmsys.io.RRFMetamorphoSysOutputStream",  # noqa: E501
        "meta_source_uri": metadir,
        "umls_source_uri": metadir,  # ?
    }

    return read_config_and_replace_values(start_config_filename, new_values)


# =============================================================================
# Main UMLS-to-BioYODIE functions
# =============================================================================


class UmlsBioyodieConversionConfig:
    """
    Simple config object to pass stuff around.
    """

    def __init__(
        self,
        umls_zip: str,
        dest_dir: str,
        tmp_dir: str,
        java_home: str,
        gate_home: str,
        groovy_executable: str,
        bioyodie_prep_repo_url: str,
        scala_url: str,
        keep_temp_dir: bool,
    ) -> None:
        """
        Prepare downloaded UMLS data for Bio-YODIE, according to the
        instructions at https://github.com/GateNLP/bio-yodie-resource-prep.

        Args:
            umls_zip:
                ZIP file of UMLS data
            dest_dir:
                output directory
            tmp_dir:
                temporary directory to use
            java_home:
                value for JAVA_HOME environment variable
            gate_home:
                value for GATE_HOME environment variable
            groovy_executable:
                path to ``groovy`` executable
            bioyodie_prep_repo_url:
                BioYODIE preprocessor Git URL
            scala_url:
                Scala .tgz URL
            keep_temp_dir:
                preserve temporary directory (for debugging)
        """
        self.umls_zip = umls_zip
        self.dest_dir = dest_dir
        self.tmp_dir = tmp_dir
        self.java_home = java_home
        self.gate_home = gate_home
        self.groovy_executable = groovy_executable
        self.bioyodie_prep_repo_url = bioyodie_prep_repo_url
        self.scala_url = scala_url
        self.keep_temp_dir = keep_temp_dir


def prepare_umls_for_bioyodie(cfg: UmlsBioyodieConversionConfig) -> None:
    """
    Prepare downloaded UMLS data for Bio-YODIE, according to the instructions
    at https://github.com/GateNLP/bio-yodie-resource-prep.
    """
    # -------------------------------------------------------------------------
    # Parameter checks
    # -------------------------------------------------------------------------
    assert cfg.java_home
    assert cfg.gate_home

    # -------------------------------------------------------------------------
    # Establish the release (version)
    # -------------------------------------------------------------------------
    # There are two releases per year, e.g. 2017AA and 2017AB.
    release_regex = regex.compile(r"umls-(\d\d\d\dA[AB])-full.zip")
    umls_zip_basename = os.path.basename(cfg.umls_zip)
    try:
        release = release_regex.match(umls_zip_basename).group(1)
    except AttributeError:  # 'NoneType' object has no attribute 'group'
        release = None  # for type-checker only (below)
        die(
            f"Unable to work out UMLS release from filename: "
            f"{umls_zip_basename!r}"
        )

    # -------------------------------------------------------------------------
    # Directory names
    # -------------------------------------------------------------------------
    umls_root_dir = join(cfg.tmp_dir, "umls_data_with_mmsys")
    umls_metadir = umls_root_dir
    umls_mmsys_home = umls_metadir
    # ... because the GUI installer wants "release.dat" (which is in the root
    # and config/2017AA directories of "mmsys.zip") to be in the same directory
    # as the Metathesaurus files. Do NOT put it in a "MMSYS" subdirectory,
    # despite
    # https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMRCXTBuilder.html
    umls_lib_dir = join(umls_mmsys_home, "lib")
    umls_plugins_dir = join(umls_mmsys_home, "plugins")

    umls_output_dir = join(cfg.tmp_dir, "umls_output")
    # ... Where we tell it to store data.
    # Log files and other output go here.

    bioyodie_repo_dir = join(cfg.tmp_dir, "bio-yodie-resource-prep")
    bioyodie_db_dir = join(bioyodie_repo_dir, "databases")
    bioyodie_scala_dir = join(bioyodie_repo_dir, "scala")
    bioyodie_tmpdata_dir = join(bioyodie_repo_dir, "tmpdata")
    bioyodie_umls_dir_containing_symlink = join(
        bioyodie_repo_dir, "srcs", "umls", "2015AB"
    )  # hard-coded "2015AB"
    bioyodie_umls_input_dir = join(
        bioyodie_umls_dir_containing_symlink, "META"
    )  # hard-coded "META"
    bioyodie_output_dir = join(bioyodie_repo_dir, "output")

    # -------------------------------------------------------------------------
    # Filenames
    # -------------------------------------------------------------------------
    scala_tgz = join(bioyodie_scala_dir, "scala.tgz")
    builder_script = join(bioyodie_repo_dir, "bin", "all.sh")
    mmsys_zip = join(umls_root_dir, "mmsys.zip")
    config_file = join(umls_metadir, "config.properties")
    boot_config = join(umls_mmsys_home, "etc", "subset.boot.properties")
    log4j_config = join(
        umls_mmsys_home, "etc", "rudolf.log4j.properties"
    )  # new

    system_java_home = cfg.java_home
    umls_java_home = join(umls_mmsys_home, "jre", "linux")  # it brings its own

    # -------------------------------------------------------------------------
    # Checks
    # -------------------------------------------------------------------------
    if os.path.exists(cfg.dest_dir):
        die(f"Directory already exists: {cfg.dest_dir}")
    system_unzip = require_external_tool("unzip")
    # These are required by the Bio-YODIE preprocessor:
    groovy_executable = cfg.groovy_executable or require_external_tool(
        "groovy"
    )
    require_external_tool("gzip")
    require_external_tool("zcat")

    # -------------------------------------------------------------------------
    # Environment variables
    # -------------------------------------------------------------------------
    # For UMLS
    umls_env = os.environ.copy()
    umls_env[EnvVar.JAVA_HOME] = umls_java_home
    # For Bio-YODIE preprocessor
    bioyodie_env = os.environ.copy()
    bioyodie_env[EnvVar.JAVA_HOME] = system_java_home
    bioyodie_env[EnvVar.GATE_HOME] = cfg.gate_home
    groovy_dir = os.path.dirname(os.path.abspath(groovy_executable))
    old_path = bioyodie_env.get(EnvVar.PATH, "")
    new_path_with_groovy = os.pathsep.join(
        x for x in [groovy_dir, old_path] if x
    )
    bioyodie_env[EnvVar.PATH] = new_path_with_groovy

    # -------------------------------------------------------------------------
    log.info("Cloning Bio-YODIE resource prep repository...")
    # -------------------------------------------------------------------------
    check_call_verbose(
        ["git", "clone", cfg.bioyodie_prep_repo_url, bioyodie_repo_dir]
    )

    # -------------------------------------------------------------------------
    log.info("Making directories...")
    # -------------------------------------------------------------------------
    mkdir_p(umls_output_dir)
    mkdir_p(bioyodie_db_dir)
    # mkdir_p(bioyodie_scala_dir)  # already exists
    mkdir_p(bioyodie_tmpdata_dir)
    mkdir_p(bioyodie_umls_dir_containing_symlink)
    mkdir_p(bioyodie_output_dir)

    # -------------------------------------------------------------------------
    log.info("Fetching/building Scala for the BioYODIE processor...")
    # -------------------------------------------------------------------------
    # ... either before we set JAVA_HOME (to use the system Java) or after
    # we've unpacked MMSYS (which brings its own JRE), but not in between!
    download(cfg.scala_url, scala_tgz)
    with pushd(bioyodie_scala_dir):
        check_call_verbose(["tar", "-xzvf", scala_tgz])
        check_call_verbose(["ant"], env=bioyodie_env)

    # -------------------------------------------------------------------------
    log.info("Unzipping UMLS data...")
    # -------------------------------------------------------------------------
    check_call_verbose(["unzip", "-j", cfg.umls_zip, "-d", umls_root_dir])
    # -j: junk paths (extract "flat" into the specified directory)

    # -------------------------------------------------------------------------
    log.info("Unzipping UMLS MetamorphoSys (MMSYS) program (and its JRE)...")
    # -------------------------------------------------------------------------
    check_call_verbose(["unzip", mmsys_zip, "-d", umls_mmsys_home])
    # "To ensure proper functionality users must unzip mmsys.zip to the same
    # directory as the other downloaded files."
    # -- https://www.ncbi.nlm.nih.gov/books/NBK9683/
    # ... but see also example above.

    # -------------------------------------------------------------------------
    log.info("Running MetamorphoSys in batch mode...")
    # -------------------------------------------------------------------------
    # https://www.nlm.nih.gov/research/umls/implementation_resources/community/mmsys/BatchMetaMorphoSys.html  # noqa: E501
    classpath = ":".join(
        [
            umls_mmsys_home,
            umls_plugins_dir,  # RNC extra
            join(umls_lib_dir, "jpf-boot.jar"),
            join(umls_lib_dir, "jpf.jar"),  # RNC extra
            # You can use "dir/*" to mean "all JAR files in a directory":
            # https://en.wikipedia.org/wiki/Classpath
            join(
                umls_plugins_dir, "gov.nih.nlm.umls.meta", "lib", "*"
            ),  # RNC extra
            join(
                umls_plugins_dir, "gov.nih.nlm.umls.mmsys", "lib", "*"
            ),  # RNC extra
            join(
                umls_plugins_dir, "gov.nih.nlm.umls.mmsys.gui", "lib", "*"
            ),  # RNC extra
            join(
                umls_plugins_dir, "gov.nih.nlm.umls.mmsys.io", "lib", "*"
            ),  # RNC extra
            join(
                umls_plugins_dir, "gov.nih.nlm.umls.util", "lib", "*"
            ),  # RNC extra
        ]
    )
    write_text(
        config_file,
        get_mmsys_configfile_text(
            metadir=umls_metadir, mmsys_home=umls_mmsys_home, release=release
        ),
    )
    write_text(log4j_config, LOG4J_PROPERTIES_TEXT)
    with pushd(umls_mmsys_home):
        log.warning(
            f"The next step is slow, and doesn't say much. "
            f"It produces roughly 29 Gb at peak. "
            f"Watch progress with: "
            f"watch 'du -bc {cfg.tmp_dir} | tail -1'"
        )
        check_call_verbose(
            [
                join(cfg.java_home, "bin", "java"),
                "-classpath",
                classpath,
                "-Djava.awt.headless=true",
                f"-Djpf.boot.config={boot_config}",
                f"-Dlog4j.configurationFile={log4j_config}",
                # not "log4j.configuration" as in the original! Argh.
                # http://logging.apache.org/log4j/2.x/manual/configuration.html
                f"-Dinput.uri={umls_metadir}",
                f"-Doutput.uri={umls_output_dir}",
                f"-Dmmsys.config.uri={config_file}",
                # Additional from run_linux.sh:
                "-client",  # JVM option: client rather than server mode
                "-Dunzip.native=true",
                f"-Dunzip.path={system_unzip}",
                "-Dfile.encoding=UTF-8",
                "-Xms1000M",  # was 300M, but it's 1000M in run_linux.sh
                "-Xmx2000M",  # was 1000M, but it's 2000M in run_linux.sh
                "org.java.plugin.boot.Boot",
            ],
            env=umls_env,
        )

    # -------------------------------------------------------------------------
    log.info("Converting UMLS data to Bio-YODIE format...")
    # -------------------------------------------------------------------------
    os.symlink(
        src=umls_output_dir,
        dst=bioyodie_umls_input_dir,
        target_is_directory=True,
    )
    with pushd(bioyodie_repo_dir):
        log.warning("The next step is also slow.")
        check_call_verbose([builder_script], env=bioyodie_env)

    # -------------------------------------------------------------------------
    log.info(f"Moving Bio-YODIE data to destination directory: {cfg.dest_dir}")
    # -------------------------------------------------------------------------
    output_files = os.listdir(bioyodie_output_dir)
    if output_files:
        shutil.copytree(bioyodie_output_dir, cfg.dest_dir)
        # ... destination should not already exist
        # ... it will make intermediate directories happily
    else:
        log.error(
            f"No output files in {bioyodie_output_dir}! "
            f"Did the Bio-YODIE preprocessor partly crash?"
        )


def prepare_umls_for_bioyodie_meta(cfg: UmlsBioyodieConversionConfig) -> None:
    """
    See :func:`prepare_umls_for_bioyodie`.
    """
    if cfg.keep_temp_dir:
        cfg.tmp_dir = tempfile.mkdtemp()
    else:
        tmp_dir_obj = tempfile.TemporaryDirectory()
        cfg.tmp_dir = tmp_dir_obj.name

    prepare_umls_for_bioyodie(cfg)
    if cfg.keep_temp_dir:
        log.warning(f"Residual files are in {cfg.tmp_dir}")
    else:
        log.info("Cleaning up on exit...")


# =============================================================================
# main
# =============================================================================


def main() -> NoReturn:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Prepare UMLS data for BioYodie.",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    parser.add_argument(
        "umls_zip",
        help="Filename of ZIP file downloaded from "
        "https://www.nlm.nih.gov/research/umls/licensedcontent/umlsknowledgesources.html, "  # noqa: E501
        "e.g. /path/to/umls-2017AA-full.zip . This can't be "
        "autodownloaded, as it requires a license/login.",
    )
    parser.add_argument("dest_dir", help="Destination directory to write.")
    parser.add_argument(
        "--keeptemp",
        action="store_true",
        help="Keep temporary directory on exit.",
    )
    parser.add_argument(
        "--java_home",
        help=f"Value for {EnvVar.JAVA_HOME} environment variable. "
        f"Should be a directory that contains 'bin/java'. "
        f"Default is (a) existing {EnvVar.JAVA_HOME} variable; "
        f"(b) location based on 'which java'.",
        default=get_default_java_home(),
    )
    parser.add_argument(
        "--gate_home",
        help=f"Value for {EnvVar.GATE_HOME} environment variable. "
        f"Should be a directory that contains 'bin/gate.*'. "
        f"Default is existing {EnvVar.GATE_HOME} environment variable.",
        default=get_default_gate_home(),
    )
    parser.add_argument(
        "--groovy",
        help="Path to groovy binary (ideally v3.0+). "
        "Default is the system copy, if there is one.",
        default=shutil.which("groovy"),
    )
    parser.add_argument(
        "--bioyodie_prep_repo_url",
        help="URL of Bio-YODIE preprocessor Git repository",
        # default="https://github.com/GateNLP/bio-yodie-resource-prep"
        default="https://github.com/RudolfCardinal/bio-yodie-resource-prep",
    )
    parser.add_argument(
        "--scala_url",
        help="URL for Scala .tgz file",
        default=(
            "https://downloads.lightbend.com/scala/2.11.7/scala-2.11.7.tgz"
        ),
    )

    args = parser.parse_args()
    cfg = UmlsBioyodieConversionConfig(
        umls_zip=args.umls_zip,
        dest_dir=args.dest_dir,
        keep_temp_dir=args.keeptemp,
        java_home=args.java_home,
        gate_home=args.gate_home,
        groovy_executable=args.groovy,
        bioyodie_prep_repo_url=args.bioyodie_prep_repo_url,
        scala_url=args.scala_url,
        tmp_dir="",  # will be changed
    )
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    if not cfg.gate_home:
        die(
            "Must specify environment variable GATE_HOME or --gate_home "
            "parameter."
        )
    prepare_umls_for_bioyodie_meta(cfg)
    log.info("Done.")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
