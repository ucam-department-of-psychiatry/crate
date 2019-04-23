#!/usr/bin/env python

"""
crate_anon/crateweb/consent/tasks.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Celery tasks for the CRATE consent-to-contact system.**

See also :mod:`crate_anon.crateweb.consent.celery`, which defines the ``app``.

**If you get a "received unregistered task" error:**

1.  Restart the Celery worker. That may fix it.

2.  If that fails, consider: SPECIFY ABSOLUTE NAMES FOR TASKS.
    e.g. with ``@shared_task(name="myfuncname")``.
    Possible otherwise that if this module is imported in different ways
    (e.g. absolute, relative), you'll get a "Received unregistered task"
    error.
    http://docs.celeryq.org/en/latest/userguide/tasks.html#task-names


**Acknowledgement/not doing things more than once:**

- http://docs.celeryproject.org/en/latest/userguide/tasks.html

- default is to acknowledge on receipt of request, not after task completion;
  that prevents things from happening more than once.
  If you can guarantee your function is idempotent, you can acknowledge after
  completion.

- http://docs.celeryproject.org/en/latest/faq.html#faq-acks-late-vs-retry

- We'll stick with the default (slightly less reliable but won't be run more
  than once).


**Circular imports:**

- http://stackoverflow.com/questions/17313532/django-import-loop-between-celery-tasks-and-my-models

- The potential circularity is:

    - At launch, Celery must import tasks, which could want to import models.

    - At launch, Django loads models, which may use tasks.

- Simplest solution is to keep tasks very simple (as below) and use delayed
  imports here.


**Race condition:**

- Django:

    (1) existing object
    (2) amend with form
    (3) save()
    (4) call function.delay(obj.id)

  Object is received by Celery in the state before save() at step 3.

- http://celery.readthedocs.org/en/latest/userguide/tasks.html#database-transactions

- http://stackoverflow.com/questions/26862942/django-related-objects-are-missing-from-celery-task-race-condition

- https://code.djangoproject.com/ticket/14051

- https://github.com/aaugustin/django-transaction-signals

- SOLUTION:
  https://docs.djangoproject.com/en/dev/topics/db/transactions/#django.db.transaction.on_commit

  .. code-block:: python

    from django.db import transaction
    transaction.on_commit(lambda: blah.delay(blah))

  Requires Django 1.9. As of 2015-11-21, that means 1.9rc1

"""  # noqa

import logging
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import set_script_prefix

log = logging.getLogger(__name__)


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def add(x: float, y: float) -> float:
    """
    Task to add two numbers. For testing!

    Args:
        x: a float
        y: another float

    Returns:
        x + y

    """
    return x + y


