#!/usr/bin/env python
# crate_anon/crateweb/research/html_functions.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

import logging
import re
import textwrap
import typing
from typing import Dict, Iterable, List, Optional

from django.contrib.staticfiles.templatetags.staticfiles import static
from django.utils.html import escape
# from django.template import loader
from django.template.defaultfilters import linebreaksbr
from pygments import highlight
from pygments.lexers.sql import SqlLexer
from pygments.formatters.html import HtmlFormatter
import sqlparse

log = logging.getLogger(__name__)


N_CSS_HIGHLIGHT_CLASSES = 3  # named highlight0, highlight1, ... highlight<n-1>
REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.


# =============================================================================
# Collapsible div, etc.
# =============================================================================

def collapsible_div_with_divbutton(tag: str,
                                   contents: str,
                                   title_html: str = '',
                                   extradivclasses: Iterable[str] = None,
                                   collapsed: bool = True) -> str:
    # The HTML pre-hides, rather than using an onload method
    if extradivclasses is None:
        extradivclasses = []
    return """
        <div class="expandcollapse" onclick="toggle('collapse_detail_{tag}', 'collapse_img_{tag}');">
            <img class="plusminus_image" id="collapse_img_{tag}" alt="" src="{img}">
            {title_html}
        </div>
        <div class="collapse_detail {extradivclasses}" id="collapse_detail_{tag}" {hide_me}>
            {contents}
        </div>
    """.format(  # noqa
        tag=str(tag),
        img=static('plus.gif') if collapsed else static('minus.gif'),
        title_html=title_html,
        extradivclasses=" ".join(extradivclasses),
        hide_me='style="display:none"' if collapsed else '',
        contents=contents,
    )


def collapsible_div_spanbutton(tag: str, collapsed: bool = True) -> str:
    return """
        <span class="expandcollapse_span" onclick="toggle('collapse_detail_{tag}', 'collapse_img_{tag}');">
            <img class="plusminus_image" id="collapse_img_{{ tag }}" alt="" src="{img}">
        </span>
    """.format(  # noqa
        tag=str(tag),
        img=static('plus.gif') if collapsed else static('minus.gif'),
    )


def collapsible_div_contentdiv(tag: str,
                               contents: str,
                               extradivclasses: Iterable[str] = None,
                               collapsed: bool = True) -> str:
    if extradivclasses is None:
        extradivclasses = []
    return """
        <div class="collapse_detail {extradivclasses}" id="collapse_detail_{tag}" {hide_me}>
            {contents}
        </div>
    """.format(  # noqa
        extradivclasses=" ".join(extradivclasses),
        tag=str(tag),
        contents=contents,
        hide_me='style="display:none"' if collapsed else '',
    )


def overflow_div(tag: str,
                 contents: str,
                 extradivclasses: Iterable[str] = None,
                 collapsed: bool = True) -> str:
    if extradivclasses is None:
        extradivclasses = []
    return """
        <div class="expandcollapsewrapper">
            <div class="expandcollapse" onclick="toggle('collapse_detail_{tag}', 'collapse_img_{tag}', 'collapse_summary_{tag}');">
                <img class="plusminus_image" id="collapse_img_{tag}" alt="" src="{plus_img}">
            </div>
            <div class="collapse_detail {extradivclasses}" id="collapse_detail_{tag}" {hide_detail}>
                {contents}
            </div>
            <div class="collapse_summary {extradivclasses}" id="collapse_summary_{tag}" {hide_summary}>
                {contents}
            </div>
        </div>
    """.format(  # noqa
        extradivclasses=" ".join(extradivclasses),
        tag=str(tag),
        contents=contents,
        plus_img=static('plus.gif'),
        hide_detail='style="display:none"' if collapsed else '',
        hide_summary='' if collapsed else 'style="display:none"',
    )


# =============================================================================
# Class to maintain element counters, for use with pages having lots of
# collapsible divs (or other HTML elements requiring individual numbering)
# =============================================================================

class HtmlElementCounter(object):
    def __init__(self):
        self.elementnum = 0

    def next(self):
        self.elementnum += 1

    def tag(self):
        return str(self.elementnum)

    def collapsible_div_with_divbutton(self,
                                       contents: str,
                                       title_html: str = '',
                                       extradivclasses: Iterable[str] = None,
                                       collapsed: bool = True) -> str:
        return collapsible_div_with_divbutton(tag=self.tag(),
                                              contents=contents,
                                              title_html=title_html,
                                              extradivclasses=extradivclasses,
                                              collapsed=collapsed)

    def collapsible_div_spanbutton(self, collapsed: bool = True) -> str:
        return collapsible_div_spanbutton(tag=self.tag(), collapsed=collapsed)

    def collapsible_div_contentdiv(self,
                                   contents: str,
                                   extradivclasses: Iterable[str] = None,
                                   collapsed: bool = True) -> str:
        return collapsible_div_contentdiv(tag=self.tag(),
                                          contents=contents,
                                          extradivclasses=extradivclasses,
                                          collapsed=collapsed)

    def overflow_div(self,
                     contents: str,
                     extradivclasses: Iterable[str] = None,
                     collapsed: bool = True) -> str:
        return overflow_div(tag=self.tag(),
                            contents=contents,
                            extradivclasses=extradivclasses,
                            collapsed=collapsed)


