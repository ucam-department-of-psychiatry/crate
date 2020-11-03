#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/nlp_manager_tests.py

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

from crate_anon.nlp_manager.cloud_request import CloudRequestProcess
from crate_anon.nlp_manager.constants import HashClass
from crate_anon.nlp_manager.input_field_config import FN_SRCPKSTR, FN_SRCPKVAL
from crate_anon.nlp_manager.nlp_manager import send_cloud_requests
from crate_anon.nlprp.constants import NlprpKeys as NKeys


class SendCloudRequestsTestCase(TestCase):
    def get_text(self) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        for text, other_values in self.test_text:
            yield text, other_values

    def setUp(self) -> None:
        # Set some sensible defaults here and be explicit in individual tests
        remote_processors = {("name-version", None): mock.Mock()}
        self.cloud_config = mock.Mock(
            remote_processors=remote_processors,
            limit_before_commit=1000,
            max_records_per_request=1000,
            max_content_length=50000,
            has_gate_processors=True
        )
        # can't set name attribute in constructor here as it has special meaning
        self.nlpdef = mock.Mock(
            get_cloud_config_or_raise=mock.Mock(return_value=self.cloud_config)
        )
        self.nlpdef.name = ""  # so set it here

        self.hasher = HashClass("hashphrase")

        self.crinfo = mock.Mock(
            get_remote_processors=mock.Mock(return_value=remote_processors),
            cloudcfg=self.cloud_config,
            # if we don't set this explicitly, getsize will get into an
            # infinite loop when trying to recursively weigh the mock object
            nlpdef=mock.Mock(hash=self.hasher.hash)
        )
        self.ifconfig = mock.Mock()

    def test_exits_when_no_available_processors(self) -> None:
        self.test_text = [
            ("", {"": None}),
        ]

        crinfo = mock.Mock(get_remote_processors=mock.Mock(return_value=[]))
        global_recnum_in = 123
        ifconfig = mock.Mock()
        cloud_request_factory = mock.Mock()

        cloud_requests, records_left, global_recnum_out = send_cloud_requests(
            cloud_request_factory,
            self.get_text(),
            crinfo,
            ifconfig,
            global_recnum_in
        )

        self.assertEqual(cloud_requests, [])
        self.assertFalse(records_left)
        self.assertEqual(global_recnum_out, global_recnum_in)

    def test_single_text_sent_in_single_request(self) -> None:
        self.test_text = [
            ("A woman, a plan, a canal. Panamowa!", {
                FN_SRCPKVAL: 1,
                FN_SRCPKSTR: "pkstr",
            }),
        ]

        cloud_request = CloudRequestProcess(
            crinfo=self.crinfo,
            nlpdef=self.nlpdef,
        )

        def cloud_request_factory(crinfo) -> CloudRequestProcess:
            self.assertEqual(cloud_request_factory.call_count, 0)

            cloud_request_factory.call_count += 1

            return cloud_request

        cloud_request_factory.call_count = 0
        global_recnum_in = 123

        with mock.patch.object(
                cloud_request, "send_process_request") as mock_send:
            (cloud_requests,
             records_processed,
             global_recnum_out) = send_cloud_requests(
                cloud_request_factory,
                self.get_text(),
                self.crinfo,
                self.ifconfig,
                global_recnum_in
            )

            self.assertEqual(cloud_requests[0], cloud_request)
            self.assertTrue(records_processed)
            self.assertEqual(global_recnum_out, 124)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors from config
        )

        records = cloud_request._request_process[NKeys.ARGS][NKeys.CONTENT]

        self.assertEqual(records[0][NKeys.METADATA][FN_SRCPKVAL], 1)
        self.assertEqual(records[0][NKeys.METADATA][FN_SRCPKSTR], "pkstr")
        self.assertEqual(records[0][NKeys.TEXT],
                         "A woman, a plan, a canal. Panamowa!")

    def test_multiple_records_sent_in_single_request(self) -> None:
        self.test_text = [
            ("A woman, a plan, a canal. Panamowa!", {
                FN_SRCPKVAL: 1,
                FN_SRCPKSTR: "pkstr",
            }),
            ("A dog! A panic in a pagoda.", {
                FN_SRCPKVAL: 2,
                FN_SRCPKSTR: "pkstr",
            }),
            ("Won't lovers revolt now?", {
                FN_SRCPKVAL: 3,
                FN_SRCPKSTR: "pkstr",
            }),
        ]

        global_recnum_in = 123

        cloud_request = CloudRequestProcess(
            crinfo=self.crinfo,
            nlpdef=self.nlpdef,
        )

        # Unrealistic - we always return the same one
        def cloud_request_factory(crinfo) -> CloudRequestProcess:
            self.assertEqual(cloud_request_factory.call_count, 0)

            cloud_request_factory.call_count += 1

            return cloud_request

        cloud_request_factory.call_count = 0

        with mock.patch.object(
                cloud_request, "send_process_request") as mock_send:
            (cloud_requests,
             records_processed,
             global_recnum_out) = send_cloud_requests(
                cloud_request_factory,
                self.get_text(),
                self.crinfo,
                self.ifconfig,
                global_recnum_in
            )

            self.assertEqual(cloud_requests[0], cloud_request)
            self.assertTrue(records_processed)
            self.assertEqual(global_recnum_out, 126)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors
        )

        records = cloud_request._request_process[NKeys.ARGS][NKeys.CONTENT]

        self.assertEqual(records[0][NKeys.METADATA][FN_SRCPKVAL], 1)
        self.assertEqual(records[1][NKeys.METADATA][FN_SRCPKSTR], "pkstr")
        self.assertEqual(records[2][NKeys.TEXT], "Won't lovers revolt now?")

    def test_max_records_per_request(self) -> None:
        self.test_text = [
            ("A woman, a plan, a canal. Panamowa!", {
                FN_SRCPKVAL: 1,
                FN_SRCPKSTR: "pkstr",
            }),
            ("A dog! A panic in a pagoda.", {
                FN_SRCPKVAL: 2,
                FN_SRCPKSTR: "pkstr",
            }),
            ("Won't lovers revolt now?", {
                FN_SRCPKVAL: 3,
                FN_SRCPKSTR: "pkstr",
            }),
        ]

        global_recnum_in = 123

        cloud_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            )
        ]

        def cloud_request_factory(crinfo) -> CloudRequestProcess:
            request = cloud_requests[cloud_request_factory.call_count]

            cloud_request_factory.call_count += 1

            return request

        cloud_request_factory.call_count = 0

        self.cloud_config.max_records_per_request = 1

        mock_cookies = mock.Mock()

        def mock_send_0_side_effect(*args, **kwargs):
            cloud_requests[0].cookies = mock_cookies

        with mock.patch.object(cloud_requests[0],
                               "send_process_request") as mock_send_0:
            mock_send_0.side_effect = mock_send_0_side_effect
            with mock.patch.object(cloud_requests[1],
                                   "send_process_request") as mock_send_1:
                with mock.patch.object(cloud_requests[2],
                                       "send_process_request") as mock_send_2:
                    (requests_out,
                     records_processed,
                     global_recnum_out) = send_cloud_requests(
                         cloud_request_factory,
                         self.get_text(),
                         self.crinfo,
                         self.ifconfig,
                         global_recnum_in
                     )

        self.assertEqual(requests_out[0], cloud_requests[0])
        self.assertEqual(requests_out[1], cloud_requests[1])
        self.assertEqual(requests_out[2], cloud_requests[2])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors from config
        )
        mock_send_1.assert_called_once_with(
            queue=True,
            cookies=mock_cookies,  # Should remember cookies from first response
            include_text_in_reply=True  # has_gate_processors from config
        )
        mock_send_2.assert_called_once_with(
            queue=True,
            cookies=mock_cookies,  # Should remember cookies from first response
            include_text_in_reply=True  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_0[0][NKeys.TEXT],
                         "A woman, a plan, a canal. Panamowa!")

        content_1 = requests_out[1]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_1[0][NKeys.TEXT],
                         "A dog! A panic in a pagoda.")

        content_2 = requests_out[2]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_2[0][NKeys.TEXT], "Won't lovers revolt now?")

    def test_limit_before_commit_2(self) -> None:
        self.test_text = [
            ("A woman, a plan, a canal. Panamowa!", {
                FN_SRCPKVAL: 1,
                FN_SRCPKSTR: "pkstr",
            }),
            ("A dog! A panic in a pagoda.", {
                FN_SRCPKVAL: 2,
                FN_SRCPKSTR: "pkstr",
            }),
            ("Won't lovers revolt now?", {
                FN_SRCPKVAL: 3,
                FN_SRCPKSTR: "pkstr",
            }),
        ]

        global_recnum_in = 123

        cloud_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        def cloud_request_factory(crinfo) -> CloudRequestProcess:
            request = cloud_requests[cloud_request_factory.call_count]

            cloud_request_factory.call_count += 1

            return request

        cloud_request_factory.call_count = 0

        self.cloud_config.limit_before_commit = 2

        with mock.patch.object(cloud_requests[0],
                               "send_process_request") as mock_send:
            (requests_out,
             records_processed,
             global_recnum_out) = send_cloud_requests(
                 cloud_request_factory,
                 self.get_text(),
                 self.crinfo,
                 self.ifconfig,
                 global_recnum_in
             )

        self.assertEqual(requests_out[0], cloud_requests[0])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 125)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(len(content_0), 2)
        self.assertEqual(content_0[0][NKeys.TEXT],
                         "A woman, a plan, a canal. Panamowa!")

        self.assertEqual(content_0[1][NKeys.TEXT],
                         "A dog! A panic in a pagoda.")

    def test_max_content_length(self) -> None:
        self.test_text = [
            ("A woman, a plan, a canal. Panamowa!", {
                FN_SRCPKVAL: 1,
                FN_SRCPKSTR: "pkstr",
            }),
            ("A dog! A panic in a pagoda.", {
                FN_SRCPKVAL: 2,
                FN_SRCPKSTR: "pkstr",
            }),
            ("Won't lovers revolt now?", {
                FN_SRCPKVAL: 3,
                FN_SRCPKSTR: "pkstr",
            }),
        ]

        global_recnum_in = 123

        cloud_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        def cloud_request_factory(crinfo) -> CloudRequestProcess:
            request = cloud_requests[cloud_request_factory.call_count]

            cloud_request_factory.call_count += 1

            return request

        cloud_request_factory.call_count = 0

        # json lengths: 274, ?, 533
        self.cloud_config.max_content_length = 500

        with mock.patch.object(cloud_requests[0],
                               "send_process_request") as mock_send_0:
            with mock.patch.object(cloud_requests[1],
                                   "send_process_request") as mock_send_1:
                (requests_out,
                 records_processed,
                 global_recnum_out) = send_cloud_requests(
                     cloud_request_factory,
                     self.get_text(),
                     self.crinfo,
                     self.ifconfig,
                     global_recnum_in
                 )

        self.assertEqual(requests_out[0], cloud_requests[0])
        self.assertEqual(requests_out[1], cloud_requests[1])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors from config
        )
        mock_send_1.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_0[0][NKeys.TEXT],
                         "A woman, a plan, a canal. Panamowa!")

        self.assertEqual(content_0[1][NKeys.TEXT],
                         "A dog! A panic in a pagoda.")

        content_1 = requests_out[1]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_1[0][NKeys.TEXT], "Won't lovers revolt now?")

    def test_skips_previous_record_if_incremental(self) -> None:
        self.test_text = [
            ("A woman, a plan, a canal. Panamowa!", {
                FN_SRCPKVAL: 1,
                FN_SRCPKSTR: "pkstr",
            }),
            ("A dog! A panic in a pagoda.", {
                FN_SRCPKVAL: 2,
                FN_SRCPKSTR: "pkstr",
            }),
        ]

        global_recnum_in = 123

        cloud_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        def cloud_request_factory(crinfo) -> CloudRequestProcess:
            request = cloud_requests[cloud_request_factory.call_count]

            cloud_request_factory.call_count += 1

            return request

        cloud_request_factory.call_count = 0

        mock_progrec = mock.Mock(srchash=self.hasher.hash(self.test_text[0][0]))

        self.ifconfig.get_progress_record = mock.Mock(return_value=mock_progrec)

        with mock.patch.object(cloud_requests[0],
                               "send_process_request") as mock_send_0:
            (requests_out,
             records_processed,
             global_recnum_out) = send_cloud_requests(
                 cloud_request_factory,
                 self.get_text(),
                 self.crinfo,
                 self.ifconfig,
                 global_recnum_in,
                 incremental=True
             )

        self.assertEqual(requests_out[0], cloud_requests[0])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 125)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_0[0][NKeys.TEXT],
                         "A dog! A panic in a pagoda.")
