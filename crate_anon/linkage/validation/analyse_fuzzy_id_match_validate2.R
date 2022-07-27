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
library(colorspace)
library(data.table)
library(ggplot2)
library(gridExtra)
# library(lme4)
# library(lmerTest)
library(lubridate)
library(patchwork)
library(pROC)
library(RJSONIO)
library(scales)  # for muted() colours or rescale()
library(tidyverse)

RLIB_STEM <- "https://egret.psychol.cam.ac.uk/rlib/"
source(paste0(RLIB_STEM, "debugfunc.R"))
source(paste0(RLIB_STEM, "miscfile.R"))
source(paste0(RLIB_STEM, "misclang.R"))
source(paste0(RLIB_STEM, "miscmath.R"))
source(paste0(RLIB_STEM, "miscplot.R"))

debugfunc$wideScreen()


# =============================================================================
# Governing constants
# =============================================================================

TWO_STAGE_SDT_METHOD <- TRUE  # See paper as to why I think this is right.
WEIGHT_MISIDENTIFICATION <- 20
# ... weighting for determining optimal settings; versus FNR.

# Maximum number of rows to read from each file.
ROW_LIMIT <- -1
# -1 (not Inf) for no limit; positive finite for debugging This works both with
# readLines and data.table::fread, but readLines doesn't accept Inf.

# Theta: absolute log odds threshold for the winner.
# A probability p = 0.5 equates to odds of 1/1 = 1 and thus log odds of 0.
# The maximum log odds will be from comparing a database to itself.
# For CDL, that is about 41.5.
# But maybe it's a little crazy to explore thresholds so high that you would
# always reject everything.

# Values for the theta parameter to explore: minimum standalone log odds for a
# match.
THETA_OPTIONS <- seq(0, 15, by = 1)
# THETA_OPTIONS <- c(0, 5, 10)  # for debugging

# Values for the delta parameter to explore: log odds advantage over the next.
# Again, 0 would be no advantage.
DELTA_OPTIONS <- seq(0, 15, by = 1)
# DELTA_OPTIONS <- 10  # for debugging

# Default values for theta and delta.
DEFAULT_THETA <- 5  # see crate_anon.linkage.fuzzy_id_match.FuzzyDefaults
DEFAULT_DELTA <- 0  # ditto

HASH_LENGTH <- 32  # length of an individual hashed identifier


# =============================================================================
# Database constants
# =============================================================================

# -----------------------------------------------------------------------------
# Labels
# -----------------------------------------------------------------------------

CDL <- "cdl"
PCMIS <- "pcmis"
RIO <- "rio"
SYSTMONE <- "systmone"

DATABASE_LABEL_MAP <- c(
    cdl = "CDL",
    pcmis = "PCMIS (*)",  # highlight the oddity -- duplicate NHS numbers
    rio = "RiO",
    systmone = "SystmOne"
)

# -----------------------------------------------------------------------------
# Loading
# -----------------------------------------------------------------------------

ALL_DATABASES <- c(CDL, PCMIS, RIO, SYSTMONE)
# ALL_DATABASES <- CDL  # for debugging

# -----------------------------------------------------------------------------
# Comparing
# -----------------------------------------------------------------------------

FROM_DATABASES <- ALL_DATABASES
# FROM_DATABASES <- CDL  # for debugging
# FROM_DATABASES <- RIO  # for debugging

TO_DATABASES <- ALL_DATABASES
# TO_DATABASES <- c(CDL, PCMIS, RIO)  # for debugging
# TO_DATABASES <- CDL  # for debugging
# TO_DATABASES <- SYSTMONE  # for debugging


# =============================================================================
# Directories, filenames
# =============================================================================

DATA_DIR <- "C:/srv/crate/crate_fuzzy_linkage_validation"
OUTPUT_DIR <- DATA_DIR
OUTPUT_FILE <- file.path(OUTPUT_DIR, "main_results.txt")
PST_OUTPUT_FILE_DEFAULTS <- file.path(
    OUTPUT_DIR, "performance_summary_at_default_threshold.csv"
)
PST_OUTPUT_FILE_ZERO <- file.path(
    OUTPUT_DIR, "performance_summary_at_zero_threshold.csv"
)
PST_OUTPUT_FILE_NEG_INF <- file.path(
    OUTPUT_DIR, "performance_summary_at_negative_infinity_threshold.csv"
)
PST_OUTPUT_FILE_THETA_DELTA_15 <- file.path(
    OUTPUT_DIR, "performance_summary_at_theta_delta_15.csv"
)


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
# Variable names, in the global environment
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

scale_colour_sequential_highlighted <- function(
    palette_fn,
    highlight_values = c(0.5),
    highlight_colours = c("yellow"),
    scale_from = c(0, 1),
    bandwidth = (scale_from[2] - scale_from[1]) * 0.01,
    granularity = 100,  # for method == "discrete"
    ...
) {
    # Returns a scale_colour_gradientn() with a palette that ranges from
    # ``low`` to ``high`` but produces entirely different colours as defined by
    # ``highlight_values_to_colours`` (with narrow bands around them as defined
    # by ``bandwidth``).
    #
    # Args:
    #   palette_fn:
    #       A function that can be called as palette_fn(n) to generate a vector
    #       of n colours, the base colours for our scale.
    #   highlight_values:
    #       Numeric values at which to modify the colours.
    #   highlight_colours:
    #       Corresponding colours; must be the same length as
    #       ``highlight_values``.
    #   bandwidth:
    #       The "band" around each value (i.e. +/- bandwidth/2) to colour,
    #       typically a narrow value.
    #   method:
    #       - "discrete": Make a discrete series of colours, albeit with fine
    #         granularity.
    #       - "continuous": truly continuous scale (NOT WORKING; SEE NOTES).
    #   scale_from:
    #       Internally, ggplot uses scales from 0-1. You can specify
    #       ``values_to_colours`` and ``bandwidth`` on the scale of values
    #       being plotted, but you should then specify ``scale_from =
    #       c(min_value, max_value)`` to scale appropriately.
    #   granularity:
    #       Number of colours from low to high (because I can't get a truly
    #       continuous method to work.

    n_values <- length(highlight_values)
    stopifnot(n_values > 0)
    stopifnot(n_values == length(highlight_colours))

    lower_bounds <- highlight_values - bandwidth / 2
    upper_bounds <- highlight_values + bandwidth / 2

    colours <- palette_fn(granularity)
    corresponding_values <- seq(
        scale_from[1], scale_from[2], length.out = granularity
    )
    for (i in 1:n_values) {
        colours[
            lower_bounds[i] <= corresponding_values
            & corresponding_values <= upper_bounds[i]
        ] <- highlight_colours[i]
    }
    return(
        scale_colour_gradientn(colours = colours, ...)
    )

    # Notes:
    # - for scale_colour_manual(), the "palette" parameter is not meant to
    #   be used and the docs are in error. You get the error "cannot coerce
    #   type 'closure' to vector of type 'character'". See
    #   https://github.com/tidyverse/ggplot2/issues/3182. Unclear if that
    #   also affects scale_colour_gradient(), but maybe. I've certainly
    #   failed to get it working.
    # - Related:
    #   https://stackoverflow.com/questions/50118741/ggplot2-colorbar-with-discontinuous-jump-for-skewed-data/50129388
    # - https://stackoverflow.com/questions/66736932/create-single-ggplot-gradient-color-scheme-with-a-discontinuous-function
}
if (FALSE) {
    # Test:
    original_palette_fn <- scale_colour_gradient(
        low = "blue", high = "red"
    )$palette
    print(
        ggplot(
            data.frame(
                x = seq(1, 10, by = 0.1),
                y = seq(1, 10, by = 0.1)
            ),
            aes(x = x, y = y, colour = y)
        )
        + geom_point()
        + scale_colour_sequential_highlighted(
            palette_fn = colorRampPalette(c("blue", "red")),
            highlight_values = c(4, 6),
            highlight_colours = c("yellow", "green"),
            bandwidth = 0.5,
            scale_from = c(1, 10)
        )
    )
}


DEFAULT_VLINE_COLOUR <- "#AAAAAA"
DEFAULT_COLOUR_SCALE_GGPLOT_REVERSED <- scale_colour_gradient(
    low = "#56B1F7",  # ggplot default high
    high = "#132B43"  # ggplot default low: see scale_colour_gradient
)

# - https://ggplot2-book.org/scale-colour.html
# - https://cran.r-project.org/web/packages/munsell/munsell.pdf
# - https://en.wikipedia.org/wiki/Munsell_color_system  <-- This!
# - https://colorusage.arc.nasa.gov/discrim.php
# - https://colorspace.r-forge.r-project.org/
# - https://www.nceas.ucsb.edu/sites/default/files/2020-04/colorPaletteCheatsheet.pdf
#
# MUNSELL: Show with munsell::hue_slice("5P"). This illustrates a
# two-dimensional slice at the hue "5P" = the centre of P(urple). All the
# colours shown have the same hue. The horizontal direction of what you'll see
# is chroma (increasing to the right) and the vertical direction is "value"
# (from 0 black to 1 white, upwards). Then pick a vertical sub-slice, e.g. "5P
# x/12"; all colours in that vertical slice have the same chroma. Pick two
# values and create a gradient between them. The notation is "hue
# value/chroma". Show all with hue_slice().
#
# COLORSPACE:
#       library(colorspace); hcl_palettes(n = 16, plot=TRUE)
# ... consider: Batlow; Lajolla; Plasma; Viridis
#
# R BASE COLOURS:
#       colors()
#       col2rgb("green")  # 0, 255, 0
#       col2hcl("green")  # "#00FF00"

# GRADIENT_FN: should be callable as fn(n_colours).
#
GRADIENT_FN <- colorRampPalette(c("blue", "red"))
# GRADIENT_FN <- colorRampPalette(c(munsell::mnsl("5G 9/6"), munsell::mnsl("5G 4/6"))
# GRADIENT_FN <- colorRampPalette(c(munsell::mnsl("5P 7/12"), munsell::mnsl("5P 2/12"))
# GRADIENT_FN <- function(n) colorspace::sequential_hcl(n, palette = "Batlow")

