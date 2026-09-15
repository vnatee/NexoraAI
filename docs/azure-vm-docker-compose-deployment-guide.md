# NexoraAI Azure VM + Docker Compose Deployment Guide

**Language:** English  
**Audience:** Azure administrators, Linux platform engineers, security teams, and NexoraAI deployment operators  
**Last verified:** 9 September 2026  
**Applies to:** `docker-compose.local-runtime.yml` with the optional `docker-compose.local-tls.yml` overlay

## 1. Purpose and deployment scope

This guide deploys the complete NexoraAI self-hosted runtime on one Azure Linux virtual machine. It uses the repository's supported Docker Compose definitions and retains the current Managed Azure MCP behavior, including the Integration Controller that creates connection-specific MCP containers through the host Docker daemon.

The deployment contains:

- NexoraAI application and production frontend bundle;
- MongoDB for identities, Teams, configuration, jobs, licenses, and server-side Chat history;
- MinIO for Knowledge source objects;
- Qdrant for vector retrieval;
- Ollama for BGE-M3 embeddings and the configured local chat model;
- Integration Controller for System Admin-managed Azure MCP instances;
- optional Docling document processing; and
- optional Nginx HTTPS ingress.

This is a **single-host deployment**. It does not provide database replication, automatic host failover, zero-downtime upgrades, or multi-node scaling. Use AKS or managed stateful services when those capabilities are required.

## 2. Reference architecture

```text
Users
  |
  | HTTPS 443
  v
Azure NSG / optional Application Gateway
  |
  v
Nginx TLS gateway on Azure VM
  |
  v
NexoraAI application
  |
  +-- MongoDB
  +-- MinIO
  +-- Qdrant
  +-- Ollama
  +-- Integration Controller --> managed Azure MCP containers

Azure Managed Disk
  +-- Docker images and named volumes

Protected off-host storage
  +-- validated NexoraAI backup archives
  +-- APP_DATA_ENCRYPTION_KEY recovery copy
```

Only SSH from an approved administration source and HTTPS from approved user networks should reach the VM. MongoDB, MinIO API, Qdrant, Ollama, Integration Controller, and MCP containers must remain on the private Docker network.

## 3. Plan the deployment

Record the following approved values before creating resources:

| Item | Example | Requirement |
| --- | --- | --- |
| Azure region | `southeastasia` | Select a region approved for the organization's data |
| Resource group | `rg-nexora-prod` | Keep production resources together |
| VM name | `vm-nexora-prod-01` | Use the organization's naming standard |
| DNS name | `nexora.example.com` | Certificate SAN must contain this exact name |
| Admin source network | `203.0.113.10/32` | Never allow SSH from the entire Internet |
| User source network | Corporate CIDR or approved Internet scope | Apply the least-access rule appropriate to the deployment |
| Backup destination | Protected Azure Storage account | Backups must be copied off the VM |

Recommended starting sizes are guidelines, not capacity guarantees:

| Workload | Starting VM | Data disk | Notes |
| --- | --- | --- | --- |
| Evaluation or light cloud-LLM use | 8 vCPU / 32 GiB RAM | 256 GiB Premium SSD | Local model responses may be slow on CPU |
| Small production with local 8B model | 16 vCPU / 64 GiB RAM | 512 GiB Premium SSD | Load-test with the actual model and documents |
| Higher local-model throughput | Supported GPU VM | 512 GiB or larger | Requires NVIDIA host/runtime configuration and a reviewed Compose GPU override |

Keep at least 25 percent free disk space. Model downloads, image layers, Knowledge files, vectors, MongoDB data, attachments, logs, and temporary backup files all consume storage.

## 4. Create the Azure VM

The following portal workflow is the recommended baseline:

1. In Azure Portal, create or select the production Resource Group.
2. Create an Ubuntu Server 24.04 LTS Generation 2 VM.
3. Select a size based on Section 3. CPU-only local LLM use is intended for evaluation or light workloads.
4. Select SSH public-key authentication. Do not enable password-based SSH.
5. Create a Standard static public IP only when the VM must receive direct Internet traffic. Prefer a private VM behind Application Gateway or another approved ingress where available.
6. Disable public inbound ports in the VM wizard; create explicit NSG rules in Section 5.
7. Use a Premium SSD OS disk of at least 128 GiB.
8. Attach an empty Premium SSD data disk sized for application state.
9. Enable boot diagnostics, Microsoft Defender controls required by policy, automatic guest patching, and a system-assigned managed identity when Azure monitoring or protected backup upload will use it.
10. Create the VM and record its private IP, resource ID, and data-disk LUN in the deployment record.

Do not place application secrets in cloud-init, VM tags, deployment outputs, or ticket comments.

## 5. Configure network access and DNS

Create NSG inbound rules with explicit priorities:

| Port | Source | Purpose |
| --- | --- | --- |
| TCP 22 | Approved administration CIDR only | SSH administration |
| TCP 80 | Approved user networks | Redirect to HTTPS; omit when an upstream ingress performs redirect |
| TCP 443 | Approved user networks | NexoraAI HTTPS |

Do not create inbound rules for ports `27017`, `9000`, `9001`, `6333`, `11434`, `8080`, or `50505`. Port `50505` is bound to loopback for host-local maintenance. The MinIO console also remains loopback-only.

Create an A or CNAME record for the approved hostname and point it to the public ingress. Wait for DNS resolution before issuing or installing the TLS certificate.

From an administrator workstation, confirm that SSH is reachable only from the approved source and that unapproved ports are closed.

## 6. Prepare the managed data disk

Connect with SSH and inspect the disks before formatting anything:

```bash
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
ls -l /dev/disk/azure/scsi1/
```

> The next formatting command destroys data on the selected device. Confirm that the device is the new empty Azure data disk and that its LUN matches the deployment record.

For a new disk at LUN 0:

```bash
sudo mkfs.ext4 /dev/disk/azure/scsi1/lun0
sudo install -d -m 0750 /mnt/nexora
sudo mount /dev/disk/azure/scsi1/lun0 /mnt/nexora
sudo blkid /dev/disk/azure/scsi1/lun0
```

Add the returned UUID to `/etc/fstab` using the organization's change-controlled method:

```text
UUID=<data-disk-uuid> /mnt/nexora ext4 defaults,nofail 0 2
```

Validate the entry before continuing:

```bash
sudo mount -a
findmnt /mnt/nexora
df -h /mnt/nexora
```

## 7. Install Docker Engine and operating-system tools

Install base packages:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git openssl python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Add Docker's official repository and install Docker Engine with the Compose plugin. Follow the current official Docker Ubuntu instructions if the repository format changes:

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Configure Docker to store images and named volumes on the managed data disk:

```bash
sudo systemctl stop docker
sudo install -d -m 0710 /mnt/nexora/docker
sudo install -d -m 0755 /etc/docker
```

Create `/etc/docker/daemon.json` with:

```json
{
  "data-root": "/mnt/nexora/docker",
  "log-driver": "local",
  "log-opts": {
    "max-size": "20m",
    "max-file": "5"
  }
}
```

Start and validate Docker:

```bash
sudo systemctl enable --now docker
sudo docker info --format '{{.DockerRootDir}}'
sudo docker compose version
```

The Docker root directory must report `/mnt/nexora/docker`.

## 8. Install the NexoraAI release

Create a restricted application directory and copy or clone the approved release into it:

```bash
sudo install -d -m 0750 /opt/nexora
sudo chown "$USER":"$USER" /opt/nexora
cd /opt/nexora
git clone <approved-private-repository-url> app
cd /opt/nexora/app
git checkout <approved-release-tag-or-commit>
git status --short
```

For an offline release package, verify its vendor-provided checksum and signature before extracting it to `/opt/nexora/app`. Do not deploy an unreviewed branch or a directory containing local developer changes.

Confirm that these files exist:

