import asyncio
import hmac
import json
import os
import re
import socket
import time
import uuid
from typing import Any

import docker
from aiohttp import web
from docker.errors import DockerException, ImageNotFound, NotFound

LABEL_KEY = "com.nexora.integration"
LABEL_VALUE = "managed-azure-mcp"
CONNECTION_LABEL = "com.nexora.connection-id"
CONFIG_LABEL = "com.nexora.config-hmac"
MANAGED_CONTAINER_CONFIG_VERSION = "3"
CONNECTION_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _authorized(request: web.Request) -> bool:
    configured = _required_setting("INTEGRATION_CONTROLLER_TOKEN")
    supplied = request.headers.get("Authorization", "")
    return hmac.compare_digest(supplied, f"Bearer {configured}")


def _connection_id(raw: str) -> str:
    value = str(raw or "").strip()
    if not CONNECTION_UUID_PATTERN.fullmatch(value):
        raise web.HTTPBadRequest(text="Invalid connection ID")
    return str(uuid.UUID(value))


def _required_uuid(payload: dict[str, Any], name: str) -> str:
    value = str(payload.get(name) or "").strip()
    # Azure directory, application, and subscription IDs are GUID-shaped
    # identifiers, but Azure does not guarantee RFC 4122 version/variant bits
    # and accepts both compact and hyphenated representations.
    try:
        normalized = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError):
        raise web.HTTPBadRequest(text=f"{name} must be an Azure GUID")
    return normalized


def _container_name(connection_id: str) -> str:
    return f"nexora-azure-mcp-{connection_id}"


def _config_hmac(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        _required_setting("INTEGRATION_CONTROLLER_TOKEN").encode("utf-8"),
        canonical.encode("utf-8"),
        "sha256",
    ).hexdigest()


def _managed_container(client: Any, connection_id: str) -> Any | None:
    try:
        container = client.containers.get(_container_name(connection_id))
    except NotFound:
        return None
    labels = container.attrs.get("Config", {}).get("Labels", {}) or {}
    if (
        labels.get(LABEL_KEY) != LABEL_VALUE
        or labels.get(CONNECTION_LABEL) != connection_id
    ):
        raise web.HTTPConflict(text="Container name is not owned by NexoraAI")
    return container


def _ensure_image(client: Any, image: str) -> None:
    try:
        client.images.get(image)
    except ImageNotFound:
        client.images.pull(image)


def _wait_until_listening(host: str) -> None:
    deadline = time.monotonic() + float(
        os.getenv("AZURE_MCP_STARTUP_TIMEOUT_SECONDS", "60")
    )
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, 8080), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError("Azure MCP container did not become ready before timeout")


def _provision(payload: dict[str, Any], connection_id: str) -> dict[str, str]:
    tenant_id = _required_uuid(payload, "azure_tenant_id")
    client_id = _required_uuid(payload, "azure_client_id")
    client_secret = str(payload.get("azure_client_secret") or "").strip()
    if not client_secret:
        raise web.HTTPBadRequest(text="azure_client_secret is required")
    subscriptions = payload.get("azure_subscription_ids")
    if not isinstance(subscriptions, list) or not subscriptions:
        raise web.HTTPBadRequest(text="azure_subscription_ids is required")
    subscription_ids = [_required_uuid({"value": item}, "value") for item in subscriptions[:100]]

    image = _required_setting("AZURE_MCP_IMAGE")
    if "@sha256:" not in image and os.getenv(
        "ALLOW_UNPINNED_AZURE_MCP_IMAGE", ""
    ).strip().lower() != "true":
        raise web.HTTPServiceUnavailable(
            text="AZURE_MCP_IMAGE must be pinned by sha256 digest"
        )
    network = _required_setting("AZURE_MCP_DOCKER_NETWORK")
    client = docker.from_env()
    _ensure_image(client, image)
    existing = _managed_container(client, connection_id)
    config_hmac = _config_hmac(
        {
            "managed_container_config_version": MANAGED_CONTAINER_CONFIG_VERSION,
            "azure_tenant_id": tenant_id,
            "azure_client_id": client_id,
            "azure_client_secret": client_secret,
            "azure_subscription_ids": subscription_ids,
            "image": image,
        }
    )
    if existing is not None:
        labels = existing.attrs.get("Config", {}).get("Labels", {}) or {}
        if labels.get(CONFIG_LABEL) == config_hmac:
            existing.reload()
            if existing.status != "running":
                existing.start()
            _wait_until_listening(existing.name)
            return {"status": "running", "url": f"http://{existing.name}:8080"}
        existing.remove(force=True)

    name = _container_name(connection_id)
    environment = {
        "ASPNETCORE_ENVIRONMENT": "Production",
        "ASPNETCORE_URLS": "http://0.0.0.0:8080",
        # Azure MCP deliberately requires this opt-in for a wildcard bind when
        # incoming HTTP auth is disabled. The child has no published host port
        # and remains reachable only on the private runtime network.
        "ALLOW_INSECURE_EXTERNAL_BINDING": "true",
        "AZURE_TENANT_ID": tenant_id,
        "AZURE_CLIENT_ID": client_id,
        "AZURE_CLIENT_SECRET": client_secret,
        "AZURE_SUBSCRIPTION_ID": subscription_ids[0],
        "AZURE_TOKEN_CREDENTIALS": "EnvironmentCredential",
        "AZURE_MCP_INCLUDE_PRODUCTION_CREDENTIALS": "true",
        "AZURE_MCP_COLLECT_TELEMETRY": os.getenv(
            "AZURE_MCP_COLLECT_TELEMETRY", "false"
        ),
        # The MCP endpoint is reachable only on the private Compose network.
        "AZURE_MCP_DANGEROUSLY_DISABLE_HTTPS_REDIRECTION": "true",
    }
    args = [
        "--transport",
        "http",
        "--dangerously-disable-http-incoming-auth",
        "--outgoing-auth-strategy",
        "UseHostingEnvironmentIdentity",
        "--mode",
        "all",
        "--read-only",
        "--disable-proxy-tools",
        "--tool",
        "subscription_list",
        "--tool",
        "group_list",
        "--tool",
        "group_resource_list",
    ]
    client.containers.run(
        image,
        command=args,
        detach=True,
        name=name,
        hostname=name,
        network=network,
        environment=environment,
        labels={
            LABEL_KEY: LABEL_VALUE,
            CONNECTION_LABEL: connection_id,
            CONFIG_LABEL: config_hmac,
        },
        restart_policy={"Name": "unless-stopped"},
        mem_limit=os.getenv("AZURE_MCP_MEMORY_LIMIT", "512m"),
        nano_cpus=int(float(os.getenv("AZURE_MCP_CPU_LIMIT", "0.5")) * 1_000_000_000),
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
    )
    _wait_until_listening(name)
    return {"status": "running", "url": f"http://{name}:8080"}


