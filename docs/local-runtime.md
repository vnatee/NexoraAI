# Portable local runtime

`docker-compose.local-runtime.yml` runs a complete self-hosted NexoraAI data
plane on one Docker host. The same stack can run on a developer machine or an
Azure Linux VM:

- NexoraAI application and production frontend bundle
- MongoDB for identities, Teams, configuration, jobs, and chat history
- MinIO for Knowledge source objects
- Qdrant for vector retrieval
- Ollama with BGE-M3 embeddings and a local chat model
- optional Docling service for configured document-processing profiles

Azure remains supported. This Compose file is one deployment option; the
provider environment variables can still point NexoraAI at Azure OpenAI,
Azure AI Search, Azure Storage, and Cosmos DB in a different deployment.

## Prepare secrets

Copy the template to an ignored file:

```bash
cp docs/local-runtime.env.example .env.local-runtime
```

Generate independent values and replace every `replace_with_*` entry:

```bash
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 32
openssl rand -hex 32
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the generated values for the MongoDB root password, MongoDB application
password, MinIO access key, MinIO secret key, one-time local-auth bootstrap
token, and `APP_DATA_ENCRYPTION_KEY`, respectively. Keep the Fernet key stable
for the lifetime of the deployment; changing it makes stored provider and Entra
secrets unreadable.

## Start

The first start builds the application image and downloads BGE-M3 plus the
configured local chat model. It can therefore take several minutes and use
multiple gigabytes of network and disk space.

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml up -d --build --wait
```

Follow startup and model-download progress with:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml logs -f app ollama-models
```

Open `http://127.0.0.1:50505`. Create the first local administrator using the
one-time bootstrap token. Then remove `LOCAL_AUTH_BOOTSTRAP_TOKEN` from the env
file and recreate only the application container:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml up -d --force-recreate app
```

The bootstrap endpoint remains closed after the first local identity exists,
but removing the token reduces exposure and prevents accidental reuse.

## Optional OCR service

Start Docling only when a processing profile needs it:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml --profile ocr up -d docling
```

In **Admin Management → Document Processing & OCR**, configure a Docling
provider endpoint as `http://docling:5001`. The application and Docling share
the Compose network; do not expose the Docling port publicly.

## Stop, upgrade, and preserve data

Stop containers without deleting state:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml down
```

Application state is held in five named volumes: MongoDB, MinIO, Qdrant,
Ollama, and temporary chat attachments. Never use `down --volumes` against a
deployment whose data must be retained. Back up MongoDB, MinIO, and Qdrant as a
consistent set before an upgrade. Source objects and vector records alone are
not a replacement for MongoDB authorization metadata.

Changing the embedding model or dimension requires a new Qdrant collection
and re-indexing. Changing storage or search providers does not migrate data
automatically.

## Azure VM deployment

The Compose stack can run unchanged on an Azure VM. For a production VM:

1. Keep MongoDB, Qdrant, Ollama, and the MinIO API on the private Compose
   network, as this file does by default.
2. Put HTTPS ingress (Application Gateway, Front Door plus a private origin, or
   a hardened reverse proxy) in front of port 50505.
3. Set `NEXORA_BIND_ADDRESS` only when the host firewall and network security
   group restrict access appropriately. Do not expose MinIO Console publicly.
4. Store the env file in a protected location or inject secrets from a secret
   manager; never bake it into the image.
5. Use managed disks and tested volume-level backups. Configure monitoring,
   log retention, patching, and restore drills.
6. Attach a supported GPU or move Ollama to a private GPU host for production
   throughput. CPU mode is intended primarily for evaluation and light loads.

For multi-node/high-availability operation, move stateful services to managed
or clustered equivalents and deploy the application image to an orchestrator.
This single-host Compose file does not provide database replication, automatic
failover, TLS termination, or zero-downtime upgrades.

## Smoke test

1. Confirm `docker compose ... ps` reports the application and dependencies as
   healthy and `/config` reports local runtime, MinIO, Qdrant, and the local
   embedding provider.
2. Bootstrap the administrator, remove the token, restart the app, and sign in.
3. Create a Team and Data Group. Upload distinct Personal, Team, and Global
   documents and wait for **Indexed**.
4. Retrieve and open citations from each allowed scope; verify a second user
   outside the Team/Data Group cannot retrieve or open Team content.
5. Restart the full stack without deleting volumes and repeat retrieval.
6. Delete one source and confirm both its object and vector results disappear.
7. Test backup restore on a disposable deployment before production use.
