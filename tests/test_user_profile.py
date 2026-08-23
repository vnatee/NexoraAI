import pytest

import app as app_module
from core.effective_access import AccessControlError


def test_self_profile_allows_only_normalized_editable_fields():
    result = app_module._normalize_self_profile(
        {
            "first_name": "  Jane ",
            "last_name": " Doe  ",
            "email": " jane@example.test ",
            "tel": " 1234 ",
            "is_sys_admin": True,
            "active": False,
            "employee_id": "changed",
        }
    )

    assert result == {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.test",
        "tel": "1234",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"first_name": "", "last_name": "Doe", "email": "jane@example.test"},
        {"first_name": "Jane", "last_name": "", "email": "jane@example.test"},
        {"first_name": "Jane", "last_name": "Doe", "email": "invalid"},
    ],
)
def test_self_profile_rejects_missing_names_and_invalid_email(payload):
    with pytest.raises(AccessControlError):
        app_module._normalize_self_profile(payload)


def test_user_auth_serialization_distinguishes_local_and_entra_accounts(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_local_identity_for_user",
        lambda _user_id: {"username": "local-admin"},
    )
    local = app_module._serialize_user_auth(
        {
            "_id": "local-1",
            "ad_email": "legacy-local-value",
            "created_by_auth_provider": "local",
        }
    )
    entra = app_module._serialize_user_auth({"_id": "entra-1", "ad_email": "jane@example.test"}, {})

    assert local["auth_providers"] == ["local"]
    assert local["local_username"] == "local-admin"
    assert entra["auth_providers"] == ["entra"]
