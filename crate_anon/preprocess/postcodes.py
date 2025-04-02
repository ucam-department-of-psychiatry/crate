#!/usr/bin/env python

"""
crate_anon/preprocess/postcodes.py

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

**Fetches UK postcode information and creates a database.**

Code-Point Open, CSV, GB

- https://www.ordnancesurvey.co.uk/business-and-government/products/opendata-products.html
- https://www.ordnancesurvey.co.uk/business-and-government/products/code-point-open.html
- https://www.ordnancesurvey.co.uk/opendatadownload/products.html
- https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

Office for National Statistics Postcode Database (ONSPD):

- https://geoportal.statistics.gov.uk/geoportal/catalog/content/filelist.page
- e.g. ONSPD_MAY_2016_csv.zip
- https://www.ons.gov.uk/methodology/geography/licences

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

"""  # noqa: E501

from abc import ABC, ABCMeta, abstractmethod
import argparse
import csv
import datetime
import logging
import os
import sys

from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Tuple,
)

from cardinal_pythonlib.dicts import rename_key
from cardinal_pythonlib.fileops import find, find_first
from cardinal_pythonlib.logs import configure_logger_for_colour
import openpyxl
from openpyxl.cell.cell import Cell
from sqlalchemy import (
    Column,
    create_engine,
    Date,
    Float,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import MetaData, Table

from crate_anon.anonymise.constants import TABLE_KWARGS
from crate_anon.common.argparse_assist import (
    RawDescriptionArgumentDefaultsRichHelpFormatter,
)
from crate_anon.common.constants import EnvVar
from crate_anon.common.stringfunc import make_twocol_table

log = logging.getLogger(__name__)

# find_first() logs a critical error if a file is not found. For our purposes,
# this is expected behaviour so we don't want to alarm the user. Maybe it
# shouldn't do that and instead leave it to the caller to decide how serious
# that is.
logging.getLogger("cardinal_pythonlib.fileops").disabled = True

# =============================================================================
# Constants
# =============================================================================

if EnvVar.GENERATING_CRATE_DOCS in os.environ:
    DEFAULT_ONSPD_DIR = "/path/to/unzipped/ONSPD/download"
else:
    DEFAULT_ONSPD_DIR = os.path.join(
        os.path.expanduser("~"), "dev", "ons", "ONSPD_Nov2019"
    )

DEFAULT_REPORT_EVERY = 1000
DEFAULT_COMMIT_EVERY = 10000
YEAR_MONTH_FMT = "%Y%m"

CODE_LEN = 9  # many ONSPD codes have this length
NAME_LEN = 80  # seems about right; a bit more than the length of many

COL_POSTCODE_NOSPACE = "pcd_nospace"
COL_POSTCODE_VARIABLE_LENGTH_SPACE = "pcds"

ROWS_TO_DUMP = 5
DUMP_FORMAT = "20.20"  # Pad and truncate columns to 20 characters

# =============================================================================
# Metadata
# =============================================================================

metadata = MetaData()


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
        d[key] = datetime.datetime.strptime(value, YEAR_MONTH_FMT)
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
    return [cell.value for cell in row]


def commit_and_announce(session: Session) -> None:
    """
    Commits an SQLAlchemy ORM session and says so.
    """
    log.info("COMMIT")
    session.commit()


# =============================================================================
# Extend SQLAlchemy Base class
# =============================================================================


class ExtendedBase:
    """
    Mixin to extend the SQLAlchemy ORM Base class by specifying table creation
    parameters (specifically, for MySQL, to set the character set and
    MySQL engine).

    Only used in the creation of Base; everything else then inherits from Base
    as usual.

    See
    https://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html
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
        from sqlalchemy.orm import declarative_base
        from sqlalchemy.sql.schema import MetaData

        class ExtendedBase:
            __table_args__ = {'mysql_charset': 'utf8', 'mysql_engine': 'InnoDB'}

        metadata = MetaData()
        Base = declarative_base(metadata=metadata, cls=ExtendedBase)

        type(Base)  # metaclass of Base: <class: 'sqlalchemy.ext.declarative.api.DeclarativeMeta'>
        type(ABC)  # metaclass of ABC: <class 'abc.ABCMeta'>

    and thus define this class to inherit from those two metaclasses, so it can
    be the metaclass we want.

    """  # noqa: E501

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

    __tablename__ = "postcode"

    pcd_nospace = Column(
        String(8), primary_key=True, comment="Postcode (no spaces)"
    )
    # ... not in original, but simplifies indexing
    pcd = Column(
        String(7),
        index=True,
        unique=True,
        comment="Unit postcode (7 characters): 2-4 char outward code, "
        "left-aligned; 3-char inward code, right-aligned",
    )
    pcd2 = Column(
        String(8),
        index=True,
        unique=True,
        comment="Unit postcode (8 characters): 2-4 char outward code, "
        "left-aligned; space; 3-char inward code, right-aligned",
    )
    pcds = Column(
        String(8),
        index=True,
        unique=True,
        comment="Unit postcode (variable length): 2-4 char outward "
        "code; space; 3-char inward code",
    )
    dointr = Column(
        Date, comment="Date of introduction (original format YYYYMM)"
    )
    doterm = Column(
        Date, comment="Date of termination (original format YYYYMM) or NULL"
    )
    oscty = Column(
        String(CODE_LEN),
        comment="County code [FK to county_england_2010.county_code]",
    )
    oslaua = Column(
        String(CODE_LEN),
        comment="Local authority district (LUA), unitary  authority "
        "(UA), metropolitan district (MD), London borough (LB),"
        " council area (CA), or district council area (DCA) "
        "[FK to lad_local_authority_district_2019.lad_code]",
    )
    osward = Column(
        String(CODE_LEN),
        comment="Electoral ward/division "
        "[FK e.g. to electoral_ward_2019.ward_code]",
    )
    usertype = Column(Integer, comment="Small (0) or large (1) postcode user")
    oseast1m = Column(
        Integer, comment="National grid reference Easting, 1m resolution"
    )
    osnrth1m = Column(
        Integer, comment="National grid reference Northing, 1m resolution"
    )
    osgrdind = Column(
        Integer, comment="Grid reference positional quality indicator"
    )
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
        "lhb_local_health_board_wales_2006.lhb_code]",
    )
    ctry = Column(
        String(CODE_LEN),
        comment="Country of the UK [England, Scotland, Wales, "
        "Northern Ireland] [FK to country_2012.country_code]",
    )
    streg = Column(
        Integer,
        comment="Standard (Statistical) Region (SSR) [FK to "
        "ssr_standard_statistical_region_1995."
        "ssr_code]",
    )
    pcon = Column(
        String(CODE_LEN),
        comment="Westminster parliamentary constituency [FK to "
        "pcon_westminster_parliamentary_constituency_2014."
        "pcon_code]",
    )
    eer = Column(
        String(CODE_LEN),
        comment="European Electoral Region (EER) [FK to "
        "eer_european_electoral_region_2010.eer_code]",
    )
    teclec = Column(
        String(CODE_LEN),
        comment="Local Learning and Skills Council (LLSC) / Dept. of "
        "Children, Education, Lifelong Learning and Skills (DCELLS) / "
        "Enterprise Region (ER) [PROBABLY FK to one of: "
        "dcells_dept_children_wales_2010.dcells_code; "
        "er_enterprise_region_scotland_2010.er_code; "
        "llsc_local_learning_skills_council_england_2010.llsc_code]",
    )
    ttwa = Column(
        String(CODE_LEN),
        comment="Travel to Work Area (TTWA) [FK to "
        "ttwa_travel_to_work_area_2011.ttwa_code]",
    )
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
        "lhb_local_health_board_wales_2014.lhb_code]",
    )
    nuts = Column(
        String(10),
        comment="LAU2 areas [European Union spatial regions; Local "
        "Adminstrative Unit, level 2] / Nomenclature of Units "
        "for Territorial Statistics (NUTS) [FK to "
        "lau_eu_local_administrative_unit_2019.lau2_code]",
    )
    statsward = Column(
        String(6),
        comment="2005 'statistical' ward [?FK to "
        "electoral_ward_2005.ward_code]",
    )
    oa01 = Column(
        String(10),
        comment="2001 Census Output Area (OA). (There are "
        "about 222,000, so ~300 population?)",
    )
    casward = Column(
        String(6),
        comment="Census Area Statistics (CAS) ward [PROBABLY FK to "
        "cas_ward_2003.cas_ward_code]",
    )
    park = Column(
        String(CODE_LEN),
        comment="National park [FK to " "park_national_park_2016.park_code]",
    )
    lsoa01 = Column(
        String(CODE_LEN),
        comment="2001 Census Lower Layer Super Output Area (LSOA) [England & "
        "Wales, ~1,500 population] / Data Zone (DZ) [Scotland] / "
        "Super Output Area (SOA) [FK to one of: "
        "lsoa_lower_layer_super_output_area_england_wales_2004.lsoa_code; "  # noqa: E501
        "lsoa_lower_layer_super_output_area_n_ireland_2005.lsoa_code]",
    )
    msoa01 = Column(
        String(CODE_LEN),
        comment="2001 Census Middle Layer Super Output Area (MSOA) [England & "
        "Wales, ~7,200 population] / "
        "Intermediate Zone (IZ) [Scotland] [FK to one of: "
        "msoa_middle_layer_super_output_area_england_wales_2004.msoa_code; "  # noqa: E501
        "iz_intermediate_zone_scotland_2005.iz_code]",
    )
    ur01ind = Column(
        String(1),
        comment="2001 Census urban/rural indicator [numeric in "
        "England/Wales/Scotland; letters in N. Ireland]",
    )
    oac01 = Column(
        String(3),
        comment="2001 Census Output Area classification (OAC)"
        "[POSSIBLY FK to output_area_classification_2011."
        "subgroup_code]",
    )
    oa11 = Column(
        String(CODE_LEN),
        comment="2011 Census Output Area (OA) [England, Wales, Scotland;"
        " ~100-625 population] / Small Area (SA) [N. Ireland]",
    )
    lsoa11 = Column(
        String(CODE_LEN),
        comment="2011 Census Lower Layer Super Output Area (LSOA) [England & "
        "Wales, ~1,500 population] / Data Zone (DZ) [Scotland] / "
        "Super Output Area (SOA) [N. Ireland] [FK to one of: "
        "lsoa_lower_layer_super_output_area_2011.lsoa_code; "
        " (defunct) dz_datazone_scotland_2011.dz_code]",
    )
    msoa11 = Column(
        String(CODE_LEN),
        comment="2011 Census Middle Layer Super Output Area (MSOA) [England & "
        "Wales, ~7,200 population] / "
        "Intermediate Zone (IZ) [Scotland] [FK to one of: "
        "msoa_middle_layer_super_output_area_2011.msoa_code; "
        "iz_intermediate_zone_scotland_2011.iz_code]",
    )
    parish = Column(
        String(CODE_LEN),
        comment="Parish/community [FK to "
        "parish_ncp_england_wales_2018.parish_code]",
    )
    wz11 = Column(String(CODE_LEN), comment="2011 Census Workplace Zone (WZ)")
    ccg = Column(
        String(CODE_LEN),
        comment="Clinical Commissioning Group (CCG) / Local Health Board "
        "(LHB) / Community Health Partnership (CHP) / Local "
        "Commissioning Group (LCG) / Primary Healthcare Directorate "
        "(PHD) [FK to one of: "
        "ccg_clinical_commissioning_group_uk_2019."
        "ccg_ons_code, lhb_local_health_board_wales_2014.lhb_code]",
    )
    bua11 = Column(
        String(CODE_LEN),
        comment="Built-up Area (BUA) [FK to "
        "bua_built_up_area_uk_2013.bua_code]",
    )
    buasd11 = Column(
        String(CODE_LEN),
        comment="Built-up Area Sub-division (BUASD) [FK to "
        "buasd_built_up_area_subdivision_uk_2013.buas_code]",
    )
    ru11ind = Column(
        String(2), comment="2011 Census rural-urban classification"
    )
    oac11 = Column(
        String(3),
        comment="2011 Census Output Area classification (OAC) [FK to "
        "output_area_classification_2011.subgroup_code]",
    )
    lat = Column(
        Numeric(precision=9, scale=6), comment="Latitude (degrees, 6dp)"
    )
    long = Column(
        Numeric(precision=9, scale=6), comment="Longitude (degrees, 6dp)"
    )
    lep1 = Column(
        String(CODE_LEN),
        comment="Local Enterprise Partnership (LEP) - first instance [FK to "
        "lep_local_enterprise_partnership_england_2017.lep1_code]",
    )
    lep2 = Column(
        String(CODE_LEN),
        comment="Local Enterprise Partnership (LEP) - second instance [FK to "
        "lep_local_enterprise_partnership_england_2017.lep1_code]",
    )
    pfa = Column(
        String(CODE_LEN),
        comment="Police Force Area (PFA) [FK to "
        "pfa_police_force_area_2015.pfa_code]",
    )
    imd = Column(
        Integer,
        comment="Index of Multiple Deprivation (IMD) [rank of LSOA/DZ, where "
        "1 is the most deprived, within each country] [FK to one of: "
        "imd_index_multiple_deprivation_england_2015.imd_rank; "
        "imd_index_multiple_deprivation_n_ireland_2010.imd_rank; "
        "imd_index_multiple_deprivation_scotland_2012.imd_rank; "
        "imd_index_multiple_deprivation_wales_2014.imd_rank]",
    )
    bua22 = Column(
        String(CODE_LEN),
        comment="Built-up Area (BUA) [FK to "
        "bua_built_up_area_uk_2022.bua_code]",
    )
    bua24 = Column(
        String(CODE_LEN),
        comment="Built-up Area (BUA) [FK to "
        "bua_built_up_area_uk_2024.bua_code]",
    )
    calncv = Column(
        String(CODE_LEN),
        comment=(
            "Cancer Alliance / National Cancer Vanguard code "
            "[FK to cal_ncv_2023.cal_ncv_code]"
        ),
    )
    ced = Column(
        String(CODE_LEN),
        comment="County Electoral Division code [FK to county_ed_2023]",
    )
    icb = Column(
        String(CODE_LEN),
        comment="Integrated Care Boards code [FK to icb_2023]",
    )
    itl = Column(
        String(CODE_LEN),
        comment=(
            "International Territory Level (former NUTS)"
            "[FK to lad23_lau121_itl321_itl221_itl121]"
        ),
    )
    lsoa21 = Column(
        String(CODE_LEN),
        comment=(
            "2021 Census Lower Layer Super Output Area (LSOA)/Super Data Zone "
            "(SDZ) [FK to lsoa_lower_layer_super_output_area_2021 or "
            "sdz_super_data_zones_2021]"
        ),
    )
    msoa21 = Column(
        String(CODE_LEN),
        comment=(
            "2021 Census Middle Layer Super Output Area (MSOA) "
            "[FK to MSOA2021]"
        ),
    )
    nhser = Column(
        String(CODE_LEN),
        comment="NHS England (Region) (NHS ER) [FK to NHSER2022]",
    )
    npark = Column(
        String(CODE_LEN),
        comment=("National park [FK to park_national_park_2022]"),
    )
    oa21 = Column(
        String(CODE_LEN),
        comment=(
            "2021 Census Output Area (OA)/ Data Zone (DZ). "
            "Based on 2011 Census OAs."
        ),
    )
    rgn = Column(
        String(CODE_LEN),
        comment="Region (former GOR) [FK to rgn_region_england_2020]",
    )
    sicbl = Column(
        String(CODE_LEN),
        comment=(
            "Sub ICB Location (LOC)/ Local Health Board (LHB)/ "
            "Community Health Partnership (CHP)/ "
            "Local Commissioning Group (LCG)/ "
            "Primary Healthcare Directorate (PHD) "
            "[FK to loc_sub_icb_locations_2022]"
        ),
    )

    def __init__(self, **kwargs: Any) -> None:
        convert_date(kwargs, "dointr")
        convert_date(kwargs, "doterm")
        convert_int(kwargs, "usertype")
        convert_int(kwargs, "oseast1m")
        convert_int(kwargs, "osnrth1m")
        convert_int(kwargs, "osgrdind")
        convert_int(kwargs, "streg")
        convert_int(kwargs, "edind")
        convert_int(kwargs, "imd")
        kwargs[COL_POSTCODE_NOSPACE] = kwargs["pcd"].replace(" ", "")
        super().__init__(**kwargs)


