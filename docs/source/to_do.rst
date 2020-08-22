..  crate_anon/docs/source/misc/to_do.rst

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

Things to do
============

.. todolist::

- fix bug (reported by JL 6/11/2018) where the RiO preprocessor tries to put
  the same column into the same index more than once (see RNC email 6/11/2018)

- BENCHMARK name denial (with forenames + surnames – English words –
  eponyms): speed, precision, recall. Share results with MB.

- Personal configurable highlight colours (with default set if none
  configured)? Or just more colours? Look at a standard highlighter pack --
  e.g.

  - https://www.jetpens.com/Stabilo-Boss-Original-Highlighter-9-Color-Bundle/pd/21976.
  - https://www.rapidtables.com/web/css/css-color.html

  - Yellow, https://hexcolor.co/hex/ffff00
  - Blue, maybe cornflowerblue, https://hexcolor.co/hex/6495ed
  - Green, maybe https://hexcolor.co/hex/72ff66 ("Stabilo Boss 1")
  - Lavender, e.g. https://hexcolor.co/hex/967bb6
  - Lilac pink, maybe magenta-ish, e.g. https://hexcolor.co/hex/ff66e5
    ("Stabilo Boss 2")
  - Orange, e.g. https://hexcolor.co/hex/ffa500
  - Pink, e.g. https://hexcolor.co/hex/f24c7c
  - Red, e.g. https://hexcolor.co/hex/ff0000
  - Turquoise blue, no idea which one that is, but consider
    https://hexcolor.co/hex/0ac768 ("Stabilo:)")

  - Note default browser Ctrl-F colours; see ``base.css``.

- More of JL’s ideas from 8 Jan 2018:

  - A series of functions like fn_age(rid), fn_is_alive(rid),
    fn_open_referral(rid)

  - Friendly names for the top 10 most used tables, which might appear at the
    top of the tables listing.

- When the Windows service stops, it is still failing to kill child processes.
  See ``crate_anon/tools/winservice.py``.

- NLP protocol revision whereby processors describe their output fields,
  saying which SQL dialect they're using; and (automatic) implementation for
  our built-in NLP.

- There's some placeholder junk in ``consent_lookup_result.html``.
