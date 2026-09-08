# Product licensing and entitlements

NexoraAI licensing is a separate layer from operational usage quotas. A license
answers which features and maximum capacities a deployment is entitled to use;
System, Team, and User quota policies continue to control consumption within
those entitlements. License processing must never rewrite quota configuration.

## Phase 1: schema and evaluator

`core/licensing.py` defines the first versioned claims model and deterministic
state evaluator. This phase intentionally has no runtime enforcement, license
upload endpoint, persistence, UI, or signing key. Existing installations remain
fully functional and are reported by the model as `unlicensed` only when a
future caller explicitly asks for that state.

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
to it as trusted input. The next slice must authenticate the complete license
document with an asymmetric signature before parsing claims.

## Next slices

1. Generate and persist one stable installation ID that survives container and
   host restarts, backup/restore, and HA replicas.
2. Define a signed envelope and verify it against a configured rotating public
   key set. Vendor private signing keys must never enter this repository or a
   customer deployment.
3. Store only the verified license document through protected System Admin
   import/status APIs and add a License page. Never return or log the raw
   document after import.
4. Add backend feature/capacity checks in audit mode, compare them with current
   usage, and expose safe audit metadata before enabling enforcement.
5. Define grace/read-only behavior, renewal, re-host, clock rollback, backup,
   recovery, and optional online revocation workflows. Expiry must never delete
   customer data or disable security, backup/export, or license administration.
6. Inventory third-party packages, images, fonts, icons, and MCP components;
   generate an SBOM and customer-facing third-party notices before commercial
   distribution.

Offline deployments must not make hidden activation or telemetry calls. If an
online activation service is added, the Portal and documentation must state
exactly which metadata leaves the deployment.
