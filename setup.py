"""
setup.py

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

CRATE setup file

To use:

    python setup.py sdist

    twine upload dist/*

To install in development mode:

    pip install -e .

More reasoning is in the setup.py file for CamCOPS.
"""

from setuptools import find_packages, setup
from codecs import open
import os
import platform

from crate_anon.common.constants import CrateCommand
from crate_anon.version import CRATE_VERSION, require_minimum_python_version

require_minimum_python_version()


# =============================================================================
# Constants
# =============================================================================

# Directories
THIS_DIR = os.path.abspath(os.path.dirname(__file__))  # .../crate

# OS; setup.py is executed on the destination system at install time, so:
RUNNING_WINDOWS = platform.system() == "Windows"

# Get the long description from the README file
with open(os.path.join(THIS_DIR, "README.rst"), encoding="utf-8") as f:
    LONG_DESCRIPTION = f.read()

# Package dependencies
INSTALL_REQUIRES = [
    "amqp==5.3.1",  # amqp is used by Celery
    "appdirs==1.4.4",  # where to store some temporary data
    "arrow==0.15.7",  # [pin exact version from cardinal_pythonlib]
    "beautifulsoup4==4.9.1",  # [pin exact version from cardinal_pythonlib]
    "cardinal_pythonlib==2.1.0",  # RNC libraries
    "cairosvg==2.7.0",  # work with SVG files
    "celery==5.2.7",  # back-end scheduling
    "chardet==5.2.0",  # character encoding detection for cardinal_pythonlib
    "cherrypy==18.6.0",  # Cross-platform web server
    "colorlog==4.1.0",  # colour in logs
    "distro==1.5.0",  # replaces platform.linux_distribution
    "django==4.2.22",  # for main CRATE research database web server
    "django-debug-toolbar==3.2.1",  # Django debug toolbar
    # "django-debug-toolbar-template-profiler==2.0.1",  # v1.0.1 removed 2017-01-30: division by zero when rendering time is zero  # noqa: E501
    "django-extensions==3.1.1",  # for graph_models, show_urls etc.
    "django-formtools==2.5.1",  # form wizards etc
    "django-picklefield==3.0.1",  # NO LONGER USED - dangerous to use pickle - but kept for migrations  # noqa: E501
    # "django-silk==4.0.1",  # Django profiler
    "djangorestframework==3.15.2",  # Anonymisation API support
    "django-sslserver==0.22",  # SSL development server for Django
    "django-tables2==2.7.5",  # Support for HTML tables within Django templates
    "drf-spectacular==0.27.2",  # Open API Schema and documentation
    "drf-spectacular-sidecar==2024.7.1",  # Static files for drf-spectacular
    "flashtext==2.7",  # fast word replacement with the FlashText algorithm
    "flower==2.0.1",  # debug Celery; web server; only runs explicitly
    "fuzzy==1.2.2",  # phonetic matching
    "gunicorn==23.0.0",  # UNIX only, though will install under Windows
    "gutenbergpy==0.3.4",  # Project Gutenberg API
    "jsonlines==3.0.0",  # JSON Lines format
    "kombu==5.3.7",  # AMQP library for Celery; requires VC++ under Windows
    "mako==1.2.2",  # templates with Python in
    "MarkupSafe==2.0.1",  # for HTML escaping
    # mmh3 requires VC++
    "mmh3==2.5.1",  # MurmurHash, for fast non-cryptographic hashing; optionally used by cardinal_pythonlib; requires VC++ under Windows?  # noqa: E501
    "numba==0.60.0",  # just-in-time compilation of functions
    "numpy==1.26.4",  # numerical work
    "openpyxl==3.0.7",  # read Excel (slower?)
    "ordered-set==4.1.0",  # ordered sets; search for ordered_set
    "pendulum==2.1.2",  # dates/times
    "Pillow==10.3.0",  # image processing; import as PIL (Python Imaging Library)  # noqa: E501
    "pdfkit==0.6.1",  # interface to wkhtmltopdf
    "prettytable==3.2.0",  # pretty formating of text-based tables
    "psutil==6.1.1",  # process management, cardinal_pythonlib dependency, not currently used  # noqa: E501
    "pyexcel-ods==0.6.0",  # for reading/writing ODS files
    "pyexcel-xlsx==0.6.0",  # for writing XLSX files (using openpyxl)
    "pygments==2.15.0",  # syntax highlighting
    "pyparsing==2.4.7",  # generic grammar parser
    "pypdf==6.0.0",  # create PDF files
    "python-dateutil==2.8.1",  # [pin exact version from cardinal_pythonlib]
    # "python-docx==0.8.10",  # needs lxml, which has Visual C++ dependencies under Windows  # noqa: E501
    # ... https://python-docx.readthedocs.org/en/latest/user/install.html
    "regex==2024.11.6",  # better regexes (cf. re)
    "rich-argparse==0.5.0",  # colourful help
    "semantic_version==2.8.5",  # semantic versioning; better than semver
    "sortedcontainers==2.2.2",  # for SortedSet
    "SQLAlchemy==2.0.36",  # database access
    "sqlparse==0.5.0",  # [pin exact version from cardinal_pythonlib]
    "unidecode==1.1.1",  # for removing accents
    # -------------------------------------------------------------------------
    # Packages for cloud NLP:
    # -------------------------------------------------------------------------
    "bcrypt==3.2.2",  # bcrypt encryption
    "cryptography==44.0.1",  # cryptography library
    # "mysqlclient",  # database access
    "paste==3.4.2",  # middleware; https://github.com/cdent/paste/
    "pyramid==1.10.4",  # Pyramid web framework
    "pyramid_tm==2.4",  # Pyramid transaction management
    "redis==4.5.4",  # interface to Redis in-memory key-value database
    "requests==2.32.4",  # HTTP requests
    "tornado==6.5",  # web framework
    "transaction==3.0.0",  # generic transaction management
    "urllib3==2.5.0",  # used by requests
    "waitress==3.0.1",  # pure-Python WSGI server
    "zope.sqlalchemy==1.3",  # Zope/SQLAlchemy transaction integration
    # -------------------------------------------------------------------------
    # For development only:
    # -------------------------------------------------------------------------
    "black==24.3.0",  # auto code formatter, keep in sync with .pre-commit-config.yaml  # noqa: E501
    "factory_boy==3.3.0",  # easier test data creation
    "faker==13.3.1",  # test data creation
    "faker-file[common]==0.17.13",  # test file creation
    "flake8==5.0.4",  # code checks, keep in sync with .pre-commit-config.yaml
    "docutils==0.19",
    "mistune<2.0.0",  # API documentation, 2.0.0 not compatible
    "paramiko==3.4.1",  # Python implementation of the SSHv2 protocol, required by faker-file  # noqa: E501
    "pre-commit==2.20.0",  # development only, various sanity checks on code
    "pytest==8.3.4",  # automatic testing
    "pytest-django==4.5.2",  # automatic testing
    "pytest-env==1.1.5",  # automatic testing
    "python-on-whales==0.68.0",  # python wrappers for testing with Docker
    "sphinx==7.1.2",  # documentation
    "sphinx_rtd_theme==3.0.2",  # documentation
    # ---------------------------------------------------------------------
    # For database connections (see manual): install manually
    # ---------------------------------------------------------------------
    # MySQL: one of:
    #   "PyMySQL",
    #   "mysqlclient",
    # SQL Server / ODBC route:
    #   "django-pyodbc-azure",
    #   "pyodbc",  # has C prerequisites
    #   "pypyodbc==1.3.3",
    # SQL Server / Embedded FreeTDS route:
    #   "django-pymssql",
    #   "django-mssql",
    #   "pymssql",
    # PostgreSQL:
    #   "psycopg2",  # has prerequisites (e.g. pg_config executable)
]

