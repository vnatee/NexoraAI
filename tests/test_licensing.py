import base64
import json
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.licensing import (
    LicenseClaimsError,
    LicenseVerificationError,
    evaluate_verified_claims,
    load_verification_keys,
    parse_verified_claims,
    unlicensed_evaluation,
    verify_license_key,
)


def _payload(**overrides):
    payload = {
        "schema_version": 1,
        "license_id": "lic-001",
        "customer_id": "customer-001",
        "product": "nexoraai",
        "edition": "enterprise",
        "issuer": "nexora",
        "key_id": "signing-key-2026-01",
        "not_before": "2026-01-01T00:00:00Z",
        "expires_at": "2026-12-31T23:59:59Z",
        "grace_days": 14,
        "features": {"mcp": True, "document.ocr": False},
        "capacities": {"users": 100, "teams": 10, "ha_replicas": None},
        "installation_id": "installation-001",
    }
    payload.update(overrides)
    return payload


def test_parse_verified_claims_normalizes_safe_versioned_claims():
    claims = parse_verified_claims(_payload())

    assert claims.schema_version == 1
    assert claims.product == "nexoraai"
    assert claims.not_before == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert claims.features == {"mcp": True, "document.ocr": False}
    assert claims.capacities["ha_replicas"] is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"schema_version": 2}, "unsupported license schema"),
        ({"product": "another-product"}, "does not match"),
        ({"expires_at": "2025-12-31T00:00:00Z"}, "later than"),
        ({"not_before": "2026-01-01T00:00:00"}, "timezone"),
        ({"grace_days": 91}, "grace_days"),
        ({"features": {"MCP": True}}, "feature names"),
        ({"capacities": {"users": True}}, "capacity values"),
        ({"installation_id": ""}, "installation_id"),
        ({"customer_id": 123}, "customer_id"),
        ({"unexpected": "claim"}, "unsupported fields"),
    ],
)
def test_invalid_claims_fail_closed(overrides, message):
    with pytest.raises(LicenseClaimsError, match=message):
        parse_verified_claims(_payload(**overrides))


@pytest.mark.parametrize(
    ("instant", "state", "reason"),
    [
        ("2025-12-31T23:59:59+00:00", "invalid", "not_yet_valid"),
        ("2026-06-01T00:00:00+00:00", "active", "within_validity_period"),
        ("2027-01-07T00:00:00+00:00", "grace", "within_grace_period"),
        ("2027-01-15T00:00:00+00:00", "expired", "validity_and_grace_elapsed"),
    ],
)
def test_time_states_are_deterministic(instant, state, reason):
    claims = parse_verified_claims(_payload())
    result = evaluate_verified_claims(
        claims,
        installation_id="installation-001",
        now=datetime.fromisoformat(instant),
    )

    assert result.state == state
    assert result.reason == reason


def test_revocation_precedes_time_and_installation_checks():
    claims = parse_verified_claims(_payload())
    result = evaluate_verified_claims(
        claims,
        installation_id="another-installation",
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        revoked_license_ids=frozenset({"lic-001"}),
    )

    assert result.state == "revoked"


def test_installation_binding_mismatch_is_invalid():
    claims = parse_verified_claims(_payload())
    result = evaluate_verified_claims(
        claims,
        installation_id="another-installation",
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert result.state == "invalid"
    assert result.reason == "installation_mismatch"


def test_unbound_license_can_be_evaluated_for_an_installation():
    claims = parse_verified_claims(_payload(installation_id=None))
    result = evaluate_verified_claims(
        claims,
        installation_id="installation-002",
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert result.state == "active"


def test_missing_license_has_explicit_unlicensed_state():
    result = unlicensed_evaluation(now=datetime(2026, 6, 1, tzinfo=timezone.utc))

    assert result.state == "unlicensed"
    assert result.claims is None


def test_naive_evaluation_time_is_rejected():
    claims = parse_verified_claims(_payload())

    with pytest.raises(LicenseClaimsError, match="timezone"):
        evaluate_verified_claims(claims, installation_id="installation-001", now=datetime(2026, 6, 1))


def _signed_license(payload=None):
    private_key = Ed25519PrivateKey.generate()
    value = payload or _payload()
    encoded = base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signature = base64.urlsafe_b64encode(private_key.sign(encoded.encode("ascii"))).rstrip(b"=").decode("ascii")
    return f"NX1.{encoded}.{signature}", private_key.public_key()


def test_signed_license_is_verified_before_claims_are_parsed():
    license_key, public_key = _signed_license()

    claims = verify_license_key(license_key, {"signing-key-2026-01": public_key})

    assert claims.license_id == "lic-001"
    assert claims.installation_id == "installation-001"


def test_tampered_and_untrusted_signed_licenses_are_rejected():
    license_key, public_key = _signed_license()
    prefix, payload, signature = license_key.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{prefix}.{payload}.{replacement}{signature[1:]}"

    with pytest.raises(LicenseVerificationError, match="signature"):
        verify_license_key(tampered, {"signing-key-2026-01": public_key})
    with pytest.raises(LicenseVerificationError, match="not trusted"):
        verify_license_key(license_key, {})


def test_public_key_directory_allows_rotation_and_rejects_wrong_key_types(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

    public_key = Ed25519PrivateKey.generate().public_key()
    (tmp_path / "key-2026.pem").write_bytes(
        public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    assert load_verification_keys(tmp_path)["key-2026"]

    bad_directory = tmp_path / "bad"
    bad_directory.mkdir()
    rsa_public_key = generate_private_key(public_exponent=65537, key_size=2048).public_key()
    (bad_directory / "rsa.pem").write_bytes(
        rsa_public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    with pytest.raises(LicenseVerificationError, match="Ed25519"):
        load_verification_keys(bad_directory)
