#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_definition.py

# =============================================================================
# Imports
# =============================================================================

import codecs
import datetime
import logging
import os
import sys
from typing import Dict, List, Optional

from cardinal_pythonlib.rnc_datetime import get_now_utc_notz
from cardinal_pythonlib.rnc_lang import chunks

from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.common.extendedconfigparser import ExtendedConfigParser
from crate_anon.nlp_manager.constants import (
    HashClass,
    MAX_SQL_FIELD_LEN,
    NLP_CONFIG_ENV_VAR,
)

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
        self._databases = {}
        self._progressdb_name = self.opt_str(nlpname, 'progressdb',
                                             required=True)
        self._progdb = self.get_database(self._progressdb_name)

        self._hashphrase = self.opt_str(nlpname, 'hashphrase', required=True)
        self._hasher = HashClass(self._hashphrase)

        self._now = get_now_utc_notz()

        # ---------------------------------------------------------------------
        # Input field definitions
        # ---------------------------------------------------------------------
        self._inputfielddefs = self.opt_strlist(nlpname, 'inputfielddefs',
                                                required=True, lower=False)
        self._inputfieldmap = {}
        for x in self._inputfielddefs:
            if x in self._inputfieldmap:
                continue
            self._inputfieldmap[x] = InputFieldConfig(self, x)

        # ---------------------------------------------------------------------
        # NLP processors
        # ---------------------------------------------------------------------
        self._processors = []
        processorpairs = self.opt_strlist(nlpname, 'processors', required=True,
                                          lower=False)
        try:
            for proctype, procname in chunks(processorpairs, 2):
                self.require_section(procname)
                processor = make_processor(proctype, self, procname)
                self._processors.append(processor)
        except:
            log.critical("Bad 'processors' specification")
            raise

    def get_name(self) -> str:
        return self._nlpname

    def get_logtag(self) -> str:
        return self._logtag

    def get_parser(self) -> ExtendedConfigParser:
        return self._parser

    def hash(self, text: str) -> str:
        return self._hasher.hash(text)

    def set_echo(self, echo: bool) -> None:
        self._progdb.engine.echo = echo
        for db in self._databases.values():
            db.engine.echo = echo
        # Now, SQLAlchemy will mess things up by adding an additional handler.
        # So, bye-bye:
        for logname in ['sqlalchemy.engine.base.Engine',
                        'sqlalchemy.engine.base.OptionEngine']:
            logger = logging.getLogger(logname)
            logger.handlers = []

    def require_section(self, section: str) -> None:
        if not self._parser.has_section(section):
            msg = "Missing config section: {}".format(section)
            log.critical(msg)
            raise ValueError(msg)

    def opt_str(self, section: str, option: str, required: bool = False,
                default: bool = None) -> str:
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

    def get_progdb_session(self):
        return self._progdb.session

    def get_progdb_engine(self):
        return self._progdb.engine

    def commit_all(self) -> None:
        """
        Execute a COMMIT on all databases (destination + progress).
        """
        self.get_progdb_session().commit()
        for db in self._databases.values():
            db.session.commit()

    def get_processors(self):
        return self._processors

    def get_ifconfigs(self):
        return self._inputfieldmap.values()

    def get_now(self) -> datetime.datetime:
        return self._now
