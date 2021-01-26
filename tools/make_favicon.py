#!/usr/bin/env python

"""
tools/make_favicon.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

Make ``favicon.ico``.

Art notes:

- Edit the original SVG with Inkscape.

- Use Inkscape's "Document Properties" to resize page to content, and
  **then** ensure the page is square, or ICO files will emerge at unusual
  rectangular sizes and browsers may ignore it.

- Use ``identify`` (part of ImageMagick) to check the final ``.ico`` file.

"""

import logging
from os.path import abspath, dirname, join, pardir
from tempfile import TemporaryDirectory

from cairosvg import svg2png
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from PIL import Image

log = logging.getLogger(__name__)

# =============================================================================
# Directories
# =============================================================================

THIS_DIR = abspath(dirname(__file__))  # .../crate/tools
DOCS_DIR = abspath(join(THIS_DIR, pardir, "docs"))  # .../crate/docs/

CRATE_ROOT_DIR = abspath(join(THIS_DIR, pardir, "crate_anon"))  # .../crate/crate_anon/  # noqa
CRATEWEB_STATIC_DIR = join(CRATE_ROOT_DIR, "crateweb", "static")

DOCS_SOURCE_IMAGES_DIR = join(DOCS_DIR, "source", "images")

# =============================================================================
# Files
# =============================================================================

SCRUBBER_SOURCE_FILENAME = join(DOCS_SOURCE_IMAGES_DIR, "scrubber.svg")
FAVICON_TARGETS = [
    join(CRATEWEB_STATIC_DIR, "scrubber.ico"),
    join(DOCS_SOURCE_IMAGES_DIR, "scrubber.ico"),
]
PNG_TARGETS = [
    (join(CRATEWEB_STATIC_DIR, "scrubber.png"), 48, 48),
    (join(DOCS_SOURCE_IMAGES_DIR, "scrubber.png"), 48, 48),
]  # each is: filename, width, height


# =============================================================================
# Create the favicon
# =============================================================================

def make_favicon() -> None:
    """
    Creates a ``favicon.ico`` file, and other associated images.
    """
    source = SCRUBBER_SOURCE_FILENAME
    with TemporaryDirectory() as tmpdirname:
        # ---------------------------------------------------------------------
        # SVG to PNG
        # ---------------------------------------------------------------------
        big_png_filename = join(tmpdirname, "tmp.png")
        log.info(f"Reading source: {source}")
        log.info(f"Writing temporary PNG file: {big_png_filename}")
        # https://stackoverflow.com/questions/6589358/convert-svg-to-png-in-python/6599172#6599172
        # https://cairosvg.org/
        # default size is very big
        svg2png(url=source, write_to=big_png_filename)
        for png_filename, width, height in PNG_TARGETS:
            log.info(f"Writing 48x48 PNG to: {png_filename}")
            svg2png(url=source, write_to=png_filename,
                    output_width=width, output_height=height)

        # ---------------------------------------------------------------------
        # PNG to ICO
        # ---------------------------------------------------------------------
        img = Image.open(big_png_filename)
        for favicon_filename in FAVICON_TARGETS:
            log.info(f"Writing multi-size icon to destination: "
                     f"{favicon_filename}")
            # https://stackoverflow.com/questions/45507/is-there-a-python-library-for-generating-ico-files
            # https://pillow.readthedocs.io/en/3.1.x/handbook/image-file-formats.html#ico
            # ... default sizes are good
            img.save(favicon_filename)

    log.info("... done.")


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == "__main__":
    main_only_quicksetup_rootlogger(level=logging.INFO)
    make_favicon()
