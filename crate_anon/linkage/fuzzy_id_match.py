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

from concurrent.futures import ProcessPoolExecutor, wait
import csv
from io import StringIO
import json
import logging
from math import ceil

import sys
import time
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
    ShowAllSubparserHelpAction,
)
from cardinal_pythonlib.datetimefunc import coerce_to_pendulum_date
from cardinal_pythonlib.hash import HashMethods
from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.maths_py import round_sf
from cardinal_pythonlib.probability import probability_from_log_odds
from cardinal_pythonlib.profile import do_cprofile

from crate_anon.common.constants import EXIT_FAILURE, EXIT_SUCCESS
from crate_anon.linkage.helpers import (
    get_metaphone,
    get_postcode_sector,
    optional_int,
    standardize_name,
    standardize_postcode,
)
from crate_anon.linkage.identifiers import TemporalIDHolder
from crate_anon.linkage.constants import (
    DAYS_PER_YEAR,
    FuzzyDefaults,
    GENDER_FEMALE,
    GENDER_MALE,
    GENDER_MISSING,
    GENDER_OTHER,
    Switches,
)
from crate_anon.linkage.matchconfig import MatchConfig, mk_dummy_match_config
from crate_anon.linkage.matchresult import MatchResult
from crate_anon.linkage.people import DuplicateIDError, People
from crate_anon.linkage.person import Person
from crate_anon.linkage.person_io import (
    gen_person_from_file,
    PersonWriter,
    write_people,
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
    SHOW_FORENAME_F2C_FREQ = "show_forename_f2c_freq"
    SHOW_SURNAME_FREQ = "show_surname_freq"
    SHOW_SURNAME_METAPHONE_FREQ = "show_surname_metaphone_freq"
    SHOW_SURNAME_F2C_FREQ = "show_surname_f2c_freq"
    SHOW_DOB_FREQ = "show_dob_freq"
    SHOW_POSTCODE_FREQ = "show_postcode_freq"


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

PARALLEL PROCESSING

This is slow:

    executor = ProcessPoolExecutor(max_workers=max_workers)
    for result in executor.map(sample.get_unique_match_detailed,
                               probands.people,
                               cycle([cfg])):
        process_result(result)

This doesn't work as you can't pickle a local function:

    from multiprocessing import Pool
    chunksize = max(1, min(n_probands // n_workers, max_chunksize))
    # ... chunksize must be >= 1
    # ... e.g. max_chunksize = 1000
    with Pool(processes=n_workers) as pool:
        for result in pool.imap_unordered(  # one arg per call
                make_result,  # local function
                probands.people,
                chunksize=chunksize):
            process_result(result)

This is fine, though it only collects results at the end:

    with Pool(processes=n_workers) as pool:
        for result in pool.starmap(  # many args
                sample.get_unique_match_detailed,
                zip(probands.people, cycle([cfg])),
                chunksize=chunksize):
            process_result(result)

This is slower than serial for 1k-to-1k matching under Linux (e.g. 19.88 with 8
workers, chunksize 125, versus 2.76s serial), and about a *hundredfold* slower
than serial for our CPFT databases under Windows -- perhaps because under
Windows, Python tries to "fake" a fork() call
(https://stackoverflow.com/questions/57535979/):

    with Pool(processes=n_workers) as pool:
        for result in pool.imap_unordered(  # one arg per call
            sample.get_unique_match_detailed,
            probands.people,
            chunksize=chunksize,
        ):
            process_result(result)

This is about the same (parallel/serial) for 1k-to-1k. For 10k-to-10k, about
379s serial, and 488s parallel (8 workers):

    from concurrent.futures import as_completed, ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = [
            executor.submit(sample.get_unique_match_detailed, proband)
            for proband in probands.people
        ]
        for future in as_completed(futures):
            process_result(future.result())

We likely have these tensions:

- For multiprocessing, fork() is fairly fast under Linux but nonexistent under
  Windows. The process creation (including variable duplication) under Windows
  is slow, so this is limiting.

- Multithreading would make tasks start fast, and this would be the method of
  choice under C++, but then they hit the Python GIL (which is why Python
  generally recommends multiprocessing for CPU-bound and multithreading for
  IO-bound operations; e.g. https://stackoverflow.com/questions/60513406/).

Anyway, performance is too good to bother rewriting in C++.

However, the other thing we could do is to split our probands into equal
groups, and launch n_workers processes, not len(probands) processes. For
1k-to-1k, slower (2.6s serial, 20.99s parallel). For 10k-to-10k, faster (338.8s
serial, 105.5s parallel). With this design, we may as well retain the original
order, so rather than "for future in as_completed(futures)" we do
"wait(futures)" then "for future in futures". So we'll do that.

(Still slow under Windows!)

OTHER SPEED CONSIDERATIONS

This is an O(n^2) algorithm, in that its time grows linearly with the number of
probands to check, and with the number of sample members to check against --
though on average at 1/(365*b) = 1/32850 the gradient for the latter, with
"exact DOB" prefiltering (a bit steeper now we allow DOB partial matches).

Other things that helped a lot:

- Simplifying Bayesian comparison structures, and pregenerating them/storing
  them as part of Identifier objects (because individual Person objects are
  compared against many others).

- numba.jit() for low-level maths.

"""


def process_proband_chunk(
    probands: List[Person],
    sample: People,
    worker_num: int,
    report_every: int = FuzzyDefaults.REPORT_EVERY,
) -> List[MatchResult]:
    """
    Used for multiprocessing, where a single process handles lots of probands,
    not one proband per process.
    """
    results = []  # type: List[MatchResult]
    n_probands = len(probands)
    for i, proband in enumerate(probands, start=1):
        if i % report_every == 0:
            log.info(f"Worker {worker_num}: processing {i}/{n_probands}")
        results.append(sample.get_unique_match_detailed(proband))
    return results


def compare_probands_to_sample(
    cfg: MatchConfig,
    probands: People,
    sample: People,
    output_filename: str,
) -> None:
    r"""
    Compares each proband to the sample. Writes to an output file. Order is
    retained.

    See notes above (in source code) re parallel processing.

    Args:
        cfg:
            The main :class:`MatchConfig` object.
        probands:
            :class:`People`
        sample:
            :class:`People`
        output_filename:
            Output CSV filename.
    """
    c = ComparisonOutputColnames
    extra_validation_output = cfg.extra_validation_output
    report_every = cfg.report_every
    n_workers = cfg.n_workers

    def process_result(r: MatchResult) -> None:
        # Uses rownum/c/writer from outer scope.
        nonlocal rownum
        rownum += 1
        if rownum % report_every == 0:
            log.info(f"Writing result {rownum}/{n_probands}")
        matched = r.matched
        rowdata = {
            c.PROBAND_LOCAL_ID: r.proband.local_id,
            c.MATCHED: int(matched),
            c.LOG_ODDS_MATCH: r.best_log_odds,
            c.P_MATCH: probability_from_log_odds(r.best_log_odds),
            c.SAMPLE_MATCH_LOCAL_ID: r.winner.local_id if matched else None,
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
        f"{n_probands} probands, and {n_sample} candidates in the sample."
    )

    # Off we go.
    parallel = n_workers > 1 and n_probands >= cfg.min_probands_for_parallel
    colnames = ComparisonOutputColnames.COMPARISON_OUTPUT_COLNAMES
    if extra_validation_output:
        colnames += ComparisonOutputColnames.COMPARISON_EXTRA_COLNAMES
    rownum = 0
    time_start = time.time()
    with open(output_filename, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=colnames)
        writer.writeheader()

        if parallel:
            log.info(f"Using parallel processing: {n_workers} workers")
            people_per_chunk = ceil(n_probands / n_workers)
            assert people_per_chunk * n_workers >= n_probands
            proband_chunks = chunks(probands.people, people_per_chunk)
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                log.info("Submitting parallel jobs...")
                futures = [
                    executor.submit(
                        process_proband_chunk,
                        probands=proband_chunk,
                        sample=sample,
                        worker_num=worker_num,
                        report_every=report_every,
                    )
                    for worker_num, proband_chunk in enumerate(
                        proband_chunks, start=1
                    )
                ]
                log.info("Waiting for workers...")
                wait(futures)
                log.info("Workers done; writing output...")
                for future in futures:
                    for result in future.result():
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
    profile: bool = False,
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
        profile:
            Profile the code?
    """
    # Sample
    log.info("Loading (or caching) sample data")
    if sample_plaintext:
        if sample_cache_filename:
            log.info(f"Using sample cache: {sample_cache_filename}")
            try:
                sample = read_people(
                    cfg, sample_cache_filename, plaintext=True, jsonl=True
                )
            except FileNotFoundError:
                sample = read_people(
                    cfg, sample_filename, plaintext=True, jsonl=False
                )
                write_people(
                    sample,
                    filename=sample_cache_filename,
                    plaintext=True,
                    plaintext_jsonl=True,
                    include_frequencies=True,
                    include_other_info=False,
                )
        else:
            # You may want to avoid a cache, for security.
            log.info("No sample cache in use.")
            sample = read_people(
                cfg, sample_filename, plaintext=True, jsonl=False
            )
    else:
        sample = read_people(cfg, sample_filename, plaintext=False, jsonl=True)

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
        log.warning("Unusual: comparing plaintext probands to hashed sample.")
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
    )


# =============================================================================
# Loading people data
# =============================================================================


def read_people_alternate_groups(
    cfg: MatchConfig,
    filename: str,
    plaintext: bool = True,
    jsonl: Optional[bool] = None,
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
        gen_person_from_file(cfg, filename, plaintext=plaintext, jsonl=jsonl),
        start=2,
    ):
        try:
            if i % 2 == 0:
                a.add_person(person)
            else:
                b.add_person(person)
        except DuplicateIDError as exc:
            msg = f"{exc} at line {i} of {filename}"
            log.error(msg)
            raise DuplicateIDError(msg)
    return a, b


def read_people(
    cfg: MatchConfig,
    filename: str,
    plaintext: bool = True,
    jsonl: Optional[bool] = None,
) -> People:
    """
    Read a list of people from a CSV/JSONLines file.

    See :func:`read_people_2`, but this version doesn't offer the feature of
    splitting into two groups, and returns only a single :class:`People`
    object.
    """
    people = People(cfg=cfg)
    for i, person in enumerate(
        gen_person_from_file(cfg, filename, plaintext=plaintext, jsonl=jsonl),
        start=2,
    ):
        try:
            people.add_person(person)
        except DuplicateIDError as exc:
            msg = f"{exc} at line {i} of {filename}"
            log.error(msg)
            raise DuplicateIDError(msg)
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


def get_demo_people(cfg: MatchConfig = None) -> List[Person]:
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

    cfg = cfg or mk_dummy_match_config()

    return [
        Person(
            cfg=cfg,
            local_id="r0",
            other_info=mkother("0"),
            forenames=["Alice", "Zara"],
            surnames=["Smith"],
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
        ),
        Person(
            cfg=cfg,
            local_id="r1",
            other_info=mkother("1"),
            forenames=["Bob", "Yorick"],
            surnames=["Jones"],
            dob="1932-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 3EB")],
        ),
        Person(
            cfg=cfg,
            local_id="r2",
            other_info=mkother("2"),
            forenames=["Celia", "Xena"],
            surnames=["Wright"],
            dob="1933-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 1TP")],
        ),
        Person(
            cfg=cfg,
            local_id="r3",
            other_info=mkother("3"),
            forenames=["David", "William", "Wallace"],
            surnames=["Cartwright"],
            dob="1934-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 8PH"), p("CB2 1TP")],
        ),
        Person(
            cfg=cfg,
            local_id="r4",
            other_info=mkother("4"),
            forenames=["Emily", "Violet"],
            surnames=["Fisher"],
            dob="1935-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB3 9DF")],
        ),
        Person(
            cfg=cfg,
            local_id="r5",
            other_info=mkother("5"),
            forenames=["Frank", "Umberto"],
            surnames=["Williams"],
            dob="1936-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 1TQ")],
        ),
        Person(
            cfg=cfg,
            local_id="r6",
            other_info=mkother("6"),
            forenames=["Greta", "Tilly"],
            surnames=["Taylor"],
            dob="1937-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 1DQ")],
        ),
        Person(
            cfg=cfg,
            local_id="r7",
            other_info=mkother("7"),
            forenames=["Harry", "Samuel"],
            surnames=["Davies"],
            dob="1938-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB3 9ET")],
        ),
        Person(
            cfg=cfg,
            local_id="r8",
            other_info=mkother("8"),
            forenames=["Iris", "Ruth"],
            surnames=["Evans", "Jones"],
            dob="1939-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB3 0DG")],
        ),
        Person(
            cfg=cfg,
            local_id="r9",
            other_info=mkother("9"),
            forenames=["James", "Quentin"],
            surnames=[
                TemporalIDHolder(
                    identifier="Thomas",
                    start_date=None,
                    end_date=d("1962-06-21"),
                ),
                TemporalIDHolder(
                    identifier="Richardson",
                    start_date=d("1962-06-22"),
                    end_date=None,
                ),
            ],
            dob="1940-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 0SZ")],
        ),
        Person(
            cfg=cfg,
            local_id="r10",
            other_info=mkother("10"),
            forenames=["Alice"],
            surnames=["Smith"],
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
        ),
        Person(
            cfg=cfg,
            local_id="r11",
            other_info=mkother("11"),
            forenames=["Alice"],
            surnames=["Abadilla"],  # much rarer than Smith
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
        ),
        Person(
            cfg=cfg,
            local_id="r12",
            other_info=mkother("12"),
            forenames=["Zara", "Alice"],
            surnames=["Smith"],
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
    write_people(people=people, file=output, plaintext=True)
    return output.getvalue()


# =============================================================================
# Command-line entry point
# =============================================================================

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

Proband order is retained in the output (even using parallel processing).
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
        help="Show help for all commands and exit.",
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
    arggroup.add_argument("--verbose", action="store_true", help="Be verbose.")


def add_hasher_options(parser: argparse.ArgumentParser) -> None:
    """
    Adds a subparser for hasher options.
    """
    hasher_group = parser.add_argument_group("Hasher (secrecy) options")
    hasher_group.add_argument(
        f"--{Switches.KEY}",
        type=str,
        default=FuzzyDefaults.HASH_KEY,
        help="Key (passphrase) for hasher.",
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
        help="Hash method.",
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
        "Frequency information for prior probabilities"
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
        help="File in which to store cached forename info (to speed loading).",
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
        help="File in which to store cached surname info (to speed loading).",
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
        f"--{Switches.ACCENT_TRANSLITERATIONS}",
        type=str,
        default=FuzzyDefaults.ACCENT_TRANSLITERATIONS_SLASH_CSV,
        help="CSV list of 'accented/plain' pairs, representing how accented "
        "characters may be transliterated (if they are not reproduced "
        "accurately and not simply mangled into ASCII like É→E). Only "
        "upper-case versions are required (anything supplied will be "
        "converted to upper case).",
    )
    priors_group.add_argument(
        f"--{Switches.NONSPECIFIC_NAME_COMPONENTS}",
        type=str,
        default=FuzzyDefaults.NONSPECIFIC_NAME_COMPONENTS_CSV,
        help="CSV list of name components that should not be used as "
        "alternatives in their own right, such as nobiliary particles.",
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
        f"as 1/({DAYS_PER_YEAR} * b), even for 29 Feb. This option is b.",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Sex/gender
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    priors_group.add_argument(
        f"--{Switches.P_NOT_MALE_OR_FEMALE}",
        type=float,
        default=FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
        help=f"Probability that a person in the population has gender "
        f"{GENDER_OTHER!r}.",
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
    error_p_group = parser.add_argument_group("Error probabilities")
    # gdh = gender dict help
    gdh = (
        f"(Comma-separated list of 'gender:p' values, where gender must "
        f"include {GENDER_FEMALE}, {GENDER_MALE} and can include "
        f"{GENDER_OTHER}, {GENDER_MISSING!r}.)"
    )

    error_p_group.add_argument(
        f"--{Switches.P_EP1_FORENAME}",
        type=str,
        default=FuzzyDefaults.P_EP1_FORENAME_CSV,
        help=f"Probability that a forename has an error such that it fails a "
        f"full match but satisfies a partial 1 (metaphone) match. {gdh}",
    )
    error_p_group.add_argument(
        f"--{Switches.P_EP2NP1_FORENAME}",
        type=str,
        default=FuzzyDefaults.P_EP2NP1_FORENAME_CSV,
        help=f"Probability that a forename has an error such that it fails a "
        f"full/partial 1 match but satisfies a partial 2 (first two "
        f"character) match. {gdh}",
    )
    error_p_group.add_argument(
        f"--{Switches.P_EN_FORENAME}",
        type=str,
        default=FuzzyDefaults.P_EN_FORENAME_CSV,
        help=f"Probability that a forename has an error such that it produces "
        f"no match at all. {gdh}",
    )
    error_p_group.add_argument(
        f"--{Switches.P_U_FORENAMES}",
        type=str,
        default=FuzzyDefaults.P_U_FORENAMES_CSV,
        help=f"Probability that a set of at least two forenames has an error "
        f"such that they become unordered (e.g. swapped/shuffled) with "
        f"respect to their counterpart. {gdh}",
    )

    error_p_group.add_argument(
        f"--{Switches.P_EP1_SURNAME}",
        type=str,
        default=FuzzyDefaults.P_EP1_SURNAME_CSV,
        help=f"Probability that a surname has an error such that it fails a "
        f"full match but satisfies a partial 1 (metaphone) match. {gdh}",
    )
    error_p_group.add_argument(
        f"--{Switches.P_EP2NP1_SURNAME}",
        type=str,
        default=FuzzyDefaults.P_EP2NP1_SURNAME_CSV,
        help=f"Probability that a surname has an error such that it fails a "
        f"full/partial 1 match but satisfies a partial 2 (first two "
        f"character) match. {gdh}",
    )
    error_p_group.add_argument(
        f"--{Switches.P_EN_SURNAME}",
        type=str,
        default=FuzzyDefaults.P_EN_SURNAME_CSV,
        help=f"Probability that a surname has an error such that it produces "
        f"no match at all. {gdh}",
    )

    error_p_group.add_argument(
        f"--{Switches.P_EP_DOB}",
        type=float,
        default=FuzzyDefaults.P_EP_DOB,
        help="Probability that a DOB is wrong in some way that causes a "
        "partial match (YM, MD, or YD) but not a full (YMD) match.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_EN_DOB}",
        type=float,
        default=FuzzyDefaults.P_EN_DOB,
        help=f"Probability that a DOB error leads to no match (neither full, "
        f"nor partial as defined above). Empirically, this is about "
        f"{round_sf(FuzzyDefaults.P_EN_DOB_TRUE, 3)}. However, we suggest "
        f"setting it to 0, as anything higher will run much slower.",
    )

    error_p_group.add_argument(
        f"--{Switches.P_E_GENDER}",
        type=float,
        default=FuzzyDefaults.P_E_GENDER,
        help="Assumed probability (p_e) that a gender is wrong, leading to a "
        "proband/candidate mismatch.",
    )

    error_p_group.add_argument(
        f"--{Switches.P_EP_POSTCODE}",
        type=float,
        default=FuzzyDefaults.P_EP_POSTCODE,
        help="Assumed probability (p_ep) that a proband/candidate postcode "
        "pair fails a full (postcode unit) match but satisfies a partial "
        "(postcode sector) match, through error or a move within a sector.",
    )
    error_p_group.add_argument(
        f"--{Switches.P_EN_POSTCODE}",
        type=float,
        default=FuzzyDefaults.P_EN_POSTCODE,
        help="Assumed probability (p_ep) that a proband/candidate postcode "
        "pair exhibits no match at all.",
    )


def add_matching_rules(parser: argparse.ArgumentParser) -> None:
    """
    Adds a  subparser for matching rules.
    """
    match_rule_group = parser.add_argument_group("Matching rules")
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
    match_rule_group.add_argument(
        f"--{Switches.PERFECT_ID_TRANSLATION}",
        type=str,
        help="Optional dictionary of the form {'nhsnum':'nhsnumber', "
        "'ni_num':'national_insurance'}, mapping the names of perfect "
        "(person-unique) identifiers as found in the proband data to their "
        "equivalents in the sample.",
    )

    control_group = parser.add_argument_group("Control options")
    control_group.add_argument(
        f"--{Switches.EXTRA_VALIDATION_OUTPUT}",
        action="store_true",
        help="Add extra output for validation purposes.",
    )
    control_group.add_argument(
        f"--{Switches.N_WORKERS}",
        type=int,
        default=FuzzyDefaults.N_PROCESSES,
        help="Number of processes to use in parallel. Defaults to 1 (Windows) "
        "or the number of CPUs on your system (other operating systems).",
    )
    control_group.add_argument(
        f"--{Switches.MIN_PROBANDS_FOR_PARALLEL}",
        type=int,
        default=FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
        help="Minimum number of probands for which we will bother to use "
        "parallel processing.",
    )
    control_group.add_argument(
        f"--{Switches.REPORT_EVERY}",
        type=int,
        default=FuzzyDefaults.REPORT_EVERY,
        help="Report progress every n probands.",
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
    comparison_group = parser.add_argument_group("Comparison options")
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
        help="JSONL file in which to store cached sample info (to speed "
        "loading)",
    )
    comparison_group.add_argument(
        f"--{Switches.OUTPUT}",
        type=str,
        required=True,
        help="Output CSV file for proband/sample comparison.",
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

    def getparam(attrname: str, default: Any, required: bool) -> Any:
        try:
            return getattr(args, attrname)
        except AttributeError:
            if required:
                raise AttributeError(f"Missing config setting: {attrname}")
            log.debug(f"Using default {attrname} = {default!r}")
            return default

    require_comparison = require_matching

    return MatchConfig(
        hash_key=getparam(
            Switches.KEY, FuzzyDefaults.HASH_KEY, require_hasher
        ),
        hash_method=getparam(
            Switches.HASH_METHOD, FuzzyDefaults.HASH_METHOD, require_hasher
        ),
        rounding_sf=getparam(
            Switches.ROUNDING_SF, FuzzyDefaults.ROUNDING_SF, require_hasher
        ),
        local_id_hash_key=getparam(
            Switches.LOCAL_ID_HASH_KEY, None, require_hasher
        ),
        population_size=getparam(
            Switches.POPULATION_SIZE,
            FuzzyDefaults.POPULATION_SIZE,
            require_main_config,
        ),
        forename_cache_filename=getparam(
            Switches.FORENAME_CACHE_FILENAME,
            FuzzyDefaults.FORENAME_CACHE_FILENAME,
            require_main_config,
        ),
        forename_sex_csv_filename=getparam(
            Switches.FORENAME_SEX_FREQ_CSV,
            FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
            require_main_config,
        ),
        surname_cache_filename=getparam(
            Switches.SURNAME_CACHE_FILENAME,
            FuzzyDefaults.SURNAME_CACHE_FILENAME,
            require_main_config,
        ),
        surname_csv_filename=getparam(
            Switches.SURNAME_FREQ_CSV,
            FuzzyDefaults.SURNAME_FREQ_CSV,
            require_main_config,
        ),
        min_name_frequency=getparam(
            Switches.MIN_NAME_FREQUENCY,
            FuzzyDefaults.NAME_MIN_FREQ,
            require_main_config,
        ),
        accent_transliterations_csv=getparam(
            Switches.ACCENT_TRANSLITERATIONS,
            FuzzyDefaults.ACCENT_TRANSLITERATIONS_SLASH_CSV,
            require_main_config,
        ),
        nonspecific_name_components_csv=getparam(
            Switches.NONSPECIFIC_NAME_COMPONENTS,
            FuzzyDefaults.NONSPECIFIC_NAME_COMPONENTS_CSV,
            require_main_config,
        ),
        birth_year_pseudo_range=getparam(
            Switches.BIRTH_YEAR_PSEUDO_RANGE,
            FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
            require_main_config,
        ),
        p_not_male_or_female=getparam(
            Switches.P_NOT_MALE_OR_FEMALE,
            FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
            require_main_config,
        ),
        p_female_given_male_or_female=getparam(
            Switches.P_FEMALE_GIVEN_MALE_OR_FEMALE,
            FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE,
            require_main_config,
        ),
        postcode_cache_filename=getparam(
            Switches.POSTCODE_CACHE_FILENAME,
            FuzzyDefaults.POSTCODE_CACHE_FILENAME,
            require_main_config,
        ),
        postcode_csv_filename=getparam(
            Switches.POSTCODE_CSV_FILENAME,
            FuzzyDefaults.POSTCODE_CACHE_FILENAME,
            require_main_config,
        ),
        mean_oa_population=getparam(
            Switches.MEAN_OA_POPULATION,
            FuzzyDefaults.MEAN_OA_POPULATION,
            require_main_config,
        ),
        p_unknown_or_pseudo_postcode=getparam(
            Switches.P_UNKNOWN_OR_PSEUDO_POSTCODE,
            FuzzyDefaults.P_UNKNOWN_OR_PSEUDO_POSTCODE,
            require_main_config,
        ),
        p_ep1_forename=getparam(
            Switches.P_EP1_FORENAME,
            FuzzyDefaults.P_EP1_FORENAME_CSV,
            require_error,
        ),
        p_ep2np1_forename=getparam(
            Switches.P_EP2NP1_FORENAME,
            FuzzyDefaults.P_EP2NP1_FORENAME_CSV,
            require_error,
        ),
        p_en_forename=getparam(
            Switches.P_EN_FORENAME,
            FuzzyDefaults.P_EN_FORENAME_CSV,
            require_error,
        ),
        p_u_forename=getparam(
            Switches.P_U_FORENAMES,
            FuzzyDefaults.P_U_FORENAMES_CSV,
            require_error,
        ),
        p_ep1_surname=getparam(
            Switches.P_EP1_SURNAME,
            FuzzyDefaults.P_EP1_SURNAME_CSV,
            require_error,
        ),
        p_ep2np1_surname=getparam(
            Switches.P_EP2NP1_SURNAME,
            FuzzyDefaults.P_EP2NP1_SURNAME_CSV,
            require_error,
        ),
        p_en_surname=getparam(
            Switches.P_EN_SURNAME,
            FuzzyDefaults.P_EN_SURNAME_CSV,
            require_error,
        ),
        p_ep_dob=getparam(
            Switches.P_EP_DOB,
            FuzzyDefaults.P_EP_DOB,
            require_error,
        ),
        p_en_dob=getparam(
            Switches.P_EN_DOB,
            FuzzyDefaults.P_EN_DOB,
            require_error,
        ),
        p_e_gender=getparam(
            Switches.P_E_GENDER,
            FuzzyDefaults.P_E_GENDER,
            require_error,
        ),
        p_ep_postcode=getparam(
            Switches.P_EP_POSTCODE,
            FuzzyDefaults.P_EP_POSTCODE,
            require_error,
        ),
        p_en_postcode=getparam(
            Switches.P_EN_POSTCODE, FuzzyDefaults.P_EN_POSTCODE, require_error
        ),
        min_log_odds_for_match=getparam(
            Switches.MIN_LOG_ODDS_FOR_MATCH,
            FuzzyDefaults.MIN_LOG_ODDS_FOR_MATCH,
            require_matching,
        ),
        exceeds_next_best_log_odds=getparam(
            Switches.EXCEEDS_NEXT_BEST_LOG_ODDS,
            FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS,
            require_matching,
        ),
        perfect_id_translation=getparam(
            Switches.PERFECT_ID_TRANSLATION,
            FuzzyDefaults.PERFECT_ID_TRANSLATION,
            require_matching,
        ),
        extra_validation_output=getparam(
            Switches.EXTRA_VALIDATION_OUTPUT,
            default=False,
            required=require_comparison,
        ),
        report_every=getparam(
            Switches.REPORT_EVERY,
            FuzzyDefaults.REPORT_EVERY,
            required=require_comparison,
        ),
        min_probands_for_parallel=getparam(
            Switches.MIN_PROBANDS_FOR_PARALLEL,
            FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
            required=require_comparison,
        ),
        n_workers=getparam(
            Switches.N_WORKERS,
            FuzzyDefaults.N_PROCESSES,
            required=require_comparison,
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
            f"{Person.PersonKey.OTHER_INFO!r} data? "
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
        "metaphones", nargs="+", help="Metaphones to check"
    )
    add_config_options(show_forename_metaphone_freq_parser)
    add_basic_options(show_forename_metaphone_freq_parser)

    show_forename_f2c_freq_parser = subparsers.add_parser(
        Commands.SHOW_FORENAME_F2C_FREQ,
        help="Show frequencies of forename first two characters",
    )
    show_forename_f2c_freq_parser.add_argument(
        "f2c", nargs="+", help="First-two-character groups to check"
    )
    add_config_options(show_forename_f2c_freq_parser)
    add_basic_options(show_forename_f2c_freq_parser)

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

    show_surname_f2c_freq_parser = subparsers.add_parser(
        Commands.SHOW_SURNAME_F2C_FREQ,
        help="Show frequencies of surname first two characters",
    )
    show_surname_f2c_freq_parser.add_argument(
        "f2c", nargs="+", help="First-two-character groups to check"
    )
    add_config_options(show_surname_f2c_freq_parser)
    add_basic_options(show_surname_f2c_freq_parser)

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
        freq_func = cfg.get_forename_freq_info
        for forename in args.forenames:
            forename = standardize_name(forename)
            log.info(
                f"Forename {forename!r}: "
                f"F {freq_func(forename, GENDER_FEMALE)}, "
                f"M {freq_func(forename, GENDER_MALE)}, "
                f"overall {freq_func(forename, GENDER_MISSING)}"
            )

    elif args.command == Commands.SHOW_FORENAME_METAPHONE_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        meta_freq_func = cfg.forename_freq_info.metaphone_frequency
        for metaphone in args.metaphones:
            metaphone = metaphone.upper()
            log.info(
                f"Forename metaphone {metaphone!r}: "
                f"F {meta_freq_func(metaphone, GENDER_FEMALE)}, "
                f"M {meta_freq_func(metaphone, GENDER_MALE)}"
            )

    elif args.command == Commands.SHOW_FORENAME_F2C_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        f2c_freq_func = cfg.forename_freq_info.first_two_char_frequency
        for f2c in args.f2c:
            f2c = f2c.upper()
            log.info(
                f"Forename first two characters {f2c!r}: "
                f"F {f2c_freq_func(f2c, GENDER_FEMALE)}, "
                f"M {f2c_freq_func(f2c, GENDER_MALE)}"
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
            surname = standardize_name(surname)
            log.info(
                f"Surname {surname!r}: {cfg.get_surname_freq_info(surname)}"
            )

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
                f"{cfg.surname_freq_info.metaphone_frequency(metaphone)}"
            )

    elif args.command == Commands.SHOW_SURNAME_F2C_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        for f2c in args.f2c:
            f2c = f2c.upper()
            log.info(
                f"Surname first two characters {f2c!r}: "
                f"{cfg.surname_freq_info.first_two_char_frequency(f2c)}"
            )

    elif args.command == Commands.SHOW_DOB_FREQ:
        cfg = get_cfg_from_args(
            args,
            require_hasher=False,
            require_main_config=True,
            require_error=False,
            require_matching=False,
        )
        log.info(f"DOB frequency: {cfg.p_f_dob}")

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
