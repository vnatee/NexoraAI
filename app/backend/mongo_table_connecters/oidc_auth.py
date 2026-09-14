from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode, urlparse

import aiohttp
import jwt
from pymongo.errors import DuplicateKeyError

from mongo_table_connecters.identity_management import record_oidc_link_request
from mongo_table_connecters.mongo_connector import get_database

STATE_COLLECTION = "auth_oidc_states"
IDENTITY_COLLECTION = "auth_identities"
SESSION_COLLECTION = "auth_sessions"
OIDC_TOKEN_PREFIX = "nx_oidc_"
STATE_MINUTES = 10
SESSION_HOURS = 12
ALLOWED_SIGNING_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}

db = get_database()
states_collection = db[STATE_COLLECTION]
identities_collection = db[IDENTITY_COLLECTION]
sessions_collection = db[SESSION_COLLECTION]
users_collection = db["users"]


class OIDCAuthError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def oidc_provider_identity_key(settings: dict[str, Any]) -> str:
    provider_id = str(settings.get("_id") or "legacy")
    if provider_id == "legacy":
        return f"oidc:{_digest(str(settings.get('issuer') or settings.get('oidc_issuer') or '').rstrip('/'))[:24]}"
    return f"oidc:{provider_id}"


def _provider_key(settings: dict[str, Any]) -> str:
    return oidc_provider_identity_key(settings)


def ensure_oidc_auth_indexes() -> None:
    states_collection.create_index("state_digest", unique=True, name="auth_oidc_state")
    states_collection.create_index("expires_at", expireAfterSeconds=0, name="auth_oidc_state_expiry")


def _require_https_url(value: Any, field: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise OIDCAuthError(f"OIDC {field} must be an absolute HTTPS URL")
    return url


async def _json_request(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    _require_https_url(url, "endpoint")
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, url, **kwargs) as response:
                payload = await response.json(content_type=None)
                if response.status < 200 or response.status >= 300:
                    raise OIDCAuthError("The identity provider rejected the OIDC request", status_code=401)
                if not isinstance(payload, dict):
                    raise OIDCAuthError("The identity provider returned an invalid response", status_code=502)
                return payload
    except OIDCAuthError:
        raise
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        raise OIDCAuthError("Unable to contact the OIDC identity provider", status_code=502) from error


async def discover_oidc_provider(issuer: str) -> dict[str, Any]:
    issuer = _require_https_url(issuer, "issuer").rstrip("/")
    discovery = await _json_request("GET", f"{issuer}/.well-known/openid-configuration")
    if str(discovery.get("issuer") or "").rstrip("/") != issuer:
        raise OIDCAuthError("OIDC discovery issuer does not match the configured issuer", status_code=502)
    for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        _require_https_url(discovery.get(field), field.replace("_", " "))
    return discovery


async def begin_oidc_login(settings: dict[str, Any], redirect_uri: str) -> str:
    if settings.get("enabled", settings.get("oidc_enabled")) is not True:
        raise OIDCAuthError("OIDC authentication is not enabled", status_code=404)
    issuer = str(settings.get("issuer") or settings.get("oidc_issuer") or "").rstrip("/")
    client_id = str(settings.get("client_id") or settings.get("oidc_client_id") or "")
    discovery = await discover_oidc_provider(issuer)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
    now = _now()
    states_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "state_digest": _digest(state),
            "nonce": nonce,
            "code_verifier": code_verifier,
            "issuer": issuer,
            "provider_id": str(settings.get("_id") or "legacy"),
            "redirect_uri": redirect_uri,
            "created_at": now,
            "expires_at": now + timedelta(minutes=STATE_MINUTES),
        }
    )
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    separator = "&" if "?" in str(discovery["authorization_endpoint"]) else "?"
    return f"{discovery['authorization_endpoint']}{separator}{query}"


async def _exchange_code(
    settings: dict[str, Any], discovery: dict[str, Any], state_document: dict[str, Any], code: str
) -> dict[str, Any]:
    client_id = str(settings.get("client_id") or settings.get("oidc_client_id") or "")
    client_secret = str(settings.get("client_secret") or settings.get("oidc_client_secret") or "")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": state_document["redirect_uri"],
        "client_id": client_id,
        "code_verifier": state_document["code_verifier"],
    }
    headers: dict[str, str] = {"Accept": "application/json"}
    if settings.get("token_auth_method", settings.get("oidc_token_auth_method")) == "client_secret_post":
        data["client_secret"] = client_secret
    else:
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
    return await _json_request("POST", str(discovery["token_endpoint"]), data=data, headers=headers)