# noinspection PyCallingNonCallable,PyPep8Naming
@shared_task(ignore_result=True)
def resend_email(email_id: int, user_id: int) -> None:
    """
    Celery task to resend a pre-existing e-mail.

    Args:
        email_id: ID of the e-mail
        user_id: ID of the sending user

    Callers include
    - :meth:`crate_anon.crateweb.core.admin.EmailDevAdmin.resend`

    Creates/saves an
    :class:`crate_anon.crateweb.consent.models.EmailTransmission`.
    """
    User = get_user_model()
    from crate_anon.crateweb.consent.models import Email  # delayed import
    email = Email.objects.get(pk=email_id)
    user = User.objects.get(pk=user_id)
    email.resend(user)


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def process_contact_request(contact_request_id: int) -> None:
    """
    Celery task to act on a contact request. For example, might send an e-mail
    to a clinician, or generate a letter to the researcher.

    Callers include
    - :meth:`crate_anon.crateweb.consent.models.ContactRequest.create`

    Sets ``processed = True`` and ``processed_at`` for the
    :class:`crate_anon.crateweb.consent.models.ContactRequest`.

    Args:
        contact_request_id: PK of the contact request
    """
    from crate_anon.crateweb.consent.models import ContactRequest  # delayed import  # noqa
    set_script_prefix(settings.FORCE_SCRIPT_NAME)  # see site_absolute_url
    contact_request = ContactRequest.objects.get(pk=contact_request_id)  # type: ContactRequest  # noqa
    contact_request.process_request()


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def finalize_clinician_response(clinician_response_id: int) -> None:
    """
    Celery task to do the thinking associated with a clinician's response to
    a contact request. For example, might generate letters to patients and
    notify the Research Database Manager of work to be done.

    Callers include
    - :meth:`crate_anon.crateweb.consent.views.finalize_clinician_response_in_background`

    Sets ``processed = True`` and ``processed_at`` for the
    :class:`crate_anon.crateweb.consent.models.ClinicianResponse`.

    Args:
        clinician_response_id: PK of the clinician response
    """  # noqa
    from crate_anon.crateweb.consent.models import ClinicianResponse  # delayed import  # noqa
    clinician_response = ClinicianResponse.objects.get(
        pk=clinician_response_id)
    clinician_response.finalize_b()  # second part of processing


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def process_consent_change(consent_mode_id: int) -> None:
    """
    Celery task to do the thinking associated with a change of consent mode
    (e.g. might send a withdrawal letter to a researcher).

    Callers include:
    - :meth:`crate_anon.crateweb.core.admin.ConsentModeMgrAdmin.save_model`

    Sets ``processed = True`` for the
    :class:`crate_anon.crateweb.consent.models.ConsentMode`,
    if ``current == True`` and ``needs_processing == True``.

    .. todo:: don't process twice

    Args:
        consent_mode_id: PK of the consent mode
    """
    from crate_anon.crateweb.consent.models import ConsentMode  # delayed import  # noqa
    consent_mode = ConsentMode.objects.get(pk=consent_mode_id)
    consent_mode.process_change()


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def process_patient_response(patient_response_id: int) -> None:
    """
    Celery task to do the thinking associated with a patient's decision.
    For example, might send a letter to a researcher.

    Sets ``processed = True`` and ``processed_at`` for the
    :class:`crate_anon.crateweb.consent.models.PatientResponse`.

    Args:
        patient_response_id: PK of the patient response
    """
    from crate_anon.crateweb.consent.models import PatientResponse  # delayed import  # noqa
    patient_response = PatientResponse.objects.get(pk=patient_response_id)
    patient_response.process_response()


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def test_email_rdbm_task() -> None:
    """
    Celery task to test the e-mail system by e-mailing the Research Database
    Manager.
    """
    subject = "TEST MESSAGE FROM RESEARCH DATABASE COMPUTER"
    text = (
        "Success! The CRATE framework can communicate via Celery with its "
        "message broker, so it can talk to an 'offline' copy of itself "
        "for background processing. And it can e-mail you."
    )
    email_rdbm_task(subject, text)  # Will this work as a function? Yes.


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def email_rdbm_task(subject: str, text: str) -> None:
    """
    Celery task to e-mail the Research Database Manager.

    Creates/saves an
    :class:`crate_anon.crateweb.consent.models.Email` and an
    :class:`crate_anon.crateweb.consent.models.EmailTransmission`.

    Args:
        subject: e-mail subject
        text: e-mail body text
    """
    from crate_anon.crateweb.consent.models import Email  # delayed import
    email = Email.create_rdbm_text_email(subject, text)
    et = email.send()
    if et is None:
        log.error("Failed to send e-mail")
        return
    if et.sent:
        log.info(str(et))
    else:
        log.error(str(et))


# noinspection PyCallingNonCallable
@shared_task(ignore_result=True)
def resubmit_unprocessed_tasks_task() -> None:
    """
    Celery task to finish up any outstanding work.
    Use this with caution.

    The idea is that if a previous Celery task crashed, it will have been
    removed from the Celery queue, but not completed.
    As of 2018-06-29, we make sure that we have completion flags. This task
    then works through anything unprocessed, and tries to process it.

    All work gets added to the Celery queue.
    """
    from crate_anon.crateweb.consent.models import ClinicianResponse  # delayed import  # noqa
    from crate_anon.crateweb.consent.models import ConsentMode  # delayed import  # noqa
    from crate_anon.crateweb.consent.models import ContactRequest  # delayed import  # noqa
    from crate_anon.crateweb.consent.models import PatientResponse  # delayed import  # noqa

    for patient_response in PatientResponse.get_unprocessed():
        process_patient_response.delay(patient_response.id)

    for clinician_response in ClinicianResponse.get_unprocessed():
        finalize_clinician_response.delay(clinician_response.id)

    for consent_mode in ConsentMode.get_unprocessed():
        process_consent_change.delay(consent_mode.id)

    for contact_request in ContactRequest.get_unprocessed():
        process_contact_request.delay(contact_request.id)
