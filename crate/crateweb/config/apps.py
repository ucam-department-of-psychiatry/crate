#!/usr/bin/env python3
# config/apps.py

from django.apps import AppConfig


class ConsentAppConfig(AppConfig):
    name = 'crate.crateweb.consent'


class ResearchAppConfig(AppConfig):
    name = 'crate.crateweb.research'


class UserProfileAppConfig(AppConfig):
    name = 'crate.crateweb.userprofile'


class CoreAppConfig(AppConfig):
    name = 'crate.crateweb.core'
