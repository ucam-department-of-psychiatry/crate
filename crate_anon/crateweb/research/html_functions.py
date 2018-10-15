#!/usr/bin/env python

"""
crate_anon/crateweb/research/html_functions.py

===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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
from typing import Any, Dict, Iterable, List, Optional, Pattern

from cardinal_pythonlib.django.function_cache import django_cache_function
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

def visibility_button(tag: str, small: bool = True,
                      title_html: str = '', as_span: bool = False,
                      as_visibility: bool = True) -> str:
    eltype = "span" if as_span else "div"
    togglefunc = "toggleVisible" if as_visibility else "toggleCollapsed"
    return """
<{eltype} class="expandcollapse" onclick="{togglefunc}('collapsible_{tag}', 'collapse_img_{tag}');">
    <img class="plusminus_image" id="collapse_img_{tag}" alt="" src="{img}">
    {title_html}
</{eltype}>
    """.format(  # noqa
        eltype=eltype,
        togglefunc=togglefunc,
        tag=str(tag),
        img=static('plus.gif') if small else static('minus.gif'),
        title_html=title_html,
    )


def visibility_contentdiv(tag: str,
                          contents: str,
                          extra_div_classes: Iterable[str] = None,
                          small: bool = True,
                          as_visibility: bool = True) -> str:
    extra_div_classes = extra_div_classes or []
    div_classes = ["collapsible"] + extra_div_classes
    if as_visibility:
        if small:
            div_classes.append("collapse_invisible")
        else:
            div_classes.append("collapse_visible")
    else:
        if small:
            div_classes.append("collapse_small")
        else:
            div_classes.append("collapse_big")
    return """
<div class="{div_classes}" id="collapsible_{tag}">
    {contents}
</div>
    """.format(
        div_classes=" ".join(div_classes),
        tag=str(tag),
        contents=contents,
    )


def visibility_div_with_divbutton(tag: str,
                                  contents: str,
                                  title_html: str = '',
                                  extra_div_classes: Iterable[str] = None,
                                  small: bool = True) -> str:
    # The HTML pre-hides, rather than using an onload method
    button = visibility_button(tag=tag, small=small,
                               title_html=title_html, as_visibility=True)
    contents = visibility_contentdiv(tag=tag, contents=contents,
                                     extra_div_classes=extra_div_classes,
                                     small=small, as_visibility=True)
    return "<div>" + button + contents + "</div>"


def overflow_div(tag: str,
                 contents: str,
                 extra_div_classes: Iterable[str] = None,
                 small: bool = True) -> str:
    button = visibility_button(tag=tag, small=small,
                               as_visibility=False)
    contentdiv = visibility_contentdiv(tag=tag, contents=contents,
                                       extra_div_classes=extra_div_classes,
                                       small=small, as_visibility=False)
    return """
<div class="expandcollapsewrapper">
    {button}
    {contentdiv}
</div>
    """.format(button=button, contentdiv=contentdiv)


# =============================================================================
# Class to maintain element counters, for use with pages having lots of
# collapsible divs (or other HTML elements requiring individual numbering)
# =============================================================================

class HtmlElementCounter(object):
    def __init__(self, prefix: str = ''):
        self.elementnum = 0
        self.prefix = prefix

    def next(self):
        self.elementnum += 1

    def tag(self):
        return self.prefix + str(self.elementnum)

    def visibility_div_with_divbutton(self,
                                      contents: str,
                                      title_html: str = '',
                                      extra_div_classes: Iterable[str] = None,
                                      visible: bool = True) -> str:
        result = visibility_div_with_divbutton(
            tag=self.tag(),
            contents=contents,
            title_html=title_html,
            extra_div_classes=extra_div_classes,
            small=visible)
        self.next()
        return result

    def visibility_div_spanbutton(self, small: bool = True) -> str:
        return visibility_button(tag=self.tag(), as_visibility=True,
                                 small=small, as_span=True)

    def visibility_div_contentdiv(self,
                                  contents: str,
                                  extra_div_classes: Iterable[str] = None,
                                  small: bool = True) -> str:
        result = visibility_contentdiv(
            tag=self.tag(),
            contents=contents,
            extra_div_classes=extra_div_classes,
            small=small,
            as_visibility=True)
        self.next()
        return result

    def collapsible_div_contentdiv(self,
                                   contents: str,
                                   extra_div_classes: Iterable[str] = None,
                                   small: bool = True) -> str:
        result = visibility_contentdiv(
            tag=self.tag(),
            contents=contents,
            extra_div_classes=extra_div_classes,
            small=small,
            as_visibility=False)
        self.next()
        return result

    def overflow_div(self,
                     contents: str,
                     extradivclasses: Iterable[str] = None,
                     small: bool = True) -> str:
        result = overflow_div(tag=self.tag(),
                              contents=contents,
                              extra_div_classes=extradivclasses,
                              small=small)
        self.next()
        return result


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
        -> Pattern:
    elements = []
    wb = r"\b"  # word boundary; escape the slash if not using a raw string
    for hl in highlight_list:
        h = escape_literal_string_for_regex(hl.text)
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
                        collapsed: bool = True,
                        null: str = '<i>NULL</i>') -> str:
    # return escape(repr(x))
    if x is None:
        return null
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
        result = element_counter.overflow_div(contents=output,
                                              small=collapsed)
        element_counter.next()
    else:
        result = output
    return result


def pre(x: str = '') -> str:
    return "<pre>{}</pre>".format(x)


# =============================================================================
# SQL formatting
# =============================================================================

SQL_BASE_CSS_CLASS = "sq"  # brief is good
SQL_FORMATTER = HtmlFormatter(cssclass=SQL_BASE_CSS_CLASS)
SQL_LEXER = SqlLexer()


def prettify_sql_html(sql: str,
                      reformat: bool = False,
                      indent_width: int = 4) -> str:
    if reformat:
        sql = sqlparse.format(sql, reindent=True, indent_width=indent_width)
    return highlight(sql, SQL_LEXER, SQL_FORMATTER)


@django_cache_function(timeout=None)
def prettify_sql_css() -> str:
    return SQL_FORMATTER.get_style_defs()


def prettify_sql_and_args(sql: str, args: List[Any] = None,
                          reformat: bool = False,
                          indent_width: int = 4) -> str:
    sql = prettify_sql_html(sql, reformat=reformat, indent_width=indent_width)
    if args:
        formatted_args = "\n".join(textwrap.wrap(repr(args)))
        return sql + "<div>Args:</div><pre>{}</pre>".format(formatted_args)
    else:
        return sql


def make_collapsible_sql_query(x: Optional[str],
                               element_counter: HtmlElementCounter,
                               args: List[Any] = None,
                               collapse_at_len: int = 400,
                               collapse_at_n_lines: int = 5) -> str:
    x = x or ''
    x = str(x)
    xlen = len(x)
    n_lines = len(x.split('\n'))
    formatted = prettify_sql_and_args(x, args, reformat=False)
    # x = linebreaksbr(escape(x))
    if ((collapse_at_len and xlen >= collapse_at_len) or
            (collapse_at_n_lines and n_lines >= collapse_at_n_lines)):
        return element_counter.overflow_div(contents=formatted)
    return formatted
