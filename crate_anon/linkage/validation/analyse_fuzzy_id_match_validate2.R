#!/usr/bin/env Rscript
# crate_anon/linkage/analyse_fuzzy_id_match_validate2.R

'
For the main CPFT validation suite.
During testing:

source("C:/srv/crate/src/crate/crate_anon/linkage/analyse_fuzzy_id_match_validate2.R")

or Ctrl-Shift-S to source from RStudio.

Criteria
--------

    log_odds_match >= threshold_1
    log_odds_match >= second_best_log_odds + threshold_2

'

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

ROW_LIMIT <- Inf  # Inf for no limit; finite for debugging


# =============================================================================
# Database constants
# =============================================================================

CDL <- "cdl"
PCMIS <- "pcmis"
RIO <- "rio"
SYSTMONE <- "systmone"

# ALL_DATABASES <- c(CDL, PCMIS, RIO, SYSTMONE)
ALL_DATABASES <- c(CDL, PCMIS, RIO)  # for debugging

# FROM_DATABASES <- ALL_DATABASES
FROM_DATABASES <- CDL  # for debugging

# TO_DATABASES <- ALL_DATABASES
TO_DATABASES <- c(CDL, PCMIS, RIO)  # for debugging


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

simplified_ethnicity <- function(ethnicity)
{
    # We have to deal with ethnicity text from lots of different clinical
    # record systems.
    #
    # - Categories as per:
    #   https://www.ethnicity-facts-figures.service.gov.uk/ethnicity-in-the-uk/ethnic-groups-by-age
    # - Single-letter codes:
    #   https://www.datadictionary.nhs.uk/attributes/ethnic_category_code_2001.html
    # - There is illogicality, e.g. China and Japan are part of Asia. But the
    #   NHS conventions include "Mixed - Asian and Chinese" and Chinese (R) is
    #   not within the Asian (A*) group. So we use "other" here.

    ETHNICITY_ASIAN <- "asian"
    ETHNICITY_BLACK <- "black"
    ETHNICITY_MIXED <- "mixed"
    ETHNICITY_WHITE <- "white"
    ETHNICITY_OTHER <- "other"
    ETHNICITY_UNKNOWN <- "unknown"

    return(factor(
        dplyr::recode(
            ethnicity,

            "Asian or Asian British - Any other Asian background" = ETHNICITY_ASIAN,
            "Asian or Asian British - Any other background" = ETHNICITY_ASIAN,
            "Asian or Asian British - Bangladeshi" = ETHNICITY_ASIAN,
            "Asian or Asian British - British" = ETHNICITY_ASIAN,
            "Asian or Asian British - Caribbean Asian" = ETHNICITY_ASIAN,
            "Asian or Asian British - East African Asian" = ETHNICITY_ASIAN,
            "Asian or Asian British - Indian" = ETHNICITY_ASIAN,
            "Asian or Asian British - Kashmiri" = ETHNICITY_ASIAN,
            "Asian or Asian British - Mixed Asian" = ETHNICITY_ASIAN,
            "Asian or Asian British - Other/Unspecified" = ETHNICITY_ASIAN,
            "Asian or Asian British - Pakistani" = ETHNICITY_ASIAN,
            "Asian or Asian British - Punjabi" = ETHNICITY_ASIAN,
            "Asian or Asian British - Sinhalese" = ETHNICITY_ASIAN,
            "Asian or Asian British - Sri Lanka" = ETHNICITY_ASIAN,
            "Asian or Asian British - Tamil" = ETHNICITY_ASIAN,
            "H" = ETHNICITY_ASIAN,  # Asian or Asian British - Indian
            "J" = ETHNICITY_ASIAN,  # Asian or Asian British - Pakistani
            "K" = ETHNICITY_ASIAN,  # Asian or Asian British - Bangladeshi
            "L" = ETHNICITY_ASIAN,  # Asian or Asian British - Any other Asian background

            "Black or Black British - African" = ETHNICITY_BLACK,
            "Black or Black British - Any other background" = ETHNICITY_BLACK,
            "Black or Black British - Any other Black background" = ETHNICITY_BLACK,
            "Black or Black British - British" = ETHNICITY_BLACK,
            "Black or Black British - Caribbean" = ETHNICITY_BLACK,
            "Black or Black British - Mixed" = ETHNICITY_BLACK,
            "Black or Black British - Nigerian" = ETHNICITY_BLACK,
            "Black or Black British - Other/Unspecified" = ETHNICITY_BLACK,
            "Black or Black British - Somali" = ETHNICITY_BLACK,
            "M" = ETHNICITY_BLACK,  # Black or Black British - Caribbean
            "N" = ETHNICITY_BLACK,  # Black or Black British - African
            "P" = ETHNICITY_BLACK,  # Black or Black British - Any other Black background

            "D" = ETHNICITY_MIXED,  # Mixed - White and Black Caribbean
            "E" = ETHNICITY_MIXED,  # Mixed - White and Black African
            "F" = ETHNICITY_MIXED,  # Mixed - White and Asian
            "G" = ETHNICITY_MIXED,  # Mixed - Any other mixed background
            "Mixed - Any other mixed background" = ETHNICITY_MIXED,
            "Mixed - Asian and Chinese" = ETHNICITY_MIXED,
            "Mixed - Black and Asian" = ETHNICITY_MIXED,
            "Mixed - Black and Chinese" = ETHNICITY_MIXED,
            "Mixed - Black and White" = ETHNICITY_MIXED,
            "Mixed - Chinese and White" = ETHNICITY_MIXED,
            "Mixed - Other/Unspecified" = ETHNICITY_MIXED,
            "Mixed - White & Asian" = ETHNICITY_MIXED,
            "Mixed - White & Black African" = ETHNICITY_MIXED,
            "Mixed - White & Black Caribbean" = ETHNICITY_MIXED,
            "Mixed - White and Black African" = ETHNICITY_MIXED,

            "A" = ETHNICITY_WHITE,  # White - British
            "Any other White background" = ETHNICITY_WHITE,
            "B" = ETHNICITY_WHITE,  # White - Irish
            "C" = ETHNICITY_WHITE,  # White - Any other White backgroud
            "CPFTEWSNI" = ETHNICITY_WHITE,  # ?England, Wales, Scotland, Northern Ireland
            "CPFTTraveller" = ETHNICITY_WHITE,  # based on national "White - Traveller"
            "White - All Republics of former USSR" = ETHNICITY_WHITE,
            "White - Any other background" = ETHNICITY_WHITE,
            "White - British" = ETHNICITY_WHITE,
            "White - English" = ETHNICITY_WHITE,
            "White - Gypsy/Romany" = ETHNICITY_WHITE,
            "White - Irish" = ETHNICITY_WHITE,
            "White - Mixed White" = ETHNICITY_WHITE,
            "White - Northern Irish" = ETHNICITY_WHITE,
            "White - Other European" = ETHNICITY_WHITE,
            "White - Other/Unspecified" = ETHNICITY_WHITE,
            "White - Polish" = ETHNICITY_WHITE,
            "White - Serbian" = ETHNICITY_WHITE,
            "White - Traveller" = ETHNICITY_WHITE,
            "White - Welsh" = ETHNICITY_WHITE,

            "Any Other Group" = ETHNICITY_OTHER,
            "Other Ethnic Group - Chinese" = ETHNICITY_OTHER,
            "Other Ethnic Group" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Any Other Group" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Arab" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Buddhist" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Chinese" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Filipino" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Hindu" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Iranian" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Israeli" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Japanese" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Jewish" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Kurdish" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Latin American" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Malaysian" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Maur/SEyc/Mald/StHelen" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Moroccan" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Muslim" = ETHNICITY_OTHER,
            "Other Ethnic Groups - South/Central American" = ETHNICITY_OTHER,
            "R" = ETHNICITY_OTHER,  # Other Ethnic Groups - Chinese
            "S" = ETHNICITY_OTHER,  # Other Ethnic Groups - Any other ethnic group

            "Not Known" = ETHNICITY_UNKNOWN,
            "Not Specified" = ETHNICITY_UNKNOWN,
            "Not Stated (Client Refused)" = ETHNICITY_UNKNOWN,
            "Not Stated (Not Requested)" = ETHNICITY_UNKNOWN,
            "Not Stated" = ETHNICITY_UNKNOWN,
            "NOTKNOWN" = ETHNICITY_UNKNOWN,
            "Z" = ETHNICITY_UNKNOWN,  # Not stated

            .default = NA_character_
        ),
        levels = c(
            ETHNICITY_UNKNOWN,  # put this first as comparator for ANOVA
            ETHNICITY_ASIAN,
            ETHNICITY_BLACK,
            ETHNICITY_MIXED,
            ETHNICITY_WHITE,
            ETHNICITY_OTHER
        )
    ))
}


