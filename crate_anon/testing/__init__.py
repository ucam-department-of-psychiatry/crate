"""
crate_anon/testing/__init__.py

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

"""

from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

# Access metadata through *Base.metadata
AnonTestBase = declarative_base(metadata=MetaData())
SourceTestBase = declarative_base(metadata=MetaData())


def mock_connection_exit(self, type_: Any, value: Any, traceback: Any) -> None:
    """
    Ensure exceptions are raised when mocking context managers.

    .. code-block:: python

        from unittest import mock

        from crate_anon.testing import mock_connection_exit

        mock_thing = mock.Mock()
        mock_cm = mock.Mock()
        mock_cm.__enter__ = mock.Mock(return_value=mock_thing)
        mock_cm.__exit___ = mock_connection_exit
        mock_fn = mock.Mock(return_value=mock_cm)
    """
    return type_ is None
