#!/usr/bin/env python
# crate_anon/common/formatting.py


# =============================================================================
# Ancillary functions
# =============================================================================

def sizeof_fmt(num: float, suffix: str = 'B') -> str:
    # http://stackoverflow.com/questions/1094841
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)
