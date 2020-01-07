#!/usr/bin/env python

"""
crate_anon/nlp_manager/parse_haematology.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Python regex-based NLP processors for haematology tests.**

All inherit from
:class:`crate_anon.nlp_manager.regex_parser.NumeratorOutOfDenominatorParser`
and are constructed with these arguments:

nlpdef:
    a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
cfgsection:
    the name of a CRATE NLP config file section (from which we may
    choose to get extra config information)
commit:
    force a COMMIT whenever we insert data? You should specify this
    in multiprocess mode, or you may get database deadlocks.

"""

from abc import ABC
import logging
from typing import List, Optional, Tuple

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    OPTIONAL_POC,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    SimpleNumericalResultParser,
    TENSE_INDICATOR,
    ValidatorBase,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.regex_numbers import SIGNED_FLOAT
from crate_anon.nlp_manager.regex_units import (
    BILLION_PER_L,
    CELLS_PER_CUBIC_MM_OR_MICROLITRE,
    G_PER_DL,
    G_PER_L,
    L_PER_L,
    MG_PER_DL,
    MG_PER_L,
    MM_PER_H,
    PERCENT,
    TRILLION_PER_L,
)

log = logging.getLogger(__name__)


# =============================================================================
# Haemoglobin (Hb)
# =============================================================================

class Haemoglobin(SimpleNumericalResultParser):
    """
    Haemoglobin (Hb).

    UK reporting for haemoglobin switched in 2013 from g/dL to g/L; see
    e.g.

    - http://www.pathology.leedsth.nhs.uk/pathology/Portals/0/PDFs/BP-2013-02%20Hb%20units.pdf
    - http://www.acb.org.uk/docs/default-source/committees/scientific/guidelines/acb/pathology-harmony-haematology.pdf

    The *DANGER* remains that "Hb 9" may have been from someone assuming
    old-style units, 9 g/dL = 90 g/L, but this will be interpreted as 9 g/L.
    This problem is hard to avoid.

    """  # noqa
    HAEMOGLOBIN = fr"""
        (?: {WORD_BOUNDARY} (?: Ha?emoglobin | Hb | HGB ) {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {HAEMOGLOBIN} )                 # group for "Hb" or equivalent
        {OPTIONAL_POC}
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?            # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                   # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                 # optional group for units
            {G_PER_L}                          # good
            | {G_PER_DL}                       # good
        )?
    """
    NAME = "Haemoglobin"
    PREFERRED_UNIT_COLUMN = "value_g_L"
    UNIT_MAPPING = {
        G_PER_L: 1,  # preferred unit
        G_PER_DL: 10,  # older unit (e.g. 2000)
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("Haemoglobin (should fail)", []),  # should fail; no values
            ("Haemoglobin 90 (should succeed)", [90]),
            ("Hemoglobin = 60", [60]),
            ("Hb 6 g/dL", [60]),
            ("Hb 60 g/L", [60]),
            ("Hb <80", [80]),
            ("Hb <80 g/L", [80]),
            ("Hb was 62", [62]),
            ("Hb was 62 g/L", [62]),
            ("Hb was 62 (L) g/L", [62]),
            ("Haemoglobin      |       7.6 (H)      | g/dL", [76]),
            ("Hb-96", [96]),
            ("HGB, POC 96", [96]),
        ], verbose=verbose)


