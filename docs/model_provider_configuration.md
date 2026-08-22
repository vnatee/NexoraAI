# Runtime and model provider configuration

The application now separates deployment mode, chat completion, and text embedding configuration. Existing Azure environment variables remain supported, so Azure deployments do not need to change immediately.

> `APP_RUNTIME_MODE=local` currently applies to the model-provider layer. Search and file storage still use Azure until their provider interfaces are migrated in a later phase.

## Runtime mode

| Variable | Values | Default |
| --- | --- | --- |
| `APP_RUNTIME_MODE` | `azure`, `local` | `azure` |

## LLM provider

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | `azure_openai`, `openai`, or `openai_compatible` |
| `LLM_MODEL` | Model identifier sent to the provider |
| `LLM_DEPLOYMENT` | Azure deployment name; omitted for non-Azure providers |
| `LLM_BASE_URL` | Base URL for an OpenAI-compatible API |
| `LLM_API_KEY` | Optional provider API key |
| `LLM_ORGANIZATION` | Optional OpenAI organization |
| `LLM_AZURE_ENDPOINT` | Optional Azure OpenAI endpoint override |
| `LLM_API_VERSION` | Optional Azure OpenAI API version override |

## Embedding provider

| Variable | Purpose |
| --- | --- |
| `EMBEDDING_PROVIDER` | `azure_openai`, `openai`, or `openai_compatible` |
| `EMBEDDING_MODEL` | Embedding model identifier |
| `EMBEDDING_DEPLOYMENT` | Azure embedding deployment name |
| `EMBEDDING_DIMENSIONS` | Vector dimensions; must match the search index |
| `EMBEDDING_BASE_URL` | Base URL for an OpenAI-compatible embedding API |
| `EMBEDDING_API_KEY` | Optional provider API key |
| `EMBEDDING_ORGANIZATION` | Optional OpenAI organization |
| `EMBEDDING_AZURE_ENDPOINT` | Optional Azure OpenAI endpoint override |
| `EMBEDDING_API_VERSION` | Optional Azure OpenAI API version override |

## Local OpenAI-compatible example

```bash
APP_RUNTIME_MODE=local

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen-chat

EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=http://embedding:8001/v1
EMBEDDING_MODEL=qwen-embedding
EMBEDDING_DIMENSIONS=1024
```

An API key is optional for OpenAI-compatible providers. When omitted, the client sends the placeholder `no-key-required` because the OpenAI SDK requires a non-empty value.

## Mixed provider example

The chat and embedding providers are independent. For example, a local LLM can use the existing Azure embedding deployment:

```bash
APP_RUNTIME_MODE=local

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen-chat

EMBEDDING_PROVIDER=azure_openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DEPLOYMENT=embedding-deployment
EMBEDDING_DIMENSIONS=3072
```

The legacy variables `OPENAI_HOST`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `AZURE_OPENAI_*` continue to work. New provider-specific variables take precedence when set.

## Agent-level LLM profiles

The system provider above is always available to agents as the `system` profile. Additional providers can be registered with `LLM_PROFILES_JSON`; each agent then selects a profile from Agent Management. Existing agents without a profile continue to use `system`.

Credentials are referenced by environment-variable name through `api_key_env`. They are never stored in the agent document or returned by `/config`.

```bash
GEMINI_API_KEY=replace-me

LLM_PROFILES_JSON='[
  {
    "id": "local-qwen",
    "label": "Local Qwen",
    "provider": "openai_compatible",
    "model": "qwen3",
    "base_url": "http://ollama:11434/v1"
  },
  {
    "id": "gemini-fast",
    "label": "Gemini Fast",
    "provider": "openai_compatible",
    "model": "gemini-model-name",
    "base_url": "provider-openai-compatible-base-url",
    "api_key_env": "GEMINI_API_KEY"
  }
]'
```

Each profile requires `id`, `label`, `provider`, and `model`. Azure profiles additionally require `endpoint`; OpenAI-compatible profiles require `base_url`; OpenAI profiles require `api_key_env`.

## Admin-managed LLM providers

System administrators can also manage providers and their model/deployment lists from **Admin Management → LLM Providers**. Enabled models appear automatically in the Agent configuration dropdown. The environment-based `system` profile remains available as a fallback.

Provider API keys are encrypted before being stored in MongoDB. Configure one stable Fernet key for every application replica before saving credentials:

```bash
APP_DATA_ENCRYPTION_KEY=<stable-fernet-key>
```

