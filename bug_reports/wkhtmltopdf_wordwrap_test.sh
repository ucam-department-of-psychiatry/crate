#!/bin/bash

wkhtmltopdf \
    --page-size A4 \
    --dpi 300 \
    --orientation portrait \
    --margin-top 20mm \
    --margin-right 20mm \
    --margin-bottom 20mm \
    --margin-left 20mm \
    --encoding UTF-8 \
    wkhtmltopdf_wordwrap_1.html \
    output_wkhtmltopdf_wordwrap_1.pdf
