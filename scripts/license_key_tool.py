#!/usr/bin/env python3
"""Vendor-side helper for generating Ed25519 keys and issuing NX1 licenses.

This script is not copied into the NexoraAI application image. Keep generated
private keys in an access-controlled vendor secret store, never in this repo or
in a customer deployment.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BACKEND = Path(__file__).resolve().parents[1] / "app" / "backend"
sys.path.insert(0, str(BACKEND))

from core.licensing import LICENSE_KEY_PREFIX, parse_verified_claims  # noqa: E402


def _write_new(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def generate_keypair(private_path: Path, public_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    _write_new(
        private_path,
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        0o600,
    )
    try:
        _write_new(
            public_path,
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            0o644,
        )
    except Exception:
        private_path.unlink(missing_ok=True)
        raise


def issue_license(private_path: Path, claims_path: Path, output_path: Path) -> None:
    claims_payload = json.loads(claims_path.read_text(encoding="utf-8"))
    claims = parse_verified_claims(claims_payload)
    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("license signing key must use Ed25519")

    canonical_payload = {
        "schema_version": claims.schema_version,
        "license_id": claims.license_id,
        "customer_id": claims.customer_id,
        "product": claims.product,
        "edition": claims.edition,
        "issuer": claims.issuer,
        "key_id": claims.key_id,
        "not_before": claims.not_before.isoformat().replace("+00:00", "Z"),
        "expires_at": claims.expires_at.isoformat().replace("+00:00", "Z"),
        "grace_days": claims.grace_days,
        "features": dict(claims.features),
        "capacities": dict(claims.capacities),
        "installation_id": claims.installation_id,
    }
    payload_bytes = json.dumps(
        canonical_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = _base64url(payload_bytes)
    signature = _base64url(private_key.sign(encoded_payload.encode("ascii")))
    _write_new(output_path, f"{LICENSE_KEY_PREFIX}.{encoded_payload}.{signature}\n".encode(), 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NexoraAI signing keys and offline license files")
    subparsers = parser.add_subparsers(dest="command", required=True)

    keypair = subparsers.add_parser("generate-keypair", help="Create a new Ed25519 key pair")
    keypair.add_argument("--private-key", type=Path, required=True)
    keypair.add_argument("--public-key", type=Path, required=True)

    issue = subparsers.add_parser("issue", help="Sign a validated JSON claims file")
    issue.add_argument("--private-key", type=Path, required=True)
    issue.add_argument("--claims", type=Path, required=True)
    issue.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "generate-keypair":
            generate_keypair(args.private_key, args.public_key)
        else:
            issue_license(args.private_key, args.claims, args.output)
    except Exception as error:
        print(f"license tool failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
