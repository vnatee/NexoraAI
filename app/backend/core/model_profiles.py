import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.runtime_settings import (
    LLMProviderSettings,
    ModelProvider,
    parse_model_provider,
)

DEFAULT_LLM_PROFILE_ID = "system"


@dataclass(frozen=True)
class LLMProfile:
    profile_id: str
    label: str
    settings: LLMProviderSettings
    managed_provider_id: str | None = None
    managed_model_id: str | None = None
    supports_tools: bool = True
    supports_vision: bool = False

    def public_dict(self) -> dict[str, Any]:
        result = {
            "id": self.profile_id,
            "label": self.label,
            "provider": self.settings.provider.value,
            "model": self.settings.model,
            "supportsTools": self.supports_tools,
            "supportsVision": self.supports_vision,
        }
        if self.managed_provider_id:
            result["managedProviderId"] = self.managed_provider_id
            result["managedModelId"] = self.managed_model_id or ""
        return result


def managed_profile_id(provider_id: str, model_id: str) -> str:
    return f"managed:{provider_id}:{model_id}"


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def load_llm_profiles(
    env: Mapping[str, str], default_settings: LLMProviderSettings
) -> dict[str, LLMProfile]:
    """Load selectable LLM profiles without exposing their credentials to agents or the UI."""
    profiles = {
        DEFAULT_LLM_PROFILE_ID: LLMProfile(
            profile_id=DEFAULT_LLM_PROFILE_ID,
            label="System default",
            settings=default_settings,
            supports_vision=env.get("USE_GPT4V", "").lower() == "true",
        )
    }
    raw_profiles = env.get("LLM_PROFILES_JSON", "").strip()
    if not raw_profiles:
        return profiles

    try:
        profile_items = json.loads(raw_profiles)
    except json.JSONDecodeError as error:
        raise ValueError("LLM_PROFILES_JSON must contain valid JSON") from error
    if not isinstance(profile_items, list):
        raise ValueError("LLM_PROFILES_JSON must be a JSON array")

    for item in profile_items:
        if not isinstance(item, dict):
            raise ValueError("Each LLM profile must be a JSON object")
        profile_id = _optional_string(item.get("id"))
        label = _optional_string(item.get("label"))
        model = _optional_string(item.get("model"))
        provider_value = _optional_string(item.get("provider"))
        if not profile_id or not label or not model or not provider_value:
            raise ValueError("Each LLM profile requires id, label, provider, and model")
        if profile_id == DEFAULT_LLM_PROFILE_ID or profile_id in profiles:
            raise ValueError(f"Duplicate or reserved LLM profile id '{profile_id}'")
        if not profile_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Invalid LLM profile id '{profile_id}'")

        provider = parse_model_provider(provider_value)
        api_key_env = _optional_string(item.get("api_key_env"))
        api_key = env.get(api_key_env) if api_key_env else None
        settings = LLMProviderSettings(
            provider=provider,
            model=model,
            deployment=_optional_string(item.get("deployment")),
            api_version=_optional_string(item.get("api_version")) or default_settings.api_version,
            endpoint=_optional_string(item.get("endpoint")),
            base_url=_optional_string(item.get("base_url")),
            api_key=_optional_string(api_key),
            organization=_optional_string(item.get("organization")),
        )
        if provider == ModelProvider.AZURE_OPENAI and not settings.endpoint:
            raise ValueError(f"Azure LLM profile '{profile_id}' requires endpoint")
        if provider == ModelProvider.OPENAI and not settings.api_key:
            raise ValueError(f"OpenAI LLM profile '{profile_id}' requires api_key_env")
        if provider == ModelProvider.OPENAI_COMPATIBLE and not settings.base_url:
            raise ValueError(f"OpenAI-compatible LLM profile '{profile_id}' requires base_url")

        profiles[profile_id] = LLMProfile(
            profile_id=profile_id,
            label=label,
            settings=settings,
            supports_tools=item.get("supports_tools", True) is not False,
            supports_vision=item.get("supports_vision", False) is True,
        )

    return profiles
