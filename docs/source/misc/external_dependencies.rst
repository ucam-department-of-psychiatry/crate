..  crate_anon/docs/source/misc/ancillary_tools.rst

..  Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

External dependencies
=====================

CRATE uses:

Python packages
~~~~~~~~~~~~~~~

- ``amqp``: https://amqp.readthedocs.io/
- ``arrow``: https://arrow.readthedocs.io/
- ``beautifulsoup4``: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- ``cardinal_pythonlib``: https://cardinalpythonlib.readthedocs.io/
- ``celery``: http://www.celeryproject.org/
- ``chardet``: https://chardet.readthedocs.io/
- ``CherryPy``: https://cherrypy.org/
- ``colorlog``: https://pypi.org/project/colorlog/
- ``distro``: https://distro.readthedocs.io/
- ``Django``: https://www.djangoproject.com/
- ``django-debug-toolbar``: https://django-debug-toolbar.readthedocs.io/
- ``django-extensions``: https://django-extensions.readthedocs.io/
- ``django-picklefield``: https://pypi.org/project/django-picklefield/
- ``django-sslserver``: https://github.com/teddziuba/django-sslserver
- ``flashtext``: https://flashtext.readthedocs.io/
- ``flower``: https://flower.readthedocs.io/
- ``gunicorn``: https://gunicorn.org/
- ``kombu``: http://docs.celeryproject.org/projects/kombu/
- ``openpyxl``: https://openpyxl.readthedocs.io/
- ``pendulum``: https://pendulum.eustace.io/
- ``pdfkit``: https://pypi.org/project/pdfkit/
- ``prettytable``: https://pypi.org/project/PrettyTable/
- ``psutil``: https://psutil.readthedocs.io/
- ``Pygments``: http://pygments.org/
- ``pyparsing``: http://infohost.nmt.edu/tcc/help/pubs/pyparsing/web/index.html
- ``PyPDF2``: https://pythonhosted.org/PyPDF2/
- ``python-dateutil``: https://dateutil.readthedocs.io/en/stable/
- ``regex``: https://bitbucket.org/mrabarnett/mrab-regex
- ``semver``: https://pypi.org/project/semver/
- ``sortedcontainers``: http://www.grantjenks.com/docs/sortedcontainers/
- ``SQLAlchemy``: https://www.sqlalchemy.org/
- ``sqlparse``: https://sqlparse.readthedocs.io/
- ``typing``: https://pypi.org/project/typing/
- ``unidecode``: https://pypi.org/project/Unidecode/
- ``Werkzeug``: http://werkzeug.pocoo.org/
- ``xlrd``: https://xlrd.readthedocs.io/


Versions of software etc. used by CRATE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+----------------+---------+------------------------------------------------------------+
| Name           | Version | Supported until                                            |
+================+=========+============================================================+
| Debian         |      11 | 2026-08-31;                                                |
| (Docker image) |         | https://wiki.debian.org/LTS                                |
+----------------+---------+------------------------------------------------------------+
| Django         |   4.2.x | 2026-04-30 (LTS);                                          |
|                |         | https://www.djangoproject.com/download/#supported-versions |
+----------------+---------+------------------------------------------------------------+
| Python         |     3.8 | 2024-10-31                                                 |
+----------------+---------+------------------------------------------------------------+
|                |     3.9 | 2025-10-31                                                 |
+----------------+---------+------------------------------------------------------------+
|                |    3.10 | 2026-10-31;                                                |
|                |         | https://devguide.python.org/versions/                      |
+----------------+---------+------------------------------------------------------------+
| SQLAlchemy     |     1.4 | Still maintained but will reach EOL when 2.1 becomes the   |
|                |         | next major release. Upgrade to 2.0 is encouraged.          |
|                |         | https://www.sqlalchemy.org/download.html                   |
+----------------+---------+------------------------------------------------------------+