# =============================================================================
# Models: core lookup tables
# =============================================================================


class OAClassification2001(Base):
    """
    Represents 2001 Census Output Area (OA) classification names/codes.
    """

    __filename__ = (
        "2001 Census Output Area Classification Names and Codes UK.xlsx"
    )
    __tablename__ = "output_area_classification_2001"

    oac01 = Column(String(3), primary_key=True)
    supergroup_code = Column(String(1))
    supergroup_desc = Column(String(35))
    group_code = Column(String(2))
    group_desc = Column(String(40))
    subgroup_code = Column(String(3))
    subgroup_desc = Column(String(60))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "OAC01", "oac01")
        rename_key(kwargs, "Supergroup", "supergroup_desc")
        rename_key(kwargs, "Group", "group_desc")
        rename_key(kwargs, "Subgroup", "subgroup_desc")
        kwargs["supergroup_code"] = kwargs["oac01"][0:1]
        kwargs["group_code"] = kwargs["oac01"][0:2]
        kwargs["subgroup_code"] = kwargs["oac01"]
        super().__init__(**kwargs)


class OAClassification2011(Base):
    """
    Represents 2011 Census Output Area (OA) classification names/codes.
    """

    __filename__ = (
        "2011 Census Output Area Classification Names and Codes UK.xlsx"
    )
    __tablename__ = "output_area_classification_2011"

    oac11 = Column(String(3), primary_key=True)
    supergroup_code = Column(String(1))
    supergroup_desc = Column(String(35))
    group_code = Column(String(2))
    group_desc = Column(String(40))
    subgroup_code = Column(String(3))
    subgroup_desc = Column(String(60))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "OAC11", "oac11")
        rename_key(kwargs, "Supergroup", "supergroup_desc")
        rename_key(kwargs, "Group", "group_desc")
        rename_key(kwargs, "Subgroup", "subgroup_desc")
        kwargs["supergroup_code"] = kwargs["oac11"][0:1]
        kwargs["group_code"] = kwargs["oac11"][0:2]
        kwargs["subgroup_code"] = kwargs["oac11"]
        super().__init__(**kwargs)


