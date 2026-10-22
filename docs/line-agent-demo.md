# LINE Agent Demo Bridge

The LINE Bridge connects a LINE Official Account to one approved NexoraAI
Agent without exposing an Agent API key to a browser or mobile client.

```text
LINE webhook
  -> signature verification and event deduplication
  -> NexoraAI background Agent job
  -> LINE Push API response
```

This bridge is intended for a controlled demonstration. It stores a bounded
conversation history in process memory only. History and deduplication state are
lost when the bridge restarts and are not shared across replicas.

## Security model

- LINE webhook requests must have a valid `X-Line-Signature`.
- The bridge uses a dedicated NexoraAI `external_customer` API key.
- The key can invoke only its selected Agent and published External Knowledge.
- LINE and NexoraAI credentials are read from deployment environment variables.
- Raw prompts, responses, tokens, and webhook bodies are not logged.
- An optional source allowlist can restrict the demonstration to approved LINE
  users, groups, or rooms.
- The bridge acknowledges the webhook immediately and runs the Agent in a
  background job with an idempotency key derived from the LINE event ID.

Do not use the existing Agent Messaging binding for inbound conversations. That
integration is an outbound write tool. The LINE Bridge is the inbound channel
adapter.

## Prerequisites

1. A LINE Official Account with a Messaging API channel.
2. Its Channel Secret and long-lived Channel Access Token.
3. A public NexoraAI HTTPS deployment.
4. An active LangGraph Agent.
5. Published External Knowledge for that Agent.
6. A dedicated `external_customer` key that permits the Agent and only the
   required External Knowledge.

Create the key in **Team workspace > Team governance > Agent API access**.
Copy it when displayed because NexoraAI does not store the plaintext value.

## Configure

Add these values to the deployment's ignored `.env.local-runtime` file:

```dotenv
LINE_CHANNEL_SECRET=replace_with_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=replace_with_line_channel_access_token
LINE_BRIDGE_NEXORA_AGENT_ID=replace_with_agent_id
LINE_BRIDGE_NEXORA_API_KEY=nxai_replace_with_external_customer_key
```

For a controlled demo, restrict access to known LINE source IDs:

```dotenv
LINE_BRIDGE_ALLOWED_SOURCE_IDS=U1234567890abcdef,G1234567890abcdef
```

Multiple IDs are comma-separated. Leave the value empty only when every user
who can reach the Official Account should be allowed to invoke the Agent.

Optional behavior:

```dotenv
LINE_BRIDGE_HISTORY_TURNS=4
LINE_BRIDGE_STATE_TTL_SECONDS=86400
LINE_BRIDGE_JOB_TIMEOUT_SECONDS=180
LINE_BRIDGE_POLL_INTERVAL_SECONDS=1
LINE_BRIDGE_SEND_ACK=true
LINE_BRIDGE_ACK_TEXT=กำลังค้นหาข้อมูล กรุณารอสักครู่...
```

Conversation history is process-local and never written to disk. Set
`LINE_BRIDGE_HISTORY_TURNS=0` for strictly stateless requests.

## Deploy

Build and start the application, bridge, and TLS gateway:

```bash
sudo docker compose \
  --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --build app line-bridge tls-gateway
```

Check the bridge:

```bash
sudo docker compose \
  --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  ps app line-bridge tls-gateway

sudo docker compose \
  --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  exec line-bridge python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health/ready').read().decode())"
```

The readiness response must be `{"status":"ready","missing":[]}`.

## Configure LINE Developers

Set the Messaging API webhook URL to:

```text
https://YOUR-NEXORA-HOST/integrations/line/webhook
```

Then:

1. Enable **Use webhook**.
2. Disable LINE's automatic greeting/response for a clean Agent demo.
3. Select **Verify**. A correctly configured endpoint returns HTTP 200.
4. Add the Official Account as a friend.
5. Send a text question.

The bridge first replies with the configured acknowledgement. It then pushes the
Agent's final answer and up to five public HTTP(S) citations.

## Operational checks

View bridge logs without printing environment variables:

```bash
sudo docker compose \
  --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  logs --since=15m line-bridge
```

Expected successful log text contains an opaque event reference and
`LINE event completed`. It never contains the LINE message or Agent response.

Common failures:

- **401 Invalid LINE signature**: Channel Secret does not match the channel.
- **503 not configured**: one or more required environment variables is empty.
- **Nexora job creation 401/403**: API key is invalid, expired, revoked, or does
  not permit the selected Agent.
- **Nexora job creation 409**: Agent is inactive, not LangGraph, or has stale
  configuration.
- **No response for an allowed user**: verify the source ID allowlist and LINE
  push-message permissions.

## Known Demo limitations

- One bridge container should be used because history and event deduplication
  are process-local.
- Restarting the container clears conversation context.
- Only LINE text messages are accepted.
- Flex Messages, images, files, postbacks, unsend events, and rich menus are not
  interpreted.
- The Agent API remains stateless; the bridge supplies a bounded previous-turn
  transcript as conversational context.
- Production rollout should replace memory state with an encrypted,
  retention-governed shared store and a durable channel-delivery queue.
