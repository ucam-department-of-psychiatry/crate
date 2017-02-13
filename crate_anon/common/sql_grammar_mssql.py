#!/usr/bin/env python
# crate_anon/crateweb/research/sql_grammar_mssql.py

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
    alphanums,
    Combine,
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
    Word,
)

from crate_anon.common.logsupport import main_only_quicksetup_rootlogger
from crate_anon.common.sql_grammar import (
    ALL,
    AND,
    ANSI92_RESERVED_WORD_LIST,
    ansi_comment,
    AS,
    ASC,
    AVG,
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
    FROM,
    GROUP,
    HAVING,
    IN,
    INNER,
    integer,
    INTERVAL,
    IS,
    JOIN,
    LEFT,
    LIKE,
    literal_value,
    LPAR,
    make_regex_except_words,
    make_words_regex,
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
    SUM,
    sql_keyword,
    SqlGrammar,
    test_fail,
    test_succeed,
    THEN,
    time_unit,
    UNION,
    USING,
    WHEN,
    WHERE,
    WITH,
)

log = logging.getLogger(__name__)


# Not in SQL Server (though in MySQL):
#
# don't think so: BINARY; http://gilfster.blogspot.co.uk/2005/08/case-sensitivity-in-mysql.html  # noqa
# DISTINCTROW: no; http://stackoverflow.com/questions/8562136/distinctrow-equivalent-in-sql-server  # noqa
# DIV/MOD: not in SQL Server; use / and % respectively; https://msdn.microsoft.com/en-us/library/ms190279.aspx  # noqa
# PARTITION: not in SELECT? - https://msdn.microsoft.com/en-us/library/ms187802.aspx  # noqa
# XOR: use ^ instead; http://stackoverflow.com/questions/5411619/t-sql-xor-operator  # noqa

# Definitely part of SQL Server:
CHECKSUM_AGG = sql_keyword("CHECKSUM_AGG")
COUNT_BIG = sql_keyword("COUNT_BIG")
GROUPING = sql_keyword("GROUPING")
GROUPING_ID = sql_keyword("GROUPING_ID")
ROLLUP = sql_keyword("ROLLUP")
SOUNDEX = sql_keyword("SOUNDEX")
STDEV = sql_keyword("STDEV")
STDEV_P = sql_keyword("STDEV_P")
TOP = sql_keyword("TOP")
VAR = sql_keyword("VAR")
VARP = sql_keyword("VARP")


# =============================================================================
# Microsoft SQL Server grammar in pyparsing
# =============================================================================