class BUA2013(Base):
    """
    Represents England & Wales 2013 built-up area (BUA) codes/names.
    """

    __filename__ = "BUA_names and codes UK as at 12_13.xlsx"
    __tablename__ = "bua_built_up_area_uk_2013"

    bua_code = Column(String(CODE_LEN), primary_key=True)
    bua_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "BUA13CD", "bua_code")
        rename_key(kwargs, "BUA13NM", "bua_name")
        super().__init__(**kwargs)


class BUA2022(Base):
    """
    Represents England & Wales 2022 built-up area (BUA) codes/names.
    """

    __filename__ = "BUA22_names and codes EW as at 12_22.xlsx"
    __tablename__ = "bua_built_up_area_uk_2022"

    bua_code = Column(String(CODE_LEN), primary_key=True)
    bua_name = Column(String(NAME_LEN))
    bua_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "BUA22CD", "bua_code")
        rename_key(kwargs, "BUA22NM", "bua_name")
        rename_key(kwargs, "BUA22NMW", "bua_name_welsh")
        super().__init__(**kwargs)


class BUA2024(Base):
    """
    Represents England & Wales 2024 built-up area (BUA) codes/names.
    """

    __filename__ = "BUA24 names and codes EW as at 04_24.xlsx"
    __tablename__ = "bua_built_up_area_uk_2024"
    __duplicates__ = [
        {"BUA24CD": "W45001083", "BUA24NM": "Bargod", "BUA24NMW": "Bargoed"}
    ]

    bua_code = Column(String(CODE_LEN), primary_key=True)
    bua_name = Column(String(NAME_LEN))
    bua_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "BUA24CD", "bua_code")
        rename_key(kwargs, "BUA24NM", "bua_name")
        rename_key(kwargs, "BUA24NMW", "bua_name_welsh")
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
        rename_key(kwargs, "BUASD13CD", "buasd_code")
        rename_key(kwargs, "BUASD13NM", "buasd_name")
        super().__init__(**kwargs)


class CALNCV2023(Base):
    """
    Represents Cancer Alliance / National Cancer Vanguard codes for each
    postcode 2023.
    """

    __filename__ = "CALNCV names and codes EN as at 07_23.xlsx"
    __tablename__ = "cal_ncv_2023"

    cal_ncv_code = Column(String(CODE_LEN), primary_key=True)
    cal_ncv_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "CAL23CD", "cal_ncv_code")
        rename_key(kwargs, "CAL23NM", "cal_ncv_name")
        super().__init__(**kwargs)


class CASWard(Base):
    """
    Represents censua area statistics (CAS) wards in the UK, 2003.

    - https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography#statistical-wards-cas-wards-and-st-wards
    """  # noqa: E501

    __filename__ = "CAS ward names and codes UK as at 01_03.xlsx"
    __tablename__ = "cas_ward_2003"

    cas_ward_code = Column(String(CODE_LEN), primary_key=True)
    cas_ward_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "WDCAS03CD", "cas_ward_code")
        rename_key(kwargs, "WDCAS03NM", "cas_ward_name")
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
        rename_key(kwargs, "CCG19CD", "ccg_ons_code")
        rename_key(kwargs, "CCG19CDH", "ccg_ccg_code")
        rename_key(kwargs, "CCG19NM", "ccg_name")
        rename_key(kwargs, "CCG19NMW", "ccg_name_welsh")
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
        rename_key(kwargs, "CTRY12CD", "country_code")
        rename_key(kwargs, "CTRY12CDO", "country_code_old")
        rename_key(kwargs, "CTRY12NM", "country_name")
        rename_key(kwargs, "CTRY12NMW", "country_name_welsh")
        super().__init__(**kwargs)


class CountyED2023(Base):
    """
    Represents county electoral divisions in England 2023.
    """

    __filename__ = "County Electoral Division names and codes EN as at 05_23.xlsx"  # noqa: E501
    __tablename__ = "county_ed_2023"

    county_ed_code = Column(String(CODE_LEN), primary_key=True)
    county_ed_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "CED23CD", "county_ed_code")
        rename_key(kwargs, "CED23NM", "county_ed_name")
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
        rename_key(kwargs, "CTY19CD", "county_code")
        rename_key(kwargs, "CTY19NM", "county_name")
        super().__init__(**kwargs)


class County2023(Base):
    """
    Represents counties, UK 2023.
    """

    __filename__ = "County names and codes UK as at 12_23.xlsx"
    __tablename__ = "county_england_2023"

    county_code = Column(String(CODE_LEN), primary_key=True)
    county_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "CTY23CD", "county_code")
        rename_key(kwargs, "CTY23NM", "county_name")
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
        rename_key(kwargs, "EER10CD", "eer_code")
        rename_key(kwargs, "EER10CDO", "eer_code_old")
        rename_key(kwargs, "EER10NM", "eer_name")
        super().__init__(**kwargs)


class HealthArea2019(Base):
    """
    Represents Health Area, 2019.
    """

    __filename__ = "HLTHAU names and codes UK as at 04_19 (OSHLTHAU).xlsx"
    __tablename__ = "health_area_2019"

    health_area_code = Column(String(CODE_LEN), primary_key=True)
    health_area_code_old = Column(String(CODE_LEN))
    health_area_name = Column(String(NAME_LEN))
    health_area_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "HLTHAUCD", "health_area_code")
        rename_key(kwargs, "HLTHAUCDO", "health_area_code_old")
        rename_key(kwargs, "HLTHAUNM", "health_area_name")
        rename_key(kwargs, "HLTHAUNMW", "health_area_name_welsh")
        super().__init__(**kwargs)


class ICB2023(Base):
    """
    Represents Integrated Care Boards, 2023.
    """

    __filename__ = "ICB names and codes UK as at 04_23.xlsx"
    __tablename__ = "icb_2023"

    icb_code = Column(String(CODE_LEN), primary_key=True)
    icb_code_h = Column(String(3))  # Don't know what this is. Has Q prefix.
    icb_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "ICB23CD", "icb_code")
        rename_key(kwargs, "ICB23CDH", "icb_code_h")
        rename_key(kwargs, "ICB23NM", "icb_name")
        super().__init__(**kwargs)


