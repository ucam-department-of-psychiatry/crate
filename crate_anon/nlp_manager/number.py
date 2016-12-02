#!/usr/bin/env python
# crate_anon/nlp_manager/number.py

from typing import Optional


def to_float(s: str) -> Optional[float]:
    if s:
        s = s.replace(',', '')  # comma as thousands separator
        s = s.replace('−', '-')  # Unicode minus
        s = s.replace('–', '-')  # en dash
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def to_pos_float(s: str) -> Optional[float]:
    try:
        return abs(to_float(s))
    except TypeError:  # to_float() returned None
        return None
