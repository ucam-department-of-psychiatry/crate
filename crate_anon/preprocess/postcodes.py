#!/usr/bin/env python

"""
crate_anon/preprocess/postcodes.py

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

**Fetches UK postcode information and creates a database.**

Code-Point Open, CSV, GB

- https://www.ordnancesurvey.co.uk/business-and-government/products/opendata-products.html
- https://www.ordnancesurvey.co.uk/business-and-government/products/code-point-open.html
- https://www.ordnancesurvey.co.uk/opendatadownload/products.html
- http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

Office for National Statistics Postcode Database (ONSPD):

- https://geoportal.statistics.gov.uk/geoportal/catalog/content/filelist.page
- e.g. ONSPD_MAY_2016_csv.zip
- http://www.ons.gov.uk/methodology/geography/licences

Background:

- OA = Output Area

  - smallest: >=40 households, >=100 people
  - 181,408 OAs in England & Wales

- LSOA = Lower Layer Super Output Area

  - 34,753 LSOAs in England & Wales

- MSOA = Middle Layer Super Output Area

  - 7,201 MSOAs in England & Wales

- WZ = Workplace Zone

  - https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography#workplace-zone-wz

- https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography#output-area-oa

"""  # noqa

from abc import ABC, ABCMeta, abstractmethod
import argparse
import csv
import datetime
import logging
import os
import sys
# import textwrap
from typing import (Any, Dict, Generator, Iterable, List, Optional, TextIO,
                    Tuple)

