#!/usr/bin/env python

"""
crate_anon/linkage/validation/validate_fuzzy_linkage.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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
    result <- optim(par=50, fn=errfunc)  # minimize error, start n=50; gives 26825

"""  # noqa

import argparse
from collections import OrderedDict
import csv
import logging
import math
import pdb
import random
import sys
import timeit
from typing import (
    Generator,
    Iterable,
    List,
    Tuple,
    TYPE_CHECKING,
)

from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
    ShowAllSubparserHelpAction,
)
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.profile import do_cprofile
from pendulum import Date
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.result import ResultProxy
from sqlalchemy.sql import text

from crate_anon.common.constants import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
)
from crate_anon.linkage.fuzzy_id_match import (
    add_common_groups,
    cache_load,
    cache_save,
    DEMO_SAMPLE,
    get_cfg_from_args,
    Hasher,
    MatchConfig,
    People,
    Person,
    POSTCODE_REGEX,
    read_people_2,
    TemporalIdentifier,
    warn_or_fail_if_default_key,
)

if TYPE_CHECKING:
    # noinspection PyProtectedMember,PyUnresolvedReferences
    from argparse import _SubParsersAction

log = logging.getLogger(__name__)


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
        original_id=1,
        first_name="Alice",
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=[p1],
    )
    alice_smith_1930 = Person(
        cfg=cfg,
        original_id=8,
        first_name="Alice",
        surname="Smith",
        dob="1930-01-01",
    )
    alice_smith_2000 = Person(
        cfg=cfg,
        original_id=9,
        first_name="Alice",
        surname="Smith",
        dob="2000-01-01",
    )
    alice_smith = Person(
        cfg=cfg,
        original_id=10,
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
            "alice_bcd_unique_2000_add.log_odds_same(alice_bcd_unique_2000_add)",  # noqa
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
            "alice_bcd_unique_2000_add.hashed().log_odds_same(alice_bcd_unique_2000_add.hashed())",  # noqa
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
            "alice_smith_1930.hashed().log_odds_same(alice_smith_2000.hashed())",  # noqa
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
                "hashed_alice_smith_1930.log_odds_same(hashed_alice_smith_1930)"  # noqa: E501
            ),
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(
        f"Compare two identical hashed objects: {t} μs per comparison"
    )  # noqa
    # On Wombat 2020-04-024: 21.7 microseconds.

    t = (
        microsec_per_sec
        * timeit.timeit(
            (
                "hashed_alice_smith_1930.log_odds_same(hashed_alice_smith_2000)"  # noqa: E501
            ),
            number=n_for_speedtest,
            globals=locals(),
        )
        / n_for_speedtest
    )
    log.info(
        f"Compare two DOB-mismatched hashed objects: {t} μs per comparison"
    )  # noqa
    # On Wombat 2020-04-024: 6.4 microseconds.


# =============================================================================
# Validation 1
# =============================================================================


def make_deletion_data(people: People, cfg: MatchConfig) -> People:
    """
    Makes a copy of the supplied data set with deliberate deletions applied.

    Surnames and DOBs are excepted as we require exact matches for those.
    """
    deletion_data = People(cfg)
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
    typo_data = People(cfg)
    log.debug(f"Making typo data for {people.size()} people")
    for person in people.people:
        modified_person = person.copy()
        modified_person.debug_mutate_something()
        log.debug(f"Mutated:\nFROM: {person}\nTO  : {modified_person}")
        typo_data.add_person(modified_person)
    return typo_data


