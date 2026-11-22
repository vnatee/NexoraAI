import pytest
from cryptography.fernet import Fernet

import app
import core.private_llm_control_plane as private_control_plane
from core.private_llm_control_plane import (
    GPUStackControlPlaneClient,
    normalize_inventory,
    normalize_model_action_request,
    normalize_model_deploy_request,
    normalize_model_test_request,
    rollout_preflight,
)
from core.provider_secrets import decrypt_secret
from mongo_table_connecters.private_llm_control_plane import (
    normalize_private_llm_settings,
    normalize_rollout_request,
    serialize_private_llm_settings,
)


def _inventory_payloads():
    workers = {
        "items": [
            {
                "id": 1,
                "name": "gpu-worker-a",
                "state": "ready",
                "ip": "10.0.0.10",
                "token": "must-not-leak",
                "status": {
                    "cpu": {"utilization_rate": 25},
                    "memory": {"total": 128_000, "used": 32_000},
                    "gpu_devices": [
                        {
                            "index": 0,
                            "uuid": "private-device-id",
                            "name": "NVIDIA L40S",
                            "vendor": "NVIDIA",
                            "core": {"utilization_rate": 45},
                            "memory": {"total": 48_000, "used": 8_000, "allocated": 16_000},
                        }
                    ],
                },
                "system_reserved": {"ram": 4_000, "vram": 2_000},
            },
            {
                "id": 2,
                "name": "gpu-worker-b",
                "state": "ready",
                "status": {
                    "gpu_devices": [
                        {
                            "index": 0,
                            "name": "NVIDIA L40S",
                            "memory": {"total": 48_000, "used": 4_000, "allocated": 12_000},
                        }
                    ]
                },
            },
        ]
    }
    models = {
        "items": [
            {
                "id": 10,
                "name": "private/qwen",
                "state": "running",
                "backend": "vLLM",
                "replicas": 2,
                "ready_replicas": 2,
                "env": {"SECRET": "must-not-leak"},
                "local_path": "/private/model/path",
            }
        ]
    }
    instances = {
        "items": [
            {
                "id": 100,
                "name": "qwen-a",
                "model_id": 10,
                "model_name": "private/qwen",
                "state": "running",
                "worker_id": 1,
                "worker_ip": "10.0.0.10",
                "resolved_path": "/private/model/path",
                "computed_resource_claim": {"vram": {"0": 16_000}},
            },
            {
                "id": 101,
                "name": "qwen-b",
                "model_id": 10,
                "model_name": "private/qwen",
                "state": "running",
                "worker_id": 2,
            },
        ]
    }
    clusters = {
        "items": [
            {
                "id": 2,
                "name": "IS_LocalAI",
                "state": "ready",
                "is_default": True,
                "workers": 2,
                "ready_workers": 2,
                "gpus": 2,
                "models": 1,
                "worker_config": {"token": "must-not-leak"},
            }
        ]
    }
    return workers, models, instances, clusters


