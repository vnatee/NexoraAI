# Embedding profiles

NexoraAI supports multiple saved embedding configurations with one active
profile for the whole Knowledge index. This Phase 1 design avoids mixing
incompatible vector spaces when a document belongs to multiple Data Groups or
a query spans Personal, Team, and Global Knowledge.

System administrators manage profiles in **Administration → Embedding
profiles**. The environment configuration is always shown as a read-only
fallback. Managed profiles support Azure OpenAI, OpenAI, and OpenAI-compatible
services such as the bundled Ollama server.

Each profile defines:

- provider endpoint and encrypted API key, when required;
- model and Azure deployment name;
- vector dimensions; and
- a unique Qdrant collection.

API keys are encrypted with `APP_DATA_ENCRYPTION_KEY` and are never returned to
the browser. Keep that Fernet key stable across application replicas and
restarts.

## Activation workflow

1. Add the profile with a collection that is not used by another profile.
2. Select **Test** and confirm that the provider returns exactly the configured
   number of dimensions.
3. Select **Activate**. This records the desired system profile but does not
   hot-swap in-flight indexing or retrieval.
4. Restart the application container. The startup path loads the active
   profile, validates or creates its Qdrant collection, and records it as the
   running profile.
5. Re-upload or explicitly re-index every Personal, Team, Global, and web
   Knowledge source. Existing vectors are not copied or converted.
6. After validating ingestion, retrieval, citations, and ACL isolation, select
   **Mark re-index complete**.

The Portal keeps separate `Selected` and `Running` indicators. A restart
warning remains visible while those values differ, and a re-index warning
remains visible until an administrator explicitly confirms completion.

Deleting a profile never deletes its Qdrant collection. This prevents an
administrative UI action from destroying vectors; obsolete collections must be
removed through a separately controlled operational procedure.

## Current limitation

Phase 1 uses one active embedding profile system-wide. Per-Data Group profiles
would require duplicate indexing for documents assigned to multiple groups and
a defined rank-fusion strategy for queries spanning different vector spaces.
That behavior is intentionally deferred.
