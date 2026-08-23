# Local and Microsoft Entra authentication

NexoraAI can run with Microsoft Entra ID, application-managed local accounts,
or both. Both identity providers resolve to the existing application `users`
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

## Deployment modes

| Local auth | Entra | Result |
|---|---|---|
| enabled | disabled | Local accounts only |
| enabled | enabled | Local and Entra sign-in are both shown |
| disabled | enabled | Existing Entra-only behavior |
| disabled | disabled | Existing no-auth behavior |

`LOCAL_AUTH_ENABLED` remains a deployment-level break-glass control and cannot
be disabled from the Portal. Entra cannot be disabled through the Portal unless
an initialized local administrator path exists, preventing an accidental
administrative lockout.
