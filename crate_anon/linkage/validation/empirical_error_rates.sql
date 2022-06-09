-- Anonymous queries for empirical error rates: RiO/SystmOne symmetrically.

-- ============================================================================
-- If two people are the same (by NHS#), how often are DOBs different?
-- ============================================================================

SELECT
    COUNT(*) AS n_people,  -- 126904
    SUM(
        IIF(sp.DOB IS NULL OR rc.DateOfBirth IS NULL, 1, 0)
    ) AS n_either_dob_missing,  -- 0
    SUM(
        IIF(CAST(sp.DOB AS DATE) != CAST(rc.DateOfBirth AS DATE), 1, 0)
    ) AS n_dob_mismatch,  -- 624 = 0.004917103 of people
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- Out by one:
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUM(
        IIF(
            (
                (
                    DAY(sp.DOB) = DAY(rc.DateOfBirth) + 1
                    OR DAY(sp.DOB) = DAY(rc.DateOfBirth) - 1
                )
                AND MONTH(sp.DOB) = MONTH(rc.DateOfBirth)
                AND YEAR(sp.DOB) = YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_day_out_by_one,  -- 74
    SUM(
        IIF(
            (
                DAY(sp.DOB) = DAY(rc.DateOfBirth)
                AND (
                    MONTH(sp.DOB) = MONTH(rc.DateOfBirth) + 1
                    OR MONTH(sp.DOB) = MONTH(rc.DateOfBirth) - 1
                )
                AND YEAR(sp.DOB) = YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_month_out_by_one,  -- 64
    SUM(
        IIF(
            (
                DAY(sp.DOB) = DAY(rc.DateOfBirth)
                AND MONTH(sp.DOB) = MONTH(rc.DateOfBirth)
                AND (
                    YEAR(sp.DOB) = YEAR(rc.DateOfBirth) + 1
                    OR YEAR(sp.DOB) = YEAR(rc.DateOfBirth) - 1
                )
            ),
            1,
            0
        )
    ) AS n_dob_year_out_by_one,  -- 55
    -- ... so those three types of error together are 0.001520835
    -- ... and represent 30.9% of DOB errors
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- Out by two:
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUM(
        IIF(
            (
                (
                    DAY(sp.DOB) = DAY(rc.DateOfBirth) + 2
                    OR DAY(sp.DOB) = DAY(rc.DateOfBirth) - 2
                )
                AND MONTH(sp.DOB) = MONTH(rc.DateOfBirth)
                AND YEAR(sp.DOB) = YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_day_out_by_two,  -- 41
    SUM(
        IIF(
            (
                DAY(sp.DOB) = DAY(rc.DateOfBirth)
                AND (
                    MONTH(sp.DOB) = MONTH(rc.DateOfBirth) + 2
                    OR MONTH(sp.DOB) = MONTH(rc.DateOfBirth) - 2
                )
                AND YEAR(sp.DOB) = YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_month_out_by_two,  -- 33
    SUM(
        IIF(
            (
                DAY(sp.DOB) = DAY(rc.DateOfBirth)
                AND MONTH(sp.DOB) = MONTH(rc.DateOfBirth)
                AND (
                    YEAR(sp.DOB) = YEAR(rc.DateOfBirth) + 2
                    OR YEAR(sp.DOB) = YEAR(rc.DateOfBirth) - 2
                )
            ),
            1,
            0
        )
    ) AS n_dob_year_out_by_two,  -- 18
    --- ... so out-by-two errors represent 14.7% of DOB errors
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- One-component mismatch:
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUM(
        IIF(
            (
                DAY(sp.DOB) != DAY(rc.DateOfBirth)
                AND MONTH(sp.DOB) = MONTH(rc.DateOfBirth)
                AND YEAR(sp.DOB) = YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_day_mismatch,  -- 274
    SUM(
        IIF(
            (
                DAY(sp.DOB) = DAY(rc.DateOfBirth)
                AND MONTH(sp.DOB) != MONTH(rc.DateOfBirth)
                AND YEAR(sp.DOB) = YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_month_mismatch,  -- 172
    SUM(
        IIF(
            (
                DAY(sp.DOB) = DAY(rc.DateOfBirth)
                AND MONTH(sp.DOB) = MONTH(rc.DateOfBirth)
                AND YEAR(sp.DOB) != YEAR(rc.DateOfBirth)
            ),
            1,
            0
        )
    ) AS n_dob_year_mismatch  -- 136
    -- ... so single-component errors account for 0.9326923 (93%) of DOB errors
FROM
    RiO62CAMLive.dbo.Client AS rc
INNER JOIN
    SystmOne.dbo.S1_Patient AS sp
    ON TRY_CAST(sp.NHSNumber AS BIGINT) = TRY_CAST(rc.NNN AS BIGINT)
    -- NHS number match. (NULL values will be excluded by the INNER JOIN.)
    -- Neither NHS number has spaces in (empirically).
WHERE
    -- Exclude test NHS numbers, which start 999:
    LEFT(sp.NHSNumber, 3) != '999'


-- ============================================================================
-- Where DOBs don't match, how far out are they? Also, transposition errors.
-- ============================================================================

SELECT
    COUNT(*) AS n_dob_mismatch,  -- 624
    AVG(
        ABS(
            DATEDIFF(DAY, CAST(sp.DOB AS DATE), CAST(rc.DateOfBirth AS DATE))
        )
    ) AS mean_abs_dob_diff_days,  -- 772
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- Transposition:
    -- ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    -- If you treat a date as a string, it automatically uses YYYY-MM-DD.
    -- You can also treat a number as a string, e.g. with DAY(), but 7 will
    -- become '7'. But not a DATE, somehow.
    -- Syntax: SUBSTRING(string, start_from_1, length).
    -- The RiO DOB field is DATETIME, as is the SystmOne field.
    -- Lots of ways to convert DATETIME to the right format. FORMAT is good.
    -- The precondition for all of these is that the DOBs don't match (or
    -- we will erroneously think e.g. that day=22 must be a transposition
    -- error).
    SUM(
        IIF(
            (
                (
                    FORMAT(sp.DOB, 'yyyyMMdd') =
                    FORMAT(rc.DateOfBirth, 'yyyyMM') +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'dd'), 2, 1) +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'dd'), 1, 1)
                )
                OR (
                    FORMAT(rc.DateOfBirth, 'yyyyMMdd') =
                    FORMAT(sp.DOB, 'yyyyMM') +
                    SUBSTRING(FORMAT(sp.DOB, 'dd'), 2, 1) +
                    SUBSTRING(FORMAT(sp.DOB, 'dd'), 1, 1)
                )
            ),
            1,
            0
        )
    ) AS n_dob_day_digits_transposition,  -- 8
    SUM(
        IIF(
            (
                (
                    FORMAT(sp.DOB, 'yyyyddMM') =
                    FORMAT(rc.DateOfBirth, 'yyyydd') +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'MM'), 2, 1) +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'MM'), 1, 1)
                )
                OR (
                    FORMAT(rc.DateOfBirth, 'yyyyddMM') =
                    FORMAT(sp.DOB, 'yyyydd') +
                    SUBSTRING(FORMAT(sp.DOB, 'MM'), 2, 1) +
                    SUBSTRING(FORMAT(sp.DOB, 'MM'), 1, 1)
                )
            ),
            1,
            0
        )
    ) AS n_dob_month_digits_transposition,  -- 7
    SUM(
        IIF(
            (
                (
                    FORMAT(sp.DOB, 'MMddyyyy') =
                    FORMAT(rc.DateOfBirth, 'MMdd') +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'yyyy'), 1, 2) +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'yyyy'), 4, 1) +
                    SUBSTRING(FORMAT(rc.DateOfBirth, 'yyyy'), 3, 1)
                )
                OR (
                    FORMAT(rc.DateOfBirth, 'MMddyyyy') =
                    FORMAT(sp.DOB, 'MMdd') +
                    SUBSTRING(FORMAT(sp.DOB, 'yyyy'), 1, 2) +
                    SUBSTRING(FORMAT(sp.DOB, 'yyyy'), 4, 1) +
                    SUBSTRING(FORMAT(sp.DOB, 'yyyy'), 3, 1)
                )
            ),
            1,
            0
        )
    ) AS n_dob_year_last_two_digits_transposition,  -- 2
    -- ... so digit transpositions account for 0.02724359 of DOB mismatches.
    SUM(
        IIF(
            (
                (
                    FORMAT(sp.DOB, 'yyyyMMdd') =
                    FORMAT(rc.DateOfBirth, 'yyyydd') +
                    FORMAT(rc.DateOfBirth, 'MM')
                )
                OR (
                    FORMAT(rc.DateOfBirth, 'yyyyMMdd') =
                    FORMAT(sp.DOB, 'yyyydd') +
                    FORMAT(sp.DOB, 'MM')
                )
            ),
            1,
            0
        )
    ) AS n_dob_day_month_transposition  -- 3
FROM
    RiO62CAMLive.dbo.Client AS rc
INNER JOIN
    SystmOne.dbo.S1_Patient AS sp
    ON TRY_CAST(sp.NHSNumber AS BIGINT) = TRY_CAST(rc.NNN AS BIGINT)
    -- NHS number match. (NULL values will be excluded by the INNER JOIN.)
    -- Neither NHS number has spaces in (empirically).
WHERE
    -- Exclude test NHS numbers, which start 999:
    LEFT(sp.NHSNumber, 3) != '999'
    -- The precondition for all is a DOB mismatch:
    AND CAST(sp.DOB AS DATE) != CAST(rc.DateOfBirth AS DATE)


-- ============================================================================
-- Surname and forename mismatches. Also sex/gender.
-- ============================================================================

SELECT
    COUNT(*) AS n_people,  -- 126904
    SUM(
        IIF(
            (
                REPLACE(UPPER(rcn.GivenName1), ' ', '') !=
                    REPLACE(UPPER(sp.FirstName), ' ', '')
            ),
            1,
            0
        )
    ) AS n_forename_mismatch,  -- 2992
    SUM(
        IIF(
            (
                REPLACE(UPPER(rcn.Surname), ' ', '') !=
                    REPLACE(UPPER(sp.Surname), ' ', '')
            ),
            1,
            0
        )
    ) AS n_surname_mismatch,  -- 6166
    SUM(
        IIF(
            (
                REPLACE(UPPER(rcn.GivenName1), ' ', '') !=
                    REPLACE(UPPER(sp.FirstName), ' ', '')
                AND REPLACE(UPPER(rcn.Surname), ' ', '') !=
                    REPLACE(UPPER(sp.Surname), ' ', '')
            ),
            1,
            0
        )
    ) AS n_forename_and_surname_mismatch,  -- 560
    SUM(
        IIF(
            (
                -- Forename mismatch:
                REPLACE(UPPER(rcn.GivenName1), ' ', '') !=
                    REPLACE(UPPER(sp.FirstName), ' ', '')
                -- Surname mismatch:
                AND REPLACE(UPPER(rcn.Surname), ' ', '') !=
                    REPLACE(UPPER(sp.Surname), ' ', '')
                -- But forename/surname match, each way:
                AND REPLACE(UPPER(rcn.GivenName1), ' ', '') =
                    REPLACE(UPPER(sp.Surname), ' ', '')
                AND REPLACE(UPPER(rcn.Surname), ' ', '') =
                    REPLACE(UPPER(sp.FirstName), ' ', '')
            ),
            1,
            0
        )
    ) AS n_forename_and_surname_mismatch_transposed,  -- 98
    SUM(
        IIF(
            (
                CASE sp.Gender
                    WHEN 'F' THEN 'F'
                    WHEN 'M' THEN 'M'
                    WHEN 'I' THEN 'X'
                    ELSE NULL  -- unknown/NULL values become NULL
                END !=
                CASE rc.Gender
                    WHEN 'F' THEN 'F'
                    WHEN 'M' THEN 'M'
                    WHEN 'X' THEN 'X'
                    ELSE NULL  -- unknown/NULL values become NULL
                END
                -- If either is unknown and therefore NULL, the NULL = NULL
                -- test will give false (0), so these will not be counted.
            ),
            1,
            0
        )
    ) AS n_gender_mismatch,  -- 423
    SUM(
        IIF(
            (
                CASE sp.Gender
                    WHEN 'F' THEN 'F'
                    WHEN 'M' THEN 'M'
                    ELSE NULL
                END !=
                CASE rc.Gender
                    WHEN 'F' THEN 'F'
                    WHEN 'M' THEN 'M'
                    ELSE NULL
                END
            ),
            1,
            0
        )
    ) AS n_gender_mismatch_m_f_only  -- 367
FROM
    RiO62CAMLive.dbo.Client AS rc
INNER JOIN
    SystmOne.dbo.S1_Patient AS sp
    ON TRY_CAST(sp.NHSNumber AS BIGINT) = TRY_CAST(rc.NNN AS BIGINT)
    -- NHS number match. (NULL values will be excluded by the INNER JOIN.)
    -- Neither NHS number has spaces in (empirically).
INNER JOIN
    RiO62CAMLive.dbo.ClientName AS rcn
    ON rcn.ClientID = rc.ClientID
WHERE
    -- Exclude test NHS numbers, which start 999:
    LEFT(sp.NHSNumber, 3) != '999'
    -- Primary RiO name:
    AND rcn.EndDate IS NULL
    AND rcn.Deleted = 0
    AND rcn.AliasType = '1'  -- usual name


-- ============================================================================
-- Surname mismatches BY gender.
-- ============================================================================

SELECT
    rc.Gender AS rio_gender,
    sp.Gender AS systmone_gender,
    COUNT(*) AS n_people,  -- F 72958, M 53484
    SUM(
        IIF(
            (
                REPLACE(UPPER(rcn.Surname), ' ', '') !=
                    REPLACE(UPPER(sp.Surname), ' ', '')
            ),
            1,
            0
        )
    ) AS n_surname_mismatch  -- F 4947, M 1185
FROM
    RiO62CAMLive.dbo.Client AS rc
INNER JOIN
    SystmOne.dbo.S1_Patient AS sp
    ON TRY_CAST(sp.NHSNumber AS BIGINT) = TRY_CAST(rc.NNN AS BIGINT)
    -- NHS number match. (NULL values will be excluded by the INNER JOIN.)
    -- Neither NHS number has spaces in (empirically).
INNER JOIN
    RiO62CAMLive.dbo.ClientName AS rcn
    ON rcn.ClientID = rc.ClientID
WHERE
    -- Exclude test NHS numbers, which start 999:
    LEFT(sp.NHSNumber, 3) != '999'
    -- Primary RiO name:
    AND rcn.EndDate IS NULL
    AND rcn.Deleted = 0
    AND rcn.AliasType = '1'  -- usual name
    -- Restrict to M/F and no discrepancy:
    AND rc.Gender IN ('M', 'F')
    AND sp.Gender = rc.Gender
GROUP BY
    rc.Gender,
    sp.Gender
ORDER BY
    rc.Gender


-- ============================================================================
-- Postcodes. Restrict to people with exactly one postcode known.
-- ============================================================================
-- Surprisingly quick, despite inelegant SQL.

SELECT
    COUNT(*) AS n_people_one_postcode_each_database,  -- 101349
    SUM(
        IIF(
            rio_postcode_unit != s1_postcode_unit,
            1,
            0
        )
    ) AS n_postcode_unit_mismatch,  -- 31399 = 0.3098107
    SUM(
        IIF(
            rio_postcode_unit != s1_postcode_unit
            AND rio_postcode_sector = s1_postcode_sector,
            1,
            0
        )
    ) AS n_postcode_unit_mismatch_but_sector_match,  -- 983 = 0.009699158
    SUM(
        IIF(
            rio_postcode_unit != s1_postcode_unit
            AND (
                rio_postcode_unit =
                    LEFT(s1_postcode_unit, LEN(s1_postcode_unit) - 2)
                    + RIGHT(s1_postcode_unit, 1)
                    + SUBSTRING(s1_postcode_unit, LEN(s1_postcode_unit) - 1, 1)
                OR s1_postcode_unit =
                    LEFT(rio_postcode_unit, LEN(rio_postcode_unit) - 2)
                    + RIGHT(rio_postcode_unit, 1)
                    + SUBSTRING(rio_postcode_unit, LEN(rio_postcode_unit) - 1, 1)
            ),
            1,
            0
        )
    ) AS n_postcode_match_if_last_two_chars_transposed  -- 27
FROM (
    SELECT
        REPLACE(UPPER(ra.PostCode), ' ', '') AS rio_postcode_unit,
        LEFT(
            REPLACE(UPPER(ra.PostCode), ' ', ''),
            LEN(REPLACE(ra.PostCode, ' ', '')) - 1
        ) AS rio_postcode_sector,
        UPPER(sa.PostCode_NoSpaces) AS s1_postcode_unit,
        LEFT(
            UPPER(sa.PostCode_NoSpaces),
            LEN(sa.PostCode_NoSpaces) - 1
        ) AS s1_postcode_sector
    FROM
        RiO62CAMLive.dbo.Client AS rc
    INNER JOIN
        SystmOne.dbo.S1_Patient AS sp
        ON TRY_CAST(sp.NHSNumber AS BIGINT) = TRY_CAST(rc.NNN AS BIGINT)
        -- NHS number match. (NULL values will be excluded by the INNER JOIN.)
        -- Neither NHS number has spaces in (empirically).
    INNER JOIN
        RiO62CAMLive.dbo.ClientAddress AS ra
        ON ra.ClientID = rc.ClientID
    INNER JOIN
        SystmOne.dbo.S1_PatientAddress AS sa
        ON sa.IDPatient = sp.IDPatient
    WHERE
        -- Exclude test NHS numbers, which start 999:
        LEFT(sp.NHSNumber, 3) != '999'
        -- People with a single RiO postcode:
        AND rc.ClientID IN (
            SELECT ra2.ClientID
            FROM RiO62CAMLive.dbo.ClientAddress AS ra2
            WHERE ra2.PostCode IS NOT NULL
            AND LEN(ra2.PostCode) >= 5
            GROUP BY ra2.ClientID
            HAVING COUNT(*) = 1  -- only one postcode for patient
        )  -- retrieves 180439
        -- People with a single SystmOne postcode:
        AND sp.IDPatient IN (
            SELECT sa2.IDPatient
            FROM SystmOne.dbo.S1_PatientAddress AS sa2
            WHERE sa2.PostCode_NoSpaces IS NOT NULL
            AND LEN(sa2.PostCode_NoSpaces) >= 5
            GROUP BY sa2.IDPatient
            HAVING COUNT(*) = 1  -- only one postcode for patient
        )  -- retrieves 618501
        -- But we need to apply the same postcode restrictions here to the main
        -- query (this is not very elegant SQL!):
        AND ra.PostCode IS NOT NULL
        AND LEN(ra.PostCode) >= 5
        AND sa.PostCode_NoSpaces IS NOT NULL
        AND LEN(sa.PostCode_NoSpaces) >= 5
) AS subquery