```bash
test -f docker-compose.local-runtime.yml
test -f docker-compose.local-tls.yml
test -f docs/local-runtime.env.example
test -f scripts/local_runtime_backup.py
```

## 9. Create and protect deployment secrets

Copy the environment template to the Git-ignored runtime file:

```bash
cp docs/local-runtime.env.example .env.local-runtime
chmod 600 .env.local-runtime
```

Generate independent values. Run each command separately and place its output directly into the protected secret store and `.env.local-runtime`:

```bash
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The final command requires the `cryptography` Python package. If it is not installed on the host, generate the Fernet key on an approved administration workstation or with the built application image. Never substitute an ordinary random string for a Fernet key.

Assign distinct values to:

- `NEXORA_MONGO_ROOT_PASSWORD`;
- `NEXORA_MONGO_APP_PASSWORD`;
- `MINIO_ACCESS_KEY`;
- `MINIO_SECRET_KEY`;
- `INTEGRATION_CONTROLLER_TOKEN`;
- one-time `LOCAL_AUTH_BOOTSTRAP_TOKEN`; and
- `APP_DATA_ENCRYPTION_KEY`.

Keep `APP_DATA_ENCRYPTION_KEY` stable for the entire installation lifetime. Losing or changing it makes encrypted LLM, integration, Entra, and MCP credentials unreadable. Store a recovery copy outside the VM in the organization's secret manager.

Set `AZURE_MCP_IMAGE` to an approved digest of Microsoft's official Azure MCP image. Do not use a floating production tag. The image is pulled only when a System Administrator enables a managed Azure MCP connection.

Render the Compose configuration and inspect it without printing the environment file:

```bash
sudo docker compose --env-file .env.local-runtime -f docker-compose.local-runtime.yml config --quiet
```

Do not commit `.env.local-runtime`, certificate private keys, license private keys, OAuth credentials, service-account JSON, raw prompts, or tool outputs.

## 10. Install the TLS certificate

Obtain a certificate for the exact production hostname from the organization PKI or a public certificate authority. Place it outside the repository:

```text
/opt/nexora/tls/
├── fullchain.pem
└── privkey.pem
```

Create and protect the directory:

```bash
sudo install -d -m 0750 /opt/nexora/tls
sudo chmod 640 /opt/nexora/tls/fullchain.pem /opt/nexora/tls/privkey.pem
```

Set these values in `.env.local-runtime`:

```text
NEXORA_BIND_ADDRESS=127.0.0.1
NEXORA_TLS_CERT_DIR=/opt/nexora/tls
NEXORA_HTTP_BIND_ADDRESS=0.0.0.0
NEXORA_HTTP_PORT=80
NEXORA_HTTPS_BIND_ADDRESS=0.0.0.0
NEXORA_HTTPS_PORT=443
```

If Application Gateway or another enterprise ingress terminates TLS, keep the VM origin private and apply equivalent TLS, forwarding-header, upload-size, streaming, and security-header controls. Do not expose plain HTTP directly to end users.

## 11. Start NexoraAI

Start the base runtime and TLS overlay together:

```bash
cd /opt/nexora/app
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --build --wait
```

The first start builds the application image and downloads the configured embedding and chat models. It may take several minutes and multiple gigabytes of network and disk space.

Monitor startup without exposing secrets:

```bash
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  ps

sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  logs --tail=200 app ollama-models tls-gateway
```

All core services must become healthy. The one-shot `ollama-models` service should exit successfully after its downloads complete.

## 12. Complete first-time application setup

1. Open `https://<approved-hostname>` in a private browser window.
2. Verify the certificate chain and hostname before entering credentials.
3. Create the first local System Administrator using the one-time bootstrap token.
4. Sign in and confirm the account is a System Administrator.
5. Remove `LOCAL_AUTH_BOOTSTRAP_TOKEN` from `.env.local-runtime`.
6. Recreate only the application container:

```bash
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --force-recreate app
```

