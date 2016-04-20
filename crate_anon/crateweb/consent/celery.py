#!/usr/bin/env python3
# crate_anon/crateweb/consent/celery.py

import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'crate_anon.crateweb.config.settings')
# RNC: note that the module path must be accessible from the PYTHONPATH,

# from django.conf import settings

app = Celery('consent')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')

# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
# ... looks for "tasks.py" in all apps
# ... REQUIRES that all apps have an __init__.py
#     https://github.com/celery/celery/issues/2523

app.autodiscover_tasks(['crate_anon.crateweb.consent'])  # simpler!


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

"""
To test:

1. Launch the Celery worker:
    $ cd [...]/crateweb
    $ celery -A consent worker --loglevel=debug

2. Call the function asynchronously
    $ manage.py shell
    >>> from consent.celery import debug_task
    >>> debug_task.delay()
"""
