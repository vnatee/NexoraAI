from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from pymongo.errors import DuplicateKeyError

from mongo_table_connecters.identity_management import record_federated_link_request
from mongo_table_connecters.mongo_connector import get_database
from mongo_table_connecters.saml_providers import saml_settings

STATE_MINUTES = 10
SESSION_HOURS = 12
SAML_TOKEN_PREFIX = "nx_saml_"

db = get_database()
states_collection = db["auth_saml_states"]
identities_collection = db["auth_identities"]
sessions_collection = db["auth_sessions"]
users_collection = db["users"]


class SAMLAuthError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def saml_provider_identity_key(provider: dict[str, Any]) -> str:
    return f"saml:{str(provider.get('_id') or '')}"


def ensure_saml_auth_indexes() -> None:
    states_collection.create_index("relay_state_digest", unique=True, name="auth_saml_relay_state")
    states_collection.create_index("expires_at", expireAfterSeconds=0, name="auth_saml_state_expiry")


def _auth(
    provider: dict[str, Any], request_data: dict[str, Any], *, acs_url: str, metadata_url: str
) -> OneLogin_Saml2_Auth:
    try:
        return OneLogin_Saml2_Auth(
            request_data,
            old_settings=saml_settings(provider, acs_url=acs_url, metadata_url=metadata_url),
        )
    except Exception as error:
        raise SAMLAuthError("SAML provider configuration is invalid") from error


def begin_saml_login(
    provider: dict[str, Any], request_data: dict[str, Any], *, acs_url: str, metadata_url: str
) -> str:
    if provider.get("enabled") is not True:
        raise SAMLAuthError("SAML authentication is not enabled", status_code=404)
    relay_state = secrets.token_urlsafe(32)
    auth = _auth(provider, request_data, acs_url=acs_url, metadata_url=metadata_url)
    try:
        redirect_url = auth.login(return_to=relay_state)
        request_id = str(auth.get_last_request_id() or "")
    except Exception as error:
        raise SAMLAuthError("Unable to create the SAML authentication request", status_code=502) from error
    if not request_id:
        raise SAMLAuthError("The SAML authentication request did not produce a request ID", status_code=500)
    now = _now()
    states_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "relay_state_digest": _digest(relay_state),
            "request_id": request_id,
            "provider_id": str(provider.get("_id") or ""),
            "created_at": now,
            "expires_at": now + timedelta(minutes=STATE_MINUTES),
        }
    )
    return redirect_url


def _attribute(attributes: dict[str, list[str]], name: str) -> str:
    values = attributes.get(name) or []
    return str(values[0] if values else "").strip()


def _allowed_email(provider: dict[str, Any], attributes: dict[str, list[str]], name_id: str) -> str:
    email = _attribute(attributes, str(provider.get("email_attribute") or "email")) or str(name_id or "").strip()
    email = email.lower()
    if "@" not in email or len(email) > 254:
        raise SAMLAuthError("The identity provider did not return a valid email address", status_code=403)
    allowed_domains = {str(item).lower() for item in (provider.get("allowed_domains") or [])}
    if provider.get("jit_enabled") is True and not allowed_domains:
        raise SAMLAuthError("SAML JIT provisioning requires an allowed email domain", status_code=403)
    if allowed_domains and email.rsplit("@", 1)[1] not in allowed_domains:
        raise SAMLAuthError("This email domain is not allowed to sign in", status_code=403)
    return email


