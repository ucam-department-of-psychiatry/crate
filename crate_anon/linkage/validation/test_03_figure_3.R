#!/usr/bin/env Rscript

# Not exactly the way the Python optimized code does it, but an
# illustration for Figure 3.

odds_from_p <- function(p) p/(1-p)
log_odds_from_p <- function(p) log(odds_from_p(p))
p_from_odds <- function(odds) odds/(1 + odds)
p_from_log_odds <- function(log_odds) p_from_odds(exp(log_odds))
log_posterior_odds_1 <- function(log_prior_odds, log_lr) log_prior_odds + log_lr
log_posterior_odds_2 <- function(log_prior_odds, p_d_h, p_d_not_h) {
    log_lr <- log(p_d_h / p_d_not_h)
    return(log_prior_odds + log_lr)
}

prior <- log_odds_from_p(1e-6)
dob_freq <- 3.04e-5
p_e_forename <- 0.001
p_e_surname <- 0.001
p_e_gender <- 0.0001

p_female <- 0.51

f_sname_smith <- 0.01006
f_smeta_sm0 <- 0.01013
f_fname_elizabeth_female <- 0.00949
f_fmeta_alsp_female <- 0.01007

compare <- function(log_prior_odds, p_d_h, p_d_not_h) {
    log_posterior_odds <- log_posterior_odds_2(log_prior_odds, p_d_h, p_d_not_h)
    cat(paste0(log_prior_odds,
               " -> P(D|H)=", p_d_h, " / P(D|¬H)=", p_d_not_h,
               " -> ", log_posterior_odds, "\n"))
    return(log_posterior_odds)
}

proband <- list(surname = "SMITH", f_surname = 0.01006,
                smeta = "SM0", f_smeta = 0.01013,
                firstname = "Elizabeth", f_firstname_given_gender = 0.00949,
                fmeta = "ALSP", f_fmeta_given_gender = 0.01007,
                dob = "1950-01-01",
                gender = "F", f_gender = 0.51)

show_sequence <- function(proband, candidate) {
    log_odds <- prior
    cat(paste0("Start at: ", log_odds, "\n"))

    if (proband$surname == candidate$surname) {
        cat("Surname matches\n")
        log_odds <- compare(log_odds, 1 - p_e_surname, proband$f_surname)
    } else if (proband$smeta == candidate$smeta) {
        cat("Surname metaphone matches\n")
        log_odds <- compare(log_odds, p_e_surname, proband$f_smeta - proband$f_surname)
    } else {
        cat("Surname mismatch; fail at -inf\n")
        return()
    }

    if (proband$firstname == candidate$firstname) {
        cat("Forename matches\n")
        log_odds <- compare(log_odds, 1 - p_e_forename, proband$f_firstname_given_gender)
    } else if (proband$fmeta == candidate$fmeta) {
        cat("Forename metaphone matches\n")
        log_odds <- compare(log_odds, p_e_forename, proband$f_fmeta_given_gender - proband$f_firstname_given_gender)
    } else {
        cat("Forename mismatch; fail at -inf\n")
        return()
    }

    if (proband$dob == candidate$dob) {
        cat("DOB matches\n")
        log_odds <- compare(log_odds, 1, dob_freq)
    } else {
        cat("DOB mismatch; fail at -inf\n")
        return()
    }

    if (proband$gender == candidate$gender) {
        cat("Gender matches\n")
        log_odds <- compare(log_odds, 1 - p_e_gender, proband$f_gender)
    } else {
        cat("Gender mismatch\n")
        log_odds <- compare(log_odds, p_e_gender, 1 - proband$f_gender)
    }

    cat(paste0("Finished at: ", log_odds, "\n"))
}

candidate1 <- list(surname = "JONES", smeta = "JNS",
                   firstname = "Elizabeth", fmeta = "ALSP",
                   dob = "1950-01-01", gender = "F")
candidate2 <- list(surname = "SMITH", smeta = "SM0",
                   firstname = "Elizabeth", fmeta = "ALSP",
                   dob = "1984-07-29", gender = "F")
candidate3 <- list(surname = "SMITH", smeta = "SM0",
                   firstname = "Elizabeth", fmeta = "ALSP",
                   dob = "1950-01-01", gender = "F")
candidate4 <- list(surname = "SMITH", smeta = "SM0",
                   firstname = "Elisabeth", fmeta = "ALSP",
                   dob = "1950-01-01", gender = "F")
candidate5 <- list(surname = "SMYTHE", smeta = "SM0",
                   firstname = "Elisabeth", fmeta = "ALSP",
                   dob = "1950-01-01", gender = "F")
show_sequence(proband, candidate1)
show_sequence(proband, candidate2)
show_sequence(proband, candidate3)
show_sequence(proband, candidate4)
show_sequence(proband, candidate5)
