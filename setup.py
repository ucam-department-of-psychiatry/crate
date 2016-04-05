#!/usr/bin/env python
# setup.py

"""
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

from setuptools import setup
from codecs import open
from os import path

from crate.version import VERSION

here = path.abspath(path.dirname(__file__))

# -----------------------------------------------------------------------------
# Get the long description from the README file
# -----------------------------------------------------------------------------
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# -----------------------------------------------------------------------------
# setup args
# -----------------------------------------------------------------------------
setup(
    name='crate',

    version=VERSION,

    description='CRATE: clinical records anonymisation and text extraction',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/RudolfCardinal/crate',

    # Author details
    author='Rudolf Cardinal',
    author_email='rudolf@pobox.com',

    # Choose your license
    license='Apache License 2.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: Apache Software License',

        'Natural Language :: English',

        'Operating System :: OS Independent',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: System :: Hardware',
        'Topic :: System :: Networking',
    ],

    keywords='anonymisation',

    packages=['crate'],

    install_requires=[

        # ---------------------------------------------------------------------
        # For the web front end:
        # ---------------------------------------------------------------------

        'celery==3.1.19',
        'Django==1.9.3',
        'django-extensions==1.5.9',
        'django-picklefield==0.3.2',
        'django-pyodbc-azure==1.9.3.0',
        'django-sslserver==0.15',
        'django-debug-toolbar==1.4',
        'gunicorn==19.3.0',
        'mysqlclient==1.3.6',
        'pdfkit==0.5.0',
        'pygraphviz==1.3.1',
        'PyPDF2==1.25.1',
        'pytz==2015.6',
        'python-dateutil==2.4.2',
        'Werkzeug==0.10.4',

        # ---------------------------------------------------------------------
        # For the anonymiser/pythonlib:
        # ---------------------------------------------------------------------

        'cardinal_pythonlib',

        'beautifulsoup4==4.4.1',
        'prettytable==0.7.2',
        'python-docx==0.8.5',
        'regex==2015.11.14',
        'sortedcontainers==1.4.2',
    ],

    entry_points={
        'console_scripts': [
            # Format is 'script=module:function".
            'crate_anonymise=crate.anonymise.anonymise:main',
            'crate_make_demo_database=crate.anonymise.make_demo_database:main',
            'crate_test_anonymisation=crate.anonymise.test_anonymisation:main',
            'crate_launch_django=crate.crateweb.manage:runserver',
        ],
    },
)
