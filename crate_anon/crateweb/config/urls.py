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
from crate_anon.crateweb.config.constants import (
    DOWNLOAD_PRIVATESTORAGE_URL_STEM,
    UrlNames,
)
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
    url(r'^login/', core_auth_views.login_view, name=UrlNames.LOGIN),
    url(r'^logout/', core_auth_views.logout_view, name=UrlNames.LOGOUT),
    url(r'^password_change/', core_auth_views.password_change,
        name=UrlNames.PASSWORD_CHANGE),

    # -------------------------------------------------------------------------
    # Home, About
    # -------------------------------------------------------------------------
    url(r'^$', core_views.home, name=UrlNames.HOME),
    url(r'^about/$', core_views.about, name=UrlNames.ABOUT),

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
    url(r'^build_query/$',
        research_views.query_build, name=UrlNames.BUILD_QUERY),
    url(r'^query/$',
        research_views.query_edit_select, name=UrlNames.QUERY),
    url(r'^activate_query/(?P<query_id>[0-9]+)/$',
        research_views.query_activate, name=UrlNames.ACTIVATE_QUERY),
    url(r'^delete_query/(?P<query_id>[0-9]+)/$',
        research_views.query_delete, name=UrlNames.DELETE_QUERY),
    url(r'^highlight/$',
        research_views.highlight_edit_select, name=UrlNames.HIGHLIGHT),
    url(r'^activate_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.highlight_activate, name=UrlNames.ACTIVATE_HIGHLIGHT),
    url(r'^deactivate_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.highlight_deactivate, name=UrlNames.DEACTIVATE_HIGHLIGHT),  # noqa
    url(r'^delete_highlight/(?P<highlight_id>[0-9]+)/$',
        research_views.highlight_delete, name=UrlNames.DELETE_HIGHLIGHT),
    url(r'^count/(?P<query_id>[0-9]+)/$',
        research_views.query_count, name=UrlNames.COUNT),
    url(r'^results/(?P<query_id>[0-9]+)/$',
        research_views.query_results, name=UrlNames.RESULTS),
    url(r'^results_recordwise/(?P<query_id>[0-9]+)/$',
        research_views.query_results_recordwise,
        name=UrlNames.RESULTS_RECORDWISE),
    url(r'^tsv/(?P<query_id>[0-9]+)/$',
        research_views.query_tsv, name=UrlNames.TSV),
    url(r'^query_excel/(?P<query_id>[0-9]+)/$',
        research_views.query_excel, name=UrlNames.QUERY_EXCEL),
    url(r'^sitewide_queries/$',
        research_views.query_add_sitewide, name=UrlNames.SITEWIDE_QUERIES),
    url(r'^delete_sitewide_query/(?P<query_id>[0-9]+)/$',
        research_views.sitewide_query_delete,
        name=UrlNames.DELETE_SITEWIDE_QUERY),
    url(r'^standard_queries/$',
        research_views.show_sitewide_queries, name=UrlNames.STANDARD_QUERIES),
    url(r'^process_standard_query/(?P<query_id>[0-9]+)/$',
        research_views.sitewide_query_process,
        name=UrlNames.PROCESS_STANDARD_QUERY),
    url(r'^edit_display/(?P<query_id>[0-9]+)/$',
        research_views.edit_display, name=UrlNames.EDIT_DISPLAY),
    url(r'^save_display/(?P<query_id>[0-9]+)/$',
        research_views.save_display, name=UrlNames.SAVE_DISPLAY),
    url(r'^show_query/(?P<query_id>[0-9]+)/$',
        research_views.show_query, name=UrlNames.SHOW_QUERY),
    url(r'^source_information/(?P<srcdb>.+)/(?P<srctable>.+)/(?P<srcfield>.+)/(?P<srcpkfield>.+)/(?P<srcpkval>.+)/(?P<srcpkstr>.+)/$',  # noqa
        research_views.source_info, name=UrlNames.SRCINFO),

    # -------------------------------------------------------------------------
    # Patient Explorer views
    # -------------------------------------------------------------------------
    url(r'^pe_build/$',
        research_views.pe_build, name=UrlNames.PE_BUILD),
    url(r'^pe_choose/$',
        research_views.pe_choose, name=UrlNames.PE_CHOOSE),
    url(r'^pe_activate/(?P<pe_id>[0-9]+)/$',
        research_views.pe_activate, name=UrlNames.PE_ACTIVATE),
    url(r'^pe_edit/(?P<pe_id>[0-9]+)/$',
        research_views.pe_edit, name=UrlNames.PE_EDIT),
    url(r'^pe_delete/(?P<pe_id>[0-9]+)/$',
        research_views.pe_delete, name=UrlNames.PE_DELETE),
    url(r'^pe_results/(?P<pe_id>[0-9]+)/$',
        research_views.pe_results, name=UrlNames.PE_RESULTS),
    # url(r'^pe_tsv_zip/(?P<pe_id>[0-9]+)/$',
    #     research_views.patient_explorer_tsv_zip, name='pe_tsv_zip'),
    url(r'^pe_excel/(?P<pe_id>[0-9]+)/$',
        research_views.pe_excel, name=UrlNames.PE_EXCEL),
    url(r'^pe_df_results/(?P<pe_id>[0-9]+)/$',
        research_views.pe_data_finder_results, name=UrlNames.PE_DF_RESULTS),
    url(r'^pe_df_excel/(?P<pe_id>[0-9]+)/$',
        research_views.pe_data_finder_excel, name=UrlNames.PE_DF_EXCEL),
    url(r'^pe_monster_results/(?P<pe_id>[0-9]+)/$',
        research_views.pe_monster_results, name=UrlNames.PE_MONSTER_RESULTS),
    # We don't offer the monster view in Excel; it'd be huge.
    url(r'^pe_table_browser/(?P<pe_id>[0-9]+)/$',
        research_views.pe_table_browser, name=UrlNames.PE_TABLE_BROWSER),
    url(r'^pe_one_table/(?P<pe_id>[0-9]+)/(?P<db>.*)/(?P<schema>.+)/(?P<table>.+)/$',  # noqa
        research_views.pe_one_table, name=UrlNames.PE_ONE_TABLE),
    url(r'^pe_one_table/(?P<pe_id>[0-9]+)/(?P<schema>.+)/(?P<table>.+)/$',
        research_views.pe_one_table, name=UrlNames.PE_ONE_TABLE),

    # -------------------------------------------------------------------------
    # Research database structure
    # -------------------------------------------------------------------------
    url(r'^structure_table_long/$',
        research_views.structure_table_long,
        name=UrlNames.STRUCTURE_TABLE_LONG),
    url(r'^structure_table_paginated/$',
        research_views.structure_table_paginated,
        name=UrlNames.STRUCTURE_TABLE_PAGINATED),
    url(r'^structure_tree/$',
        research_views.structure_tree, name=UrlNames.STRUCTURE_TREE),
    url(r'^structure_tsv/$',
        research_views.structure_tsv, name=UrlNames.STRUCTURE_TSV),
    url(r'^structure_excel/$',
        research_views.structure_excel, name=UrlNames.STRUCTURE_EXCEL),
    url(r'^structure_help/$',
        research_views.local_structure_help, name=UrlNames.STRUCTURE_HELP),

    # -------------------------------------------------------------------------
    # SQL helpers
    # -------------------------------------------------------------------------
    url(r'^sqlhelper_text_anywhere/$',
        research_views.sqlhelper_text_anywhere,
        name=UrlNames.SQLHELPER_TEXT_ANYWHERE),
    url(r'^sqlhelper_text_anywhere_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.sqlhelper_text_anywhere_with_db,
        name=UrlNames.SQLHELPER_TEXT_ANYWHERE_WITH_DB),
    url(r'^sqlhelper_drug_type/$',
        research_views.sqlhelper_drug_type, name=UrlNames.SQLHELPER_DRUG_TYPE),
    url(r'^sqlhelper_drug_type_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.sqlhelper_drug_type_with_db,
        name=UrlNames.SQLHELPER_DRUG_TYPE_WITH_DB),

    # -------------------------------------------------------------------------
    # Researcher consent functions
    # -------------------------------------------------------------------------
    url(r'^submit_contact_request/$',
        consent_views.submit_contact_request,
        name=UrlNames.SUBMIT_CONTACT_REQUEST),

    # -------------------------------------------------------------------------
    # Clinician views
    # -------------------------------------------------------------------------
    url(r'^all_text_from_pid/$',
        research_views.all_text_from_pid, name=UrlNames.ALL_TEXT_FROM_PID),
    url(r'^all_text_from_pid_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.all_text_from_pid_with_db,
        name=UrlNames.ALL_TEXT_FROM_PID_WITH_DB),
    url(r'^clinician_contact_request/$',
        consent_views.clinician_initiated_contact_request,
        name=UrlNames.CLINICIAN_CONTACT_REQUEST),

    # -------------------------------------------------------------------------
    # Archive views
    # -------------------------------------------------------------------------
    url(r'^launch_archive/$',
        research_views.launch_archive, name=UrlNames.LAUNCH_ARCHIVE),
    url(r'^archive/$',
        research_views.archive_template, name=UrlNames.ARCHIVE_TEMPLATE),
    url(r'^archive_attachment/$',
        research_views.archive_attachment, name=UrlNames.ARCHIVE_ATTACHMENT),
    url(r'^archive_static/$',
        research_views.archive_static, name=UrlNames.ARCHIVE_STATIC),

    # -------------------------------------------------------------------------
    # Look up PID/RID
    # -------------------------------------------------------------------------
    url(r'^pidlookup/$', research_views.pidlookup, name=UrlNames.PIDLOOKUP),
    url(r'^pidlookup_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.pidlookup_with_db, name=UrlNames.PIDLOOKUP_WITH_DB),
    url(r'^ridlookup/$', research_views.ridlookup, name=UrlNames.RIDLOOKUP),
    url(r'^ridlookup_with_db/(?P<dbname>[a-zA-Z0-9_]+)/$',
        research_views.ridlookup_with_db, name=UrlNames.RIDLOOKUP_WITH_DB),

    # -------------------------------------------------------------------------
    # User profile
    # -------------------------------------------------------------------------
    url(r'^edit_profile/$',
        userprofile_views.edit_profile, name=UrlNames.EDIT_PROFILE),

    # -------------------------------------------------------------------------
    # Superuser access only
    # -------------------------------------------------------------------------
    url(fr'^{DOWNLOAD_PRIVATESTORAGE_URL_STEM}/(?P<filename>.+)$',
        consent_views.download_privatestorage,
        name=UrlNames.DOWNLOAD_PRIVATESTORAGE),
        # ... NB hard-coded reference to this in consent/storage.py;
        # can't use reverse
    url(r'^charity_report/$',
        consent_views.charity_report, name=UrlNames.CHARITY_REPORT),
    url(r'^exclusion_report/$',
        consent_views.exclusion_report, name=UrlNames.EXCLUSION_REPORT),
    url(r'^test_email_rdbm/$',
        consent_views.test_email_rdbm, name=UrlNames.TEST_EMAIL_RDBM),

    # -------------------------------------------------------------------------
    # Public views
    # -------------------------------------------------------------------------
    url(r'^study_details/(?P<study_id>-?[0-9]+)/$',
        consent_views.study_details, name=UrlNames.STUDY_DETAILS),
    url(r'^study_form/(?P<study_id>[0-9]+)/$',
        consent_views.study_form, name=UrlNames.STUDY_FORM),
    url(r'^study_pack/(?P<study_id>[0-9]+)/$',
        consent_views.study_pack, name=UrlNames.STUDY_PACK),
    url(r'^leaflet/(?P<leaflet_name>[a-zA-Z0-9_]+)/$',
        consent_views.view_leaflet, name=UrlNames.LEAFLET),

    # -------------------------------------------------------------------------
    # Restricted C4C views (token-based); clinicians
    # -------------------------------------------------------------------------
    url(r'^clinician_response/(?P<clinician_response_id>-?[0-9]+)/$',
        consent_views.clinician_response_view,
        name=UrlNames.CLINICIAN_RESPONSE),
        # note the -? : allows viewing (and URL-reversing within) an e-mail
        # having a dummy ID of -1.
    url(r'^clinician_pack/(?P<clinician_response_id>-?[0-9]+)/(?P<token>[a-zA-Z0-9]+)/$',  # noqa
        consent_views.clinician_pack, name=UrlNames.CLINICIAN_PACK),

    # -------------------------------------------------------------------------
    # Restricted views; superuser + researchers
    # -------------------------------------------------------------------------
    url(r'^view_email_html/(?P<email_id>[0-9]+)/$',
        consent_views.view_email_html, name=UrlNames.VIEW_EMAIL_HTML),
    url(r'^view_email_attachment/(?P<attachment_id>[0-9]+)/$',
        consent_views.view_email_attachment,
        name=UrlNames.VIEW_EMAIL_ATTACHMENT),
    url(r'^letter/(?P<letter_id>[0-9]+)/$',
        consent_views.view_letter, name=UrlNames.LETTER),

    # -------------------------------------------------------------------------
    # Developer functions and test views
    # -------------------------------------------------------------------------
    url(r'^generate_random_nhs/$',
        consent_views.generate_random_nhs, name=UrlNames.GENERATE_RANDOM_NHS),
    url(r'^test_patient_lookup/$',
        consent_views.test_patient_lookup, name=UrlNames.TEST_PATIENT_LOOKUP),
    url(r'^test_consent_lookup/$',
        consent_views.test_consent_lookup, name=UrlNames.TEST_CONSENT_LOOKUP),

    url(r'^draft_clinician_email/(?P<contact_request_id>-?[0-9]+)/$',
        consent_views.draft_clinician_email,
        name=UrlNames.DRAFT_CLINICIAN_EMAIL),
    url(r'^draft_approval_email/(?P<contact_request_id>-?[0-9]+)/$',
        consent_views.draft_approval_email,
        name=UrlNames.DRAFT_APPROVAL_EMAIL),
    url(r'^draft_withdrawal_email/(?P<contact_request_id>-?[0-9]+)/$',
        consent_views.draft_withdrawal_email,
        name=UrlNames.DRAFT_WITHDRAWAL_EMAIL),

    url(r'^draft_approval_letter/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_approval_letter,
        name=UrlNames.DRAFT_APPROVAL_LETTER),
    url(r'^draft_withdrawal_letter/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_withdrawal_letter,
        name=UrlNames.DRAFT_WITHDRAWAL_LETTER),
    url(r'^draft_first_traffic_light_letter/(?P<patient_lookup_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_first_traffic_light_letter,
            name=UrlNames.DRAFT_FIRST_TRAFFIC_LIGHT_LETTER),
    url(r'^draft_letter_clinician_to_pt_re_study/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_letter_clinician_to_pt_re_study,
        name=UrlNames.DRAFT_LETTER_CLINICIAN_TO_PT_RE_STUDY),
    url(r'^decision_form_to_pt_re_study/(?P<contact_request_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.decision_form_to_pt_re_study,
        name=UrlNames.DECISION_FORM_TO_PT_RE_STUDY),
    url(r'^draft_confirm_traffic_light_letter/(?P<consent_mode_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_confirm_traffic_light_letter,
        name=UrlNames.DRAFT_CONFIRM_TRAFFIC_LIGHT_LETTER),
    url(r'^draft_traffic_light_decision_form/(?P<patient_lookup_id>-?[0-9]+)/(?P<viewtype>pdf|html)/$',  # noqa
        consent_views.draft_traffic_light_decision_form,
        name=UrlNames.DRAFT_TRAFFIC_LIGHT_DECISION_FORM),

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
