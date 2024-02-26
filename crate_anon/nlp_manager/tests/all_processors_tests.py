"""
crate_anon/nlp_manager/tests/all_processors_tests.py

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

**Test all simple regexes and regex-based NLP parsers.**

"""

import logging
import unittest

from crate_anon.common.constants import JSON_INDENT
from crate_anon.nlp_manager.all_processors import all_local_parser_classes
from crate_anon.nlprp.constants import SqlDialects

log = logging.getLogger(__name__)


# =============================================================================
# Unit tests
# =============================================================================


class NlpProcessorsTests(unittest.TestCase):
    @staticmethod
    def test_all_processors() -> None:
        """
        Self-tests all NLP processors.
        """
        verbose = True
        skip_validators: bool = False

        for cls in all_local_parser_classes():
            if skip_validators and cls.classname().endswith("Validator"):
                continue
            log.info("Testing parser class: {}".format(cls.classname()))
            instance = cls(None, None)
            log.info("... instantiated OK")
            schema_json = instance.nlprp_processor_info_json(
                indent=JSON_INDENT,
                sort_keys=True,
                sql_dialect=SqlDialects.MYSQL,
            )
            log.info(f"NLPRP processor information:\n{schema_json}")
            instance.test(verbose=verbose)
        log.info("Tests completed successfully.")