# HIGHLIGHT <- "darkorange"  # FF8C00
# HIGHLIGHT <- "blue"  # 0000FF
# HIGHLIGHT <- "darkgreen"  # 006400
# HIGHLIGHT <- "#00BB00"  # a green
# HIGHLIGHT <- "#646400"  # very dark yellow
HIGHLIGHT <- "black"

COLOUR_SCALE_THETA <- scale_colour_sequential_highlighted(
    palette_fn = GRADIENT_FN,
    highlight_values = DEFAULT_THETA,
    highlight_colours = HIGHLIGHT,
    scale_from = range(THETA_OPTIONS),
    bandwidth = 1  # +/- 0.5, so no overlap with the next; see THETA_OPTIONS
)
COLOUR_SCALE_DELTA <- scale_colour_sequential_highlighted(
    palette_fn = GRADIENT_FN,
    highlight_values = DEFAULT_DELTA,
    highlight_colours = HIGHLIGHT,
    scale_from = range(DELTA_OPTIONS),
    bandwidth = 1  # +/- 0.5, so no overlap with the next; see DELTA_OPTIONS
)
# Check: COLOUR_SCALE_DELTA$map(rescale(DELTA_OPTIONS)). Should
# provide colours for all values. IF THAT FAILS, ggplot2 is too old -- v3.3.6
# works, v3.3.2 doesn't. It's a difference in scale_colour_manual(). Try:
# update.packages("ggplot2"), or use RStudio to update all.

LINEBREAK_1 <- paste(c(rep("=", 79), "\n"), collapse="")
LINEBREAK_2 <- paste(c(rep("-", 79), "\n"), collapse="")
PAGE_WIDTH_CM <- 17  # A4 with 2cm margins, 210 - 40 mm
PAGE_HEIGHT_CM <- 25.7  # 297 - 40 mm

DIAGONAL_PANEL_BG_COLOUR <- "black"
DIAGONAL_PANEL_BG_ALPHA <- 0.1

LABEL_SIZE <- 2


# =============================================================================
# Basic helper functions
# =============================================================================

all_unique <- function(x)
{
    # Are all the values in x distinct (unique)?

    # return(length(x) == length(unique(x)))
    return(!any(duplicated(x)))
}


part_of_duplicated_group <- function(x)
{
    # For every value of x, return TRUE/FALSE according to whether the is
    # duplicated within x.
    #
    # If you count based on duplicated(), you count the "extras"; for example,
    # for
    #       x <- c(1, 1, 1, 2, 3, 4)
    # then
    #       sum(duplicated(x))
    # is 2 (the second and third items are the duplicates). But for "the number
    # of records with a duplicated NHS number" we would want 3 here. Hence this
    # function which returns a boolean vector, like duplicated(), but includes
    # the first item. So
    #       part_of_duplicated_group(x)
    # returns
    #       [1]  TRUE  TRUE  TRUE FALSE FALSE FALSE

    duplicates <- unique(x[duplicated(x)])
    return(x %in% duplicates)
}


n_with_duplicates <- function(x)
{
    # Return the number of values with x that are duplicated (including the
    # first such value of each duplicated set, which is not standard R
    # behaviour; see above).

    return(sum(part_of_duplicated_group(x)))
}


n_unique_duplicates <- function(x)
{
    # Returns the number of unique values that are duplicated within x.
    # For example, if x is c(1, 1, 1, 2, 3, 4), this is 1.
    # If x is c(1, 1, 2, 2, 3, 3, 4), this is 3 (three values are duplicated).

    duplicates <- unique(x[duplicated(x)])
    return(length(duplicates))
}