class IMDLookupEN2015(Base):
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
        rename_key(kwargs, "LSOA11CD", "lsoa_code")
        rename_key(kwargs, "LSOA11NM", "lsoa_name")
        rename_key(kwargs, "IMD15", "imd_rank")
        convert_int(kwargs, "imd_rank")
        super().__init__(**kwargs)


class IMDLookupEN2019(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), England 2019.
    """

    __filename__ = "IMD lookup EN as at 12_19.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_england_2019"

    fid = Column(Integer)  # MB: Don't know what this is
    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    lad_code = Column(String(CODE_LEN))
    lad_name = Column(String(NAME_LEN))
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "FID", "fid")
        rename_key(kwargs, "LSOA11CD", "lsoa_code")
        rename_key(kwargs, "LSOA11NM", "lsoa_name")
        rename_key(kwargs, "LAD19CD", "lad_code")
        rename_key(kwargs, "LAD19NM", "lad_name")

        rename_key(kwargs, "IMD19", "imd_rank")
        convert_int(kwargs, "fid")
        convert_int(kwargs, "imd_rank")
        super().__init__(**kwargs)


class IMDLookupNI2017(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Northern Ireland 2017.
    """

    __filename__ = "IMD lookup NI as at 12_17.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_northern_ireland_2017"

    fid = Column(Integer)  # Don't know what this is
    lgd_code = Column(String(CODE_LEN))  # Local government district
    lgd_name = Column(String(NAME_LEN))
    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "FID", "fid")
        rename_key(kwargs, "LGD14CD", "lgd_code")
        rename_key(kwargs, "LGD14NM", "lgd_name")
        rename_key(kwargs, "LSOA01CD", "lsoa_code")
        rename_key(kwargs, "LSOA01NM", "lsoa_name")

        rename_key(kwargs, "IMD17", "imd_rank")
        convert_int(kwargs, "fid")
        convert_int(kwargs, "imd_rank")
        super().__init__(**kwargs)


class IMDLookupSC2016(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Scotland 2016.
    """

    __filename__ = "IMD lookup SC as at 12_16.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_scotland_2016"

    dz_code = Column(String(CODE_LEN), primary_key=True)
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "DZ11CD", "dz_code")
        rename_key(kwargs, "IMD16", "imd_rank")
        convert_int(kwargs, "imd_rank")
        super().__init__(**kwargs)


class IMDLookupSC2020(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Scotland 2020.
    """

    __filename__ = "IMD lookup SC as at 12_20.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_scotland_2020"

    dz_code = Column(String(CODE_LEN), primary_key=True)
    dz_name = Column(String(NAME_LEN))
    imd_rank = Column(Integer)
    vigintile = Column(Integer)
    decile = Column(Integer)
    quintile = Column(Integer)
    # Some of these columns have multiple rows with the same rank that
    # aren't integers e.g. SIMD2020v2_Income_Domain_Rank is 5955.5 for six
    # rows.
    income_domain_rank = Column(Float)
    employment_domain_rank = Column(Float)
    education_domain_rank = Column(Float)
    health_domain_rank = Column(Float)
    access_domain_rank = Column(Float)
    crime_domain_rank = Column(Float)
    housing_domain_rank = Column(Float)
    population = Column(Integer)
    working_age_population = Column(Integer)
    urban_rural_class = Column(Integer)
    urban_rural_name = Column(String(NAME_LEN))
    intermediate_zone_code = Column(String(CODE_LEN))
    intermediate_zone_name = Column(String(NAME_LEN))
    local_authority_code = Column(String(CODE_LEN))
    local_authority_name = Column(String(NAME_LEN))
    health_board_code = Column(String(CODE_LEN))
    health_board_name = Column(String(NAME_LEN))
    multi_member_ward_code = Column(String(CODE_LEN))
    multi_member_ward_name = Column(String(NAME_LEN))
    scottish_parliamentary_constituency_code = Column(String(CODE_LEN))
    scottish_parliamentary_constituency_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "DZ", "dz_code")
        rename_key(kwargs, "DZname", "dz_name")
        rename_key(kwargs, "SIMD2020v2_Rank", "imd_rank")
        rename_key(kwargs, "SIMD2020v2_Vigintile", "vigintile")
        rename_key(kwargs, "SIMD2020v2_Decile", "decile")
        rename_key(kwargs, "SIMD2020v2_Quintile", "quintile")
        rename_key(
            kwargs, "SIMD2020v2_Income_Domain_Rank", "income_domain_rank"
        )
        rename_key(
            kwargs, "SIMD2020_Employment_Domain_Rank", "employment_domain_rank"
        )
        rename_key(
            kwargs, "SIMD2020_Education_Domain_Rank", "education_domain_rank"
        )
        rename_key(kwargs, "SIMD2020_Health_Domain_Rank", "health_domain_rank")
        rename_key(kwargs, "SIMD2020_Access_Domain_Rank", "access_domain_rank")
        rename_key(kwargs, "SIMD2020_Crime_Domain_Rank", "crime_domain_rank")
        rename_key(
            kwargs, "SIMD2020_Housing_Domain_Rank", "housing_domain_rank"
        )
        rename_key(kwargs, "Population", "population")
        rename_key(kwargs, "Working_Age_Population", "working_age_population")
        rename_key(kwargs, "URclass", "urban_rural_class")
        rename_key(kwargs, "URname", "urban_rural_name")
        rename_key(kwargs, "IZcode", "intermediate_zone_code")
        rename_key(kwargs, "IZname", "intermediate_zone_name")
        rename_key(kwargs, "LAcode", "local_authority_code")
        rename_key(kwargs, "LAname", "local_authority_name")
        rename_key(kwargs, "HBcode", "health_board_code")
        rename_key(kwargs, "HBname", "health_board_name")
        rename_key(kwargs, "MMWcode", "multi_member_ward_code")
        rename_key(kwargs, "MMWname", "multi_member_ward_name")
        rename_key(
            kwargs, "SPCcode", "scottish_parliamentary_constituency_code"
        )
        rename_key(
            kwargs, "SPCname", "scottish_parliamentary_constituency_name"
        )

        convert_int(kwargs, "imd_rank")
        convert_int(kwargs, "vigintile")
        convert_int(kwargs, "decile")
        convert_int(kwargs, "quintile")
        convert_float(kwargs, "income_domain_rank")
        convert_float(kwargs, "employment_domain_rank")
        convert_float(kwargs, "education_domain_rank")
        convert_float(kwargs, "health_domain_rank")
        convert_float(kwargs, "access_domain_rank")
        convert_float(kwargs, "crime_domain_rank")
        convert_float(kwargs, "housing_domain_rank")
        convert_int(kwargs, "population")
        convert_int(kwargs, "working_age_population")
        convert_int(kwargs, "urban_rural_class")
        super().__init__(**kwargs)


