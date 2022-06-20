
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