class SqlGrammarMSSQLServer(SqlGrammar):
    # -------------------------------------------------------------------------
    # Forward declarations
    # -------------------------------------------------------------------------
    expr = Forward()
    select_statement = Forward()

    # -------------------------------------------------------------------------
    # Keywords
    # -------------------------------------------------------------------------
    # https://msdn.microsoft.com/en-us/library/ms189822.aspx
    sql_server_reserved_words = """
ADD ALL ALTER AND ANY AS ASC AUTHORIZATION
BACKUP BEGIN BETWEEN BREAK BROWSE BULK BY
CASCADE CASE CHECK CHECKPOINT CLOSE CLUSTERED COALESCE COLLATE COLUMN COMMIT
    COMPUTE CONSTRAINT CONTAINS CONTAINSTABLE CONTINUE CONVERT CREATE CROSS
    CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR
DATABASE DBCC DEALLOCATE DECLARE DEFAULT DELETE DENY DESC DISK DISTINCT
    DISTRIBUTED DOUBLE DROP DUMP
ELSE END ERRLVL ESCAPE EXCEPT EXEC EXECUTE EXISTS EXIT EXTERNAL
FETCH FILE FILLFACTOR FOR FOREIGN FREETEXT FREETEXTTABLE FROM FULL FUNCTION
GOTO GRANT GROUP
HAVING HOLDLOCK
IDENTITY IDENTITY_INSERT IDENTITYCOL IF IN INDEX INNER INSERT INTERSECT INTO IS
JOIN
KEY KILL
LEFT LIKE LINENO LOAD
MERGE
NATIONAL NOCHECK NONCLUSTERED NOT NULL NULLIF
OF OFF OFFSETS ON OPEN OPENDATASOURCE OPENQUERY OPENROWSET OPENXML OPTION OR
    ORDER OUTER OVER
PERCENT PIVOT PLAN PRECISION PRIMARY PRINT PROC PROCEDURE PUBLIC
RAISERROR READ READTEXT RECONFIGURE REFERENCES REPLICATION RESTORE RESTRICT
    RETURN REVERT REVOKE RIGHT ROLLBACK ROWCOUNT ROWGUIDCOL RULE
SAVE SCHEMA SECURITYAUDIT SELECT SEMANTICKEYPHRASETABLE
    SEMANTICSIMILARITYDETAILSTABLE SEMANTICSIMILARITYTABLE SESSION_USER SET
    SETUSER SHUTDOWN SOME STATISTICS SYSTEM_USER
TABLE TABLESAMPLE TEXTSIZE THEN TO TOP TRAN TRANSACTION TRIGGER TRUNCATE
    TRY_CONVERT TSEQUAL
UNION UNIQUE UNPIVOT UPDATE UPDATETEXT USE USER
VALUES VARYING VIEW
WAITFOR WHEN WHERE WHILE WITH WITHIN WRITETEXT
    """
    # ... "WITHIN GROUP" is listed, not "WITHIN", but
    odbc_reserved_words = """
ABSOLUTE ACTION ADA ADD ALL ALLOCATE ALTER AND ANY ARE AS ASC ASSERTION AT
    AUTHORIZATION AVG BEGIN BETWEEN BIT BIT_LENGTH BOTH BY
CASCADE CASCADED CASE CAST CATALOG CHAR CHAR_LENGTH CHARACTER CHARACTER_LENGTH
    CHECK CLOSE COALESCE COLLATE COLLATION COLUMN COMMIT CONNECT CONNECTION
    CONSTRAINT CONSTRAINTS CONTINUE CONVERT CORRESPONDING COUNT CREATE CROSS
    CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR
DATE DAY DEALLOCATE DEC DECIMAL DECLARE DEFAULT DEFERRABLE DEFERRED DELETE DESC
    DESCRIBE DESCRIPTOR DIAGNOSTICS DISCONNECT DISTINCT DOMAIN DOUBLE DROP
ELSE END END-EXEC ESCAPE EXCEPT EXCEPTION EXEC EXECUTE EXISTS EXTERNAL EXTRACT
FALSE FETCH FIRST FLOAT FOR FOREIGN FORTRAN FOUND FROM FULL
GET GLOBAL GO GOTO GRANT GROUP
HAVING HOUR
IDENTITY IMMEDIATE IN INCLUDE INDEX INDICATOR INITIALLY INNER INPUT INSENSITIVE
    INSERT INT INTEGER INTERSECT INTERVAL INTO IS ISOLATION
JOIN
KEY
LANGUAGE LAST LEADING LEFT LEVEL LIKE LOCAL LOWER
MATCH MAX MIN MINUTE MODULE MONTH
NAMES NATIONAL NATURAL NCHAR NEXT NO NONE NOT NULL NULLIF NUMERIC
OCTET_LENGTH OF ON ONLY OPEN OPTION OR ORDER OUTER OUTPUT OVERLAPS
PAD PARTIAL PASCAL POSITION PRECISION PREPARE PRESERVE PRIMARY PRIOR PRIVILEGES
    PROCEDURE PUBLIC
READ REAL REFERENCES RELATIVE RESTRICT REVOKE RIGHT ROLLBACK ROWS
SCHEMA SCROLL SECOND SECTION SELECT SESSION SESSION_USER SET SIZE SMALLINT SOME
    SPACE SQL SQLCA SQLCODE SQLERROR SQLSTATE SQLWARNING SUBSTRING SUM
    SYSTEM_USER
TABLE TEMPORARY THEN TIME TIMESTAMP TIMEZONE_HOUR TIMEZONE_MINUTE TO TRAILING
    TRANSACTION TRANSLATE TRANSLATION TRIM TRUE
UNION UNIQUE UNKNOWN UPDATE UPPER USAGE USER USING
VALUE VALUES VARCHAR VARYING VIEW
WHEN WHENEVER WHERE WITH WORK WRITE
YEAR
ZONE
    """
    # ... who thought "END-EXEC" was a good one?

    # Then some more:
    # - WITH ROLLUP: https://technet.microsoft.com/en-us/library/ms189305(v=sql.90).aspx  # noqa
    # - SOUNDEX: https://msdn.microsoft.com/en-us/library/ms187384.aspx
    rnc_extra_sql_server_keywords = """
ROLLUP
SOUNDEX
    """
    sql_server_keywords = " ".join(sorted(list(set(
        sql_server_reserved_words.split() +
        odbc_reserved_words.split() +
        ANSI92_RESERVED_WORD_LIST.split()
    ))))
    # log.critical(sql_server_keywords)
    keyword = make_words_regex(sql_server_keywords, caseless=True,
                               name="keyword")

    # -------------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------------
    # https://msdn.microsoft.com/en-us/library/ff848807.aspx
    comment = ansi_comment

    # -----------------------------------------------------------------------------
    # identifier
    # -----------------------------------------------------------------------------
    # http://dev.mysql.com/doc/refman/5.7/en/identifiers.html
    bare_identifier_word = make_regex_except_words(
        r"\b[a-zA-Z0-9$_]*\b",
        ANSI92_RESERVED_WORD_LIST,
        caseless=True,
        name="bare_identifier_word"
    )
    identifier = (
        bare_identifier_word |
        QuotedString(quoteChar="[", endQuoteChar="]", unquoteResults=False)
    ).setName("identifier")
    collation_name = identifier.copy()
    column_name = identifier.copy()
    column_alias = identifier.copy()
    table_name = identifier.copy()
    table_alias = identifier.copy()
    schema_name = identifier.copy()
    index_name = identifier.copy()
    function_name = identifier.copy()
    parameter_name = identifier.copy()
    database_name = identifier.copy()

    no_dot = NotAny('.')
    table_spec = (
        Combine(database_name + '.' + schema_name + '.' + table_name + no_dot) |
        Combine(schema_name + '.' + table_name + no_dot) |
        table_name + no_dot
    ).setName("table_spec")
    column_spec = (
        Combine(database_name + '.' + schema_name + '.' + table_name + '.' +
                column_name + no_dot) |
        Combine(schema_name + '.' + table_name + '.' + column_name + no_dot) |
        Combine(table_name + '.' + column_name + no_dot) |
        column_name + no_dot
    ).setName("column_spec")
    # I'm unsure if SQL Server allows keywords in the parts after dots, like
    # MySQL does.
    # - http://stackoverflow.com/questions/285775/how-to-deal-with-sql-column-names-that-look-like-sql-keywords  # noqa

    bind_parameter = Literal('?')

    variable = Regex(r"@[a-zA-Z0-9\.$_]+").setName("variable")

    argument_list = (
        delimitedList(expr).setName("arglist").setParseAction(', '.join)
    )
    function_call = Combine(function_name + LPAR) + argument_list + RPAR

    # Not supported: index hints
    # ... http://stackoverflow.com/questions/11016935/how-can-i-force-a-query-to-not-use-a-index-on-a-given-table  # noqa

    # -----------------------------------------------------------------------------
    # CASE
    # -----------------------------------------------------------------------------
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
    # Expressions
    # -----------------------------------------------------------------------------
    aggregate_function = (
        # https://msdn.microsoft.com/en-us/library/ms173454.aspx
        AVG |
        CHECKSUM_AGG |
        COUNT |
        COUNT_BIG |
        GROUPING |
        GROUPING_ID |
        MAX |
        MIN |
        STDEV |
        STDEV_P |
        SUM |
        VAR |
        VARP
    )
    expr_term = (
        INTERVAL + expr + time_unit |
        Optional(EXISTS) + LPAR + select_statement + RPAR |
        # ... e.g. mycol = EXISTS(SELECT ...)
        # ... e.g. mycol IN (SELECT ...)
        LPAR + delim_list(expr) + RPAR |
        # ... e.g. mycol IN (1, 2, 3)
        case_expr |
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
        (COLLATE | oneOf('! - + ~'), UNARY_OP, opAssoc.RIGHT),
        (
            (
                oneOf('^ * / %') |
                oneOf('+ - << >> & | = <=> >= > <= < <> !=') |
                (IS + Optional(NOT)) | LIKE | (Optional(NOT) + IN) |
                SOUNDEX  # RNC; presumably at same level as LIKE
            ),
            BINARY_OP,
            opAssoc.LEFT
        ),
        ((BETWEEN, AND), TERNARY_OP, opAssoc.LEFT),
        # CASE handled above (hoping precedence is not too much of a problem)
        (NOT, UNARY_OP, opAssoc.RIGHT),
        (AND | '&&' | OR | '||' | ':=', BINARY_OP, opAssoc.LEFT),
    ], lpar=LPAR, rpar=RPAR)
    # ignores LIKE [ESCAPE]

    # -------------------------------------------------------------------------
    # SELECT
    # -------------------------------------------------------------------------

    compound_operator = UNION + Optional(ALL | DISTINCT)

    ordering_term = (
        expr + Optional(COLLATE + collation_name) + Optional(ASC | DESC)
    )

    join_constraint = Optional(Group(
        (ON + expr) |
        (USING + LPAR + delim_list(column_name) + RPAR)
    ))

    join_op = Group(
        COMMA |
        NATURAL + (Optional(LEFT | RIGHT) + Optional(OUTER)) + JOIN |
        (INNER | CROSS) + JOIN |
        Optional(LEFT | RIGHT) + Optional(OUTER) + JOIN
    )

    join_source = Forward()
    single_source = (
        (
            table_spec.copy().setResultsName("from_tables",
                                             listAllMatches=True) +
            Optional(Optional(AS) + table_alias)
            # Optional(index_hint_list)  # not supported yet
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
    where_expr = Group(expr).setResultsName("where_expr")
    where_clause = Group(
        Optional(WHERE + where_expr)
    ).setResultsName("where_clause")
    select_core = (
        SELECT +
        Optional(TOP + integer) +
        Group(Optional(ALL | DISTINCT))("select_specifier") +
        Group(delim_list(result_column))("select_expression") +
        Optional(
            FROM + join_source +
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
        # PROCEDURE ignored
        # rest ignored
        Optional(';')
    )
    select_statement.ignore(comment)

    # https://msdn.microsoft.com/en-us/library/ms175874.aspx
    # ... approximately (and conservatively):
    MSSQL_INVALID_FIRST_IF_UNQUOTED = re.compile(r"[^a-zA-Z_@#]")
    MSSQL_INVALID_IF_UNQUOTED = re.compile(r"[^a-zA-Z0-9_@#$]")

    def __init__(self):
        super().__init__()

    @classmethod
    def quote_identifier(cls, identifier: str) -> str:
        return "[{}]".format(identifier)

    @classmethod
    def is_quoted(cls, identifier: str) -> bool:
        return identifier.startswith("[") and identifier.endswith("]")

    @classmethod
    def requires_quoting(cls, identifier: str) -> bool:
        assert identifier, "Empty identifier"
        if cls.MSSQL_INVALID_IF_UNQUOTED.search(identifier):
            return True
        firstchar = identifier[0]
        if cls.MSSQL_INVALID_FIRST_IF_UNQUOTED.search(firstchar):
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
    def test_dialect_specific_2(cls):
        log.info("Testing Microsoft SQL Server-specific aspects...")

        log.info("Testing quoted identifiers")
        test_succeed(cls.identifier, "[FROM]")
        test_succeed(cls.identifier, "[SELECT FROM]")

        log.info("Testing table_spec")
        # SQL Server uses up to: db.schema.table.column
        test_succeed(cls.table_spec, "mytable")
        test_succeed(cls.table_spec, "mydb.mytable")
        test_succeed(cls.table_spec, "mydb.[my silly table]")
        test_succeed(cls.table_spec, "mydb.myschema.mytable")
        test_fail(cls.table_spec, "mydb . mytable")
        test_fail(cls.table_spec, "mydb.myschema.mytable.mycol")

        log.info("Testing column_spec")
        test_succeed(cls.column_spec, "mycol")
        test_succeed(cls.column_spec, "forename")
        test_succeed(cls.column_spec, "mytable.mycol")
        test_succeed(cls.column_spec, "t1.a")
        test_succeed(cls.column_spec, "[my silly table].[my silly column]")
        test_succeed(cls.column_spec, "mydb.myschema.mytable.mycol")
        test_succeed(cls.column_spec, "myschema.mytable.mycol")
        test_fail(cls.column_spec, "myschema . mytable . mycol")

        log.info("Testing variable")
        test_succeed(cls.variable, "@myvar")

        log.info("Testing argument_list")
        test_succeed(cls.argument_list, "@myvar, 5")

        log.info("Testing function_call")
        test_succeed(cls.function_call, "myfunc(@myvar, 5)")

        # ---------------------------------------------------------------------
        # Expressions
        # ---------------------------------------------------------------------

        log.info("Testing case_expr")
        test_succeed(cls.case_expr, """
            CASE v
              WHEN 2 THEN x
              WHEN 3 THEN y
              ELSE -99
            END
        """)


# =============================================================================
# Tests
# =============================================================================

# noinspection PyUnboundLocalVariable
def pyparsing_bugtest_delimited_list_combine(fix_problem: bool = True) -> None:
    if fix_problem:
        # noinspection PyPep8Naming,PyShadowingNames
        delimitedList = delim_list
    word = Word(alphanums)
    word_list_no_combine = delimitedList(word, combine=False)
    word_list_combine = delimitedList(word, combine=True)
    print(word_list_no_combine.parseString('one, two', parseAll=True))  # ['one', 'two']  # noqa
    print(word_list_no_combine.parseString('one,two', parseAll=True))  # ['one', 'two']  # noqa
    print(word_list_combine.parseString('one, two', parseAll=True))  # ['one']: ODD ONE OUT  # noqa
    print(word_list_combine.parseString('one,two', parseAll=True))  # ['one,two']  # noqa


# =============================================================================
# main
# =============================================================================

def main() -> None:
    log.info("TESTING MICROSOFT SQL SERVER DIALECT")
    mssql = SqlGrammarMSSQLServer()
    mssql.test()
    log.info("ALL TESTS SUCCESSFUL")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    main()
