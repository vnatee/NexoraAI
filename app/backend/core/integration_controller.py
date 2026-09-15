import os
from dataclasses import dataclass
from typing import Any

import httpx2


class IntegrationControllerError(RuntimeError):
    pass


@dataclass(frozen=True)
class AzureMCPProvisionRequest:
    connection_id: str
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    azure_subscription_ids: tuple[str, ...]


class IntegrationControllerClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("INTEGRATION_CONTROLLER_URL", "").strip().rstrip("/")
        self.token = os.getenv("INTEGRATION_CONTROLLER_TOKEN", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise IntegrationControllerError(
                "Managed Azure MCP provisioning is unavailable in this deployment"
            )
        return {"Authorization": f"Bearer {self.token}"}

    async def provision_azure_mcp(
        self, request: AzureMCPProvisionRequest
    ) -> dict[str, Any]:
        payload = {
            "connection_id": request.connection_id,
            "azure_tenant_id": request.azure_tenant_id,
            "azure_client_id": request.azure_client_id,
            "azure_client_secret": request.azure_client_secret,
            "azure_subscription_ids": list(request.azure_subscription_ids),
        }
        try:
            async with httpx2.AsyncClient(timeout=180, follow_redirects=False) as client:
                response = await client.put(
                    f"{self.base_url}/v1/azure-mcp/instances/{request.connection_id}",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx2.RequestError:
            raise IntegrationControllerError(
                "Managed Azure MCP controller is unreachable"
            ) from None
        return self._result(response, "provision")

    async def stop_azure_mcp(self, connection_id: str) -> dict[str, Any]:
        try:
            async with httpx2.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.post(
                    f"{self.base_url}/v1/azure-mcp/instances/{connection_id}/stop",
                    headers=self._headers(),
                )
        except httpx2.RequestError:
            raise IntegrationControllerError(
                "Managed Azure MCP controller is unreachable"
            ) from None
        return self._result(response, "stop")

    async def delete_azure_mcp(self, connection_id: str) -> dict[str, Any]:
        try:
            async with httpx2.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.delete(
                    f"{self.base_url}/v1/azure-mcp/instances/{connection_id}",
                    headers=self._headers(),
                )
        except httpx2.RequestError:
            raise IntegrationControllerError(
                "Managed Azure MCP controller is unreachable"
            ) from None
        return self._result(response, "delete")

    @staticmethod
    def _result(response: Any, action: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise IntegrationControllerError(
                str(message or f"Integration controller {action} failed ({response.status_code})")
            )
        if not isinstance(payload, dict):
            raise IntegrationControllerError(
                f"Integration controller {action} returned an invalid response"
            )
        return payload
