#!/usr/bin/env Rscript
# crate_anon/linkage/analyse_fuzzy_id_match_validate2.R

# =============================================================================
# Notes
# =============================================================================

'
For the main CPFT validation suite.
During testing:

source("C:/srv/crate/src/crate/crate_anon/linkage/analyse_fuzzy_id_match_validate2.R")

or Ctrl-Shift-S to source from RStudio.

Consider also:

- https://rviews.rstudio.com/2019/03/01/some-r-packages-for-roc-curves/

A ggplot resource:

- https://nextjournal.com/jk/best-ggplot

RStudio IDE problems:

- https://community.rstudio.com/t/resizing-ide-window-crashes-ide/78133/2

  or Tools --> Global Options --> General --> Advanced
        Rendering engine = Software

  but more likely the problem was View --> Panes
        and turn off anything to do with zooming.

'

# =============================================================================
# Libraries
# =============================================================================

library(car)  # for car::Anova
library(data.table)
library(ggplot2)
library(gridExtra)
# library(lme4)
# library(lmerTest)
library(lubridate)
library(patchwork)
# library(pROC)
library(RJSONIO)
# library(scales)  # for muted() colours
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

ROW_LIMIT <- -1
# -1 (not Inf) for no limit; positive finite for debugging This works both with
# readLines and data.table::fread, but readLines doesn't accept Inf.

# Theta: absolute log odds threshold for the winner.
# A probability p = 0.5 equates to odds of 1/1 = 1 and thus log odds of 0.
# The maximum log odds will be from comparing a database to itself.
# For CDL, that is about 41.5.
# But maybe it's a little crazy to explore thresholds so high that you would
# always reject everything.

THETA_OPTIONS <- seq(0, 15, by = 1)
# THETA_OPTIONS <- c(0, 5, 10)  # for debugging

# Delta: log odds advantage over the next.
# Again, 0 would be no advantage.

DELTA_OPTIONS <- seq(0, 15, by = 2.5)
# DELTA_OPTIONS <- 10  # for debugging

DEFAULT_THETA <- 5  # see crate_anon.linkage.fuzzy_id_match.FuzzyDefaults
DEFAULT_DELTA <- 10  # ditto


# =============================================================================
# Database constants
# =============================================================================

CDL <- "cdl"
PCMIS <- "pcmis"
RIO <- "rio"
SYSTMONE <- "systmone"

# ALL_DATABASES <- c(CDL, PCMIS, RIO, SYSTMONE)
ALL_DATABASES <- CDL  # for debugging

# FROM_DATABASES <- ALL_DATABASES
FROM_DATABASES <- CDL  # for debugging

# TO_DATABASES <- ALL_DATABASES
# TO_DATABASES <- c(CDL, PCMIS, RIO)  # for debugging
TO_DATABASES <- CDL


# =============================================================================
# Directories, filenames
# =============================================================================

DATA_DIR <- "C:/srv/crate/crate_fuzzy_linkage_validation"
OUTPUT_DIR <- DATA_DIR
OUTPUT_FILE <- file.path(OUTPUT_DIR, "main_results.txt")


get_data_filename <- function(db)
{
    file.path(DATA_DIR, paste0("fuzzy_data_", db, "_hashed.jsonl"))
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
# Factor constants
# =============================================================================

DX_GROUP_SMI <- "SMI"
DX_GROUP_F_NOT_SMI <- "F_not_SMI"
DX_GROUP_OUTSIDE_F <- "codes_not_F"
DX_GROUP_NONE <- "no_codes"
# Should be no NA values for diagnostic_group.
DIAGNOSTIC_GROUP_LEVELS <- c(
    DX_GROUP_NONE,
    DX_GROUP_OUTSIDE_F,
    DX_GROUP_F_NOT_SMI,
    DX_GROUP_SMI
)
# For dx_group_simple, we blend the last two into this:
DX_GROUP_NO_MH <- "no_MH_codes"

ETHNICITY_ASIAN <- "asian"
ETHNICITY_BLACK <- "black"
ETHNICITY_MIXED <- "mixed"
ETHNICITY_WHITE <- "white"
ETHNICITY_OTHER <- "other"
ETHNICITY_UNKNOWN <- "unknown"
# Should be no NA values for ethnicity.
ETHNICITY_LEVELS <- c(
    ETHNICITY_WHITE,  # most common group in UK, so reference category here
    ETHNICITY_ASIAN,
    ETHNICITY_BLACK,
    ETHNICITY_MIXED,
    ETHNICITY_OTHER,
    ETHNICITY_UNKNOWN
)

SEX_F <- "F"
SEX_M <- "M"
SEX_X <- "X"
# In "gender", we have NA for unknown.
GENDER_LEVELS <- c(SEX_F, SEX_M, SEX_X)
# In "sex_simple", we combine X with NA for and use this:
SEX_OTHER_UNKNOWN <- "other_unknown"


# =============================================================================
# Cosmetic constants
# =============================================================================

DEFAULT_VLINE_COLOUR <- "#AAAAAA"
DEFAULT_COLOUR_SCALE_GGPLOT_REVERSED <- scale_colour_gradient(
    low = "#56B1F7",  # ggplot default high
    high = "#132B43"  # ggplot default low: see scale_colour_gradient
)
COLOUR_SCALE_THETA <- scale_colour_gradient(
    # https://ggplot2-book.org/scale-colour.html
    # Show with munsell::hue_slice("5P") and pick a vertical slice.
    low = munsell::mnsl("5P 7/12"),
    high = munsell::mnsl("5P 2/12")
)
COLOUR_SCALE_DELTA <- scale_colour_gradient(
    low = munsell::mnsl("5R 7/8"),
    high = munsell::mnsl("5R 2/8")
)

LINEBREAK_1 <- paste(c(rep("=", 79), "\n"), collapse="")
LINEBREAK_2 <- paste(c(rep("-", 79), "\n"), collapse="")
PAGE_WIDTH_CM <- 17  # A4 with 2cm margins, 210 - 40 mm
PAGE_HEIGHT_CM <- 25.7  # 297 - 40 mm


# =============================================================================
# Basic helper functions
# =============================================================================

all_unique <- function(x)
{
    # return(length(x) == length(unique(x)))
    return(!any(duplicated(x)))
}


write_output <- function(x, append = TRUE, filename = OUTPUT_FILE, width = 1000)
{
    # 1. Output to file
    old_width <- getOption("width")
    options(width = width)
    sink(filename, append = append)
    # 2. Print it
    x_name <- deparse(substitute(x))  # fetch the variable name passed in
    cat(LINEBREAK_1, x_name, "\n", LINEBREAK_2, sep = "")
    print(x)
    cat(LINEBREAK_1)
    # 3. Restore output
    sink()
    options(width = old_width)
    # 4. Sensible/useful return value
    return(x)
}


# =============================================================================
# Loading data and basic preprocessing
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
            "British or mixed British - ethnic category 2001 census" = ETHNICITY_WHITE,  # huge disparity if marked as "mixed"
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
        levels = ETHNICITY_LEVELS
    ))
}


