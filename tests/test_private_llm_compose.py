from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_private_llm_overlay_pins_and_persists_gpustack_without_public_binding():
    compose = yaml.safe_load((ROOT / "docker-compose.private-llm.yml").read_text(encoding="utf-8"))
    gpustack = compose["services"]["gpustack"]

    assert gpustack["image"] == "${GPUSTACK_IMAGE:-gpustack/gpustack:v2.3.1}"
    assert gpustack["ports"] == ["${GPUSTACK_BIND_ADDRESS:-127.0.0.1}:${GPUSTACK_PORT:-18080}:80"]
    assert "nexora_gpustack_data:/var/lib/gpustack" in gpustack["volumes"]
    assert "no-new-privileges:true" in gpustack["security_opt"]
    assert "http://127.0.0.1/healthz" in gpustack["healthcheck"]["test"]


def test_private_llm_overlay_exposes_only_control_plane_health_to_app():
    compose = yaml.safe_load((ROOT / "docker-compose.private-llm.yml").read_text(encoding="utf-8"))
    app_environment = compose["services"]["app"]["environment"]

    assert app_environment == {
        "GPUSTACK_CONTROL_PLANE_URL": "${GPUSTACK_CONTROL_PLANE_URL:-http://gpustack:80}"
    }
    assert "GPUSTACK_API_KEY" not in app_environment


def test_private_llm_environment_template_contains_no_credentials():
    template = (ROOT / "docs/private-model-control-plane.env.example").read_text(encoding="utf-8")

    assert "GPUSTACK_IMAGE=gpustack/gpustack:v2.3.1" in template
    assert "GPUSTACK_BIND_ADDRESS=127.0.0.1" in template
    assert "API_KEY=" not in template
    assert "TOKEN=" not in template

