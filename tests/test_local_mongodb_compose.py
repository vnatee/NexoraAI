from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_local_mongodb_compose_is_private_persistent_and_health_checked():
    compose = yaml.safe_load((ROOT / "docker-compose.local-mongodb.yml").read_text(encoding="utf-8"))
    service = compose["services"]["mongodb"]

    assert service["ports"] == ["127.0.0.1:${NEXORA_MONGO_PORT:-27017}:27017"]
    assert "nexora_mongodb_data:/data/db" in service["volumes"]
    assert any("mongodb-init.js" in volume and volume.endswith(":ro") for volume in service["volumes"])
    assert service["healthcheck"]["test"][0] == "CMD-SHELL"
    assert "ping" in service["healthcheck"]["test"][1]
    assert "nexora_mongodb_data" in compose["volumes"]


def test_local_mongodb_initializes_a_database_scoped_application_user():
    script = (ROOT / "scripts/mongodb-init.js").read_text(encoding="utf-8")

    assert "NEXORA_MONGO_APP_USERNAME" in script
    assert "NEXORA_MONGO_APP_PASSWORD" in script
    assert 'role: "readWrite"' in script
    assert 'role: "root"' not in script
    assert "createUser" in script
