#!/usr/bin/env python

"""
crate_anon/crateweb/userprofile/models.py

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

**Extended user profile for Django, with all our user configuration details.**

"""

from typing import Any, List, Optional, Type

from cardinal_pythonlib.django.fields.jsonclassfield import JsonClassField
from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.http.request import HttpRequest

from crate_anon.crateweb.core.constants import (
    LEN_ADDRESS,
    LEN_PHONE,
    LEN_TITLE,
)
from crate_anon.crateweb.extra.salutation import (
    forename_surname,
    salutation,
    title_forename_surname,
)


# =============================================================================
# User profile information
# =============================================================================

class UserProfile(models.Model):
    """
    User profile information.

    This is used for:

    - stuff the user might edit, e.g. per_page
    - a representation of the user as a researcher (or maybe clinician)
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                primary_key=True,
                                on_delete=models.CASCADE,
                                related_name="profile")
    # http://stackoverflow.com/questions/14345303/creating-a-profile-model-with-both-an-inlineadmin-and-a-post-save-signal-in-djan  # noqa

    # first_name: in Django User model
    # last_name: in Django User model
    # email: in Django User model

    N_PAGE_CHOICES = (
        (10, '10'),
        (20, '20'),
        (50, '50'),
        (100, '100'),
        (200, '200'),
        (500, '500'),
        (1000, '1000'),
    )
    N_PATIENT_PAGE_CHOICES = (
        (1, '1'),
        (5, '5'),
        (10, '10'),
        (20, '20'),
        (50, '50'),
        (100, '100'),
    )

    # -------------------------------------------------------------------------
    # Web site personal settings
    # -------------------------------------------------------------------------
    per_page = models.PositiveSmallIntegerField(
        choices=N_PAGE_CHOICES, default=50,
        verbose_name="Number of items to show per page")
    patients_per_page = models.PositiveSmallIntegerField(
        choices=N_PATIENT_PAGE_CHOICES, default=1,
        verbose_name="Number of patients to show per page "
                     "(for Patient Explorer view)")
    line_length = models.PositiveSmallIntegerField(
        default=80,
        verbose_name="Characters to word-wrap text at in results "
                     "display (0 for no wrap)")
    collapse_at_len = models.PositiveSmallIntegerField(
        default=400,
        verbose_name="Number of characters beyond which results field starts "
                     "collapsed (0 for none)")
    collapse_at_n_lines = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="Number of lines beyond which result/query field starts "
                     "collapsed (0 for none)")
    sql_scratchpad = models.TextField(
        verbose_name='SQL scratchpad for query builder')
    patient_multiquery_scratchpad = JsonClassField(
        verbose_name='PatientMultiQuery scratchpad (in JSON) for builder',
        null=True)  # type: 'PatientMultiQuery'

    # -------------------------------------------------------------------------
    # Developer
    # -------------------------------------------------------------------------
    is_developer = models.BooleanField(
        default=False,
        verbose_name="Enable developer functions?")

    # -------------------------------------------------------------------------
    # Contact details
    # -------------------------------------------------------------------------
    title = models.CharField(max_length=LEN_TITLE, blank=True)
    address_1 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 1")
    address_2 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 2")
    address_3 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 3")
    address_4 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 4")
    address_5 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 5 (county)")
    address_6 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 6 (postcode)")
    address_7 = models.CharField(max_length=LEN_ADDRESS, blank=True,
                                 verbose_name="Address line 7 (country)")
    telephone = models.CharField(max_length=LEN_PHONE, blank=True)

    # -------------------------------------------------------------------------
    # Clinician-specific bits
    # -------------------------------------------------------------------------
    is_clinician = models.BooleanField(
        default=False,
        verbose_name="User is a clinician (with implied permission to look "
                     "up RIDs)")
    is_consultant = models.BooleanField(
        default=False,
        verbose_name="User is an NHS consultant "
                     "(relevant for clinical trials)")
    signatory_title = models.CharField(
        max_length=255,
        verbose_name='Title for signature (e.g. "Consultant psychiatrist")')

    # -------------------------------------------------------------------------
    # Functions
    # -------------------------------------------------------------------------
    def get_address_components(self) -> List[str]:
        """
        Returns the user's address lines.
        """
        return list(filter(None,
                           [self.address_1, self.address_2, self.address_3,
                            self.address_4, self.address_5, self.address_6,
                            self.address_7]))

    def get_title_forename_surname(self) -> str:
        """
        Returns the user's name in the form "Dr Joe Bloggs".
        """
        # noinspection PyTypeChecker,PyUnresolvedReferences
        return title_forename_surname(self.title, self.user.first_name,
                                      self.user.last_name)

    def get_salutation(self) -> str:
        """
        Returns a salutation for the user (e.g. "Dr Bloggs").
        """
        # noinspection PyTypeChecker,PyUnresolvedReferences
        return salutation(self.title, self.user.first_name,
                          self.user.last_name, assume_dr=True)

    def get_forename_surname(self) -> str:
        """
        Returns the user's name in the form "Joe Bloggs".
        """
        # noinspection PyUnresolvedReferences
        return forename_surname(self.user.first_name, self.user.last_name)


# noinspection PyUnusedLocal
@receiver(models.signals.post_save, sender=settings.AUTH_USER_MODEL)
def user_saved_so_create_profile(sender: Type[settings.AUTH_USER_MODEL],
                                 instance: settings.AUTH_USER_MODEL,
                                 created: bool,
                                 **kwargs: Any) -> None:
    """
    Django signal receiver.

    Called when a Django User object has been saved. Attaches

    Args:
        sender: the model class (User)
        instance: will be the User object
        created: was a new record created?
        **kwargs: other arguments we don't care about

    See https://docs.djangoproject.com/en/2.1/ref/signals/#post-save.

    """
    UserProfile.objects.get_or_create(user=instance)


# =============================================================================
# Helper functions
# =============================================================================


def get_per_page(request: HttpRequest) -> Optional[int]:
    """
    Returns the number of items per page (a pagination preference) of the
    current user.

    Args:
        request: the :class:`django.http.request.HttpRequest`

    Returns:
        the number of items per page, or ``None`` if the user was not
        authenticated

    """
    if not request.user.is_authenticated:
        return None
    return request.user.profile.per_page


def get_patients_per_page(request: HttpRequest) -> Optional[int]:
    """
    Returns the number of patients per page (a pagination preference, for the
    Patient Explorer view) of the current user.

    Args:
        request: the :class:`django.http.request.HttpRequest`

    Returns:
        the number of patients per page, or ``None`` if the user was not
        authenticated

    """
    if not request.user.is_authenticated:
        return None
    return request.user.profile.patients_per_page
