#!/usr/bin/env python3
"""Small, secret-safe Compose launcher for supported NexoraAI modes."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".env.nexora-runtime"
ALLOWED_CONFIG_KEYS = {
    "MODE",
    "FEATURES",
    "ENV_FILE",
    "DATADOG_COMPOSE_FILE",
    "DOCKER_COMMAND",
    "GPUSTACK_BRANDING",
}
MODES = {"local-simple", "private-enterprise", "external-gateway"}
FEATURES = {"tls", "ocr", "datadog"}
SWITCH_VALUES = {"enabled": True, "disabled": False}


def parse_config(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_CONFIG_KEYS:
            raise ValueError(f"{path}:{number}: unsupported setting {key}")
        result[key] = value.strip()
    return result


def split_features(value: str) -> set[str]:
    requested = {item.strip() for item in value.split(",") if item.strip()}
    unknown = requested - FEATURES
    if unknown:
        raise ValueError(f"unsupported feature(s): {', '.join(sorted(unknown))}")
    return requested


def parse_switch(value: str, *, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in SWITCH_VALUES:
        raise ValueError(f"{name} must be enabled or disabled")
    return SWITCH_VALUES[normalized]


def compose_files(
    mode: str,
    features: set[str],
    datadog_file: str = "",
    *,
    gpustack_branding: bool = True,
) -> list[Path]:
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")
    files = [ROOT / "docker-compose.local-runtime.yml"]
    if mode in {"private-enterprise", "external-gateway"}:
        files.append(ROOT / "docker-compose.external-ai-runtime.yml")
    if mode == "private-enterprise":
        files.append(ROOT / "docker-compose.private-llm.yml")
        if gpustack_branding:
            files.append(ROOT / "docker-compose.gpustack-branding.yml")
    if "tls" in features:
        files.append(ROOT / "docker-compose.local-tls.yml")
    if "datadog" in features:
        if not datadog_file:
            raise ValueError("FEATURES includes datadog but DATADOG_COMPOSE_FILE is empty")
        path = Path(datadog_file)
        files.append(path if path.is_absolute() else ROOT / path)
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise ValueError(f"Compose file not found: {', '.join(missing)}")
    return files


def compose_prefix(settings: dict[str, str], mode: str, features: set[str]) -> list[str]:
    docker_command = settings.get("DOCKER_COMMAND", "docker")
    command = [*shlex.split(docker_command), "compose"]
    env_file = settings.get("ENV_FILE", ".env.local-runtime")
    env_path = Path(env_file)
    env_path = env_path if env_path.is_absolute() else ROOT / env_path
    command.extend(["--env-file", str(env_path)])
    gpustack_branding = parse_switch(
        settings.get("GPUSTACK_BRANDING", "enabled"), name="GPUSTACK_BRANDING"
    )
    for path in compose_files(
        mode,
        features,
        settings.get("DATADOG_COMPOSE_FILE", ""),
        gpustack_branding=gpustack_branding,
    ):
        command.extend(["-f", str(path)])
    if "ocr" in features:
        command.extend(["--profile", "ocr"])
    return command


def infra_services(mode: str) -> list[str]:
    common = ["mongodb", "minio", "qdrant", "integration-controller"]
    if mode == "local-simple":
        return [*common, "ollama", "ollama-models"]
    if mode == "private-enterprise":
        return [*common, "gpustack"]
    return common


def build_command(
    action: str,
    settings: dict[str, str],
    mode: str,
    features: set[str],
    services: Sequence[str] = (),
) -> list[str]:
    prefix = compose_prefix(settings, mode, features)
    if action == "up":
        return [*prefix, "up", "-d", "--build", "--wait", "--remove-orphans"]
    if action == "infra-up":
        return [
            *prefix,
            "up",
            "-d",
            "--build",
            "--wait",
            "--remove-orphans",
            *infra_services(mode),
        ]
    if action == "ps":
        return [*prefix, "ps", "-a"]
    if action == "logs":
        return [*prefix, "logs", "--tail", "200", *services]
    if action == "recreate":
        targets = list(services) or ["app"]
        return [*prefix, "up", "-d", "--build", "--no-deps", "--force-recreate", *targets]
    if action == "down":
        return [*prefix, "down", "--remove-orphans"]
    if action in {"config", "preflight"}:
        return [*prefix, "config", "--quiet"]
    raise ValueError(f"unsupported action: {action}")


def print_command(command: Sequence[str]) -> None:
    print(shlex.join(command))


def run(command: Sequence[str], *, dry_run: bool) -> None:
    if dry_run:
        print_command(command)
        return
    subprocess.run(command, cwd=ROOT, check=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="nexora", description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--mode", choices=sorted(MODES))
    result.add_argument("--dry-run", action="store_true")
    subparsers = result.add_subparsers(dest="command", required=True)
    subparsers.add_parser("up")
    infra = subparsers.add_parser("infra")
    infra.add_argument("action", choices=["up"])
    subparsers.add_parser("ps")
    logs = subparsers.add_parser("logs")
    logs.add_argument("services", nargs="*")
    recreate = subparsers.add_parser("recreate")
    recreate.add_argument("services", nargs="*")
    subparsers.add_parser("down")
    subparsers.add_parser("config")
    subparsers.add_parser("preflight")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        settings = parse_config(args.config)
        mode = args.mode or settings.get("MODE", "local-simple")
        if mode not in MODES:
            raise ValueError(f"unsupported mode: {mode}")
        features = split_features(settings.get("FEATURES", ""))
        action = "infra-up" if args.command == "infra" else args.command
        services = getattr(args, "services", ())
        command = build_command(action, settings, mode, features, services)
        run(command, dry_run=args.dry_run)
        if args.command == "preflight" and not args.dry_run:
            print(f"Preflight passed for mode={mode}; Compose configuration is valid.")
            if mode == "private-enterprise":
                print(
                    "Next: ./nexora infra up, configure GPUStack workers/models, "
                    "then ./nexora up"
                )
        return 0
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"nexora: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
