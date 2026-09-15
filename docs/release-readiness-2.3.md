# Release readiness — 2.3.0

This is the evidence and acceptance gate for the planned `2.3.0` release. The
application must continue to report `2.2.0` until every required production
gate below passes. Do not treat a successful build alone as release approval.

Candidate branch: `feature/mcp-catalog-navigation`

Candidate checkpoint: `698de34 feat: expand agent catalog and enterprise authentication`

## Completed evidence

- The service-free backend regression passed with `964 passed, 1 deselected`.
- The memory-safe TypeScript production build passed.
- The local application image rebuilt successfully and imported both
  `python3-saml` and `xmlsec`; the application container became healthy.
- Focused backup/TLS/SAML regression passed with `19 passed` on 2026-09-15.
- A real backup and destructive restore drill passed on 2026-09-15 in the
  isolated Compose project `nexora-p0-drill`. The drill:
  - used a separate Docker network and project-scoped volumes;
  - wrote unique test markers to MongoDB, MinIO, and Qdrant;
  - created and validated an archive with checksums and manifest version 1;
  - deleted all three markers before restore;
  - restored and verified all three markers; and
  - removed the disposable containers, volumes, network, and archive after
    verification. The active `nexoraai` project was not modified.

## Required production acceptance

### Deployment and upgrade

- [ ] Back up the deployed environment and validate the archive before upgrade.
- [ ] Preserve `APP_DATA_ENCRYPTION_KEY`, the license installation identity,
      object/vector configuration, and protected environment file.
- [ ] Pull the candidate commit, rebuild, and start with the same Compose
      overlays used by the deployment.
- [ ] Confirm every expected System Health component is healthy.
- [ ] Confirm existing Local users, Teams, Agents, integrations, Knowledge,
      citations, chat history, retention, quotas, and license status remain
      available.
- [ ] Run one new ingestion and one Chat request after upgrade.

### HTTPS ingress

- [ ] Validate the public certificate chain and hostname without `--insecure`.
- [ ] Confirm HTTP redirects to the exact HTTPS hostname.
- [ ] Confirm HSTS and the baseline browser security headers are present.
- [ ] Confirm sign-in, Chat streaming, upload/download, citations, and Draw.io
      artifacts work through HTTPS.
- [ ] Confirm MongoDB, MinIO API, Qdrant, Ollama, Integration Controller, and
      managed MCP services are not exposed publicly.

### SAML with a real identity provider

- [ ] Set `NEXORA_PUBLIC_URL` to the final HTTPS origin before copying SAML
      identifiers.
- [ ] Create a disabled SAML connection and register its generated ACS URL and
      SP Entity ID/Audience at the IdP.
- [ ] Map a stable email attribute and optional first/last-name attributes.
- [ ] Validate a new allowed-domain user through JIT provisioning and confirm
      the user receives no System Admin permission.
- [ ] Validate an existing-email collision creates an Identity Links review
      request instead of silently linking the identity.
- [ ] Approve the intended link and confirm sign-in succeeds.
- [ ] Disable the provider and confirm its Nexora sessions are revoked while a
      Local break-glass administrator can still sign in.

## Release decision

When every required item passes:

1. update the product version from `2.2.0` to `2.3.0`;
2. update release notes and manuals for the final labels and limitations;
3. run the service-free backend suite and production frontend build again;
4. create the release commit and tag `v2.3.0` only after approval.
