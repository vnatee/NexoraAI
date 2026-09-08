# Azure inventory to Draw.io with MCP

NexoraAI supports two MCP deployment models in this workflow:

- Draw.io uses the official hosted endpoint at `https://mcp.draw.io/mcp`.
- Azure uses Microsoft's official Azure MCP Server image. Microsoft documents
  local package/stdio use and self-hosted remote HTTP deployment; it does not
  provide a public hosted tenant endpoint equivalent to Draw.io.

## Managed on-prem Azure MCP

The portable runtime includes an Integration Controller. It is installed on
day one but remains idle when no managed Azure connection is enabled. A System
Administrator can later provision one isolated Azure MCP instance per Portal
connection without signing in to the host OS.

```text
NexoraAI Portal
    -> NexoraAI backend (encrypted connection records)
    -> Integration Controller (private network, fixed operations)
    -> official Azure MCP container per connection
    -> Azure ARM / Resource Graph
```

The controller is deliberately separate from the application process. Only the
controller receives the Docker socket. Its API is not published to the host,
requires `INTEGRATION_CONTROLLER_TOKEN`, accepts UUID connection IDs, uses only
the configured `AZURE_MCP_IMAGE`, and does not accept arbitrary commands,
images, mounts, ports, or environment variables from the browser.

At initial platform installation, set:

```env
INTEGRATION_CONTROLLER_TOKEN=<independent random secret>
AZURE_MCP_IMAGE=mcr.microsoft.com/azure-sdk/azure-mcp@sha256:<verified-digest>
NEXORA_RUNTIME_NETWORK=nexoraai_runtime
AZURE_MCP_CPU_LIMIT=0.5
AZURE_MCP_MEMORY_LIMIT=512m
AZURE_MCP_STARTUP_TIMEOUT_SECONDS=60
AZURE_MCP_COLLECT_TELEMETRY=false
```

The controller rejects an unpinned image unless
`ALLOW_UNPINNED_AZURE_MCP_IMAGE=true`; that override is for disposable
development only. No Azure tenant credential is needed during initial NexoraAI
installation.

### Entra application and RBAC

Managed local mode needs one workload Service Principal. The MCP instance uses
it to authenticate to Azure. Grant it only `Reader` at the required
subscription/resource-group scopes. Add narrow data-plane reader roles only
when a selected inventory tool needs them.

In **Administration -> Integrations -> MCP Servers -> Browse Catalog ->
Microsoft Azure**, select **Managed on-prem container** and enter:

- Azure Tenant ID
- workload Client ID and Client Secret
- one or more Subscription IDs

The workload client secret is Fernet-encrypted in MongoDB and is never returned
to the browser. It must exist in the managed container's runtime
environment, so a root-equivalent administrator of the Docker host can inspect
it; Docker-host administration remains a trusted role. Enabling the connection
pulls the pinned image when absent, provisions or starts the container, and
waits for its private HTTP port to become ready;
disabling it stops the container; deleting an unused connection removes it.
Lifecycle audit rows contain identifiers, action, outcome, and error type only.
If the controller is temporarily unavailable during deletion, the connection is
removed from the Portal immediately, its stored credentials are erased, and a
metadata-only cleanup tombstone retries container removal when the controller
returns.

The controller starts the upstream image with HTTP transport,
`UseHostingEnvironmentIdentity`, explicit inventory tools, `--read-only`, and
`--dangerously-disable-http-incoming-auth`. That last option is acceptable only
inside this managed topology: the container has no published port, its URL is
generated and validated by NexoraAI, and the backend and controller communicate
on the private Compose network. Do not expose the container or reuse this mode
for a remote endpoint. NexoraAI independently filters ambiguous/write-oriented
tool names. A managed connection is not offered to Agents until its
provisioning status is `ready`.

The first implementation uses an internal Docker network and terminates trust
at the on-prem host boundary. Do not publish managed instance ports. For
multi-host production, replace the Docker controller with a Kubernetes
controller using narrow namespace RBAC and TLS without changing the Portal
contract.

## External Azure MCP

Select **Existing remote Azure MCP server** when an operator already hosts the
official server, such as on Azure Container Apps. Configure its HTTPS endpoint
and Entra client credentials. NexoraAI obtains and refreshes the bearer token;
do not paste an expiring access token into generic headers. This advanced mode
still requires the remote MCP server application, Nexora OAuth client ID and
secret, and OAuth scope. It does not disable incoming HTTP authentication.

## Draw.io connection

Add **Draw.io** from the catalog. The official URL is prefilled:

```text
https://mcp.draw.io/mcp
```

Run **Test**, then allowlist `create_diagram`. The hosted service uses the MCP
Apps extension for an inline interactive preview. NexoraAI currently supports
the tool result but not the MCP Apps iframe. After a successful call, NexoraAI
therefore exposes the exact generated XML as a downloadable `.drawio` artifact;
Mermaid input is exposed as `.mmd`. Azure architecture requests are guided to
use XML so the result opens directly in Draw.io. Consider implementing the MCP
Apps host protocol or self-hosting the official Draw.io server if an embedded
editor is required or Azure inventory must not be sent to a hosted endpoint.

Azure inventory does not always contain a complete application dependency
graph. Diagrams use solid connectors for relationships evidenced by returned
resource IDs/properties. Plausible conventional relationships may be included
only as dashed connectors labelled `inferred`, with a legend, and must not be
presented as observed Azure configuration.

For Azure architecture, the Agent calls Draw.io `search_shapes` with the exact
Azure service types before generating XML, then copies the returned Azure icon
styles into resource cells and places resource names below the icons. A generic
labelled box is used only when the Draw.io library has no matching Azure icon.

## Agent workflow

Assign the ready Azure and Draw.io connections to the same Team and LangGraph
Agent. A suitable request is:

```text
Read the Azure resources in resource group rg-example. Build a Draw.io
architecture diagram using only resources and relationships returned by Azure.
Preserve each Azure resource ID in the diagram metadata. Do not create, update,
or delete Azure resources.
```

Provisioning Azure resources from a diagram remains outside this slice. It
requires a validated intermediate architecture schema, generated IaC, Azure
What-If, explicit approval, and a separate write-enabled policy.

## Upstream references

- [Azure MCP Server getting started](https://learn.microsoft.com/azure/developer/azure-mcp-server/get-started)
- [Official Azure MCP Server source](https://github.com/microsoft/mcp/tree/main/servers/Azure.Mcp.Server)
- [Official Draw.io MCP server](https://www.drawio.com/docs/manual/generate/drawio-mcp-server/)
