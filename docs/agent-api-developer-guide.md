# NexoraAI Agent API Developer Guide

This guide shows application developers how to call an approved NexoraAI Agent,
test the integration, and handle production failures safely.

## Before you begin

Ask a Team administrator to create an API key in:

**Team workspace > Team governance > Agent API access**

The administrator selects the allowed Agents and Team-wide Knowledge. Copy both
the generated key and the example request shown by the Portal. The complete key
Select **Developer Guide** on that page for an in-Portal quick start and
copyable examples.

is shown only once.

You need:

- the HTTPS base URL, such as `https://ai.example.com`;
- the Agent ID shown in the Portal example;
- an API key beginning with `nxai_`.

Store the key in a server-side secret manager or environment variable. Never
commit it, log it, place it in a URL, or embed it in browser/mobile code. A
browser or mobile application should call your own backend, which then calls
NexoraAI.

## Choose the right endpoint

| Need | Endpoint | Recommendation |
| --- | --- | --- |
| Simple request that completes quickly | `POST /api/v1/agents/{agent_id}/invoke` | Start here |
| Keep a connection open and receive lifecycle events | `POST /api/v1/agents/{agent_id}/invoke/stream` | SSE; not token streaming |
| Long-running or production workflow | `POST /api/v1/agents/{agent_id}/jobs` | Recommended with an idempotency key |
| Check an asynchronous job | `GET /api/v1/agent-jobs/{job_id}` | Poll with the same API key |
| Retry a failed job | `POST /api/v1/agent-jobs/{job_id}/retry` | Failed, unexpired jobs only |

The machine-readable contract is available from a running deployment at
`/api/v1/openapi.yaml`. It can be imported into Swagger Editor, Postman, or an
OpenAPI client generator.

## Five-minute smoke test

Set local shell variables without placing secrets in command history where
possible:

```bash
export NEXORA_BASE_URL="https://ai.example.com"
export NEXORA_AGENT_ID="replace-with-agent-id"
export NEXORA_API_KEY="replace-with-key-from-secret-store"
```

Call the synchronous endpoint:

```bash
curl --fail-with-body -X POST \
  "$NEXORA_BASE_URL/api/v1/agents/$NEXORA_AGENT_ID/invoke" \
  -H "Authorization: Bearer $NEXORA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":"Summarize the current employee leave policy."}'
```

A successful response contains `output` and may contain citations, a chart, or
a diagram:

```json
{
  "id": "request-id",
  "object": "agent.invocation",
  "agent_id": "agent-id",
  "conversation_id": "conversation-id",
  "output": "The Agent response.",
  "citations": [],
  "chart": null,
  "diagram": null
}
```

## Asynchronous job test

Generate a new idempotency key for each business operation:

```bash
IDEMPOTENCY_KEY="$(uuidgen)"
curl --fail-with-body -i -X POST \
  "$NEXORA_BASE_URL/api/v1/agents/$NEXORA_AGENT_ID/jobs" \
  -H "Authorization: Bearer $NEXORA_API_KEY" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":"Analyze the incident and compare it with our runbooks."}'
```

The server returns `202 Accepted`, a `Location` header, and a job ID. Poll
with the same API key:

```bash
curl --fail-with-body \
  "$NEXORA_BASE_URL/api/v1/agent-jobs/replace-with-job-id" \
  -H "Authorization: Bearer $NEXORA_API_KEY"
```

The status progresses through `queued`, `running`, and then `succeeded` or
`failed`. A successful job has a `result` using the synchronous response
schema.

Repeat the create request with the same body and idempotency key. It must return
the original job with `idempotent_replay: true`. Reusing that key with a
different body must return `409 Conflict`.

## SSE lifecycle test

```bash
curl --no-buffer --fail-with-body -X POST \
  "$NEXORA_BASE_URL/api/v1/agents/$NEXORA_AGENT_ID/invoke/stream" \
  -H "Authorization: Bearer $NEXORA_API_KEY" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"input":"Investigate current service alerts."}'
```

Expected events are `started`, optional periodic `heartbeat`, and either
`completed` or `error`. Only the final `completed` event contains the
validated response.

## Python example

Install Requests with `python -m pip install requests`, then keep the API key
in the process environment:

```python
import os
import time
import uuid

import requests

base_url = os.environ["NEXORA_BASE_URL"].rstrip("/")
agent_id = os.environ["NEXORA_AGENT_ID"]
api_key = os.environ["NEXORA_API_KEY"]
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Idempotency-Key": str(uuid.uuid4()),
}

created = requests.post(
    f"{base_url}/api/v1/agents/{agent_id}/jobs",
    headers=headers,
    json={"input": "Summarize relevant HR policy and cite the sources."},
    timeout=30,
)
created.raise_for_status()
job = created.json()

while job["status"] in {"queued", "running"}:
    time.sleep(2)
    response = requests.get(
        f"{base_url}/api/v1/agent-jobs/{job['id']}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    job = response.json()

if job["status"] == "failed":
    raise RuntimeError(job["error"]["message"])

print(job["result"]["output"])
```