imd_centile_100_most_deprived <- function(index_of_multiple_deprivation)
{
    # index_of_multiple_deprivation: the England IMD, from  1 = Tendring, North
    # East Essex, most deprived in England, through (in CPFT's area) 10 =
    # Waveney, Suffolk, through ~14000 for Kensington & Chelsea via 32785
    # somewhere in South Cambridgeshire to 32844 in Wokingham, Berkshire, the
    # least deprived in England.
    # Waveney's deprivation is confirmed at
    # https://www.eastsuffolk.gov.uk/assets/Your-Council/WDC-Council-Meetings/2016/November/WDC-Overview-and-Scrutiny-Committee-01-11-16/Item-5a-Appendix-A-Hidden-Needs-for-East-Suffolk-Oct-update.pdf
    # Here, we do not correct for population (unlike e.g.
    # Jones et al. 2022, https://pubmed.ncbi.nlm.nih.gov/35477868/), and we
    # simply use the IMD order (so it's the centile for IMD number, not the
    # centile for population). But like Jones 2022, we use a "deprivation"
    # centile, i.e. 0 least deprived, 100 most deprived.
    # See als:
    # - https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/853811/IoD2019_FAQ_v4.pdf

    MOST_DEPRIVED_IMD <- 1
    LEAST_DEPRIVED_IMD <- 32844
    # Confirmed: SELECT MIN(imd), MAX(imd) FROM onspd.dbo.postcode
    return(
        100
        - 100 * (index_of_multiple_deprivation - MOST_DEPRIVED_IMD)
        / (LEAST_DEPRIVED_IMD - MOST_DEPRIVED_IMD)
    )

    # Tests:
    # imd_centile_100_most_deprived(1)  # 100
    # imd_centile_100_most_deprived(32844)  # 0
}


