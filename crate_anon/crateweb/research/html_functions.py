#!/usr/bin/env python3
# research/html_functions.py

import re
import textwrap
from django.utils.html import escape
from django.template import loader
from django.template.defaultfilters import linebreaksbr
import logging
logger = logging.getLogger(__name__)


N_CSS_HIGHLIGHT_CLASSES = 3  # named highlight0, highlight1, ... highlight<n-1>
REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.


# =============================================================================
# Collapsible div
# =============================================================================

def collapsible_div(tag, contents, extradivclasses=None):
    # The HTML pre-hides, rather than using an onload method
    if extradivclasses is None:
        extradivclasses = []
    template = loader.get_template('collapsible_div.html')
    context = {
        'extradivclasses': " ".join(extradivclasses),
        'tag': tag,
        'contents': contents,
    }
    return template.render(context)  # as HTML


def overflow_div(tag, contents, extradivclasses=None):
    if extradivclasses is None:
        extradivclasses = []
    template = loader.get_template('overflow_div.html')
    context = {
        'extradivclasses': " ".join(extradivclasses),
        'tag': tag,
        'contents': contents,
    }
    return template.render(context)  # as HTML


# =============================================================================
# Highlighting of query results
# =============================================================================

def escape_literal_string_for_regex(s):
    r"""
    Escape any regex characters.

    Start with \ -> \\
        ... this should be the first replacement in REGEX_METACHARS.
    """
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


def get_regex_from_highlights(highlight_list, at_word_boundaries_only=False):
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


def highlight_text(x, n=0):
    n %= N_CSS_HIGHLIGHT_CLASSES
    return r'<span class="highlight{n}">{x}</span>'.format(n=n, x=x)


def make_highlight_replacement_regex(n=0):
    return highlight_text(r"\1", n=n)


def make_result_element(x, elementnum, highlight_dict=None, collapse_at=None,
                        line_length=None):
    if x is None:
        return ""
    highlight_dict = highlight_dict or {}
    x = str(x)
    xlen = len(x)  # before we mess around with it
    if line_length:
        x = "\n".join(textwrap.wrap(x, width=line_length))
    x = linebreaksbr(escape(x))
    for n, highlight_list in highlight_dict.items():
        find = get_regex_from_highlights(highlight_list)
        replace = make_highlight_replacement_regex(n)
        x = find.sub(replace, x)
    if collapse_at and xlen >= collapse_at:
        # return collapsible_div(elementnum, x)
        return overflow_div(elementnum, x)
    return x


def pre(x=''):
    return "<pre>{}</pre>".format(x)


def make_collapsible_query(x, elementnum, collapse_at_n_lines=5):
    if x is None:
        return pre()
    x = str(x)
    n_lines = len(x.split('\n'))
    x = linebreaksbr(escape(x))
    if collapse_at_n_lines and n_lines >= collapse_at_n_lines:
        return overflow_div(elementnum, pre(x))
    return pre(x)
