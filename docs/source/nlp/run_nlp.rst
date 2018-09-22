.. crate_anon/docs/source/nlp/run_nlp.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

Run the NLP
-----------

Now you've created and edited your config file, you can run the NLP process in
one of the following ways:

.. code-block:: bash

    crate_nlp --nlpdef NLP_NAME --incremental
    crate_nlp --nlpdef NLP_NAME --full
    crate_nlp_multiprocess --nlpdef NLP_NAME --incremental
    crate_nlp_multiprocess --nlpdef NLP_NAME --full

where `NLP_NAME` is something you’ve configured in the :ref:`NLP config file
<nlp_config>` (e.g. a drug-parsing NLP program or the GATE demonstration
name/location NLP app). Use

The ‘multiprocess’ versions are faster (if you have a multi-core/-CPU
computer). The ‘full’ option destroys the destination database and starts
again. The ‘incremental’ one brings the destination database up to date
(creating it if necessary). The default is ‘incremental’, for safety reasons.

Get more help with

.. code-block:: bash

    crate_nlp --help


crate_nlp
~~~~~~~~~

This runs a single-process NLP controller.

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_nlp [-h] [--version] [--config CONFIG] [--verbose]
                     [--nlpdef [NLPDEF]] [--report_every_fast [REPORT_EVERY_FAST]]
                     [--report_every_nlp [REPORT_EVERY_NLP]]
                     [--chunksize [CHUNKSIZE]] [--process [PROCESS]]
                     [--nprocesses [NPROCESSES]] [--processcluster PROCESSCLUSTER]
                     [--democonfig] [--listprocessors] [--describeprocessors]
                     [--showinfo [NLP_CLASS_NAME]] [--count] [-i | -f]
                     [--dropremake] [--skipdelete] [--nlp] [--echo] [--timing]

    NLP manager. Version 0.18.12 (2017-02-26). By Rudolf Cardinal.

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      --config CONFIG       Config file (overriding environment variable
                            CRATE_NLP_CONFIG)
      --verbose, -v         Be verbose (use twice for extra verbosity)
      --nlpdef [NLPDEF]     NLP definition name (from config file)
      --report_every_fast [REPORT_EVERY_FAST]
                            Report insert progress (for fast operations) every n
                            rows in verbose mode (default 100000)
      --report_every_nlp [REPORT_EVERY_NLP]
                            Report progress for NLP every n rows in verbose mode
                            (default 500)
      --chunksize [CHUNKSIZE]
                            Number of records copied in a chunk when copying PKs
                            from one database to another (default 100000)
      --process [PROCESS]   For multiprocess mode: specify process number
      --nprocesses [NPROCESSES]
                            For multiprocess mode: specify total number of
                            processes (launched somehow, of which this is to be
                            one)
      --processcluster PROCESSCLUSTER
                            Process cluster name
      --democonfig          Print a demo config file
      --listprocessors      Show possible built-in NLP processor names
      --describeprocessors  Show details of built-in NLP processors
      --showinfo [NLP_CLASS_NAME]
                            Show detailed information for a parser
      --count               Count records in source/destination databases, then
                            stop
      -i, --incremental     Process only new/changed information, where possible
                            (* default)
      -f, --full            Drop and remake everything
      --dropremake          Drop/remake destination tables only
      --skipdelete          For incremental updates, skip deletion of rows present
                            in the destination but not the source
      --nlp                 Perform NLP processing only
      --echo                Echo SQL
      --timing              Show detailed timing breakdown

Current NLP processors
~~~~~~~~~~~~~~~~~~~~~~

NLP processors as of 2017-02-28 (from ``crate_nlp --describeprocessors``):

