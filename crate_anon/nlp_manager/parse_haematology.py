#!/usr/bin/env python
# crate_anon/nlp_manager/parse_haematology.py

import regex
import typing
from typing import List, Dict

from crate_anon.nlp_manager.regex_elements import (
    numerical_result_finder,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    RE_UNITS_BILLION_PER_L,
    RE_UNITS_CELLS_PER_CUBIC_MM,
    RE_UNITS_MM_H,
    REGEX_COMPILE_FLAGS,
    SIGNED_FLOAT,
    TENSE_INDICATOR,
    UNITS_BILLION_PER_L,
    UNITS_CELLS_PER_CUBIC_MM,
    UNITS_MM_H,
    WORD_BOUNDARY,
)

# =============================================================================
#  Erythrocyte sedimentation rate (ESR)
# =============================================================================

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

RE_ESR_V1 = regex.compile(r"""
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
    UNITS_MM_H=UNITS_MM_H,
), REGEX_COMPILE_FLAGS)
ESR_NAME = "ESR"
ESR_PREFERRED_UNIT_COLUMN = "value_mm_h"
ESR_UNIT_MAPPING = {
    RE_UNITS_MM_H: 1,       # preferred unit
}


def esr_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return numerical_result_finder(
        text=text,
        compiled_regex=RE_ESR_V1,
        variable=ESR_NAME,
        target_unit=ESR_PREFERRED_UNIT_COLUMN,
        unitregex_to_multiple_dict=ESR_UNIT_MAPPING,
        assume_preferred_unit=assume_preferred_unit
    )


def test_esr() -> None:
    esr_test_strings = [
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
    ]
    print("Testing ESR regex...")
    for s in esr_test_strings:
        print("    {} -> {}".format(repr(s), repr(esr_v1(s))))
    print()


# =============================================================================
#  White blood cell count and differential
# =============================================================================

WBC_PREFERRED_UNIT_COLUMN = "value_billion_per_l"
WBC_UNIT_MAPPING = {
    RE_UNITS_BILLION_PER_L: 1,     # preferred unit: 10^9 / L
    RE_UNITS_CELLS_PER_CUBIC_MM: 0.001,  # 1000 cells/mm^3 -> 1 x 10^9 / L
}


def make_wbc_regex(cell_type_regex_text):
    return regex.compile(r"""
        ({CELL_TYPE})                   # group for cell type name
        {OPTIONAL_RESULTS_IGNORABLES}
        ({TENSE_INDICATOR})?            # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ({RELATION})?                   # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ({SIGNED_FLOAT})                # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        ({UNITS_BILLION_PER_L} | {UNITS_CELLS_PER_CUBIC_MM})?  # optional units
    """.format(
        CELL_TYPE=cell_type_regex_text,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        UNITS_BILLION_PER_L=UNITS_BILLION_PER_L,
        UNITS_CELLS_PER_CUBIC_MM=UNITS_CELLS_PER_CUBIC_MM,
    ), REGEX_COMPILE_FLAGS)


def generic_white_cell(text: str,
                       compiled_regex: typing.re.Pattern,
                       variable: str,
                       assume_preferred_unit: bool = True) -> List[Dict]:
    return numerical_result_finder(
        text=text,
        compiled_regex=compiled_regex,
        variable=variable,
        target_unit=WBC_PREFERRED_UNIT_COLUMN,
        unitregex_to_multiple_dict=WBC_UNIT_MAPPING,
        assume_preferred_unit=assume_preferred_unit
    )


# -----------------------------------------------------------------------------
# WBC
# -----------------------------------------------------------------------------

RE_WBC = make_wbc_regex(r"""
    (?:
        \b
        (?:
            (?:                     # White blood cells, white cell count, etc.
                White\b
                [\s]*
                (?:\bblood\b)?
                [\s]*
                \bcell[s]?\b
                [\s]*
                (?:\bcount\b)?
                [\s]*
                (?:                     # optional suffix (WBC), (WBCC), (WCC)
                    [\(]?               # brackets are optional
                    (?: WBC | WBCC | WCC)
                    [\)]?
                )?
            )
            | (?:                   # just WBC(s), WBCC, WCC
                (?: WBC[s]? | WBCC | WCC )
            )
        )
        \b
    )
""")


def wbc_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return generic_white_cell(text, RE_WBC, "WBC",
                              assume_preferred_unit=assume_preferred_unit)


def test_wbc() -> None:
    wbc_test_strings = [
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
    ]
    print("Testing WBC regex...")
    for s in wbc_test_strings:
        print("    {} -> {}".format(repr(s), repr(wbc_v1(s))))
    print()


# -----------------------------------------------------------------------------
#  Neutrophils
# -----------------------------------------------------------------------------

RE_NEUTROPHILS = make_wbc_regex(r"""
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
""")


def neutrophil_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return generic_white_cell(text, RE_NEUTROPHILS, "neutrophils",
                              assume_preferred_unit=assume_preferred_unit)


def test_neutrophils() -> None:
    neutrophil_test_strings = [
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
    ]
    print("Testing neutrophil regex...")
    for s in neutrophil_test_strings:
        print("    {} -> {}".format(repr(s), repr(neutrophil_v1(s))))
    print()


# -----------------------------------------------------------------------------
#  Lymphocytes
# -----------------------------------------------------------------------------

RE_LYMPHOCYTES = make_wbc_regex(r"""
    (?:
        (?: \b absolute \s* )?
        \b
        (?:
            Lymph(?:o(?:cyte)?)?s?
            |
            L0
        )
        \b
        (?: \s* count \b )?
    )
""")


def lymphocyte_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return generic_white_cell(text, RE_LYMPHOCYTES, "lymphocytes",
                              assume_preferred_unit=assume_preferred_unit)


def test_lymphocytes() -> None:
    lymphocyte_test_strings = [
        "lymphocytes (should fail)",  # should fail; no values
        "absolute lymphocyte count 6",
        "lymphs = 6",
        "L0 6 x 10^9/L",
        "lymphocyte count 6 x 10 ^ 9 / L",
        "lymphs 6.2",
        "lymph 6.2",
        "lympho 6.2",
        "lymphos 9800/mm3",
        "absolute lymphocytes 9800 cell/mm3",
        "lymphocytes count 9800 cells/mm3",
        "l0 9800 per cubic mm",
        "l0 17,600/mm3",
    ]
    print("Testing lymphocyte regex...")
    for s in lymphocyte_test_strings:
        print("    {} -> {}".format(repr(s), repr(lymphocyte_v1(s))))
    print()


# -----------------------------------------------------------------------------
#  Monocytes
# -----------------------------------------------------------------------------

RE_MONOCYTES = make_wbc_regex(r"""
    (?:
        (?: \b absolute \s* )?
        \b
        (?:
            Mono(?:cyte)?s?
            |
            M0
        )
        \b
        (?: \s* count \b )?
    )
""")


def monocyte_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return generic_white_cell(text, RE_MONOCYTES, "monocytes",
                              assume_preferred_unit=assume_preferred_unit)


def test_monocytes() -> None:
    monocyte_test_strings = [
        "monocytes (should fail)",  # should fail; no values
        "absolute monocyte count 6",
        "monos = 6",
        "M0 6 x 10^9/L",
        "monocyte count 6 x 10 ^ 9 / L",
        "monos 6.2",
        "mono 6.2",
        "monos 9800/mm3",
        "absolute mono 9800 cell/mm3",
        "monocytes count 9800 cells/mm3",
        "m0 9800 per cubic mm",
        "m0 17,600/mm3",
    ]
    print("Testing monocyte regex...")
    for s in monocyte_test_strings:
        print("    {} -> {}".format(repr(s), repr(monocyte_v1(s))))
    print()


# -----------------------------------------------------------------------------
#  Basophils
# -----------------------------------------------------------------------------

RE_BASOPHILS = make_wbc_regex(r"""
    (?:
        (?: \b absolute \s* )?
        \b
        (?:
            Baso(?:phil)?s?
            |
            B0
        )
        \b
        (?: \s* count \b )?
    )
""")


def basophil_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return generic_white_cell(text, RE_BASOPHILS, "basophils",
                              assume_preferred_unit=assume_preferred_unit)


def test_basophils() -> None:
    basophil_test_strings = [
        "basophils (should fail)",  # should fail; no values
        "absolute basophil count 6",
        "basos = 6",
        "B0 6 x 10^9/L",
        "basophil count 6 x 10 ^ 9 / L",
        "basos 6.2",
        "baso 6.2",
        "basos 9800/mm3",
        "absolute basophil 9800 cell/mm3",
        "basophils count 9800 cells/mm3",
        "b0 9800 per cubic mm",
        "b0 17,600/mm3",
    ]
    print("Testing basophil regex...")
    for s in basophil_test_strings:
        print("    {} -> {}".format(repr(s), repr(basophil_v1(s))))
    print()


# -----------------------------------------------------------------------------
#  Eososinophils
# -----------------------------------------------------------------------------

RE_EOSINOPHILS = make_wbc_regex(r"""
    (?:
        (?: \b absolute \s* )?
        \b
        (?:
            Eo(?:sin(?:o(?:phil)?)?)?s?
            |
            E0
        )
        \b
        (?: \s* count \b )?
    )
""")


def eosinophil_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    return generic_white_cell(text, RE_EOSINOPHILS, "eosinophils",
                              assume_preferred_unit=assume_preferred_unit)


def test_eosinophils() -> None:
    eosinophil_test_strings = [
        "eosinophils (should fail)",  # should fail; no values
        "absolute eosinophil count 6",
        "eos = 6",
        "E0 6 x 10^9/L",
        "eosinophil count 6 x 10 ^ 9 / L",
        "eosins 6.2",
        "eosino 6.2",
        "eosinos 9800/mm3",
        "absolute eosinophil 9800 cell/mm3",
        "eosinophils count 9800 cells/mm3",
        "e0 9800 per cubic mm",
        "e0 17,600/mm3",
    ]
    print("Testing eosinophil regex...")
    for s in eosinophil_test_strings:
        print("    {} -> {}".format(repr(s), repr(eosinophil_v1(s))))
    print()


# -----------------------------------------------------------------------------
# All WBC subtypes (since they share structure, we can join them)
# -----------------------------------------------------------------------------

def all_leukocytes_v1(text: str,
                      assume_preferred_unit: bool = True) -> List[Dict]:
    return (
        wbc_v1(text, assume_preferred_unit=assume_preferred_unit) +
        neutrophil_v1(text, assume_preferred_unit=assume_preferred_unit) +
        lymphocyte_v1(text, assume_preferred_unit=assume_preferred_unit) +
        monocyte_v1(text, assume_preferred_unit=assume_preferred_unit) +
        basophil_v1(text, assume_preferred_unit=assume_preferred_unit) +
        eosinophil_v1(text, assume_preferred_unit=assume_preferred_unit)
    )


def test_all_leukocytes() -> None:
    leukocyte_test_strings = [
        "diff: WBC 6.2; N0 1.2, L0 1.3, baso <0.1, eo 0.08, mono 2/mm3",
    ]
    print("Testing leukocytes en masse...")
    for s in leukocyte_test_strings:
        print("    {} -> {}".format(repr(s), repr(all_leukocytes_v1(s))))
    print()


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    # ESR
    test_esr()

    # WBC and differential
    test_wbc()
    test_neutrophils()
    test_lymphocytes()
    test_monocytes()
    test_basophils()
    test_eosinophils()
    test_all_leukocytes()
