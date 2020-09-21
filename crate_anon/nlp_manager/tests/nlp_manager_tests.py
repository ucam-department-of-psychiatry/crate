#!/usr/bin/env python

"""
crate_anon/nlp_manager/nlp_manager.py

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

"""

from typing import Any, Dict, Generator, Tuple
from unittest import mock, TestCase

from crate_anon.nlp_manager.nlp_manager import send_cloud_requests


class SendCloudRequestsTestCase(TestCase):
    def get_text(self) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        yield "", {"": None}

    def test_exits_when_no_available_processors(self) -> None:
        generated_text = self.get_text()

        crinfo = mock.Mock(get_remote_processors=mock.Mock(return_value=False))
        global_recnum_in = 123
        ifconfig = mock.Mock()

        cloud_requests, records_left, global_recnum_out = send_cloud_requests(
           generated_text,
           crinfo,
           ifconfig,
           global_recnum_in
        )

        self.assertEqual(cloud_requests, [])
        self.assertFalse(records_left)
        self.assertEqual(global_recnum_out, global_recnum_in)