.. code-block:: none

    +---------------------------------+---------------------------------------------------------------------------------+
    | NLP name                        | Description                                                                     |
    +---------------------------------+---------------------------------------------------------------------------------+
    | Ace                             | Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III).                      |
    | AceValidator                    | Validator for Ace (see ValidatorBase for explanation).                          |
    | Basophils                       | Basophil count (absolute).                                                      |
    | BasophilsValidator              | Validator for Basophils (see ValidatorBase for explanation).                    |
    | Bmi                             | Body mass index (in kg / m^2).                                                  |
    | BmiValidator                    | Validator for Bmi (see ValidatorBase for explanation).                          |
    | Bp                              | Blood pressure, in mmHg. (Since we produce two variables, SBP and DBP,          |
    |                                 |     and we use something a little more complex than                             |
    |                                 |     NumeratorOutOfDenominatorParser, we subclass BaseNlpParser directly.)       |
    | BpValidator                     | Validator for Bp (see ValidatorBase for explanation).                           |
    | Crp                             | C-reactive protein.                                                             |
    |                                 |                                                                                 |
    |                                 |     CRP units:                                                                  |
    |                                 |     - mg/L is commonest in the UK (or at least standard at Addenbrooke's,       |
    |                                 |       Hinchingbrooke, and Dundee)                                               |
    |                                 |     - values of <=6 mg/L or <10 mg/L are normal, and e.g. 70-250 mg/L in        |
    |                                 |       pneumonia.                                                                |
    |                                 |     - Refs include:                                                             |
    |                                 |             http://www.ncbi.nlm.nih.gov/pubmed/7705110                          |
    |                                 |             http://emedicine.medscape.com/article/2086909-overview              |
    |                                 |     - 1 mg/dL = 10 mg/L                                                         |
    |                                 |         ... so normal in mg/dL is <=1 roughly.                                  |
    |                                 |                                                                                 |
    | CrpValidator                    | Validator for CRP (see ValidatorBase for explanation).                          |
    | Eosinophils                     | Eosinophil count (absolute).                                                    |
    | EosinophilsValidator            | Validator for Eosinophils (see ValidatorBase for explanation).                  |
    | Esr                             | Erythrocyte sedimentation rate (ESR).                                           |
    | EsrValidator                    | Validator for Esr (see ValidatorBase for explanation).                          |
    | Gate                            | Class controlling an external process, typically our Java interface to          |
    |                                 |     GATE programs, CrateGatePipeline.java (but it could be any external         |
    |                                 |     program).                                                                   |
    |                                 |                                                                                 |
    |                                 |     We send text to it, it parses the text, and it sends us back results, which |
    |                                 |     we return as dictionaries. The specific text sought depends on the          |
    |                                 |     configuration file and the specific GATE program used.                      |
    |                                 |                                                                                 |
    |                                 |     PROBLEM when attempting to use KConnect (Bio-YODIE): its source code is     |
    |                                 |     riddled with direct calls to System.out.println().                          |
    |                                 |                                                                                 |
    |                                 |     POTENTIAL SOLUTIONS                                                         |
    |                                 |     - named pipes:                                                              |
    |                                 |         os.mkfifo() - Unix only.                                                |
    |                                 |         win32pipe - http://stackoverflow.com/questions/286614                   |
    |                                 |     - ZeroMQ with some sort of security                                         |
    |                                 |         - pip install zmq                                                       |
    |                                 |         - some sort of Java binding (jzmq, jeromq...)                           |
    |                                 |     - redirect stdout in our Java handler                                       |
    |                                 |         System.setOut()                                                         |
    |                                 |         ... yes, that works.                                                    |
    |                                 |                                                                                 |
    | Height                          | Height. Handles metric and imperial.                                            |
    | HeightValidator                 | Validator for Height (see ValidatorBase for explanation).                       |
    | Lymphocytes                     | Lymphocyte count (absolute).                                                    |
    | LymphocytesValidator            | Validator for Lymphocytes (see ValidatorBase for explanation).                  |
    | Medex                           | Class controlling a Medex-UIMA external process, via our custom                 |
    |                                 |     Java interface, CrateMedexPipeline.java.                                    |
    |                                 |                                                                                 |
    | MiniAce                         | Mini-Addenbrooke's Cognitive Examination (M-ACE).                               |
    | MiniAceValidator                | Validator for MiniAce (see ValidatorBase for explanation).                      |
    | Mmse                            | Mini-mental state examination (MMSE).                                           |
    | MmseValidator                   | Validator for Mmse (see ValidatorBase for explanation).                         |
    | Moca                            | Montreal Cognitive Assessment (MOCA).                                           |
    | MocaValidator                   | Validator for MiniAce (see ValidatorBase for explanation).                      |
    | Monocytes                       | Monocyte count (absolute).                                                      |
    | MonocytesValidator              | Validator for Monocytes (see ValidatorBase for explanation).                    |
    | Neutrophils                     | Neutrophil count (absolute).                                                    |
    | NeutrophilsValidator            | Validator for Neutrophils (see ValidatorBase for explanation).                  |
    | NumeratorOutOfDenominatorParser | Base class for X-out-of-Y numerical results, e.g. for MMSE/ACE.                 |
    |                                 |     Integer denominator, expected to be positive.                               |
    |                                 |     Otherwise similar to SimpleNumericalResultParser.                           |
    | NumericalResultParser           | DO NOT USE DIRECTLY. Base class for generic numerical results, where            |
    |                                 |     a SINGLE variable is produced.                                              |
    | SimpleNumericalResultParser     | Base class for simple single-format numerical results. Use this when            |
    |                                 |     not only do you have a single variable to produce, but you have a single    |
    |                                 |     regex (in a standard format) that can produce it.                           |
    | Sodium                          | Sodium (Na).                                                                    |
    | SodiumValidator                 | Validator for Sodium (see ValidatorBase for explanation).                       |
    | Tsh                             | Thyroid-stimulating hormone (TSH).                                              |
    | TshValidator                    | Validator for TSH (see ValidatorBase for explanation).                          |
    | ValidatorBase                   | DO NOT USE DIRECTLY. Base class for validating regex parser sensitivity.        |
    |                                 |     The validator will find fields that refer to the variable, whether or not   |
    |                                 |     they meet the other criteria of the actual NLP processors (i.e. whether or  |
    |                                 |     not they contain a valid value). More explanation below.                    |
    |                                 |                                                                                 |
    |                                 |     Suppose we're validating C-reactive protein (CRP). Key concepts:            |
    |                                 |         - source (true state of the world): Pr present, Ab absent               |
    |                                 |         - software decision: Y yes, N no                                        |
    |                                 |         - signal detection theory classification:                               |
    |                                 |             hit = Pr & Y = true positive                                        |
    |                                 |             miss = Pr & N = false negative                                      |
    |                                 |             false alarm = Ab & Y = false positive                               |
    |                                 |             correct rejection = Ab & N = true negative                          |
    |                                 |         - common SDT metrics:                                                   |
    |                                 |             positive predictive value, PPV = P(Pr | Y) = precision (*)          |
    |                                 |             negative predictive value, NPV = P(Ab | N)                          |
    |                                 |             sensitivity = P(Y | Pr) = recall (*) = true positive rate           |
    |                                 |             specificity = P(N | Ab) = true negative rate                        |
    |                                 |             (*) common names used in the NLP context.                           |
    |                                 |         - other common classifier metric:                                       |
    |                                 |             F_beta score = (1 + beta^2) * precision * recall /                  |
    |                                 |                            ((beta^2 * precision) + recall)                      |
    |                                 |             ... which measures performance when you value recall beta times as  |
    |                                 |             much as precision; e.g. the F1 score when beta = 1. See             |
    |                                 |             https://en.wikipedia.org/wiki/F1_score                              |
    |                                 |                                                                                 |
    |                                 |     Working from source to NLP, we can see there are a few types of "absent":   |
    |                                 |         - X. unselected database field containing text                          |
    |                                 |             - Q. field contains "CRP", "C-reactive protein", etc.; something    |
    |                                 |                 that a human (or as a proxy: a machine) would judge as          |
    |                                 |                 containing a textual reference to CRP.                          |
    |                                 |                 - Pr. Present: a human would judge that a CRP value is present, |
    |                                 |                     e.g. "today her CRP is 7, which I am not concerned about."  |
    |                                 |                     - H.  Hit: software reports the value.                      |
    |                                 |                     - M.  Miss: software misses the value.                      |
    |                                 |                         (maybe: "his CRP was twenty-one".)                      |
    |                                 |                 - Ab1. Absent: reference to CRP, but no numerical information,  |
    |                                 |                     e.g. "her CRP was normal".                                  |
    |                                 |                     - FA1. False alarm: software reports a numerical value.     |
    |                                 |                         (maybe: "my CRP was 7 hours behind my boss's deadline") |
    |                                 |                     - CR1. Correct rejection: software doesn't report a value.  |
    |                                 |             - Ab2. field contains no reference to CRP at all.                   |
    |                                 |                     - FA2. False alarm: software reports a numerical value.     |
    |                                 |                         (a bit hard to think of examples...)                    |
    |                                 |                     - CR2. Correct rejection: software doesn't report a value.  |
    |                                 |                                                                                 |
    |                                 |     From NLP backwards to source:                                               |
    |                                 |         - Y. Software says value present.                                       |
    |                                 |             - H. Hit: value is present.                                         |
    |                                 |             - FA. False alarm: value is absent.                                 |
    |                                 |         - N. Software says value absent.                                        |
    |                                 |             - CR. Correct rejection: value is absent.                           |
    |                                 |             - M. Miss: value is present.                                        |
    |                                 |                                                                                 |
    |                                 |     The key metrics are:                                                        |
    |                                 |         - precision = positive predictive value = P(Pr | Y)                     |
    |                                 |             ... relatively easy to check; find all the "Y" records and check    |
    |                                 |             manually that they're correct.                                      |
    |                                 |         - sensitivity = recall = P(Y | Pr)                                      |
    |                                 |             ... Here, we want a sample that is enriched for "symptom actually   |
    |                                 |             present", for human reasons. For example, if 0.1% of text entries   |
    |                                 |             refer to CRP, then to assess 100 "Pr" samples we would have to      |
    |                                 |             review 100,000 text records, 99,900 of which are completely         |
    |                                 |             irrelevant. So we want an automated way of finding "Pr" records.    |
    |                                 |             That's what the validator classes do.                               |
    |                                 |                                                                                 |
    |                                 |     You can enrich for "Pr" records with SQL, e.g.                              |
    |                                 |         SELECT textfield FROM sometable WHERE (                                 |
    |                                 |             textfield LIKE '%CRP%'                                              |
    |                                 |             OR textfield LIKE '%C-reactive protein%');                          |
    |                                 |     or similar, but really we want the best "CRP detector" possible. That is    |
    |                                 |     probably to use a regex, either in SQL (... "WHERE textfield REGEX          |
    |                                 |     'myregex'") or using these validator classes. (The main NLP regexes don't   |
    |                                 |     distinguish between "CRP present, no valid value" and "CRP absent",         |
    |                                 |     because regexes either match or don't.)                                     |
    |                                 |                                                                                 |
    |                                 |     Each validator class implements the core variable-finding part of its       |
    |                                 |     corresponding NLP regex class, but without the value or units. For example, |
    |                                 |     the CRP class looks for things like "CRP is 6" or "CRP 20 mg/L", whereas    |
    |                                 |     the CRP validator looks for things like "CRP".                              |
    |                                 |                                                                                 |
    | Wbc                             | White cell count (WBC, WCC).                                                    |
    | WbcBase                         | DO NOT USE DIRECTLY. White cell count base class.                               |
    | WbcValidator                    | Validator for Wbc (see ValidatorBase for explanation).                          |
    | Weight                          | Weight. Handles metric and imperial.                                            |
    | WeightValidator                 | Validator for Weight (see ValidatorBase for explanation).                       |
    +---------------------------------+---------------------------------------------------------------------------------+

crate_nlp_multiprocess
~~~~~~~~~~~~~~~~~~~~~~

This program runs multiple copies of ``crate_nlp`` in parallel.

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_nlp_multiprocess [-h] --nlpdef NLPDEF [--nproc [NPROC]]
                                  [--verbose]

    Runs the CRATE NLP manager in parallel. Version 0.18.12 (2017-02-26). Note
    that all arguments not specified here are passed to the underlying script (see
    crate_nlp --help).

    optional arguments:
      -h, --help            show this help message and exit
      --nlpdef NLPDEF       NLP processing name, from the config file
      --nproc [NPROC], -n [NPROC]
                            Number of processes (default on this machine: 8)
      --verbose, -v         Be verbose
