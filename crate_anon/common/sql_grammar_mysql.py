#!/usr/bin/env python
# crate_anon/crateweb/research/sql_grammar_mysql.py

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
"""

import logging
import re

from pyparsing import (
    Combine,
    cStyleComment,
    delimitedList,
    Forward,
    Group,
    infixNotation,
    Literal,
    NotAny,
    oneOf,
    OneOrMore,
    opAssoc,
    Optional,
    QuotedString,
    Regex,
    ZeroOrMore,
)

from crate_anon.common.logsupport import main_only_quicksetup_rootlogger
from crate_anon.common.sql_grammar import (
    ALL,
    AND,
    ansi_comment,
    ANSI92_RESERVED_WORD_LIST,
    AS,
    ASC,
    AVG,
    bash_comment,
    BETWEEN,
    BY,
    CASE,
    COLLATE,
    COMMA,
    CROSS,
    COUNT,
    delim_list,
    DESC,
    DISTINCT,
    ELSE,
    END,
    EXISTS,
    FOR,
    FROM,
    GROUP,
    HAVING,
    IN,
    INDEX,
    INNER,
    integer,
    INTERVAL,
    IS,
    JOIN,
    KEY,
    LANGUAGE,
    LEFT,
    LIKE,
    literal_value,
    LPAR,
    make_pyparsing_regex,
    make_regex_except_words,
    make_words_regex,
    MATCH,
    MAX,
    MIN,
    NATURAL,
    NOT,
    ON,
    OR,
    ORDER,
    OUTER,
    RIGHT,
    RPAR,
    SELECT,
    string_literal,
    SUM,
    sql_keyword,
    SqlGrammar,
    test_fail,
    test_succeed,
    THEN,
    time_unit,
    UNION,
    USE,
    USING,
    WHEN,
    WHERE,
    WITH,
)

log = logging.getLogger(__name__)

AGAINST = sql_keyword("AGAINST")
BIT_AND = sql_keyword("BIT_AND")
BIT_OR = sql_keyword("BIT_OR")
BIT_XOR = sql_keyword("BIT_XOR")
BOOLEAN = sql_keyword("BOOLEAN")
EXPANSION = sql_keyword("EXPANSION")
GROUP_CONCAT = sql_keyword("GROUP_CONCAT")
MODE = sql_keyword("MODE")
NULLS = sql_keyword("NULLS")
QUERY = sql_keyword("QUERY")
ROW = sql_keyword("ROW")
TABLESPACE = sql_keyword("TABLESPACE")
BINARY = sql_keyword("BINARY")
DISTINCTROW = sql_keyword("DISTINCTROW")
DIV = sql_keyword("DIV")
FORCE = sql_keyword("FORCE")
HIGH_PRIORITY = sql_keyword("HIGH_PRIORITY")
IGNORE = sql_keyword("IGNORE")
LIMIT = sql_keyword("LIMIT")
MAX_STATEMENT_TIME = sql_keyword("MAX_STATEMENT_TIME")
MOD = sql_keyword("MOD")
OFFSET = sql_keyword("OFFSET")
OJ = sql_keyword("OJ")
PARTITION = sql_keyword("PARTITION")
PROCEDURE = sql_keyword("PROCEDURE")
REGEXP = sql_keyword("REGEXP")
ROLLUP = sql_keyword("ROLLUP")
SOUNDS = sql_keyword("SOUNDS")
STD = sql_keyword("STD")
STDDEV = sql_keyword("STDDEV")
STDDEV_POP = sql_keyword("STDDEV_POP")
STDDEV_SAMP = sql_keyword("STDDEV_SAMP")
SQL_BIG_RESULT = sql_keyword("SQL_BIG_RESULT")
SQL_BUFFER_RESULT = sql_keyword("SQL_BUFFER_RESULT")
SQL_CACHE = sql_keyword("SQL_CACHE")
SQL_CALC_FOUND_ROWS = sql_keyword("SQL_CALC_FOUND_ROWS")
SQL_NO_CACHE = sql_keyword("SQL_NO_CACHE")
SQL_SMALL_RESULT = sql_keyword("SQL_SMALL_RESULT")
STRAIGHT_JOIN = sql_keyword("STRAIGHT_JOIN")
VAR_POP = sql_keyword("VAR_POP")
VAR_SAMP = sql_keyword("VAR_SAMP")
VARIANCE = sql_keyword("VARIANCE")
XOR = sql_keyword("XOR")


# =============================================================================
# MySQL 5.7 grammar in pyparsing
# =============================================================================
# http://dev.mysql.com/doc/refman/5.7/en/dynindex-statement.html

class SqlGrammarMySQL(SqlGrammar):
    # -------------------------------------------------------------------------
    # Forward declarations
    # -------------------------------------------------------------------------
    expr = Forward()
    select_statement = Forward()

    # -------------------------------------------------------------------------
    # Keywords
    # -------------------------------------------------------------------------
    # https://dev.mysql.com/doc/refman/5.7/en/keywords.html
    mysql_reserved_words = """
