#!/usr/bin/env python

"""
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
"""

# import itertools
import logging
import re
# import sys

from pyparsing import (
    alphanums,
    # alphas,
    # alphas8bit,
    # CaselessKeyword,
    # CaselessLiteral,
    # CharsNotIn,
    Combine,
    # commaSeparatedList,
    cStyleComment,
    # downcaseTokens,
    delimitedList,
    Forward,
    Group,
    # hexnums,
    infixNotation,
    # Keyword,
    Literal,
    NotAny,
    # nums,
    oneOf,
    OneOrMore,
    opAssoc,
    Optional,
    # Or,
    ParseException,
    # ParserElement,
    QuotedString,
    Regex,
    # sglQuotedString,
    # srange,
    Suppress,
    restOfLine,
    Word,
    ZeroOrMore,
)
import sqlparse

from crate_anon.anonymise.logsupport import main_only_quicksetup_rootlogger

log = logging.getLogger(__name__)


# =============================================================================
# pyparsing helpers
# =============================================================================

def delim_list(expr_, delim=",", combine=False,
               combine_adjacent=False,
               suppress_delim=False):
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


def word_regex_element(word):
    return WORD_BOUNDARY + word + WORD_BOUNDARY


def multiple_words_regex_element(words_as_string):
    wordlist = words_as_string.split()
    return WORD_BOUNDARY + "(" + "|".join(wordlist) + ")" + WORD_BOUNDARY


def make_pyparsing_regex(regex_str, caseless=False, name=None):
    flags = re.IGNORECASE if caseless else 0
    result = Regex(regex_str, flags=flags)
    if name:
        result.setName(name)
    return result


def make_words_regex(words_as_string, caseless=False, name=None, debug=False):
    regex_str = multiple_words_regex_element(words_as_string)
    if debug:
        log.debug(regex_str)
    return make_pyparsing_regex(regex_str, caseless=caseless, name=name)


def make_regex_except_words(word_pattern, negative_words_str, caseless=False,
                            name=None, debug=False):
    # http://regexr.com/
    regex_str = r"(?!{negative}){positive}".format(
        negative=multiple_words_regex_element(negative_words_str),
        positive=(WORD_BOUNDARY + word_pattern + WORD_BOUNDARY),
    )
    if debug:
        log.debug(regex_str)
    return make_pyparsing_regex(regex_str, caseless=caseless, name=name)


def sql_keyword(word):
    regex_str = word_regex_element(word)
    return make_pyparsing_regex(regex_str, caseless=True, name=word)


def bracket(fragment):
    return "(" + fragment + ")"


def single_quote(fragment):
    return "'" + fragment + "'"


# =============================================================================
# MySQL 5.7 grammar in pyparsing
# =============================================================================
# http://dev.mysql.com/doc/refman/5.7/en/dynindex-statement.html

