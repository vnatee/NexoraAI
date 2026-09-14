from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from mongo_table_connecters import saml_auth


class MemoryCollection:
    def __init__(self):
        self.documents: list[dict] = []

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def insert_one(self, document):
        self.documents.append(deepcopy(document))

    def find_one(self, query, projection=None):
        return next((deepcopy(item) for item in self.documents if self._matches(item, query)), None)

    def find(self, query, projection=None):
        return [deepcopy(item) for item in self.documents if self._matches(item, query)]

    def find_one_and_delete(self, query):
        document = self.find_one(query)
        if document:
            self.documents = [item for item in self.documents if not self._matches(item, query)]
        return document

    def update_one(self, query, update):
        for item in self.documents:
            if self._matches(item, query):
                item.update(deepcopy(update.get("$set") or {}))
                return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()

    def update_many(self, query, update):
        modified = 0
        for item in self.documents:
            if self._matches(item, query):
                item.update(deepcopy(update.get("$set") or {}))
                modified += 1
        return type("Result", (), {"modified_count": modified})()

    def delete_one(self, query):
        self.documents = [item for item in self.documents if not self._matches(item, query)]


@pytest.fixture
def stores(monkeypatch):
    states = MemoryCollection()
    identities = MemoryCollection()
    sessions = MemoryCollection()
    users = MemoryCollection()
    monkeypatch.setattr(saml_auth, "states_collection", states)
    monkeypatch.setattr(saml_auth, "identities_collection", identities)
    monkeypatch.setattr(saml_auth, "sessions_collection", sessions)
    monkeypatch.setattr(saml_auth, "users_collection", users)
    monkeypatch.setattr(saml_auth, "record_federated_link_request", lambda **kwargs: kwargs)
    return states, identities, sessions, users


def provider(**overrides):
    result = {
        "_id": "provider-a",
        "enabled": True,
        "entity_id": "https://id.example.com/entity",
        "email_attribute": "mail",
        "first_name_attribute": "givenName",
        "last_name_attribute": "surname",
        "jit_enabled": True,
        "allowed_domains": ["example.com"],
    }
    result.update(overrides)
    return result


def test_jit_identity_uses_name_id_and_never_grants_admin(stores):
    _, identities, _, users = stores
    identity, user = saml_auth._identity_user(
        provider(),
        name_id="stable-name-id",
        attributes={"mail": ["person@example.com"], "givenName": ["Test"], "surname": ["Person"]},
    )

    assert identity["provider"] == "saml:provider-a"
    assert identity["username_normalized"] == "stable-name-id"
    assert user["created_by_auth_provider"] == "saml"
    assert user["is_sys_admin"] is False


def test_begin_login_records_one_time_request_correlation(stores, monkeypatch):
    states, _, _, _ = stores

    class FakeAuth:
        def login(self, return_to=None):
            assert return_to
            return "https://id.example.com/sso?SAMLRequest=request"

        def get_last_request_id(self):
            return "request-id"

    monkeypatch.setattr(saml_auth, "_auth", lambda *args, **kwargs: FakeAuth())
    redirect = saml_auth.begin_saml_login(
        provider(), {}, acs_url="https://portal/acs", metadata_url="https://portal/metadata"
    )

    assert redirect.startswith("https://id.example.com/sso")
    assert states.documents[0]["request_id"] == "request-id"
    assert "relay_state" not in states.documents[0]


def test_existing_email_requires_admin_review_even_without_jit(stores, monkeypatch):
    _, _, _, users = stores
    users.insert_one({"_id": "existing", "ad_email": "person@example.com", "delete_at": None})
    recorded = []
    monkeypatch.setattr(saml_auth, "record_federated_link_request", lambda **kwargs: recorded.append(kwargs))

    with pytest.raises(saml_auth.SAMLAuthError, match="Administrator must approve") as error:
        saml_auth._identity_user(
            provider(jit_enabled=False),
            name_id="stable-name-id",
            attributes={"mail": ["person@example.com"]},
        )

    assert error.value.status_code == 409
    assert recorded[0]["provider"] == "saml:provider-a"


def test_jit_rejects_unapproved_email_domain(stores):
    with pytest.raises(saml_auth.SAMLAuthError, match="domain is not allowed"):
        saml_auth._identity_user(
            provider(),
            name_id="stable-name-id",
            attributes={"mail": ["person@other.example"]},
        )


def test_resolve_saml_session_returns_internal_claims(stores):
    _, identities, sessions, users = stores
    token = f"{saml_auth.SAML_TOKEN_PREFIX}token"
    identities.insert_one({"_id": "identity", "subject": "external-id", "active": True, "delete_at": None})
    users.insert_one({"_id": "user", "email": "person@example.com", "active": True, "delete_at": None})
    sessions.insert_one({
        "token_digest": saml_auth._digest(token),
        "identity_id": "identity",
        "user_id": "user",
        "username": "person@example.com",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "revoked_at": None,
    })

    claims = saml_auth.resolve_saml_session(token)
    assert claims["auth_provider"] == "saml"
    assert claims["application_user_id"] == "user"


def test_relay_state_is_single_use(stores, monkeypatch):
    states, _, _, _ = stores

    class FakeAuth:
        def process_response(self, request_id=None):
            self.request_id = request_id

        def get_errors(self):
            return []

        def is_authenticated(self):
            return True

        def get_nameid(self):
            return "stable-name-id"

        def get_attributes(self):
            return {"mail": ["person@example.com"]}

    monkeypatch.setattr(saml_auth, "_auth", lambda *args, **kwargs: FakeAuth())
    relay_state = "one-time-state"
    states.insert_one({
        "relay_state_digest": saml_auth._digest(relay_state),
        "request_id": "request-id",
        "provider_id": "provider-a",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    })

    token, _ = saml_auth.complete_saml_login(
        provider(), {}, relay_state, acs_url="https://portal/acs", metadata_url="https://portal/metadata"
    )
    assert token.startswith(saml_auth.SAML_TOKEN_PREFIX)

    with pytest.raises(saml_auth.SAMLAuthError, match="state is invalid"):
        saml_auth.complete_saml_login(
            provider(), {}, relay_state, acs_url="https://portal/acs", metadata_url="https://portal/metadata"
        )


def test_disabling_provider_revokes_its_sessions(stores):
    _, identities, sessions, _ = stores
    identities.insert_one({"_id": "one", "provider": "saml:provider-a", "delete_at": None})
    identities.insert_one({"_id": "two", "provider": "saml:provider-b", "delete_at": None})
    sessions.insert_one({"_id": "a", "identity_id": "one", "revoked_at": None})
    sessions.insert_one({"_id": "b", "identity_id": "two", "revoked_at": None})

    assert saml_auth.revoke_saml_provider_sessions("provider-a") == 1
    assert sessions.find_one({"_id": "a"})["revoked_at"] is not None
    assert sessions.find_one({"_id": "b"})["revoked_at"] is None