def test_private_llm_settings_encrypt_and_redact_api_key(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_private_llm_settings(
        {
            "base_url": "http://gpustack:80",
            "console_url": "http://127.0.0.1:18080",
            "console_auth_mode": "local",
            "api_key": "control-plane-secret",
            "timeout_seconds": 45,
        }
    )
    public = serialize_private_llm_settings(normalized)

    assert decrypt_secret(normalized["api_key_ciphertext"]) == "control-plane-secret"
    assert public["has_api_key"] is True
    assert public["console_url"] == "http://127.0.0.1:18080"
    assert public["console_auth_mode"] == "local"
    assert "api_key_ciphertext" not in public
    assert "control-plane-secret" not in str(public)


def test_private_llm_settings_reject_public_plain_http():
    with pytest.raises(ValueError, match="HTTPS"):
        normalize_private_llm_settings({"base_url": "http://gpustack.example.com"})
    with pytest.raises(ValueError, match="HTTPS"):
        normalize_private_llm_settings({"base_url": "http://169.254.169.254"})
    assert normalize_private_llm_settings({"base_url": "https://gpustack.example.com"})[
        "base_url"
    ] == "https://gpustack.example.com"


def test_private_llm_console_supports_local_and_sso_without_url_credentials():
    oidc = normalize_private_llm_settings(
        {
            "base_url": "http://gpustack:80",
            "console_url": "https://gpustack.internal.example/console",
            "console_auth_mode": "oidc",
        }
    )
    assert oidc["console_auth_mode"] == "oidc"

    with pytest.raises(ValueError, match="Console URL"):
        normalize_private_llm_settings(
            {
                "base_url": "http://gpustack:80",
                "console_url": "https://admin:secret@gpustack.example.com",
            }
        )
    with pytest.raises(ValueError, match="sign-in"):
        normalize_private_llm_settings(
            {
                "base_url": "http://gpustack:80",
                "console_auth_mode": "disabled",
            }
        )


def test_inventory_is_capacity_focused_and_omits_sensitive_source_fields():
    inventory = normalize_inventory(*_inventory_payloads())
    rendered = str(inventory)

    assert inventory["summary"]["ready_workers"] == 2
    assert inventory["summary"]["gpus"] == 2
    assert inventory["summary"]["ready_models"] == 1
    assert inventory["summary"]["ready_clusters"] == 1
    assert inventory["clusters"] == [
        {
            "id": 2,
            "name": "IS_LocalAI",
            "state": "ready",
            "is_default": True,
            "workers": 2,
            "ready_workers": 2,
            "gpus": 2,
            "models": 1,
        }
    ]
    assert inventory["summary"]["vram_total_bytes"] == 96_000
    assert inventory["summary"]["vram_used_bytes"] == 12_000
    assert inventory["summary"]["vram_allocated_bytes"] == 28_000
    assert inventory["summary"]["vram_system_reserved_bytes"] == 2_000
    assert inventory["summary"]["vram_physical_free_bytes"] == 84_000
    assert inventory["summary"]["vram_schedulable_bytes"] == 66_000
    first_gpu = inventory["workers"][0]["gpus"][0]
    assert first_gpu["memory_physical_free_bytes"] == 40_000
    assert first_gpu["memory_schedulable_bytes"] == 30_000
    assert first_gpu["memory_available_bytes"] == 30_000
    assert inventory["generated_at"].endswith("+00:00")
    assert "must-not-leak" not in rendered
    assert "private-device-id" not in rendered
    assert "10.0.0.10" not in rendered
    assert "/private/model/path" not in rendered


def test_rollout_preflight_requires_replicas_across_distinct_workers():
    inventory = normalize_inventory(*_inventory_payloads())
    result = rollout_preflight(
        inventory,
        candidate_model="private/qwen",
        min_ready_replicas=2,
        min_ready_workers=2,
    )
    assert result["ready_replicas"] == 2
    assert result["ready_workers"] == 2

    with pytest.raises(ValueError, match="worker requirement"):
        rollout_preflight(
            inventory,
            candidate_model="private/qwen",
            min_ready_replicas=2,
            min_ready_workers=3,
        )


def test_rollout_request_has_bounded_governed_fields_only():
    normalized = normalize_rollout_request(
        {
            "proxy_id": "private-chat",
            "candidate_model": "private/qwen-72b:v2",
            "min_ready_replicas": 2,
            "min_ready_workers": 2,
            "prompt": "must not be persisted",
        }
    )
    assert normalized == {
        "proxy_id": "private-chat",
        "candidate_model": "private/qwen-72b:v2",
        "min_ready_replicas": 2,
        "min_ready_workers": 2,
    }


def test_model_deployment_is_a_bounded_confirmed_gpustack_request():
    normalized = normalize_model_deploy_request(
        {
            "name": "private-qwen",
            "huggingface_repo_id": "Qwen/Qwen3-8B",
            "category": "llm",
            "replicas": 2,
            "cluster_id": 2,
            "confirmation": "deploy:private-qwen",
            "env": {"SECRET": "must-not-pass"},
            "backend_parameters": ["--unsafe"],
        }
    )

    assert normalized == {
        "name": "private-qwen",
        "source": "huggingface",
        "huggingface_repo_id": "Qwen/Qwen3-8B",
        "backend": "vLLM",
        "categories": ["llm"],
        "placement_strategy": "spread",
        "replicas": 2,
        "cluster_id": 2,
        "enable_model_route": True,
    }
    with pytest.raises(ValueError, match="confirmation"):
        normalize_model_deploy_request(
            {
                "name": "private-qwen",
                "huggingface_repo_id": "Qwen/Qwen3-8B",
                "cluster_id": 2,
            }
        )


def test_model_actions_require_exact_confirmation_and_bounded_replicas():
    assert normalize_model_action_request(
        {"action": "stop", "confirmation": "stop:10"}, model_id=10
    ) == {"action": "stop", "replicas": 0}
    assert normalize_model_action_request(
        {"action": "scale", "replicas": 3, "confirmation": "scale:10"},
        model_id=10,
    ) == {"action": "scale", "replicas": 3}
    with pytest.raises(ValueError, match="confirmation"):
        normalize_model_action_request(
            {"action": "restart", "confirmation": "restart:11"}, model_id=10
        )
    with pytest.raises(ValueError, match="between 0 and 100"):
        normalize_model_action_request(
            {"action": "scale", "replicas": 101, "confirmation": "scale:10"},
            model_id=10,
        )


def test_model_test_prompt_is_bounded_without_extra_fields():
    assert normalize_model_test_request(
        {"prompt": "  Say OK  ", "system_prompt": "must not pass"}
    ) == {"prompt": "Say OK"}
    with pytest.raises(ValueError, match="4,000"):
        normalize_model_test_request({"prompt": "x" * 4_001})


@pytest.mark.asyncio
async def test_gpustack_model_scale_reads_source_then_sends_allowlisted_update(monkeypatch):
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, path, **_kwargs):
            requests.append(("GET", path, None))
            return Response(
                {
                    "id": 10,
                    "name": "private-qwen",
                    "source": "huggingface",
                    "huggingface_repo_id": "Qwen/Qwen3-8B",
                    "env": {"SECRET": "must-not-pass"},
                }
            )

        async def put(self, path, json):
            requests.append(("PUT", path, json))
            return Response({"id": 10, **json, "state": "pending"})

    client = Client()
    monkeypatch.setattr(private_control_plane.httpx, "AsyncClient", lambda **_kwargs: client)
    result = await GPUStackControlPlaneClient(
        {"base_url": "http://gpustack:80", "timeout_seconds": 30}
    ).scale_model(10, 3)

    assert result["replicas"] == 3
    assert requests[-1] == (
        "PUT",
        "/v2/models/10",
        {
            "name": "private-qwen",
            "source": "huggingface",
            "replicas": 3,
            "huggingface_repo_id": "Qwen/Qwen3-8B",
        },
    )
    assert "SECRET" not in str(requests)


