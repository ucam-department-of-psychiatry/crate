#!/usr/bin/python
# -*- encoding: utf8 -*-

# =============================================================================
# ErrorReportingMiddleware
# =============================================================================

import sys
import cgitb
import StringIO


class ErrorReportingMiddleware(object):
    """WSGI middleware to produce cgitb traceback."""
    def __init__(self, app):
        self.app = app

    def format_exception(self, exc_info):
        dummy_file = StringIO.StringIO()
        hook = cgitb.Hook(file=dummy_file)
        hook(*exc_info)
        return [dummy_file.getvalue()]

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except:
            exc_info = sys.exc_info()
            start_response(
                '500 Internal Server Error',
                [('content-type', 'text/html')],
                exc_info
            )
            return self.format_exception(exc_info)