from cardinal_pythonlib.argparse_func import RawDescriptionArgumentDefaultsHelpFormatter  # noqa
from cardinal_pythonlib.dicts import rename_key
from cardinal_pythonlib.extract_text import wordwrap
from cardinal_pythonlib.fileops import find_first
from cardinal_pythonlib.logs import configure_logger_for_colour
import openpyxl
from openpyxl.cell.cell import Cell
import prettytable
from sqlalchemy import (
    Column,
    create_engine,
    Date,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import MetaData, Table
import xlrd

from crate_anon.anonymise.constants import CHARSET, TABLE_KWARGS

log = logging.getLogger(__name__)
metadata = MetaData()

DEFAULT_ONSPD_DIR = os.path.join(
    os.path.expanduser("~"), "dev", "ons", "ONSPD_Nov2019")
DEFAULT_REPORT_EVERY = 1000
DEFAULT_COMMIT_EVERY = 10000
YEAR_MONTH_FMT = "%Y%m"

CODE_LEN = 9  # many ONSPD codes have this length
NAME_LEN = 80  # seems about right; a bit more than the length of many


# =============================================================================
# Ancillary functions
# =============================================================================

def convert_date(d: Dict[str, Any], key: str) -> None:
    """
    Modifies ``d[key]``, if it exists, to convert it to a
    :class:`datetime.datetime` or ``None``.

    Args:
        d: dictionary
        key: key
    """
    if key not in d:
        return
    value = d[key]
    if value:
        d[key] = datetime.datetime.strptime(value,
                                            YEAR_MONTH_FMT)
    else:
        d[key] = None


def convert_int(d: Dict[str, Any], key: str) -> None:
    """
    Modifies ``d[key]``, if it exists, to convert it to an int or ``None``.

    Args:
        d: dictionary
        key: key
    """
    if key not in d:
        return
    value = d[key]
    if value is None or (isinstance(value, str) and not value.strip()):
        d[key] = None
    else:
        d[key] = int(value)


def convert_float(d: Dict[str, Any], key: str) -> None:
    """
    Modifies ``d[key]``, if it exists, to convert it to a float or ``None``.

    Args:
        d: dictionary
        key: key
    """
    if key not in d:
        return
    value = d[key]
    if value is None or (isinstance(value, str) and not value.strip()):
        d[key] = None
    else:
        d[key] = float(value)


def values_from_row(row: Iterable[Cell]) -> List[Any]:
    """
    Returns all values from a spreadsheet row.

    For the ``openpyxl`` interface to XLSX files.
    """
    values = []  # type: List[Any]
    for cell in row:
        values.append(cell.value)
    return values


def commit_and_announce(session: Session) -> None:
    """
    Commits an SQLAlchemy ORM session and says so.
    """
    log.info("COMMIT")
    session.commit()


# =============================================================================
# Extend SQLAlchemy Base class
# =============================================================================

class ExtendedBase(object):
    """
    Mixin to extend the SQLAlchemy ORM Base class by specifying table creation
    parameters (specifically, for MySQL, to set the character set and
    MySQL engine).

    Only used in the creation of Base; everything else then inherits from Base
    as usual.

    See
    http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html
    """
    __table_args__ = TABLE_KWARGS


Base = declarative_base(metadata=metadata, cls=ExtendedBase)


# =============================================================================
# Go to considerable faff to provide type hints for lookup classes
# =============================================================================

class GenericLookupClassMeta(DeclarativeMeta, ABCMeta):
    """
    To avoid: "TypeError: metaclass conflict: the metaclass of a derived class
    must be a (non-strict) subclass of the metaclasses of all its bases".

    We want a class that's a subclass of Base and ABC. So we can work out their
    metaclasses:

    .. code-block:: python

        from abc import ABC
        from sqlalchemy.ext.declarative import declarative_base
        from sqlalchemy.sql.schema import MetaData

        class ExtendedBase(object):
            __table_args__ = {'mysql_charset': 'utf8', 'mysql_engine': 'InnoDB'}

        metadata = MetaData()
        Base = declarative_base(metadata=metadata, cls=ExtendedBase)

        type(Base)  # metaclass of Base: <class: 'sqlalchemy.ext.declarative.api.DeclarativeMeta'>
        type(ABC)  # metaclass of ABC: <class 'abc.ABCMeta'>

    and thus define this class to inherit from those two metaclasses, so it can
    be the metaclass we want.

    """  # noqa
    pass


class GenericLookupClassType(Base, ABC, metaclass=GenericLookupClassMeta):
    """
    Type hint for our various simple lookup classes.

    Alternatives that don't work: Type[Base], Type[BASETYPE], type(Base).
    """
    __abstract__ = True  # abstract as seen by SQLAlchemy
    # ... avoids SQLAlchemy error: "sqlalchemy.exc.InvalidRequestError: Class
    # <class '__main__.GenericLookupClassType'> does not have a __table__ or
    # __tablename__ specified and does not inherit from an existing
    # table-mapped class."

    @abstractmethod
    def __call__(self, *args, **kwargs) -> None:
        # Represents __init__... not sure I have this quite right, but it
        # appeases PyCharm; see populate_generic_lookup_table()
        pass

    @property
    @abstractmethod
    def __table__(self) -> Table:
        pass

    @property
    @abstractmethod
    def __tablename__(self) -> str:
        pass

    @property
    @abstractmethod
    def __filename__(self) -> str:
        pass


# =============================================================================
# Models: all postcodes
# =============================================================================

class Postcode(Base):
    """
    Maps individual postcodes to... lots of things. Large table.
    """
    __tablename__ = 'postcode'

    pcd_nospace = Column(
        String(8), primary_key=True,
        comment="Postcode (no spaces)")
    # ... not in original, but simplifies indexing
    pcd = Column(
        String(7), index=True, unique=True,
        comment="Unit postcode (7 characters): 2-4 char outward code, "
                "left-aligned; 3-char inward code, right-aligned")
    pcd2 = Column(
        String(8), index=True, unique=True,
        comment="Unit postcode (8 characters): 2-4 char outward code, "
                "left-aligned; space; 3-char inward code, right-aligned")
    pcds = Column(
        String(8), index=True, unique=True,
        comment="Unit postcode (variable length): 2-4 char outward "
                "code; space; 3-char inward code")
    dointr = Column(
        Date,
        comment="Date of introduction (original format YYYYMM)")
    doterm = Column(
        Date,
        comment="Date of termination (original format YYYYMM) or NULL")
    oscty = Column(
        String(CODE_LEN),
        comment="County code [FK to county_england_2010.county_code]")
    oslaua = Column(
        String(CODE_LEN),
        comment="Local authority district (LUA), unitary  authority "
                "(UA), metropolitan district (MD), London borough (LB),"
                " council area (CA), or district council area (DCA) "
                "[FK to lad_local_authority_district_2019.lad_code]")
    osward = Column(
        String(CODE_LEN),
        comment="Electoral ward/division "
                "[FK e.g. to electoral_ward_2019.ward_code]")
    usertype = Column(
        Integer,
        comment="Small (0) or large (1) postcode user")
    oseast1m = Column(
        Integer,
        comment="National grid reference Easting, 1m resolution")
    osnrth1m = Column(
        Integer,
        comment="National grid reference Northing, 1m resolution")
    osgrdind = Column(
        Integer,
        comment="Grid reference positional quality indicator")
    oshlthau = Column(
        String(CODE_LEN),
        comment="Former (up to 2013) Strategic Health Authority (SHA), Local "
                "Health Board (LHB), Health Board (HB), Health Authority "
                "(HA), or Health & Social Care Board (HSCB) [FK to one of: "
                "sha_strategic_health_authority_england_2010.sha_code or "
                "sha_strategic_health_authority_england_2004.sha_code; "
                "hb_health_board_n_ireland_2003.hb_code; "
                "hb_health_board_scotland_2014.hb_code; "
                "hscb_health_social_care_board_n_ireland_2010.hscb_code; "
                "lhb_local_health_board_wales_2014.lhb_code or "
                "lhb_local_health_board_wales_2006.lhb_code]")
    ctry = Column(
        String(CODE_LEN),
        comment="Country of the UK [England, Scotland, Wales, "
                "Northern Ireland] [FK to country_2012.country_code]")
    streg = Column(
        Integer,
        comment="Standard (Statistical) Region (SSR) [FK to "
                "ssr_standard_statistical_region_1995."
                "ssr_code]")
    pcon = Column(
        String(CODE_LEN),
        comment="Westminster parliamentary constituency [FK to "
                "pcon_westminster_parliamentary_constituency_2014."
                "pcon_code]")
    eer = Column(
        String(CODE_LEN),
        comment="European Electoral Region (EER) [FK to "
                "eer_european_electoral_region_2010.eer_code]")
    teclec = Column(
        String(CODE_LEN),
        comment="Local Learning and Skills Council (LLSC) / Dept. of "
                "Children, Education, Lifelong Learning and Skills (DCELLS) / "
                "Enterprise Region (ER) [PROBABLY FK to one of: "
                "dcells_dept_children_wales_2010.dcells_code; "
                "er_enterprise_region_scotland_2010.er_code; "
                "llsc_local_learning_skills_council_england_2010.llsc_code]")
    ttwa = Column(
        String(CODE_LEN),
        comment="Travel to Work Area (TTWA) [FK to "
                "ttwa_travel_to_work_area_2011.ttwa_code]")
    pct = Column(
        String(CODE_LEN),
        comment="Primary Care Trust (PCT) / Care Trust / "
                "Care Trust Plus (CT) / Local Health Board (LHB) / "
                "Community Health Partnership (CHP) / "
                "Local Commissioning Group (LCG) / "
                "Primary Healthcare Directorate (PHD) [FK to one of: "
                "pct_primary_care_trust_2019.pct_code; "
                "chp_community_health_partnership_scotland_2012.chp_code; "
                "lcg_local_commissioning_group_n_ireland_2010.lcg_code; "
                "lhb_local_health_board_wales_2014.lhb_code]")
    nuts = Column(
        String(10),
        comment="LAU2 areas [European Union spatial regions; Local "
                "Adminstrative Unit, level 2] / Nomenclature of Units "
                "for Territorial Statistics (NUTS) [FK to "
                "lau_eu_local_administrative_unit_2019.lau2_code]")
    statsward = Column(
        String(6),
        comment="2005 'statistical' ward [?FK to "
                "electoral_ward_2005.ward_code]")
    oa01 = Column(
        String(10),
        comment="2001 Census Output Area (OA). (There are "
                "about 222,000, so ~300 population?)")
    casward = Column(
        String(6),
        comment="Census Area Statistics (CAS) ward [PROBABLY FK to "
                "cas_ward_2003.cas_ward_code]")
    park = Column(
        String(CODE_LEN),
        comment="National park [FK to "
                "park_national_park_2016.park_code]")
    lsoa01 = Column(
        String(CODE_LEN),
        comment="2001 Census Lower Layer Super Output Area (LSOA) [England & "
                "Wales, ~1,500 population] / Data Zone (DZ) [Scotland] / "
                "Super Output Area (SOA) [FK to one of: "
                "lsoa_lower_layer_super_output_area_england_wales_2004.lsoa_code; "  # noqa
                "lsoa_lower_layer_super_output_area_n_ireland_2005.lsoa_code]")
    msoa01 = Column(
        String(CODE_LEN),
        comment="2001 Census Middle Layer Super Output Area (MSOA) [England & "
                "Wales, ~7,200 population] / "
                "Intermediate Zone (IZ) [Scotland] [FK to one of: "
                "msoa_middle_layer_super_output_area_england_wales_2004.msoa_code; "  # noqa
                "iz_intermediate_zone_scotland_2005.iz_code]")
    ur01ind = Column(
        String(1),
        comment="2001 Census urban/rural indicator [numeric in "
                "England/Wales/Scotland; letters in N. Ireland]")
    oac01 = Column(
        String(3),
        comment="2001 Census Output Area classification (OAC)"
                "[POSSIBLY FK to output_area_classification_2011."
                "subgroup_code]")
    oa11 = Column(
        String(CODE_LEN),
        comment="2011 Census Output Area (OA) [England, Wales, Scotland;"
                " ~100-625 population] / Small Area (SA) [N. Ireland]")
    lsoa11 = Column(
        String(CODE_LEN),
        comment="2011 Census Lower Layer Super Output Area (LSOA) [England & "
                "Wales, ~1,500 population] / Data Zone (DZ) [Scotland] / "
                "Super Output Area (SOA) [N. Ireland] [FK to one of: "
                "lsoa_lower_layer_super_output_area_2011.lsoa_code; "  # noqa
                " (defunct) dz_datazone_scotland_2011.dz_code]")
    msoa11 = Column(
        String(CODE_LEN),
        comment="2011 Census Middle Layer Super Output Area (MSOA) [England & "
                "Wales, ~7,200 population] / "
                "Intermediate Zone (IZ) [Scotland] [FK to one of: "
                "msoa_middle_layer_super_output_area_2011.msoa_code; "  # noqa
                "iz_intermediate_zone_scotland_2011.iz_code]")
    parish = Column(
        String(CODE_LEN),
        comment="Parish/community [FK to "
                "parish_ncp_england_wales_2018.parish_code]")
    wz11 = Column(
        String(CODE_LEN),
        comment="2011 Census Workplace Zone (WZ)")
    ccg = Column(
        String(CODE_LEN),
        comment="Clinical Commissioning Group (CCG) / Local Health Board "
                "(LHB) / Community Health Partnership (CHP) / Local "
                "Commissioning Group (LCG) / Primary Healthcare Directorate "
                "(PHD) [FK to one of: "
                "ccg_clinical_commissioning_group_uk_2019."
                "ccg_ons_code, lhb_local_health_board_wales_2014.lhb_code]")
    bua11 = Column(
        String(CODE_LEN),
        comment="Built-up Area (BUA) [FK to "
                "bua_built_up_area_uk_2013.bua_code]")
    buasd11 = Column(
        String(CODE_LEN),
        comment="Built-up Area Sub-division (BUASD) [FK to "
                "buasd_built_up_area_subdivision_uk_2013.buas_code]")
    ru11ind = Column(
        String(2),
        comment="2011 Census rural-urban classification")
    oac11 = Column(
        String(3),
        comment="2011 Census Output Area classification (OAC) [FK to "
                "output_area_classification_2011.subgroup_code]")
    lat = Column(
        Numeric(precision=9, scale=6),
        comment="Latitude (degrees, 6dp)")
    long = Column(
        Numeric(precision=9, scale=6),
        comment="Longitude (degrees, 6dp)")
    lep1 = Column(
        String(CODE_LEN),
        comment="Local Enterprise Partnership (LEP) - first instance [FK to "
                "lep_local_enterprise_partnership_england_2017.lep1_code]")
    lep2 = Column(
        String(CODE_LEN),
        comment="Local Enterprise Partnership (LEP) - second instance [FK to "
                "lep_local_enterprise_partnership_england_2017.lep1_code]")
    pfa = Column(
        String(CODE_LEN),
        comment="Police Force Area (PFA) [FK to "
                "pfa_police_force_area_2015.pfa_code]")
    imd = Column(
        Integer,
        comment="Index of Multiple Deprivation (IMD) [rank of LSOA/DZ, where "
                "1 is the most deprived, within each country] [FK to one of: "
                "imd_index_multiple_deprivation_england_2015.imd_rank; "
                "imd_index_multiple_deprivation_n_ireland_2010.imd_rank; "
                "imd_index_multiple_deprivation_scotland_2012.imd_rank; "
                "imd_index_multiple_deprivation_wales_2014.imd_rank]")

    # New in Nov 2019 ONSPD, relative to 2016 ONSPD:
    # ** Not yet implemented:
    # calncv
    # ced
    # nhser
    # rgn
    # stp

    def __init__(self, **kwargs: Any) -> None:
        convert_date(kwargs, 'dointr')
        convert_date(kwargs, 'doterm')
        convert_int(kwargs, 'usertype')
        convert_int(kwargs, 'oseast1m')
        convert_int(kwargs, 'osnrth1m')
        convert_int(kwargs, 'osgrdind')
        convert_int(kwargs, 'streg')
        convert_int(kwargs, 'edind')
        convert_int(kwargs, 'imd')
        kwargs['pcd_nospace'] = kwargs['pcd'].replace(" ", "")
        super().__init__(**kwargs)


# =============================================================================
# Models: core lookup tables
# =============================================================================

class OAClassification(Base):
    """
    Represents 2011 Census Output Area (OA) classification names/codes.
    """
    __filename__ = "2011 Census Output Area Classification Names and Codes " \
                   "UK.xlsx"
    __tablename__ = "output_area_classification_2011"

    oac11 = Column(String(3), primary_key=True)
    supergroup_code = Column(String(1))
    supergroup_desc = Column(String(35))
    group_code = Column(String(2))
    group_desc = Column(String(40))
    subgroup_code = Column(String(3))
    subgroup_desc = Column(String(60))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'OAC11', 'oac11')
        rename_key(kwargs, 'Supergroup', 'supergroup_desc')
        rename_key(kwargs, 'Group', 'group_desc')
        rename_key(kwargs, 'Subgroup', 'subgroup_desc')
        kwargs['supergroup_code'] = kwargs['oac11'][0:1]
        kwargs['group_code'] = kwargs['oac11'][0:2]
        kwargs['subgroup_code'] = kwargs['oac11']
        super().__init__(**kwargs)


