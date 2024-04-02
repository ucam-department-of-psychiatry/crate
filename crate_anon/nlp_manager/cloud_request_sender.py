"""
crate_anon/nlp_manager/cloud_request_sender.py

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

**CloudRequestSender class.**

"""

# =============================================================================
# Imports
# =============================================================================

from enum import auto, Enum
import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Generator,
    TYPE_CHECKING,
)

from crate_anon.nlp_manager.constants import (
    DEFAULT_REPORT_EVERY_NLP,
)
from crate_anon.nlp_manager.input_field_config import (
    InputFieldConfig,
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
    FN_SRCFIELD,
)
from crate_anon.nlp_manager.models import FN_SRCHASH
from crate_anon.nlp_manager.cloud_request import (
    CloudRequestProcess,
    RecordNotPrintable,
    RecordsPerRequestExceeded,
    RequestTooLong,
)
from crate_anon.nlp_manager.cloud_run_info import CloudRunInfo

if TYPE_CHECKING:
    from http.cookiejar import CookieJar

log = logging.getLogger(__name__)


# =============================================================================
# CloudRequestSender
# =============================================================================


class CloudRequestSender:
    """
    Class to encapsulate a NLP request outbound to a cloud NLP server.
    """

    class State(Enum):
        """
        Request state.
        """

        BUILDING_REQUEST = auto()
        SENDING_REQUEST = auto()
        FINISHED = auto()

    def __init__(
        self,
        text_generator: Generator[Tuple[str, Dict[str, Any]], None, None],
        crinfo: CloudRunInfo,
        ifconfig: InputFieldConfig,
        report_every: int = DEFAULT_REPORT_EVERY_NLP,
        incremental: bool = False,
        queue: bool = True,
    ) -> None:
        """
        Initialise class

        Args:
            text_generator:
                 Generator that generates text strings from the source
                 database. See
                 :meth:`crate_anon.nlp_manager.input_field_config.InputFieldConfig.gen_text`.
            crinfo:
                A :class:`crate_anon.nlp_manager.cloud_run_info.CloudRunInfo`
                object.
            ifconfig:
                An
                :class:`crate_anon.nlp_manager.input_field_config.InputFieldConfig`
                object.
            report_every:
                Report to the log every *n* requests.
            incremental:
                Process in incremental mode (ignoring source records that have
                not changed since last time)?
            queue:
                Queue the requests for back-end processing (rather than waiting
                for an immediate reply)?
        """
        self._text_generator = text_generator
        self._crinfo = crinfo
        self._ifconfig = ifconfig
        self._report_every = report_every
        self._incremental = incremental
        self._queue = queue

        self._global_recnum = -1
        self._requests = []  # type: List[CloudRequestProcess]
        self._cookies = None  # type: Optional[CookieJar]
        self._request_count = 0  # number of requests sent
        self._text = None  # type: Optional[str]
        self._other_values = None  # type: Optional[Dict[str, Any]]
        self._request_is_empty = True
        self._need_new_record = True
        self._need_new_request = True
        self._num_recs_processed = 0
        self._state = self.State.BUILDING_REQUEST
        self._request = None  # type: Optional[CloudRequestProcess]

    def send_requests(
        self, global_recnum: int
    ) -> Tuple[List[CloudRequestProcess], bool, int]:
        """
        Sends off a series of cloud requests and returns them as a list.
        ``self._queue`` determines whether these are queued requests or not.
        Also returns whether the generator for the text is empty.

        Return tuple is: ``requests, some_records_processed, global_recnum``.
        """
        self._global_recnum = global_recnum
        self._requests = []
        self._cookies = None
        self._request_count = 1
        self._text = None
        self._other_values = None
        self._request_is_empty = True
        self._need_new_record = True
        self._need_new_request = True

        # Check processors are available
        available_procs = self._crinfo.get_remote_processors()
        if not available_procs:
            return [], False, self._global_recnum

        self._num_recs_processed = 0
        self._state = self.State.BUILDING_REQUEST

        # If we've reached the limit of records before commit, return to
        # outer function in order to process and commit (or write to file if
        # it's a queued request)
        while self._state != self.State.FINISHED:
            if self._state == self.State.BUILDING_REQUEST:
                self._build_request()

            if self._state == self.State.SENDING_REQUEST:
                self._send_request()

        return (
            self._requests,
            self._num_recs_processed > 0,
            self._global_recnum,
        )

    def _build_request(self) -> None:
        """
        Adds another record to the outbound request, until the request is
        fully built. Updates our state to reflect what needs to happen next.
        """
        if self._need_new_record:
            try:
                self._get_next_record()
            except StopIteration:
                self._update_state_for_no_more_records()
                return

            hasher = self._crinfo.nlpdef.hash
            srchash = hasher(self._text)

            if self._incremental and self._record_already_processed(srchash):
                return

            self._num_recs_processed += 1
            self._other_values[FN_SRCHASH] = srchash

        if self._need_new_request:
            self._request = self._get_new_cloud_request()
            self._request_is_empty = True
            self._need_new_request = False

        self._need_new_record = True

        # Add the text to the cloud request with the appropriate metadata
        try:
            self._request.add_text(self._text, self._other_values)

            # added OK, request now has some text
            self._request_is_empty = False

        except RecordNotPrintable:
            # Text contained no printable characters. Skip it.
            pass
        except (RecordsPerRequestExceeded, RequestTooLong) as e:
            if isinstance(e, RequestTooLong) and self._request_is_empty:
                # Get some new text next time
                log.warning("Skipping text that's too long to send")
            else:
                # Try same text again with a fresh request
                self._need_new_record = False
                self._state = self.State.SENDING_REQUEST

        if self._record_limit_reached():
            self._state = self.State.SENDING_REQUEST

    def _get_new_cloud_request(self) -> CloudRequestProcess:
        """
        Creates and returns a new
        :class:`crate_anon.nlp_manager.cloud_request.CloudRequestProcess`
        object.
        """
        return CloudRequestProcess(self._crinfo)

    def _update_state_for_no_more_records(self) -> None:
        """
        No more input records are available. This means either (a) we've sent
        all our requests and have finished, or (b) we're building our last
        request and we need to send it. Set the state accordingly.
        """
        if self._request_is_empty or self._need_new_request:
            # Nothing more to send
            self._state = self.State.FINISHED
            return

        # Send last request
        self._state = self.State.SENDING_REQUEST

    def _record_already_processed(self, srchash: str) -> bool:
        """
        Has this source record (identified by its PK and its hash) already been
        processed? (If so, then in incremental mode, we can skip it.)
        """
        pkval = self._other_values[FN_SRCPKVAL]
        pkstr = self._other_values[FN_SRCPKSTR]
        progrec = self._ifconfig.get_progress_record(pkval, pkstr)
        if progrec is not None:
            if progrec.srchash == srchash:
                log.debug("Record previously processed; skipping")
                return True

            log.debug("Record has changed")
        else:
            log.debug("Record is new")

        return False

    def _record_limit_reached(self) -> bool:
        """
        Have we processed as many records as we're allowed before we should
        COMMIT to the database?
        """
        limit_before_commit = self._crinfo.cloudcfg.limit_before_commit
        return self._num_recs_processed >= limit_before_commit

    def _get_next_record(self) -> None:
        """
        Reads the next text record and metadata into ``self._text`` and
        ``self._other_values``.

        Raises:
            :exc:`StopIteration` if there are no more records
        """
        self._text, self._other_values = next(self._text_generator)
        self._global_recnum += 1

        pkval = self._other_values[FN_SRCPKVAL]
        pkstr = self._other_values[FN_SRCPKSTR]
        # 'ifconfig.get_progress_record' expects pkstr to be None if it's
        # empty
        if not pkstr:
            pkstr = None
        if (
            self._report_every
            and self._global_recnum % self._report_every == 0
        ):
            # total number of records in table
            totalcount = self._ifconfig.get_count()
            log.info(
                "Processing {db}.{t}.{c}, PK: {pkf}={pkv} "
                "(record {g_recnum}/{totalcount})".format(
                    db=self._other_values[FN_SRCDB],
                    t=self._other_values[FN_SRCTABLE],
                    c=self._other_values[FN_SRCFIELD],
                    pkf=self._other_values[FN_SRCPKFIELD],
                    pkv=pkstr if pkstr else pkval,
                    g_recnum=self._global_recnum,
                    totalcount=totalcount,
                )
            )

    def _send_request(self) -> None:
        """
        Send a pending request to the remote NLP server.
        Update the state afterwards.
        """
        self._request.send_process_request(
            queue=self._queue,
            cookies=self._cookies,
            include_text_in_reply=self._crinfo.cloudcfg.has_gate_processors,
        )
        # If there's a connection error, we only get this far if we
        # didn't choose to stop at failure
        if self._request.request_failed:
            log.warning("Continuing after failed request.")
        else:
            if self._request.cookies:
                self._cookies = self._request.cookies
            log.info(
                f"Sent request to be processed: #{self._request_count} "
                f"of this block"
            )
            self._request_count += 1
            self._requests.append(self._request)

        if self._record_limit_reached():
            self._state = self.State.FINISHED
            return

        self._state = self.State.BUILDING_REQUEST
        self._need_new_request = True
