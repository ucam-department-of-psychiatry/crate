#!/usr/bin/env python

"""
crate_anon/preprocess/rio_view_func.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Assistance functions for RiO view creation.**

"""

from typing import Dict, Iterable, List, Union

from crate_anon.common.sql import (
    sql_string_literal,
    ViewMaker,
)
from crate_anon.preprocess.rio_constants import (
    CRATE_COL_LAST_DOC,
    CRATE_COL_LAST_NOTE,
    CRATE_COL_PK,
    CRATE_COL_RIO_NUMBER,
)


# =============================================================================
# RiO view creators: generic
# =============================================================================

class RioViewConfigOptions(object):
    """
    Simple class to store some command-line options for RiO view creation
    """
    def __init__(self,
                 rio: bool,
                 rcep: bool,
                 cpft: bool,
                 print_sql_only: bool,
                 drop_not_create: bool,
                 master_patient_table: str,
                 full_prognotes_table: str,
                 prognotes_current_only: bool = True,
                 clindocs_current_only: bool = True,
                 allergies_current_only: bool = True,
                 audit_info: bool = False,
                 postcodedb: str = "",
                 geogcols: List[str] = None) -> None:
        """
        Args:
            rio:
                Treat the source database as a direct copy of RiO?
            rcep:
                Treat the source database as the product of Servelec's RiO CRIS
                Extract Program v2 (instead of raw RiO)?
            cpft:
                Apply hacks for Cambridgeshire & Peterborough NHS Foundation
                Trust (CPFT) RCEP database?
            print_sql_only:
                print SQL rather than executing it?
            drop_not_create:
                REMOVES new columns/indexes, rather than creating them.
                (Not really very dangerous, but might take some time to
                recreate.)
            prognotes_current_only:
                restrict Progress Note records to current versions only?
            clindocs_current_only:
                restrict Clinical Document records to current versions only?
            allergies_current_only:
                restrict Allergy records to current versions only?
            audit_info:
                include audit trail information in the research database?
            postcodedb:
                Specify database (schema) name for ONS Postcode Database (as
                imported by CRATE) to link in. With SQL Server, you will have
                to specify the schema as well as the database; e.g.
                ``ONS_PD.dbo"``.
            geogcols:
                List of geographical information columns to link in from ONS
                Postcode Database. BEWARE that you do not specify anything too
                identifying.
        """
        assert rio != rcep, "Use either RiO or RCEP format"
        self.rio = rio
        self.rcep = rcep
        self.cpft = cpft
        self.print_sql_only = print_sql_only
        self.drop_not_create = drop_not_create
        self.master_patient_table = master_patient_table
        self.full_prognotes_table = full_prognotes_table
        self.prognotes_current_only = prognotes_current_only
        self.clindocs_current_only = clindocs_current_only
        self.allergies_current_only = allergies_current_only
        self.audit_info = audit_info
        self.postcodedb = postcodedb
        self.geogcols = geogcols or []  # type: List[str]


def lookup_from_fragment(lookup_table: str,
                         aliased_lookup_table: str,
                         lookup_pk: str,
                         basetable: str,
                         basecolumn: str) -> str:
    """
    Returns ``LEFT JOIN`` SQL to implement a lookup from a system lookup
    table.

    For when ``lookup_pk`` is really a PK.

    Args:
        lookup_table: name of the lookup table
        aliased_lookup_table: alias to use (in SQL) for the lookup table
        lookup_pk: PK in the lookup table
        basetable: name of the base table from which to look up information
        basecolumn: name of the column in the base table that maps to the PK
            in the lookup table

    Returns:
        an SQL string like
        ``LEFT JOIN lookuptable lkalias ON lkalias.pk = basetable.somecol``
    """
    return (
        f"LEFT JOIN {lookup_table} {aliased_lookup_table}\n"
        f"  ON {aliased_lookup_table}.{lookup_pk} = {basetable}.{basecolumn}"
    )


def lookup_from_fragment_first_row(lookup_table: str,
                                   aliased_lookup_table: str,
                                   lookup_key: str,
                                   lookup_unique_field: str,
                                   basetable: str,
                                   basecolumn: str) -> str:
    """
    Returns ``LEFT JOIN`` SQL to look up values from a lookup table that might
    give us multiple values and we only want the first. See below.

    Args:
        lookup_table: name of the lookup table
        aliased_lookup_table: alias to use (in SQL) for the lookup table
        lookup_key: a field we'll match to ``basetable.basecolumn``
        lookup_unique_field: the field from which we want the first value 
        basetable: name of the base table from which to look up information
        basecolumn: name of the column in the base table that maps to the PK
            in the lookup table

    Returns:
        an SQL string

    Modified 2017-01-23, because sometimes the lookup column is not unique,
    e.g. lookup from "Code" to "CodeDescription" in NNNStatus (see also
    rio_views.py). The LEFT JOIN was giving us duplicate rows. We want only
    the first match. See
    https://www.periscopedata.com/blog/4-ways-to-join-only-the-first-row-in-sql.html

    We were doing the FROM component as:

    .. code-block:: none

        LEFT JOIN {lookup_table} {aliased_lookup_table}
            ON {aliased_lookup_table}.{lookup_pk} = {basetable}.{basecolumn}

    and we'll replace that with

    .. code-block:: none

        LEFT JOIN {lookup_table} {aliased_lookup_table}
            ON {aliased_lookup_table}.{lookup_pk} = (
                SELECT {lookup_pk} FROM {lookup_table}
                WHERE {lookup_table}.{lookup_pk} = {basetable}.{basecolumn}
                ORDER BY {lookup_table}.{lookup_pk}
                LIMIT 1
            )

    ... compare to the example of

    .. code-block:: none

        SELECT * FROM users
        JOIN widgets ON widgets.id = (
            SELECT id FROM widgets
            WHERE widgets.user_id = users.id
            ORDER BY created_at DESC
            LIMIT 1
        )

    Note that SQL Server uses "SELECT TOP 1 ..." not "SELECT ... LIMIT 1".

    """  # noqa
    return (
        f"LEFT JOIN {lookup_table} {aliased_lookup_table} "
        f"ON {aliased_lookup_table}.{lookup_unique_field} = ("
        f"SELECT TOP 1 {lookup_unique_field} FROM {lookup_table} "
        f"WHERE {lookup_table}.{lookup_key} = {basetable}.{basecolumn} "
        f"ORDER BY {lookup_table}.{lookup_unique_field})"
    )


