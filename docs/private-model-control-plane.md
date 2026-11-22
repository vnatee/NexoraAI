# Private Model Control Plane

InsightSphere supports a private-model topology in which GPUStack manages GPU
workers and deploys vLLM, while the InsightSphere Enterprise AI Gateway remains
the policy and routing boundary.

```text
Users / channels
       |
InsightSphere Agents, Knowledge, Tools and Guardrails
       |
InsightSphere Enterprise AI Gateway policy
       |
GPUStack OpenAI-compatible route and API key
       |
GPUStack scheduler ---- GPU worker(s) ---- vLLM model instance(s)
```

GPUStack is not a replacement for InsightSphere governance. It owns model
placement, GPU capacity and inference-runtime lifecycle. InsightSphere keeps
Team and Agent authorization, Knowledge ACLs, tool policy, guardrails, audit,
model aliases and fail-closed provider routing.

## Supported topology

- The GPUStack control plane may run on a CPU host. The supplied Compose
  overlay pins GPUStack `v2.3.1`, persists its state and binds its UI to
  loopback only.
- Production GPU workers run separately on Linux hosts with a supported GPU,
  vendor driver, Docker Engine and NVIDIA Container Toolkit where applicable.
- GPUStack deploys vLLM containers on workers. Do not install vLLM in the
  InsightSphere application container.
- InsightSphere reaches the GPUStack OpenAI-compatible `/v1` route through the
  existing External AI Gateway mode. Its inference key is separate from the
  dedicated GPUStack management key used for inventory and approved model
  lifecycle actions; both are encrypted by the existing Fernet secret helpers.
- System Health probes only `/healthz`. The System Administration inventory
  endpoint additionally reads authenticated `/v2/workers`, `/v2/models`, and
  `/v2/model-instances` data, but returns only bounded capacity and readiness
  fields. Worker addresses, device UUIDs, model paths, environment values,
  credentials, prompts, and responses are not exposed or logged.

## Start the control plane

Copy the environment template values into the protected runtime environment,
copy `docs/nexora-runtime.example` to `.env.nexora-runtime`, and keep
`MODE=private-enterprise`. Validate the selected overlays, then start only the
infrastructure layer:

```bash
./nexora preflight
./nexora infra up
```

The private-enterprise mode disables the bundled Ollama services. It starts
GPUStack, MongoDB, MinIO, Qdrant, and the Integration Controller first. After
the approved GPU workers and vLLM routes are Ready, start InsightSphere with
`./nexora up`. This prevents two local inference stacks from competing for GPU
and memory on the same deployment.

Retrieve the one-time initial administrator password without writing it to a
shell history or ticket:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.external-ai-runtime.yml \
  -f docker-compose.private-llm.yml exec gpustack \
  cat /var/lib/gpustack/initial_admin_password
```

Open `http://127.0.0.1:18080` locally, or use an SSH tunnel. Change the initial
password immediately. Do not expose this port directly to users or the public
Internet.

## Console access and future SSO

**Private LLM Infrastructure** stores a browser-facing **Console URL** separately
from the internal control-plane URL. The System-Admin-only **Open GPUStack
Console** action opens that URL in a new tab with `noopener`/`noreferrer`. It
never appends the GPUStack API key, password, InsightSphere bearer token, or
other credentials to the URL.

Use **Local login** initially. For local development, the Console URL can be
`http://127.0.0.1:18080`; a browser on another workstation must instead use an
approved internal address or an SSH tunnel. Production should publish GPUStack
only through a private HTTPS reverse proxy and a separate hostname such as
`https://gpustack.internal.example`.

GPUStack v2.3.1 supports OIDC and SAML external authentication. To enable SSO
later:

1. Create a separate OIDC client or SAML service-provider registration for
   GPUStack in the same organization IdP used by InsightSphere. Do not reuse an
   InsightSphere client secret.
2. Configure GPUStack's external URL and its OIDC (`--oidc-*`) or SAML
   (`--saml-*`) startup settings through deployment-owned protected
   configuration. Keep client secrets and SAML private keys outside Git.
3. Restrict the reverse proxy and GPUStack roles to approved platform
   administrators, set trusted proxy CIDRs, and verify login, logout, session
   expiry and role mapping.
4. Change **Console sign-in** in InsightSphere to **OIDC SSO** or **SAML SSO**.
   This field records the expected operator experience; GPUStack remains the
   authority that authenticates its console.

When the browser already has an active IdP session, opening the console should
complete the normal GPUStack SSO redirect without another password prompt. If
the IdP session has expired, the IdP may still require authentication or MFA.
InsightSphere does not act as an IdP and does not bypass that decision.

## Add GPU workers and deploy vLLM

1. In GPUStack, create a Docker GPU cluster and generate a short-lived worker
   registration command.
2. Run the generated command on each approved GPU host. Treat its worker token
   as a secret and do not store it in this repository or operational tickets.
3. Confirm the worker is Ready and review GPU type, total/free VRAM, RAM and
   disk capacity before model deployment.
4. Deploy the approved model using the vLLM backend. Start with one replica and
   explicit GPU placement. Enable GPUStack's inference health check.
5. Wait for the model route and every required replica to report Running.
6. Create a dedicated GPUStack API key for InsightSphere. Use one key per
   environment and rotate it through the Gateway administration workflow. If
   native lifecycle actions are required, its principal must be able to read
   inventory and create, update, and restart models; do not grant worker,
   identity, or cluster administration solely for these actions.
7. Deploy a separate embedding route when Knowledge/RAG is required. Chat and
   embedding routes may use different model families and scaling policies.
8. Run `./nexora up`, open **System Administration > LLM Providers > Private
   AI Infrastructure**, save the management connection, and verify worker,
   GPU, model, and model-instance inventory.

