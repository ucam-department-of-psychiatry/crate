#!/usr/bin/env python
# setup.py

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

CRATE setup file

To use:

    python setup.py sdist

    twine upload dist/*

To install in development mode:

    pip install -e .

"""
# https://packaging.python.org/en/latest/distributing/#working-in-development-mode  # noqa
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/
# http://jtushman.github.io/blog/2013/06/17/sharing-code-across-applications-with-python/  # noqa

from setuptools import setup, find_packages
from codecs import open
# import fnmatch
import os
import platform

from crate_anon.version import VERSION

here = os.path.abspath(os.path.dirname(__file__))

# setup.py is executed on the destination system at install time, so:
windows = platform.system() == 'Windows'

# -----------------------------------------------------------------------------
# Get the long description from the README file
# -----------------------------------------------------------------------------
with open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

# -----------------------------------------------------------------------------
# Get all filenames
# -----------------------------------------------------------------------------
# rootdir = os.path.join(here, 'crate')
# data_files = []
# for dir_, subdirs, filenames in os.walk(rootdir):
#     files = []
#     reldir = os.path.relpath(dir_, rootdir)
#     for pattern in ['*.py', '*.html']:
#         for filename in fnmatch.filter(filenames, pattern):
#             files.append(filename)
#     if files:
#         data_files.append((reldir, files))
# print(data_files)
# http://stackoverflow.com/questions/2186525/use-a-glob-to-find-files-recursively-in-python  # noqa
# http://stackoverflow.com/questions/27664504/how-to-add-package-data-recursively-in-python-setup-py  # noqa

# rootdir = os.path.join(here, 'crate', 'crateweb', 'static_collected')
# static_collected = []
# for dir_, subdirs, filenames in os.walk(rootdir):
#     reldir = os.path.normpath(os.path.join(
#         'static_collected', os.path.relpath(dir_, rootdir)))
#     for filename in filenames:
#         if filename in ['.gitignore']:
#             continue
#         static_collected.append(os.path.join(reldir, filename))

# -----------------------------------------------------------------------------
# setup args
# -----------------------------------------------------------------------------
setup(
    name='crate-anon',  # 'crate' is taken

    version=VERSION,

    description='CRATE: clinical records anonymisation and text extraction',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/RudolfCardinal/crate',

    # Author details
    author='Rudolf Cardinal',
    author_email='rudolf@pobox.com',

    # Choose your license
    license='GNU General Public License v3 or later (GPLv3+)',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',  # noqa

        'Natural Language :: English',

        'Operating System :: OS Independent',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: System :: Hardware',
        'Topic :: System :: Networking',
    ],

    keywords='anonymisation',

    packages=find_packages(),  # finds all the .py files in subdirectories
    package_data={
        '': [
            'README.md'
        ],
        'crate_anon.crateweb': [
            # Don't use 'static/*', or at the point of installation it gets
            # upset about "demo_logo" ("can't copy... doesn't exist or not
            # a regular file). Keep running "python setup.py sdist >/dev/null"
            # until stderr comes up clean.
            'consent/templates/*.html',
            'consent/templates/*.js',
            'research/templates/*.html',
            'static/demo_logo/*',
            'static/jquery-ui-1.12.1/external/*',
            'static/jquery-ui-1.12.1/external/jquery/*',
            'static/jquery-ui-1.12.1/images/*',
            'static/jquery-ui-1.12.1/*',
            'static/*.css',
            'static/*.gif',
            'static/*.ico',
            'static/*.js',
            'static/*.png',
            'templates/admin/*.html',
            'templates/*.css',
            'templates/*.html',
            'templates/*.js',
            'userprofile/templates/*.html',
        ],
        'crate_anon.docs': [
            'Cardinal_2017_Clinical_records_anon.pdf',
            'CRATE_MANUAL.odt',
        ],
        'crate_anon.nlp_manager': [
            '*.java',
            '*.sh',
        ],
        'crate_anon.mysql_auditor': [
            '*.conf',
            '*.lua',
            '*.sh',
        ],
        'crate_anon.testdocs_for_text_extraction': [
            'doctest.*',
            'nonascii.odt',
        ],
    },

    install_requires=[

        # ---------------------------------------------------------------------
        # For the web front end:
        # ---------------------------------------------------------------------
        # Core tools with accessories:
        'arrow==0.10.0',  # better datetime
        'chardet==3.0.2',  # character encoding detection for cardinal_pythonlib  # noqa
        'colorlog==2.10.0',  # colour in logs
        # 'configobj==5.0.6',  # better config files
        'distro==1.0.2',  # replaces platform.linux_distribution
        # requires VC++ under Windows # 'mmh3==2.2',  # MurmurHash, for fast non-cryptographic hashing  # noqa
        'psutil==5.0.1',  # process management
        # REMOVED in version 0.18.42; needs Visual C++ under Windows  # 'pyhashxx==0.1.3',  # fast non-cryptographic hashing  # noqa
        'semver==2.7.5',  # comparing semantic versions
        'SQLAlchemy==1.1.5',  # database access
        'typing==3.5.3.0',  # part of stdlib in Python 3.5, but not 3.4

        # Web app:
        'amqp==2.1.3',  # because 2.1.4 has a bug; see CRATE manual; amqp is used by Celery  # noqa
        'celery==4.0.1',  # 4.0.1 is the highest that'll accept kombu 4.0.1 and thus amqp 2.1.3  # noqa
        'Django==1.10.5',  # "django" versus "Django": neither helps pycharm checking  # noqa
        'django-debug-toolbar==1.6',
        # 'django-debug-toolbar-template-profiler==1.0.1',  # removed 2017-01-30: division by zero when rendering time is zero  # noqa
        'django-extensions==1.7.6',
        'django-picklefield==0.3.2',  # NO LONGER USED - dangerous to use pickle - but kept for migrations  # noqa
        # 'django-silk==0.5.7',
        'django-sslserver==0.19',
        'flower==0.9.1',  # debug Celery; web server; only runs explicitly
        'kombu==4.0.1',  # see above re amqp/celery
        'pdfkit==0.6.1',
        'pygments==2.2.0',  # syntax highlighting
        # 'pygraphviz==1.3.1',  # not used
        'pyparsing==2.1.10',  # generic grammar parser
        'PyPDF2==1.26.0',
        'pytz==2016.10',
        'python-dateutil==2.6.0',
        'sqlparse==0.2.2',
        'Werkzeug==0.11.15',

        # ONSPD:
        'openpyxl==2.4.2',
        'xlrd==1.0.0',

        # Serving:
        'gunicorn==19.6.0',  # UNIX only, though will install under Windows
        'cherrypy==10.0.0',  # Cross-platform

        # ---------------------------------------------------------------------
        # For the anonymiser/pythonlib:
        # ---------------------------------------------------------------------

        'cardinal_pythonlib==1.0.2',

        'beautifulsoup4==4.5.3',
        'prettytable==0.7.2',
        # 'python-docx==0.8.5',  # needs lxml, which has Visual C++ dependencies under Windows  # noqa
        # ... https://python-docx.readthedocs.org/en/latest/user/install.html
        'regex==2017.1.17',
        'sortedcontainers==1.5.7',

        # ---------------------------------------------------------------------
        # For database connections (see manual): install manually
        # ---------------------------------------------------------------------
        # MySQL: one of:
        #   'PyMySQL',
        #   'mysqlclient',
        # SQL Server / ODBC route:
        #   'django-pyodbc-azure',
        #   'pyodbc',  # has C prerequisites
        #   'pypyodbc==1.3.3',
        # SQL Server / Embedded FreeTDS route:
        #   'django-pymssql',
        #   'django-mssql',
        #   'pymssql',
        # PostgreSQL:
        #   'psycopg2',  # has prerequisites (e.g. pg_config executable)
    ] + ([
        'pypiwin32==219'
    ] if windows else []),

    entry_points={
        'console_scripts': [
            # Format is 'script=module:function".

            'crate_postcodes=crate_anon.preprocess.postcodes:main',
            'crate_preprocess_rio=crate_anon.preprocess.preprocess_rio:main',
            'crate_preprocess_pcmis=crate_anon.preprocess.preprocess_pcmis:main',  # noqa

            'crate_anonymise=crate_anon.anonymise.anonymise_cli:main',
            'crate_anonymise_multiprocess=crate_anon.anonymise.launch_multiprocess_anonymiser:main',  # noqa
            'crate_make_demo_database=crate_anon.anonymise.make_demo_database:main',  # noqa
            'crate_test_anonymisation=crate_anon.anonymise.test_anonymisation:main',  # noqa
            'crate_test_extract_text=crate_anon.anonymise.test_extract_text:main',  # noqa

            'crate_nlp=crate_anon.nlp_manager.nlp_manager:main',
            'crate_nlp_multiprocess=crate_anon.nlp_manager.launch_multiprocess_nlp:main',  # noqa
            'crate_nlp_build_gate_java_interface=crate_anon.nlp_manager.build_gate_java_interface:main',  # noqa
            'crate_nlp_build_medex_java_interface=crate_anon.nlp_manager.build_medex_java_interface:main',  # noqa
            'crate_nlp_build_medex_itself=crate_anon.nlp_manager.build_medex_itself:main',  # noqa

            'crate_django_manage=crate_anon.crateweb.manage:main',  # will cope with argv  # noqa
            'crate_launch_django_server=crate_anon.crateweb.manage:runserver',

            'crate_launch_cherrypy_server=crate_anon.tools.launch_cherrypy_server:main',  # noqa
            # ... a separate script with ":main" rather than
            # "crate_anon.crateweb.manage:runcpserver" so that we can launch
            # the "runcpserver" function from our Windows service, and have it
            # deal with the CherryPy special environment variable
            'crate_launch_celery=crate_anon.tools.launch_celery:main',
            'crate_launch_flower=crate_anon.tools.launch_flower:main',
            'crate_print_demo_crateweb_config=crate_anon.tools.print_crateweb_demo_config:main',  # noqa

            'crate_windows_service=crate_anon.tools.winservice:main',

            'crate_estimate_mysql_memory_usage=cardinal_pythonlib.tools.estimate_mysql_memory_usage:main',  # noqa
            'crate_generate_new_django_secret_key=cardinal_pythonlib.django.tools.generate_new_django_secret_key:main',  # noqa
            'crate_list_all_extensions=cardinal_pythonlib.tools.list_all_extensions:main',  # noqa
            'crate_merge_csv=cardinal_pythonlib.tools.merge_csv:main',

        ],
    },
)
