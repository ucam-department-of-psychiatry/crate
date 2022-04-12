#!/usr/bin/env python

"""
crate_anon/anonymise_webserver/tools/create_private_settings.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Create Django secrets file**

"""

import os
import secrets

TOOLS_DIR = os.path.dirname(os.path.realpath(__file__))
WEBSERVER_DIR = os.path.join(TOOLS_DIR, "..")
SETTINGS_DIR = os.path.join(WEBSERVER_DIR, "anonymiser")


def main() -> None:
    secret_key = secrets.token_urlsafe()

    contents = f"""#!/usr/bin/env python

SECRET_KEY = "{secret_key}"
"""

    with open(os.path.join(SETTINGS_DIR, "private_settings.py"), "w") as f:
        f.write(contents)


if __name__ == "__main__":
    main()
