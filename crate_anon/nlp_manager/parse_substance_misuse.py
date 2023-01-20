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
    at_wb_start_end,
    noncapture_group,
    optional_named_capture_group,
    optional_noncapture_group,
    regex_or,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.number import to_float
from crate_anon.nlp_manager.regex_func import (
    compile_regex,
    compile_regex_dict,
    get_regex_dict_match,
    get_regex_dict_search,
)
from crate_anon.nlp_manager.regex_parser import (
    common_tense,
    EVER,
    FN_CONTENT,
    FN_END,
    FN_RELATION,
    FN_RELATION_TEXT,
    FN_START,
    FN_TENSE,
    FN_TENSE_TEXT,
    FN_UNITS,
    FN_VALUE_TEXT,
    FN_VARIABLE_NAME,
    FN_VARIABLE_TEXT,
    GROUP_NAME_QUANTITY,
    GROUP_NAME_RELATION,
    GROUP_NAME_TENSE,
    GROUP_NAME_UNITS,
    GROUP_NAME_VALUE,
    GROUP_NUMBER_WHOLE_EXPRESSION,
    make_simple_numeric_regex,
    NumericalResultParser,
    PAST,
    PRESENT,
    ValidatorBase,
)
from crate_anon.nlp_manager.regex_units import (
    ALCOHOL,
    UK_ALCOHOL_UNITS_PER_DAY,
    UK_ALCOHOL_UNITS_PER_WEEK,
)

log = logging.getLogger(__name__)


# =============================================================================
# Alcohol
# =============================================================================