# Keywords, using regexed for speed
AGAINST = sql_keyword("AGAINST")
ALL = sql_keyword("ALL")
ALTER = sql_keyword("ALTER")
AND = sql_keyword("AND")
ANY = sql_keyword("ANY")
AS = sql_keyword("AS")
ASC = sql_keyword("ASC")
BETWEEN = sql_keyword("BETWEEN")
BINARY = sql_keyword("BINARY")
BOOLEAN = sql_keyword("BOOLEAN")
BY = sql_keyword("BY")
CASE = sql_keyword("CASE")
CASCADE = sql_keyword("CASCADE")
COLLATE = sql_keyword("COLLATE")
CREATE = sql_keyword("CREATE")
CROSS = sql_keyword("CROSS")
DATE = sql_keyword("DATE")
DATETIME = sql_keyword("DATETIME")
DELETE = sql_keyword("DELETE")
DEFAULT = sql_keyword("DEFAULT")
DESC = sql_keyword("DESC")
DISTINCT = sql_keyword("DISTINCT")
DISTINCTROW = sql_keyword("DISTINCTROW")
DIV = sql_keyword("DIV")
DROP = sql_keyword("DROP")
ELSE = sql_keyword("ELSE")
END = sql_keyword("END")
ESCAPE = sql_keyword("ESCAPE")
EXISTS = sql_keyword("EXISTS")
EXPANSION = sql_keyword("EXPANSION")
FALSE = sql_keyword("FALSE")
FIRST = sql_keyword("FIRST")
FOR = sql_keyword("FOR")
FORCE = sql_keyword("FORCE")
FROM = sql_keyword("FROM")
GROUP = sql_keyword("GROUP")
HAVING = sql_keyword("HAVING")
HIGH_PRIORITY = sql_keyword("HIGH_PRIORITY")
IGNORE = sql_keyword("IGNORE")
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
LIMIT = sql_keyword("LIMIT")
MATCH = sql_keyword("MATCH")
MAX_STATEMENT_TIME = sql_keyword("MAX_STATEMENT_TIME")
MOD = sql_keyword("MOD")
MODE = sql_keyword("MODE")
NATURAL = sql_keyword("NATURAL")
NOT = sql_keyword("NOT")
NULL = sql_keyword("NULL")
NULLS = sql_keyword("NULLS")
OFFSET = sql_keyword("OFFSET")
OJ = sql_keyword("OJ")
ON = sql_keyword("ON")
ONLY = sql_keyword("ONLY")
OR = sql_keyword("OR")
ORDER = sql_keyword("ORDER")
OUTER = sql_keyword("OUTER")
PARTITION = sql_keyword("PARTITION")
PROCEDURE = sql_keyword("PROCEDURE")
QUERY = sql_keyword("QUERY")
REGEXP = sql_keyword("REGEXP")
RESTRICT = sql_keyword("RESTRICT")
RIGHT = sql_keyword("RIGHT")
ROLLUP = sql_keyword("ROLLUP")
ROW = sql_keyword("ROW")
SELECT = sql_keyword("SELECT")
SET = sql_keyword("SET")
SOUNDS = sql_keyword("SOUNDS")
SQL_BIG_RESULT = sql_keyword("SQL_BIG_RESULT")
SQL_BUFFER_RESULT = sql_keyword("SQL_BUFFER_RESULT")
SQL_CACHE = sql_keyword("SQL_CACHE")
SQL_CALC_FOUND_ROWS = sql_keyword("SQL_CALC_FOUND_ROWS")
SQL_NO_CACHE = sql_keyword("SQL_NO_CACHE")
SQL_SMALL_RESULT = sql_keyword("SQL_SMALL_RESULT")
STRAIGHT_JOIN = sql_keyword("STRAIGHT_JOIN")
TABLE = sql_keyword("TABLE")
TABLESPACE = sql_keyword("TABLESPACE")
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
WITH = sql_keyword("WITH")
WHEN = sql_keyword("WHEN")
WHERE = sql_keyword("WHERE")
XOR = sql_keyword("XOR")


all_keywords = """
    AGAINST ALL ALTER AND ASC AS
    BETWEEN BINARY BOOLEAN BY
    CASE CASCADE COLLATE CREATE CROSS
    DATETIME DATE DELETE DESC DISTINCTROW DISTINCT DIV DROP
    ELSE END ESCAPE EXISTS EXPANSION
    FALSE FIRST FORCE FOR FROM
    GROUP
    HAVING HIGH_PRIORITY
    IGNORE INDEX INNER INSERT INTERVAL INTO IN IS
    JOIN
    KEY
    LANGUAGE LAST LEFT LIKE LIMIT
    MATCH MAX_STATEMENT_TIME MODE MOD
    NATURAL NOT NULLS NULL
    OFFSET OJ ONLY ON ORDER OR OUTER
    PARTITION PROCEDURE
    QUERY
    REGEXP RESTRICT RIGHT ROLLUP ROW
    SELECT SET SOUNDS SQL_BIG_RESULT SQL_BUFFER_RESULT
        SQL_CACHE SQL_CALC_FOUND_ROWS SQL_NO_CACHE SQL_SMALL_RESULT
        STRAIGHT_JOIN
    TABLESPACE TABLE THEN TIMESTAMP TIME TRUE
    UNION UPDATE USE USING UNKNOWN
    VALUES
    WITH WHEN WHERE
    XOR
"""
keyword = make_words_regex(all_keywords, caseless=True, name="keyword")

COMMA = Literal(",")
LPAR = Literal("(")
RPAR = Literal(")")


# -----------------------------------------------------------------------------
# Literals
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Forward declarations
# -----------------------------------------------------------------------------

