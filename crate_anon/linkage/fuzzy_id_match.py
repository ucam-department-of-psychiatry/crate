#!/usr/bin/env python

r"""
crate_anon/linkage/fuzzy_id_match.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Fuzzy matching with hashed identifiers.**

See draft paper.

"""

# =============================================================================
# Imports
# =============================================================================

import argparse
import csv
from io import StringIO
import json
import logging
from multiprocessing import Pool
import sys
import time
from typing import Any, List, Tuple, TYPE_CHECKING

from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
    ShowAllSubparserHelpAction,
)
from cardinal_pythonlib.datetimefunc import coerce_to_pendulum_date
from cardinal_pythonlib.hash import HashMethods
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.probability import probability_from_log_odds
from cardinal_pythonlib.profile import do_cprofile

from crate_anon.common.constants import EXIT_FAILURE, EXIT_SUCCESS
from crate_anon.linkage.helpers import (
    cache_load,
    cache_save,
    get_metaphone,
    get_postcode_sector,
    optional_int,
    standardize_postcode,
)
from crate_anon.linkage.identifiers import TemporalIDHolder
from crate_anon.linkage.constants import (
    DAYS_PER_YEAR,
    FuzzyDefaults,
    GENDER_FEMALE,
    GENDER_MALE,
)
from crate_anon.linkage.matchconfig import MatchConfig
from crate_anon.linkage.person import (
    gen_person_from_file,
    SimplePerson,
    DuplicateLocalIDError,
    MatchResult,
    People,
    Person,
    PersonWriter,
)
from crate_anon.version import CRATE_VERSION

if TYPE_CHECKING:
    # noinspection PyProtectedMember,PyUnresolvedReferences
    from argparse import _SubParsersAction

log = logging.getLogger(__name__)


# =============================================================================
# Notes
# =============================================================================

_ = """

**Testing the concept of fuzzy matching with hashed identifiers, as part of
work to link UK NHS and education/social care data without sharing direct
patient identifiers.**


.. _TLSH: https://github.com/trendmicro/tlsh
.. _sdhash: https://roussev.net/sdhash/sdhash.html
.. _Nilsimsa: https://en.wikipedia.org/wiki/Nilsimsa_Hash
.. _ssdeep: https://ssdeep-project.github.io/ssdeep/index.html


**See draft paper.**


Other approaches to fuzzy matching of reduced data
--------------------------------------------------

[COVERED IN THE PAPER. FURTHER DETAIL HERE.]

Note the unsuitability of fuzzy hashing algorithms designed for long streams of
bytes or text. In general, these chop the input up into blocks, hash each
block, and then compare the sequence of mini-hashes for similarity.

- the trend micro locality sensitive hash (TLSH_), for fuzzy hashing of byte
  streams of at least 50 bytes;

- sdhash_, comparison of arbitrary data blobs based on common strings of binary
  data.

- Nilsimsa_ (2001/2004) a locality-sensitive hashing algorithm) and ssdeep_, a
  context triggered piecewise hashing (CTPH) algorithm.

  - See Kornblum J (2006), "Identifying almost identical files using context
    triggered piecewise hashing", *Digital Investigation* 3S: S91-S97,
    https://doi.org/10.1016/j.diin.2006.06.015.

... cited in the paper via Kornblum (2006) and Lee & Atkinson (2017), which
covers SSDEEP, TLSH, sdhash, and others.


"""  # noqa


# =============================================================================
# Constants
# =============================================================================

CRATE_FETCH_WORDLISTS = "crate_fetch_wordlists"


# =============================================================================
# Comparing people
# =============================================================================


class ComparisonOutputColnames:
    PROBAND_LOCAL_ID = "proband_local_id"
    MATCHED = "matched"
    LOG_ODDS_MATCH = "log_odds_match"
    P_MATCH = "p_match"
    SAMPLE_MATCH_LOCAL_ID = "sample_match_local_id"
    SECOND_BEST_LOG_ODDS = "second_best_log_odds"

    BEST_CANDIDATE_LOCAL_ID = "best_candidate_local_id"

    COMPARISON_OUTPUT_COLNAMES = [
        PROBAND_LOCAL_ID,
        MATCHED,
        LOG_ODDS_MATCH,
        P_MATCH,
        SAMPLE_MATCH_LOCAL_ID,
        SECOND_BEST_LOG_ODDS,
    ]
    COMPARISON_EXTRA_COLNAMES = [BEST_CANDIDATE_LOCAL_ID]


_ = """

compare_probands_to_sample:

    Profiling with 10,000 probands and the exact same people in the sample, on
    Wombat:

    - Start (2020-04-25, 11:52): 52 seconds for the first 1,000 probands.
    - next: 50.99. Not much improvement!
    - multiprocessing didn't help (overheads?)
    - multithreading didn't help (GIL?)
    - we remain at about 25.889 seconds per 400 probands within a
      10k * 10k set (= 15 probands/sec).
    - down to 22.5 seconds with DOB shortlisting, and that is with a highly
      self-similar sample, so that may improve dramatically.
    - retried multithreading with ThreadPoolExecutor: 20.9 seconds for 400,
      compared to 23.58 with single-threading; pretty minimal difference.
    - retried multiprocessing with ProcessPoolExecutor: maybe 2/8 cores at high
      usage at any given time? Not properly profiled.
    - then with multiprocessing.Pool...

      - https://stackoverflow.com/questions/18671528/processpoolexecutor-from-concurrent-futures-way-slower-than-multiprocessing-pool
      - https://helpful.knobs-dials.com/index.php/Python_usage_notes/Multiprocessing_notes
      - slow, but then added ``chunksize = n_probands // n_workers`` (I think
        it's the interprocess communication/setup that is slow)...

      - 147.168 seconds -- but for all 10k rows, so that is equivalent to
        5.88 seconds for 400, and much better.
      - Subsequently reached 111.8 s for 10k probands (and 10k sample),
        for 89 probands/sec.

    - This is an O(n^2) algorithm, in that its time grows linearly with the
      number of probands to check, and with the number of sample members to
      check against -- though on average at 1/(365*b) = 1/32850 the gradient
      for the latter, since we use birthday prefiltering.

    - Different DOB, middle name methods and gender check takes us to
      150.15 s for 10k*10k (2020-05-02). The fake data has lots of DOB overlap
      so real-world performance is likely to be much better.

    - Using generic ID/frequency structures took this down to 130.5s
      (2020-05-02), and some simplification to 124.76s, for 10k*10k.

    .. code-block:: none

        crate_fuzzy_id_match compare_plaintext \
            --probands fuzzy_sample_10k.csv \
            --sample fuzzy_sample_10k.csv \
            --output fuzzy_output_10k.csv

        # to profile, add: --profile --n_workers 1

"""  # noqa


