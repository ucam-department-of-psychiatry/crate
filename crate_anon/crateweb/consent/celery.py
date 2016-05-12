#!/usr/bin/env python3
# crate_anon/crateweb/consent/celery.py

import os

from celery import Celery, current_task

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
    print('Backend: {}'.format(current_task.backend))

"""
===============================================================================
To test:
===============================================================================

1. Launch the Celery worker:
    # no directory change required for an installed package
    # in early testing:
    #   $ cd [...]/crateweb
    #   $ celery --app consent worker --loglevel=debug
    # but with a proper package:
    
    $ celery worker --app crate_anon.crateweb.consent --loglevel debug

2. Call the function asynchronously
    $ manage.py shell
    >>> from consent.celery import debug_task
    >>> debug_task.delay()

    or simply:
    $ python
    >>> from crate_anon.crateweb.consent.celery import debug_task
    >>> debug_task.delay()

===============================================================================
Command-line testing under Windows (2016-05-12):
===============================================================================
(1)
Run crate_launch_celery (which runs the "celery worker" command).
With that running...

(2)
$ python
>>> from crate_anon.crateweb.consent.tasks import add
>>> add(3, 4)  # call immediately
7
>>> result = add.delay(3, 5)  # call via Celery

# AT THAT MOMENT, THE CELERY WORKER PROCESS SHOULD SAY:
[... INFO/MainProcess] Received task: celery.local.add[...]
[... INFO/MainProcess] Task celery.local.add[...] succeeded in ...s: 8

>>> result
<AsyncResult: 48ad8faa-ce75-4a19-bb0e-77feb9567b06>
>>> result.ready()
>>> result.state

(3) When it doesn't work...

$ sudo rabbitmqctl list_queues name messages consumers
    
>>> from crate_anon.crateweb.consent.celery import app
>>> app.control.purge()
# Should report the number of tasks in the queue, after which the rabbitmqctl
# should show an empty queue.

# Using the lengthy "--include" argument to "celery worker", which I was using
# (in launch_celery.py) before creating a proper pip-installed package, seems
# to be unnecessary.

# With "--loglevel info", the task list looks like:
[tasks]
  . crate_anon.crateweb.consent.celery.debug_task
  . crate_anon.crateweb.consent.tasks.add
  . crate_anon.crateweb.consent.tasks.email_rdbm_task
  . crate_anon.crateweb.consent.tasks.finalize_clinician_response
  . crate_anon.crateweb.consent.tasks.process_consent_change
  . crate_anon.crateweb.consent.tasks.process_contact_request
  . crate_anon.crateweb.consent.tasks.process_patient_response
  . crate_anon.crateweb.consent.tasks.resend_email
  . crate_anon.crateweb.consent.tasks.test_email_rdbm_task

With "--loglevel debug", it looks like this:
[tasks]
  . celery.backend_cleanup
  . celery.chain
  . celery.chord
  . celery.chord_unlock
  . celery.chunks
  . celery.group
  . celery.local.add
  . celery.local.email_rdbm_task
  . celery.local.finalize_clinician_response
  . celery.local.process_consent_change
  . celery.local.process_contact_request
  . celery.local.process_patient_response
  . celery.local.resend_email
  . celery.local.test_email_rdbm_task
  . celery.map
  . celery.starmap
  . crate_anon.crateweb.consent.celery.debug_task
  . crate_anon.crateweb.consent.tasks.add
  . crate_anon.crateweb.consent.tasks.email_rdbm_task
  . crate_anon.crateweb.consent.tasks.finalize_clinician_response
  . crate_anon.crateweb.consent.tasks.process_consent_change
  . crate_anon.crateweb.consent.tasks.process_contact_request
  . crate_anon.crateweb.consent.tasks.process_patient_response
  . crate_anon.crateweb.consent.tasks.resend_email
  . crate_anon.crateweb.consent.tasks.test_email_rdbm_task

... but that doesn't stop it working under Linux.


Inspecting workers:
    http://docs.celeryproject.org/en/latest/userguide/workers.html#inspecting-workers  # noqa

Inspecting lots of things:
    pip install flower
    celery -A crate_anon.crateweb.consent flower
    http://localhost:5555/

Celery bug under Windows? https://github.com/celery/celery/issues/897

Upgrade from Celery 3.1.19 to 3.1.23:
    OK! Now we're talking.
    - Flower can now connect to the Celery worker (which reports things in its
      log as Flower does so).
    - Tasks now show up in Flower -> Tasks, marked "Received", with appropriate
      arguments, and with a worker assigned, but the "Started" column remains
      blank.

But then it stopped working again.
- https://github.com/mher/flower/issues/452
  ... indicates that "celery inspect ping" should be doing something, but I'm
  getting "No workers replied within time constraint." On Linux, we get:
    -> celery@wombat: OK
            pong

Improvement if you run the Celery worker with "--concurrency=4" (up from its
default of 1). Flower talks to the nodes. The tasks appear in the worker's
task list. Both "celery status" and "celery inspect ping" work. But tasks
still go into the "Reserved" list.

The "-Ofair" option didn't fix it:
    http://stackoverflow.com/questions/24519559

And then it screwed up again, and became unresponsive to the status things.
Argh!

- Close all Celery things.
- Hard reset of RabbitMQ:
    rabbitmqctl stop_app
    rabbitmqctl reset
    rabbitmqctl start_app
- Start Celery worker(s).
- celery -A crate_anon.crateweb.consent status
    ... now works
- But tasks are still going into the reserved queue.

People have achieved this with Win10:
    https://github.com/hotdogee/django-blast/Windows-Development-Environment-Setup  # noqa

Aha! Using "--pool=solo" made it work!
    https://stackoverflow.com/questions/20309954


===============================================================================
See also tasks.py, with more notes
===============================================================================
"""
