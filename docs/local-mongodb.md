# Local MongoDB

NexoraAI's application metadata connector already accepts a standard MongoDB
URI. The local deployment therefore uses the same collections and authorization
code as Cosmos DB's Mongo-compatible endpoint; it does not introduce a second
database implementation.

This slice runs MongoDB only. The backend continues to run with `app/start.sh`,
and Azure Search and Knowledge object storage remain unchanged.

## Configure

Copy the non-secret template to an ignored local file:

```bash
cp docs/local-mongodb.env.example .env.local-mongodb
```

Generate two different URI-safe passwords and place them in the copied file:

```bash
openssl rand -hex 24
openssl rand -hex 24
```

Use the application password in both `NEXORA_MONGO_APP_PASSWORD` and the
password portion of `MONGO_URI`. Do not commit `.env.local-mongodb`.

The root account is used only by the container health check and first-volume
initialization. NexoraAI connects as `nexora_app`, which has `readWrite` access
only to the configured application database. The port is bound to
`127.0.0.1`, not every host interface.

## Start and stop

Start MongoDB and wait for it to become healthy:

```bash
docker compose --env-file .env.local-mongodb -f docker-compose.local-mongodb.yml up -d mongodb
docker compose --env-file .env.local-mongodb -f docker-compose.local-mongodb.yml ps
```

Load the backend variables into the current shell before starting NexoraAI:

```bash
set -a
. ./.env.local-mongodb
set +a
app/start.sh
```

Quart otherwise defaults to a 16 MiB request limit. NexoraAI sets the default
Knowledge upload request limit to 100 MiB; override `MAX_UPLOAD_SIZE_BYTES` when
the deployment needs a different hard limit. This is a per-request limit and is
separate from Personal, Team, and Global storage quotas. Keep any ingress or
reverse-proxy body-size limit at least as large as this value.

Stop the container without deleting data:

```bash
docker compose --env-file .env.local-mongodb -f docker-compose.local-mongodb.yml down
```

The `nexora_mongodb_data` named volume retains users, authentication sessions,
Teams, Data Groups, managed settings, jobs, and other application metadata.
Never run `down --volumes` against a deployment whose data must be retained.

## Verification

After MongoDB reports `healthy`, verify the application user without printing
credentials:

```bash
docker compose --env-file .env.local-mongodb -f docker-compose.local-mongodb.yml exec mongodb \
  sh -lc 'mongosh --quiet --username "$NEXORA_MONGO_APP_USERNAME" \
  --password "$NEXORA_MONGO_APP_PASSWORD" --authenticationDatabase "$NEXORA_MONGO_DB_NAME" \
  "$NEXORA_MONGO_DB_NAME" --eval "db.runCommand({ ping: 1 })"'
```

Then complete this application smoke test:

1. Bootstrap or sign in with a Local account and create a Team and Data Group.
2. Restart both the backend and MongoDB container; confirm the account, Team,
   Data Group, and managed settings remain present.
3. Change the Local password and confirm the old session is rejected.
4. Upload a small document and confirm its processing job survives a graceful
   backend restart.
5. Confirm Team/Data Group access and citations are identical to the Azure
   Mongo-compatible deployment.

## Existing volumes and credential changes

The image runs initialization scripts only when `/data/db` is empty. Editing
the environment file later does not rotate users inside an existing volume.
Rotate credentials with an authenticated MongoDB administration operation, then
update `MONGO_URI`. Keep `APP_DATA_ENCRYPTION_KEY` stable; MongoDB persistence
does not make encrypted application secrets recoverable after that key is lost.

No automatic Cosmos-to-local data migration is included. A new local deployment
may start empty. Use `mongodump`/`mongorestore` only after reviewing source and
destination compatibility, access controls, retention requirements, and a
tested rollback plan.
