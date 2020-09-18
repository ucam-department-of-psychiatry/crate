#!/usr/bin/env Rscript
# crate_anon/linkage/analyse_fuzzy_id_match_validation1.R

# For testing the output of "crate_fuzzy_id_match validate1"

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
INPUT_CSV <- file.path(WORKING_DIR, "fuzzy_validation1_output.csv")
FIGURE_FILENAME <- file.path(WORKING_DIR, "fuzzy_validation1_figure.pdf")


# =============================================================================
# Load data
# =============================================================================

fuzzy <- data.table(read.csv(INPUT_CSV))


# =============================================================================
# ROC
# =============================================================================

create_roc <- function(d,
                       title = "MISSING TITLE",
                       very_large_negative = -1000)
{
    # Create a ROC curve in which group membership (in or out) is predicted
    # by the log odds of the best match in the sample.

    response1 <- d$in_sample
    predictor1 <- d$best_log_odds
    predictor1[predictor1 < very_large_negative] <- very_large_negative
    # ... roc() doesn't like -Inf
    r1 <- pROC::roc(response = response1, predictor = predictor1)
    # https://stackoverflow.com/questions/3443687/formatting-decimal-places-in-r
    auc1_str <- format(round(r1$auc, 3), nsmall = 3)
    p1 <- (
        pROC::ggroc(r1) +
        ggplot2::geom_abline(intercept = 1, slope = 1, colour = "grey") +
        ggplot2::ggtitle(title) +
        ggplot2::theme_bw() +
        ggplot2::annotate("text", x = 0.25, y = 0.125,
                          label = paste0("AUC: ", auc1_str))
    )

    d2 <- d[!is.na(winner_id)]
    prop_correct <- sum(d2$correct_if_winner) / nrow(d2)
    pct_correct_str <- format(round(prop_correct * 100, 1), nsmall = 1)
    response2 <- d2$correct_if_winner
    if (length(unique(response2)) < 2) {
        r2 <- NULL
        p2 <- NULL
    } else {
        predictor2 <- d2$winner_advantage
        predictor2[predictor2 < very_large_negative] <- very_large_negative
        r2 <- pROC::roc(response = response2, predictor = predictor2)
        # https://stackoverflow.com/questions/3443687/formatting-decimal-places-in-r
        auc2_str <- format(round(r2$auc, 3), nsmall = 3)
        p2 <- (
            pROC::ggroc(r2) +
            ggplot2::geom_abline(intercept = 1, slope = 1, colour = "grey") +
            ggplot2::ggtitle(title) +
            ggplot2::theme_bw() +
            ggplot2::annotate("text", x = 0.25, y = 0.125,
                              label = paste0("AUC: ", auc2_str)) +
            ggplot2::annotate("text", x = 0.25, y = 0.25,
                              label = paste0("%correct: ", pct_correct_str))
        )
    }

    return(list(
        roc1 = r1,
        rocplot1 = p1,
        roc2 = r2,
        rocplot2 = p2
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
    plaintext_results$rocplot1, hashed_results$rocplot1,
    deletion_results$rocplot1, hashed_deletion_results$rocplot1,
    typo_results$rocplot1, hashed_typo_results$rocplot1,
    widths = c(0.5, 0.5),
    ncol = 2
)
# plot(fig)
miscplot$save_grob_to_pdf(fig, FIGURE_FILENAME, width_mm = 160, height_mm = 250)
