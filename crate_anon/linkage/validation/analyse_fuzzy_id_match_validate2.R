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
# Database constants
# =============================================================================

CDL <- "cdl"
PCMIS <- "pcmis"
RIO <- "rio"
SYSTMONE <- "systmone"
ALL_DATABASES <- c(CDL, PCMIS, RIO, SYSTMONE)


# =============================================================================
# Directories, filenames
# =============================================================================

DATA_DIR <- "C:/srv/crate/crate_fuzzy_linkage_validation"
OUTPUT_DIR <- "C:/Users/rcardinal/Documents/fuzzy_linkage_validation"

get_data_filename <- function(db) {
    file.path(DATA_DIR, paste0("fuzzy_data_", db, "_hashed.csv"))
}

get_comparison_filename <- function(db1, db2) {
    file.path(
        DATA_DIR,
        paste0("fuzzy_compare_", db1, "_to_", db2, "_hashed.csv")
    )
}


# =============================================================================
# Data handling functions
# =============================================================================

load_people <- function(filename) {
    d <- data.table(read.csv(filename))
    # Now expand the "other_info" column, which is JSON.
    # https://stackoverflow.com/questions/31599299/expanding-a-json-column-in-r
    d <- lapply(as.character(df$other_info), RJSONIO::fromJSON) %>%
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
        select(-other_info)
    return(d)
}


load_comparison <- function(filename) {
    return(data.table(read.csv(filename)))
}


# =============================================================================
# Load data
# =============================================================================

for (db1 in ALL_DATABASES) {
    assign(
        paste0("people_", db1),
        load_people(get_data_filename(db1))
    )
    for (db2 in ALL_DATABASES) {
        assign(
            paste0("compare_", db1, "_to_", db2),
            load_comparison(get_comparison_filename(db1, db2))
        )
    }
}
