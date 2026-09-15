import pytest
from quart import Quart

from config import CONFIG_AUTH_CLIENT
from core.authentication import AuthError
from decorators import authenticated


class _RejectingAuthenticationHelper:
    def __init__(self, status_code: int):
        self.status_code = status_code

    async def get_auth_claims_if_enabled(self, _headers):
        raise AuthError("provider details must not be returned", self.status_code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_code", "expected_message"),
    [
        (401, "authentication_required", "Your session has expired or is invalid. Please sign in again."),
        (403, "access_denied", "You do not have permission to access this resource."),
    ],
)
async def test_authenticated_returns_safe_json_for_auth_errors(status_code, expected_code, expected_message):
    app = Quart(__name__)
    app.config[CONFIG_AUTH_CLIENT] = _RejectingAuthenticationHelper(status_code)

    @app.get("/protected")
    @authenticated
    async def protected(_auth_claims):
        return {"ok": True}

    response = await app.test_client().get("/protected")

    assert response.status_code == status_code
    assert response.content_type == "application/json"
    assert await response.get_json() == {"error": expected_message, "code": expected_code}