def compare_probands_to_sample(
    cfg: MatchConfig,
    probands: People,
    sample: People,
    output_filename: str,
    report_every: int = 100,
    extra_validation_output: bool = False,
    n_workers: int = FuzzyDefaults.N_PROCESSES,
    max_chunksize: int = FuzzyDefaults.MAX_CHUNKSIZE,
    min_probands_for_parallel: int = FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
) -> None:
    r"""
    Compares each proband to the sample. Writes to an output file. If
    ``n_workers == 1``, proband order is retained. If parallel processing is
    used, order may not be preserved.

    Args:
        cfg:
            The main :class:`MatchConfig` object.
        probands:
            :class:`People`
        sample:
            :class:`People`
        output_filename:
            Output CSV filename.
        report_every:
            Report progress every n probands.
        extra_validation_output:
            Add extra columns to the output for validation purposes?
        n_workers:
            Number of parallel processes to use.
        max_chunksize:
            Maximum chunksize for parallel processing.
        min_probands_for_parallel:
            Minimum number of probands for which we will bother to use parallel
            processing.
    """

    def process_result(r: MatchResult) -> None:
        # Uses "rownum" and "writer" from outer scope.
        nonlocal rownum
        rownum += 1
        if rownum % report_every == 0:
            log.info(f"Processing result {rownum}/{n_probands}")
        p = r.proband
        w = r.winner
        matched = r.matched
        c = ComparisonOutputColnames
        rowdata = {
            c.PROBAND_LOCAL_ID: p.local_id,
            c.MATCHED: int(matched),
            c.LOG_ODDS_MATCH: r.best_log_odds,
            c.P_MATCH: probability_from_log_odds(r.best_log_odds),
            c.SAMPLE_MATCH_LOCAL_ID: w.local_id if matched else None,
            c.SECOND_BEST_LOG_ODDS: r.second_best_log_odds,
        }
        if extra_validation_output:
            rowdata[c.BEST_CANDIDATE_LOCAL_ID] = (
                r.best_candidate.local_id if r.best_candidate else None
            )
        writer.writerow(rowdata)

    # Checks:
    n_probands = probands.size()
    probands.ensure_valid_as_probands()
    n_sample = sample.size()
    if n_sample > cfg.population_size:
        log.critical(
            f"Sample size exceeds population size of {cfg.population_size}; "
            f"assumptions violated! In particular, the prior probability for "
            f"each candidate is guaranteed to be wrong. Aborting."
        )
        sys.exit(EXIT_FAILURE)
    sample.ensure_valid_as_sample()
    log.info(
        f"Comparing each proband to sample. There are "
        f"{n_probands} probands and {n_sample} in the sample."
    )

    # Off we go.
    parallel = n_workers > 1 and n_probands >= min_probands_for_parallel
    colnames = ComparisonOutputColnames.COMPARISON_OUTPUT_COLNAMES
    if extra_validation_output:
        colnames += ComparisonOutputColnames.COMPARISON_EXTRA_COLNAMES
    rownum = 0
    time_start = time.time()
    with open(output_filename, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=colnames)
        writer.writeheader()

        if parallel:
            chunksize = max(1, min(n_probands // n_workers, max_chunksize))
            # ... chunksize must be >= 1
            log.info(
                f"Using parallel processing with {n_workers} workers and "
                f"chunksize of {chunksize}."
            )

            # This is slow:
            #
            # executor = ProcessPoolExecutor(max_workers=max_workers)
            # for result in executor.map(sample.get_unique_match_detailed,
            #                            probands.people,
            #                            cycle([cfg])):
            #     process_result(result)
            #
            # This doesn't work as you can't pickle a local function:
            #
            # with Pool(processes=n_workers) as pool:
            #     for result in pool.imap_unordered(  # one arg per call
            #             make_result,  # local function
            #             probands.people,
            #             chunksize=chunksize):
            #         process_result(result)
            #
            # This is fine, though it only collects results at the end:
            # with Pool(processes=n_workers) as pool:
            #     for result in pool.starmap(  # many args
            #             sample.get_unique_match_detailed,
            #             zip(probands.people, cycle([cfg])),
            #             chunksize=chunksize):
            #         process_result(result)

            with Pool(processes=n_workers) as pool:
                for result in pool.imap_unordered(  # one arg per call
                    sample.get_unique_match_detailed,
                    probands.people,
                    chunksize=chunksize,
                ):
                    process_result(result)

        else:
            log.info("Not using parallel processing.")
            for rownum, proband in enumerate(probands.people, start=1):
                result = sample.get_unique_match_detailed(proband)
                process_result(result)

    time_end = time.time()
    total_dur = time_end - time_start

    log.info(f"... comparisons done. Time taken: {total_dur} s")


def compare_probands_to_sample_from_files(
    cfg: MatchConfig,
    probands_filename: str,
    sample_filename: str,
    output_filename: str,
    probands_plaintext: bool = True,
    sample_plaintext: bool = True,
    sample_cache_filename: str = "",
    extra_validation_output: bool = False,
    profile: bool = False,
    n_workers: int = FuzzyDefaults.N_PROCESSES,
    max_chunksize: int = FuzzyDefaults.MAX_CHUNKSIZE,
    min_probands_for_parallel: int = FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
) -> None:
    """
    Compares each of the people in the probands file to the sample file.

    Args:
        cfg:
            The main :class:`MatchConfig` object.
        probands_filename:
            Filename of people (probands); see :func:`read_people`.
        sample_filename:
            Filename of people (sample); see :func:`read_people`.
        output_filename:
            Output filename.
        sample_cache_filename:
            File in which to cache sample, for speed.
        probands_plaintext:
            Is the probands file plaintext (not hashed)?
        sample_plaintext:
            Is the sample file plaintext (not hashed)?
        extra_validation_output:
            Add extra columns to the output for validation purposes?
        profile:
            Profile the code?
        n_workers:
            Number of parallel processes to use.
        max_chunksize:
            Maximum chunksize for parallel processing.
        min_probands_for_parallel:
            Minimum number of probands for which we will bother to use parallel
            processing.
    """
    # Sample
    log.info("Loading (or caching) sample data")
    if sample_plaintext:
        if sample_cache_filename:
            log.info(f"Using sample cache: {sample_cache_filename}")
            try:
                (sample,) = cache_load(sample_cache_filename)
            except FileNotFoundError:
                sample = read_people(cfg, sample_filename)
                cache_save(sample_cache_filename, [sample])
        else:
            # You may want to avoid a cache, for security.
            log.info("No sample cache in use.")
            sample = read_people(cfg, sample_filename)
    else:
        sample = read_people(cfg, sample_filename, plaintext=False)

    # Probands
    log.info("Loading proband data")
    probands = read_people(
        cfg, probands_filename, plaintext=probands_plaintext
    )

    # Ensure they are comparable
    if sample_plaintext and not probands_plaintext:
        log.info("Hashing sample...")
        sample = sample.hashed()
        log.info("... done")
    elif probands_plaintext and not sample_plaintext:
        log.warning("Odd: comparing plaintext probands to hashed sample!")
        log.info("Hashing probands...")
        probands = probands.hashed()
        log.info("... done")

    # Compare
    compare_fn = (
        do_cprofile(compare_probands_to_sample, sort="cumtime")
        if profile
        else compare_probands_to_sample
    )
    compare_fn(
        cfg=cfg,
        probands=probands,
        sample=sample,
        output_filename=output_filename,
        extra_validation_output=extra_validation_output,
        n_workers=n_workers,
        max_chunksize=max_chunksize,
        min_probands_for_parallel=min_probands_for_parallel,
    )


# =============================================================================
# Loading people data
# =============================================================================


def read_people_alternate_groups(
    cfg: MatchConfig,
    filename: str,
    plaintext: bool = True,
) -> Tuple[People, People]:
    """
    Read people from a file, splitting consecutive people into "first group",
    "second group". (A debugging/validation feature.)

    Returns:
        tuple: ``first_group``, ``second_group``
    """
    a = People(cfg=cfg)
    b = People(cfg=cfg)
    for i, person in enumerate(
        gen_person_from_file(cfg, filename, plaintext), start=2
    ):
        try:
            if i % 2 == 0:
                a.add_person(person)
            else:
                b.add_person(person)
        except DuplicateLocalIDError as exc:
            msg = f"{exc} at line {i} of {filename}"
            log.error(msg)
            raise DuplicateLocalIDError(msg)
    return a, b


def read_people(
    cfg: MatchConfig, filename: str, plaintext: bool = True
) -> People:
    """
    Read a list of people from a CSV/JSONLines file.

    See :func:`read_people_2`, but this version doesn't offer the feature of
    splitting into two groups, and returns only a single :class:`People`
    object.
    """
    people = People(cfg=cfg)
    for i, person in enumerate(
        gen_person_from_file(cfg, filename, plaintext), start=2
    ):
        try:
            people.add_person(person)
        except DuplicateLocalIDError as exc:
            msg = f"{exc} at line {i} of {filename}"
            log.error(msg)
            raise DuplicateLocalIDError(msg)
    return people


# =============================================================================
# Hash plaintext to encrypted CSV
# =============================================================================


def hash_identity_file(
    cfg: MatchConfig,
    input_filename: str,
    output_filename: str,
    include_frequencies: bool = True,
    include_other_info: bool = False,
) -> None:
    """
    Hash a file of identifiable people to a hashed version. Order is preserved.

    Args:
        cfg:
            The main :class:`MatchConfig` object.
        input_filename:
            Input (plaintext) CSV filename to read.
        output_filename:
            Output (hashed) CSV filename to write.
        include_frequencies:
            Include frequency information. Without this, the resulting file is
            suitable for use as a sample, but not as a proband file.
        include_other_info:
            Include the (potentially identifying) ``other_info`` data? Usually
            ``False``; may be ``True`` for validation.
    """
    with PersonWriter(
        filename=output_filename,
        plaintext=False,
        include_frequencies=include_frequencies,
        include_other_info=include_other_info,
    ) as writer:
        for person in gen_person_from_file(cfg, input_filename):
            writer.write(person)


# =============================================================================
# Demonstration data
# =============================================================================


def get_demo_people() -> List[SimplePerson]:
    """
    Some demonstration records. All data are fictional. The postcodes are real
    but are institutional, not residential, addresses in Cambridge.
    """
    d = coerce_to_pendulum_date

    def p(postcode: str) -> TemporalIDHolder:
        return TemporalIDHolder(
            identifier=postcode,
            start_date=d("2000-01-01"),
            end_date=d("2010-12-31"),
        )

    def mkother(original_id: str) -> str:
        return json.dumps({"original_id": original_id, "other_info": "?"})

    return [
        SimplePerson(
            local_id="r1",
            other_info=mkother("1"),
            first_name="Alice",
            middle_names=["Zara"],
            surname="Smith",
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
        ),
        SimplePerson(
            local_id="r2",
            other_info=mkother("2"),
            first_name="Bob",
            middle_names=["Yorick"],
            surname="Jones",
            dob="1932-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 3EB")],
        ),
        SimplePerson(
            local_id="r3",
            other_info=mkother("3"),
            first_name="Celia",
            middle_names=["Xena"],
            surname="Wright",
            dob="1933-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 1TP")],
        ),
        SimplePerson(
            local_id="r4",
            other_info=mkother("4"),
            first_name="David",
            middle_names=["William", "Wallace"],
            surname="Cartwright",
            dob="1934-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 8PH"), p("CB2 1TP")],
        ),
        SimplePerson(
            local_id="r5",
            other_info=mkother("5"),
            first_name="Emily",
            middle_names=["Violet"],
            surname="Fisher",
            dob="1935-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB3 9DF")],
        ),
        SimplePerson(
            local_id="r6",
            other_info=mkother("6"),
            first_name="Frank",
            middle_names=["Umberto"],
            surname="Williams",
            dob="1936-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 1TQ")],
        ),
        SimplePerson(
            local_id="r7",
            other_info=mkother("7"),
            first_name="Greta",
            middle_names=["Tilly"],
            surname="Taylor",
            dob="1937-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 1DQ")],
        ),
        SimplePerson(
            local_id="r8",
            other_info=mkother("8"),
            first_name="Harry",
            middle_names=["Samuel"],
            surname="Davies",
            dob="1938-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB3 9ET")],
        ),
        SimplePerson(
            local_id="r9",
            other_info=mkother("9"),
            first_name="Iris",
            middle_names=["Ruth"],
            surname="Evans",
            dob="1939-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB3 0DG")],
        ),
        SimplePerson(
            local_id="r10",
            other_info=mkother("10"),
            first_name="James",
            middle_names=["Quentin"],
            surname="Thomas",
            dob="1940-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 0SZ")],
        ),
        SimplePerson(
            local_id="r11",
            other_info=mkother("11"),
            first_name="Alice",
            middle_names=[],
            surname="Smith",
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
        ),
    ]


