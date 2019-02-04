from typing import Dict, Any

from pyramid.config import Router
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from nlp_web.models import DBSession, Base


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
