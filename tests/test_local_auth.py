from copy import deepcopy

import pytest

from mongo_table_connecters import local_auth


class Result:
    def __init__(self, *, modified_count=0):
        self.modified_count = modified_count


class MemoryCollection:
    def __init__(self):
        self.items: dict[str, dict] = {}
        self.indexes = []

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def insert_one(self, document):
        self.items[document["_id"]] = deepcopy(document)

    def find_one(self, query, projection=None):
        for item in self.items.values():
            if all(item.get(key) == value for key, value in query.items()):
                return deepcopy(item)
        return None

    def update_one(self, query, update):
        for item in self.items.values():
            if all(item.get(key) == value for key, value in query.items()):
                item.update(deepcopy(update.get("$set") or {}))
                return Result(modified_count=1)
        return Result()

    def update_many(self, query, update):
        modified = 0
        for item in self.items.values():
            if all(item.get(key) == value for key, value in query.items()):
                item.update(deepcopy(update.get("$set") or {}))
                modified += 1
        return Result(modified_count=modified)

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        item = self.items.get(query["_id"])
        if item is None and upsert:
            item = {"_id": query["_id"]}
            item.update(deepcopy(update.get("$setOnInsert") or {}))
            self.items[query["_id"]] = item
        if item is not None:
            for key, value in (update.get("$inc") or {}).items():
                item[key] = int(item.get(key) or 0) + value
        return deepcopy(item)

    def delete_one(self, query):
        for identifier, item in list(self.items.items()):
            if all(item.get(key) == value for key, value in query.items()):
                del self.items[identifier]
                return Result(modified_count=1)
        return Result()


@pytest.fixture
def collections(monkeypatch):
    identities = MemoryCollection()
    sessions = MemoryCollection()
    users = MemoryCollection()
    bootstrap = MemoryCollection()
    login_limits = MemoryCollection()
    monkeypatch.setattr(local_auth, "identities_collection", identities)
    monkeypatch.setattr(local_auth, "sessions_collection", sessions)
    monkeypatch.setattr(local_auth, "users_collection", users)
    monkeypatch.setattr(local_auth, "bootstrap_collection", bootstrap)
    monkeypatch.setattr(local_auth, "login_limits_collection", login_limits)
    return identities, sessions, users


def test_password_hash_is_salted_and_verifiable():
    first = local_auth.hash_password("correct horse battery staple")
    second = local_auth.hash_password("correct horse battery staple")

    assert first != second
    assert local_auth.verify_password("correct horse battery staple", first)
    assert not local_auth.verify_password("incorrect password", first)


def test_bootstrap_login_resolve_and_logout(collections):
    identities, sessions, _users = collections
    user = local_auth.bootstrap_local_superuser(
        username="Admin",
        password="correct horse battery staple",
        email="admin@example.test",
        first_name="Local",
        last_name="Admin",
    )

    assert user["is_sys_admin"] is True
    assert local_auth.local_identity_exists()
    with pytest.raises(local_auth.LocalAuthError) as duplicate:
        local_auth.bootstrap_local_superuser(
            username="other", password="another strong password", email="", first_name="", last_name=""
        )
    assert duplicate.value.status_code == 409

    token, _ = local_auth.authenticate_local_user("ADMIN", "correct horse battery staple")
    claims = local_auth.resolve_local_session(token)
    assert claims["auth_provider"] == "local"
    assert claims["application_user_id"] == user["_id"]
    assert claims["oid"] == user["_id"]
    assert not any("correct horse" in str(item) for item in identities.items.values())
    assert not any(token in str(item) for item in sessions.items.values())

    assert local_auth.revoke_local_session(token)
    with pytest.raises(local_auth.LocalAuthError):
        local_auth.resolve_local_session(token)


def test_failed_login_locks_identity_after_five_attempts(collections):
    local_auth.bootstrap_local_superuser(
        username="admin",
        password="correct horse battery staple",
        email="admin@example.test",
        first_name="Local",
        last_name="Admin",
    )

    for _ in range(5):
        with pytest.raises(local_auth.LocalAuthError):
            local_auth.authenticate_local_user("admin", "wrong password")

    with pytest.raises(local_auth.LocalAuthError) as locked:
        local_auth.authenticate_local_user("admin", "correct horse battery staple")
    assert locked.value.status_code == 423


def test_password_policy_rejects_short_password(collections):
    with pytest.raises(local_auth.LocalAuthError, match="at least 12"):
        local_auth.create_local_identity(user_id="user-1", username="user", password="short")


def test_password_reset_revokes_existing_sessions(collections):
    user = local_auth.bootstrap_local_superuser(
        username="admin",
        password="correct horse battery staple",
        email="admin@example.test",
        first_name="Local",
        last_name="Admin",
    )
    old_token, _ = local_auth.authenticate_local_user("admin", "correct horse battery staple")

    local_auth.reset_local_password(user["_id"], "new correct horse password")

    with pytest.raises(local_auth.LocalAuthError):
        local_auth.resolve_local_session(old_token)
    with pytest.raises(local_auth.LocalAuthError):
        local_auth.authenticate_local_user("admin", "correct horse battery staple")
    new_token, _ = local_auth.authenticate_local_user("admin", "new correct horse password")
    assert local_auth.resolve_local_session(new_token)["application_user_id"] == user["_id"]


def test_user_can_change_own_password_with_current_password(collections):
    user = local_auth.bootstrap_local_superuser(
        username="admin",
        password="correct horse battery staple",
        email="admin@example.test",
        first_name="Local",
        last_name="Admin",
    )
    old_token, _ = local_auth.authenticate_local_user("admin", "correct horse battery staple")

    local_auth.change_local_password(
        user["_id"], "correct horse battery staple", "a different strong password"
    )

    with pytest.raises(local_auth.LocalAuthError):
        local_auth.resolve_local_session(old_token)
    with pytest.raises(local_auth.LocalAuthError):
        local_auth.authenticate_local_user("admin", "correct horse battery staple")
    new_token, _ = local_auth.authenticate_local_user("admin", "a different strong password")
    assert local_auth.resolve_local_session(new_token)["application_user_id"] == user["_id"]


def test_user_password_change_requires_correct_and_different_current_password(collections):
    user = local_auth.bootstrap_local_superuser(
        username="admin",
        password="correct horse battery staple",
        email="admin@example.test",
        first_name="Local",
        last_name="Admin",
    )

    with pytest.raises(local_auth.LocalAuthError, match="Current password is incorrect") as incorrect:
        local_auth.change_local_password(user["_id"], "wrong password", "a different strong password")
    assert incorrect.value.status_code == 403

    with pytest.raises(local_auth.LocalAuthError, match="must be different"):
        local_auth.change_local_password(
            user["_id"], "correct horse battery staple", "correct horse battery staple"
        )


def test_login_rate_limit_is_shared_through_persistent_bucket(collections):
    for _ in range(local_auth.LOGIN_RATE_LIMIT):
        local_auth.enforce_local_login_rate_limit("127.0.0.1")

    with pytest.raises(local_auth.LocalAuthError) as limited:
        local_auth.enforce_local_login_rate_limit("127.0.0.1")
    assert limited.value.status_code == 429