class HaemoglobinValidator(ValidatorBase):
    """
    Validator for Haemoglobin
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Haemoglobin.NAME, [Haemoglobin.HAEMOGLOBIN]


# =============================================================================
# Haematocrit (Hct)
# =============================================================================

class Haematocrit(SimpleNumericalResultParser):
    """
    Haematocrit (Hct).
    """
    HAEMATOCRIT = fr"""
        (?: {WORD_BOUNDARY} (?: Ha?ematocrit | Hct ) {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {HAEMATOCRIT} )               # group for "haematocrit" or equivalent
        {OPTIONAL_POC}
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?          # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                 # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )              # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                               # optional group for units
            {L_PER_L}                          # good
        )?
    """
    NAME = "Haematocrit"
    PREFERRED_UNIT_COLUMN = "value_L_L"
    UNIT_MAPPING = {
        L_PER_L: 1,  # preferred unit
        # not MG_PER_DL, MG_PER_L
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("Haematocrit (should fail)", []),  # should fail; no values
            ("Haematocrit 0.4 (should succeed)", [0.4]),
            ("Hematocrit = 0.4", [0.4]),
            ("Hct 0.3 L/L", [0.3]),
            ("Haematocrit         |       0.33 (H)      | L/L", [0.33]),
            ("my haematocrit was 0.3; his haematocrit was 0.4!", [0.3, 0.4]),
            ("Hct-0.48", [0.48]),
        ], verbose=verbose)


class HaematocritValidator(ValidatorBase):
    """
    Validator for Haematocrit
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Haematocrit.NAME, [Haematocrit.HAEMATOCRIT]


# =============================================================================
#  RBCs
# =============================================================================

class RBC(SimpleNumericalResultParser):
    """
    Red blood cell count.

    Typical:

    .. code-block:: none

        RBC, POC    4.84            10*12/L
        RBC, POC    9.99    (H)     10*12/L
    """
    RED_BLOOD_CELLS = fr"""
        (?:
            {WORD_BOUNDARY}
            (?:
                # Red [blood] cell[s] [(RBC)] [count]
                Red \b \s* (?: blood \s*)? \b cells? \b
                    (?:\s* \(RBC\) )?
                    (?:\s* count \b )?
                # RBC(s)
                | (?: RBCs? )
            )
        )
    """
    # Beware: \( or \) next to \b becomes unhappy.
    REGEX = fr"""
        ( {RED_BLOOD_CELLS} )              # group for RBCs or equivalent
        {OPTIONAL_POC}
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {TRILLION_PER_L}                        # good
            | {CELLS_PER_CUBIC_MM_OR_MICROLITRE}    # good
            | {BILLION_PER_L}                       # bad
        )?
    """
    NAME = "RBC"
    PREFERRED_UNIT_COLUMN = "value_trillion_per_l"
    UNIT_MAPPING = {
        TRILLION_PER_L: 1,  # preferred unit; 10^12/L or "per pL"
        CELLS_PER_CUBIC_MM_OR_MICROLITRE: 1e-6,
        # not BILLION_PER_L
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("RBC (should fail)", []),  # should fail; no values
            ("RBC 6", [6]),
            ("RBC = 6", [6]),
            ("RBC 6 x 10^9/L", []),
            ("RBC 6 x 10 ^ 9 / L", []),
            ("RBC 6 x 10 ^ 12 / L", [6]),
            ("RBC 6    10*12/L", [6]),
            ("RBCs 6.2", [6.2]),
            ("red cells 6.2", [6.2]),
            ("red blood cells 6.2", [6.2]),
            ("red blood cell count 6.2", [6.2]),
            ("red blood cells 5000000/mm3", [5]),
            ("red blood cells 5000000 cell/mm3", [5]),
            ("red blood cells 5000000 cells/mm3", [5]),
            ("red blood cells 5000000 per cubic mm", [5]),
            ("red blood cells 5000000 per cmm", [5]),
            ("RBC – 6", [6]),  # en dash
            ("RBC—6", [6]),  # em dash
            ("RBC -- 6", [6]),  # double hyphen used as dash
            ("RBC - 6", [6]),
            ("RBC-6.5", [6.5]),
            ("RBC POC    4.84            10*12/L", [4.84]),
            ("RBC, POC    4.84            10*12/L", [4.84]),
            ("RBC, POC    4.84   (H)      10*12/L", [4.84]),
            ("red blood cells count 6.2", [6.2]),
            ("red blood cells (RBC) 6.2", [6.2]),
        ], verbose=verbose)