class BUA(Base):
    """
    Represents England & Wales 2013 build-up area (BUA) codes/names.
    """
    __filename__ = "BUA_names and codes UK as at 12_13.xlsx"
    __tablename__ = "bua_built_up_area_uk_2013"

    bua_code = Column(String(CODE_LEN), primary_key=True)
    bua_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'BUA13CD', 'bua_code')
        rename_key(kwargs, 'BUA13NM', 'bua_name')
        super().__init__(**kwargs)


class BUASD(Base):
    """
    Represents built-up area subdivisions (BUASD) in England & Wales 2013.
    """
    __filename__ = "BUASD_names and codes UK as at 12_13.xlsx"
    __tablename__ = "buasd_built_up_area_subdivision_uk_2013"

    buasd_code = Column(String(CODE_LEN), primary_key=True)
    buasd_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'BUASD13CD', 'buasd_code')
        rename_key(kwargs, 'BUASD13NM', 'buasd_name')
        super().__init__(**kwargs)


class CASWard(Base):
    """
    Represents censua area statistics (CAS) wards in the UK, 2003.

    - https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography#statistical-wards-cas-wards-and-st-wards
    """  # noqa
    __filename__ = "CAS ward names and codes UK as at 01_03.xlsx"
    __tablename__ = "cas_ward_2003"

    cas_ward_code = Column(String(CODE_LEN), primary_key=True)
    cas_ward_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'WDCAS03CD', 'cas_ward_code')
        rename_key(kwargs, 'WDCAS03NM', 'cas_ward_name')
        super().__init__(**kwargs)


