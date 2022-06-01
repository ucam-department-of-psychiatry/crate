#!/usr/bin/env python

"""
crate_anon/linkage/validation/validate_fuzzy_linkage.py

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

**Highly specific code to develop/validate fuzzy linkage.**


Speed of "validate1" test
-------------------------

On a test 3 GHz desktop, this code takes approximately 100 μs to hash a person
record, and 14-40 μs to compare two records (see timing tests).

A comparison of 1000 pre-hashed subjects to 50m records requiring hashing,
without any caching, is going to take about 1000 * 50m * 120 μs, or quite a
long time -- a big part of which would be pointless re-hashing. A reasonable
strategy for a large database would therefore be to:

- pre-hash the sample with the agreed key (e.g. about 1.8 hours for 66m
  records);
- for each hashed proband, restrict the comparison to those with a matching
  hashed DOB, and either a partial or a full match on surname (e.g. for
  "SMITH", with a frequency of about 0.01, this would give about 1800 records
  to check; checking would take up to about 40 μs each (so up to 72 ms per
  proband) -- plus some query time;
- checking 1000 probands would therefore take about 72 seconds; checking
  200k probands about 4 hours.
- So we'd be talking about a time of the order of 6 hours to compare an NHS
  Trust's entire data set to a UK national database.

For validation, we are thinking about a much larger, :math:`n^2`, comparison.
Again, we should pre-hash. So if :math:`h` is the hashing time and :math:`c` is
the comparison time, we're talking about :math:`hn + cn^2`. If we work
backwards and say :math:`h` is 100 μs, :math:`c` is 20 μs on average, and we
want this achievable in 1 hour, then that gives a value for n of about 19,000,
so let's say 20,000 (sample size 10,000, "other" size 10,000).

Subsequent speedup 2020-04-24: see comments in timing tests; ``h`` now down
from 100 to 71; ``c`` now down from 14-40 to 6-22 (6 for DOB mismatch, 22 for
match). So realistically ``c = 10`` or thereabouts.

.. code-block:: r

    h <- 71 / 1e6  # microseconds to seconds
    c <- 10 / 1e6  # 20 microseconds
    t <- function(n) { h * n + c * n^2 / 2 }  # function relating time to n
    target <- 60 * 60  # target time: 1 hour = 3600 seconds
    errfunc <- function(n) { (t(n) - target) ^ 2 }  # function giving error
    result <- optim(par = 50, fn = errfunc)  # minimize error, start n = 50
    # ... gives 26825


JSON encoding
-------------

There's no reason that fuzzy_id_match.py needs to be specific about JSON
handling; it can just treat the "other_info" column as a string. We can
use JSON encoding here, and decode it in R later:
https://stackoverflow.com/questions/31599299/expanding-a-json-column-in-r.


Finding columns across databases
--------------------------------

In SQL Server, if you select from ``information_schema.columns``, you only see
columns from the database selected with the ``USE <database>`` statement or
equivalent.

There are approaches that iterate over databases
(https://stackoverflow.com/questions/2729126/,
https://web.archive.org/web/20220326112007/https://www.mssqltips.com/sqlservertip/4039/search-all-string-columns-in-all-sql-server-databases/).
The latter is *very* slow (as acknowledged).

A nasty but effective (and reasonably quick) approach is:

.. code-block:: sql

    sp_MSforeachdb '
        -- Double up single quotes within this section.
        -- Question mark stands for the current database name.
        SELECT
            ''?'' AS [database_name],
            s.name AS [schema_name],
            t.name AS [table_name],
            c.name AS [column_name]
        FROM sys.columns c
        INNER JOIN sys.objects t ON t.object_id = c.object_id
            -- sys.objects is per-column, not per-table, but this allows
            -- WHERE clauses to say "t.name", which is clearer.
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE ''?'' NOT IN (''master'', ''msdb'', ''tempdb'', ''model'')
        AND c.name LIKE ''%post%''  -- e.g. look for postcodes
        ORDER BY s.name, t.name, c.column_id
    '


SMI definition
--------------

NICE SMI definition of severe mental illness: see Chen et al. (2020) PMID
33035957, which is from NICE (2016) NG58:

    "Severe mental illness includes a clinical diagnosis of: schizophrenia,
    schizotypal and delusional disorders, or bipolar affective disorder, or
    severe depressive episodes with or without psychotic episodes."

Thus, codes:

.. code-block:: none

    dx_smi.CODE LIKE 'F20%'  -- schizophrenia
    OR dx_smi.CODE LIKE 'F21%'  -- schizotypal
    OR dx_smi.CODE LIKE 'F22%'  -- persistent delusional
    OR dx_smi.CODE LIKE 'F25%'  -- schizoaffective
    OR dx_smi.CODE LIKE 'F31%'  -- bipolar
    OR dx_smi.CODE LIKE 'F322%'  -- severe depressive episode, not psychotic
    OR dx_smi.CODE LIKE 'F323%'  -- severe depressive episode, psychotic
    OR dx_smi.CODE LIKE 'F332%'  -- rec. dep, severe, not psychotic
    OR dx_smi.CODE LIKE 'F333%'  -- rec. dep, severe, psychotic


Sort order involving NULL
-------------------------

.. code-block:: sql

    -- Test sort order involving NULL.

    CREATE DATABASE testdb;
    USE testdb;
    CREATE TABLE test_sort_postcode_dates (
        postcode VARCHAR(8) NOT NULL,
        start_date DATE,
        end_date DATE
    );

    INSERT INTO test_sort_postcode_dates
        (postcode, start_date, end_date)
    VALUES
        ('AA11 1AA', NULL,         NULL),
        ('AA11 1AA', NULL,         '2020-01-01'),
        ('AA11 1AA', NULL,         '2025-01-01'),
        ('AA11 1AA', '1990-01-01', NULL),
        ('AA11 1AA', '1990-01-01', '2020-01-01'),
        ('AA11 1AA', '1990-01-01', '2025-01-01'),
        ('AA11 1AA', '1995-01-01', NULL),
        ('AA11 1AA', '1995-01-01', '2020-01-01'),
        ('AA11 1AA', '1995-01-01', '2025-01-01'),
        ('BB22 2BB', NULL,         NULL),
        ('BB22 2BB', NULL,         '2020-01-01'),
        ('BB22 2BB', NULL,         '2025-01-01'),
        ('BB22 2BB', '1990-01-01', NULL),
        ('BB22 2BB', '1990-01-01', '2020-01-01'),
        ('BB22 2BB', '1990-01-01', '2025-01-01'),
        ('BB22 2BB', '1995-01-01', NULL),
        ('BB22 2BB', '1995-01-01', '2020-01-01'),
        ('BB22 2BB', '1995-01-01', '2025-01-01');

    SELECT
        *,
        CASE WHEN end_date IS NULL THEN 1 ELSE 0 END AS debug_end_date_sorter
    FROM test_sort_postcode_dates
    ORDER BY
        -- By default, NULL is smaller than any other value.
        -- We want any current postcodes (NULL end date) last. So:
        CASE WHEN end_date IS NULL THEN 1 ELSE 0 END,
        -- ... (ASC) past (NOT NULL) -> current (NULL)
        start_date,  -- (ASC) then by start date: NULL -> older -> newer
        end_date,  -- (ASC) then by end date: older -> newer
        postcode  -- tiebreaker


SQL Server error notes
----------------------

Sometimes when comparing two columns in SQL with ``a = b``, you may get this
error: Collation error: Cannot resolve the collation conflict between
"Latin1_General_CI_AS" and "SQL_Latin1_General_CP1_CI_AS" in the equal to
operation. This is easily resolved
(https://stackoverflow.com/questions/1607560/) by comparing e.g. ``a = b
COLLATE Latin1_General_CI_AS`` (forcing ``b`` to the right collation, in this
example).

CAST() doesn't return NULL on failure (e.g. converting characters to integer);
it produces an error. Use TRY_CAST() to return NULL on failure.

"""

import argparse
import csv
from dataclasses import asdict, dataclass
import datetime
import json
import logging
import math
import pdb
import random
import re
import sys
import timeit
from typing import (
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
)

from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
)
from cardinal_pythonlib.datetimefunc import (
    coerce_to_pendulum_date,
    truncate_date_to_first_of_month,
)
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.profile import do_cprofile
from pendulum import Date
from pendulum.parsing.exceptions import ParserError
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.result import ResultProxy, RowProxy
from sqlalchemy.sql import text

from crate_anon.common.constants import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
)
from crate_anon.linkage.fuzzy_id_match import (
    add_subparsers,
    BasePerson,
    cache_load,
    cache_save,
    get_basic_options_subparser,
    get_cfg_from_args,
    get_config_option_subparser,
    get_hasher_option_subparser,
    get_demo_csv,
    Hasher,
    MatchConfig,
    People,
    Person,
    POSTCODE_REGEX,
    read_people_2,
    TemporalIdentifier,
    warn_or_fail_if_default_key,
)

log = logging.getLogger(__name__)


# =============================================================================
# Date checking, formatting, calculation
# =============================================================================

# ISO format, yyyy-MM-dd
ISOFORMAT_DATE_RE = re.compile(
    # https://stackoverflow.com/questions/3143070/javascript-regex-iso-datetime
    r"\d{4}-([0][1-9]|1[0-2])-([0-2][1-9]|[1-3]0|3[01])"
    # ^^^^^ ^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^
    # year  month             day
)


def is_valid_isoformat_date(x: str) -> bool:
    """
    Validates an ISO-format date with separators, e.g. '2022-12-31'.
    """
    if not isinstance(x, str):
        return False
    if not ISOFORMAT_DATE_RE.match(x):
        # We check this because "2020" will convert to 2020-01-01 if we just
        # let Pendulum autoconvert below.
        return False
    try:
        coerce_to_pendulum_date(x)
    except (ParserError, ValueError):
        return False
    return True


def is_valid_isoformat_blurred_date(x: str) -> bool:
    """
    Validates an ISO-format date (as above) that must be the first of the
    month.
    """
    if not is_valid_isoformat_date(x):
        return False
    d = coerce_to_pendulum_date(x)
    return d.day == 1