class RBCValidator(ValidatorBase):
    """
    Validator for RBC
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return RBC.NAME, [RBC.RED_BLOOD_CELLS]


# =============================================================================
# Erythrocyte sedimentation rate (ESR)
# =============================================================================

class Esr(SimpleNumericalResultParser):
    """
    Erythrocyte sedimentation rate (ESR).
    """
    ESR = fr"""
        (?: {WORD_BOUNDARY}
            (?: (?: Erythrocyte [\s]+ sed(?:\.|imentation)? [\s]+ rate)
                | ESR )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {ESR} )                           # group for "ESR" or equivalent
        {OPTIONAL_POC}
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?              # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                     # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                  # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                   # optional group for units
            {MM_PER_H}                          # good
            | {MG_PER_DL}                       # bad
            | {MG_PER_L}                        # bad
        )?
    """
    NAME = "ESR"
    PREFERRED_UNIT_COLUMN = "value_mm_h"
    UNIT_MAPPING = {
        MM_PER_H: 1,       # preferred unit
        # not MG_PER_DL, MG_PER_L
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("ESR (should fail)", []),  # should fail; no values
            ("ESR 6 (should succeed)", [6]),
            ("ESR = 6", [6]),
            ("ESR 6 mm/h", [6]),
            ("ESR <10", [10]),
            ("ESR <10 mm/hr", [10]),
            ("ESR >100", [100]),
            ("ESR >100 mm/hour", [100]),
            ("ESR was 62", [62]),
            ("ESR was 62 mm/h", [62]),
            ("ESR was 62 (H) mm/h", [62]),
            ("ESR was 62 mg/dl (should fail, wrong units)", []),
            ("Erythrocyte sed. rate was 19", [19]),
            ("his erythrocyte sedimentation rate was 19", [19]),
            ("erythrocyte sedimentation rate was 19", [19]),
            ("ESR 1.9 mg/L", []),  # wrong units
            ("ESR 1.9 (H) mg/L", []),  # wrong units
            ("ESR        |       1.9 (H)      | mg/L", []),
            ("my ESR was 15, but his ESR was 89!", [15, 89]),
            ("ESR-18", [18]),
        ], verbose=verbose)


class EsrValidator(ValidatorBase):
    """
    Validator for Esr
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Esr.NAME, [Esr.ESR]


# =============================================================================
# White blood cell count and differential
# =============================================================================
# Do NOT accept my handwritten abbreviations with slashed zeros, e.g.
#       L0 lymphocytes
#       N0 neutrophils
#       M0 monocytes
#       B0 basophils
#       E0 eosinophils
# ... too likely that these are interpreted in wrong contexts, particularly
# if we are not allowing units, like "M0 3": macrophages 3 x 10^9/L, or part
# of "T2 N0 M0 ..." cancer staging?

