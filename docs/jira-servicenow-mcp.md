# Jira, Confluence, and ServiceNow MCP connections

NexoraAI treats these connections as externally hosted MCP servers. It does not
start or manage a Docker container for either connection.

## Atlassian Jira and Confluence

The catalog preset uses Atlassian's official hosted Rovo MCP endpoint:

`https://mcp.atlassian.com/v1/mcp/authv2`

Atlassian requires OAuth 2.1. The current NexoraAI connection form accepts an
OAuth bearer access token and encrypts it with the existing provider-secret
helpers. Atlassian API tokens are not accepted. Because an access token can
expire, replace it in the connection when required. A browser-based OAuth flow
with refresh-token rotation remains a separate product slice.

The remote server applies the permissions of the Atlassian user represented by
the token. Administrators should use a dedicated least-privilege account when
the connection is shared with a Team.

## ServiceNow

ServiceNow MCP is hosted by the customer's ServiceNow instance. A ServiceNow
administrator must activate and configure the MCP Server capability, select the
exposed tools, configure ACLs, and provide the resulting Streamable HTTP
endpoint. NexoraAI accepts HTTPS endpoints under `service-now.com` and an OAuth
bearer access token, which is stored encrypted.

Custom ServiceNow domains can still be connected through the Custom Streamable
HTTP catalog item after the deployment owner has validated the target.

## Security boundaries

- Connections retain existing Team ownership and Agent assignment checks.
- Credentials are never returned to the browser after saving.
- Allowed-tools and read-only/read-write policy remain enforced by NexoraAI.
- Deleting a connection removes its encrypted credential through the existing
  MCP deletion path.
