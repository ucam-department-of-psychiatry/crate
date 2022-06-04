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

RLIB_STEM <- "https://egret.psychol.cam.ac.uk/rlib/"
source(paste0(RLIB_STEM, "debugfunc.R"))
source(paste0(RLIB_STEM, "miscfile.R"))
source(paste0(RLIB_STEM, "misclang.R"))
source(paste0(RLIB_STEM, "miscplot.R"))

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

ALL_DATABASES <- c(CDL, PCMIS, RIO, SYSTMONE)
# ALL_DATABASES <- c(CDL, PCMIS, RIO)  # for debugging

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

get_data_cache_filename <- function(db)
{
    file.path(DATA_DIR, paste0("cached_people_", db, ".rds"))
}

get_comparison_cache_filename <- function(db1, db2)
{
    file.path(DATA_DIR, paste0("cached_comparison_", db1, "_to_", db2, ".rds"))
}


# =============================================================================
# Variable names
# =============================================================================

mk_people_var <- function(db)
{
    paste0("people_", db)
}

mk_comparison_var <- function(db1, db2)
{
    paste0("compare_", db1, "_to_", db2)
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
    # - SystmOne has an extraordinary profusion of these.

    ETHNICITY_ASIAN <- "asian"
    ETHNICITY_BLACK <- "black"
    ETHNICITY_MIXED <- "mixed"
    ETHNICITY_WHITE <- "white"
    ETHNICITY_OTHER <- "other"
    ETHNICITY_UNKNOWN <- "unknown"

    return(factor(
        dplyr::recode(
            str_trim(ethnicity),  # remove leading/trailing whitespace

            "Asian - ethnic group" = ETHNICITY_ASIAN,
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
            "Asian or Asian British: Indian - NI ethnic cat 2011 census" = ETHNICITY_ASIAN,
            "Asian/Asian Brit: Bangladeshi- Eng+Wales eth cat 2011 census" = ETHNICITY_ASIAN,
            "Asian/Asian Brit: Indian - Eng+Wales ethnic cat 2011 census" = ETHNICITY_ASIAN,
            "Asian/Asian Brit: other Asian- Eng+Wales eth cat 2011 census" = ETHNICITY_ASIAN,
            "Asian/Asian British: other Asian - NI ethnic cat 2011 census" = ETHNICITY_ASIAN,
            "Asian/Asian British: Pakistani - NI ethnic cat 2011 census" = ETHNICITY_ASIAN,
            "Asian/Asian British:Pakistani- Eng+Wales eth cat 2011 census" = ETHNICITY_ASIAN,
            "Asian: Indian, Indian Scot/Indian Brit- Scotland 2011 census" = ETHNICITY_ASIAN,
            "Asian: other Asian group - Scotland ethnic cat 2011 census" = ETHNICITY_ASIAN,
            "Asian: Pakistani/Pakistani Scot/Pakistani Brit- Scot 2011" = ETHNICITY_ASIAN,
            "Bangladeshi or British Bangladeshi - ethn categ 2001 census" = ETHNICITY_ASIAN,
            "Bangladeshi" = ETHNICITY_ASIAN,
            "Bangladeshi,  Bangladeshi or British Bangladeshi - ethn categ 2001 census" = ETHNICITY_ASIAN,
            "British Asian - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Caribbean Asian - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "East African Asian (NMO)" = ETHNICITY_ASIAN,
            "East African Asian - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "H" = ETHNICITY_ASIAN,  # Asian or Asian British - Indian
            "Indian or British Indian - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Indian sub-continent (NMO)" = ETHNICITY_ASIAN,
            "Indian" = ETHNICITY_ASIAN,
            "J" = ETHNICITY_ASIAN,  # Asian or Asian British - Pakistani
            "K" = ETHNICITY_ASIAN,  # Asian or Asian British - Bangladeshi
            "Kashmiri - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "L" = ETHNICITY_ASIAN,  # Asian or Asian British - Any other Asian background
            "Other Asian (NMO)" = ETHNICITY_ASIAN,
            "Other Asian background - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Other Asian ethnic group" = ETHNICITY_ASIAN,
            "Other Asian or Asian unspecified ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Other Asian" = ETHNICITY_ASIAN,
            "Pakistani or British Pakistani - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Pakistani" = ETHNICITY_ASIAN,
            "Punjabi - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Race - Indian" = ETHNICITY_ASIAN,
            "Race: Pakistani" = ETHNICITY_ASIAN,
            "South East Asian" = ETHNICITY_ASIAN,  # ?
            "Sri Lankan - ethnic category 2001 census" = ETHNICITY_ASIAN,
            "Tamil - ethnic category 2001 census" = ETHNICITY_ASIAN,

            "African - ethnic category 2001 census" = ETHNICITY_BLACK,
            "African: African/African Scot/African Brit - Scotland 2011" = ETHNICITY_BLACK,
            "African: any other African - Scotland ethnic cat 2011 census" = ETHNICITY_BLACK,
            "Black - ethnic group" = ETHNICITY_BLACK,
            "Black - other African country" = ETHNICITY_BLACK,
            "Black - other Asian" = ETHNICITY_BLACK,
            "Black - other, mixed" = ETHNICITY_BLACK,
            "Black African" = ETHNICITY_BLACK,
            "Black Black - other" = ETHNICITY_BLACK,
            "Black British - ethnic category 2001 census" = ETHNICITY_BLACK,
            "Black British" = ETHNICITY_BLACK,
            "Black Caribbean" = ETHNICITY_BLACK,
            "Black Caribbean/W.I./Guyana" = ETHNICITY_BLACK,
            "Black East African Asian" = ETHNICITY_BLACK,
            "Black Indian sub-continent" = ETHNICITY_BLACK,  # presumably?
            "Black N African/Arab/Iranian" = ETHNICITY_BLACK,
            "Black North African" = ETHNICITY_BLACK,
            "Black or Black British - African" = ETHNICITY_BLACK,
            "Black or Black British - Any other background" = ETHNICITY_BLACK,
            "Black or Black British - Any other Black background" = ETHNICITY_BLACK,
            "Black or Black British - British" = ETHNICITY_BLACK,
            "Black or Black British - Caribbean" = ETHNICITY_BLACK,
            "Black or Black British - Mixed" = ETHNICITY_BLACK,
            "Black or Black British - Nigerian" = ETHNICITY_BLACK,
            "Black or Black British - Other/Unspecified" = ETHNICITY_BLACK,
            "Black or Black British - Somali" = ETHNICITY_BLACK,
            "Black West Indian" = ETHNICITY_BLACK,
            "Black, other, non-mixed origin" = ETHNICITY_BLACK,
            "Black/Afr/Carib/Black Brit: other Black- Eng+Wales 2011 cens" = ETHNICITY_BLACK,
            "Black/Afri/Carib/Black Brit: African- NI eth cat 2011 census" = ETHNICITY_BLACK,
            "Black/Afri/Carib/Black Brit: other - NI eth cat 2011 census" = ETHNICITY_BLACK,
            "Black/African/Carib/Black Brit: African- Eng+Wales 2011 cens" = ETHNICITY_BLACK,
            "Black/African/Caribbn/Black Brit: Caribbean - Eng+Wales 2011" = ETHNICITY_BLACK,
            "Caribbean - ethnic category 2001 census" = ETHNICITY_BLACK,
            "E Afric Asian/Indo-Carib (NMO)" = ETHNICITY_BLACK,  # based on "Black East African Asian"
            "M" = ETHNICITY_BLACK,  # Black or Black British - Caribbean
            "N" = ETHNICITY_BLACK,  # Black or Black British - African
            "Nigerian - ethnic category 2001 census" = ETHNICITY_BLACK,
            "North African - ethnic category 2001 census" = ETHNICITY_BLACK,
            "Other African countries (NMO)" = ETHNICITY_BLACK,
            "Other Black background - ethnic category 2001 census" = ETHNICITY_BLACK,
            "Other black ethnic group" = ETHNICITY_BLACK,
            "Other Black or Black unspecified ethnic category 2001 census" = ETHNICITY_BLACK,
            "P" = ETHNICITY_BLACK,  # Black or Black British - Any other Black background
            "Race: Afro-Caribbean" = ETHNICITY_BLACK,
            "Somali - ethnic category 2001 census" = ETHNICITY_BLACK,
            "West Indian (NMO)" = ETHNICITY_BLACK,

            "Asian and Chinese - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Black - other, mixed" = ETHNICITY_MIXED,
            "Black African and White" = ETHNICITY_MIXED,
            "Black and Asian - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Black and White - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Black Caribbean and White" = ETHNICITY_MIXED,
            "British or mixed British - ethnic category 2001 census" = ETHNICITY_MIXED,  # ?
            "Chinese and White - ethnic category 2001 census" = ETHNICITY_MIXED,
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
            "Mixed - White and Asian" = ETHNICITY_MIXED,
            "Mixed - White and Black African" = ETHNICITY_MIXED,
            "Mixed - White and Black Caribbean" = ETHNICITY_MIXED,
            "Mixed Asian - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Mixed Black - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Mixed ethnic census group" = ETHNICITY_MIXED,
            "Mixed Irish and other White - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Mixed: other Mixed/multiple backgrd - Eng+Wales 2011 census" = ETHNICITY_MIXED,
            "Mixed: other Mixed/multiple ethnic backgrd - NI 2011 census" = ETHNICITY_MIXED,
            "Mixed: White and Asian - NI ethnic category 2011 census" = ETHNICITY_MIXED,
            "Mixed: White and Black African - NI ethnic cat 2011 census" = ETHNICITY_MIXED,
            "Mixed: White and Black Caribbean - NI ethnic cat 2011 census" = ETHNICITY_MIXED,
            "Mixed: White+Asian - Eng+Wales ethnic category 2011 census" = ETHNICITY_MIXED,
            "Mixed: White+Black African - Eng+Wales eth cat 2011 census" = ETHNICITY_MIXED,
            "Mixed: White+Black Caribbean - Eng+Wales eth cat 2011 census" = ETHNICITY_MIXED,
            "Other Black - Black/Asian orig" = ETHNICITY_MIXED,
            "Other Black - Black/White orig" = ETHNICITY_MIXED,
            "Other ethnic, Asian/White orig" = ETHNICITY_MIXED,
            "Other ethnic, Black/White orig" = ETHNICITY_MIXED,
            "Other ethnic, mixed origin" = ETHNICITY_MIXED,
            "Other ethnic, mixed white orig" = ETHNICITY_MIXED,
            "Other ethnic, other mixed orig" = ETHNICITY_MIXED,
            "Other Mixed background - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Other Mixed or Mixed unspecified ethnic category 2001 census" = ETHNICITY_MIXED,
            "Other mixed White - ethnic category 2001 census" = ETHNICITY_MIXED,
            "Race: Mixed" = ETHNICITY_MIXED,
            "White and Asian - ethnic category 2001 census" = ETHNICITY_MIXED,
            "White and Black African - ethnic category 2001 census" = ETHNICITY_MIXED,
            "White and Black Caribbean - ethnic category 2001 census" = ETHNICITY_MIXED,

            "A" = ETHNICITY_WHITE,  # White - British
            "Albanian - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Any other White background" = ETHNICITY_WHITE,
            "B" = ETHNICITY_WHITE,  # White - Irish
            "Bosnian - ethnic category 2001 census" = ETHNICITY_WHITE,
            "C" = ETHNICITY_WHITE,  # White - Any other White backgroud
            "Cornish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "CPFTEWSNI" = ETHNICITY_WHITE,  # ?England, Wales, Scotland, Northern Ireland
            "CPFTTraveller" = ETHNICITY_WHITE,  # based on national "White - Traveller"
            "Cypriot (part not stated) - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Czech Roma" = ETHNICITY_WHITE,  # based on national Gypsy/Romany category
            "English - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Greek (NMO)" = ETHNICITY_WHITE,
            "Greek - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Greek Cypriot (NMO)" = ETHNICITY_WHITE,
            "Greek Cypriot - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Gypsies" = ETHNICITY_WHITE,
            "Gypsy/Romany - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Hungarian Roma" = ETHNICITY_WHITE,  # based on national Gypsy/Romany category
            "Irish (NMO)" = ETHNICITY_WHITE,
            "Irish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Irish Traveller - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Irish traveller" = ETHNICITY_WHITE,
            "Italian - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Kosovan - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Northern Irish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Oth White European/European unsp/Mixed European 2001 census" = ETHNICITY_WHITE,
            "Other European (NMO)" = ETHNICITY_WHITE,
            "Other republics former Yugoslavia - ethnic categ 2001 census" = ETHNICITY_WHITE,
            "Other White background - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Other white British ethnic group" = ETHNICITY_WHITE,
            "Other white ethnic group" = ETHNICITY_WHITE,
            "Other White or White unspecified ethnic category 2001 census" = ETHNICITY_WHITE,
            "Polish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Portuguese" = ETHNICITY_WHITE,  # based on "other European"
            "Race - British" = ETHNICITY_WHITE,
            "Race - Mediterranean" = ETHNICITY_WHITE,  # based on e.g. Greek, Italian
            "Race: Caucasian" = ETHNICITY_WHITE,
            "Roma ethnic group" = ETHNICITY_WHITE,  # based on national Gypsy/Romany category
            "Romanian Roma" = ETHNICITY_WHITE,  # based on national Gypsy/Romany category
            "Romanian"  = ETHNICITY_WHITE,  # based on "other European"
            "Scottish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Serbian - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Slovak Roma" = ETHNICITY_WHITE,  # based on national Gypsy/Romany category
            "Slovak" = ETHNICITY_WHITE,  # based on "other European"
            "Traveller - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Turkish (NMO)" = ETHNICITY_WHITE,
            "Turkish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Turkish Cypriot - ethnic category 2001 census" = ETHNICITY_WHITE,
            "Turkish/Turkish Cypriot (NMO)" = ETHNICITY_WHITE,
            "Welsh - ethnic category 2001 census" = ETHNICITY_WHITE,
            "White - Albanian" = ETHNICITY_WHITE,
            "White - All Republics of former USSR" = ETHNICITY_WHITE,
            "White - Any other background" = ETHNICITY_WHITE,
            "White - Bosnian" = ETHNICITY_WHITE,
            "White - British" = ETHNICITY_WHITE,
            "White - Cornish" = ETHNICITY_WHITE,
            "White - Croatian" = ETHNICITY_WHITE,
            "White - Cypriot (part not stated)" = ETHNICITY_WHITE,
            "White - English" = ETHNICITY_WHITE,
            "White - ethnic group" = ETHNICITY_WHITE,
            "White - Greek Cypriot" = ETHNICITY_WHITE,
            "White - Greek" = ETHNICITY_WHITE,
            "White - Gypsy/Romany" = ETHNICITY_WHITE,
            "White - Irish Traveller" = ETHNICITY_WHITE,
            "White - Irish" = ETHNICITY_WHITE,
            "White - Italian" = ETHNICITY_WHITE,
            "White - Kosovan" = ETHNICITY_WHITE,
            "White - Mixed White" = ETHNICITY_WHITE,
            "White - Northern Ireland ethnic category 2011 census" = ETHNICITY_WHITE,
            "White - Northern Irish" = ETHNICITY_WHITE,
            "White - Other European" = ETHNICITY_WHITE,
            "White - Other Republics of former Yugoslavia" = ETHNICITY_WHITE,
            "White - Other/Unspecified" = ETHNICITY_WHITE,
            "White - Polish" = ETHNICITY_WHITE,
            "White - Scottish" = ETHNICITY_WHITE,
            "White - Serbian  " = ETHNICITY_WHITE,
            "White - Serbian" = ETHNICITY_WHITE,
            "White - Traveller" = ETHNICITY_WHITE,
            "White - Turkish Cypriot" = ETHNICITY_WHITE,
            "White - Turkish" = ETHNICITY_WHITE,
            "White - Welsh" = ETHNICITY_WHITE,
            "White British - ethnic category 2001 census" = ETHNICITY_WHITE,
            "White British" = ETHNICITY_WHITE,
            "White Irish - ethnic category 2001 census" = ETHNICITY_WHITE,
            "White Irish" = ETHNICITY_WHITE,
            "White Scottish" = ETHNICITY_WHITE,
            "White: Gypsy/Irish Traveller - Eng+Wales eth cat 2011 census" = ETHNICITY_WHITE,
            "White: Irish - England and Wales ethnic category 2011 census" = ETHNICITY_WHITE,
            "White: other British - Scotland ethnic category 2011 census" = ETHNICITY_WHITE,
            "White: other White backgrd- Eng+Wales ethnic cat 2011 census" = ETHNICITY_WHITE,
            "White: Polish - Scotland ethnic category 2011 census" = ETHNICITY_WHITE,
            "White: Scottish - Scotland ethnic category 2011 census" = ETHNICITY_WHITE,
            "White:Eng/Welsh/Scot/NI/Brit - England and Wales 2011 census" = ETHNICITY_WHITE,

            "Any other group - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Any Other Group" = ETHNICITY_OTHER,
            "Arab - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Asian/Asian Brit: Chinese - Eng+Wales ethnic cat 2011 census" = ETHNICITY_OTHER,
            "Asian/Asian British: Chinese - NI ethnic cat 2011 census" = ETHNICITY_OTHER,
            "Baltic Estonian/Latvian/Lithuanian - ethn categ 2001 census" = ETHNICITY_OTHER,  # debatable, but in "other" category?
            "Brit. ethnic minor. spec.(NMO)" = ETHNICITY_OTHER,
            "Brit. ethnic minor. unsp (NMO)" = ETHNICITY_OTHER,
            "Bulgarian" = ETHNICITY_OTHER,  # unclear
            "Chinese - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Chinese" = ETHNICITY_OTHER,
            "Commonwealth (Russian) Indep States - ethn categ 2001 census" = ETHNICITY_OTHER,  # unclear
            "Croatian - ethnic category 2001 census" = ETHNICITY_OTHER,  # unclear
            "Czech" = ETHNICITY_OTHER,  # unclear
            "Fijian" = ETHNICITY_OTHER,
            "Filipino - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Hindu - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Iranian (NMO)" = ETHNICITY_OTHER,
            "Iranian - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Israeli - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Japanese - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Jewish - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Kurdish - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Latin American - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Malaysian - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Mauritian/Seychellois/Maldivian/St Helena eth cat 2001census" = ETHNICITY_OTHER,
            "Mid East (excl Israeli, Iranian & Arab) - eth cat 2001 cens" = ETHNICITY_OTHER,
            "Moroccan - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Muslim - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Nepali" = ETHNICITY_OTHER,
            "New Zealand ethnic groups" = ETHNICITY_OTHER,
            "North African Arab (NMO)" = ETHNICITY_OTHER,
            "Other - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Other Ethnic Group - Chinese" = ETHNICITY_OTHER,
            "Other Ethnic Group" = ETHNICITY_OTHER,
            "Other ethnic group" = ETHNICITY_OTHER,
            "Other ethnic group: Arab - Eng+Wales ethnic cat 2011 census" = ETHNICITY_OTHER,
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
            "Other Ethnic Groups - North African" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Other Middle East" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Sikh" = ETHNICITY_OTHER,
            "Other Ethnic Groups - South/Central American" = ETHNICITY_OTHER,
            "Other Ethnic Groups - Vietnamese" = ETHNICITY_OTHER,
            "Other ethnic NEC (NMO)" = ETHNICITY_OTHER,
            "Other ethnic non-mixed (NMO)" = ETHNICITY_OTHER,
            "Other ethnic: any other grp - Eng+Wales eth cat 2011 census" = ETHNICITY_OTHER,
            "R" = ETHNICITY_OTHER,  # Other Ethnic Groups - Chinese
            "Race: Arab" = ETHNICITY_OTHER,
            "Race: Chinese" = ETHNICITY_OTHER,
            "Race: Japanese" = ETHNICITY_OTHER,
            "Race: Korean" = ETHNICITY_OTHER,
            "Race: Other" = ETHNICITY_OTHER,
            "S" = ETHNICITY_OTHER,  # Other Ethnic Groups - Any other ethnic group
            "Sikh - ethnic category 2001 census" = ETHNICITY_OTHER,
            "South and Central American - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Vietnamese - ethnic category 2001 census" = ETHNICITY_OTHER,
            "Vietnamese" = ETHNICITY_OTHER,

            "Ethnic category - 2001 census" = ETHNICITY_UNKNOWN,
            "Ethnic category - 2011 census England and Wales" = ETHNICITY_UNKNOWN,
            "Ethnic category - 2011 census" = ETHNICITY_UNKNOWN,
            "Ethnic category not stated - 2001 census" = ETHNICITY_UNKNOWN,
            "Ethnic group not given - patient refused" = ETHNICITY_UNKNOWN,
            "Ethnic groups (census) NOS" = ETHNICITY_UNKNOWN,
            "Ethnic groups (census)" = ETHNICITY_UNKNOWN,
            "Ethnic groups" = ETHNICITY_UNKNOWN,
            "Ethnicity and other related nationality data" = ETHNICITY_UNKNOWN,
            "Not Known" = ETHNICITY_UNKNOWN,
            "Not Specified" = ETHNICITY_UNKNOWN,
            "Not Stated (Client Refused)" = ETHNICITY_UNKNOWN,
            "Not Stated (Not Requested)" = ETHNICITY_UNKNOWN,
            "Not Stated" = ETHNICITY_UNKNOWN,
            "NOTKNOWN" = ETHNICITY_UNKNOWN,
            "Patient ethnicity unknown" = ETHNICITY_UNKNOWN,
            "Race" = ETHNICITY_UNKNOWN,
            "Race: Not stated" = ETHNICITY_UNKNOWN,
            "Race: Unknown" = ETHNICITY_UNKNOWN,
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
    de_null <- function(x, na_value) {
        # RJSONIO::fromJSON("{'a': null}") produces NULL. rbindlist() later
        # complains, so let's convert NULL to NA explicitly.
        return(ifelse(is.null(x), na_value, x))
    }
    d <- lapply(as.character(d$other_info), RJSONIO::fromJSON) %>%
        lapply(
            function(e) {
                list(
                    hashed_nhs_number = e$hashed_nhs_number,

                    blurred_dob = e$blurred_dob,
                    gender = e$gender,
                    raw_ethnicity = de_null(e$ethnicity, NA_character_),
                    index_of_multiple_deprivation = de_null(
                        e$index_of_multiple_deprivation,
                        NA_integer_
                    ),

                    # unnecessary: first_mh_care_date = e$first_mh_care_date,
                    age_at_first_mh_care = de_null(
                        e$age_at_first_mh_care,
                        NA_integer_
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
    unknown_ethnicities <- sort(unique(
        d$raw_ethnicity[is.na(d$ethnicity) & !is.na(d$raw_ethnicity)]
    ))
    if (length(unknown_ethnicities) > 0) {
        warning(paste0(
            "  - Unknown ethnicities: ",
            paste(unknown_ethnicities, collapse = "; "),
            "\n"
        ))
    }
    d[, raw_ethnicity := NULL]

    DX_GROUP_SMI <- "SMI"
    DX_GROUP_F_NOT_SMI <- "F_not_SMI"
    DX_GROUP_OUTSIDE_F <- "codes_not_F"
    DX_GROUP_NONE <- "no_codes"
    d[,
        diagnostic_group := factor(
            ifelse(
                severe_mental_illness_icd10_dx_present,
                DX_GROUP_SMI,
                ifelse(
                    chapter_f_icd10_dx_present,
                    DX_GROUP_F_NOT_SMI,
                    ifelse(
                        any_icd10_dx_present,
                        DX_GROUP_OUTSIDE_F,
                        DX_GROUP_NONE
                    )
                )
            ),
            levels = c(
                DX_GROUP_NONE,
                DX_GROUP_OUTSIDE_F,
                DX_GROUP_F_NOT_SMI,
                DX_GROUP_SMI
            )
        )
    ]
    d[, any_icd10_dx_present := NULL]
    d[, chapter_f_icd10_dx_present := NULL]
    d[, severe_mental_illness_icd10_dx_present := NULL]

    cat(paste0("  ... done (", nrow(d), " rows).\n"))
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
            # "first_mh_care_date",
            "age_at_first_mh_care",
            # "any_icd10_dx_present",
            # "chapter_f_icd10_dx_present",
            # "severe_mental_illness_icd10_dx_present",
            "diagnostic_group",

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

    cat(paste0("  ... done (", nrow(d), " rows).\n"))
    return(d)
}


load_all <- function()
{
    for (db1 in ALL_DATABASES) {
        assign(
            mk_people_var(db1),
            misclang$load_rds_or_run_function(
                get_data_cache_filename(db1),
                load_people,
                get_data_filename(db1)
            ),
            load_people(),
            envir = .GlobalEnv
        )
    }
    for (db1 in FROM_DATABASES) {
        for (db2 in TO_DATABASES) {
            assign(
                mk_comparison_var(db1, db2),
                misclang$load_rds_or_run_function(
                    get_comparison_cache_filename(db1, db2),
                    load_comparison,
                    get_comparison_filename(db1, db2),
                    # ... don't use filename =; clashes with load_rds_or_run_function
                    probands = get(mk_people_var(db1)),
                    sample = get(mk_people_var(db2))
                ),
                envir = .GlobalEnv
            )
        }
    }
}


# =============================================================================
# Load data
# =============================================================================

# load_all()
