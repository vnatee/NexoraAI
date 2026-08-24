from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_local_minio_compose_is_private_persistent_and_health_checked():
    compose = yaml.safe_load((ROOT / "docker-compose.local-storage.yml").read_text(encoding="utf-8"))
    service = compose["services"]["minio"]

    assert service["ports"] == [
        "127.0.0.1:${NEXORA_MINIO_API_PORT:-9000}:9000",
        "127.0.0.1:${NEXORA_MINIO_CONSOLE_PORT:-9001}:9001",
    ]
    assert "nexora_minio_data:/data" in service["volumes"]
    assert service["restart"] == "unless-stopped"
    assert service["healthcheck"]["test"] == ["CMD", "mc", "ready", "local"]
    assert "nexora_minio_data" in compose["volumes"]


def test_local_storage_template_contains_placeholders_not_credentials():
    template = (ROOT / "docs/local-storage.env.example").read_text(encoding="utf-8")

    assert "KNOWLEDGE_STORAGE_PROVIDER=minio" in template
    assert "MINIO_ACCESS_KEY=replace_with_" in template
    assert "MINIO_SECRET_KEY=replace_with_" in template
