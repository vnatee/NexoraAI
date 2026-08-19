# Migration testing

This test matrix protects existing behavior while the Azure-dependent application is migrated to a self-hosted stack.

## Test levels

| Level | Purpose | External services |
| --- | --- | --- |
| Fast unit | Authentication filters, parsers, splitting, configuration | None |
| Data integration | Parse and chunk the mutable files under `data/` | None, but results depend on repository data |
| Application integration | Quart routes with mocked Azure/OpenAI clients | None after test fixtures are initialized |
| External integration | Verify real storage, vector store, model, and database adapters | Required |
| End-to-end | Browser flows for login, upload, search, chat, and administration | Full test stack |

## Commands

Run the fast baseline in the Dev Container:

```bash
.venv/bin/python -m pytest -q -m "not data_integration and not external_integration" \
  tests/test_authenticationhelper.py \
  tests/test_mongo_connector_config.py \
  tests/test_textparser.py \
  tests/test_jsonparser.py \
  tests/test_csvparser.py \
  tests/test_prepdocslib_textsplitter.py
```

Run repository-data parsing tests explicitly:

```bash
.venv/bin/python -m pytest -q -m data_integration
```

Run the complete Python suite:

```bash
.venv/bin/python -m pytest
```

## Critical migration contracts

Every migration slice must preserve these contracts until an intentional API version change is approved:

- A user cannot search or download another user's personal document.
- A user cannot search or download a team document without membership in an allowed data group.
- Global documents are available only when the selected scope and server policy allow them.
- Management permissions are enforced by the backend, not only by hidden UI controls.
- Agent model settings do not affect other agents.
- Upload, delete, re-index, and citation paths refer to the same stored object.
- Tool executions are restricted to tools bound to the selected agent and are recorded in an audit log.

## Migration gate

A slice is complete only when its unit and contract tests pass, persistent data survives a container restart, and the previous implementation remains available behind a temporary configuration switch until acceptance testing is complete.

## Baseline recorded on 2026-08-18

The focused fast baseline passes with `49 passed, 1 deselected`. It includes legacy Entra ACL behavior, custom personal/global/data-group filters, citation path filtering, parser tests, and standard local MongoDB URI configuration.

The broader service-free Python suite now passes with `338 passed, 1 deselected`:

```bash
.venv/bin/python -m pytest -q -m "not data_integration and not external_integration"
```

The frontend also passes `npx tsc --noEmit` and its production bundle builds with:

```bash
NODE_OPTIONS=--max-old-space-size=4096 npm run build
```

The larger heap is currently needed because the bundle transforms more than 6,000 modules and the default Node heap is exhausted during Rollup rendering. Vite also reports the existing large vendor chunk as a non-blocking optimization warning.
