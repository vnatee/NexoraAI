# Approved Web Sources

## Purpose

Approved Web Sources lets an authorized administrator capture a bounded,
point-in-time copy of a public website and review the scan before it becomes
searchable Knowledge. Agents search only the confirmed copy through the existing
RAG and Data Group access controls. This feature is not live web search and does
not grant an Agent unrestricted internet access.

## Scope and permissions

- Company sources require **Manage global uploads**.
- Team sources require Team membership and **Manage team uploads**.
- A Team source must be assigned to at least one Data Group owned by that Team.
- The backend rechecks the scope and Data Groups at both scan and confirmation
  time; hiding a control in the Portal is not the security boundary.

## Scan, verify, and index

1. Open **Approved Web Sources** from the management menu.
2. Select **Company Data** or **Team Data**, when both scopes are available.
3. For Team Data, select one or more Data Groups.
4. Enter a public `http://` or `https://` root URL such as
   `https://docs.example.com/product/`.
5. Select **Crawl depth**:
   - **0 — Root only** scans only the submitted page;
   - **1 — Recommended** scans the root plus links found on it; or
   - **2 — Extended depth** follows one additional link level.
6. Select **Fetch mode**:
   - **Auto — Recommended** starts with standard HTTP and uses an isolated
     browser only when the response is a JavaScript application shell;
   - **Standard HTTP** never executes JavaScript; or
   - **Browser-rendered** renders every selected page with Chromium.
7. Select a scan limit:
   - **Standard** uses the normal bounded page and byte limits; or
   - **Extended** allows up to 250 pages and 100 MiB by default. It is still
     bounded and should be used only when the website scope has been reviewed.
8. Select **Scan & Verify**. This creates a temporary staged snapshot only.
   Nothing from the scan is searchable in RAG at this point.
9. Review the page count, total extracted bytes, URLs, titles, skipped-page
   issues, and any **Partial snapshot** warning. All pages are selected initially;
   clear individual checkboxes or use **Select all pages** to choose the exact
   pages to retain.
10. Select **Confirm Index** to queue only the checked pages, or **Discard Scan**
   to remove the entire staged scan. Confirmation returns immediately; indexing
   continues in the background and the page may be closed safely.

The **Recent indexing jobs** panel reports completed/selected pages, current
status, attempt number, and a progress bar. Failed jobs retain an error for each
failed URL and expose **Retry failed pages**. Pages already indexed successfully
are not repeated. A worker lease and heartbeat let another application process
resume queued or interrupted work after a restart without weakening the staged
content integrity check.

Submitting the same canonical root URL and confirming it refreshes the indexed
snapshot. New pages are indexed before stale pages are removed. If indexing
fails, the previous snapshot is retained and the staged scan remains available
for retry until expiry.

The server verifies every selected staged page with SHA-256 immediately before
indexing. Hashes remain an internal integrity control and are not shown in the
normal review UI. A selected URL must belong to the server-side manifest, and a
changed or missing staging object is rejected. Unconfirmed scans expire after
24 hours by default and a cleanup worker removes their temporary objects and
manifests. Closing or discarding the review also requests immediate cleanup.

## Crawl contract

The Phase 1 crawler:

- includes the approved root page and follows the selected depth of 0, 1, or 2;
- stays on the same hostname and under the approved path;
- removes fragments and query strings from discovered links to avoid duplicate
  or token-bearing URLs;
- honors an available `robots.txt` policy;
- accepts HTML/XHTML only and does not download arbitrary files;
- can render public JavaScript applications in Auto or Browser-rendered mode
  using a fresh isolated Chromium context; it does not sign in, reuse user
  cookies, solve CAPTCHAs, or bypass access controls;
- limits redirects, pages, bytes per page, total bytes, and request duration,
  and marks a bounded result as partial when a ceiling stops traversal;
- rejects URL credentials, query strings on the root URL, custom ports, and
  hostnames resolving to private, loopback, link-local, reserved, multicast, or
  unspecified addresses; and
