#!/usr/bin/env python
# crate_anon/common/lang.py


def merge_two_dicts(x, y):
    '''Given two dicts, merge them into a new dict as a shallow copy.'''
    # http://stackoverflow.com/questions/38987
    z = x.copy()
    z.update(y)  # y takes precedence over x
    return z
