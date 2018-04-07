#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_definition.py

"""
===============================================================================
    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

# =============================================================================
# Imports
# =============================================================================

import codecs
import datetime
import logging
import os
import sys
from typing import Dict, Iterable, List, Optional

from cardinal_pythonlib.datetimefunc import get_now_utc_notz_datetime
from cardinal_pythonlib.lists import chunks
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import MetaData

from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.common.extendedconfigparser import ExtendedConfigParser
from crate_anon.common.sql import TransactionSizeLimiter
from crate_anon.nlp_manager.constants import (
    DEFAULT_MAX_BYTES_BEFORE_COMMIT,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT,
    DEFAULT_TEMPORARY_TABLENAME,
    HashClass,
    MAX_SQL_FIELD_LEN,
    NLP_CONFIG_ENV_VAR,
)

# if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
#     from crate_anon.nlp_manager import input_field_config
#     from crate_anon.nlp_manager import base_nlp_parser  # SEE NEXT LINES

# - see PEP0484 / forward references
# - some circular imports work under Python 3.5 but not 3.4:
#   https://docs.python.org/3/whatsnew/3.5.html#other-language-changes
#   https://bugs.python.org/issue17636
# - see also:
#   http://stackoverflow.com/questions/6351805/cyclic-module-dependencies-and-relative-imports-in-python  # noqa
#   http://stackoverflow.com/questions/35776791/type-hinting-union-with-forward-references  # noqa
# - OK, still problems.
#   Let's strip this back to something sensible.
#   Does BaseNlpParser really need to know about NlpDefinition?
#   - Not directly.
#   - For typing, if it stores a reference (optional).
#   - It could also be given subcomponents instead.
#   Does NlpDefinition really need to know about BaseNlpParser?
#   - Yes, but only for delayed imports.
# - For now, solved by weakening type hints for NlpDefinition.
# - # noinspection PyUnresolvedReferences
#   ... see http://codeoptimism.com/blog/pycharm-suppress-inspections-list/
#   for a full list.

log = logging.getLogger(__name__)


# =============================================================================
# Config class
# =============================================================================

class NlpDefinition(object):
    """
    Class representing NLP master configuration as read from config file.
    """

    # noinspection PyUnresolvedReferences
    def __init__(self, nlpname: str, logtag: str = "") -> None:
        """
        Read config from file.
        """

        # DELAYED IMPORTS (to make life simpler for classes deriving from
        # NlpParser and using NlpDefinition -- they can now do it directly,
        # not just via forward reference).
        from crate_anon.nlp_manager.all_processors import make_processor
        from crate_anon.nlp_manager.input_field_config import InputFieldConfig

        self._nlpname = nlpname
        self._logtag = logtag

        log.info("Loading config for section: {}".format(nlpname))
        # Get filename
        try:
            self._config_filename = os.environ[NLP_CONFIG_ENV_VAR]
            assert self._config_filename
        except (KeyError, AssertionError):
            print(
                "You must set the {} environment variable to point to a CRATE "
                "anonymisation config file. Run crate_print_demo_anon_config "
                "to see a specimen config.".format(NLP_CONFIG_ENV_VAR))
            sys.exit(1)

        # Read config from file.
        self._parser = ExtendedConfigParser()
        self._parser.optionxform = str  # make it case-sensitive
        log.info("Reading config file: {}".format(self._config_filename))
        self._parser.read_file(codecs.open(self._config_filename, "r", "utf8"))

        if not self._parser.has_section(nlpname):
            raise ValueError("No section named {} present".format(nlpname))

        # ---------------------------------------------------------------------
        # Our own stuff
        # ---------------------------------------------------------------------
        self._databases = {}  # type: Dict[str, DatabaseHolder]
        self._progressdb_name = self.opt_str(nlpname, 'progressdb',
                                             required=True)
        self._progdb = self.get_database(self._progressdb_name)
        self._temporary_tablename = self.opt_str(
            nlpname, 'temporary_tablename',
            default=DEFAULT_TEMPORARY_TABLENAME)
        self._hashphrase = self.opt_str(nlpname, 'hashphrase', required=True)
        self._hasher = HashClass(self._hashphrase)
        self._max_rows_before_commit = self.opt_int(
            nlpname, 'max_rows_before_commit', DEFAULT_MAX_ROWS_BEFORE_COMMIT)
        self._max_bytes_before_commit = self.opt_int(
            nlpname, 'max_bytes_before_commit',
            DEFAULT_MAX_BYTES_BEFORE_COMMIT)
        self._now = get_now_utc_notz_datetime()

        # ---------------------------------------------------------------------
        # Input field definitions
        # ---------------------------------------------------------------------
        self._inputfielddefs = self.opt_strlist(nlpname, 'inputfielddefs',
                                                required=True, lower=False)
        self._inputfieldmap = {}  # type: Dict[str, InputFieldConfig]
        for x in self._inputfielddefs:
            if x in self._inputfieldmap:
                continue
            self._inputfieldmap[x] = InputFieldConfig(self, x)

        # ---------------------------------------------------------------------
        # NLP processors
        # ---------------------------------------------------------------------
        self._processors = []  # type: List[BaseNlpParser]
        processorpairs = self.opt_strlist(nlpname, 'processors', required=True,
                                          lower=False)
        try:
            for proctype, procname in chunks(processorpairs, 2):
                self.require_section(procname)
                processor = make_processor(proctype, self, procname)
                self._processors.append(processor)
        except ValueError:
            log.critical("Bad 'processors' specification")
            raise

        # ---------------------------------------------------------------------
        # Transaction sizes, for early commit
        # ---------------------------------------------------------------------
        self._transaction_limiters = {}  # type: Dict[Session, TransactionSizeLimiter]  # noqa
        # dictionary of session -> TransactionSizeLimiter

    def get_name(self) -> str:
        return self._nlpname

    def get_logtag(self) -> str:
        return self._logtag

    def get_parser(self) -> ExtendedConfigParser:
        return self._parser

    def hash(self, text: str) -> str:
        return self._hasher.hash(text)

    def get_temporary_tablename(self) -> str:
        return self._temporary_tablename

    def set_echo(self, echo: bool) -> None:
        self._progdb.engine.echo = echo
        for db in self._databases.values():
            db.engine.echo = echo
        # Now, SQLAlchemy will mess things up by adding an additional handler.
        # So, bye-bye:
        for logname in ('sqlalchemy.engine.base.Engine',
                        'sqlalchemy.engine.base.OptionEngine'):
            logger = logging.getLogger(logname)
            logger.handlers = []  # type: List[logging.Handler]

    def require_section(self, section: str) -> None:
        if not self._parser.has_section(section):
            msg = "Missing config section: {}".format(section)
            log.critical(msg)
            raise ValueError(msg)

    def opt_str(self, section: str, option: str, required: bool = False,
                default: str = None) -> str:
        return self._parser.get_str(section, option, default=default,
                                    required=required)

    def opt_strlist(self, section: str, option: str, required: bool = False,
                    lower: bool = True, as_words: bool = True) -> List[str]:
        return self._parser.get_str_list(section, option, as_words=as_words,
                                         lower=lower, required=required)

    def opt_int(self, section: str, option: str,
                default: Optional[int]) -> Optional[int]:
        return self._parser.getint(section, option, fallback=default)

    def opt_bool(self, section: str, option: str, default: bool) -> bool:
        return self._parser.getboolean(section, option, fallback=default)

    def get_database(self, name_and_cfg_section: str,
                     with_session: bool = True,
                     with_conn: bool = False,
                     reflect: bool = False) -> DatabaseHolder:
        if name_and_cfg_section in self._databases:
            return self._databases[name_and_cfg_section]
        assert len(name_and_cfg_section) <= MAX_SQL_FIELD_LEN
        db = self._parser.get_database(name_and_cfg_section,
                                       with_session=with_session,
                                       with_conn=with_conn,
                                       reflect=reflect)
        self._databases[name_and_cfg_section] = db
        return db

    def get_env_dict(self, section: str,
                     parent_env: Optional[Dict]=None) -> Dict:
        return self._parser.get_env_dict(section, parent_env=parent_env)

    def get_progdb_session(self) -> Session:
        return self._progdb.session

    def get_progdb_engine(self) -> Engine:
        return self._progdb.engine

    def get_progdb_metadata(self) -> MetaData:
        return self._progdb.metadata

    def commit_all(self) -> None:
        """
        Execute a COMMIT on all databases (destination + progress).
        """
        self.commit(self.get_progdb_session())
        for db in self._databases.values():
            self.commit(db.session)

    def get_transation_limiter(self,
                               session: Session) -> TransactionSizeLimiter:
        if session not in self._transaction_limiters:
            self._transaction_limiters[session] = TransactionSizeLimiter(
                session,
                max_rows_before_commit=self._max_rows_before_commit,
                max_bytes_before_commit=self._max_bytes_before_commit)
        return self._transaction_limiters[session]

    def notify_transaction(self, session: Session,
                           n_rows: int, n_bytes: int,
                           force_commit: bool=False) -> None:
        tl = self.get_transation_limiter(session)
        tl.notify(n_rows=n_rows, n_bytes=n_bytes, force_commit=force_commit)

    def commit(self, session: Session) -> None:
        tl = self.get_transation_limiter(session)
        tl.commit()

    # noinspection PyUnresolvedReferences
    def get_processors(self) -> List['base_nlp_parser.BaseNlpParser']:  # typing / circular reference problem  # noqa
        return self._processors

    # noinspection PyUnresolvedReferences
    def get_ifconfigs(self) -> Iterable['input_field_config.InputFieldConfig']:  # typing / circular reference problem  # noqa
        return self._inputfieldmap.values()

    def get_now(self) -> datetime.datetime:
        return self._now