7. Sign out and sign in again. Confirm that bootstrap is no longer offered.
8. Open **System administration → License**. Start the one-time 14-day Trial or import an offline license issued for the displayed Installation ID.
9. Configure Teams, Data Groups, roles, LLM providers, and integrations according to the Administrator Manual.

Never retain the bootstrap token in screenshots, command history, tickets, or operating procedures after setup.

## 13. Optional Microsoft Entra authentication

Local authentication works immediately. For hybrid Local and Microsoft Entra authentication:

1. Register the exact HTTPS frontend origin and redirect URI in Microsoft Entra ID.
2. Grant only the API permissions required by the approved NexoraAI authentication design.
3. In **System administration → Sign-in & authentication**, enter the Tenant ID, application IDs, and client secret.
4. Save and reload the browser.
5. Test both Local and Entra sign-in using separate approved test accounts.
6. Remove obsolete production HTTP redirect URIs after validation.

Application-managed secrets are encrypted using `APP_DATA_ENCRYPTION_KEY`. Keep the key stable across VM restarts, redeployments, backup restoration, and any future replicas.

## 14. Optional OCR and managed Azure MCP

Start Docling only when a configured processing profile requires it:

```bash
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  --profile ocr up -d docling
```

Configure the Docling endpoint in NexoraAI as `http://docling:5001`. Do not expose its port publicly.

The Integration Controller starts on day one but creates no Azure MCP container until a System Administrator enables a managed Azure connection. It has no host port and is the only service with Docker socket access. Protect `INTEGRATION_CONTROLLER_TOKEN`, pin `AZURE_MCP_IMAGE` by digest, and do not add arbitrary controller commands, mounts, images, or host ports.

## 15. Validate the deployment

Run host-level checks:

```bash
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  ps

curl --fail --location https://<approved-hostname>/config
openssl s_client -connect <approved-hostname>:443 -servername <approved-hostname>
```

Complete this acceptance checklist:

1. The certificate chain and hostname validate without bypass options.
2. HTTP redirects to the approved HTTPS hostname.
3. **System administration → System health** shows core services and **HTTPS gateway · Nginx** as healthy.
4. Sign-in, Chat streaming, file upload, citation download, and Draw.io artifact download work.
5. Create a Team and Data Group; upload distinct Personal, Team, and Global documents and wait for **Indexed**.
6. Retrieve and open citations from allowed scopes.
7. Confirm a user outside the Team or Data Group cannot retrieve or open Team content.
8. Test one configured LLM provider and one read-only integration.
9. If Managed Azure MCP is used, enable one connection and confirm exactly one connection-specific container is created without a public port.
10. Restart the stack without deleting volumes and repeat representative sign-in, retrieval, and System Health checks.

## 16. Configure backup and restore operations

Create a validated logical backup before production acceptance and every upgrade:

```bash
cd /opt/nexora/app
sudo python3 scripts/local_runtime_backup.py backup \
  --env-file .env.local-runtime \
  --output /mnt/nexora/backups/nexora-backup-<UTC-timestamp>.tar.gz
```

Validate the archive:

```bash
sudo python3 scripts/local_runtime_backup.py validate \
  --archive /mnt/nexora/backups/nexora-backup-<UTC-timestamp>.tar.gz
```

Copy the validated archive to protected off-host storage and apply the organization's encryption, access-control, retention, immutability, and deletion policies. The archive deliberately excludes `.env.local-runtime` and `APP_DATA_ENCRYPTION_KEY`; protect their recovery copies separately.

VM snapshots alone are not a consistent application backup. The validated workflow briefly stops the application writer and captures MongoDB, MinIO, and Qdrant as a coordinated set.

Perform a restore drill on a disposable deployment. Restore is destructive to the target MongoDB collections, configured MinIO bucket, and backed-up Qdrant collections:

```bash
sudo python3 scripts/local_runtime_backup.py restore \
  --env-file .env.local-runtime \
  --archive /secure/nexora-backup-<UTC-timestamp>.tar.gz \
  --confirm-restore
```