VALIDATION_OUTPUT_COLNAMES = [
    "collection_name",
    "in_sample",
    "deletions",
    "typos",
    "is_hashed",
    "original_id",
    "winner_id",
    "best_match_id",
    "best_log_odds",
    "second_best_log_odds",
    "second_best_match_id",
    "correct_if_winner",
    "leader_advantage",
]
VALIDATION_OUTPUT_CSV_HELP = (
    f"Header row present. Columns: {VALIDATION_OUTPUT_COLNAMES}."
)


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
        ),  # noqa
        (
            out_deletions_hashed,
            "out_deletions_hashed",
            in_hashed,
            False,
            True,
            False,
        ),  # noqa
        (in_typos, "in_typos", in_plaintext, True, False, True),
        (out_typos, "out_typos", in_plaintext, False, False, True),
        (in_typos_hashed, "in_typos_hashed", in_hashed, True, False, True),
        (out_typos_hashed, "out_typos_hashed", in_hashed, False, False, True),
    ]  # type: List[Tuple[People, str, People, bool, bool, bool]]
    log.info(f"Writing to: {output_csv}")
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
        ) in data:  # noqa
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
                    result.best_person.original_id
                    if result.best_person
                    else None
                )
                correct_if_winner = (
                    int(best_match_id == person.original_id)
                    if result.winner
                    else None
                )

                rowdata = dict(
                    # As of Python 3.6, keyword order is preserved:
                    # https://docs.python.org/3/library/collections.html#collections.OrderedDict  # noqa
                    # https://www.python.org/dev/peps/pep-0468/
                    # ... but it doesn't matter since we're using a DictWriter.
                    collection_name=collection_name,
                    in_sample=int(in_sample),
                    deletions=int(deletions),
                    typos=int(typos),
                    is_hashed=int(person.is_hashed),
                    original_id=person.original_id,
                    winner_id=(
                        result.winner.original_id if result.winner else None
                    ),
                    best_match_id=best_match_id,
                    best_log_odds=result.best_log_odds,
                    second_best_log_odds=result.second_best_log_odds,
                    second_best_match_id=(
                        result.second_best_person.original_id
                        if result.second_best_person
                        else None
                    ),
                    correct_if_winner=correct_if_winner,
                    leader_advantage=leader_advantage,
                )
                writer.writerow(rowdata)
    log.info("... done")


# =============================================================================
# Validation 2
# =============================================================================

# -----------------------------------------------------------------------------
# CRS/CDL
# -----------------------------------------------------------------------------


def _get_cdl_postcodes(
    engine: Engine, cdl_m_number: int
) -> List[TemporalIdentifier]:
    """
    Fetches distinct valid time-stamped postcodes for a given person, from
    CRS/CDL.

    Args:
        engine:
            SQLAlchemy engine
        cdl_m_number:
            CRS/CDL primary key ("M number")

    Returns:
        list: of postcodes in :class:`TemporalIdentifier` format
    """
    log.critical("_get_cdl_postcodes: needs to be checked")
    sql = text(
        """

        SELECT DISTINCT
            UPPER(PostCode) AS upper_postcode,
            CAST(StartDate AS DATE) AS start_date,
            CAST(EndDate AS DATE) AS end_date
        FROM
            Addresses A
        WHERE
            ClientID = :cdl_m_number
            AND PostCode IS NOT NULL
            AND LEN(PostCode) >= 6  -- minimum for valid postcode
        ORDER BY
            start_date,
            end_date,
            upper_postcode

    """
    )
    rows = engine.execute(sql, cdl_m_number=cdl_m_number)
    postcodes = [
        TemporalIdentifier(
            identifier=row[0], start_date=row[1], end_date=row[2]  # postcode
        )
        for row in rows
        if POSTCODE_REGEX.match(row[0])
    ]
    return postcodes


# noinspection PyUnusedLocal
def _get_cdl_middle_names(engine: Engine, cdl_m_number: int) -> List[str]:
    """
    Fetches distinct middle names for a given person, from CRS/CDL.

    Args:
        engine:
            SQLAlchemy engine
        cdl_m_number:
            CRS/CDL primary key ("M number")

    Returns:
        list: of middle names

    """
    log.critical("_get_cdl_middle_names: needs to be checked")
    return []  # Information not present in database!


