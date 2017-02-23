#!/usr/bin/env python
# crate_anon/crateweb/research/sql_grammar.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

Two approaches:

- sqlparse
  https://sqlparse.readthedocs.io/en/latest/
  ... LESS GOOD.

- pyparsing
  https://pyparsing.wikispaces.com/file/view/select_parser.py
  http://pyparsing.wikispaces.com/file/view/simpleSQL.py
  http://sacharya.com/parsing-sql-with-pyparsing/
  http://bazaar.launchpad.net/~eleybourn/temporal-proxy/devel/view/head:/parser.py  # noqa
  http://pyparsing.wikispaces.com/file/view/select_parser.py/158651233/select_parser.py  # noqa

  - Maximum recursion depth exceeded:
    http://pyparsing.wikispaces.com/share/view/11262229

  - Match-first (|) versus match-longest (^):
    http://pyparsing.wikispaces.com/HowToUsePyparsing

  - How to do arithmetic recursive parsing:
    http://stackoverflow.com/questions/1345039

  - Somebody else's MySQL parser:
    https://github.com/gburns/mysql_pyparsing/blob/master/src/sqlparser.py

  - ... or generic SQL:
    http://pyparsing.wikispaces.com/file/view/select_parser.py/158651233/select_parser.py  # noqa

ANSI SQL syntax:
    http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
    ... particularly the formal specifications in chapter 5 on wards
