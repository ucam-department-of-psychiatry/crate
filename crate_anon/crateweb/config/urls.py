#!/usr/bin/env python3
# crate_anon/crateweb/config/urls.py

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
from crate_anon.crateweb.core.admin import (
    mgr_admin_site,
    dev_admin_site,
    res_admin_site,
)
import crate_anon.crateweb.core.auth_views as core_auth_views
import crate_anon.crateweb.core.views as core_views
import crate_anon.crateweb.consent.views as consent_views
import crate_anon.crateweb.research.views as research_views
import crate_anon.crateweb.userprofile.views as userprofile_views

# This is the place for one-time startup code.
# http://stackoverflow.com/questions/6791911/execute-code-when-django-starts-once-only  # noqa
# So we cache things here that we don't want the user to have to wait for:
from crate_anon.crateweb.research.models import research_database_info

research_database_info.get_infodictlist()


urlpatterns = [
    # -------------------------------------------------------------------------
    # Login, other authentication/password stuff
    # -------------------------------------------------------------------------
    url(r'^login/', core_auth_views.login_view, name='login'),
    url(r'^logout/', core_auth_views.logout_view, name='logout'),
    url(r'^password_change/', core_auth_views.password_change,
        name='password_change'),

    # -------------------------------------------------------------------------
    # Home
    # -------------------------------------------------------------------------
    url(r'^$', core_views.home, name='home'),

    # -------------------------------------------------------------------------
    # Admin sites
    # -------------------------------------------------------------------------
    # ... obfuscate: p351 of Greenfeld_2015.
    url(r'^mgr_admin/', include(mgr_admin_site.urls)),
    url(r'^dev_admin/', include(dev_admin_site.urls)),
    url(r'^res_admin/', include(res_admin_site.urls)),
    # ... namespace is defined in call to AdminSite(); see core/admin.py

    # -------------------------------------------------------------------------
    # Main query views
    # -------------------------------------------------------------------------
    url(r'^query/$', research_views.edit_select_query, name='query'),
    url(r'^activate_query/(?P<query_id>[0-9]+)/$',
        research_views.activate_query, name='activate_query'),
    url(r'^delete_query/(?P<query_id>[0-9]+)/$',
        research_views.delete_query, name='delete_query'),
    url(r'^highlight/$',
        research_views.edit_select_highlight, name='highlight'),
    url(r'^activate_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.activate_highlight, name='activate_highlight'),
    url(r'^deactivate_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.deactivate_highlight, name='deactivate_highlight'),
    url(r'^delete_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.delete_highlight, name='delete_highlight'),
    url(r'^count/(?P<query_id>[0-9]+)/$',
        research_views.count, name='count'),
    url(r'^results/(?P<query_id>[0-9]+)/$',
        research_views.results, name='results'),
    url(r'^tsv/$', research_views.tsv, name='tsv'),

    # -------------------------------------------------------------------------
    # Research database structure
    # -------------------------------------------------------------------------
    url(r'^structure_table_long/$', research_views.structure_table_long,
        name='structure_table_long'),
    url(r'^structure_table_paginated/$',
        research_views.structure_table_paginated,
        name='structure_table_paginated'),
    url(r'^structure_tsv/$', research_views.structure_tsv,
        name='structure_tsv'),

    # -------------------------------------------------------------------------
    # SQL helpers
    # -------------------------------------------------------------------------
    url(r'^sqlhelper_text_anywhere/$', research_views.sqlhelper_text_anywhere,
        name='sqlhelper_text_anywhere'),

    # -------------------------------------------------------------------------
    # Researcher consent functions
    # -------------------------------------------------------------------------
    url(r'^submit_contact_request/$', consent_views.submit_contact_request,
        name='submit_contact_request'),

    # -------------------------------------------------------------------------
    # Look up PID
    # -------------------------------------------------------------------------
    url(r'^pidlookup/$', research_views.pidlookup, name='pidlookup'),

    # -------------------------------------------------------------------------
    # User profile
    # -------------------------------------------------------------------------
    url(r'^edit_profile/$', userprofile_views.edit_profile,
        name='edit_profile'),

    # -------------------------------------------------------------------------
    # Superuser access only
    # -------------------------------------------------------------------------
    url(r'^download_privatestorage/(?P<filename>.+)$',
        consent_views.download_privatestorage,
        name="download_privatestorage"),
        # ... NB hard-coded reference to this in consent/storage.py;
        # can't use reverse
    url(r'^charity_report/$',
        consent_views.charity_report, name="charity_report"),
    url(r'^exclusion_report/$',
        consent_views.exclusion_report, name="exclusion_report"),
    url(r'^test_email_rdbm/$',
        consent_views.test_email_rdbm, name="test_email_rdbm"),

    # -------------------------------------------------------------------------
    # Public views
    # -------------------------------------------------------------------------
    url(r'^study_details/(?P<study_id>[0-9]+)/$', consent_views.study_details,
        name='study_details'),
    url(r'^study_form/(?P<study_id>[0-9]+)/$', consent_views.study_form,
        name='study_form'),
    url(r'^study_pack/(?P<study_id>[0-9]+)/$', consent_views.study_pack,
        name='study_pack'),
    url(r'^leaflet/(?P<leaflet_name>[a-zA-Z0-9_]+)/$',
        consent_views.view_leaflet, name='leaflet'),

    # -------------------------------------------------------------------------
    # Restricted views (token-based); clinicians
    # -------------------------------------------------------------------------
    url(r'^clinician_response/(?P<clinician_response_id>-?[0-9]+)/$',
        consent_views.clinician_response_view, name='clinician_response'),
        # note the -? : allows viewing (and URL-reversing within) an e-mail
        # having a dummy ID of -1.
    url(r'^clinician_pack/(?P<clinician_response_id>[0-9]+)/(?P<token>[a-zA-Z0-9]+)/$',  # noqa
        consent_views.clinician_pack, name='clinician_pack'),

    # -------------------------------------------------------------------------
    # Restricted views; superuser + researchers
    # -------------------------------------------------------------------------
    url(r'^view_email_html/(?P<email_id>[0-9]+)/$',
        consent_views.view_email_html, name='view_email_html'),
    url(r'^view_email_attachment/(?P<attachment_id>[0-9]+)/$',
        consent_views.view_email_attachment, name='view_email_attachment'),
    url(r'^letter/(?P<letter_id>[0-9]+)/$',
        consent_views.view_letter, name='letter'),

    # -------------------------------------------------------------------------
    # Developer functions and test views
    # -------------------------------------------------------------------------
    url(r'^generate_fake_nhs/$', consent_views.generate_fake_nhs,
        name='generate_fake_nhs'),
    url(r'^test_patient_lookup/$', consent_views.test_patient_lookup,
        name='test_patient_lookup'),

    url(r'^draft_clinician_email/(?P<contact_request_id>[0-9]+)/$',
        consent_views.draft_clinician_email,
        name='draft_clinician_email'),
    url(r'^draft_approval_email/(?P<contact_request_id>[0-9]+)/$',
        consent_views.draft_approval_email,
        name='draft_approval_email'),
    url(r'^draft_withdrawal_email/(?P<contact_request_id>[0-9]+)/$',
        consent_views.draft_withdrawal_email,
        name='draft_withdrawal_email'),

    url(r'^draft_approval_letter/(?P<contact_request_id>[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_approval_letter,
        name='draft_approval_letter'),
    url(r'^draft_withdrawal_letter/(?P<contact_request_id>[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_withdrawal_letter,
        name='draft_withdrawal_letter'),
    url(r'^draft_first_traffic_light_letter/(?P<patient_lookup_id>[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_first_traffic_light_letter,
        name='draft_first_traffic_light_letter'),
    url(r'^draft_letter_clinician_to_pt_re_study/(?P<contact_request_id>[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_letter_clinician_to_pt_re_study,
        name='draft_letter_clinician_to_pt_re_study'),
    url(r'^decision_form_to_pt_re_study/(?P<contact_request_id>[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.decision_form_to_pt_re_study,
        name='decision_form_to_pt_re_study'),
    url(r'^draft_confirm_traffic_light_letter/(?P<consent_mode_id>[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_confirm_traffic_light_letter,
        name='draft_confirm_traffic_light_letter'),

    # -------------------------------------------------------------------------
    # Other test views
    # -------------------------------------------------------------------------
    # url(r'^404/$', django.views.defaults.page_not_found, ),
]
