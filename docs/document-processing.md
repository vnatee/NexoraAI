# Document Processing and OCR

NexoraAI can select a document processor at ingestion time without changing the
existing Azure deployment configuration. If no managed profile is marked as
default, uploads continue to use the parser selected by the current environment
variables.

## Providers

- **Azure Document Intelligence (system)** uses the existing
  `AZURE_DOCUMENTINTELLIGENCE_*` configuration and Azure credential.
- **Local Text (system)** extracts embedded PDF text with pypdf. It is not OCR.
- **Docling Local / Serve** handles PDF, office documents, and images locally.
  Service mode is recommended because it keeps the large ML runtime outside the
  web container. Embedded mode is intended for development only.
- **PaddleOCR / PaddleX API** calls self-hosted General OCR or Layout Parsing.
- **Google Document AI** calls a configured OCR/Layout/Form processor through
  the regional REST API using encrypted Service Account credentials.
- **Generic OCR REST API** connects an internal/local OCR service using
  multipart or Base64 JSON and configurable response-field mappings.

Provider, profile, and routing-rule administration is under **Admin Management >
Integrations > Document Processing & OCR** and requires a system administrator.
Test the provider before assigning it to a profile used by an enabled rule.

## Routing rules

Personal, Team, and Global uploads default to **Auto — use routing rules**.
Rules resolve an exact team before the upload scope and `all`; exact file
extensions precede `*`, and priority resolves remaining order. Each rule chooses
a processing profile and controls whether an unavailable profile continues to
another rule, uses the fallback chain, or fails the upload.

Use **Explain Route** to preview a filename, scope, and optional team before
activating a rule. Enabled rules with the same scope, file specificity, and
priority cannot overlap. A system administrator may manually select a profile
on an upload; the backend independently enforces this permission.

For compatibility, an unmatched upload uses the legacy Default profile when it
supports the extension, then the startup Azure/local parser configuration.

Profile creation is protected against accidental double submission. While a
save is in progress the dialog is locked and displays `Saving…`; repeated HTTP
requests from the same dialog are idempotent. Profile names must also be unique
without regard to letter case. Existing duplicates from an older application
version are left untouched so administrators can first verify routing-rule
references and then delete only the unwanted profile.

## Run Docling Serve locally

Start the optional CPU service from the repository root:

```bash
docker compose -f docker-compose.ocr.yml up -d
```

The API is published at `http://localhost:5001`. Use the URL that is reachable
from the backend process:

- backend and Docling in the same Compose network: `http://docling:5001`
- backend running directly on the host: `http://localhost:5001`
- backend in a dev container: normally `http://host.docker.internal:5001`

The image is large and downloads local model artifacts on first use. Pin
`DOCLING_SERVE_IMAGE` to an approved version or digest for production.

To embed Docling in the backend instead, start with:

```bash
INSTALL_LOCAL_OCR=true ./app/start.sh
```

This installs `app/backend/requirements-ocr.txt` and materially increases the
backend environment size.

## Create the default local OCR profile

1. Add a **Docling Local / Serve** provider in service mode.
2. Enter the reachable service URL and select **Test**.
3. Add a processing profile, choose the provider, and list the extensions to
   route to it, for example `.pdf,.png,.jpg,.jpeg,.tiff,.docx,.pptx,.xlsx`.
4. Add OCR language codes such as `th,en`, then mark the profile as default.
5. Upload a scanned test document and verify that chunks are searchable.

The current Docling adapter emits converted Markdown as one logical page. RAG
content is searchable, but exact page-number citations remain an Azure parser
advantage until page-aware Docling output is added.

See `docs/ocr-provider-contract.md` for Generic API, PaddleOCR and Google
Document AI configuration details.