expr = Forward()
select_statement = Forward()

# -----------------------------------------------------------------------------
# identifier
# -----------------------------------------------------------------------------
# http://dev.mysql.com/doc/refman/5.7/en/identifiers.html
bare_identifier_word = make_regex_except_words(
    r"\b[a-zA-Z0-9$_]*\b",
    all_keywords,
    caseless=True,
    name="bare_identifier_word"
)
identifier = (
    bare_identifier_word |
    QuotedString(quoteChar="`", unquoteResults=False)
).setName("identifier")
# http://dev.mysql.com/doc/refman/5.7/en/charset-collate.html
collation_name = identifier.copy()
column_name = identifier.copy()
column_alias = identifier.copy()
table_name = identifier.copy()
table_alias = identifier.copy()
index_name = identifier.copy()
function_name = identifier.copy()
parameter_name = identifier.copy()
database_name = identifier.copy()
partition_name = identifier.copy()

no_dot = NotAny('.')
table_spec = (
    Combine(database_name + '.' + table_name + no_dot) |
    table_name + no_dot
).setName("table_spec")
column_spec = (
    Combine(database_name + '.' + table_name + '.' + column_name + no_dot) |
    Combine(table_name + '.' + column_name + no_dot) |
    column_name + no_dot
).setName("column_spec")

# http://dev.mysql.com/doc/refman/5.7/en/expressions.html
bind_parameter = Literal('?')

# http://dev.mysql.com/doc/refman/5.7/en/user-variables.html
variable = Regex(r"@[a-zA-Z0-9\.$_]+").setName("variable")

# http://dev.mysql.com/doc/refman/5.7/en/functions.html
argument_list = (
    delimitedList(expr).setName("arglist").setParseAction(', '.join)
)
# ... we don't care about sub-parsing the argument list, so use combine=True
# or setParseAction: http://stackoverflow.com/questions/37926516
function_call = Combine(function_name + LPAR) + argument_list + RPAR

# http://dev.mysql.com/doc/refman/5.7/en/partitioning-selection.html
partition_list = (
    LPAR + delim_list(partition_name, combine=True) + RPAR
).setName("partition_list")

# http://dev.mysql.com/doc/refman/5.7/en/index-hints.html
index_list = delim_list(index_name, combine=False)
# ... see pyparsing_bugtest_delimited_list_combine
index_hint = (
    (
        USE + (INDEX | KEY) +
        Optional(FOR + (JOIN | (ORDER + BY) | (GROUP + BY))) +
        LPAR + Optional(index_list) + RPAR
    ) |
    (
        IGNORE + (INDEX | KEY) +
        Optional(FOR + (JOIN | (ORDER + BY) | (GROUP + BY))) +
        LPAR + index_list + RPAR
    ) |
    (
        FORCE + (INDEX | KEY) +
        Optional(FOR + (JOIN | (ORDER + BY) | (GROUP + BY))) +
        LPAR + index_list + RPAR
    )
)
index_hint_list = delim_list(index_hint, combine=True).setName(
    "index_hint_list")

# -----------------------------------------------------------------------------
# CASE
# -----------------------------------------------------------------------------
# NOT THIS: https://dev.mysql.com/doc/refman/5.7/en/case.html
# THIS: https://dev.mysql.com/doc/refman/5.7/en/control-flow-functions.html#operator_case  # noqa
case_expr = (
    (
        CASE + expr +
        OneOrMore(WHEN + expr + THEN + expr) +
        Optional(ELSE + expr) +
        END
    ) | (
        CASE +
        OneOrMore(WHEN + expr + THEN + expr) +
        Optional(ELSE + expr) +
        END
    )
).setName("case_expr")

# -----------------------------------------------------------------------------
# MATCH
# -----------------------------------------------------------------------------
# https://dev.mysql.com/doc/refman/5.7/en/fulltext-search.html#function_match
search_modifier = (
    (IN + NATURAL + LANGUAGE + MODE + Optional(WITH + QUERY + EXPANSION)) |
    (IN + BOOLEAN + MODE) |
    (WITH + QUERY + EXPANSION)
)
match_expr = (
    MATCH + LPAR + delim_list(column_spec) + RPAR +
    AGAINST + LPAR + expr + Optional(search_modifier) + RPAR
).setName("match_expr")

