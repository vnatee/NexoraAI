# Agent mail integrations

InsightSphere supports Team Mail Profiles for Microsoft 365, Gmail, and generic
IMAP/POP3 plus SMTP. A Team Admin creates a profile in **Admin Management >
Integrations > Mail**, then assigns it to an Agent with `Read` and/or `Send`
permission.

A profile has one account mode:

- **Personal accounts**: every signed-in User connects and tests their own
  mailbox under **My email accounts**. The same Agent therefore uses Alice's
  mailbox for Alice and Bob's mailbox for Bob. A missing, disabled, or untested
  account removes the mail tools for that User; it never falls back to another
  User or the shared mailbox.
- **Shared mailbox**: the Team-managed mailbox and credential are used by every
  authorized User of the Agent. Existing mail connections keep this behavior.

Provider and account mode are fixed after a profile is created. Create a new
profile to change either one. Changing connection settings on a Personal
profile marks its linked User accounts as **Test required**.

Team and User credentials are encrypted at rest with
`APP_DATA_ENCRYPTION_KEY`, are never returned to the browser, and are removed
when the related User account or Team Mail Profile is disconnected. Keep the
same encryption key across application replicas and restarts.

A System Admin can also create and test a connection in the unassigned Platform
Integration Catalog before a Team exists. It cannot be bound to an Agent until
the System Admin assigns it to one Team. Direct edit requests cannot silently
move an assigned connection between Teams.

## Microsoft 365

This implementation uses Microsoft Graph with the OAuth 2.0 client-credentials flow (application identity).

1. Create an app registration in Microsoft Entra ID.
2. Add Microsoft Graph **Application** permissions:
   - `Mail.ReadBasic.All` for message metadata, or `Mail.Read` when message content is required.
   - `Mail.Send` to send messages.
3. Grant tenant admin consent.
4. Create a client secret and record the secret **value** immediately.
5. Restrict the application to intended mailboxes with Exchange Online Application RBAC/application access policy.
6. For **Personal accounts**, enter Tenant ID, Client ID, and Client Secret in
   the Team Mail Profile. InsightSphere derives each mailbox from the User's
   managed Microsoft identity email; a User cannot type a different mailbox.
7. For **Shared mailbox**, also enter the target mailbox address in the Team
   Mail Profile.

Personal Microsoft 365 accounts currently use the Team's application identity,
not delegated User OAuth. Exchange Application RBAC is therefore an important
security boundary: limit the application to the mailboxes that InsightSphere
is allowed to access.

## Gmail

This implementation uses the Gmail API with a stored OAuth refresh token for one mailbox.

1. Create or select a Google Cloud project and enable Gmail API.
2. Configure the OAuth consent screen and create an OAuth client.
3. Obtain offline consent (`access_type=offline`) and a refresh token for the mailbox.
4. Request only the required scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` for reading.
   - `https://www.googleapis.com/auth/gmail.send` for sending.
5. Enter OAuth Client ID and Client Secret in a Personal Team Mail Profile.
   Each User then enters the mailbox and its refresh token under **My email
   accounts**, and runs **Test** before the Agent can use it.
6. For Shared mailbox mode, enter the Refresh Token and mailbox address in the
   Team Mail Profile instead.

For Google Workspace, the administrator may need to trust the OAuth app. Public apps using restricted Gmail scopes may require Google verification.

## Generic IMAP/POP3 + SMTP

1. Enable IMAP (preferred) or POP3 and SMTP for the mailbox.
2. Create an application password when MFA or server policy requires it.
3. A Team Admin enters the incoming host, port and security mode, plus the SMTP
   host, port and security mode.
4. For Personal mode, each User enters their mailbox, username, and password or
   app password under **My email accounts**, then runs **Test**. For Shared mode,
   those values remain in the Team Mail Profile.
5. Allow the InsightSphere container outbound DNS/TCP access to both hosts.

Common defaults are IMAP over TLS `993`, POP3 over TLS `995`, SMTP with STARTTLS `587`, or SMTP over TLS `465`. Exact values must come from the mail administrator. Avoid `None` security outside an isolated development environment.

## Agent controls

- `Read / search mailbox` exposes a provider-specific search tool.
- `Send mail` exposes a write tool.
- Allowed recipient domains and maximum recipient count are enforced by the runtime before sending.
- Disabling `Mail` in Agent Info keeps bindings saved but removes mail tools from that Agent's runtime.
- Personal accounts are resolved only from the authenticated application User
  ID and the Agent's Team. External Agent API channels and background runs that
  have no signed-in User do not receive Personal mail tools.
- Mail binding create, edit, toggle, list, and delete operations require the
  Agent's Team **Manage agents** permission.
- Mail content and credentials must not be written to application logs, audit
  metadata, or telemetry.
- LangGraph Playground provides **Test** and **Live** Mail modes. Test executes
  Mail Binding validation and returns a simulated result without contacting the
  provider. Live behaves like the Agent runtime and may send multiple messages
  with To, CC, and BCC subject to the binding's recipient policy. Neither mode
  enables any non-mail write tool.

## Current limitations

- Gmail Personal setup currently accepts an administrator-issued refresh token;
  browser-based OAuth connect/revoke is a later improvement.
- Microsoft 365 Personal mode uses application permissions rather than
  delegated User consent.
- Sending is a write-risk tool and the Agent is instructed to use it only after
  an explicit User request. A dedicated draft/approval screen is not included
  yet.
- Attachments, reply/forward, Gmail domain-wide delegation, and generic XOAUTH2
  are not included yet.