class WbcBase(SimpleNumericalResultParser, ABC):
    """
    DO NOT USE DIRECTLY. White cell count base class.
    """
    PREFERRED_UNIT_COLUMN = "value_billion_per_l"
    UNIT_MAPPING = {
        BILLION_PER_L: 1,     # preferred unit: 10^9 / L
        CELLS_PER_CUBIC_MM_OR_MICROLITRE: 0.001,
        # ... 1000 cells/mm^3 -> 1 x 10^9 / L
        # but NOT percent (too hard to interpret relative differentials
        # reliably)
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 cell_type_regex_text: str,
                 variable: str,
                 commit: bool = False) -> None:
        """

        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the name of a CRATE NLP config file section (from which we may
                choose to get extra config information)
            cell_type_regex_text:
                text for regex for the cell type, representing e.g.
                "monocytes" or "basophils"
            variable:
                used as the record value for ``variable_name``
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.make_wbc_regex(cell_type_regex_text),
            variable=variable,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    @staticmethod
    def make_wbc_regex(cell_type_regex_text: str) -> str:
        """
        Makes a regular expression (as text) from text representing a cell
        type.
        """
        return fr"""
            ({cell_type_regex_text})        # group for cell type name
            {OPTIONAL_POC}
            {OPTIONAL_RESULTS_IGNORABLES}
            ({TENSE_INDICATOR})?            # optional group for tense indicator
            {OPTIONAL_RESULTS_IGNORABLES}
            ({RELATION})?                   # optional group for relation
            {OPTIONAL_RESULTS_IGNORABLES}
            ({SIGNED_FLOAT})                # group for value
            {OPTIONAL_RESULTS_IGNORABLES}
            (                               # optional units, good and bad
                {BILLION_PER_L}                      # good
                | {CELLS_PER_CUBIC_MM_OR_MICROLITRE} # good
                | {PERCENT}                          # bad, so we can ignore it
            )?
        """


# -----------------------------------------------------------------------------
# WBC
# -----------------------------------------------------------------------------

class Wbc(WbcBase):
    """
    White cell count (WBC, WCC).
    """
    WBC = r"""
        (?: \b (?:
            (?:                 # White blood cells, white cell count, etc.
                White\b [\s]* (?:\bblood\b)? [\s]* \bcell[s]?\b
                [\s]* (?:\bcount\b)? [\s]*
                (?:     # optional suffix WBC, (WBC), (WBCC), (WCC), etc.
                    [\(]? (?: WBC | WBCC | WCC) [\)]?
                )?
            )
            | (?:               # just WBC(s), WBCC, WCC
                (?: WBC[s]? | WBCC | WCC )
            )
        ) \b )
    """
    NAME = "WBC"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.WBC,
                         variable=self.NAME)

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("WBC (should fail)", []),  # should fail; no values
            ("WBC 6", [6]),
            ("WBC = 6", [6]),
            ("WBC 6 x 10^9/L", [6]),
            ("WBC 6 x 10 ^ 9 / L", [6]),
            ("WCC 6.2", [6.2]),
            ("white cells 6.2", [6.2]),
            ("white cells 6.2", [6.2]),
            ("white cells 9800/mm3", [9.8]),
            ("white cells 9800 cell/mm3", [9.8]),
            ("white cells 9800 cells/mm3", [9.8]),
            ("white cells 9800 per cubic mm", [9.8]),
            ("white cells 9800 per cmm", [9.8]),
            ("white cells 17,600/mm3", [17.6]),
            ("white cells 17,600/μL", [17.6]),
            ("white cells 17,600/microlitre", [17.6]),
            ("WBC – 6", [6]),  # en dash
            ("WBC—6", [6]),  # em dash
            ("WBC -- 6", [6]),  # double hyphen used as dash
            ("WBC - 6", [6]),
            ("WBC-6.5", [6.5]),
            ("WBC, POC 6.5", [6.5]),
        ], verbose=verbose)


class WbcValidator(ValidatorBase):
    """
    Validator for Wbc
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Wbc.NAME, [Wbc.WBC]


# -----------------------------------------------------------------------------
# Neutrophils
# -----------------------------------------------------------------------------

class Neutrophils(WbcBase):
    """
    Neutrophil count (absolute).
    """
    NEUTROPHILS = r"""
        (?:
            (?: \b absolute \s* )?
            \b (?: Neut(?:r(?:o(?:phil)?)?)?s? | N0 ) \b
            (?: \s* count \b )?
        )
    """
    NAME = "neutrophils"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.NEUTROPHILS,
                         variable=self.NAME)

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("neutrophils (should fail)", []),  # should fail; no values
            ("absolute neutrophil count 6", [6]),
            ("neuts = 6", [6]),
            ("N0 6 x 10^9/L", [6]),
            ("neutrophil count 6 x 10 ^ 9 / L", [6]),
            ("neutrs 6.2", [6.2]),
            ("neutrophil 6.2", [6.2]),
            ("neutrophils 6.2", [6.2]),
            ("n0 9800/mm3", [9.8]),
            ("absolute neutrophils 9800 cell/mm3", [9.8]),
            ("neutrophils count 9800 cells/mm3", [9.8]),
            ("neuts 9800 per cmm", [9.8]),
            ("n0 9800 per cubic mm", [9.8]),
            ("n0 17,600/mm3", [17.6]),
            ("neuts-17", [17]),
        ], verbose=verbose)