# -----------------------------------------------------------------------------
# Expressions
# -----------------------------------------------------------------------------
# http://dev.mysql.com/doc/refman/5.7/en/expressions.html
# https://pyparsing.wikispaces.com/file/view/select_parser.py
# http://dev.mysql.com/doc/refman/5.7/en/operator-precedence.html
expr_term = (
    INTERVAL + expr + time_unit |
    # "{" + identifier + expr + "}" |  # see MySQL notes; antique ODBC syntax
    Optional(EXISTS) + LPAR + select_statement + RPAR |
    # ... e.g. mycol = EXISTS(SELECT ...)
    # ... e.g. mycol IN (SELECT ...)
    LPAR + delim_list(expr) + RPAR |
    # ... e.g. mycol IN (1, 2, 3)
    case_expr |
    match_expr |
    bind_parameter |
    variable |
    function_call |
    literal_value |
    column_spec  # not just identifier
)
UNARY_OP, BINARY_OP, TERNARY_OP = 1, 2, 3
expr << infixNotation(expr_term, [
    # Having lots of operations in the list here SLOWS IT DOWN A LOT.
    # Just combine them into an ordered list.
    (BINARY | COLLATE | oneOf('! - + ~'), UNARY_OP, opAssoc.RIGHT),
    (
        oneOf('^ * / %') | DIV | MOD |
        oneOf('+ - << >> & | = <=> >= > <= < <> !=') |
        (IS + Optional(NOT)) | LIKE | REGEXP | (Optional(NOT) + IN) |
        (SOUNDS + LIKE),  # RNC; presumably at same level as LIKE
        BINARY_OP,
        opAssoc.LEFT
    ),
    ((BETWEEN, AND), TERNARY_OP, opAssoc.LEFT),
    # CASE handled above (hoping precedence is not too much of a problem)
    (NOT, UNARY_OP, opAssoc.RIGHT),
    (AND | '&&' | XOR | OR | '||' | ':=', BINARY_OP, opAssoc.LEFT),
], lpar=LPAR, rpar=RPAR)
# ignores LIKE [ESCAPE]

# -----------------------------------------------------------------------------
# SELECT
# -----------------------------------------------------------------------------
# http://dev.mysql.com/doc/refman/5.7/en/select.html
"""
SELECT
    [ALL | DISTINCT | DISTINCTROW ]
      [HIGH_PRIORITY]
      [MAX_STATEMENT_TIME = N]
      [STRAIGHT_JOIN]
      [SQL_SMALL_RESULT] [SQL_BIG_RESULT] [SQL_BUFFER_RESULT]
      [SQL_CACHE | SQL_NO_CACHE] [SQL_CALC_FOUND_ROWS]
    select_expr [, select_expr ...]
    [FROM table_references
      [PARTITION partition_list]
    [WHERE where_condition]
    [GROUP BY {col_name | expr | position}
      [ASC | DESC], ... [WITH ROLLUP]]
    [HAVING where_condition]
    [ORDER BY {col_name | expr | position}
      [ASC | DESC], ...]
    [LIMIT {[offset,] row_count | row_count OFFSET offset}]

... ignore below here...

    [PROCEDURE procedure_name(argument_list)]
    [INTO OUTFILE 'file_name'
        [CHARACTER SET charset_name]
        export_options
      | INTO DUMPFILE 'file_name'
      | INTO var_name [, var_name]]
    [FOR UPDATE | LOCK IN SHARE MODE]]
"""

compound_operator = UNION + Optional(ALL | DISTINCT)
# no INTERSECT or EXCEPT in MySQL?

ordering_term = (
    expr + Optional(COLLATE + collation_name) + Optional(ASC | DESC)
)
# ... COLLATE can appear in lots of places;
# http://dev.mysql.com/doc/refman/5.7/en/charset-collate.html

join_constraint = Optional(Group(  # join_condition in MySQL grammar
    (ON + expr) |
    (USING + LPAR + delim_list(column_name) + RPAR)
))

