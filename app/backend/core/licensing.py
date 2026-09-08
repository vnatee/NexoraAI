"""Signed product-entitlement claims and deterministic state evaluation.

NX1 imports are authenticated with trusted Ed25519 public keys before claims
are parsed. Enforcement remains separate so callers can evaluate and display
entitlements without accidentally turning this module into an authorization
boundary.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PRODUCT_ID = "nexoraai"
SUPPORTED_SCHEMA_VERSION = 1
MAX_CLAIM_ENTRIES = 128
MAX_GRACE_DAYS = 90
MAX_LICENSE_KEY_BYTES = 64 * 1024
LICENSE_KEY_PREFIX = "NX1"

LicenseState = Literal["unlicensed", "active", "grace", "expired", "revoked", "invalid"]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ENTITLEMENT_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_CLAIM_FIELDS = frozenset(
    {
        "schema_version",
        "license_id",
        "customer_id",
        "product",
        "edition",
        "issuer",
        "key_id",
        "not_before",
        "expires_at",
        "grace_days",
        "features",
        "capacities",
        "installation_id",
    }
)


class LicenseClaimsError(ValueError):
    """Raised when a verified document does not match the claims schema."""


class LicenseVerificationError(ValueError):
    """Raised when a signed license cannot be authenticated safely."""


@dataclass(frozen=True)
class EntitlementClaims:
    schema_version: int
    license_id: str
    customer_id: str
    product: str
    edition: str
    issuer: str
    key_id: str
    not_before: datetime
    expires_at: datetime
    grace_days: int
    features: Mapping[str, bool]
    capacities: Mapping[str, int | None]
    installation_id: str | None = None


@dataclass(frozen=True)
class LicenseEvaluation:
    state: LicenseState
    reason: str
    evaluated_at: datetime
    claims: EntitlementClaims | None = None


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise LicenseClaimsError(f"{field} must be a valid bounded identifier")
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise LicenseClaimsError(f"{field} must be a valid bounded identifier")
    return normalized


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LicenseClaimsError(f"{field} must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise LicenseClaimsError(f"{field} must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LicenseClaimsError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _feature_claims(value: Any) -> Mapping[str, bool]:
    if not isinstance(value, dict) or len(value) > MAX_CLAIM_ENTRIES:
        raise LicenseClaimsError("features must be a bounded object")
    normalized: dict[str, bool] = {}
    for key, enabled in value.items():
        if not isinstance(key, str) or not _ENTITLEMENT_KEY.fullmatch(key):
            raise LicenseClaimsError("feature names must be valid entitlement keys")
        if not isinstance(enabled, bool):
            raise LicenseClaimsError("feature values must be boolean")
        normalized[key] = enabled
    return MappingProxyType(normalized)


def _capacity_claims(value: Any) -> Mapping[str, int | None]:
    if not isinstance(value, dict) or len(value) > MAX_CLAIM_ENTRIES:
        raise LicenseClaimsError("capacities must be a bounded object")
    normalized: dict[str, int | None] = {}
    for key, capacity in value.items():
        if not isinstance(key, str) or not _ENTITLEMENT_KEY.fullmatch(key):
            raise LicenseClaimsError("capacity names must be valid entitlement keys")
        if capacity is not None and (isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0):
            raise LicenseClaimsError("capacity values must be non-negative integers or null")
        normalized[key] = capacity
    return MappingProxyType(normalized)


def parse_verified_claims(payload: Mapping[str, Any]) -> EntitlementClaims:
    """Validate claims only after a caller has authenticated the document.

    This function performs no cryptographic verification. Keeping that fact in
    the API name makes it harder to accidentally treat arbitrary JSON as a
    trusted license in a later persistence or Portal slice.
    """

    if not isinstance(payload, Mapping):
        raise LicenseClaimsError("license claims must be an object")
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise LicenseClaimsError("unsupported license schema version")
    if set(payload) - _CLAIM_FIELDS:
        raise LicenseClaimsError("license claims contain unsupported fields")

    product = _identifier(payload.get("product"), "product")
    if product != PRODUCT_ID:
        raise LicenseClaimsError("license product does not match NexoraAI")

    not_before = _timestamp(payload.get("not_before"), "not_before")
    expires_at = _timestamp(payload.get("expires_at"), "expires_at")
    if expires_at <= not_before:
        raise LicenseClaimsError("expires_at must be later than not_before")

    grace_days = payload.get("grace_days", 0)
    if isinstance(grace_days, bool) or not isinstance(grace_days, int) or not 0 <= grace_days <= MAX_GRACE_DAYS:
        raise LicenseClaimsError(f"grace_days must be between 0 and {MAX_GRACE_DAYS}")

    installation_value = payload.get("installation_id")
    installation_id = None if installation_value is None else _identifier(installation_value, "installation_id")

    return EntitlementClaims(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        license_id=_identifier(payload.get("license_id"), "license_id"),
        customer_id=_identifier(payload.get("customer_id"), "customer_id"),
        product=product,
        edition=_identifier(payload.get("edition"), "edition"),
        issuer=_identifier(payload.get("issuer"), "issuer"),
        key_id=_identifier(payload.get("key_id"), "key_id"),
        not_before=not_before,
        expires_at=expires_at,
        grace_days=grace_days,
        features=_feature_claims(payload.get("features", {})),
        capacities=_capacity_claims(payload.get("capacities", {})),
        installation_id=installation_id,
    )


def load_verification_keys(directory: str | Path | None) -> Mapping[str, Ed25519PublicKey]:
    """Load bounded Ed25519 public keys indexed by their filename stem."""

    if not directory:
        return MappingProxyType({})
    path = Path(directory)
    if not path.is_dir():
        raise LicenseVerificationError("license verification key directory is unavailable")
    key_files = sorted(path.glob("*.pem"))
    if len(key_files) > 16:
        raise LicenseVerificationError("license verification key directory contains too many PEM keys")

    keys: dict[str, Ed25519PublicKey] = {}
    for key_file in key_files:
        key_id = _identifier(key_file.stem, "key_id")
        encoded = key_file.read_bytes()
        if len(encoded) > 16 * 1024:
            raise LicenseVerificationError("license verification key file is too large")
        try:
            public_key = serialization.load_pem_public_key(encoded)
        except (TypeError, ValueError) as error:
            raise LicenseVerificationError("license verification key is invalid") from error
        if not isinstance(public_key, Ed25519PublicKey):
            raise LicenseVerificationError("license verification key must use Ed25519")
        keys[key_id] = public_key
    return MappingProxyType(keys)


def verify_license_key(
    license_key: str,
    verification_keys: Mapping[str, Ed25519PublicKey],
) -> EntitlementClaims:
    """Authenticate an NX1 license and then validate its claims."""

    if not isinstance(license_key, str) or not license_key.strip():
        raise LicenseVerificationError("license key is required")
    normalized = license_key.strip()
    if len(normalized.encode("utf-8")) > MAX_LICENSE_KEY_BYTES:
        raise LicenseVerificationError("license key is too large")
    parts = normalized.split(".")
    if len(parts) != 3 or parts[0] != LICENSE_KEY_PREFIX:
        raise LicenseVerificationError("license key format is invalid")
    try:
        payload_bytes = _decode_base64url(parts[1])
        signature = _decode_base64url(parts[2])
        payload = json.loads(payload_bytes.decode("utf-8"), object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise LicenseVerificationError("license key payload is invalid") from error
    if not isinstance(payload, dict):
        raise LicenseVerificationError("license key payload is invalid")

    key_id = payload.get("key_id")
    if not isinstance(key_id, str) or not _IDENTIFIER.fullmatch(key_id):
        raise LicenseVerificationError("license key ID is invalid")
    public_key = verification_keys.get(key_id)
    if public_key is None:
        raise LicenseVerificationError("license signing key is not trusted")
    try:
        public_key.verify(signature, parts[1].encode("ascii"))
    except (InvalidSignature, ValueError) as error:
        raise LicenseVerificationError("license signature is invalid") from error
    try:
        return parse_verified_claims(payload)
    except LicenseClaimsError as error:
        raise LicenseVerificationError(str(error)) from error


def _decode_base64url(value: str) -> bytes:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("invalid base64url")
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def unlicensed_evaluation(*, now: datetime | None = None) -> LicenseEvaluation:
    evaluated_at = _evaluation_time(now)
    return LicenseEvaluation(state="unlicensed", reason="license_not_installed", evaluated_at=evaluated_at)


def evaluate_verified_claims(
    claims: EntitlementClaims,
    *,
    installation_id: str,
    now: datetime | None = None,
    revoked_license_ids: frozenset[str] = frozenset(),
) -> LicenseEvaluation:
    """Evaluate authenticated claims without applying feature gates."""

    evaluated_at = _evaluation_time(now)
    current_installation = _identifier(installation_id, "installation_id")

    if claims.license_id in revoked_license_ids:
        return LicenseEvaluation("revoked", "license_revoked", evaluated_at, claims)
    if claims.installation_id is not None and claims.installation_id != current_installation:
        return LicenseEvaluation("invalid", "installation_mismatch", evaluated_at, claims)
    if evaluated_at < claims.not_before:
        return LicenseEvaluation("invalid", "not_yet_valid", evaluated_at, claims)
    if evaluated_at <= claims.expires_at:
        return LicenseEvaluation("active", "within_validity_period", evaluated_at, claims)
    if evaluated_at <= claims.expires_at + timedelta(days=claims.grace_days):
        return LicenseEvaluation("grace", "within_grace_period", evaluated_at, claims)
    return LicenseEvaluation("expired", "validity_and_grace_elapsed", evaluated_at, claims)


def _evaluation_time(value: datetime | None) -> datetime:
    evaluated_at = value or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise LicenseClaimsError("evaluation time must include a timezone")
    return evaluated_at.astimezone(timezone.utc)
