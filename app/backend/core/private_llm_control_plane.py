"""Governed GPUStack inventory, model lifecycle, and rollout checks."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from core.provider_secrets import decrypt_secret

_ROUTE_NAME = re.compile(r"^[A-Za-z](?:[A-Za-z0-9_.:-]*[A-Za-z0-9])?$")
_HUGGING_FACE_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_DEPLOY_CATEGORIES = {"llm", "embedding"}
_MODEL_ACTIONS = {"restart", "scale", "stop"}


def normalize_model_deploy_request(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Model deployment payload must be an object")
    name = str(data.get("name") or "").strip()
    repository = str(data.get("huggingface_repo_id") or "").strip()
    category = str(data.get("category") or "llm").strip().lower()
    if len(name) > 128 or not _ROUTE_NAME.fullmatch(name):
        raise ValueError(
            "Model name must start with a letter and contain only letters, numbers, hyphens, underscores, dots, or colons"
        )
    if str(data.get("confirmation") or "") != f"deploy:{name}":
        raise ValueError("Model deployment confirmation does not match")
    if not _HUGGING_FACE_REPOSITORY.fullmatch(repository) or "/" not in repository:
        raise ValueError("Enter a valid Hugging Face repository such as organization/model")
    if category not in _DEPLOY_CATEGORIES:
        raise ValueError("Model category must be llm or embedding")
    try:
        replicas = int(data.get("replicas") or 1)
    except (TypeError, ValueError) as error:
        raise ValueError("Replica count must be an integer") from error
    if not 1 <= replicas <= 100:
        raise ValueError("Replica count must be between 1 and 100")
    try:
        cluster_id = int(data.get("cluster_id"))
    except (TypeError, ValueError) as error:
        raise ValueError("Select a GPUStack deployment cluster") from error
    if cluster_id < 1:
        raise ValueError("Select a GPUStack deployment cluster")
    return {
        "name": name,
        "source": "huggingface",
        "huggingface_repo_id": repository,
        "backend": "vLLM",
        "categories": [category],
        "placement_strategy": "spread",
        "replicas": replicas,
        "cluster_id": cluster_id,
        "enable_model_route": True,
    }


def normalize_model_action_request(
    data: object, *, model_id: int
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Model action payload must be an object")
    action = str(data.get("action") or "").strip().lower()
    if action not in _MODEL_ACTIONS:
        raise ValueError("Model action must be restart, scale, or stop")
    if str(data.get("confirmation") or "") != f"{action}:{model_id}":
        raise ValueError("Model action confirmation does not match")
    normalized: dict[str, Any] = {"action": action}
    if action == "scale":
        try:
            replicas = int(data.get("replicas"))
        except (TypeError, ValueError) as error:
            raise ValueError("Replica count must be an integer") from error
        if not 0 <= replicas <= 100:
            raise ValueError("Replica count must be between 0 and 100")
        normalized["replicas"] = replicas
    elif action == "stop":
        normalized["replicas"] = 0
    return normalized


def normalize_model_test_request(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Model test payload must be an object")
    prompt = str(data.get("prompt") or "").strip()
    if not prompt or len(prompt) > 4_000:
        raise ValueError("Test prompt must contain between 1 and 4,000 characters")
    return {"prompt": prompt}


def _items(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("GPUStack returned an unsupported inventory response")
    return [item for item in payload["items"] if isinstance(item, dict)]


def _integer(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _worker_view(worker: dict[str, Any]) -> dict[str, Any]:
    status = worker.get("status") if isinstance(worker.get("status"), dict) else {}
    system_reserved = (
        worker.get("system_reserved")
        if isinstance(worker.get("system_reserved"), dict)
        else {}
    )
    reserved_vram = _integer(system_reserved.get("vram"))
    devices = status.get("gpu_devices") if isinstance(status.get("gpu_devices"), list) else []
    gpus: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        memory = device.get("memory") if isinstance(device.get("memory"), dict) else {}
        total = _integer(memory.get("total"))
        used = _integer(memory.get("used"))
        allocated = _integer(memory.get("allocated"))
        physical_free = max(0, total - used)
        schedulable = max(0, total - allocated - reserved_vram)
        utilization = memory.get("utilization_rate")
        if utilization is None:
            utilization = (used / total * 100) if total else 0
        gpus.append(
            {
                "index": device.get("index"),
                "name": str(device.get("name") or "Unknown GPU")[:160],
                "vendor": str(device.get("vendor") or "")[:60],
                "memory_total_bytes": total,
                "memory_used_bytes": used,
                "memory_allocated_bytes": allocated,
                "memory_system_reserved_bytes": reserved_vram,
                "memory_physical_free_bytes": physical_free,
                "memory_schedulable_bytes": schedulable,
                # Compatibility field for clients predating the explicit
                # physical-versus-schedulable capacity split.
                "memory_available_bytes": min(physical_free, schedulable),
                "memory_utilization_percent": float(utilization or 0),
                "utilization_percent": float(
                    (device.get("core") or {}).get("utilization_rate") or 0
                ),
            }
        )
    memory = status.get("memory") if isinstance(status.get("memory"), dict) else {}
    return {
        "id": worker.get("id"),
        "name": str(worker.get("name") or worker.get("hostname") or "Unnamed worker")[:160],
        "state": str(worker.get("state") or "unknown"),
        "heartbeat_time": worker.get("heartbeat_time"),
        "worker_version": str(worker.get("worker_version") or "")[:80],
        "cpu_utilization_percent": float(
            (status.get("cpu") or {}).get("utilization_rate") or 0
        ),
        "memory_total_bytes": _integer(memory.get("total")),
        "memory_used_bytes": _integer(memory.get("used")),
        "gpus": gpus,
    }


def _model_view(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": model.get("id"),
        "name": str(model.get("name") or "Unnamed model")[:255],
        "state": str(model.get("state") or "unknown"),
        "backend": str(model.get("backend") or "")[:80],
        "backend_version": str(model.get("backend_version") or "")[:80],
        "replicas": _integer(model.get("replicas")),
        "ready_replicas": _integer(model.get("ready_replicas")),
        "categories": [str(value)[:60] for value in (model.get("categories") or [])[:20]],
        "stale": model.get("stale") is True,
        "updated_at": model.get("updated_at"),
    }


def _instance_worker_ids(instance: dict[str, Any]) -> list[int]:
    values: set[int] = set()
    primary = instance.get("worker_id")
    if isinstance(primary, int):
        values.add(primary)
    distributed = instance.get("distributed_servers")
    if isinstance(distributed, dict):
        for subordinate in distributed.get("subordinate_workers") or []:
            if isinstance(subordinate, dict) and isinstance(subordinate.get("worker_id"), int):
                values.add(subordinate["worker_id"])
    return sorted(values)


def _instance_view(instance: dict[str, Any]) -> dict[str, Any]:
    claim = instance.get("computed_resource_claim")
    vram = claim.get("vram") if isinstance(claim, dict) and isinstance(claim.get("vram"), dict) else {}
    return {
        "id": instance.get("id"),
        "name": str(instance.get("name") or "Unnamed instance")[:255],
        "model_id": instance.get("model_id"),
        "model_name": str(instance.get("model_name") or "")[:255],
        "state": str(instance.get("state") or "unknown"),
        "worker_ids": _instance_worker_ids(instance),
        "gpu_indexes": [value for value in (instance.get("gpu_indexes") or []) if isinstance(value, int)][:64],
        "vram_claim_bytes": sum(_integer(value) for value in vram.values()),
        "restart_count": _integer(instance.get("restart_count")),
        "updated_at": instance.get("updated_at"),
    }


def _cluster_view(cluster: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": cluster.get("id"),
        "name": str(cluster.get("name") or "Unnamed cluster")[:160],
        "state": str(cluster.get("state") or "unknown"),
        "is_default": cluster.get("is_default") is True,
        "workers": _integer(cluster.get("workers")),
        "ready_workers": _integer(cluster.get("ready_workers")),
        "gpus": _integer(cluster.get("gpus")),
        "models": _integer(cluster.get("models")),
    }


def _catalog_model_view(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": model.get("id"),
        "name": str(model.get("name") or "Unnamed model")[:160],
        "description": str(model.get("description") or "")[:1_000],
        "categories": [str(value)[:60] for value in (model.get("categories") or [])[:20]],
        "capabilities": [str(value)[:60] for value in (model.get("capabilities") or [])[:20]],
        "size": model.get("size"),
        "size_unit": str(model.get("size_unit") or "")[:20],
        "licenses": [str(value)[:100] for value in (model.get("licenses") or [])[:20]],
    }


def _catalog_spec_view(spec: dict[str, Any]) -> dict[str, Any] | None:
    if str(spec.get("source") or "") != "huggingface":
        return None
    repository = str(spec.get("huggingface_repo_id") or "")[:255]
    if not repository:
        return None
    return {
        "huggingface_repo_id": repository,
        "backend": str(spec.get("backend") or "")[:80],
        "backend_version": str(spec.get("backend_version") or "")[:80],
        "quantization": str(spec.get("quantization") or "")[:80],
        "mode": str(spec.get("mode") or "standard")[:80],
    }


def normalize_inventory(
    workers_payload: object,
    models_payload: object,
    instances_payload: object,
    clusters_payload: object | None = None,
) -> dict[str, Any]:
    workers = [_worker_view(item) for item in _items(workers_payload)]
    models = [_model_view(item) for item in _items(models_payload)]
    instances = [_instance_view(item) for item in _items(instances_payload)]
    clusters = [
        _cluster_view(item)
        for item in _items(clusters_payload or {"items": []})
    ]
    gpus = [gpu for worker in workers for gpu in worker["gpus"]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "workers": len(workers),
            "ready_workers": sum(worker["state"].lower() == "ready" for worker in workers),
            "gpus": len(gpus),
            "vram_total_bytes": sum(gpu["memory_total_bytes"] for gpu in gpus),
            "vram_used_bytes": sum(gpu["memory_used_bytes"] for gpu in gpus),
            "vram_allocated_bytes": sum(gpu["memory_allocated_bytes"] for gpu in gpus),
            "vram_system_reserved_bytes": sum(
                gpu["memory_system_reserved_bytes"] for gpu in gpus
            ),
            "vram_physical_free_bytes": sum(
                gpu["memory_physical_free_bytes"] for gpu in gpus
            ),
            "vram_schedulable_bytes": sum(
                gpu["memory_schedulable_bytes"] for gpu in gpus
            ),
            "vram_available_bytes": sum(gpu["memory_available_bytes"] for gpu in gpus),
            "models": len(models),
            "ready_models": sum(
                model["state"].lower() == "running" and model["ready_replicas"] > 0
                for model in models
            ),
            "running_instances": sum(instance["state"].lower() == "running" for instance in instances),
            "clusters": len(clusters),
            "ready_clusters": sum(
                cluster["state"].lower() == "ready" for cluster in clusters
            ),
        },
        "clusters": clusters,
        "workers": workers,
        "models": models,
        "instances": instances,
    }


class GPUStackControlPlaneClient:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.base_url = str(settings.get("base_url") or "").rstrip("/")
        self.timeout_seconds = int(settings.get("timeout_seconds") or 30)
        token = decrypt_secret(settings.get("api_key_ciphertext"))
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def _all(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        extra_params: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        params = {"page": 1, "perPage": 100, **(extra_params or {})}
        response = await client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        collected = _items(payload)
        pagination = payload.get("pagination") if isinstance(payload, dict) else {}
        total_pages = min(100, _integer((pagination or {}).get("totalPage")) or 1)
        for page in range(2, total_pages + 1):
            next_response = await client.get(
                path, params={**params, "page": page}
            )
            next_response.raise_for_status()
            collected.extend(_items(next_response.json()))
        return {"items": collected}

    async def inventory(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            payloads = await asyncio.gather(
                self._all(client, "/v2/workers"),
                self._all(client, "/v2/models"),
                self._all(client, "/v2/model-instances"),
                self._all(
                    client,
                    "/v2/clusters",
                    extra_params={"gpu_instance_enabled": "false"},
                ),
            )
            return normalize_inventory(*payloads)

    async def deploy_model(self, deployment: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post("/v2/models", json=deployment)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("GPUStack returned an unsupported model response")
        return _model_view(payload)

    async def _replica_update_payload(
        self, client: httpx.AsyncClient, model_id: int, replicas: int
    ) -> dict[str, Any]:
        response = await client.get(f"/v2/models/{model_id}")
        response.raise_for_status()
        model = response.json()
        if not isinstance(model, dict):
            raise ValueError("GPUStack returned an unsupported model response")
        schedule = model.get("scaling_schedule")
        if isinstance(schedule, dict) and schedule.get("enabled") is True:
            raise ValueError(
                "Disable the GPUStack scaling schedule before changing replicas manually"
            )
        source = str(model.get("source") or "")
        payload: dict[str, Any] = {
            "name": str(model.get("name") or ""),
            "source": source,
            "replicas": replicas,
        }
        source_fields = {
            "huggingface": ("huggingface_repo_id", "huggingface_filename"),
            "model_scope": ("model_scope_model_id", "model_scope_file_path"),
            "local_path": ("local_path",),
        }.get(source)
        if not payload["name"] or source_fields is None:
            raise ValueError("GPUStack model source cannot be safely updated")
        for field in source_fields:
            value = model.get(field)
            if value is not None:
                payload[field] = value
        if not any(payload.get(field) for field in source_fields):
            raise ValueError("GPUStack model source cannot be safely updated")
        return payload

    async def scale_model(self, model_id: int, replicas: int) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            payload = await self._replica_update_payload(client, model_id, replicas)
            response = await client.put(f"/v2/models/{model_id}", json=payload)
            response.raise_for_status()
            model = response.json()
        if not isinstance(model, dict):
            raise ValueError("GPUStack returned an unsupported model response")
        return _model_view(model)

    async def restart_model(self, model_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(f"/v2/models/{model_id}/restart")
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("GPUStack returned an unsupported restart response")
        return {
            "accepted": payload.get("accepted") is not False,
            "completed": payload.get("completed") is True,
            "phase": str(payload.get("phase") or "restarting")[:40],
            "restarted": payload.get("restarted") is True,
            "message": str(payload.get("message") or "")[:500],
        }

    async def test_chat_model(self, model_name: str, prompt: str) -> dict[str, Any]:
        started = time.perf_counter()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 256,
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices") if isinstance(payload, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices else None
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ValueError("GPUStack returned an unsupported chat response")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return {
            "model": model_name,
            "content": content[:20_000],
            "finish_reason": str(choice.get("finish_reason") or "")[:80],
            "latency_ms": round((time.perf_counter() - started) * 1_000),
            "usage": {
                "prompt_tokens": _integer(usage.get("prompt_tokens")),
                "completion_tokens": _integer(usage.get("completion_tokens")),
                "total_tokens": _integer(usage.get("total_tokens")),
            },
        }

    async def catalog_models(
        self, *, category: str, search: str = ""
    ) -> list[dict[str, Any]]:
        if category not in _DEPLOY_CATEGORIES:
            raise ValueError("Catalog category must be llm or embedding")
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            payload = await self._all(
                client,
                "/v2/model-sets",
                extra_params={
                    "categories": category,
                    **({"search": search[:100]} if search else {}),
                },
            )
        return [_catalog_model_view(item) for item in _items(payload)][:200]

    async def catalog_specs(
        self, *, model_set_id: int, cluster_id: int
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        ) as client:
            payload = await self._all(
                client,
                f"/v2/model-sets/{model_set_id}/specs",
                extra_params={"cluster_id": cluster_id},
            )
        views = [_catalog_spec_view(item) for item in _items(payload)]
        return [item for item in views if item is not None][:100]

    async def evaluate_model(self, deployment: dict[str, Any]) -> dict[str, Any]:
        spec = {
            key: value
            for key, value in deployment.items()
            if key
            in {
                "name",
                "source",
                "huggingface_repo_id",
                "backend",
                "categories",
                "placement_strategy",
                "replicas",
            }
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=max(self.timeout_seconds, 60),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                "/v2/model-evaluations",
                json={"cluster_id": deployment["cluster_id"], "model_specs": [spec]},
            )
            response.raise_for_status()
            payload = response.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        result = results[0] if isinstance(results, list) and results else None
        if not isinstance(result, dict):
            raise ValueError("GPUStack returned an unsupported evaluation response")
        claim = result.get("resource_claim") if isinstance(result.get("resource_claim"), dict) else {}
        return {
            "compatible": result.get("compatible") is True and result.get("error") is not True,
            "error": result.get("error") is True,
            "error_message": str(result.get("error_message") or "")[:1_000],
            "compatibility_messages": [
                str(value)[:1_000] for value in (result.get("compatibility_messages") or [])[:20]
            ],
            "scheduling_messages": [
                str(value)[:1_000] for value in (result.get("scheduling_messages") or [])[:20]
            ],
            "resource_claim": {
                "ram_bytes": _integer(claim.get("ram")),
                "vram_bytes": _integer(claim.get("vram")),
            },
        }


def rollout_preflight(
    inventory: dict[str, Any],
    *,
    candidate_model: str,
    min_ready_replicas: int,
    min_ready_workers: int,
) -> dict[str, Any]:
    model = next(
        (item for item in inventory.get("models") or [] if item.get("name") == candidate_model),
        None,
    )
    if model is None:
        raise ValueError("Candidate model was not found in GPUStack inventory")
    if str(model.get("state") or "").lower() != "running":
        raise ValueError("Candidate model is not running")
    if int(model.get("ready_replicas") or 0) < min_ready_replicas:
        raise ValueError("Candidate model does not meet the ready replica requirement")
    running = [
        item
        for item in inventory.get("instances") or []
        if item.get("model_name") == candidate_model
        and str(item.get("state") or "").lower() == "running"
    ]
    ready_worker_ids = {
        worker_id
        for item in running
        for worker_id in item.get("worker_ids") or []
    }
    if len(ready_worker_ids) < min_ready_workers:
        raise ValueError("Candidate model does not meet the ready worker requirement")
    return {
        "model_id": model.get("id"),
        "model_state": model.get("state"),
        "ready_replicas": model.get("ready_replicas"),
        "ready_workers": len(ready_worker_ids),
        "running_instances": len(running),
        "stale": model.get("stale") is True,
    }