ACCESSIBLE ADD ALL ALTER ANALYZE AND AS ASC ASENSITIVE
BEFORE BETWEEN BIGINT BINARY BLOB BOTH BY
CALL CASCADE CASE CHANGE CHAR CHARACTER CHECK COLLATE COLUMN CONDITION
    CONSTRAINT CONTINUE CONVERT CREATE CROSS CURRENT_DATE CURRENT_TIME
    CURRENT_TIMESTAMP CURRENT_USER CURSOR
DATABASE DATABASES DAY_HOUR DAY_MICROSECOND DAY_MINUTE DAY_SECOND DEC DECIMAL
    DECLARE DEFAULT DELAYED DELETE DESC DESCRIBE DETERMINISTIC DISTINCT
    DISTINCTROW DIV DOUBLE DROP DUAL
EACH ELSE ELSEIF ENCLOSED ESCAPED EXISTS EXIT EXPLAIN
FALSE FETCH FLOAT FLOAT4 FLOAT8 FOR FORCE FOREIGN FROM FULLTEXT
GENERATED GET GRANT GROUP
HAVING HIGH_PRIORITY HOUR_MICROSECOND HOUR_MINUTE HOUR_SECOND
IF IGNORE IN INDEX INFILE INNER INOUT INSENSITIVE INSERT INT INT1 INT2 INT3
    INT4 INT8 INTEGER INTERVAL INTO IO_AFTER_GTIDS IO_BEFORE_GTIDS IS
    ITERATE
JOIN
KEY KEYS KILL
LEADING LEAVE LEFT LIKE LIMIT LINEAR LINES LOAD LOCALTIME LOCALTIMESTAMP
    LOCK LONG LONGBLOB LONGTEXT LOOP LOW_PRIORITY
MASTER_BIND MASTER_SSL_VERIFY_SERVER_CERT MATCH MAXVALUE MEDIUMBLOB
    MEDIUMINT MEDIUMTEXT MIDDLEINT MINUTE_MICROSECOND MINUTE_SECOND MOD
    MODIFIES
NATURAL NOT NO_WRITE_TO_BINLOG NULL NUMERIC
ON OPTIMIZE OPTIMIZER_COSTS OPTION OPTIONALLY OR ORDER OUT OUTER OUTFILE
PARTITION PRECISION PRIMARY PROCEDURE PURGE
RANGE READ READS READ_WRITE REAL REFERENCES REGEXP RELEASE RENAME REPEAT
    REPLACE REQUIRE RESIGNAL RESTRICT RETURN REVOKE RIGHT RLIKE
SCHEMA SCHEMAS SECOND_MICROSECOND SELECT SENSITIVE SEPARATOR SET SHOW SIGNAL
    SMALLINT SPATIAL SPECIFIC SQL SQLEXCEPTION SQLSTATE SQLWARNING
    SQL_BIG_RESULT SQL_CALC_FOUND_ROWS SQL_SMALL_RESULT SSL STARTING STORED
    STRAIGHT_JOIN
TABLE TERMINATED THEN TINYBLOB TINYINT TINYTEXT TO TRAILING TRIGGER TRUE
UNDO UNION UNIQUE UNLOCK UNSIGNED UPDATE USAGE USE USING UTC_DATE UTC_TIME
    UTC_TIMESTAMP
VALUES VARBINARY VARCHAR VARCHARACTER VARYING VIRTUAL
WHEN WHERE WHILE WITH WRITE
XOR
YEAR_MONTH
ZEROFILL
    """
    mysql_nonreserved_keywords = """
ACCOUNT ACTION AFTER AGAINST AGGREGATE ALGORITHM ALWAYS ANALYSE ANY ASCII AT
    AUTOEXTEND_SIZE AUTO_INCREMENT AVG AVG_ROW_LENGTH
