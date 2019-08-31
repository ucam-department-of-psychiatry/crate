.. crate_anon/docs/source/website_using/archive.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.


.. _CamCOPS: https://camcops.readthedocs.io/
.. _Django: https://docs.djangoproject.com/
.. _Django-Mako-Plus: http://doconix.github.io/django-mako-plus/index.html;
.. _Mako: https://www.makotemplates.org/
.. _Other template engines: https://wiki.python.org/moin/Templating#Templating_Engines


.. _archive:

Archive view
------------

.. warning:: Development thoughts only.


Background
~~~~~~~~~~

This view provides an "archive" (read-only) view of an electronic health record
(EHR). It has two potential purposes:

- to provide a useful, configurable way in which researchers can explore the
  anonymised EHR of a single patient;

- potentially, to act as an archive view onto an identifiable EHR.

It is *entirely* configurable by the local system.


Design notes
~~~~~~~~~~~~

- Config, via Django ``settings``:

  - ``ARCHIVE_TEMPLATE_DIRS``
  - ``ARCHIVE_ROOT_TEMPLATE``, e.g. ``root.mako``

- HTML templates, written locally, stored on disk in one of
  ``ARCHIVE_TEMPLATE_DIRS``.

  - Any template engine would be reasonable, but the two obvious candidates are

    - Django_, because we use that for the CRATE web front end (but the
      template language is somewhat restricted);
    - Mako_, because the templates can include arbitrary Python, and because
      Django/Mako interoperability is possible via
      Django-Mako-Plus_.
    - `Other template engines`_, but nothing is particularly compelling over
      those two.

    Let's use Mako.

- A structure that is configurable by the local administrator (stored in a
  config file or conceivably a database, but probably a config file),
  including:

  - A catalogue of templates:

    .. code-block:: none

        template_name   template_filename
        =============== =======================================================
        core2           assessments/core2/core2_root.mako
        ...             ...

  - One template is referred to by ``ARCHIVE_ROOT_TEMPLATE` and should  need
    any additional arguments

- A URL system to produce requests. For example,

  ``https://site/crate/archive/<patient_id>/<template_name>?<args>``

  The URL parameters (the parts after the "?") become the ``request.GET``
  dictionary in Django.

- Pre-population of the template dictionary with useful objects (but not those
  that take much time to create). See
  :func:`crate_anon.crateweb.research.views.archive_view`.


How to customize the archive view
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. todo:: write how-to for archive view ***


These Python objects are visible to the templates:

- ``archive_url``:

  Function to generate a URL to another part of the archive, for the
  same patient. Call it as

  .. code-block:: python

    archive_url(template_name, **kwargs)

- ``attachment_url``:

  Function to generate a URL to a binary attachment. Call it as:

  .. code-block:: python

    attachment_url(filename, content_type)
    attachment_url(filename, content_type, offered_filename)

- ``CRATE_HOME_URL``:

  URL to the CRATE home page.

- ``patient_id``:

  The ID of this patient. (A string, but that will still work with
  integer fields.)

- ``query``:

  Function to run an SQL query (on the research database) and return
  a database cursor. Call it as

  .. code-block:: python

    cursor = query(sql)
    cursor = query(sql, args)

  Use question marks (``?``) in the SQL as argument placeholders.

- ``request``:

  The Django request.

- ``template``:

  The  name of the template (introspection!). Also used as a URL parameter
  key.

- ``URL_FAVICON``:

  URL to the default favicon on this site (the scrubber picture).