class AlcoholUnits(NumericalResultParser):
    """
    SUBSTANCE MISUSE.

    Alcohol consumption, specified explicitly as (UK) units per day or per
    week, or via non-numeric references to not drinking any.

    - Output is in UK units per week. A UK unit is 10 ml of ethanol [#f1]_ [#f2]_.
      UK NHS guidelines used to be "per week" and remain broadly week-based [#f1]_.
    - It doesn't attempt any understanding of other alcohol descriptions (e.g.
      "pints of beer", "glasses of wine", "bottles of vodka") so is expected to
      apply where a clinician has converted a (potentially mixed) alcohol
      description to a units-per-week calculation.

    .. [#f1] https://www.nhs.uk/live-well/alcohol-advice/calculating-alcohol-units/,
           accessed 2023-01-18.
    .. [#f2] https://en.wikipedia.org/wiki/Unit_of_alcohol
    """  # noqa: E501

    # There are no relevant Read codes for alcohol consumption in
    # v3ReadCode_PBCL.xlsx.

    # -------------------------------------------------------------------------
    # Regex building for tense-related statements
    # -------------------------------------------------------------------------

    # All these are verbose regexes, so don't omit \s+ for whitespace!
    PAST_ADVERBS = (
        "formerly",
        "once",
        "peak",
        "previously",
        "was",
    )
    PAST_ADVERBS_RE = noncapture_group(regex_or(*PAST_ADVERBS))
    PRESENT_ADVERBS = (
        r"at \s+ present",
        r"currently",
        r"has \s+ been",
        r"now",
        r"nowadays",
        r"presently",
        r"these \s+ days",
    )
    PRESENT_ADVERBS_RE = noncapture_group(regex_or(*PRESENT_ADVERBS))
    TEMPORAL_WORDS = tuple(
        at_wb_start_end(x) for x in PAST_ADVERBS + PRESENT_ADVERBS
    )
    TEMPORAL = noncapture_group(regex_or(*TEMPORAL_WORDS))
    OPT_TEMPORAL = optional_noncapture_group(regex_or(*TEMPORAL_WORDS))

    NEVER = "never"
    # "Never" is both temporal and negating and thus fiddly. We do *not*
    # include it in standard temporal words, or a statement about "has never
    # drunk >100 u/w" would be misinterpreted as positive.

    # -------------------------------------------------------------------------
    # Regex building for drinking alcohol (and when)
    # -------------------------------------------------------------------------

    DRINKING_PAST = (
        # Past infinitive: she used to drink
        r"\b used \s+ to \s+ drink \b",
        # Imperfect tense: she [adverb] drank
        rf"\b (?: {PAST_ADVERBS_RE} \s+ )? drank \b",
        # Perfect tense: has drunk
        rf"\b has (?: {PAST_ADVERBS_RE} \s+ )? drunk \b",
        # Past continuous tense: he was [adverb] drinking
        # Also abbreviated past continuous tense: previously drinking
        rf"\b {PAST_ADVERBS_RE} \s+ drinking \b",
    )
    # We don't allow the adverbs by themselves, to avoid something that isn't
    # explicitly about alcohol or drinking, e.g. "[insulin] currently 6
    # units/day".
    DRINKING_PRESENT = (
        # Present tense: he [adverb] drinks
        rf"\b (?: {PRESENT_ADVERBS_RE} \s+)? drinks \b",
        # Present continuous tense: he is [adverb] drinking
        rf"\b (?: is \s+)? (?: {PRESENT_ADVERBS_RE} \s+)? drinking \b",
    )
    DRINKING_PAST_PRESENT = DRINKING_PAST + DRINKING_PRESENT
    DRINKING = noncapture_group(regex_or(*DRINKING_PAST_PRESENT))
    OPT_DRINKING = optional_noncapture_group(regex_or(*DRINKING_PAST_PRESENT))
    ALCOHOL_PM_CONSUMPTION = rf"{ALCOHOL} (?: \s+ consumption \b)?"
    ALC = noncapture_group(ALCOHOL_PM_CONSUMPTION)
    OPT_ALC = optional_noncapture_group(ALCOHOL_PM_CONSUMPTION)

    # BRK: requires some sort of wordbreak or whitespace, but also disposes of
    # junk like some punctuation (e.g. "previously: none" versus "previously
    # none") and words like "at" (e.g. in "drinking at X units/week").
    BRK = noncapture_group(
        regex_or(
            r"\s* : \s*",  # colon +/- whitespace
            r"\s* \b at \b \s*",  # "at" +/- whitespace
            r"\s+",  # whitespace
            WORD_BOUNDARY,  # other word break
        )
    )

    # Move from more to less specific, or the less specific will capture first.
    ALCOHOL_DRINKING = rf"""
        {WORD_BOUNDARY}
            # Alcohol drinking:
            (?:
                    # 1. ... DRINKING ... [ALC] ...
                    {OPT_TEMPORAL} {BRK}
                    {DRINKING} {BRK}
                    {OPT_TEMPORAL} {BRK}
                    {OPT_ALC} {BRK}
                    {OPT_TEMPORAL}
                |
                    # 2. ... ALC ... [DRINKING] ...
                    {OPT_TEMPORAL} {BRK}
                    {ALC} {BRK}
                    {OPT_TEMPORAL} {BRK}
                    {OPT_DRINKING} {BRK}
                    {OPT_TEMPORAL}
            )
        {WORD_BOUNDARY}
    """

    _drinking_tense_dict = {}  # type: Dict[str, str]
    for _past in DRINKING_PAST + PAST_ADVERBS:
        _drinking_tense_dict[_past] = PAST
    for _present in DRINKING_PRESENT + PRESENT_ADVERBS:
        _drinking_tense_dict[_present] = PRESENT
    TENSE_PAST_PRESENT_LOOKUP = compile_regex_dict(_drinking_tense_dict)
    TENSE_NEVER_LOOKUP = compile_regex_dict({NEVER: EVER})

    # -------------------------------------------------------------------------
    # Regex building for "drinking alcohol at X units per week"
    # -------------------------------------------------------------------------

    # A temporal suffix allows e.g. "drinking X units/week previously".
    GROUP_NAME_SUFFIX = "suffix"
    group_suffix = r"\b \s*" + optional_named_capture_group(
        TEMPORAL, GROUP_NAME_SUFFIX
    )
    REGEX_ALCOHOL_UNITS = (
        make_simple_numeric_regex(
            quantity=ALCOHOL_DRINKING,
            units=regex_or(
                UK_ALCOHOL_UNITS_PER_DAY, UK_ALCOHOL_UNITS_PER_WEEK
            ),
            units_optional=False,
        )
        + group_suffix
    )

    # -------------------------------------------------------------------------
    # Regex building for "no alcohol" statements
    # -------------------------------------------------------------------------

    NONE = noncapture_group(
        WORD_BOUNDARY
        + noncapture_group(
            regex_or(
                "0",
                r"abstinent (?: \s+ from )?",
                NEVER,
                "no",
                "none",
                "zero",
            )
        )
        + WORD_BOUNDARY
    )
    TEETOTAL = noncapture_group(
        r"\b te[ea][-]?total(?:l?er)? \b",
    )
    HAS_NEVER_DRUNK = rf"\b has \s+ {NEVER} \s+ drunk \b"
    OPT_TEMPORAL_AND_OR_DRINKING_BRK = (
        f"{OPT_TEMPORAL} {BRK} {OPT_DRINKING} {BRK} {OPT_TEMPORAL} {BRK}"
    )
    NO_ALCOHOL = rf"""
        {WORD_BOUNDARY}
            # "No alcohol" statements.
            # Temporal modifiers might be found in all sorts of places.
            (?:
                    # 1. [DRINKING] ... ALC ... [DRINKING] ... NONE ...
                    {OPT_TEMPORAL_AND_OR_DRINKING_BRK}
                    {ALC} {BRK}
                    {OPT_TEMPORAL_AND_OR_DRINKING_BRK}
                    {NONE} {BRK}
                    {OPT_TEMPORAL_AND_OR_DRINKING_BRK}
                |
                    # 2. NONE ... ALC (e.g. "never alcohol")
                    {OPT_TEMPORAL_AND_OR_DRINKING_BRK}
                    {NONE} {BRK}
                    {OPT_TEMPORAL_AND_OR_DRINKING_BRK}
                    {ALC} {BRK}
                    {OPT_TEMPORAL_AND_OR_DRINKING_BRK}
                |
                    # 3. "has never drunk... alcohol"
                    {HAS_NEVER_DRUNK} {BRK} {ALC} {BRK}
                |
                    # 4. "teetotal" with typos
                    {TEETOTAL}
                # ... but not just "drinking... none" (could be water etc.)
            )
        {WORD_BOUNDARY}
    """

    # -------------------------------------------------------------------------
    # Other class variables
    # -------------------------------------------------------------------------

    NAME = "AlcoholUnits"
    PREFERRED_UNIT_COLUMN = "value_uk_units_per_week"
    UNIT_MAPPING = {
        UK_ALCOHOL_UNITS_PER_WEEK: 1,  # preferred unit
        UK_ALCOHOL_UNITS_PER_DAY: 7,  # 1 unit/day -> 7 units/week
    }

    # -------------------------------------------------------------------------
    # Init
    # -------------------------------------------------------------------------

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
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            regex_str_for_debugging=self.REGEX_ALCOHOL_UNITS,
            commit=commit,
        )
        self.compiled_regex_alcohol = compile_regex(self.REGEX_ALCOHOL_UNITS)
        self.units_to_factor = compile_regex_dict(self.UNIT_MAPPING)
        self.compiled_regex_no_alcohol = compile_regex(self.NO_ALCOHOL)

    # -------------------------------------------------------------------------
    # Parse
    # -------------------------------------------------------------------------

    def parse(
        self, text: str, debug: bool = False
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """
        Parse for two regexes which operate slightly differently.
        """
        if not text:
            return
        yield from self.parse_alcohol_units(text, debug)
        yield from self.parse_alcohol_none(text, debug)

    def parse_alcohol_units(
        self, text: str, debug: bool = False
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """
        We amend SimpleNumericalResultParser.parse() to deal with tense a bit
        better (e.g. "used to drink"). Comments from that version not repeated.
        That version also shortened a bit since we guarantee some aspects of
        the flags.
        """
        for m in self.compiled_regex_alcohol.finditer(text):
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(GROUP_NUMBER_WHOLE_EXPRESSION)
            variable_text = m.group(GROUP_NAME_QUANTITY)
            tense_text = m.group(GROUP_NAME_TENSE)
            relation_text = m.group(GROUP_NAME_RELATION)
            value_text = m.group(GROUP_NAME_VALUE)
            units = m.group(GROUP_NAME_UNITS)
            suffix_text = m.group(self.GROUP_NAME_SUFFIX)

            value_in_target_units = None
            if units:
                matched_unit, multiple_or_fn = get_regex_dict_match(
                    units, self.units_to_factor
                )
                if not matched_unit:
                    continue
                # MODIFIED: no need to check callable(multiple_or_fn); always
                # no
                value_in_target_units = to_float(value_text) * multiple_or_fn
            # MODIFIED: no need to check self.assume_preferred_unit (we never
            # assume that here)

            # MODIFIED: no need to check self.take_absolute (always yes)
            if value_in_target_units is not None:
                value_in_target_units = abs(value_in_target_units)

            tense, relation = common_tense(tense_text, relation_text)

            # MODIFIED: Extra bit here to detect tense information in a
            # different place:
            for temporal_info in (variable_text, suffix_text):
                if tense:
                    break
                tense = self._get_tense(temporal_info)
                if tense:
                    tense_text = temporal_info

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
                log.debug(f"Match {m} for {text!r} -> {result}")
            yield self.tablename, result

    def parse_alcohol_none(
        self, text: str, debug: bool = False
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """
        Deal with references to not drinking any alcohol (except those referred
        to as e.g. "0 units per week", which will be picked up by the
        units-per-week function -- that will be rare!).
        """
        for m in self.compiled_regex_no_alcohol.finditer(text):
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(GROUP_NUMBER_WHOLE_EXPRESSION)
            tense = self._get_tense(matching_text)
            tense_text = matching_text if tense else None

            result = {
                FN_VARIABLE_NAME: self.variable,
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,
                FN_VARIABLE_TEXT: matching_text,
                FN_RELATION_TEXT: None,
                FN_RELATION: None,
                FN_VALUE_TEXT: matching_text,
                FN_UNITS: None,
                self.target_unit: 0,  # zero units
                FN_TENSE_TEXT: tense_text,
                FN_TENSE: tense,
            }
            if debug:
                log.debug(f"Match {m} for {text!r} -> {result}")
            yield self.tablename, result

    def _get_tense(self, text: str) -> Optional[str]:
        """
        Find a tense indicator and return the corresponding text, or None.
        """
        # We deal with "never" first because otherwise "never drank" may hit
        # "[optional_stuff] drank" and be classified as the past tense.
        _, tense = get_regex_dict_search(text, self.TENSE_NEVER_LOOKUP)
        if not tense:
            _, tense = get_regex_dict_search(
                text, self.TENSE_PAST_PRESENT_LOOKUP
            )
        return tense

    # -------------------------------------------------------------------------
    # Test
    # -------------------------------------------------------------------------

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        # Test via e.g.:
        #   pytest -k TestSubstanceMisuse  # self-tests
        #   crate_run_crate_nlp_demo - --processors AlcoholUnits  # interactive
        no_results = []
        six_no_tense = [{self.target_unit: 6, FN_TENSE: None}]
        six_past = [{self.target_unit: 6, FN_TENSE: PAST}]
        six_present = [{self.target_unit: 6, FN_TENSE: PRESENT}]
        forty_two_present = [{self.target_unit: 6 * 7, FN_TENSE: PRESENT}]
        under_6_present = [
            {self.target_unit: 6, FN_RELATION: "<", FN_TENSE: PRESENT}
        ]
        over_200_present = [
            {self.target_unit: 200, FN_RELATION: ">", FN_TENSE: PRESENT}
        ]
        no_alcohol_no_tense = [{self.target_unit: 0, FN_TENSE: None}]
        no_alcohol_past = [{self.target_unit: 0, FN_TENSE: PAST}]
        no_alcohol_present = [{self.target_unit: 0, FN_TENSE: PRESENT}]
        no_alcohol_ever = [{self.target_unit: 0, FN_TENSE: EVER}]
        self.detailed_test_multiple(
            [
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # No results expected:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol", no_results),
                ("He used to drink like a fish", no_results),
                ("[e.g. insulin] currently 6 units per week", no_results),
                ("[e.g. insulin] previously 6 units per week", no_results),
                ("[could be insulin] peak 6 u/w", no_results),
                ("[!] methylalcohol 6 u/w", no_results),
                ("[not starts with no] Alcohol: not explored", no_results),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Value with no tense:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol 6 u/w", six_no_tense),
                ("Alcohol - 6 u/w", six_no_tense),
                ("EtOH = 6 u/w", six_no_tense),
                ("EtOH = 6 u/wk", six_no_tense),
                ("Alcohol (units/week): 6", six_no_tense),
                ("Ethanol 6 units/week", six_no_tense),
                ("[not international but] alcohol 6 IU/week", six_no_tense),
                ("alcohol 6 I.U./week", six_no_tense),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Past tense:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol: was 6 u/w", six_past),  # other tenses fail (= good)
                ("Alcohol: formerly 6 u/w", six_past),
                ("Alcohol: previously 6 u/w", six_past),
                ("Alcohol: once 6 u/w", six_past),
                ("Alcohol: peak 6 u/w", six_past),
                ("Used to drink 6 u/w", six_past),
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
                ("Alcohol: 6 u/w previously", six_past),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Present tense:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Drinks 6 units per week", six_present),
                ("Drinks 6 alcohol units per week", six_present),
                ("Drinks 6 UK units per week", six_present),
                ("Drinks 6 UK alcohol units per week", six_present),
                ("[silly] Drinks 6 UK alcohol IU per week", six_present),
                ("Drinks 6 units/d", forty_two_present),
                ("Drinks 6 units/dy", forty_two_present),
                ("Drinks 6 units/day", forty_two_present),
                ("Currently drinks 6 units per week", six_present),
                ("These days drinks 6 units per week", six_present),
                ("Now drinks 6 units per week", six_present),
                ("Nowadays drinks 6 units per week", six_present),
                ("Drinking 6 units per week", six_present),
                ("Currently drinking 6 units per week", six_present),
                ("Presently drinking 6 units per week", six_present),
                ("Alcohol: currently 6 u/w", six_present),
                ("Alcohol: presently 6 u/w", six_present),
                ("In terms of alcohol she drinks 6 units/week", six_present),
                ("Has been drinking 6 units per week", six_present),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Inequalities:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol: presently less than 6 u/w", under_6_present),
                ("Alcohol: presently under 6 u/w", under_6_present),
                ("Alcohol: presently >200 u/w", over_200_present),
                ("Alcohol: currently more than 200 u/w", over_200_present),
                ("Alcohol: currently over 200 u/w", over_200_present),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # References to not drinking -- no tense:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol: none", no_alcohol_no_tense),
                ("Teetotal", no_alcohol_no_tense),
                ("Tee-total", no_alcohol_no_tense),  # typo
                ("Teetotaller", no_alcohol_no_tense),
                ("Teetotaler", no_alcohol_no_tense),  # typo
                ("Abstinent from alcohol", no_alcohol_no_tense),
                ("Alcohol: abstinent", no_alcohol_no_tense),
                ("Alcohol: zero", no_alcohol_no_tense),
                ("Alcohol: 0", no_alcohol_no_tense),
                ("Alcohol: no", no_alcohol_no_tense),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # References to not drinking -- past tense:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol: was abstinent", no_alcohol_past),
                ("Alcohol: previously abstinent", no_alcohol_past),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # References to not drinking -- present tense:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Alcohol: has been abstinent", no_alcohol_present),
                ("Alcohol: currently abstinent", no_alcohol_present),
                ("Alcohol: currently none", no_alcohol_present),
                ("Drinks no alcohol", no_alcohol_present),
                ("Drinks zero alcohol", no_alcohol_present),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # References to not drinking -- ever:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Has never drunk alcohol", no_alcohol_ever),
                ("Never drank alcohol", no_alcohol_ever),
                ("Alcohol: never", no_alcohol_ever),
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Vague references to not drinking, not interpreted:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                ("Has not drunk alcohol", no_results),
            ],
            verbose=verbose,
        )


class AlcoholUnitsValidator(ValidatorBase):
    """
    Validator for AlcoholUnits (see help for explanation).
    """

    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return AlcoholUnits.NAME, [AlcoholUnits.ALCOHOL_DRINKING]


# =============================================================================
# All classes in this module
# =============================================================================

ALL_SUBSTANCE_MISUSE_NLP_AND_VALIDATORS = [
    (AlcoholUnits, AlcoholUnitsValidator),
]
