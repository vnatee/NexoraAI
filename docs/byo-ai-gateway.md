# Bring Your Own AI Gateway

InsightSphere can enforce one deployment-wide LLM route without coupling the
product to a specific gateway vendor. The external route uses an
OpenAI-compatible API and applies to Portal Chat, Ask, LangGraph Agents, Agent
Invocation API, external channels, delegated Agents, and Vision-capable
requests.

## Routing modes

- **Built-in Gateway** keeps the current environment and System-managed LLM
  providers available to Agents.
- **External AI Gateway** exposes only models declared on the gateway profile.
  Existing Agent model references that are no longer available resolve to the
  gateway default. Direct provider connections remain stored but are not
  reachable by runtime requests.
- **Direct Development** exposes environment-defined profiles only. It is
  unavailable unless the deployment explicitly sets
  `ALLOW_DIRECT_AI_PROVIDER_MODE=true` and must not be enabled in production.

External mode is fail-closed. An unavailable gateway causes the LLM request to
fail; InsightSphere does not retry through Azure OpenAI, OpenAI, a local model,
or another managed provider.

## Configure

Open **System administration > AI Runtime & Models**. Use **Routing Overview**
to confirm the active policy, **Built-in Providers** for direct provider
records, and **Enterprise Gateways** for the enforced gateway configuration.
Built-in records remain visible as configured-but-inactive while External mode
is selected, so rollback does not require recreating credentials.

In **Enterprise Gateways**:

1. Select **External AI Gateway**.
2. Select a Gateway Template. The MuleSoft template selects Client ID
   Enforcement defaults; the generic template keeps vendor-neutral settings.
3. Enter the shared HTTPS Gateway Base URL (normally the origin/root before the
   individual MuleSoft proxy path).
4. Select authentication:
   - API key;
   - OAuth 2.0 client credentials, using `client_secret_post` or
     `client_secret_basic`, with optional scope and audience; or
   - MuleSoft Client ID Enforcement, which sends `client_id`, `client_secret`,
     and the gateway-routing `ClientId` header without requesting an OAuth
     access token; or
   - gateway/network-managed authentication.
5. Add a custom CA when the gateway uses an enterprise/private trust chain.
6. Optionally enable mTLS and add the client certificate and private key.
7. Add stable Model Proxy IDs. For each proxy configure its relative Proxy Path
   (for example `smartmodel/v1`) under the shared Gateway Base URL, then choose:
   - **Model-Based** and map it to the model alias expected by the gateway; or
   - **Semantic** (MuleSoft only), where the Semantic Model Proxy selects the
     target model from request content and InsightSphere omits the upstream
     `model` field.
   A proxy can use the advanced full-URL override when it is hosted on a
   different origin. Mark Tool Calling and Vision support accurately.
8. Choose the deployment Default Proxy and save.
9. Use **Test Proxy** and **Run Conformance** directly on every saved proxy card
   before production use.

Semantic proxy cards require an ephemeral **Semantic Probe Prompt**. Enter a
short request that matches one of the topics configured in the MuleSoft
Semantic Model Proxy. A generic health prompt might not match any topic and can
correctly produce `route_or_model_not_found`. The probe is sent only for the
operator-initiated Test/Conformance request; InsightSphere does not persist it
in Gateway settings or lifecycle audit metadata.

API keys, OAuth client secrets, CA material, client certificates, and private
keys are encrypted with the existing Fernet application-secret contract. The
Portal returns only `has_*` indicators. Keep `APP_DATA_ENCRYPTION_KEY` stable
across replicas, upgrades, and restarts.

HTTP gateway and token URLs are rejected by default. A local development
deployment may set `AI_GATEWAY_ALLOW_INSECURE_HTTP=true`; production should use
HTTPS and should leave this flag unset.

## Runtime contract

The persisted policy is resolved before the LLM profile registry is built.
With External mode active:

- the reserved `system` profile maps to the configured Default Proxy;
- additional profiles use `gateway:<proxy-id>`;
- every effective profile uses the governed client for its configured route;
- old managed-provider profile IDs fall back to gateway `system`, never to the
  previously selected direct provider;
- Azure AI Search agentic retrieval is rejected while External mode is active
  because its internal model call cannot be routed through the external
  gateway; standard text/vector/hybrid RAG remains available;
- startup fails if the saved external policy cannot be read or constructed;
- runtime refresh rolls back a policy update when the new client/profile
  registry cannot be constructed.

Credential-bearing URLs are rejected. Connection-test responses and lifecycle
audit records contain status, actor, proxy ID, and exception type only;
they do not contain credentials, prompts, responses, or upstream error bodies.

## Conformance report

**Run Conformance** performs bounded requests against the selected saved proxy:

- gateway authentication and Chat Completions are always required;
- streaming is always required because Portal Chat streams responses;
- tool calling is required only when the configured model declares Tool
  support;
- Vision is required only when the configured model declares Vision support.
- Semantic routes additionally require a successful model-less Semantic Proxy
  request using the operator-supplied Semantic Probe Prompt. The same topic-
  matching context is retained for streaming, Tool Calling and Vision probes.
  The report may show the model selected by the upstream response.

The report returns pass/fail/skipped, safe error categories, HTTP status, and
allowlisted upstream correlation IDs. It never returns response bodies,
prompts, completions, credential headers, or secrets. A failed required check
marks the route **Not ready** but does not route around the configured gateway.

## Gateway compatibility

P1.1 requires the standard OpenAI Chat Completions shape. The generic layer can
therefore sit in front of MuleSoft AI Chain Gateway, Azure API Management,
Kong, LiteLLM, Portkey, an internal gateway, GPUStack/vLLM, or another product
that exposes a compatible endpoint.

MuleSoft Client ID Enforcement and its Portal template are the first
vendor-specific adapter. Configure the base URL only through the version segment (for example,
`https://gateway.example/smart-model/v1`); the OpenAI client appends
`/chat/completions`. InsightSphere resolves each endpoint as `Gateway Base URL
+ Proxy Path`; for example, `https://gateway.example/smartmodel/v1`. A
Model-Based proxy sends its configured `model`. A Semantic proxy uses a stable
internal virtual alias but removes `model` from
the outbound Chat Completions JSON, allowing the MuleSoft Semantic Model Proxy
to route by prompt topics. Gateway authentication and certificate settings are
currently shared across those routes; use MuleSoft proxies protected by the
same client application, or configure separate deployments when credentials
differ. Other vendor policy templates, configurable header
mappings, catalog import, and usage reconciliation remain follow-up adapters.

The administration API uses `proxies` and `default_proxy_id`. It continues to
return the earlier `models` and `default_model_id` names as compatibility
aliases, and existing saved endpoints remain operational as per-proxy full-URL
overrides until an administrator separates the shared Base URL and Proxy Path.
They must not weaken the central Agent/Data/Tool authorization enforced inside
InsightSphere.

## Recovery

If a saved external route is healthy enough for the Portal but the upstream
model is unavailable, a System Administrator can switch the routing mode back
to **Built-in Gateway**. If the Portal cannot start because its persisted
external configuration cannot be decrypted, restore the stable
`APP_DATA_ENCRYPTION_KEY` rather than replacing or clearing encrypted values.

Do not enable the test-only `SKIP_MANAGED_LLM_PROVIDER_LOAD` setting in a real
deployment. It exists for service-free test startup and bypasses database-backed
route loading.
