#!/usr/bin/env python
# crate_anon/nlp_manager/parse_haematology.py

import logging
import typing
from typing import Optional

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    NumericalResultParser,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    SIGNED_FLOAT,
    TENSE_INDICATOR,
    BILLION_PER_L,
    CELLS_PER_CUBIC_MM,
    MM_PER_H,
    PERCENT,
    WORD_BOUNDARY,
)

log = logging.getLogger(__name__)


# =============================================================================
#  Erythrocyte sedimentation rate (ESR)
# =============================================================================

class Esr(NumericalResultParser):
    ESR = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                (?: Erythrocyte [\s]+ sed(?:\.|imentation)? [\s]+ rate)
                | (?:ESR)
            )
            {WORD_BOUNDARY}
        )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    REGEX = r"""
        ( {ESR} )                           # group for "ESR" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?              # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                     # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                  # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {UNITS_MM_H} )?                   # optional group for units
    """.format(
        ESR=ESR,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        UNITS_MM_H=MM_PER_H,
    )
    NAME = "ESR"
    PREFERRED_UNIT_COLUMN = "value_mm_h"
    UNIT_MAPPING = {
        MM_PER_H: 1,       # preferred unit
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit
        )

    def test(self):
        self.test_parser([
            "ESR (should fail)",  # should fail; no values
            "ESR 6 (should succeed)",
            "ESR = 6",
            "ESR 6 mm/h",
            "ESR <10",
            "ESR <10 mm/hr",
            "ESR >100",
            "ESR >100 mm/hour",
            "ESR was 62",
            "ESR was 62 mm/h",
            "ESR was 62 mg/dl (should give null units)",
            "Erythrocyte sed. rate was 19",
            "his erythrocyte sedimentation rate was 19",
            "erythrocyte sedimentation rate was 19",
            "ESR        |       1.9 (H)      | mg/L",
            "my ESR was 15, but his ESR was 89!",
        ])


# =============================================================================
#  White blood cell count and differential
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

class WbcBase(NumericalResultParser):
    PREFERRED_UNIT_COLUMN = "value_billion_per_l"
    UNIT_MAPPING = {
        BILLION_PER_L: 1,     # preferred unit: 10^9 / L
        CELLS_PER_CUBIC_MM: 0.001,  # 1000 cells/mm^3 -> 1 x 10^9 / L
        # but NOT percent (too hard to interpret relative differentials
        # reliably)
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 cell_type_regex_text: str,
                 variable: str,
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.make_wbc_regex(cell_type_regex_text),
            variable=variable,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit
        )

    @staticmethod
    def make_wbc_regex(cell_type_regex_text: str) -> typing.re.Pattern:
        return r"""
            ({CELL_TYPE})                   # group for cell type name
            {OPTIONAL_RESULTS_IGNORABLES}
            ({TENSE_INDICATOR})?            # optional group for tense indicator
            {OPTIONAL_RESULTS_IGNORABLES}
            ({RELATION})?                   # optional group for relation
            {OPTIONAL_RESULTS_IGNORABLES}
            ({SIGNED_FLOAT})                # group for value
            {OPTIONAL_RESULTS_IGNORABLES}
            (                               # optional units, good and bad
                {UNITS_BILLION_PER_L}           # good
                | {UNITS_CELLS_PER_CUBIC_MM}    # good
                | {UNITS_PERCENT}               # bad, so we can ignore it
            )?
        """.format(
            CELL_TYPE=cell_type_regex_text,
            OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
            TENSE_INDICATOR=TENSE_INDICATOR,
            RELATION=RELATION,
            SIGNED_FLOAT=SIGNED_FLOAT,
            UNITS_BILLION_PER_L=BILLION_PER_L,
            UNITS_CELLS_PER_CUBIC_MM=CELLS_PER_CUBIC_MM,
            UNITS_PERCENT=PERCENT,
        )


# -----------------------------------------------------------------------------
# WBC
# -----------------------------------------------------------------------------

class Wbc(WbcBase):
    WBC = r"""
        (?:
            \b
            (?:
                (?:                 # White blood cells, white cell count, etc.
                    White\b
                    [\s]*
                    (?:\bblood\b)?
                    [\s]*
                    \bcell[s]?\b
                    [\s]*
                    (?:\bcount\b)?
                    [\s]*
                    (?:                 # optional suffix (WBC), (WBCC), (WCC)
                        [\(]?           # brackets are optional
                        (?: WBC | WBCC | WCC)
                        [\)]?
                    )?
                )
                | (?:               # just WBC(s), WBCC, WCC
                    (?: WBC[s]? | WBCC | WCC )
                )
            )
            \b
        )
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.WBC,
                         variable="WBC")

    def test(self) -> None:
        self.test_parser([
            "WBC (should fail)",  # should fail; no values
            "WBC 6",
            "WBC = 6",
            "WBC 6 x 10^9/L",
            "WBC 6 x 10 ^ 9 / L",
            "WCC 6.2",
            "white cells 6.2",
            "white cells 6.2",
            "white cells 9800/mm3",
            "white cells 9800 cell/mm3",
            "white cells 9800 cells/mm3",
            "white cells 9800 per cubic mm",
            "white cells 17,600/mm3",
        ])


# -----------------------------------------------------------------------------
#  Neutrophils
# -----------------------------------------------------------------------------

class Neutrophils(WbcBase):
    NEUTROPHILS = r"""
        (?:
            (?: \b absolute \s* )?
            \b
            (?:
                Neut(?:r(?:o(?:phil)?)?)?s?
                |
                N0
            )
            \b
            (?: \s* count \b )?
        )
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.NEUTROPHILS,
                         variable="neutrophils")

    def test(self) -> None:
        self.test_parser([
            "neutrophils (should fail)",  # should fail; no values
            "absolute neutrophil count 6",
            "neuts = 6",
            "N0 6 x 10^9/L",
            "neutrophil count 6 x 10 ^ 9 / L",
            "neutrs 6.2",
            "neutrophil 6.2",
            "neutrophils 6.2",
            "n0 9800/mm3",
            "absolute neutrophils 9800 cell/mm3",
            "neutrophils count 9800 cells/mm3",
            "n0 9800 per cubic mm",
            "n0 17,600/mm3",
        ])


