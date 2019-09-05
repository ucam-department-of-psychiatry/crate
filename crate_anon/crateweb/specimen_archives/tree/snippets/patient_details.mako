## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/snippets/patient_id.mako

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

This demonstrates a Mako template offering Python functions (with return
values) to other Mako templates. The specific example is to apply site-specific
processing to the ``patient_id`` string.

Note the various kinds of Mako "Python things":

## ----------------------------------------------------------------------------
## Module-level block, semicolon and exclamation mark
## ----------------------------------------------------------------------------

<%!

# Python code here is executed on template startup, NOT every time the template
# is used.
#
# Commonly used to import Python objects, and to define functions and
# constants.
#
# If a function here needs access to a template "instance" variable,
# you must pass in the relevant variable or the "context" object (the
# Mako-provided dictionary of all objects provided within the template).
#
# Functions here can't be accessed directly by templates other than this one,
# even via the <%namespace%> directive. If you try, you get errors like
# "Namespace 'patient_details' has no member 'CPFTPatientID'".

%>

## ----------------------------------------------------------------------------
## Standard block, semicolon only
## ----------------------------------------------------------------------------

<%

# Python code here is executed as the template's body() is evaluated.
# Code here has access to any module-level code, and also to objects that are
# part of the Mako context.
#
# Functions here can't be accessed directly by templates other than this one.

%>

## ----------------------------------------------------------------------------
## Mako def
## ----------------------------------------------------------------------------

## Use this to execute functions to make HTML (etc.).
## You can call functions that have been defined thus far (in module-level
## blocks or standard blocks).

<%def name="heading(heading_text, capitalize)">
    %if capitalize:
        <h1>${heading_text.upper()}</h1>
    %else:
        <h1>${heading_text}</h1>
    %endif
</%def>

## In another template, you can access this as:

<%namespace name="testfunc" file="somewhere/testfunc.mako"/>
${testfunc.heading("Hello, world", False)}

## However, what about functions that return values?

## ----------------------------------------------------------------------------
## Mako def that returns a value
## ----------------------------------------------------------------------------

## This was less obvious; thanks to
## https://stackoverflow.com/questions/4749458/calling-a-def-as-a-function-in-a-mako-template

<%def name="is_too_long(text)">
    <%
        if len(text) > 5:
            return True
        return False
    %>
</%def>

## Then, in another template:

<%namespace name="testfunc" file="somewhere/testfunc.mako"/>
<%
    text = "Huckleberry Finn"
%>

%if testfunc.is_too_long(text):
    ${testfunc.heading(text, False)}
%else:
    <h1>Heading was too long<h1>
%endif

## ----------------------------------------------------------------------------
## Parameter naming for <%def> functions
## ----------------------------------------------------------------------------

Do not name the parameter "context". A Mako block like

.. code-block:: none

    <%def name="get_patient_details(context)">\
        <% return CPFTPatientDetails(context) %>
    </%def>

will translate to Python like:

.. code-block:: python

    def render_get_patient_details(context,context):
        __M_caller = context.caller_stack._push_frame()
        try:
            __M_writer = context.writer()
            __M_writer('    ')
            return CPFTPatientDetails(context)

            __M_writer('\n')
            return ''
        finally:
            context.caller_stack._pop_frame()

... which will crash with ``duplicate argument 'context' in function
definition``.

The solution here is to realize that context always arrives "for free" in
``<%def>`` blocks.

## ----------------------------------------------------------------------------
## BEWARE:
## ----------------------------------------------------------------------------

When Mako Python code is syntactically wrong, it can lead to the appearance of
the browser hanging, and all sorts of oddities. The error messages, when they
come, relate to the whole block of Python code rather than the line with the
error. Debug your Python carefully.


</%doc>

<%!

import logging
from typing import Any, Dict, Optional

from crate_anon.crateweb.research.archive_backend import ArchiveContextKeys

log = logging.getLogger(__name__)


class CPFTPatientDetails(object):
    """
    Class to translate an incoming string-encoded patient ID, on demand, on to
    one of several.
    """
    def __init__(self, context: Dict[str, Any]) -> None:
        """
        Args:
            context:
                Mako ``context`` object, which will contain the patient ID
                information
        """
        self.context = context
        self.patient_id = context[ArchiveContextKeys.patient_id]  # type: str

    @property
    def rio_number(self) -> Optional[int]:
        """
        Returns the CPFT RiO number, if known.
        """
        return self.patient_id  # but could do e.g. JSON evaluation

    @property
    def crs_cdl_number(self) -> Optional[int]:
        """
        Returns the CPFT CRS/CDL number, if known.
        """
        return None  # but could do e.g. JSON evaluation

    @property
    def nhs_number(self) -> Optional[int]:
        """
        Returns the NHS number, if known.
        """
        return None  # but could do e.g. JSON evaluation

    @property
    def forename(self) -> str:
        """
        Returns the forename, or a blank string if unknown.
        """
        return ""

    @property
    def surname(self) -> str:
        """
        Returns the surname, or a blank string if unknown.
        """
        return ""


%>

<%def name="get_patient_details()"><%
    pd = CPFTPatientDetails(context)
    return pd
%></%def>
