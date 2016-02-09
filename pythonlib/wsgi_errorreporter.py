#!/usr/bin/python
# -*- encoding: utf8 -*-

# =============================================================================
# ErrorReportingMiddleware
# =============================================================================
# From: http://pylonsbook.com/en/1.0/the-web-server-gateway-interface-wsgi.html
# Modified to use six.StringIO
# Latest changes: 6 Jan 2016

import six
import sys
import cgitb


class ErrorReportingMiddleware(object):
    """WSGI middleware to produce cgitb traceback."""
    def __init__(self, app):
        self.app = app

    def format_exception(self, exc_info):
        dummy_file = six.StringIO()
        hook = cgitb.Hook(file=dummy_file)
        hook(*exc_info)
        if six.PY3:
            return [dummy_file.getvalue().encode('utf-8')]
        else:
            return [dummy_file.getvalue()]

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except:
            exc_info = sys.exc_info()
            start_response(
                '500 Internal Server Error',
                [('content-type', 'text/html; charset=utf-8')],
                exc_info
            )
            return self.format_exception(exc_info)
