
-- ============================================================================
-- Total counts
-- ============================================================================

SELECT
    'CDL' AS db_name,
    COUNT(*) AS total_n,
    SUM(IIF(DOB IS NULL, 1, 0)) AS n_with_no_dob
FROM rawCRSCDL.dbo.[CRS_Output_2020 09 21]  -- 162874

UNION

SELECT
    'PCMIS' AS db_name,
    COUNT(*) AS total_n,
    SUM(IIF(DOB IS NULL, 1, 0)) AS n_with_no_dob
FROM rawPCMIS.dbo.PatientDetails
-- 94344 previously (on 2022-05-26) but now (on 2022-06-20) 120966

UNION

SELECT
    'RiO' AS db_name,
    COUNT(*) AS total_n,
    SUM(IIF(DateOfBirth IS NULL, 1, 0)) AS n_with_no_dob
FROM RiO62CAMLive.dbo.Client  -- 216739

UNION

SELECT
    'SystmOne' AS db_name,
    COUNT(*) AS total_n,
    SUM(IIF(DOB IS NULL, 1, 0)) AS n_with_no_dob
FROM SystmOne.dbo.S1_Patient  -- 619062


-- ============================================================================
-- Total number of distinct NHS numbers, in any of the four databases
-- ============================================================================
-- Ignore test numbers for now (they are few or non-existent).

SELECT COUNT(DISTINCT nhs_number) AS n_distinct_patients_with_nhs_number
FROM (
    -- CDL
    SELECT TRY_CAST(REPLACE(c.NHS_ID, ' ', '') AS BIGINT) AS nhs_number
    FROM zVaultCRS_CDL.dbo.NHSID_BRC_Lookup AS c
    WHERE LEFT(c.NHS_ID, 3) != '999'

    UNION ALL

    -- PCMIS
    SELECT TRY_CAST(p.NHSNumber AS BIGINT) AS nhs_number
    FROM rawPCMIS.dbo.PatientDetails AS p
    WHERE LEFT(p.NHSNumber, 3) != '999'

    UNION ALL

    -- RiO
    -- Empirically: no spaces.
    SELECT TRY_CAST(r.NNN AS BIGINT) AS nhs_number
    FROM RiO62CAMLive.dbo.Client AS r
    WHERE LEFT(r.NNN, 3) != '999'

    UNION ALL

    -- SystmOne
    -- Empirically: no spaces.
    SELECT TRY_CAST(s.NHSNumber AS BIGINT) AS nhs_number
    FROM SystmOne.dbo.S1_Patient AS s
    WHERE LEFT(s.NHSNumber, 3) != '999'

) AS subquery
-- 756821 on 2022-07-21.
