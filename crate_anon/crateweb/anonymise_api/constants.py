"""
crate_anon/crateweb/anonymise_api/constants.py

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

Constants for the anonymisation API.

"""


class ApiKeys:
    """
    Values need to match the serializers in serializers.py. Don't change just
    here.

    Some keys are also those of a config; these are just the extras.
    """

    ALLOWLIST = "allowlist"
    ALTERNATIVES = "alternatives"
    ANONYMISED = "anonymised"
    CODES = "codes"
    DATES = "dates"
    DENYLIST = "denylist"
    FILES = "files"
    NON_NUMERIC_PHRASES = "non_numeric_phrases"
    NUMBERS = "numbers"
    PATIENT = "patient"
    PHRASES = "phrases"
    TEXT = "text"
    THIRD_PARTY = "third_party"
    WORDS = "words"


class ApiSettingsKeys:
    HASH_KEY = "HASH_KEY"
    ALLOWLIST_FILENAMES = "ALLOWLIST_FILENAMES"
    DENYLIST_FILENAMES = "DENYLIST_FILENAMES"
