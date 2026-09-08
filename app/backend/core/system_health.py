from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import aiohttp
import psutil

INTEGRATION_COLLECTIONS = {
    "rest_api": "external_apis",
    "database": "external_databases",
    "mail": "mail_connections",
    "messaging": "messaging_connections",
    "business_documents": "business_document_connections",
    "mcp": "mcp_servers",
}


def _service(
    service_id: str,
    name: str,
    status: str,
    detail: str,
    *,
    provider: str = "",
    latency_ms: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": service_id,
        "name": name,
        "status": status,
        "detail": detail,
        "provider": provider,
    }
    if latency_ms is not None:
        result["latency_ms"] = latency_ms
    return result


def _safe_http_url(raw_url: str, path: str) -> str | None:
    value = str(raw_url or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}{path}"


async def _http_probe(url: str, headers: Mapping[str, str] | None = None) -> int:
    started = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=2)
    async with aiohttp.ClientSession(timeout=timeout, headers=dict(headers or {})) as session:
        async with session.get(url) as response:
            if response.status >= 400:
                raise RuntimeError("Health endpoint returned an error")
            await response.content.read(1024)
    return round((time.perf_counter() - started) * 1000)


async def _http_service(
    service_id: str,
    name: str,
    provider: str,
    url: str | None,
    *,
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not url:
        return _service(service_id, name, "not_configured", "Not configured", provider=provider)
    try:
        latency = await _http_probe(url, headers)
        return _service(service_id, name, "healthy", "Health endpoint responded", provider=provider, latency_ms=latency)
    except Exception:
        return _service(service_id, name, "unavailable", "Health endpoint did not respond", provider=provider)


async def _static_service(value: dict[str, Any]) -> dict[str, Any]:
    return value


def _task_state(config: Mapping[str, Any], key: str, enabled: bool) -> str:
    if not enabled:
        return "not_configured"
    task = config.get(key)
    if task is None:
        return "stopped"
    return "stopped" if task.done() else "running"


def _integration_summary(database: Any) -> dict[str, Any]:
    by_kind: list[dict[str, Any]] = []
    total = enabled = disabled = attention = 0
    attention_states = {"failed", "cleanup_pending", "stop_pending"}
    for kind, collection_name in INTEGRATION_COLLECTIONS.items():
        collection = database[collection_name]
        active_filter = {"delete_at": None}
        kind_total = int(collection.count_documents(active_filter))
        kind_disabled = int(collection.count_documents({**active_filter, "enabled": False}))
        kind_attention = int(
            collection.count_documents(
                {**active_filter, "provisioning_status": {"$in": sorted(attention_states)}}
            )
        )
        kind_enabled = max(0, kind_total - kind_disabled)
        total += kind_total
        enabled += kind_enabled
        disabled += kind_disabled
        attention += kind_attention
        by_kind.append(
            {
                "kind": kind,
                "total": kind_total,
                "enabled": kind_enabled,
                "attention": kind_attention,
            }
        )
    return {
        "total": total,
        "enabled": enabled,
        "disabled": disabled,
        "attention": attention,
        "by_kind": by_kind,
    }


def _job_summary(database: Any, config: Mapping[str, Any], environ: Mapping[str, str]) -> dict[str, Any]:
    ingestion = database["ingestion_jobs"]
    attachments = database["chat_attachment_metadata"]
    attachment_enabled = str(environ.get("CHAT_ATTACHMENT_STORE", "disabled")).lower() != "disabled"
    ingestion_enabled = str(environ.get("USE_USER_UPLOAD", "")).lower() == "true"
    return {
        "ingestion": {
            "queued": int(ingestion.count_documents({"status": "uploaded"})),
            "processing": int(ingestion.count_documents({"status": {"$in": ["extracting", "chunking", "embedding"]}})),
            "failed": int(ingestion.count_documents({"status": "failed"})),
            "worker_status": _task_state(config, "ingestion_recovery_task", ingestion_enabled),
        },
        "attachments": {
            "queued": int(attachments.count_documents({"status": "stored", "delete_at": None})),
            "processing": int(attachments.count_documents({"status": "extracting", "delete_at": None})),
            "failed": int(attachments.count_documents({"status": "failed", "delete_at": None})),
            "worker_status": _task_state(config, "chat_attachment_recovery_task", attachment_enabled),
            "cleanup_status": _task_state(config, "chat_attachment_cleanup_task", attachment_enabled),
        },
    }


def _ollama_health_url(environ: Mapping[str, str]) -> str | None:
    for setting_name in ("LLM_BASE_URL", "EMBEDDING_BASE_URL"):
        raw_url = str(environ.get(setting_name, "")).strip()
        candidate = _safe_http_url(raw_url, "/api/tags")
        if not candidate:
            continue
        parsed = urlparse(candidate)
        if parsed.hostname == "ollama" or parsed.port == 11434:
            return candidate
    return None


def _resource_status(percent: float) -> str:
    if percent >= 90:
        return "critical"
    if percent >= 80:
        return "warning"
    return "healthy"


def _resource_snapshot() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_percent = round(float(psutil.cpu_percent(interval=0.1)), 1)
    process = psutil.Process()
    process_memory = process.memory_info()
    statuses = [
        _resource_status(cpu_percent),
        _resource_status(float(memory.percent)),
        _resource_status(float(disk.percent)),
    ]
    status = "critical" if "critical" in statuses else "warning" if "warning" in statuses else "healthy"
    try:
        load_average_1m = round(float(os.getloadavg()[0]), 2)
    except (AttributeError, OSError):
        load_average_1m = None
    return {
        "scope": "runtime_environment",
        "scope_label": "Runtime environment visible to the application",
        "status": status,
        "cpu": {
            "usage_percent": cpu_percent,
            "logical_cores": int(psutil.cpu_count(logical=True) or 0),
            "load_average_1m": load_average_1m,
        },
        "memory": {
            "used_bytes": int(memory.used),
            "total_bytes": int(memory.total),
            "available_bytes": int(memory.available),
            "usage_percent": round(float(memory.percent), 1),
        },
        "disk": {
            "mount": "/",
            "used_bytes": int(disk.used),
            "total_bytes": int(disk.total),
            "free_bytes": int(disk.free),
            "usage_percent": round(float(disk.percent), 1),
        },
        "process": {
            "resident_memory_bytes": int(process_memory.rss),
        },
        "thresholds": {"warning_percent": 80, "critical_percent": 90},
    }


async def build_system_health_snapshot(
    database: Any,
    config: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    settings = os.environ if environ is None else environ
    services = [_service("application", "NexoraAI application", "healthy", "System Health API is responding")]
    try:
        resources = _resource_snapshot()
    except Exception:
        resources = {
            "scope": "runtime_environment",
            "scope_label": "Runtime environment visible to the application",
            "status": "unavailable",
        }

    try:
        started = time.perf_counter()
        database.command("ping")
        services.append(
            _service(
                "mongodb",
                "Metadata database",
                "healthy",
                "Database ping succeeded",
                provider="MongoDB",
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
        )
        integrations = _integration_summary(database)
        jobs = _job_summary(database, config, settings)
    except Exception:
        services.append(_service("mongodb", "Metadata database", "unavailable", "Database ping failed", provider="MongoDB"))
        integrations = {"total": 0, "enabled": 0, "disabled": 0, "attention": 0, "by_kind": []}
        jobs = {
            "ingestion": {"queued": 0, "processing": 0, "failed": 0, "worker_status": "unknown"},
            "attachments": {"queued": 0, "processing": 0, "failed": 0, "worker_status": "unknown", "cleanup_status": "unknown"},
        }

    storage_provider = str(settings.get("KNOWLEDGE_STORAGE_PROVIDER", "azure")).strip().lower()
    if storage_provider == "minio":
        minio_url = _safe_http_url(str(settings.get("MINIO_ENDPOINT", "")), "/minio/health/live")
        storage_check = _http_service("knowledge_storage", "Knowledge storage", "MinIO", minio_url)
    else:
        storage_check = _static_service(
            _service("knowledge_storage", "Knowledge storage", "configured", "Azure storage client initialized", provider="Azure Storage")
        )

    search_provider = str(settings.get("KNOWLEDGE_SEARCH_PROVIDER", "azure")).strip().lower()
    if search_provider == "qdrant":
        qdrant_url = _safe_http_url(str(settings.get("QDRANT_URL", "")), "/readyz")
        search_check = _http_service("knowledge_search", "Vector search", "Qdrant", qdrant_url)
    else:
        search_check = _static_service(
            _service("knowledge_search", "Vector search", "configured", "Azure AI Search client initialized", provider="Azure AI Search")
        )

    llm_profiles = config.get("llm_profiles") or {}
    ollama_url = _ollama_health_url(settings)
    if ollama_url:
        async def model_check() -> dict[str, Any]:
            result = await _http_service("model_runtime", "Model runtime", "Ollama", ollama_url)
            result["detail"] = (
                f"Health endpoint responded · {len(llm_profiles)} model profile(s) loaded"
                if result["status"] == "healthy"
                else "Ollama health endpoint did not respond"
            )
            return result

        model_service_check = model_check()
    else:
        model_service_check = _static_service(
            _service(
                "model_runtime",
                "Model runtime",
                "configured" if llm_profiles else "unavailable",
                f"{len(llm_profiles)} model profile(s) loaded" if llm_profiles else "No model profiles loaded",
            )
        )

    controller_url = _safe_http_url(str(settings.get("INTEGRATION_CONTROLLER_URL", "")), "/health")
    controller_check = _http_service(
        "integration_controller",
        "Integration controller",
        "Managed containers",
        controller_url,
    )
    service_checks = [storage_check, search_check, model_service_check, controller_check]
    gateway_url = _safe_http_url(str(settings.get("NEXORA_TLS_GATEWAY_HEALTH_URL", "")), "/gateway-healthz")
    if gateway_url:
        service_checks.append(
            _http_service(
                "tls_gateway",
                "HTTPS gateway",
                "Nginx",
                gateway_url,
            )
        )
    services.extend(await asyncio.gather(*service_checks))

    required_failures = [item for item in services if item["status"] == "unavailable"]
    resource_attention = resources["status"] in {"warning", "critical", "unavailable"}
    status = "healthy" if not required_failures and not resource_attention else "degraded"
    return {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "services": services,
        "resources": resources,
        "integrations": integrations,
        "jobs": jobs,
    }
