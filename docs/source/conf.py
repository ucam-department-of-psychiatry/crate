"""
docs/source/conf.py

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

**Configure Sphinx to build documentation.**

Tips when Sphinx goes wrong (e.g. on docstrings):

- Add ``-W`` to ``SPHINXOPTS`` in the ``Makefile``
- Add ``-vvv`` to ``SPHINXOPTS`` in the ``Makefile``.
- Run ``make html > tmp_sphinx_output.txt`` (stderr is less helpful).
- Search for (a) your filename, then (b) ``[autodoc] output:`` subsequently;
  this should show the RST. Search also for things like
  ``.. py:method:: BaseNlpParser``.
- Put the RST into https://livesphinx.herokuapp.com/.
- Inspect the RST.

- Notice in particular:

  - Most docstrings are autoconverted from the Google ``Args:`` format to the
    ugly ``:param thing:`` format.
  - In some cases, a class-level docstring is automatically merged with the
    ``__init__`` docstring, with a different indentation level, and this means
    that ``Args:`` stuff comes through at the wrong indentation level and is
    misinterpreted.

- Attempt to fix this problem:
  https://stackoverflow.com/questions/5599254/how-to-use-sphinxs-autodoc-to-document-a-classs-init-self-method

  - However, note that this makes the ``__init__`` functions appear, but does
    not prevent the ``__init__`` docstring being appended to the main class
    docstring.
  - Then remove ``autoclass_content = "both"``; see
    https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#confval-autoclass_content.
  - That makes message more helpful!
  - But you still often need to add a line at the top of the ``__init__``
    docstring.

Less helpful:

- add ``import traceback; traceback.print_stack()`` to
  ``sphinx.util.logging.WarningIsErrorFilter.filter``
- add ``print(">>>\n" + "\n".join(lines) + "<<<")`` as the penultimate line
  of ``sphinx.util.docstrings.prepare_docstring``
- noting that ``sphinx/parsers.py`` does everything via
  ``docutils.parsers.rst.states.RSTStateMachine``, ... oh, never mind

"""  # noqa

# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import os
from typing import Any

import django
from sphinx.application import Sphinx
from sphinx.ext.autodoc import Options

from crate_anon.common.constants import EnvVar
from crate_anon.version import CRATE_VERSION


# -- Project information -----------------------------------------------------

project = "CRATE"
# noinspection PyShadowingBuiltins
copyright = "2015, University of Cambridge, Department of Psychiatry"
author = "Rudolf Cardinal"

# The short X.Y version
version = CRATE_VERSION
# The full version, including alpha/beta/rc tags
release = CRATE_VERSION


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.githubpages",
    "sphinx.ext.imgmath",
    "sphinx.ext.napoleon",
    # ... support different docstring styles; we use the Google style:
    # https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings  # noqa
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.

# Since Sphinx 5.0 language = None is not recommended and generates a
# warning.
# https://github.com/sphinx-doc/sphinx/issues/10474
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = [
    # Stuff from Sphinx
    "_build",
    "Thumbs.db",
    ".DS_Store",
    # CRATE:
    "installation/include*.rst",
    "website_using/include*.rst",
    # ... but don't exclude autodoc/**/include*.rst, so don't use
    # "**/include*.rst"
]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#

# See http://www.sphinx-doc.org/en/master/theming.html
# html_theme = 'alabaster'  # elegant but monochrome
# html_theme = 'classic'  # like the Python docs. GOOD. CHOSEN. Then sphinx_rtd_theme  # noqa
# html_theme = 'sphinxdoc'  # OK; TOC on right
# html_theme = 'scrolls'  # ugly
# html_theme = 'agogo'  # nice, but a bit big-print; TOC on right; justified
# html_theme = 'traditional'  # moderately ugly
# html_theme = 'nature'  # very nice. Used for CamCOPS.
# html_theme = 'haiku'  # doesn't do sidebar
# html_theme = 'pyramid'  # Once inline code customized, GOOD.
# html_theme = 'bizstyle'  # OK
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# favicon; see
# https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_favicon  # noqa
html_favicon = "images/scrubber.ico"

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
# 'searchbox.html']``.
#
# html_sidebars = {}

# https://stackoverflow.com/questions/18969093/how-to-include-the-toctree-in-the-sidebar-of-each-page
html_sidebars = {
    "**": [
        "globaltoc.html",
        "relations.html",
        "sourcelink.html",
        "searchbox.html",
    ]
}

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "CRATEdoc"


# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "CRATE.tex",
        "CRATE Documentation",
        "Rudolf Cardinal",
        "manual",
    ),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "crate", "CRATE Documentation", [author], 1)]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "CRATE",
        "CRATE Documentation",
        author,
        "CRATE",
        "One line description of project.",
        "Miscellaneous",
    ),
]


# -- Extension configuration -------------------------------------------------

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True


# -----------------------------------------------------------------------------
# RNC extras
# -----------------------------------------------------------------------------


# noinspection PyUnusedLocal
def skip(
    app: Sphinx,
    what: str,
    name: str,
    obj: Any,
    would_skip: bool,
    options: Options,
) -> bool:
    # Called by sphinx.ext.autodoc.Documenter.filter_members (q.v.).
    if name == "__init__":
        return False
    return would_skip


def setup(app: Sphinx) -> None:
    # Add CSS
    # https://stackoverflow.com/questions/23462494/how-to-add-a-custom-css-file-to-sphinx  # noqa
    app.add_css_file("css/crate_docs.css")  # may also be an URL

    # Don't skip __init__
    # https://stackoverflow.com/questions/5599254/how-to-use-sphinxs-autodoc-to-document-a-classs-init-self-method  # noqa
    app.connect("autodoc-skip-member", skip)


# -----------------------------------------------------------------------------
# RNC: autodoc
# -----------------------------------------------------------------------------
# http://www.sphinx-doc.org/en/stable/ext/autodoc.html#confval-autodoc_mock_imports  # noqa
# https://stackoverflow.com/questions/36228537/django-settings-module-not-defined-when-building-sphinx-documentation

autodoc_mock_imports = [
    "servicemanager",  # Windows only
    "win32event",  # Windows only
    "win32service",  # Windows only
    "win32serviceutil",  # Windows only
    "winerror",  # Windows only
]

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

# sys.path.insert(0, os.path.join(os.path.abspath('.'), '../../myproj'))

# ... see crate_anon/crateweb/config/settings.py
os.environ["DJANGO_SETTINGS_MODULE"] = "crate_anon.crateweb.config.settings"
django.setup()


# https://stackoverflow.com/questions/5599254/how-to-use-sphinxs-autodoc-to-document-a-classs-init-self-method  # noqa
autoclass_content = "class"

# To prevent Pyramid SETTINGS breaking:
os.environ[EnvVar.GENERATING_CRATE_DOCS] = "true"

# For "Command killed due to excessive memory consumption" on readthedocs.org:
# https://docs.readthedocs.io/en/latest/guides/build-using-too-many-resources.html  # noqa