@pytest.mark.asyncio
async def test_gpustack_model_deploy_uses_pinned_v2_contract(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": 12,
                "name": "qwen3-0.6b-demo",
                "state": "pending",
                "backend": "vLLM",
                "replicas": 1,
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, path, json):
            requests.append((path, json))
            return Response()

    monkeypatch.setattr(
        private_control_plane.httpx, "AsyncClient", lambda **_kwargs: Client()
    )
    deployment = normalize_model_deploy_request(
        {
            "name": "qwen3-0.6b-demo",
            "huggingface_repo_id": "Qwen/Qwen3-0.6B",
            "category": "llm",
            "replicas": 1,
            "cluster_id": 2,
            "confirmation": "deploy:qwen3-0.6b-demo",
        }
    )

    result = await GPUStackControlPlaneClient(
        {"base_url": "http://gpustack:80", "timeout_seconds": 30}
    ).deploy_model(deployment)

    assert result["id"] == 12
    assert requests == [("/v2/models", deployment)]


@pytest.mark.asyncio
async def test_gpustack_catalog_returns_allowlisted_models_and_variants(monkeypatch):
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, path, params):
            requests.append((path, params))
            if path == "/v2/model-sets":
                return Response(
                    {
                        "items": [
                            {
                                "id": 1,
                                "name": "Qwen3-0.6B",
                                "description": "Small chat model",
                                "categories": ["llm"],
                                "capabilities": ["tools"],
                                "size": 0.6,
                                "size_unit": "B",
                                "licenses": ["apache-2.0"],
                                "private_metadata": "must-not-pass",
                            }
                        ],
                        "pagination": {"totalPage": 1},
                    }
                )
            return Response(
                {
                    "items": [
                        {
                            "source": "huggingface",
                            "huggingface_repo_id": "Qwen/Qwen3-0.6B",
                            "backend": "vLLM",
                            "backend_version": "0.9.2",
                            "quantization": "BF16",
                            "mode": "standard",
                            "env": {"SECRET": "must-not-pass"},
                        },
                        {"source": "model_scope", "model_scope_model_id": "private"},
                    ],
                    "pagination": {"totalPage": 1},
                }
            )

    monkeypatch.setattr(
        private_control_plane.httpx, "AsyncClient", lambda **_kwargs: Client()
    )
    control_plane = GPUStackControlPlaneClient(
        {"base_url": "http://gpustack:80", "timeout_seconds": 30}
    )

    models = await control_plane.catalog_models(category="llm", search="qwen")
    specs = await control_plane.catalog_specs(model_set_id=1, cluster_id=2)

    assert models[0]["name"] == "Qwen3-0.6B"
    assert specs == [
        {
            "huggingface_repo_id": "Qwen/Qwen3-0.6B",
            "backend": "vLLM",
            "backend_version": "0.9.2",
            "quantization": "BF16",
            "mode": "standard",
        }
    ]
    assert requests == [
        ("/v2/model-sets", {"page": 1, "perPage": 100, "categories": "llm", "search": "qwen"}),
        ("/v2/model-sets/1/specs", {"page": 1, "perPage": 100, "cluster_id": 2}),
    ]
    assert "must-not-pass" not in str(models)
    assert "must-not-pass" not in str(specs)


