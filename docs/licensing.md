# Product licensing and entitlements

NexoraAI licensing is a separate layer from operational usage quotas. A license
answers which features and maximum capacities a deployment is entitled to use;
System, Team, and User quota policies continue to control consumption within
those entitlements. License processing must never rewrite quota configuration.

## Implemented foundation

`core/licensing.py` defines the first versioned claims model and deterministic
state evaluator. The current implementation remains in audit mode: it does not
block runtime features, and existing installations remain fully functional.

The version 1 claims are:

| Claim | Purpose |
| --- | --- |
| `schema_version` | Exact supported schema version; currently `1` |
| `license_id` | Stable subscription/license identifier |
| `customer_id` | Stable customer identifier |
| `product` | Must be `nexoraai` |
| `edition` | Commercial edition identifier |
| `issuer` / `key_id` | Issuer and public-key rotation identifiers |
| `not_before` / `expires_at` | Timezone-aware ISO 8601 validity window |
| `grace_days` | Post-expiry grace duration, from 0 through 90 days |
| `features` | Bounded feature-name to boolean entitlement map |
| `capacities` | Bounded capacity-name to non-negative integer map; `null` means unlimited |
| `installation_id` | Optional stable installation binding |

Evaluation produces `unlicensed`, `active`, `grace`, `expired`, `revoked`, or
`invalid`, with a controlled reason code. Revocation takes precedence;
installation mismatch and a future `not_before` value fail closed as invalid.
UTC normalization makes boundary tests deterministic.

The parser is deliberately named `parse_verified_claims`: it validates schema
but performs no cryptographic verification. Arbitrary JSON must never be passed
to it as trusted input. The import path authenticates the complete NX1 document
with Ed25519 before passing its payload to this parser.

## Installation identity and Trial

Opening **System administration → License** creates one random Installation ID
in the `application_settings` collection. It survives application/container
restarts and is included in the normal MongoDB backup. It is not derived from a
MAC address, hostname, or ephemeral container ID.

A System Administrator may start the Trial once. Its timestamps are stored
atomically and it lasts exactly 14 days with no grace period. Restarting
containers does not restart it. Deleting or replacing the entire MongoDB
deployment can reset local state; preventing deliberate offline database
rollback requires a future activation service or trusted external state.

## Vendor key generation

Run the issuer tool only on a protected Nexora/vendor workstation. Never run it
inside a customer application container and never put the private key in this
repository:

```bash
.venv/bin/python scripts/license_key_tool.py generate-keypair \
  --private-key /secure/nexora-license/vendor-2026-private.pem \
  --public-key /tmp/vendor-2026.pem
```

Copy only `vendor-2026.pem` into the deployment's
`deploy/license-public-keys/` directory. PEM files in that directory are
Git-ignored and mounted read-only into the application. The filename stem must
equal the license claim's `key_id`. Retain old public keys while licenses signed
with them are still valid.

Create a claims file outside the repository:

```json
{
  "schema_version": 1,
  "license_id": "LIC-2026-0001",
  "customer_id": "CUSTOMER-001",
  "product": "nexoraai",
  "edition": "enterprise",
  "issuer": "nexora",
  "key_id": "vendor-2026",
  "not_before": "2026-09-08T00:00:00Z",
  "expires_at": "2027-09-07T23:59:59Z",
  "grace_days": 14,
  "features": {
    "mcp": true,
    "ocr": true,
    "langgraph": true,
    "dashboards": true,
    "api_access": false
  },
  "capacities": {
    "users": 100,
    "teams": 10,
    "agents": 50,
    "ha_replicas": 2
  },
  "installation_id": "COPY-FROM-THE-CUSTOMER-LICENSE-PAGE"
}
```

Issue the license into a new mode-0600 file:

```bash
.venv/bin/python scripts/license_key_tool.py issue \
  --private-key /secure/nexora-license/vendor-2026-private.pem \
  --claims /secure/nexora-license/customer-001.json \
  --output /secure/nexora-license/customer-001.nxlicense
```

The resulting `NX1.<payload>.<signature>` value may be imported only by a System
Administrator. The backend validates the signature, schema, dates, product, and
Installation ID, encrypts the raw key with `APP_DATA_ENCRYPTION_KEY`, and returns
only safe claims. Import and Trial actions create 365-day metadata-only audit
events without the raw key.

## Next slices

1. Add backend feature/capacity checks in audit mode, compare them with current
   usage, and expose safe audit metadata before enabling enforcement.
2. Define grace/read-only behavior, renewal, re-host, clock rollback, backup,
   recovery, and optional online revocation workflows. Expiry must never delete
   customer data or disable security, backup/export, or license administration.
3. Inventory third-party packages, images, fonts, icons, and MCP components;
   generate an SBOM and customer-facing third-party notices before commercial
   distribution.

Offline deployments must not make hidden activation or telemetry calls. If an
online activation service is added, the Portal and documentation must state
exactly which metadata leaves the deployment.
