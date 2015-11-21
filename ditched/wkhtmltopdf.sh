#!/bin/bash
# Necessary only if running wkhtmltopdf in a version that requires an X Server.
# Prefer installing a better version!
xvfb-run --auto-servernum --server-args="-screen 0 640x480x16" /usr/bin/wkhtmltopdf "$@"