"""

import logging
import re
from typing import List, Union

from pyparsing import (
    Combine,
    Literal,
    Optional,
    ParseException,
    ParserElement,
    ParseResults,
    QuotedString,
    Regex,
    Suppress,
    Token,
    restOfLine,
    ZeroOrMore,
)
import sqlparse

from crate_anon.common.logsupport import main_only_quicksetup_rootlogger

log = logging.getLogger(__name__)


# =============================================================================
# pyparsing helpers
# =============================================================================

def delim_list(expr_: Token,
               delim: str = ",",
               combine: bool = False,
               combine_adjacent: bool = False,
               suppress_delim: bool = False):
    # A better version of delimitedList
    # BUT SEE ALSO ALTERNATIVE: http://stackoverflow.com/questions/37926516
    name = str(expr_) + " [" + str(delim) + " " + str(expr_) + "]..."
    if combine:
        return Combine(expr_ + ZeroOrMore(delim + expr_),
                       adjacent=combine_adjacent).setName(name)
    else:
        if suppress_delim:
            return (expr_ + ZeroOrMore(Suppress(delim) + expr_)).setName(name)
        else:
            return (expr_ + ZeroOrMore(delim + expr_)).setName(name)


WORD_BOUNDARY = r"\b"
# The meaning of \b:
# http://stackoverflow.com/questions/4213800/is-there-something-like-a-counter-variable-in-regular-expression-replace/4214173#4214173  # noqa


def word_regex_element(word: str) -> str:
    return WORD_BOUNDARY + word + WORD_BOUNDARY


def multiple_words_regex_element(
        words_as_string_or_list: Union[str, List[str]]) -> str:
    if isinstance(words_as_string_or_list, list):
        wordlist = words_as_string_or_list
    elif isinstance(words_as_string_or_list, str):
        wordlist = words_as_string_or_list.split()
    else:
        raise ValueError("Bad wordlist to multiple_words_regex_element")
    return WORD_BOUNDARY + "(" + "|".join(wordlist) + ")" + WORD_BOUNDARY


def make_pyparsing_regex(regex_str: str,
                         caseless: bool = False,
                         name: str = None) -> Regex:
    flags = re.IGNORECASE if caseless else 0
    result = Regex(regex_str, flags=flags)
    if name:
        result.setName(name)
    return result


def make_words_regex(words_as_string_or_list: Union[str, List[str]],
                     caseless: bool = False,
                     name: str = None,
                     debug: bool = False) -> Regex:
    regex_str = multiple_words_regex_element(words_as_string_or_list)
    if debug:
        log.debug(regex_str)
    return make_pyparsing_regex(regex_str, caseless=caseless, name=name)


def make_regex_except_words(word_pattern: str,
                            negative_words_str_or_list: Union[str, List[str]],
                            caseless: bool = False,
                            name: str = None,
                            debug: bool = False) -> Regex:
    # http://regexr.com/
    regex_str = r"(?!{negative}){positive}".format(
        negative=multiple_words_regex_element(negative_words_str_or_list),
        positive=(WORD_BOUNDARY + word_pattern + WORD_BOUNDARY),
    )
    if debug:
        log.debug(regex_str)
    return make_pyparsing_regex(regex_str, caseless=caseless, name=name)


def sql_keyword(word: str) -> Regex:
    regex_str = word_regex_element(word)
    return make_pyparsing_regex(regex_str, caseless=True, name=word)


def bracket(fragment: str) -> str:
    return "(" + fragment + ")"


def single_quote(fragment: str) -> str:
    return "'" + fragment + "'"


# =============================================================================
# Potential keywords
# =============================================================================

# <reserved word>
# http://www.contrib.andrew.cmu.edu/~shadow/sql/sql2bnf.aug92.txt
ANSI92_RESERVED_WORD_LIST = """
    ABSOLUTE ACTION ADD ALL ALLOCATE ALTER AND ANY ARE AS ASC
        ASSERTION AT AUTHORIZATION AVG
    BEGIN BETWEEN BIT BIT_LENGTH BOTH BY
    CASCADE CASCADED CASE CAST CATALOG CHAR CHARACTER CHAR_LENGTH
        CHARACTER_LENGTH CHECK CLOSE COALESCE COLLATE COLLATION
        COLUMN COMMIT CONNECT CONNECTION CONSTRAINT CONSTRAINTS CONTINUE
        CONVERT CORRESPONDING COUNT CREATE CROSS CURRENT
        CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR
    DATE DAY DEALLOCATE DEC DECIMAL DECLARE DEFAULT DEFERRABLE
        DEFERRED DELETE DESC DESCRIBE DESCRIPTOR DIAGNOSTICS
        DISCONNECT DISTINCT DOMAIN DOUBLE DROP
    ELSE END END-EXEC ESCAPE EXCEPT EXCEPTION EXEC EXECUTE EXISTS
        EXTERNAL EXTRACT
    FALSE FETCH FIRST FLOAT FOR FOREIGN FOUND FROM FULL
    GET GLOBAL GO GOTO GRANT GROUP
    HAVING HOUR
    IDENTITY IMMEDIATE IN INDICATOR INITIALLY INNER INPUT INSENSITIVE
        INSERT INT INTEGER INTERSECT INTERVAL INTO IS ISOLATION
    JOIN
    KEY
    LANGUAGE LAST LEADING LEFT LEVEL LIKE LOCAL LOWER
    MATCH MAX MIN MINUTE MODULE MONTH
    NAMES NATIONAL NATURAL NCHAR NEXT NO NOT NULL NULLIF NUMERIC
    OCTET_LENGTH OF ON ONLY OPEN OPTION OR ORDER OUTER OUTPUT OVERLAPS
    PAD PARTIAL POSITION PRECISION PREPARE PRESERVE PRIMARY
    PRIOR PRIVILEGES PROCEDURE PUBLIC
    READ REAL REFERENCES RELATIVE RESTRICT REVOKE RIGHT ROLLBACK ROWS
    SCHEMA SCROLL SECOND SECTION SELECT SESSION SESSION_USER SET
        SIZE SMALLINT SOME SPACE SQL SQLCODE SQLERROR SQLSTATE
        SUBSTRING SUM SYSTEM_USER
    TABLE TEMPORARY THEN TIME TIMESTAMP TIMEZONE_HOUR TIMEZONE_MINUTE
        TO TRAILING TRANSACTION TRANSLATE TRANSLATION TRIM TRUE
    UNION UNIQUE UNKNOWN UPDATE UPPER USAGE USER USING
    VALUE VALUES VARCHAR VARYING VIEW
    WHEN WHENEVER WHERE WITH WORK WRITE
    YEAR
    ZONE