class NeutrophilsValidator(ValidatorBase):
    """
    Validator for Neutrophils
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Neutrophils.NAME, [Neutrophils.NEUTROPHILS]


# -----------------------------------------------------------------------------
# Lymphocytes
# -----------------------------------------------------------------------------

class Lymphocytes(WbcBase):
    """
    Lymphocyte count (absolute).
    """
    LYMPHOCYTES = r"""
        (?:
            (?: \b absolute \s* )?
            \b Lymph(?:o(?:cyte)?)?s? \b
            (?: \s* count \b )?
        )
    """
    NAME = "lymphocytes"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.LYMPHOCYTES,
                         variable=self.NAME)

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("lymphocytes (should fail)", []),  # should fail; no values
            ("absolute lymphocyte count 6", [6]),
            ("lymphs = 6", [6]),
            ("L0 6 x 10^9/L (should fail)", []),
            ("lymphocyte count 6 x 10 ^ 9 / L", [6]),
            ("lymphs 6.2", [6.2]),
            ("lymph 6.2", [6.2]),
            ("lympho 6.2", [6.2]),
            ("lymphos 9800/mm3", [9.8]),
            ("absolute lymphocytes 9800 cell/mm3", [9.8]),
            ("lymphocytes count 9800 cells/mm3", [9.8]),
            ("lymphocytes 9800 per cmm", [9.8]),
            ("lymphs-6.3", [6.3]),
            # We are not supporting "L0":
            ("l0 9800 per cubic mm (should fail)", []),
            ("l0 9800 per cmm (should fail)", []),
            ("l0 17,600/mm3 (should fail)", []),
        ], verbose=verbose)


class LymphocytesValidator(ValidatorBase):
    """
    Validator for Lymphocytes
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Lymphocytes.NAME, [Lymphocytes.LYMPHOCYTES]


# -----------------------------------------------------------------------------
# Monocytes
# -----------------------------------------------------------------------------

class Monocytes(WbcBase):
    """
    Monocyte count (absolute).
    """
    MONOCYTES = r"""
        (?:
            (?: \b absolute \s* )?
            \b Mono(?:cyte)?s? \b
            (?: \s* count \b )?
        )
    """
    NAME = "monocytes"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.MONOCYTES,
                         variable=self.NAME)

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("monocytes (should fail)", []),  # should fail; no values
            ("absolute monocyte count 6", [6]),
            ("monos = 6", [6]),
            ("M0 6 x 10^9/L (should fail)", []),
            ("monocyte count 6 x 10 ^ 9 / L", [6]),
            ("monos 6.2", [6.2]),
            ("mono 6.2", [6.2]),
            ("monos 9800/mm3", [9.8]),
            ("absolute mono 9800 cell/mm3", [9.8]),
            ("monocytes count 9800 cells/mm3", [9.8]),
            ("monocytes 9800 per cmm", [9.8]),
            ("monocytes-5.2", [5.2]),
            # We are not supporting "M0":
            ("m0 9800 per cubic mm (should fail)", []),
            ("m0 17,600/mm3 (should fail)", []),
        ], verbose=verbose)


class MonocytesValidator(ValidatorBase):
    """
    Validator for Monocytes
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Monocytes.NAME, [Monocytes.MONOCYTES]


# -----------------------------------------------------------------------------
# Basophils
# -----------------------------------------------------------------------------

class Basophils(WbcBase):
    """
    Basophil count (absolute).
    """
    BASOPHILS = r"""
        (?:
            (?: \b absolute \s* )?
            \b Baso(?:phil)?s? \b
            (?: \s* count \b )?
        )
    """
    NAME = "basophils"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.BASOPHILS,
                         variable=self.NAME)

    def test(self, verbose=False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("basophils (should fail)", []),  # should fail; no values
            ("absolute basophil count 6", [6]),
            ("basos = 6", [6]),
            ("B0 6 x 10^9/L (should fail)", []),
            ("basophil count 6 x 10 ^ 9 / L", [6]),
            ("basos 6.2", [6.2]),
            ("baso 6.2", [6.2]),
            ("basos 9800/mm3", [9.8]),
            ("absolute basophil 9800 cell/mm3", [9.8]),
            ("basophils count 9800 cells/mm3", [9.8]),
            ("basophils 9800 per cmm", [9.8]),
            ("basophils-5.2", [5.2]),
            # We are not supporting "B0":
            ("b0 9800 per cubic mm (should fail)", []),
            ("b0 17,600/mm3 (should fail)", []),
        ], verbose=verbose)


class BasophilsValidator(ValidatorBase):
    """
    Validator for Basophils
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Basophils.NAME, [Basophils.BASOPHILS]


