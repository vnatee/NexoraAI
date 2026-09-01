from load_azd_env import should_load_azd_env


def test_local_runtime_uses_injected_environment_without_azd():
    assert should_load_azd_env({"APP_RUNTIME_MODE": "local"}) is False
    assert should_load_azd_env({"APP_RUNTIME_MODE": " LOCAL "}) is False


def test_azure_compatible_local_development_keeps_azd_loading():
    assert should_load_azd_env({}) is True
    assert should_load_azd_env({"APP_RUNTIME_MODE": "azure"}) is True