load_people <- function(filename, nrows = ROW_LIMIT, strip_irrelevant = TRUE)
{
    cat(paste0("- Loading from: ", filename, "\n"))
    # Read from JSON lines
    # https://stackoverflow.com/questions/31599299/expanding-a-json-column-in-r
    # https://stackoverflow.com/questions/55120019/how-to-read-a-json-file-line-by-line-in-r
    de_null <- function(x, na_value) {
        # RJSONIO::fromJSON("{'a': null}") produces NULL. rbindlist() later
        # complains, so let's convert NULL to NA explicitly.
        # Likewise empty strings.
        return(
            ifelse(
                is.null(x),
                na_value,
                ifelse(
                    is.na(x) | x == "",
                    na_value,
                    x
                )
            )
        )
        # DO NOT use: is.null(x) | x == ""
        # ... because is.null(NULL) | NULL == "" gives logical(0), not FALSE.
        # x must be a SINGLE VALUE, not a vector; e.g.
        # is.null(c(NULL, 5)) gives FALSE, not c(TRUE, FALSE)
    }
    sep <- ";"
    d <- (
        readLines(filename, n = nrows) %>%
        lapply(RJSONIO::fromJSON, simplify = FALSE) %>%
        lapply(
            function(e) {
                middle_names <- e$middle_names
                m_names <- paste(
                    lapply(middle_names, function(p) p$hashed_name),
                    collapse = sep
                )
                m_name_freq <- paste(
                    lapply(middle_names, function(p) p$name_freq),
                    collapse = sep
                )
                m_metaphones <- paste(
                    lapply(middle_names, function(p) p$hashed_metaphone),
                    collapse = sep
                )
                m_metaphone_freq <- paste(
                    lapply(middle_names, function(p) p$metaphone_freq),
                    collapse = sep
                )

                postcodes <- e$postcodes
                p_start_dates <- paste(
                    lapply(
                        postcodes,
                        function(p) de_null(p$start_date, "")
                    ),
                    collapse = sep
                )
                p_end_dates <- paste(
                    lapply(
                        postcodes,
                        function(p) de_null(p$end_date, "")
                    ),
                    collapse = sep
                )
                p_units <- paste(
                    lapply(postcodes, function(p) p$hashed_postcode_unit),
                    collapse = sep
                )
                p_unit_freq <- paste(
                    lapply(postcodes, function(p) p$unit_freq),
                    collapse = sep
                )
                p_sectors <- paste(
                    lapply(postcodes, function(p) p$hashed_postcode_sector),
                    collapse = sep
                )
                p_sector_freq <- paste(
                    lapply(postcodes, function(p) p$sector_freq),
                    collapse = sep
                )

                other_info <- fromJSON(e$other_info, simplify = FALSE)

                return(list(
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # main
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    local_id = e$local_id,

                    hashed_first_name = de_null(
                        e$first_name$hashed_name,
                        NA_character_
                    ),
                    first_name_frequency = de_null(
                        e$first_name$name_freq,
                        NA_real_
                    ),
                    hashed_first_name_metaphone = de_null(
                        e$first_name$hashed_metaphone,
                        NA_character_
                    ),
                    first_name_metaphone_frequency = de_null(
                        e$first_name$metaphone_freq,
                        NA_real_
                    ),

                    hashed_middle_names = m_names,
                    middle_name_frequencies = m_name_freq,
                    hashed_middle_name_metaphones = m_metaphones,
                    middle_name_metaphone_frequencies = m_metaphone_freq,

                    hashed_surname = de_null(
                        e$surname$hashed_name,
                        NA_character_
                    ),
                    surname_frequency = de_null(
                        e$surname$name_freq,
                        NA_real_
                    ),
                    hashed_surname_metaphone = de_null(
                        e$surname$hashed_metaphone,
                        NA_character_
                    ),
                    surname_metaphone_frequency = de_null(
                        e$surname$metaphone_freq,
                        NA_real_
                    ),

                    hashed_dob = e$dob$hashed_dob,

                    hashed_gender = de_null(
                        e$gender$hashed_gender,
                        NA_character_
                    ),
                    gender_frequency = de_null(
                        e$gender$gender_freq,
                        NA_real_
                    ),

                    hashed_postcode_units = p_units,
                    postcode_unit_frequencies = p_unit_freq,
                    hashed_postcode_sectors = p_sectors,
                    postcode_sector_frequencies = p_sector_freq,
                    postcode_start_dates = p_start_dates,
                    postcode_end_dates = p_end_dates,

                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # other_info
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    hashed_nhs_number = other_info$hashed_nhs_number,

                    blurred_dob = de_null(
                        other_info$blurred_dob,
                        NA_character_
                    ),
                    gender = de_null(
                        other_info$gender,
                        NA_character_
                    ),
                    raw_ethnicity = de_null(
                        other_info$ethnicity,
                        NA_character_
                    ),
                    index_of_multiple_deprivation = de_null(
                        other_info$index_of_multiple_deprivation,
                        NA_integer_
                    ),

                    first_mh_care_date = de_null(
                        other_info$first_mh_care_date,
                        NA_character_
                    ),
                    age_at_first_mh_care = de_null(
                        other_info$age_at_first_mh_care,
                        NA_integer_
                    ),
                    any_icd10_dx_present = other_info$any_icd10_dx_present,
                    chapter_f_icd10_dx_present =
                        other_info$chapter_f_icd10_dx_present,
                    severe_mental_illness_icd10_dx_present =
                        other_info$severe_mental_illness_icd10_dx_present
                ))
            }
        ) %>%
        rbindlist() %>%
        as.data.table()
    )
    cat("  ... loaded; processing...\n")
    d[
        index_of_multiple_deprivation == 0,  # invalid
        index_of_multiple_deprivation := NA_integer_
    ]
    d[local_id == "", local_id := NA_character_]
    d[hashed_nhs_number == "", hashed_nhs_number := NA_character_]
    setkey(d, local_id)
    setcolorder(d, "local_id")

    stopifnot(all(!is.na(d$local_id)))
    stopifnot(all(!is.na(d$hashed_nhs_number)))
    stopifnot(all_unique(d$local_id))
    # this is not guaranteed: stopifnot(all_unique(d$hashed_nhs_number))

    d[, gender := factor(gender, levels = GENDER_LEVELS)]
    sex_renames <- c(
        # Values: new values
        SEX_F,
        SEX_M,
        SEX_OTHER_UNKNOWN
    )
    # ... and names: old values
    names(sex_renames) <- GENDER_LEVELS
    d[, sex_simple := recode_factor(
        as.character(gender),
        # ... as.character() required for ".missing" to work, or we get the
        # error: "`.missing` is not supported for factors"
        !!!sex_renames,
        .missing = SEX_OTHER_UNKNOWN
    )]

    d[, ethnicity := simplified_ethnicity(raw_ethnicity)]
    d[is.na(ethnicity), ethnicity := ETHNICITY_UNKNOWN]
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

    d[, deprivation_centile_100_most_deprived :=
        imd_centile_100_most_deprived(index_of_multiple_deprivation)
    ]

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
            levels = DIAGNOSTIC_GROUP_LEVELS
        )
    ]
    dx_group_renames <- c(
        # Values: new values
        DX_GROUP_NO_MH,
        DX_GROUP_NO_MH,
        DX_GROUP_F_NOT_SMI,
        DX_GROUP_SMI
    )
    # ... and names: old values
    names(dx_group_renames) <- DIAGNOSTIC_GROUP_LEVELS
    d[, dx_group_simple := recode_factor(
        diagnostic_group,
        !!!dx_group_renames
    )]

    if (strip_irrelevant) {
        d[, raw_ethnicity := NULL]
        d[, first_mh_care_date := NULL]
        d[, any_icd10_dx_present := NULL]
        d[, chapter_f_icd10_dx_present := NULL]
        d[, severe_mental_illness_icd10_dx_present := NULL]
    }

    stopifnot(all(!is.na(d$blurred_dob)))
    stopifnot(all(!is.na(d$sex_simple)))
    stopifnot(all(!is.na(d$ethnicity)))
    stopifnot(all(!is.na(d$diagnostic_group)))
    stopifnot(all(!is.na(d$dx_group_simple)))

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
            # "gender",
            "sex_simple",
            "ethnicity",
            "index_of_multiple_deprivation",
            # "first_mh_care_date",
            "age_at_first_mh_care",
            # "any_icd10_dx_present",
            # "chapter_f_icd10_dx_present",
            # "severe_mental_illness_icd10_dx_present",
            # "diagnostic_group",
            "dx_group_simple",

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
# Demographics
# =============================================================================