def isoformat_optional_date(d: Optional[Date]) -> str:
    """
    Returns a date in string format.
    """
    if not d:
        return ""
    return d.isoformat()


def age_years(dob: Optional[Date], when: Optional[Date]) -> Optional[int]:
    """
    A person's age in years when something happened, or ``None`` if either
    DOB or the index date is unknown.
    """
    if dob and when:
        return (when - dob).in_years()
    return None


# =============================================================================
# Postcode convenience functions
# =============================================================================


def last_imd(postcodes: List["PostcodeInfo"]) -> Optional[int]:
    """
    The IMD from the last postcode specified for which an IMD is known, if any.
    """
    for p in reversed(postcodes):
        if p.index_of_multiple_deprivation is not None:
            return p.index_of_multiple_deprivation
    return None


def postcode_temporal_identifiers(
    postcodes: List["PostcodeInfo"],
) -> List[TemporalIdentifier]:
    """
    Returns the TemporalIdentifier components of a list of postcodes.
    """
    return [p.temporal_identifier for p in postcodes]


# =============================================================================
# Speed testing
# =============================================================================


def speedtest(cfg: MatchConfig, set_breakpoint: bool = False) -> None:
    """
    Run self-tests or timing tests.

    Args:
        cfg:
            the master :class:`MatchConfig` object
        set_breakpoint:
            set a pdb breakpoint to explore objects from the Python console?
    """
    log.info("Building test conditions...")
    p1 = TemporalIdentifier(
        "CB2 0QQ", Date(2000, 1, 1), Date(2010, 1, 1)  # Addenbrooke's Hospital
    )
    alice_bcd_unique_2000_add = Person(
        cfg=cfg,
        local_id="1",
        first_name="Alice",
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=[p1],
    )
    alice_smith_1930 = Person(
        cfg=cfg,
        local_id="8",
        first_name="Alice",
        surname="Smith",
        dob="1930-01-01",
    )
    alice_smith_2000 = Person(
        cfg=cfg,
        local_id="9",
        first_name="Alice",
        surname="Smith",
        dob="2000-01-01",
    )
    alice_smith = Person(
        cfg=cfg,
        local_id="10",
        first_name="Alice",
        surname="Smith",
    )

    if set_breakpoint:
        pdb.set_trace()

    # -------------------------------------------------------------------------
    # Timing tests
    # -------------------------------------------------------------------------
    log.info("Testing comparison speed (do NOT use verbose logging)...")
    # NB Python has locals() and globals() but not nonlocals() so it's hard
    # to make this code work with a temporary function as you might hope.
    microsec_per_sec = 1e6
    n_for_speedtest = 10000

    t = (
        microsec_per_sec
        * timeit.timeit(
            "alice_bcd_unique_2000_add"
            ".log_odds_same(alice_bcd_unique_2000_add)",
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(f"Plaintext full match: {t} μs per comparison")
    # On Wombat: 146 microseconds.
    # On Wombat 2020-04-24: 64 microseconds.

    t = (
        microsec_per_sec
        * timeit.timeit(
            "alice_bcd_unique_2000_add.hashed()"
            ".log_odds_same(alice_bcd_unique_2000_add.hashed())",
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(f"Hash two objects + full match: {t} μs per comparison")
    # On Wombat: 631 microseconds.
    # On Wombat 2020-04-24: 407 microseconds.

    t = (
        microsec_per_sec
        * timeit.timeit(
            "alice_smith_1930.log_odds_same(alice_smith_2000, )",
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(f"Plaintext DOB mismatch: {t} μs per comparison")
    # On Wombat: 13.6 microseconds.
    # On Wombat 2020-04-24: 6.1 microseconds.

    t = (
        microsec_per_sec
        * timeit.timeit(
            "alice_smith_1930.hashed()"
            ".log_odds_same(alice_smith_2000.hashed())",
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(f"Hash two objects + DOB mismatch: {t} μs per comparison")
    # On Wombat: 240 microseconds.
    # On Wombat 2020-04-24: 153 microseconds.

    t = (
        microsec_per_sec
        * timeit.timeit(
            "alice_smith_1930.hashed()",
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(f"Hash one object: {t} μs per comparison")
    # On Wombat: 104 microseconds.
    # On Wombat 2020-04-24: 71 microseconds.

    hashed_alice_smith_1930 = alice_smith_1930.hashed()
    hashed_alice_smith_2000 = alice_smith_2000.hashed()

    t = (
        microsec_per_sec
        * timeit.timeit(
            (
                "hashed_alice_smith_1930"
                ".log_odds_same(hashed_alice_smith_1930)"
            ),
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(f"Compare two identical hashed objects: {t} μs per comparison")
    # On Wombat 2020-04-024: 21.7 microseconds.

    t = (
        microsec_per_sec
        * timeit.timeit(
            (
                "hashed_alice_smith_1930"
                ".log_odds_same(hashed_alice_smith_2000)"
            ),
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(
        f"Compare two DOB-mismatched hashed objects: {t} μs per comparison"
    )
    # On Wombat 2020-04-024: 6.4 microseconds.


# =============================================================================
# Validation 1
# =============================================================================


def make_deletion_data(people: People, cfg: MatchConfig) -> People:
    """
    Makes a copy of the supplied data set with deliberate deletions applied.

    Surnames and DOBs are excepted as we require exact matches for those.
    """
    deletion_data = People(cfg)  # start a new empty collection
    log.debug(f"Making deletion data for {people.size()} people")
    for person in people.people:
        modified_person = person.copy()
        modified_person.debug_delete_something()
        log.debug(f"Deleted:\nFROM: {person}\nTO  : {modified_person}")
        deletion_data.add_person(modified_person)
    return deletion_data


def make_typo_data(people: People, cfg: MatchConfig) -> People:
    """
    Makes a copy of the supplied data set with deliberate typos applied.

    Surnames and DOBs are excepted as we require exact matches for those.
    """
    typo_data = People(cfg)  # start a new empty collection
    log.debug(f"Making typo data for {people.size()} people")
    for person in people.people:
        modified_person = person.copy()
        modified_person.debug_mutate_something()
        log.debug(f"Mutated:\nFROM: {person}\nTO  : {modified_person}")
        typo_data.add_person(modified_person)
    return typo_data


class ValidationOutputColnames:
    COLLECTION_NAME = "collection_name"
    IN_SAMPLE = "in_sample"
    DELETIONS = "deletions"
    TYPOS = "typos"

    IS_HASHED = "is_hashed"
    PROBAND_ID = "proband_id"
    WINNER_ID = "winner_id"
    BEST_MATCH_ID = "best_match_id"
    BEST_LOG_ODDS = "best_log_odds"
    SECOND_BEST_LOG_ODDS = "second_best_log_odds"
    SECOND_BEST_MATCH_ID = "second_best_match_id"

    CORRECT_IF_WINNER = "correct_if_winner"
    LEADER_ADVANTAGE = "leader_advantage"


VALIDATION_OUTPUT_COLNAMES = [
    getattr(ValidationOutputColnames, x)
    for x in vars(ValidationOutputColnames).keys()
    if not x.startswith("_")
    # dir() sorts by name; use vars()
]


def validate_1(
    cfg: MatchConfig,
    people_csv: str,
    output_csv: str,
    cache_filename: str = None,
    seed: int = 1234,
    report_every: int = 100,
) -> None:
    """
    Read data and perform split-half validation.

    Args:
        cfg: the master :class:`MatchConfig` object
        people_csv: CSV of people; see :func:`read_people`.
        cache_filename: cache filename, for faster loading
        output_csv: output filename
        seed: RNG seed
        report_every: report progress every n rows
    """
    # -------------------------------------------------------------------------
    # Load and hash data
    # -------------------------------------------------------------------------
    try:
        if not cache_filename:
            raise FileNotFoundError
        (
            in_plaintext,
            out_plaintext,
            in_hashed,
            out_hashed,
            in_deletions,
            out_deletions,
            in_deletions_hashed,
            out_deletions_hashed,
            in_typos,
            out_typos,
            in_typos_hashed,
            out_typos_hashed,
        ) = cache_load(cache_filename)
        log.info(f"Read from cache: {cache_filename}")
    except FileNotFoundError:
        in_plaintext, out_plaintext = read_people_2(
            cfg, people_csv, alternate_groups=True
        )
        log.info(f"Seeding random number generator with: {seed}")
        random.seed(seed)
        log.info("Making copies with deliberate deletions...")
        in_deletions = make_deletion_data(in_plaintext, cfg)
        out_deletions = make_deletion_data(out_plaintext, cfg)
        log.info("Making copies with deliberate typos...")
        in_typos = make_typo_data(in_plaintext, cfg)
        out_typos = make_typo_data(out_plaintext, cfg)

        log.info("Hashing...")
        in_hashed = in_plaintext.hashed()
        out_hashed = out_plaintext.hashed()
        in_deletions_hashed = in_deletions.hashed()
        out_deletions_hashed = out_deletions.hashed()
        in_typos_hashed = in_typos.hashed()
        out_typos_hashed = out_typos.hashed()
        log.info("... done")

        if cache_filename:
            cache_save(
                cache_filename,
                [
                    in_plaintext,
                    out_plaintext,
                    in_hashed,
                    out_hashed,
                    in_deletions,
                    out_deletions,
                    in_deletions_hashed,
                    out_deletions_hashed,
                    in_typos,
                    out_typos,
                    in_typos_hashed,
                    out_typos_hashed,
                ],
            )
    # -------------------------------------------------------------------------
    # Calculate validation data and save it
    # -------------------------------------------------------------------------
    data = [
        # people, collection_name, sample, in_sample, deletions, typos
        (in_plaintext, "in_plaintext", in_plaintext, True, False, False),
        (out_plaintext, "out_plaintext", in_plaintext, False, False, False),
        (in_hashed, "in_hashed", in_hashed, True, False, False),
        (out_hashed, "out_hashed", in_hashed, False, False, False),
        (in_deletions, "in_deletions", in_plaintext, True, True, False),
        (out_deletions, "out_deletions", in_plaintext, False, True, False),
        (
            in_deletions_hashed,
            "in_deletions_hashed",
            in_hashed,
            True,
            True,
            False,
        ),
        (
            out_deletions_hashed,
            "out_deletions_hashed",
            in_hashed,
            False,
            True,
            False,
        ),
        (in_typos, "in_typos", in_plaintext, True, False, True),
        (out_typos, "out_typos", in_plaintext, False, False, True),
        (in_typos_hashed, "in_typos_hashed", in_hashed, True, False, True),
        (out_typos_hashed, "out_typos_hashed", in_hashed, False, False, True),
    ]  # type: List[Tuple[People, str, People, bool, bool, bool]]
    log.info(f"Writing to: {output_csv}")
    vc = ValidationOutputColnames
    with open(output_csv, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=VALIDATION_OUTPUT_COLNAMES)
        writer.writeheader()
        i = 1  # row 1 is the header
        for (
            people,
            collection_name,
            sample,
            in_sample,
            deletions,
            typos,
        ) in data:
            for person in people.people:
                i += 1
                if i % report_every == 0:
                    log.info(f"... creating CSV row {i}")
                result = sample.get_unique_match_detailed(person)

                if math.isfinite(result.best_log_odds) and math.isfinite(
                    result.second_best_log_odds
                ):
                    leader_advantage = (
                        result.best_log_odds - result.second_best_log_odds
                    )
                else:
                    leader_advantage = None
                best_match_id = (
                    result.best_candidate.local_id
                    if result.best_candidate
                    else None
                )
                correct_if_winner = (
                    int(best_match_id == person.local_id)
                    if result.winner
                    else None
                )

                rowdata = {
                    # As of Python 3.6, keyword order is preserved:
                    # https://docs.python.org/3/library/collections.html#collections.OrderedDict  # noqa
                    # https://www.python.org/dev/peps/pep-0468/
                    # ... but it doesn't matter since we're using a DictWriter.
                    vc.COLLECTION_NAME: collection_name,
                    vc.IN_SAMPLE: int(in_sample),
                    vc.DELETIONS: int(deletions),
                    vc.TYPOS: int(typos),
                    vc.IS_HASHED: int(person.is_hashed),
                    vc.PROBAND_ID: person.local_id,
                    vc.WINNER_ID: (
                        result.winner.local_id if result.winner else None
                    ),
                    vc.BEST_MATCH_ID: best_match_id,
                    vc.BEST_LOG_ODDS: result.best_log_odds,
                    vc.SECOND_BEST_LOG_ODDS: result.second_best_log_odds,
                    vc.SECOND_BEST_MATCH_ID: (
                        result.second_best_candidate.local_id
                        if result.second_best_candidate
                        else None
                    ),
                    vc.CORRECT_IF_WINNER: correct_if_winner,
                    vc.LEADER_ADVANTAGE: leader_advantage,
                }
                writer.writerow(rowdata)
    log.info("... done")


# =============================================================================
# Validation 2
# =============================================================================


@dataclass
class PostcodeInfo:
    """
    Postcode with IMD.
    """

    postcode: str
    start_date: Optional[datetime.date]
    end_date: Optional[datetime.date]
    index_of_multiple_deprivation: Optional[int]

    def __post_init__(self) -> None:
        nonetype = type(None)
        if not isinstance(self.postcode, str) or not POSTCODE_REGEX.match(
            self.postcode
        ):
            raise ValueError(f"Bad postcode: {self.postcode!r}")
        if not isinstance(self.start_date, (datetime.date, nonetype)):
            raise ValueError(f"Bad start_date: {self.start_date!r}")
        if not isinstance(self.end_date, (datetime.date, nonetype)):
            raise ValueError(f"Bad end_date: {self.end_date!r}")
        if not isinstance(self.index_of_multiple_deprivation, (int, nonetype)):
            raise ValueError(
                f"Bad index_of_multiple_deprivation: "
                f"{self.index_of_multiple_deprivation!r}"
            )

    @property
    def temporal_identifier(self) -> TemporalIdentifier:
        return TemporalIdentifier(
            identifier=self.postcode,
            start_date=self.start_date,
            end_date=self.end_date,
        )


@dataclass
class CPFTValidationExtras:
    """
    Extra information for the "other_info" column for validation, as per the
    approved CPFT protocol.

    This class should contain all information that would not otherwise make it
    into the matching file, i.e. that information required to check the
    correctness and/or bias of matching. It should not contain anything
    directly identifiable.

    We store dates as strings because they are then JSON-serializable.
    """

    # Gold-standard identifier to compare across databases:
    hashed_nhs_number: str  # because "local_id" will be per system

    # Demographics:
    blurred_dob: str  # ISO-format string version of blurred DOB
    gender: str
    ethnicity: Optional[str]
    index_of_multiple_deprivation: Optional[int]

    # MH-related information:
    first_mh_care_date: Optional[str]
    age_at_first_mh_care: Optional[int]  # deliberately blurred to year
    any_icd10_dx_present: int  # binary
    chapter_f_icd10_dx_present: int  # binary
    severe_mental_illness_icd10_dx_present: int  # binary

    def __post_init__(self) -> None:
        binary = (0, 1)
        nonetype = type(None)

        if not isinstance(self.hashed_nhs_number, str):
            raise ValueError(
                f"Bad hashed_nhs_number: {self.hashed_nhs_number!r}"
            )

        if not is_valid_isoformat_blurred_date(self.blurred_dob):
            raise ValueError(f"Bad blurred_dob: {self.blurred_dob!r}")
        if not isinstance(self.gender, str):
            raise ValueError(f"Bad gender: {self.gender!r}")
        if not isinstance(self.ethnicity, (str, nonetype)):
            raise ValueError(f"Bad ethnicity: {self.ethnicity!r}")
        if not isinstance(self.index_of_multiple_deprivation, (int, nonetype)):
            raise ValueError(
                f"Bad index_of_multiple_deprivation: "
                f"{self.index_of_multiple_deprivation!r}"
            )

        if self.first_mh_care_date is not None:
            if not is_valid_isoformat_date(self.first_mh_care_date):
                raise ValueError(
                    f"Bad first_mh_care_date: {self.first_mh_care_date!r}"
                )
        if not isinstance(self.age_at_first_mh_care, (int, nonetype)):
            raise ValueError(
                f"Bad age_at_first_mh_care: {self.age_at_first_mh_care!r}"
            )
        if self.any_icd10_dx_present not in binary:
            raise ValueError(
                f"Bad any_icd10_dx_present: {self.any_icd10_dx_present!r}"
            )
        if self.chapter_f_icd10_dx_present not in binary:
            raise ValueError(
                f"Bad chapter_f_icd10_dx_present: "
                f"{self.chapter_f_icd10_dx_present!r}"
            )
        if self.severe_mental_illness_icd10_dx_present not in binary:
            raise ValueError(
                f"Bad severe_mental_illness_icd10_dx_present: "
                f"{self.severe_mental_illness_icd10_dx_present!r}"
            )

    @property
    def json(self) -> str:
        return json.dumps(asdict(self))


class QueryColnames:
    """
    Used to reduce some duplication. However, we don't use these within SQL
    itself simply because copying/pasting is helpful for SQL development.
    """

    ANY_ICD10_DX_PRESENT = "any_icd10_dx_present"
    CHAPTER_F_ICD10_DX_PRESENT = "chapter_f_icd10_dx_present"
    DOB = "dob"
    END_DATE = "end_date"
    ETHNICITY = "ethnicity"
    FIRST_MH_CARE_DATE = "first_mh_care_date"
    FIRST_NAME = "first_name"
    GENDER = "gender"
    INDEX_OF_MULTIPLE_DEPRIVATION = "index_of_multiple_deprivation"
    PREV_INDEX_OF_MULTIPLE_DEPRIVATION = "prev_index_of_multiple_deprivation"
    MIDDLE_NAME = "middle_name"
    NHS_NUMBER = "nhs_number"
    POSTCODE = "postcode"
    PREV_POSTCODE = "prev_postcode"
    SMI_ICD10_DX_PRESENT = "smi_icd10_dx_present"
    START_DATE = "start_date"
    SURNAME = "surname"


# -----------------------------------------------------------------------------
# RiO
# -----------------------------------------------------------------------------


def _get_rio_postcodes(
    engine: Engine, rio_patient_id: str
) -> List[PostcodeInfo]:
    """
    Fetches distinct valid time-stamped postcodes for a given person, from RiO.
    The most recent should be last.

    Args:
        engine:
            SQLAlchemy engine
        rio_patient_id:
            RiO patient ID

    Returns:
        list: of postcodes in :class:`PostcodeInfo` format

    """
    sql = text(
        """
        SELECT DISTINCT
            -- TOP 0  -- for debugging

            -- From the identifiable address table:
            UPPER(a.PostCode) AS postcode,
            CAST(a.FromDate AS DATE) AS start_date,
            CAST(a.ToDate AS DATE) AS end_date,

            -- From the ONS postcode-to-IMD lookup:
            ons.imd AS index_of_multiple_deprivation,

            CASE
                WHEN CAST(a.ToDate AS DATE) IS NULL THEN 1 ELSE 0
            END AS end_date_is_null
            -- "ORDER BY items must appear in the select list if
            -- SELECT DISTINCT is specified."
        FROM
            RiO62CAMLive.dbo.ClientAddress a
        LEFT OUTER JOIN
            onspd.dbo.postcode AS ons  -- Office for National Statistics
            ON ons.pcd_nospace = REPLACE(UPPER(a.PostCode), ' ', '')
        WHERE
            a.ClientID = :patient_id
            AND a.PostCode IS NOT NULL
            AND LEN(a.PostCode) >= 5  -- minimum for valid postcode
        ORDER BY
            -- You can use aliases in ORDER BY from SQL Server 2008 onwards.
            end_date_is_null,
            start_date,
            end_date,
            postcode
    """
    )
    rows = engine.execute(sql, patient_id=rio_patient_id)
    q = QueryColnames
    postcodes = [
        PostcodeInfo(
            postcode=row[q.POSTCODE],
            start_date=coerce_to_pendulum_date(row[q.START_DATE]),
            end_date=coerce_to_pendulum_date(row[q.END_DATE]),
            index_of_multiple_deprivation=row[q.INDEX_OF_MULTIPLE_DEPRIVATION],
        )
        for row in rows
        if POSTCODE_REGEX.match(row[q.POSTCODE])
    ]
    return postcodes


def _get_rio_middle_names(engine: Engine, rio_client_id: str) -> List[str]:
    """
    Fetches middle names for a given person, from RiO.

    Args:
        engine:
            SQLAlchemy engine
        rio_client_id:
            RiO primary key (``ClientId``)

    Returns:
        list: of middle names

    Out of a large database (>150k people), 4 have two rows here. JL notes that
    in each case examined, the earliest EffectiveDate, or smallest crate_pk, is
    the right one.

    De-identified debugging queries:

    .. code-block:: sql

        SELECT TOP 10
            -- De-identified inspection:
            c2.crate_rio_number,
            c2.ClientNameID,
            c2.EffectiveDate,
            c2.Deleted,
            c2.AliasType,
            c2.EndDate,
            c2.crate_pk
        FROM (
            -- Patients with >1 apparent record in this table:
            SELECT c1.crate_rio_number, COUNT(*) AS n_per_patient
            FROM RiO62CAMLive.dbo.ClientName c1
            WHERE c1.EndDate IS NULL
            AND c1.Deleted = 0
            GROUP BY c1.crate_rio_number
            HAVING COUNT(*) > 1
        ) s
        INNER JOIN RiO62CAMLive.dbo.ClientName c2
            ON c2.crate_rio_number = s.crate_rio_number

    The majority appear to have one entry with AliasType = '1' and another with
    AliasType = '2'. These are defined in ClientAliasType (a non-patient
    table); note that the code is of type NVARCHAR(10). Here, we see that '1'
    is 'Usual name'; '2' is 'Alias'; there are others.

    Restricting to '1' eliminates duplicates.

    .. code-block:: sql

        SELECT
            COUNT(DISTINCT crate_rio_number) AS n_patients,
            COUNT(DISTINCT ClientID) AS n_patients_another_way,
            COUNT(*) AS n_rows
        FROM RiO62CAMLive.dbo.ClientName c1
        WHERE EndDate IS NULL
            AND Deleted = 0
            AND AliasType = '1'  -- usual name

    """
    sql = text(
        """
        SELECT
            -- OK to use UPPER() with NULL values. Result is, of course, NULL.
            -- GivenName1 should be the first name.
            UPPER(GivenName2) AS middle_name_1,
            UPPER(GivenName3) AS middle_name_2,
            UPPER(GivenName4) AS middle_name_3,
            UPPER(GivenName5) AS middle_name_4
            -- None contain a double space.
        FROM
            RiO62CAMLive.dbo.ClientName
        WHERE
            ClientID = :client_id
            AND EndDate IS NULL  -- still current
            AND Deleted = 0  -- redundant
            AND AliasType = '1'  -- usual name
    """
    )
    result = engine.execute(sql, client_id=rio_client_id)  # type: ResultProxy
    rows = result.fetchall()  # type: List[RowProxy]
    n_rows = len(rows)  # or result.rowcount()
    assert n_rows <= 1, "Didn't expect >1 row per patient in ClientName"
    if n_rows == 0:
        return []
    row = rows[0]
    middle_names = [x for x in row if x]  # remove blanks
    return middle_names


def validate_2_fetch_rio(
    url: str, hash_key: str, echo: bool = False
) -> Generator[BasePerson, None, None]:
    """
    Generates IDENTIFIED people from CPFT's RiO source database.

    The connection to any such database is HIGHLY confidential; it sits on a
    secure server within a secure network and access to this specific database
    is very restricted -- to administrators only.

    Args:
        url:
            SQLAlchemy URL.
        hash_key:
            Key for hashing NHS number (original ID) to research ID.
        echo:
            Echo SQL?

    Yields:
        :class:`Person` objects
    """
    sql = text(
        """
        SELECT
        
            -- From the main patient index:
            ci.ClientID AS rio_client_id,  -- VARCHAR(15) NOT NULL
            CAST(ci.NNN AS BIGINT) AS nhs_number,
            ci.Firstname AS first_name,
            ci.Surname AS surname,
            CAST(ci.DateOfBirth AS DATE) AS dob,
            CASE ci.Gender
                WHEN 'F' THEN 'F'
                WHEN 'M' THEN 'M'
                WHEN 'X' THEN 'X'
                ELSE ''
                -- 'U' is the RiO "unknown" value
            END AS gender,
            CAST(ci.FirstCareDate AS DATE) AS first_mh_care_date,

            -- From the ethnicity table:
            ge.CodeDescription AS ethnicity,

            -- From diagnostic codes:
            -- Codes can be with or without dots, e.g. F321 or F32.1 (!).
            -- But a dot only as the fourth character, if present.
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        RiO62CAMLive.dbo.DiagnosisClient dx_any
                    WHERE
                        dx_any.ClientID = ci.ClientID
                        AND dx_any.RemovalDate IS NULL  -- not removed
                        -- NB RemovalDate indicates deletion and is separate
                        -- from DiagnosisEndDate, e.g. a real problem now gone. 
                        -- AND dx_any.CodingScheme = 'ICD10'  -- redundant
                        -- AND dx_any.Diagnosis IS NOT NULL  -- redundant
                        -- AND dx_any.Diagnosis != ''  -- redundant
                ) THEN 1
                ELSE 0
            END AS any_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        RiO62CAMLive.dbo.DiagnosisClient dx_f
                    WHERE
                        dx_f.ClientID = ci.ClientID
                        AND dx_f.RemovalDate IS NULL
                        AND dx_f.Diagnosis LIKE 'F%'
                ) THEN 1
                ELSE 0
            END AS chapter_f_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        RiO62CAMLive.dbo.DiagnosisClient dx_smi
                    WHERE
                        dx_smi.ClientID = ci.ClientID
                        AND dx_smi.RemovalDate IS NULL
                        AND (
                            dx_smi.Diagnosis LIKE 'F20%'  -- schizophrenia
                            OR dx_smi.Diagnosis LIKE 'F21%'  -- schizotypal
                            OR dx_smi.Diagnosis LIKE 'F22%'  -- persistent delusional
                            OR dx_smi.Diagnosis LIKE 'F25%'  -- schizoaffective
                            OR dx_smi.Diagnosis LIKE 'F31%'  -- bipolar
                            OR REPLACE(dx_smi.Diagnosis, '.', '') LIKE 'F322%'  -- severe depressive episode, not psychotic
                            OR REPLACE(dx_smi.Diagnosis, '.', '') LIKE 'F323%'  -- severe depressive episode, psychotic
                            OR REPLACE(dx_smi.Diagnosis, '.', '') LIKE 'F332%'  -- rec. dep, severe, not psychotic
                            OR REPLACE(dx_smi.Diagnosis, '.', '') LIKE 'F333%'  -- rec. dep, severe, psychotic
                        )
                ) THEN 1
                ELSE 0
            END AS smi_icd10_dx_present

        FROM
            RiO62CAMLive.dbo.ClientIndex AS ci  -- identifiable patient table
            -- We use the original raw RiO database, not the CRATE-processed 
            -- one.
        LEFT JOIN
            RiO62CAMLive.dbo.GenEthnicity ge
            ON ge.Code = ci.Ethnicity
            AND ge.Deleted = 0
        WHERE
            -- Restrict to patients with NHS numbers:
            (ci.NNNStatus = 1 OR ci.NNNStatus = 2)
            -- 2 = NHS number verified; see table NNNStatus
            -- Most people have status 1 (about 119k people), compared to
            -- about 80k for status 2 (on 2020-04-28). Then about 6k have
            -- status 0 ("trace/verification required"), and about 800 have
            -- status 3 ("no match found"). Other codes not present.
            -- A very small number (~40) have a null NHS number despite an
            -- OK-looking status flag; we'll skip them.
            AND (
                TRY_CAST(REPLACE(ci.NNN, ' ', '') AS BIGINT) IS NOT NULL
                AND LEN(REPLACE(ci.NNN, ' ', '')) = 10
            )

        -- Final count: 208538 (on 2022-05-26).
    """  # noqa
    )
    _hash = Hasher(hash_key).hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    q = QueryColnames
    for row in result:
        rio_client_id = row["rio_client_id"]  # type: str
        nhs_number = row[q.NHS_NUMBER]  # type: int
        dob = coerce_to_pendulum_date(row[q.DOB])
        gender = row[q.GENDER]  # type: str
        first_mh_care_date = coerce_to_pendulum_date(row[q.FIRST_MH_CARE_DATE])

        middle_names = _get_rio_middle_names(engine, rio_client_id)
        postcodes = _get_rio_postcodes(engine, rio_client_id)

        other = CPFTValidationExtras(
            hashed_nhs_number=_hash(nhs_number),
            blurred_dob=isoformat_optional_date(
                truncate_date_to_first_of_month(dob)
            ),
            gender=gender,
            ethnicity=row[q.ETHNICITY],
            index_of_multiple_deprivation=last_imd(postcodes),
            first_mh_care_date=isoformat_optional_date(first_mh_care_date),
            age_at_first_mh_care=age_years(dob, first_mh_care_date),
            any_icd10_dx_present=row[q.ANY_ICD10_DX_PRESENT],
            chapter_f_icd10_dx_present=row[q.CHAPTER_F_ICD10_DX_PRESENT],
            severe_mental_illness_icd10_dx_present=row[q.SMI_ICD10_DX_PRESENT],
        )
        p = BasePerson(
            local_id=rio_client_id,
            other_info=other.json,
            first_name=row[q.FIRST_NAME] or "",
            middle_names=middle_names,
            surname=row[q.SURNAME] or "",
            gender=gender,
            dob=isoformat_optional_date(dob),
            postcodes=postcode_temporal_identifiers(postcodes),
        )
        yield p


# -----------------------------------------------------------------------------
# CRS/CDL
# -----------------------------------------------------------------------------


def validate_2_fetch_cdl(
    url: str, hash_key: str, echo: bool = False
) -> Generator[BasePerson, None, None]:
    """
    Generates IDENTIFIED people from CPFT's CRS/CRL source database.

    See :func:`validate_2_fetch_rio` for notes.

    Information we do not have:

    - Dates for postcodes; there are address dates in CRS_CDL.dbo.Address but
      that is de-identified. Not sure where the master identifiable copy is,
      but maybe no longer available?
    - Middle names (not present anywhere).

    An older query with columns like ``patients.dttm_of_birth`` is no longer
    current.

    Column exploration (see non-aliased table names below):

    - v.EJPS_ID is PRIMARY KEY VARCHAR(10) NOT NULL; either 'M<number>' or
      'number'; length 3/4/6/7.
    - ip.PatientID is INT NOT NULL, observed length 4/5/6 = ?
    - ip.Identifier is NVARCHAR(50) NOT NULL, length 4/10/12; deduced (below)
      to be NHS#
    - ip.CRSNo is NVARCHAR(50) NOT NULL; length 4/6/7/8; deduced to be CRS/CDL#

    - Linkage combinations that do/do not work:

      - ``v.EPJS_ID = ip.PatientID`` -- type mismatch

      - ``v.EPJS_ID = ip.Identifier COLLATE Latin1_General_CI_AS`` -- matches 0

      - ``v.EPJS_ID = ip.CRSNo COLLATE Latin1_General_CI_AS`` -- matches 154658
      - ``REPLACE(v.EPJS_ID, 'M', '') = REPLACE(ip.CRSNo COLLATE
        Latin1_General_CI_AS, 'M', '')`` -- also matches 154658

      - ``v.NHS_ID = ip.Identifier COLLATE Latin1_General_CI_AS`` -- matches
        152944
      - ``REPLACE(v.NHS_ID, ' ', '') = REPLACE(ip.Identifier COLLATE
        Latin1_General_CI_AS, ' ', '')``  -- matches 153060

    - v.NHS_ID: VARCHAR(15) column, can be NULL. Length 3/8/10/12.

      - If 3, is '123' (junk) or 'xNx', i.e. missing. (Note that 'xNx' is/was a
        common "missing" code in CRIS.)
      - If 8, is garbage.
      - If 12, has spaces in (format: xxx xxx xxxx).

    """
    sql = text(
        """
        SELECT
            -- TOP 0  -- use for debugging; check syntax, no results
            -- or use COUNT(*) instead of what follows

            -- From the identifiable patient table:
            ip.PatientID AS cdl_m_number,  -- INT NOT NULL
            ip.FirstName AS first_name,
            ip.LastName AS surname,
            CAST(ip.DOB AS DATE) as dob,
            ip.PostCode AS postcode,

            -- From the linkage table:
            CAST(REPLACE(v.NHS_ID, ' ', '') AS BIGINT) AS nhs_number,

            -- From the research (de-identified) master patient table:
            CASE rp.GENDER
                WHEN 'Female' THEN 'F'
                WHEN 'Male' THEN 'M'
                WHEN 'Not Specified' THEN 'X'
                ELSE ''
                -- 'Not Known' is the CRS/CDL "unknown" value
            END AS gender,
            rp.ETHNICITY AS ethnicity,  -- see also CDLPatient.Ethnicity
            CAST(rp.CREATE_DTTM AS DATE) AS first_mh_care_date,
            -- ... first registration date

            -- From the diagnosis table in the research database:
            -- Codes are of the format "F2391", with no space or full stop.
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        CRS_CDL.dbo.Diagnosis dx_any
                    WHERE
                        dx_any.BrcId = rp.BrcId
                        AND dx_any.CODE IS NOT NULL
                ) THEN 1
                ELSE 0
            END AS any_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        CRS_CDL.dbo.Diagnosis dx_f
                    WHERE
                        dx_f.BrcId = rp.BrcId
                        AND dx_f.CODE LIKE 'F%'
                ) THEN 1
                ELSE 0
            END AS chapter_f_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        CRS_CDL.dbo.Diagnosis dx_smi
                    WHERE
                        dx_smi.BrcId = rp.BrcId
                        AND (
                            dx_smi.CODE LIKE 'F20%'  -- schizophrenia
                            OR dx_smi.CODE LIKE 'F21%'  -- schizotypal
                            OR dx_smi.CODE LIKE 'F22%'  -- persistent delusional
                            OR dx_smi.CODE LIKE 'F25%'  -- schizoaffective
                            OR dx_smi.CODE LIKE 'F31%'  -- bipolar
                            OR dx_smi.CODE LIKE 'F322%'  -- severe depressive episode, not psychotic
                            OR dx_smi.CODE LIKE 'F323%'  -- severe depressive episode, psychotic
                            OR dx_smi.CODE LIKE 'F332%'  -- rec. dep, severe, not psychotic
                            OR dx_smi.CODE LIKE 'F333%'  -- rec. dep, severe, psychotic
                        )
                ) THEN 1
                ELSE 0
            END AS smi_icd10_dx_present,

            -- From the ONS postcode-to-IMD lookup:
            ons.imd AS index_of_multiple_deprivation

        FROM
            rawCRSCDL.dbo.[CRS_Output_2020 09 21] AS ip
            -- ... identifiable patient table (only table in that database)
        INNER JOIN
            zVaultCRS_CDL.dbo.NHSID_BRC_Lookup AS v  -- vault, linking id/de-id
            ON v.EPJS_ID = ip.CRSNo COLLATE Latin1_General_CI_AS  -- CRS/CDL#
        INNER JOIN
            CRS_CDL.dbo.MPI AS rp  -- research patient table
            ON rp.BrcId = v.BRC_ID  -- research ID; INT NOT NULL
        LEFT OUTER JOIN
            onspd.dbo.postcode AS ons  -- Office for National Statistics
            ON ons.pcd_nospace = REPLACE(UPPER(ip.PostCode), ' ', '')
        WHERE
            -- We require an NHS number to be known.
            (
                TRY_CAST(REPLACE(v.NHS_ID, ' ', '') AS BIGINT) IS NOT NULL
                AND LEN(REPLACE(v.NHS_ID, ' ', '')) = 10
            )
            -- Successful double-check: no change with: v.EPJS_ID != 'xNx'.

        -- Final count: 152888 (on 2022-05-26).
    """  # noqa
    )
    _hash = Hasher(hash_key).hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    q = QueryColnames
    for row in result:
        cdl_m_number = row["cdl_m_number"]  # type: int
        nhs_number = row[q.NHS_NUMBER]
        dob = coerce_to_pendulum_date(row[q.DOB])
        gender = row[q.GENDER]
        first_mh_care_date = coerce_to_pendulum_date(row[q.FIRST_MH_CARE_DATE])

        postcodes = []  # type: List[PostcodeInfo]
        postcode_str = row[q.POSTCODE]
        if postcode_str and POSTCODE_REGEX.match(postcode_str):
            postcodes.append(
                PostcodeInfo(
                    postcode=postcode_str.upper(),
                    start_date=None,
                    end_date=None,
                    index_of_multiple_deprivation=row[
                        q.INDEX_OF_MULTIPLE_DEPRIVATION
                    ],
                )
            )

        other = CPFTValidationExtras(
            hashed_nhs_number=_hash(nhs_number),
            blurred_dob=isoformat_optional_date(
                truncate_date_to_first_of_month(dob)
            ),
            gender=gender,
            ethnicity=row[q.ETHNICITY],
            index_of_multiple_deprivation=last_imd(postcodes),
            first_mh_care_date=isoformat_optional_date(first_mh_care_date),
            age_at_first_mh_care=age_years(dob, first_mh_care_date),
            any_icd10_dx_present=row[q.ANY_ICD10_DX_PRESENT],
            chapter_f_icd10_dx_present=row[q.CHAPTER_F_ICD10_DX_PRESENT],
            severe_mental_illness_icd10_dx_present=row[q.SMI_ICD10_DX_PRESENT],
        )
        p = BasePerson(
            local_id=str(cdl_m_number),
            other_info=other.json,
            first_name=row[q.FIRST_NAME] or "",
            middle_names=[],
            surname=row[q.SURNAME] or "",
            gender=gender,
            dob=isoformat_optional_date(dob),
            postcodes=postcode_temporal_identifiers(postcodes),
        )
        yield p


# -----------------------------------------------------------------------------
# PCMIS
# -----------------------------------------------------------------------------


def validate_2_fetch_pcmis(
    url: str, hash_key: str, echo: bool = False
) -> Generator[BasePerson, None, None]:
    """
    Generates IDENTIFIED people from CPFT's PCMIS source database.

    Args:
        url:
            SQLAlchemy URL.
        hash_key:
            Key for hashing NHS number (original ID) to research ID.
        echo:
            Echo SQL?

    Yields:
        :class:`Person` objects

    Before running:

    .. code-block:: sql

        CREATE INDEX _crateidx_fuzzy_pcmis_pd_pid
            ON rawPCMIS.dbo.PatientDetails (PatientID);
        CREATE INDEX _crateidx_fuzzy_pcmis_pd_nhsn
            ON rawPCMIS.dbo.PatientDetails (NHSNumber);

        CREATE INDEX _crateidx_fuzzy_pcmis_ref_pid
            ON rawPCMIS.dbo.CPFT_Referrals (PatientID);
        CREATE INDEX _crateidx_fuzzy_pcmis_ref_case
            ON rawPCMIS.dbo.CPFT_Referrals (CaseNumber);
        CREATE INDEX _crateidx_fuzzy_pcmis_ref_dx1
            ON rawPCMIS.dbo.CPFT_Referrals (PrimaryDiagnosis);
        CREATE INDEX _crateidx_fuzzy_pcmis_ref_dx2
            ON rawPCMIS.dbo.CPFT_Referrals (SecondaryDiagnosis);

    """
    sql = text(
        """
        SELECT
            -- TOP 0  -- for debugging

            -- From the main patient index:
            p.PatientID as pcmis_patient_id,  -- NVARCHAR(100) NOT NULL
            CAST(p.NHSNumber AS BIGINT) AS nhs_number,
            p.FirstName AS first_name,
            p.MiddleName AS middle_name,
            p.LastName AS surname,
            CAST(p.DOB AS DATE) AS dob,
            CASE p.Gender
                -- VARCHAR; possible values '0', '1', '2', '9'.
                -- https://www.datadictionary.nhs.uk/attributes/person_gender_code.html
                WHEN '1' THEN 'M'
                WHEN '2' THEN 'F'
                ELSE ''
                -- '0' = "not known"
                -- '9' = "not specified"
            END AS gender,
            p.Ethnicity AS ethnicity,  -- as a code
            p.PostCode AS postcode,
            p.PreviousPostCode AS prev_postcode,

            -- From the ONS postcode table:
            ons_current.imd AS index_of_multiple_deprivation,
            ons_previous.imd AS prev_index_of_multiple_deprivation,

            -- From the referrals table:
            CAST(r.ReferralDate AS DATE) AS first_mh_care_date,

            -- From diagnostic codes:
            -- Possibilities:
            -- CaseContactDetails.PrimaryDiagnosis -- ICD-10 with dot 
            -- IAPTDataReferral.ProvDiag -- empty
            -- CPFT_Referrals.PrimaryDiagnosis -- ICD-10 with dot
            -- ReferralDetails.PrimaryDiagnosis -- ICD-10 with dot
            -- ... and likewise SecondaryDiagnosis
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        rawPCMIS.dbo.CPFT_Referrals dx_any
                    WHERE
                        dx_any.PatientId = p.PatientId
                        AND (
                            dx_any.PrimaryDiagnosis IS NOT NULL
                            OR dx_any.SecondaryDiagnosis IS NOT NULL
                        )
                ) THEN 1
                ELSE 0
            END AS any_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        rawPCMIS.dbo.CPFT_Referrals dx_f
                    WHERE
                        dx_f.PatientId = p.PatientId
                        AND (
                            dx_f.PrimaryDiagnosis LIKE 'F%'
                            OR dx_f.SecondaryDiagnosis LIKE 'F%'
                        )
                ) THEN 1
                ELSE 0
            END AS chapter_f_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        rawPCMIS.dbo.CPFT_Referrals dx_smi
                    WHERE
                        dx_smi.PatientId = p.PatientId
                        AND (
                            -- To be more efficient: the dots are predictable,
                            -- so include in the query strings rather than 
                            -- using REPLACE().
                            dx_smi.PrimaryDiagnosis LIKE 'F20%'  -- schizophrenia
                            OR dx_smi.PrimaryDiagnosis LIKE 'F21%'  -- schizotypal
                            OR dx_smi.PrimaryDiagnosis LIKE 'F22%'  -- persistent delusional
                            OR dx_smi.PrimaryDiagnosis LIKE 'F25%'  -- schizoaffective
                            OR dx_smi.PrimaryDiagnosis LIKE 'F31%'  -- bipolar
                            OR dx_smi.PrimaryDiagnosis LIKE 'F32.2%'  -- severe depressive episode, not psychotic
                            OR dx_smi.PrimaryDiagnosis LIKE 'F32.3%'  -- severe depressive episode, psychotic
                            OR dx_smi.PrimaryDiagnosis LIKE 'F33.2%'  -- rec. dep, severe, not psychotic
                            OR dx_smi.PrimaryDiagnosis LIKE 'F33.3%'  -- rec. dep, severe, psychotic

                            OR dx_smi.SecondaryDiagnosis LIKE 'F20%'  -- schizophrenia
                            OR dx_smi.SecondaryDiagnosis LIKE 'F21%'  -- schizotypal
                            OR dx_smi.SecondaryDiagnosis LIKE 'F22%'  -- persistent delusional
                            OR dx_smi.SecondaryDiagnosis LIKE 'F25%'  -- schizoaffective
                            OR dx_smi.SecondaryDiagnosis LIKE 'F31%'  -- bipolar
                            OR dx_smi.SecondaryDiagnosis LIKE 'F32.2%'  -- severe depressive episode, not psychotic
                            OR dx_smi.SecondaryDiagnosis LIKE 'F32.3%'  -- severe depressive episode, psychotic
                            OR dx_smi.SecondaryDiagnosis LIKE 'F33.2%'  -- rec. dep, severe, not psychotic
                            OR dx_smi.SecondaryDiagnosis LIKE 'F33.3%'  -- rec. dep, severe, psychotic
                        )
                ) THEN 1
                ELSE 0
            END AS smi_icd10_dx_present

        FROM
            rawPCMIS.dbo.PatientDetails AS p  -- identifiable patient table
        LEFT OUTER JOIN
            onspd.dbo.postcode AS ons_current
            ON ons_current.pcd_nospace = REPLACE(UPPER(p.PostCode), ' ', '')
        LEFT OUTER JOIN
            onspd.dbo.postcode AS ons_previous
            ON ons_previous.pcd_nospace = REPLACE(
                UPPER(p.PreviousPostCode), ' ', ''
            )
        LEFT OUTER JOIN
            -- Finding the first referral.
            -- When ReferralDetails had 131973 records, so did CPFT_Referrals.
            -- ReferralDetails.CaseNumber is alphanumeric but unique.
            -- ReferralDetails.DateOfOnset is NULL much more often than not.
            -- ReferralDetails.ReferredToService is a service name, not a date.
            -- ReferralDetails contains no clear date field.
            -- CPFT_Referrals does.
            rawPCMIS.dbo.CPFT_Referrals AS r
            ON r.CaseNumber = (
                SELECT TOP 1
                    CaseNumber
                FROM
                    rawPCMIS.dbo.CPFT_Referrals AS r2
                WHERE
                    r2.PatientID = p.PatientID
                ORDER BY
                    r2.ReferralDate
            )
        WHERE
            -- Restrict to patients with NHS numbers:
            p.NHSNumber IS NOT NULL
            AND LEN(p.NHSNumber) = 10
            -- ... non-NULL values only have lengths 0 or 10
            AND TRY_CAST(p.NHSNumber AS BIGINT) IS NOT NULL

        -- Final count: 93347 (on 2022-05-26).
        -- Compare: SELECT COUNT(*) FROM rawPCMIS.dbo.PatientDetails = 94344.
    """  # noqa
    )
    _hash = Hasher(hash_key).hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    q = QueryColnames
    for row in result:
        pcmis_patient_id = row["pcmis_patient_id"]  # type: str
        nhs_number = row[q.NHS_NUMBER]
        middle_name = row[q.MIDDLE_NAME]
        dob = coerce_to_pendulum_date(row[q.DOB])
        gender = row[q.GENDER]
        first_mh_care_date = coerce_to_pendulum_date(row[q.FIRST_MH_CARE_DATE])

        postcodes = []  # type: List[PostcodeInfo]
        if row[q.PREV_POSTCODE] and POSTCODE_REGEX.match(row[q.PREV_POSTCODE]):
            postcodes.append(
                PostcodeInfo(
                    postcode=row[q.PREV_POSTCODE].upper(),
                    start_date=None,
                    end_date=None,
                    index_of_multiple_deprivation=row[
                        q.PREV_INDEX_OF_MULTIPLE_DEPRIVATION
                    ],
                )
            )
        if row[q.POSTCODE] and POSTCODE_REGEX.match(row[q.POSTCODE]):
            postcodes.append(
                PostcodeInfo(
                    postcode=row[q.POSTCODE].upper(),
                    start_date=None,
                    end_date=None,
                    index_of_multiple_deprivation=row[
                        q.INDEX_OF_MULTIPLE_DEPRIVATION
                    ],
                )
            )

        other = CPFTValidationExtras(
            hashed_nhs_number=_hash(nhs_number),
            blurred_dob=isoformat_optional_date(
                truncate_date_to_first_of_month(dob)
            ),
            gender=gender,
            ethnicity=row[q.ETHNICITY],
            index_of_multiple_deprivation=last_imd(postcodes),
            first_mh_care_date=isoformat_optional_date(first_mh_care_date),
            age_at_first_mh_care=age_years(dob, first_mh_care_date),
            any_icd10_dx_present=row[q.ANY_ICD10_DX_PRESENT],
            chapter_f_icd10_dx_present=row[q.CHAPTER_F_ICD10_DX_PRESENT],
            severe_mental_illness_icd10_dx_present=row[q.SMI_ICD10_DX_PRESENT],
        )
        p = BasePerson(
            local_id=pcmis_patient_id,
            other_info=other.json,
            first_name=row[q.FIRST_NAME] or "",
            middle_names=[middle_name] if middle_name else [],
            surname=row[q.SURNAME] or "",
            gender=gender,
            dob=isoformat_optional_date(dob),
            postcodes=postcode_temporal_identifiers(postcodes),
        )
        yield p


# -----------------------------------------------------------------------------
# SystmOne
# -----------------------------------------------------------------------------


def _get_systmone_postcodes(
    engine: Engine, systmone_patient_id: int
) -> List[PostcodeInfo]:
    """
    Fetches distinct valid time-stamped postcodes for a given person, from RiO.
    The most recent should be last.

    Args:
        engine:
            SQLAlchemy engine
        systmone_patient_id:
            SystmOne patient ID

    Returns:
        list: of postcodes in :class:`PostcodeInfo` format

    """
    sql = text(
        """
        SELECT DISTINCT
            TOP 0  -- for debugging

            -- From the identifiable address table:
            a.PostCode_NoSpaces AS postcode,
            CAST(a.DateEvent AS DATE) AS start_date,
            CAST(a.DateTo AS DATE) AS end_date,

            -- From the ONS postcode-to-IMD lookup:
            ons.imd AS index_of_multiple_deprivation,

            CASE
                WHEN CAST(a.DateTo AS DATE) IS NULL THEN 1 ELSE 0
            END AS end_date_is_null
        FROM
            SystmOne.dbo.S1_PatientAddress a
        LEFT OUTER JOIN
            onspd.dbo.postcode AS ons  -- Office for National Statistics
            ON ons.pcd_nospace = a.PostCode_NoSpaces
        WHERE
            a.IDPatient = :patient_id
            AND a.PostCode_NoSpaces IS NOT NULL
            AND LEN(a.PostCode_NoSpaces) >= 5  -- minimum for valid postcode
        ORDER BY
            -- You can use aliases in ORDER BY from SQL Server 2008 onwards.
            end_date_is_null,
            start_date,
            end_date,
            postcode
    """
    )
    rows = engine.execute(sql, patient_id=systmone_patient_id)
    q = QueryColnames
    postcodes = [
        PostcodeInfo(
            postcode=row[q.POSTCODE],
            start_date=coerce_to_pendulum_date(row[q.START_DATE]),
            end_date=coerce_to_pendulum_date(row[q.END_DATE]),
            index_of_multiple_deprivation=row[q.INDEX_OF_MULTIPLE_DEPRIVATION],
        )
        for row in rows
        if POSTCODE_REGEX.match(row[0])
    ]
    return postcodes


def validate_2_fetch_systmone(
    url: str, hash_key: str, echo: bool = False
) -> Generator[BasePerson, None, None]:
    """
    Generates IDENTIFIED people from CPFT's SystmOne source database.

    Args:
        url:
            SQLAlchemy URL.
        hash_key:
            Key for hashing NHS number (original ID) to research ID.
        echo:
            Echo SQL?

    Yields:
        :class:`Person` objects
    """
    sql = text(
        """
        SELECT
            -- TOP 0  -- for debugging
        
            -- From the main patient index:
            p.IDPatient as systmone_patient_id,  -- BIGINT NULL
            CAST(p.NHSNumber AS BIGINT) AS nhs_number,
            p.FirstName AS first_name,
            p.GivenName2 AS middle_name,
            p.Surname AS surname,
            CAST(p.DOB AS DATE) AS dob,
            CASE p.Gender
                WHEN 'F' THEN 'F'
                WHEN 'M' THEN 'M'
                WHEN 'I' THEN 'X'
                ELSE ''
                -- 'U' = "unknown"
            END AS gender,

            -- From the demographics table:
            d.Ethnicity AS ethnicity,

            -- From the referrals table:
            CAST(r.ReferralDateTime AS DATE) AS first_mh_care_date,

            -- From diagnostic codes:
            -- There are no dots in ICD-10 codes.
            -- Length is 4 or 5. Codes can be like this: 'F03X-'.
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        SystmOne.dbo.S1_Diagnosis dx_any
                    WHERE
                        dx_any.IDPatient = p.IDPatient
                        AND dx_any.CodeScheme = 'ICD-10'
                        AND dx_any.DateEnded IS NOT NULL  -- none in practice
                        -- DateEpisodeEnd is separate; that is sometimes
                        -- populated.
                        AND dx_any.CODE IS NOT NULL  -- none in practice
                ) THEN 1
                ELSE 0
            END AS any_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        SystmOne.dbo.S1_Diagnosis dx_f
                    WHERE
                        dx_f.IDPatient = p.IDPatient
                        AND dx_f.CodeScheme = 'ICD-10'
                        AND dx_f.DateEnded IS NOT NULL  -- none in practice
                        AND dx_f.CODE LIKE 'F%'
                ) THEN 1
                ELSE 0
            END AS chapter_f_icd10_dx_present,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        SystmOne.dbo.S1_Diagnosis dx_smi
                    WHERE
                        dx_smi.IDPatient = p.IDPatient
                        AND dx_smi.CodeScheme = 'ICD-10'
                        AND dx_smi.DateEnded IS NOT NULL  -- none in practice
                        AND (
                            dx_smi.CODE LIKE 'F20%'  -- schizophrenia
                            OR dx_smi.CODE LIKE 'F21%'  -- schizotypal
                            OR dx_smi.CODE LIKE 'F22%'  -- persistent delusional
                            OR dx_smi.CODE LIKE 'F25%'  -- schizoaffective
                            OR dx_smi.CODE LIKE 'F31%'  -- bipolar
                            OR dx_smi.CODE LIKE 'F322%'  -- severe depressive episode, not psychotic
                            OR dx_smi.CODE LIKE 'F323%'  -- severe depressive episode, psychotic
                            OR dx_smi.CODE LIKE 'F332%'  -- rec. dep, severe, not psychotic
                            OR dx_smi.CODE LIKE 'F333%'  -- rec. dep, severe, psychotic
                        )
                ) THEN 1
                ELSE 0
            END AS smi_icd10_dx_present

        FROM
            SystmOne.dbo.S1_Patient AS p  -- identifiable patient table
        LEFT OUTER JOIN
            SystmOne.dbo.S1_Demographics AS d
            ON d.IDPatient = p.IDPatient  -- 1:1 mapping
        LEFT OUTER JOIN
            SystmOne.dbo.S1_ReferralsIn AS r
            ON r.RowIdentifier = (
                -- The first mental health referral.
                SELECT TOP 1
                    RowIdentifier
                FROM
                    SystmOne.dbo.S1_ReferralsIn AS r2
                WHERE
                    r2.IDPatient = p.IDPatient
                    AND r2.IsMentalHealth = 1  -- 0 or 1
                ORDER BY
                    r2.ReferralDateTime
            )
        WHERE
            -- Restrict to patients with NHS numbers:
            p.NHSNumber IS NOT NULL
            AND LEN(p.NHSNumber) = 10
            AND TRY_CAST(p.NHSNumber AS BIGINT) IS NOT NULL

        -- Final count: 601755 (2022-05-26).
        -- Compare: SELECT COUNT(*) FROM SystmOne.dbo.S1_Patient = 607605.
    """  # noqa
    )
    _hash = Hasher(hash_key).hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    q = QueryColnames
    for row in result:
        systmone_patient_id = row["systmone_patient_id"]  # type: int
        assert systmone_patient_id is not None
        nhs_number = row[q.NHS_NUMBER]
        middle_name = row[q.MIDDLE_NAME]
        dob = coerce_to_pendulum_date(row[q.DOB])
        gender = row[q.GENDER]
        first_mh_care_date = coerce_to_pendulum_date(row[q.FIRST_MH_CARE_DATE])

        postcodes = _get_systmone_postcodes(engine, systmone_patient_id)

        other = CPFTValidationExtras(
            hashed_nhs_number=_hash(nhs_number),
            blurred_dob=isoformat_optional_date(
                truncate_date_to_first_of_month(dob)
            ),
            gender=gender,
            ethnicity=row[q.ETHNICITY],
            index_of_multiple_deprivation=last_imd(postcodes),
            first_mh_care_date=isoformat_optional_date(first_mh_care_date),
            age_at_first_mh_care=age_years(dob, first_mh_care_date),
            any_icd10_dx_present=row[q.ANY_ICD10_DX_PRESENT],
            chapter_f_icd10_dx_present=row[q.CHAPTER_F_ICD10_DX_PRESENT],
            severe_mental_illness_icd10_dx_present=row[q.SMI_ICD10_DX_PRESENT],
        )
        p = BasePerson(
            local_id=str(systmone_patient_id),
            other_info=other.json,
            first_name=row[q.FIRST_NAME] or "",
            middle_names=[middle_name] if middle_name else [],
            surname=row[q.SURNAME] or "",
            gender=gender,
            dob=isoformat_optional_date(dob),
            postcodes=postcode_temporal_identifiers(postcodes),
        )
        yield p


# -----------------------------------------------------------------------------
# Common functions
# -----------------------------------------------------------------------------


def save_people_from_db(
    people: Iterable[BasePerson], output_csv: str, report_every: int = 1000
) -> None:
    """
    Saves people (in plaintext) from a function that generates them from a
    database.

    Args:
        people:
            iterable of :class:`Person`
        output_csv:
            output filename
        report_every:
            report progress every n people
    """
    rownum = 0
    log.info(f"Saving to: {output_csv}")
    with open(output_csv, "wt") as f:
        for i, p in enumerate(people):
            if i == 0:
                # This allows us to do custom headers for "other" info
                writer = csv.DictWriter(
                    f, fieldnames=p.plaintext_csv_columns()
                )
                writer.writeheader()
            writer.writerow(p.plaintext_csv_dict())
            rownum += 1
            if rownum % report_every == 0:
                log.info(f"Processing person #{rownum}")
    log.info("... finished saving.")


# =============================================================================
# Command-line entry point
# =============================================================================

# -----------------------------------------------------------------------------
# Constants and helper functions for help text
# -----------------------------------------------------------------------------

CAMBS_POPULATION = 852523
# ... 2018 estimate; https://cambridgeshireinsight.org.uk/population/

CDL = "cdl"
RIO = "rio"
PCMIS = "pcmis"
SYSTMONE = "systmone"
ALL_DATABASES = (CDL, RIO, PCMIS, SYSTMONE)
HASHKEY_ENVVAR = "CRATE_FUZZY_HASH_KEY"


def v2_plaintext(database: str) -> str:
    """
    A default filename.
    """
    return f"fuzzy_data_{database}_DANGER_IDENTIFIABLE.csv"


def v2_hashed(database: str) -> str:
    """
    A default filename.
    """
    return f"fuzzy_data_{database}_hashed.csv"


def v2_outplain(probands: str, sample: str) -> str:
    """
    A default filename.
    """
    return f"fuzzy_compare_{probands}_to_{sample}_plaintext.csv"


def v2_outhashed(probands: str, sample: str) -> str:
    """
    A default filename.
    """
    return f"fuzzy_compare_{probands}_to_{sample}_hashed.csv"


def help_v2_fetch() -> str:
    """
    Help string for fetching data from all sources.
    """
    return "\n".join(
        f"""        validate_fuzzy_linkage.py validate2_fetch_{db} ^
            --output {v2_plaintext(db)} ^
            --url <SQLALCHEMY_URL>"""
        for db in ALL_DATABASES
    )


def help_v2_hash() -> str:
    """
    Help string for hashing data from all sources.
    """
    return "\n".join(
        f'''        crate_fuzzy_id_match hash ^
            --input {v2_plaintext(db)} ^
            --output {v2_hashed(db)} ^
            --include_other_info ^
            --key "%{HASHKEY_ENVVAR}%"'''
        for db in ALL_DATABASES
    )


def help_v2_compare(plaintext: bool) -> str:
    """
    Help string for comparing data from all sources.
    """
    if plaintext:
        command = "compare_plaintext"
        source_fn = v2_plaintext
        out_fn = v2_outplain
    else:
        command = "compare_hashed_to_hashed"
        source_fn = v2_hashed
        out_fn = v2_outhashed
    return "\n".join(
        f"""        crate_fuzzy_id_match {command} ^
            --population_size {CAMBS_POPULATION} ^
            --probands {source_fn(db1)} ^
            --sample {source_fn(db2)} ^
            --output {out_fn(db1, db2)} ^
            --extra_validation_output"""
        for db1 in ALL_DATABASES
        for db2 in ALL_DATABASES
        if db1 != db2
    )


# -----------------------------------------------------------------------------
# Long help strings
# -----------------------------------------------------------------------------

HELP_VALIDATE_1 = f"""
    Takes an identifiable list of people (typically a short list of imaginary
    people!) and validates the matching process.

    This is done by splitting the input list into two groups (alternating),
    then comparing a list of probands either against itself (there should be
    matches) or against the other group (there should generally not be). The
    process is carried out in cleartext (plaintext) and in a hashed form. At
    times it's made harder by introducing deletions or mutations (typos) into
    one of the groups.

    Here's a specimen test CSV file to use, with entirely made-up people and
    institutional (not personal) postcodes in Cambridge:

{get_demo_csv()}

    Explanation of the output format:

    {ValidationOutputColnames.COLLECTION_NAME}:
        A human-readable name summarizing the next four.
    {ValidationOutputColnames.IN_SAMPLE}:
        (Boolean) Whether the probands are in the sample.
    {ValidationOutputColnames.DELETIONS}:
        (Boolean) Whether random items have been deleted from the probands.
    {ValidationOutputColnames.TYPOS}:
        (Boolean) Whether random typos have been made in the probands.

    {ValidationOutputColnames.IS_HASHED}:
        (Boolean) Whether the proband and sample are hashed.
    {ValidationOutputColnames.PROBAND_ID}:
        The gold-standard ID of the proband. ***
    {ValidationOutputColnames.WINNER_ID}:
        The *** ID of the best-matching person in the sample if they were a
        good enough match to win.
    {ValidationOutputColnames.BEST_MATCH_ID}:
        The *** ID of the best-matching person in the sample.
    {ValidationOutputColnames.BEST_LOG_ODDS}:
        The calculated log (ln) odds that the proband and the sample member
        identified by 'winner_id' are the sample person (ideally high if there
        is a true match, low if not).
    {ValidationOutputColnames.SECOND_BEST_LOG_ODDS}:
        The calculated log odds of the proband and the runner-up being the same
        person (ideally low).
    {ValidationOutputColnames.SECOND_BEST_MATCH_ID}:
        The ID of the second-best matching person, if there is one.

    {ValidationOutputColnames.CORRECT_IF_WINNER}:
        (Boolean) Whether the proband and winner IDs are the same (ideally
        true).
    {ValidationOutputColnames.LEADER_ADVANTAGE}:
        The log odds by which the winner beats the runner-up (ideally high,
        indicating a strong preference for the winner over the runner-up).

    Clearly, if the probands are in the sample, then a match may occur; if not,
    no match should occur. If hashing is in use, this tests de-identified
    linkage; if not, this tests identifiable linkage. Deletions and typos may
    reduce (but we hope not always eliminate) the likelihood of a match, and we
    don't want to see mismatches.

    For n input rows, each basic set test involves n^2/2 comparisons. Then we
    repeat for typos and deletions. (There is no point in DOB typos as our
    rules preclude that.)

    Examine:
    - P(unique plaintext match | proband in sample) -- should be close to 1.
    - P(unique plaintext match | proband in others) -- should be close to 0.
    - P(unique hashed match | proband in sample) -- should be close to 1.
    - P(unique hashed match | proband in others) -- should be close to 0.
"""

HELP_VALIDATE_2_CDL = f"""
    Validation #2. Sequence (using Windows command-line syntax):

    0. Setup

        set {HASHKEY_ENVVAR}=<SOME_SECRET_KEY>

    1. Fetch

{help_v2_fetch()}

    2. Hash

{help_v2_hash()}

    3. Compare.

{help_v2_compare(plaintext=True)}

{help_v2_compare(plaintext=False)}
"""


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    """
    Command-line entry point.
    """

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Argument parser
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Validate identity matching via hashed fuzzy identifiers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = add_subparsers(parser)
    base_subparser = get_basic_options_subparser()
    hasher_subparser = get_hasher_option_subparser()
    config_subparser = get_config_option_subparser()
    all_parents = [base_subparser, hasher_subparser, config_subparser]
    dbfetch_parents = [base_subparser, hasher_subparser]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # speedtest command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    speedtest_parser = subparsers.add_parser(
        "speedtest",
        help="Run speed tests and stop",
        parents=all_parents,
        description="""
        This will run several comparisons to test hashing and comparison
        speed. Results are reported as microseconds per comparison.
        """,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    speedtest_parser.add_argument(
        "--profile",
        action="store_true",
        help="Profile (makes things slower but shows you what's taking the "
        "time).",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # validate1 command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    validate1_parser = subparsers.add_parser(
        "validate1",
        help="Run validation test 1 and stop. In this test, a list of people "
        "is compared to a version of itself, at times with elements "
        "deleted or with typos introduced.",
        parents=all_parents,
        description=HELP_VALIDATE_1,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    validate1_parser.add_argument(
        "--people",
        type=str,
        required=True,
        help="CSV filename for validation 1 data. "
        + Person.PLAINTEXT_CSV_FORMAT_HELP,
    )
    validate1_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help=(
            f"Output CSV file for validation. Header row present. Columns: "
            f"{VALIDATION_OUTPUT_COLNAMES}."
        ),
    )
    validate1_parser.add_argument(
        "--seed",
        type=int,
        default=1234,
        help="Random number seed, for introducing deliberate errors in "
        "validation test 1",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # validate2 and ancillary commands
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _add_validate2_elements(parser_: argparse.ArgumentParser) -> None:
        """
        Adds common options.
        """
        parser_.add_argument(
            "--url",
            type=str,
            required=True,
            help="SQLAlchemy URL for source (IDENTIFIABLE) database",
        )
        parser_.add_argument("--echo", action="store_true", help="Echo SQL?")
        parser_.add_argument(
            "--output",
            type=str,
            required=True,
            help="CSV filename for output (plaintext, IDENTIFIABLE) data. "
            + Person.PLAINTEXT_CSV_FORMAT_HELP,
        )

    # CDL
    validate2_cdl_parser = subparsers.add_parser(
        "validate2_fetch_cdl",
        help="Validation 2A: fetch people from CPFT CDL database",
        parents=dbfetch_parents,
        description=HELP_VALIDATE_2_CDL,
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    _add_validate2_elements(validate2_cdl_parser)

    # RiO
    validate2_rio_parser = subparsers.add_parser(
        "validate2_fetch_rio",
        help="Validation 2B: fetch people from CPFT RiO database",
        parents=dbfetch_parents,
        description="See validate2_fetch_cdl command.",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    _add_validate2_elements(validate2_rio_parser)

    # PCMIS
    validate2_pcmis_parser = subparsers.add_parser(
        "validate2_fetch_pcmis",
        help="Validation 2C: fetch people from CPFT PCMIS database",
        parents=dbfetch_parents,
        description="See validate2_fetch_cdl command.",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    _add_validate2_elements(validate2_pcmis_parser)

    # SystmOne
    validate2_systmone_parser = subparsers.add_parser(
        "validate2_fetch_systmone",
        help="Validation 2B: fetch people from CPFT SystmOne database",
        parents=dbfetch_parents,
        description="See validate2_fetch_cdl command.",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    _add_validate2_elements(validate2_systmone_parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Parse arguments and set up
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Run a command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    log.info(f"Command: {args.command}")

    if args.command == "speedtest":
        cfg = get_cfg_from_args(args)
        fn = do_cprofile(speedtest) if args.profile else speedtest
        fn(cfg)

    elif args.command == "validate1":
        cfg = get_cfg_from_args(args)
        log.info("Running validation test 1.")
        validate_1(
            cfg,
            people_csv=args.people,
            output_csv=args.output,
            seed=args.seed,
        )
        log.info("Validation test 1 complete.")

    elif args.command == "validate2_fetch_cdl":
        warn_or_fail_if_default_key(args)
        save_people_from_db(
            people=validate_2_fetch_cdl(
                url=args.url, hash_key=args.key, echo=args.echo
            ),
            output_csv=args.output,
        )

    elif args.command == "validate2_fetch_rio":
        warn_or_fail_if_default_key(args)
        save_people_from_db(
            people=validate_2_fetch_rio(
                url=args.url, hash_key=args.key, echo=args.echo
            ),
            output_csv=args.output,
        )

    elif args.command == "validate2_fetch_pcmis":
        warn_or_fail_if_default_key(args)
        save_people_from_db(
            people=validate_2_fetch_pcmis(
                url=args.url, hash_key=args.key, echo=args.echo
            ),
            output_csv=args.output,
        )

    elif args.command == "validate2_fetch_systmone":
        warn_or_fail_if_default_key(args)
        save_people_from_db(
            people=validate_2_fetch_systmone(
                url=args.url, hash_key=args.key, echo=args.echo
            ),
            output_csv=args.output,
        )

    else:
        # Shouldn't get here.
        log.error(f"Unknown command: {args.command}")
        return EXIT_FAILURE

    log.info(f"... command {args.command} finished.")

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
