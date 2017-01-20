#!/usr/bin/env python
# bug_reports/check_pycharm_generator_hint.py

# See https://youtrack.jetbrains.com/issue/PY-20709
# - reported as fixed in version 2016.3.1, build 163.10230
# - partially fixed in version 2016.3.2, build #PY-163.10154.54 (28 Dec 2016)
#   ... so presumably still to be released, and "Fix versions" doesn't mean
#   "version in which it was fixed".

from typing import Generator


def generate_int() -> Generator[int, None, None]:
    for x in [1, 2, 3, 4, 5]:
        yield x


def use_int(x: int) -> None:
    print("x is {}".format(x))


for value in generate_int():
    use_int(value)
