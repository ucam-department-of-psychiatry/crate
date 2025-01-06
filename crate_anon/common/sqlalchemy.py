"""
crate_anon/common/sqlalchemy.py

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

**Additional SQLAlchemy assistance functions.**

"""

# =============================================================================
# Imports
# =============================================================================

import logging
from typing import Dict

from cardinal_pythonlib.sqlalchemy.dialect import get_dialect_name
from sqlalchemy.dialects.mysql import insert as insert_mysql
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.schema import Table
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import Insert

log = logging.getLogger(__name__)


# =============================================================================
# INSERT ... ON DUPLICATE KEY UPDATE
# =============================================================================


def insert_with_upsert_if_supported(
    table: Table,
    values: Dict,
    session: Session = None,
    dialect: Dialect = None,
) -> Insert:
    """
    Creates an "upsert" (INSERT ... ON DUPLICATE KEY UPDATE) statment if
    possible (e.g. MySQL/MariaDB). Failing that, returns an INSERT statement.

    Args:
        table:
            SQLAlchemy Table in which to insert values.
        values:
            Values to insert (column: value dictionary).
        session:
            Session from which to extract a dialect.
        dialect:
            Explicit dialect.

    Previously (prior to 2025-01-05 and prior to SQLAlchemy 2), we did this:

    .. code-block:: python

        q = sqla_table.insert_on_duplicate().values(destvalues)

    This "insert_on_duplicate" member was available because
    crate_anon/anonymise/config.py ran monkeypatch_TableClause(), from
    cardinal_pythonlib.sqlalchemy.insert_on_duplicate. The function did dialect
    detection via "@compiles(InsertOnDuplicate, SqlaDialectName.MYSQL)". But
    it did nasty text-based hacking to get the column names.

    However, SQLAlchemy now supports "upsert" for MySQL:
    https://docs.sqlalchemy.org/en/20/dialects/mysql.html#insert-on-duplicate-key-update-upsert

    Note the varying argument forms possible.

    The only other question: if the dialect is not MySQL, will the reference to
    insert_stmt.on_duplicate_key_update crash or just not do anything? To test:

    .. code-block:: python

        from sqlalchemy import table
        t = table("tablename")
        destvalues = {"a": 1}

        insert_stmt = t.insert().values(destvalues)
        on_dup_key_stmt = insert_stmt.on_duplicate_key_update(destvalues)

    This does indeed crash (AttributeError: 'Insert' object has no attribute
    'on_duplicate_key_update'). In contrast, this works:

    .. code-block:: python

        from sqlalchemy.dialects.mysql import insert as insert_mysql

        insert2 = insert_mysql(t).values(destvalues)
        on_dup_key2 = insert2.on_duplicate_key_update(destvalues)

    Note also that an insert() statement doesn't gain a
    "on_duplicate_key_update" attribute just because MySQL is used (the insert
    statement doesn't know that yet).

    The old way was good for dialect detection but ugly for textual analysis of
    the query. The new way is more elegant in the query, but less for dialect
    detection. Overall, new way likely preferable.

    """
    if bool(session) + bool(dialect) != 1:
        raise ValueError(
            f"Must specify exactly one of: {session=}, {dialect=}"
        )
    dialect_name = get_dialect_name(dialect or session)
    if dialect_name == "mysql":
        return (
            insert_mysql(table).values(values).on_duplicate_key_update(values)
        )
    else:
        return table.insert().values(values)