@pytest.mark.asyncio
async def test_gpustack_model_preflight_sends_allowlisted_spec_and_bounds_result(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "compatible": True,
                        "error": False,
                        "resource_claim": {"ram": 2_000, "vram": 4_000},
                        "compatibility_messages": ["vLLM supported"],
                        "scheduling_messages": ["Fits worker 1"],
                        "internal": "must-not-pass",
                    }
                ]
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, path, json):
            requests.append((path, json))
            return Response()

    monkeypatch.setattr(
        private_control_plane.httpx, "AsyncClient", lambda **_kwargs: Client()
    )
    deployment = {
        **normalize_model_deploy_request(
            {
                "name": "qwen3-0.6b-demo",
                "huggingface_repo_id": "Qwen/Qwen3-0.6B",
                "category": "llm",
                "replicas": 1,
                "cluster_id": 2,
                "confirmation": "deploy:qwen3-0.6b-demo",
            }
        ),
        "prompt": "must-not-pass",
    }

    result = await GPUStackControlPlaneClient(
        {"base_url": "http://gpustack:80", "timeout_seconds": 30}
    ).evaluate_model(deployment)

    assert requests[0][0] == "/v2/model-evaluations"
    assert requests[0][1]["cluster_id"] == 2
    assert "cluster_id" not in requests[0][1]["model_specs"][0]
    assert "prompt" not in str(requests)
    assert result["compatible"] is True
    assert result["resource_claim"] == {"ram_bytes": 2_000, "vram_bytes": 4_000}
    assert "internal" not in result


@pytest.mark.asyncio
async def test_gpustack_native_chat_test_returns_bounded_result(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 1,
                    "total_tokens": 5,
                },
                "internal": "must-not-pass",
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, path, json):
            requests.append((path, json))
            return Response()

    monkeypatch.setattr(
        private_control_plane.httpx, "AsyncClient", lambda **_kwargs: Client()
    )
    result = await GPUStackControlPlaneClient(
        {"base_url": "http://gpustack:80", "timeout_seconds": 30}
    ).test_chat_model("qwen3-0.6b-demo", "Say OK")

    assert requests[0][0] == "/v1/chat/completions"
    assert requests[0][1]["model"] == "qwen3-0.6b-demo"
    assert result["content"] == "OK"
    assert result["usage"]["total_tokens"] == 5
    assert "internal" not in result


