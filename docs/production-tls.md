# Production TLS for the local runtime

`docker-compose.local-tls.yml` adds an Nginx TLS gateway in front of the
portable Compose runtime. It is an opt-in production overlay: the application
continues to listen on the private Compose network and on its existing
loopback-only maintenance port, while users enter through HTTPS on port 443.
HTTP port 80 redirects to HTTPS.

This slice terminates TLS and adds baseline response headers. It does not issue
certificates, manage DNS, configure a host firewall, or replace the existing
Local Auth bearer stored in browser `sessionStorage` with an HttpOnly cookie.

## Prerequisites

Create a DNS record for the NexoraAI hostname and obtain a certificate from the
organization PKI or a public certificate authority. Place these files in a
directory outside the repository:

```text
/opt/nexora/tls/
├── fullchain.pem
└── privkey.pem
```

The private key must not be committed, copied into the application image, or
included in NexoraAI backups. Restrict the directory and key to the deployment
operator/root account. The gateway mounts the directory read-only.

Set the following values in the ignored `.env.local-runtime` file:

```bash
NEXORA_BIND_ADDRESS=127.0.0.1
NEXORA_TLS_CERT_DIR=/opt/nexora/tls
NEXORA_HTTP_BIND_ADDRESS=0.0.0.0
NEXORA_HTTP_PORT=80
NEXORA_HTTPS_BIND_ADDRESS=0.0.0.0
NEXORA_HTTPS_PORT=443
```

The example pins the gateway image by digest. Verify the digest for the approved
registry and architecture during each planned upgrade; do not replace it with a
floating tag in production.

Keep `NEXORA_BIND_ADDRESS=127.0.0.1`. Port 50505 is then available only for
host-local maintenance and cannot bypass TLS from another machine. Restrict
ports 80 and 443 at the host firewall/security group to the intended networks.

## Start or upgrade

Use both Compose files whenever managing this deployment:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --build --wait
```

Open `https://<your-hostname>`. The certificate must contain that hostname in
its Subject Alternative Name. Requests to HTTP are redirected to HTTPS. The
gateway forwards the original host/client chain and marks the upstream request
as HTTPS. Streaming responses are not buffered.

The gateway accepts TLS 1.2 and 1.3, disables session tickets and server version
disclosure, and emits HSTS, MIME-sniffing, same-origin framing, referrer, and
browser-permission headers. The included 100 MiB request limit matches the
application's default `MAX_UPLOAD_SIZE_BYTES`; if that application limit is
raised, review `client_max_body_size` in
`deploy/nginx/nexora-tls.conf` at the same time.

## Entra configuration

For hybrid Local + Microsoft Entra authentication, register the exact HTTPS
origin and redirect URI used by the frontend. Remove obsolete HTTP production
redirect URIs after validation. A development-only localhost redirect may stay
separate. Changing managed Entra settings still requires a browser reload.

TLS does not change OAuth client secrets or the application's Fernet key. Keep
`APP_DATA_ENCRYPTION_KEY` stable across upgrades and replicas.

## Certificate renewal

Renew certificates with the host PKI/ACME process, replace `fullchain.pem` and
`privkey.pem` atomically, then recreate the gateway without rebuilding or
restarting the application:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --force-recreate tls-gateway
```

Automatic ACME issuance is intentionally outside this first slice because many
on-premises deployments use internal PKI or place NexoraAI behind an existing
enterprise load balancer. Do not expose an ACME challenge port unless that
deployment method has been selected and reviewed.

## Validation

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml ps

curl --fail --location https://<your-hostname>/config
openssl s_client -connect <your-hostname>:443 -servername <your-hostname>
```

Confirm that:

- the certificate chain and hostname validate without `--insecure`;
- **System administration → System health** lists **HTTPS gateway · Nginx** as
  healthy while this overlay is enabled;
- HTTP redirects to the expected HTTPS hostname;
- sign-in, Chat streaming, uploads, downloads, and Draw.io artifacts work;
- response headers include `Strict-Transport-Security`;
- MongoDB, MinIO API, Qdrant, Ollama, Integration Controller, and managed MCP
  containers have no public host ports;
- the MinIO console is either loopback-only or separately protected.

If an enterprise load balancer already terminates TLS, do not add a second
public gateway merely for consistency. Keep the application origin private,
send the same forwarded headers, enforce the equivalent protocol/security
policy at that ingress, and perform the same end-to-end checks.