- revalidates each redirect and requested page before retrieval.

Each confirmed page contains evidence metadata in the searchable document:
source title, canonical source URL, retrieval timestamp, and SHA-256 content
hash. Citations continue to open the original public page.

## Configuration

| Environment variable | Default | Maximum | Meaning |
| --- | ---: | ---: | --- |
| `WEB_SCRAPE_MAX_PAGES` | 50 | 250 | Standard scan page ceiling |
| `WEB_SCRAPE_MAX_PAGE_BYTES` | 2 MiB | 10 MiB | Decompressed bytes per page |
| `WEB_SCRAPE_MAX_TOTAL_BYTES` | 20 MiB | 100 MiB | Standard total byte ceiling |
| `WEB_SCRAPE_EXTENDED_MAX_PAGES` | 250 | 250 | Extended scan page ceiling |
| `WEB_SCRAPE_EXTENDED_MAX_TOTAL_BYTES` | 100 MiB | 100 MiB | Extended total byte ceiling |
| `WEB_SCRAPE_TIMEOUT_SECONDS` | 15 | 60 | Per-request timeout |
| `WEB_SCRAPE_MIN_TEXT_CHARS` | 80 | 10,000 | Minimum extracted text length |
| `WEB_SCRAPE_BROWSER_EXECUTABLE` | image default | — | Chromium executable for rendered scans |
| `WEB_SCRAPE_BROWSER_MAX_PAGES` | 25 | 100 | Rendered-page ceiling per scan |
| `WEB_SCRAPE_BROWSER_SETTLE_MS` | 750 ms | 5,000 ms | Extra render settle time |
| `WEB_SOURCE_SCAN_RETENTION_HOURS` | 24 | 72 | Unconfirmed staging retention |
| `WEB_SOURCE_SCAN_CLEANUP_INTERVAL_SECONDS` | 3600 | — | Cleanup worker interval; minimum 60 |
| `WEB_SOURCE_INDEX_RECOVERY_INTERVAL_SECONDS` | 15 | — | Queued/interrupted index-job recovery interval; minimum 5 |

For Docker Compose, define these values in `.env.local-runtime`; the Compose
file passes them into the application container.

## Security and operational notes

- Approval is two-step: scan permission does not make content searchable;
  confirmation is separately authorized.
- Temporary objects contain extracted evidence, while MongoDB stores only the
  review manifest and staging references. No page body is stored in the
  manifest.
- Retrieved HTML is untrusted evidence. Existing RAG prompt-injection
  sanitization and Knowledge ACLs remain in force.
- Application URL checks reduce SSRF risk, but production deployments should
  also enforce outbound network policy and DNS controls to prevent DNS-rebinding
  or proxy bypass at the infrastructure layer.
- Browser rendering keeps the approved hostname and public-address checks for
  navigation and subresources, blocks service workers plus image/media/font
  downloads, and uses a new cookie-free browser context for each scan. It is a
  compatibility mode, not an anti-bot or authenticated-browser mechanism.
- Website scanning remains synchronous so the reviewer can inspect the staged
  result. Confirmed indexing uses a MongoDB-backed background job with a worker
  lease, heartbeat, per-URL progress, and retry/resume after an application
  restart. The worker currently runs inside an application process; a separate
  worker service is recommended for future high-volume or multi-replica use.
- Confirm that crawling and retaining the selected website is allowed by the
  site's terms, licensing, privacy policy, and organizational policy.

## Planned next phases

### Phase 2 — governed live web search

Add a provider-neutral search adapter that is opt-in per Agent. It will require
allowed domains, result/query limits, safe retrieval of selected results,
short-lived caching, source/date citations, metadata-only audit, and separate
permissions from permanent Knowledge ingestion.

### Phase 3 — authenticated sources

Add authenticated connectors in an isolated worker, with encrypted credentials,
domain and redirect allowlists, controlled egress,
download limits, audit, and explicit handling of MFA/session expiry. This must
not reuse end-user browser cookies or expose credentials to prompts or tools.