class IMDLookupWA2014(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Wales 2014.
    """

    __filename__ = "IMD lookup WA as at 12_14.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_wales_2014"

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LSOA11CD", "lsoa_code")
        rename_key(kwargs, "LSOA11NM", "lsoa_name")
        rename_key(kwargs, "IMD14", "imd_rank")
        convert_int(kwargs, "imd_rank")
        super().__init__(**kwargs)


class IMDLookupWA2019(Base):
    """
    Represents the Index of Multiple Deprivation (IMD), Wales 2019.
    """

    __filename__ = "IMD lookup WA as at 12_19.xlsx"
    __tablename__ = "imd_index_multiple_deprivation_wales_2019"

    fid = Column(Integer)  # MB: Don't know what this is
    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    lad_code = Column(String(CODE_LEN))
    lad_name = Column(String(NAME_LEN))
    lad_name_welsh = Column(String(NAME_LEN))

    imd_rank = Column(Integer)

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "FID", "fid")
        rename_key(kwargs, "lsoa11cd", "lsoa_code")
        rename_key(kwargs, "lsoa11nm", "lsoa_name")
        rename_key(kwargs, "ladcd", "lad_code")
        rename_key(kwargs, "ladnm", "lad_name")
        rename_key(kwargs, "ladnmw", "lad_name_welsh")
        rename_key(kwargs, "wimd_2019", "imd_rank")
        convert_int(kwargs, "imd_rank")
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
        rename_key(kwargs, "LAU219CD", "lau2_code")
        rename_key(kwargs, "LAU219NM", "lau2_name")
        super().__init__(**kwargs)


class LAD2019(Base):
    """
    Represents local authority districts (LADs), UK 2019.
    """

    __filename__ = "LA_UA names and codes UK as at 12_19.xlsx"
    __tablename__ = "lad_local_authority_district_2019"

    lad_code = Column(String(CODE_LEN), primary_key=True)
    lad_name = Column(String(NAME_LEN))
    lad_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LAD19CD", "lad_code")
        rename_key(kwargs, "LAD19NM", "lad_name")
        rename_key(kwargs, "LAD19NMW", "lad_name_welsh")
        super().__init__(**kwargs)


class LAD2023(Base):
    """
    Represents local authority districts (LADs), UK 2023.
    """

    __filename__ = "LA_UA names and codes UK as at 04_23.xlsx"
    __tablename__ = "lad_local_authority_district_2023"

    lad_code = Column(String(CODE_LEN), primary_key=True)
    lad_name = Column(String(NAME_LEN))
    lad_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LAD23CD", "lad_code")
        rename_key(kwargs, "LAD23NM", "lad_name")
        rename_key(kwargs, "LAD23NMW", "lad_name_welsh")
        super().__init__(**kwargs)


class LAD23LAU121ITL321ITL221ITL121(Base):
    """
    Represents Local Authority Districts (LADs), Local Administrative Units
    (LAUs) and (International Territorial Levels (ITLs). Following the UK's
    departure from the EU, ITLs replace but mirror the former NUTS
    classification.
    """

    __filename__ = "LAD23_LAU121_ITL321_ITL221_ITL121_UK_LU.xlsx"
    __tablename__ = "lad23_lau121_itl321_itl221_itl121"

    # lad_code is not unique but lau1 appears to be and is referenced from the
    # itl field in the postcode table.
    lad_code = Column(String(CODE_LEN))
    lad_name = Column(String(NAME_LEN))
    lau1_code = Column(String(CODE_LEN), primary_key=True)
    lau1_name = Column(String(NAME_LEN))
    itl3_code = Column(String(5))
    itl3_name = Column(String(NAME_LEN))
    itl2_code = Column(String(4))
    itl2_name = Column(String(NAME_LEN))
    itl1_code = Column(String(3))
    itl1_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LAD23CD", "lad_code")
        rename_key(kwargs, "LAD23NM", "lad_name")
        rename_key(kwargs, "LAU121CD", "lau1_code")
        rename_key(kwargs, "LAU121NM", "lau1_name")
        rename_key(kwargs, "ITL321CD", "itl3_code")
        rename_key(kwargs, "ITL321NM", "itl3_name")
        rename_key(kwargs, "ITL221CD", "itl2_code")
        rename_key(kwargs, "ITL221NM", "itl2_name")
        rename_key(kwargs, "ITL121CD", "itl1_code")
        rename_key(kwargs, "ITL121NM", "itl1_name")
        super().__init__(**kwargs)


class LEP2017(Base):
    """
    Represents Local Enterprise Partnerships (LEPs), England 2017.
    """

    __filename__ = "LEP names and codes EN as at 04_17 v2.xlsx"
    __tablename__ = "lep_local_enterprise_partnership_england_2017"
    # __debug_content__ = True

    lep_code = Column(String(CODE_LEN), primary_key=True)
    lep_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LEP17CD", "lep_code")
        rename_key(kwargs, "LEP17NM", "lep_name")
        super().__init__(**kwargs)


class LEP2021(Base):
    """
    Represents Local Enterprise Partnerships (LEPs), England 2021.
    """

    __filename__ = "LEP names and codes EN as at 04_21 v2.xlsx"
    __tablename__ = "lep_local_enterprise_partnership_england_2021"
    # __debug_content__ = True

    lep_code = Column(String(CODE_LEN), primary_key=True)
    lep_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LEP21CD", "lep_code")
        rename_key(kwargs, "LEP21NM", "lep_name")
        super().__init__(**kwargs)


class LOC2022(Base):
    """
    Represents Sub-ICB Locations (LOCs), UK 2022.
    Replaces CCGs following Health and Care Act 2022.
    """

    __filename__ = "LOC names and codes UK as at 07_22.xlsx"
    __tablename__ = "loc_sub_icb_locations_2022"

    loc_ons_code = Column(String(CODE_LEN), primary_key=True)
    loc_ods_code = Column(String(9))
    loc_name = Column(String(NAME_LEN))
    loc_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LOC22CD", "loc_ons_code")
        rename_key(kwargs, "LOC22CDH", "loc_ods_code")
        rename_key(kwargs, "LOC22NM", "loc_name")
        rename_key(kwargs, "LOC22NMW", "loc_name_welsh")
        super().__init__(**kwargs)


class LSOA2001(Base):
    """
    Represents lower layer super output area (LSOAs), UK 2001.
    """

    __filename__ = "LSOA (2001) names and codes EW & NI as at 02_05.xlsx"
    __tablename__ = "lsoa_lower_layer_super_output_area_2001"

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "LSOA01CD", "lsoa_code")
        rename_key(kwargs, "LSOA01NM", "lsoa_name")
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
        rename_key(kwargs, "LSOA11CD", "lsoa_code")
        rename_key(kwargs, "LSOA11NM", "lsoa_name")
        super().__init__(**kwargs)


class LSOA2021(Base):
    """
    Represents lower layer super output area (LSOAs), England and Wales 2021.
    """

    __filename__ = "LSOA (2021) names and codes EW as at 12_21.xlsx"
    __tablename__ = "lsoa_lower_layer_super_output_area_2021"

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "lsoa21cd", "lsoa_code")
        rename_key(kwargs, "lsoa21nm", "lsoa_name")
        super().__init__(**kwargs)


class MSOA2001(Base):
    """
    Represents middle layer super output areas (MSOAs), UK 2001.
    """

    __filename__ = "MSOA (2001) names and codes GB as at 11_11.xlsx"
    __tablename__ = "msoa_middle_layer_super_output_area_2001"

    msoa_code = Column(String(CODE_LEN), primary_key=True)
    msoa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "MSOA01CD", "msoa_code")
        rename_key(kwargs, "MSOA01NM", "msoa_name")
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
        rename_key(kwargs, "MSOA11CD", "msoa_code")
        rename_key(kwargs, "MSOA11NM", "msoa_name")
        super().__init__(**kwargs)


class MSOA2021(Base):
    """
    Represents middle layer super output areas (MSOAs), UK 2021.
    """

    __filename__ = "MSOA (2021) names and codes EW as at 12_21.xlsx"
    __tablename__ = "msoa_middle_layer_super_output_area_2021"

    msoa_code = Column(String(CODE_LEN), primary_key=True)
    msoa_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "MSOA21CD", "msoa_code")
        rename_key(kwargs, "MSOA21NM", "msoa_name")
        super().__init__(**kwargs)


class NationalPark2016(Base):
    """
    Represents national parks, Great Britain 2016.
    """

    __filename__ = "National Park names and codes GB as at 08_16.xlsx"
    __tablename__ = "park_national_park_2016"

    park_code = Column(String(CODE_LEN), primary_key=True)
    park_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "NPARK16CD", "park_code")
        rename_key(kwargs, "NPARK16NM", "park_name")
        super().__init__(**kwargs)


class NationalPark2022(Base):
    """
    Represents national parks, Great Britain 2022.
    """

    __filename__ = "National Park names and codes GB as at 03_23.xlsx"
    __tablename__ = "park_national_park_2022"

    park_code = Column(String(CODE_LEN), primary_key=True)
    park_name = Column(String(NAME_LEN))
    park_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "NPARK22CD", "park_code")
        rename_key(kwargs, "NPARK22NM", "park_name")
        rename_key(kwargs, "NPARK22NMW", "park_name_welsh")
        super().__init__(**kwargs)


class NHSER2022(Base):
    """
    Represents NHS England (Region) Names and Codes 2022.
    """

    __filename__ = "NHSER names and codes EN as at 07_22.xlsx"
    __tablename__ = "nhser_nhs_england_region_2022"

    region_ons_code = Column(String(CODE_LEN), primary_key=True)
    region_nhser_code = Column(String(3))
    region_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "NHSER22CD", "region_ons_code")
        rename_key(kwargs, "NHSER22CDH", "region_nhser_code")
        rename_key(kwargs, "NHSER22NM", "region_name")
        super().__init__(**kwargs)


class NHSER2024(Base):
    """
    Represents NHS England (Region) Names and Codes 2024.
    """

    __filename__ = "NHSER names and codes EN as at 04_24.xlsx"
    __tablename__ = "nhser_nhs_england_region_2024"

    region_ons_code = Column(String(CODE_LEN), primary_key=True)
    region_nhser_code = Column(String(3))
    region_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "NHSER24CD", "region_ons_code")
        rename_key(kwargs, "NHSER24CDH", "region_nhser_code")
        rename_key(kwargs, "NHSER24NM", "region_name")
        super().__init__(**kwargs)


class Parish2018(Base):
    """
    Represents parishes, England & Wales 2018.
    """

    __filename__ = "Parish_NCP names and codes EW as at 12_18.xlsx"
    __tablename__ = "parish_ncp_england_wales_2018"

    parish_code = Column(String(CODE_LEN), primary_key=True)
    parish_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "PARNCP18CD", "parish_code")
        rename_key(kwargs, "PARNCP18NM", "parish_name")
        super().__init__(**kwargs)


class Parish2021(Base):
    """
    Represents parishes, England & Wales 2021.
    """

    __filename__ = "Parish_NCP names and codes EW as at 12_21.xlsx"
    __tablename__ = "parish_ncp_england_wales_2021"

    parish_code = Column(String(CODE_LEN), primary_key=True)
    parish_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "PARNCP21CD", "parish_code")
        rename_key(kwargs, "PARNCP21NM", "parish_name")
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
        rename_key(kwargs, "PCTCD", "pct_code")
        rename_key(kwargs, "PCTCDO", "pct_code_old")
        rename_key(kwargs, "PCTNM", "pct_name")
        rename_key(kwargs, "PCTNMW", "pct_name_welsh")
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
        rename_key(kwargs, "PFA15CD", "pfa_code")
        rename_key(kwargs, "PFA15NM", "pfa_name")
        super().__init__(**kwargs)


class GOR(Base):
    """
    Represents Government Office Regions (GORs), England 2010.

    The nine GORs were abolished in 2011 and are now known as Regions for
    statistical purposes. See RGN2020.
    """

    __filename__ = "Region names and codes EN as at 12_10 (RGN).xlsx"
    __tablename__ = "gor_govt_office_region_england_2010"

    gor_code = Column(String(CODE_LEN), primary_key=True)
    gor_code_old = Column(String(1))
    gor_name = Column(String(NAME_LEN))
    gor_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "GOR10CD", "gor_code")
        rename_key(kwargs, "GOR10CDO", "gor_code_old")
        rename_key(kwargs, "GOR10NM", "gor_name")
        rename_key(kwargs, "GOR10NMW", "gor_name")
        super().__init__(**kwargs)


class RGN2020(Base):
    """
    Represents Regions (RGNs), England 2020.
    """

    __filename__ = "Region names and codes EN as at 12_20 (RGN).xlsx"
    __tablename__ = "rgn_region_england_2020"

    rgn_code = Column(String(CODE_LEN), primary_key=True)
    rgn_code_old = Column(String(1))
    rgn_name = Column(String(NAME_LEN))
    rgn_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "RGN20CD", "rgn_code")
        rename_key(kwargs, "RGN20CDO", "rgn_code_old")
        rename_key(kwargs, "RGN20NM", "rgn_name")
        rename_key(kwargs, "RGN20NMW", "rgn_name")
        super().__init__(**kwargs)


class RuralUrban2011(Base):
    """
    Represents Rural Urban indicators, GB 2011.
    """

    __filename__ = "Rural Urban (2011) Indicator names and codes GB as at 12_16.xlsx"  # noqa: E501
    __tablename__ = "rural_urban_indicator_2011"

    ru_code = Column(String(2), primary_key=True)
    ru_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "RU11IND", "ru_code")
        rename_key(kwargs, "RU11NM", "ru_name")
        super().__init__(**kwargs)


class SDZ2021(Base):
    """
    Represents Super Data Zones, Northern Ireland, 2021.
    """

    __filename__ = "SDZ names and codes NI as at 03_21.xlsx"
    __tablename__ = "sdz_super_data_zones_2021"

    sdz_code = Column(String(CODE_LEN), primary_key=True)
    sdz_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "SDZ21CD", "sdz_code")
        rename_key(kwargs, "SDZ21NM", "sdz_name")
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
        rename_key(kwargs, "SSR95CD", "ssr_code")
        rename_key(kwargs, "SSR95NM", "ssr_name")
        convert_int(kwargs, "ssr_code")
        super().__init__(**kwargs)


class StatisticalWard2005(Base):
    """
    Represents "Statistical" wards. These no longer exist. See ONSPD user
    guide.
    """

    __filename__ = "Statistical ward names and codes UK as at 2005.xlsx"
    __tablename__ = "statistical_ward_2005"

    ward_code = Column(String(6), primary_key=True)
    ward_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "WDSTL05CD", "ward_code")
        rename_key(kwargs, "WDSTL05NM", "ward_name")
        super().__init__(**kwargs)


class SICBLEN2023(Base):
    """
    Represents Sub ICB Locations in England. Seems to be a subset of LOC2022.
    """

    __filename__ = "Sub_ICB Location and Local Health Board names and codes EW as at 04_23.xlsx"  # noqa: E501
    __tablename__ = "sicbl_sub_icb_locations_en_2023"

    sicbl_ons_code = Column(String(CODE_LEN), primary_key=True)
    sicbl_ods_code = Column(String(5))
    sicbl_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "SICBL23CD", "sicbl_ons_code")
        rename_key(kwargs, "SICBL23CDH", "sicbl_ods_code")
        rename_key(kwargs, "SICBL23NM", "sicbl_name")
        super().__init__(**kwargs)


class SICBLUK2023(Base):
    """
    Represents Sub ICB Locations in UK 2023.
    """

    __filename__ = "Sub_ICB Location and Local Health Board names and codes UK as at 04_23.xlsx"  # noqa: E501
    __tablename__ = "sicbl_sub_icb_locations_uk_2023"

    sicbl_ons_code = Column(String(CODE_LEN), primary_key=True)
    sicbl_ods_code = Column(String(5))
    sicbl_name = Column(String(NAME_LEN))
    sicbl_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "SICBL23CD", "sicbl_ons_code")
        rename_key(kwargs, "SICBL23CDH", "sicbl_ods_code")
        rename_key(kwargs, "SICBL23NM", "sicbl_name")
        rename_key(kwargs, "SICBL23NMW", "sicbl_name_welsh")
        super().__init__(**kwargs)


class Ward2019(Base):
    """
    Represents electoral wards, UK 2019.
    """

    __filename__ = "Ward names and codes UK as at 12_19.xlsx"
    __tablename__ = "electoral_ward_2019"

    ward_code = Column(String(CODE_LEN), primary_key=True)
    ward_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "WD19CD", "ward_code")
        rename_key(kwargs, "WD19NM", "ward_name")
        super().__init__(**kwargs)


class Ward2024(Base):
    """
    Represents electoral wards, UK 2024.
    """

    __filename__ = "Ward names and codes UK as at ??_24.xlsx"
    __tablename__ = "electoral_ward_2024"

    ward_code = Column(String(CODE_LEN), primary_key=True)
    ward_name = Column(String(NAME_LEN))
    ward_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "WD24CD", "ward_code")
        rename_key(kwargs, "WD24NM", "ward_name")
        rename_key(kwargs, "WD24NMW", "ward_name_welsh")
        super().__init__(**kwargs)


class TECLEC(Base):
    """
    Represents Local Learning and Skills Council (LLSC)
    Dept. of Children, Education, Lifelong Learning and Skills (DCELLS)
    Enterprise Region (ER).
    """

    __filename__ = "TECLEC names and codes UK as at 12_16.xlsx"
    __tablename__ = "teclec_2016"

    teclec_code = Column(String(CODE_LEN), primary_key=True)
    teclec_code_old = Column(String(5))
    teclec_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "TECLECCD", "teclec_code")
        rename_key(kwargs, "TECLECCDO", "teclec_code_old")
        rename_key(kwargs, "TECLECNM", "teclec_name")
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
        rename_key(kwargs, "TTWA11CD", "ttwa_code")
        rename_key(kwargs, "TTWA11NM", "ttwa_name")
        super().__init__(**kwargs)


class UrbanRural2001(Base):
    """
    Represents Urban Rural indicators, UK 2001.
    """

    __filename__ = "Urban Rural (2001) Indicator names and codes UK.xlsx"
    __tablename__ = "urban_rural_indicator_2001"

    # ur_code is not unique
    id = Column(Integer, primary_key=True, autoincrement=True)
    ur_code = Column(String(1))
    ur_name = Column(String(200))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "UR01IND", "ur_code")
        rename_key(kwargs, "UR01NM", "ur_name")
        super().__init__(**kwargs)


class WestminsterConstituency2014(Base):
    """
    Represents Westminster parliamentary constituencies, UK 2014.
    """

    __filename__ = (
        "Westminster Parliamentary Constituency names and codes "
        "UK as at 12_14.xlsx"
    )
    __tablename__ = "pcon_westminster_parliamentary_constituency_2014"

    pcon_code = Column(String(CODE_LEN), primary_key=True)
    pcon_name = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "PCON14CD", "pcon_code")
        rename_key(kwargs, "PCON14NM", "pcon_name")
        super().__init__(**kwargs)


class WestminsterConstituency2024(Base):
    """
    Represents Westminster parliamentary constituencies, UK 2024.
    """

    __filename__ = (
        "Westminster Parliamentary Constituency names and codes "
        "UK as at 12_24.xlsx"
    )
    __tablename__ = "pcon_westminster_parliamentary_constituency_2024"

    pcon_code = Column(String(CODE_LEN), primary_key=True)
    pcon_name = Column(String(NAME_LEN))
    pcon_name_welsh = Column(String(NAME_LEN))

    def __init__(self, **kwargs: Any) -> None:
        rename_key(kwargs, "PCON24CD", "pcon_code")
        rename_key(kwargs, "PCON24NM", "pcon_name")
        rename_key(kwargs, "PCON24NMW", "pcon_name_welsh")
        super().__init__(**kwargs)


_ = '''
# =============================================================================
# Models: centroids
# =============================================================================
# https://webarchive.nationalarchives.gov.uk/20160105160709/https://www.ons.gov.uk/ons/guide-method/geography/products/census/spatial/centroids/index.html  # noqa: E501
#
# Looking at lower_layer_super_output_areas_(e+w)_2011_population_weighted_centroids_v2.zip : # noqa: E501
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
    """
    __filename__ = "LSOA_2011_EW_PWC_COORD_V2.CSV"
    __tablename__ = "pop_weighted_centroids_lsoa_2011"
    # __debug_content__ = True

    lsoa_code = Column(String(CODE_LEN), primary_key=True)
    lsoa_name = Column(String(NAME_LEN))
    bng_north = Column(Integer, comment="British National Grid, North (m)")
    bng_east = Column(Integer, comment="British National Grid, East (m)")
    # https://en.wikipedia.org/wiki/Ordnance_Survey_National_Grid#All-numeric_grid_references  # noqa: E501
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


def populate_postcode_table(
    filename: str,
    session: Session,
    replace: bool = False,
    startswith: List[str] = None,
    reportevery: int = DEFAULT_REPORT_EVERY,
    commit: bool = True,
    commitevery: int = DEFAULT_COMMIT_EVERY,
    dump: bool = False,
) -> None:
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
        dump: Dump a sample of lines from the table
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
    num_inserted = 0
    num_dumped = 0
    extra_fields = []  # type: List[str]
    db_fields = sorted(
        k for k in table.columns.keys() if k != COL_POSTCODE_NOSPACE
    )
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            n += 1
            if n % reportevery == 0:
                log.info(
                    f"Processing row {n}: "
                    f"{row[COL_POSTCODE_VARIABLE_LENGTH_SPACE]} "
                    f"({num_inserted} inserted)"
                )
                # log.debug(row)
            if n == 1:
                file_fields = sorted(row.keys())
                missing_fields = sorted(set(db_fields) - set(file_fields))
                extra_fields = sorted(set(file_fields) - set(db_fields))
                if missing_fields:
                    log.warning(
                        f"Fields in database but not file: {missing_fields}"
                    )
                if extra_fields:
                    log.warning(
                        f"Fields in file but not database : {extra_fields}"
                    )

            for k in extra_fields:
                del row[k]
            if startswith:
                ok = False
                for s in startswith:
                    if row["pcd"].startswith(s):
                        ok = True
                        break
                if not ok:
                    continue
            obj = Postcode(**row)
            session.add(obj)
            num_inserted += 1
            if dump and num_dumped <= ROWS_TO_DUMP:
                print("-" * 80)
                for k, v in row.items():
                    v = str("" if v is None else v)
                    print(f"| {k:{DUMP_FORMAT}}| {v}")
                num_dumped += 1

            if commit and n % commitevery == 0:
                commit_and_announce(session)
    if commit:
        commit_and_announce(session)


# BASETYPE = TypeVar('BASETYPE', bound=Base)
# http://mypy.readthedocs.io/en/latest/kinds_of_types.html
# https://docs.python.org/3/library/typing.html


def populate_generic_lookup_table(
    sa_class: GenericLookupClassType,
    filename: str,
    session: Session,
    replace: bool = False,
    commit: bool = True,
    commitevery: int = DEFAULT_COMMIT_EVERY,
    dump: bool = False,
) -> None:
    """
    Populates one of many generic lookup tables with ONSPD data.

    The ``.TXT`` files look at first glance like tab-separated values files,
    but in some cases have inconsistent numbers of tabs (e.g. "2011 Census
    Output Area Classification Names and Codes UK.txt"). So we'll use the
    ``.XLSX`` files.

    If the headings parameter is passed, those headings are used. Otherwise,
    the first row is used for headings.

    Args:
        sa_class: SQLAlchemy ORM class
        filename: .XLSX file containing lookup table
        session: SQLAlchemy ORM database session
        replace: replace tables even if they exist? (Otherwise, skip existing
            tables.)
        commit: COMMIT the session once we've inserted the data?
        commitevery: if committing: commit every *n* rows inserted
        dump: Dump a sample of lines from every table
    """
    tablename = sa_class.__tablename__

    headings = getattr(sa_class, "__headings__", [])
    debug = getattr(sa_class, "__debug_content__", False)
    duplicates = getattr(sa_class, "__duplicates__", [])

    if not replace:
        engine = session.bind
        if engine.has_table(tablename):
            log.info(f"Table {tablename} exists; skipping")
            return

    log.info(f"Dropping/recreating table: {tablename}")
    sa_class.__table__.drop(checkfirst=True)
    sa_class.__table__.create(checkfirst=True)

    log.info(f'Processing file "{filename}" -> table "{tablename}"')
    dict_iterator = read_spreadsheet(filename, headings)

    row = 0
    num_inserted = 0
    num_dumped = 0

    for datadict in dict_iterator:
        row += 1

        if debug:
            log.critical(f"{row}: {datadict}")
        # filter out blanks:
        datadict = {k: v for k, v in datadict.items() if k}
        if dump and row == 1:
            dump_header = "|".join(
                [f"{k:{DUMP_FORMAT}}" for k in datadict.keys()]
            )
            print(dump_header)
            print("-" * len(dump_header))

        values = datadict.values()
        if any(values):
            # noinspection PyNoneFunctionAssignment
            obj = sa_class(**datadict)
            if datadict in duplicates:
                commit_and_announce(session)

            session.add(obj)
            if datadict in duplicates:
                try:
                    commit_and_announce(session)
                except IntegrityError:
                    log.info(f"Skipping duplicate row {datadict}")
                    session.rollback()
            num_inserted += 1
            if dump and num_dumped <= ROWS_TO_DUMP:
                dump_values = [str("" if v is None else v) for v in values]
                print("|".join([f"{v:{DUMP_FORMAT}}" for v in dump_values]))
                num_dumped += 1

            if commit and num_inserted % commitevery == 0:
                commit_and_announce(session)
    if commit:
        commit_and_announce(session)
    log.info(f"... inserted {num_inserted} rows")


def read_spreadsheet(
    filename: str, headings: List[str]
) -> Generator[Dict, None, None]:
    if os.path.splitext(filename)[1].lower() != ".xlsx":
        raise ValueError(
            f"Unable to import {filename}. Only .xlsx files are supported."
        )

    def dict_from_rows(
        row_iterator: Iterable[List],
    ) -> Generator[Dict, None, None]:
        local_headings = headings
        first_row = True
        for row in row_iterator:
            values = values_from_row(row)
            if first_row and not local_headings:
                local_headings = values
            else:
                yield dict(zip(local_headings, values))
            first_row = False

    workbook = openpyxl.load_workbook(filename)  # read_only=True
    # openpyxl BUG: with read_only=True, cells can have None as their value
    # when they're fine if opened in non-read-only mode.
    # May be related to this:
    # https://bitbucket.org/openpyxl/openpyxl/issues/601/read_only-cell-row-column-attributes-are

    # Assume the first sheet is the one with the data in it.
    # Choosing the active sheet is unreliable for some files.
    # If this proves to be a wrong assumption, support an optional named
    # sheet to load for each class.
    sheet = workbook.worksheets[0]
    return dict_from_rows(sheet.iter_rows())


# =============================================================================
# Docs
# =============================================================================


def show_docs() -> None:
    """
    Print the column ``doc`` attributes from the :class:`Postcode` class, in
    tabular form, to stdout.
    """
    colnames = ["Postcode field", "Description"]
    # noinspection PyUnresolvedReferences
    table = Postcode.__table__
    columns = sorted(table.columns.keys())
    rows = []  # type: List[List[str]]
    for col in columns:
        rows.append([col, getattr(Postcode, col).comment])
    tabletext = make_twocol_table(colnames, rows, vertical_lines=False)
    print(tabletext)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point. See command-line help.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=RawDescriptionArgumentDefaultsRichHelpFormatter,
        description=r"""
-   This program reads data from the UK Office of National Statistics Postcode
    Database (ONSPD) and inserts it into a database.

-   You will need to download the ONSPD from
        https://geoportal.statistics.gov.uk
    e.g. ONSPD_AUG_2024.zip and unzip it (>3.7 Gb) to a directory.
    Tell this program which directory you used.

-   Specify your database as an SQLAlchemy connection URL: see
        https://docs.sqlalchemy.org/en/latest/core/engines.html
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

    See https://www.ons.gov.uk/methodology/geography/licences
    """,  # noqa: E501
    )
    parser.add_argument(
        "--dir",
        default=DEFAULT_ONSPD_DIR,
        help="Root directory of unzipped ONSPD download",
    )
    parser.add_argument("--url", help="SQLAlchemy database URL")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    parser.add_argument(
        "--reportevery",
        type=int,
        default=DEFAULT_REPORT_EVERY,
        help="Report every n rows",
    )
    parser.add_argument(
        "--commitevery",
        type=int,
        default=DEFAULT_COMMIT_EVERY,
        help=(
            "Commit every n rows. If you make this too large "
            "(relative e.g. to your MySQL max_allowed_packet setting, you may"
            " get crashes with errors like 'MySQL has gone away'."
        ),
    )
    parser.add_argument(
        "--startswith",
        nargs="+",
        help="Restrict to postcodes that start with one of these strings",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace tables even if they exist (default: skip existing "
        "tables)",
    )
    parser.add_argument(
        "--skiplookup",
        action="store_true",
        help="Skip generation of code lookup tables",
    )
    parser.add_argument(
        "--specific_lookup_tables",
        nargs="*",
        help="Within the lookup tables, process only specific named tables",
    )
    parser.add_argument(
        "--list_lookup_tables",
        action="store_true",
        help="List all possible lookup tables, then stop",
    )
    parser.add_argument(
        "--skippostcodes",
        action="store_true",
        help="Skip generation of main (large) postcode table",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Dump a sample of rows from each table",
    )
    parser.add_argument(
        "--docsonly",
        action="store_true",
        help="Show help for postcode table then stop",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()
    rootlogger = logging.getLogger()
    configure_logger_for_colour(
        rootlogger, level=logging.DEBUG if args.verbose else logging.INFO
    )
    log.debug(f"args = {args!r}")

    if args.docsonly:
        show_docs()
        sys.exit(0)

    classlist = [
        # Core lookup tables:
        # In alphabetical order of filename:
        OAClassification2001,
        OAClassification2011,
        BUA2013,
        BUA2022,
        BUA2024,
        BUASD,
        CALNCV2023,
        CASWard,
        CCG,
        Country,
        CountyED2023,
        County2019,
        County2023,
        EER,
        HealthArea2019,
        ICB2023,
        IMDLookupEN2015,
        IMDLookupEN2019,
        IMDLookupNI2017,
        IMDLookupSC2016,
        IMDLookupSC2020,
        IMDLookupWA2014,
        IMDLookupWA2019,
        LAU,
        LAD2019,
        LAD2023,
        LAD23LAU121ITL321ITL221ITL121,
        LEP2017,
        LEP2021,
        LOC2022,
        LSOA2001,
        LSOA2011,
        LSOA2021,
        MSOA2001,
        MSOA2011,
        MSOA2021,
        NationalPark2016,
        NationalPark2022,
        NHSER2022,
        NHSER2024,
        Parish2018,
        Parish2021,
        PCT2019,
        PFA,
        GOR,
        RGN2020,
        RuralUrban2011,
        SDZ2021,
        SSR,
        StatisticalWard2005,
        SICBLEN2023,
        SICBLUK2023,
        TECLEC,
        TTWA,
        UrbanRural2001,
        Ward2019,
        Ward2024,
        WestminsterConstituency2014,
        WestminsterConstituency2024,
        # Centroids:
        # PopWeightedCentroidsLsoa2011,
    ]

    if args.list_lookup_tables:
        tables_files = []  # type: List[Tuple[str, str]]
        for sa_class in classlist:
            tables_files.append(
                (sa_class.__tablename__, sa_class.__filename__)
            )
        tables_files.sort(key=lambda x: x[0])
        for table, file in tables_files:
            print(f"Table {table} from file {file!r}")
        return

    if not args.url:
        print("Must specify URL")
        return

    engine = create_engine(args.url, echo=args.echo, future=True)
    metadata.bind = engine
    session = sessionmaker(bind=engine, future=True)()

    log.info(f"Using directory: {args.dir}")
    datadir = args.dir

    if not args.skiplookup:
        all_files = [os.path.basename(f) for f in find("*.xlsx", datadir)]
        found_files = []
        missing_files = []
        omitted_files = []

        for sa_class in classlist:
            filename = None

            try:
                filename = find_first(sa_class.__filename__, datadir)
                basename = os.path.basename(filename)
            except IndexError:
                log.info(
                    f"Could not find match for {sa_class.__filename__}; "
                    "skipping"
                )
                missing_files.append(sa_class.__filename__)
                continue

            if (
                args.specific_lookup_tables
                and sa_class.__tablename__ not in args.specific_lookup_tables
            ):
                omitted_files.append(basename)
                continue

            populate_generic_lookup_table(
                sa_class=sa_class,
                filename=filename,
                session=session,
                replace=args.replace,
                commit=True,
                commitevery=args.commitevery,
                dump=args.dump,
            )
            found_files.append(basename)

        extra_files = sorted(
            set(all_files) - set(found_files) - set(omitted_files)
        )
        if extra_files:
            log.warning(
                "You may be using a later version of ONSPD and the importer "
                f"didn't recognise these files: {extra_files}"
            )

        if omitted_files:
            log.warning(
                f"These files were deliberately omitted: {omitted_files}"
            )

        if missing_files:
            log.info(
                f"These files were not found under {datadir}: {missing_files}"
            )

    if not args.skippostcodes:
        populate_postcode_table(
            filename=find_first("ONSPD_*.csv", datadir),
            session=session,
            replace=args.replace,
            startswith=args.startswith,
            reportevery=args.reportevery,
            commit=True,
            commitevery=args.commitevery,
            dump=args.dump,
        )


if __name__ == "__main__":
    main()
