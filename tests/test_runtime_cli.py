from pathlib import Path

import pytest

from scripts import nexora_runtime

ROOT = Path(__file__).resolve().parents[1]


def test_private_enterprise_mode_starts_gpustack_without_ollama():
    command = nexora_runtime.build_command(
        "infra-up",
        {"ENV_FILE": "docs/local-runtime.env.example"},
        "private-enterprise",
        set(),
    )

    assert str(ROOT / "docker-compose.external-ai-runtime.yml") in command
    assert str(ROOT / "docker-compose.private-llm.yml") in command
    assert str(ROOT / "docker-compose.gpustack-branding.yml") in command
    assert "gpustack" in command
    assert "docling" in command
    assert "ollama" not in command
    assert "ollama-models" not in command
    assert "app" not in command
    assert "--remove-orphans" in command
    assert "--build" in command


def test_private_enterprise_can_disable_branded_console_for_rollback():
    command = nexora_runtime.build_command(
        "infra-up",
        {
            "ENV_FILE": "docs/local-runtime.env.example",
            "GPUSTACK_BRANDING": "disabled",
        },
        "private-enterprise",
        set(),
    )

    assert str(ROOT / "docker-compose.private-llm.yml") in command
    assert str(ROOT / "docker-compose.gpustack-branding.yml") not in command


def test_local_simple_mode_retains_bundled_ollama():
    command = nexora_runtime.build_command(
        "infra-up",
        {"ENV_FILE": "docs/local-runtime.env.example"},
        "local-simple",
        set(),
    )

    assert str(ROOT / "docker-compose.external-ai-runtime.yml") not in command
    assert "ollama" in command
    assert "ollama-models" in command
    assert "docling" in command
    assert "gpustack" not in command
    assert "docling" in command


def test_external_gateway_mode_disables_all_bundled_model_runtimes():
    command = nexora_runtime.build_command(
        "infra-up",
        {"ENV_FILE": "docs/local-runtime.env.example"},
        "external-gateway",
        set(),
    )

    assert str(ROOT / "docker-compose.external-ai-runtime.yml") in command
    assert str(ROOT / "docker-compose.private-llm.yml") not in command
    assert "ollama" not in command
    assert "gpustack" not in command


def test_optional_features_add_tls_ocr_and_datadog_files():
    command = nexora_runtime.build_command(
        "up",
        {
            "ENV_FILE": "docs/local-runtime.env.example",
            "DATADOG_COMPOSE_FILE": "docker-compose.private-llm.yml",
        },
        "local-simple",
        {"tls", "ocr", "datadog"},
    )

    assert str(ROOT / "docker-compose.local-tls.yml") in command
    assert command[command.index("--profile") + 1] == "ocr"
    assert command.count(str(ROOT / "docker-compose.private-llm.yml")) == 1


def test_unknown_feature_fails_closed():
    with pytest.raises(ValueError, match="unsupported feature"):
        nexora_runtime.split_features("tls,unknown")


def test_runtime_switch_rejects_unknown_value():
    with pytest.raises(ValueError, match="GPUSTACK_BRANDING must be enabled or disabled"):
        nexora_runtime.parse_switch("maybe", name="GPUSTACK_BRANDING")


def test_runtime_config_rejects_unknown_settings(tmp_path):
    config = tmp_path / "runtime"
    config.write_text("MODE=local-simple\nSECRET=value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported setting SECRET"):
        nexora_runtime.parse_config(config)
