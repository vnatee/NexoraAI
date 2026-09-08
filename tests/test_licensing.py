from datetime import datetime, timezone

import pytest

from core.licensing import (
    LicenseClaimsError,
    evaluate_verified_claims,
    parse_verified_claims,
    unlicensed_evaluation,
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
