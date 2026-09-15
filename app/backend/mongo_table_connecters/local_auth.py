from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from mongo_table_connecters.mongo_connector import get_database


IDENTITY_COLLECTION = "auth_identities"
SESSION_COLLECTION = "auth_sessions"
LOCAL_TOKEN_PREFIX = "nx_local_"
PASSWORD_SCHEME = "scrypt"
PASSWORD_N = 2**14
PASSWORD_R = 8
PASSWORD_P = 1
SESSION_HOURS = 12
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
LOGIN_RATE_LIMIT = 30
LOGIN_RATE_WINDOW_MINUTES = 15

db = get_database()
identities_collection = db[IDENTITY_COLLECTION]
sessions_collection = db[SESSION_COLLECTION]
users_collection = db["users"]
bootstrap_collection = db["auth_bootstrap"]
login_limits_collection = db["auth_login_limits"]


class LocalAuthError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_username(username: Any) -> str:
    value = str(username or "").strip().lower()
    if not value or len(value) > 254:
        raise LocalAuthError("A valid username is required")
    return value


def _validate_password(password: Any) -> str:
    value = str(password or "")
    if len(value) < 12:
        raise LocalAuthError("Password must contain at least 12 characters")
    if len(value) > 1024:
        raise LocalAuthError("Password is too long")
    return value


def hash_password(password: str) -> str:
    password = _validate_password(password)
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=PASSWORD_N, r=PASSWORD_R, p=PASSWORD_P, dklen=32
    )
    return "$".join(
        [PASSWORD_SCHEME, str(PASSWORD_N), str(PASSWORD_R), str(PASSWORD_P), salt.hex(), digest.hex()]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, raw_n, raw_r, raw_p, raw_salt, raw_digest = encoded.split("$", 5)
        if scheme != PASSWORD_SCHEME:
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(raw_salt),
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(bytes.fromhex(raw_digest)),
        )
        return hmac.compare_digest(digest, bytes.fromhex(raw_digest))
    except (ValueError, TypeError):
        return False


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_local_auth_indexes() -> None:
    identities_collection.create_index(
        [("provider", 1), ("username_normalized", 1)], unique=True, name="auth_identity_provider_username"
    )
    identities_collection.create_index("user_id", name="auth_identity_user")
    sessions_collection.create_index("token_digest", unique=True, name="auth_session_token")
    sessions_collection.create_index("expires_at", expireAfterSeconds=0, name="auth_session_expiry")
    login_limits_collection.create_index("expires_at", expireAfterSeconds=0, name="auth_login_limit_expiry")