# =============================================================================
# Highlighting of query results
# =============================================================================

HIGHLIGHT_FWD_REF = "Highlight"


def escape_literal_string_for_regex(s: str) -> str:
    r"""
    Escape any regex characters.

    Start with \ -> \\
        ... this should be the first replacement in REGEX_METACHARS.
    """
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


def get_regex_from_highlights(highlight_list: Iterable[HIGHLIGHT_FWD_REF],
                              at_word_boundaries_only: bool = False) \
        -> typing.re.Pattern:
    elements = []
    wb = r"\b"  # word boundary; escape the slash if not using a raw string
    for highlight in highlight_list:
        h = escape_literal_string_for_regex(highlight.text)
        if at_word_boundaries_only:
            elements.append(wb + h + wb)
        else:
            elements.append(h)
    regexstring = u"(" + "|".join(elements) + ")"  # group required, to replace
    return re.compile(regexstring, re.IGNORECASE | re.UNICODE)


def highlight_text(x: str, n: int = 0) -> str:
    n %= N_CSS_HIGHLIGHT_CLASSES
    return r'<span class="highlight{n}">{x}</span>'.format(n=n, x=x)


def make_highlight_replacement_regex(n: int = 0) -> str:
    return highlight_text(r"\1", n=n)


def make_result_element(x: Optional[str],
                        element_counter: HtmlElementCounter,
                        highlight_dict: Dict[int,
                                             List[HIGHLIGHT_FWD_REF]] = None,
                        collapse_at_len: int = None,
                        collapse_at_n_lines: int = None,
                        line_length: int = None,
                        keep_existing_newlines: bool = True,
                        collapsed: bool = True) -> str:
    # return escape(repr(x))
    if x is None:
        return ""
    highlight_dict = highlight_dict or {}
    x = str(x)
    xlen = len(x)  # before we mess around with it
    # textwrap.wrap will absorb existing newlines
    if keep_existing_newlines:
        input_lines = x.split("\n")
    else:
        input_lines = [x]
    if line_length:
        output_lines = []
        for line in input_lines:
            if line:
                output_lines.extend(textwrap.wrap(line, width=line_length))
            else:  # blank line; textwrap.wrap will swallow it
                output_lines.append('')
    else:
        output_lines = input_lines
    n_lines = len(output_lines)
    # return escape(repr(output_lines))
    output = linebreaksbr(escape("\n".join(output_lines)))
    # return escape(repr(output))
    for n, highlight_list in highlight_dict.items():
        find = get_regex_from_highlights(highlight_list)
        replace = make_highlight_replacement_regex(n)
        output = find.sub(replace, output)
    if ((collapse_at_len and xlen >= collapse_at_len) or
            (collapse_at_n_lines and n_lines >= collapse_at_n_lines)):
        return element_counter.overflow_div(contents=output,
                                            collapsed=collapsed)
    return output


def pre(x: str = '') -> str:
    return "<pre>{}</pre>".format(x)


# =============================================================================
# SQL formatting
# =============================================================================

SQL_BASE_CSS_CLASS = "sql_formatted"
SQL_FORMATTER = HtmlFormatter(cssclass=SQL_BASE_CSS_CLASS)
SQL_LEXER = SqlLexer()


def prettify_sql_html(sql: str,
                      reformat: bool = False,
                      indent_width: int = 4) -> str:
    if reformat:
        sql = sqlparse.format(sql, reindent=True, indent_width=indent_width)
    return highlight(sql, SQL_LEXER, SQL_FORMATTER)


def prettify_sql_css() -> str:
    return SQL_FORMATTER.get_style_defs()


def make_collapsible_sql_query(x: Optional[str],
                               element_counter: HtmlElementCounter,
                               collapse_at_len: int = 400,
                               collapse_at_n_lines: int = 5) -> str:
    x = x or ''
    formatted = prettify_sql_html(x, reformat=False)
    x = str(x)
    xlen = len(x)
    n_lines = len(x.split('\n'))
    x = linebreaksbr(escape(x))
    if ((collapse_at_len and xlen >= collapse_at_len) or
            (collapse_at_n_lines and n_lines >= collapse_at_n_lines)):
        return element_counter.overflow_div(contents=formatted)
    return formatted