Generate the value once and store it as a Docker/Kubernetes secret:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Do not rotate or remove this value until all stored provider credentials have been re-encrypted. The API never returns the encrypted value or plaintext key to the browser. Disabling a provider removes it from Agent selection while preserving its configuration; deletion is blocked while an Agent still references the provider.

### Vendor request policies

Admin-managed providers retain their vendor identity separately from the internal transport. The runtime applies a vendor policy before every Chat Completions request, including RAG query rewriting and vision requests.

| Vendor | Runtime behavior |
| --- | --- |
| Azure OpenAI / OpenAI | Standard OpenAI parameters; non-null `seed`, `n`, and streaming usage are retained. |
| Google Gemini | Omits unsupported Chat `seed`; retains `n=1` and streaming usage. |
| Anthropic Claude | Omits ignored `seed`, enforces `n=1`, and caps temperature at `1`. The OpenAI compatibility layer is intended for compatibility, not full native-Claude feature parity. |
| Ollama | Retains supported `seed`, omits undocumented `n`, and uses model-level tool capability configuration. |
| Groq | Retains `seed`, enforces `n=1`, and normalizes temperature `0` to `1e-8`. |
| OpenRouter | Retains OpenAI-compatible `seed`, `n`, and streaming usage. Actual feature support can still depend on the routed upstream model. |
| Mistral AI | Maps OpenAI `seed` to Mistral `random_seed` and omits OpenAI streaming-usage options. |
| DeepSeek | Omits fields absent from its Chat schema (`seed` and `n`) while retaining streaming usage. |
| Together AI | Retains best-effort `seed`, omits model-dependent `n`, caps temperature at `1`, and uses conservative streaming options. |
| vLLM / LocalAI | Uses their OpenAI-compatible transport; tool support remains model/backend dependent. |
| Other OpenAI-compatible | Uses a conservative policy that omits `seed`, `n`, and streaming-usage extensions. |

Cloud vendors require an encrypted API key when the provider is enabled. Azure OpenAI can continue to use Azure identity, while local vendors can run without an API key. `Supports tool / function calling` and `Supports image / vision input` remain per-model settings because these capabilities vary by model even within the same vendor.

### Tool/function-calling capability test

The Admin LLM Provider **Test** action checks every configured model in that
provider. It first verifies a normal Chat Completions request, then sends a
small tool schema and requests a deterministic function call.

- `supported`: the model returned the expected tool call. The model capability
  is enabled.
- `unsupported`: the provider rejected tool/function parameters or accepted the
  request without returning the required tool call. The capability is disabled
  and its frontend switch is locked.
- `unknown`: the probe was inconclusive, for example because of a rate limit,
  transient provider failure, or a compatibility endpoint that rejects only
  forced `tool_choice`. The existing manual setting is preserved and remains
  editable.

The database stores only capability status, a normalized reason code, and the
check timestamp. Probe prompts and provider responses are not persisted. A
model/deployment change clears the prior result to `unknown`; run **Test** again
after changing a model, deployment, API version, or compatibility gateway. Each
test makes live model requests and may consume a small number of tokens.

### Image/vision capability test

The same **Test** action sends a small in-memory PNG to each configured model
using the OpenAI-compatible multimodal message contract.

- `supported`: the provider accepted the image request. The model's vision
  capability is enabled automatically.
- `unsupported`: the provider explicitly rejected image/multimodal input. The
  capability is disabled and its switch is locked.
- `unknown`: the probe was inconclusive because of a transient, quota, network,
  or ambiguous compatibility error. The administrator's existing setting is
  preserved and remains editable.

After saving/testing the model, select that LLM profile on a Legacy Agent and
enable **Image input** under **Agent Info → Message attachments**. Chat and Ask
then accept user-attached images without a per-message Vision switch. The
selected managed model receives those images directly and does not require
`USE_GPT4V` or `AZURE_VISION_ENDPOINT`.

The Provider card shows per-model capability tags from the latest conclusive
Test result. Chat and Ask refresh those capabilities immediately after a
provider Save/Test/Delete. Image input and Agentic Retrieval remain mutually
exclusive only for a request that actually contains an image. Enabling the
Agent image policy grants permission but does not force text-only or
document-only messages through the Vision path.

The legacy environment feature remains separate: Azure Knowledge image
embeddings/retrieval require both `USE_GPT4V=true` and a valid absolute HTTP(S)
`AZURE_VISION_ENDPOINT`. With the flag but no valid endpoint, retrieval falls
back to text instead of attempting a malformed Computer Vision URL. These
settings are not required merely to send an image attachment to a
Portal-managed vision model.
