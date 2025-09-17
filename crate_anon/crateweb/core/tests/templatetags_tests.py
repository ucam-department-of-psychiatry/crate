"""
crate_anon/crateweb/core/tests/templatetags_tests.py

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

**Template tags tests.**

"""

from unittest import mock, TestCase

from django.test import override_settings

from crate_anon.crateweb.core.templatetags.css_version import css_version


class CssVersionTests(TestCase):
    @override_settings(DEBUG=False)
    def test_css_version_is_crate_version_when_in_production(self) -> None:
        with mock.patch.multiple(
            "crate_anon.crateweb.core.templatetags.css_version",
            CRATE_VERSION="0.20.6",
        ):
            self.assertEqual(css_version(), "0_20_6")

    @override_settings(DEBUG=True)
    def test_css_version_is_uuid_when_in_debug(self) -> None:
        with mock.patch.multiple(
            "crate_anon.crateweb.core.templatetags.css_version.uuid",
            uuid4=mock.Mock(return_value="not-a-real-uuid"),
        ):
            self.assertEqual(css_version(), "not-a-real-uuid")