get_demographics <- function(d, db_name)
{
    results <- data.table(
        db_name = db_name,

        n_total = nrow(d),
        n_duplicated_nhs_number = sum(duplicated(d$hashed_nhs_number)),

        dob_year_min = min(year(d$blurred_dob), na.rm = TRUE),
        dob_year_max = max(year(d$blurred_dob), na.rm = TRUE),
        dob_year_mean = mean(year(d$blurred_dob), na.rm = TRUE),
        dob_year_sd = sd(year(d$blurred_dob), na.rm = TRUE),

        sex_n_female = sum(d$gender == SEX_F, na.rm = TRUE),
        sex_n_male = sum(d$gender == SEX_M, na.rm = TRUE),
        sex_n_other = sum(d$gender == SEX_X, na.rm = TRUE),
        sex_n_unknown = sum(is.na(d$gender)),

        ethnicity_n_asian = sum(d$ethnicity == ETHNICITY_ASIAN, na.rm = TRUE),
        ethnicity_n_black = sum(d$ethnicity == ETHNICITY_BLACK, na.rm = TRUE),
        ethnicity_n_mixed = sum(d$ethnicity == ETHNICITY_MIXED, na.rm = TRUE),
        ethnicity_n_white = sum(d$ethnicity == ETHNICITY_WHITE, na.rm = TRUE),
        ethnicity_n_other = sum(d$ethnicity == ETHNICITY_OTHER, na.rm = TRUE),
        ethnicity_n_unknown = sum(d$ethnicity == ETHNICITY_UNKNOWN, na.rm = TRUE),

        dx_n_smi = sum(d$diagnostic_group == DX_GROUP_SMI, na.rm = TRUE),
        dx_n_f_not_smi = sum(d$diagnostic_group == DX_GROUP_F_NOT_SMI, na.rm = TRUE),
        dx_n_outside_f = sum(d$diagnostic_group == DX_GROUP_OUTSIDE_F, na.rm = TRUE),
        dx_n_none = sum(d$diagnostic_group == DX_GROUP_NONE, na.rm = TRUE),

        deprivation_centile_min = min(d$deprivation_centile_100_most_deprived, na.rm = TRUE),
        deprivation_centile_max = max(d$deprivation_centile_100_most_deprived, na.rm = TRUE),
        deprivation_centile_mean = mean(d$deprivation_centile_100_most_deprived, na.rm = TRUE),
        deprivation_centile_sd = sd(d$deprivation_centile_100_most_deprived, na.rm = TRUE),
        deprivation_centile_n_unknown = sum(is.na(d$deprivation_centile_100_most_deprived)),

        age_at_first_mh_care_min = min(d$age_at_first_mh_care, na.rm = TRUE),
        age_at_first_mh_care_max = max(d$age_at_first_mh_care, na.rm = TRUE),
        age_at_first_mh_care_mean = mean(d$age_at_first_mh_care, na.rm = TRUE),
        age_at_first_mh_care_sd = sd(d$age_at_first_mh_care, na.rm = TRUE),
        age_at_first_mh_care_n_unknown = sum(is.na(d$age_at_first_mh_care))
    )

    results[, sex_pct_female := 100 * sex_n_female / n_total]
    results[, sex_pct_male := 100 * sex_n_male / n_total]
    results[, sex_pct_other := 100 * sex_n_other / n_total]
    results[, sex_pct_unknown := 100 * sex_n_unknown / n_total]

    results[, ethnicity_pct_asian := 100 * ethnicity_n_asian / n_total]
    results[, ethnicity_pct_black := 100 * ethnicity_n_black / n_total]
    results[, ethnicity_pct_mixed := 100 * ethnicity_n_mixed / n_total]
    results[, ethnicity_pct_white := 100 * ethnicity_n_white / n_total]
    results[, ethnicity_pct_other := 100 * ethnicity_n_other / n_total]
    results[, ethnicity_pct_unknown := 100 * ethnicity_n_unknown / n_total]

    results[, dx_pct_smi := 100 * dx_n_smi / n_total]
    results[, dx_pct_f_not_smi := 100 * dx_n_f_not_smi / n_total]
    results[, dx_pct_outside_f := 100 * dx_n_outside_f / n_total]
    results[, dx_pct_none := 100 * dx_n_none / n_total]

    results[, deprivation_centile_pct_unknown :=
        100 * deprivation_centile_n_unknown / n_total]

    results[, age_at_first_mh_care_pct_unknown :=
        100 * age_at_first_mh_care_n_unknown / n_total]

    return(results)
}

