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

"""


# =============================================================================
# Imports
# =============================================================================

from collections import Counter
import csv
import logging
from typing import (
    Dict,
    Set,
    Tuple,
    Union,
)

from crate_anon.common.logfunc import warn_once
from crate_anon.linkage.constants import FuzzyDefaults
from crate_anon.linkage.helpers import (
    cache_load,
    cache_save,
    get_metaphone,
    get_postcode_sector,
    is_pseudo_postcode,
    open_even_if_zipped,
    standardize_name,
    standardize_postcode,
)

log = logging.getLogger(__name__)


# =============================================================================
# NameFrequencyInfo
# =============================================================================


class NameFrequencyInfo(object):
    """
    Holds frequencies of a class of names (e.g. first names or surnames), and
    also of their hashed versions.
    """

    def __init__(
        self,
        csv_filename: str,
        cache_filename: str,
        by_gender: bool = False,
        min_frequency: float = 5e-6,
    ) -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file, with no header, of "name, frequency" pairs.
            cache_filename:
                File in which to cache information, for faster loading.
            by_gender:
                read, split, and key by gender as well as name
            min_frequency:
                minimum frequency to allow; see command-line help.
        """
        assert csv_filename and cache_filename
        self._csv_filename = csv_filename
        self._cache_filename = cache_filename
        self._min_frequency = min_frequency
        self._name_freq = {}  # type: Dict[Union[str, Tuple[str, str]], float]
        self._metaphone_freq = (
            {}
        )  # type: Dict[Union[str, Tuple[str, str]], float]  # noqa
        self._by_gender = by_gender

        try:
            self._name_freq, self._metaphone_freq = cache_load(cache_filename)
            for d in [self._name_freq, self._metaphone_freq]:
                keytype = tuple if by_gender else str
                for k in d.keys():
                    assert isinstance(k, keytype), (
                        f"Cache file {cache_filename!r} has the wrong key "
                        f"type (is {type(k)}, should be {keytype}. "
                        f"Please delete this file and try again."
                    )
        except FileNotFoundError:
            # For extra speed:
            name_freq = self._name_freq
            metaphone_freq = self._metaphone_freq
            # Load
            with open_even_if_zipped(csv_filename) as f:
                csvreader = csv.reader(f)
                for row in csvreader:
                    name = standardize_name(row[0])
                    if by_gender:
                        gender = row[1]
                        freq_str = row[2]
                    else:
                        freq_str = row[1]
                    freq = max(float(freq_str), min_frequency)
                    metaphone = get_metaphone(name)
                    # Note that the metaphone can be "", e.g. if the name is
                    # "W". But we can still calculate the frequency of those
                    # metaphones cumulatively across all our names.
                    if by_gender:
                        name_key = name, gender
                        metaphone_key = metaphone, gender
                    else:
                        name_key = name
                        metaphone_key = metaphone
                    name_freq[name_key] = freq
                    # https://stackoverflow.com/questions/12992165/python-dictionary-increment  # noqa
                    metaphone_freq[metaphone_key] = (
                        metaphone_freq.get(metaphone_key, 0) + freq
                    )
            # Save to cache
            cache_save(cache_filename, [name_freq, metaphone_freq])

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
        if not prestandardized:
            name = standardize_name(name)
        key = (name, gender) if self._by_gender else name
        # Note operator precedence! Do NOT do this:
        # key = name, gender if self._by_gender else name
        return self._name_freq.get(key, self._min_frequency)

    def metaphone_frequency(self, metaphone: str, gender: str = "") -> float:
        """
        Returns the frequency of a metaphone
        """
        key = (metaphone, gender) if self._by_gender else metaphone
        # ... as above!
        return self._metaphone_freq.get(key, self._min_frequency)


# =============================================================================
# PostcodeFrequencyInfo
# =============================================================================


