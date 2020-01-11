.. crate_anon/docs/source/anonymisation/overview.rst

..  Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).
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

.. _anonymisation:

Overview of anonymisation
-------------------------

You set things up as follows.

- You start with one or more **source database(s)** and blank **destination
  database(s)**, plus blank **secret database(s)** that CRATE uses for
  temporary storage and storing PID-to-RID lookup information.

  - You may need to **preprocess** your source database a little, if it has
    an odd or inconvenient format.

- You create an **anonymiser config file** that points to your databases and
  governs high-level parameters relating to the anonymisation process.

- You create a **data dictionary** that describes what to do with each column
  of the source database(s). For example, some columns may be allowed through
  unchanged; some may be skipped; some may contain patient identifiers; some
  may contain free text that needs to have identifiers "scrubbed" out. You
  tell your config file about your data dictionary.

  - CRATE can draft one for you, but you will need to check it manually.

- You run the **anonymiser**, pointing it at your config file.

  - There are some additional options here (for example, to restrict to
    specific patients or eliminate all free text fields), which allow you to
    use a standard config file and data dictionary but produce variant versions
    of your database without too much effort.
