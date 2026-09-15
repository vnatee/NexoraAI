# Contributing to NexoraAI

NexoraAI is maintained through reviewed feature branches. Before making a
change, open or reference an issue that describes the expected behavior,
security impact, and acceptance criteria.

## Development rules

- Never commit credentials, tokens, certificates, connection strings, customer
  documents, raw prompts, tool output, or copied production logs.
- Preserve application authorization, document ACLs, read-only database
  enforcement, guardrails, tool policy, and metadata-only audit contracts.
- Keep Azure behavior working when adding local or provider-neutral adapters.
- Add focused tests and avoid repository-wide formatting of legacy files.
- Document new configuration and operational requirements.

## Pull requests

1. Create a focused branch from the approved integration baseline.
2. Implement the smallest coherent change and add tests.
3. Run the service-free backend suite and frontend production build.
4. Update the handoff/manual/backlog when behavior or operations change.
5. Open a pull request with risk, migration, validation, and rollback notes.
6. Obtain maintainer review before merging. Security-sensitive changes require
   explicit review of authorization, secrets, audit, and failure behavior.

## Validation

```bash
.venv/bin/pytest -q --ignore=tests/test_app_config.py \
  -m 'not azure and not external and not data_integration'

cd app/frontend
npm run build:memory-safe
```

Additional provider or deployment tests may be required. See
[`docs/CODEX_HANDOFF.md`](docs/CODEX_HANDOFF.md) for current status.
