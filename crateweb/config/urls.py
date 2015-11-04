#!/usr/bin/env python3
# config/urls.py

"""crateweb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
# import django.contrib.auth.views
# from django.contrib import admin
# import django.views.defaults
# import admin_honeypot
from core.admin import admin_site, dev_admin_site, res_admin_site
import core.auth_views
import core.views
import consent.views
import research.views
import userprofile.views

urlpatterns = [
    # -------------------------------------------------------------------------
    # Login, other authentication/password stuff
    # -------------------------------------------------------------------------
    url(r'^login/', core.auth_views.login_view, name='login'),
    url(r'^logout/', core.auth_views.logout_view, name='logout'),
    url(r'^password_change/', core.auth_views.password_change,
        name='password_change'),

    # -------------------------------------------------------------------------
    # Home
    # -------------------------------------------------------------------------
    url(r'^$', core.views.home, name='home'),

    # -------------------------------------------------------------------------
    # Admin site
    # -------------------------------------------------------------------------
    # ... obfuscate: p351 of Greenfeld_2015.
    url(r'^risotto_admin/', include(admin_site.urls)),
    url(r'^pastapesto_admin/', include(dev_admin_site.urls)),
    url(r'^resadmin/', include(res_admin_site.urls)),
    # ... namespace is defined in call to AdminSite(); see core/admin.py

    # -------------------------------------------------------------------------
    # Main query views
    # -------------------------------------------------------------------------
    url(r'^query/$', research.views.query, name='query'),
    url(r'^activate_query/(?P<query_id>[0-9]+)/$',
        research.views.activate_query, name='activate_query'),
    url(r'^delete_query/(?P<query_id>[0-9]+)/$',
        research.views.delete_query, name='delete_query'),
    url(r'^highlight/$',
        research.views.highlight, name='highlight'),
    url(r'^activate_highlight/(?P<highlight_id>[0-9]+)/$',
        research.views.activate_highlight, name='activate_highlight'),
    url(r'^deactivate_highlight/(?P<highlight_id>[0-9]+)/$',
        research.views.deactivate_highlight, name='deactivate_highlight'),
    url(r'^delete_highlight/(?P<highlight_id>[0-9]+)/$',
        research.views.delete_highlight, name='delete_highlight'),
    url(r'^count/(?P<query_id>[0-9]+)/$',
        research.views.count, name='count'),
    url(r'^results/(?P<query_id>[0-9]+)/$',
        research.views.results, name='results'),
    url(r'^tsv/$', research.views.tsv, name='tsv'),

    # -------------------------------------------------------------------------
    # Research database structure
    # -------------------------------------------------------------------------
    url(r'^structure_table_long/$', research.views.structure_table_long,
        name='structure_table_long'),
    url(r'^structure_table_paginated/$',
        research.views.structure_table_paginated,
        name='structure_table_paginated'),
    url(r'^structure_tsv/$', research.views.structure_tsv,
        name='structure_tsv'),

    # -------------------------------------------------------------------------
    # Researcher consent functions
    # -------------------------------------------------------------------------
    url(r'submit_contact_request/$', consent.views.submit_contact_request,
        name='submit_contact_request'),

    # -------------------------------------------------------------------------
    # Look up PID
    # -------------------------------------------------------------------------
    url(r'^pidlookup/$', research.views.pidlookup, name='pidlookup'),

    # -------------------------------------------------------------------------
    # User profile
    # -------------------------------------------------------------------------
    url(r'^edit_profile/$', userprofile.views.edit_profile,
        name='edit_profile'),

    # -------------------------------------------------------------------------
    # Private file storage - superuser access
    # -------------------------------------------------------------------------
    url(r'^privatestorage/(?P<filename>.+)$',
        consent.views.download_privatestorage),

    # -------------------------------------------------------------------------
    # Public views
    # -------------------------------------------------------------------------
    url(r'^study_details/(?P<study_id>[0-9]+)/$', consent.views.study_details,
        name='study_details'),
    url(r'^study_form/(?P<study_id>[0-9]+)/$', consent.views.study_form,
        name='study_form'),
    url(r'^study_pack/(?P<study_id>[0-9]+)/$', consent.views.study_pack,
        name='study_pack'),
    url(r'^leaflet/(?P<leaflet_name>[a-zA-Z0-9_]+)/$', consent.views.leaflet,
        name='leaflet'),

    # -------------------------------------------------------------------------
    # Developer functions
    # -------------------------------------------------------------------------
    url(r'^generate_fake_nhs$', consent.views.generate_fake_nhs,
        name='generate_fake_nhs'),
    url(r'view_email_html/(?P<email_id>[0-9]+)/$',
        consent.views.view_email_html, name='view_email_html'),
    url(r'view_email_attachment/(?P<attachment_id>[0-9]+)/$',
        consent.views.view_email_attachment, name='view_email_attachment'),
    url(r'test_patient_lookup/$', consent.views.test_patient_lookup,
        name='test_patient_lookup'),

    # -------------------------------------------------------------------------
    # Other test views
    # -------------------------------------------------------------------------
    # url(r'^404/$', django.views.defaults.page_not_found, ),
]
