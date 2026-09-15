# Local, Microsoft Entra, OIDC, and SAML authentication

NexoraAI can run with Microsoft Entra ID, standards-based OpenID Connect (OIDC),
SAML 2.0, application-managed local accounts, or a combination. All identity providers resolve to the existing application `users`
records, so Team membership, Data Groups, permissions, document ACLs, and audit
ownership use the same authorization model.

## First deployment

Set these values before starting the backend:

```text
LOCAL_AUTH_ENABLED=true
LOCAL_AUTH_BOOTSTRAP_TOKEN=<a long random one-time setup token>
APP_DATA_ENCRYPTION_KEY=<the deployment's stable Fernet key>
```

Open the application. While no local identity exists, the Login page displays
the first-administrator setup form. Enter the bootstrap token and create a
password of at least 12 characters. The endpoint is permanently closed after
the first local identity is created. Remove `LOCAL_AUTH_BOOTSTRAP_TOKEN` from
the runtime environment and restart the service after setup.

Passwords are stored as salted scrypt hashes. Login sessions use opaque random
bearer tokens; only their SHA-256 digests are stored in MongoDB, sessions expire
after 12 hours, and five failed attempts lock an account for 15 minutes.

## Add local users

Sign in as a system administrator and open **Admin Management → Users & Access
→ User Management**. Enter both **Local username** and **Temporary local
password** when creating a user. Leaving both fields empty creates the existing
Entra-only user. Team membership, Data Groups, and permissions are assigned in
the existing access-management tabs. A local user's password can be reset from
User Detail; resetting it revokes all of that user's current local sessions.

## My profile and password

The account menu shows the application user's first and last name above the
local username or Entra sign-in ID. **My profile** lets a signed-in user update
only their own first name, last name, contact email, and telephone number.
Employee ID, sign-in identities, account status, system-administrator status,
Teams, roles, and permissions remain administrator-managed fields.

A user with a Local identity can change their own password from this dialog.
They must supply the current password, the new password must contain at least
12 characters and must differ from the current password, and a successful
change revokes every existing Local session for the account. A user currently
signed in through Local authentication is returned to Login. For an Entra-only
user, the dialog directs password management to Microsoft Entra ID instead.

Self-service forgotten-password recovery is intentionally not implemented in
this slice. An authorized user manager can issue a reset from User Detail;
production recovery should later use a short-lived, single-use token delivered
through a verified channel rather than security questions.

## Configure Microsoft Entra ID

Open **Admin Management → Users & Access → Authentication**. A system
administrator can enable Entra and enter:

- Tenant ID
- API application (server) ID
- SPA application (client) ID
- API application client secret

The secret is encrypted with `APP_DATA_ENCRYPTION_KEY` and is never returned to
the browser. Managed settings override the corresponding environment values.
Reload the browser after saving so MSAL is initialized with the new client
configuration. **Use environment settings** removes the managed override.

Keep `APP_DATA_ENCRYPTION_KEY` stable across restarts and replicas. Losing or
rotating it without re-encrypting stored secrets makes the saved Entra client
secret and other managed credentials unreadable.

## Configure Generic OpenID Connect

Open **System administration → Sign-in & authentication → OpenID Connect
connections**. Add one connection for each identity provider or tenant. This
works with providers such as Okta, Keycloak, Auth0, Google Workspace, and Ping
Identity. Configure:

- **Connection / sign-in name**: the label users see, for example `Company SSO`.
- **Issuer URL**: the exact HTTPS issuer from the provider's OpenID discovery
  document. Do not enter the authorization endpoint itself.
- **Client ID / Client secret**: credentials for a confidential web
  application. The secret is encrypted with `APP_DATA_ENCRYPTION_KEY` and is
  never returned to the browser.
- **Token endpoint authentication**: use `client_secret_basic` unless the IdP
  explicitly requires `client_secret_post`.
- **Redirect / callback URI**: copy the read-only value shown by the Portal
  into the IdP application exactly.
- **Allowed email domains**: an allow-list such as `example.com`. It is
  mandatory when JIT provisioning is enabled and routes the work-email login
  to the correct connection. A domain can belong to only one enabled
  connection.
- **Create new users on first sign-in (JIT)**: creates an active, non-admin
  internal user after a signed and validated OIDC login. The user must still
  request and receive Team approval.

