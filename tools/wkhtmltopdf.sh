#!/bin/bash
xvfb-run --auto-servernum --server-args="-screen 0 640x480x16" /usr/bin/wkhtmltopdf "$@"
