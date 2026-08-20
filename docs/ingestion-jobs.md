# Persistent ingestion jobs

Personal, Team, and Global uploads create one persistent MongoDB job per file.
The HTTP upload request stores the source file first and then returns `202` with
the created jobs. Extraction, chunking, embedding, and search indexing continue
in a bounded background worker.

## Status lifecycle

```text
Uploaded → Extracting → Chunking → Embedding → Indexed
                                           ↘ Failed → Retry
```

`Embedding` covers vector creation and the final search-index write. It remains
the stage name when vectors are disabled so the public lifecycle stays stable.
Every transition is timestamped. Jobs also retain the processing provider,
profile, routing rule, attempt number, safe error summary, and completion time.
The resolved profile is pinned when the upload is accepted so a later rule edit
cannot make the recorded provider differ from the provider actually used.

The Recent processing jobs panel shows active work and failures. A successful
Indexed job remains there for 60 seconds as completion feedback, then leaves the
panel. Failed jobs remain available for Retry. The successful completion time is
shown as Indexed Time in the Personal, Team, or Global file list, so the durable
result stays with the file instead of filling the activity panel.

## Access and secrets

The list and Retry endpoints always scope queries to the authenticated Entra
object ID. A user sees only jobs they submitted, including within Team and
Global scopes. Retry reconstructs the original Personal or data-group ACLs from
server-side job data. Storage paths, routing context, data-group IDs, worker
leases, credentials, document contents, and provider responses are not returned
by the API. Persisted error text is length-limited and redacts common
token/API-key/secret patterns.

## Recovery

Workers use a MongoDB lease so multiple application replicas do not normally
claim the same job. Active stages refresh a 60-minute lease. Every replica runs
a 30-second recovery sweep; an unclaimed Uploaded job is picked up immediately,
while work interrupted by a process/container failure is resumed after its
lease expires. Search document IDs are deterministic, so a recovery attempt
updates the same indexed sections rather than intentionally creating new ones.

Failed jobs can be retried only by their original submitter. Retry increments
the attempt count and reuses the source file and recorded ACL/routing context.
If the source object was deleted, Retry fails safely and records the storage
error.

This is an application-hosted worker, not a separate durable queue service.
Very long extraction calls should remain below the one-hour lease; moving job
execution to a dedicated queue/worker is still recommended before high-volume
horizontal scaling. Jobs currently have no automatic retention/TTL cleanup;
define an operational retention period before long-running production use.

## API

- `GET /ingestion-jobs?scope=personal|team|global&team_id=...&limit=...`
- `POST /ingestion-jobs/{job_id}/retry`

Upload responses from `/upload`, `/team_upload`, and `/global_upload` include a
`jobs` array with the initial serialized job state.