Production deployments behind a reverse proxy should set
`NEXORA_PUBLIC_URL=https://nexora.example.com` so the generated callback URI
uses the public HTTPS origin. OIDC issuer and discovery/token/JWKS endpoints
must use HTTPS.

The authorization-code flow uses PKCE, one-time state, nonce validation,
issuer/audience/expiry validation, and an asymmetric signing-key allow-list.
NexoraAI links an external identity using issuer plus the immutable OIDC
`sub`; it never links an existing user based only on a matching email address.
JIT users never receive System Admin rights automatically.

When more than one connection is enabled, Login accepts a work email address
and selects the unique connection assigned to its domain. It also displays the
explicit provider buttons as a fallback. The routing endpoint returns only a
provider identifier and never exposes configured domain lists or credentials.
Disabling or deleting a managed connection revokes its active Nexora OIDC
sessions. A legacy single-provider configuration remains usable during
migration and can be disabled after its replacement connection is tested.

## Configure SAML 2.0

Open **System administration → Sign-in & authentication → SAML 2.0
connections** and select **Add SAML connection**. Each connection represents
one IdP application or tenant. Create it disabled first and configure:

- **Connection / sign-in name**: the label displayed on Login.
- **Identity provider Entity ID**: the exact IdP issuer/entity identifier.
- **Identity provider SSO URL**: the HTTPS redirect-binding sign-in endpoint.
- **Identity provider X.509 signing certificate**: the current PEM certificate
  used to validate assertions. Private keys are never entered in NexoraAI.
- **ACS / Reply URL**: copy the generated, read-only URL to the IdP application.
- **SP Entity ID / Audience**: copy the generated, read-only identifier to the
  IdP audience/entity-ID setting. Its URL also serves NexoraAI SP metadata.
- **Email, first-name, and last-name attributes**: exact case-sensitive SAML
  attribute names emitted by the IdP. Email falls back to NameID when NameID is
  an email address.
- **Allowed email domains** and **JIT provisioning**: use the same restrictions
  and non-admin provisioning behavior as OIDC.

Select **Validate configuration**, save the disabled connection, register its
ACS URL and Entity ID at the IdP, and then enable it. Production deployments
must set `NEXORA_PUBLIC_URL` to the public HTTPS origin before copying these
values. A provider ID is generated in the browser before the first save, so the
displayed URLs remain stable.

SAML operates in strict mode. NexoraAI requires a signed assertion, validates
the IdP certificate, issuer, audience, destination, time conditions, one-time
RelayState, and `InResponseTo`, and rejects IdP-initiated/unsolicited responses.
The first release supports SP-initiated sign-in and local NexoraAI logout; IdP
single logout and encrypted assertions are not yet enabled.

## Review identity links

NexoraAI never links an OIDC subject or SAML NameID to an existing user merely because their
email addresses match. When a verified federated sign-in matches an existing login
email, the attempt stops and creates a seven-day pending request under **System
administration → Organization → Identity links**. A System Administrator must
verify the person and provider independently, select the intended internal
user, and approve or reject the request. This flow cannot add a federated identity
to a System Administrator account; that requires a future step-up-protected
administrative workflow.

The same page lists current OIDC and SAML links. Unlinking revokes every active session
for that identity. NexoraAI refuses to remove a user's only sign-in identity;
add and verify another sign-in method first. Link, rejection, and unlink events
retain metadata only for 365 days and do not store tokens, provider claims,
email content, or raw authentication messages.

## Deployment modes

| Local auth | Entra | OIDC / SAML | Result |
|---|---|---|---|
| enabled | disabled | disabled | Local accounts only |
| enabled | enabled/disabled | enabled | Local plus configured enterprise SSO buttons |
| disabled | enabled | disabled | Existing Entra-only behavior |
| disabled | any | enabled | Not supported; managed federation requires a Local break-glass administrator path |
| disabled | disabled | disabled | Existing no-auth behavior |

`LOCAL_AUTH_ENABLED` remains a deployment-level break-glass control and cannot
be disabled from the Portal. Entra cannot be disabled through the Portal unless
an initialized local administrator path exists, preventing an accidental
administrative lockout.

## Authentication roadmap

The next slices are SCIM 2.0 provisioning, SAML metadata import/certificate rollover and IdP single logout, Local TOTP/WebAuthn, and
optional LDAPS for disconnected enterprise networks.
