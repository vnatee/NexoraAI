import pytest

import app as backend_app


def _status():
    return {
        "status": "unlicensed",
        "reason": "license_not_installed",
        "source": "none",
        "installation_id": "installation-001",
        "audit_mode": True,
        "trial_available": True,
    }


@pytest.mark.asyncio
async def test_license_routes_require_system_admin_and_never_echo_key(client, monkeypatch):
    authorization_calls = []
    imported = []
    monkeypatch.setattr(
        backend_app,
        "_require_system_admin",
        lambda claims: authorization_calls.append(claims) or {"_id": "admin-1"},
    )
    monkeypatch.setattr(backend_app, "_license_verification_keys", lambda: {"key": object()})
    monkeypatch.setattr(backend_app, "get_license_status", lambda _keys: _status())
    monkeypatch.setattr(backend_app, "start_trial", lambda **_kwargs: {**_status(), "source": "trial"})

    def import_key(value, _keys, **_kwargs):
        imported.append(value)
        return {**_status(), "status": "active", "source": "license", "trial_available": False}

    monkeypatch.setattr(backend_app, "import_license", import_key)

    get_response = await client.get("/admin/license")
    trial_response = await client.post("/admin/license/trial")
    import_response = await client.put("/admin/license", json={"license_key": "NX1.private.value"})

    assert get_response.status_code == 200
    assert trial_response.status_code == 201
    assert import_response.status_code == 200
    assert imported == ["NX1.private.value"]
    assert "NX1.private.value" not in str(await import_response.get_json())
    assert len(authorization_calls) == 3


@pytest.mark.asyncio
async def test_license_import_requires_configured_trusted_key(client, monkeypatch):
    monkeypatch.setattr(backend_app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(backend_app, "_license_verification_keys", lambda: {})

    response = await client.put("/admin/license", json={"license_key": "NX1.payload.signature"})

    assert response.status_code == 503
    assert (await response.get_json())["error"] == "No trusted license signing keys are configured"
