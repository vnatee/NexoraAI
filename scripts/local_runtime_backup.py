#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

ARCHIVE_VERSION = 1
COMPONENTS = ("mongodb.archive.gz", "minio.tar.gz", "qdrant.tar.gz")
FORBIDDEN_MANIFEST_KEYS = {"password", "secret", "token", "credential", "api_key", "encryption_key"}
ROOT = Path(__file__).resolve().parents[1]


class BackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _key_fingerprint(env: dict[str, str]) -> str:
    key = env.get("APP_DATA_ENCRYPTION_KEY", "")
    if not key or key.startswith("replace_with_"):
        raise BackupError("APP_DATA_ENCRYPTION_KEY must be set to the deployment's stable Fernet key")
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _compose_base(args: argparse.Namespace) -> list[str]:
    command = ["docker", "compose", "--env-file", str(args.env_file), "-f", str(args.compose_file)]
    if args.project_name:
        command.extend(["-p", args.project_name])
    return command


def _run(command: list[str], *, input_file: BinaryIO | None = None, output_file: BinaryIO | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            stdin=input_file,
            stdout=output_file or subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError as error:
        raise BackupError(f"Required command is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise BackupError(f"Command failed: {' '.join(command[:3])}: {detail or 'no error detail'}") from error


def _service_running(compose: list[str], service: str) -> bool:
    result = _run([*compose, "ps", "-q", "--status", "running", service])
    return bool(result.stdout.strip())


def _require_services(compose: list[str]) -> None:
    missing = [service for service in ("mongodb", "minio", "qdrant") if not _service_running(compose, service)]
    if missing:
        raise BackupError(f"Required services are not running: {', '.join(missing)}")


def _set_app_running(compose: list[str], running: bool) -> None:
    action = "start" if running else "stop"
    _run([*compose, action, "app"])


def _app_helper(compose: list[str], operation: str, component: str, path: Path) -> None:
    command = [*compose, "run", "--rm", "--no-deps", "-T", "app", "python", "-m", "core.local_backup_io", operation, component]
    if operation == "export":
        with path.open("wb") as output:
            _run(command, output_file=output)
    else:
        with path.open("rb") as source:
            _run(command, input_file=source)


def _export_mongodb(compose: list[str], path: Path) -> None:
    command = [
        *compose,
        "exec",
        "-T",
        "mongodb",
        "sh",
        "-ec",
        'mongodump --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" '
        '--authenticationDatabase admin --db "$NEXORA_MONGO_DB_NAME" --archive --gzip',
    ]
    with path.open("wb") as output:
        _run(command, output_file=output)


def _import_mongodb(compose: list[str], path: Path) -> None:
    command = [
        *compose,
        "exec",
        "-T",
        "mongodb",
        "sh",
        "-ec",
        'mongorestore --quiet --drop --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" '
        '--authenticationDatabase admin --archive --gzip',
    ]
    with path.open("rb") as source:
        _run(command, input_file=source)


def _manifest(env: dict[str, str], component_dir: Path, project_name: str) -> dict[str, Any]:
    return {
        "archive_version": ARCHIVE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deployment": {
            "project_name": project_name or ROOT.name.lower(),
            "mongo_database": env.get("NEXORA_MONGO_DB_NAME", "nexora"),
            "minio_bucket": env.get("MINIO_KNOWLEDGE_BUCKET", "nexora-knowledge"),
            "qdrant_collection": env.get("QDRANT_COLLECTION", "nexora-knowledge-bge-m3"),
            "embedding_model": env.get("EMBEDDING_MODEL", "bge-m3"),
            "embedding_dimensions": int(env.get("EMBEDDING_DIMENSIONS", "1024")),
            "app_image": env.get("NEXORA_APP_IMAGE", "nexoraai:local"),
            "mongo_image": env.get("NEXORA_MONGO_IMAGE", "mongo:8.0"),
            "minio_image": env.get("NEXORA_MINIO_IMAGE", "minio/minio:RELEASE.2025-07-23T15-54-02Z"),
            "qdrant_image": env.get("NEXORA_QDRANT_IMAGE", "qdrant/qdrant:v1.15.5"),
        },
        "encryption_key_fingerprint": _key_fingerprint(env),
        "components": {
            name: {"size": (component_dir / name).stat().st_size, "sha256": _sha256(component_dir / name)}
            for name in COMPONENTS
        },
        "excluded": ["credentials", "APP_DATA_ENCRYPTION_KEY", "Ollama model cache", "temporary chat attachments"],
    }


def _manifest_has_forbidden_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            contains_secret_name = any(fragment in normalized for fragment in FORBIDDEN_MANIFEST_KEYS)
            if (contains_secret_name and not normalized.endswith("_fingerprint")) or _manifest_has_forbidden_keys(child):
                return True
    elif isinstance(value, list):
        return any(_manifest_has_forbidden_keys(item) for item in value)
    return False


def _validate_component_archive(path: Path, expected_index: str = "index.json") -> None:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            if not members or members[0].name != expected_index:
                raise BackupError(f"{path.name} is missing {expected_index}")
            if len({member.name for member in members}) != len(members):
                raise BackupError(f"{path.name} contains duplicate members")
            for member in members:
                if not member.isfile() or member.name.startswith("/") or ".." in member.name.split("/"):
                    raise BackupError(f"Unsafe member in {path.name}: {member.name}")
            index_file = archive.extractfile(members[0])
            if index_file is None or json.load(index_file).get("format_version") != ARCHIVE_VERSION:
                raise BackupError(f"Unsupported component format in {path.name}")
    except (json.JSONDecodeError, tarfile.TarError) as error:
        raise BackupError(f"Invalid component archive: {path.name}") from error


def unpack_and_validate(archive_path: Path, destination: Path) -> dict[str, Any]:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            allowed = {"manifest.json", *COMPONENTS}
            names = {member.name for member in members}
            if names != allowed or len(members) != len(allowed):
                raise BackupError(f"Unexpected archive members: {sorted(names ^ allowed)}")
            for member in members:
                if not member.isfile() or member.name.startswith("/") or ".." in member.name.split("/"):
                    raise BackupError(f"Unsafe archive member: {member.name}")
                source = archive.extractfile(member)
                if source is None:
                    raise BackupError(f"Unable to read archive member: {member.name}")
                with (destination / member.name).open("wb") as output:
                    shutil.copyfileobj(source, output)
    except tarfile.TarError as error:
        raise BackupError("Backup is not a valid gzip tar archive") from error

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("archive_version") != ARCHIVE_VERSION:
        raise BackupError("Unsupported backup archive version")
    if _manifest_has_forbidden_keys(manifest):
        raise BackupError("Backup manifest contains a forbidden secret field")
    for name in COMPONENTS:
        metadata = manifest.get("components", {}).get(name, {})
        path = destination / name
        if path.stat().st_size <= 0 or metadata.get("size") != path.stat().st_size or metadata.get("sha256") != _sha256(path):
            raise BackupError(f"Checksum or size validation failed for {name}")
    _validate_component_archive(destination / "minio.tar.gz")
    _validate_component_archive(destination / "qdrant.tar.gz")
    return manifest


def create_backup(args: argparse.Namespace) -> None:
    compose = _compose_base(args)
    env = _read_env(args.env_file)
    _require_services(compose)
    app_was_running = _service_running(compose, "app")
    output_path = args.output or ROOT / "backups" / f"nexora-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nexora-backup-") as temp_name:
        temp = Path(temp_name)
        try:
            if app_was_running:
                _set_app_running(compose, False)
            _export_mongodb(compose, temp / "mongodb.archive.gz")
            _app_helper(compose, "export", "minio", temp / "minio.tar.gz")
            _app_helper(compose, "export", "qdrant", temp / "qdrant.tar.gz")
            manifest = _manifest(env, temp, args.project_name)
            (temp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            temporary_output = output_path.with_suffix(output_path.suffix + ".partial")
            try:
                with tarfile.open(temporary_output, "w:gz") as archive:
                    for name in ("manifest.json", *COMPONENTS):
                        archive.add(temp / name, arcname=name, recursive=False)
                os.replace(temporary_output, output_path)
            finally:
                temporary_output.unlink(missing_ok=True)
        finally:
            if app_was_running:
                _set_app_running(compose, True)

    with tempfile.TemporaryDirectory(prefix="nexora-validate-") as validate_name:
        unpack_and_validate(output_path, Path(validate_name))
    print(f"Backup created and validated: {output_path}")


def validate_backup(args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="nexora-validate-") as temp_name:
        manifest = unpack_and_validate(args.archive.resolve(), Path(temp_name))
    print(json.dumps({"status": "valid", "archive_version": manifest["archive_version"], "created_at": manifest["created_at"]}, indent=2))


def restore_backup(args: argparse.Namespace) -> None:
    if not args.confirm_restore:
        raise BackupError("Restore is destructive; rerun with --confirm-restore")
    compose = _compose_base(args)
    env = _read_env(args.env_file)
    _require_services(compose)
    app_was_running = _service_running(compose, "app")
    app_was_stopped = False
    restore_succeeded = False
    with tempfile.TemporaryDirectory(prefix="nexora-restore-") as temp_name:
        temp = Path(temp_name)
        manifest = unpack_and_validate(args.archive.resolve(), temp)
        if manifest.get("encryption_key_fingerprint") != _key_fingerprint(env):
            raise BackupError("APP_DATA_ENCRYPTION_KEY does not match this backup")
        expected = manifest.get("deployment") or {}
        actual = {
            "mongo_database": env.get("NEXORA_MONGO_DB_NAME", "nexora"),
            "minio_bucket": env.get("MINIO_KNOWLEDGE_BUCKET", "nexora-knowledge"),
            "qdrant_collection": env.get("QDRANT_COLLECTION", "nexora-knowledge-bge-m3"),
            "embedding_model": env.get("EMBEDDING_MODEL", "bge-m3"),
            "embedding_dimensions": int(env.get("EMBEDDING_DIMENSIONS", "1024")),
        }
        mismatches = [key for key, value in actual.items() if expected.get(key) != value]
        if mismatches:
            raise BackupError(f"Restore target does not match backup configuration: {', '.join(mismatches)}")
        try:
            if app_was_running:
                _set_app_running(compose, False)
                app_was_stopped = True
            _app_helper(compose, "import", "minio", temp / "minio.tar.gz")
            _app_helper(compose, "import", "qdrant", temp / "qdrant.tar.gz")
            _import_mongodb(compose, temp / "mongodb.archive.gz")
            restore_succeeded = True
        finally:
            if app_was_running and restore_succeeded:
                _set_app_running(compose, True)
            elif app_was_stopped:
                print("Restore did not complete; the app service remains stopped to protect the deployment.", file=sys.stderr)
    print("Restore completed. Verify authentication, ACLs, document counts, and citations before returning the deployment to service.")


def _path(value: str) -> Path:
    return Path(value).expanduser()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Backup, validate, or restore the NexoraAI local Compose data plane")
    subparsers = result.add_subparsers(dest="command", required=True)

    def runtime_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("--env-file", type=_path, default=ROOT / ".env.local-runtime")
        command.add_argument("--compose-file", type=_path, default=ROOT / "docker-compose.local-runtime.yml")
        command.add_argument("--project-name", default="")

    backup = subparsers.add_parser("backup")
    runtime_options(backup)
    backup.add_argument("--output", type=_path)
    backup.set_defaults(handler=create_backup)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--archive", type=_path, required=True)
    validate.set_defaults(handler=validate_backup)

    restore = subparsers.add_parser("restore")
    runtime_options(restore)
    restore.add_argument("--archive", type=_path, required=True)
    restore.add_argument("--confirm-restore", action="store_true")
    restore.set_defaults(handler=restore_backup)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if hasattr(args, "env_file") and not args.env_file.is_file():
            raise BackupError(f"Environment file not found: {args.env_file}")
        if hasattr(args, "compose_file") and not args.compose_file.is_file():
            raise BackupError(f"Compose file not found: {args.compose_file}")
        if hasattr(args, "archive") and not args.archive.is_file():
            raise BackupError(f"Backup archive not found: {args.archive}")
        args.handler(args)
        return 0
    except BackupError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