def lookup_from_fragment_first_row_outer_apply(lookup_fields: Iterable[str],
                                               lookup_table: str,
                                               aliased_lookup_table: str,
                                               lookup_key: str,
                                               basetable: str,
                                               basecolumn: str) -> str:
    """
    As for :func:`lookup_from_fragment_first_row` (q.v.), but works without a
    unique field in the lookup table.

    Args:
        lookup_fields: field(s) to look up the first values from 
        lookup_table: name of the lookup table
        aliased_lookup_table: alias to use (in SQL) for the lookup table
        lookup_key: a field we'll match to ``basetable.basecolumn``
        basetable: name of the base table from which to look up information
        basecolumn: name of the column in the base table that maps to the PK
            in the lookup table

    Returns:
        an SQL string

    See
    
    - http://stackoverflow.com/questions/2043259/sql-server-how-to-join-to-first-row
    - http://stackoverflow.com/questions/9275132/real-life-example-when-to-use-outer-cross-apply-in-sql
    """  # noqa
    return (
        f"OUTER APPLY (SELECT TOP 1 {', '.join(lookup_fields)} "
        f"FROM {lookup_table} "
        f"WHERE {lookup_table}.{lookup_key} = {basetable}.{basecolumn}) "
        f"{aliased_lookup_table}"
    )


def simple_lookup_join(viewmaker: ViewMaker,
                       basecolumn: str,
                       lookup_table: str,
                       lookup_pk: str,
                       lookup_fields_aliases: Dict[str, str],
                       internal_alias_prefix: str) -> None:
    """
    Modifies the ViewMaker to add a simple lookup join.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: name of the column in the base table to look up from
        lookup_table: name of the lookup table
        lookup_pk: PK of the lookup table
        lookup_fields_aliases: dictionary mapping lookup field names (in the
            lookup table) to aliases in the SELECT part of the SQL statement
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert lookup_table, "Missing lookup_table"
    assert lookup_pk, "Missing lookup_pk"
    assert lookup_fields_aliases, "lookup_fields_aliases column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    aliased_lookup_table = internal_alias_prefix + "_" + lookup_table
    for column, alias in lookup_fields_aliases.items():
        viewmaker.add_select(
            f"{aliased_lookup_table}.{column} AS {alias}")
    viewmaker.add_from(lookup_from_fragment_first_row_outer_apply(
        lookup_fields=lookup_fields_aliases.keys(),
        lookup_table=lookup_table,
        aliased_lookup_table=aliased_lookup_table,
        lookup_key=lookup_pk,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn
    ))
    viewmaker.record_lookup_table_keyfield(lookup_table, lookup_pk)


def standard_rio_code_lookup(viewmaker: ViewMaker,
                             basecolumn: str,
                             lookup_table: str,
                             column_prefix: str,
                             internal_alias_prefix: str) -> None:
    """
    Implements a standard RiO lookup using a lookup table with ``Code`` /
    ``CodeDescription`` fields.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: name of the column in the base table to look up from
        lookup_table: name of the lookup table
        column_prefix: prefix for the view alias that describes the thing being
            looked up
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert lookup_table, "Missing lookup_table"
    assert column_prefix, "Missing column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    aliased_lookup_table = internal_alias_prefix + "_" + lookup_table
    viewmaker.add_select(f"""
        {viewmaker.basetable}.{basecolumn} AS {column_prefix}_Code,
        {aliased_lookup_table}.CodeDescription AS {column_prefix}_Description
    """)
    lookup_pk = 'Code'
    viewmaker.add_from(lookup_from_fragment_first_row_outer_apply(
        lookup_fields=['CodeDescription'],
        lookup_table=lookup_table,
        aliased_lookup_table=aliased_lookup_table,
        lookup_key=lookup_pk,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn
    ))
    viewmaker.record_lookup_table_keyfield(lookup_table, lookup_pk)