def get_demo_csv() -> str:
    """
    A demonstration CSV file, as text.
    """
    people = get_demo_people()
    assert len(people) >= 1
    output = StringIO()
    with PersonWriter(file=output, plaintext=True) as writer:
        for person in people:
            writer.write(person)
    return output.getvalue()


# =============================================================================
# Command-line entry point
# =============================================================================


class Switches:
    """
    Argparse option switches that are used in several places.
    """

    ALLOW_DEFAULT_HASH_KEY = "allow_default_hash_key"
    EXTRA_VALIDATION_OUTPUT = "extra_validation_output"
    INCLUDE_OTHER_INFO = "include_other_info"
    INPUT = "input"
    OUTPUT = "output"
    N_WORKERS = "n_workers"

    KEY = "key"
    HASH_METHOD = "hash_method"
    ROUNDING_SF = "rounding_sf"
    LOCAL_ID_HASH_KEY = "local_id_hash_key"

    POPULATION_SIZE = "population_size"

    FORENAME_CACHE_FILENAME = "forename_cache_filename"
    FORENAME_SEX_FREQ_CSV = "forename_sex_freq_csv"
    SURNAME_CACHE_FILENAME = "surname_cache_filename"
    SURNAME_FREQ_CSV = "surname_freq_csv"
    MIN_NAME_FREQUENCY = "min_name_frequency"
    P_MIDDLE_NAME_N_PRESENT = "p_middle_name_n_present"

    BIRTH_YEAR_PSEUDO_RANGE = "birth_year_pseudo_range"

    P_NOT_MALE_OR_FEMALE = "p_not_male_or_female"
    P_FEMALE_GIVEN_MALE_OR_FEMALE = "p_female_given_male_or_female"

    POSTCODE_CACHE_FILENAME = "postcode_cache_filename"
    POSTCODE_CSV_FILENAME = "postcode_csv_filename"
    MEAN_OA_POPULATION = "mean_oa_population"
    P_UNKNOWN_OR_PSEUDO_POSTCODE = "p_unknown_or_pseudo_postcode"

    P_MINOR_FORENAME_ERROR = "p_minor_forename_error"
    P_PROBAND_MIDDLE_NAME_MISSING = "p_proband_middle_name_missing"
    P_SAMPLE_MIDDLE_NAME_MISSING = "p_sample_middle_name_missing"
    P_MINOR_SURNAME_ERROR = "p_minor_surname_error"
    P_DOB_ERROR = "p_dob_error"
    P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR = (
        "p_dob_single_component_error_if_error"
    )
    P_GENDER_ERROR = "p_gender_error"
    P_MINOR_POSTCODE_ERROR = "p_minor_postcode_error"

    MIN_LOG_ODDS_FOR_MATCH = "min_log_odds_for_match"
    EXCEEDS_NEXT_BEST_LOG_ODDS = "exceeds_next_best_log_odds"