def _stop(connection_id: str) -> dict[str, str]:
    client = docker.from_env()
    container = _managed_container(client, connection_id)
    if container is not None:
        container.stop(timeout=10)
    return {"status": "stopped"}


def _delete(connection_id: str) -> dict[str, str]:
    client = docker.from_env()
    container = _managed_container(client, connection_id)
    if container is not None:
        container.remove(force=True)
    return {"status": "deleted"}


def _remove_all_managed_containers() -> None:
    client = docker.from_env()
    for container in client.containers.list(
        all=True, filters={"label": f"{LABEL_KEY}={LABEL_VALUE}"}
    ):
        container.remove(force=True)


@web.middleware
async def authenticate(request: web.Request, handler):
    if request.path == "/health":
        return await handler(request)
    if not _authorized(request):
        raise web.HTTPUnauthorized(text="Unauthorized")
    return await handler(request)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def provision(request: web.Request) -> web.Response:
    connection_id = _connection_id(request.match_info["connection_id"])
    try:
        payload = await request.json()
        if not isinstance(payload, dict) or payload.get("connection_id") != connection_id:
            raise web.HTTPBadRequest(text="Connection ID does not match request path")
        result = await asyncio.to_thread(_provision, payload, connection_id)
        return web.json_response(result)
    except web.HTTPException:
        raise
    except (DockerException, ImageNotFound, RuntimeError, ValueError) as error:
        return web.json_response({"error": str(error)[:500]}, status=503)


async def stop(request: web.Request) -> web.Response:
    connection_id = _connection_id(request.match_info["connection_id"])
    try:
        return web.json_response(await asyncio.to_thread(_stop, connection_id))
    except (DockerException, RuntimeError) as error:
        return web.json_response({"error": str(error)[:500]}, status=503)


async def delete(request: web.Request) -> web.Response:
    connection_id = _connection_id(request.match_info["connection_id"])
    try:
        return web.json_response(await asyncio.to_thread(_delete, connection_id))
    except (DockerException, RuntimeError) as error:
        return web.json_response({"error": str(error)[:500]}, status=503)


async def cleanup(_application: web.Application) -> None:
    try:
        await asyncio.to_thread(_remove_all_managed_containers)
    except DockerException:
        # Docker may already be shutting down. No request data or secrets are logged.
        pass


application = web.Application(
    middlewares=[authenticate], client_max_size=64 * 1024
)
application.router.add_get("/health", health)
application.router.add_put("/v1/azure-mcp/instances/{connection_id}", provision)
application.router.add_post("/v1/azure-mcp/instances/{connection_id}/stop", stop)
application.router.add_delete("/v1/azure-mcp/instances/{connection_id}", delete)
application.on_cleanup.append(cleanup)


if __name__ == "__main__":
    web.run_app(application, host="0.0.0.0", port=8080, access_log=None)