class PostcodeFrequencyInfo(object):
    """
    Holds frequencies of UK postcodes, and also their hashed versions.
    Handles pseudo-postcodes somewhat separately.
    """

    def __init__(
        self,
        csv_filename: str,
        cache_filename: str,
        mean_oa_population: float = FuzzyDefaults.MEAN_OA_POPULATION,
        p_unknown_or_pseudo_postcode: float = (
            FuzzyDefaults.P_UNKNOWN_OR_PSEUDO_POSTCODE
        ),
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
            mean_oa_population:
                Mean population of each census Output Area.
            p_unknown_or_pseudo_postcode:
                Probability that a random person will have a pseudo-postcode,
                e.g. ZZ99 3VZ (no fixed above) or a postcode not known to our
                database.
        """
        assert csv_filename and cache_filename
        assert mean_oa_population > 0
        assert 0 <= p_unknown_or_pseudo_postcode <= 1

        self._csv_filename = csv_filename
        self._cache_filename = cache_filename
        self._mean_oa_population = mean_oa_population
        self._p_unknown_or_pseudo_postcode = p_unknown_or_pseudo_postcode

        self._p_known_postcode = 1 - p_unknown_or_pseudo_postcode
        self._postcode_unit_freq = {}  # type: Dict[str, float]
        self._postcode_sector_freq = {}  # type: Dict[str, float]
        self._total_population = 0

        try:
            (
                self._postcode_unit_freq,
                self._postcode_sector_freq,
                self._total_population,
            ) = cache_load(cache_filename)
        except FileNotFoundError:
            oa_unit_counter = Counter()
            unit_to_oa = {}  # type: Dict[str, str]
            sector_to_oas = {}  # type: Dict[str, Set[str]]

            # Load data
            report_every = 10000
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

            # Calculate
            log.info("Calculating population frequencies for postcodes...")
            unit_freq = self._postcode_unit_freq
            sector_freq = self._postcode_sector_freq
            n_oas = len(oa_unit_counter)
            log.info(f"Number of Output Areas: {n_oas}")
            self._total_population = n_oas * mean_oa_population
            log.info(f"Calculated total population: {self._total_population}")
            for unit, oa in unit_to_oa.items():
                n_units_in_this_oa = oa_unit_counter[oa]
                unit_population = mean_oa_population / n_units_in_this_oa
                unit_freq[unit] = unit_population / self._total_population
            for sector, oas in sector_to_oas.items():
                n_oas_in_this_sector = len(oas)
                sector_population = mean_oa_population * n_oas_in_this_sector
                sector_freq[sector] = (
                    sector_population / self._total_population
                )  # noqa
            log.info("... done")
            # Save to cache
            cache_save(
                cache_filename,
                [unit_freq, sector_freq, self._total_population],
            )

    def postcode_unit_sector_frequency(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> Tuple[float, float]:
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
            unit_freq = self._postcode_unit_freq[unit] * self._p_known_postcode
            sector_freq = (
                self._postcode_sector_freq[sector] * self._p_known_postcode
            )
        except KeyError:
            if not is_pseudo_postcode(unit):
                warn_once(f"Unknown postcode: {unit}", log)
            unit_freq = self._p_unknown_or_pseudo_postcode
            sector_freq = self._p_unknown_or_pseudo_postcode
        assert unit_freq <= sector_freq, (
            f"Postcodes: unit_freq = {unit_freq}, "
            f"sector_freq = {sector_freq}, but should have "
            f"unit_freq <= sector_freq, for unit = {unit}, sector = {sector}"
        )
        return unit_freq, sector_freq

    def debug_is_valid_postcode(self, postcode_unit: str) -> bool:
        """
        Is this a valid postcode?
        """
        return postcode_unit in self._postcode_unit_freq or is_pseudo_postcode(
            postcode_unit
        )

    def debug_postcode_unit_population(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
        """
        unit_freq, _ = self.postcode_unit_sector_frequency(
            postcode_unit, prestandardized
        )
        return unit_freq * self._total_population

    def debug_postcode_sector_population(
        self, postcode_sector: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the postcode pre-standardized in format?
        """
        sector = (
            postcode_sector
            if prestandardized
            else standardize_postcode(postcode_sector)
        )
        return (
            self._postcode_sector_freq[sector]
            * self._p_known_postcode
            * self._total_population
        )
