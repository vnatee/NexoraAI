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

Provider and profile administration is under **Admin Management > Integrations >
Document Processing & OCR**. Test the provider before assigning it to a default
profile.

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