class CCG(Base):
    """
    Represents clinical commissioning groups (CCGs), UK 2019.
    """
    __filename__ = "CCG names and codes UK as at 04_19.xlsx"
    __tablename__ = "ccg_clinical_commissioning_group_uk_2019"

    ccg_ons_code = Column(String(CODE_LEN), primary_key=True)
    ccg_ccg_code = Column(String(9))
    ccg_name = Column(String(NAME_LEN))
    ccg_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'CCG19CD', 'ccg_ons_code')
        rename_key(kwargs, 'CCG19CDH', 'ccg_ccg_code')
        rename_key(kwargs, 'CCG19NM', 'ccg_name')
        rename_key(kwargs, 'CCG19NMW', 'ccg_name_welsh')
        super().__init__(**kwargs)


class Country(Base):
    """
    Represents UK countries, 2012.

    This is not a long table.
    """
    __filename__ = "Country names and codes UK as at 08_12.xlsx"
    __tablename__ = "country_2012"

    country_code = Column(String(CODE_LEN), primary_key=True)
    country_code_old = Column(Integer)  # ?
    country_name = Column(String(NAME_LEN))
    country_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'CTRY12CD', 'country_code')
        rename_key(kwargs, 'CTRY12CDO', 'country_code_old')
        rename_key(kwargs, 'CTRY12NM', 'country_name')
        rename_key(kwargs, 'CTRY12NMW', 'country_name_welsh')
        super().__init__(**kwargs)


class County2019(Base):
    """
    Represents counties, UK 2019.
    """
    __filename__ = "County names and codes UK as at 04_19.xlsx"
    __tablename__ = "county_england_2010"

    county_code = Column(String(CODE_LEN), primary_key=True)
    county_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'CTY19CD', 'county_code')
        rename_key(kwargs, 'CTY19NM', 'county_name')
        super().__init__(**kwargs)


class EER(Base):
    """
    Represents European electoral regions (EERs), UK 2010.
    """
    __filename__ = "EER names and codes UK as at 12_10.xlsx"
    __tablename__ = "eer_european_electoral_region_2010"

    eer_code = Column(String(CODE_LEN), primary_key=True)
    eer_code_old = Column(String(2))  # ?
    eer_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'EER10CD', 'eer_code')
        rename_key(kwargs, 'EER10CDO', 'eer_code_old')
        rename_key(kwargs, 'EER10NM', 'eer_name')
        super().__init__(**kwargs)


class IMDLookupEN(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), England 2015.

    **This is quite an important one to us!** IMDs are mapped to LSOAs; see
    e.g. :class:`LSOAEW2011`.
    """
    __filename__ = "IMD lookup EN as at 12_15.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_england_2015"

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LSOA11CD', 'lsoa_code')
        rename_key(kwargs, 'LSOA11NM', 'lsoa_name')
        rename_key(kwargs, 'IMD15', 'imd_rank')
        convert_int(kwargs, 'imd_rank')
        super().__init__(**kwargs)


class IMDLookupSC(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Scotland 2016.
    """
    __filename__ = "IMD lookup SC as at 12_16.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_scotland_2016"

    dz_code = Column(String(CODE_LEN), primary_key=True)
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'DZ11CD', 'dz_code')
        rename_key(kwargs, 'IMD16', 'imd_rank')
        convert_int(kwargs, 'imd_rank')
        super().__init__(**kwargs)