def enforce_local_login_rate_limit(source: str) -> None:
    now = _now()
    window_seconds = LOGIN_RATE_WINDOW_MINUTES * 60
    bucket = int(now.timestamp()) // window_seconds
    source_digest = hashlib.sha256(str(source or "unknown").encode("utf-8")).hexdigest()
    document = login_limits_collection.find_one_and_update(
        {"_id": f"{source_digest}:{bucket}"},
        {
            "$inc": {"attempts": 1},
            "$setOnInsert": {"expires_at": now + timedelta(seconds=window_seconds * 2)},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if int((document or {}).get("attempts") or 0) > LOGIN_RATE_LIMIT:
        raise LocalAuthError("Too many sign-in attempts. Try again later.", status_code=429)


def local_identity_exists() -> bool:
    return identities_collection.find_one({"provider": "local", "delete_at": None}, {"_id": 1}) is not None


def create_local_identity(*, user_id: str, username: str, password: str) -> dict[str, Any]:
    normalized = _normalize_username(username)
    now = _now()
    document = {
        "_id": str(uuid.uuid4()),
        "provider": "local",
        "username": str(username).strip(),
        "username_normalized": normalized,
        "user_id": str(user_id),
        "password_hash": hash_password(password),
        "active": True,
        "failed_login_count": 0,
        "locked_until": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
        "delete_at": None,
    }
    try:
        identities_collection.insert_one(document)
    except DuplicateKeyError as error:
        raise LocalAuthError("That local username is already in use", status_code=409) from error
    return document


def bootstrap_local_superuser(
    *, username: str, password: str, email: str, first_name: str, last_name: str
) -> dict[str, Any]:
    if local_identity_exists():
        raise LocalAuthError("Local authentication has already been initialized", status_code=409)
    try:
        bootstrap_collection.insert_one({"_id": "local", "created_at": _now()})
    except DuplicateKeyError as error:
        raise LocalAuthError("Local authentication has already been initialized", status_code=409) from error
    normalized = _normalize_username(username)
    user_id = str(uuid.uuid4())
    try:
        identity = create_local_identity(user_id=user_id, username=normalized, password=password)
    except Exception:
        bootstrap_collection.delete_one({"_id": "local"})
        raise
    now = _now()
    user = {
        "_id": user_id,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
        "email": str(email or normalized).strip(),
        "ad_email": normalized,
        "first_name": str(first_name or "Local").strip(),
        "last_name": str(last_name or "Administrator").strip(),
        "employee_id": "",
        "tel": "",
        "active": True,
        "is_sys_admin": True,
        "created_by_auth_provider": "local",
    }
    try:
        users_collection.insert_one(user)
    except Exception:
        identities_collection.delete_one({"_id": identity["_id"]})
        bootstrap_collection.delete_one({"_id": "local"})
        raise
    return user


def authenticate_local_user(username: str, password: str) -> tuple[str, dict[str, Any]]:
    normalized = _normalize_username(username)
    identity = identities_collection.find_one(
        {"provider": "local", "username_normalized": normalized, "delete_at": None}
    )
    now = _now()
    if not identity or identity.get("active", True) is not True:
        raise LocalAuthError("Invalid username or password", status_code=401)
    locked_until = identity.get("locked_until")
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until and locked_until > now:
        raise LocalAuthError("Account is temporarily locked", status_code=423)
    if not verify_password(str(password or ""), str(identity.get("password_hash") or "")):
        failed = int(identity.get("failed_login_count") or 0) + 1
        update: dict[str, Any] = {"failed_login_count": failed, "updated_at": now}
        if failed >= MAX_FAILED_LOGINS:
            update["locked_until"] = now + timedelta(minutes=LOCK_MINUTES)
            update["failed_login_count"] = 0
        identities_collection.update_one({"_id": identity["_id"]}, {"$set": update})
        raise LocalAuthError("Invalid username or password", status_code=401)
    user = users_collection.find_one({"_id": identity["user_id"], "delete_at": None, "active": True})
    if not user:
        raise LocalAuthError("The application user is disabled or unavailable", status_code=403)
    identities_collection.update_one(
        {"_id": identity["_id"]},
        {"$set": {"failed_login_count": 0, "locked_until": None, "last_login_at": now, "updated_at": now}},
    )
    token = LOCAL_TOKEN_PREFIX + secrets.token_urlsafe(32)
    sessions_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "token_digest": _token_digest(token),
            "identity_id": identity["_id"],
            "user_id": identity["user_id"],
            "username": identity["username"],
            "created_at": now,
            "expires_at": now + timedelta(hours=SESSION_HOURS),
            "revoked_at": None,
        }
    )
    return token, user


def resolve_local_session(token: str) -> dict[str, Any]:
    if not token.startswith(LOCAL_TOKEN_PREFIX):
        raise LocalAuthError("Invalid local session", status_code=401)
    session = sessions_collection.find_one(
        {"token_digest": _token_digest(token), "revoked_at": None}
    )
    now = _now()
    expires_at = session.get("expires_at") if session else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not session or not expires_at or expires_at <= now:
        raise LocalAuthError("Local session has expired", status_code=401)
    user = users_collection.find_one({"_id": session["user_id"], "delete_at": None, "active": True})
    if not user:
        raise LocalAuthError("The application user is disabled or unavailable", status_code=403)
    username = str(session.get("username") or user.get("email") or user["_id"])
    return {
        "auth_provider": "local",
        "sub": str(session["identity_id"]),
        "oid": str(user["_id"]),
        "application_user_id": str(user["_id"]),
        "preferred_username": username,
        "email": str(user.get("email") or username),
        "groups": [],
    }


