..  docs/source/administrator/docker.rst

..  Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

Firewall setup
--------------


..  contents::
    :local:
    :depth: 3

List of domains that the CRATE installer will need to access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


If you are installing CRATE behind a firewall that restricts access to the internet, you will need to ensure the following domains are allowed.This list is correct as of May 2023 and is likely to change over time:

- \*.debian.org
- \*.docker.com
- \*.docker.io
- \*.github.com
- \*.githubusercontent.com
- \*.maven.org
- \*.pypi.org
- \*.pythonhosted.org
- \*.ubuntu.com
