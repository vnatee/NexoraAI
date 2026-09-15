# OCR provider contract

Managed OCR providers normalize their output into zero-based pages containing
text plus optional table and confidence metadata. The current RAG index consumes
the page text/page number. Optional metadata is available at parser time but is
not indexed yet; it is reserved for later ingestion-status and chat-image
features.

## Generic OCR API

The provider supports either multipart upload or Base64 JSON. The default
Nexora JSON contract is:

```json
{
  "pages": [
    {
      "page_number": 1,
      "text": "Recognized page text",
      "tables": [],
      "confidence": 0.98
    }
  ]
}
```

For Base64 JSON requests the service receives:

```json
{
  "file": "BASE64_CONTENT",
  "filename": "invoice.pdf",
  "mime_type": "application/pdf"
}
```

Response paths are dot-separated and configurable in the provider dialog. API
key and bearer credentials are encrypted with `APP_DATA_ENCRYPTION_KEY` and are
never returned by the management API.

## PaddleOCR / PaddleX

The adapter uses PaddleX basic serving directly:

- General OCR: `POST /ocr`
- Layout/PP-Structure: `POST /layout-parsing`
- Request: Base64 `file`, with `fileType=0` for PDF and `1` for images

Start the optional CPU template:

```bash
docker compose -f docker-compose.ocr.yml --profile paddleocr up -d paddleocr
```

The first build and first inference download large Python/model artifacts. In
production, pin package/model versions and bake the model cache into an approved
image. Configure the provider URL as `http://paddleocr:8080` on the same Compose
network, or normally `http://host.docker.internal:8080` from the dev container.

## Google Document AI

Create a Google Document AI processor and a least-privilege service account.
The provider requires:

- Google Cloud project ID
- processor location and ID
- optional processor version
- Service Account JSON

The backend creates a short-lived OAuth assertion and calls the regional REST
`processors:process` endpoint. The stored Service Account JSON is encrypted with
`APP_DATA_ENCRYPTION_KEY`. Grant only processor get/process permissions required
by the selected processor and environment.