class Commands:
    """
    Main commands.
    """

    HASH = "hash"
    COMPARE_PLAINTEXT = "compare_plaintext"
    COMPARE_HASHED_TO_HASHED = "compare_hashed_to_hashed"
    COMPARE_HASHED_TO_PLAINTEXT = "compare_hashed_to_plaintext"

    PRINT_DEMO_SAMPLE = "print_demo_sample"
    SHOW_METAPHONE = "show_metaphone"
    SHOW_FORENAME_FREQ = "show_forename_freq"
    SHOW_FORENAME_METAPHONE_FREQ = "show_forename_metaphone_freq"
    SHOW_SURNAME_FREQ = "show_surname_freq"
    SHOW_SURNAME_METAPHONE_FREQ = "show_surname_metaphone_freq"
    SHOW_DOB_FREQ = "show_dob_freq"
    SHOW_POSTCODE_FREQ = "show_postcode_freq"


# -----------------------------------------------------------------------------
# Long help strings
# -----------------------------------------------------------------------------

HELP_COMPARISON = f"""
Comparison rules:

- People MUST match on DOB and surname (or surname metaphone), or hashed
  equivalents, to be considered a plausible match.

- Only plausible matches proceed to the Bayesian comparison.

The output file is a CSV (comma-separated value) file with a header and
these columns:

    {ComparisonOutputColnames.PROBAND_LOCAL_ID}:
        Local ID (identifiable or de-identified as the user chose) of the
        proband. Taken from the input.
    {ComparisonOutputColnames.MATCHED}:
        Boolean as binary (0/1). Was a matching person (a "winner") found in
        the sample, who is to be considered a match to the proband? To give a
        match requires (a) that the log odds for the winner reaches a
        threshold, and (b) that the log odds for the winner exceeds the log
        odds for the runner-up by a certain amount (because a mismatch may be
        worse than a failed match).
    {ComparisonOutputColnames.LOG_ODDS_MATCH}:
        Log (ln) odds that the best candidate in the sample is a match to the
        proband.
    {ComparisonOutputColnames.P_MATCH}:
        Probability that the best candidate in the sample is a match.
        Equivalent to {ComparisonOutputColnames.LOG_ODDS_MATCH}.
    {ComparisonOutputColnames.SAMPLE_MATCH_LOCAL_ID}:
        Local ID of the "winner" in the sample (the candidate who was matched
        to the proband), or blank if there was no winner.
    {ComparisonOutputColnames.SECOND_BEST_LOG_ODDS}:
        Log odds of the runner-up (the candidate from the sample who is the
        second-closest match) being the same person as the proband.

If '--{Switches.EXTRA_VALIDATION_OUTPUT}' is used, the following columns are
added:

    {ComparisonOutputColnames.BEST_CANDIDATE_LOCAL_ID}:
        Local ID of the closest-matching person (candidate) in the sample, EVEN
        IF THEY DID NOT WIN. (This will be the same as the winner if there was
        a match.) String; blank for no match.

If you use '--{Switches.N_WORKERS} 1`, proband order is reproduced in the
output. Otherwise, the results file is NOT necessarily sorted as the same order
as the input proband file (because not sorting improves parallel processing
efficiency).
"""


# -----------------------------------------------------------------------------
# Helper functions for main argument parser
# -----------------------------------------------------------------------------


def warn_or_fail_if_default_key(args: argparse.Namespace) -> None:
    """
    Ensure that we are not using the default (insecure) hash key unless the
    user has specifically authorized this.

    It's pretty unlikely that ``local_id_hash_key`` will be this specific
    default, because that defaults to ``None``. However, ``key`` might be.
    """
    if (
        args.key == FuzzyDefaults.HASH_KEY
        or args.local_id_hash_key == FuzzyDefaults.HASH_KEY
    ):
        if args.allow_default_hash_key:
            log.warning(
                "Proceeding with default hash key at user's "
                "explicit request."
            )
        else:
            log.error(
                "You have not specified a hash key, so are using the "
                "default! Stopping, because this is a very bad idea for "
                f"real data. Specify --{Switches.ALLOW_DEFAULT_HASH_KEY} to "
                "use the default for testing purposes."
            )
            sys.exit(EXIT_FAILURE)


def add_subparsers(
    parser: argparse.ArgumentParser,
) -> "_SubParsersAction":
    """
    Adds global-only options and subparsers.
    """
    parser.add_argument(
        "--version", action="version", version=f"CRATE {CRATE_VERSION}"
    )
    parser.add_argument(
        "--allhelp",
        action=ShowAllSubparserHelpAction,
        help="show help for all commands and exit",
    )
    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid commands are as follows.",
        help="Specify one command.",
        dest="command",  # sorts out the help for the command being mandatory
    )  # type: _SubParsersAction  # noqa
    subparsers.required = True  # requires a command
    return subparsers


def add_basic_options(parser: argparse.ArgumentParser) -> None:
    """
    Adds a subparser for global options.
    """
    arggroup = parser.add_argument_group("display options")
    arggroup.add_argument("--verbose", action="store_true", help="Be verbose")


def add_hasher_options(parser: argparse.ArgumentParser) -> None:
    """
    Adds a subparser for hasher options.
    """
    hasher_group = parser.add_argument_group("hasher (secrecy) options")
    hasher_group.add_argument(
        f"--{Switches.KEY}",
        type=str,
        default=FuzzyDefaults.HASH_KEY,
        help="Key (passphrase) for hasher",
    )
    hasher_group.add_argument(
        f"--{Switches.ALLOW_DEFAULT_HASH_KEY}",
        action="store_true",
        help=(
            "Allow the default hash key to be used beyond tests. INADVISABLE!"
        ),
    )
    hasher_group.add_argument(
        f"--{Switches.HASH_METHOD}",
        choices=[
            HashMethods.HMAC_MD5,
            HashMethods.HMAC_SHA256,
            HashMethods.HMAC_SHA512,
        ],
        default=FuzzyDefaults.HASH_METHOD,
        help="Hash method",
    )
    hasher_group.add_argument(
        f"--{Switches.ROUNDING_SF}",
        type=optional_int,
        default=FuzzyDefaults.ROUNDING_SF,
        help="Number of significant figures to use when rounding frequencies "
        "in hashed version. Use 'None' to disable rounding.",
    )
    hasher_group.add_argument(
        f"--{Switches.LOCAL_ID_HASH_KEY}",
        type=str,
        default=None,
        help=f"Only applicable to the {Commands.HASH!r} command. Hash the "
        f"local_id values, using this key (passphrase). There are good "
        f"reasons to use a key different to that specified for "
        f"--{Switches.KEY}. If you leave this blank, or specify an empty "
        f"string, then local ID values will be left unmodified (e.g. if you "
        f"have pre-hashed them).",
    )


