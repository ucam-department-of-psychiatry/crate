#!/usr/bin/env python

"""
crate_anon/crateweb/core/utils.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Core utility functions for the web interface.**

"""

from abc import ABC, abstractmethod
import datetime
import logging
import mimetypes
import re
import urllib.parse
from typing import Any, Generator, List, Optional, Union

from cardinal_pythonlib.reprfunc import auto_repr
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, Page, PageNotAnInteger
from django.db.models import QuerySet
from django.http import QueryDict
from django.http.request import HttpRequest
from django.utils import timezone
from crate_anon.crateweb.userprofile.models import get_per_page

log = logging.getLogger(__name__)


# =============================================================================
# User tests/user profile
# =============================================================================

def is_superuser(user: settings.AUTH_USER_MODEL) -> bool:
    """
    Is the user a superuser?

    Function for use with a decorator, e.g.

    .. code-block:: python

        @user_passes_test(is_superuser)
        def some_view(request: HttpRequest) -> HttpResponse:
            pass

    Superuser equates to Research Database Manager.
    """
    # https://docs.djangoproject.com/en/dev/topics/auth/default/#django.contrib.auth.decorators.user_passes_test  # noqa
    return user.is_superuser


def is_developer(user: settings.AUTH_USER_MODEL) -> bool:
    """
    Is the user a developer?

    (Developers are a subset of superusers.)
    """
    if not user.is_authenticated:
        return False  # won't have a profile
    return user.profile.is_developer


def is_clinician(user: settings.AUTH_USER_MODEL) -> bool:
    """
    Is the user a clinician?
    """
    if not user.is_authenticated:
        return False  # won't have a profile
    return user.profile.is_clinician


# =============================================================================
# Forms
# =============================================================================