# http://dev.mysql.com/doc/refman/5.7/en/join.html
join_op = Group(
    COMMA |
    STRAIGHT_JOIN |
    NATURAL + (Optional(LEFT | RIGHT) + Optional(OUTER)) + JOIN |
    (INNER | CROSS) + JOIN |
    Optional(LEFT | RIGHT) + Optional(OUTER) + JOIN
    # ignores antique ODBC "{ OJ ... }" syntax
)

join_source = Forward()
single_source = (
    (
        table_spec.copy().setResultsName("from_tables", listAllMatches=True) +
        Optional(PARTITION + partition_list) +
        Optional(Optional(AS) + table_alias) +
        Optional(index_hint_list)
    ) |
    (select_statement + Optional(AS) + table_alias) +
    (LPAR + join_source + RPAR)
)
join_source << Group(
    single_source + ZeroOrMore(join_op + single_source + join_constraint)
)("join_source")
# ... must have a Group to append to it later, it seems
# ... but name it "join_source" here, or it gets enclosed in a further list
#     when you name it later

result_column = (
    '*' |
    Combine(table_name + '.' + '*') |
    column_spec |
    expr + Optional(Optional(AS) + column_alias)
).setResultsName("select_columns", listAllMatches=True)

select_core = (
    SELECT +
    Group(Optional(ALL | DISTINCT | DISTINCTROW))("select_specifier") +
    Optional(HIGH_PRIORITY) +
    Optional(MAX_STATEMENT_TIME + '=' + integer) +
    Optional(STRAIGHT_JOIN) +
    Optional(SQL_SMALL_RESULT) +
    Optional(SQL_BIG_RESULT) +
    Optional(SQL_BUFFER_RESULT) +
    Optional(SQL_CACHE | SQL_NO_CACHE) +
    Optional(SQL_CALC_FOUND_ROWS) +
    Group(delim_list(result_column))("select_expression") +
    Optional(
        FROM + join_source +
        Optional(PARTITION + partition_list) +
        Group(Optional(WHERE + Group(expr)("where_expr")))("where_clause") +
        Optional(
            GROUP + BY +
            delim_list(ordering_term +
                       Optional(ASC | DESC))("group_by_term") +
            Optional(WITH + ROLLUP)
        ) +
        Optional(HAVING + expr("having_expr"))
    )
)

select_statement << (
    select_core +
    ZeroOrMore(compound_operator + select_core) +
    Optional(
        ORDER + BY +
        delim_list(ordering_term +
                   Optional(ASC | DESC))("order_by_terms")
    ) +
    Optional(LIMIT + (
        (Optional(integer("offset") + COMMA) + integer("row_count")) |
        (integer("row_count") + OFFSET + integer("offset")))
    )
    # PROCEDURE ignored
    # rest ignored
)

# -----------------------------------------------------------------------------
# Comments
# -----------------------------------------------------------------------------
# http://dev.mysql.com/doc/refman/5.7/en/comments.html
ansi_comment = Literal("--") + restOfLine
bash_comment = Literal("#") + restOfLine
comment = (ansi_comment | bash_comment | cStyleComment)

# -----------------------------------------------------------------------------
# Grammar (here, just SELECT)
# -----------------------------------------------------------------------------
select_statement.ignore(comment)
sql_grammar = select_statement


# =============================================================================
# sqlparse tests
# =============================================================================

# def parsed_from_text(sql):
#     statements = sqlparse.parse(sql)
#     if not statements:
#         return None
#     first_statement = statements[0]
#     return first_statement


# def formatted_from_parsed(statement):
#     sql = str(statement)
#     return sqlparse.format(sql, reindent=True)


# =============================================================================
# pyparsing test
# =============================================================================

# See also: parser.runTests()

def standardize_whitespace(text):
    return " ".join(text.split())


def test_succeed(parser, text, target=None, skip_target=True, show_raw=False,
                 verbose=True):
    if target is None:
        target = text
    try:
        p = parser.parseString(text)
        log.debug("Success: {} -> {}".format(text, text_from_parsed(p)))
        if show_raw:
            log.debug("... raw: {}".format(p))
        if verbose:
            log.debug("... dump:\n{}".format(p.dump()))
    except ParseException as exception:
        log.debug("Failure on: {} [parser: {}]".format(text, parser))
        print(statement_and_failure_marker(text, exception))
        raise
    if not skip_target:
        intended = standardize_whitespace(target)
        actual = standardize_whitespace(text_from_parsed(p))
        if intended != actual:
            raise ValueError(
                "Failure on: {} -> {} (should have been: {})"
                " [parser: {}] [as list: {}]".format(
                    text, actual, intended, parser, repr(p.asList())))


