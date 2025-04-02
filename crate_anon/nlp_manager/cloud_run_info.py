"""
crate_anon/nlp_manager/cloud_run_info.py

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

Information class describing an NLPRP remote server; particularly, which
NLP processors it offers.

"""

import logging
from typing import List, Optional, Tuple

from crate_anon.nlp_manager.cloud_parser import Cloud
from crate_anon.nlp_manager.cloud_request import CloudRequestListProcessors
from crate_anon.nlp_manager.input_field_config import InputFieldConfig
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_webserver.server_processor import ServerProcessor

log = logging.getLogger(__name__)


class CloudRunInfo:
    """
    Represents session-wide information about an NLP cloud run, including
    details of the server and our chosen processors and config.
    """

    def __init__(
        self,
        nlpdef: NlpDefinition,
        debug_post_request: bool = False,
        debug_post_response: bool = False,
    ) -> None:
        """
        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        """
        self.nlpdef = nlpdef
        # Convenience member for our users:
        self.cloudcfg = nlpdef.get_cloud_config_or_raise()
        self._remote_processors = None  # type: Optional[List[ServerProcessor]]
        self._local_processors = None  # type: Optional[List[Cloud]]
        self._debug_post_request = debug_post_request
        self._debug_post_response = debug_post_response

        self._configure_local_processors()

    def get_remote_processors(self) -> List[ServerProcessor]:
        """
        Returns processors offered by the remote server.
        """
        if self._remote_processors is None:
            # Fetch from server
            req = CloudRequestListProcessors(
                nlpdef=self.nlpdef,
                debug_post_request=self._debug_post_request,
                debug_post_response=self._debug_post_response,
            )
            self._remote_processors = req.get_remote_processors()
        return self._remote_processors

    def get_local_processors(self) -> List[Cloud]:
        """
        Returns instances of local processors (which know about the local
        database structure, etc.).
        """
        if self._local_processors is None:
            self._local_processors = [
                p for p in self.nlpdef.processors if isinstance(p, Cloud)
            ]
        return self._local_processors

    def _configure_local_processors(self) -> None:
        for lp in self.get_local_processors():
            for rp in self.get_remote_processors():
                lp.set_procinfo_if_correct(rp)

    def get_requested_processors(self) -> List[Tuple[str, str]]:
        """
        Returns the processors we wish the server to use.

        Returns:
             a list of tuples: each ``procname, procversion``.
        """
        requested = []  # type: List[Tuple[str, str]]
        for lp in self.get_local_processors():
            if lp.available_remotely:
                name_version = lp.procname, lp.procversion
                requested.append(name_version)
        return requested

    def delete_dest_records(
        self,
        ifconfig: InputFieldConfig,
        pkval: int,
        pkstr: Optional[str],
        commit: bool = True,
    ):
        """
        Used for incremental updates. Deletes old destination records.
        """
        for processor in self.get_local_processors():
            processor.delete_dest_record(ifconfig, pkval, pkstr, commit=commit)
