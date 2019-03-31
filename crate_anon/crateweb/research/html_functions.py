#!/usr/bin/env python

"""
crate_anon/crateweb/research/html_functions.py

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

**Helper functions for low-level HTML, used in the "research" section of the
CRATE web site.**

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
    """
    Returns HTML for a "(+)/(-)" button. Used for:

    - visibility (show/hide): to show/hide things
    - collapse (expand/collapse): to collapse large cells in query results.

    Args:
        tag: tag used for this set of elements; used as part of the parameters
            to Javascript ``toggleVisible`` or ``toggleCollapsed`` functions;
            see ``crate_anon/crateweb/static/collapse.js``
        small: start small (or invisible) rather than big (or visible)?
        title_html: HTML to put inside the element
        as_span: return a ``<span>`` element rather than a ``<div>`` element?
        as_visibility: "visibility" style, rather than "collapse" style?

    Returns:
        str: HTML

    See :func:`visibility_contentdiv` for the associated content.

    """
    eltype = "span" if as_span else "div"
    togglefunc = "toggleVisible" if as_visibility else "toggleCollapsed"
    tag = str(tag)
    img = static('plus.gif') if small else static('minus.gif')
    return f"""
<{eltype} class="expandcollapse" onclick="{togglefunc}('collapsible_{tag}', 'collapse_img_{tag}');">
    <img class="plusminus_image" id="collapse_img_{tag}" alt="" src="{img}">
    {title_html}
</{eltype}>
    """  # noqa


def visibility_contentdiv(tag: str,
                          contents: str,
                          extra_div_classes: Iterable[str] = None,
                          small: bool = True,
                          as_visibility: bool = True) -> str:
    """
    Returns HTML for a content ``<div>`` that can be collapsed by a button
    (for which, see :func:`visibility_button`).

    Args:
        tag: tag used for this set of elements; used as part of the parameters
            to Javascript ``toggleVisible`` or ``toggleCollapsed`` functions;
            see ``crate_anon/crateweb/static/collapse.js``
        contents: HTML contents of the ``div``
        extra_div_classes: extra CSS classes to add to the ``div``
        small: start small (or invisible) rather than big (or visible)?
        as_visibility: "visibility" style, rather than "collapse" style?

    Returns:
        str: HTML

    """
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
    tag = str(tag)
    return f"""
<div class="{" ".join(div_classes)}" id="collapsible_{str(tag)}">
    {contents}
</div>
    """


def visibility_div_with_divbutton(tag: str,
                                  contents: str,
                                  title_html: str = '',
                                  extra_div_classes: Iterable[str] = None,
                                  small: bool = True) -> str:
    """
    Returns an HTML ``<div>`` with a show/hide button and contents.

    Args:
        tag: tag used for this set of elements; used as part of the parameters
            to Javascript ``toggleVisible`` or ``toggleCollapsed`` functions;
            see ``crate_anon/crateweb/static/collapse.js``
        contents: HTML contents of the content ``div``
        title_html: HTML to put inside the button element
        extra_div_classes: extra CSS classes to add to the content ``div``
        small: start invisible rather than visible?

    Returns:
        str: HTML

    - The HTML pre-hides, rather than using an onload method.

    """
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
    """
    Returns an HTML ``<div>`` with an expand/collapse button and contents.

    Args:
        tag: tag used for this set of elements; used as part of the parameters
            to Javascript ``toggleVisible`` or ``toggleCollapsed`` functions;
            see ``crate_anon/crateweb/static/collapse.js``
        contents: HTML contents of the content ``div``
        extra_div_classes: extra CSS classes to add to the content ``div``
        small: start collapsed rather than expanded?

    Returns:
        str: HTML
    """
    button = visibility_button(tag=tag, small=small,
                               as_visibility=False)
    contentdiv = visibility_contentdiv(tag=tag, contents=contents,
                                       extra_div_classes=extra_div_classes,
                                       small=small, as_visibility=False)
    return f"""
<div class="expandcollapsewrapper">
    {button}
    {contentdiv}