get_all_demographics <- function()
{
    combined <- NULL
    for (db in ALL_DATABASES) {
        dg <- get_demographics(get(mk_people_var(db)), db)
        combined <- rbind(combined, dg)
    }
    return(combined)
}


# =============================================================================
# Comparisons
# =============================================================================

compare_simple <- function(from_dbname, to_dbname, compdata)
{
    d <- data.table(
        # In:
        from = from_dbname,
        to = to_dbname,
        # Out:
        n_overlap = sum(compdata$proband_in_sample)
    )
    return(d)
}


get_comparisons_simple <- function()
{
    comp_simple <- NULL
    for (db1 in FROM_DATABASES) {
        for (db2 in TO_DATABASES) {
            comp_simple <- rbind(
                comp_simple,
                compare_simple(
                    db1,
                    db2,
                    get(mk_comparison_var(db1, db2))
                )
            )
        }
    }
    return(comp_simple)
}


decide_at_thresholds <- function(compdata, theta, delta)
{
    # Makes a copy of the data supplied and applies decision thresholds.
    d <- data.table::copy(compdata)
    d[, declare_match := (
        # Criterion A:
        log_odds_match >= theta
        # Criterion B:
        & log_odds_match >= second_best_log_odds + delta
    )]

    # Extreme caution here, because we have two aspects: detecting that someone
    # is in the sample, and finding the correct person. The SDT methods need
    # everything to add up, so we deal with these separately. (We do *not* say
    # that a "hit" is declaring a match and the best candidate being correct.)
    # So, the first phase:
    d[, hit := declare_match & proband_in_sample]
    d[, false_alarm := declare_match & !proband_in_sample]
    d[, correct_rejection := !declare_match & !proband_in_sample]
    d[, miss := !declare_match & proband_in_sample]

    # And the second:
    d[, correctly_identified := declare_match & best_candidate_correct]
    d[, misidentified := declare_match & !best_candidate_correct]

    return(d)
}


compare_at_thresholds <- function(
    from_dbname, to_dbname, theta, delta, compdata, with_obscure = FALSE
)
{
    decided <- decide_at_thresholds(compdata, theta, delta)

    d <- data.table(
        # In:
        from = from_dbname,
        to = to_dbname,
        theta = theta,
        delta = delta,
        # Out:
        n = nrow(decided),
        n_tp = sum(decided$hit),  # true positive
        n_fp = sum(decided$false_alarm),  # false positive
        n_tn = sum(decided$correct_rejection),  # true negative
        n_fn = sum(decided$miss),  # false negative

        n_identified = sum(decided$declare_match),
        n_correctly_identified = sum(decided$correctly_identified),
        n_misidentified = sum(decided$misidentified)
    )

    # Standard derived SDT measures
    # https://en.wikipedia.org/wiki/Receiver_operating_characteristic
    # Capitals to look pretty in graphs automatically.
    d[, n_p := n_tp + n_fn]  # positive: proband in sample
    d[, n_n := n_tn + n_fp]  # negative: proband not in sample
    d[, TPR := n_tp / n_p]  # sensitivity, recall, hit rate, true pos. rate
    d[, TNR := n_tn / n_n]  # specificity, selectivity, true neg. rate
    d[, PPV := n_tp / (n_tp + n_fp)]
    d[, NPV := n_tn / (n_tn + n_fn)]
    d[, FNR := n_fn / n_p]  # miss rate, false neg. rate
    d[, FPR := n_fp / n_n]  # false pos. rate
    d[, FDR := n_fp / (n_fp + n_tp)]  # false discovery rate
    d[, FOR := n_fn / (n_fn + n_tn)]  # false omission rate
    d[, Prevalence := n_p / n]  # = n_p / (n_p + n_n)
    d[, Accuracy := (n_tp + n_tn) / n]  # proportion of decisions correct
    d[, F1 := 2 * n_tp / (2 * n_tp + n_fp + n_fn)]
    if (with_obscure) {
        d[, LR_pos := TPR / FPR]
        d[, LR_neg := FNR / TNR]
        d[, PT :=
             sqrt(FPR) / (sqrt(TPR) + sqrt(FPR))
        ]
        d[, TS_CSI := n_tp / (n_tp + n_fn + n_fp)]
        d[, Balanced_accuracy :=
            (TPR + TNR) / 2
        ]
        # ... etc.
    }

    # And for our second phase:
    d[, MID := n_misidentified / n_identified]  # misidentification rate

    # Checks
    stopifnot(d$n_p == sum(decided$proband_in_sample))
    stopifnot(d$n_n == sum(!decided$proband_in_sample))
    stopifnot(all(d$n_tp + d$n_fp + d$n_tn + d$n_fn == d$n))

    return(d)
}