BACKUP BEGIN BINLOG BIT BLOCK BOOL BOOLEAN BTREE BYTE
CACHE CASCADED CATALOG_NAME CHAIN CHANGED CHANNEL CHARSET CHECKSUM CIPHER
    CLASS_ORIGIN CLIENT CLOSE COALESCE CODE COLLATION COLUMNS COLUMN_FORMAT
    COLUMN_NAME COMMENT COMMIT COMMITTED COMPACT COMPLETION COMPRESSED
    COMPRESSION CONCURRENT CONNECTION CONSISTENT CONSTRAINT_CATALOG
    CONSTRAINT_NAME CONSTRAINT_SCHEMA CONTAINS CONTEXT CPU CUBE CURRENT
    CURSOR_NAME
DATA DATAFILE DATE DATETIME DAY DEALLOCATE DEFAULT_AUTH DEFINER DELAY_KEY_WRITE
    DES_KEY_FILE DIAGNOSTICS DIRECTORY DISABLE DISCARD DISK DO DUMPFILE
    DUPLICATE DYNAMIC
ENABLE ENCRYPTION END ENDS ENGINE ENGINES ENUM ERROR ERRORS ESCAPE EVENT EVENTS
    EVERY EXCHANGE EXECUTE EXPANSION EXPIRE EXPORT EXTENDED EXTENT_SIZE
FAST FAULTS FIELDS FILE FILE_BLOCK_SIZE FILTER FIRST FIXED FLUSH FOLLOWS FORMAT
    FOUND FULL FUNCTION
GENERAL GEOMETRY GEOMETRYCOLLECTION GET_FORMAT GLOBAL GRANTS GROUP_REPLICATION
HANDLER HASH HELP HOST HOSTS HOUR
IDENTIFIED IGNORE_SERVER_IDS IMPORT INDEXES INITIAL_SIZE INSERT_METHOD INSTALL
    INSTANCE INVOKER IO IO_THREAD IPC ISOLATION ISSUER
JSON
KEY_BLOCK_SIZE
LANGUAGE LAST LEAVES LESS LEVEL LINESTRING LIST LOCAL LOCKS LOGFILE LOGS
MASTER MASTER_AUTO_POSITION MASTER_CONNECT_RETRY MASTER_DELAY
    MASTER_HEARTBEAT_PERIOD MASTER_HOST MASTER_LOG_FILE MASTER_LOG_POS
    MASTER_PASSWORD MASTER_PORT MASTER_RETRY_COUNT MASTER_SERVER_ID MASTER_SSL
    MASTER_SSL_CA MASTER_SSL_CAPATH MASTER_SSL_CERT MASTER_SSL_CIPHER
    MASTER_SSL_CRL MASTER_SSL_CRLPATH MASTER_SSL_KEY MASTER_TLS_VERSION
    MASTER_USER MAX_CONNECTIONS_PER_HOUR MAX_QUERIES_PER_HOUR MAX_ROWS MAX_SIZE
    MAX_STATEMENT_TIME MAX_UPDATES_PER_HOUR MAX_USER_CONNECTIONS MEDIUM
    MEMORY MERGE MESSAGE_TEXT MICROSECOND MIGRATE MINUTE MIN_ROWS MODE MODIFY
    MONTH MULTILINESTRING MULTIPOINT MULTIPOLYGON MUTEX MYSQL_ERRNO
NAME NAMES NATIONAL NCHAR NDB NDBCLUSTER NEVER NEW NEXT NO NODEGROUP
    NONBLOCKING NONE NO_WAIT NUMBER NVARCHAR
OFFSET OLD_PASSWORD ONE ONLY OPEN OPTIONS OWNER
PACK_KEYS PAGE PARSER PARSE_GCOL_EXPR PARTIAL PARTITIONING PARTITIONS PASSWORD
    PHASE PLUGIN PLUGINS PLUGIN_DIR POINT POLYGON PORT PRECEDES PREPARE
    PRESERVE PREV PRIVILEGES PROCESSLIST PROFILE PROFILES PROXY
QUARTER QUERY QUICK
READ_ONLY REBUILD RECOVER REDOFILE REDO_BUFFER_SIZE REDUNDANT RELAY RELAYLOG
    RELAY_LOG_FILE RELAY_LOG_POS RELAY_THREAD RELOAD REMOVE REORGANIZE REPAIR
    REPEATABLE REPLICATE_DO_DB REPLICATE_DO_TABLE REPLICATE_IGNORE_DB
    REPLICATE_IGNORE_TABLE REPLICATE_REWRITE_DB REPLICATE_WILD_DO_TABLE
    REPLICATE_WILD_IGNORE_TABLE REPLICATION RESET RESTORE RESUME
    RETURNED_SQLSTATE RETURNS REVERSE ROLLBACK ROLLUP ROTATE ROUTINE ROW ROWS
    ROW_COUNT ROW_FORMAT RTREE