Sizing must be based on the selected model, precision/quantization, context
window, concurrency target, KV-cache requirement and measured tokens/second.
The model artifact size alone is not a VRAM sizing calculation.

## Connect InsightSphere

In **System Administration > LLM Providers > Enterprise AI Gateway**:

1. Select **External AI Gateway** and **Generic OpenAI-compatible Gateway**.
2. Set the base URL to `http://gpustack:80/v1` when both services share this
   private Compose network. For separate hosts, use a private HTTPS name.
3. Select API-key authentication and enter the dedicated GPUStack API key.
4. Create a stable InsightSphere model alias whose upstream model ID exactly
   matches the GPUStack model route. Declare Tool/Vision capability only after
   it has been verified for that model and vLLM configuration.
5. Save and run **Gateway Conformance**. Do not activate production Agents
   unless every required check passes.

For same-network HTTP, the deployment owner must explicitly set
`AI_GATEWAY_ALLOW_INSECURE_HTTP=true`. This exception is suitable only for an
isolated private container network; use HTTPS across hosts or network zones.

In **Private LLM Infrastructure**, configure the GPUStack control-plane URL and
a dedicated management API key. Public host names require HTTPS. Plain HTTP is
accepted only for loopback, private IPs, or internal service names such as
`http://gpustack:80`. The inventory paginates the supported GPUStack v2.3.1
management API and reports workers, GPU/VRAM capacity, model readiness and
running instances without copying GPUStack's sensitive source fields.

## Native InsightSphere model lifecycle

**Private AI Infrastructure** is the normal operator surface and carries a
small **Powered by GPUStack** attribution. System Administrators can deploy a
bounded Hugging Face vLLM workload, scale it (including scale-to-zero stop),
restart its instances, inspect worker/model capacity, and use the existing
controlled Gateway rollout without receiving the GPUStack management key in
the browser. Every lifecycle action requires explicit confirmation and records
an integration lifecycle audit event.

The guided deployment can search GPUStack's curated model catalog by workload,
then loads the Hugging Face/vLLM variants available for the selected Ready
cluster. It displays bounded model size, capability, license, backend,
quantization, and mode metadata and fills the repository without requiring the
operator to know its exact identifier. **Custom model** remains available for
public Hugging Face repositories not present in the catalog.

Before confirmation, **Check resource fit** calls GPUStack's model-evaluation
API for the exact route name, repository, workload, cluster, and replica count.
InsightSphere displays the bounded RAM/VRAM claim and compatibility/scheduling
messages. Deployment remains disabled until the current configuration is
compatible; changing any field invalidates the prior result. The deploy API
also repeats this evaluation server-side immediately before creating the model,
so bypassing the browser cannot skip the gate.

The deployment contract intentionally accepts only the model route name,
Hugging Face repository, LLM/Embedding workload, Ready deployment cluster, and
replica count. The cluster is selected from the bounded `/v2/clusters`
inventory; its identifier is never guessed or hard-coded. Arbitrary
environment variables, runtime commands, image names, backend arguments, and
credentials are not accepted through InsightSphere. Use **Advanced console**
for those GPUStack-owned capabilities. Manual scale/stop is rejected while a
GPUStack scaling schedule is enabled so the two control loops cannot conflict.

## Controlled rollout and rollback

Use immutable model route names, for example `assistant-14b-candidate`, and a
stable InsightSphere alias, for example `private-general`. Do not replace a
running model in place.

1. Deploy the candidate route beside the current route.
2. In **Private LLM Infrastructure**, select a Model-Based Enterprise Gateway
   proxy, the candidate GPUStack model, and the minimum ready replicas/workers.
3. Run preflight. InsightSphere verifies the candidate is Running, meets the
   replica threshold, and has Running instances placed on enough distinct
   workers. It records a pending plan but does not change runtime traffic.
4. Review and explicitly approve the plan. InsightSphere rechecks capacity,
   runs required Gateway Conformance against the candidate in memory, and only
   then updates that one proxy route and refreshes the runtime registry.
5. Test representative Agent workflows with non-sensitive acceptance prompts,
   then monitor latency, errors, saturation, output quality and policy
   decisions.
6. Use the recorded Rollback action to validate and restore the exact prior
   route. The action is rejected if the proxy changed outside the plan. Retain
   the old deployment until the observation window closes.

Semantic proxies are intentionally excluded from this model-target rollout:
their upstream gateway selects a model from request meaning, so switching one
model identifier would be misleading. Manage their topic/model policy in the
semantic gateway and validate it through Semantic Probe Conformance instead.

Stop a rollout if a required conformance check fails, a worker is unhealthy,
GPU memory is persistently saturated, error/timeout rate exceeds the agreed
threshold, or an Agent acceptance test regresses.

## Backup and recovery

- Back up the `nexora_gpustack_data` volume and the external database if one is
  configured. Store backups encrypted and test restore separately.
- Backing up GPUStack does not back up InsightSphere MongoDB, Knowledge objects,
  vectors or the stable `APP_DATA_ENCRYPTION_KEY`; retain the existing
  InsightSphere backup procedure.
- Model caches are rebuildable and should not be treated as the only copy of an
  approved model artifact.
- After recovery, verify workers, model routes, API-key rotation, Gateway
  Conformance and one end-to-end Agent request before reopening traffic.

## Production acceptance

- GPUStack UI is private and administrator-authenticated.
- At least one GPU worker and the approved vLLM route are healthy.
- Capacity and failure testing cover expected concurrency and one worker/model
  restart.
- Required Gateway Conformance checks pass.
- Alias rollback is demonstrated without editing Agent definitions.
- Backups and restore are demonstrated in an isolated environment.
- Logs, traces and audit records contain no API keys, prompts or responses by
  default.

