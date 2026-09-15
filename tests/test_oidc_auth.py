from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mongo_table_connecters import oidc_auth


class MemoryCollection:
    def __init__(self):
        self.documents: list[dict] = []

    @staticmethod
    def _matches(document, query):
        return all(
            document.get(key) in value["$in"] if isinstance(value, dict) and "$in" in value
            else document.get(key) == value
            for key, value in query.items()
        )

    def find_one(self, query, projection=None):
        return next((deepcopy(item) for item in self.documents if self._matches(item, query)), None)

    def find(self, query, projection=None):
        return [deepcopy(item) for item in self.documents if self._matches(item, query)]

    def insert_one(self, document):
        self.documents.append(deepcopy(document))

    def delete_one(self, query):
        self.documents = [item for item in self.documents if not self._matches(item, query)]

    def find_one_and_delete(self, query):
        document = self.find_one(query)
        if document:
            self.delete_one(query)
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


@pytest.fixture
def stores(monkeypatch):
    states = MemoryCollection()
    identities = MemoryCollection()
    sessions = MemoryCollection()
    users = MemoryCollection()
    monkeypatch.setattr(oidc_auth, "states_collection", states)
    monkeypatch.setattr(oidc_auth, "identities_collection", identities)
    monkeypatch.setattr(oidc_auth, "sessions_collection", sessions)
    monkeypatch.setattr(oidc_auth, "users_collection", users)
    monkeypatch.setattr(oidc_auth, "record_oidc_link_request", lambda **kwargs: kwargs)
    return states, identities, sessions, users


def settings(**overrides):
    result = {
        "oidc_enabled": True,
        "oidc_issuer": "https://id.example.com",
        "oidc_client_id": "nexora",
        "oidc_client_secret": "secret",
        "oidc_token_auth_method": "client_secret_basic",
        "oidc_jit_enabled": True,
        "oidc_allowed_domains": ["example.com"],
    }
    result.update(overrides)
    return result


def test_jit_identity_uses_subject_and_does_not_grant_admin(stores):
    _, identities, _, users = stores
    identity, user = oidc_auth._identity_user(
        settings(),
        {
            "sub": "stable-subject",
            "email": "person@example.com",
            "email_verified": True,
            "given_name": "Test",
            "family_name": "Person",
        },
    )

    assert identity["username_normalized"] == "stable-subject"
    assert user["is_sys_admin"] is False
    assert user["created_by_auth_provider"] == "oidc"
    assert len(identities.documents) == 1
    assert len(users.documents) == 1


def test_jit_never_links_existing_user_by_email(stores):
    _, _, _, users = stores
    users.insert_one({"_id": "existing", "ad_email": "person@example.com", "delete_at": None})

    with pytest.raises(oidc_auth.OIDCAuthError, match="Administrator must approve") as error:
        oidc_auth._identity_user(
            settings(),
            {"sub": "new-subject", "email": "person@example.com", "email_verified": True},
        )
    assert error.value.status_code == 409


def test_existing_user_creates_review_request_even_when_jit_is_disabled(stores, monkeypatch):
    _, _, _, users = stores
    users.insert_one({"_id": "existing", "ad_email": "person@example.com", "delete_at": None})
    recorded = []
    monkeypatch.setattr(oidc_auth, "record_oidc_link_request", lambda **kwargs: recorded.append(kwargs))

    with pytest.raises(oidc_auth.OIDCAuthError, match="Administrator must approve"):
        oidc_auth._identity_user(
            settings(oidc_jit_enabled=False),
            {"sub": "new-subject", "email": "person@example.com", "email_verified": True},
        )

    assert recorded[0]["suggested_user_id"] == "existing"


def test_jit_rejects_unapproved_domain(stores):
    with pytest.raises(oidc_auth.OIDCAuthError, match="domain is not allowed"):
        oidc_auth._identity_user(
            settings(),
            {"sub": "subject", "email": "person@other.example", "email_verified": True},
        )


def test_resolve_oidc_session_returns_internal_user_claims(stores):
    _, identities, sessions, users = stores
    now = datetime.now(timezone.utc)
    token = f"{oidc_auth.OIDC_TOKEN_PREFIX}token"
    identities.insert_one(
        {"_id": "identity", "subject": "external-sub", "active": True, "delete_at": None}
    )
    users.insert_one(
        {"_id": "user", "email": "person@example.com", "active": True, "delete_at": None}
    )
    sessions.insert_one(
        {
            "token_digest": oidc_auth._digest(token),
            "identity_id": "identity",
            "user_id": "user",
            "username": "person@example.com",
            "expires_at": now + timedelta(hours=1),
            "revoked_at": None,
        }
    )

    claims = oidc_auth.resolve_oidc_session(token)
    assert claims["auth_provider"] == "oidc"
    assert claims["application_user_id"] == "user"
    assert claims["sub"] == "external-sub"


def test_disabling_provider_can_revoke_all_of_its_sessions(stores):
    _, identities, sessions, _ = stores
    identities.insert_one({"_id": "one", "provider": "oidc:provider-a", "delete_at": None})
    identities.insert_one({"_id": "two", "provider": "oidc:provider-b", "delete_at": None})
    sessions.insert_one({"_id": "a", "identity_id": "one", "revoked_at": None})
    sessions.insert_one({"_id": "b", "identity_id": "two", "revoked_at": None})

    assert oidc_auth.revoke_oidc_provider_sessions("provider-a") == 1
    assert sessions.find_one({"_id": "a"})["revoked_at"] is not None
    assert sessions.find_one({"_id": "b"})["revoked_at"] is None


def test_disabling_legacy_provider_uses_issuer_identity_key(stores):
    _, identities, sessions, _ = stores
    issuer = "https://legacy.example.com"
    provider_key = f"oidc:{oidc_auth._digest(issuer)[:24]}"
    identities.insert_one({"_id": "legacy-id", "provider": provider_key, "delete_at": None})
    sessions.insert_one({"_id": "legacy-session", "identity_id": "legacy-id", "revoked_at": None})

    assert oidc_auth.revoke_oidc_provider_sessions("legacy", legacy_issuer=issuer) == 1
    assert sessions.find_one({"_id": "legacy-session"})["revoked_at"] is not None


@pytest.mark.asyncio
async def test_id_token_validation_requires_signature_audience_issuer_and_nonce(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": "https://id.example.com",
            "aud": "nexora",
            "sub": "subject",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "nonce": "expected-nonce",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    async def fake_json_request(method, url, **kwargs):
        return {"keys": [public_jwk]}

    monkeypatch.setattr(oidc_auth, "_json_request", fake_json_request)
    claims = await oidc_auth._validate_id_token(
        settings(), {"jwks_uri": "https://id.example.com/jwks"}, token, "expected-nonce"
    )
    assert claims["sub"] == "subject"

    with pytest.raises(oidc_auth.OIDCAuthError, match="nonce"):
        await oidc_auth._validate_id_token(
            settings(), {"jwks_uri": "https://id.example.com/jwks"}, token, "wrong-nonce"
        )
