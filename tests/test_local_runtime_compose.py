from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_local_runtime_compose_keeps_data_services_private_and_persistent():
    compose = yaml.safe_load((ROOT / "docker-compose.local-runtime.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["app"]["ports"] == [
        "${NEXORA_BIND_ADDRESS:-127.0.0.1}:${NEXORA_APP_PORT:-50505}:8000"
    ]
    assert "ports" not in services["mongodb"]
    assert "ports" not in services["qdrant"]
    assert "ports" not in services["ollama"]
    assert services["minio"]["ports"] == [
        "${NEXORA_BIND_ADDRESS:-127.0.0.1}:${NEXORA_MINIO_CONSOLE_PORT:-9001}:9001"
    ]
    assert "nexora_mongodb_data:/data/db" in services["mongodb"]["volumes"]
    assert "nexora_minio_data:/data" in services["minio"]["volumes"]
    assert "nexora_qdrant_data:/qdrant/storage" in services["qdrant"]["volumes"]
    assert "nexora_ollama_data:/root/.ollama" in services["ollama"]["volumes"]


def test_local_runtime_app_uses_local_provider_endpoints_and_health_dependencies():
    compose = yaml.safe_load((ROOT / "docker-compose.local-runtime.yml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]
    environment = app["environment"]

    assert environment["KNOWLEDGE_STORAGE_PROVIDER"] == "minio"
    assert environment["MINIO_ENDPOINT"] == "minio:9000"
    assert environment["KNOWLEDGE_SEARCH_PROVIDER"] == "qdrant"
    assert environment["QDRANT_URL"] == "http://qdrant:6333"
    assert environment["EMBEDDING_BASE_URL"] == "http://ollama:11434/v1"
    assert environment["LLM_BASE_URL"] == "http://ollama:11434/v1"
    assert environment["AZURE_ENFORCE_ACCESS_CONTROL"] == "true"
    assert environment["AZURE_ENABLE_UNAUTHENTICATED_ACCESS"] == "false"
    assert environment["USE_CHAT_HISTORY_COSMOS"] == "false"
    assert environment["USE_CHAT_HISTORY_BROWSER"] == "true"
    assert environment["CHAT_ATTACHMENT_STORE"] == "local"
    assert all(
        dependency["condition"] in {"service_healthy", "service_completed_successfully"}
        for dependency in app["depends_on"].values()
    )


def test_local_runtime_template_contains_placeholders_not_real_credentials():
    template = (ROOT / "docs/local-runtime.env.example").read_text(encoding="utf-8")

    assert "APP_DATA_ENCRYPTION_KEY=replace_with_a_fernet_key" in template
    assert "LOCAL_AUTH_BOOTSTRAP_TOKEN=replace_with_a_long_random_one_time_token" in template
    assert "NEXORA_MONGO_ROOT_PASSWORD=replace_with_" in template
    assert "MINIO_SECRET_KEY=replace_with_" in template
    assert "QDRANT_COLLECTION=nexora-knowledge-bge-m3" in template


def test_local_runtime_image_builds_frontend_and_runs_as_non_root():
    dockerfile = (ROOT / "Dockerfile.local").read_text(encoding="utf-8")

    assert "npm run build:memory-safe" in dockerfile
    assert "COPY --from=frontend-build" in dockerfile
    assert "USER nexora" in dockerfile
    assert '"hypercorn"' in dockerfile