if RUNNING_WINDOWS:
    INSTALL_REQUIRES += [
        # Windows-specific stuff
        "pypiwin32==223",
    ]


# =============================================================================
# setup args
# =============================================================================

setup(
    name="crate-anon",  # "crate" is taken
    version=CRATE_VERSION,
    description="CRATE: clinical records anonymisation and text extraction",
    long_description=LONG_DESCRIPTION,
    # The project"s main homepage.
    url="https://crateanon.readthedocs.io",
    # Author details
    author="Rudolf Cardinal",
    author_email="rudolf@pobox.com",
    # Choose your license
    license="GNU General Public License v3 or later (GPLv3+)",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 5 - Production/Stable",
        # Indicate who your project is intended for
        "Intended Audience :: Science/Research",
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",  # noqa: E501
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: System :: Hardware",
        "Topic :: System :: Networking",
    ],
    keywords="anonymisation",
    packages=find_packages(),
    # finds all the .py files in subdirectories, as long as there are
    # __init__.py files
    include_package_data=True,  # use MANIFEST.in during install?
    # https://stackoverflow.com/questions/7522250/how-to-include-package-data-with-setuptools-distribute  # noqa: E501
    install_requires=INSTALL_REQUIRES,
    entry_points={
        "console_scripts": [
            # Format is "script=module:function".
            # Documentation
            "crate_help=crate_anon.tools.launch_docs:main",
            # Preprocessing
            f"{CrateCommand.AUTOIMPORTDB}=crate_anon.preprocess.autoimport_db:main",  # noqa: E501
            f"{CrateCommand.FETCH_WORDLISTS}=crate_anon.anonymise.fetch_wordlists:main",  # noqa: E501
            f"{CrateCommand.POSTCODES}=crate_anon.preprocess.postcodes:main",
            f"{CrateCommand.PREPROCESS_PCMIS}=crate_anon.preprocess.preprocess_pcmis:main",  # noqa: E501
            f"{CrateCommand.PREPROCESS_RIO}=crate_anon.preprocess.preprocess_rio:main",  # noqa: E501
            f"{CrateCommand.PREPROCESS_SYSTMONE}=crate_anon.preprocess.preprocess_systmone:main",  # noqa: E501
            # Linkage
            f"{CrateCommand.BULK_HASH}=crate_anon.linkage.bulk_hash:main",
            f"{CrateCommand.FUZZY_ID_MATCH}=crate_anon.linkage.fuzzy_id_match:main",  # noqa: E501
            # Anonymisation
            f"{CrateCommand.ANON_CHECK_TEXT_EXTRACTOR}=crate_anon.anonymise.check_text_extractor:main",  # noqa: E501
            f"{CrateCommand.ANON_DEMO_CONFIG}=crate_anon.anonymise.demo_config:main",  # noqa: E501
            f"{CrateCommand.ANON_DRAFT_DD}=crate_anon.anonymise.draft_dd:main",
            f"{CrateCommand.ANON_SHOW_COUNTS}=crate_anon.anonymise.show_counts:main",  # noqa: E501
            f"{CrateCommand.ANON_SUMMARIZE_DD}=crate_anon.anonymise.summarize_dd:main",  # noqa: E501
            f"{CrateCommand.ANONYMISE}=crate_anon.anonymise.anonymise_cli:main",  # noqa: E501
            f"{CrateCommand.ANONYMISE_MULTIPROCESS}=crate_anon.anonymise.launch_multiprocess_anonymiser:main",  # noqa: E501
            f"{CrateCommand.MAKE_DEMO_DATABASE}=crate_anon.anonymise.make_demo_database:main",  # noqa: E501
            f"{CrateCommand.RESEARCHER_REPORT}=crate_anon.anonymise.researcher_report:main",  # noqa: E501
            f"{CrateCommand.SUBSET_DB}=crate_anon.anonymise.subset_db:main",
            f"{CrateCommand.TEST_ANONYMISATION}=crate_anon.anonymise.test_anonymisation:main",  # noqa: E501
            f"{CrateCommand.TEST_EXTRACT_TEXT}=crate_anon.anonymise.test_extract_text:main",  # noqa: E501
            # NLP
            f"{CrateCommand.NLP}=crate_anon.nlp_manager.nlp_manager:main",
            f"{CrateCommand.NLP_BUILD_GATE_JAVA_INTERFACE}=crate_anon.nlp_manager.build_gate_java_interface:main",  # noqa: E501
            f"{CrateCommand.NLP_BUILD_MEDEX_ITSELF}=crate_anon.nlp_manager.build_medex_itself:main",  # noqa: E501
            f"{CrateCommand.NLP_BUILD_MEDEX_JAVA_INTERFACE}=crate_anon.nlp_manager.build_medex_java_interface:main",  # noqa: E501
            f"{CrateCommand.NLP_MULTIPROCESS}=crate_anon.nlp_manager.launch_multiprocess_nlp:main",  # noqa: E501
            f"{CrateCommand.NLP_PREPARE_YMLS_FOR_BIOYODIE}=crate_anon.nlp_manager.prepare_umls_for_bioyodie:main",  # noqa: E501
            f"{CrateCommand.NLP_WRITE_GATE_AUTO_INSTALL_XML}=crate_anon.nlp_manager.write_gate_auto_install_xml:main",  # noqa: E501
            f"{CrateCommand.RUN_CRATE_NLP_DEMO}=crate_anon.nlp_manager.run_crate_nlp_demo:main",  # noqa: E501
            f"{CrateCommand.RUN_GATE_ANNIE_DEMO}=crate_anon.nlp_manager.run_gate_annie_demo:main",  # noqa: E501
            f"{CrateCommand.RUN_GATE_KCL_KCONNECT_DEMO}=crate_anon.nlp_manager.run_gate_kcl_kconnect_demo:main",  # noqa: E501
            f"{CrateCommand.RUN_GATE_KCL_LEWY_DEMO}=crate_anon.nlp_manager.run_gate_kcl_lewy_demo:main",  # noqa: E501
            f"{CrateCommand.RUN_GATE_KCL_PHARMACOTHERAPY_DEMO}=crate_anon.nlp_manager.run_gate_kcl_pharmacotherapy_demo:main",  # noqa: E501
            f"{CrateCommand.SHOW_CRATE_GATE_PIPELINE_OPTIONS}=crate_anon.nlp_manager.show_crate_gate_pipeline_options:main",  # noqa: E501
            f"{CrateCommand.SHOW_CRATE_MEDEX_PIPELINE_OPTIONS}=crate_anon.nlp_manager.show_crate_medex_pipeline_options:main",  # noqa: E501
            # Web site
            f"{CrateCommand.CELERY_STATUS}=crate_anon.tools.celery_status:main",  # noqa: E501
            f"{CrateCommand.DJANGO_MANAGE}=crate_anon.crateweb.manage:main",  # will cope with argv  # noqa: E501
            f"{CrateCommand.EMAIL_RDBM}=crate_anon.tools.email_rdbm:main",
            f"{CrateCommand.GENERATE_NEW_DJANGO_SECRET_KEY}=cardinal_pythonlib.django.tools.generate_new_django_secret_key:main",  # noqa: E501
            f"{CrateCommand.LAUNCH_CELERY}=crate_anon.tools.launch_celery:main",  # noqa: E501
            f"{CrateCommand.LAUNCH_FLOWER}=crate_anon.tools.launch_flower:main",  # noqa: E501
            f"{CrateCommand.PRINT_DEMO_CRATEWEB_CONFIG}=crate_anon.tools.print_crateweb_demo_config:main",  # noqa: E501
            f"{CrateCommand.TEST_DATABASE_CONNECTION}=crate_anon.tools.test_database_connection:main",  # noqa: E501
            f"{CrateCommand.WINDOWS_SERVICE}=crate_anon.tools.winservice:main",
            # Indirect shortcuts to "crate_django_manage" commands:
            f"{CrateCommand.LAUNCH_CHERRYPY_SERVER}=crate_anon.tools.launch_cherrypy_server:main",  # noqa: E501
            # ... a separate script with ":main" rather than
            # "crate_anon.crateweb.manage:runcpserver" so that we can launch
            # the "runcpserver" function from our Windows service, and have it
            # deal with the CherryPy special environment variable
            f"{CrateCommand.LAUNCH_DJANGO_SERVER}=crate_anon.crateweb.manage:runserver",  # noqa: E501
            # NLP web server
            f"{CrateCommand.NLP_WEBSERVER_GENERATE_ENCRYPTION_KEY}=crate_anon.nlp_webserver.security:generate_encryption_key",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_INITIALIZE_DB}=crate_anon.nlp_webserver.initialize_db:main",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_LAUNCH_CELERY}=crate_anon.tools.launch_nlp_webserver_celery:main",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_LAUNCH_FLOWER}=crate_anon.tools.launch_nlp_webserver_flower:main",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_LAUNCH_GUNICORN}=crate_anon.tools.launch_nlp_webserver_gunicorn:main",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_MANAGE_USERS}=crate_anon.nlp_webserver.manage_users:main",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_PRINT_DEMO}=crate_anon.nlp_webserver.print_demos:main",  # noqa: E501
            f"{CrateCommand.NLP_WEBSERVER_PSERVE}=pyramid.scripts.pserve:main",  # noqa: E501
        ],
        # Entry point for nlp webserver
        "paste.app_factory": [
            "main = crate_anon.nlp_webserver.wsgi_app:make_wsgi_app",
            # ... means we can launch with "pserve <config_file>"; see
            # https://docs.pylonsproject.org/projects/pyramid-cookbook/en/latest/pylons/launch.html  # noqa: E501
        ],
        "paste.server_runner": [
            "cherrypy = crate_anon.nlp_webserver.wsgi_launchers:cherrypy",
            "waitress = crate_anon.nlp_webserver.wsgi_launchers:waitress",
        ],
    },
)