class IMDLookupWA(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Wales 2014.
    """
    __filename__ = "IMD lookup WA as at 12_14.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_wales_2014"

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LSOA11CD', 'lsoa_code')
        rename_key(kwargs, 'LSOA11NM', 'lsoa_name')
        rename_key(kwargs, 'IMD14', 'imd_rank')
        convert_int(kwargs, 'imd_rank')
        super().__init__(**kwargs)


class LAU(Base):
    """
    Represents European Union Local Administrative Units (LAUs), UK 2019.
    """
    __filename__ = "LAU2 names and codes UK as at 12_19 (NUTS).xlsx"
    __tablename__ = "lau_eu_local_administrative_unit_2019"

    lau2_code = Column(String(10), primary_key=True)
    lau2_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LAU219CD', 'lau2_code')
        rename_key(kwargs, 'LAU219NM', 'lau2_name')
        super().__init__(**kwargs)


class LAD(Base):
    """
    Represents local authority districts (LADs), UK 2019.
    """
    __filename__ = "LA_UA names and codes UK as at 12_19.xlsx"
    __tablename__ = "lad_local_authority_district_2019"

    lad_code = Column(String(CODE_LEN), primary_key=True)
    lad_name = Column(String(NAME_LEN))
    lad_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LAD19CD', 'lad_code')
        rename_key(kwargs, 'LAD19NM', 'lad_name')
        rename_key(kwargs, 'LAD19NMW', 'lad_name_welsh')
        super().__init__(**kwargs)


class LEP(Base):
    """
    Represents Local Enterprise Partnerships (LEPs), England 2017.
    """
    __filename__ = "LEP names and codes EN as at 04_17 v2.xlsx"
    __tablename__ = "lep_local_enterprise_partnership_england_2017"
    # __debug_content__ = True

    lep_code = Column(String(CODE_LEN), primary_key=True)
    lep_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LEP17CD', 'lep_code')
        rename_key(kwargs, 'LEP17NM', 'lep_name')
        super().__init__(**kwargs)


class LSOA2011(Base):
    """
    Represents lower layer super output area (LSOAs), UK 2011.

    **This is quite an important one.** LSOAs map to IMDs; see
    :class:`IMDLookupEN`.
    """
    __filename__ = "LSOA (2011) names and codes UK as at 12_12.xlsx"
    __tablename__ = "lsoa_lower_layer_super_output_area_2011"

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LSOA11CD', 'lsoa_code')
        rename_key(kwargs, 'LSOA11NM', 'lsoa_name')
        super().__init__(**kwargs)


class MSOA2011(Base):
    """
    Represents middle layer super output areas (MSOAs), UK 2011.
    """
    __filename__ = "MSOA (2011) names and codes UK as at 12_12.xlsx"
    __tablename__ = "msoa_middle_layer_super_output_area_2011"

    msoa_code = Column(String(CODE_LEN), primary_key=True)
    msoa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'MSOA11CD', 'msoa_code')
        rename_key(kwargs, 'MSOA11NM', 'msoa_name')
        super().__init__(**kwargs)


class NationalPark(Base):
    """
    Represents national parks, Great Britain 2016.
    """
    __filename__ = "National Park names and codes GB as at 08_16.xlsx"
    __tablename__ = "park_national_park_2016"

    park_code = Column(String(CODE_LEN), primary_key=True)
    park_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'NPARK16CD', 'park_code')
        rename_key(kwargs, 'NPARK16NM', 'park_name')
        super().__init__(**kwargs)


class Parish(Base):
    """
    Represents parishes, England & Wales 2014.
    """
    __filename__ = "Parish_NCP names and codes EW as at 12_18.xlsx"
    __tablename__ = "parish_ncp_england_wales_2018"

    parish_code = Column(String(CODE_LEN), primary_key=True)
    parish_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'PARNCP18CD', 'parish_code')
        rename_key(kwargs, 'PARNCP18NM', 'parish_name')
        super().__init__(**kwargs)


class PCT2019(Base):
    """
    Represents Primary Care Trust (PCT) organizations, UK 2019.

    The forerunner of CCGs (q.v.).
    """
    __filename__ = "PCT names and codes UK as at 04_19.xlsx"
    __tablename__ = "pct_primary_care_trust_2019"

    pct_code = Column(String(CODE_LEN), primary_key=True)
    pct_code_old = Column(String(5))
    pct_name = Column(String(NAME_LEN))
    pct_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'PCTCD', 'pct_code')
        rename_key(kwargs, 'PCTCDO', 'pct_code_old')
        rename_key(kwargs, 'PCTNM', 'pct_name')
        rename_key(kwargs, 'PCTNMW', 'pct_name_welsh')
        super().__init__(**kwargs)


class PFA(Base):
    """
    Represents police force areas (PFAs), Great Britain 2015.
    """
    __filename__ = "PFA names and codes GB as at 12_15.xlsx"
    __tablename__ = "pfa_police_force_area_2015"

    pfa_code = Column(String(CODE_LEN), primary_key=True)
    pfa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'PFA15CD', 'pfa_code')
        rename_key(kwargs, 'PFA15NM', 'pfa_name')
        super().__init__(**kwargs)


class GOR(Base):
    """
    Represents Government Office Regions (GORs), England 2010.
    """
    __filename__ = "Region names and codes EN as at 12_10 (RGN).xlsx"
    __tablename__ = "gor_govt_office_region_england_2010"

    gor_code = Column(String(CODE_LEN), primary_key=True)
    gor_code_old = Column(String(1))
    gor_name = Column(String(NAME_LEN))
    gor_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'GOR10CD', 'gor_code')
        rename_key(kwargs, 'GOR10CDO', 'gor_code_old')
        rename_key(kwargs, 'GOR10NM', 'gor_name')
        rename_key(kwargs, 'GOR10NMW', 'gor_name')
        super().__init__(**kwargs)


class SSR(Base):
    """
    Represents Standard Statistical Regions (SSRs), UK 2005.
    """
    __filename__ = "SSR names and codes UK as at 12_05 (STREG).xlsx"
    __tablename__ = "ssr_standard_statistical_region_1995"

    ssr_code = Column(Integer, primary_key=True)
    ssr_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'SSR95CD', 'ssr_code')
        rename_key(kwargs, 'SSR95NM', 'ssr_name')
        convert_int(kwargs, 'ssr_code')
        super().__init__(**kwargs)


_ = '''
# NOT WORKING 2020-03-03: missing PK somewhere? Also: unimportant.
class Ward2005(Base):
    """
    Represents electoral wards, UK 2005.
    """
    __filename__ = "Statistical ward names and codes UK as at 2005.xlsx"
    __tablename__ = "electoral_ward_2005"

    ward_code = Column(String(6), primary_key=True)
    ward_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'WDSTL05CD', 'ward_code')
        rename_key(kwargs, 'WDSTL05NM', 'ward_name')
        super().__init__(**kwargs)
'''


class Ward2019(Base):
    """
    Represents electoral wards, UK 2016.
    """
    __filename__ = "Ward names and codes UK as at 12_19.xlsx"
    __tablename__ = "electoral_ward_2019"

    ward_code = Column(String(CODE_LEN), primary_key=True)
    ward_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'WD19CD', 'ward_code')
        rename_key(kwargs, 'WD19NM', 'ward_name')
        super().__init__(**kwargs)


class TTWA(Base):
    """
    Represents travel-to-work area (TTWAs), UK 2011.
    """
    __filename__ = "TTWA names and codes UK as at 12_11 v5.xlsx"
    __tablename__ = "ttwa_travel_to_work_area_2011"

    ttwa_code = Column(String(CODE_LEN), primary_key=True)
    ttwa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'TTWA11CD', 'ttwa_code')
        rename_key(kwargs, 'TTWA11NM', 'ttwa_name')
        super().__init__(**kwargs)


class WestminsterConstituency(Base):
    """
    Represents Westminster parliamentary constituencies, UK 2014.
    """
    __filename__ = "Westminster Parliamentary Constituency names and codes " \
                   "UK as at 12_14.xlsx"
    __tablename__ = "pcon_westminster_parliamentary_constituency_2014"

    pcon_code = Column(String(CODE_LEN), primary_key=True)
    pcon_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'PCON14CD', 'pcon_code')
        rename_key(kwargs, 'PCON14NM', 'pcon_name')
        super().__init__(**kwargs)


_ = '''
# =============================================================================
# Models: centroids
# =============================================================================
# http://webarchive.nationalarchives.gov.uk/20160105160709/http://www.ons.gov.uk/ons/guide-method/geography/products/census/spatial/centroids/index.html  # noqa
#
# Looking at lower_layer_super_output_areas_(e+w)_2011_population_weighted_centroids_v2.zip : # noqa
# - LSOA_2011_EW_PWC.shp -- probably a Shape file;
#   ... yes
#   ... https://en.wikipedia.org/wiki/Shapefile
#   ... ... describes most of the other files
# - LSOA_2011_EW_PWC_COORD_V2.CSV  -- LSOA to centroid coordinates

class PopWeightedCentroidsLsoa2011(Base):
    """
    Represents a population-weighted centroid of a lower layer super output
    area (LSOA).

    That is, the geographical centre of the LSOA, weighted by population. (A
    first approximation: imagine every person pulling on the centroid
    simultaneously and with equal force from their home. Where will it end up?)
    """  # noqa
    __filename__ = "LSOA_2011_EW_PWC_COORD_V2.CSV"
    __tablename__ = "pop_weighted_centroids_lsoa_2011"
    # __debug_content__ = True

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    bng_north = Column(Integer, comment="British National Grid, North (m)")
    bng_east = Column(Integer, comment="British National Grid, East (m)")
    # https://en.wikipedia.org/wiki/Ordnance_Survey_National_Grid#All-numeric_grid_references  # noqa
    latitude = Column(Numeric(precision=13, scale=10),
                      comment="Latitude (degrees, 10dp)")
    longitude = Column(Numeric(precision=13, scale=10),
                       comment="Longitude (degrees, 10dp)")
    # ... there are some with 10dp, e.g. 0.0000570995
    # ... (precision - scale) = number of digits before '.'
    # ... which can't be more than 3 for any latitude/longitude

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, 'LSOA11CD', 'lsoa_code')
        rename_key(kwargs, 'LSOA11NM', 'lsoa_name')
        rename_key(kwargs, 'BNGNORTH', 'bng_north')
        rename_key(kwargs, 'BNGEAST', 'bng_east')
        rename_key(kwargs, 'LONGITUDE', 'longitude')
        rename_key(kwargs, 'LATITUDE', 'latitude')
        # MySQL doesn't care if you pass a string to a numeric field, but
        # SQL server does. So:
        convert_int(kwargs, 'bng_north')
        convert_int(kwargs, 'bng_east')
        convert_float(kwargs, 'longitude')
        convert_float(kwargs, 'latitude')
        super().__init__(**kwargs)
        if not self.lsoa_code:
            raise ValueError("Can't have a blank lsoa_code")
'''


# =============================================================================
# Files -> table data
# =============================================================================

def populate_postcode_table(filename: str,
                            session: Session,
                            replace: bool = False,
                            startswith: List[str] = None,
                            reportevery: int = DEFAULT_REPORT_EVERY,
                            commit: bool = True,
                            commitevery: int = DEFAULT_COMMIT_EVERY) -> None:
    """
    Populates the :class:`Postcode` table, which is very big, from Office of
    National Statistics Postcode Database (ONSPD) database that you have
    downloaded.

    Args:
        filename: CSV file to read
        session: SQLAlchemy ORM database session
        replace: replace tables even if they exist? (Otherwise, skip existing
            tables.)
        startswith: if specified, restrict to postcodes that start with one of
            these strings
        reportevery: report to the Python log every *n* rows
        commit: COMMIT the session once we've inserted the data?
        commitevery: if committing: commit every *n* rows inserted
    """
    tablename = Postcode.__tablename__
    # noinspection PyUnresolvedReferences
    table = Postcode.__table__
    if not replace:
        engine = session.bind
        if engine.has_table(tablename):
            log.info(f"Table {tablename} exists; skipping")
            return
    log.info(f"Dropping/recreating table: {tablename}")
    table.drop(checkfirst=True)
    table.create(checkfirst=True)
    log.info(f"Using ONSPD data file: {filename}")
    n = 0
    n_inserted = 0
    extra_fields = []  # type: List[str]
    db_fields = sorted(k for k in table.columns.keys() if k != 'pcd_nospace')
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            n += 1
            if n % reportevery == 0:
                log.info(f"Processing row {n}: {row['pcds']} "
                         f"({n_inserted} inserted)")
                # log.debug(row)
            if n == 1:
                file_fields = sorted(row.keys())
                missing_fields = sorted(set(db_fields) - set(file_fields))
                extra_fields = sorted(set(file_fields) - set(db_fields))
                if missing_fields:
                    log.warning(
                        f"Fields in database but not file: {missing_fields}")
                if extra_fields:
                    log.warning(
                        f"Fields in file but not database : {extra_fields}")
            for k in extra_fields:
                del row[k]
            if startswith:
                ok = False
                for s in startswith:
                    if row['pcd'].startswith(s):
                        ok = True
                        break
                if not ok:
                    continue
            obj = Postcode(**row)
            session.add(obj)
            n_inserted += 1
            if commit and n % commitevery == 0:
                commit_and_announce(session)
    if commit:
        commit_and_announce(session)


# BASETYPE = TypeVar('BASETYPE', bound=Base)
# http://mypy.readthedocs.io/en/latest/kinds_of_types.html
# https://docs.python.org/3/library/typing.html


def populate_generic_lookup_table(
        sa_class: GenericLookupClassType,
        datadir: str,
        session: Session,
        replace: bool = False,
        commit: bool = True,
        commitevery: int = DEFAULT_COMMIT_EVERY) -> None:
    """
    Populates one of many generic lookup tables with ONSPD data.

    We find the data filename from the ``__filename__`` property of the
    specific class, hunting for it within ``datadir`` and its subdirectories.

    The ``.TXT`` files look at first glance like tab-separated values files,
    but in some cases have inconsistent numbers of tabs (e.g. "2011 Census
    Output Area Classification Names and Codes UK.txt"). So we'll use the
    ``.XLSX`` files.

    If the headings parameter is passed, those headings are used. Otherwise,
    the first row is used for headings.

    Args:
        sa_class: SQLAlchemy ORM class
        datadir: root directory of ONSPD data
        session: SQLAlchemy ORM database session
        replace: replace tables even if they exist? (Otherwise, skip existing
            tables.)
        commit: COMMIT the session once we've inserted the data?
        commitevery: if committing: commit every *n* rows inserted
    """
    tablename = sa_class.__tablename__
    filename = find_first(sa_class.__filename__, datadir)
    headings = getattr(sa_class, '__headings__', [])
    debug = getattr(sa_class, '__debug_content__', False)
    n = 0

    if not replace:
        engine = session.bind
        if engine.has_table(tablename):
            log.info(f"Table {tablename} exists; skipping")
            return

    log.info(f"Dropping/recreating table: {tablename}")
    sa_class.__table__.drop(checkfirst=True)
    sa_class.__table__.create(checkfirst=True)

    log.info(f'Processing file "{filename}" -> table "{tablename}"')
    ext = os.path.splitext(filename)[1].lower()
    type_xlsx = ext in ['.xlsx']
    type_csv = ext in ['.csv']
    file = None  # type: Optional[TextIO]

    def dict_from_rows(row_iterator: Iterable[List]) \
            -> Generator[Dict, None, None]:
        local_headings = headings
        first_row = True
        for row in row_iterator:
            values = values_from_row(row)
            if first_row and not local_headings:
                local_headings = values
            else:
                yield dict(zip(local_headings, values))
            first_row = False

    if type_xlsx:
        workbook = openpyxl.load_workbook(filename)  # read_only=True
        # openpyxl BUG: with read_only=True, cells can have None as their value
        # when they're fine if opened in non-read-only mode.
        # May be related to this:
        # https://bitbucket.org/openpyxl/openpyxl/issues/601/read_only-cell-row-column-attributes-are  # noqa
        sheet = workbook.active
        dict_iterator = dict_from_rows(sheet.iter_rows())
    elif type_csv:
        file = open(filename, 'r')
        csv_reader = csv.DictReader(file)
        dict_iterator = csv_reader
    else:
        workbook = xlrd.open_workbook(filename)
        sheet = workbook.sheet_by_index(0)
        dict_iterator = dict_from_rows(sheet.get_rows())
    for datadict in dict_iterator:
        n += 1
        if debug:
            log.critical(f"{n}: {datadict}")
        # filter out blanks:
        datadict = {k: v for k, v in datadict.items() if k}
        obj = sa_class(**datadict)
        session.add(obj)
        if commit and n % commitevery == 0:
            commit_and_announce(session)
    if commit:
        commit_and_announce(session)
    log.info(f"... inserted {n} rows")

    if file:
        file.close()


# =============================================================================
# Docs
# =============================================================================

def show_docs() -> None:
    """
    Print the column ``doc`` attributes from the :class:`Postcode` class, in
    tabular form, to stdout.
    """
    # noinspection PyUnresolvedReferences
    table = Postcode.__table__
    columns = sorted(table.columns.keys())
    pt = prettytable.PrettyTable(
        ["postcode field", "Description"],
        # header=False,
        border=True,
        hrules=prettytable.ALL,
        vrules=prettytable.NONE,
    )
    pt.align = 'l'
    pt.valign = 't'
    pt.max_width = 80
    for col in columns:
        doc = getattr(Postcode, col).doc
        doc = wordwrap(doc, width=70)
        ptrow = [col, doc]
        pt.add_row(ptrow)
    print(pt.get_string())


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point. See command-line help.
    """
    parser = argparse.ArgumentParser(
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=
        r"""
-   This program reads data from the UK Office of National Statistics Postcode
    Database (ONSPD) and inserts it into a database.

-   You will need to download the ONSPD from
        https://geoportal.statistics.gov.uk/geoportal/catalog/content/filelist.page
    e.g. ONSPD_MAY_2016_csv.zip (79 Mb), and unzip it (>1.4 Gb) to a directory.
    Tell this program which directory you used.

-   Specify your database as an SQLAlchemy connection URL: see
        http://docs.sqlalchemy.org/en/latest/core/engines.html
    The general format is:
        dialect[+driver]://username:password@host[:port]/database[?key=value...]

-   If you get an error like:
        UnicodeEncodeError: 'latin-1' codec can't encode character '\u2019' in
        position 33: ordinal not in range(256)
    then try appending "?charset=utf8" to the connection URL.

-   ONS POSTCODE DATABASE LICENSE.
    Output using this program must add the following attribution statements:

    Contains OS data © Crown copyright and database right [year]
    Contains Royal Mail data © Royal Mail copyright and database right [year]
    Contains National Statistics data © Crown copyright and database right [year]

    See http://www.ons.gov.uk/methodology/geography/licences
    """)  # noqa
    parser.add_argument(
        "--dir", default=DEFAULT_ONSPD_DIR,
        help="Root directory of unzipped ONSPD download")
    parser.add_argument(
        "--url", help="SQLAlchemy database URL")
    parser.add_argument(
        "--echo", action="store_true", help="Echo SQL")
    parser.add_argument(
        "--reportevery", type=int, default=DEFAULT_REPORT_EVERY,
        help="Report every n rows")
    parser.add_argument(
        "--commitevery", type=int, default=DEFAULT_COMMIT_EVERY,
        help=(
            "Commit every n rows. If you make this too large "
            "(relative e.g. to your MySQL max_allowed_packet setting, you may"
            " get crashes with errors like 'MySQL has gone away'."))
    parser.add_argument(
        "--startswith", nargs="+",
        help="Restrict to postcodes that start with one of these strings")
    parser.add_argument(
        "--replace", action="store_true",
        help="Replace tables even if they exist (default: skip existing "
             "tables)")
    parser.add_argument(
        "--skiplookup", action="store_true",
        help="Skip generation of code lookup tables")
    parser.add_argument(
        "--specific_lookup_tables", nargs="*",
        help="Within the lookup tables, process only specific named tables")
    parser.add_argument(
        "--list_lookup_tables", action="store_true",
        help="List all possible lookup tables, then stop")
    parser.add_argument(
        "--skippostcodes", action="store_true",
        help="Skip generation of main (large) postcode table")
    parser.add_argument(
        "--docsonly", action="store_true",
        help="Show help for postcode table then stop")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()
    rootlogger = logging.getLogger()
    configure_logger_for_colour(
        rootlogger, level=logging.DEBUG if args.verbose else logging.INFO)
    log.debug(f"args = {args!r}")

    if args.docsonly:
        show_docs()
        sys.exit(0)

    classlist = [
        # Core lookup tables:
        # In alphabetical order of filename:
        OAClassification,
        BUA,
        BUASD,
        CASWard,
        CCG,
        Country,
        County2019,
        EER,
        IMDLookupEN,
        IMDLookupSC,
        IMDLookupWA,
        LAU,
        LAD,
        LEP,
        LSOA2011,
        MSOA2011,
        NationalPark,
        Parish,
        PCT2019,
        PFA,
        GOR,
        SSR,
        # Ward2005,
        TTWA,
        Ward2019,
        WestminsterConstituency,

        # Centroids:
        # PopWeightedCentroidsLsoa2011,
    ]

    if args.list_lookup_tables:
        tables_files = []  # type: List[Tuple[str, str]]
        for sa_class in classlist:
            tables_files.append((sa_class.__tablename__,
                                 sa_class.__filename__))
        tables_files.sort(key=lambda x: x[0])
        for table, file in tables_files:
            print(f"Table {table} from file {file!r}")
        return

    if not args.url:
        print("Must specify URL")
        return

    engine = create_engine(args.url, echo=args.echo, encoding=CHARSET)
    metadata.bind = engine
    session = sessionmaker(bind=engine)()

    log.info(f"Using directory: {args.dir}")
    # lookupdir = os.path.join(args.dir, "Documents")
    lookupdir = args.dir
    # datadir = os.path.join(args.dir, "Data")
    datadir = args.dir

    if not args.skiplookup:
        for sa_class in classlist:
            if (args.specific_lookup_tables and
                    sa_class.__tablename__ not in args.specific_lookup_tables):
                continue
            # if (sa_class.__tablename__ ==
            #         "ccg_clinical_commissioning_group_uk_2019"):
            #     log.warning("Ignore warning 'Discarded range with reserved "
            #                 "name' below; it works regardless")
            populate_generic_lookup_table(
                sa_class=sa_class,
                datadir=lookupdir,
                session=session,
                replace=args.replace,
                commit=True,
                commitevery=args.commitevery
            )
    if not args.skippostcodes:
        populate_postcode_table(
            filename=find_first("ONSPD_*.csv", datadir),
            session=session,
            replace=args.replace,
            startswith=args.startswith,
            reportevery=args.reportevery,
            commit=True,
            commitevery=args.commitevery
        )


if __name__ == '__main__':
    main()
