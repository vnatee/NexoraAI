import json
import stat

from core.licensing import load_verification_keys, verify_license_key

from scripts.license_key_tool import generate_keypair, issue_license


def test_vendor_tool_generates_keypair_and_issues_compatible_license(tmp_path):
    private_key = tmp_path / "vendor-private.pem"
    public_directory = tmp_path / "public"
    public_key = public_directory / "vendor-2026.pem"
    claims = tmp_path / "claims.json"
    output = tmp_path / "customer.nxlicense"
    claims.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "license_id": "license-001",
                "customer_id": "customer-001",
                "product": "nexoraai",
                "edition": "enterprise",
                "issuer": "nexora",
                "key_id": "vendor-2026",
                "not_before": "2026-09-01T00:00:00Z",
                "expires_at": "2027-09-01T00:00:00Z",
                "grace_days": 14,
                "features": {"mcp": True},
                "capacities": {"users": 100},
                "installation_id": "installation-001",
            }
        ),
        encoding="utf-8",
    )

    generate_keypair(private_key, public_key)
    issue_license(private_key, claims, output)
    verified = verify_license_key(output.read_text(encoding="utf-8"), load_verification_keys(public_directory))

    assert verified.license_id == "license-001"
    assert stat.S_IMODE(private_key.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