SAVEPOINT SCHEDULE SCHEMA_NAME SECOND SECURITY SERIAL SERIALIZABLE SERVER
    SESSION SHARE SHUTDOWN SIGNED SIMPLE SLAVE SLOW SNAPSHOT SOCKET SOME SONAME
    SOUNDS SOURCE SQL_AFTER_GTIDS SQL_AFTER_MTS_GAPS SQL_BEFORE_GTIDS
    SQL_BUFFER_RESULT SQL_CACHE SQL_NO_CACHE SQL_THREAD SQL_TSI_DAY
    SQL_TSI_HOUR SQL_TSI_MINUTE SQL_TSI_MONTH SQL_TSI_QUARTER SQL_TSI_SECOND
    SQL_TSI_WEEK SQL_TSI_YEAR STACKED START STARTS STATS_AUTO_RECALC
    STATS_PERSISTENT STATS_SAMPLE_PAGES STATUS STOP STORAGE STRING
    SUBCLASS_ORIGIN SUBJECT SUBPARTITION SUBPARTITIONS SUPER SUSPEND SWAPS
    SWITCHES
TABLES TABLESPACE TABLE_CHECKSUM TABLE_NAME TEMPORARY TEMPTABLE TEXT THAN TIME
    TIMESTAMP TIMESTAMPADD TIMESTAMPDIFF TRANSACTION TRIGGERS TRUNCATE TYPE
    TYPES
UNCOMMITTED UNDEFINED UNDOFILE UNDO_BUFFER_SIZE UNICODE UNINSTALL UNKNOWN UNTIL
    UPGRADE USER USER_RESOURCES USE_FRM