# -----------------------------------------------------------------------------
# Eosinophils
# -----------------------------------------------------------------------------

class Eosinophils(WbcBase):
    """
    Eosinophil count (absolute).
    """
    EOSINOPHILS = r"""
        (?:
            (?: \b absolute \s* )?
            \b Eo(?:sin(?:o(?:phil)?)?)?s? \b
            (?: \s* count \b )?
        )
    """
    NAME = "eosinophils"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.EOSINOPHILS,
                         variable=self.NAME)

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("eosinophils (should fail)", []),  # should fail; no values
            ("absolute eosinophil count 6", [6]),
            ("eos = 6", [6]),
            ("E0 6 x 10^9/L (should fail)", []),
            ("eosinophil count 6 x 10 ^ 9 / L", [6]),
            ("eosins 6.2", [6.2]),
            ("eosino 6.2", [6.2]),
            ("eosinos 9800/mm3", [9.8]),
            ("absolute eosinophil 9800 cell/mm3", [9.8]),
            ("eosinophils count 9800 cells/mm3", [9.8]),
            ("eosinophils 9800 per cmm", [9.8]),
            ("eosinophils-5.3", [5.3]),
            # We are not supporting "E0":
            ("e0 9800 per cubic mm (should fail)", []),
            ("e0 17,600/mm3 (should fail)", []),
        ], verbose=verbose)


class EosinophilsValidator(ValidatorBase):
    """
    Validator for Eosinophils
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Eosinophils.NAME, [Eosinophils.EOSINOPHILS]


# -----------------------------------------------------------------------------
# Platelet count
# -----------------------------------------------------------------------------

class Platelets(WbcBase):
    """
    Platelet count.

    Not actually a white blood cell, of course, but can share the same base
    class; platelets are expressed in the same units, of 10^9 / L.
    Typical values 150–450 ×10^9 / L (or 150,000–450,000 per μL).
    """
    PLATELETS = r"""
        (?:
            \b (?: Platelets? | plts? ) \b  # platelet(s), plt(s)
            (?: \s* count \b )?             # optional "count"
        )
    """
    NAME = "platelets"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.PLATELETS,
                         variable=self.NAME)

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("platelets (should fail)", []),  # should fail; no values
            ("platelet count 150", [150]),
            ("plt = 150", [150]),
            ("PLT 150 x 10^9/L", [150]),
            ("platelet count 150 x 10 ^ 9 / L", [150]),
            ("plt 400", [400]),
            ("plts 400", [400]),
            ("plt 400000/mm3", [400]),
            ("plt count 400000/μL", [400]),
            ("plts 400000 per microliter", [400]),
        ], verbose=verbose)


class PlateletsValidator(ValidatorBase):
    """
    Validator for Platelets
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Platelets.NAME, [Platelets.PLATELETS]


# =============================================================================
# All classes in this module
# =============================================================================

ALL_HAEMATOLOGY_NLP_AND_VALIDATORS = [
    (Basophils, BasophilsValidator),
    (Eosinophils, EosinophilsValidator),
    (Esr, EsrValidator),
    (Haematocrit, HaematocritValidator),
    (Haemoglobin, HaemoglobinValidator),
    (Lymphocytes, LymphocytesValidator),
    (Monocytes, MonocytesValidator),
    (Neutrophils, NeutrophilsValidator),
    (Platelets, PlateletsValidator),
    (RBC, RBCValidator),
    (Wbc, WbcValidator),
]
ALL_HAEMATOLOGY_NLP, ALL_HAEMATOLOGY_VALIDATORS = zip(*ALL_HAEMATOLOGY_NLP_AND_VALIDATORS)  # noqa


# =============================================================================
# Command-line entry point
# =============================================================================

def test_all(verbose: bool = False) -> None:
    """
    Test all parsers in this module.
    """
    for cls in ALL_HAEMATOLOGY_NLP:
        cls(None, None).test(verbose=verbose)


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    test_all(verbose=True)
