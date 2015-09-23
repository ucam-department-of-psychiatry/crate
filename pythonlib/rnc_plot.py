#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support for plotting.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: October 2013
Last update: 21 Sep 2015

Copyright/licensing:

    Copyright (C) 2013-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import io
import numpy
import sys
if sys.version_info > (3,):
    buffer = memoryview

import rnc_web


# =============================================================================
# Image embedding in PDFs
# =============================================================================
# xhtml2pdf (2013-04-11) supports PNG, but not SVG.
# You can convert SVG to PNG for embedding:
# http://stackoverflow.com/questions/787287
# You could make a PDF and append it, though that would (without further
# effort) lack the patient headers.

def png_img_html_from_pyplot_figure(fig, dpi=100, extra_html_class=None):
    """Converts a pyplot figure to an HTML IMG tag with encapsulated PNG."""
    if fig is None:
        return ""
    # Make a file-like object
    memfile = io.BytesIO()
    # In general, can do
    #   fig.savefig(filename/file-like-object/backend, format=...)
    # or
    #   backend.savefig(fig):
    # see e.g. http://matplotlib.org/api/backend_pdf_api.html
    fig.savefig(memfile, format="png", dpi=dpi)
    memfile.seek(0)
    pngblob = buffer(memfile.read())
    return rnc_web.get_png_img_html(pngblob, extra_html_class)


def svg_html_from_pyplot_figure(fig):
    """Converts a pyplot figure to an SVG tag."""
    if fig is None:
        return ""
    memfile = io.BytesIO()  # StringIO doesn't like mixing str/unicode
    fig.savefig(memfile, format="svg")
    return memfile.getvalue().decode("utf-8")  # returns a text/Unicode type
    # SVG works directly in HTML; it returns <svg ...></svg>


# =============================================================================
# Plotting
# =============================================================================

def set_matplotlib_fontsize(matplotlib, fontsize=12):
    """Sets the current font size within the matplotlib library."""
    font = {
        # http://stackoverflow.com/questions/3899980
        # http://matplotlib.org/users/customizing.html
        'family': 'sans-serif',
        # ... serif, sans-serif, cursive, fantasy, monospace
        'style': 'normal',  # normal (roman), italic, oblique
        'variant': 'normal',  # normal, small-caps
        'weight': 'normal',
        # ... normal [=400], bold [=700], bolder [relative to current],
        # lighter [relative], 100, 200, 300, ..., 900
        'size': fontsize  # in pt (default 12)
    }
    matplotlib.rc('font', **font)
    legend = {
        # http://stackoverflow.com/questions/7125009
        'fontsize': fontsize
    }
    matplotlib.rc('legend', **legend)


# =============================================================================
# Maths
# =============================================================================

def logistic(x, k, theta):
    """Standard logistic function."""
    if x is None or k is None or theta is None:
        return None
    return 1 / (1 + numpy.exp(-k * (x - theta)))


def inv_logistic(y, k, theta):
    """Inverse standard logistic function."""
    if y is None or k is None or theta is None:
        return None
    return (numpy.log((1 / y) - 1) / -k) + theta