def revoke_local_session(token: str) -> bool:
    result = sessions_collection.update_one(
        {"token_digest": _token_digest(token), "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    return result.modified_count > 0


def get_local_identity_for_user(user_id: str) -> dict[str, Any] | None:
    return identities_collection.find_one(
        {"provider": "local", "user_id": str(user_id), "delete_at": None},
        {"_id": 1, "username": 1, "active": 1},
    )


def list_local_identities_by_user_ids(user_ids: list[str]) -> dict[str, dict[str, Any]]:
    normalized = [str(user_id) for user_id in user_ids if user_id]
    if not normalized:
        return {}
    return {
        str(item["user_id"]): item
        for item in identities_collection.find(
            {"provider": "local", "user_id": {"$in": normalized}, "delete_at": None},
            {"_id": 1, "user_id": 1, "username": 1, "active": 1},
        )
    }


def reset_local_password(user_id: str, password: str) -> None:
    identity = get_local_identity_for_user(user_id)
    if not identity:
        raise LocalAuthError("This user does not have a local identity", status_code=404)
    now = _now()
    identities_collection.update_one(
        {"_id": identity["_id"]},
        {
            "$set": {
                "password_hash": hash_password(password),
                "failed_login_count": 0,
                "locked_until": None,
                "updated_at": now,
            }
        },
    )
    sessions_collection.update_many(
        {"user_id": str(user_id), "revoked_at": None}, {"$set": {"revoked_at": now}}
    )


def change_local_password(user_id: str, current_password: str, new_password: str) -> None:
    identity = identities_collection.find_one(
        {"provider": "local", "user_id": str(user_id), "delete_at": None}
    )
    if not identity:
        raise LocalAuthError("This user does not have a local identity", status_code=404)
    if not verify_password(str(current_password or ""), str(identity.get("password_hash") or "")):
        raise LocalAuthError("Current password is incorrect", status_code=403)
    validated_password = _validate_password(new_password)
    if verify_password(validated_password, str(identity.get("password_hash") or "")):
        raise LocalAuthError("New password must be different from the current password")
    now = _now()
    identities_collection.update_one(
        {"_id": identity["_id"]},
        {
            "$set": {
                "password_hash": hash_password(validated_password),
                "failed_login_count": 0,
                "locked_until": None,
                "updated_at": now,
            }
        },
    )
    sessions_collection.update_many(
        {"user_id": str(user_id), "revoked_at": None}, {"$set": {"revoked_at": now}}
    )


def create_managed_local_user(*, username: str, password: str, user: dict[str, Any]) -> dict[str, Any]:
    user_id = str(uuid.uuid4())
    identity = create_local_identity(user_id=user_id, username=username, password=password)
    now = _now()
    document = {
        "_id": user_id,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
        "email": str(user.get("email") or username).strip(),
        "ad_email": str(user.get("ad_email") or "").strip(),
        "first_name": str(user.get("first_name") or "").strip(),
        "last_name": str(user.get("last_name") or "").strip(),
        "employee_id": str(user.get("employee_id") or "").strip(),
        "tel": str(user.get("tel") or "").strip(),
        "active": user.get("active", True) is not False,
        "is_sys_admin": user.get("is_sys_admin") is True,
        "created_by_auth_provider": "local",
    }
    try:
        users_collection.insert_one(document)
    except Exception:
        identities_collection.delete_one({"_id": identity["_id"]})
        raise
    return document