def test_fail(parser, text):
    try:
        p = parser.parseString(text)
        raise ValueError(
            "Succeeded erroneously: {} -> {} [raw: {}] [parser: {}]".format(
                text, text_from_parsed(p), p, parser))
    except ParseException:
        log.debug("Correctly failed: {}".format(text))


def test_select(text):
    test_succeed(select_statement, text, verbose=True)


def test(parser, text):
    print("STATEMENT:\n{}".format(text))

    # scanned = parser.scanString(text)
    # for tokens, start, end in scanned:
    #     print(start, end, tokens)

    try:
        tokens = parser.parseString(text)
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
        print(" "*err.loc + "^\n" + err.msg)
        print(err)
    print()


def flatten(*args):
    for x in args:
        if isinstance(x, (list, tuple)):
            for y in flatten(*x):
                yield y
        else:
            yield x


def text_from_parsed(parsetree, formatted=True, indent_width=4):
    nested_list = parsetree.asList()
    flattened_list = flatten(nested_list)
    plain_str = " ".join(flattened_list)
    if not formatted:
        return plain_str

    # Forget my feeble efforts for now (below) and use sqlparse:
    return sqlparse.format(plain_str, reindent=True,
                           indent_width=indent_width)

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


def statement_and_failure_marker(text, parse_exception):
    output_lines = []
    for line_index, line in enumerate(text.split("\n")):
        output_lines.append(line)
        if parse_exception.lineno == line_index + 1:
            output_lines.append("-" * (parse_exception.col - 1) + "^")
    return "\n".join(output_lines)


# =============================================================================
# Tests
# =============================================================================

# noinspection PyUnboundLocalVariable
def pyparsing_bugtest_delimited_list_combine(fix_problem=True):
    if fix_problem:
        # noinspection PyPep8Naming,PyShadowingNames
        delimitedList = delim_list
    word = Word(alphanums)
    word_list_no_combine = delimitedList(word, combine=False)
    word_list_combine = delimitedList(word, combine=True)
    print(word_list_no_combine.parseString('one, two'))  # ['one', 'two']
    print(word_list_no_combine.parseString('one,two'))  # ['one', 'two']
    print(word_list_combine.parseString('one, two'))  # ['one']: ODD ONE OUT
    print(word_list_combine.parseString('one,two'))  # ['one,two']