</div>
    """


# =============================================================================
# HtmlElementCounter
# =============================================================================

class HtmlElementCounter(object):
    """
    Class to maintain element counters, for use with pages having lots of
    collapsible divs (or other HTML elements requiring individual numbering).
    """
    def __init__(self, prefix: str = '') -> None:
        """
        Args:
            prefix: text to be prefixed to the tag used for HTML elements
        """
        self.elementnum = 0
        self.prefix = prefix

    def next(self) -> None:
        """
        Increments the ``elementnum`` counter.
        """
        self.elementnum += 1

    def tag(self) -> str:
        """
        Returns a tag based on the prefix and current element number.
        """
        return self.prefix + str(self.elementnum)

    def visibility_div_with_divbutton(self,
                                      contents: str,
                                      title_html: str = '',
                                      extra_div_classes: Iterable[str] = None,
                                      small: bool = True) -> str:
        """
        Returns a "visibility" ``<div>`` with a show/hide button.

        Args:
            contents: HTML contents of the content ``div``
            title_html: HTML to put inside the button element
            extra_div_classes: extra CSS classes to add to the content ``div``
            small: start invisible, rather than visible?

        Returns:
            str: HTML
        """
        result = visibility_div_with_divbutton(
            tag=self.tag(),
            contents=contents,
            title_html=title_html,
            extra_div_classes=extra_div_classes,
            small=small)
        self.next()
        return result

    def visibility_div_spanbutton(self, small: bool = True) -> str:
        """
        Returns a visibility button in an HTML ``<span>``.

        Args:
            small: start in "hidden" rather than "visible" mode?

        Returns:
            str: HTML

        """
        return visibility_button(tag=self.tag(), as_visibility=True,
                                 small=small, as_span=True)

    def visibility_div_contentdiv(self,
                                  contents: str,
                                  extra_div_classes: Iterable[str] = None,
                                  small: bool = True) -> str:
        """
        Returns a "visibility" content ``<div>``.

        Args:
            contents: HTML contents of the content ``div``
            extra_div_classes: extra CSS classes to add to the ``div``
            small: start invisible, rather than visible?

        Returns:
            str: HTML

        """
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
        """
        Returns a "collapsible" content ``<div>``

        Args:
            contents: HTML contents of the ``div``
            extra_div_classes: extra CSS classes to add to the content ``div``
            small: start collapsed, rather than expanded?

        Returns:
            str: HTML
        """
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
                     extra_div_classes: Iterable[str] = None,
                     small: bool = True) -> str:
        """
        Returns a "overflow" ``<div>`` with content and an expand/collapse
        button.

        Args:
            contents: HTML contents of the ``div``
            extra_div_classes: extra CSS classes to add to the content ``div``
            small: start collapsed, rather than expanded?

        Returns:
            str: HTML
        """
        result = overflow_div(tag=self.tag(),
                              contents=contents,
                              extra_div_classes=extra_div_classes,
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

    - Start with `\` -> ``\\``.
      This should be the first replacement in REGEX_METACHARS.
    """
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


def get_regex_from_highlights(highlight_list: Iterable[HIGHLIGHT_FWD_REF],
                              at_word_boundaries_only: bool = False) \
        -> Pattern:
    """
    Takes a list of the user's chosen highlights to apply to results, and
    builds a compiled regular expression for (any of) them.

    Args:
        highlight_list: list of
            :class:`crate_anon.crateweb.research.models.Highlight` objects,
            which represent text to find and a colour to highlight it with
        at_word_boundaries_only: match at word boundaries only?

    Returns:
        a compiled regular expression (case-insensitive)

    """
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
    """
    Transforms text (from a query result) into HTML that highlights it.

    Args:
        x: original text
        n: highlight colour number to use (as per our ``static/base.css``)

    Returns:

    """
    n %= N_CSS_HIGHLIGHT_CLASSES
    return fr'<span class="highlight{n}">{x}</span>'


def make_highlight_replacement_regex(n: int = 0) -> str:
    r"""
    Makes a regex replacement string that highlights the first "found" group
    with a specific highlight colour.

    Args:
        n: highlight colour number to use (as per our ``static/base.css``)

    Returns:
        str: regex text like ``<span class="highlight1">\1</span>``

    """
    return highlight_text(r"\1", n=n)


