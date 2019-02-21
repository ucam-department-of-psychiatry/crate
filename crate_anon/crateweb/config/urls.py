#!/usr/bin/env python

"""
crate_anon/crateweb/config/urls.py

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

**crateweb Django URL configuration**

The `urlpatterns` list routes URLs to views. For more information please see:
https://docs.djangoproject.com/en/1.8/topics/http/urls/

Examples:

Function views

    1. Add an import:  ``from my_app import views``
    2. Add a URL to urlpatterns:  ``url(r'^$', views.home, name='home')``

Class-based views

    1. Add an import:  ``from other_app.views import Home``
    2. Add a URL to urlpatterns:  ``url(r'^$', Home.as_view(), name='home')``

Including another URLconf

    1. Add an import:  ``from blog import urls as blog_urls``
    2. Add a URL to urlpatterns:  ``url(r'^blog/', include(blog_urls))``

"""

from django.conf import settings
from django.conf.urls import include, url
# import django.contrib.auth.views
# from django.contrib import admin
# import django.views.defaults
# import admin_honeypot

# noinspection PyPackageRequirements
import debug_toolbar
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
from crate_anon.crateweb.research.research_db_info import research_database_info  # noqa

research_database_info.get_colinfolist()


urlpatterns = [
    # -------------------------------------------------------------------------
    # Login, other authentication/password stuff
    # -------------------------------------------------------------------------
    url(r'^login/', core_auth_views.login_view, name='login'),
    url(r'^logout/', core_auth_views.logout_view, name='logout'),
    url(r'^password_change/', core_auth_views.password_change,
        name='password_change'),

    # -------------------------------------------------------------------------
    # Home, About
    # -------------------------------------------------------------------------
    url(r'^$', core_views.home, name='home'),
    url(r'^about/$', core_views.about, name='about'),

    # -------------------------------------------------------------------------
    # Admin sites
    # -------------------------------------------------------------------------
    # ... obfuscate: p351 of Greenfeld_2015.
    url(r'^mgr_admin/', mgr_admin_site.urls),
    url(r'^dev_admin/', dev_admin_site.urls),
    url(r'^res_admin/', res_admin_site.urls),
    # ... namespace is defined in call to AdminSite(); see core/admin.py

    # -------------------------------------------------------------------------
    # Main query views
    # -------------------------------------------------------------------------
    url(r'^build_query/$', research_views.query_build, name='build_query'),
    url(r'^query/$', research_views.query_edit_select, name='query'),
    url(r'^activate_query/(?P<query_id>[0-9]+)/$',
        research_views.query_activate, name='activate_query'),
    url(r'^delete_query/(?P<query_id>[0-9]+)/$',
        research_views.query_delete, name='delete_query'),
    url(r'^highlight/$',
        research_views.highlight_edit_select, name='highlight'),
    url(r'^activate_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.highlight_activate, name='activate_highlight'),
    url(r'^deactivate_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.highlight_deactivate, name='deactivate_highlight'),
    url(r'^delete_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.highlight_delete, name='delete_highlight'),
    url(r'^count/(?P<query_id>[0-9]+)/$',
        research_views.query_count, name='count'),
    url(r'^results/(?P<query_id>[0-9]+)/$',
        research_views.query_results, name='results'),
    url(r'^results_recordwise/(?P<query_id>[0-9]+)/$',
        research_views.query_results_recordwise, name='results_recordwise'),
    url(r'^tsv/(?P<query_id>[0-9]+)/$', research_views.query_tsv, name='tsv'),
    url(r'^query_excel/(?P<query_id>[0-9]+)/$',
        research_views.query_excel, name='query_excel'),
    url(r'^sitewide_queries/$', research_views.query_add_sitewide,
        name='sitewide_queries'),
    url(r'^delete_sitewide_query/(?P<query_id>[0-9]+)/$',
        research_views.sitewide_query_delete, name='delete_sitewide_query'),
    url(r'^standard_queries/$', research_views.show_sitewide_queries,
        name='standard_queries'),
    url(r'^process_standard_query/(?P<query_id>[0-9]+)/$',
        research_views.sitewide_query_process, name='process_standard_query'),
    url(r'^edit_display/(?P<query_id>[0-9]+)/$',
        research_views.edit_display, name='edit_display'),
    url(r'^save_display/(?P<query_id>[0-9]+)/$',
        research_views.save_display, name='save_display'),

    # -------------------------------------------------------------------------
    # Patient Explorer views
    # -------------------------------------------------------------------------
    url(r'^pe_build/$', research_views.pe_build,
        name='pe_build'),
    url(r'^pe_choose/$', research_views.pe_choose,
        name='pe_choose'),
    url(r'^pe_activate/(?P<pe_id>[0-9]+)/$',
        research_views.pe_activate, name='pe_activate'),
    url(r'^pe_edit/(?P<pe_id>[0-9]+)/$',
        research_views.pe_edit, name='pe_edit'),
    url(r'^pe_delete/(?P<pe_id>[0-9]+)/$',
        research_views.pe_delete, name='pe_delete'),
    url(r'^pe_results/(?P<pe_id>[0-9]+)/$',
        research_views.pe_results, name='pe_results'),
    # url(r'^pe_tsv_zip/(?P<pe_id>[0-9]+)/$',
    #     research_views.patient_explorer_tsv_zip, name='pe_tsv_zip'),
    url(r'^pe_excel/(?P<pe_id>[0-9]+)/$',
        research_views.pe_excel, name='pe_excel'),
    url(r'^pe_df_results/(?P<pe_id>[0-9]+)/$',
        research_views.pe_data_finder_results, name='pe_df_results'),
    url(r'^pe_df_excel/(?P<pe_id>[0-9]+)/$',
        research_views.pe_data_finder_excel, name='pe_df_excel'),
    url(r'^pe_monster_results/(?P<pe_id>[0-9]+)/$',
        research_views.pe_monster_results, name='pe_monster_results'),
    # We don't offer the monster view in Excel; it'd be huge.
    url(r'^pe_table_browser/(?P<pe_id>[0-9]+)/$',
        research_views.pe_table_browser, name='pe_table_browser'),
    url(r'^pe_one_table/(?P<pe_id>[0-9]+)/(?P<db>.*)/(?P<schema>.+)/(?P<table>.+)/$',  # noqa
        research_views.pe_one_table, name='pe_one_table'),
    url(r'^pe_one_table/(?P<pe_id>[0-9]+)/(?P<schema>.+)/(?P<table>.+)/$',  # noqa
        research_views.pe_one_table, name='pe_one_table'),

    # -------------------------------------------------------------------------
    # Research database structure
    # -------------------------------------------------------------------------
    url(r'^structure_table_long/$', research_views.structure_table_long,
        name='structure_table_long'),
    url(r'^structure_table_paginated/$',
        research_views.structure_table_paginated,
        name='structure_table_paginated'),
    url(r'^structure_tree/$', research_views.structure_tree,
        name='structure_tree'),
    url(r'^structure_tsv/$', research_views.structure_tsv,
        name='structure_tsv'),
    url(r'^structure_excel/$', research_views.structure_excel,
        name='structure_excel'),
    url(r'^structure_help/$', research_views.local_structure_help,
        name='structure_help'),

    # -------------------------------------------------------------------------
    # SQL helpers
    # -------------------------------------------------------------------------
    url(r'^sqlhelper_text_anywhere/$', research_views.sqlhelper_text_anywhere,
        name='sqlhelper_text_anywhere'),
    url(r'^sqlhelper_text_anywhere_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.sqlhelper_text_anywhere_with_db,
        name='sqlhelper_text_anywhere_with_db'),
    url(r'^sqlhelper_drug_type/$', research_views.sqlhelper_drug_type,
        name='sqlhelper_drug_type'),
    url(r'^sqlhelper_drug_type_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.sqlhelper_drug_type_with_db,
        name='sqlhelper_drug_type_with_db'),

    # -------------------------------------------------------------------------
    # Researcher consent functions
    # -------------------------------------------------------------------------
    url(r'^submit_contact_request/$', consent_views.submit_contact_request,
        name='submit_contact_request'),

    # -------------------------------------------------------------------------
    # Clinician views
    # -------------------------------------------------------------------------
    url(r'^all_text_from_pid/$', research_views.all_text_from_pid,
        name='all_text_from_pid'),
    url(r'^all_text_from_pid_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.all_text_from_pid_with_db,
        name='all_text_from_pid_with_db'),
    url(r'^clinician_contact_request/$',
        consent_views.clinician_initiated_contact_request,
        name='clinician_contact_request'),

    # -------------------------------------------------------------------------
    # Look up PID/RID
    # -------------------------------------------------------------------------
    url(r'^pidlookup/$', research_views.pidlookup, name='pidlookup'),
    url(r'^pidlookup_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.pidlookup_with_db,
        name='pidlookup_with_db'),
    url(r'^ridlookup/$', research_views.ridlookup, name='ridlookup'),
    url(r'^ridlookup_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.ridlookup_with_db,
        name='ridlookup_with_db'),

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
    url(r'^study_details/(?P<study_id>-?[0-9]+)/$', consent_views.study_details,
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
    url(r'^clinician_pack/(?P<clinician_response_id>-?[0-9]+)/(?P<token>[a-zA-Z0-9]+)/$',  # noqa
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
    url(r'^generate_random_nhs/$', consent_views.generate_random_nhs,
        name='generate_random_nhs'),
    url(r'^test_patient_lookup/$', consent_views.test_patient_lookup,
        name='test_patient_lookup'),
    url(r'^test_consent_lookup/$', consent_views.test_consent_lookup,
        name='test_consent_lookup'),

    url(r'^draft_clinician_email/(?P<contact_request_id>-?[0-9]+)/$',
        consent_views.draft_clinician_email,
        name='draft_clinician_email'),
    url(r'^draft_approval_email/(?P<contact_request_id>-?[0-9]+)/$',
        consent_views.draft_approval_email,
        name='draft_approval_email'),
    url(r'^draft_withdrawal_email/(?P<contact_request_id>-?[0-9]+)/$',
        consent_views.draft_withdrawal_email,
        name='draft_withdrawal_email'),

    url(r'^draft_approval_letter/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_approval_letter,
        name='draft_approval_letter'),
    url(r'^draft_withdrawal_letter/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_withdrawal_letter,
        name='draft_withdrawal_letter'),
    url(r'^draft_first_traffic_light_letter/(?P<patient_lookup_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_first_traffic_light_letter,
        name='draft_first_traffic_light_letter'),
    url(r'^draft_letter_clinician_to_pt_re_study/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_letter_clinician_to_pt_re_study,
        name='draft_letter_clinician_to_pt_re_study'),
    url(r'^decision_form_to_pt_re_study/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.decision_form_to_pt_re_study,
        name='decision_form_to_pt_re_study'),
    url(r'^draft_confirm_traffic_light_letter/(?P<consent_mode_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_confirm_traffic_light_letter,
        name='draft_confirm_traffic_light_letter'),
    url(r'^draft_traffic_light_decision_form/(?P<patient_lookup_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_traffic_light_decision_form,
        name='draft_traffic_light_decision_form'),

    # -------------------------------------------------------------------------
    # Other test views
    # -------------------------------------------------------------------------
    # url(r'^404/$', django.views.defaults.page_not_found, ),

]

# urlpatterns += patterns('', url(r'^silk/',
#                                 include('silk.urls', namespace='silk')))


if settings.DEBUG:
    # https://github.com/jazzband/django-debug-toolbar/issues/529
    # http://stackoverflow.com/questions/32111203/what-is-the-benefit-of-using-django-conf-urls-patterns-versus-a-list-of-url-in-d  # noqa
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