## TypeScript example

This server-side example uses the native `fetch` available in Node.js 18 and
later:

```typescript
import { randomUUID } from "node:crypto";

const baseUrl = process.env.NEXORA_BASE_URL!.replace(/\/$/, "");
const agentId = process.env.NEXORA_AGENT_ID!;
const apiKey = process.env.NEXORA_API_KEY!;

const createdResponse = await fetch(
  `${baseUrl}/api/v1/agents/${agentId}/jobs`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      "Idempotency-Key": randomUUID()
    },
    body: JSON.stringify({
      input: "Summarize relevant HR policy and cite the sources."
    }),
    signal: AbortSignal.timeout(30_000)
  }
);

if (!createdResponse.ok) {
  throw new Error(`NexoraAI returned ${createdResponse.status}: ${await createdResponse.text()}`);
}

let job = await createdResponse.json();

while (job.status === "queued" || job.status === "running") {
  await new Promise(resolve => setTimeout(resolve, 2_000));
  const response = await fetch(
    `${baseUrl}/api/v1/agent-jobs/${job.id}`,
    {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(30_000)
    }
  );
  if (!response.ok) throw new Error(`Job polling failed: ${response.status}`);
  job = await response.json();
}

if (job.status === "failed") throw new Error(job.error.message);
console.log(job.result.output);
```

## C# example

This example targets modern .NET:

```csharp
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

var baseUrl = Environment.GetEnvironmentVariable("NEXORA_BASE_URL")!.TrimEnd('/');
var agentId = Environment.GetEnvironmentVariable("NEXORA_AGENT_ID")!;
var apiKey = Environment.GetEnvironmentVariable("NEXORA_API_KEY")!;

using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
client.DefaultRequestHeaders.Authorization =
    new AuthenticationHeaderValue("Bearer", apiKey);

using var request = new HttpRequestMessage(
    HttpMethod.Post,
    $"{baseUrl}/api/v1/agents/{agentId}/jobs"
);
request.Headers.Add("Idempotency-Key", Guid.NewGuid().ToString());
request.Content = JsonContent.Create(new {
    input = "Summarize relevant HR policy and cite the sources."
});

using var createdResponse = await client.SendAsync(request);
createdResponse.EnsureSuccessStatusCode();
var job = await createdResponse.Content.ReadFromJsonAsync<JsonElement>();

while (job.GetProperty("status").GetString() is "queued" or "running")
{
    await Task.Delay(TimeSpan.FromSeconds(2));
    var jobId = job.GetProperty("id").GetString();
    job = await client.GetFromJsonAsync<JsonElement>(
        $"{baseUrl}/api/v1/agent-jobs/{jobId}"
    );
}

if (job.GetProperty("status").GetString() == "failed")
    throw new Exception(job.GetProperty("error").GetProperty("message").GetString());

Console.WriteLine(job.GetProperty("result").GetProperty("output").GetString());
```

## Production integration rules

- Prefer asynchronous jobs for work that uses Knowledge, MCP, or external tools.
- Use one API key per application and environment.
- Set a unique `Idempotency-Key` per business operation and retain it until the
  operation completes.
- Poll every 2–5 seconds with exponential backoff for longer jobs. Do not create
  a new job merely because a poll timed out.
- Treat `429` as retryable using backoff and jitter.
- Treat `401` as a key rotation, revocation, or expiry problem.
- Treat `403` as a scope/configuration problem; do not retry automatically.
- Treat `409` as a state or idempotency conflict requiring inspection.
- Do not log Authorization headers, prompts, responses, or tool output.
- The durable worker provides at-least-once recovery. Integrations that perform
  external writes must also implement idempotency at the destination.

## Postman

Import `docs/NexoraAI-Agent-Invocation-API.postman_collection.json`. Set these
collection variables:

- `baseUrl`
- `apiKey`
- `agentId`

The create-job request generates an idempotency value and stores the returned
job ID automatically. Run **Create async job**, then **Get job** until complete.
Use **Retry failed job** only after a failed result.

## Acceptance checklist

- Synchronous call returns HTTP 200 and an `agent.invocation` object.
- SSE emits `started` followed by `completed` or `error`.
- Async creation returns HTTP 202 and a `Location` header.
- Polling with the creating key reaches a terminal state.
- Repeating an identical idempotent request returns the same job.
- Reusing the idempotency key for another payload returns HTTP 409.
- Another API key cannot read the job and receives HTTP 404.
- Revoked or expired keys receive HTTP 401.
- System Health shows the Agent API invocation worker and job counts.
- Application logs and audit records do not contain API keys or request content.

For the security model and endpoint behavior, also see
[Agent Invocation API](agent-invocation-api.md).
