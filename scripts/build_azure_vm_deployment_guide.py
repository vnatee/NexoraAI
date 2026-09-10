#!/usr/bin/env python3
"""Build the NexoraAI Azure VM and Docker Compose deployment guide."""

from pathlib import Path

from build_manual_docx import build

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> int:
    output = DOCS / "NexoraAI-Azure-VM-Docker-Compose-Deployment-Guide.docx"
    build(
        DOCS / "azure-vm-docker-compose-deployment-guide.md",
        output,
        "Azure administrators, Linux platform engineers, security teams, and NexoraAI deployment operators",
        {
            "4. Create the Azure VM": (
                "Azure VM overview",
                "Capture the VM Overview page with subscription IDs, public IPs, tenant names, and operator identities removed or blurred.",
            ),
            "5. Configure network access and DNS": (
                "Network Security Group and DNS",
                "Capture the approved inbound rules and DNS record. Hide public IP addresses if the document will leave the operations team.",
            ),
            "12. Complete first-time application setup": (
                "NexoraAI first-time setup",
                "Capture the bootstrap or sign-in screen without passwords, bootstrap tokens, license keys, or customer identities.",
            ),
            "15. Validate the deployment": (
                "System Health acceptance check",
                "Capture System Health with the Nginx HTTPS gateway healthy. Blur installation IDs, hostnames, and organization-specific values as required.",
            ),
        },
        document_type="Deployment Guide",
        last_verified="9 September 2026",
        subject="Step-by-step deployment of NexoraAI on an Azure VM with Docker Compose",
        keywords="NexoraAI, Azure VM, Docker Compose, deployment, TLS, backup, operations",
    )
    print(f"Created {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
