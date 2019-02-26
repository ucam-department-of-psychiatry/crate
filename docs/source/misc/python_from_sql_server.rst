.. crate_anon/docs/source/misc/python_from_sql_server.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
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

.. _pandas: https://pandas.pydata.org/


Calling Python from SQL Server
==============================

Prerequisites
-------------

- SQL Server, obviously. See
  https://www.microsoft.com/sql-server/sql-server-downloads.

- SQL Server 2017 Machine Learning Services; see
  https://docs.microsoft.com/en-us/sql/advanced-analytics/install/sql-machine-learning-services-windows-install?view=sql-server-2017.

  - Once you have SQL Server 2017 installed, run "SQL Server Installation
    Center".

    - If it appears to be missing run it as e.g.
      ``C:\SQLServer2017Media\Developer_ENU\setup.exe``.

  - Choose :menuselection:`Installation --> New SQL Server stand-alone
    installation or add features to an existing installation`.

    - If you think you don't have the media that it asks for because you used
      an online installer... re-run that installer; be reminded that it saved
      everything (by default) to ``C:\SQLServer2017Media``; provide that as the
      location! In this situation, the folder you need is e.g.
      ``C:\SQLServer2017Media\Developer_ENU`` (for an English Developer
      edition).

  - Click through. When you get to a choice of performing a new installation or
    adding features to an existing instance, choose the latter.

  - Add ``Machine Learning Services / Python``, and while we're at it,
    ``Machine Learning Services / R``. And since it sounds interesting,
    ``Full-Text and Semantic Extractions for Search``. You probably want to add
    them as "instance features".

  - Accept some license terms and put the coffee on.

Basic communication with Python
-------------------------------

Check Python is installed and SQL Server can talk to it; see
https://docs.microsoft.com/en-us/sql/advanced-analytics/tutorials/quickstart-python-verify?view=sql-server-2017

- Run SQL Server Management Studio, connect to your server, and try the
  following script:

  .. code-block:: sql

    EXECUTE sp_execute_external_script @language = N'Python', @script = N'
    import sys
    print(sys.version)
    ';
    GO

- If you get this:

  .. code-block:: none

    Msg 39023, Level 16, State 1, Procedure sp_execute_external_script, Line 1
    [Batch Start Line 0]

    'sp_execute_external_script' is disabled on this instance of SQL Server.
    Use sp_configure 'external scripts enabled' to enable it.

  then, as per
  https://docs.microsoft.com/en-us/sql/database-engine/configure-windows/external-scripts-enabled-server-configuration-option?view=sql-server-2017:

  #. Execute

     .. code-block:: sql

        sp_configure 'external scripts enabled', 1;
        RECONFIGURE WITH OVERRIDE;

  #. Restart SQL Server (via Windows Services).

.. tip::

    As and when you restart SQL Server, restart "SQL Server Launchpad
    (MSSQLSERVER)".

- Note the version of Python. In my case the result was this:

  .. code-block:: none

    STDOUT message(s) from external script:
    3.5.2 |Continuum Analytics, Inc.| (default, Jul  5 2016, 11:41:13) [MSC v.1900 64 bit (AMD64)]

  so this is a custom version of Python 3.5.2.

Install some external Python code
---------------------------------

It looks like we can't have arbitrary multiple virtual environments. But there
is one virtual environment. This is implied by
https://docs.microsoft.com/en-us/sql/advanced-analytics/python/install-additional-python-packages-on-sql-server?view=sql-server-2017.
So to install something using ``pip``, run an **administrative**-authority
command prompt (because we are going to be modifying files that live within
the ``C:\Program Files`` tree), then:

.. code-block:: bat

    cd C:\Program Files\Microsoft SQL Server\MSSQL14.MSSQLSERVER\PYTHON_SERVICES\Scripts
    pip install --upgrade pip
    pip install cardinal_pythonlib

