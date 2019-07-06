#!/usr/bin/env Rscript

# For testing fuzzy_id_match.py

# =============================================================================
# Libraries
# =============================================================================

library(data.table)
library(ggplot2)
library(gridExtra)
library(pROC)

source("https://egret.psychol.cam.ac.uk/rlib/miscfile.R")
source("https://egret.psychol.cam.ac.uk/rlib/miscplot.R")


# =============================================================================
# Directories
# =============================================================================

WORKING_DIR <- file.path(miscfile$current_script_directory(),
                         "..", "..", "working")
INPUT_CSV <- file.path(WORKING_DIR, "fuzzy_validation_output.csv")
FIGURE_FILENAME <- file.path(WORKING_DIR, "fuzzy_validation_figure.pdf")


# =============================================================================
# Load data
# =============================================================================

fuzzy <- data.table(read.csv(INPUT_CSV))
fuzzy[, correct := ifelse(in_sample,
                          !is.na(best_match_id) & unique_id == best_match_id,
                          is.na(best_match_id))]

# =============================================================================
# ROC
# =============================================================================

create_roc <- function(d,
                       title = "MISSING TITLE",
                       very_large_negative = -1000,
                       dp = 3)
{
    # Create a ROC curve in which group membership (in or out) is predicted
    # by the log odds of the best match in the sample.

    response <- d$in_sample
    predictor <- d$best_log_odds
    predictor[predictor < very_large_negative] <- very_large_negative
    # ... roc() doesn't like -Inf
    r <- pROC::roc(response = response, predictor = predictor)
    # https://stackoverflow.com/questions/3443687/formatting-decimal-places-in-r
    auc_str <- format(round(r$auc, dp), nsmall = dp)
    p <- (
        pROC::ggroc(r) +
        ggplot2::geom_abline(intercept = 1, slope = 1, colour = "grey") +
        ggplot2::ggtitle(title) +
        ggplot2::theme_bw() +
        ggplot2::annotate("text", x = 0.25, y = 0.125,
                          label = paste0("AUC: ", auc_str))
    )
    return(list(
        roc = r,
        rocplot= p,
        auc = r$auc
    ))
}


plaintext_data <- fuzzy[collection_name %in% c("in_plaintext", "out_plaintext")]
plaintext_results <- create_roc(plaintext_data, "Plaintext original data")

hashed_data <- fuzzy[collection_name %in% c("in_hashed", "out_hashed")]
hashed_results <- create_roc(hashed_data, "Hashed original data")

deletion_data <- fuzzy[collection_name %in% c("in_deletions", "out_deletions")]
deletion_results <- create_roc(deletion_data, "Plaintext deletion data")

hashed_deletion_data <- fuzzy[collection_name %in% c("in_deletions_hashed", "out_deletions_hashed")]
hashed_deletion_results <- create_roc(hashed_deletion_data, "Hashed deletion data")

typo_data <- fuzzy[collection_name %in% c("in_typos", "out_typos")]
typo_results <- create_roc(typo_data, "Plaintext typo data")

hashed_typo_data <- fuzzy[collection_name %in% c("in_typos_hashed", "out_typos_hashed")]
hashed_typo_results <- create_roc(hashed_typo_data, "Hashed typo data")

fig <- gridExtra::arrangeGrob(
    plaintext_results$rocplot, hashed_results$rocplot,
    deletion_results$rocplot, hashed_deletion_results$rocplot,
    typo_results$rocplot, hashed_typo_results$rocplot,
    widths = c(0.5, 0.5),
    ncol = 2
)
# plot(fig)
miscplot$save_grob_to_pdf(fig, FIGURE_FILENAME, width_mm = 160, height_mm = 250)