Never run a restore against production without confirming the target, maintenance window, archive checksum, compatible component versions, and matching encryption-key fingerprint.

## 17. Routine operations

Check service status and recent logs:

```bash
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml ps

sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml logs --since=30m app tls-gateway
```

Monitor CPU, memory, disk consumption, container restarts, backup success, certificate expiry, and external provider availability. The NexoraAI System Health page is an on-demand snapshot and does not replace Azure Monitor alerts.

Renew certificates through the approved PKI or ACME process, replace both files atomically, and recreate only the gateway:

```bash
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --force-recreate tls-gateway
```

Never use `docker compose down --volumes` on a deployment whose data must be retained.

## 18. Upgrade and rollback

Before an upgrade:

1. Read the release notes and compatibility requirements.
2. Confirm sufficient free disk space.
3. Create, validate, and copy an off-host backup.
4. Record the currently deployed Git commit and container image IDs.
5. Schedule a maintenance window because the single-host stack has no zero-downtime upgrade.

Deploy the approved release:

```bash
cd /opt/nexora/app
git fetch --tags
git checkout <approved-new-release-tag-or-commit>
sudo docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  -f docker-compose.local-tls.yml \
  up -d --build --wait
```

Repeat Section 15. If code rollback is supported by the release notes, check out the recorded commit and rebuild. Restore application data only when required by a documented incompatible migration or data incident; an unnecessary restore can discard valid post-backup changes.

## 19. Troubleshooting

| Symptom | Check | Corrective action |
| --- | --- | --- |
| Application remains unhealthy | `docker compose ps` and `logs app` | Verify MongoDB, MinIO, Qdrant, Ollama model download, secrets, and disk space |
| Browser shows JSON parse or session error | Session age and backend response | Sign out and sign in again; verify the current app image is deployed |
| Port 80 or 443 cannot bind | Existing listener and NSG | Stop the conflicting service or use the approved enterprise ingress design |
| Certificate error | SAN, chain, expiry, and mounted paths | Install the correct full chain and private key, then recreate `tls-gateway` |
| Nginx missing from System Health | Compose command omitted TLS overlay | Recreate the app and gateway using both Compose files |
| Model download is slow or fails | Disk, DNS, outbound firewall, registry access | Permit approved registry/model endpoints and retry `ollama-models` |
| Managed Azure MCP provisioning unavailable | Controller health, token, image digest, Docker socket | Correct configuration and recreate the controller; do not expose its port |
| Data disappeared after maintenance | Compose project name or volume deletion | Stop changes, inspect named volumes, and follow the approved restore procedure |
| Stored credentials cannot be decrypted | `APP_DATA_ENCRYPTION_KEY` changed | Restore the exact original key from the protected recovery store |

## 20. Production handover checklist

- Azure resource ownership, tags, budget alerts, and support contacts are recorded.
- SSH is restricted to approved administrators and password authentication is disabled.
- Only approved HTTP/HTTPS ingress is public.
- TLS chain, renewal ownership, and expiry alerts are verified.
- `.env.local-runtime`, certificate private key, and encryption-key recovery copy are protected.
- MongoDB, MinIO, Qdrant, Ollama, controller, and MCP ports are not public.
- Trial or production license status is confirmed.
- System Health, user workflows, ACL isolation, and integrations pass acceptance tests.
- Backup automation, off-host copy, retention, alerting, and restore drill are documented.
- Azure Monitor and disk-capacity alerts are enabled.
- Upgrade and rollback owners have the approved release and backup locations.
- The single-host recovery-time and recovery-point objectives are accepted by the service owner.

## 21. Related NexoraAI documentation

- [Portable local runtime](local-runtime.md)
- [Production TLS](production-tls.md)
- [Local backup and restore](local-backup-restore.md)
- [Licensing](licensing.md)
- [Azure and Draw.io MCP](azure-drawio-mcp.md)
- [Administrator Manual](admin-manual.md)
- [System Health](system-health.md)