You may need to stop SQL Server first [the service named "SQL Server
(MSSQLSERVER)"] to prevent further "access denied" errors. But if you have used
an administrative command prompt *and* stopped the SQL Server first, I don't
know why it complains; just repeat the command that failed.

Now try this:

.. code-block:: sql

    EXECUTE sp_execute_external_script @language = N'Python', @script = N'

    from cardinal_pythonlib.psychiatry.drugs import (
        drug_name_to_generic,
        drug_names_to_generic
    )
    # You cannot do "import *"; it says "import * only allowed at module level"
    # Watch out: no unescaped apostrophes within the Python code!

    print(drug_name_to_generic("UNKNOWN"))
    print(drug_name_to_generic("UNKNOWN", unknown_to_default=True))
    print(drug_names_to_generic([
        "citalopram", "Citalopram", "Cipramil", "Celexa",
        "olanzepine",  # typo
        "dextroamphetamine",
        "amitryptyline",
    ]))

    ';
    GO

See what packages are installed locally
---------------------------------------

See https://docs.microsoft.com/en-us/sql/advanced-analytics/tutorials/quickstart-python-verify?view=sql-server-2017.
Specifically:

.. code-block:: sql

    EXECUTE sp_execute_external_script @language =N'Python', @script=N'
    import pip
    for i in pip.get_installed_distributions():
        print(i)
    ';
    GO

You should see packages that you installed above.

Structured data flow
--------------------

Let's go beyond stdout and have data flow from an SQL Server table to Python,
and back from Python to a result set (or another table).

See https://docs.microsoft.com/en-us/sql/advanced-analytics/tutorials/quickstart-python-inputs-and-outputs?view=sql-server-2017.

The basic messages are as follows:

- By default, SQL Server translates the parameter called ``@input_data_1`` into
  a Python variable called ``InputDataSet``, runs the Python, and then
  translates the Python variable called ``OutputDataSet`` into an SQL result
  set, according to a schema that you specify with the ``WITH RESULT SETS``
  clause.

- The data format on the Python side is a pandas_ data frame.

- So the basic setup is:

  .. code-block:: sql

    EXECUTE sp_execute_external_script
        @language = N'Python'
        , @script = N'

    # PYTHON CODE

    from somewhere import somefunc

    OutputDataSet = somefunc(InputDataSet)

        '
        , @input_data_1 = N'

    -- SOURCE SQL

    SELECT * FROM sometable;

        '
        WITH RESULT SETS (

            -- DEFINE OUTPUT DATA FORMAT HERE
            (  -- first (and in this case only) result set definition
                [first_column] INT NOT NULL,
                [second_column] NVARCHAR(MAX)
                -- etc.
            )
        );

- The ``WITH RESULT SETS`` syntax is described at
  https://docs.microsoft.com/en-us/sql/t-sql/language-elements/execute-transact-sql?view=sql-server-2017.

- You can rename the input/output parameters if you wish.

Example to find two antidepressants "episodes"
----------------------------------------------

- We'll use an algorithm from our core Python assistance library, described at
  https://cardinalpythonlib.readthedocs.io/.

- Create a dummy table and some **test data**:

  .. code-block:: sql

    USE rnctestdb;  -- or whatever it's called
    -- DROP TABLE dummy_drug_data;
    CREATE TABLE dummy_drug_data (
        brcid VARCHAR(255) NOT NULL,  -- or INT, etc....
        generic_drug VARCHAR(100) NOT NULL,
        document_date DATE NOT NULL
    );
    INSERT INTO dummy_drug_data
        (brcid, generic_drug, document_date) VALUES
        -- Bob: mixture switch; should pick mirtaz -> sert
        ('Bob', 'venlafaxine', '2018-01-01'),
        ('Bob', 'mirtazapine', '2018-01-01'),
        ('Bob', 'venlafaxine', '2018-02-01'),
        ('Bob', 'mirtazapine', '2018-02-01'),
        ('Bob', 'venlafaxine', '2018-03-01'),
        ('Bob', 'sertraline', '2018-03-02'),
        ('Bob', 'venlafaxine', '2018-04-01'),
        ('Bob', 'sertraline', '2018-05-01'),
        ('Bob', 'sertraline', '2018-06-01'),
        -- Alice: two consecutive switches; should pick the first, c -> f
        -- ... goes second in the data; should be sorted to first
        ('Alice', 'citalopram', '2018-01-01'),
        ('Alice', 'citalopram', '2018-02-01'),
        ('Alice', 'fluoxetine', '2018-03-01'),
        ('Alice', 'fluoxetine', '2018-04-01'),
        ('Alice', 'mirtazapine', '2018-05-01'),
        ('Alice', 'mirtazapine', '2018-06-01'),
        -- Chloe: courses just too short; should give nothing
        ('Chloe', 'fluoxetine', '2018-01-01'),
        ('Chloe', 'fluoxetine', '2018-01-27'),
        ('Chloe', 'venlafaxine', '2018-02-01'),
        ('Chloe', 'venlafaxine', '2018-01-27'),
        -- Dave: courses just long enough
        ('Dave', 'fluoxetine', '2018-01-01'),
        ('Dave', 'fluoxetine', '2018-01-28'),
        ('Dave', 'venlafaxine', '2018-02-01'),
        ('Dave', 'venlafaxine', '2018-02-28'),
        -- Elsa: courses overlap; invalid
        ('Elsa', 'citalopram', '2018-01-01'),
        ('Elsa', 'citalopram', '2018-02-05'),
        ('Elsa', 'mirtazapine', '2018-02-01'),
        ('Elsa', 'mirtazapine', '2018-02-28'),
        -- Fred: courses overlap, same day; invalid
        ('Fred', 'citalopram', '2018-01-01'),
        ('Fred', 'citalopram', '2018-02-01'),
        ('Fred', 'mirtazapine', '2018-02-01'),
        ('Fred', 'mirtazapine', '2018-02-28'),
        -- Grace: multiple potentials; should pick 'citalopram' -> 'fluoxetine'
        ('Grace', 'citalopram', '2018-01-01'),
        ('Grace', 'citalopram', '2018-01-28'),
        ('Grace', 'fluoxetine', '2018-02-01'),
        ('Grace', 'venlafaxine', '2018-02-02'),
        ('Grace', 'fluoxetine', '2018-02-28'),
        ('Grace', 'venlafaxine', '2018-03-01'),
        ('Grace', 'mirtazapine', '2018-04-01'),
        ('Grace', 'mirtazapine', '2018-04-28');
    GO

- Debug the input:

  .. code-block:: sql

    USE rnctestdb;  -- or whatever it's called
    EXECUTE sp_execute_external_script
        @language = N'Python'
        , @script = N'
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Start Python
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    print(repr(InputDataSet))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # End Python
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '
        , @input_data_1 = N'SELECT * FROM dummy_drug_data;'
        ;

- Discover that dates are not acceptable...

  .. code-block:: none

    Unsupported input data type in column 'document_date'.  Supported types:
    bit, tinyint, smallint, int, bigint, uniqueidentifier, real, float, char,
    varchar, nchar, nvarchar, varbinary.

    SqlSatelliteCall error: Unsupported input data type in column
    'document_date'.  Supported types: bit, tinyint, smallint, int, bigint,
    uniqueidentifier, real, float, char, varchar, nchar, nvarchar, varbinary.

  See https://docs.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-execute-external-script-transact-sql?view=sql-server-2017,
  only that suggests that ``DATE`` and ``DATETIME`` should be OK. Clearly they
  aren't.

- Check that data is coming in once converted via ``CAST``:

  .. code-block:: sql

    USE rnctestdb;  -- or whatever it's called
    EXECUTE sp_execute_external_script
        @language = N'Python'
        , @script = N'
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Start Python
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    print(repr(InputDataSet))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # End Python
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '
        , @input_data_1 = N'
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- Start source SQL
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    SELECT
        brcid,
        generic_drug,
        CAST(document_date AS VARCHAR(10)) AS document_date
    FROM dummy_drug_data;

    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- End source SQL
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ';

- **Final query.** Process it properly, including converting that column back
  to a date on the Python side. We'll also create it as a stored procedure
  called ``py_generate_two_antidepressant_episodes``, which will allow us to
  view the result directly or stash it back into a table:

  .. code-block:: none

    USE rnctestdb;  -- or whatever it's called

    DROP PROCEDURE IF EXISTS [dbo].[py_generate_two_antidepressant_episodes];
    GO

    CREATE PROCEDURE [dbo].[py_generate_two_antidepressant_episodes] AS
    BEGIN

    EXECUTE sp_execute_external_script
        @language = N'Python'
        , @script = N'
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Start Python
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Imports
    import logging
    import sys
    from cardinal_pythonlib.psychiatry.treatment_resistant_depression import (
        two_antidepressant_episodes,
    )
    import pandas as pd

    # Constants governing our algorithm
    COURSE_LENGTH_DAYS = 28
    EXPECT_RESPONSE_BY_DAYS = 56
    SYMPTOM_ASSESSMENT_TIME_DAYS = 180

    # Make Python log output go to stdout as well as stderr
    SHOW_LOG_OUTPUT = True
    VERBOSE = True
    if SHOW_LOG_OUTPUT:
        loglevel = logging.DEBUG if VERBOSE else logging.INFO
        rootlog = logging.getLogger()
        rootlog.setLevel(loglevel)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(loglevel)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        rootlog.addHandler(handler)

    # Convert date-as-text columns to proper dates
    InputDataSet["document_date"] = pd.to_datetime(
        InputDataSet["document_date"], format="%Y-%m-%d"
    )

    # Run our algorithm of interest
    result = two_antidepressant_episodes(
        patient_drug_date_df = InputDataSet,  # data in here
        patient_colname = "brcid",
        drug_colname = "generic_drug",
        date_colname = "document_date",
        course_length_days = COURSE_LENGTH_DAYS,
        expect_response_by_days = EXPECT_RESPONSE_BY_DAYS,
        symptom_assessment_time_days = SYMPTOM_ASSESSMENT_TIME_DAYS
    )

    # We cannot send dates back out to SQL, so convert to standard text format:
    for datecolname in ["drug_a_first", "drug_a_second",
                        "drug_b_first", "drug_b_second",
                        "expect_response_to_b_by", "end_of_symptom_period"]:
        result[datecolname] = result[datecolname].dt.strftime("%Y-%m-%d")

    # Give the final result set its expected name
    OutputDataSet = result

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # End Python
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '
        , @input_data_1 = N'
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- Start source SQL
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    SELECT
        brcid,
        generic_drug,
        CAST(document_date AS VARCHAR(10)) AS document_date  -- YYYY-MM-DD
    FROM dummy_drug_data;

    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- End source SQL
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '
        WITH RESULT SETS (
            (
                -- Python uses Unicode strings, therefore NVARCHAR.
                [patient_id] NVARCHAR(255) NOT NULL,
                [drug_a_name] NVARCHAR(255),
                [drug_a_first] DATE,
                [drug_a_second] DATE,
                [drug_b_name] NVARCHAR(255),
                [drug_b_first] DATE,
                [drug_b_second] DATE,
                [expect_response_to_b_by] DATE,
                [end_of_symptom_period] DATE
            )
        )

    END;
    GO

- Create a table to receive results:

  .. code-block:: sql

    USE rnctestdb;  -- or whatever it's called
    -- DROP TABLE two_antidepressant_results;
    CREATE TABLE two_antidepressant_results (
        [patient_id] NVARCHAR(255) NOT NULL,
        [drug_a_name] NVARCHAR(255),
        [drug_a_first] DATE,
        [drug_a_second] DATE,
        [drug_b_name] NVARCHAR(255),
        [drug_b_first] DATE,
        [drug_b_second] DATE,
        [expect_response_to_b_by] DATE,
        [end_of_symptom_period] DATE
    );

- If we want to view the results, we can do this:

  .. code-block:: sql

    USE rnctestdb;  -- or whatever it's called
    EXEC [dbo].[py_generate_two_antidepressant_episodes]

- If we want to stash the results, we can do this:

  .. code-block:: sql

    USE rnctestdb;  -- or whatever it's called
    -- DELETE FROM two_antidepressant_results
    INSERT INTO two_antidepressant_results
    EXEC [dbo].[py_generate_two_antidepressant_episodes]