def _identity_user(
    provider: dict[str, Any], *, name_id: str, attributes: dict[str, list[str]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    subject = str(name_id or "").strip()
    if not subject or len(subject) > 512:
        raise SAMLAuthError("The identity provider returned an invalid NameID", status_code=401)
    provider_key = saml_provider_identity_key(provider)
    identity = identities_collection.find_one(
        {"provider": provider_key, "username_normalized": subject, "delete_at": None}
    )
    if identity:
        user = users_collection.find_one({"_id": identity["user_id"], "delete_at": None, "active": True})
        if not user:
            raise SAMLAuthError("The application user is disabled or unavailable", status_code=403)
        return identity, user
    email = _allowed_email(provider, attributes, subject)
    existing_user = users_collection.find_one({"ad_email": email, "delete_at": None}, {"_id": 1})
    if existing_user:
        record_federated_link_request(
            provider=provider_key,
            issuer=str(provider.get("entity_id") or ""),
            subject=subject,
            email=email,
            suggested_user_id=str(existing_user["_id"]),
        )
        raise SAMLAuthError(
            "An account with this email already exists; a System Administrator must approve the identity link",
            status_code=409,
        )
    if provider.get("jit_enabled") is not True:
        raise SAMLAuthError("This SAML identity has not been provisioned in NexoraAI", status_code=403)
    now = _now()
    user_id = str(uuid.uuid4())
    user = {
        "_id": user_id,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
        "email": email,
        "ad_email": email,
        "first_name": _attribute(attributes, str(provider.get("first_name_attribute") or "firstName")),
        "last_name": _attribute(attributes, str(provider.get("last_name_attribute") or "lastName")),
        "employee_id": "",
        "tel": "",
        "active": True,
        "is_sys_admin": False,
        "created_by_auth_provider": "saml",
    }
    identity = {
        "_id": str(uuid.uuid4()),
        "provider": provider_key,
        "issuer": str(provider.get("entity_id") or ""),
        "subject": subject,
        "username": email,
        "username_normalized": subject,
        "user_id": user_id,
        "active": True,
        "created_at": now,
        "updated_at": now,
        "delete_at": None,
    }
    try:
        users_collection.insert_one(user)
        identities_collection.insert_one(identity)
    except DuplicateKeyError as error:
        users_collection.delete_one({"_id": user_id})
        raise SAMLAuthError("This SAML identity is already linked", status_code=409) from error
    except Exception:
        users_collection.delete_one({"_id": user_id})
        identities_collection.delete_one({"_id": identity["_id"]})
        raise
    return identity, user


def complete_saml_login(
    provider: dict[str, Any],
    request_data: dict[str, Any],
    relay_state: str,
    *,
    acs_url: str,
    metadata_url: str,
) -> tuple[str, dict[str, Any]]:
    state = states_collection.find_one_and_delete({"relay_state_digest": _digest(relay_state)})
    expires_at = state.get("expires_at") if state else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        not state
        or not expires_at
        or expires_at <= _now()
        or str(state.get("provider_id") or "") != str(provider.get("_id") or "")
    ):
        raise SAMLAuthError("SAML login state is invalid or expired", status_code=401)
    auth = _auth(provider, request_data, acs_url=acs_url, metadata_url=metadata_url)
    try:
        auth.process_response(request_id=str(state.get("request_id") or ""))
    except Exception as error:
        raise SAMLAuthError("SAML response validation failed", status_code=401) from error
    errors = auth.get_errors()
    if errors or not auth.is_authenticated():
        raise SAMLAuthError("SAML response validation failed", status_code=401)
    identity, user = _identity_user(
        provider,
        name_id=str(auth.get_nameid() or ""),
        attributes=auth.get_attributes() or {},
    )
    now = _now()
    identities_collection.update_one(
        {"_id": identity["_id"]}, {"$set": {"last_login_at": now, "updated_at": now}}
    )
    token = SAML_TOKEN_PREFIX + secrets.token_urlsafe(32)
    sessions_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "token_digest": _digest(token),
            "identity_id": identity["_id"],
            "user_id": user["_id"],
            "username": identity.get("username") or user.get("email"),
            "auth_provider": "saml",
            "provider": identity.get("provider"),
            "created_at": now,
            "expires_at": now + timedelta(hours=SESSION_HOURS),
            "revoked_at": None,
        }
    )
    return token, user


def resolve_saml_session(token: str) -> dict[str, Any]:
    if not token.startswith(SAML_TOKEN_PREFIX):
        raise SAMLAuthError("Invalid SAML session", status_code=401)
    session = sessions_collection.find_one({"token_digest": _digest(token), "revoked_at": None})
    now = _now()
    expires_at = session.get("expires_at") if session else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not session or not expires_at or expires_at <= now:
        raise SAMLAuthError("SAML session has expired", status_code=401)
    identity = identities_collection.find_one({"_id": session["identity_id"], "delete_at": None, "active": True})
    user = users_collection.find_one({"_id": session["user_id"], "delete_at": None, "active": True})
    if not identity or not user:
        raise SAMLAuthError("The application user is disabled or unavailable", status_code=403)
    username = str(session.get("username") or user.get("email") or user["_id"])
    return {
        "auth_provider": "saml",
        "sub": str(identity.get("subject") or identity["_id"]),
        "oid": str(user["_id"]),
        "application_user_id": str(user["_id"]),
        "preferred_username": username,
        "email": str(user.get("email") or username),
        "groups": [],
    }


def revoke_saml_session(token: str) -> bool:
    result = sessions_collection.update_one(
        {"token_digest": _digest(token), "revoked_at": None}, {"$set": {"revoked_at": _now()}}
    )
    return result.modified_count > 0


def revoke_saml_provider_sessions(provider_id: str) -> int:
    identity_ids = [
        item["_id"]
        for item in identities_collection.find(
            {"provider": f"saml:{provider_id}", "delete_at": None}, {"_id": 1}
        )
    ]
    if not identity_ids:
        return 0
    result = sessions_collection.update_many(
        {"identity_id": {"$in": identity_ids}, "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    return result.modified_count


def saml_metadata(provider: dict[str, Any], *, acs_url: str, metadata_url: str) -> str:
    try:
        settings = OneLogin_Saml2_Settings(saml_settings(provider, acs_url=acs_url, metadata_url=metadata_url))
        metadata = settings.get_sp_metadata()
        errors = settings.validate_metadata(metadata)
    except Exception as error:
        raise SAMLAuthError("Unable to generate SAML service provider metadata", status_code=500) from error
    if errors:
        raise SAMLAuthError("Generated SAML service provider metadata is invalid", status_code=500)
    return metadata.decode("utf-8") if isinstance(metadata, bytes) else str(metadata)
