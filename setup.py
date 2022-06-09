#!/usr/bin/env python

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
    "amqp==5.0.9",  # amqp is used by Celery
    "appdirs==1.4.4",  # where to store some temporary data
    "arrow==0.15.7",  # [pin exact version from cardinal_pythonlib]
    "beautifulsoup4==4.9.1",  # [pin exact version from cardinal_pythonlib]
    "cardinal_pythonlib==1.1.21",  # RNC libraries
    "cairosvg==2.5.1",  # work with SVG files
    "celery==5.2.3",  # back-end scheduling
    "chardet==3.0.4",  # character encoding detection for cardinal_pythonlib
    "cherrypy==18.6.0",  # Cross-platform web server
    "colorlog==4.1.0",  # colour in logs
    "distro==1.5.0",  # replaces platform.linux_distribution
    "django==3.2.13",  # for main CRATE research database web server
    "django-debug-toolbar==3.0a2",  # Django debug toolbar
    # "django-debug-toolbar-template-profiler==2.0.1",  # v1.0.1 removed 2017-01-30: division by zero when rendering time is zero  # noqa: E501
    "django-extensions==3.1.1",  # for graph_models, show_urls etc.
    "django-picklefield==3.0.1",  # NO LONGER USED - dangerous to use pickle - but kept for migrations  # noqa: E501
    # "django-silk==4.0.1",  # Django profiler
    "djangorestframework==3.13.1",  # Anonymisation API support
    "django-sslserver==0.22",  # SSL development server for Django
    "drf-spectacular==0.22.0",  # Open API Schema and documentation
    "drf-spectacular-sidecar==2022.3.21",  # Static files for drf-spectacular
    "flashtext==2.7",  # fast word replacement with the FlashText algorithm
    "flower==1.0.0",  # debug Celery; web server; only runs explicitly
    "fuzzy==1.2.2",  # phonetic matching
    "gunicorn==20.0.4",  # UNIX only, though will install under Windows
    "jsonlines==3.0.0",  # JSON Lines format
    "kombu==5.2.3",  # AMQP library for Celery; requires VC++ under Windows
    "mako==1.1.3",  # templates with Python in
    "MarkupSafe==2.0.1",  # for HTML escaping
    # mmh3 requires VC++
    "mmh3==2.5.1",  # MurmurHash, for fast non-cryptographic hashing; optionally used by cardinal_pythonlib; requires VC++ under Windows?  # noqa: E501
    "numba==0.55.2",  # just-in-time compilation of functions
    "openpyxl==3.0.7",  # read Excel
    "pendulum==2.1.2",  # dates/times
    "Pillow==9.0.1",  # image processing; import as PIL (Python Imaging Library)  # noqa: E501
    "pdfkit==0.6.1",  # interface to wkhtmltopdf
    "prettytable==3.2.0",  # pretty formating of text-based tables
    "psutil==5.7.2",  # process management
    "pyexcel-ods==0.6.0",  # for reading/writing ODS files
    "pyexcel-xlsx==0.6.0",  # for writing XLSX files (using openpyxl)
    "pygments==2.8.1",  # syntax highlighting
    "pyparsing==2.4.7",  # generic grammar parser
    "PyPDF2==1.27.5",  # [pin exact version from cardinal_pythonlib]
    "pytz==2021.3",  # timezones
    "python-dateutil==2.8.1",  # [pin exact version from cardinal_pythonlib]
    # "python-docx==0.8.10",  # needs lxml, which has Visual C++ dependencies under Windows  # noqa: E501
    # ... https://python-docx.readthedocs.org/en/latest/user/install.html
    "regex==2020.11.13",  # better regexes (cf. re)
    "semantic_version==2.8.5",  # semantic versioning; better than semver
    "sortedcontainers==2.2.2",  # for SortedSet
    "SQLAlchemy==1.3.18",  # database access
    "sqlparse==0.4.2",  # [pin exact version from cardinal_pythonlib]
    "unidecode==1.1.1",  # for removing accents
    # Packages for cloud NLP:
    "bcrypt==3.1.7",  # bcrypt encryption
    "cryptography==3.3.2",  # cryptography library
    # "mysqlclient",  # database access
    "paste==3.4.2",  # middleware; https://github.com/cdent/paste/
    "pyramid==1.10.4",  # Pyramid web framework
    "pyramid_tm==2.4",  # Pyramid transaction management
    "redis==3.5.3",  # interface to Redis in-memory key-value database
    "requests==2.25.1",  # HTTP requests
    "tornado==6.1",  # web framework
    "transaction==3.0.0",  # generic transaction management
    "urllib3==1.26.5",  # used by requests
    "waitress==2.1.1",  # pure-Python WSGI server
    "zope.sqlalchemy==1.3",  # Zope/SQLAlchemy transaction integration
    # For development only:
    "black==22.3.0",  # auto code formatter
    "faker==13.3.1",  # test data creation
    "flake8==3.8.4",  # code checks
    "docutils==0.17",  # documentation, 0.18 not compatible with Sphinx
    "mistune<2.0.0",  # API documentation, 2.0.0 not compatible
    "pytest==7.1.1",  # automatic testing
    "pytest-django==4.5.2",  # automatic testing
    # Sphinx 4.4.0 gives "more than one target for cross-reference" warning
    # when resolving crate_anon.anonymise.patient.Patient in
    # crate_anon.anonymise.altermethod.py
    "sphinx==4.2.0",  # documentation
    "sphinx_rtd_theme==1.0.0",  # documentation
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
        "Development Status :: 4 - Beta",
        # Indicate who your project is intended for
        "Intended Audience :: Science/Research",
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",  # noqa: E501
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
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
            "crate_fetch_wordlists=crate_anon.anonymise.fetch_wordlists:main",
            "crate_postcodes=crate_anon.preprocess.postcodes:main",
            "crate_preprocess_pcmis=crate_anon.preprocess.preprocess_pcmis:main",  # noqa: E501
            "crate_preprocess_rio=crate_anon.preprocess.preprocess_rio:main",
            "crate_preprocess_systmone=crate_anon.preprocess.preprocess_systmone:main",  # noqa: E501
            # Linkage
            "crate_bulk_hash=crate_anon.linkage.bulk_hash:main",
            "crate_fuzzy_id_match=crate_anon.linkage.fuzzy_id_match:main",
            # Anonymisation
            "crate_anon_check_text_extractor=crate_anon.anonymise.check_text_extractor:main",  # noqa: E501
            "crate_anon_demo_config=crate_anon.anonymise.demo_config:main",
            "crate_anon_draft_dd=crate_anon.anonymise.draft_dd:main",
            "crate_anon_show_counts=crate_anon.anonymise.show_counts:main",
            "crate_anon_summarize_dd=crate_anon.anonymise.summarize_dd:main",
            "crate_anonymise=crate_anon.anonymise.anonymise_cli:main",
            "crate_anonymise_multiprocess=crate_anon.anonymise.launch_multiprocess_anonymiser:main",  # noqa: E501
            "crate_make_demo_database=crate_anon.anonymise.make_demo_database:main",  # noqa: E501
            "crate_test_anonymisation=crate_anon.anonymise.test_anonymisation:main",  # noqa: E501
            "crate_test_extract_text=crate_anon.anonymise.test_extract_text:main",  # noqa: E501
            # NLP
            "crate_nlp=crate_anon.nlp_manager.nlp_manager:main",
            "crate_nlp_build_gate_java_interface=crate_anon.nlp_manager.build_gate_java_interface:main",  # noqa: E501
            "crate_nlp_build_medex_itself=crate_anon.nlp_manager.build_medex_itself:main",  # noqa: E501
            "crate_nlp_build_medex_java_interface=crate_anon.nlp_manager.build_medex_java_interface:main",  # noqa: E501
            "crate_nlp_multiprocess=crate_anon.nlp_manager.launch_multiprocess_nlp:main",  # noqa: E501
            "crate_nlp_prepare_ymls_for_bioyodie=crate_anon.nlp_manager.prepare_umls_for_bioyodie:main",  # noqa: E501
            "crate_run_crate_nlp_demo=crate_anon.nlp_manager.run_crate_nlp_demo:main",  # noqa: E501
            "crate_run_gate_annie_demo=crate_anon.nlp_manager.run_gate_annie_demo:main",  # noqa: E501
            "crate_run_gate_kcl_kconnect_demo=crate_anon.nlp_manager.run_gate_kcl_kconnect_demo:main",  # noqa: E501
            "crate_run_gate_kcl_lewy_demo=crate_anon.nlp_manager.run_gate_kcl_lewy_demo:main",  # noqa: E501
            "crate_run_gate_kcl_pharmacotherapy_demo=crate_anon.nlp_manager.run_gate_kcl_pharmacotherapy_demo:main",  # noqa: E501
            "crate_show_crate_gate_pipeline_options=crate_anon.nlp_manager.show_crate_gate_pipeline_options:main",  # noqa: E501
            "crate_show_crate_medex_pipeline_options=crate_anon.nlp_manager.show_crate_medex_pipeline_options:main",  # noqa: E501
            # Web site
            "crate_celery_status=crate_anon.tools.celery_status:main",
            "crate_django_manage=crate_anon.crateweb.manage:main",  # will cope with argv  # noqa: E501
            "crate_email_rdbm=crate_anon.tools.email_rdbm:main",
            "crate_generate_new_django_secret_key=cardinal_pythonlib.django.tools.generate_new_django_secret_key:main",  # noqa: E501
            "crate_launch_celery=crate_anon.tools.launch_celery:main",
            "crate_launch_flower=crate_anon.tools.launch_flower:main",
            "crate_print_demo_crateweb_config=crate_anon.tools.print_crateweb_demo_config:main",  # noqa: E501
            "crate_windows_service=crate_anon.tools.winservice:main",
            # Indirect shortcuts to "crate_django_manage" commands:
            "crate_launch_cherrypy_server=crate_anon.tools.launch_cherrypy_server:main",  # noqa: E501
            # ... a separate script with ":main" rather than
            # "crate_anon.crateweb.manage:runcpserver" so that we can launch
            # the "runcpserver" function from our Windows service, and have it
            # deal with the CherryPy special environment variable
            "crate_launch_django_server=crate_anon.crateweb.manage:runserver",
            # NLP web server
            "crate_nlp_webserver_generate_encryption_key=crate_anon.nlp_webserver.security:generate_encryption_key",  # noqa: E501
            "crate_nlp_webserver_initialize_db=crate_anon.nlp_webserver.initialize_db:main",  # noqa: E501
            "crate_nlp_webserver_launch_celery=crate_anon.tools.launch_nlp_webserver_celery:main",  # noqa: E501
            "crate_nlp_webserver_launch_flower=crate_anon.tools.launch_nlp_webserver_flower:main",  # noqa: E501
            "crate_nlp_webserver_launch_gunicorn=crate_anon.tools.launch_nlp_webserver_gunicorn:main",  # noqa: E501
            "crate_nlp_webserver_manage_users=crate_anon.nlp_webserver.manage_users:main",  # noqa: E501
            "crate_nlp_webserver_print_demo=crate_anon.nlp_webserver.print_demos:main",  # noqa: E501
            "crate_nlp_webserver_pserve=pyramid.scripts.pserve:main",  # noqa: E501
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
