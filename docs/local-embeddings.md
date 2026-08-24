# Local text embeddings with Ollama and BGE-M3

NexoraAI can create Knowledge query and document embeddings locally through
Ollama's OpenAI-compatible API. The recommended multilingual baseline is
`bge-m3`, which produces fixed 1024-dimensional dense vectors and works well
for mixed Thai and English documents.

Azure OpenAI and OpenAI remain supported. Chat completion and text embedding
providers are independent, so enabling this service does not require changing
the LLM used by an Agent.

## Requirements

- Docker with at least 4 GB of memory available for a CPU development smoke
  test. More memory and an NVIDIA GPU are recommended for sustained ingestion.
- A vector index configured for 1024 dimensions. The local Qdrant setup is
  documented in [local-vector-search.md](local-vector-search.md).

## Start Ollama and install BGE-M3

Create an untracked environment file:

```bash
cp docs/local-embedding.env.example .env.local-embedding
```

Start the persistent Ollama service, then run the one-shot model installer:

```bash
docker compose --env-file .env.local-embedding \
  -f docker-compose.local-embedding.yml up -d --wait ollama
docker compose --env-file .env.local-embedding \
  -f docker-compose.local-embedding.yml run --rm ollama-model
```

The model is stored in the `nexora_ollama_data` named volume and remains
available after container restarts. The API listens only on
`127.0.0.1:11434` by default.

Verify the OpenAI-compatible endpoint with synthetic text:

```bash
curl http://127.0.0.1:11434/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"bge-m3","input":"NexoraAI embedding smoke test"}'
```

## Start NexoraAI

Load the embedding settings after the Qdrant settings so the dedicated
1024-dimensional collection name takes precedence:

```bash
set -a
. ./.env.local-vector
. ./.env.local-embedding
set +a
app/start.sh
```

The relevant values are:

```text
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSIONS=1024
QDRANT_COLLECTION=nexora-knowledge-bge-m3
```

When the backend itself runs in the same Compose network, override the base URL
with `http://ollama:11434/v1` instead of the host loopback address.

## Re-index and validate

Embedding vectors from different models are not interchangeable. Do not point
BGE-M3 at a collection created for an OpenAI/Azure embedding model, even if a
provider supports configurable output dimensions. Use the new collection and
re-index the source documents.

1. Upload one unique Personal, Team/Data Group, and Global document.
2. Wait until all three ingestion jobs report **Indexed**.
3. Retrieve a unique phrase from each permitted scope and open its citation.
4. Confirm another user outside the Team/Data Group cannot retrieve or open the
   Team document.
5. Restart Ollama, Qdrant, and NexoraAI and repeat retrieval.
6. Delete the test files and confirm their content is no longer returned.

## Operational notes

- The initial model pull is large and may take several minutes. Follow progress
  with `docker compose -f docker-compose.local-embedding.yml logs -f
  ollama-model`.
- CPU inference is suitable for development but can make bulk ingestion slow.
  Production deployments should attach a supported GPU or use a dedicated
  OpenAI-compatible embedding server while retaining the same provider
  configuration.
- Never expose port 11434 publicly without an authenticated reverse proxy and
  network policy. The development Compose file intentionally binds to
  loopback.
- Changing the embedding model or dimension requires another collection and a
  complete re-index. NexoraAI does not copy or convert existing vectors.
