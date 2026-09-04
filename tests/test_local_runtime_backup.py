import io
import json
import tarfile
from argparse import Namespace
from pathlib import Path

import pytest

from scripts import local_runtime_backup as backup


def _component_archive(path: Path) -> None:
    payload = json.dumps({"format_version": 1}).encode("utf-8")
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("index.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))


def _outer_archive(source: Path, destination: Path) -> None:
    with tarfile.open(destination, "w:gz") as archive:
        for name in ("manifest.json", *backup.COMPONENTS):
            archive.add(source / name, arcname=name, recursive=False)


def _backup_files(path: Path) -> dict:
    (path / "mongodb.archive.gz").write_bytes(b"mongo-archive")
    _component_archive(path / "minio.tar.gz")
    _component_archive(path / "qdrant.tar.gz")
    manifest = backup._manifest(
        {
            "APP_DATA_ENCRYPTION_KEY": "stable-fernet-key",
            "NEXORA_MONGO_DB_NAME": "nexora",
            "MINIO_KNOWLEDGE_BUCKET": "nexora-knowledge",
        },
        path,
        "test-project",
    )
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_backup_archive_validation_checks_manifest_components_and_fingerprint(tmp_path):
    source = tmp_path / "source"
    extracted = tmp_path / "extracted"
    source.mkdir()
    extracted.mkdir()
    expected = _backup_files(source)
    archive = tmp_path / "backup.tar.gz"
    _outer_archive(source, archive)

    manifest = backup.unpack_and_validate(archive, extracted)

    assert manifest["components"] == expected["components"]
    assert manifest["encryption_key_fingerprint"] == backup._key_fingerprint(
        {"APP_DATA_ENCRYPTION_KEY": "stable-fernet-key"}
    )
    assert "stable-fernet-key" not in (extracted / "manifest.json").read_text(encoding="utf-8")


def test_backup_archive_validation_rejects_tampered_component(tmp_path):
    source = tmp_path / "source"
    extracted = tmp_path / "extracted"
    source.mkdir()
    extracted.mkdir()
    _backup_files(source)
    (source / "mongodb.archive.gz").write_bytes(b"tampered")
    archive = tmp_path / "backup.tar.gz"
    _outer_archive(source, archive)

    with pytest.raises(backup.BackupError, match="Checksum or size validation failed"):
        backup.unpack_and_validate(archive, extracted)


def test_backup_archive_validation_rejects_unexpected_members(tmp_path):
    source = tmp_path / "source"
    extracted = tmp_path / "extracted"
    source.mkdir()
    extracted.mkdir()
    _backup_files(source)
    (source / "credentials.env").write_text("PASSWORD=not-allowed", encoding="utf-8")
    archive = tmp_path / "backup.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for name in ("manifest.json", *backup.COMPONENTS, "credentials.env"):
            output.add(source / name, arcname=name, recursive=False)

    with pytest.raises(backup.BackupError, match="Unexpected archive members"):
        backup.unpack_and_validate(archive, extracted)


def test_failed_partial_restore_leaves_previously_running_app_stopped(tmp_path, monkeypatch):
    env = {
        "APP_DATA_ENCRYPTION_KEY": "stable-fernet-key",
        "NEXORA_MONGO_DB_NAME": "nexora",
        "MINIO_KNOWLEDGE_BUCKET": "nexora-knowledge",
        "QDRANT_COLLECTION": "nexora-knowledge-bge-m3",
        "EMBEDDING_MODEL": "bge-m3",
        "EMBEDDING_DIMENSIONS": "1024",
    }
    manifest = {
        "encryption_key_fingerprint": backup._key_fingerprint(env),
        "deployment": {
            "mongo_database": "nexora",
            "minio_bucket": "nexora-knowledge",
            "qdrant_collection": "nexora-knowledge-bge-m3",
            "embedding_model": "bge-m3",
            "embedding_dimensions": 1024,
        },
    }
    state_changes = []
    monkeypatch.setattr(backup, "_compose_base", lambda _args: ["docker", "compose"])
    monkeypatch.setattr(backup, "_read_env", lambda _path: env)
    monkeypatch.setattr(backup, "_require_services", lambda _compose: None)
    monkeypatch.setattr(backup, "_service_running", lambda _compose, service: service == "app")
    monkeypatch.setattr(backup, "unpack_and_validate", lambda _archive, _temp: manifest)
    monkeypatch.setattr(backup, "_set_app_running", lambda _compose, running: state_changes.append(running))
    monkeypatch.setattr(backup, "_app_helper", lambda *_args: (_ for _ in ()).throw(backup.BackupError("restore failed")))

    args = Namespace(
        confirm_restore=True,
        env_file=tmp_path / "runtime.env",
        compose_file=tmp_path / "compose.yml",
        project_name="",
        archive=tmp_path / "backup.tar.gz",
    )

    with pytest.raises(backup.BackupError, match="restore failed"):
        backup.restore_backup(args)

    assert state_changes == [False]