@pytest.mark.asyncio
async def test_rollout_activation_rechecks_capacity_and_switches_only_planned_proxy(monkeypatch):
    gateway_settings = {
        "_id": "system",
        "mode": "external",
        "name": "Private Gateway",
        "base_url": "https://gateway.test/v1",
        "models": [
            {
                "id": "private-chat",
                "model": "private/qwen-v1",
                "routing_strategy": "model_based",
            },
            {
                "id": "other",
                "model": "private/other",
                "routing_strategy": "model_based",
            },
        ],
        "default_model_id": "private-chat",
    }
    plan = {
        "_id": "rollout-1",
        "proxy_id": "private-chat",
        "candidate_model": "private/qwen",
        "previous_model": "private/qwen-v1",
        "min_ready_replicas": 2,
        "min_ready_workers": 2,
        "status": "pending_approval",
    }
    saved = []
    updated = []
    inventory = normalize_inventory(*_inventory_payloads())

    monkeypatch.setattr(app, "get_ai_gateway_settings", lambda: gateway_settings)

    async def get_inventory():
        return inventory

    async def conform(settings, model_id=None):
        assert model_id == "private-chat"
        assert settings["models"][0]["model"] == "private/qwen"
        assert settings["models"][1]["model"] == "private/other"
        return {"ready": True, "checks": []}

    monkeypatch.setattr(app, "_private_llm_inventory", get_inventory)
    monkeypatch.setattr(app, "run_gateway_conformance", conform)
    monkeypatch.setattr(
        app,
        "save_ai_gateway_settings",
        lambda settings, actor_id: saved.append((settings, actor_id)) or settings,
    )
    monkeypatch.setattr(app, "_refresh_llm_profile_registry", lambda: None)
    monkeypatch.setattr(
        app,
        "update_rollout_plan",
        lambda plan_id, actor_id, **values: updated.append(values)
        or {**plan, **values},
    )

    result = await app._activate_private_llm_route(plan, actor_id="admin-1", rollback=False)

    assert saved[0][0]["models"][0]["model"] == "private/qwen"
    assert saved[0][0]["models"][1]["model"] == "private/other"
    assert saved[0][1] == "admin-1"
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_private_llm_admin_inventory_requires_system_admin(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        app,
        "_require_system_admin",
        lambda claims: called.append(claims) or {"_id": "admin-1"},
    )

    async def inventory():
        return normalize_inventory(*_inventory_payloads())

    monkeypatch.setattr(app, "_private_llm_inventory", inventory)
    monkeypatch.setattr(app, "insert_integration_lifecycle_event", lambda **_event: None)

    response = await client.get("/admin/private-llm/inventory")

    assert response.status_code == 200
    assert called
    body = await response.get_json()
    assert body["summary"]["ready_workers"] == 2


@pytest.mark.asyncio
async def test_private_llm_model_action_is_admin_confirmed_and_audited(client, monkeypatch):
    calls = []

    class ControlPlane:
        async def scale_model(self, model_id, replicas):
            calls.append((model_id, replicas))
            return {"id": model_id, "replicas": replicas}

    monkeypatch.setattr(app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(app, "_private_llm_client", lambda: ControlPlane())
    monkeypatch.setattr(
        app,
        "insert_integration_lifecycle_event",
        lambda **event: calls.append(event),
    )

    response = await client.post(
        "/admin/private-llm/models/10/actions",
        json={"action": "scale", "replicas": 2, "confirmation": "scale:10"},
    )

    assert response.status_code == 202
    assert calls[0] == (10, 2)
    assert calls[1]["action"] == "private_llm_model_scale"
    assert calls[1]["actor_id"] == "admin-1"
