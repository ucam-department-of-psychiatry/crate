#!/usr/bin/env python

r"""
crate_anon/nlp_web/__init__.py

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

Init file for ``crate_anon.nlp_web`` module, with :func:`main` that returns a
WSGI application implementing CRATE's built-in :ref:`NLPRP <nlprp>` server.

"""

from typing import Dict, Any
import logging

from pyramid.config import Router
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from crate_anon.nlp_web.models import DBSession, Base

logging.basicConfig()
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


# noinspection PyUnusedLocal
def main(global_config: Dict[Any, Any], **settings) -> Router:
    # Database
    engine = engine_from_config(settings, 'sqlalchemy.')  # add to config
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    config = Configurator(settings=settings)

    # Security policies
    authn_policy = AuthTktAuthenticationPolicy(
        settings['nlp_web.secret'],
        secure=True,  # only allow requests over HTTPS
        hashalg='sha512')
    authz_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)

    config.add_route('index', '/')
    config.scan('.views')
    return config.make_wsgi_app()