"""

# Keywords, using regexes for speed
ALL = sql_keyword("ALL")
ALTER = sql_keyword("ALTER")
AND = sql_keyword("AND")
ANY = sql_keyword("ANY")
AS = sql_keyword("AS")
ASC = sql_keyword("ASC")
AVG = sql_keyword("AVG")
BETWEEN = sql_keyword("BETWEEN")
BY = sql_keyword("BY")
CASE = sql_keyword("CASE")
CASCADE = sql_keyword("CASCADE")
COLLATE = sql_keyword("COLLATE")
CREATE = sql_keyword("CREATE")
CROSS = sql_keyword("CROSS")
COUNT = sql_keyword("COUNT")
DATE = sql_keyword("DATE")
DATETIME = sql_keyword("DATETIME")
DELETE = sql_keyword("DELETE")
DEFAULT = sql_keyword("DEFAULT")
DESC = sql_keyword("DESC")
DISTINCT = sql_keyword("DISTINCT")
DROP = sql_keyword("DROP")
ELSE = sql_keyword("ELSE")
END = sql_keyword("END")
ESCAPE = sql_keyword("ESCAPE")
EXISTS = sql_keyword("EXISTS")
FALSE = sql_keyword("FALSE")
FIRST = sql_keyword("FIRST")
FOR = sql_keyword("FOR")
FROM = sql_keyword("FROM")
GROUP = sql_keyword("GROUP")
HAVING = sql_keyword("HAVING")
IN = sql_keyword("IN")
INDEX = sql_keyword("INDEX")
INNER = sql_keyword("INNER")
INSERT = sql_keyword("INSERT")
INTERVAL = sql_keyword("INTERVAL")
INTO = sql_keyword("INTO")
IS = sql_keyword("IS")
JOIN = sql_keyword("JOIN")
KEY = sql_keyword("KEY")
LANGUAGE = sql_keyword("LANGUAGE")
LAST = sql_keyword("LAST")
LEFT = sql_keyword("LEFT")
LIKE = sql_keyword("LIKE")
MATCH = sql_keyword("MATCH")
MAX = sql_keyword("MAX")
MIN = sql_keyword("MIN")
NATURAL = sql_keyword("NATURAL")
NOT = sql_keyword("NOT")
NULL = sql_keyword("NULL")
ON = sql_keyword("ON")
ONLY = sql_keyword("ONLY")
OR = sql_keyword("OR")
ORDER = sql_keyword("ORDER")
OUTER = sql_keyword("OUTER")
RESTRICT = sql_keyword("RESTRICT")
RIGHT = sql_keyword("RIGHT")
SELECT = sql_keyword("SELECT")
SET = sql_keyword("SET")
SUM = sql_keyword("SUM")
TABLE = sql_keyword("TABLE")
THEN = sql_keyword("THEN")
TIME = sql_keyword("TIME")
TIMESTAMP = sql_keyword("TIMESTAMP")
TRUE = sql_keyword("TRUE")
UNION = sql_keyword("UNION")
UPDATE = sql_keyword("UPDATE")
USE = sql_keyword("USE")
USING = sql_keyword("USING")
UNKNOWN = sql_keyword("UNKNOWN")
VALUES = sql_keyword("VALUES")
WHEN = sql_keyword("WHEN")
WHERE = sql_keyword("WHERE")
WITH = sql_keyword("WITH")

# =============================================================================
# Punctuation
# =============================================================================

COMMA = Literal(",")
LPAR = Literal("(")
RPAR = Literal(")")

# =============================================================================
# Types of comments
# =============================================================================

ansi_comment = Literal("--") + restOfLine
bash_comment = Literal("#") + restOfLine

# =============================================================================
# Literals
# =============================================================================
# http://dev.mysql.com/doc/refman/5.7/en/literals.html
# http://dev.mysql.com/doc/refman/5.7/en/date-and-time-literals.html

boolean_literal = make_words_regex("TRUE FALSE", name="boolean")
binary_literal = Regex("(b'[01]+')|(0b[01]+)").setName("binary")
hexadecimal_literal = Regex("(X'[0-9a-fA-F]+')|"
                            "(x'[0-9a-fA-F]+')|"
                            "(0x[0-9a-fA-F]+)").setName("hex")
numeric_literal = Regex(r"[+-]?\d+(\.\d*)?([eE][+-]?\d+)?")
integer = Regex(r"[+-]?\d+")  # ... simple integer
sql_keyword_literal = make_words_regex("NULL TRUE FALSE UNKNOWN",
                                       name="boolean")

string_value_singlequote = QuotedString(
    quoteChar="'", escChar="\\", escQuote="''", unquoteResults=False
).setName("single_q_string")
string_value_doublequote = QuotedString(
    quoteChar='"', escChar='\\', escQuote='""', unquoteResults=False
).setName("double_q_string")
string_literal = (
    string_value_singlequote | string_value_doublequote
).setName("string")

# http://dev.mysql.com/doc/refman/5.7/en/date-and-time-literals.html
RE_YEAR = r"([\d]{4}|[\d]{2})"
RE_MONTH = bracket(r"[0][1-9]|[1][0-2]")  # 01 to 12
RE_DAY = bracket(r"[0][0-1]|[1-2][1-9]|[3][0-1]")  # 01 to 31
RE_HOUR = bracket(r"[0-1][0-9]|[2][0-3]")  # 00 to 23
RE_MINUTE = bracket(r"[0-5][0-9]")  # 00 to 59
RE_SECOND = RE_MINUTE
FRACTIONAL_SECONDS = bracket(r"(.[0-9]{1,6})?")  # dot then from 1-6 digits
PUNCTUATION = r"[_,!@#$%&*;\\|:./\^-]"
DATESEP = bracket(r"{}?".format(PUNCTUATION))  # "any punctuation"... or none
DTSEP = bracket(r"[T ]?")  # T or none
TIMESEP = bracket(r"[:]?")  # can also be none

DATE_CORE_REGEX_STR = (
    "({year}{sep}{month}{sep}{day})".format(
        year=RE_YEAR,
        month=RE_MONTH,
        day=RE_DAY,
        sep=DATESEP
    )
)
DATE_LITERAL_REGEX_STR = single_quote(DATE_CORE_REGEX_STR)
TIME_CORE_REGEX_STR = (
    bracket(
        "({hour}{sep}{minute}{sep}{second}{fraction})|"
        "({hour}{sep}{minute})".format(
            hour=RE_HOUR,
            minute=RE_MINUTE,
            second=RE_SECOND,
            fraction=FRACTIONAL_SECONDS,
            sep=TIMESEP
        )
    )
)
TIME_LITERAL_REGEX_STR = single_quote(TIME_CORE_REGEX_STR)
DATETIME_CORE_REGEX_STR = "({date}{sep}{time})".format(
    date=DATE_CORE_REGEX_STR,
    sep=DTSEP,
    time=TIME_CORE_REGEX_STR)
DATETIME_LITERAL_REGEX_STR = single_quote(DATETIME_CORE_REGEX_STR)

date_string = Regex(DATE_LITERAL_REGEX_STR)
time_string = Regex(TIME_LITERAL_REGEX_STR)
datetime_string = Regex(DATETIME_LITERAL_REGEX_STR)
datetime_literal = (
    (Optional(DATE | 'd') + date_string) |
    (Optional(TIME | 't') + time_string) |
    (Optional(TIMESTAMP | 'ts') + datetime_string)
).setName("datetime")

literal_value = (
    numeric_literal |
    boolean_literal |
    binary_literal |
    hexadecimal_literal |
    sql_keyword_literal |
    string_literal |
    datetime_literal
).setName("literal_value")

# https://dev.mysql.com/doc/refman/5.7/en/date-and-time-functions.html#function_date-add  # noqa
time_unit = make_words_regex(
    "MICROSECOND SECOND MINUTE HOUR DAY WEEK MONTH QUARTER YEAR"
    " SECOND_MICROSECOND"
    " MINUTE_MICROSECOND MINUTE_SECOND"
    " HOUR_MICROSECOND HOUR_SECOND HOUR_MINUTE"
    " DAY_MICROSECOND DAY_SECOND DAY_MINUTE DAY_HOUR"
    " YEAR_MONTH",
    caseless=True,
    name="time_unit"
)

# =============================================================================
# sqlparse tests
# =============================================================================

# def parsed_from_text(sql):
#     statements = sqlparse.parse(sql)
#     if not statements:
#         return None
#     first_statement = statements[0]
#     return first_statement


def format_sql(sql: str, reindent: bool = True, indent_width: int = 4) -> str:
    # https://media.readthedocs.org/pdf/sqlparse/latest/sqlparse.pdf
    return sqlparse.format(
        sql,
        reindent=reindent,
        indent_width=indent_width,
        # keyword_case='upper',
    )
    # DON'T use keyword_case='upper'. It converts things like
    # "SELECT ... AS table_name" to "SELECT ... AS TABLE_NAME".


# def formatted_from_parsed(statement):
#     sql = str(statement)
#     return format_sql(sql)


# =============================================================================
# pyparsing test
# =============================================================================

# See also: parser.runTests()

def standardize_for_testing(text: str) -> str:
    text = " ".join(text.split())
    text = text.replace("- ", "-")
    text = text.replace("+ ", "+")
    text = text.replace("~ ", "~")
    text = text.replace("! ", "!")
    text = text.replace(" (", "(")
    text = text.replace("( ", "(")
    text = text.replace(" )", ")")
    return text


def test_succeed(parser: ParserElement,
                 text: str,
                 target: str = None,
                 skip_target: bool = False,
                 show_raw: bool = False,
                 verbose: bool = False) -> None:
    log.critical("Testing to succeed: " + text)
    if target is None:
        target = text
    try:
        p = parser.parseString(text, parseAll=True)
        log.debug("Success: {} -> {}".format(text, text_from_parsed(p)))
        if show_raw:
            log.debug("... raw: {}".format(p))
        if verbose:
            log.debug("... dump:\n{}".format(p.dump()))
    except ParseException as exception:
        log.debug("ParseException on: {}\n... parser: {}".format(text, parser))
        print(statement_and_failure_marker(text, exception))
        raise
    if not skip_target:
        intended = standardize_for_testing(target)
        raw = text_from_parsed(p)
        actual = standardize_for_testing(raw)
        if intended != actual:
            raise ValueError(
                "Failure on: {input}\n"
                "-> Raw output:\n{raw}\n"
                "-> Standardized output:\n{actual}\n"
                "... should have been:\n{intended}\n"
                "... parser: {parser}\n"
                "... as list: {as_list}]".format(
                    input=text,
                    raw=repr(raw),
                    actual=repr(actual),
                    intended=repr(intended),
                    parser=parser,
                    as_list=repr(p.asList())))


def test_fail(parser: ParserElement, text: str, verbose: bool = True) -> None:
    if verbose:
        log.critical("Testing to fail: " + text)
    try:
        p = parser.parseString(text, parseAll=True)
        raise ValueError(
            "Succeeded erroneously (no ParseException): {input}\n"
            "-> structured format: {p}\n"
            "-> Raw text output: {raw}\n"
            "... parser: {parser}]".format(
                input=text,
                raw=text_from_parsed(p),
                p=p,
                parser=parser))
    except ParseException:
        log.debug("Correctly failed: {}".format(text))


def test(parser: ParserElement, text: str) -> None:
    print("STATEMENT:\n{}".format(text))

    # scanned = parser.scanString(text)
    # for tokens, start, end in scanned:
    #     print(start, end, tokens)

    try:
        tokens = parser.parseString(text, parseAll=True)
        print(tokens.asXML())
        # print(tokens.dump())
        # print(text_from_parsed(tokens))
        print("tokens = {}".format(tokens))
        d = tokens.asDict()
        for k, v in d.items():
            print("tokens.{} = {}".format(k, v))
        for c in tokens.columns:
            print("column: {}".format(c))
    except ParseException as err:
        print(statement_and_failure_marker(text, err))
        raise
    print()


def flatten(*args):
    for x in args:
        if isinstance(x, (list, tuple)):
            for y in flatten(*x):
                yield y
        else:
            yield x


def text_from_parsed(parsetree: ParseResults,
                     formatted: bool = True,
                     indent_width: int = 4) -> str:
    nested_list = parsetree.asList()
    flattened_list = flatten(nested_list)
    plain_str = " ".join(flattened_list)
    if not formatted:
        return plain_str

    # Forget my feeble efforts for now (below) and use sqlparse:
    return format_sql(plain_str, reindent=True, indent_width=indent_width)

    # result = ""
    # newline_before = ["SELECT", "FROM", "WHERE", "GROUP"]
    # indent_after = ["SELECT", "FROM", "WHERE", "GROUP"]
    # no_space_before = [",", ")"]
    # no_space_after = ["("]
    # at_line_start = True
    # indent = 0
    #
    # def start_new_line(indent_change=0):
    #     nonlocal at_line_start
    #     nonlocal indent
    #     nonlocal result
    #     if at_line_start:
    #         return
    #     indent += indent_change
    #     result += "\n" + " " * indent * indent_spaces
    #     at_line_start = True
    #
    # previous_item = None
    # for index, item in enumerate(flattened_list):
    #     if item in newline_before:
    #         start_new_line(indent_change=-1)
    #     leading_space = (
    #         not at_line_start and
    #         item not in no_space_before and
    #         previous_item not in no_space_after
    #     )
    #     if leading_space:
    #         result += " "
    #     result += item
    #     at_line_start = False
    #     if item in indent_after:
    #         start_new_line(indent_change=1)
    #     previous_item = item
    # return result


def statement_and_failure_marker(text: str,
                                 parse_exception: ParseException) -> str:
    output_lines = []
    for line_index, line in enumerate(text.split("\n")):
        output_lines.append(line)
        if parse_exception.lineno == line_index + 1:
            output_lines.append("-" * (parse_exception.col - 1) + "^")
    return "\n".join(output_lines)


# =============================================================================
# Base class for SQL grammar
# =============================================================================

class SqlGrammar(object):
    # For type checker:
    bare_identifier_word = None
    column_spec = None
    expr = None
    expr_term = None
    identifier = None
    join_op = None
    join_source = None
    keyword = None
    result_column = None
    select_statement = None
    table_spec = None

    def __init__(self):
        pass

    @classmethod
    def quote_identifier_if_required(cls, identifier: str,
                                     debug_force_quote: bool = False) -> str:
        if debug_force_quote:
            return cls.quote_identifier(identifier)
        if cls.is_quoted(identifier):
            return identifier
        if cls.requires_quoting(identifier):
            return cls.quote_identifier(identifier)
        return identifier

    @classmethod
    def quote_identifier(cls, identifier: str) -> str:
        raise NotImplementedError()

    @classmethod
    def is_quoted(cls, identifier: str) -> bool:
        raise NotImplementedError()

    @classmethod
    def requires_quoting(cls, identifier: str) -> bool:
        raise NotImplementedError()

    @classmethod
    def get_grammar(cls):
        raise NotImplementedError()

    @classmethod
    def get_column_spec(cls):
        raise NotImplementedError()

    @classmethod
    def get_result_column(cls):
        raise NotImplementedError()

    @classmethod
    def get_join_op(cls):
        raise NotImplementedError()

    @classmethod
    def get_table_spec(cls):
        raise NotImplementedError()

    @classmethod
    def get_join_constraint(cls):
        raise NotImplementedError()

    @classmethod
    def get_select_statement(cls):
        raise NotImplementedError()

    @classmethod
    def get_expr(cls):
        raise NotImplementedError()

    @classmethod
    def get_where_clause(cls):
        raise NotImplementedError()

    @classmethod
    def get_where_expr(cls):
        raise NotImplementedError()

    @classmethod
    def test(cls, test_expr: bool = True):
        cls.test_dialect_specific_1()
        cls.test_identifiers()
        if test_expr:
            cls.test_expr()
        cls.test_sql_core()
        cls.test_dialect_specific_2()

    @classmethod
    def test_select(cls, text: str) -> None:
        test_succeed(cls.select_statement, text)

    @classmethod
    def test_select_fail(cls, text: str) -> None:
        test_fail(cls.select_statement, text)

    @classmethod
    def test_identifiers(cls):
        # ---------------------------------------------------------------------
        # Identifiers
        # ---------------------------------------------------------------------
        log.info("Testing keyword")
        # print(cls.keyword.pattern)
        test_succeed(cls.keyword, "TABLE")
        test_fail(cls.keyword, "thingfor")  # shouldn't match FOR
        test_fail(cls.keyword, "forename")  # shouldn't match FOR

        log.info("Testing bare_identifier_word")
        test_succeed(cls.bare_identifier_word, "blah")
        test_fail(cls.bare_identifier_word, "FROM")
        test_succeed(cls.bare_identifier_word, "forename")

        log.info("Testing identifier")
        test_succeed(cls.identifier, "blah")
        test_succeed(cls.identifier, "idx1")
        test_succeed(cls.identifier, "idx2")
        test_succeed(cls.identifier, "a")
        log.info("... done")

        log.info("Testing table_spec")
        test_succeed(cls.table_spec, "mytable")
        test_succeed(cls.table_spec, "mydb.mytable")
        test_fail(cls.table_spec, "mydb . mytable")

        log.info("Testing column_spec")
        test_succeed(cls.column_spec, "mycol")
        test_succeed(cls.column_spec, "forename")
        test_succeed(cls.column_spec, "mytable.mycol")
        test_succeed(cls.column_spec, "t1.a")
        test_succeed(cls.column_spec, "mydb.mytable.mycol")
        test_fail(cls.column_spec, "mydb . mytable . mycol")

    @classmethod
    def test_expr(cls):
        # ---------------------------------------------------------------------
        # Expressions
        # ---------------------------------------------------------------------

        log.info("Testing expr_term")
        test_succeed(cls.expr_term, "5")
        test_succeed(cls.expr_term, "-5")
        test_succeed(cls.expr_term, "5.12")
        test_succeed(cls.expr_term, "'string'")
        test_succeed(cls.expr_term, "mycol")
        test_succeed(cls.expr_term, "myfunc(myvar, 8)")
        test_succeed(cls.expr_term, "INTERVAL 5 MICROSECOND")
        test_succeed(cls.expr_term, "(SELECT 1)")
        test_succeed(cls.expr_term, "(1, 2, 3)")
        # Concatenated rubbish shouldn't pass
        # test_fail(cls.expr_term, "one two three four")  # matches "one"

        log.info("Testing expr")
        test_succeed(cls.expr, "5")
        test_succeed(cls.expr, "-5")
        test_succeed(cls.expr, "a")
        test_succeed(cls.expr, "mycol1 || mycol2")
        test_succeed(cls.expr, "+mycol")
        test_succeed(cls.expr, "-mycol")
        test_succeed(cls.expr, "~mycol")
        test_succeed(cls.expr, "!mycol")
        test_succeed(cls.expr, "a | b")
        test_succeed(cls.expr, "a & b")
        test_succeed(cls.expr, "a << b")
        test_succeed(cls.expr, "a >> b")
        test_succeed(cls.expr, "a + b")
        test_succeed(cls.expr, "a - b")
        test_succeed(cls.expr, "a * b")
        test_succeed(cls.expr, "a / b")
        test_succeed(cls.expr, "a % b")
        test_succeed(cls.expr, "a ^ b")
        test_succeed(cls.expr, "a ^ (b + (c - d) / e)")
        test_succeed(cls.expr, "a NOT IN (SELECT 1)")
        test_succeed(cls.expr, "a IN (1, 2, 3)")
        test_succeed(cls.expr, "a IS NULL")
        test_succeed(cls.expr, "a IS NOT NULL")
        test_fail(cls.expr, "IS NULL")
        test_fail(cls.expr, "IS NOT NULL")
        test_succeed(cls.expr, "(a * (b - 3)) > (d - 2)")

        # Bare keywords shouldn't pass:
        test_fail(cls.expr, "COUNT")

        # Concatenated rubbish shouldn't pass
        test_fail(cls.expr, "one two three four")

    @classmethod
    def test_sql_core(cls):
        log.info("Testing join_op")
        test_succeed(cls.join_op, ",")
        test_succeed(cls.join_op, "INNER JOIN")

        log.info("Testing join_source")
        test_succeed(cls.join_source, "a")
        test_succeed(cls.join_source, "a INNER JOIN b")
        test_succeed(cls.join_source, "a, b")

        log.info("Testing result_column")
        test_succeed(cls.result_column, "t1.a")
        test_succeed(cls.result_column, "col1")
        test_succeed(cls.result_column, "t1.col1")
        test_succeed(cls.result_column, "col1 AS alias")
        test_succeed(cls.result_column, "t1.col1 AS alias")
        # test_succeed(cls.result_column, "*")
        test_succeed(cls.result_column, "COUNT(*)")
        test_succeed(cls.result_column, "COUNT(*) AS alias")
        test_fail(cls.result_column, "COUNT")

        test_succeed(Combine(COUNT + LPAR) + '*', "COUNT(*")
        test_succeed(Combine(COUNT + LPAR) + '*', "COUNT( *")
        test_fail(Combine(COUNT + LPAR) + '*', "COUNT (*")

        test_fail(cls.result_column, "COUNT (*)")  # space disallowed
        test_succeed(cls.result_column, "COUNT(DISTINCT col)")
        test_succeed(cls.result_column, "MAX(col)")
        test_fail(cls.result_column, "MAX (col)")

        log.info("Testing select_statement")
        cls.test_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 IN (1, 2, 3)")
        cls.test_select("SELECT a, b FROM c")  # no WHERE
        cls.test_select("SELECT a, b FROM c WHERE d > 5 AND e = 4")
        cls.test_select("SELECT a, b FROM c INNER JOIN f WHERE d > 5 AND e = 4")
        cls.test_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5")

        log.info("Testing SELECT something AS alias")
        cls.test_select("SELECT col1 AS alias FROM t1")
        cls.test_select("SELECT t1.col1 AS alias FROM t1")

        log.info("Testing nested query: IN")
        cls.test_select("SELECT col1 FROM table1 WHERE col2 IN (SELECT col3 FROM table2)")  # noqa

        log.info("Testing COUNT(*)")
        cls.test_select("SELECT col1, COUNT(*) FROM table1 GROUP BY col1")

        log.info("MySQL rejects COUNT (*) and other aggregate functions with "
                 "a space between the function and the opening bracket")
        cls.test_select_fail(
            "SELECT col1, COUNT (*) FROM table1 GROUP BY col1")

        log.info("Testing SELECT with literal")
        cls.test_select("SELECT 'blah' AS some_literal")

        log.info("Testing SELECT result columns")
        test_succeed(cls.get_result_column(), "somecol")
        test_succeed(cls.get_result_column(), "somecol AS alias")
        test_succeed(cls.get_result_column(), "COUNT(*)")
        test_succeed(cls.get_result_column(), "COUNT(*) AS alias")
        test_succeed(cls.get_result_column(), "'blah'")
        test_succeed(cls.get_result_column(), "'blah' AS alias")
        test_succeed(cls.get_result_column(), "NULL")
        test_succeed(cls.get_result_column(), "NULL AS alias")

    @classmethod
    def test_dialect_specific_1(cls):
        pass

    @classmethod
    def test_dialect_specific_2(cls):
        pass


def test_base_elements() -> None:
    # -------------------------------------------------------------------------
    # pyparsing tests
    # -------------------------------------------------------------------------
    log.info("Testing pyparsing elements")
    regexp_for = Regex(r"\bfor\b", flags=re.IGNORECASE)
    test_succeed(regexp_for, "for")
    test_fail(regexp_for, "blandford")
    test_fail(regexp_for, "upfor")
    test_fail(regexp_for, "forename")

    # -------------------------------------------------------------------------
    # Literals
    # -------------------------------------------------------------------------
    log.info("Testing boolean_literal")
    test_succeed(boolean_literal, "TRUE")
    test_succeed(boolean_literal, "FALSE")
    test_fail(boolean_literal, "blah")

    log.info("Testing binary_literal")
    test_succeed(binary_literal, "b'010101'")
    test_succeed(binary_literal, "0b010101")

    log.info("Testing hexadecimal_literal")
    test_succeed(hexadecimal_literal, "X'12fac'")
    test_succeed(hexadecimal_literal, "x'12fac'")
    test_succeed(hexadecimal_literal, "0x12fac")

    log.info("Testing integer")
    test_succeed(integer, "99")
    test_succeed(integer, "-99")

    log.info("Testing numeric_literal")
    test_succeed(numeric_literal, "45")
    test_succeed(numeric_literal, "+45")
    test_succeed(numeric_literal, "-45")
    test_succeed(numeric_literal, "-45E-3")
    test_succeed(numeric_literal, "-45E3")
    test_succeed(numeric_literal, "-45.32")
    test_succeed(numeric_literal, "-45.32E6")

    log.info("Testing string_value_singlequote")
    test_succeed(string_value_singlequote, "'single-quoted string'")
    log.info("Testing string_value_doublequote")
    test_succeed(string_value_doublequote, '"double-quoted string"')
    log.info("Testing string_literal")
    test_succeed(string_literal, "'single-quoted string'")
    test_succeed(string_literal, '"double-quoted string"')

    log.info("Testing date_string")
    test_succeed(date_string, single_quote("2015-04-14"))
    test_succeed(date_string, single_quote("20150414"))
    log.info("Testing time_string")
    test_succeed(time_string, single_quote("15:23"))
    test_succeed(time_string, single_quote("1523"))
    test_succeed(time_string, single_quote("15:23:00"))
    test_succeed(time_string, single_quote("15:23:00.1"))
    test_succeed(time_string, single_quote("15:23:00.123456"))
    log.info("Testing datetime_string")
    test_succeed(datetime_string, single_quote("2015-04-14 15:23:00.123456"))
    test_succeed(datetime_string, single_quote("2015-04-14T15:23:00.123456"))

    log.info("Testing literal")
    test_succeed(literal_value, "NULL")
    test_succeed(literal_value, "99")
    test_succeed(literal_value, "-99")

    log.info("Testing time_unit")
    test_succeed(time_unit, "MICROSECOND")
    test_succeed(time_unit, "year_month")

    # -------------------------------------------------------------------------
    # Identifiers
    # -------------------------------------------------------------------------

    log.info("Testing FOR")
    # print(FOR.pattern)
    test_succeed(FOR, "for")
    test_fail(FOR, "thingfor")  # shouldn't match FOR
    test_fail(FOR, "forename")  # shouldn't match FOR


# =============================================================================
# main
# =============================================================================

def main() -> None:
    # blank = ''
    # p_blank = parsed_from_text(blank)
    # p_sql1 = parsed_from_text(sql1)
    # print(formatted_from_parsed(p_blank))
    # print(formatted_from_parsed(p_sql1))

    # pyparsing_bugtest_delimited_list_combine()

    log.info("TESTING BASE ELEMENTS")
    test_base_elements()
    log.info("ALL TESTS SUCCESSFUL")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    main()