def validate_2_fetch_cdl(
    cfg: MatchConfig, url: str, hash_key: str, echo: bool = False
) -> Generator[Person, None, None]:
    """
    Generates IDENTIFIED people from CPFT's CRS/CRL source database.

    See :func:`validate_2_fetch_rio` for notes.
    """
    log.critical("validate_2_fetch_cdl: needs to be checked")
    sql = text(
        """

        SELECT
            p.Patient_ID AS cdl_m_number,
            CAST(p.NHS_IDENTIFIER AS BIGINT) AS nhs_number,
            p.FORENAME AS first_name,
            p.SURNAME AS surname,
            CASE p.GENDER
                WHEN 'Female' THEN 'F'
                WHEN 'Male' THEN 'M'
                WHEN 'Not Specified' THEN 'X'
                ELSE ''
                -- 'Not Known' is the CRS/CDL "unknown" value
            END AS gender,
            CAST(p.DTTM_OF_BIRTH, DATE) AS dob,
            p.ETHNICITY AS ethnicity,  -- see also CDLPatient.Ethnicity
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        DIAGNOSIS_PROCEDURES dp
                    WHERE
                        dp.Patient_ID = p.Patient_ID
                        AND dc.CODE IS NOT NULL
                ) THEN 1
                ELSE 0
            END AS icd10_dx_present,
            CAST(p.CREATE_DTTM AS DATE) AS first_registration_date
        FROM
            PATIENTS as p

    """
    )
    hasher = Hasher(hash_key)
    _hash = hasher.hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    for row in result:
        cdl_m_number = row["cdl_m_number"]
        middle_names = _get_cdl_middle_names(engine, cdl_m_number)
        postcodes = _get_cdl_postcodes(engine, cdl_m_number)
        nhs_number = row["nhs_number"]
        research_id = _hash(nhs_number)
        other = OrderedDict()
        dob = row["dob"]
        first_mh_care_date = row["first_registration_date"]
        other["first_mh_care_date"] = first_mh_care_date
        other["age_at_first_mh_care"] = (
            (first_mh_care_date - dob).in_years()
            if dob and first_mh_care_date
            else None
        )
        other["ethnicity"] = row["ethnicity"]
        other["icd10_dx_present"] = row["icd10_dx_present"]
        p = Person(
            cfg=cfg,
            original_id=nhs_number,
            research_id=research_id,
            first_name=row["first_name"] or "",
            middle_names=middle_names,
            surname=row["surname"] or "",
            gender=row["gender"] or "",
            dob=row["dob"] or "",
            postcodes=postcodes,
            other=other,
        )
        yield p


# -----------------------------------------------------------------------------
# RiO
# -----------------------------------------------------------------------------


