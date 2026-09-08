# Business document integrations

NexoraAI can connect a Team-scoped Agent to Microsoft 365 Documents or Google
Workspace. Credentials are encrypted with the existing
`APP_DATA_ENCRYPTION_KEY`; API responses never return stored secrets.

## Capabilities

- Search and list documents in a configured drive or folder.
- Read `.docx`, `.xlsx`, `.pptx`, PDF, text, CSV, and Markdown content.
- Export native Google Docs, Sheets, and Slides before extracting their text.
- Optionally create Word/Docs, Excel/Sheets, and PowerPoint/Slides documents.
- Grant `Read` and `Create` independently on each Agent binding. `Create` is
  available only when the connection is configured as **Read & create**.

Creating a document is classified as a write tool. Read-only is the default,
and Create is disabled on a new Agent binding until an administrator enables
it explicitly.

## Microsoft 365

Create an Entra application and use application permissions with tenant admin
consent. Read-only connections need Microsoft Graph `Files.Read.All` and
`Sites.Read.All`. Add `Files.ReadWrite.All` only when document creation is
required.

The portal requires:

- Entra Tenant ID
- Application (Client) ID
- Client Secret
- Drive ID for the OneDrive or SharePoint document library
- Optional Root Folder Item ID

The Drive ID can be obtained through Microsoft Graph Explorer by listing the
site drives, for example `GET /sites/{site-id}/drives`.

## Google Workspace

Enable Google Drive API and create an OAuth client. Obtain an offline refresh
token using a read-only Drive scope, or a Drive file/write scope when document
creation is required. The portal requires:

- OAuth Client ID
- OAuth Client Secret
- OAuth Refresh Token
- Optional Root Folder ID
- Optional Shared Drive ID

For Shared Drives, the OAuth user must be a member and must have permission to
read or create files in the selected folder.

## Administration workflow

1. Open **Administration → Integrations → Business Documents**.
2. Add and test a connection.
3. If it was created in the unassigned catalog, assign it to one Team.
4. Open the Team Agent, select **Integrations → Documents**, and add a binding.
5. Keep `Read` enabled and grant `Create` only to Agents that need it.

Connections cannot be deleted while an Agent binding references them. Moving a
connection between Teams is intentionally not supported by the edit form.
