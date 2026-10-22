# Messaging & Chat integrations

Connections are managed in **Admin Management > Integrations > Messaging & Chat**. Assign them in **Agent > Integrations > Messaging**. Tokens and webhook URLs are encrypted with `APP_DATA_ENCRYPTION_KEY`.

A System Admin may create and test an unassigned connection before creating a
Team, then explicitly assign it to one Team. Unassigned and cross-Team
connections are rejected by the Agent-binding API.

## LINE Messaging API

1. Create a LINE Official Account and Messaging API channel in LINE Developers Console.
2. Issue a channel access token and store it in NexoraAI.
3. Add the Official Account as a friend or invite it to the target group/room.
4. Use a `userId`, `groupId`, or `roomId` received from a LINE webhook event as Default Target.

NexoraAI sends text push messages through `POST /v2/bot/message/push`.

## Slack

1. Create a Slack App and add a bot user.
2. Add the Bot Token Scope `chat:write`; add `chat:write.public` only if posting to public channels without inviting the bot is required.
3. Install/reinstall the app into the workspace and copy the Bot User OAuth Token (`xoxb-...`).
4. Invite the bot to private channels and normally to public channels.
5. Configure a channel ID such as `C0123456789` as Default Target.

NexoraAI sends messages through `chat.postMessage` and uses `auth.test` for connection testing.

## Discord

1. Open the Discord channel settings, choose Integrations > Webhooks, and create a webhook.
2. Copy the webhook URL and store it in NexoraAI. Treat the URL as a secret.
3. No separate Default Target is required because the channel is encoded in the webhook URL.

Only official `discord.com` webhook hosts are accepted.

## Agent binding

- Default Target overrides the connection default for one Agent.
- A Message Template may contain placeholders such as `{{service}}` and `{{status}}`.
- With no template, the Agent generates the complete message text.
- Sending is a write action and is recorded by Agent runtime audit events.
- Agent Messaging bindings remain outbound-only. For an inbound LINE text
  conversation, use the separate [LINE Agent Channel](line-agent-channel.md).
  Threaded replies, Slack inbound events, LINE Flex Messages, files, and
  interactive callbacks remain future work.
