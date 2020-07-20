#!/usr/bin/env python

"""
crate_anon/nlp_manager/cloud_config.py

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

Config object used for cloud NLP requests.

"""

import logging
import os
from typing import TYPE_CHECKING, Dict, Tuple

from crate_anon.common.extendedconfigparser import ConfigSection
from crate_anon.nlp_manager.constants import (
    CloudNlpConfigKeys,
    NlpDefValues,
    DEFAULT_CLOUD_LIMIT_BEFORE_COMMIT,
    DEFAULT_CLOUD_MAX_CONTENT_LENGTH,
    DEFAULT_CLOUD_MAX_RECORDS_PER_REQUEST,
    DEFAULT_CLOUD_MAX_TRIES,
    DEFAULT_CLOUD_RATE_LIMIT_HZ,
    DEFAULT_CLOUD_WAIT_ON_CONN_ERR_S,
    full_sectionname,
    NlpConfigPrefixes,
)

if TYPE_CHECKING:
    from crate_anon.nlp_manager.nlp_definition import NlpDefinition
    from crate_anon.nlp_manager.cloud_parser import Cloud

log = logging.getLogger(__name__)


# =============================================================================
# CloudConfig
# =============================================================================

class CloudConfig(object):
    """
    Common config object for cloud NLP.
    """

    def __init__(self, nlpdef: "NlpDefinition", name: str,
                 req_data_dir: str) -> None:
        """
        Reads the config from the NLP definition's config file.

        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            name:
                name for the cloud NLP configuration (to which a standard
                prefix will be added to get the config section name)
            req_data_dir:
                directory in which to store temporary request files
        """
        from crate_anon.nlp_manager.cloud_parser import Cloud  # delayed import  # noqa

        self._nlpdef = nlpdef
        self.req_data_dir = req_data_dir

        cfg = ConfigSection(
            section=full_sectionname(NlpConfigPrefixes.CLOUD, name),
            parser=nlpdef.parser
        )

        self.url = cfg.opt_str(CloudNlpConfigKeys.CLOUD_URL, required=True)
        self.verify_ssl = cfg.opt_bool(CloudNlpConfigKeys.VERIFY_SSL, True)
        self.compress = cfg.opt_bool(CloudNlpConfigKeys.COMPRESS, True)
        self.username = cfg.opt_str(CloudNlpConfigKeys.USERNAME, default="")
        self.password = cfg.opt_str(CloudNlpConfigKeys.PASSWORD, default="")
        self.max_content_length = cfg.opt_int(
            CloudNlpConfigKeys.MAX_CONTENT_LENGTH,
            DEFAULT_CLOUD_MAX_CONTENT_LENGTH)
        self.limit_before_commit = cfg.opt_int(
            CloudNlpConfigKeys.LIMIT_BEFORE_COMMIT,
            DEFAULT_CLOUD_LIMIT_BEFORE_COMMIT)
        self.max_records_per_request = cfg.opt_int(
            CloudNlpConfigKeys.MAX_RECORDS_PER_REQUEST,
            DEFAULT_CLOUD_MAX_RECORDS_PER_REQUEST)
        self.stop_at_failure = cfg.opt_bool(
            CloudNlpConfigKeys.STOP_AT_FAILURE, True)
        self.wait_on_conn_err = cfg.opt_int(
            CloudNlpConfigKeys.WAIT_ON_CONN_ERR,
            DEFAULT_CLOUD_WAIT_ON_CONN_ERR_S)
        self.max_tries = cfg.opt_int(
            CloudNlpConfigKeys.MAX_TRIES, DEFAULT_CLOUD_MAX_TRIES)
        self.rate_limit_hz = cfg.opt_int(
            CloudNlpConfigKeys.RATE_LIMIT_HZ, DEFAULT_CLOUD_RATE_LIMIT_HZ)
        self.test_length_function_speed = cfg.opt_bool(
            CloudNlpConfigKeys.TEST_LENGTH_FUNCTION_SPEED, True)
        self.remote_processors = {}  # type: Dict[Tuple[str, str], 'Cloud']
        for processor in self._nlpdef.get_processors():
            if not isinstance(processor, Cloud):
                # ... only add 'Cloud' processors
                log.warning(
                    f"Skipping NLP processor of non-cloud (e.g. local) "
                    f"type: {processor.friendly_name}")
                continue
            self.remote_processors[(
                processor.procname, processor.procversion)] = processor
            # NOTE: KEY IS A TUPLE!
        # We need the following in order to decide whether to ask to include
        # text in reply - if a processor is GATE we need to, as it does not
        # send back the content of the nlp snippet
        self.has_gate_processors = any(
            (x.format == NlpDefValues.FORMAT_GATE)
            for x in self.remote_processors.values())

    @property
    def data_filename(self) -> str:
        """
        Returns the filename to be used for storing data.
        """
        nlpname = self._nlpdef.name
        return os.path.abspath(os.path.join(
            self.req_data_dir, f"request_data_{nlpname}.csv"))
