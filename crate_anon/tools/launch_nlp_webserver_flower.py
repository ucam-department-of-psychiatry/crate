#!/usr/bin/env python

"""
crate_anon/tools/launch_nlp_webserver_flower.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Launch Flower, the Celery monitoring tool, for the CRATE NLP web server.**

"""

import subprocess

from crate_anon.nlp_webserver.constants import NLP_WEBSERVER_CELERY_APP_NAME


def main() -> None:
    """
    Command-line entry point.
    """
    cmdargs = ["celery", "--app", NLP_WEBSERVER_CELERY_APP_NAME, "flower"]
    print(f"Launching Flower: {cmdargs}")
    subprocess.call(cmdargs)


if __name__ == "__main__":
    main()