def unit_tests(test_expr=False):
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

    log.info("Testing time_unit")
    test_succeed(time_unit, "MICROSECOND")
    test_succeed(time_unit, "year_month")

    # -------------------------------------------------------------------------
    # Identifiers
    # -------------------------------------------------------------------------

    log.info("Testing FOR")
    print(FOR.pattern)
    test_succeed(FOR, "for")
    test_fail(FOR, "thingfor")  # shouldn't match FOR
    test_fail(FOR, "forename")  # shouldn't match FOR

    log.info("Testing keyword")
    print(keyword.pattern)
    test_succeed(keyword, "TABLE")
    test_fail(keyword, "thingfor")  # shouldn't match FOR
    test_fail(keyword, "forename")  # shouldn't match FOR

    log.info("Testing bare_identifier_word")
    test_succeed(bare_identifier_word, "blah")
    test_fail(bare_identifier_word, "FROM")
    test_succeed(bare_identifier_word, "forename")

    log.info("Testing identifier")
    test_succeed(identifier, "blah")
    test_succeed(identifier, "idx1")
    test_succeed(identifier, "idx2")
    test_succeed(identifier, "a")
    test_succeed(identifier, "`FROM`")
    test_succeed(identifier, "`SELECT FROM`")
    log.info("... done")

    log.info("Testing table_spec")
    test_succeed(table_spec, "mytable")
    test_succeed(table_spec, "mydb.mytable")
    test_succeed(table_spec, "mydb.`my silly table`")
    test_fail(table_spec, "mydb . mytable")
    test_fail(table_spec, "mydb.mytable.mycol")

    log.info("Testing column_spec")
    test_succeed(column_spec, "mycol")
    test_succeed(column_spec, "forename")
    test_succeed(column_spec, "mytable.mycol")
    test_succeed(column_spec, "t1.a")
    test_succeed(column_spec, "`my silly table`.`my silly column`")
    test_succeed(column_spec, "mydb.mytable.mycol")
    test_fail(column_spec, "mydb . mytable . mycol")

    log.info("Testing variable")
    test_succeed(variable, "@myvar")

    log.info("Testing argument_list")
    test_succeed(argument_list, "@myvar, 5")

    log.info("Testing function_call")
    test_succeed(function_call, "myfunc(@myvar, 5)")

    log.info("Testing index_list")
    test_succeed(index_list, "idx1, idx2")

    log.info("Testing index_hint")
    test_succeed(index_hint, "USE INDEX FOR JOIN (idx1, idx2)")

    # -------------------------------------------------------------------------
    # Expressions
    # -------------------------------------------------------------------------

    log.info("Testing case_expr")
    test_succeed(case_expr, """
        CASE v
          WHEN 2 THEN x
          WHEN 3 THEN y
          ELSE -99
        END
    """)

    log.info("Testing match_expr")
    test_succeed(match_expr, """
         MATCH (content_field)
         AGAINST('+keyword1 +keyword2' IN BOOLEAN MODE)
    """)

    log.info("Testing expr_term")
    test_succeed(expr_term, "5")
    test_succeed(expr_term, "5.12")
    test_succeed(expr_term, "'string'")
    test_succeed(expr_term, "mycol")
    test_succeed(expr_term, "myfunc(myvar, 8)")
    test_succeed(expr_term, "INTERVAL 5 MICROSECOND")
    test_succeed(expr_term, "(SELECT 1)")
    test_succeed(expr_term, "(1, 2, 3)")

    if test_expr:
        log.info("Testing expr")
        test_succeed(expr, "5")
        test_succeed(expr, "a")
        test_succeed(expr, "mycol1 || mycol2")
        test_succeed(expr, "+mycol")
        test_succeed(expr, "-mycol")
        test_succeed(expr, "~mycol")
        test_succeed(expr, "!mycol")
        test_succeed(expr, "a | b")
        test_succeed(expr, "a & b")
        test_succeed(expr, "a << b")
        test_succeed(expr, "a >> b")
        test_succeed(expr, "a + b")
        test_succeed(expr, "a - b")
        test_succeed(expr, "a * b")
        test_succeed(expr, "a / b")
        test_succeed(expr, "a DIV b")
        test_succeed(expr, "a MOD b")
        test_succeed(expr, "a % b")
        test_succeed(expr, "a ^ b")
        test_succeed(expr, "a ^ (b + (c - d) / e)")
        test_succeed(expr, "a NOT IN (SELECT 1)")
        test_succeed(expr, "a IN (1, 2, 3)")
        test_succeed(expr, "a IS NULL")
        test_succeed(expr, "a IS NOT NULL")
        test_fail(expr, "IS NULL")
        test_fail(expr, "IS NOT NULL")
        test_succeed(expr, "(a * (b - 3)) > (d - 2)")

    log.info("Testing join_op")
    test_succeed(join_op, ",")
    test_succeed(join_op, "INNER JOIN")

    log.info("Testing join_source")
    test_succeed(join_source, "a")
    test_succeed(join_source, "a INNER JOIN b")
    test_succeed(join_source, "a, b")

    log.info("Testing result_column")
    test_succeed(result_column, "t1.a")

    log.info("Testing select_statement")
    test_select("SELECT a, b FROM c")  # no WHERE
    test_select("SELECT a, b FROM c WHERE d > 5 AND e = 4")
    test_select("SELECT a, b FROM c INNER JOIN f WHERE d > 5 AND e = 4")
    test_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5")
    test_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 IN (1, 2, 3)")


# =============================================================================
# main
# =============================================================================

def main():
    # blank = ''
    # p_blank = parsed_from_text(blank)
    # p_sql1 = parsed_from_text(sql1)
    # print(formatted_from_parsed(p_blank))
    # print(formatted_from_parsed(p_sql1))

    # pyparsing_bugtest_delimited_list_combine()
    unit_tests(test_expr=True)


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    main()
