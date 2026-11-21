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

Open **System administration > LLM Providers > Enterprise AI Gateway** and:

1. Select **External AI Gateway**.
2. Select a Gateway Template. The MuleSoft template selects Client ID
   Enforcement defaults; the generic template keeps vendor-neutral settings.
3. Enter the OpenAI-compatible HTTPS base URL.
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
7. Add stable Route IDs. For each route choose:
   - **Model-Based** and map it to the model alias expected by the gateway; or
   - **Semantic** (MuleSoft only), where the Semantic Model Proxy selects the
     target model from request content and InsightSphere omits the upstream
     `model` field.
   A route can override the shared Base URL when Model-Based and Semantic
   proxies use different MuleSoft paths. Mark Tool Calling and Vision support
   accurately.
8. Choose the deployment default and save.
9. Use **Test Saved Route** for a lightweight request, then **Run Conformance**
   before production use.

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

- the reserved `system` profile maps to the configured default gateway model;
- additional profiles use `gateway:<model-id>`;
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
audit records contain status, actor, route, model ID, and exception type only;
they do not contain credentials, prompts, responses, or upstream error bodies.

## Conformance report

**Run Conformance** performs bounded requests against the selected saved route:

- gateway authentication and Chat Completions are always required;
- streaming is always required because Portal Chat streams responses;
- tool calling is required only when the configured model declares Tool
  support;
- Vision is required only when the configured model declares Vision support.
- Semantic routes additionally require a successful model-less Semantic Proxy
  request. The report may show the model selected by the upstream response.

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
`/chat/completions`. A Model-Based route sends its configured `model`. A
Semantic route uses a stable internal virtual alias but removes `model` from
the outbound Chat Completions JSON, allowing the MuleSoft Semantic Model Proxy
to route by prompt topics. Configure separate per-route Base URLs when both
proxy strategies are used. Gateway authentication and certificate settings are
currently shared across those routes; use MuleSoft proxies protected by the
same client application, or configure separate deployments when credentials
differ. Other vendor policy templates, configurable header
mappings, catalog import, and usage reconciliation remain follow-up adapters.
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
