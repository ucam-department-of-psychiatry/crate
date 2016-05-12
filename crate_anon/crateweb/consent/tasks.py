#!/usr/bin/env python3
# consent/tasks.py

from celery import shared_task, task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.urlresolvers import set_script_prefix

"""
===============================================================================
See also celery.py, which defines the app
===============================================================================

===============================================================================
If you get a "received unregistered task" error:
===============================================================================
1.  Restart the Celery worker. That may fix it.
2.  If that fails, consider: SPECIFY ABSOLUTE NAMES FOR TASKS.
    e.g. with @shared_task(name="myfuncname")
    Possible otherwise that if this module is imported in different ways
    (e.g. absolute, relative), you'll get a "Received unregistered task"
    error.
    http://docs.celeryq.org/en/latest/userguide/tasks.html#task-names

===============================================================================
Acknowledgement/not doing things more than once:
===============================================================================
- http://docs.celeryproject.org/en/latest/userguide/tasks.html
- default is to acknowledge on receipt of request, not after task completion;
  that prevents things from happening more than once.
  If you can guarantee your function is idempotent, you can acknowledge after
  completion.
- http://docs.celeryproject.org/en/latest/faq.html#faq-acks-late-vs-retry
- We'll stick with the default (slightly less reliable but won't be run more
  than once).

===============================================================================
Circular imports:
===============================================================================
- http://stackoverflow.com/questions/17313532/django-import-loop-between-celery-tasks-and-my-models  # noqa
- The potential circularity is:
    - At launch, Celery must import tasks, which could want to import models.
    - At launch, Django loads models, which may use tasks.
- Simplest solution is to keep tasks very simple (as below) and use delayed
  imports here.

===============================================================================
Race condition:
===============================================================================
- Django:
    (1) existing object
    (2) amend with form
    (3) save()
    (4) call function.delay(obj.id)
  Object is received by Celery in the state before save() at step 3.
- http://celery.readthedocs.org/en/latest/userguide/tasks.html#database-transactions  # noqa
- http://stackoverflow.com/questions/26862942/django-related-objects-are-missing-from-celery-task-race-condition  # noqa
- https://code.djangoproject.com/ticket/14051
- https://github.com/aaugustin/django-transaction-signals
- SOLUTION:
  https://docs.djangoproject.com/en/dev/topics/db/transactions/#django.db.transaction.on_commit  # noqa
    from django.db import transaction
    transaction.on_commit(lambda: blah.delay(blah))
  Requires Django 1.9. As of 2015-11-21, that means 1.9rc1
"""


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def add(x, y):
    return x + y


# noinspection PyCallingNonCallable,PyPep8Naming
@shared_task
@task(ignore_result=True)
def resend_email(email_id, user_id):
    User = get_user_model()
    from crate_anon.crateweb.consent.models import Email  # delayed import
    email = Email.objects.get(pk=email_id)
    user = User.objects.get(pk=user_id)
    email.resend(user)


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def process_contact_request(contact_request_id):
    from crate_anon.crateweb.consent.models import ContactRequest  # delayed import  # noqa
    set_script_prefix(settings.FORCE_SCRIPT_NAME)  # see site_absolute_url
    contact_request = ContactRequest.objects.get(pk=contact_request_id)
    contact_request.process_request()


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def finalize_clinician_response(clinician_response_id):
    from crate_anon.crateweb.consent.models import ClinicianResponse  # delayed import  # noqa
    clinician_response = ClinicianResponse.objects.get(
        pk=clinician_response_id)
    clinician_response.finalize_b()  # second part of processing


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def process_consent_change(consent_mode_id):
    from crate_anon.crateweb.consent.models import ConsentMode  # delayed import  # noqa
    consent_mode = ConsentMode.objects.get(pk=consent_mode_id)
    consent_mode.process_change()


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def process_patient_response(patient_response_id):
    from crate_anon.crateweb.consent.models import PatientResponse  # delayed import  # noqa
    patient_response = PatientResponse.objects.get(pk=patient_response_id)
    patient_response.process_response()


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def test_email_rdbm_task():
    subject = "TEST MESSAGE FROM RESEARCH DATABASE COMPUTER"
    text = (
        "Success! The CRATE framework can communicate via Celery with its "
        "message broker, so it can talk to an 'offline' copy of itself "
        "for background processing. And it can e-mail you."
    )
    email_rdbm_task(subject, text)  # Will this work as a function? Yes.


# noinspection PyCallingNonCallable
@shared_task
@task(ignore_result=True)
def email_rdbm_task(subject, text):
    from crate_anon.crateweb.consent.models import Email  # delayed import
    email = Email.create_rdbm_text_email(subject, text)
    email.send()
