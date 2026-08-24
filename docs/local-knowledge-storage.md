# Local Knowledge object storage

NexoraAI can store Personal, Team, Global, and web-ingested Knowledge source
files in either Azure Blob/Data Lake or an S3-compatible MinIO service. The
selection is deployment-wide and does not change document ACLs, ingestion-job
ownership, routing rules, or citation authorization.

This slice replaces Knowledge **object storage only**. Azure AI Search remains
the document index and retrieval backend. A deployment using MinIO therefore
still needs its configured Azure AI Search service until a search-provider
adapter is introduced.

## Provider selection

The default remains Azure and requires no new setting:

```bash
KNOWLEDGE_STORAGE_PROVIDER=azure
```

To use MinIO:

```bash
KNOWLEDGE_STORAGE_PROVIDER=minio
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_SECURE=false
MINIO_ACCESS_KEY=<generated-access-key>
MINIO_SECRET_KEY=<generated-secret-key>
MINIO_KNOWLEDGE_BUCKET=nexora-knowledge
```

When the backend itself runs in Docker, use the MinIO service name rather than
the host loopback address:

```bash
MINIO_ENDPOINT=minio:9000
```

`MINIO_ENDPOINT` accepts a host and port or an HTTP(S) URL. Set
`MINIO_SECURE=true` for a TLS-enabled external MinIO endpoint. Never commit the
credentials or place them in a frontend environment variable.

## Start MinIO locally

Copy the non-secret template and generate two different credentials:

```bash
cp docs/local-storage.env.example .env.local-storage
openssl rand -hex 24
openssl rand -hex 32
```

Replace both placeholders in `.env.local-storage`, then start the service:

```bash
docker compose --env-file .env.local-storage -f docker-compose.local-storage.yml up -d minio
docker compose --env-file .env.local-storage -f docker-compose.local-storage.yml ps
```

Load the same variables before starting a backend running on the host:

```bash
set -a
. ./.env.local-storage
set +a
app/start.sh
```

The API and console ports bind to `127.0.0.1` by default. Do not expose the
console publicly. For production, create a least-privilege application account,
enable TLS, restrict network access, and keep the bucket private.

Stop MinIO without deleting its data:

```bash
docker compose --env-file .env.local-storage -f docker-compose.local-storage.yml down
```

The `nexora_minio_data` named volume persists source files. Do not use
`down --volumes` for a deployment whose data must be retained.

## Storage layout and behavior

One private bucket contains isolated prefixes:

```text
personal/<user-id>/<filename>
team/<team-id>/<filename>
global/<filename>
web_team/<team-id>/<source-path>
web_global/<source-path>
```

The backend remains the authorization boundary. It resolves Personal/Team/
Global access before retrieving a source and never gives the browser direct
MinIO credentials. Team object tags retain processing status and Data Group
associations, matching the existing Azure behavior.

Azure Knowledge image-vector retrieval is Azure-only in this slice and is
disabled when MinIO is selected. Agent message image input and document OCR are
separate features and continue to depend on the selected LLM and document
processing provider.

## Verification

After MinIO is healthy and the backend is running:

1. Open the application configuration endpoint and confirm
   `knowledgeStorageProvider` is `minio`.
2. Upload one small document in each enabled scope: Personal, Team, and Global.
3. Wait for each job to reach Indexed, then refresh the page and restart the
   backend. Confirm the files and indexed timestamps remain visible.
4. Ask a permitted Agent a question that cites each document. Open each
   citation and confirm the correct source is returned.
5. Verify a user outside the Team/Data Group receives no search result and
   cannot open the Team citation directly.
6. Delete the test documents and confirm both their search sections and stored
   objects are removed.
7. Restart MinIO without deleting the named volume and repeat one citation.

## Switching and migration

Changing `KNOWLEDGE_STORAGE_PROVIDER` does not copy existing objects. Azure and
MinIO can be selected independently per deployment, but one running backend
uses one Knowledge object provider at a time. Re-index source documents after
copying them to a different provider so indexed storage URLs, processing
metadata, and citations remain consistent. Test backup and restore procedures
before production cutover.
