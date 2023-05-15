from unittest import mock, TestCase

from crate_anon.nlp_webserver.security import Credentials, hash_password
from crate_anon.nlp_webserver.views import (
    NlpWebViews,
    REDIS_SESSIONS,
    SESSION_TOKEN_EXPIRY_S,
)

TEST_TOKEN = "test-unique-id"


class NlpWebViewsTests(TestCase):
    @mock.patch(
        "crate_anon.nlp_webserver.views.get_auth_credentials",
        return_value=Credentials("test", "test"),
    )
    @mock.patch(
        "crate_anon.nlp_webserver.views.get_users",
        return_value={"test": hash_password("test")},
    )
    @mock.patch(
        "crate_anon.nlp_webserver.views.make_unique_id",
        return_value=TEST_TOKEN,
    )
    def test_authenticate_sets_redis_session(self, *args) -> None:
        request = mock.Mock()
        view = NlpWebViews(request)
        view._authenticate()
        self.assertEqual(
            REDIS_SESSIONS.get("test"), bytes(TEST_TOKEN, encoding="utf8")
        )
        self.assertLessEqual(
            REDIS_SESSIONS.ttl("test"), SESSION_TOKEN_EXPIRY_S
        )
