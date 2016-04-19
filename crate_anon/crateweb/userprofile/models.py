#!/usr/bin/env python3
# userprofile/models.py

from django.conf import settings
from django.db import models
from django.dispatch import receiver
from crate_anon.crateweb.core.constants import (
    LEN_ADDRESS,
    LEN_PHONE,
    LEN_TITLE,
)


# =============================================================================
# User profile information
# =============================================================================
# This is used for:
#   - stuff the user might edit, e.g. per_page
#   - a representation of the user as a researcher (or maybe clinician)

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                primary_key=True,
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

    # -------------------------------------------------------------------------
    # Web site personal settings
    # -------------------------------------------------------------------------
    per_page = models.PositiveSmallIntegerField(
        choices=N_PAGE_CHOICES, default=50,
        verbose_name="Number of items to show per page")
    line_length = models.PositiveSmallIntegerField(
        default=80,
        verbose_name="Characters to word-wrap text at in results "
                     "display (0 for no wrap)")
    collapse_at = models.PositiveSmallIntegerField(
        default=400,
        verbose_name="Number of characters beyond which results field starts "
                     "collapsed (0 for none)")

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
    is_consultant = models.BooleanField(
        default=False,
        verbose_name="User is an NHS consultant")
    signatory_title = models.CharField(
        max_length=255,
        verbose_name='Title for signature (e.g. "Consultant psychiatrist")')

    def get_address_components(self):
        return list(filter(None,
                           [self.address_1, self.address_2, self.address_3,
                            self.address_4, self.address_5, self.address_6,
                            self.address_7]))

    def get_title_forename_surname(self):
        return " ".join(filter(None, [self.title, self.user.first_name,
                                      self.user.last_name]))

    def get_title_surname(self):
        if self.title.lower() == "sir":  # frivolous!
            return " ".join([self.title, self.user.first_name])
        else:
            return " ".join([self.title, self.user.last_name])

    def get_forename_surname(self):
        return " ".join([self.user.first_name, self.user.last_name])


# noinspection PyUnusedLocal
@receiver(models.signals.post_save, sender=settings.AUTH_USER_MODEL)
def user_saved_so_create_profile(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)


# =============================================================================
# Helper functions
# =============================================================================


def get_per_page(request):
    if not request.user.is_authenticated():
        return None
    return request.user.profile.per_page