def standard_rio_code_lookup_with_national_code(
        viewmaker: ViewMaker,
        basecolumn: str,
        lookup_table: str,
        column_prefix: str,
        internal_alias_prefix: str) -> None:
    """
    Implements a standard RiO lookup using a lookup table with ``Code``,
    ``CodeDescription``, and ``NationalCode`` fields.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: name of the column in the base table to look up from
        lookup_table: name of the lookup table
        column_prefix: prefix for the view alias that describes the thing being
            looked up
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert lookup_table, "Missing lookup_table"
    assert column_prefix, "Missing column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    aliased_lookup_table = internal_alias_prefix + "_" + lookup_table
    viewmaker.add_select(f"""
        {viewmaker.basetable}.{basecolumn} AS {column_prefix}_Code,
        {aliased_lookup_table}.CodeDescription AS {column_prefix}_Description,
        {aliased_lookup_table}.NationalCode AS {column_prefix}_National_Code
    """)
    lookup_pk = 'Code'
    viewmaker.add_from(lookup_from_fragment_first_row_outer_apply(
        lookup_fields=['CodeDescription', 'NationalCode'],
        lookup_table=lookup_table,
        aliased_lookup_table=aliased_lookup_table,
        lookup_key=lookup_pk,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn
    ))
    viewmaker.record_lookup_table_keyfield(lookup_table, lookup_pk)


def view_formatting_dict(viewmaker: ViewMaker) -> Dict[str, str]:
    """
    Produces a dictionary that can be used for automatically formatting
    templatized SQL.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`

    Returns:
        dict: dictionary with the following keys:

            =============== ===================================================
            Key             Meaning
            =============== ===================================================
            ``basetable``   Base table of the view
            =============== ===================================================

    """
    return {
        'basetable': viewmaker.basetable,
    }


def simple_view_expr(viewmaker: ViewMaker,
                     expr: str,
                     alias: str) -> None:
    """
    Adds a simple SQL expression to a viewmaker.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        expr: SQL expression; e.g. ``42``, ``mycol + 17``
        alias: alias to apply (``... AS somealias``)
    """
    assert expr, "Missing expr"
    assert alias, "Missing alias"
    vd = view_formatting_dict(viewmaker)
    formatted_expr = expr.format(**vd)
    viewmaker.add_select(formatted_expr + f" AS {alias}")


def simple_view_where(viewmaker: ViewMaker,
                      where_clause: str,
                      index_cols: Iterable[str] = None) -> None:
    """
    Applies a simple ``WHERE`` clause to a viewmaker.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        where_clause: WHERE clause, e.g. ``somecol = 1``
        index_cols: names of columns that are part of the WHERE condition and
            would benefit from being indexed, for speed
    """

    assert where_clause, "Missing where_clause"
    index_cols = index_cols or []
    viewmaker.add_where(where_clause)
    # noinspection PyTypeChecker
    for col in index_cols:
        viewmaker.record_lookup_table_keyfield(viewmaker.basetable, col)


def add_index_only(viewmaker: ViewMaker,
                   table: str,
                   column_or_columns: Union[str, Iterable[str]]) -> None:
    """
    Adds an index request to a viewmaker.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        table: table name
        column_or_columns: column name (string or list of strings) to index
            within that table
    """
    viewmaker.record_lookup_table_keyfield(table, column_or_columns)


# =============================================================================
# RiO view creators: specific
# =============================================================================

def rio_add_user_lookup(viewmaker: ViewMaker,
                        basecolumn: str,
                        column_prefix: str = None,
                        internal_alias_prefix: str = None) -> None:
    """
    Adds a user lookup. For example, RiO tables tend to have columns like
    "modified_by_user" with a cryptic ID; this function adds views so we can
    see who that was.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: user ID column from the base table
        column_prefix: column prefix describing the kind of user
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once

    NOT VERIFIED IN FULL - insufficient data with just top 1000 rows for
    each table (2016-07-12).
    """
    assert basecolumn, "Missing basecolumn"
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    # ... table alias
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_Code,

        {ap}_genhcp.ConsultantFlag AS {cp}_Consultant_Flag,

        {ap}_genperson.Email AS {cp}_Email,
        {ap}_genperson.Title AS {cp}_Title,
        {ap}_genperson.FirstName AS {cp}_First_Name,
        {ap}_genperson.Surname AS {cp}_Surname,

        {ap}_prof.Code AS {cp}_Resp_Clinician_Profession_Code,
        {ap}_prof.CodeDescription AS {cp}_Resp_Clinician_Profession_Description,

        {ap}_serviceteam.Code AS {cp}_Primary_Team_Code,
        {ap}_serviceteam.CodeDescription AS {cp}_Primary_Team_Description,

        {ap}_genspec.Code AS {cp}_Main_Specialty_Code,
        {ap}_genspec.CodeDescription AS {cp}_Main_Specialty_Description,
        {ap}_genspec.NationalCode AS {cp}_Main_Specialty_National_Code,

        {ap}_profgroup.Code AS {cp}_Professional_Group_Code,
        {ap}_profgroup.CodeDescription AS {cp}_Professional_Group_Description,

        {ap}_genorg.Code AS {cp}_Organisation_Type_Code,
        {ap}_genorg.CodeDescription AS {cp}_Organisation_Type_Description
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    # - RECP had "speciality" / "specialty" inconsistency.
    # - {cp}_location... ?? Presumably from GenLocation, but via what? Seems
    #   meaningless. In our snapshut, all are NULL anyway.
    # - User codes are keyed to GenUser.GenUserID, but also to several other
    #   tables, e.g. GenHCP.GenHCPCode; GenPerson.GenPersonID
    # - We use unique table aliases here, so that overall we can make >1 sets
    #   of different "user" joins simultaneously.
    viewmaker.add_from("""
        LEFT JOIN (
            GenUser {ap}_genuser
            LEFT JOIN GenPerson {ap}_genperson
                ON {ap}_genperson.GenPersonID = {ap}_genuser.GenUserID
            LEFT JOIN GenHCP {ap}_genhcp
                ON {ap}_genhcp.GenHCPCode = {ap}_genuser.GenUserID
            LEFT JOIN GenHCPRCProfession {ap}_prof
                ON {ap}_prof.Code = {ap}_genhcp.RCProfession
            LEFT JOIN GenServiceTeam {ap}_serviceteam
                ON {ap}_serviceteam.Code = {ap}_genhcp.PrimaryTeam
            LEFT JOIN GenSpecialty {ap}_genspec
                ON {ap}_genspec.Code = {ap}_genhcp.MainGenSpecialtyCode
            LEFT JOIN GenStaffProfessionalGroup {ap}_profgroup
                ON {ap}_profgroup.Code = {ap}_genhcp.StaffProfessionalGroup
            LEFT JOIN GenOrganisationType {ap}_genorg
                ON {ap}_genorg.Code = {ap}_genuser.OrganisationType
        ) ON {ap}_genuser.GenUserID = {basetable}.{basecolumn}
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    # OTHER THINGS:
    # - GenHCP.Occupation is listed in the RiO docs but doesn't actually seem
    #   to exist. (Perhaps explaining why it's not linked in the RCEP output.)
    #   I had tried to link it to CareCoordinatorOccupation.Code.
    #   If you use:
    #       SELECT *
    #       FROM information_schema.columns
    #       WHERE column_name LIKE '%Occup%'
    #   you only get Client_Demographic_Details.Occupation and
    #   Client_Demographic_Details.Partner_Occupation
    viewmaker.record_lookup_table_keyfields([
        ('GenHCP', 'GenHCPCode'),
        ('GenUser', 'GenUserID'),
        ('GenPerson', 'GenPersonID'),
        ('GenHCPRCProfession', 'Code'),
        ('GenServiceTeam', 'Code'),
        ('GenSpecialty', 'Code'),
        ('GenStaffProfessionalGroup', 'Code'),
        ('GenOrganisationType', 'Code'),
    ])


def rio_add_consultant_lookup(viewmaker: ViewMaker,
                              basecolumn: str,
                              column_prefix: str = None,
                              internal_alias_prefix: str = None) -> None:
    """
    Adds a user lookup where that lookup is a hospital consultant.
    Compare :func:`rio_add_user_lookup`.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: user ID column from the base table
        column_prefix: column prefix describing the kind of user
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_ID,
        {ap}_cons.Firstname AS {cp}_First_Name,
        {ap}_cons.Surname AS {cp}_Surname,
        {ap}_cons.SpecialtyID AS {cp}_Specialty_Code,
        {ap}_spec.CodeDescription AS {cp}_Specialty_Description
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            GenHospitalConsultant {ap}_cons
            LEFT JOIN GenSpecialty {ap}_spec
                ON {ap}_spec.Code = {ap}_cons.SpecialtyID
        ) ON {ap}_cons.ConsultantID = {basetable}.{basecolumn}
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_table_keyfields([
        ('GenHospitalConsultant', 'ConsultantID'),
        ('GenSpecialty', 'Code'),
    ])


def rio_add_team_lookup(viewmaker: ViewMaker,
                        basecolumn: str,
                        column_prefix: str = None,
                        internal_alias_prefix: str = None) -> None:
    """
    Adds a team lookup (from team ID to team details).

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: team ID column from the base table
        column_prefix: column prefix describing the kind of team
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_Code,
        {ap}_team.CodeDescription AS {cp}_Description,
        {ap}_classif.Code AS {cp}_Classification_Group_Code,
        {ap}_classif.CodeDescription AS {cp}_Classification_Group_Description
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            GenServiceTeam {ap}_team
            INNER JOIN GenServiceTeamClassification {ap}_classif
                ON {ap}_classif.Code = {ap}_team.ClassificationGroup
        ) ON {basetable}.{basecolumn} = {ap}_team.Code
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_table_keyfields([
        ('GenServiceTeam', 'Code'),
        ('GenServiceTeamClassification', 'Code'),
    ])


def rio_add_carespell_lookup(viewmaker: ViewMaker,
                             basecolumn: str,
                             column_prefix: str = None,
                             internal_alias_prefix: str = None) -> None:
    """
    Adds a care spell lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: ID column from the base table
        column_prefix: column prefix describing the kind of care spell this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_Number,
        {ap}_spell.StartDate AS {cp}_Start_Date,
        {ap}_spell.EndDate AS {cp}_End_Date,
        {ap}_spell.MentalHealth AS {cp}_Mental_Health,
        {ap}_spell.GenSpecialtyCode AS {cp}_Specialty_Code,
        {ap}_spec.CodeDescription AS {cp}_Specialty_Description,
        {ap}_spec.NationalCode AS {cp}_Specialty_National_Code
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            ClientCareSpell {ap}_spell
            INNER JOIN GenSpecialty {ap}_spec
                ON {ap}_spec.Code = {ap}_spell.GenSpecialtyCode
        ) ON {basetable}.{basecolumn} = {ap}_spell.CareSpellNum
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_table_keyfields([
        ('ClientCareSpell', 'CareSpellNum'),
        ('GenSpecialty', 'Code'),
    ])


def rio_add_diagnosis_lookup(viewmaker: ViewMaker,
                             basecolumn_scheme: str,
                             basecolumn_code: str,
                             alias_scheme: str,
                             alias_code: str,
                             alias_description: str,
                             internal_alias_prefix: str = None) -> None:
    """
    Adds a diagnosis lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn_scheme: base table column giving the diagnostic scheme (e.g.
            a column containing "ICD-10")
        basecolumn_code: base table column containing the diagnostic code
        alias_scheme: alias to be used for "diagnostic scheme"
        alias_code: alias to be used for "diagnostic code"
        alias_description: alias to be used for "description of diagnosis"
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    # Can't use simple_lookup_join as we have to join on two fields,
    # diagnostic scheme and diagnostic code.
    assert basecolumn_scheme, "Missing basecolumn_scheme"
    assert basecolumn_code, "Missing basecolumn_code"
    assert alias_scheme, "Missing alias_scheme"
    assert alias_code, "Missing alias_code"
    assert alias_description, "Missing alias_description"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    internal_alias_prefix = internal_alias_prefix or "t"
    viewmaker.add_select("""
        {basetable}.{basecolumn_scheme} AS {alias_scheme},
        {basetable}.{basecolumn_code} AS {alias_code},
        {ap}_diag.CodeDescription AS {alias_description}
    """.format(
        basetable=viewmaker.basetable,
        basecolumn_scheme=basecolumn_scheme,
        alias_scheme=alias_scheme,
        basecolumn_code=basecolumn_code,
        alias_code=alias_code,
        ap=internal_alias_prefix,
        alias_description=alias_description,
    ))
    # - RECP had "speciality" / "specialty" inconsistency.
    # - {cp}_location... ?? Presumably from GenLocation, but via what? Seems
    #   meaningless. In our snapshut, all are NULL anyway.
    # - User codes are keyed to GenUser.GenUserID, but also to several other
    #   tables, e.g. GenHCP.GenHCPCode; GenPerson.GenPersonID
    # - We use unique table aliases here, so that overall we can make >1 sets
    #   of different "user" joins simultaneously.
    viewmaker.add_from("""
        LEFT JOIN DiagnosisCode {ap}_diag
            ON {ap}_diag.CodingScheme = {basetable}.{basecolumn_scheme}
            AND {ap}_diag.Code = {basetable}.{basecolumn_code}
    """.format(
        basetable=viewmaker.basetable,
        basecolumn_scheme=basecolumn_scheme,
        basecolumn_code=basecolumn_code,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_table_keyfield('DiagnosisCode', ['CodingScheme',
                                                             'Code'])


def rio_add_ims_event_lookup(viewmaker: ViewMaker,
                             basecolumn_event_num: str,
                             column_prefix: str,
                             internal_alias_prefix: str) -> None:
    """
    Adds an IMS event lookup. (?)

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn_event_num: ID column from the base table
        column_prefix: column prefix describing the kind of care spell this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    # There is a twin key: ClientID and EventNumber
    # However, we have made crate_rio_number, so we'll use that instead.
    # Key to the TABLE, not the VIEW.
    assert basecolumn_event_num, "Missing basecolumn_event_num"
    assert column_prefix, "Missing column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    viewmaker.add_select("""
        {basetable}.{basecolumn_event_num} AS {cp}_Event_Number,
        {ap}_evt.{CRATE_COL_PK} AS {cp}_Inpatient_Stay_PK
    """.format(
        basetable=viewmaker.basetable,
        basecolumn_event_num=basecolumn_event_num,
        cp=column_prefix,
        ap=internal_alias_prefix,
        CRATE_COL_PK=CRATE_COL_PK,
    ))
    viewmaker.add_from("""
        LEFT JOIN ImsEvent {ap}_evt
            ON {ap}_evt.{CRATE_COL_RIO_NUMBER} = {basetable}.{CRATE_COL_RIO_NUMBER}
            AND {ap}_evt.EventNumber = {basetable}.{basecolumn_event_num}
    """.format(  # noqa
        basetable=viewmaker.basetable,
        ap=internal_alias_prefix,
        CRATE_COL_RIO_NUMBER=CRATE_COL_RIO_NUMBER,
        basecolumn_event_num=basecolumn_event_num,
    ))
    viewmaker.record_lookup_table_keyfield('ImsEvent', [CRATE_COL_RIO_NUMBER,
                                                        'EventNumber'])


def rio_add_gp_lookup(viewmaker: ViewMaker,
                      basecolumn: str,
                      column_prefix: str,
                      internal_alias_prefix: str) -> None:
    """
    Adds a general practitioner (GP) lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: ID column from the base table
        column_prefix: column prefix describing the kind of GP this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert column_prefix, "Missing column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_Code,
        {ap}_gp.CodeDescription AS {cp}_Description,
        {ap}_gp.NationalCode AS {cp}_National_Code,
        {ap}_gp.Title AS {cp}_Title,
        {ap}_gp.Forename AS {cp}_Forename,
        {ap}_gp.Surname AS {cp}_Surname
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN GenGP {ap}_gp
            ON {ap}_gp.Code = {basetable}.{basecolumn}
    """.format(
        ap=internal_alias_prefix,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
    ))
    viewmaker.record_lookup_table_keyfield('GenGP', 'Code')


def rio_add_gp_practice_lookup(viewmaker: ViewMaker,
                               basecolumn: str,
                               column_prefix: str,
                               internal_alias_prefix: str) -> None:
    """
    Adds a GP practice lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: ID column from the base table
        column_prefix: column prefix describing the kind of GP practice this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert column_prefix, "Missing column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_Code,
        {ap}_prac.CodeDescription AS {cp}_Description,
        {ap}_prac.AddressLine1 AS {cp}_Address_Line_1,
        {ap}_prac.AddressLine2 AS {cp}_Address_Line_2,
        {ap}_prac.AddressLine3 AS {cp}_Address_Line_3,
        {ap}_prac.AddressLine4 AS {cp}_Address_Line_4,
        {ap}_prac.AddressLine5 AS {cp}_Address_Line_5,
        {ap}_prac.PostCode AS {cp}_Post_Code,
        {ap}_prac.NationalCode AS {cp}_National_Code
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN GenGPPractice {ap}_prac
            ON {ap}_prac.Code = {basetable}.{basecolumn}
    """.format(
        ap=internal_alias_prefix,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
    ))
    viewmaker.record_lookup_table_keyfield('GenGPPractice', 'Code')


def rio_add_gp_lookup_with_practice(viewmaker: ViewMaker,
                                    basecolumn: str,
                                    column_prefix: str,
                                    internal_alias_prefix: str) -> None:
    """
    Adds a GP-with-their-practice lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: ID column from the base table
        column_prefix: column prefix describing the kind of GP this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    if column_prefix:
        column_prefix += '_'
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}GP_Code,
        {ap}_gp.CodeDescription AS {cp}GP_Description,
        {ap}_gp.NationalCode AS {cp}GP_National_Code,
        {ap}_gp.Title AS {cp}GP_Title,
        {ap}_gp.Forename AS {cp}GP_Forename,
        {ap}_gp.Surname AS {cp}GP_Surname,
        {ap}_prac.Code AS {cp}Practice_Code,
        {ap}_prac.CodeDescription AS {cp}Practice_Description,
        {ap}_prac.AddressLine1 AS {cp}Practice_Address_Line_1,
        {ap}_prac.AddressLine2 AS {cp}Practice_Address_Line_2,
        {ap}_prac.AddressLine3 AS {cp}Practice_Address_Line_3,
        {ap}_prac.AddressLine4 AS {cp}Practice_Address_Line_4,
        {ap}_prac.AddressLine5 AS {cp}Practice_Address_Line_5,
        {ap}_prac.PostCode AS {cp}Practice_Post_Code,
        {ap}_prac.NationalCode AS {cp}Practice_National_Code
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            GenGP {ap}_gp
            INNER JOIN GenGPGPPractice  -- linking table
                ON GenGPPractice.GenGPCode = {ap}_gp.Code
            INNER JOIN GenGPPractice {ap}_prac
                ON {ap}_prac.Code = GenGPPractice.GenPracticeCode
        ) ON {ap}_gp.Code = {basetable}.{basecolumn}
    """.format(
        ap=internal_alias_prefix,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
    ))
    viewmaker.record_lookup_table_keyfields([
        ('GenGP', 'Code'),
        ('GenGPPractice', 'Code'),
        ('GenGPGPPractice', 'GenGPCode'),
    ])


def where_prognotes_current(viewmaker: ViewMaker) -> None:
    """
    Apply a WHERE clause restricting a progress notes table to current versions
    of progress notes only.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
    """
    configoptions = viewmaker.userobj  # type: RioViewConfigOptions
    if not configoptions.prognotes_current_only:
        return
    viewmaker.add_where(
        "({bt}.EnteredInError <> 1 OR {bt}.EnteredInError IS NULL) "
        "AND {bt}.{last_note_col} = 1".format(
            bt=viewmaker.basetable,
            last_note_col=CRATE_COL_LAST_NOTE))
    viewmaker.record_lookup_table_keyfield(viewmaker.basetable,
                                           'EnteredInError')
    viewmaker.enforce_same_n_rows_as_base = False
    # CRATE_COL_LAST_NOTE already indexed


def where_clindocs_current(viewmaker: ViewMaker) -> None:
    """
    Apply a WHERE clause restricting a clinical documents table to current
    versions of documents only.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
    """
    configoptions = viewmaker.userobj  # type: RioViewConfigOptions
    if not configoptions.clindocs_current_only:
        return
    viewmaker.add_where(
        "{bt}.{last_doc_col} = 1 AND {bt}.DeletedDate IS NULL".format(
            bt=viewmaker.basetable,
            last_doc_col=CRATE_COL_LAST_DOC))
    viewmaker.record_lookup_table_keyfield(viewmaker.basetable, 'DeletedDate')
    viewmaker.enforce_same_n_rows_as_base = False
    # CRATE_COL_LAST_DOC already indexed


def where_allergies_current(viewmaker: ViewMaker) -> None:
    """
    Apply a WHERE clause restricting an allergies table to current versions of
    records only.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
    """
    configoptions = viewmaker.userobj  # type: RioViewConfigOptions
    if not configoptions.allergies_current_only:
        return
    where_not_deleted_flag(viewmaker, 'Deleted')


def where_not_deleted_flag(viewmaker: ViewMaker, basecolumn: str) -> None:
    """
    Apply a WHERE clause restricting a table to "non-deleted" records only.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: name of column indicating "deleted" status
    """
    assert basecolumn, "Missing basecolumn"
    viewmaker.add_where(
        "({table}.{col} IS NULL OR {table}.{col} = 0)".format(
            table=viewmaker.basetable, col=basecolumn))
    viewmaker.record_lookup_table_keyfield(viewmaker.basetable, basecolumn)
    viewmaker.enforce_same_n_rows_as_base = False


def rio_add_bay_lookup(viewmaker: ViewMaker,
                       basecolumn_ward: str,
                       basecolumn_bay: str,
                       column_prefix: str,
                       internal_alias_prefix: str) -> None:
    """
    Adds a ward bed-bay lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn_ward: ward ID column from the base table
        basecolumn_bay: bay ID column from the base table
        column_prefix: column prefix describing the kind of GP this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn_ward, "Missing basecolumn_ward"
    assert basecolumn_bay, "Missing basecolumn_bay"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    if column_prefix:
        column_prefix += '_'
    viewmaker.add_select("""
        {basetable}.{basecolumn_ward} AS {cp}Ward_Code,
        {ap}_ward.WardDescription AS {cp}Ward_Description,
        {basetable}.{basecolumn_bay} AS {cp}Bay_Code,
        {ap}_bay.BayDescription AS {cp}Bay_Description
    """.format(
        basetable=viewmaker.basetable,
        basecolumn_ward=basecolumn_ward,
        basecolumn_bay=basecolumn_bay,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            ImsBay {ap}_bay
            INNER JOIN ImsWard {ap}_ward
                ON {ap}_ward.WardCode = {ap}_bay.WardCode
        ) ON {ap}_bay.WardCode = {basetable}.{basecolumn_ward}
            AND {ap}_bay.BayCode = {basetable}.{basecolumn_bay}
    """.format(
        ap=internal_alias_prefix,
        basetable=viewmaker.basetable,
        basecolumn_ward=basecolumn_ward,
        basecolumn_bay=basecolumn_bay,
    ))
    viewmaker.record_lookup_table_keyfield('ImsBay', ['WardCode', 'BayCode'])
    viewmaker.record_lookup_table_keyfield('ImsWard', ['WardCode'])


def rio_add_location_lookup(viewmaker: ViewMaker,
                            basecolumn: str,
                            column_prefix: str,
                            internal_alias_prefix: str) -> None:
    """
    Adds a location (institutional address) lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: ID column from the base table
        column_prefix: column prefix describing the kind of location this is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert column_prefix, "Missing column_prefix"
    assert internal_alias_prefix, "Missing internal_alias_prefix"
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_Code,
        {ap}_loc.CodeDescription AS {cp}_Description,
        {ap}_loc.NationalCode AS {cp}_National_Code,
        {ap}_loc.AddressLine1 as {cp}_Address_1,
        {ap}_loc.AddressLine2 as {cp}_Address_2,
        {ap}_loc.AddressLine3 as {cp}_Address_3,
        {ap}_loc.AddressLine4 as {cp}_Address_4,
        {ap}_loc.AddressLine5 as {cp}_Address_5,
        {ap}_loc.Postcode as {cp}_Post_Code,
        {ap}_loc.LocationType as {cp}_Type_Code,
        {ap}_loctype.CodeDescription as {cp}_Type_Description,
        {ap}_loctype.NationalCode as {cp}_Type_National_Code
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            GenLocation {ap}_loc
            INNER JOIN GenLocationType {ap}_loctype
                ON {ap}_loctype.Code = {ap}_loc.LocationType
        ) ON {ap}_loc.Code = {basetable}.{basecolumn}
    """.format(  # noqa
        ap=internal_alias_prefix,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
    ))
    viewmaker.record_lookup_table_keyfield('GenLocation', ['Code'])
    viewmaker.record_lookup_table_keyfield('GenLocationType', ['Code'])


def rio_add_org_contact_lookup(viewmaker: ViewMaker,
                               basecolumn: str,
                               column_prefix: str,
                               internal_alias_prefix: str) -> None:
    """
    Adds an organisation lookup.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: ID column from the base table
        column_prefix: column prefix describing the kind of organisation this
            is
        internal_alias_prefix: prefix to add to the lookup table's name to
            make it unique, in case the SELECT statement uses the same lookup
            table more than once
    """
    assert basecolumn, "Missing basecolumn"
    assert column_prefix, "Missing column_prefix"
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_ID,
        {ap}_con.ContactType AS {cp}_Contact_Type_Code,
        {ap}_ct.CodeDescription AS {cp}_Contact_Type_Description,
        {ap}_ct.NationalCode AS {cp}_Contact_Type_National_Code,
        {ap}_con.Title AS {cp}_Title,
        {ap}_con.FirstName AS {cp}_First_Name,
        {ap}_con.Surname AS {cp}_Surname,
        {ap}_con.JobTitle AS {cp}_Job_Title,
        {ap}_con.MainPhoneNo AS {cp}_Main_Phone_Number,
        {ap}_con.OtherPhoneNo AS {cp}_Other_Phone_Number,
        {ap}_con.FaxNo AS {cp}_Fax_Number,
        {ap}_con.EmailAddress AS {cp}_Email_Address,
        {ap}_con.Comments AS {cp}_Comments,
        {ap}_con.OrganisationID AS {cp}_Organisation_ID,
        {ap}_org.OrganisationCode AS {cp}_Organisation_Code,
        {ap}_org.OrganisationName AS {cp}_Organisation_Name,
        {ap}_org.OrganisationType AS {cp}_Organisation_Type_Code,
        {ap}_orgtype.CodeDescription AS {cp}_Organisation_Type_Description,
        {ap}_org.DepartmentName AS {cp}_Organisation_Department_Name,
        {ap}_org.MainPhoneNo AS {cp}_Organisation_Main_Phone_Number,
        {ap}_org.OtherPhoneNo AS {cp}_Organisation_Other_Phone_Number,
        {ap}_org.FaxNo AS {cp}_Organisation_Fax_Number,
        {ap}_org.EmailAddress AS {cp}_Organisation_Email_Address,
        {ap}_org.AddressLine1 AS {cp}_Organisation_Address_Line_1,
        {ap}_org.AddressLine2 AS {cp}_Organisation_Address_Line_2,
        {ap}_org.AddressLine3 AS {cp}_Organisation_Address_Line_3,
        {ap}_org.AddressLine4 AS {cp}_Organisation_Address_Line_4,
        {ap}_org.AddressLine5 AS {cp}_Organisation_Address_Line_5,
        {ap}_org.PostCode AS {cp}_Organisation_Post_Code
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    # Phone/fax/email/comments not in RCEP
    viewmaker.add_from("""
        LEFT JOIN (
            OrgContact {ap}_con
            INNER JOIN OrgContactType {ap}_ct
                ON {ap}_ct.Code = {ap}_con.ContactType
            INNER JOIN OrgOrganisation {ap}_org
                ON {ap}_org.SequenceID = {ap}_con.OrganisationID  -- ?
            INNER JOIN OrgType {ap}_orgtype
                ON {ap}_orgtype.Code = {ap}_org.OrganisationType
        ) ON {ap}_con.OrganisationID = {basetable}.{basecolumn}
    """.format(
        ap=internal_alias_prefix,
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
    ))
    viewmaker.record_lookup_table_keyfields([
        ('OrgContact', 'OrganisationID'),
        ('OrgContactType', 'Code'),
        ('OrgOrganisation', 'SequenceID'),
        ('OrgType', 'Code'),
    ])


def rio_amend_standard_noncore(viewmaker: ViewMaker) -> None:
    """
    Modifies a standard RiO "non-core" table (a table defined by the using
    institution -- e.g. CPFT "Core Assessment" tables...).

    - Adds a user lookup on ``type12_UpdatedBy``.
    - Omits deleted records based on ``type12_DeletedDate``.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
    """
    # Add user:
    rio_add_user_lookup(viewmaker, "type12_UpdatedBy",
                        column_prefix="Updated_By", internal_alias_prefix="ub")
    # Omit deleted:
    viewmaker.add_where("{bt}.type12_DeletedDate IS NULL".format(
        bt=viewmaker.basetable))
    viewmaker.record_lookup_table_keyfield(viewmaker.basetable,
                                           'type12_DeletedDate')
    viewmaker.enforce_same_n_rows_as_base = False


def rio_noncore_yn(viewmaker: ViewMaker,
                   basecolumn: str,
                   result_alias: str) -> None:
    """
    Modifies a standard RiO "non-core" table to map a field using "1 = yes,
    2 = no" encoding to a more conventional Boolean (1 = yes, 0 = no).

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified
        basecolumn: column name in the base table
        result_alias: what to call the result
    """
    # 1 = yes, 2 = no
    # ... clue: "pregnant?" for males, in UserAssesstfkcsa.expectQ
    assert basecolumn, "Missing basecolumn"
    assert result_alias, "Missing result_alias"
    viewmaker.add_select(
        "CASE "
        "WHEN {basetable}.{basecolumn} = 1 THEN 1 "  # 1 = yes
        "WHEN {basetable}.{basecolumn} = 2 THEN 0 "  # 2 = no
        "ELSE NULL "
        "END "
        "AS {result_alias}".format(
            basetable=viewmaker.basetable,
            basecolumn=basecolumn,
            result_alias=result_alias,
        )
    )


def rio_add_audit_info(viewmaker: ViewMaker) -> None:
    """
    Modifies a RiO view to add audit information.

    Args:
        viewmaker: :class:`crate_anon.common.sql.ViewMaker`; will be modified

    - In RCEP: lots of tables have Created_Date, Updated_Date with no source
      column; likely from the audit table.

    - Here, we call them: Audit_Created_Date, Audit_Updated_Date
    """
    ap1 = "_au_cr"
    ap2 = "_au_up"
    viewmaker.add_select("""
        {ap1}_subq.Audit_Created_Date AS Audit_Created_Date,
        {ap2}_subq.Audit_Updated_Date AS Audit_Updated_Date
    """.format(
        ap1=ap1,
        ap2=ap2,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            SELECT {ap1}_audit.RowID,
                MIN({ap1}_audit.ActionDateTime) AS Audit_Created_Date
            FROM AuditTrail {ap1}_audit
            INNER JOIN GenTable {ap1}_table
                ON {ap1}_table.TableNumber = {ap1}_audit.TableNumber
            WHERE {ap1}_table.GenTableCode = {literal}
                AND {ap1}_audit.AuditAction = 2  -- INSERT
            GROUP BY {ap1}_audit.RowID
        ) {ap1}_subq
            ON {ap1}_subq.RowID = {basetable}.{CRATE_COL_PK}
        LEFT JOIN (
            SELECT {ap2}_audit.RowID,
                MAX({ap2}_audit.ActionDateTime) AS Audit_Updated_Date
            FROM AuditTrail {ap2}_audit
            INNER JOIN GenTable {ap2}_table
                ON {ap2}_table.TableNumber = {ap2}_audit.TableNumber
            WHERE {ap2}_table.GenTableCode = {literal}
                AND {ap2}_audit.AuditAction = 3  -- UPDATE
            GROUP BY {ap2}_audit.RowID
        ) {ap2}_subq
            ON {ap2}_subq.RowID = {basetable}.{CRATE_COL_PK}
    """.format(
        ap1=ap1,
        ap2=ap2,
        basetable=viewmaker.basetable,
        literal=sql_string_literal(viewmaker.basetable),
        CRATE_COL_PK=CRATE_COL_PK,
    ))
    viewmaker.record_lookup_table_keyfields([
        ('AuditTrail', ['AuditAction', 'RowID', 'TableNumber']),
        ('GenTable', 'GenTableCode'),
    ])
    # AuditTrail indexes based on SQL Server recommendations (Query -> Analyze
    # Query in Database Engine Tuning Advisor -> ... -> Recommendations ->
    # Index Recommendations -> Definition). Specifically:
    # CREATE STATISTICS [_dta_stat_1213247377_6_4] ON [dbo].[AuditTrail](
    #     [TableNumber], [AuditAction])
    # CREATE STATISTICS [_dta_stat_1213247377_5_4] ON [dbo].[AuditTrail](
    #     [RowID], [AuditAction])
    # CREATE NONCLUSTERED INDEX [_dta_index_AuditTrail_blahblah]
    #     ON [dbo].[AuditTrail]
    # (
    #   [AuditAction] ASC,
    #   [RowID] ASC,
    #   [TableNumber] ASC
    # )
    # INCLUDE ( [ActionDateTime]) WITH (SORT_IN_TEMPDB = OFF,
    #     IGNORE_DUP_KEY = OFF, DROP_EXISTING = OFF, ONLINE = OFF) ON [PRIMARY]