get_comparisons_varying_threshold <- function()
{
    comp_thresholds <- NULL
    for (db1 in FROM_DATABASES) {
        for (db2 in TO_DATABASES) {
            for (theta in THETA_OPTIONS) {
                for (delta in DELTA_OPTIONS) {
                    comp_thresholds <- rbind(
                        comp_thresholds,
                        compare_at_thresholds(
                            db1,
                            db2,
                            theta,
                            delta,
                            get(mk_comparison_var(db1, db2))
                        )
                    )
                }
            }
        }
    }
    return(comp_thresholds)
}


bias_at_threshold <- function(
    compdata,
    theta = DEFAULT_THETA,
    delta = DEFAULT_DELTA
)
{
    # Make decisions. We only care about probands who are in the sample.
    decided <- decide_at_thresholds(
        compdata[proband_in_sample == TRUE],
        theta,
        delta
    )
    decided[, birth_year := year(blurred_dob)]
    m <- glm(
        declare_match ~
            birth_year
                + sex_simple
                + ethnicity
                + deprivation_centile_100_most_deprived
                # + age_at_first_mh_care
                + dx_group_simple,
        family = binomial(link = "logit"),
        data = decided
    )
    # Downs (2019) used age_at_first_mh_care, but it is poorly coded and likely
    # confounded to some degree with birth year.
    #
    # tmp <- decided[!is.na(age_at_first_mh_care)]
    # cor(tmp$birth_year, tmp$age_at_first_mh_care)  # -0.98 ! Yes, very.

    return(m)
}


# =============================================================================
# Plots
# =============================================================================

mk_generic_pairwise_plot <- function(
    comp_threshold,
    depvars,
    linetypes,
    shapes,
    x_is_theta,  # if FALSE, x is delta
    vline_colour = DEFAULT_VLINE_COLOUR,
    with_overlap_label = FALSE,
    comp_simple = NULL,
    overlap_label_y = 0.25,
    overlap_label_vjust = 0,  # vcentre
    overlap_label_x = max(THETA_OPTIONS),
    overlap_label_hjust = 1,  # 0 = left-justify, 1 = right-justify
    overlap_label_size = 2,
    diagonal_colour = "black",
    diagonal_background_alpha = 0.1
)
{
    CORE_VARS <- c("from", "to", "theta", "delta")
    required_vars <- c(CORE_VARS, depvars)
    d <- (
        comp_threshold
        %>% select(!!!required_vars)
        %>% pivot_longer(
            all_of(depvars),
            names_to = "quantity",
            values_to = "value"
        )
        %>% mutate(
            # Get the ordering right, for the scales.
            quantity = factor(quantity, levels = depvars)
        )
        %>% as.data.table()
    )
    facet_data_diagonal <- unique(d[, .(from, to)])[from == to]
    if (x_is_theta) {
        xvar <- "theta"
        colourvar <- "delta"
        # d[, x_factor := as.factor(theta)]
        d[, x_grouper := paste0(quantity, "_", delta)]
        vline_xintercept <- DEFAULT_THETA
        colour_scale <- COLOUR_SCALE_THETA

    } else {
        # x is delta
        xvar <- "delta"
        colourvar <- "theta"
        # d[, x_factor := as.factor(delta)]
        d[, x_grouper := paste0(quantity, "_", theta)]
        vline_xintercept <- DEFAULT_DELTA
        colour_scale <- COLOUR_SCALE_DELTA
    }
    y_label <- paste(depvars, collapse = ", ")

    p <- (
        ggplot(
            d,
            aes_string(
                x = xvar,
                y = "value",
                group = "x_grouper",
                colour = colourvar,
                linetype = "quantity",
                shape = "quantity"
            )
        )
        + geom_rect(
            # Make the leading diagonal panels a different colour.
            # ggplot doesn't support altering the facet colours in a systematic
            # way. However:
            # - https://stackoverflow.com/questions/6750664
            # - https://www.cedricscherer.com/2019/08/05/a-ggplot2-tutorial-for-beautiful-plotting-in-r/#panels
            # - https://stackoverflow.com/questions/9847559/conditionally-change-panel-background-with-facet-grid
            #   ... last of these is the best by far.
            # Put the geom_rect at the bottom (first).
            data = facet_data_diagonal,
            aes(
                # Reset to NULL anything set in the top-level aes() or
                # aes_string() call.
                x = NULL,
                y = NULL,
                group = NULL,
                colour = NULL,
                linetype = NULL,
                shape = NULL
            ),
            xmin = -Inf,
            xmax = Inf,
            ymin = -Inf,
            ymax = Inf,
            fill = diagonal_colour,
            alpha = diagonal_background_alpha
        )
        + geom_vline(
            xintercept = vline_xintercept,
            colour = vline_colour
        )
        + geom_line()
        + geom_point()
        + facet_grid(from ~ to)
        + theme_bw()
        + scale_linetype_manual(values = linetypes)
        + scale_shape_manual(values = shapes)
        + colour_scale
        + ylab(y_label)
    )
    if (with_overlap_label) {
        if (is.null(comp_simple)) {
            stop("Must specify comp_simple to use with_overlap_label")
        }
        cs <- data.table::copy(comp_simple)
        cs[, overlap_label := paste0("o = ", n_overlap)]
        p <- (
            p
            + geom_text(
                data = cs,
                mapping = aes(
                    label = overlap_label,
                    # implicit (for facet plot): from, to
                    group = NULL,
                    colour = NULL,
                    linetype = NULL,
                    shape = NULL
                ),
                x = overlap_label_x,
                hjust = overlap_label_hjust,
                y = overlap_label_y,
                vjust = overlap_label_vjust,
                size = overlap_label_size
            )
        )
    }
    return(p)
}


