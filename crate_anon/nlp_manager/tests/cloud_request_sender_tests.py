#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/cloud_request_sender_tests.py

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

crate_anon/nlp_manager/tests/nlp_manager_tests.py
"""

import logging
from typing import Any, Dict, Generator, Optional, Tuple
from unittest import mock, TestCase

from crate_anon.nlp_manager.cloud_request import CloudRequestProcess
from crate_anon.nlp_manager.cloud_request_sender import CloudRequestSender
from crate_anon.nlp_manager.constants import HashClass
from crate_anon.nlp_manager.input_field_config import (
    FN_SRCDB,
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKSTR,
    FN_SRCPKVAL,
    FN_SRCTABLE,
)
from crate_anon.nlp_manager.models import FN_SRCHASH, NlpRecord
from crate_anon.nlprp.constants import NlprpKeys as NKeys

PANAMOWA = "A woman, a plan, a canal. Panamowa!"
PAGODA = "A dog! A panic in a pagoda."
PATACA = "A cat! A panic in a pataca."
REVOLT = "Won't lovers revolt now?"


class TestCloudRequestSender(CloudRequestSender):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_count = 0
        self.test_requests = []

    def _get_new_cloud_request(self) -> CloudRequestProcess:
        request = self.test_requests[self.call_count]
        self.call_count += 1

        return request


class CloudRequestSenderTests(TestCase):
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
            has_gate_processors=True,
        )
        # can't set name attribute in constructor here as it has special
        # meaning
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
            nlpdef=mock.Mock(hash=self.hasher.hash),
        )
        self.ifconfig = mock.Mock()
        self.sender = TestCloudRequestSender(
            self.get_text(),
            self.crinfo,
            self.ifconfig,
        )

    def test_exits_when_no_available_processors(self) -> None:
        self.test_text = [
            ("", {"": None}),
        ]

        crinfo = mock.Mock(get_remote_processors=mock.Mock(return_value=[]))
        global_recnum_in = 123
        ifconfig = mock.Mock()

        # No need to use TestCloudRequestSender because we should never get as
        # far as creating requests.
        sender = CloudRequestSender(
            self.get_text(),
            crinfo,
            ifconfig,
        )
        (
            cloud_requests,
            records_left,
            global_recnum_out,
        ) = sender.send_requests(global_recnum_in)

        self.assertEqual(cloud_requests, [])
        self.assertFalse(records_left)
        self.assertEqual(global_recnum_out, global_recnum_in)

    def test_single_text_sent_in_single_request(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
            CloudRequestProcess(crinfo=self.crinfo, nlpdef=self.nlpdef)
        ]

        with mock.patch.object(
            self.sender.test_requests[0], "send_process_request"
        ) as mock_send:
            (
                cloud_requests,
                records_processed,
                global_recnum_out,
            ) = self.sender.send_requests(global_recnum=global_recnum_in)

            self.assertEqual(cloud_requests[0], self.sender.test_requests[0])
            self.assertTrue(records_processed)
            self.assertEqual(global_recnum_out, 124)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )

        records = cloud_requests[0]._request_process[NKeys.ARGS][NKeys.CONTENT]

        self.assertEqual(records[0][NKeys.METADATA][FN_SRCPKVAL], 1)
        self.assertEqual(records[0][NKeys.METADATA][FN_SRCPKSTR], "pkstr")
        self.assertEqual(
            records[0][NKeys.METADATA][FN_SRCHASH], self.hasher.hash(PANAMOWA)
        )
        self.assertEqual(records[0][NKeys.TEXT], PANAMOWA)

    def test_multiple_records_sent_in_single_request(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                PAGODA,
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
            CloudRequestProcess(crinfo=self.crinfo, nlpdef=self.nlpdef)
        ]

        with mock.patch.object(
            self.sender.test_requests[0], "send_process_request"
        ) as mock_send:
            (
                cloud_requests,
                records_processed,
                global_recnum_out,
            ) = self.sender.send_requests(global_recnum_in)

            self.assertEqual(cloud_requests[0], self.sender.test_requests[0])
            self.assertTrue(records_processed)
            self.assertEqual(global_recnum_out, 126)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors
        )

        records = cloud_requests[0]._request_process[NKeys.ARGS][NKeys.CONTENT]

        self.assertEqual(records[0][NKeys.METADATA][FN_SRCPKVAL], 1)
        self.assertEqual(records[1][NKeys.METADATA][FN_SRCPKSTR], "pkstr")
        self.assertEqual(records[2][NKeys.TEXT], REVOLT)

    def test_max_records_per_request(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                PAGODA,
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
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
            ),
        ]

        self.cloud_config.max_records_per_request = 1

        mock_cookies = mock.Mock()

        # noinspection PyUnusedLocal
        def mock_send_0_side_effect(*args, **kwargs):
            self.sender.test_requests[0].cookies = mock_cookies

        with self.assertLogs(level=logging.INFO) as logging_cm:
            with mock.patch.object(
                self.sender.test_requests[0], "send_process_request"
            ) as mock_send_0:
                mock_send_0.side_effect = mock_send_0_side_effect
                with mock.patch.object(
                    self.sender.test_requests[1], "send_process_request"
                ) as mock_send_1:
                    with mock.patch.object(
                        self.sender.test_requests[2], "send_process_request"
                    ) as mock_send_2:
                        (
                            requests_out,
                            records_processed,
                            global_recnum_out,
                        ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out[0], self.sender.test_requests[0])
        self.assertEqual(requests_out[1], self.sender.test_requests[1])
        self.assertEqual(requests_out[2], self.sender.test_requests[2])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )
        mock_send_1.assert_called_once_with(
            queue=True,
            cookies=mock_cookies,  # Should remember cookies from first response  # noqa: E501
            include_text_in_reply=True,  # has_gate_processors from config
        )
        mock_send_2.assert_called_once_with(
            queue=True,
            cookies=mock_cookies,  # Should remember cookies from first response  # noqa: E501
            include_text_in_reply=True,  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_0[0][NKeys.TEXT], PANAMOWA)

        content_1 = requests_out[1]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_1[0][NKeys.TEXT], PAGODA)

        content_2 = requests_out[2]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_2[0][NKeys.TEXT], REVOLT)

        logger_name = "crate_anon.nlp_manager.cloud_request_sender"
        expected_message = "Sent request to be processed: #1 of this block"
        self.assertIn(
            f"INFO:{logger_name}:{expected_message}", logging_cm.output
        )
        expected_message = "Sent request to be processed: #2 of this block"
        self.assertIn(
            f"INFO:{logger_name}:{expected_message}", logging_cm.output
        )
        expected_message = "Sent request to be processed: #3 of this block"
        self.assertIn(
            f"INFO:{logger_name}:{expected_message}", logging_cm.output
        )

    def test_limit_before_commit_2(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                PAGODA,
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        self.cloud_config.limit_before_commit = 2

        with mock.patch.object(
            self.sender.test_requests[0], "send_process_request"
        ) as mock_send:
            (
                requests_out,
                records_processed,
                global_recnum_out,
            ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out[0], self.sender.test_requests[0])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 125)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(len(content_0), 2)
        self.assertEqual(content_0[0][NKeys.TEXT], PANAMOWA)

        self.assertEqual(content_0[1][NKeys.TEXT], PAGODA)

    def test_max_content_length(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                PAGODA,
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        # json lengths: 274, ?, 533
        self.cloud_config.max_content_length = 500

        with mock.patch.object(
            self.sender.test_requests[0], "send_process_request"
        ) as mock_send_0:
            with mock.patch.object(
                self.sender.test_requests[1], "send_process_request"
            ) as mock_send_1:
                (
                    requests_out,
                    records_processed,
                    global_recnum_out,
                ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out[0], self.sender.test_requests[0])
        self.assertEqual(requests_out[1], self.sender.test_requests[1])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )
        mock_send_1.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_0[0][NKeys.TEXT], PANAMOWA)

        self.assertEqual(content_0[1][NKeys.TEXT], PAGODA)

        content_1 = requests_out[1]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_1[0][NKeys.TEXT], REVOLT)

    def test_record_bigger_than_max_content_length_skipped(self) -> None:
        short_text = "Some text with serialized length greater than 500. "
        long_text = short_text * 6
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                long_text,
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        self.cloud_config.max_content_length = 500

        with self.assertLogs(level=logging.WARNING) as logging_cm:
            with mock.patch.object(
                self.sender.test_requests[0], "send_process_request"
            ) as mock_send_0:
                with mock.patch.object(
                    self.sender.test_requests[1], "send_process_request"
                ) as mock_send_1:
                    (
                        requests_out,
                        records_processed,
                        global_recnum_out,
                    ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out[0], self.sender.test_requests[0])
        self.assertEqual(requests_out[1], self.sender.test_requests[1])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )
        mock_send_1.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(len(content_0), 1)
        self.assertEqual(content_0[0][NKeys.TEXT], PANAMOWA)

        content_1 = requests_out[1]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_1[0][NKeys.TEXT], REVOLT)

        logger_name = "crate_anon.nlp_manager.cloud_request_sender"
        self.assertIn(
            (
                f"WARNING:{logger_name}:"
                f"Skipping text that's too long to send"
            ),
            logging_cm.output,
        )

    def test_skips_previous_record_if_incremental(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                PAGODA,
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender._incremental = True
        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        # noinspection PyUnusedLocal
        def get_progress_record(pkval: int, pkstr: str) -> Optional[NlpRecord]:

            # same as before
            if pkval == 1:
                return mock.Mock(
                    srchash=self.hasher.hash(self.test_text[0][0])
                )

            # changed
            if pkval == 2:
                return mock.Mock(srchash=self.hasher.hash(PATACA))

            # new
            return None

        self.ifconfig.get_progress_record = get_progress_record

        with self.assertLogs(level=logging.DEBUG) as logging_cm:
            with mock.patch.object(
                self.sender.test_requests[0], "send_process_request"
            ) as mock_send_0:
                (
                    requests_out,
                    records_processed,
                    global_recnum_out,
                ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out[0], self.sender.test_requests[0])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send_0.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(content_0[0][NKeys.TEXT], PAGODA)

        logger_name = "crate_anon.nlp_manager.cloud_request_sender"
        self.assertIn(
            (f"DEBUG:{logger_name}:Record previously processed; " "skipping"),
            logging_cm.output,
        )
        self.assertIn(
            f"DEBUG:{logger_name}:Record has changed", logging_cm.output
        )
        self.assertIn(f"DEBUG:{logger_name}:Record is new", logging_cm.output)

    def test_log_message_frequency(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCDB: "db",
                    FN_SRCFIELD: "field",
                    FN_SRCPKFIELD: "pkfield",
                    FN_SRCPKSTR: "pkstr",
                    FN_SRCPKVAL: 1,
                    FN_SRCTABLE: "table",
                },
            ),
            (
                PAGODA,
                {
                    FN_SRCPKSTR: "pkstr",
                    FN_SRCPKVAL: 2,
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCDB: "db",
                    FN_SRCFIELD: "field",
                    FN_SRCPKFIELD: "pkfield",
                    FN_SRCPKSTR: "",
                    FN_SRCPKVAL: 3,
                    FN_SRCTABLE: "table",
                },
            ),
        ]

        global_recnum_in = 1

        self.sender._report_every = 2
        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        self.ifconfig.get_count = mock.Mock(return_value=100)
        with self.assertLogs(level=logging.INFO) as logging_cm:
            with mock.patch.object(
                self.sender.test_requests[0], "send_process_request"
            ):
                self.sender.send_requests(global_recnum_in)

        logger_name = "crate_anon.nlp_manager.cloud_request_sender"
        expected_message = (
            "Processing db.table.field, PK: pkfield=pkstr " "(record 2/100)"
        )
        self.assertIn(
            f"INFO:{logger_name}:{expected_message}", logging_cm.output
        )

        expected_message = (
            "Processing db.table.field, PK: pkfield=3 " "(record 4/100)"
        )
        self.assertIn(
            f"INFO:{logger_name}:{expected_message}", logging_cm.output
        )

    def test_failed_request_logged(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKSTR: "pkstr",
                    FN_SRCPKVAL: 1,
                },
            ),
        ]

        global_recnum_in = 1

        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        # noinspection PyUnusedLocal
        def mock_send_0_side_effect(*args, **kwargs):
            self.sender.test_requests[0].request_failed = True

        with self.assertLogs(level=logging.WARNING) as logging_cm:
            with mock.patch.object(
                self.sender.test_requests[0], "send_process_request"
            ) as mock_send_0:
                mock_send_0.side_effect = mock_send_0_side_effect

                (
                    requests_out,
                    records_processed,
                    global_recnum_out,
                ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out, [])
        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 2)

        logger_name = "crate_anon.nlp_manager.cloud_request_sender"
        self.assertIn(
            f"WARNING:{logger_name}:Continuing after failed request.",
            logging_cm.output,
        )

    def test_record_with_no_text_skipped(self) -> None:
        self.test_text = [
            (
                PANAMOWA,
                {
                    FN_SRCPKVAL: 1,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                "     \t\t\n\n         ",
                {
                    FN_SRCPKVAL: 2,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
            (
                REVOLT,
                {
                    FN_SRCPKVAL: 3,
                    FN_SRCPKSTR: "pkstr",
                },
            ),
        ]

        global_recnum_in = 123

        self.sender.test_requests = [
            CloudRequestProcess(
                crinfo=self.crinfo,
                nlpdef=self.nlpdef,
            ),
        ]

        with mock.patch.object(
            self.sender.test_requests[0], "send_process_request"
        ) as mock_send:
            (
                requests_out,
                records_processed,
                global_recnum_out,
            ) = self.sender.send_requests(global_recnum_in)

        self.assertEqual(requests_out[0], self.sender.test_requests[0])

        self.assertTrue(records_processed)
        self.assertEqual(global_recnum_out, 126)

        mock_send.assert_called_once_with(
            queue=True,
            cookies=None,  # First call: no cookies
            include_text_in_reply=True,  # has_gate_processors from config
        )

        content_0 = requests_out[0]._request_process[NKeys.ARGS][NKeys.CONTENT]
        self.assertEqual(len(content_0), 2)
        self.assertEqual(content_0[0][NKeys.TEXT], PANAMOWA)

        self.assertEqual(content_0[1][NKeys.TEXT], REVOLT)
