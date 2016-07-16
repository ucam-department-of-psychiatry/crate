#!/usr/bin/env python
# crate_anon/common/stringfunc.py

import re


# =============================================================================
# Replacement
# =============================================================================

def multiple_replace(text, rep):
    """Returns text in which the keys of rep (a dict) have been replaced by
    their values."""
    # http://stackoverflow.com/questions/6116978/python-replace-multiple-strings  # noqa
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    return pattern.sub(lambda m: rep[re.escape(m.group(0))], text)


def replace_in_list(stringlist, replacedict):
    newlist = []
    for i in range(len(stringlist)):
        newlist.append(multiple_replace(stringlist[i], replacedict))
    return newlist


# =============================================================================
# Simple string manipulation
# =============================================================================

def get_digit_string_from_vaguely_numeric_string(s):
    """
    Strips non-digit characters from a string.
    For example, converts "(01223) 123456" to "01223123456".
    """
    return "".join([d for d in s if d.isdigit()])


def reduce_to_alphanumeric(s):
    """
    Strips non-alphanumeric characters from a string.
    For example, converts "PE12 3AB" to "PE12 3AB".
    """
    return "".join([d for d in s if d.isalnum()])


def remove_whitespace(s):
    """
    Removes whitespace from a string.
    """
    return ''.join(s.split())


