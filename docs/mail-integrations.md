# Agent mail integrations

NexoraAI supports three centrally managed mail connection types. A team administrator stores a connection in **Admin Management > Integrations > Mail**, then assigns it to an Agent with `Read` and/or `Send` permission. Credentials are encrypted at rest with `APP_DATA_ENCRYPTION_KEY` and are never returned to the browser.

## Microsoft 365

This implementation uses Microsoft Graph with the OAuth 2.0 client-credentials flow (application identity).

1. Create an app registration in Microsoft Entra ID.
2. Add Microsoft Graph **Application** permissions:
   - `Mail.ReadBasic.All` for message metadata, or `Mail.Read` when message content is required.
   - `Mail.Send` to send messages.
3. Grant tenant admin consent.
4. Create a client secret and record the secret **value** immediately.
5. Restrict the application to intended mailboxes with Exchange Online Application RBAC/application access policy.
6. Enter Tenant ID, Client ID, Client Secret, and the target mailbox address in NexoraAI.

## Gmail

This implementation uses the Gmail API with a stored OAuth refresh token for one mailbox.

1. Create or select a Google Cloud project and enable Gmail API.
2. Configure the OAuth consent screen and create an OAuth client.
3. Obtain offline consent (`access_type=offline`) and a refresh token for the mailbox.
4. Request only the required scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` for reading.
   - `https://www.googleapis.com/auth/gmail.send` for sending.
5. Enter OAuth Client ID, Client Secret, Refresh Token, and mailbox address in NexoraAI.

For Google Workspace, the administrator may need to trust the OAuth app. Public apps using restricted Gmail scopes may require Google verification.

## Generic IMAP/POP3 + SMTP

1. Enable IMAP (preferred) or POP3 and SMTP for the mailbox.
2. Create an application password when MFA or server policy requires it.
3. Enter the incoming host, port and security mode, plus the SMTP host, port and security mode.
4. Allow the NexoraAI container outbound DNS/TCP access to both hosts.

Common defaults are IMAP over TLS `993`, POP3 over TLS `995`, SMTP with STARTTLS `587`, or SMTP over TLS `465`. Exact values must come from the mail administrator. Avoid `None` security outside an isolated development environment.

## Agent controls

- `Read / search mailbox` exposes a provider-specific search tool.
- `Send mail` exposes a write tool.
- Allowed recipient domains and maximum recipient count are enforced by the runtime before sending.
- Disabling `Mail` in Agent Info keeps bindings saved but removes mail tools from that Agent's runtime.
- Attachments, reply/forward, delegated Microsoft sign-in, Gmail domain-wide delegation, and generic XOAUTH2 are not part of this first version.
