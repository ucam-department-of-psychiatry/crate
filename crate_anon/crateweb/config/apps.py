#!/usr/bin/env python3
# crate_anon/crateweb/config/apps.py

from django.apps import AppConfig


class ConsentAppConfig(AppConfig):
    name = 'crate_anon.crateweb.consent'


class ResearchAppConfig(AppConfig):
    name = 'crate_anon.crateweb.research'


class UserProfileAppConfig(AppConfig):
    name = 'crate_anon.crateweb.userprofile'


class CoreAppConfig(AppConfig):
    name = 'crate_anon.crateweb.core'
