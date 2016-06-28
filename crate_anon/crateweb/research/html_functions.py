#!/usr/bin/env python3
# research/html_functions.py

import re
import textwrap
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.utils.html import escape
from django.template import loader
from django.template.defaultfilters import linebreaksbr
import logging
log = logging.getLogger(__name__)


N_CSS_HIGHLIGHT_CLASSES = 3  # named highlight0, highlight1, ... highlight<n-1>
REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.


# =============================================================================
# Collapsible div
# =============================================================================

def collapsible_div_with_divbutton(tag, contents, extradivclasses=None,
                                   collapsed=True):
    # The HTML pre-hides, rather than using an onload method
    if extradivclasses is None:
        extradivclasses = []
    return """
        <div class="expandcollapse" onclick="toggle('collapse_detail_{tag}', 'collapse_img_{tag}');">
            <img class="plusminus_image" id="collapse_img_{tag}" alt="" src="{img}">
        </div>
        <div class="collapse_detail {extradivclasses}" id="collapse_detail_{tag}" {hide_me}>
            {contents}
        </div>
    """.format(  # noqa
        tag=str(tag),
        img=static('plus.gif') if collapsed else static('minus.gif'),
        extradivclasses=" ".join(extradivclasses),
        hide_me='style="display:none"' if collapsed else '',
        contents=contents,
    )


def collapsible_div_spanbutton(tag, collapsed=True):
    return """
        <span class="expandcollapse_span" onclick="toggle('collapse_detail_{tag}', 'collapse_img_{tag}');">
            <img class="plusminus_image" id="collapse_img_{{ tag }}" alt="" src="{img}">
        </span>
    """.format(  # noqa
        tag=str(tag),
        img=static('plus.gif') if collapsed else static('minus.gif'),
    )


def collapsible_div_contentdiv(tag, contents, extradivclasses=None,
                               collapsed=True):
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


def overflow_div(tag, contents, extradivclasses=None):
    if extradivclasses is None:
        extradivclasses = []
    return """
        <div class="expandcollapsewrapper">
            <div class="expandcollapse" onclick="toggle('collapse_detail_{tag}', 'collapse_img_{tag}', 'collapse_summary_{tag}');">
                <img class="plusminus_image" id="collapse_img_{tag}" alt="" src="{plus_img}">
            </div>
            <div class="collapse_detail {extradivclasses}" id="collapse_detail_{tag}" style="display:none">
                {contents}
            </div>
            <div class="collapse_summary {extradivclasses}" id="collapse_summary_{tag}">
                {contents}
            </div>
        </div>
    """.format(  # noqa
        extradivclasses=" ".join(extradivclasses),
        tag=str(tag),
        contents=contents,
        plus_img=static('plus.gif'),
    )


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


def make_result_element(x, elementnum, highlight_dict=None,
                        collapse_at_len=None, collapse_at_n_lines=None,
                        line_length=None, keep_existing_newlines=True):
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
        return overflow_div(elementnum, output)
    return output


def pre(x=''):
    return "<pre>{}</pre>".format(x)


def make_collapsible_query(x, elementnum,
                           collapse_at_len=400, collapse_at_n_lines=5):
    if x is None:
        return pre()
    x = str(x)
    xlen = len(x)
    n_lines = len(x.split('\n'))
    x = linebreaksbr(escape(x))
    if ((collapse_at_len and xlen >= collapse_at_len) or
            (collapse_at_n_lines and n_lines >= collapse_at_n_lines)):
        return overflow_div(elementnum, pre(x))
    return pre(x)
