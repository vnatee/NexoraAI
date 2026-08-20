# NexoraAI agent instructions

Read `docs/CODEX_HANDOFF.md` before changing this repository. It is the current
source of truth for product decisions, implemented slices, known limitations,
validation status, and the recommended next work.

- Preserve the dirty working tree. Changes after checkpoint `fba5481` belong to
  the current migration and must not be discarded or broadly reformatted.
- Keep Azure behavior working while provider interfaces are introduced for
  local/container operation.
- Do not commit credentials, service-account JSON, tokens, connection strings,
  raw prompts, tool outputs, or copied chat logs.
- Store application secrets only through the existing Fernet helpers and keep
  `APP_DATA_ENCRYPTION_KEY` stable across replicas and restarts.
- Use `apply_patch` for focused edits. Avoid repository-wide formatters because
  several legacy frontend files have large line-ending/formatting diffs.
- Add focused tests for each migration slice and run the service-free Python
  suite plus TypeScript/production build before handoff.
- Management authorization, personal/team/global document ACLs, read-only
  database enforcement, tool policy, and audit metadata are security contracts;
  do not weaken them for convenience.

Typical validation commands are listed in `docs/CODEX_HANDOFF.md`.