def paginate(request: HttpRequest,
             all_items: Union[QuerySet, List[Any]],
             per_page: int = None) -> Page:
    """
    Paginate a list or a Django QuerySet.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        all_items: a list or a :class:`django.db.models.QuerySet`
        per_page: number of items per page

    Returns:
        a :class:`django.core.paginator.Page`

    """
    if per_page is None:
        per_page = get_per_page(request)
    paginator = Paginator(all_items, per_page)
    # noinspection PyCallByClass,PyArgumentList
    requested_page = request.GET.get('page')
    try:
        return paginator.page(requested_page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


# =============================================================================
# URL creation
# =============================================================================

def url_with_querystring(path: str,
                         querydict: QueryDict = None,
                         **kwargs: Any) -> str:
    """
    Add GET arguments to a URL from named arguments or a QueryDict.

    Args:
        path:
            a base URL path
        querydict:
            a :class:`django.http.QueryDict`
        **kwargs:
            as an alternative to the ``querydict``, we can use ``kwargs`` as a
            dictionary of query attribute-value pairs

    Returns:
        the URL with query parameters

    Note:

        This does not currently sort query parameters. Doing that might be
        slightly advantageous for caching, i.e. to ensure that
        "path?a=1&b=2" is treated as identical to "path?b=2&a=1". However, it
        is legal for servers to treat them as ordered. See
        https://stackoverflow.com/questions/43893853/http-cache-control-and-params-order.
    """  # noqa
    # Get initial query parameters, if any.
    # log.critical(f"IN: path={path!r}, querydict={querydict!r}, "
    #              f"kwargs={kwargs!r}")
    pr = urllib.parse.urlparse(path)  # type: urllib.parse.ParseResult
    qd = QueryDict(mutable=True)
    if pr.query:
        for k, values in urllib.parse.parse_qs(pr.query).items():
            for v in values:
                qd[k] = v

    # Update with the new parameters
    if querydict is not None:
        if not isinstance(querydict, QueryDict):
            raise ValueError("Bad querydict value")
        qd.update(querydict)
    if kwargs:
        qd.update(kwargs)

    # Calculate the query string
    if qd:
        querystring = qd.urlencode()
        # for kwargs: querystring = urllib.parse.urlencode(kwargs)
    else:
        querystring = ""

    # Return the final rebuilt URL.
    # You can't write to a urllib.parse.ParseResult. So, as per
    # https://stackoverflow.com/questions/26221669/how-do-i-replace-a-query-with-a-new-value-in-urlparse  # noqa
    # we have do to this:

    components = list(pr)
    components[4] = querystring
    url = urllib.parse.urlunparse(components)
    # log.critical(f"OUT: {url}")
    return url


def site_absolute_url(path: str) -> str:
    """
    Returns an absolute URL for the site, given a relative part.
    Use like:

    .. code-block:: python

        url = site_absolute_url(static('red.png'))
            # ... determined in part by STATIC_URL.
        url = site_absolute_url(reverse(UrlNames.CLINICIAN_RESPONSE, args=[self.id]))
            # ... determined by SCRIPT_NAME or FORCE_SCRIPT_NAME
            # ... which is context-dependent: see below

    We need to generate links to our site outside the request environment, e.g.
    for inclusion in e-mails, even when we're generating the e-mails offline
    via Celery. There's no easy way to do this automatically (site path
    information comes in only via requests), so we put it in the settings.

    See also:

    - http://stackoverflow.com/questions/4150258/django-obtaining-the-absolute-url-without-access-to-a-request-object
    - https://fragmentsofcode.wordpress.com/2009/02/24/django-fully-qualified-url/

    **IMPORTANT**

    BEWARE: :func:`reverse` will produce something different inside a request
    and outside it.

    - http://stackoverflow.com/questions/32340806/django-reverse-returns-different-values-when-called-from-wsgi-or-shell

    So the only moderately clean way of doing this is to do this in the Celery
    backend jobs, for anything that uses Django URLs (e.g. :func:`reverse`) --
    NOT necessary for anything using only static URLs (e.g. pictures in PDFs).

    .. code-block:: python

        from django.conf import settings
        from django.urls import set_script_prefix

        set_script_prefix(settings.FORCE_SCRIPT_NAME)

    But that does at least mean we can use the same method for static and
    Django URLs.
    """  # noqa
    url = settings.DJANGO_SITE_ROOT_ABSOLUTE_URL + path
    log.debug(f"site_absolute_url: {path} -> {url}")
    return url


# =============================================================================
# Formatting
# =============================================================================

def get_friendly_date(date: datetime.datetime) -> str:
    """
    Returns a string form of a date/datetime.
    """
    if date is None:
        return ""
    try:
        return date.strftime("%d %B %Y")  # e.g. 03 December 2013
    except Exception as e:
        raise type(e)(str(e) + f' [value was {date!r}]')


# =============================================================================
# Date/time
# =============================================================================

def string_time_now() -> str:
    """
    Returns the current time in short-form ISO-8601 UTC, for filenames.
    """
    return timezone.now().strftime("%Y%m%dT%H%M%SZ")


# =============================================================================
# HTTP Content-Type and MIME types
# =============================================================================

def guess_mimetype(filename: str, default: str = None) -> Optional[str]:
    """
    Guesses a file's MIME type (HTTP Content-Type) from its filename.

    Args:
        filename: filename
        default: value to return if guessing fails
    """
    return mimetypes.guess_type(filename)[0] or default


# =============================================================================
# Javascript help
# =============================================================================

HTML_WHITESPACE = re.compile("[ \n\t]+")


def javascript_quoted_string_from_html(html: str) -> str:
    """
    Takes some HTML, which may be multiline, and makes it into a single quoted
    Javascript string, for when we want to muck around with the DOM.

    We elect to use double-quotes.
    """
    # log.error(f"Before: {html}")
    x = " ".join(HTML_WHITESPACE.split(html))  # Remove extra whitespace/newlines  # noqa
    x = x.replace('"', r'\"')  # Escape double quotes
    x = f'"{x}"'  # Enclose string in double quotes
    # log.critical(f"After: {x}")
    return x


# =============================================================================
# Javascript tree
# =============================================================================

class JavascriptTreeNode(ABC):
    """
    Represents a node of a :class:`JavascriptTree`.
    """
    def __init__(self,
                 text: str = "",
                 node_id: str = "",
                 children: List["JavascriptTreeNode"] = None) -> None:
        """
        Args:
            text: text to display
            node_id: CSS node ID (only the root node will use this mechanism;
                the rest will be autoset by the root node)
            children: child nodes, if any
        """
        self.text = text
        self.node_id = node_id
        self.children = children or []  # type: List[JavascriptTreeNode]

    def __repr__(self) -> str:
        return auto_repr(self)

    def set_node_id(self, node_id: str) -> None:
        """
        Sets the node's ID.
        """
        self.node_id = node_id

    def gen_descendants(self) -> Generator["JavascriptTreeNode", None, None]:
        """
        Yields all descendants, recursively.
        """
        for child in self.children:
            yield child
            for descendant in child.gen_descendants():
                yield descendant

    @abstractmethod
    def html(self) -> str:
        """
        Returns HTML for this node.
        """
        pass


class JavascriptLeafNode(JavascriptTreeNode):
    """
    Represents a leaf node of a :class:`JavascriptTree`, i.e. one that launches
    some action.
    """
    def __init__(self,
                 text: str,
                 action_html: str) -> None:
        """
        Args:
            text: text to display
            action_html: HTML associated with the action (e.g. to attach to
                part of the page, in order to load other content)
        """
        super().__init__(text=text)
        self.action_html = action_html

    def html(self) -> str:
        return f'<li id="{self.node_id}">{self.text}</li>'

    def js_action_dict_key_value(self) -> str:
        """
        Returns a Javascript snippet for incorporating into a dictionary:
        ``node_id: action_html``.
        """
        js_action_html = javascript_quoted_string_from_html(self.action_html)
        return f'"{self.node_id}":{js_action_html}'


class JavascriptBranchNode(JavascriptTreeNode):
    """
    Represents a leaf node of a :class:`JavascriptTree`, i.e. one that has
    children but does not itself perform an action.
    """
    def __init__(self,
                 text: str,
                 children: List[JavascriptTreeNode] = None,
                 branch_class: str = "caret",
                 child_ul_class: str = "nested") -> None:
        """
        Args:
            text: text to display
            children: children of this node
            branch_class: CSS class for the branch with caret/indicator
            child_ul_class: CSS class for the sublist with the children
        """
        super().__init__(text=text, children=children)
        self.branch_class = branch_class
        self.child_ul_class = child_ul_class

    def html(self) -> str:
        child_html = "".join(node.html() for node in self.children)
        return (
            f'<li>'
            f'<span class="{self.branch_class}">{self.text}</span>'
            f'<ul class="{self.child_ul_class}">'
            f'{child_html}'
            f'</ul>'
            f'</li>'
        )

    def add_child(self, child: JavascriptTreeNode) -> None:
        """
        Adds a child at the end of our list.
        """
        self.children.append(child)


class JavascriptTree(JavascriptTreeNode):
    """
    Represents the root node of an expanding tree implemented via Javascript.

    Demo:

    .. code-block:: Python

        # Django debugging preamble
        import os
        import django
        os.environ['DJANGO_SETTINGS_MODULE'] = 'crate_anon.crateweb.config.settings'
        django.setup()

        from crate_anon.crateweb.core.utils import (
            JavascriptBranchNode,
            JavascriptLeafNode,
            JavascriptTree,
        )

        t = JavascriptTree(
            tree_id="my_tree",
            child_id_prefix="my_tree_child_",
            children=[
                JavascriptBranchNode("RiO", [
                    JavascriptLeafNode("Clinical Documents", "<p>Clinical docs</p>"),
                    JavascriptLeafNode("Progress Notes", "<p>Prog notes</p>"),
                ]),
                JavascriptLeafNode("Test PDF", "<p>Test a PDF</p>"),
            ]
        )
        print(t.html())
        print(t.js_str_html())
        print(t.js_data())

    """  # noqa
    def __init__(self,
                 tree_id: str,
                 child_id_prefix: str,
                 children: List[JavascriptTreeNode] = None,
                 tree_class: str = "tree") -> None:
        """
        Args:
            tree_id: CSS ID for this tree
            child_id_prefix: CSS ID prefix for children
            children: child nodes
            tree_class: CSS class for this tree
        """
        super().__init__(children=children, node_id=tree_id)
        self.node_id_prefix = child_id_prefix
        self.tree_class = tree_class
        self._node_ids_set = False

    def add_child(self, child: JavascriptTreeNode) -> None:
        """
        Adds a child at the end of our list.
        """
        self.children.append(child)
        self._node_ids_set = False

    def _write_child_ids(self) -> None:
        """
        Sets the node IDs for all our children.
        """
        if self._node_ids_set:
            return
        for i, descendant in enumerate(self.gen_descendants()):
            descendant.set_node_id(f"{self.node_id_prefix}{i}")
        self._node_ids_set = True

    def html(self) -> str:
        """
        Returns HTML for this tree.
        """
        self._write_child_ids()
        child_html = "".join(node.html() for node in self.children)
        return (
            f'<ul class="{self.tree_class}" id="{self.node_id}">'
            f'{child_html}'
            f'</ul>'
        )

    def js_str_html(self) -> str:
        """
        Returns HTML for this tree, as a quoted Javascript string, for
        embedding in Javascript code directly.
        """
        return javascript_quoted_string_from_html(self.html())

    def js_data(self) -> str:
        """
        Returns Javascript code for a dictionary mapping node IDs to
        action HTML.
        """
        self._write_child_ids()
        content = ",".join(
            child.js_action_dict_key_value()
            for child in self.gen_descendants()
            if isinstance(child, JavascriptLeafNode)
        )
        return f"{{{content}}}"

    @property
    def tree_id(self) -> str:
        """
        Synonym for ``node_id`` for the root node.
        """
        return self.node_id
