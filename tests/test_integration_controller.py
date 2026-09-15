from types import SimpleNamespace

import pytest

from core import integration_controller
from core.integration_controller import (
    AzureMCPProvisionRequest,
    IntegrationControllerClient,
    IntegrationControllerError,
)


def test_controller_requires_both_url_and_token(monkeypatch):
    monkeypatch.delenv("INTEGRATION_CONTROLLER_URL", raising=False)
    monkeypatch.delenv("INTEGRATION_CONTROLLER_TOKEN", raising=False)

    client = IntegrationControllerClient()

    assert client.configured is False
    with pytest.raises(IntegrationControllerError, match="unavailable"):
        client._headers()


@pytest.mark.asyncio
async def test_controller_provision_sends_fixed_connection_path(monkeypatch):
    monkeypatch.setenv("INTEGRATION_CONTROLLER_URL", "http://controller:8080/")
    monkeypatch.setenv("INTEGRATION_CONTROLLER_TOKEN", "controller-token")
    calls = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def put(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"status": "running", "url": "http://managed:8080"},
            )

    monkeypatch.setattr(
        integration_controller.httpx2,
        "AsyncClient",
        lambda **_kwargs: Client(),
    )

    result = await IntegrationControllerClient().provision_azure_mcp(
        AzureMCPProvisionRequest(
            connection_id="11111111-1111-4111-8111-111111111111",
            azure_tenant_id="22222222-2222-4222-8222-222222222222",
            azure_client_id="33333333-3333-4333-8333-333333333333",
            azure_client_secret="workload-secret",
            azure_subscription_ids=("44444444-4444-4444-8444-444444444444",),
        )
    )

    assert result["status"] == "running"
    assert calls[0][0].endswith(
        "/v1/azure-mcp/instances/11111111-1111-4111-8111-111111111111"
    )
    assert calls[0][1]["headers"] == {
        "Authorization": "Bearer controller-token"
    }
    assert calls[0][1]["json"]["azure_client_secret"] == "workload-secret"
    assert "server_app_client_id" not in calls[0][1]["json"]


@pytest.mark.asyncio
async def test_controller_client_hides_network_failure_details(monkeypatch):
    monkeypatch.setenv("INTEGRATION_CONTROLLER_URL", "http://controller:8080")
    monkeypatch.setenv("INTEGRATION_CONTROLLER_TOKEN", "controller-secret")

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            request = integration_controller.httpx2.Request(
                "POST", "http://controller:8080"
            )
            raise integration_controller.httpx2.ConnectError(
                "socket detail", request=request
            )

    monkeypatch.setattr(
        integration_controller.httpx2,
        "AsyncClient",
        lambda **_kwargs: FailingClient(),
    )

    with pytest.raises(
        IntegrationControllerError, match="controller is unreachable"
    ) as caught:
        await IntegrationControllerClient().stop_azure_mcp("connection-1")

    assert "socket detail" not in str(caught.value)
