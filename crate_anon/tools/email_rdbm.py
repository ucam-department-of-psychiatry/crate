#!/usr/bin/env python

"""
crate_anon/tools/email_rdbm.py

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

**E-mail the RDBM from the command line.**

Useful for "this job has finished" notifications, e.g. in anonymisation or NLP
scripts.

"""

from crate_anon.crateweb.manage import email_rdbm


def main() -> None:
    """
    Command-line entry point.
    """
    email_rdbm()


if __name__ == '__main__':
    main()