write_output <- function(
    x, append = TRUE, filename = OUTPUT_FILE, width = 1000
) {
    # Write an R object to a results file.

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


format_sig_fig <- function(x, sf = 3)
{
    # Format a number to a certain number of significant figures.

    formatC(signif(x, digits = sf), digits = sf, format = "fg", flag = "#")
}


`%!=na%` <- function(e1, e2)
{
    # "Not equal, treating NA like a level."
    #
    # Use like this:
    # a <- c(1, NA, 2, 2, NA)
    # b <- c(1, 1, 1, NA, NA)
    # a %!=na% b
    #
    # See
    # https://stackoverflow.com/questions/37610056/how-to-treat-nas-like-values-when-comparing-elementwise-in-r

    return(
        (e1 != e2 | (is.na(e1) & !is.na(e2)) | (is.na(e2) & !is.na(e1)))
        & !(is.na(e1) & is.na(e2))
    )
}


# =============================================================================
# Loading data and basic preprocessing
# =============================================================================

simplified_ethnicity <- function(ethnicity)
{
    # We have to deal with ethnicity text from lots of different clinical
    # record systems. This function maps many different versions to a small
    # standardized subset, following a UK standard.
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
    # Returns the index of multiple deprivation (IMD) centile, from 0 least
    # deprived to 100 most deprived.
    #
    # index_of_multiple_deprivation: the England IMD, from  1 = Tendring, North
    # East Essex, most deprived in England, through (in CPFT's area) 10 =
    # Waveney, Suffolk, through ~14000 for Kensington & Chelsea via 32785
    # somewhere in South Cambridgeshire to 32844 in Wokingham, Berkshire, the
    # least deprived in England. Waveney's deprivation is confirmed at
    # https://www.eastsuffolk.gov.uk/assets/Your-Council/WDC-Council-Meetings/2016/November/WDC-Overview-and-Scrutiny-Committee-01-11-16/Item-5a-Appendix-A-Hidden-Needs-for-East-Suffolk-Oct-update.pdf
    # Here, we do not correct for population (unlike e.g. Jones et al. 2022,
    # https://pubmed.ncbi.nlm.nih.gov/35477868/), and we simply use the IMD
    # order (so it's the centile for IMD number, not the centile for
    # population). But like Jones 2022, we use a "deprivation" centile, i.e. 0
    # least deprived, 100 most deprived. See also:
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
    # Load a (hashed) file of people, extracted from a single database. Include
    # the special "other_info" validation information (not normally used).

    cat(paste0("- Loading from: ", filename, "\n"))
    # Read from JSON lines
    # https://stackoverflow.com/questions/31599299/expanding-a-json-column-in-r
    # https://stackoverflow.com/questions/55120019/how-to-read-a-json-file-line-by-line-in-r
    de_null <- function(x, na_value = NA) {
        # - RJSONIO::fromJSON("{'a': null}") produces NULL. rbindlist() later
        #   complains, so let's convert NULL to NA explicitly.
        # - Likewise let's convert empty strings to NA.
        # - And likewise numeric(0), which is what you get from e.g.
        #   tail(c(1, 2, 3), -4).
        # - RJSONIO::fromJSON("{'a': [1, 2, 3]}")$a[4] produces NA too.
        return(
            ifelse(
                is.null(x),
                na_value,
                ifelse(
                    is.na(x) | x == "" | identical(x, numeric(0)),
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
    empty_str <- ""
    d <- (
        readLines(filename, n = nrows) %>%
        lapply(RJSONIO::fromJSON, simplify = FALSE) %>%
        lapply(
            function(e) {
                forenames <- e$forenames
                n_forenames <- length(forenames)
                # These are all hashed/de-identified; don't worry about the
                # naming.
                if (n_forenames >= 1) {
                    f <- forenames[[1]]
                    first_name_name <- de_null(f$name, NA_character_)
                    first_name_metaphone <- de_null(f$metaphone, NA_character_)
                    first_name_f2c <- de_null(f$f2c, NA_character_)
                    first_name_p_f <- de_null(f$p_f, NA_real_)
                    first_name_p_p1nf <- de_null(f$p_p1nf, NA_real_)
                    first_name_p_p2np1 <- de_null(f$p_p2np1, NA_real_)
                } else {
                    first_name_name <- NA_character_
                    first_name_metaphone <- NA_character_
                    first_name_f2c <- NA_character_
                    first_name_p_f <- NA_real_
                    first_name_p_p1nf <- NA_real_
                    first_name_p_p2np1 <- NA_real_
                }
                if (n_forenames >= 2) {
                    m <- forenames[[2]]
                    second_forename_name <- de_null(m$name, NA_character_)
                    second_forename_metaphone <- de_null(m$metaphone, NA_character_)
                    second_forename_f2c <- de_null(m$f2c, NA_character_)
                    second_forename_p_f <- de_null(m$p_f, NA_real_)
                    second_forename_p_p1nf <- de_null(m$p_p1nf, NA_real_)
                    second_forename_p_p2np1 <- de_null(m$p_p2np1, NA_real_)
                } else {
                    second_forename_name <- NA_character_
                    second_forename_metaphone <- NA_character_
                    second_forename_f2c <- NA_character_
                    second_forename_p_f <- NA_real_
                    second_forename_p_p1nf <- NA_real_
                    second_forename_p_p2np1 <- NA_real_
                }
                if (n_forenames >= 3) {
                    om <- tail(forenames, -2)
                    other_middle_names_names <- paste(
                        lapply(om, function(p) p$name),
                        collapse = sep
                    )
                    other_middle_names_metaphones <- paste(
                        lapply(om, function(p) p$metaphone),
                        collapse = sep
                    )
                    other_middle_names_f2c <- paste(
                        lapply(om, function(p) p$f2c),
                        collapse = sep
                    )
                    other_middle_names_p_f <- paste(
                        lapply(om, function(p) p$p_f),
                        collapse = sep
                    )
                    other_middle_names_p_p1nf <- paste(
                        lapply(om, function(p) p$p_p1nf),
                        collapse = sep
                    )
                    other_middle_names_p_p2np1 <- paste(
                        lapply(om, function(p) p$p_p2np1),
                        collapse = sep
                    )
                } else {
                    other_middle_names_names <- NA_character_
                    other_middle_names_metaphones <- NA_character_
                    other_middle_names_f2c <- NA_character_
                    other_middle_names_p_f <- NA_character_
                    other_middle_names_p_p1nf <- NA_character_
                    other_middle_names_p_p2np1 <- NA_character_
                }

                # Surnames have fragments. The first fragment is the full name.
                surnames <- e$surnames
                n_surnames <- length(surnames)
                if (n_surnames >= 1) {
                    s <- surnames[[1]]$fragments[[1]]
                    surname_name <- de_null(s$name, NA_character_)
                    surname_metaphone <- de_null(s$metaphone, NA_character_)
                    surname_f2c <- de_null(s$f2c, NA_character_)
                    surname_p_f <- de_null(s$p_f, NA_real_)
                    surname_p_p1nf <- de_null(s$p_p1nf, NA_real_)
                    surname_p_p2np1 <- de_null(s$p_p2np1, NA_real_)
                } else {
                    surname_name <- NA_character_
                    surname_metaphone <- NA_character_
                    surname_f2c <- NA_character_
                    surname_p_f <- NA_real_
                    surname_p_p1nf <- NA_real_
                    surname_p_p2np1 <- NA_real_
                }

                if (n_surnames >= 2) {
                    os <- tail(n_surnames, -1)
                    other_surname_names <-  paste(
                        lapply(os, function(p) p$fragments[[1]]$name),
                        collapse = sep
                    )
                    other_surname_metaphones <- paste(
                        lapply(os, function(p) p$fragments[[1]]$metaphone),
                        collapse = sep
                    )
                    other_surname_f2c <- paste(
                        lapply(os, function(p) p$fragments[[1]]$f2c),
                        collapse = sep
                    )
                    other_surname_p_f <- paste(
                        lapply(os, function(p) p$fragments[[1]]$p_f),
                        collapse = sep
                    )
                    other_surname_p_p1nf <- paste(
                        lapply(os, function(p) p$fragments[[1]]$p_p1nf),
                        collapse = sep
                    )
                    other_surname_p_p2np1 <- paste(
                        lapply(os, function(p) p$fragments[[1]]$p_p1nf),
                        collapse = sep
                    )
                } else {
                    other_surname_names <- NA_character_
                    other_surname_metaphones <- NA_character_
                    other_surname_f2c <- NA_character_
                    other_surname_p_f <- NA_real_
                    other_surname_p_p1nf <- NA_real_
                    other_surname_p_p2np1 <- NA_real_
                }

                postcodes <- e$postcodes
                postcode_units <- paste(
                    lapply(postcodes, function(p) p$postcode_unit),
                    collapse = sep
                )
                postcode_unit_freq <- paste(
                    lapply(postcodes, function(p) p$unit_freq),
                    collapse = sep
                )
                postcode_sectors <- paste(
                    lapply(postcodes, function(p) p$postcode_sector),
                    collapse = sep
                )
                postcode_sector_freq <- paste(
                    lapply(postcodes, function(p) p$sector_freq),
                    collapse = sep
                )
                postcode_start_dates <- paste(
                    lapply(
                        postcodes,
                        function(p) de_null(p$start_date, empty_str)
                    ),
                    collapse = sep
                )
                postcode_end_dates <- paste(
                    lapply(
                        postcodes,
                        function(p) de_null(p$end_date, empty_str)
                    ),
                    collapse = sep
                )

                other_info <- RJSONIO::fromJSON(e$other_info, simplify = FALSE)

                return(list(
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # main
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    local_id = e$local_id,

                    first_name_name = first_name_name,
                    first_name_metaphone = first_name_metaphone,
                    first_name_f2c = first_name_f2c,
                    first_name_p_f = first_name_p_f,
                    first_name_p_p1nf = first_name_p_p1nf,
                    first_name_p_p2np1 = first_name_p_p2np1,

                    second_forename_name = second_forename_name,
                    second_forename_metaphone = second_forename_metaphone,
                    second_forename_f2c = second_forename_f2c,
                    second_forename_p_f = second_forename_p_f,
                    second_forename_p_p1nf = second_forename_p_p1nf,
                    second_forename_p_p2np1 = second_forename_p_p2np1,

                    other_middle_names_names = other_middle_names_names,
                    other_middle_names_metaphones = other_middle_names_metaphones,
                    other_middle_names_f2c = other_middle_names_f2c,
                    other_middle_names_p_f = other_middle_names_p_f,
                    other_middle_names_p_p1nf = other_middle_names_p_p1nf,
                    other_middle_names_p_p2np1 = other_middle_names_p_p2np1,

                    surname_name = surname_name,
                    surname_metaphone = surname_metaphone,
                    surname_f2c = surname_f2c,
                    surname_p_f = surname_p_f,
                    surname_p_p1nf = surname_p_p1nf,
                    surname_p_p2np1 = surname_p_p2np1,

                    other_surname_names = other_surname_names,
                    other_surname_metaphones = other_surname_metaphones,
                    other_surname_f2c = other_surname_f2c,
                    other_surname_p_f = other_surname_p_f,
                    other_surname_p_p1nf = other_surname_p_p1nf,
                    other_surname_p_p2np1 = other_surname_p_p2np1,

                    dob = e$dob$dob,
                    dob_md = e$dob$dob_md,
                    dob_yd = e$dob$dob_yd,
                    dob_ym = e$dob$dob_ym,

                    gender_hashed = de_null(e$gender$gender, NA_character_),
                    # NB otherwise name conflict with "true" version below
                    gender_freq = de_null(e$gender$gender_freq, NA_real_),

                    postcode_units = postcode_units,
                    postcode_unit_freq = postcode_unit_freq,
                    postcode_sectors = postcode_sectors,
                    postcode_sector_freq = postcode_sector_freq,
                    postcode_start_dates = postcode_start_dates,
                    postcode_end_dates = postcode_end_dates,

                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # other_info
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    hashed_nhs_number = other_info$hashed_nhs_number,

                    blurred_dob = de_null(other_info$blurred_dob, NA_character_),
                    gender = de_null(other_info$gender, NA_character_),
                    raw_ethnicity = de_null(other_info$ethnicity, NA_character_),
                    index_of_multiple_deprivation = de_null(other_info$index_of_multiple_deprivation, NA_integer_),

                    first_mh_care_date = de_null(other_info$first_mh_care_date, NA_character_),
                    age_at_first_mh_care = de_null(other_info$age_at_first_mh_care, NA_integer_),
                    any_icd10_dx_present = other_info$any_icd10_dx_present,
                    chapter_f_icd10_dx_present = other_info$chapter_f_icd10_dx_present,
                    severe_mental_illness_icd10_dx_present = other_info$severe_mental_illness_icd10_dx_present,

                    has_pseudopostcode = other_info$has_pseudopostcode,
                    has_nfa_pseudopostcode = other_info$has_nfa_pseudopostcode,
                    has_non_nfa_pseudopostcode = other_info$has_non_nfa_pseudopostcode
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
    # Loads the results of a Bayesian comparison process. Merge in "special"
    # validation information: demographic information about the probands, and
    # gold-standard match information (based on hashed NHS number).

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
            "has_pseudopostcode",
            "has_nfa_pseudopostcode",
            "has_non_nfa_pseudopostcode",

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
    # Load all per-database people files (per ALL_DATABASES), and all pairwise
    # comparisons (per FROM_DATABASES and TO_DATABASES).

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
                    # ... don't use filename =; clashes with
                    # load_rds_or_run_function
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

get_demographics <- function(d, db_name, hash_length = HASH_LENGTH)
{
    # Use information derived from our special validation "other_info" details
    # to characterize the demographics, in aggregate, of people from a single
    # database. Also some details from the de-identified info, e.g. number of
    # postcodes per person.

    d <- data.table::copy(d)
    d[,
        n_postcodes := str_length(str_replace_all(postcode_units, ";", ""))
                       / HASH_LENGTH
    ]
    d[, birth_year := year(blurred_dob)]

    results <- data.table(
        db_name = db_name,

        n_total = nrow(d),
        # n_duplicated_nhs_number = sum(duplicated(d$hashed_nhs_number)),
        n_records_duplicated_nhs_number = n_with_duplicates(d$hashed_nhs_number),
        n_distinct_duplicated_nhs_numbers = n_unique_duplicates(d$hashed_nhs_number),

        dob_year_min = min(d$birth_year, na.rm = TRUE),
        dob_year_max = max(d$birth_year, na.rm = TRUE),
        dob_year_mean = mean(d$birth_year, na.rm = TRUE),
        dob_year_sd = sd(d$birth_year, na.rm = TRUE),

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

        n_postcodes_mean = mean(d$n_postcodes),
        n_postcodes_min = min(d$n_postcodes),
        n_postcodes_max = max(d$n_postcodes),
        cor_birth_year_n_postcodes = cor(d$birth_year, d$n_postcodes),

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
    # Load demographic information about all databases (per ALL_DATABASES).

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
    # Compare a pair of databases in a very simple way: how many probands were
    # (in truth) in the sample?

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
    # Apply compare_simple() to all databases pairwise (per FROM_DATABASES,
    # TO_DATABASES).

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
    # Make a copy of the data supplied (which is a comparison of two databases
    # with enough information to re-apply new thresholds), apply new decision
    # thresholds (theta and delta), and calculate basic signal detection theory
    # labels (hit, miss, false alarm, correct rejection) for every proband.

    d <- data.table::copy(compdata)
    d[, declare_match := (
        # Criterion A:
        log_odds_match >= theta
        # Criterion B:
        & log_odds_match >= second_best_log_odds + delta
    )]

    if (TWO_STAGE_SDT_METHOD) {
        # RNC METHOD.
        # Extreme caution here, because we have two aspects: detecting that
        # someone is in the sample, and finding the correct person. The SDT
        # methods need everything to add up, so we deal with these separately.
        # (We do *not* say that a "hit" is declaring a match and the best
        # candidate being correct.) So, the first phase:
        d[, hit := declare_match & proband_in_sample]  # TP
        d[, false_alarm := declare_match & !proband_in_sample]  # FP
        d[, correct_rejection := !declare_match & !proband_in_sample]  # TN
        d[, miss := !declare_match & proband_in_sample]  # FN
        # PREDICTION:
        # - test positive (TP + FP) = declare match (linked)
        # - test negative (TN + FN) = declare no match (not linked)
        # STATE OF THE WORLD:
        # - positive = TP + FN = proband in sample
        # - negative = TN + FP = proband not in sample

        # And the second:
        d[, correctly_identified := declare_match & best_candidate_correct]
        d[, misidentified := declare_match & !best_candidate_correct]

    } else {
        # ALTERNATIVE METHOD. Following Lyons (2009) PMID 19149883, in turn
        # following Karmel & Gibson (2007) PMID 17892601 (p2, penultimate
        # paragraph):
        # - true positive (hit) = true link
        # - true negative (correct rejection) = no link
        # - false positive (false alarm) = false link
        # - false negative (miss) = missed link

        d[, hit := declare_match & best_candidate_correct]  # TP
        d[, false_alarm := declare_match & !best_candidate_correct]  # FP
        d[, correct_rejection := !declare_match & !proband_in_sample]  # TN
        d[, miss := !declare_match & proband_in_sample]  # FN
        # PREDICTION:
        # - test positive (TP + FP) = declare match (linked)
        # - test negative (TN + FN) = declare no match (not linked)
        # STATE OF THE WORLD:
        # - positive (P) = TP + FN =
        #           (proband in sample and matched correctly)
        #           + (proband in sample and no match declared)
        # - negative (N) = TN + FP =
        #           (proband not in sample and no match declared)
        #           + (proband in sample and matched incorrectly)
        #           + (proband not in sample and matched incorrectly)
        #         = (proband not in sample)
        #           + (proband in sample and matched incorrectly)
        # That's the problem -- they are definable but the definitions of P/N
        # are not independent of the test. See paper, and demo_re_two_systems()
        # below.

        # These are redundant. Make that clear:
        d[, correctly_identified := NA_integer_]
        d[, misidentified := NA_integer_]
    }

    return(d)
}


demo_re_two_systems <- function()
{
    # My claim that in K&G 2007, variations in the test affect the measured
    # prevalence:

    prevalence <- function(tp, fp, tn, fn) {
        p <- tp + fn
        n <- tn + fp
        return(p / (p + n))
    }

    # -------------------------------------------------------------------------
    # Situation A, system 1.
    # -------------------------------------------------------------------------
    # Working down the rows of Table 7:

    a1_tn <- 1
    a1_fp <- 2
    a1_fn <- 3
    a1_fp <- a_fp + 4
    a1_tp <- 5

    print(prevalence(tp = a1_tp, fp = a1_fp, tn = a1_tn, fn = a1_fn))
    # 0.727

    # -------------------------------------------------------------------------
    # Situation B, system 1.
    # -------------------------------------------------------------------------
    # As before, but now the test correctly identifies those 4, so they change
    # from being FP to TP.

    b1_tn <- 1
    b1_fp <- 2
    b1_fn <- 3
    b1_tp <- 4 + 5

    print(prevalence(tp = b1_tp, fp = b1_fp, tn = b1_tn, fn = b1_fn))
    # 0.8
    # The apparent prevalence has changed as the result of the test getting
    # better.

    # -------------------------------------------------------------------------
    # Situation A, system 2.
    # -------------------------------------------------------------------------

    a2_tn <- 1
    a2_fp <- 2
    a2_fn <- 3
    a2_tp <- 4
    a2_tp <- a2_tp + 5

    print(prevalence(tp = a2_tp, fp = a2_fp, tn = a2_tn, fn = a2_fn))
    # 0.8

    # -------------------------------------------------------------------------
    # Situation B, system 1.
    # -------------------------------------------------------------------------
    # As before, but now the test correctly identifies those 4, so they change
    # from being one kind of TP to another kind of TP.

    b2_tn <- 1
    b2_fp <- 2
    b2_fn <- 3
    b2_tp <- 4 + 5

    print(prevalence(tp = b2_tp, fp = b2_fp, tn = b2_tn, fn = b2_fn))
    # 0.8
    # No change.

}


compare_at_thresholds <- function(
    from_dbname, to_dbname, theta, delta, compdata, with_obscure = FALSE
)
{
    # Take comparison data from two databases (compdata, and labels from_dbname
    # and to_dbname), re-apply new decision thresholds (theta, delta), and
    # calculate whole-comparison SDT measures, such as true/false positive
    # rate, etc. Optionally include some obscure ones.

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
    d[, n_p := n_tp + n_fn]  # positive (in reality)
    d[, n_n := n_tn + n_fp]  # negative (in reality)
    d[, TPR := n_tp / n_p]  # sensitivity, recall, hit rate, true pos. rate
    d[, TNR := n_tn / n_n]  # specificity, selectivity, true neg. rate
    d[, PPV := n_tp / (n_tp + n_fp)]
    d[, NPV := n_tn / (n_tn + n_fn)]
    d[, FNR := n_fn / n_p]  # miss rate, false neg. rate = 1 - TPR
    d[, FPR := n_fp / n_n]  # false pos. rate = 1 - TNR
    d[, FDR := n_fp / (n_fp + n_tp)]  # false discovery rate
    d[, FOR := n_fn / (n_fn + n_tn)]  # false omission rate
    d[, Prevalence := n_p / n]  # = n_p / (n_p + n_n)
    d[, Accuracy := (n_tp + n_tn) / n]  # proportion of decisions correct
    d[, F1 :=
        2 * n_tp / (2 * n_tp + n_fp + n_fn)
    ]  # F1 score: harmonic mean of precision and recall
    if (with_obscure) {
        d[, LR_pos := TPR / FPR]  # positive likelihood ratio
        d[, LR_neg := FNR / TNR]  # negative likelihood ratio
        d[, PT :=
             sqrt(FPR) / (sqrt(TPR) + sqrt(FPR))
        ]  # prevalence threshold
        d[, TS_CSI :=
            n_tp / (n_tp + n_fn + n_fp)
        ]  # threat score, or critical success index
        d[, Balanced_accuracy :=
            (TPR + TNR) / 2
        ]
        # ... etc.
    }

    # And for our second phase, if applicable:
    d[, MID := n_misidentified / n_identified]  # misidentification rate

    # Thoughts: a natural metric is "distance from the top left of the ROC
    # plot". The x distance is FPR, and the y distance is 1 - TPR. So, by
    # Pythagoras's theorem, the distance is sqrt(FPR^2 + (1 - TPR)^2). That
    # doesn't seem to be one that's above, so:
    # d[, distance_roc_corner := sqrt(FPR^2 + (1 - TPR)^2)]
    d[, distance_to_corner := sqrt(FPR^2 + (1 - TPR)^2)]
    # Aha. It's called "distance to corner":
    # https://ncss-wpengine.netdna-ssl.com/wp-content/themes/ncss/pdf/Procedures/NCSS/One_ROC_Curve_and_Cutoff_Analysis.pdf
    # ... they use the form sqrt((1 - sensitivity)^2 + (1 - specificity)^2),
    # where 1 - sensitivity[TPR] = FNR (y distance), and 1 - specificity[TNR] =
    # FPR (x distance). So that's the distance from the top left too, and 0 is
    # good.

    # Checks
    if (TWO_STAGE_SDT_METHOD) {
        stopifnot(d$n_p == sum(decided$proband_in_sample))
        stopifnot(d$n_n == sum(!decided$proband_in_sample))
    }
    stopifnot(all(d$n_tp + d$n_fp + d$n_tn + d$n_fn == d$n))

    return(d)
}


get_comparisons_varying_threshold <- function()
{
    # For all database pairs (FROM_DATABASES, TO_DATABASES), and all decision
    # thresholds of interest (THETA_OPTIONS, DELTA_OPTIONS), recalculate
    # decisions and calculate SDT aggregate measures; return these in a big
    # table.

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
    # Apply new decision thresholds (theta, delta) to a comparison (compdata).
    # Return a logistic regression model using demographic factors to predict
    # the likelihood of correct linkage.

    # Make decisions. We only care about probands who are in the sample.
    decided <- decide_at_thresholds(
        compdata[proband_in_sample == TRUE],
        theta,
        delta
    )
    decided[, birth_year := year(blurred_dob)]
    m <- glm(
        correctly_identified ~
            birth_year
                + sex_simple
                + ethnicity
                + deprivation_centile_100_most_deprived
                # + age_at_first_mh_care
                + dx_group_simple
                + has_pseudopostcode,
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

mk_proband_label <- function(from_db_name)
{
    # Tweak labels to indicate that a database is serving as the proband
    # database.

    paste0(recode(from_db_name, !!!DATABASE_LABEL_MAP), " [p]")
}


mk_sample_label <- function(to_db_name)
{
    # Tweak labels to indicate that a database is serving as the sample
    # database.

    paste0(recode(to_db_name, !!!DATABASE_LABEL_MAP), " [s]")
}


mk_generic_pairwise_plot <- function(
    comp_threshold_labelled,
    depvars,
    linetypes,
    shapes,
    x_is_theta,  # if FALSE, x is delta
    vline_colour = DEFAULT_VLINE_COLOUR,
    with_overlap_label = FALSE,
    comp_simple_labelled = NULL,
    overlap_label_y = 0.6,  # 0.25,
    overlap_label_vjust = 0,  # vbottom
    overlap_label_x = DEFAULT_THETA + 1,  # max(THETA_OPTIONS),
    overlap_label_hjust = 0,  # 0 = left-justify, 1 = right-justify
    overlap_label_size = LABEL_SIZE,
    diagonal_colour = DIAGONAL_PANEL_BG_COLOUR,
    diagonal_background_alpha = DIAGONAL_PANEL_BG_ALPHA
) {
    # Plot some form of SDT measures (comp_threshold_labelled) across
    # parameters (theta, delta) and database pairs.

    CORE_VARS <- c("from", "to", "from_label", "to_label", "theta", "delta")
    required_vars <- c(CORE_VARS, depvars)
    d <- (
        comp_threshold_labelled
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
    facet_data_diagonal <- unique(d[from == to, .(from_label, to_label)])
    if (x_is_theta) {
        xvar <- "theta"
        colourvar <- "delta"
        # d[, x_factor := as.factor(theta)]
        d[, x_grouper := paste0(quantity, "_", delta)]
        vline_xintercept <- DEFAULT_THETA
        colour_scale <- COLOUR_SCALE_DELTA

    } else {
        # x is delta
        xvar <- "delta"
        colourvar <- "theta"
        # d[, x_factor := as.factor(delta)]
        d[, x_grouper := paste0(quantity, "_", theta)]
        vline_xintercept <- DEFAULT_DELTA
        colour_scale <- COLOUR_SCALE_THETA
    }
    y_label <- paste(depvars, collapse = ", ")

    p <- (
        ggplot(d)
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
        + geom_line(
            mapping = aes_string(
                x = xvar,
                y = "value",
                group = "x_grouper",
                colour = colourvar,
                linetype = "quantity"
            )
        )
        + geom_point(
            mapping = aes_string(
                x = xvar,
                y = "value",
                group = "x_grouper",
                colour = colourvar,
                shape = "quantity"
            )
            # colour = "black"
        )
        + facet_grid(from_label ~ to_label)
        + theme_bw()
        + scale_linetype_manual(values = linetypes)
        + scale_shape_manual(values = shapes)
        + colour_scale
        + ylab(y_label)
    )
    if (with_overlap_label) {
        if (is.null(comp_simple_labelled)) {
            stop("Must specify comp_simple_labelled to use with_overlap_label")
        }
        cs <- data.table::copy(comp_simple_labelled)
        cs[, overlap_label := paste0("o = ", n_overlap)]
        p <- (
            p
            + geom_text(
                data = cs,
                mapping = aes(
                    label = overlap_label
                    # implicit (for facet plot): from_label, to_label
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


mk_threshold_plot_tpr_fpr <- function(comp_threshold_labelled, ...)
{
    # Make a plot for TPR and FPR, by either theta or delta, and across
    # database pairs.

    # The quantities that are informative and independent of the prevalence
    # (and thus reflect qualities of the test) include TPR (sensitivity,
    # recall), TNR (specificity), FPR (false alarm rate), and FNR (miss rate).
    #
    # Those that are affected by prevalence include PPV (precision), NPV.
    #
    # TNR = 1 - FPR, and TPR = 1 - FNR, so no need to plot both.
    # Let's use: TPR, FPR.
    return(mk_generic_pairwise_plot(
        comp_threshold_labelled,
        depvars = c("TPR", "FPR"),
        linetypes = c("solid", "dotted"),
        shapes = c(24, 25),  # up triangle, down triangle
        ...
    ))
}


mk_threshold_plot_tpr <- function(comp_threshold_labelled, ...)
{
    # Make a plot for TPR and FPR, by either theta or delta, and across
    # database pairs.

    return(mk_generic_pairwise_plot(
        comp_threshold_labelled,
        depvars = "TPR",
        linetypes = "solid",
        shapes = 24,  # up triangle
        ...
    ))
}


mk_threshold_plot_fpr <- function(comp_threshold_labelled, ...)
{
    # Make a plot for FNR (false negative rate), by either theta or delta,
    # and across database pairs.

    return(mk_generic_pairwise_plot(
        comp_threshold_labelled,
        depvars = "FPR",
        linetypes = "solid",
        shapes = 25,  # down triangle
        ...
    ))
}


mk_threshold_plot_mid <- function(comp_threshold_labelled, ...)
{
    # Make a plot for MID (misidentification rate), by either theta or delta,
    # and across database pairs.

    return(mk_generic_pairwise_plot(
        comp_threshold_labelled,
        depvars = "MID",
        linetypes = "solid",
        shapes = 4,  # X
        ...
    ))
}


mk_auroc_plot_ignoring_delta <- function(
    replace_neg_inf_log_odds_with = -1e5,
    diagonal_colour = DIAGONAL_PANEL_BG_COLOUR,
    diagonal_background_alpha = DIAGONAL_PANEL_BG_ALPHA,
    auroc_dp = 3,
    auroc_label_x = 1,
    auroc_label_y = 0.1,
    auroc_label_vjust = 0,  # vbottom
    auroc_label_hjust = 1,  # right-justify
    auroc_label_size = LABEL_SIZE,
    random_line_colour = "grey",
    default_theta = DEFAULT_THETA,
    default_theta_shape = 4  # 4 cross, 19 filled circle
    # point_shape = 1,  # hollow circle
    # point_alpha = 0.1
) {
    # Create an AUROC plot for a fixed value of delta, across databases (per
    # FROM_DATABASES, TO_DATABASES).

    # The normal decision criteria are
    # (A) log_odds_match >= theta;
    # (B) log_odds_match >= second_best_log_odds + delta.
    # An AUROC curve requires a continuous (or binary) predictor and a binary
    # (true) outcome. Clearly, log_odds_match has to be part of that predictor.
    # If delta is ignored, and we only examine (A), then log_odds_match is
    # itself the predictor.
    detailed_data <- NULL
    summary_data <- NULL
    facet_data_diagonal <- NULL
    for (db1 in FROM_DATABASES) {
        for (db2 in TO_DATABASES) {
            compdata <- get(mk_comparison_var(db1, db2))
            from_label <- mk_proband_label(db1)
            to_label <- mk_sample_label(db2)
            facet_data_diagonal <- rbind(
                facet_data_diagonal,
                data.table(
                    from = db1,
                    to = db2,
                    from_label = from_label,
                    to_label = to_label
                )
            )
            compdata_finite_odds <- compdata[, .(
                log_odds_match,
                second_best_log_odds,
                proband_in_sample
            )]
            # pROC requires a finite predictor, so:
            compdata_finite_odds[
                !is.finite(log_odds_match),
                log_odds_match := replace_neg_inf_log_odds_with
            ]
            if (length(unique(compdata_finite_odds$proband_in_sample)) == 1) {
                # pROC::roc() would say: 'response' must have two levels
                # This will happen when we compare a database to itself.
                next
            }
            r <- pROC::roc(
                data = compdata_finite_odds,
                predictor = log_odds_match,
                response = proband_in_sample,
                levels = c(FALSE, TRUE),  # controls, cases (respectively)
                direction = "<"  # controls < cases
            )
            detailed_data <- rbind(
                detailed_data,
                data.table(
                    from = db1,
                    to = db2,
                    from_label = from_label,
                    to_label = to_label,
                    specificity = r$specificities,
                    sensitivity = r$sensitivities,
                    threshold = r$thresholds
                )
            )
            summary_data <- rbind(
                summary_data,
                data.table(
                    from = db1,
                    to = db2,
                    from_label = from_label,
                    to_label = to_label,
                    auroc = r$auc
                )
            )
        }
    }
    detailed_data[, fpr := 1 - specificity]

    summary_data[,
        auroc_pretty := paste0(
            "AUROC: ",
            miscmath$format_dp(auroc, dp = auroc_dp)
        )
    ]
    # For AUROC "randomness" line:
    summary_data[, random_line_intercept := 0]
    summary_data[, random_line_slope := 1]

    threshold_data <- rbind(
        (
            detailed_data
            %>% group_by(from, to, from_label, to_label)
            %>% filter(
                threshold == max(
                    ifelse(
                        threshold <= default_theta,
                        threshold,
                        NA_real_
                    ),
                    na.rm = TRUE
                )
            )
            %>% mutate(condition = "max_below")
            %>% as.data.table()
        ),
        (
            detailed_data
            %>% group_by(from, to, from_label, to_label)
            %>% filter(
                threshold == min(
                    ifelse(
                        threshold >= default_theta,
                        threshold,
                        NA_real_
                    ),
                    na.rm = TRUE
                )
            )
            %>% mutate(condition = "min_above")
            %>% as.data.table()
        )
    )

    # https://stackoverflow.com/questions/21435339/data-table-vs-dplyr-can-one-do-something-well-the-other-cant-or-does-poorly
    # https://dplyr.tidyverse.org/reference/do.html
    # https://dplyr.tidyverse.org/reference/summarise.html
    interp <- function(threshold, specificity, sensitivity, fpr,
                       target_threshold = default_theta) {
        # Interpolate across several variables to make them align with
        # "threshold" if it were "target_threshold".
        stopifnot(length(threshold) == 2)
        a <- threshold[1]
        b <- threshold[2]
        width <- b - a
        if (width == 0) {
            props <- c(0.5, 0.5)
        } else {
            # If we have:
            # A ----------------------------- TARGET ------- B
            # then we want A * lower + big_chunk * B.
            props <- c(
                (b - target_threshold) / width,  # A fraction
                (target_threshold - a) / width  # B fraction
            )
        }
        return(tibble(
            threshold = target_threshold,
            specificity = sum(props * specificity),
            sensitivity = sum(props * sensitivity),
            fpr = sum(props * fpr),
            condition = "interpolated"
        ))
    }
    # Test: interp(c(0, 1), c(0, 1), c(2, 3), c(1, 0), 0.75)
    threshold_data <- rbind(
        threshold_data,
        (
            threshold_data
            %>% group_by(from, to, from_label, to_label)
            %>% summarize(
                interp(threshold, specificity, sensitivity, fpr),
                .groups = "drop"
            )
            %>% as.data.table()
        )
    )
    setkeyv(threshold_data, c("from_label", "to_label", "condition"))

    # The raw tables don't contain any rows where the "from" and "to" databases
    # are the same, so for shading, we'll just make a dummy table, as above.
    facet_data_diagonal <- facet_data_diagonal[from == to]

    # We'll go a bit beyond what ggroc() offers, but follow it broadly.
    p <- (
        # There is a bug with respect to geom_abline() and scale_x_reverse(). See
        # https://stackoverflow.com/questions/28603078/why-geom-abline-does-not-honor-scales-x-reverse
        # So we plot FPR (1 - specificity) directly, rather than plotting
        # specificity and reversing.
        ggplot()
        + geom_rect(
            data = facet_data_diagonal,
            xmin = -Inf,
            xmax = Inf,
            ymin = -Inf,
            ymax = Inf,
            fill = diagonal_colour,
            alpha = diagonal_background_alpha
        )
        + geom_abline(
            data = summary_data,
            mapping = aes(
                # Using an aesthetic means we can avoid drawing in the blank
                # leading diagonal panels.
                intercept = random_line_intercept,
                slope = random_line_slope
            ),
            colour = random_line_colour
        )
        + geom_line(
            data = detailed_data,
            mapping = aes(
                x = fpr,  # = 1 - specificity
                y = sensitivity
            )
        )
        # + geom_point(
        #     # Too many points!
        #     data = detailed_data,
        #     mapping = aes(
        #         x = fpr,  # = 1 - specificity
        #         y = sensitivity
        #     ),
        #     shape = point_shape,
        #     alpha = point_alpha
        # )
        + geom_point(
            data = threshold_data[condition == "interpolated"],
            mapping = aes(
                x = fpr,
                y = sensitivity
            ),
            shape = default_theta_shape
        )
        + geom_text(
            data = summary_data,
            mapping = aes(
                label = auroc_pretty
            ),
            x = auroc_label_x,
            y = auroc_label_y,
            hjust = auroc_label_hjust,
            vjust = auroc_label_vjust,
            size = auroc_label_size
        )
        + theme_bw()
        + xlab("FPR (1 - specificity)")
        + scale_x_continuous(
            labels = function(x) {
                miscmath$format_dp_unless_integer(x, dp = 2)
            }
        )
        + ylab("TPR (sensitivity)")
        + facet_grid(from_label ~ to_label)
    )
    # ggsave(file.path(OUTPUT_DIR, "tmp.pdf"), p)
    # ggsave(file.path(OUTPUT_DIR, "tmp.pdf"), ggroc(r))
    return(p)
}


mk_save_performance_plot <- function(comp_threshold, comp_simple)
{
    # Create a composite plot: AUROC, TPR/FPR, MID for pairwise database
    # comparisons.

    comp_threshold_labelled <- (
        comp_threshold
        %>% mutate(
            # Make the labels nicer, and add proband/sample indicators.
            from_label = mk_proband_label(from),
            to_label = mk_sample_label(to)
        )
        %>% as.data.table()
    )
    comp_simple_labelled <- (
        comp_simple
        %>% mutate(
            from_label = mk_proband_label(from),
            to_label = mk_sample_label(to)
        )
        %>% as.data.table()
    )

    if (TWO_STAGE_SDT_METHOD) {
        # The two things of real interest are the TPR (sensitivity) and the
        # misidentification rate.

        # tpr_fpr_theta <- mk_threshold_plot_tpr_fpr(
        #     comp_threshold_labelled,
        #     x_is_theta = TRUE,
        #     with_overlap_label = TRUE,
        #     comp_simple_labelled = comp_simple_labelled
        # )
        # tpr_fpr_delta <- mk_threshold_plot_tpr_fpr(comp_threshold_labelled, x_is_theta = FALSE)
        tpr_theta <- mk_threshold_plot_tpr(
            comp_threshold_labelled,
            x_is_theta = TRUE,
            with_overlap_label = TRUE,
            comp_simple_labelled = comp_simple_labelled
        )
        tpr_delta <- mk_threshold_plot_tpr(comp_threshold_labelled, x_is_theta = FALSE)
        # fpr_theta <- mk_threshold_plot_fpr(comp_threshold_labelled, x_is_theta = TRUE)
        # fpr_delta <- mk_threshold_plot_fpr(comp_threshold_labelled, x_is_theta = FALSE)
        mid_theta <- mk_threshold_plot_mid(comp_threshold_labelled, x_is_theta = TRUE)
        mid_delta <- mk_threshold_plot_mid(comp_threshold_labelled, x_is_theta = FALSE)
        auroc_plots <- mk_auroc_plot_ignoring_delta()
        composite <- (
            (auroc_plots | plot_spacer()) /
            # (tpr_fpr_theta | tpr_fpr_delta) /
            (tpr_theta | tpr_delta) /
            # (fpr_theta | fpr_delta) /
            (mid_theta | mid_delta)
        ) + plot_annotation(tag_levels = "A")
    } else {
        tpr_theta <- mk_threshold_plot_tpr(
            comp_threshold_labelled,
            x_is_theta = TRUE,
            with_overlap_label = TRUE,
            comp_simple_labelled = comp_simple_labelled
        )
        tpr_delta <- mk_threshold_plot_tpr(comp_threshold_labelled, x_is_theta = FALSE)
        fpr_theta <- mk_threshold_plot_fpr(comp_threshold_labelled, x_is_theta = TRUE)
        fpr_delta <- mk_threshold_plot_fpr(comp_threshold_labelled, x_is_theta = FALSE)
        auroc_plots <- mk_auroc_plot_ignoring_delta()
        composite <- (
            (auroc_plots | plot_spacer()) /
            (tpr_theta | tpr_delta) /
            (fpr_theta | fpr_delta)
        ) + plot_annotation(tag_levels = "A")
    }

    ggsave(
        file.path(OUTPUT_DIR, "fig_pairwise_thresholds.pdf"),
        composite,
        width = PAGE_WIDTH_CM * 1.1 * 2,
        height = PAGE_HEIGHT_CM * 1.1 * 1.5,
        units = "cm"
    )
}


# =============================================================================
# Failure analysis
# =============================================================================

people_missingness_summary <- function(people)
{
    # Summarize how often various variables are missing, within a single
    # database.

    n <- nrow(people)
    prop_missing <- function(x) {
        sum(is.na(x)) / n
    }
    return(
        people
        %>% summarize(
            # Strings can be "" not NA, but frequencies are NA if missing.
            missing_first_name = prop_missing(first_name_p_f),
            missing_second_name = prop_missing(second_forename_p_f),
            missing_other_middle_names = prop_missing(other_middle_names_p_f),
            missing_surname = prop_missing(surname_p_f),
            missing_gender = prop_missing(gender_freq),
            missing_postcode = prop_missing(postcode_unit_freq)
        )
        %>% as.data.table()
    )
}


extract_miss_or_misidentified_info <- function(
    probands, sample, comparison,
    sample_db_name,
    theta = DEFAULT_THETA, delta = DEFAULT_DELTA,
    allow.cartesian = TRUE,
    remove_sample_duplicates = TRUE,
    rowtype = c("miss", "misidentified")
) {
    # For a pair of databases, establish people who were "missed" (proband in
    # truth present in sample but no match declared) or misidentified (match
    # declared for wrong person). Link them (proband to sample) by
    # gold-standard linkage (hashed NHS number), allowing comparison of
    # identifiers for errors.

    rowtype <- match.arg(rowtype)
    decided <- decide_at_thresholds(comparison, theta, delta)
    if (rowtype == "miss") {
        comp_selected <- decided[proband_in_sample & !declare_match]
    } else if (rowtype == "misidentified") {
        comp_selected <- decided[proband_in_sample & misidentified]
    } else {
        stop("bad rowtype")
    }
    person_columns <- c(
        # For linkage
        "hashed_nhs_number",

        # For error exploration
        "first_name_name", "first_name_p_f",
        "first_name_metaphone", "first_name_p_p1nf",
        "first_name_f2c", "first_name_p_p2np1",

        "second_forename_name", "second_forename_p_f",
        "second_forename_metaphone", "second_forename_p_p1nf",
        "second_forename_f2c", "second_forename_p_p2np1",

        "other_middle_names_names", "other_middle_names_p_f",
        "other_middle_names_metaphones", "other_middle_names_p_p1nf",
        "other_middle_names_f2c", "other_middle_names_p_p2np1",

        "surname_name", "surname_p_f",
        "surname_metaphone", "surname_p_p1nf",
        "surname_f2c", "surname_p_p2np1",

        "dob",  # all frequencies the same
        "dob_md",
        "dob_yd",
        "dob_ym",

        "gender_hashed", "gender_freq",

        "postcode_units", "postcode_unit_freq",
        "postcode_sectors", "postcode_sector_freq",

        # For bias analysis
        "blurred_dob",
        "gender",
        "sex_simple",
        "deprivation_centile_100_most_deprived",
        "diagnostic_group",
        "dx_group_simple"
    )
    miss_hashed_nhs <- comp_selected$hashed_nhs_number_proband
    miss_probands <- probands[
        hashed_nhs_number %in% miss_hashed_nhs,
        ..person_columns
    ]
    miss_sample_candidates <- sample[
        hashed_nhs_number %in% miss_hashed_nhs,
        ..person_columns
    ]
    # If there are duplicates in the sample here, we should remove them,
    # because otherwise we will over-count the error types. This is a bit
    # tricky.
    if (remove_sample_duplicates) {
        # Order is arbitrary here.
        miss_sample_candidates[, is_duplicate := duplicated(hashed_nhs_number)]
        n_duplicates <- sum(miss_sample_candidates$is_duplicate)
        if (n_duplicates > 0) {
            cat(paste0(
                "extract_miss_or_misidentified_info: Removing ",
                n_duplicates,
                " duplicates (by hashed_nhs_number) from ",
                "miss_sample_candidates for database ",
                sample_db_name,
                "\n"
            ))
            miss_sample_candidates <- miss_sample_candidates[
                is_duplicate == FALSE
            ]
        }
    }
    failure_info <- merge(  # fi = failure_info
        x = miss_probands,
        y = miss_sample_candidates,
        by.x = "hashed_nhs_number",
        by.y = "hashed_nhs_number",
        all.x = TRUE,  # all missed probands
        all.y = FALSE,
        # ... not all candidates, just those that (in truth) match the missed
        # probands
        suffixes = c("_proband", "_sample"),
        allow.cartesian = allow.cartesian
        # ... see: ?'[.data.table'
        # ... one way of handling for duplicate NHS numbers, i.e. PCMIS
        # ... but irrelevant if remove_sample_duplicates, as above
    )
    return(failure_info)
}


failure_summary <- function(failure_info, colprefix)
{
    # Used to characterize the identifier problems AMONGST LINKAGE FAILURES
    # (misses and misidentifications).

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
    failsumm <- (
        failure_info
        %>% summarize(
            n = n,

            proband_missing_first_name = prop_missing(first_name_name_proband),
            proband_missing_second_forename = prop_missing(second_forename_name_proband),
            proband_missing_surname = prop_missing(surname_name_proband),
            proband_missing_gender = prop_missing(gender_freq_proband),
            proband_missing_postcode = prop_missing(postcode_unit_freq_proband),

            sample_missing_first_name = prop_missing(first_name_name_sample),
            sample_missing_second_forename = prop_missing(second_forename_name_sample),
            sample_missing_surname = prop_missing(surname_name_sample),
            sample_missing_gender = prop_missing(gender_freq_sample),
            sample_missing_postcode = prop_missing(postcode_unit_freq_sample),

            mismatch_first_name = prop_mismatch(
                first_name_name_proband,
                first_name_name_sample
            ),
            mismatch_first_name_metaphone = prop_mismatch(
                first_name_metaphone_proband,
                first_name_metaphone_sample
            ),
            mismatch_first_name_f2c = prop_mismatch(
                first_name_f2c_proband,
                first_name_f2c_sample
            ),

            mismatch_second_forename = prop_mismatch(
                second_forename_name_proband,
                second_forename_name_sample
            ),
            mismatch_second_forename_metaphone = prop_mismatch(
                second_forename_metaphone_proband,
                second_forename_metaphone_sample
            ),
            mismatch_second_forename_f2c = prop_mismatch(
                second_forename_f2c_proband,
                second_forename_f2c_sample
            ),

            mismatch_surname = prop_mismatch(
                surname_name_proband,
                surname_name_sample
            ),
            mismatch_surname_metaphone = prop_mismatch(
                surname_metaphone_proband,
                surname_metaphone_sample
            ),
            mismatch_surname_f2c = prop_mismatch(
                surname_f2c_proband,
                surname_f2c_sample
            ),

            mismatch_dob = prop_mismatch(
                dob_proband,
                dob_sample
            ),
            mismatch_dob_partial = sum(
                mismatch(dob_md_proband, dob_md_sample)
                & mismatch(dob_yd_proband, dob_yd_sample)
                & mismatch(dob_ym_proband, dob_ym_sample)
            ) / n,

            mismatch_gender = prop_mismatch(
                gender_proband,
                gender_sample
            ),
            firstname_surname_swapped = sum(
                mismatch(first_name_name_proband, first_name_name_sample)
                & mismatch(surname_name_proband, surname_name_sample)
                & (first_name_name_proband == surname_name_sample)
                & (surname_name_proband == first_name_name_sample)
            ) / n,
            firstname_secondforename_swapped = sum(
                mismatch(first_name_name_proband, first_name_name_sample)
                & mismatch(second_forename_name_proband, second_forename_name_sample)
                & (first_name_name_proband == second_forename_name_sample)
                & (second_forename_name_proband == first_name_name_sample)
            ) / n
        )
        %>% as.data.table()
    )
    colnames(failsumm) <- paste0(colprefix, colnames(failsumm))
    return(failsumm)
}


performance_summary_at_threshold <- function(
    theta = DEFAULT_THETA,
    delta = DEFAULT_DELTA
) {
    # Compare all databases (per FROM_DATABASES, TO_DATABASES) at the specified
    # levels of theta and delta, and extract:
    # - SDT measures, via compare_at_thresholds()
    # - miss errors, via extract_miss_or_misidentified_info()
    # - misidentification errors, via extract_miss_or_misidentified_info()

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
            miss_info <- failure_summary(
                extract_miss_or_misidentified_info(
                    probands,
                    sample,
                    comparison,
                    sample_db_name = db2,
                    theta = theta,
                    delta = delta,
                    rowtype = "miss"
                ),
                colprefix = "miss_"
            )
            mismatch_info <- failure_summary(
                extract_miss_or_misidentified_info(
                    probands,
                    sample,
                    comparison,
                    sample_db_name = db2,
                    theta = theta,
                    delta = delta,
                    rowtype = "misidentified"
                ),
                colprefix = "misidentified_"
            )
            combined_summary <- cbind(
                main_performance_summary,
                miss_info,
                mismatch_info
            )
            perf_summ <- rbind(perf_summ, combined_summary)
        }
    }
    return(perf_summ)
}


write_simplified_performance_summary_at_threshold <- function(
    theta = DEFAULT_THETA,
    delta = DEFAULT_DELTA,
    write_pst = TRUE
) {
    # Reasons for non-linkage, etc., for every pairwise database comparison,
    # at default values of theta/delta:
    write_output(paste0(
        "PERFORMANCE SUMMARIES: theta = ", theta, ", delta = ", delta
    ))
    pst <- performance_summary_at_threshold(theta = theta, delta = delta)
    if (write_pst) {
        write_output(pst)
    }

    # Key metrics for every pairwise database comparison at default values of
    # theta/delta:
    pst_simplified <- (
        pst
        %>% select(from, to, TPR, FPR, TNR, F1, MID)
        %>% as.data.table()
    )
    write_output(pst_simplified)

    pst_means_non_self <- (
        pst_simplified
        %>% filter(from != to)
        %>% summarize(
            mean_TPR = mean(TPR),
            min_TPR = min(TPR),
            max_TPR = max(TPR),

            mean_FPR = mean(FPR),
            min_FPR = min(FPR),
            max_FPR = max(FPR),

            mean_TNR = mean(TNR),
            min_TNR = min(TNR),
            max_TNR = max(TNR),

            mean_F1 = mean(F1),
            min_F1 = min(F1),
            max_F1 = max(F1),

            mean_MID = mean(MID),
            min_MID = min(MID),
            max_MID = max(MID)
        )
        %>% as.data.table()
    )
    write_output(pst_means_non_self)

    pst_table <- (
        pst_simplified
        %>% mutate(
            text = paste0(
                "TPR: ", format_sig_fig(TPR),
                # "; FPR: ", format_sig_fig(FPR),
                "; MID: ", format_sig_fig(MID)
            )
        )
        %>% select(from, to, text)
        %>% pivot_wider(
            names_from = to,
            names_prefix = "to_",
            values_from = text
        )
    )
    write_output(pst_table)

    return(pst_table)
}


# =============================================================================
# Empirical discrepancy rates
# =============================================================================

empirical_discrepancy_rates <- function(people_data_1, people_data_2, gender = NA)
{
    # Characterize the rates of empirical discrepancies amongst people who we
    # know to be the same in two databases.
    #
    # Link on NHS numbers. Note -- this is an absolute (gold-standard) linkage,
    # and nothing to do with our Bayesian system.
    combined <- merge(
        x = people_data_1,
        y = people_data_2,
        by.x = "hashed_nhs_number",
        by.y = "hashed_nhs_number",
        all.x = FALSE,
        all.y = FALSE,
        suffixes = c("_db1", "_db2")
    )
    s <- combined
    if (!is.na(gender)) {
        s <- s %>% filter(gender_db1 == gender, gender_db2 == gender)
    }
    s <- (
        s
        %>% summarize(
            n_total = n(),

            first_name_n_present = sum(
                !is.na(first_name_name_db1) & !is.na(first_name_name_db2)
            ),
            first_name_n_full_match = sum(
                !is.na(first_name_name_db1) & !is.na(first_name_name_db2)
                # Name match:
                & first_name_name_db1 == first_name_name_db2
            ),
            first_name_n_p1nf_match = sum(
                !is.na(first_name_name_db1) & !is.na(first_name_name_db2)
                # Metaphone but not name match:
                & first_name_name_db1 != first_name_name_db2
                & first_name_metaphone_db1 == first_name_metaphone_db2
            ),
            first_name_n_p2np1_match = sum(
                !is.na(first_name_name_db1) & !is.na(first_name_name_db2)
                # First two characters, but not name or metaphone:
                & first_name_name_db1 != first_name_name_db2
                & first_name_metaphone_db1 != first_name_metaphone_db2
                & first_name_f2c_db1 == first_name_f2c_db2
            ),
            first_name_n_no_match = sum(
                !is.na(first_name_name_db1) & !is.na(first_name_name_db2)
                # Nothing matches:
                & first_name_name_db1 != first_name_name_db2
                & first_name_metaphone_db1 != first_name_metaphone_db2
                & first_name_f2c_db1 != first_name_f2c_db2
            ),

            forenames_misordered_denominator = sum(
                # Unidirectional check here.
                # Think of "first" as proband and "second" as candidate.
                #
                # Proband has at least the first forename:
                !is.na(first_name_name_db1)
                # Candidate has two non-identical forenames:
                & !is.na(first_name_name_db2) & !is.na(second_forename_name_db2)
                & first_name_name_db2 != second_forename_name_db2
            ),
            forenames_n_misordered = sum(
                # The conditions above...
                !is.na(first_name_name_db1)
                & !is.na(first_name_name_db2) & !is.na(second_forename_name_db2)
                & first_name_name_db2 != second_forename_name_db2
                # ... and an order mismatch:
                & (
                    # Candidate #2 matches proband #1...
                    second_forename_name_db2 == first_name_name_db1
                    # or (if proband #2 exists) candidate #1 matches proband #2
                    | (
                        !is.na(second_forename_name_db1)
                        & first_name_name_db2 == second_forename_name_db1
                    )
                )
            ),

            surname_n_present = sum(
                !is.na(surname_name_db1) & !is.na(surname_name_db2)
            ),
            surname_n_full_match = sum(
                !is.na(surname_name_db1) & !is.na(surname_name_db2)
                # Name match:
                & surname_name_db1 == surname_name_db2
            ),
            surname_n_p1nf_match = sum(
                !is.na(surname_name_db1) & !is.na(surname_name_db2)
                # Metaphone but not name match:
                & surname_name_db1 != surname_name_db2
                & surname_metaphone_db1 == surname_metaphone_db2
            ),
            surname_n_p2np1_match = sum(
                !is.na(surname_name_db1) & !is.na(surname_name_db2)
                # First two characters, but not name or metaphone:
                & surname_name_db1 != surname_name_db2
                & surname_metaphone_db1 != surname_metaphone_db2
                & surname_f2c_db1 == surname_f2c_db2
            ),
            surname_n_no_match = sum(
                !is.na(surname_name_db1) & !is.na(surname_name_db2)
                # Nothing matches:
                & surname_name_db1 != surname_name_db2
                & surname_metaphone_db1 != surname_metaphone_db2
                & surname_f2c_db1 != surname_f2c_db2
            ),

            dob_n_present = sum(
                !is.na(dob_db1) & !is.na(dob_db2)
            ),
            dob_n_full_match = sum(
                !is.na(dob_db1) & !is.na(dob_db2)
                & dob_db1 == dob_db2
            ),
            dob_n_partial_match = sum(
                !is.na(dob_db1) & !is.na(dob_db2)
                & dob_db1 != dob_db2
                & (
                    dob_md_db1 == dob_md_db2
                    | dob_yd_db1 == dob_yd_db2
                    | dob_ym_db1 == dob_ym_db2
                )
            ),
            dob_n_no_match = sum(
                !is.na(dob_db1) & !is.na(dob_db2)
                & dob_db1 != dob_db2
                & dob_md_db1 != dob_md_db2
                & dob_yd_db1 != dob_yd_db2
                & dob_ym_db1 != dob_ym_db2
            )
        ) %>%
        mutate(
            # f for fraction
            first_name_f_full_match = first_name_n_full_match / first_name_n_present,
            first_name_f_p1nf_match = first_name_n_p1nf_match / first_name_n_present,
            first_name_f_p2np1_match = first_name_n_p2np1_match / first_name_n_present,
            first_name_f_no_match = first_name_n_no_match / first_name_n_present,

            first_second_f_forename_misordered = forenames_n_misordered
                / forenames_misordered_denominator,

            surname_f_full_match = surname_n_full_match / surname_n_present,
            surname_f_p1nf_match = surname_n_p1nf_match / surname_n_present,
            surname_f_p2np1_match = surname_n_p2np1_match / surname_n_present,
            surname_f_no_match = surname_n_no_match / surname_n_present,

            dob_f_full_match = dob_n_full_match / dob_n_present,
            dob_f_partial_match = dob_n_partial_match / dob_n_present,
            dob_f_no_match = dob_n_no_match / dob_n_present,

            query_gender = gender
        )
        %>% as.data.table()
    )
    setcolorder(s, "query_gender")
    return(s)
}


empirical_discrepancy_rates_by_gender <- function(people_data_1, people_data_2)
{
    # Characterize the rates of empirical discrepancies amongst people who we
    # know to be the same in two databases, by gender and across all genders.

    return(rbind(
        empirical_discrepancy_rates(people_data_1, people_data_2, NA),
        empirical_discrepancy_rates(people_data_1, people_data_2, SEX_F),
        empirical_discrepancy_rates(people_data_1, people_data_2, SEX_M)
    ))
}


show_duplicate_nhsnum_effect <- function(probands, sample, comparison)
{
    # Show the effect of having a database where there are duplicate records
    # (judged by NHS number). We expect it to be harder to match if this
    # database serves as the sample.
    #
    # IN PROGRESS.

    probands[,
        is_nhsnum_duplicated :=
            part_of_duplicated_group(hashed_nhs_number)
    ]
    sample[,
        is_nhsnum_duplicated :=
            part_of_duplicated_group(hashed_nhs_number)
    ]
    return(NULL)
}


# =============================================================================
# Consider defaults
# =============================================================================

show_performance_means_by_theta_delta <- function(
    comp_threshold,
    weight_misidentification = WEIGHT_MISIDENTIFICATION,
    include_self_links = FALSE
) {
    performance_means_by_theta_delta <- (
        comp_threshold
    )
    if (!include_self_links) {
        # Self-linkages have lower misidentification rates, so it's better to
        # exclude these (as per the defaults).
        performance_means_by_theta_delta <- (
            performance_means_by_theta_delta %>%
            filter(from != to)
        )
    }
    performance_means_by_theta_delta <- (
        performance_means_by_theta_delta %>%
        mutate(WPM = FNR + weight_misidentification * MID) %>%
        # ... Weighted performance metric. Just for this study.
        group_by(theta, delta) %>%
        summarize(
            mean_TPR = mean(TPR),
            mean_FNR = mean(FNR),  # = 1 - TPR
            mean_FPR = mean(FPR, na.rm = TRUE),
            mean_accuracy = mean(Accuracy),
            mean_F1 = mean(F1),
            mean_MID = mean(MID),
            mean_WPM = mean(WPM),
            mean_distance_to_corner = mean(distance_to_corner, na.rm = TRUE),
            .groups = "drop"
        ) %>%
        as.data.table()
    )
    # To have the top row be the best, sort negatively for good quantities and
    # positively for bad quantities:
    write_output("By distance to corner:\n")
    setorder(performance_means_by_theta_delta, mean_distance_to_corner);
    write_output(performance_means_by_theta_delta)
    # ... for this, with TWO_STAGE_SDT_METHOD, theta = delta = 0 is best

    write_output("\nBy F1 score:\n")
    setorder(performance_means_by_theta_delta, -mean_F1);
    write_output(performance_means_by_theta_delta)

    write_output("\nBy TPR:\n")
    setorder(performance_means_by_theta_delta, -mean_TPR);
    write_output(performance_means_by_theta_delta)

    write_output("\nBy accuracy:\n")
    setorder(performance_means_by_theta_delta, -mean_accuracy);
    write_output(performance_means_by_theta_delta)

    # ... for these, theta = delta = 0 is best
    if (TWO_STAGE_SDT_METHOD) {
        write_output("\nBy MID:\n")
        setorder(performance_means_by_theta_delta, mean_MID);
        write_output(performance_means_by_theta_delta)
    }

    write_output("\nBy FPR:\n")
    setorder(performance_means_by_theta_delta, mean_FPR);
    write_output(performance_means_by_theta_delta)
    # ... for these, theta = delta = 15 is best.

    write_output(paste0(
        "\nBy WPM with weight_misidentification = ",
         weight_misidentification,
         ":\n"
     ))
    setorder(performance_means_by_theta_delta, mean_WPM);
    write_output(performance_means_by_theta_delta)
}


# =============================================================================
# Main
# =============================================================================

main <- function()
{
    # -------------------------------------------------------------------------
    # Load people and comparisons.
    # -------------------------------------------------------------------------

    load_all()

    # -------------------------------------------------------------------------
    # Basic missingness analysis; demographics
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Algorithm performance
    # -------------------------------------------------------------------------

    # Number of (truly) overlapping people in each pairwise comparison:
    comp_simple <- get_comparisons_simple()

    # Performance metrics at all combinations of theta/delta tested:
    comp_threshold <- get_comparisons_varying_threshold()

    # Show performance metrics by theta/delta
    write_output(show_performance_means_by_theta_delta(comp_threshold))

    # Performance figure
    mk_save_performance_plot(comp_threshold, comp_simple)

    # Performance metrics at default theta/delta values:
    comp_at_defaults <- comp_threshold[
        theta == DEFAULT_THETA & delta == DEFAULT_DELTA
    ]
    write_output(comp_at_defaults)

    # Simplified performance summary
    pst_table_defaults <- write_simplified_performance_summary_at_threshold()
    write.table(pst_table_defaults, PST_OUTPUT_FILE_DEFAULTS, row.names = FALSE)

    pst_table_zero <- write_simplified_performance_summary_at_threshold(
        theta = 0, delta = 0
    )
    write.table(pst_table_zero, PST_OUTPUT_FILE_ZERO, row.names = FALSE)

    # pst_table_neg_inf <- write_simplified_performance_summary_at_threshold(
    #     theta = -Inf, delta = 0
    # )
    # write.table(pst_table_neg_inf, PST_OUTPUT_FILE_NEG_INF, row.names = FALSE)
    #
    # The misidentification rates are very high, as expected, because every
    # proband (and in particular, everyone who is NOT in the sample database)
    # is paired with some candidate. This is perhaps not particularly
    # interesting.

    pst_table_theta_delta_15 <- write_simplified_performance_summary_at_threshold(
        theta = 15, delta = 15
    )
    write.table(
        pst_table_theta_delta_15,
        PST_OUTPUT_FILE_THETA_DELTA_15,
        row.names = FALSE
    )

    # -------------------------------------------------------------------------
    # Factors associated with non-linkage (in RiO -> SystmOne comparison)
    # -------------------------------------------------------------------------
    # ... at default values of theta/delta.

    m <- bias_at_threshold(compare_rio_to_systmone)  # at default thresholds
    write_output(summary(m))
    # Estimate = 0 is no effect, >0 more likely to be linked, <0 less likely.
    # Estimates are of log odds.
    write_output(car::Anova(m, type = "III", test.statistic = "F"))
    write_output(length(m$residuals))  # number of subjects participating

    # Not done: demographics predicting specific sub-reasons for non-linkage.
    # (We predict overall non-linkage above.)

    # -------------------------------------------------------------------------
    # Rates of identifier discrepancy for known-same people.
    # -------------------------------------------------------------------------
    # See also empirical_rates.sql, which does similar things direct from the
    # source databases.

    # Empirical analysis of identifier discrepancies between a single pair of
    # databases, among people known to be the same (by NHS number).
    discrepancies <- empirical_discrepancy_rates_by_gender(
        people_data_1 = get(mk_people_var(RIO)),
        people_data_2 = get(mk_people_var(SYSTMONE))
    )
    write_output(t(discrepancies))
    # For forename mis-ordering (first/second forenames swapped):
    #   F 90/54480; M 91/41736. (Across all genders: 184/96569.)
    # Analysis by gender:
    #   chisq.test(matrix(c(90, 91, 54480 - 90, 41736 - 91), nrow = 2))
    # Not significant.
    # Double-check with the canonical jury example via my 2004 stats booklet:
    #   chisq.test(matrix(c(153, 24, 105, 76), nrow = 2, byrow = TRUE), correct = FALSE)  # chisq = 35.93
    #   chisq.test(matrix(c(153, 24, 105, 76), nrow = 2, byrow = FALSE), correct = FALSE)  # chisq = 35.93
    # ... reminding us that transposing makes no difference.

    # -------------------------------------------------------------------------
    # Effects of duplication in PCMIS
    # -------------------------------------------------------------------------

    # duplicate_nhs_numbers_in_sample <- show_duplicate_nhsnum_effect(
    #     probands = get(mk_people_var(RIO)),
    #     sample = get(mk_people_var(PCMIS)),
    #     comparison = get(mk_comparison_var(RIO, PCMIS))
    # )  # INCOMPLETE. IGNORE.

    # -------------------------------------------------------------------------
    # Superseded analyses.
    # -------------------------------------------------------------------------

    if (FALSE) {
        # superseded analyses
        write_output(
            mean(people_systmone$first_name_frequency)
        )  # 0.003866141
        write_output(
            mean(people_systmone$first_name_metaphone_frequency)
        )  # 0.006856901
        write_output(
            mean(people_systmone$surname_frequency, na.rm = TRUE)
        )  # 0.000548923
        write_output(
            mean(people_systmone$surname_metaphone_frequency, na.rm = TRUE)
        )  # 0.001779113
    }

    # -------------------------------------------------------------------------
    # Done.
    # -------------------------------------------------------------------------

    write_output(paste("Finished:", Sys.time()))
}

# main()