load_people <- function(filename, nrows = ROW_LIMIT, strip_irrelevant = TRUE)
{
    # data.table::fread() messes up the quotes in JSON; probably possible to
    # tweak it, but this is easier!
    cat(paste0("- Loading from: ", filename, "\n"))
    d <- data.table(read.csv(filename, nrows = nrows))
    cat("  ... loaded; processing...\n")
    if (strip_irrelevant) {
        # Get rid of columns we don't care about
        d <- d[, .(local_id, other_info)]
    }
    # Now expand the "other_info" column, which is JSON.
    # https://stackoverflow.com/questions/31599299/expanding-a-json-column-in-r
    d <- lapply(as.character(d$other_info), RJSONIO::fromJSON) %>%
        lapply(
            function(e) {
                # RJSONIO::fromJSON("{'a': null}") produces NULL.
                # rbindlist() later complains, so let's convert NULL to NA
                # explicitly.
                list(
                    hashed_nhs_number = e$hashed_nhs_number,

                    blurred_dob = e$blurred_dob,
                    gender = e$gender,
                    raw_ethnicity = e$ethnicity,
                    index_of_multiple_deprivation = ifelse(
                        is.null(e$index_of_multiple_deprivation),
                        NA_integer_,
                        e$index_of_multiple_deprivation
                    ),

                    # unnecessary: first_mh_care_date = e$first_mh_care_date,
                    age_at_first_mh_care = ifelse(
                        is.null(e$age_at_first_mh_care),
                        NA_integer_,
                        e$age_at_first_mh_care
                    ),
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
    d[local_id == "", local_id := NA_character_]
    d[hashed_nhs_number == "", hashed_nhs_number := NA_character_]
    setkey(d, local_id)
    setcolorder(d, "local_id")
    stopifnot(all(!is.na(d$local_id)))
    stopifnot(all(!is.na(d$hashed_nhs_number)))
    d[, ethnicity := simplified_ethnicity(raw_ethnicity)]
    unknown_ethnicities <- sort(unique(d$raw_ethnicity[is.na(d$ethnicity) & !is.na(d$raw_ethnicity)]))
    if (length(unknown_ethnicities) > 0) {
        warning(paste0(
            "  - Unknown ethnicities: ",
            paste(unknown_ethnicities, collapse = ", "),
            "\n"
        ))
    }
    cat("  ... done.\n")
    return(d)
}


load_comparison <- function(filename, probands, sample, nrows = ROW_LIMIT)
{
    # No JSON here; we can use the fast fread() function.
    cat(paste0("- Loading from: ", filename, "\n"))
    comparison_result <- data.table::fread(
        file = filename,
        nrows = nrows,
        index = "proband_local_id"
    )
    cat("  ... loaded; processing...\n")
    # Sort out NA values
    comparison_result[
        best_candidate_local_id == "",
        best_candidate_local_id := NA_character_
    ]
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
    stopifnot(all(!is.na(d$hashed_nhs_number_proband)))

    # Calculations
    # ... boolean is better than integer for subsequent use.
    d[, best_candidate_correct :=
        # Hit, subject to thresholds.
        !is.na(hashed_nhs_number_best_candidate)
        & hashed_nhs_number_proband == hashed_nhs_number_best_candidate
    ]
    d[, best_candidate_incorrect :=
        # False alarm, subject to thresholds.
        !is.na(hashed_nhs_number_best_candidate)
        & hashed_nhs_number_proband != hashed_nhs_number_best_candidate
    ]
    d[, proband_in_sample :=
        hashed_nhs_number_proband %in% sample$hashed_nhs_number
    ]
    d[, correctly_eliminated :=
        # Correct rejection, subject to thresholds.
        is.na(hashed_nhs_number_best_candidate) & !proband_in_sample
    ]
    d[, not_found :=
        # Miss, subject to thresholds.
        is.na(hashed_nhs_number_best_candidate) & !proband_in_sample
    ]
    cat("  ... done.\n")

    return(d)
}


load_all <- function()
{
    mk_people_var <- function(db)
    {
        paste0("people_", db)
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
    for (db1 in FROM_DATABASES) {
        for (db2 in TO_DATABASES) {
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
