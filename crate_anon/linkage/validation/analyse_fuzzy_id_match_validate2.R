#!/usr/bin/env Rscript
# crate_anon/linkage/analyse_fuzzy_id_match_validate2.R

# For the main CPFT validation suite.
# During testing:
# source("C:/srv/crate/src/crate/crate_anon/linkage/analyse_fuzzy_id_match_validate2.R")

# =============================================================================
# Libraries
# =============================================================================

library(data.table)
library(ggplot2)
library(gridExtra)
library(pROC)
library(RJSONIO)
library(tidyverse)

source("https://egret.psychol.cam.ac.uk/rlib/debugfunc.R")
source("https://egret.psychol.cam.ac.uk/rlib/miscfile.R")
source("https://egret.psychol.cam.ac.uk/rlib/miscplot.R")

debugfunc$wideScreen()


# =============================================================================
# Governing constants
# =============================================================================

ROW_LIMIT <- 1000  # Inf for no limit; finite for debugging


# =============================================================================
# Database constants
# =============================================================================

CDL <- "cdl"
PCMIS <- "pcmis"
RIO <- "rio"
SYSTMONE <- "systmone"

# ALL_DATABASES <- c(CDL, PCMIS, RIO, SYSTMONE)
ALL_DATABASES <- c(CDL)  # for debugging


# =============================================================================
# Directories, filenames
# =============================================================================

DATA_DIR <- "C:/srv/crate/crate_fuzzy_linkage_validation"
OUTPUT_DIR <- "C:/Users/rcardinal/Documents/fuzzy_linkage_validation"


get_data_filename <- function(db)
{
    file.path(DATA_DIR, paste0("fuzzy_data_", db, "_hashed.csv"))
}


get_comparison_filename <- function(db1, db2)
{
    file.path(
        DATA_DIR,
        paste0("fuzzy_compare_", db1, "_to_", db2, "_hashed.csv")
    )
}


# =============================================================================
# Data handling functions
# =============================================================================

load_people <- function(filename, nrows = ROW_LIMIT, strip_irrelevant = TRUE)
{
    # data.table::fread() messes up the quotes in JSON; probably possible to
    # tweak it, but this is easier!
    d <- data.table(read.csv(filename, nrows = nrows))
    if (strip_irrelevant) {
        # Get rid of columns we don't care about
        d <- d[, .(local_id, other_info)]
    }
    # Now expand the "other_info" column, which is JSON.
    # https://stackoverflow.com/questions/31599299/expanding-a-json-column-in-r
    d <- lapply(as.character(d$other_info), RJSONIO::fromJSON) %>%
        lapply(
            function(e) {
                 list(
                     hashed_nhs_number = e$hashed_nhs_number,

                     blurred_dob = e$blurred_dob,
                     gender = e$gender,
                     ethnicity = e$ethnicity,
                     index_of_multiple_deprivation = e$index_of_multiple_deprivation,

                     first_mh_care_date = e$first_mh_care_date,
                     age_at_first_mh_care = e$age_at_first_mh_care,
                     any_icd10_dx_present = e$any_icd10_dx_present,
                     chapter_f_icd10_dx_present = e$chapter_f_icd10_dx_present,
                     severe_mental_illness_icd10_dx_present = e$severe_mental_illness_icd10_dx_present
                 )
            }
        ) %>%
        rbindlist() %>%
        cbind(d) %>%
        select(-other_info) %>%
        as.data.table()
    setkey(d, local_id)
    setcolorder(d, "local_id")
    return(d)
}


load_comparison <- function(filename, probands, sample, nrows = ROW_LIMIT)
{
    # No JSON here; we can use the fast fread() function.
    comparison_result <- data.table::fread(
        file = filename,
        nrows = nrows,
        index = "proband_local_id"
    )
    # Demographic information and gold-standard match info from the probands
    d <- merge(
        x = comparison_result,
        y = probands,
        by.x = "proband_local_id",
        by.y = "local_id",
        all.x = TRUE,
        all.y = FALSE
    )
    # Gold-standard match info from the sample (best candidate)
    d <- merge(
        x = d,
        y = sample[, .(local_id, hashed_nhs_number)],
        by.x = "best_candidate_local_id",
        by.y = "local_id",
        all.x = TRUE,
        all.y = FALSE,
        suffixes = c("", "_best_candidate")
    )
    setkey(d, proband_local_id)
    setnames(d, "hashed_nhs_number", "hashed_nhs_number_proband")
    # Remove sample_match_local_id, which depends on specific threshold
    # settings; we will inspect best_candidate_local_id instead.
    d[, sample_match_local_id := NULL]
    setcolorder(
        d,
        c(
            # Proband
            "hashed_nhs_number_proband",
            "proband_local_id",
            "blurred_dob",
            "gender",
            "ethnicity",
            "index_of_multiple_deprivation",
            "first_mh_care_date",
            "age_at_first_mh_care",
            "any_icd10_dx_present",
            "chapter_f_icd10_dx_present",
            "severe_mental_illness_icd10_dx_present",

            # Reported match
            "log_odds_match",
            "p_match",
            "second_best_log_odds",
            "matched",
            # "sample_match_local_id",
            "best_candidate_local_id",  # the extra validation one

            # Gold standard for matching
            "hashed_nhs_number_best_candidate"
        )
    )

    # Checks
    stopifnot(all(!is.na(hashed_nhs_number_proband)))

    # Calculations
    d[, best_candidate_correct := as.integer(
        # Hit, subject to thresholds.
        hashed_nhs_number_proband == hashed_nhs_number_best_candidate
        & !is.na(hashed_nhs_number_best_candidate)
    )]
    d[, best_candidate_incorrect := as.integer(
        # False alarm, subject to thresholds.
        hashed_nhs_number_proband != hashed_nhs_number_best_candidate
        & !is.na(hashed_nhs_number_best_candidate)
    )]
    d[, proband_in_sample := as.integer(
        hashed_nhs_number_proband %in% sample$hashed_nhs_number
    )]
    d[, correctly_eliminated := as.integer(
        # Correct rejection, subject to thresholds.
        is.na(hashed_nhs_number_best_candidate) & !proband_in_sample
    )]
    d[, not_found := as.integer(
        # Miss, subject to thresholds.
        is.na(hashed_nhs_number_best_candidate) & !proband_in_sample
    )]

    return(d)
}


load_all <- function()
{
    mk_people_var <- function(db)
    {
        paste0("people_", db1)
    }
    mk_comparison_var <- function(db1, db2)
    {
        paste0("compare_", db1, "_to_", db2)
    }
    for (db1 in ALL_DATABASES) {
        assign(
            mk_people_var(db1),
            load_people(get_data_filename(db1)),
            envir = .GlobalEnv
        )
    }
    for (db1 in ALL_DATABASES) {
        for (db2 in ALL_DATABASES) {
            assign(
                mk_comparison_var(db1, db2),
                load_comparison(
                    filename = get_comparison_filename(db1, db2),
                    probands = get(mk_people_var(db1)),
                    sample = get(mk_people_var(db2)),
                ),
                envir = .GlobalEnv
            )
        }
    }
}


# =============================================================================
# Load data
# =============================================================================

load_all()
