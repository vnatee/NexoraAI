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
  existing External AI Gateway mode. The GPUStack API key is encrypted by the
  existing Fernet secret helpers.
- The application probes only `/healthz` for System Health. It does not copy
  GPUStack credentials or model inventory into logs.

## Start the control plane

Copy the environment template values into the protected runtime environment,
then render and start the overlay:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.private-llm.yml config --quiet

docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.private-llm.yml up -d gpustack app
```

Retrieve the one-time initial administrator password without writing it to a
shell history or ticket:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.private-llm.yml exec gpustack \
  cat /var/lib/gpustack/initial_admin_password
```

Open `http://127.0.0.1:18080` locally, or use an SSH tunnel. Change the initial
password immediately. Do not expose this port directly to users or the public
Internet.

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
   environment and rotate it through the Gateway administration workflow.

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

## Controlled rollout and rollback

Use immutable model route names, for example `assistant-14b-candidate`, and a
stable InsightSphere alias, for example `private-general`. Do not replace a
running model in place.

1. Deploy the candidate route beside the current route.
2. Run GPUStack inference health checks and InsightSphere Gateway Conformance.
3. Test representative Agent workflows with non-sensitive acceptance prompts.
4. Update the stable alias during an approved change window.
5. Monitor latency, errors, saturation, output quality and policy decisions.
6. Roll back by restoring the prior alias target. Retain the old deployment
   until the observation window closes.

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

