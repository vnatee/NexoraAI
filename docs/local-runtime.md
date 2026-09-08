# Portable local runtime

`docker-compose.local-runtime.yml` runs a complete self-hosted NexoraAI data
plane on one Docker host. The same stack can run on a developer machine or an
Azure Linux VM:

- NexoraAI application and production frontend bundle
- MongoDB for identities, Teams, configuration, jobs, and document metadata
- MinIO for Knowledge source objects
- Qdrant for vector retrieval
- Ollama with BGE-M3 embeddings and a local chat model
- Integration Controller for System Admin-managed Azure MCP instances
- optional Docling service for configured document-processing profiles

Azure remains supported. This Compose file is one deployment option; the
provider environment variables can still point NexoraAI at Azure OpenAI,
Azure AI Search, Azure Storage, and Cosmos DB in a different deployment.

The single-host local stack disables the optional Azure Cosmos-native Chat
History provider and enables the MongoDB-backed server history provider.
Conversation history is synchronized between browsers and is isolated by the
stable authenticated application user ID. Records include an absolute
`expires_at` value and are removed by a periodic application cleanup worker.
The worker removes attachment objects, extracted chunks, attachment metadata,
and then the conversation. Citations and Draw.io artifacts are stored inside
the conversation and disappear with it. A MongoDB TTL index is deliberately
not used for conversation rows because it could remove the parent before those
dependencies. The default is 90 days from the latest conversation update.

System Administrators can change the platform maximum under
**Administration → System chat history**. Team administrators with `Manage
agents` can choose a shorter Team period under **Team settings → Team chat
history**, but cannot extend it beyond the System policy. Available values are
30, 90, 180, 365 days, and **No expiry** where the parent policy permits it.
Lowering a policy recalculates expiry
for existing affected conversations. `CHAT_HISTORY_RETENTION_DAYS` supplies the
initial System default and `CHAT_HISTORY_CLEANUP_INTERVAL_SECONDS` controls the
cleanup interval; saved Portal settings survive restarts in MongoDB.
User deletion runs the same cascade immediately. A separate 365-day audit
collection stores only actor, time, reason, and deleted conversation/attachment
counts; it never stores removed content.

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
openssl rand -hex 32
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the generated values for the MongoDB root password, MongoDB application
password, MinIO access key, MinIO secret key, Integration Controller token,
one-time local-auth bootstrap token, and `APP_DATA_ENCRYPTION_KEY`, respectively.
Set `AZURE_MCP_IMAGE` to a verified digest of Microsoft's official image during
initial installation; the image is not pulled until Azure is enabled. Keep the Fernet key stable
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

The Integration Controller is also started on day one but publishes no host
port and creates no Azure MCP instances until a System Administrator enables a
managed Azure connection. It is the only service with Docker socket access.
Protect `INTEGRATION_CONTROLLER_TOKEN`; do not reuse the Fernet key or another
application credential. See [`azure-drawio-mcp.md`](azure-drawio-mcp.md).

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

Application state is held in five named volumes: MongoDB (including Chat
history), MinIO, Qdrant, Ollama, and temporary chat attachments. Never use
`down --volumes` against a
deployment whose data must be retained. Back up MongoDB, MinIO, and Qdrant as a
consistent set before an upgrade. Source objects and vector records alone are
not a replacement for MongoDB authorization metadata.

During shutdown the controller removes the ephemeral Azure MCP instances.
Enabled managed connections are recreated from encrypted MongoDB configuration
after the stack starts again.

Use the validated backup/restore workflow in
[`local-backup-restore.md`](local-backup-restore.md). It briefly stops the
application writer, creates logical MongoDB and MinIO backups plus native
Qdrant snapshots, and validates a checksummed manifest. Credentials and
`APP_DATA_ENCRYPTION_KEY` are deliberately excluded and must be protected
separately.

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
8. Create a Chat, reload it from **Recent chats** in another browser session,
   then set a short test retention period in **Administration → System chat history**
   and confirm owner isolation and expiry cleanup. Restore the intended policy
   after the test.
