from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from mongo_table_connecters import identity_management


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item.get(key) or datetime.min.replace(tzinfo=timezone.utc), reverse=direction < 0))

    def limit(self, value):
        return Cursor(self[:value])


class MemoryCollection:
    def __init__(self):
        self.documents: list[dict] = []

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$gt" in expected:
                if actual is None or actual <= expected["$gt"]:
                    return False
            elif isinstance(expected, dict) and "$ne" in expected:
                if actual == expected["$ne"]:
                    return False
            elif isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, document):
        self.documents.append(deepcopy(document))

    def find(self, query, projection=None):
        return Cursor(deepcopy([item for item in self.documents if self._matches(item, query)]))

    def find_one(self, query, projection=None):
        return next((deepcopy(item) for item in self.documents if self._matches(item, query)), None)

    def update_one(self, query, update, upsert=False):
        for item in self.documents:
            if self._matches(item, query):
                item.update(deepcopy(update.get("$set") or {}))
                return type("Result", (), {"modified_count": 1})()
        if upsert:
            document = {key: value for key, value in query.items() if not isinstance(value, dict)}
            document.update(deepcopy(update.get("$setOnInsert") or {}))
            document.update(deepcopy(update.get("$set") or {}))
            self.documents.append(document)
        return type("Result", (), {"modified_count": 0})()

    def update_many(self, query, update):
        modified = 0
        for item in self.documents:
            if self._matches(item, query):
                item.update(deepcopy(update.get("$set") or {}))
                modified += 1
        return type("Result", (), {"modified_count": modified})()

    def delete_one(self, query):
        before = len(self.documents)
        self.documents = [item for item in self.documents if not self._matches(item, query)]
        return type("Result", (), {"deleted_count": before - len(self.documents)})()


@pytest.fixture
def stores(monkeypatch):
    identities = MemoryCollection()
    sessions = MemoryCollection()
    requests = MemoryCollection()
    audits = MemoryCollection()
    users = MemoryCollection()
    monkeypatch.setattr(identity_management, "identities_collection", identities)
    monkeypatch.setattr(identity_management, "sessions_collection", sessions)
    monkeypatch.setattr(identity_management, "requests_collection", requests)
    monkeypatch.setattr(identity_management, "audit_collection", audits)
    monkeypatch.setattr(identity_management, "users_collection", users)
    return identities, sessions, requests, audits, users


def _request(stores):
    *_, users = stores
    users.insert_one({"_id": "user-1", "active": True, "delete_at": None, "ad_email": "person@example.com"})
    return identity_management.record_oidc_link_request(
        provider="oidc:provider-a",
        issuer="https://id.example.com",
        subject="immutable-subject",
        email="person@example.com",
        suggested_user_id="user-1",
    )


def test_request_is_pending_and_contains_no_token_or_claim_payload(stores):
    request = _request(stores)

    assert request["status"] == "pending"
    assert request["expires_at"] > datetime.now(timezone.utc)
    assert "token" not in request
    assert "claims" not in request


def test_admin_approval_creates_explicit_identity_and_metadata_only_audit(stores):
    identities, _, requests, audits, _ = stores
    request = _request(stores)

    identity = identity_management.approve_identity_link(request["_id"], "user-1", actor_id="admin-1")

    assert identity["provider"] == "oidc:provider-a"
    assert identity["username_normalized"] == "immutable-subject"
    assert requests.find_one({"_id": request["_id"]})["status"] == "approved"
    audit = audits.documents[0]
    assert audit["action"] == "linked"
    assert audit["actor_id"] == "admin-1"
    assert "email" not in audit and "subject" not in audit
    assert identities.find_one({"_id": identity["_id"]}) is not None


def test_approval_cannot_add_a_sign_in_path_to_system_admin(stores):
    *_, users = stores
    request = _request(stores)
    users.update_one({"_id": "user-1"}, {"$set": {"is_sys_admin": True}})

    with pytest.raises(ValueError, match="System Administrator"):
        identity_management.approve_identity_link(request["_id"], "user-1", actor_id="admin-2")


def test_reject_records_review_without_creating_identity(stores):
    identities, _, requests, audits, _ = stores
    request = _request(stores)

    assert identity_management.reject_identity_link(request["_id"], actor_id="admin-1") is True
    assert requests.find_one({"_id": request["_id"]})["status"] == "rejected"
    assert identities.documents == []
    assert audits.documents[0]["action"] == "link_rejected"


def test_unlink_revokes_sessions_when_another_login_identity_exists(stores):
    identities, sessions, _, audits, users = stores
    users.insert_one({"_id": "user-1", "active": True, "delete_at": None, "created_by_auth_provider": "local"})
    identities.insert_one({"_id": "oidc-id", "provider": "oidc:provider-a", "user_id": "user-1", "active": True, "delete_at": None})
    identities.insert_one({"_id": "local-id", "provider": "local", "user_id": "user-1", "active": True, "delete_at": None})
    sessions.insert_one({"_id": "session", "identity_id": "oidc-id", "revoked_at": None})

    assert identity_management.unlink_oidc_identity("oidc-id", actor_id="admin-1") is True
    assert identities.find_one({"_id": "oidc-id"}) is None
    assert sessions.find_one({"_id": "session"})["revoked_at"] is not None
    assert audits.documents[0]["action"] == "unlinked"


def test_unlink_refuses_to_remove_only_sign_in_identity(stores):
    identities, _, _, _, users = stores
    users.insert_one({"_id": "user-1", "active": True, "delete_at": None, "created_by_auth_provider": "oidc"})
    identities.insert_one({"_id": "oidc-id", "provider": "oidc:provider-a", "user_id": "user-1", "active": True, "delete_at": None})

    with pytest.raises(ValueError, match="only identity"):
        identity_management.unlink_oidc_identity("oidc-id", actor_id="admin-1")


def test_saml_identity_uses_the_same_reviewed_unlink_policy(stores):
    identities, sessions, _, audits, users = stores
    users.insert_one({"_id": "user-1", "active": True, "delete_at": None, "created_by_auth_provider": "local"})
    identities.insert_one({"_id": "saml-id", "provider": "saml:provider-a", "user_id": "user-1", "active": True, "delete_at": None})
    identities.insert_one({"_id": "local-id", "provider": "local", "user_id": "user-1", "active": True, "delete_at": None})
    sessions.insert_one({"_id": "session", "identity_id": "saml-id", "revoked_at": None})

    assert identity_management.unlink_federated_identity("saml-id", actor_id="admin-1") is True
    assert sessions.find_one({"_id": "session"})["revoked_at"] is not None
    assert audits.documents[0]["provider"] == "saml:provider-a"