mk_threshold_plot_sdt <- function(comp_threshold, x_is_theta, ...)
{
    # The quantities that are informative and independent of the prevalence
    # (and thus reflect qualities of the test) include TPR (sensitivity,
    # recall), TNR (specificity), FPR (false alarm rate), and FNR (miss rate).
    #
    # Those that are affected by prevalence include PPV (precision), NPV.
    #
    # TNR = 1 - FPR, and TPR = 1 - FNR, so no need to plot both.
    # Let's use: TPR, FPR.
    return(mk_generic_pairwise_plot(
        comp_threshold,
        depvars = c("TPR", "FPR"),
        linetypes = c("solid", "dotted", "dotted"),
        shapes = c(24, 25),  # up triangle, down triangle
        x_is_theta = x_is_theta,
        ...
    ))
}


mk_threshold_plot_mid <- function(comp_threshold, x_is_theta, ...)
{
    return(mk_generic_pairwise_plot(
        comp_threshold,
        depvars = "MID",
        linetypes = "solid",
        shapes = 4,  # X
        x_is_theta = x_is_theta,
        ...
    ))
}


mk_save_performance_plot <- function(comp_threshold, comp_simple)
{
    panel_a <- mk_threshold_plot_sdt(
        comp_threshold,
        x_is_theta = TRUE,
        with_overlap_label = TRUE,
        comp_simple = comp_simple
    )
    panel_b <- mk_threshold_plot_sdt(comp_threshold, x_is_theta = FALSE)
    panel_c <- mk_threshold_plot_mid(comp_threshold, x_is_theta = TRUE)
    panel_d <- mk_threshold_plot_mid(comp_threshold, x_is_theta = FALSE)
    composite <- (
        (panel_a | panel_b) /
        (panel_c | panel_d)
    ) + plot_annotation(tag_levels = "A")
    ggsave(
        file.path(OUTPUT_DIR, "fig_pairwise_thresholds.pdf"),
        composite,
        width = PAGE_WIDTH_CM * 1.1 * 2,
        height = PAGE_HEIGHT_CM * 1.1,
        units = "cm"
    )
}


# =============================================================================
# Failure analysis
# =============================================================================

people_missingness_summary <- function(people)
{
    n <- nrow(people)
    prop_missing <- function(x) {
        sum(is.na(x)) / n
    }
    return(
        people
        %>% summarize(
            # Strings can be "" not NA, but frequencies are NA if missing.
            missing_first_name = prop_missing(first_name_frequency),
            missing_middle_names = prop_missing(middle_name_frequencies),
            missing_surname = prop_missing(surname_frequency),
            missing_gender = prop_missing(gender_frequency),
            missing_postcode = prop_missing(postcode_unit_frequencies)
        )
        %>% as.data.table()
    )
}


extract_miss_info <- function(
    probands, sample, comparison,
    theta = DEFAULT_THETA, delta = DEFAULT_DELTA,
    allow.cartesian = TRUE  # for duplicate NHS numbers, i.e. PCMIS
)
{
    decided <- decide_at_thresholds(comparison, theta, delta)
    comp_misses <- decided[proband_in_sample & !declare_match]
    person_columns <- c(
        # For linkage
        "hashed_nhs_number",
        # For error exploration
        "hashed_first_name", "first_name_frequency",
        "hashed_first_name_metaphone", "first_name_metaphone_frequency",
        "hashed_middle_names", "middle_name_frequencies",
        "hashed_middle_name_metaphones", "middle_name_metaphone_frequencies",
        "hashed_surname", "surname_frequency",
        "hashed_surname_metaphone", "surname_metaphone_frequency",
        "hashed_dob",  # all frequencies the same
        "hashed_gender", "gender_frequency",
        "hashed_postcode_units", "postcode_unit_frequencies",
        "hashed_postcode_sectors", "postcode_sector_frequencies",
        # For bias analysis
        "blurred_dob",
        "gender",
        "sex_simple",
        "deprivation_centile_100_most_deprived",
        "diagnostic_group",
        "dx_group_simple"
    )
    miss_hashed_nhs <- comp_misses$hashed_nhs_number_proband
    failure_info <- merge(  # fi = failure_info
        x = probands[hashed_nhs_number %in% miss_hashed_nhs, ..person_columns],
        y = sample[hashed_nhs_number %in% miss_hashed_nhs, ..person_columns],
        by.x = "hashed_nhs_number",
        by.y = "hashed_nhs_number",
        all.x = TRUE,
        all.y = FALSE,
        suffixes = c("_proband", "_sample"),
        allow.cartesian = allow.cartesian
    )
    return(failure_info)
}


