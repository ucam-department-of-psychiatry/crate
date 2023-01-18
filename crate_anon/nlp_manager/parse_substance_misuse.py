#!/usr/bin/env python

"""
crate_anon/nlp_manager/parse_substance_misuse.py

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

**Python regex-based NLP processors for substance misuse.**

"""

import logging
from typing import Any, Dict, Generator, List, Optional, Tuple

from crate_anon.common.regex_helpers import (
    noncapture_group,
    optional_noncapture_group,
    regex_or,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.number import to_float
from crate_anon.nlp_manager.regex_func import (
    compile_regex_dict,
    get_regex_dict_match,
    get_regex_dict_search,
)
from crate_anon.nlp_manager.regex_parser import (
    common_tense,
    GROUP_NAME_QUANTITY,
    GROUP_NAME_RELATION,
    GROUP_NAME_TENSE,
    GROUP_NAME_UNITS,
    GROUP_NAME_VALUE,
    GROUP_NUMBER_WHOLE_EXPRESSION,
    FN_VARIABLE_NAME,
    FN_CONTENT,
    FN_START,
    FN_END,
    FN_VARIABLE_TEXT,
    FN_RELATION_TEXT,
    FN_RELATION,
    FN_VALUE_TEXT,
    FN_UNITS,
    FN_TENSE_TEXT,
    FN_TENSE,
    make_simple_numeric_regex,
    PAST,
    PRESENT,
    SimpleNumericalResultParser,
    ValidatorBase,
)
from crate_anon.nlp_manager.regex_units import (
    UK_ALCOHOL_UNITS_PER_DAY,
    UK_ALCOHOL_UNITS_PER_WEEK,
)

log = logging.getLogger(__name__)


# =============================================================================
# Alcohol
# =============================================================================


class AlcoholUnits(SimpleNumericalResultParser):
    """
    SUBSTANCE MISUSE.

    Alcohol consumption, specified explicitly as (UK) units per day or per
    week. A UK unit is 10 ml of ethanol [1, 2]. UK NHS guidelines used to be
    "per week" and remain broadly week-based [1]. It doesn't attempt any
    understanding of other alcohol descriptions (e.g. "pints of beer", "glasses
    of wine", "bottles of vodka") so is expected to apply where a clinician has
    converted a (potentially mixed) alcohol description to a units-per-week
    calculation.

    [1] https://www.nhs.uk/live-well/alcohol-advice/calculating-alcohol-units/,
        accessed 2023-01-18.
    [2] https://en.wikipedia.org/wiki/Unit_of_alcohol
    """

    # There are no relevant Read codes for alcohol consumption in
    # v3ReadCode_PBCL.xlsx.

    # All these are verbose regexes, so don't omit \s+ for whitespace!
    _PAST_ADVERBS = ("previously", "formerly", "once")
    _PAST_ADVERBS_RE = noncapture_group(regex_or(*_PAST_ADVERBS))
    _DRINKING_PAST = (
        # Infinitive: she used to drink
        r"used \s+ to \s+ drink",
        # Noun phrase: peak drinking
        r"peak (?: \s+ drinking )?",
        # Imperfect tense: she [adverb] drank
        rf"(?: {_PAST_ADVERBS_RE} \s+ )? drank",
        # Past continuous tense: he was [adverb] drinking
        rf"was (?: \s+ {_PAST_ADVERBS_RE} )? \s+ drinking",
    )
    # We don't allow the adverbs by themselves, to avoid something that isn't
    # explicitly about alcohol or drinking, e.g. "[insulin] currently 6
    # units/day".
    _PRESENT_ADVERBS = (
        "currently",
        "presently",
        r"at \s+ present",
        "now",
        "nowadays",
        r"these \s+ days",
    )
    _PRESENT_ADVERBS_RE = noncapture_group(regex_or(*_PRESENT_ADVERBS))
    _DRINKING_PRESENT = (
        # Present tense (he [adverb] drinks):
        rf"(?: {_PRESENT_ADVERBS_RE} \s+)? drinks",
        # Present continuous tense (he is [adverb] drinking):
        rf"(?: is \s+)? (?: {_PRESENT_ADVERBS_RE} \s+)? drinking",
    )
    _DRINKING = noncapture_group(
        regex_or(*(_DRINKING_PAST + _DRINKING_PRESENT))
    )
    _ALCOHOL = (
        "alcohol",
        "ethanol",
        "EtOH",
    )
    _ALCOHOL_RE = noncapture_group(regex_or(*_ALCOHOL))
    _ALC = noncapture_group(rf"{_ALCOHOL_RE} (?: \s+ consumption)?")
    _PURE_TEMPORAL = _PAST_ADVERBS + _PRESENT_ADVERBS
    _JUNK_ELEMENTS = (r"\s* :", r"\s+ at")
    _OPTIONAL_JUNK = optional_noncapture_group(regex_or(*_JUNK_ELEMENTS))
    _OPTIONAL_SPACE_TEMPORAL = optional_noncapture_group(
        r"\s+" + noncapture_group(regex_or(*_PURE_TEMPORAL))
    )

    ALCOHOL = rf"""
        {WORD_BOUNDARY}
            (?:
                {_DRINKING} \s+ {_ALC} {_OPTIONAL_JUNK}
                | {_ALC} {_OPTIONAL_JUNK} \s+ {_DRINKING} {_OPTIONAL_JUNK}
                | {_DRINKING} {_OPTIONAL_JUNK}
                | {_ALC} {_OPTIONAL_JUNK} {_OPTIONAL_SPACE_TEMPORAL}
            )
        {WORD_BOUNDARY}
    """
    # Move from more to less specific, or the less specific will capture first.
    # Examples:
    # "drinking X" -- _DRINKING
    # "EtOH X" -- _ALC
    # "peak alcohol" -- _DRINKING, _ALC
    # "alcohol: was drinking" -- _ALC, _OPTIONAL_JUNK, _DRINKING
    # "was drinking alcohol at" -- _DRINKING, _ALC, _OPTIONAL_JUNK

    REGEX = make_simple_numeric_regex(
        quantity=ALCOHOL,
        units=regex_or(UK_ALCOHOL_UNITS_PER_DAY, UK_ALCOHOL_UNITS_PER_WEEK),
        units_optional=False,
    )
    NAME = "AlcoholUnits"
    PREFERRED_UNIT_COLUMN = "value_uk_units_per_week"
    UNIT_MAPPING = {
        UK_ALCOHOL_UNITS_PER_WEEK: 1,  # preferred unit
        UK_ALCOHOL_UNITS_PER_DAY: 7,  # 1 unit/day -> 7 units/week
    }

    _drinking_tense_dict = {}  # type: Dict[str, str]
    for _past in _DRINKING_PAST + _PAST_ADVERBS:
        _drinking_tense_dict[_past] = PAST
    for _present in _DRINKING_PRESENT + _PRESENT_ADVERBS:
        _drinking_tense_dict[_present] = PRESENT
    DRINKING_TENSE_LOOKUP = compile_regex_dict(_drinking_tense_dict)

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True,
        )

    def parse(
        self, text: str, debug: bool = False
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """
        We override the parent version to deal with tense a bit better (e.g.
        "used to drink"). Comments from parent version not repeated.
        """
        if not text:
            return
        for m in self.compiled_regex.finditer(text):
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(GROUP_NUMBER_WHOLE_EXPRESSION)
            variable_text = m.group(GROUP_NAME_QUANTITY)
            tense_text = m.group(GROUP_NAME_TENSE)
            relation_text = m.group(GROUP_NAME_RELATION)
            value_text = m.group(GROUP_NAME_VALUE)
            units = m.group(GROUP_NAME_UNITS)

            value_in_target_units = None
            if units:
                matched_unit, multiple_or_fn = get_regex_dict_match(
                    units, self.units_to_factor
                )
                if not matched_unit:
                    continue
                if callable(multiple_or_fn):
                    value_in_target_units = multiple_or_fn(value_text)
                else:
                    value_in_target_units = (
                        to_float(value_text) * multiple_or_fn
                    )
            elif self.assume_preferred_unit:  # unit is None or empty
                value_in_target_units = to_float(value_text)

            if value_in_target_units is not None and self.take_absolute:
                value_in_target_units = abs(value_in_target_units)

            tense, relation = common_tense(tense_text, relation_text)

            # Extra bit here:
            if not tense:
                # Does the "variable" text contain tense information?
                _, tense = get_regex_dict_search(
                    variable_text, self.DRINKING_TENSE_LOOKUP
                )
                if tense:
                    tense_text = variable_text

            # Back to the previous code:
            result = {
                FN_VARIABLE_NAME: self.variable,
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,
                FN_VARIABLE_TEXT: variable_text,
                FN_RELATION_TEXT: relation_text,
                FN_RELATION: relation,
                FN_VALUE_TEXT: value_text,
                FN_UNITS: units,
                self.target_unit: value_in_target_units,
                FN_TENSE_TEXT: tense_text,
                FN_TENSE: tense,
            }
            if debug:
                log.debug(f"Match {m} for {repr(text)} -> {result}")
            yield self.tablename, result

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        # run via e.g. "pytest -k TestSubstanceMisuse -rP"
        no_results = []
        six_no_tense = [{self.target_unit: 6, FN_TENSE: None}]
        six_past = [{self.target_unit: 6, FN_TENSE: PAST}]
        six_present = [{self.target_unit: 6, FN_TENSE: PRESENT}]
        forty_two_present = [{self.target_unit: 6 * 7, FN_TENSE: PRESENT}]
        self.detailed_test_multiple(
            [
                # No results expected:
                ("Alcohol", no_results),
                ("He used to drink like a fish", no_results),
                ("[e.g. insulin] currently 6 units per week", no_results),
                ("[e.g. insulin] previously 6 units per week", no_results),
                ("[IU is wrong] alcohol 6 IU/week", no_results),
                # Value with no tense:
                ("Alcohol 6 u/w", six_no_tense),
                ("Alcohol - 6 u/w", six_no_tense),
                ("EtOH = 6 u/w", six_no_tense),
                ("Alcohol (units/week): 6", six_no_tense),
                ("Ethanol 6 units/week", six_no_tense),
                # Past tense:
                ("Alcohol: was 6 u/w", six_past),
                # ... double-checked: fails with six_present, six_no_tense
                ("Alcohol: formerly 6 u/w", six_past),
                ("Alcohol: previously 6 u/w", six_past),
                ("Alcohol: once 6 u/w", six_past),
                ("Used to drink 6 u/w", six_past),
                ("Peak 6 u/w", six_past),
                ("Peak drinking 6 u/w", six_past),
                ("Peak alcohol consumption: 6 u/w", six_past),
                ("Drank 6 u/w", six_past),
                ("Formerly drank 6 u/w", six_past),
                ("Previously drank 6 u/w", six_past),
                ("Was drinking 6 u/w", six_past),
                ("Was previously drinking 6 u/w", six_past),
                ("Was formerly drinking 6 u/w", six_past),
                ("Alcohol: formerly 6 u/w", six_past),
                ("Alcohol: previously 6 u/w", six_past),
                # Present tense:
                ("Drinks 6 units per week", six_present),
                ("Drinks 6 UK units per week", six_present),
                ("Drinks 6 units/d", forty_two_present),
                ("Currently drinks 6 units per week", six_present),
                ("These days drinks 6 units per week", six_present),
                ("Now drinks 6 units per week", six_present),
                ("Nowadays drinks 6 units per week", six_present),
                ("Drinking 6 units per week", six_present),
                ("Currently drinking 6 units per week", six_present),
                ("Presently drinking 6 units per week", six_present),
                ("Alcohol: currently 6 u/w", six_present),
                ("Alcohol: presently 6 u/w", six_present),
            ],
            verbose=verbose,
        )


class AlcoholUnitsValidator(ValidatorBase):
    """
    Validator for AlcoholUnits (see help for explanation).
    """

    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return AlcoholUnits.NAME, [AlcoholUnits.ALCOHOL]


# =============================================================================
# All classes in this module
# =============================================================================

ALL_SUBSTANCE_MISUSE_NLP_AND_VALIDATORS = [
    (AlcoholUnits, AlcoholUnitsValidator),
]