async def _validate_id_token(
    settings: dict[str, Any], discovery: dict[str, Any], id_token: str, nonce: str
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(id_token)
        algorithm = str(header.get("alg") or "")
        key_id = str(header.get("kid") or "")
        if algorithm not in ALLOWED_SIGNING_ALGORITHMS or not key_id:
            raise OIDCAuthError("OIDC ID token uses an unsupported signing key", status_code=401)
        jwks = await _json_request("GET", str(discovery["jwks_uri"]))
        key_data = next((item for item in jwks.get("keys", []) if str(item.get("kid")) == key_id), None)
        if not key_data:
            raise OIDCAuthError("OIDC ID token signing key was not found", status_code=401)
        claims = jwt.decode(
            id_token,
            key=jwt.PyJWK.from_dict(key_data, algorithm=algorithm).key,
            algorithms=[algorithm],
            audience=str(settings.get("client_id") or settings.get("oidc_client_id") or ""),
            issuer=str(settings.get("issuer") or settings.get("oidc_issuer") or "").rstrip("/"),
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except OIDCAuthError:
        raise
    except jwt.PyJWTError as error:
        raise OIDCAuthError("OIDC ID token validation failed", status_code=401) from error
    if not secrets.compare_digest(str(claims.get("nonce") or ""), nonce):
        raise OIDCAuthError("OIDC login nonce is invalid", status_code=401)
    return claims


def _allowed_email(settings: dict[str, Any], claims: dict[str, Any]) -> str:
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if "@" not in email or len(email) > 254:
        raise OIDCAuthError("The identity provider did not return a valid email address", status_code=403)
    if claims.get("email_verified") is False:
        raise OIDCAuthError("The identity provider did not verify this email address", status_code=403)
    allowed_domains = {
        str(item).lower()
        for item in (settings.get("allowed_domains") or settings.get("oidc_allowed_domains") or [])
    }
    jit_enabled = settings.get("jit_enabled", settings.get("oidc_jit_enabled")) is True
    if jit_enabled and not allowed_domains:
        raise OIDCAuthError("OIDC JIT provisioning requires an allowed email domain", status_code=403)
    if allowed_domains and email.rsplit("@", 1)[1] not in allowed_domains:
        raise OIDCAuthError("This email domain is not allowed to sign in", status_code=403)
    return email


def _identity_user(settings: dict[str, Any], claims: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    issuer = str(settings.get("issuer") or settings.get("oidc_issuer") or "").rstrip("/")
    subject = str(claims.get("sub") or "")
    if not subject or len(subject) > 512:
        raise OIDCAuthError("The identity provider returned an invalid subject identifier", status_code=401)
    provider = _provider_key(settings)
    identity = identities_collection.find_one(
        {"provider": provider, "username_normalized": subject, "delete_at": None}
    )
    if identity:
        user = users_collection.find_one({"_id": identity["user_id"], "delete_at": None, "active": True})
        if not user:
            raise OIDCAuthError("The application user is disabled or unavailable", status_code=403)
        return identity, user
    email = _allowed_email(settings, claims)
    # Email is display/contact data, not a federated identity key. Never attach
    # a new subject to an existing account merely because the email matches.
    existing_user = users_collection.find_one({"ad_email": email, "delete_at": None}, {"_id": 1})
    if existing_user:
        record_oidc_link_request(
            provider=provider,
            issuer=issuer,
            subject=subject,
            email=email,
            suggested_user_id=str(existing_user["_id"]),
        )
        raise OIDCAuthError(
            "An account with this email already exists; a System Administrator must approve the identity link",
            status_code=409,
        )
    if settings.get("jit_enabled", settings.get("oidc_jit_enabled")) is not True:
        raise OIDCAuthError("This OIDC identity has not been provisioned in NexoraAI", status_code=403)
    now = _now()
    user_id = str(uuid.uuid4())
    name = str(claims.get("name") or "").strip().split()
    user = {
        "_id": user_id,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
        "email": email,
        "ad_email": email,
        "first_name": str(claims.get("given_name") or (name[0] if name else "")).strip(),
        "last_name": str(claims.get("family_name") or (" ".join(name[1:]) if len(name) > 1 else "")).strip(),
        "employee_id": "",
        "tel": "",
        "active": True,
        "is_sys_admin": False,
        "created_by_auth_provider": "oidc",
    }
    identity = {
        "_id": str(uuid.uuid4()),
        "provider": provider,
        "issuer": issuer,
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
        raise OIDCAuthError("This OIDC identity is already linked", status_code=409) from error
    except Exception:
        users_collection.delete_one({"_id": user_id})
        identities_collection.delete_one({"_id": identity["_id"]})
        raise
    return identity, user


def _create_session(identity: dict[str, Any], user: dict[str, Any]) -> str:
    token = OIDC_TOKEN_PREFIX + secrets.token_urlsafe(32)
    now = _now()
    sessions_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "token_digest": _digest(token),
            "identity_id": identity["_id"],
            "user_id": user["_id"],
            "username": identity.get("username") or user.get("email"),
            "auth_provider": "oidc",
            "provider": identity.get("provider"),
            "created_at": now,
            "expires_at": now + timedelta(hours=SESSION_HOURS),
            "revoked_at": None,
        }
    )
    return token


async def complete_oidc_login(
    provider_loader: Callable[[str], dict[str, Any] | None], state: str, code: str
) -> tuple[str, dict[str, Any]]:
    state_document = states_collection.find_one_and_delete({"state_digest": _digest(state)})
    now = _now()
    expires_at = state_document.get("expires_at") if state_document else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not state_document or not expires_at or expires_at <= now:
        raise OIDCAuthError("OIDC login state is invalid or expired", status_code=401)
    settings = provider_loader(str(state_document.get("provider_id") or "legacy")) or {}
    issuer = str(settings.get("issuer") or settings.get("oidc_issuer") or "").rstrip("/")
    if settings.get("enabled", settings.get("oidc_enabled")) is not True or issuer != state_document.get("issuer"):
        raise OIDCAuthError("OIDC configuration changed during sign-in", status_code=401)
    discovery = await discover_oidc_provider(issuer)
    tokens = await _exchange_code(settings, discovery, state_document, code)
    id_token = str(tokens.get("id_token") or "")
    if not id_token:
        raise OIDCAuthError("The identity provider did not return an ID token", status_code=401)
    claims = await _validate_id_token(settings, discovery, id_token, str(state_document["nonce"]))
    _allowed_email(settings, claims)
    identity, user = _identity_user(settings, claims)
    identities_collection.update_one(
        {"_id": identity["_id"]}, {"$set": {"last_login_at": now, "updated_at": now}}
    )
    return _create_session(identity, user), user


def resolve_oidc_session(token: str) -> dict[str, Any]:
    if not token.startswith(OIDC_TOKEN_PREFIX):
        raise OIDCAuthError("Invalid OIDC session", status_code=401)
    session = sessions_collection.find_one({"token_digest": _digest(token), "revoked_at": None})
    now = _now()
    expires_at = session.get("expires_at") if session else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not session or not expires_at or expires_at <= now:
        raise OIDCAuthError("OIDC session has expired", status_code=401)
    identity = identities_collection.find_one({"_id": session["identity_id"], "delete_at": None, "active": True})
    user = users_collection.find_one({"_id": session["user_id"], "delete_at": None, "active": True})
    if not identity or not user:
        raise OIDCAuthError("The application user is disabled or unavailable", status_code=403)
    username = str(session.get("username") or user.get("email") or user["_id"])
    return {
        "auth_provider": "oidc",
        "sub": str(identity.get("subject") or identity["_id"]),
        "oid": str(user["_id"]),
        "application_user_id": str(user["_id"]),
        "preferred_username": username,
        "email": str(user.get("email") or username),
        "groups": [],
    }


def revoke_oidc_session(token: str) -> bool:
    result = sessions_collection.update_one(
        {"token_digest": _digest(token), "revoked_at": None}, {"$set": {"revoked_at": _now()}}
    )
    return result.modified_count > 0


def revoke_oidc_provider_sessions(provider_id: str, *, legacy_issuer: str = "") -> int:
    provider = str(provider_id or "")
    if provider == "legacy" and legacy_issuer:
        provider_key = f"oidc:{_digest(legacy_issuer.rstrip('/'))[:24]}"
    else:
        provider_key = provider if provider.startswith("oidc:") else f"oidc:{provider}"
    identity_ids = [
        item["_id"]
        for item in identities_collection.find(
            {"provider": provider_key, "delete_at": None}, {"_id": 1}
        )
    ]
    if not identity_ids:
        return 0
    result = sessions_collection.update_many(
        {"identity_id": {"$in": identity_ids}, "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    return result.modified_count