failure_summary <- function(failure_info)
{
    n <- nrow(failure_info)
    prop_missing <- function(x) {
        sum(is.na(x)) / n
    }
    mismatch <- function(x, y) {
        return(!is.na(x) & !is.na(y) & x != y)
    }
    prop_mismatch <- function(x, y) {
        sum(mismatch(x, y)) / n
    }
    failure_summary <- (
        failure_info
        %>% summarize(
            n_missed = n,

            proband_missing_first_name = prop_missing(first_name_frequency_proband),
            proband_missing_middle_names = prop_missing(middle_name_frequencies_proband),
            proband_missing_surname = prop_missing(surname_frequency_proband),
            proband_missing_gender = prop_missing(gender_frequency_proband),
            proband_missing_postcode = prop_missing(postcode_unit_frequencies_proband),

            sample_missing_first_name = prop_missing(first_name_frequency_sample),
            sample_missing_middle_names = prop_missing(middle_name_frequencies_sample),
            sample_missing_surname = prop_missing(surname_frequency_sample),
            sample_missing_gender = prop_missing(gender_frequency_sample),
            sample_missing_postcode = prop_missing(postcode_unit_frequencies_sample),

            mismatch_first_name = prop_mismatch(
                hashed_first_name_proband,
                hashed_first_name_sample
            ),
            mismatch_first_name_metaphone = prop_mismatch(
                hashed_first_name_metaphone_proband,
                hashed_first_name_metaphone_sample
            ),
            mismatch_surname = prop_mismatch(
                hashed_surname_proband,
                hashed_surname_sample
            ),
            mismatch_surname_metaphone = prop_mismatch(
                hashed_surname_metaphone_proband,
                hashed_surname_metaphone_sample
            ),
            mismatch_dob = prop_mismatch(
                hashed_dob_proband,
                hashed_dob_sample
            ),
            mismatch_gender = prop_mismatch(
                hashed_gender_proband,
                hashed_gender_sample
            ),
            firstname_surname_swapped = sum(
                mismatch(hashed_first_name_proband, hashed_first_name_sample)
                & mismatch(hashed_surname_proband, hashed_surname_sample)
                & (hashed_first_name_proband == hashed_surname_sample)
                & (hashed_surname_proband == hashed_first_name_sample)
            ) / n
        )
        %>% as.data.table()
    )
}


performance_summary_at_threshold <- function(
    theta = DEFAULT_THETA,
    delta = DEFAULT_DELTA
)
{
    perf_summ <- NULL
    for (db1 in FROM_DATABASES) {
        for (db2 in TO_DATABASES) {
            probands <- get(mk_people_var(db1))
            sample <- get(mk_people_var(db2))
            comparison <- get(mk_comparison_var(db1, db2))
            main_performance_summary <- compare_at_thresholds(
                from_dbname = db1,
                to_dbname = db2,
                theta = theta,
                delta = delta,
                comparison
            )
            failure_info <- failure_summary(
                extract_miss_info(
                    probands,
                    sample,
                    comparison,
                    theta = theta,
                    delta = delta
                )
            )
            combined_summary <- cbind(main_performance_summary, failure_info)
            perf_summ <- rbind(perf_summ, combined_summary)
        }
    }
    return(perf_summ)
}


# =============================================================================
# Main
# =============================================================================

main <- function()
{
    load_all()

    write_output(paste("Starting:", Sys.time()), append = FALSE)

    # Basic checks
    write_output(people_missingness_summary(people_cdl))  # middle names missing as expected
    write_output(people_missingness_summary(people_pcmis))  # OK
    write_output(people_missingness_summary(people_rio))  # OK
    write_output(people_missingness_summary(people_systmone))  # OK

    # Demographics
    dg <- get_all_demographics()
    write_output(dg)
    write_output(t(dg))

    # Working:
    comp_simple <- get_comparisons_simple()
    comp_threshold <- get_comparisons_varying_threshold()

    # Performance figure
    mk_save_performance_plot(comp_threshold, comp_simple)

    comp_at_defaults <- comp_threshold[
        theta == DEFAULT_THETA & delta == DEFAULT_DELTA
    ]
    write_output(comp_at_defaults)

    # Factors associated with non-linkage
    m <- bias_at_threshold(compare_rio_to_systmone)  # at default thresholds
    write_output(summary(m))
    # Estimate = 0 is no effect, >0 more likely to be linked, <0 less likely.
    # Estimates are of log odds.
    write_output(car::Anova(m, type = "III", test.statistic = "F"))

    # Reasons for non-linkage, etc.
    pst <- performance_summary_at_threshold()
    write_output(pst)
    # !!! WARNING: the calculation for duplicate NHS numbers needs thought.
    #     See allow.cartesian above.

    pst_simplified <- (
        pst
        %>% select(from, to, TPR, FPR, TNR, MID)
        %>% as.data.table()
    )
    write_output(pst_simplified)

    # Not done: demographics predicting specific sub-reasons for non-linkage.
    # (We predict overall non-linkage above.)

    write_output(paste("Finished:", Sys.time()))
}

# main()

# TODO: handle multiple options for first name, surname?
#   *** see Downs paper; use some of those strategies?
#   *** aliases
#   *** former surnames
#   *** forename comparison to middle name
#   *** first two characters of forename
#   ? generic Name that is a kind of TemporalIdentifier?
#   - main tricky bit is the identifiable file format; needs to be easy

# TODO: use empirical estimates of remaining error types; see FuzzyDefaults

# TODO: rethink analytically about the PCMIS NHS# duplication problem

# TODO: document new DOB matching