def _get_rio_postcodes(
    engine: Engine, rio_client_id: str
) -> List[TemporalIdentifier]:
    """
    Fetches distinct valid time-stamped postcodes for a given person, from RiO.

    Args:
        engine:
            SQLAlchemy engine
        rio_client_id:
            RiO primary key (``ClientId``)

    Returns:
        list: list: of postcodes in :class:`TemporalIdentifier` format

    """
    log.critical("_get_rio_postcodes: needs to be checked")
    sql = text(
        """

        SELECT DISTINCT
            UPPER(PostCode) AS upper_postcode,
            CAST(FromDate AS DATE) AS start_date,
            CAST(ToDate AS DATE) AS end_date
        FROM
            ClientAddress
        WHERE
            ClientID = :client_id
            AND PostCode IS NOT NULL
            AND LEN(PostCode) >= 6  -- minimum for valid postcode
        ORDER BY
            start_date,
            end_date,
            upper_postcode

    """
    )
    rows = engine.execute(sql, client_id=rio_client_id)
    postcodes = [
        TemporalIdentifier(
            identifier=row[0], start_date=row[1], end_date=row[2]  # postcode
        )
        for row in rows
        if POSTCODE_REGEX.match(row[0])
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

    """
    log.critical("_get_rio_middle_names: needs to be checked")
    sql = text(
        """

        SELECT
            -- OK to use UPPER() with NULL values. Result is, of course, NULL.
            -- GivenName1 should be the first name.
            UPPER(GivenName2) AS middle_name_1,
            UPPER(GivenName3) AS middle_name_2,
            UPPER(GivenName4) AS middle_name_3,
            UPPER(GivenName5) AS middle_name_4
        FROM
            ClientName
        WHERE
            ClientID = :client_id

    """
    )
    rows = engine.execute(sql, client_id=rio_client_id)
    assert len(rows) == 1, "Didn't expect >1 row per patient in ClientName"
    row = rows[0]
    middle_names = [x for x in row if x]  # remove blanks
    return middle_names


def validate_2_fetch_rio(
    cfg: MatchConfig, url: str, hash_key: str, echo: bool = False
) -> Generator[Person, None, None]:
    """
    Generates IDENTIFIED people from CPFT's RiO source database.

    The connection to any such database is HIGHLY confidential; it sits on a
    secure server within a secure network and access to this specific database
    is very restricted -- to administrators only.

    Args:
        cfg:
            Configuration object.
        url:
            SQLAlchemy URL.
        hash_key:
            Key for hashing NHS number (original ID) to research ID.
        echo:
            Echo SQL?

    Yields:
        :class:`Person` objects

    Generating postcodes in SQL as semicolon-separated values: pretty hard.
    The challenges are:

    - String concatenation

      - Prior to SQL Server 2017:
        https://stackoverflow.com/questions/6899/how-to-create-a-sql-server-function-to-join-multiple-rows-from-a-subquery-into

        .. code-block:: none

            SELECT
                CAST(ci.NNN AS BIGINT) AS original_id,  -- NHS number
                -- ...

                STUFF(
                    (
                        SELECT
                            ';' + ca.PostCode
                        FROM
                            ClientAddress AS ca
                        WHERE
                            ca.ClientID = ci.ClientID
                            AND ca.PostCode IS NOT NULL
                            AND ca.PostCode != ''
                        FOR XML PATH('')
                    ),
                    1, 1, ''
                ) AS postcodes
            FROM
                ClientIndex AS ci

      - From SQL Server 2017: the ``STRING_AGG(..., ';')`` construct.
        Still tricky, though.

    - We need to return people with no postcodes.

    - We must deal with a profusion of invalid postcodes -- and SQL Server
      doesn't support proper regular expressions.

    SQLAlchemy Core query to Python dict:

    - https://stackoverflow.com/questions/1958219/convert-sqlalchemy-row-object-to-python-dict

    SQL Server doesn't permit "SELECT EXISTS":

    - https://stackoverflow.com/questions/2759756/is-it-possible-to-select-exists-directly-as-a-bit

    """  # noqa
    log.critical("validate_2_fetch_rio: needs to be checked")
    sql = text(
        """

        -- We use the original raw RiO database, not the CRATE-processed one.

        SELECT
            ci.ClientID AS rio_client_id,
            CAST(ci.NNN AS BIGINT) AS nhs_number,
            ci.Firstname AS first_name,
            ci.Surname AS surname,
            CASE ci.Gender
                WHEN 'F' THEN 'F'
                WHEN 'M' THEN 'M'
                WHEN 'X' THEN 'X'
                ELSE ''
                -- 'U' is the RiO "unknown" value
            END AS gender,
            CAST(ci.DateOfBirth AS DATE) AS dob,
            ge.CodeDescription AS ethnicity,
            CASE
                WHEN EXISTS(
                    SELECT
                        1
                    FROM
                        DiagnosisClient dc
                    WHERE
                        dc.ClientID = ci.ClientID
                        AND dc.RemovalDate IS NOT NULL
                ) THEN 1
                ELSE 0
            END AS icd10_dx_present,
            CAST(ci.FirstCareDate AS DATE) AS first_mh_care_date
        FROM
            ClientIndex AS ci
        LEFT JOIN
            GenEthnicity ge
            ON ge.Code = ci.Ethnicity
            AND ge.Deleted = 0
        WHERE
            -- Restrict to patients with NHS numbers:
            (ci.NNNStatus = 1 OR ci.NNNStatus = 2)
            AND NOT (ci.NNN IS NULL OR ci.NNN = '')
            -- 2 = NHS number verified; see table NNNStatus
            -- Most people have status 1 (about 119k people), compared to
            -- about 80k for status 2 (on 2020-04-28). Then about 6k have
            -- status 0 ("trace/verification required"), and about 800 have
            -- status 3 ("no match found"). Other codes not present.
            -- A very small number (~40) have a null NHS number despite an
            -- OK-looking status flag; we'll skip them.

    """
    )
    hasher = Hasher(hash_key)
    _hash = hasher.hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    for row in result:
        rio_client_id = row["rio_client_id"]
        middle_names = _get_rio_middle_names(engine, rio_client_id)
        postcodes = _get_rio_postcodes(engine, rio_client_id)
        nhs_number = row["nhs_number"]
        research_id = _hash(nhs_number)
        other = OrderedDict()
        dob = row["dob"]
        first_mh_care_date = row["first_mh_care_date"]
        other["first_mh_care_date"] = first_mh_care_date
        other["age_at_first_mh_care"] = (
            (first_mh_care_date - dob).in_years()
            if dob and first_mh_care_date
            else None
        )
        other["ethnicity"] = row["ethnicity"]
        other["icd10_dx_present"] = row["icd10_dx_present"]
        p = Person(
            cfg=cfg,
            original_id=nhs_number,
            research_id=research_id,
            first_name=row["first_name"] or "",
            middle_names=middle_names,
            surname=row["surname"] or "",
            gender=row["gender"] or "",
            dob=row["dob"] or "",
            postcodes=postcodes,
            other=other,
        )
        yield p


# -----------------------------------------------------------------------------
# Comon functions
# -----------------------------------------------------------------------------


def save_people_from_db(
    people: Iterable[Person], output_csv: str, report_every: int = 1000
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
    with open(output_csv, "wt") as f:
        for i, p in enumerate(people):
            if i == 0:
                # This allows us to do custom headers for "other" info
                writer = csv.DictWriter(
                    f, fieldnames=p.plaintext_csv_columns()
                )  # noqa
                writer.writeheader()
            writer.writerow(p.plaintext_csv_dict())
            rownum += 1
            if rownum % report_every == 0:
                log.info(f"Processing person #{rownum}")


# =============================================================================
# Long help strings
# =============================================================================

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

{DEMO_SAMPLE}

    Explanation of the output format:

    collection_name:
        A human-readable name summarizing the next four.
    in_sample:
        (Boolean) Whether the probands are in the sample.
    deletions:
        (Boolean) Whether random items have been deleted from the probands.
    typos:
        (Boolean) Whether random typos have been made in the probands.

    is_hashed:
        (Boolean) Whether the proband and sample are hashed.
    original_id:
        The gold-standard ID of the proband.
    winner_id:
        The ID of the best-matching person in the sample if they were a good
        enough match to win.
    best_match_id:
        The ID of the best-matching person in the sample.
    best_log_odds:
        The calculated log (ln) odds that the proband and the sample member
        identified by 'winner_id' are the sample person (ideally high if there
        is a true match, low if not).
    second_best_log_odds:
        The calculated log odds of the proband and the runner-up being the same
        person (ideally low).
    second_best_match_id:
        The ID of the second-best matching person, if there is one.

    correct_if_winner:
        (Boolean) Whether the proband and winner IDs are the same (ideally
        true).
    leader_advantage:
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

DEFAULT_CDL_PLAINTEXT = "validate2_cdl_DANGER_IDENTIFIABLE.csv"
DEFAULT_RIO_PLAINTEXT = "validate2_rio_DANGER_IDENTIFIABLE.csv"
DEFAULT_CDL_HASHED = "validate2_cdl_hashed.csv"
DEFAULT_RIO_HASHED = "validate2_rio_hashed.csv"
CAMBS_POPULATION = 852523  # 2018 estimate; https://cambridgeshireinsight.org.uk/population/  # noqa
HELP_VALIDATE_2_CDL = f"""
    Validation #2. Sequence:

    1. Fetch

    - crate_fuzzy_id_match validate2_fetch_cdl --output {DEFAULT_CDL_PLAINTEXT} --url <SQLALCHEMY_URL_CDL>
    - crate_fuzzy_id_match validate2_fetch_rio --output {DEFAULT_RIO_PLAINTEXT} --url <SQLALCHEMY_URL_RIO>

    2. Hash

    - crate_fuzzy_id_match hash --input {DEFAULT_CDL_PLAINTEXT} --output {DEFAULT_CDL_HASHED} --include_original_id --allow_default_hash_key
    - crate_fuzzy_id_match hash --input {DEFAULT_RIO_PLAINTEXT} --output {DEFAULT_RIO_HASHED} --include_original_id --allow_default_hash_key

    3. Compare

    - crate_fuzzy_id_match compare_plaintext --population_size {CAMBS_POPULATION} --probands {DEFAULT_CDL_PLAINTEXT} --sample {DEFAULT_RIO_PLAINTEXT} --output cdl_to_rio_plaintext.csv --extra_validation_output
    - crate_fuzzy_id_match compare_hashed_to_hashed --population_size {CAMBS_POPULATION} --probands {DEFAULT_CDL_HASHED} --sample {DEFAULT_RIO_HASHED} --output cdl_to_rio_hashed.csv --extra_validation_output
    - crate_fuzzy_id_match compare_plaintext --population_size {CAMBS_POPULATION} --probands {DEFAULT_RIO_PLAINTEXT} --sample {DEFAULT_CDL_PLAINTEXT} --output rio_to_cdl_plaintext.csv --extra_validation_output
    - crate_fuzzy_id_match compare_hashed_to_hashed --population_size {CAMBS_POPULATION} --probands {DEFAULT_RIO_HASHED} --sample {DEFAULT_CDL_HASHED} --output rio_to_cdl_hashed.csv --extra_validation_output
"""  # noqa


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """
    Command-line entry point.
    """

    # -------------------------------------------------------------------------
    # Argument parser
    # -------------------------------------------------------------------------

    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Validate identity matching via hashed fuzzy identifiers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--allhelp",
        action=ShowAllSubparserHelpAction,
        help="show help for all commands and exit",
    )

    # -------------------------------------------------------------------------
    # Common arguments
    # -------------------------------------------------------------------------

    add_common_groups(parser)

    # -------------------------------------------------------------------------
    # Subcommand subparser
    # -------------------------------------------------------------------------

    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid commands are as follows.",
        help="Specify one command.",
        dest="command",  # sorts out the help for the command being mandatory
    )  # type: _SubParsersAction  # noqa
    subparsers.required = True  # requires a command

    # -------------------------------------------------------------------------
    # speedtest command
    # -------------------------------------------------------------------------

    speedtest_parser = subparsers.add_parser(
        "speedtest",
        help="Run speed tests and stop",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
        This will run several comparisons to test hashing and comparison
        speed. Results are reported as microseconds per comparison.
        """,
    )
    speedtest_parser.add_argument(
        "--profile",
        action="store_true",
        help="Profile (makes things slower but shows you what's taking the "
        "time).",
    )

    # -------------------------------------------------------------------------
    # validate1 command
    # -------------------------------------------------------------------------

    validate1_parser = subparsers.add_parser(
        "validate1",
        help="Run validation test 1 and stop. In this test, a list of people "
        "is compared to a version of itself, at times with elements "
        "deleted or with typos introduced.",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_VALIDATE_1,
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
        help="Output CSV file for validation. " + VALIDATION_OUTPUT_CSV_HELP,
    )
    validate1_parser.add_argument(
        "--seed",
        type=int,
        default=1234,
        help="Random number seed, for introducing deliberate errors in "
        "validation test 1",
    )

    # -------------------------------------------------------------------------
    # validate2 and ancillary commands
    # -------------------------------------------------------------------------

    validate2_cdl_parser = subparsers.add_parser(
        "validate2_fetch_cdl",
        help="Validation 2A: fetch people from CPFT CDL database",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_VALIDATE_2_CDL,
    )
    validate2_cdl_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="SQLAlchemy URL for CPFT CDL source (IDENTIFIABLE) database",
    )
    validate2_cdl_parser.add_argument(
        "--echo", action="store_true", help="Echo SQL?"
    )
    validate2_cdl_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="CSV filename for output (plaintext, IDENTIFIABLE) data. "
        + Person.PLAINTEXT_CSV_FORMAT_HELP,
    )

    validate2_rio_parser = subparsers.add_parser(
        "validate2_fetch_rio",
        help="Validation 2B: fetch people from CPFT RiO database",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description="See validate2_fetch_cdl command.",
    )
    validate2_rio_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="SQLAlchemy URL for CPFT RiO source (IDENTIFIABLE) database",
    )
    validate2_rio_parser.add_argument(
        "--echo", action="store_true", help="Echo SQL?"
    )
    validate2_rio_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="CSV filename for output (plaintext, IDENTIFIABLE) data. "
        + Person.PLAINTEXT_CSV_FORMAT_HELP,
    )

    # -------------------------------------------------------------------------
    # Parse arguments and set up
    # -------------------------------------------------------------------------

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO,
        with_process_id=True,
    )
    cfg = get_cfg_from_args(args)

    # -------------------------------------------------------------------------
    # Run a command
    # -------------------------------------------------------------------------

    log.info(f"Command: {args.command}")

    if args.command == "speedtest":
        fn = do_cprofile(speedtest) if args.profile else speedtest
        fn(cfg)

    elif args.command == "validate1":
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
                cfg=cfg, url=args.url, hash_key=args.key, echo=args.echo
            ),
            output_csv=args.output,
        )

    elif args.command == "validate2_fetch_rio":
        warn_or_fail_if_default_key(args)
        save_people_from_db(
            people=validate_2_fetch_rio(
                cfg=cfg, url=args.url, hash_key=args.key, echo=args.echo
            ),
            output_csv=args.output,
        )

    else:
        # Shouldn't get here.
        log.error(f"Unknown command: {args.command}")
        return EXIT_FAILURE

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