def make_result_element(x: Any,
                        element_counter: HtmlElementCounter,
                        highlight_dict: Dict[int,
                                             List[HIGHLIGHT_FWD_REF]] = None,
                        collapse_at_len: int = None,
                        collapse_at_n_lines: int = None,
                        line_length: int = None,
                        keep_existing_newlines: bool = True,
                        collapsed: bool = True,
                        null: str = '<i>NULL</i>') -> str:
    """
    Returns a collapsible HTML ``<div>`` for a result cell, with optional
    highlighting of results.

    Args:
        x: the value
        element_counter: a :class:``HtmlElementCounter``, used for
            distinguishing multiple elements; it will be modified
        highlight_dict: an optional dictionary mapping highlight colour to all
            the :class:`crate_anon.crateweb.research.models.Highlight` objects
            that use it (e.g.: ``2`` maps to highlight objects for all the
            separate pieces of text to be highlighted in colour 2)
        collapse_at_len: if specified, the string length beyond which the cell
            will be collapsed
        collapse_at_n_lines: if specified, the number of lines beyond which the
            cell will be collapsed
        line_length: if specified, the line length to word-wrap at
        keep_existing_newlines: retain existing newlines from the source?
        collapsed: start cells collapsed rather than expanded?
        null: HTML string to use for database NULL values

    Returns:
        str: HTML

    """
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
    """
    Applies an HTML ``<pre>...</pre>`` tag.

    Args:
        x: input

    Returns:
        the input within a ``pre`` tag

    """
    return f"<pre>{x}</pre>"


# =============================================================================
# SQL formatting
# =============================================================================

SQL_BASE_CSS_CLASS = "sq"  # brief is good
SQL_FORMATTER = HtmlFormatter(cssclass=SQL_BASE_CSS_CLASS)
SQL_LEXER = SqlLexer()


def prettify_sql_html(sql: str,
                      reformat: bool = False,
                      indent_width: int = 4) -> str:
    """
    Formats SQL (optionally), and highlights it with Pygments.

    Args:
        sql: raw SQL text
        reformat: reformat the layout?
        indent_width: if reformatting, what indent should we use?

    Returns:
        str: HTML

    """
    if reformat:
        sql = sqlparse.format(sql, reindent=True, indent_width=indent_width)
    return highlight(sql, SQL_LEXER, SQL_FORMATTER)


@django_cache_function(timeout=None)
def prettify_sql_css() -> str:
    """
    Returns the CSS used by the Pygments SQL formatter.
    """
    return SQL_FORMATTER.get_style_defs()


def prettify_sql_and_args(sql: str, args: List[Any] = None,
                          reformat: bool = False,
                          indent_width: int = 4) -> str:
    """
    Returns HTML for both some SQL and its arguments.

    Args:
        sql: SQL text
        args: optional list of arguments
        reformat: reformat the layout?
        indent_width: if reformatting, what indent should we use?

    Returns:
        str: HTML

    """
    sql = prettify_sql_html(sql, reformat=reformat, indent_width=indent_width)
    if args:
        formatted_args = "\n".join(textwrap.wrap(repr(args)))
        return sql + f"<div>Args:</div><pre>{formatted_args}</pre>"
    else:
        return sql


def make_collapsible_sql_query(sql: Optional[str],
                               element_counter: HtmlElementCounter,
                               args: List[Any] = None,
                               collapse_at_len: int = 400,
                               collapse_at_n_lines: int = 5) -> str:
    """
    Formats an SQL query (and its arguments, if any) in a collapsible HTML
    ``<div>``.

    Args:
        sql: SQL text
        element_counter:
        args: optional list of arguments
        collapse_at_len: if specified, the string length beyond which the cell
            will be collapsed
        collapse_at_n_lines: if specified, the number of lines beyond which the
            cell will be collapsed

    Returns:
        str: HTML

    """
    sql = sql or ''
    sql = str(sql)
    xlen = len(sql)
    n_lines = len(sql.split('\n'))
    formatted = prettify_sql_and_args(sql, args, reformat=False)
    # x = linebreaksbr(escape(x))
    if ((collapse_at_len and xlen >= collapse_at_len) or
            (collapse_at_n_lines and n_lines >= collapse_at_n_lines)):
        return element_counter.overflow_div(contents=formatted)
    return formatted
