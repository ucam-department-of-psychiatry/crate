#!/usr/bin/env python
# crate_anon/nlp_manager/text_handling.py

from typing import Dict
from cardinal_pythonlib.rnc_lang import chunks


# =============================================================================
# Input support methods
# =============================================================================

def tsv_pairs_to_dict(line: str, key_lower: bool = True) -> Dict[str, str]:
    """
    Converts a TSV line into sequential key/value pairs as a dictionary.
    """
    items = line.split("\t")
    d = {}
    for chunk in chunks(items, 2):
        key = chunk[0]
        value = unescape_tabs_newlines(chunk[1])
        if key_lower:
            key = key.lower()
        d[key] = value
    return d


def escape_tabs_newlines(s: str) -> str:
    """
    Escapes CR, LF, tab, and backslashes. (Here just for testing; mirrors the
    equivalent function in the Java code.)
    """
    if not s:
        return s
    s = s.replace("\\", r"\\")  # replace \ with \\
    s = s.replace("\n", r"\n")  # escape \n; note ord("\n") == 10
    s = s.replace("\r", r"\r")  # escape \r; note ord("\r") == 13
    s = s.replace("\t", r"\t")  # escape \t; note ord("\t") == 9
    return s


def unescape_tabs_newlines(s: str) -> str:
    """
    Reverses escape_tabs_newlines.
    """
    # See also http://stackoverflow.com/questions/4020539
    if not s:
        return s
    d = ""  # the destination string
    in_escape = False
    for i in range(len(s)):
        c = s[i]  # the character being processed
        if in_escape:
            if c == "r":
                d += "\r"
            elif c == "n":
                d += "\n"
            elif c == "t":
                d += "\t"
            else:
                d += c
            in_escape = False
        else:
            if c == "\\":
                in_escape = True
            else:
                d += c
    return d
