# Local Knowledge vector search (Qdrant)

NexoraAI can use either Azure AI Search or Qdrant for the persistent Knowledge
index. This selection is independent from Knowledge object storage and MongoDB:

```text
KNOWLEDGE_STORAGE_PROVIDER=azure|minio
KNOWLEDGE_SEARCH_PROVIDER=azure|qdrant
APP_DATABASE_PROVIDER=cosmos|mongodb
```

Azure remains the default. Changing providers does not copy or migrate existing
documents; re-upload or explicitly re-index documents into the selected index.

## Start Qdrant

```bash
cp docs/local-vector.env.example .env.local-vector
docker compose --env-file .env.local-vector -f docker-compose.local-vector.yml up -d
```

Load the backend settings into the current shell before starting NexoraAI:

```bash
set -a
. ./.env.local-vector
set +a
app/start.sh
```

The default Compose ports listen only on `127.0.0.1`. The Qdrant dashboard is
available at `http://127.0.0.1:6333/dashboard`. No login is configured for this
loopback-only development setup.

## Embeddings

Qdrant stores vectors but does not create them. Configure one of NexoraAI's
existing embedding providers (Azure OpenAI, OpenAI, or OpenAI-compatible) and
keep `USE_VECTORS=true`. The configured embedding dimensions are used when the
collection is first created. If the dimensions later change, startup fails
instead of silently mixing incompatible vectors; use a new collection name or
perform an explicit re-index.

## Runtime behavior

- Existing Personal, Team, Global, and Data Group ACL payloads are stored on
  each Qdrant point and applied during retrieval and citation authorization.
- Unsupported filter expressions fail closed rather than running an unfiltered
  query.
- Qdrant supports vector retrieval plus a bounded lexical fallback. Azure-only
  semantic ranker, query rewriting, agentic retrieval, and Knowledge image
  vectors are disabled when Qdrant is selected.
- Agent image/vision input and OCR/document-processing routing are independent
  of the Knowledge search provider.

## Smoke test

1. Start Qdrant and the backend with `KNOWLEDGE_SEARCH_PROVIDER=qdrant`.
2. Upload one unique document in each enabled scope: Personal, a Team Data
   Group, and Global.
3. Wait until each job is **Indexed**, then ask for a unique phrase and open its
   citation.
4. Verify a user outside the Team/Data Group cannot retrieve or open that Team
   document.
5. Restart Qdrant and NexoraAI; repeat retrieval to verify persistence.
6. Delete each test file and confirm its content is no longer retrieved.

To return to Azure AI Search, unset the Qdrant variables and set:

```bash
export KNOWLEDGE_SEARCH_PROVIDER=azure
```

## Production notes

Do not expose the Compose ports publicly. For a remote or clustered Qdrant
deployment, enable an API key, TLS, backups/snapshots, monitoring, and network
policy. Store `QDRANT_API_KEY` only in the deployment secret store; never commit
it to Git.