VALIDATION VALUE VARIABLES VIEW WAIT
WARNINGS WEEK WEIGHT_STRING WITHOUT WORK WRAPPER
X509 XA XID XML
YEAR
    """
    mysql_keywords = " ".join(sorted(list(set(
        mysql_reserved_words.split() +
        ANSI92_RESERVED_WORD_LIST.split()
    ))))
    # log.critical(mysql_keywords)
    keyword = make_words_regex(mysql_keywords, caseless=True, name="keyword")

    # -------------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------------
    # http://dev.mysql.com/doc/refman/5.7/en/comments.html
    comment = (ansi_comment | bash_comment | cStyleComment)

    # -----------------------------------------------------------------------------
    # identifier
    # -----------------------------------------------------------------------------
    # http://dev.mysql.com/doc/refman/5.7/en/identifiers.html
    bare_identifier_word = make_regex_except_words(
        r"\b[a-zA-Z0-9$_]*\b",
        mysql_keywords,
        caseless=True,
        name="bare_identifier_word"
    )
    liberal_identifier_word = make_pyparsing_regex(
        r"\b[a-zA-Z0-9$_]*\b",
        caseless=True,
        name="liberal_identifier_word"
    )
    identifier = (
        bare_identifier_word |
        QuotedString(quoteChar="`", unquoteResults=False)
    ).setName("identifier")
    liberal_identifier = (
        liberal_identifier_word |
        QuotedString(quoteChar="`", unquoteResults=False)
    ).setName("liberal_identifier")
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
    # MySQL allows keywords in the later parts of combined identifiers;
    # therefore, for example, "count.thing.thing" is not OK, but
    # "thing.thing.count" is.
    table_spec = (
        Combine(database_name + '.' + liberal_identifier + no_dot) |
        table_name + no_dot
    ).setName("table_spec")
    column_spec = (
        Combine(database_name + '.' + liberal_identifier + '.' +
                liberal_identifier + no_dot) |
        Combine(table_name + '.' + liberal_identifier + no_dot) |
        Combine(column_name + no_dot)
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

    # -------------------------------------------------------------------------
    # MATCH
    # -------------------------------------------------------------------------
    # https://dev.mysql.com/doc/refman/5.7/en/fulltext-search.html#function_match
    search_modifier = (
        (IN + NATURAL + LANGUAGE + MODE + Optional(WITH + QUERY + EXPANSION)) |
        (IN + BOOLEAN + MODE) |
        (WITH + QUERY + EXPANSION)
    )
    match_expr = (
        MATCH + LPAR + delim_list(column_spec) + RPAR +
        AGAINST + LPAR + string_literal + Optional(search_modifier) + RPAR
    ).setName("match_expr")
    # ... don't use "expr"; MATCH AGAINST uses restricted expressions, and we
    # don't want it to think that "MATCH ... AGAINST ('+keyword' IN
    # BOOLEAN MODE)" resembles the IN in "WHERE something IN (SELECT ...)"

    # -----------------------------------------------------------------------------
    # Expressions
    # -----------------------------------------------------------------------------
    # http://dev.mysql.com/doc/refman/5.7/en/expressions.html
    # https://pyparsing.wikispaces.com/file/view/select_parser.py
    # http://dev.mysql.com/doc/refman/5.7/en/operator-precedence.html
    expr_term = (
        INTERVAL + expr + time_unit |
        # "{" + identifier + expr + "}" |  # see MySQL notes; antique ODBC syntax  # noqa
        Optional(EXISTS) + LPAR + select_statement + RPAR |
        # ... e.g. mycol = EXISTS(SELECT ...)
        # ... e.g. mycol IN (SELECT ...)
        LPAR + delim_list(expr) + RPAR |
        # ... e.g. mycol IN (1, 2, 3) -- "(1, 2, 3)" being a term here
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
        # https://pythonhosted.org/pyparsing/

        # Having lots of operations in the list here SLOWS IT DOWN A LOT.
        # Just combine them into an ordered list.
        (BINARY | COLLATE | oneOf('! - + ~'), UNARY_OP, opAssoc.RIGHT),
        (
            (
                oneOf('^ * / %') | DIV | MOD |
                oneOf('+ - << >> & | = <=> >= > <= < <> !=') |
                (IS + Optional(NOT)) | LIKE | REGEXP | (Optional(NOT) + IN) |
                (SOUNDS + LIKE)
            ),  # RNC; presumably at same level as LIKE
            BINARY_OP,
            opAssoc.LEFT
        ),
        ((BETWEEN, AND), TERNARY_OP, opAssoc.LEFT),
        # CASE handled above (hoping precedence is not too much of a problem)
        (NOT, UNARY_OP, opAssoc.RIGHT),
        (AND | '&&' | XOR | OR | '||' | ':=', BINARY_OP, opAssoc.LEFT),
    ], lpar=LPAR, rpar=RPAR)
    # ignores LIKE [ESCAPE]

    # -------------------------------------------------------------------------
    # SELECT
    # -------------------------------------------------------------------------

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
            table_spec.copy().setResultsName("from_tables",
                                             listAllMatches=True) +
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

    aggregate_function = (
        # https://dev.mysql.com/doc/refman/5.7/en/group-by-functions.html
        AVG |
        BIT_AND |
        BIT_OR |
        BIT_XOR |
        COUNT |  # also: special handling for COUNT(DISTINCT ...), see below
        GROUP_CONCAT |
        MAX |
        MIN |
        STD |
        STDDEV |
        STDDEV_POP |
        STDDEV_SAMP |
        SUM |
        VAR_POP |
        VAR_SAMP |
        VARIANCE
    )
    result_base = (
        # Aggregate functions: e.g. "MAX(" allowed, "MAX (" not allowed
        Combine(COUNT + LPAR) + '*' + RPAR |  # special aggregate function
        Combine(COUNT + LPAR) + DISTINCT + expr + RPAR |  # special aggregate function  # noqa
        Combine(aggregate_function + LPAR) + expr + RPAR |
        expr |
        '*' |
        Combine(table_name + '.' + '*') |
        column_spec |
        literal_value
    )
    result_column = (
        result_base + Optional(Optional(AS) + column_alias)
    ).setResultsName("select_columns", listAllMatches=True)

    # -------------------------------------------------------------------------
    # SELECT
    # -------------------------------------------------------------------------
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
    where_expr = Group(expr).setResultsName("where_expr")
    where_clause = Group(
        Optional(WHERE + where_expr)
    ).setResultsName("where_clause")
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
            where_clause +
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
            (integer("row_count") + OFFSET + integer("offset"))
        )) +
        # PROCEDURE ignored
        # rest ignored
        Optional(';')
    )
    select_statement.ignore(comment)

    # http://dev.mysql.com/doc/refman/5.7/en/identifiers.html
    # ... approximately (and conservatively):
    MYSQL_INVALID_FIRST_IF_UNQUOTED = re.compile(r"[^a-zA-Z_$]")
    MYSQL_INVALID_IF_UNQUOTED = re.compile(r"[^a-zA-Z0-9_$]")

    def __init__(self):
        super().__init__()

    @classmethod
    def quote_identifier(cls, identifier: str) -> str:
        return "`{}`".format(identifier)

    @classmethod
    def is_quoted(cls, identifier: str) -> bool:
        return identifier.startswith("`") and identifier.endswith("`")

    @classmethod
    def requires_quoting(cls, identifier: str) -> bool:
        assert identifier, "Empty identifier"
        if cls.MYSQL_INVALID_IF_UNQUOTED.search(identifier):
            return True
        firstchar = identifier[0]
        if cls.MYSQL_INVALID_FIRST_IF_UNQUOTED.search(firstchar):
            return True
        return False

    @classmethod
    def get_grammar(cls):
        # Grammar (here, just SELECT)
        return cls.select_statement

    @classmethod
    def get_column_spec(cls):
        return cls.column_spec

    @classmethod
    def get_result_column(cls):
        return cls.result_column

    @classmethod
    def get_join_op(cls):
        return cls.join_op

    @classmethod
    def get_table_spec(cls):
        return cls.table_spec

    @classmethod
    def get_join_constraint(cls):
        return cls.join_constraint

    @classmethod
    def get_select_statement(cls):
        return cls.select_statement

    @classmethod
    def get_expr(cls):
        return cls.expr

    @classmethod
    def get_where_clause(cls):
        return cls.where_clause

    @classmethod
    def get_where_expr(cls):
        return cls.where_expr

    @classmethod
    def test_dialect_specific_1(cls):
        log.info("Testing MySQL-specific aspects (1/2)...")
        test_fail(cls.case_expr, "one two three four")
        test_fail(cls.match_expr, "one two three four")
        test_fail(cls.bind_parameter, "one two three four")
        test_fail(cls.variable, "one two three four")
        test_fail(cls.function_call, "one two three four")
        test_fail(literal_value, "one two three four")
        # test_fail(cls.column_spec, "one two three four")  # matches "one"

    @classmethod
    def test_dialect_specific_2(cls):
        log.info("Testing MySQL-specific aspects (2/2)...")

        log.info("Testing expr")
        test_succeed(cls.expr, "a DIV b")
        test_succeed(cls.expr, "a MOD b")

        log.info("Testing quoted identifiers")
        test_succeed(cls.identifier, "`a`")
        test_succeed(cls.identifier, "`FROM`")
        test_succeed(cls.identifier, "`SELECT FROM`")
        # MySQL uses up to: schema.table.column
        test_succeed(cls.table_spec, "mydb.`my silly table`")
        test_succeed(cls.table_spec, "myschema.mytable")
        test_fail(cls.table_spec, "mydb.myschema.mytable")
        # ... but not 4:
        test_succeed(cls.column_spec, "`my silly table`.`my silly column`")
        test_succeed(cls.column_spec, "myschema.mytable.mycol")
        test_succeed(cls.column_spec, "starfeeder.mass_event.thing")
        test_succeed(cls.column_spec, "starfeeder.mass_event.at")
        test_fail(cls.column_spec, "mydb.myschema.mytable.mycol")

        log.info("Testing variable")
        test_succeed(cls.variable, "@myvar")

        log.info("Testing argument_list")
        test_succeed(cls.argument_list, "@myvar, 5")

        log.info("Testing function_call")
        test_succeed(cls.function_call, "myfunc(@myvar, 5)")

        log.info("Testing index_list")
        test_succeed(cls.index_list, "idx1, idx2")

        log.info("Testing index_hint")
        test_succeed(cls.index_hint, "USE INDEX FOR JOIN (idx1, idx2)")

        log.info("Testing case_expr")
        test_succeed(cls.case_expr, """
            CASE v
              WHEN 2 THEN x
              WHEN 3 THEN y
              ELSE -99
            END
        """)

        log.info("Testing match_expr")
        test_succeed(cls.match_expr, """
             MATCH (content_field)
             AGAINST('+keyword1 +keyword2')
        """)
        test_succeed(cls.match_expr, """
             MATCH (content_field)
             AGAINST('+keyword1 +keyword2' IN BOOLEAN MODE)
        """)


# =============================================================================
# main
# =============================================================================

def main() -> None:
    log.info("TESTING MYSQL DIALECT")
    mysql = SqlGrammarMySQL()
    mysql.test()
    log.info("ALL TESTS SUCCESSFUL")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    main()
