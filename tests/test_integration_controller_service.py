import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_service(monkeypatch):
    class DockerException(Exception):
        pass

    class ImageNotFound(DockerException):
        pass

    class NotFound(DockerException):
        pass

    docker_module = ModuleType("docker")
    docker_module.from_env = lambda: None
    errors_module = ModuleType("docker.errors")
    errors_module.DockerException = DockerException
    errors_module.ImageNotFound = ImageNotFound
    errors_module.NotFound = NotFound
    monkeypatch.setitem(sys.modules, "docker", docker_module)
    monkeypatch.setitem(sys.modules, "docker.errors", errors_module)

    path = (
        Path(__file__).parents[1]
        / "services"
        / "integration-controller"
        / "server.py"
    )
    spec = importlib.util.spec_from_file_location("integration_controller_service", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, NotFound


def test_managed_local_container_disables_only_incoming_http_auth(monkeypatch):
    service, not_found = _load_service(monkeypatch)
    run_calls = []

    class Images:
        def get(self, _image):
            return object()

    class Containers:
        def get(self, _name):
            raise not_found()

        def run(self, image, **kwargs):
            run_calls.append((image, kwargs))

    client = SimpleNamespace(images=Images(), containers=Containers())
    monkeypatch.setattr(service.docker, "from_env", lambda: client)
    monkeypatch.setattr(service, "_wait_until_listening", lambda _host: None)
    monkeypatch.setenv("INTEGRATION_CONTROLLER_TOKEN", "controller-token")
    monkeypatch.setenv(
        "AZURE_MCP_IMAGE", "mcr.microsoft.com/azure-sdk/azure-mcp@sha256:digest"
    )
    monkeypatch.setenv("AZURE_MCP_DOCKER_NETWORK", "nexoraai_runtime")

    connection_id = "11111111-1111-4111-8111-111111111111"
    result = service._provision(
        {
            "connection_id": connection_id,
            # Azure GUIDs do not guarantee RFC 4122 version/variant bits.
            "azure_tenant_id": "222222222222e2220222222222222222",
            "azure_client_id": "33333333-3333-f333-7333-333333333333",
            "azure_client_secret": "workload-secret",
            "azure_subscription_ids": [
                "4444444444440444f444444444444444"
            ],
        },
        connection_id,
    )

    assert result["url"].startswith("http://nexora-azure-mcp-")
    _image, options = run_calls[0]
    assert "--dangerously-disable-http-incoming-auth" in options["command"]
    assert "--disable-proxy-tools" in options["command"]
    assert "subscription_list" in options["command"]
    assert "azmcp_subscription_list" not in options["command"]
    assert options["network"] == "nexoraai_runtime"
    assert "ports" not in options
    assert "AzureAd__ClientId" not in options["environment"]
    assert options["environment"]["ASPNETCORE_URLS"] == "http://0.0.0.0:8080"
    assert options["environment"]["ALLOW_INSECURE_EXTERNAL_BINDING"] == "true"
    assert (
        options["environment"]["AZURE_TENANT_ID"]
        == "22222222-2222-e222-0222-222222222222"
    )
    assert (
        options["environment"]["AZURE_SUBSCRIPTION_ID"]
        == "44444444-4444-0444-f444-444444444444"
    )
    assert options["environment"]["AZURE_CLIENT_SECRET"] == "workload-secret"