# -----------------------------------------------------------------------------
#  Lymphocytes
# -----------------------------------------------------------------------------

class Lymphocytes(WbcBase):
    LYMPHOCYTES = r"""
        (?:
            (?: \b absolute \s* )?
            \b
            Lymph(?:o(?:cyte)?)?s?
            \b
            (?: \s* count \b )?
        )
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.LYMPHOCYTES,
                         variable="lymphocytes")

    def test(self) -> None:
        self.test_parser([
            "lymphocytes (should fail)",  # should fail; no values
            "absolute lymphocyte count 6",
            "lymphs = 6",
            "L0 6 x 10^9/L (should fail)",
            "lymphocyte count 6 x 10 ^ 9 / L",
            "lymphs 6.2",
            "lymph 6.2",
            "lympho 6.2",
            "lymphos 9800/mm3",
            "absolute lymphocytes 9800 cell/mm3",
            "lymphocytes count 9800 cells/mm3",
            "l0 9800 per cubic mm (should fail)",
            "l0 17,600/mm3 (should fail)",
        ])


# -----------------------------------------------------------------------------
#  Monocytes
# -----------------------------------------------------------------------------

class Monocytes(WbcBase):
    MONOCYTES = r"""
        (?:
            (?: \b absolute \s* )?
            \b
            Mono(?:cyte)?s?
            \b
            (?: \s* count \b )?
        )
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.MONOCYTES,
                         variable="monocytes")

    def test(self) -> None:
        self.test_parser([
            "monocytes (should fail)",  # should fail; no values
            "absolute monocyte count 6",
            "monos = 6",
            "M0 6 x 10^9/L (should fail)",
            "monocyte count 6 x 10 ^ 9 / L",
            "monos 6.2",
            "mono 6.2",
            "monos 9800/mm3",
            "absolute mono 9800 cell/mm3",
            "monocytes count 9800 cells/mm3",
            "m0 9800 per cubic mm (should fail)",
            "m0 17,600/mm3 (should fail)",
        ])


# -----------------------------------------------------------------------------
#  Basophils
# -----------------------------------------------------------------------------

class Basophils(WbcBase):
    BASOPHILS = r"""
        (?:
            (?: \b absolute \s* )?
            \b
            Baso(?:phil)?s?
            \b
            (?: \s* count \b )?
        )
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.BASOPHILS,
                         variable="basophils")

    def test(self) -> None:
        self.test_parser([
            "basophils (should fail)",  # should fail; no values
            "absolute basophil count 6",
            "basos = 6",
            "B0 6 x 10^9/L (should fail)",
            "basophil count 6 x 10 ^ 9 / L",
            "basos 6.2",
            "baso 6.2",
            "basos 9800/mm3",
            "absolute basophil 9800 cell/mm3",
            "basophils count 9800 cells/mm3",
            "b0 9800 per cubic mm (should fail)",
            "b0 17,600/mm3 (should fail)",
        ])


# -----------------------------------------------------------------------------
#  Eosinophils
# -----------------------------------------------------------------------------

class Eosinophils(WbcBase):
    EOSINOPHILS = r"""
        (?:
            (?: \b absolute \s* )?
            \b
            Eo(?:sin(?:o(?:phil)?)?)?s?
            \b
            (?: \s* count \b )?
        )
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit,
                         cell_type_regex_text=self.EOSINOPHILS,
                         variable="eosinophils")

    def test(self) -> None:
        self.test_parser([
            "eosinophils (should fail)",  # should fail; no values
            "absolute eosinophil count 6",
            "eos = 6",
            "E0 6 x 10^9/L (should fail)",
            "eosinophil count 6 x 10 ^ 9 / L",
            "eosins 6.2",
            "eosino 6.2",
            "eosinos 9800/mm3",
            "absolute eosinophil 9800 cell/mm3",
            "eosinophils count 9800 cells/mm3",
            "e0 9800 per cubic mm (should fail)",
            "e0 17,600/mm3 (should fail)",
        ])


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    # ESR
    esr = Esr(None, None)
    esr.test()

    # WBC and differential
    wbc = Wbc(None, None)
    wbc.test()
    n0 = Neutrophils(None, None)
    n0.test()
    l0 = Lymphocytes(None, None)
    l0.test()
    m0 = Monocytes(None, None)
    m0.test()
    b0 = Basophils(None, None)
    b0.test()
    e0 = Eosinophils(None, None)
    e0.test()
