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

Background
~~~~~~~~~~

This view provides an "archive" (read-only) view of an electronic health record
(EHR). It has two potential purposes:

- to provide a useful, configurable way in which researchers can explore the
  anonymised EHR of a single patient;

- potentially, to act as an archive view onto an identifiable EHR.

It is *entirely* configurable by the local system, though CRATE comes with
some specimens.


How to customize the archive view
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Write your archive
##################

Within a directory tree of your choice, write Mako_ templates. Some specimen
miniature web sites are provided to show you how, in:

.. code-block:: none

    crate_anon/crateweb/specimen_archives/basic/
    crate_anon/crateweb/specimen_archives/tree/

The "basic" one demonstrates basic layout, SQL queries, and downloading of
binary attachments. The "tree" one uses a collapsible tree-style menu on the
left and a range of specimen views onto the EHR on the right.

This system gives you full use of HTML/Javascript and Python simultaneously.
(Python code will run within the same interpreter and virtual environment used
by CRATE.)


.. _archive_mako_context:

The Python context
##################

These Python objects are visible to the Mako templates:

- ``archive_url``:

  Function to generate a URL to a template in another part of the archive, for
  the same patient. Call it as

  .. code-block:: python

    archive_url(template_name, **kwargs)

  You can pass any keyword parameters except the built-in keywords (see
  :class:`crate_anon.crateweb.research.views.ArchiveContextKeys`).

- ``attachment_url``:

  Function to generate a URL to a binary attachment, which is
  :func:`crate_anon.crateweb.research.views.archive_attachment_url` (see that
  for details). Call it like this:

  .. code-block:: python

    attachment_url(filename, ...)

- ``CRATE_HOME_URL``:

  URL to the CRATE home page.

- ``patient_id``:

  The ID of this patient. (A string, but that will still work an an SQL
  parameter for integer fields. You can of course process it further if you
  wish.)

- ``execute``:

  Function to run an SQL query (via the research database connection), or just
  execute raw SQL, and return a database cursor. Call it as

  .. code-block:: python

    cursor = execute(sql)
    cursor = execute(sql, args)

  Use question marks (``?``) in the SQL as argument placeholders.

- ``request``:

  The Django request.

- ``static_url``:

  Function to generate a URL to a binary attachment, which is
  :func:`crate_anon.crateweb.research.views.archive_static_url` (see that
  for details). Call it like this:

  .. code-block:: python

    static_url(filename, ...)

- ``template``:

  The  name of the template (introspection!). Also used as a URL parameter
  key.


Point CRATE at your archive
###########################

See the relevant section of the :ref:`web config file <webconfig_archive>`.


Design notes
~~~~~~~~~~~~

- HTML templates, written locally, stored on disk in a user-defined directory.

  - Any template engine would be reasonable, but the two obvious candidates are

    - Django_, because we use that for the CRATE web front end (but the
      template language is somewhat restricted);
    - Mako_, because the templates can include arbitrary Python, and because
      Django/Mako interoperability is possible (including via
      Django-Mako-Plus_ but also directly).
    - `Other template engines`_, but nothing is particularly compelling over
      those two.

    Let's use Mako.

- A structure that is configurable by the local administrator (stored in a
  config file, a database, or on disk), mapping the templates.

  The best is probably to specify a single template as the root template in
  the config file.

- A URL system to produce requests to other parts of the archive, with
  arbitrary parameters via HTTP GET URL parameters.

- Pre-population of the template dictionary with useful objects (but not those
  that take much time to create). See
  :func:`crate_anon.crateweb.research.views.archive_view`.

