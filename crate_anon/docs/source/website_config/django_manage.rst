.. crate_anon/docs/source/website_config/django_manage.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.


.. _Django: https://www.djangoproject.com/

Manage the CRATE web server
===========================

.. _crate_django_manage:

The CRATE web front end uses Django_, which comes with a number of built-in
management comments; to these, CRATE adds some more. All are available as
subcommands of

.. code-block:: bash

    crate_django_manage

As of 2018-06-29, the available commands are:

.. code-block:: none

    Type 'crate_django_manage help <subcommand>' for help on a specific subcommand.

    Available subcommands:

    [auth]
        changepassword
        createsuperuser

    [consent]
        fetch_optouts
        lookup_consent
        lookup_patient
        populate
        resubmit_unprocessed_tasks
        test_email

    [contenttypes]
        remove_stale_contenttypes

    [core]
        runcpserver

    [debug_toolbar]
        debugsqlshell

    [django]
        check
        compilemessages
        createcachetable
        dbshell
        diffsettings
        dumpdata
        flush
        inspectdb
        loaddata
        makemessages
        makemigrations
        migrate
        sendtestemail
        shell
        showmigrations
        sqlflush
        sqlmigrate
        sqlsequencereset
        squashmigrations
        startapp
        startproject
        test
        testserver

    [django_extensions]
        admin_generator
        clean_pyc
        clear_cache
        compile_pyc
        create_app
        create_command
        create_jobs
        create_template_tags
        delete_squashed_migrations
        describe_form
        drop_test_database
        dumpscript
        export_emails
        find_template
        generate_password
        generate_secret_key
        graph_models
        mail_debug
        merge_model_instances
        notes
        passwd
        pipchecker
        print_settings
        print_user_for_session
        reset_db
        reset_schema
        runjob
        runjobs
        runprofileserver
        runscript
        runserver_plus
        set_default_site
        set_fake_emails
        set_fake_passwords
        shell_plus
        show_template_tags
        show_templatetags
        show_urls
        sqlcreate
        sqldiff
        sqldsn
        sync_s3
        syncdata
        unreferenced_files
        update_permissions
        validate_templates

    [sessions]
        clearsessions

    [sslserver]
        runsslserver

    [staticfiles]
        collectstatic
        findstatic
        runserver