def add_config_options(parser: argparse.ArgumentParser) -> None:
    """
    Adds a subparser for MatchConfig options (excepting hasher, above).
    In a function because we use these in validate_fuzzy_linkage.py too.
    """
    priors_group = parser.add_argument_group(
        "frequency information for prior probabilities"
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Population size
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    priors_group.add_argument(
        f"--{Switches.POPULATION_SIZE}",
        type=int,
        default=FuzzyDefaults.POPULATION_SIZE,
        help="Size of the whole population, from which we calculate the "
        "baseline log odds that two people, randomly selected (and "
        "replaced) from the population are the same person.",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Name frequencies
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    priors_group.add_argument(
        f"--{Switches.FORENAME_CACHE_FILENAME}",
        type=str,
        default=FuzzyDefaults.FORENAME_CACHE_FILENAME,
        help="File in which to store cached forename info (to speed loading)",
    )
    priors_group.add_argument(
        f"--{Switches.FORENAME_SEX_FREQ_CSV}",
        type=str,
        default=FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
        help=f'CSV file of "name, sex, frequency" pairs for forenames. '
        f"You can generate one via {CRATE_FETCH_WORDLISTS}. If you later "
        f"alter this, delete your forename cache so it can be rebuilt.",
    )
    priors_group.add_argument(
        f"--{Switches.SURNAME_CACHE_FILENAME}",
        type=str,
        default=FuzzyDefaults.SURNAME_CACHE_FILENAME,
        help="File in which to store cached surname info (to speed loading)",
    )
    priors_group.add_argument(
        f"--{Switches.SURNAME_FREQ_CSV}",
        type=str,
        default=FuzzyDefaults.SURNAME_FREQ_CSV,
        help=f'CSV file of "name, frequency" pairs for forenames. '
        f"You can generate one via {CRATE_FETCH_WORDLISTS}. If you later "
        f"alter this, delete your surname cache so it can be rebuilt.",
    )
    priors_group.add_argument(
        f"--{Switches.MIN_NAME_FREQUENCY}",
        type=float,
        default=FuzzyDefaults.NAME_MIN_FREQ,
        help="Minimum base frequency for names. If a frequency is less than "
        "this, use this minimum. Allowing extremely low frequencies may "
        "increase the chances of a spurious match. Note also that "
        "typical name frequency tables don't give very-low-frequency "
        "information. For example, for US census forename/surname "
        "information, below 0.001 percent they report 0.000 percent; so "
        "a reasonable minimum is 0.0005 percent or 0.000005 or 5e-6.",
    )
    priors_group.add_argument(
        f"--{Switches.P_MIDDLE_NAME_N_PRESENT}",
        type=str,
        default=FuzzyDefaults.P_MIDDLE_NAME_N_PRESENT_STR,
        help="CSV list of probabilities that a randomly selected person has a "
        "certain number of middle names. The first number is P(has a "
        "first middle name). The second number is P(has a second middle "
        "name | has a first middle name), and so on. The last number "
        "present will be re-used ad infinitum if someone has more names.",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DOB
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    priors_group.add_argument(
        f"--{Switches.BIRTH_YEAR_PSEUDO_RANGE}",
        type=float,
        default=FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
        help=f"Birth year pseudo-range. The sole purpose is to calculate the "
        f"probability of two random people sharing a DOB, which is taken "
        f"as 1/({DAYS_PER_YEAR} * b). This option is b.",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Sex/gender
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    priors_group.add_argument(
        f"--{Switches.P_NOT_MALE_OR_FEMALE}",
        type=float,
        default=FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
        help="Probability that a person in the population has gender 'X'.",
    )
    priors_group.add_argument(
        f"--{Switches.P_FEMALE_GIVEN_MALE_OR_FEMALE}",
        type=float,
        default=FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE,
        help="Probability that a person in the population is female, given "
        "that they are either male or female.",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Postcodes
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    affects_postcode_cache = (
        "[Information saved in the postcode cache. If you change this, delete "
        "your postcode cache.]"
    )
    # noinspection PyUnresolvedReferences
    priors_group.add_argument(
        f"--{Switches.POSTCODE_CACHE_FILENAME}",
        type=str,
        default=FuzzyDefaults.POSTCODE_CACHE_FILENAME,
        help="File in which to store cached postcodes (to speed loading).",
    )
    priors_group.add_argument(
        f"--{Switches.POSTCODE_CSV_FILENAME}",
        type=str,
        default=FuzzyDefaults.POSTCODES_CSV,
        help="CSV file of postcode geography from UK Census/ONS data. A ZIP "
        f"file is also acceptable. {affects_postcode_cache}",
    )
    priors_group.add_argument(
        f"--{Switches.MEAN_OA_POPULATION}",
        type=float,
        default=FuzzyDefaults.MEAN_OA_POPULATION,
        help="Mean population of a UK Census Output Area, from which we "
        "estimate the population of postcode-based units. "
        f"{affects_postcode_cache}",
    )
    priors_group.add_argument(
        f"--{Switches.P_UNKNOWN_OR_PSEUDO_POSTCODE}",
        type=float,
        default=FuzzyDefaults.P_UNKNOWN_OR_PSEUDO_POSTCODE,
        help="Proportion of the (UK) population expected to be assigned a "
        "'pseudo-postcode' (e.g. ZZ99 3VZ, no fixed abode; ZZ99 3CZ, "
        "England/UK not otherwise specified) or to have a postcode not known "
        "to the postcode geography database.",
    )


def add_error_probabilities(parser: argparse.ArgumentParser) -> None:
    """
    Adds a subparser for error probabilities.
    """
    error_p_group = parser.add_argument_group("error probabilities")
    error_p_group.add_argument(
        f"--{Switches.P_MINOR_FORENAME_ERROR}",
        type=float,
        default=FuzzyDefaults.P_MINOR_FORENAME_ERROR,
        help="Assumed probability that a forename has an error in that means "
        "it fails a full match but satisfies a partial (metaphone) match.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_PROBAND_MIDDLE_NAME_MISSING}",
        type=float,
        default=FuzzyDefaults.P_PROBAND_MIDDLE_NAME_MISSING,
        help="Probability that a middle name, present in the sample, is "
        "missing from the proband.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_SAMPLE_MIDDLE_NAME_MISSING}",
        type=float,
        default=FuzzyDefaults.P_SAMPLE_MIDDLE_NAME_MISSING,
        help="Probability that a middle name, present in the proband, is "
        "missing from the sample.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_MINOR_SURNAME_ERROR}",
        type=float,
        default=FuzzyDefaults.P_MINOR_SURNAME_ERROR,
        help="Assumed probability that a surname has an error in that means "
        "it fails a full match but satisfies a partial (metaphone) match.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_DOB_ERROR}",
        type=float,
        default=FuzzyDefaults.P_DOB_ERROR,
        help="Assumed probability (p_e) that a DOB is wrong in some way, "
        "leading to a proband/candidate partial match or mismatch.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR}",
        type=float,
        default=FuzzyDefaults.P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR,
        help="Given that a DOB is wrong, what is the probability that the "
        "error leads to a partial match, in which only one component (year, "
        "month, or day) is wrong? (This is p_ep / p_e.) NOTE: Empirical data "
        "suggests this is about 0.933, but we suggest setting it to 1, as "
        "anything below 1 sacrifices an opportunity for enormous "
        "computational efficiency -- <1 will run much slower.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_GENDER_ERROR}",
        type=float,
        default=FuzzyDefaults.P_GENDER_ERROR,
        help="Assumed probability (p_e) that a gender is wrong, leading to a "
        "proband/candidate mismatch.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_MINOR_POSTCODE_ERROR}",
        type=float,
        default=FuzzyDefaults.P_MINOR_POSTCODE_ERROR,
        help="Assumed probability (p_ep) that a postcode has an error that "
        "means it fails a full (postcode unit) match but satisfies a partial "
        "(postcode sector) match.",
    )


def add_matching_rules(parser: argparse.ArgumentParser) -> None:
    """
    Adds a  subparser for matching rules.
    """
    match_rule_group = parser.add_argument_group("matching rules")
    match_rule_group.add_argument(
        f"--{Switches.MIN_LOG_ODDS_FOR_MATCH}",
        type=float,
        default=FuzzyDefaults.MIN_LOG_ODDS_FOR_MATCH,
        help=f"Minimum natural log (ln) odds of two people being the same, "
        f"before a match will be considered. Referred to as theta (θ) in the "
        f"validation paper. (Default is equivalent to "
        f"p = {FuzzyDefaults.MIN_P_FOR_MATCH}.)",
    )
    match_rule_group.add_argument(
        f"--{Switches.EXCEEDS_NEXT_BEST_LOG_ODDS}",
        type=float,
        default=FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS,
        help="Minimum log (ln) odds by which a best match must exceed the "
        "next-best match to be considered a unique match. Referred to as "
        "delta (δ) in the validation paper.",
    )


def add_comparison_options(
    parser: argparse.ArgumentParser,
    proband_is_hashed: bool = True,
    sample_is_hashed: bool = True,
) -> None:
    """
    Adds a subparser for comparisons.
    """
    proband_fmt_help = (
        Person.HASHED_JSONLINES_FORMAT_HELP
        if proband_is_hashed
        else Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    sample_fmt_help = (
        Person.HASHED_JSONLINES_FORMAT_HELP
        if sample_is_hashed
        else Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    comparison_group = parser.add_argument_group("comparison options")
    comparison_group.add_argument(
        "--probands",
        type=str,
        required=True,
        help="Input filename for probands data. " + proband_fmt_help,
    )
    comparison_group.add_argument(
        "--sample",
        type=str,
        required=True,
        help="Input filename for sample data. " + sample_fmt_help,
    )
    comparison_group.add_argument(
        "--sample_cache",
        type=str,
        default=None,
        # The cache might contain sensitive information; don't offer it by
        # default.
        help="File in which to store cached sample info (to speed loading)",
    )
    comparison_group.add_argument(
        f"--{Switches.OUTPUT}",
        type=str,
        required=True,
        help="Output CSV file for proband/sample comparison.",
    )
    comparison_group.add_argument(
        f"--{Switches.EXTRA_VALIDATION_OUTPUT}",
        action="store_true",
        help="Add extra output for validation purposes.",
    )
    comparison_group.add_argument(
        f"--{Switches.N_WORKERS}",
        type=int,
        default=FuzzyDefaults.N_PROCESSES,
        help="Number of processes to use in parallel. Defaults to 1 (Windows) "
        "or the number of CPUs on your system (other operating systems).",
    )
    comparison_group.add_argument(
        "--max_chunksize",
        type=int,
        default=FuzzyDefaults.MAX_CHUNKSIZE,
        help="Maximum chunk size (number of probands to pass to a "
        "subprocess each time).",
    )
    comparison_group.add_argument(
        "--min_probands_for_parallel",
        type=int,
        default=FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
        help="Minimum number of probands for which we will bother to use "
        "parallel processing.",
    )
    comparison_group.add_argument(
        "--profile",
        action="store_true",
        help="Profile the code (for development only).",
    )


def get_cfg_from_args(
    args: argparse.Namespace,
    require_hasher: bool,
    require_main_config: bool,
    require_error: bool,
    require_matching: bool,
) -> MatchConfig:
    """
    Return a MatchConfig object from our standard arguments.
    Uses defaults where not specified.
    """

    def g(attrname: str, default: Any, required: bool) -> Any:
        try:
            return getattr(args, attrname)
        except AttributeError:
            if required:
                raise AttributeError(f"Missing config setting: {attrname}")
            log.debug(f"Using default {attrname} = {default!r}")
            return default

    return MatchConfig(
        hash_key=g(Switches.KEY, FuzzyDefaults.HASH_KEY, require_hasher),
        hash_method=g(
            Switches.HASH_METHOD, FuzzyDefaults.HASH_METHOD, require_hasher
        ),
        rounding_sf=g(
            Switches.ROUNDING_SF, FuzzyDefaults.ROUNDING_SF, require_hasher
        ),
        local_id_hash_key=g(Switches.LOCAL_ID_HASH_KEY, None, require_hasher),
        population_size=g(
            Switches.POPULATION_SIZE,
            FuzzyDefaults.POPULATION_SIZE,
            require_main_config,
        ),
        forename_cache_filename=g(
            Switches.FORENAME_CACHE_FILENAME,
            FuzzyDefaults.FORENAME_CACHE_FILENAME,
            require_main_config,
        ),
        forename_sex_csv_filename=g(
            Switches.FORENAME_SEX_FREQ_CSV,
            FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
            require_main_config,
        ),
        surname_cache_filename=g(
            Switches.SURNAME_CACHE_FILENAME,
            FuzzyDefaults.SURNAME_CACHE_FILENAME,
            require_main_config,
        ),
        surname_csv_filename=g(
            Switches.SURNAME_FREQ_CSV,
            FuzzyDefaults.SURNAME_FREQ_CSV,
            require_main_config,
        ),
        min_name_frequency=g(
            Switches.MIN_NAME_FREQUENCY,
            FuzzyDefaults.NAME_MIN_FREQ,
            require_main_config,
        ),
        p_middle_name_n_present=[
            float(x)
            for x in g(
                Switches.P_MIDDLE_NAME_N_PRESENT,
                FuzzyDefaults.P_MIDDLE_NAME_N_PRESENT_STR,
                require_main_config,
            ).split(",")
        ],
        birth_year_pseudo_range=g(
            Switches.BIRTH_YEAR_PSEUDO_RANGE,
            FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
            require_main_config,
        ),
        p_not_male_or_female=g(
            Switches.P_NOT_MALE_OR_FEMALE,
            FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
            require_main_config,
        ),
        p_female_given_male_or_female=g(
            Switches.P_FEMALE_GIVEN_MALE_OR_FEMALE,
            FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE,
            require_main_config,
        ),
        postcode_cache_filename=g(
            Switches.POSTCODE_CACHE_FILENAME,
            FuzzyDefaults.POSTCODE_CACHE_FILENAME,
            require_main_config,
        ),
        postcode_csv_filename=g(
            Switches.POSTCODE_CSV_FILENAME,
            FuzzyDefaults.POSTCODE_CACHE_FILENAME,
            require_main_config,
        ),
        mean_oa_population=g(
            Switches.MEAN_OA_POPULATION,
            FuzzyDefaults.MEAN_OA_POPULATION,
            require_main_config,
        ),
        p_unknown_or_pseudo_postcode=g(
            Switches.P_UNKNOWN_OR_PSEUDO_POSTCODE,
            FuzzyDefaults.P_UNKNOWN_OR_PSEUDO_POSTCODE,
            require_main_config,
        ),
        p_minor_forename_error=g(
            Switches.P_MINOR_FORENAME_ERROR,
            FuzzyDefaults.P_MINOR_FORENAME_ERROR,
            require_error,
        ),
        p_minor_surname_error=g(
            Switches.P_MINOR_SURNAME_ERROR,
            FuzzyDefaults.P_MINOR_SURNAME_ERROR,
            require_error,
        ),
        p_proband_middle_name_missing=g(
            Switches.P_PROBAND_MIDDLE_NAME_MISSING,
            FuzzyDefaults.P_PROBAND_MIDDLE_NAME_MISSING,
            require_error,
        ),
        p_sample_middle_name_missing=g(
            Switches.P_SAMPLE_MIDDLE_NAME_MISSING,
            FuzzyDefaults.P_SAMPLE_MIDDLE_NAME_MISSING,
            require_error,
        ),
        p_dob_error=g(
            Switches.P_DOB_ERROR,
            FuzzyDefaults.P_DOB_ERROR,
            require_error,
        ),
        p_dob_single_component_error_if_error=g(
            Switches.P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR,
            FuzzyDefaults.P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR,
            require_error,
        ),
        p_gender_error=g(
            Switches.P_GENDER_ERROR,
            FuzzyDefaults.P_GENDER_ERROR,
            require_error,
        ),
        p_minor_postcode_error=g(
            Switches.P_MINOR_POSTCODE_ERROR,
            FuzzyDefaults.P_MINOR_POSTCODE_ERROR,
            require_error,
        ),
        min_log_odds_for_match=g(
            Switches.MIN_LOG_ODDS_FOR_MATCH,
            FuzzyDefaults.MIN_LOG_ODDS_FOR_MATCH,
            require_matching,
        ),
        exceeds_next_best_log_odds=g(
            Switches.EXCEEDS_NEXT_BEST_LOG_ODDS,
            FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS,
            require_matching,
        ),
        verbose=args.verbose,  # always required
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    """
    Command-line entry point.

    Returns:
        program exit status code
    """

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Argument parser
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Using parents=[] makes the "parent" options appear first, which we often
    # don't want.

    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Identity matching via hashed fuzzy identifiers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = add_subparsers(parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # hash command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    hash_parser = subparsers.add_parser(
        Commands.HASH,
        help="STEP 1 OF DE-IDENTIFIED LINKAGE. "
        "Hash an identifiable CSV file into an encrypted one. ",
        description="""
Takes an identifiable list of people (with name, DOB, and postcode information)
and creates a hashed, de-identified equivalent. Order is preserved.

The local ID (presumed not to be a direct identifier) is preserved exactly,
unless you explicitly elect to hash it.

Optionally, the "other" information (you can choose, e.g. attaching a direct
identifier) is preserved, but you have to ask for that explicitly; that is
normally for testing.""",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    hash_parser.add_argument(
        f"--{Switches.INPUT}",
        type=str,
        required=True,
        help="Filename for input (plaintext) data. "
        + Person.PLAINTEXT_CSV_FORMAT_HELP,
    )
    hash_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file for hashed version. "
        + Person.HASHED_JSONLINES_FORMAT_HELP,
    )
    hash_parser.add_argument(
        "--without_frequencies",
        action="store_true",
        help="Do not include frequency information. This makes the result "
        "suitable for use as a sample file, but not a proband file.",
    )
    hash_parser.add_argument(
        f"--{Switches.INCLUDE_OTHER_INFO}",
        action="store_true",
        help=(
            f"Include the (potentially identifying) "
            f"{SimplePerson.PersonKey.OTHER_INFO!r} data? "
            "Usually False; may be set to True for validation."
        ),
    )
    add_hasher_options(hash_parser)
    add_config_options(hash_parser)
    add_basic_options(hash_parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # compare_plaintext command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    compare_plaintext_parser = subparsers.add_parser(
        Commands.COMPARE_PLAINTEXT,
        help="IDENTIFIABLE LINKAGE COMMAND. "
        "Compare a list of probands against a sample (both in "
        "plaintext). ",
        description=HELP_COMPARISON,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    add_comparison_options(
        compare_plaintext_parser,
        proband_is_hashed=False,
        sample_is_hashed=False,
    )
    add_matching_rules(compare_plaintext_parser)
    add_error_probabilities(compare_plaintext_parser)
    add_config_options(compare_plaintext_parser)
    add_basic_options(compare_plaintext_parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # compare_hashed_to_hashed command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    compare_h2h_parser = subparsers.add_parser(
        Commands.COMPARE_HASHED_TO_HASHED,
        help=(
            "STEP 2 OF DE-IDENTIFIED LINKAGE (for when you have de-identified "
            "both sides in advance). "
            "Compare a list of probands against a sample (both hashed)."
        ),
        description=HELP_COMPARISON,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    add_comparison_options(
        compare_h2h_parser, proband_is_hashed=True, sample_is_hashed=True
    )
    add_matching_rules(compare_h2h_parser)
    add_error_probabilities(compare_h2h_parser)
    add_config_options(compare_h2h_parser)
    add_basic_options(compare_h2h_parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # compare_hashed_to_plaintext command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    compare_h2p_parser = subparsers.add_parser(
        Commands.COMPARE_HASHED_TO_PLAINTEXT,
        help="STEP 2 OF DE-IDENTIFIED LINKAGE (for when you have received "
        "de-identified data and you want to link to your identifiable "
        "data, producing a de-identified result). "
        "Compare a list of probands (hashed) against a sample "
        "(plaintext). Hashes the sample on the fly.",
        description=HELP_COMPARISON,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    add_comparison_options(
        compare_h2p_parser, proband_is_hashed=True, sample_is_hashed=False
    )
    add_hasher_options(compare_h2p_parser)
    add_matching_rules(compare_h2p_parser)
    add_error_probabilities(compare_h2p_parser)
    add_config_options(compare_h2p_parser)
    add_basic_options(compare_h2p_parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Debugging commands
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    demo_sample_parser = subparsers.add_parser(
        Commands.PRINT_DEMO_SAMPLE,
        help="Print a demo sample .CSV file.",
    )
    add_basic_options(demo_sample_parser)

    show_metaphone_parser = subparsers.add_parser(
        Commands.SHOW_METAPHONE,
        help="Show metaphones of words",
    )
    show_metaphone_parser.add_argument(
        "words", nargs="+", help="Words to check"
    )
    add_basic_options(show_metaphone_parser)

    show_forename_freq_parser = subparsers.add_parser(
        Commands.SHOW_FORENAME_FREQ,
        help="Show frequencies of forenames",
    )
    show_forename_freq_parser.add_argument(
        "forenames", nargs="+", help="Forenames to check"
    )
    add_config_options(show_forename_freq_parser)
    add_basic_options(show_forename_freq_parser)

    show_forename_metaphone_freq_parser = subparsers.add_parser(
        Commands.SHOW_FORENAME_METAPHONE_FREQ,
        help="Show frequencies of forename metaphones",
    )
    show_forename_metaphone_freq_parser.add_argument(
        "metaphones", nargs="+", help="Forenames to check"
    )
    add_config_options(show_forename_metaphone_freq_parser)
    add_basic_options(show_forename_metaphone_freq_parser)

    show_surname_freq_parser = subparsers.add_parser(
        Commands.SHOW_SURNAME_FREQ,
        help="Show frequencies of surnames",
    )
    show_surname_freq_parser.add_argument(
        "surnames", nargs="+", help="surnames to check"
    )
    add_config_options(show_surname_freq_parser)
    add_basic_options(show_surname_freq_parser)

    show_surname_metaphone_freq_parser = subparsers.add_parser(
        Commands.SHOW_SURNAME_METAPHONE_FREQ,
        help="Show frequencies of surname metaphones",
    )
    show_surname_metaphone_freq_parser.add_argument(
        "metaphones", nargs="+", help="surnames to check"
    )
    add_config_options(show_surname_metaphone_freq_parser)
    add_basic_options(show_surname_metaphone_freq_parser)

    show_dob_freq_parser = subparsers.add_parser(
        Commands.SHOW_DOB_FREQ,
        help="Show the frequency of any DOB",
    )
    add_config_options(show_dob_freq_parser)
    add_basic_options(show_dob_freq_parser)

    show_postcode_freq_parser = subparsers.add_parser(
        Commands.SHOW_POSTCODE_FREQ,
        help="Show the frequency of any postcode",
    )
    show_postcode_freq_parser.add_argument(
        "postcodes", nargs="+", help="postcodes to check"
    )
    add_config_options(show_postcode_freq_parser)
    add_basic_options(show_postcode_freq_parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Parse arguments and set up
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO,
        with_process_id=True,
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Run a command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    log.info(f"Command: {args.command}")

    if args.command == Commands.PRINT_DEMO_SAMPLE:
        print(get_demo_csv())
        return EXIT_SUCCESS

    elif args.command == Commands.HASH:
        cfg = get_cfg_from_args(
            args,
            require_hasher=True,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        warn_or_fail_if_default_key(args)
        log.info(f"Hashing identity file: {args.input}")
        hash_identity_file(
            cfg=cfg,
            input_filename=args.input,
            output_filename=args.output,
            include_frequencies=not args.without_frequencies,
            include_other_info=args.include_other_info,
        )
        log.info(f"... finished; written to {args.output}")

    elif args.command == Commands.COMPARE_PLAINTEXT:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=True,
            require_matching=True,
        )
        log.info(
            f"Comparing files:\n"
            f"- plaintext probands: {args.probands}\n"
            f"- plaintext sample: {args.sample}"
        )
        compare_probands_to_sample_from_files(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
            min_probands_for_parallel=args.min_probands_for_parallel,
            n_workers=args.n_workers,
            output_filename=args.output,
            probands_filename=args.probands,
            probands_plaintext=True,
            profile=args.profile,
            sample_cache_filename=args.sample_cache,
            sample_filename=args.sample,
            sample_plaintext=True,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == Commands.COMPARE_HASHED_TO_HASHED:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=True,
            require_matching=True,
        )
        log.info(
            f"Comparing files:\n"
            f"- hashed probands: {args.probands}\n"
            f"- hashed sample: {args.sample}"
        )
        compare_probands_to_sample_from_files(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
            min_probands_for_parallel=args.min_probands_for_parallel,
            n_workers=args.n_workers,
            output_filename=args.output,
            probands_filename=args.probands,
            probands_plaintext=False,
            profile=args.profile,
            sample_filename=args.sample,
            sample_plaintext=False,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == Commands.COMPARE_HASHED_TO_PLAINTEXT:
        cfg = get_cfg_from_args(
            args,
            require_hasher=True,
            require_main_config=True,
            require_error=True,
            require_matching=True,
        )
        warn_or_fail_if_default_key(args)
        log.info(
            f"Comparing files:\n"
            f"- hashed probands: {args.probands}\n"
            f"- plaintext sample: {args.sample}"
        )
        compare_probands_to_sample_from_files(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
            min_probands_for_parallel=args.min_probands_for_parallel,
            n_workers=args.n_workers,
            output_filename=args.output,
            probands_filename=args.probands,
            probands_plaintext=False,
            profile=args.profile,
            sample_cache_filename=args.sample_cache,
            sample_filename=args.sample,
            sample_plaintext=True,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == Commands.SHOW_METAPHONE:
        for word in args.words:
            log.info(f"Metaphone for {word!r}: {get_metaphone(word)}")

    elif args.command == Commands.SHOW_FORENAME_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        for forename in args.forenames:
            log.info(
                f"Forename {forename!r}: "
                f"F {cfg.forename_freq(forename, GENDER_FEMALE)}, "
                f"M {cfg.forename_freq(forename, GENDER_MALE)}, "
                f"overall {cfg.forename_freq(forename, '')}"
            )

    elif args.command == Commands.SHOW_FORENAME_METAPHONE_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        for metaphone in args.metaphones:
            log.info(
                f"Forename metaphone {metaphone!r}: "
                f"F {cfg.forename_metaphone_freq(metaphone, GENDER_FEMALE)}, "  # noqa
                f"M {cfg.forename_metaphone_freq(metaphone, GENDER_MALE)}, "  # noqa
                f"overall {cfg.forename_metaphone_freq(metaphone, '')}"
            )

    elif args.command == Commands.SHOW_SURNAME_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        for surname in args.surnames:
            log.info(f"Surname {surname!r}: {cfg.surname_freq(surname)}")

    elif args.command == Commands.SHOW_SURNAME_METAPHONE_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        for metaphone in args.metaphones:
            log.info(
                f"Surname metaphone {metaphone!r}: "
                f"{cfg.surname_metaphone_freq(metaphone)}"
            )

    elif args.command == Commands.SHOW_DOB_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        log.info(f"DOB frequency: {cfg.p_two_people_share_dob_ymd}")

    elif args.command == Commands.SHOW_POSTCODE_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        for postcode in args.postcodes:
            postcode = standardize_postcode(postcode)
            sector = get_postcode_sector(postcode)
            unit_freq, sector_freq = cfg.postcode_unit_sector_freq(
                postcode, prestandardized=True
            )
            log.info(
                f"Postcode {postcode!r}: {unit_freq} / "
                f"sector {sector!r}: {sector_freq}"
            )

    else:
        # Shouldn't get here.
        log.error(f"Unknown command: {args.command}")
        return EXIT_FAILURE

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
