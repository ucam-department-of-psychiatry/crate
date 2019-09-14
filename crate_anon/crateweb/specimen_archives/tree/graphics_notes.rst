.. crate_anon/crateweb/specimen_archives/tree/graphics_notes.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.


Notes on some Javascript libraries for plotting
===============================================

An overview is at
https://en.wikipedia.org/wiki/Comparison_of_JavaScript_charting_libraries.


Plotly
------

- https://plot.ly/

- MIT licensed core. Good graphics.

- PNG export for free; documents suggest that SVG export requires a
  subscription. See
  https://plot.ly/javascript/static-image-export/#saving-as-svg. However,
  actually not; see
  https://community.plot.ly/t/save-as-svg-instead-of-png-in-modebar/4560;
  https://codepen.io/etpinard/pen/zzzBXv?editors=0010.

- Uses D3 behind the scenes.

- Python version has a ggplot-style interface, ggplotly(); see
  https://plot.ly/ggplot2/.


D3
--

- https://d3js.org

- BSD licence.

- Can save raster formats by converting core SVG object to HTML canvas, then
  saving:
  http://bl.ocks.org/SevenChan07/bfc0cbffad7847845a2dfb123a39aa92

- Possibly can save direct from SVG:
  https://stackoverflow.com/questions/23218174/how-do-i-save-export-an-svg-file-after-creating-an-svg-with-d3-js-ie-safari-an

- ... via FileSaver.js:
  https://github.com/eligrey/FileSaver.js/

- Markedly harder to get basic graphs going than with Plotly.


Decision
--------

Plotly looks like an excellent open-source default.



Mapping
=======

Plotly uses GeoJSON data for choropleth maps.

For the UK, see http://geoportal.statistics.gov.uk/. Specifically, for LSOA
data, see
https://data.gov.uk/dataset/fa883558-22fb-4a1a-8529-cffdee47d500/lower-layer-super-output-area-lsoa-boundaries.
But see also https://github.com/martinjc/UK-GeoJSON.
