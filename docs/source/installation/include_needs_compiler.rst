.. crate_anon/docs/source/installation/include_needs_compiler.rst

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

.. note::

    This module needs to compile itself from C/C++ source. Under Linux, this
    should just work. Under Windows, you may need to install a compiler, which
    must (to some degree) match the Python version you're using. If you don't
    have a compiler, you will get errors relating to "query_vcvarsall". For
    Python 3.4, try Microsoft Visual Studio 2010 (Visual C++ 10.0) or Visual
    C++ Express 2010. Under 64-bit Windows, or if you have a later version of
    Visual Studio, see also http://stackoverflow.com/questions/28251314; you’ll
    need to set the ``VS100COMNTOOLS`` environment variable.
