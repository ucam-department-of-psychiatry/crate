#!/usr/bin/env python

r"""
crate_anon/linkage/frequencies.py

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

**Frequency classes for linkage tools.**

These record and calculate frequencies of real-world things (names, postcodes)
from publicly available data.

"""


# =============================================================================
# Imports
# =============================================================================

from collections import Counter, defaultdict
import csv
import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cardinal_pythonlib.reprfunc import auto_repr
import jsonlines

from crate_anon.common.logfunc import warn_once
from crate_anon.linkage.constants import UK_POPULATION_2017
from crate_anon.linkage.helpers import (
    get_first_two_char,
    get_metaphone,
    get_postcode_sector,
    is_pseudopostcode,
    mkdir_for_filename,
    open_even_if_zipped,
    standardize_name,
    standardize_postcode,
)

log = logging.getLogger(__name__)


# =============================================================================
# BasicNameMetaphoneFreq
# =============================================================================


class BasicNameFreqInfo:
    """
    Used for calculating P(share F2C but not name or metaphone).

    Note that the metaphone can be "", e.g. if the name is "W". But we can
    still calculate the frequency of those metaphones cumulatively across all
    our names.
    """

    KEY_NAME = "name"
    KEY_P_NAME = "p_f"
    KEY_GENDER = "gender"
    KEY_METAPHONE = "metaphone"
    KEY_P_METAPHONE = "p_p1"
    KEY_P_METAPHONE_NOT_NAME = "p_p1nf"
    KEY_F2C = "f2c"
    KEY_P_F2C = "p_p2"
    KEY_P_F2C_NOT_NAME_METAPHONE = "p_p2np1"

    def __init__(
        self,
        name: str,
        p_name: float,
        gender: str = "",
        metaphone: str = "",
        p_metaphone: float = 0.0,
        p_metaphone_not_name: float = 0.0,
        f2c: str = "",
        p_f2c: float = 0.0,
        p_f2c_not_name_metaphone: float = 0.0,
        synthetic: bool = False,
    ) -> None:
        """
        The constructor allows initialization with just a name and its
        frequency (with other probabilities being set later), or from a saved
        representation with full details.

        Args:
            name:
                Name.
            p_name:
                Population probability (frequency) of this name, within the
                specified gender if there is one.
            gender:
                Specified gender, or a blank string for non-gender-associated
                names.
            metaphone:
                "Sounds-like" representation as the first part of a double
                metaphone.
            p_metaphone:
                Population frequency (probability) of the metaphone.
            p_metaphone_not_name:
                Probability that someone in the population shares this
                metaphone, but not this name. Usually this is ``p_metaphone -
                p_name``, but you may choose to impose a minimum frequency.
            f2c:
                First two characters (F2C) of the name.
            p_f2c:
                Population probability of the F2C.
            p_f2c_not_name_metaphone:
                Probability that someone in the population shares this F2C, but
                not this name or metaphone.
            synthetic:
                Is this record made up (e.g. an unknown name, or a mean of two
                other records)?
        """
        name = standardize_name(name)
        self.name = name
        self.gender = gender
        self.p_name = p_name

        self.metaphone = metaphone or get_metaphone(name)
        self.p_metaphone = p_metaphone
        self.p_metaphone_not_name = p_metaphone_not_name

        self.f2c = f2c or get_first_two_char(name)
        self.p_f2c = p_f2c  # not important! For info only.
        self.p_f2c_not_name_metaphone = p_f2c_not_name_metaphone

        self.synthetic = synthetic

    def __repr__(self) -> str:
        return auto_repr(self, sort_attrs=False)

    @property
    def p_no_match(self) -> float:
        assert (
            self.p_metaphone >= self.p_name
        ), "Set p_metaphone before using p_no_match"
        return 1 - self.p_metaphone - self.p_f2c_not_name_metaphone
        # p_metaphone includes p_name

    def as_dict(self) -> Dict[str, Any]:
        """
        Returns a JSON representation.
        """
        return {
            self.KEY_NAME: self.name,
            self.KEY_GENDER: self.gender,
            self.KEY_P_NAME: self.p_name,
            self.KEY_METAPHONE: self.metaphone,
            self.KEY_P_METAPHONE: self.p_metaphone,
            self.KEY_P_METAPHONE_NOT_NAME: self.p_metaphone_not_name,
            self.KEY_F2C: self.f2c,
            self.KEY_P_F2C: self.p_f2c,
            self.KEY_P_F2C_NOT_NAME_METAPHONE: self.p_f2c_not_name_metaphone,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BasicNameFreqInfo":
        """
        Create from JSON representation.
        """
        return BasicNameFreqInfo(
            name=d[cls.KEY_NAME],
            gender=d[cls.KEY_GENDER],
            p_name=d[cls.KEY_P_NAME],
            metaphone=d[cls.KEY_METAPHONE],
            p_metaphone=d[cls.KEY_P_METAPHONE],
            p_metaphone_not_name=d[cls.KEY_P_METAPHONE_NOT_NAME],
            f2c=d[cls.KEY_F2C],
            p_f2c=d[cls.KEY_P_F2C],
            p_f2c_not_name_metaphone=d[cls.KEY_P_F2C_NOT_NAME_METAPHONE],
        )

    @staticmethod
    def weighted_mean(
        objects: Sequence["BasicNameFreqInfo"], weights: Sequence[float]
    ):
        """
        Returns an object with the weighted probabilities across the objects
        specified. Used for gender weighting.
        """
        assert len(objects) == len(weights) > 0
        first = objects[0]
        result = BasicNameFreqInfo(name=first.name, p_name=0.0, synthetic=True)
        for i, obj in enumerate(objects):
            w = weights[i]
            result.p_name += w * obj.p_name
            result.p_metaphone += w * obj.p_name
            result.p_metaphone_not_name += w * obj.p_metaphone_not_name
            result.p_f2c += w * obj.p_f2c
            result.p_f2c_not_name_metaphone += w * obj.p_f2c_not_name_metaphone
        return result


# =============================================================================
# NameFrequencyInfo
# =============================================================================


class NameFrequencyInfo:
    """
    Holds frequencies of a class of names (e.g. first names or surnames), and
    also of their fuzzy (metaphone) versions.

    We keep these frequency representations entirely here (source) and with
    the probands (storage); the config doesn't get involved except to define
    min_frequency at creation. We need to scan across all names for an estimate
    of the empty ("") metaphone, which does arise in our standard data. There
    is a process for obtaining default frequency information for any names not
    encountered in our name definitions, of course, but that is then stored
    with the (hashed) name representations and nothing needs to be recalculated
    at comparison time. (Compare postcodes, where further geographical
    adjustments may be required, depending on the comparison population.)
    """

    def __init__(
        self,
        csv_filename: str,
        cache_filename: str,
        by_gender: bool = False,
        min_frequency: float = 0,
    ) -> None:
        """
        Initializes the object from a CSV file.
        Uses standardize_name().

        Args:
            csv_filename:
                CSV file, with no header, of "name, frequency" pairs.
            cache_filename:
                File in which to cache information, for faster loading.
            by_gender:
                Is the source data split by gender?
            min_frequency:
                Minimum frequency to allow; see command-line help.
        """
        self._csv_filename = csv_filename
        self._cache_filename = cache_filename
        self._min_frequency = min_frequency
        self.by_gender = by_gender

        self.infolist = []  # type: List[BasicNameFreqInfo]

        # We key the following by (name, gender), even if gender is "".
        # This makes the code much simpler.
        self.name_gender_idx = (
            {}
        )  # type: Dict[Tuple[str, str], BasicNameFreqInfo]
        self.metaphone_freq = {}  # type: Dict[Tuple[str, str], float]
        self.f2c_freq = {}  # type: Dict[Tuple[str, str], float]
        self.f2c_to_infolist = defaultdict(
            list
        )  # type: Dict[Tuple[str, str], List[BasicNameFreqInfo]]

        if not csv_filename or not cache_filename:
            log.debug("Using dummy NameFrequencyInfo")
            return

        try:
            self._load_from_cache(cache_filename)
        except ValueError:
            log.critical(f"Bad cache: please delete {cache_filename}")
            raise
        except FileNotFoundError:
            self._load_from_csv(csv_filename)
            self._save_to_cache(cache_filename)

    def _load_from_cache(self, cache_filename: str) -> None:
        """
        Loads from a JSONL cache.
        """
        log.info(f"Reading from cache: {cache_filename}")
        with jsonlines.open(cache_filename) as reader:
            self.infolist = [BasicNameFreqInfo.from_dict(d) for d in reader]
        log.debug(f"... finished reading from: {cache_filename}")
        self._index(update_infolist=False)

    def _save_to_cache(self, cache_filename: str) -> None:
        """
        Saves to a JSONL cache.
        """
        if not cache_filename:
            return
        log.info(f"Writing to cache: {cache_filename}")
        mkdir_for_filename(cache_filename)
        with jsonlines.open(cache_filename, mode="w") as writer:
            for i in self.infolist:
                writer.write(i.as_dict())
        log.debug(f"... finished writing to cache: {cache_filename}")

    def _load_from_csv(self, csv_filename: str) -> None:
        """
        Read from the original data.
        """
        log.info(f"Reading source data: {csv_filename}")
        by_gender = self.by_gender
        min_frequency = self._min_frequency
        self.infolist = []
        with open_even_if_zipped(csv_filename) as f:
            for row in csv.reader(f):
                if by_gender:
                    gender = row[1]
                    freq_str = row[2]
                else:
                    gender = ""
                    freq_str = row[1]
                self.infolist.append(
                    BasicNameFreqInfo(
                        name=row[0],
                        p_name=max(min_frequency, float(freq_str)),
                        gender=gender,
                    )
                )
        log.debug(f"... finished reading from: {csv_filename}")
        self._index(update_infolist=True)

    def _index(self, update_infolist: bool) -> None:
        """
        Build our internal indexes, having loaded `self.infolist`.

        Example for thinking (with fictional metaphones; these might be
        wrong!):

        .. code-block:: none

            #   name        p       metaphone   f2c
            1   SMITH       0.2     SMT         SM
            2   SMYTHE      0.05    SMT         SM
            3   SCHMITH     0.01    SMT         SC
            4   SMALL       0.04    SML         SM
            5   JONES       0.2     JNS         JO
            6   JOPLIN      0.1     JPL         JO
            7   WALKER      0.2     WLK         WA
            8   ZEBRA       0.2     ZBR         ZE

        With respect to a proband called SMITH:

        - P(another person's name is SMITH) = 0.2 [1];

        - P(another person's metaphone is SMT) = 0.26 [1, 2, 3];
        - P(another person's metaphone is SMT but their name is not SMITH) =
          0.06 [2, 3], being the preceding minus [1];

        - P(another person's F2C is SM) = 0.29 [1, 2, 4];
        - P(another person's F2C is SM but their metaphone is not SMT and their
          name is not SMITH) = 0.04 [4].

        With respect to a proband called SMALL:

        - P(another person's name is SMALL) = 0.04 [4];

        - P(... metaphone SML) = 0.04 [4];
        - P(... metaphone SML, name not SMALL) = 0, being the preceding minus
          [4];

        - P(... F2C SM) = 0.29 [1, 2, 4];
        - P(... F2C SM but metaphone not SML and name not SMALL) = 0.25 [1, 2].

        This makes it apparent that:

        - P(another person matches on name) = P(name in the population).

        - Since names have a one-to-one or many-to-one relationship with
          metaphones (one name can only have one metaphone but two names can
          share a metaphone), P(metaphone match but not name match) is
          P(metaphone match) minus P(name match).

        - There is obviously a quantity P(F2C) that is constant for every F2C.
          Also, the relationship between names and F2C is one-to-one or
          many-to-one, as for metaphones. However, if F2C are second in the
          hierarchy, such that we need to calculate P(F2C match but not name OR
          METAPHONE match), it becomes relevant that the relationship between
          metaphones and F2C is many-to-many [see examples 1-4 above].

          THEREFORE, P(F2C match but name or metaphone match) is SPECIFIC TO
          A NAME.

        """
        log.debug("Indexing name frequency info...")

        # Reset
        self.name_gender_idx = {}
        self.metaphone_freq = {}
        self.f2c_freq = {}
        self.f2c_to_infolist = defaultdict(list)

        # For extra speed:
        min_frequency = self._min_frequency
        name_gender_idx = self.name_gender_idx
        metaphone_freq = self.metaphone_freq
        f2c_freq = self.f2c_freq
        f2c_to_infolist = self.f2c_to_infolist

        meta_to_infolist = defaultdict(
            list
        )  # type: Dict[Tuple[str, str], List[BasicNameFreqInfo]]

        for i in self.infolist:
            name_key = i.name, i.gender
            metaphone_key = i.metaphone, i.gender
            f2c_key = i.f2c, i.gender
            p_name = i.p_name

            # Enable rapid lookup by name/gender
            name_gender_idx[name_key] = i

            # Calculate metaphone frequency (maybe for writing back to name
            # info objects, but certainly for frequency information relating to
            # unknown names with known metaphones).
            metaphone_freq[metaphone_key] = (
                metaphone_freq.get(metaphone_key, 0) + p_name
            )

            # Calculate F2C frequency (not very important!).
            f2c_freq[f2c_key] = f2c_freq.get(f2c_key, 0) + p_name

            # Enable lookup by F2C
            f2c_to_infolist[f2c_key].append(i)

            if update_infolist:
                # Enable temporary lookup by metaphone
                meta_to_infolist[metaphone_key].append(i)

        if update_infolist:
            log.info("... calculating additional frequency info (slow)...")
            # Store metaphone frequency for each name.
            for metaphone_key, metaphone_infolist in meta_to_infolist.items():
                p_meta = metaphone_freq[metaphone_key]
                for i in metaphone_infolist:  # type: BasicNameFreqInfo
                    i.p_metaphone = max(min_frequency, p_meta)
                    i.p_metaphone_not_name = max(
                        min_frequency, p_meta - i.p_name
                    )
            # This is not very important, but... store F2C frequency.
            for f2c_key, f2c_infolist in f2c_to_infolist.items():
                p_f2c = max(min_frequency, f2c_freq[f2c_key])
                for i in f2c_infolist:  # type: BasicNameFreqInfo
                    i.p_f2c = p_f2c
            # Calculate P(F2C match but not name or metaphone match).
            # This is name-specific; see above.
            for i in self.infolist:
                f2c_key = i.f2c, i.gender
                i.p_f2c_not_name_metaphone = 0.0
                for other in f2c_to_infolist[f2c_key]:  # ... same F2C...
                    if other.name != i.name and other.metaphone != i.metaphone:
                        # ... but different name and metaphone...
                        i.p_f2c_not_name_metaphone += other.p_name
                i.p_f2c_not_name_metaphone = max(
                    min_frequency, i.p_f2c_not_name_metaphone
                )

        log.debug("... finished indexing name frequency info")

    def name_frequency_info(
        self, name: str, gender: str = "", prestandardized: bool = True
    ) -> BasicNameFreqInfo:
        """
        Look up frequency information for a name (with gender, optionally).
        """
        if not prestandardized:
            name = standardize_name(name)
        key = name, gender
        result = self.name_gender_idx.get(key, None)
        if result is not None:
            return result
        return self._unknown_name_info(name, gender)

    def _unknown_name_info(
        self, name: str, gender: str = ""
    ) -> BasicNameFreqInfo:
        """
        Return a default set of information for unknown names. We do not alter
        our saved information.

        It's possible that an unknown name has a known metaphone or F2C,
        though, so we account for that.
        """
        min_frequency = self._min_frequency
        result = BasicNameFreqInfo(
            name=name,
            p_name=min_frequency,
            gender=gender,
            synthetic=True,
        )

        metaphone = result.metaphone
        meta_key = metaphone, gender
        result.p_metaphone = max(
            min_frequency, self.metaphone_freq.get(meta_key, min_frequency)
        )
        result.p_metaphone_not_name = max(
            min_frequency, result.p_metaphone - result.p_name
        )

        f2c_key = result.f2c, gender
        result.p_f2c = max(
            min_frequency, self.f2c_freq.get(f2c_key, min_frequency)
        )
        p_f2c_not_name_metaphone = 0.0
        for i in self.f2c_to_infolist[f2c_key]:  # same F2C
            if i.metaphone != metaphone:  # but not same metaphone
                # and by definition not the same name, or we wouldn't be here
                p_f2c_not_name_metaphone += i.p_name
        result.p_f2c_not_name_metaphone = max(
            min_frequency, p_f2c_not_name_metaphone
        )

        return result

    def name_frequency(
        self, name: str, gender: str = "", prestandardized: bool = True
    ) -> float:
        """
        Returns the frequency of a name.

        Args:
            name: the name to check
            gender: the gender, if created with ``by_gender=True``
            prestandardized: was the name pre-standardized in format?

        Returns:
            the name's frequency in the population
        """
        return self.name_frequency_info(
            name, gender, prestandardized=prestandardized
        ).p_name

    def metaphone_frequency(self, metaphone: str, gender: str = "") -> float:
        """
        Returns the frequency of a metaphone.
        """
        key = metaphone, gender
        return self.metaphone_freq.get(key, self._min_frequency)

    def first_two_char_frequency(self, f2c: str, gender: str = "") -> float:
        """
        Returns the frequency of the first two characters of a name.
        This one isn't very important; we want a more refined probability.
        """
        key = f2c, gender
        return self.f2c_freq.get(key, self._min_frequency)

    def get_names_for_metaphone(self, metaphone: str) -> List[str]:
        """
        Return (for debugging purposes) a list of all names matching the
        specified metaphone.
        """
        metaphone = metaphone.upper()
        return sorted(
            set(
                info.name
                for info in self.infolist
                if info.metaphone == metaphone
            )
        )


# =============================================================================
# PostcodeFrequencyInfo
# =============================================================================


class PostcodeFrequencyInfo:
    """
    Holds frequencies of UK postcodes, and also their hashed versions.
    Handles pseudo-postcodes somewhat separately.

    Frequencies are national estimates for known real postcodes. Any local
    correction or correction for unknown postcodes is done separately.

    We return explicit "don't know" values for unknown postcodes (including
    pseudopostcodes) since those values may be handled differently, in a way
    that is set at comparison time.
    """

    KEY_POSTCODE_UNIT_FREQ = "postcode_unit_freq"
    KEY_POSTCODE_SECTOR_FREQ = "postcode_sector_freq"

    def __init__(
        self,
        csv_filename: str,
        cache_filename: str,
        report_every: int = 10000,
    ) -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file from the UK Office of National Statistics, e.g.
                ``ONSPD_MAY_2022_UK.csv``. Columns include "pdcs" (one of the
                postcode formats) and "oa11" (Output Area from the 2011
                Census). A ZIP file containing a single CSV file is also
                permissible (distinguished by filename extension).
            cache_filename:
                Filename to hold pickle format cached data, because the CSV
                read process is slow (it's a 1.4 Gb CSV).
            report_every:
                How often to report progress during loading.
        """
        self._csv_filename = csv_filename
        self._cache_filename = cache_filename

        self._postcode_unit_freq = {}  # type: Dict[str, float]
        self._postcode_sector_freq = {}  # type: Dict[str, float]

        if not csv_filename or not cache_filename:
            log.debug("Using dummy PostcodeFrequencyInfo")
            return

        try:
            self._load_from_cache(cache_filename)
        except (KeyError, ValueError):
            log.critical(f"Bad cache: please delete {cache_filename}")
            raise
        except FileNotFoundError:
            self._load_from_csv(
                csv_filename,
                report_every=report_every,
            )
            self._save_to_cache(cache_filename)

    def _load_from_cache(self, cache_filename: str) -> None:
        """
        Loads from a JSON cache.

        May raise KeyError, ValueError.
        """
        log.info(f"Reading from cache: {cache_filename}")
        with open(cache_filename) as file:
            d = json.load(file)

        # May raise KeyError:
        self._postcode_unit_freq = d[self.KEY_POSTCODE_UNIT_FREQ]
        self._postcode_sector_freq = d[self.KEY_POSTCODE_SECTOR_FREQ]

        if not isinstance(self._postcode_unit_freq, dict):
            raise ValueError(
                f"Bad cache: {self.KEY_POSTCODE_UNIT_FREQ} is of wrong type "
                f"{type(self._postcode_unit_freq)}"
            )
        if not isinstance(self._postcode_sector_freq, dict):
            raise ValueError(
                f"Bad cache: {self.KEY_POSTCODE_SECTOR_FREQ} is of wrong type "
                f"{type(self._postcode_sector_freq)}"
            )

        log.debug(f"... finished reading from: {cache_filename}")

    def _save_to_cache(self, cache_filename: str) -> None:
        """
        Saves to a JSON cache.
        """
        if not cache_filename:
            return
        log.info(f"Writing to cache: {cache_filename}")
        mkdir_for_filename(cache_filename)
        d = {
            self.KEY_POSTCODE_UNIT_FREQ: self._postcode_unit_freq,
            self.KEY_POSTCODE_SECTOR_FREQ: self._postcode_sector_freq,
        }
        with open(cache_filename, mode="w") as file:
            json.dump(d, file)
        log.debug(f"... finished writing to cache: {cache_filename}")

    def _load_from_csv(self, csv_filename: str, report_every: int) -> None:
        """
        Read from the original data.
        """
        log.info(f"Reading source data: {csv_filename}")

        self._postcode_unit_freq = {}
        self._postcode_sector_freq = {}

        oa_unit_counter = Counter()
        unit_to_oa = {}  # type: Dict[str, str]
        sector_to_oas = {}  # type: Dict[str, Set[str]]

        # Load data
        with open_even_if_zipped(csv_filename) as f:
            csvreader = csv.DictReader(f)
            for rownum, row in enumerate(csvreader, start=1):
                unit = standardize_postcode(row["pcds"])
                sector = get_postcode_sector(unit)
                oa = row["oa11"]
                if rownum % report_every == 0:
                    log.debug(
                        f"Row# {rownum}: postcode unit {unit}, "
                        f"postcode sector {sector}, Output Area {oa}"
                    )

                unit_to_oa[unit] = oa
                oa_unit_counter[oa] += 1  # one more unit for this OA
                if sector in sector_to_oas:
                    sector_to_oas[sector].add(oa)
                else:
                    sector_to_oas[sector] = {oa}

        # Calculate. The absolute value of the population size of an OA is
        # irrelevant as it cancels out.
        log.info("Calculating population frequencies for postcodes...")
        unit_freq = self._postcode_unit_freq
        sector_freq = self._postcode_sector_freq
        total_n_oas = len(oa_unit_counter)
        log.info(f"Number of Output Areas: {total_n_oas}")
        for unit, oa in unit_to_oa.items():
            n_units_in_this_oa = oa_unit_counter[oa]
            unit_n_oas = 1 / n_units_in_this_oa
            unit_freq[unit] = unit_n_oas / total_n_oas
        for sector, oas in sector_to_oas.items():
            sector_n_oas = len(oas)
            sector_freq[sector] = sector_n_oas / total_n_oas

        log.debug(f"... finished reading from: {csv_filename}")

    def postcode_unit_sector_frequency(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Returns the frequency of a postcode unit and its associated sector.
        Performs an important check that the sector frequency is as least as
        big as the unit frequency.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?

        Returns:
            tuple: unit_frequency, sector_frequency
        """
        unit = (
            postcode_unit
            if prestandardized
            else standardize_postcode(postcode_unit)
        )
        sector = get_postcode_sector(unit)
        try:
            unit_freq = self._postcode_unit_freq[unit]
            sector_freq = self._postcode_sector_freq[sector]
            assert unit_freq <= sector_freq, (
                f"Postcodes: unit_freq = {unit_freq}, "
                f"sector_freq = {sector_freq}, but should have "
                f"unit_freq <= sector_freq, "
                f"for unit = {unit}, sector = {sector}"
            )
        except KeyError:
            if not is_pseudopostcode(unit, prestandardized=True):
                warn_once(
                    f"Unknown postcode: {unit}", log, level=logging.DEBUG
                )
            unit_freq = None
            sector_freq = None
        return unit_freq, sector_freq

    def debug_is_valid_postcode(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> bool:
        """
        Is this a valid postcode?
        """
        if not prestandardized:
            postcode_unit = standardize_postcode(postcode_unit)
        return postcode_unit in self._postcode_unit_freq or is_pseudopostcode(
            postcode_unit, prestandardized=True
        )

    def debug_postcode_unit_population(
        self,
        postcode_unit: str,
        prestandardized: bool = False,
        total_population: int = UK_POPULATION_2017,
    ) -> Optional[float]:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
            total_population: national population
        """
        unit_freq, _ = self.postcode_unit_sector_frequency(
            postcode_unit, prestandardized
        )
        if unit_freq is None:
            return None
        return unit_freq * total_population

    def debug_postcode_sector_population(
        self,
        postcode_sector: str,
        prestandardized: bool = False,
        total_population: int = UK_POPULATION_2017,
    ) -> Optional[float]:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the sector pre-standardized in format?
            total_population: national population
        """
        sector = (
            postcode_sector
            if prestandardized
            else standardize_postcode(postcode_sector)
        )
        sector_freq = self._postcode_sector_freq.get(sector)
        if sector_freq is None:
            return None
        return sector_freq * total_population
