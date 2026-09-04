# Local backup and restore

NexoraAI's portable Compose runtime can create one validated archive containing
a consistent logical backup of:

- MongoDB application data (`mongodump --archive --gzip`);
- MinIO Knowledge objects, including custom metadata and object tags; and
- every Qdrant collection as a native collection snapshot.

The archive contains a versioned manifest, component sizes, SHA-256 checksums,
non-secret runtime compatibility metadata, and a SHA-256 fingerprint of
`APP_DATA_ENCRYPTION_KEY`. It never contains the encryption key, MongoDB/MinIO
passwords, API keys, bootstrap tokens, the environment file, raw prompts, or
tool output.

Ollama's model cache is reproducible and is not backed up. Temporary Chat
attachments follow their own retention policy and are also excluded. Browser
Chat history remains in each user's IndexedDB and is outside the server backup.

## Prerequisites

Use the same Compose file and protected environment file as the local runtime.
Rebuild the application image after installing this feature so the MinIO and
Qdrant backup helper exists inside the image:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml up -d --build --wait
```

MongoDB, MinIO, and Qdrant must be running. The script stops only the `app`
service while capturing or restoring the consistent set, then starts it again
only if it was running before the operation. This assumes no other application
or operator writes directly to these services during the maintenance window.

Keep the original `APP_DATA_ENCRYPTION_KEY` in a separate secret manager or
offline recovery record. Encrypted provider credentials restored from MongoDB
cannot be used without that exact key.

## Create a backup

Backups default to the ignored `backups/` directory:

```bash
.venv/bin/python scripts/local_runtime_backup.py backup \
  --env-file .env.local-runtime
```

Choose an explicit destination when copying to protected external storage:

```bash
.venv/bin/python scripts/local_runtime_backup.py backup \
  --env-file .env.local-runtime \
  --output /secure/nexora-backup-20260903T120000Z.tar.gz
```

If the deployment uses an explicit Compose project name, pass the same value
with `--project-name`. A partial archive is never promoted to the requested
output name, and the finished archive is validated before success is reported.

## Validate without restoring

Validation checks the archive allowlist, format versions, safe member names,
component sizes, and SHA-256 checksums:

```bash
.venv/bin/python scripts/local_runtime_backup.py validate \
  --archive /secure/nexora-backup-20260903T120000Z.tar.gz
```

Validation proves integrity, not recoverability. Perform periodic restore
drills on a disposable deployment.

## Restore

Restore is destructive for the configured MinIO bucket and for Qdrant
collections present in the backup. Other Qdrant collections are not deleted.
MongoDB uses `mongorestore --drop` for collections present in the archive. Stop
external writers and verify the target environment before continuing.

The target must use the same MongoDB database, MinIO bucket, Qdrant collection,
embedding model/dimensions, and `APP_DATA_ENCRYPTION_KEY` fingerprint recorded
in the manifest. Use compatible MongoDB, MinIO, and Qdrant image versions;
Qdrant snapshot compatibility in particular must be reviewed before an upgrade.

```bash
.venv/bin/python scripts/local_runtime_backup.py restore \
  --env-file .env.local-runtime \
  --archive /secure/nexora-backup-20260903T120000Z.tar.gz \
  --confirm-restore
```

The explicit confirmation flag prevents accidental restores. Restore writes
MinIO and Qdrant first and MongoDB metadata last. It cannot provide one atomic
transaction across three products; if any component fails, keep the deployment
out of service, correct the cause, and rerun the same validated archive. The
script deliberately leaves the `app` service stopped after a partial failure.

## Recovery verification

After restore:

1. Confirm all Compose services are healthy and sign in with a restored Local
   account.
2. Verify Teams, Data Groups, Agents, provider configurations, quota policies,
   and audit metadata.
3. List Personal, Team, and Global files and compare representative counts.
4. Retrieve one unique document from each allowed scope and open its citation.
5. Verify a user outside the Team/Data Group cannot retrieve the Team source.
6. Run an ingestion and confirm the configured Qdrant collection accepts new
   vectors.
7. Store the archive encrypted at rest with restricted access and record the
   restore-drill result separately.

## Current limitations

- This workflow targets the single-host local Compose runtime, not Azure Blob,
  Azure AI Search, Cosmos DB, or an external managed provider.
- Scheduling, retention rotation, remote-object-storage upload, and alerting
  are operator responsibilities in this slice.
- Restore does not migrate embedding models or Qdrant dimensions.
- Multi-node writes and zero-downtime backups require provider-native clustered
  backup capabilities and are outside this Compose workflow.
