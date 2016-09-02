#!/usr/bin/env python
# crate_anon/nlp_manager/parse_biochemistry.py

import regex
from typing import List, Dict

from crate_anon.nlp_manager.regex_elements import (
    numerical_result_finder,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    RE_UNITS_MG_DL,
    RE_UNITS_MG_L,
    REGEX_COMPILE_FLAGS,
    SIGNED_FLOAT,
    TENSE_INDICATOR,
    UNITS_MG_DL,
    UNITS_MG_L,
    WORD_BOUNDARY,
)


# =============================================================================
#  C-reactive protein (CRP)
# =============================================================================

CRP = r"""
    (?:
        {WORD_BOUNDARY}
        (?:
            (?: C [-\s]+ reactive [\s]+ protein )
            | (?: CRP )
        )
        {WORD_BOUNDARY}
    )
""".format(WORD_BOUNDARY=WORD_BOUNDARY)

RE_CRP_V1 = regex.compile(r"""
    ( {CRP} )                           # group for "CRP" or equivalent
    {OPTIONAL_RESULTS_IGNORABLES}
    ( {TENSE_INDICATOR} )?              # optional group for tense indicator
    {OPTIONAL_RESULTS_IGNORABLES}
    ( {RELATION} )?                     # optional group for relation
    {OPTIONAL_RESULTS_IGNORABLES}
    ( {SIGNED_FLOAT} )                # group for value
    {OPTIONAL_RESULTS_IGNORABLES}
    ( {UNITS_MG_DL} | {UNITS_MG_L} )?   # optional group for units
""".format(
    CRP=CRP,
    OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
    TENSE_INDICATOR=TENSE_INDICATOR,
    RELATION=RELATION,
    SIGNED_FLOAT=SIGNED_FLOAT,
    UNITS_MG_DL=UNITS_MG_DL,
    UNITS_MG_L=UNITS_MG_L,
), REGEX_COMPILE_FLAGS)
CRP_NAME = "CRP"
CRP_PREFERRED_UNIT_COLUMN = "value_mg_l"
CRP_UNIT_MAPPING = {
    RE_UNITS_MG_L: 1,       # preferred unit
    RE_UNITS_MG_DL: 10,     # 1 mg/dL -> 10 mg/L
}


def crp_v1(text: str, assume_preferred_unit: bool = True) -> List[Dict]:
    """
    CRP units:
    - mg/L is commonest in the UK (or at least standard at Addenbrooke's,
      Hinchingbrooke, and Dundee)
    - values of <=6 mg/L or <10 mg/L are normal, and e.g. 70-250 mg/L in
      pneumonia.
    - Refs include:
            http://www.ncbi.nlm.nih.gov/pubmed/7705110
            http://emedicine.medscape.com/article/2086909-overview
    - 1 mg/dL = 10 mg/L
        ... so normal in mg/dL is <=1 roughly.
    """
    return numerical_result_finder(
        text=text,
        compiled_regex=RE_CRP_V1,
        variable=CRP_NAME,
        target_unit=CRP_PREFERRED_UNIT_COLUMN,
        unitregex_to_multiple_dict=CRP_UNIT_MAPPING,
        assume_preferred_unit=assume_preferred_unit
    )


def test_crp() -> None:
    crp_test_strings = [
        "CRP",  # should fail; no values
        "CRP 6",
        "CRP = 6",
        "CRP 6 mg/dl",
        "CRP <1",
        "CRP <1 mg/dl",
        "CRP >250",
        "CRP >250 mg/dl",
        "CRP was 62",
        "CRP was 62 mg/l",
        "CRP was <1",
        "CRP is 19",
        "CRP is >250",
        "CRP is 19 mg dl-1",
        "CRP is 19 mg dl -1",
        "CRP 1.9 mg/L",
        "CRP 1.9 mg L-1",
        "CRP        |       1.9 (H)      | mg/L",
    ]
    print("Testing CRP regex...")
    for s in crp_test_strings:
        print("    {} -> {}".format(repr(s), crp_v1(s)))
    print()


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    test_crp()
