
import dataclasses
import io
from io import BytesIO
import json
import logging
import math
import mimetypes
import os
import re
import time
import random
import uuid

import requests
# Scraping import
from bs4 import BeautifulSoup
from azure.storage.blob import BlobServiceClient
from urllib.parse import urljoin, urlparse
import asyncio
# End of Scraping import
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Dict, Union, cast
from datetime import datetime, timezone
from tokens_usage.save_tokens_usage import insert_user_usage
from tokens_usage.get_usage import get_all_usage
from feedback.createfeedback import insert_feedback
from feedback.getfeedback import get_all_feedback
from mongo_table_connecters.mongo_connector import get_database
from mongo_table_connecters.teams import insert_team, get_all_teams, get_team_by_id, update_team, get_team_by_user_id, delete_team_by_id
from mongo_table_connecters.users import get_user_by_id, get_user_by_ad_email, get_all_user_by_is_sys_admin, get_all_users, insert_user, delete_user_by_id, update_user
from mongo_table_connecters.agents import insert_agent, get_agent_by_id, update_agent, delete_agent_by_id
from mongo_table_connecters.llm_providers import (
    get_llm_provider,
    insert_llm_provider,
    list_llm_providers,
    soft_delete_llm_provider,
    update_llm_provider,
)
from mongo_table_connecters.mcp_servers import (
    decrypt_mcp_headers,
    get_mcp_server,
    insert_mcp_server,
    list_mcp_servers,
    normalize_mcp_server_payload,
    serialize_mcp_server,
    soft_delete_mcp_server,
    update_mcp_server,
)
from mongo_table_connecters.agent_audit import list_agent_audit_events
from mongo_table_connecters.data_group import get_data_group_by_id, insert_data_group, delete_data_group_by_id, get_all_data_groups_by_user_id, update_data_group
from mongo_table_connecters.permissions import insert_permission, get_all_permissions, get_permission_by_name
from mongo_table_connecters.user_permission import get_user_permission_by_user_id, get_user_permission_by_team_id, delete_user_permission_by_id, get_user_permission_by_user_team_id, insert_user_permission, update_user_permission
from mongo_table_connecters.roles import insert_role, update_role, get_all_roles, get_role_by_id, get_all_roles_by_team, delete_role_by_id
from mongo_table_connecters.limit_size_config import insert_limit_size_config, get_all_limit_size_configs
from mongo_table_connecters.external_apis import insert_apis, delete_apis_by_id, update_apis, get_all_apis_by_team_id, get_apis_by_id, get_apis_by_team_id_and_name
from mongo_table_connecters.agent_bindings import insert_agent_binding, get_all_agent_bindings_by_agent_id, delete_agent_binding_by_id, update_agent_binding,get_agent_binding_by_apisid_and_endpointname
from mongo_table_connecters.fixed_promts import insert_fixed_prompt, get_all_fixed_prompt
from mongo_table_connecters.external_database import insert_external_database, get_external_database_by_id, get_external_databases_by_team_id, get_all_external_databases, update_external_database, delete_external_database_by_id, serialize_external_database
from mongo_table_connecters.database_binding import insert_database_binding, get_database_binding_by_id, get_database_bindings_by_agent_id, get_all_database_bindings, update_database_binding, delete_database_binding_by_id
# ⭐ CHART CAPABILITY: import chart binding functions
from mongo_table_connecters.chart_binding import insert_chart_binding, get_chart_bindings_by_agent_id, get_enabled_chart_bindings_by_agent_id, update_chart_binding, delete_chart_binding_by_id
from db_retrieval import get_agent_mongodb_sources
from database_connectors import normalize_database_config, test_database_connection
from smtp.send_mail import send_approve_mail, approved_mail, rejected_mail
from mongo_table_connecters.mail_template import insert_mail_template, get_all_mail_template
from mongo_table_connecters.mail_connections import (
    decrypt_mail_secrets,
    get_mail_connection,
    insert_mail_connection,
    list_mail_connections,
    normalize_mail_connection,
    serialize_mail_connection,
    soft_delete_mail_connection,
    update_mail_connection,
)
from mongo_table_connecters.mail_bindings import (
    collection as mail_bindings_collection,
    delete_mail_binding,
    get_mail_binding,
    insert_mail_binding,
    list_mail_bindings,
    normalize_mail_binding,
    update_mail_binding,
)
from email_connectors import test_mail_connection
from messaging_connectors import test_messaging_connection
from mongo_table_connecters.messaging_connections import (
    decrypt_messaging_secrets, delete_messaging_connection, get_messaging_connection,
    insert_messaging_connection, list_messaging_connections, normalize_messaging_connection,
    serialize_messaging_connection, update_messaging_connection,
)
from mongo_table_connecters.messaging_bindings import (
    collection as messaging_bindings_collection, delete_messaging_binding,
    get_messaging_binding, insert_messaging_binding, list_messaging_bindings,
    normalize_messaging_binding, update_messaging_binding,
)
from mongo_table_connecters.document_processing import (
    delete_profile as delete_document_profile,
    delete_provider as delete_document_provider,
    delete_routing_rule as delete_document_routing_rule,
    ensure_system_providers,
    get_routing_rule as get_document_routing_rule,
    get_provider as get_document_provider,
    list_profiles as list_document_profiles,
    list_providers as list_document_providers,
    list_routing_rules as list_document_routing_rules,
    normalize_profile as normalize_document_profile,
    normalize_provider as normalize_document_provider,
    normalize_routing_rule as normalize_document_routing_rule,
    resolve_processing_route,
    save_profile as save_document_profile,
    save_provider as save_document_provider,
    save_routing_rule as save_document_routing_rule,
    serialize_provider as serialize_document_provider,
)
from mongo_table_connecters.ingestion_jobs import (
    claim_ingestion_job,
    create_ingestion_job,
    get_ingestion_job,
    latest_indexed_times,
    list_ingestion_jobs,
    list_recoverable_ingestion_jobs,
    restart_failed_ingestion_job,
    serialize_ingestion_job,
    update_ingestion_job_status,
)
from mongo_table_connecters.chat_attachment_metadata import (
    create_attachment_metadata,
    delete_expired_attachment_metadata,
    ensure_attachment_metadata_indexes,
    get_attachment_metadata,
    get_attachment_metadata_by_upload_id,
    list_attachment_metadata,
    serialize_attachment_metadata,
    soft_delete_attachment_metadata,
    update_attachment_status,
)
from mongo_table_connecters.chat_attachment_index import (
    MongoAttachmentIndex,
    ensure_attachment_index_indexes,
)
from pymongo.errors import DuplicateKeyError

from azure.cognitiveservices.speech import (
    ResultReason,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesisResult,
    SpeechSynthesizer,
)
from azure.core.exceptions import ResourceNotFoundError, ServiceResponseError, ResourceExistsError
from azure.identity.aio import (
    AzureDeveloperCliCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
)
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.storage.blob.aio import ContainerClient, BlobClient
from azure.storage.blob.aio import StorageStreamDownloader as BlobDownloader
from azure.storage.filedatalake.aio import FileSystemClient
from azure.storage.filedatalake.aio import StorageStreamDownloader as DatalakeDownloader
from openai import AsyncOpenAI
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from quart import (
    Blueprint,
    Quart,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
    send_from_directory,
    stream_with_context,
)
from quart_cors import cors

from approaches.approach import Approach
from approaches.chatreadretrieveread import ChatReadRetrieveReadApproach
from approaches.chatreadretrievereadvision import ChatReadRetrieveReadVisionApproach
from approaches.promptmanager import PromptyManager
from approaches.retrievethenread import RetrieveThenReadApproach
from approaches.retrievethenreadvision import RetrieveThenReadVisionApproach
from agent_runtime.factory import create_agent_runtime
from agent_runtime.charting import ChartValidationError, validate_echarts_spec
from agent_runtime.adapters.mcp import MCPServerConfig, discover_mcp_tools
from core.chat_attachments import ChatAttachmentError, validate_chat_attachments
from core.attachment_cleanup import cleanup_expired_attachments
from core.attachment_extraction import AttachmentExtractionError, extract_attachment_chunks
from core.attachment_index import AttachmentIndex
from core.attachment_retrieval import (
    ATTACHMENT_EVIDENCE_KNOWLEDGE_ONLY,
    ATTACHMENT_EVIDENCE_UPLOADED_ONLY,
    AttachmentRetrievalError,
    classify_attachment_evidence_scope,
    format_attachment_sources,
    normalize_attachment_ids,
)
from core.attachment_store import (
    AttachmentAccessError,
    AttachmentIntegrityError,
    AttachmentNotFoundError,
    AttachmentStore,
    create_attachment_store,
)
from core.document_attachments import (
    DisabledMalwareScanner,
    DocumentAttachmentError,
    MalwareDetectedError,
    MalwareScanner,
    MAX_DOCUMENT_BYTES,
    validate_document_attachment,
)
from chat_history.cosmosdb import chat_history_cosmosdb_bp
from config import (
    CONFIG_AGENT_CLIENT,
    CONFIG_AGENTIC_RETRIEVAL_ENABLED,
    CONFIG_ASK_APPROACH,
    CONFIG_ASK_VISION_APPROACH,
    CONFIG_AUTH_CLIENT,
    CONFIG_BLOB_CONTAINER_CLIENT,
    CONFIG_WEB_BLOB_CONTAINER_CLIENT,
    CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT,
    CONFIG_GROUP_BLOB_CONTAINER_CLIENT,
    CONFIG_CHAT_APPROACH,
    CONFIG_CHAT_ATTACHMENT_CLEANUP_TASK,
    CONFIG_CHAT_ATTACHMENT_CONTAINER_CLIENT,
    CONFIG_CHAT_ATTACHMENT_INDEX,
    CONFIG_CHAT_ATTACHMENT_SCANNER,
    CONFIG_CHAT_ATTACHMENT_STORE,
    CONFIG_CHAT_HISTORY_BROWSER_ENABLED,
    CONFIG_CHAT_HISTORY_COSMOS_ENABLED,
    CONFIG_CHAT_VISION_APPROACH,
    CONFIG_CREDENTIAL,
    CONFIG_DEFAULT_REASONING_EFFORT,
    CONFIG_GPT4V_DEPLOYED,
    CONFIG_KNOWLEDGE_VISION_ENABLED,
    CONFIG_INGESTER,
    CONFIG_LANGUAGE_PICKER_ENABLED,
    CONFIG_OPENAI_CLIENT,
    CONFIG_QUERY_REWRITING_ENABLED,
    CONFIG_REASONING_EFFORT_ENABLED,
    CONFIG_LLM_PROFILES,
    CONFIG_LLM_PROFILE_CLIENTS,
    CONFIG_RUNTIME_SETTINGS,
    CONFIG_SEARCH_CLIENT,
    CONFIG_SEARCH_INDEX_CLIENT,
    CONFIG_SEMANTIC_RANKER_DEPLOYED,
    CONFIG_SPEECH_INPUT_ENABLED,
    CONFIG_SPEECH_OUTPUT_AZURE_ENABLED,
    CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED,
    CONFIG_SPEECH_SERVICE_ID,
    CONFIG_SPEECH_SERVICE_LOCATION,
    CONFIG_SPEECH_SERVICE_TOKEN,
    CONFIG_SPEECH_SERVICE_VOICE,
    CONFIG_STREAMING_ENABLED,
    CONFIG_USER_BLOB_CONTAINER_CLIENT,
    CONFIG_USER_UPLOAD_ENABLED,
    CONFIG_VECTOR_SEARCH_ENABLED,
    CONFIG_MAIL_COMPONENT,
    CONFIG_EXTERNAL_API_ENPOINT
)
from core.authentication import AuthenticationHelper
from core.model_providers import create_embedding_service, create_llm_client
from core.llm_vendors import apply_llm_vendor_chat_policy, get_llm_vendor, infer_llm_vendor
from core.model_profiles import (
    DEFAULT_LLM_PROFILE_ID,
    LLMProfile,
    load_llm_profiles,
    managed_profile_id,
)
from core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret
from core.runtime_settings import LLMProviderSettings, ModelProvider, RuntimeSettings, parse_model_provider
from agent_runtime.policy import normalize_tool_policy
from core.sessionhelper import create_session_id, ensure_conversation_id
from decorators import authenticated, authenticated_path
from error import error_dict, error_response
from prepdocs import (
    setup_file_processors,
    setup_search_info,
)
from prepdocslib.filestrategy import UploadUserFileStrategy
from prepdocslib.listfilestrategy import File
from prepdocslib.docinteldb import insert_docintel_usage, get_all_docintel_usage
from addons.scraping_web import run_scraping_job


def _require_fields(data: Dict[str, Any], required: list[str]):
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _has_configured_knowledge_vision(use_gpt4v: bool, vision_endpoint: str) -> bool:
    if not use_gpt4v:
        return False
    parsed = urlparse(str(vision_endpoint or "").strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _validate_agent_model_config(config: object) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("Agent config must be an object")
    profile_id = config.get("llm_profile_id") or DEFAULT_LLM_PROFILE_ID
    profiles: dict[str, LLMProfile] = current_app.config[CONFIG_LLM_PROFILES]
    if profile_id not in profiles:
        raise ValueError(f"Unknown LLM profile '{profile_id}'")
    runtime = str(config.get("runtime") or "legacy").strip().lower()
    if runtime not in ("legacy", "langgraph"):
        raise ValueError("Agent runtime must be 'legacy' or 'langgraph'")
    if runtime == "langgraph" and not profiles[profile_id].supports_tools:
        raise ValueError("LangGraph runtime requires a model with Supports tool / function calling enabled")
    for policy_field in ("image_input_enabled", "document_attachments_enabled"):
        if policy_field in config and not isinstance(config[policy_field], bool):
            raise ValueError(f"Agent {policy_field} must be a boolean")
    image_input_enabled = config.get("image_input_enabled") is True
    if image_input_enabled and not profiles[profile_id].supports_vision:
        raise ValueError("Image input requires an LLM profile with Supports image / vision input enabled")
    if image_input_enabled and runtime == "langgraph":
        raise ValueError("Image input is not yet supported by the LangGraph runtime")
    raw_tool_settings = config.get("tool_settings") or {}
    if not isinstance(raw_tool_settings, dict):
        raise ValueError("Agent tool_settings must be an object")
    knowledge_search = str(raw_tool_settings.get("knowledge_search") or "auto").strip().lower()
    if knowledge_search not in ("auto", "always", "disabled"):
        raise ValueError("Knowledge Search must be 'auto', 'always', or 'disabled'")
    mcp_execution = str(raw_tool_settings.get("mcp_execution") or "auto").strip().lower()
    if mcp_execution not in ("auto", "required"):
        raise ValueError("MCP execution must be 'auto' or 'required'")
    raw_mcp_allowlists = raw_tool_settings.get("mcp_tool_allowlists") or {}
    if not isinstance(raw_mcp_allowlists, dict):
        raise ValueError("MCP tool allowlists must be an object keyed by server ID")
    mcp_tool_allowlists = {
        str(server_id): _normalize_id_list(tool_names, f"mcp_tool_allowlists.{server_id}")
        for server_id, tool_names in raw_mcp_allowlists.items()
        if str(server_id).strip()
    }
    tool_settings = {
        "knowledge_search": knowledge_search,
        "external_database": raw_tool_settings.get("external_database", True) is not False,
        "rest_integrations": raw_tool_settings.get("rest_integrations", True) is not False,
        "mail": raw_tool_settings.get("mail", True) is not False,
        "messaging": raw_tool_settings.get("messaging", True) is not False,
        "mcp": raw_tool_settings.get("mcp", True) is not False,
        "mcp_execution": mcp_execution,
        "subagents": raw_tool_settings.get("subagents", False) is True,
        "mcp_server_ids": _normalize_id_list(
            raw_tool_settings.get("mcp_server_ids"), "mcp_server_ids"
        ),
        "mcp_tool_allowlists": mcp_tool_allowlists,
        "mcp_timeout_seconds": max(
            1, min(int(raw_tool_settings.get("mcp_timeout_seconds") or 60), 300)
        ),
        "subagent_ids": _normalize_id_list(
            raw_tool_settings.get("subagent_ids"), "subagent_ids"
        ),
        "subagent_max_depth": max(
            1, min(int(raw_tool_settings.get("subagent_max_depth") or 2), 5)
        ),
        "tool_policy": normalize_tool_policy(raw_tool_settings.get("tool_policy")),
    }
    return {
        **config,
        "llm_profile_id": profile_id,
        "runtime": runtime,
        "image_input_enabled": image_input_enabled,
        "document_attachments_enabled": config.get("document_attachments_enabled", True) is not False,
        "tool_settings": tool_settings,
    }


def _normalize_id_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    result = []
    for item in value[:100]:
        normalized = str(item or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _apply_agent_llm_profile(context: dict[str, Any], agent_id: str | None) -> None:
    profile_id = DEFAULT_LLM_PROFILE_ID
    agent_config: dict[str, Any] = {}
    agent_found = not agent_id
    if agent_id:
        agent = get_agent_by_id(agent_id)
        if agent:
            agent_found = True
            agent_config = agent.get("config") or {}
            profile_id = agent_config.get("llm_profile_id") or DEFAULT_LLM_PROFILE_ID

    profiles: dict[str, LLMProfile] = current_app.config[CONFIG_LLM_PROFILES]
    clients: dict[str, AsyncOpenAI] = current_app.config[CONFIG_LLM_PROFILE_CLIENTS]
    profile = profiles.get(profile_id)
    if profile is None:
        current_app.logger.warning(
            "Agent %s references unavailable LLM profile %s; using system default",
            agent_id,
            profile_id,
        )
        profile = profiles[DEFAULT_LLM_PROFILE_ID]
        profile_id = DEFAULT_LLM_PROFILE_ID

    overrides = context.setdefault("overrides", {})
    overrides["_llm_client"] = clients[profile_id]
    overrides["_llm_model"] = profile.settings.model
    overrides["_llm_deployment"] = profile.settings.deployment
    overrides["_llm_profile_id"] = profile_id
    overrides["_llm_supports_tools"] = profile.supports_tools
    overrides["_llm_supports_vision"] = profile.supports_vision
    overrides["_rag_vision_enabled"] = current_app.config.get(CONFIG_KNOWLEDGE_VISION_ENABLED, False)
    if agent_id:
        image_input_enabled = agent_found and agent_config.get("image_input_enabled") is True
        # Agent configuration grants permission; the validated attachments on
        # this request decide whether the Vision approach is actually selected.
        overrides["use_gpt4v"] = False
    else:
        image_input_enabled = bool(overrides.get("use_gpt4v", False))
    overrides["_agent_image_input_enabled"] = image_input_enabled
    overrides["_agent_document_attachments_enabled"] = (
        agent_found and agent_config.get("document_attachments_enabled", True) is not False
    )
    overrides["_llm_vendor"] = infer_llm_vendor(
        {
            "provider": profile.settings.provider.value,
            "name": profile.label,
            "base_url": profile.settings.base_url,
            "endpoint": profile.settings.endpoint,
        }
    ).id
    # Kept inside the request-local overrides so delegated sub-agents can select
    # their own configured model without touching Quart globals during stream execution.
    overrides["_llm_profiles"] = profiles
    overrides["_llm_clients"] = clients
    overrides["_llm_profile_vendors"] = {
        item_id: infer_llm_vendor(
            {
                "provider": item.settings.provider.value,
                "name": item.label,
                "base_url": item.settings.base_url,
                "endpoint": item.settings.endpoint,
            }
        ).id
        for item_id, item in profiles.items()
    }


def _require_system_admin(auth_claims: dict[str, Any]) -> dict[str, Any]:
    username = (
        auth_claims.get("preferred_username")
        or auth_claims.get("email")
        or auth_claims.get("upn")
    )
    user = get_user_by_ad_email(username) if username else None
    if not user or not user.get("active", True) or not user.get("is_sys_admin"):
        abort(403)
    return user


def _is_system_admin(auth_claims: dict[str, Any]) -> bool:
    username = (
        auth_claims.get("preferred_username")
        or auth_claims.get("email")
        or auth_claims.get("upn")
    )
    user = get_user_by_ad_email(username) if username else None
    return bool(user and user.get("active", True) and user.get("is_sys_admin"))


def _normalize_provider_models(
    models: object, existing_models: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    if not isinstance(models, list) or not models:
        raise ValueError("At least one model is required")
    normalized = []
    seen_ids = set()
    existing_by_id = {
        str(item.get("id")): item for item in (existing_models or []) if item.get("id")
    }
    for item in models:
        if not isinstance(item, dict):
            raise ValueError("Each model must be an object")
        model = str(item.get("model") or "").strip()
        model_id = str(item.get("id") or model).strip()
        label = str(item.get("label") or model).strip()
        deployment = str(item.get("deployment") or "").strip() or None
        if not model or not model_id:
            raise ValueError("Each model requires model and id")
        if ":" in model_id:
            raise ValueError("Model id cannot contain ':'")
        if model_id in seen_ids:
            raise ValueError(f"Duplicate model id '{model_id}'")
        seen_ids.add(model_id)
        previous = existing_by_id.get(model_id)
        same_target = bool(
            previous
            and previous.get("model") == model
            and (previous.get("deployment") or None) == deployment
        )
        capability_status = (
            str(previous.get("tool_capability_status") or "unknown")
            if same_target and previous
            else "unknown"
        )
        supports_tools = bool(item.get("supports_tools", True))
        if capability_status == "unsupported":
            supports_tools = False
        vision_capability_status = (
            str(previous.get("vision_capability_status") or "unknown")
            if same_target and previous
            else "unknown"
        )
        supports_vision = bool(item.get("supports_vision", False))
        if vision_capability_status == "unsupported":
            supports_vision = False
        normalized_model = {
            "id": model_id,
            "label": label,
            "model": model,
            "deployment": deployment,
            "supports_tools": supports_tools,
            "tool_capability_status": capability_status,
            "supports_vision": supports_vision,
            "vision_capability_status": vision_capability_status,
        }
        if same_target and previous:
            if previous.get("tool_capability_checked_at"):
                normalized_model["tool_capability_checked_at"] = previous["tool_capability_checked_at"]
            if previous.get("tool_capability_detail"):
                normalized_model["tool_capability_detail"] = previous["tool_capability_detail"]
            if previous.get("vision_capability_checked_at"):
                normalized_model["vision_capability_checked_at"] = previous["vision_capability_checked_at"]
            if previous.get("vision_capability_detail"):
                normalized_model["vision_capability_detail"] = previous["vision_capability_detail"]
        normalized.append(normalized_model)
    return normalized


def _normalize_llm_provider_payload(body: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    vendor_source = {**(existing or {}), **body}
    vendor = (
        get_llm_vendor(str(body["vendor"]))
        if str(body.get("vendor") or "").strip()
        else infer_llm_vendor(vendor_source)
    )
    provider = vendor.provider
    endpoint = str(body.get("endpoint") or "").strip() or None
    base_url = str(body.get("base_url") or "").strip() or vendor.default_base_url
    if not name:
        raise ValueError("Provider name is required")
    if provider == ModelProvider.AZURE_OPENAI and not endpoint:
        raise ValueError("Azure OpenAI provider requires endpoint")
    if provider == ModelProvider.OPENAI_COMPATIBLE and not base_url:
        raise ValueError("OpenAI-compatible provider requires base_url")

    api_key_ciphertext = existing.get("api_key_ciphertext") if existing else None
    if body.get("clear_api_key"):
        api_key_ciphertext = None
    elif str(body.get("api_key") or "").strip():
        api_key_ciphertext = encrypt_provider_secret(str(body["api_key"]).strip())
    enabled = bool(body.get("enabled", True))
    if vendor.requires_api_key and enabled and not api_key_ciphertext:
        raise ValueError(f"{vendor.label} provider requires an API key when enabled")

    return {
        "name": name,
        "vendor": vendor.id,
        "provider": provider.value,
        "endpoint": endpoint,
        "base_url": base_url,
        "api_version": (
            str(body.get("api_version") or "").strip() or "2024-10-21"
            if provider == ModelProvider.AZURE_OPENAI
            else None
        ),
        "organization": str(body.get("organization") or "").strip() or None,
        "models": _normalize_provider_models(body.get("models"), (existing or {}).get("models")),
        "enabled": enabled,
        "api_key_ciphertext": api_key_ciphertext,
    }


def _serialize_llm_provider(document: dict[str, Any]) -> dict[str, Any]:
    vendor = infer_llm_vendor(document)
    return {
        "_id": str(document["_id"]),
        "name": document["name"],
        "vendor": vendor.id,
        "vendor_label": vendor.label,
        "provider": document["provider"],
        "endpoint": document.get("endpoint"),
        "base_url": document.get("base_url"),
        "api_version": document.get("api_version"),
        "organization": document.get("organization"),
        "models": document.get("models", []),
        "enabled": document.get("enabled", True),
        "has_api_key": bool(document.get("api_key_ciphertext")),
        "create_at": document.get("create_at").isoformat() if document.get("create_at") else None,
        "update_at": document.get("update_at").isoformat() if document.get("update_at") else None,
    }


def _settings_for_managed_model(provider: dict[str, Any], model: dict[str, Any]) -> LLMProviderSettings:
    return LLMProviderSettings(
        provider=parse_model_provider(provider["provider"]),
        model=model["model"],
        deployment=model.get("deployment"),
        api_version=provider.get("api_version") or "2024-10-21",
        endpoint=provider.get("endpoint"),
        base_url=provider.get("base_url"),
        api_key=decrypt_provider_secret(provider.get("api_key_ciphertext")),
        organization=provider.get("organization"),
    )


def _tool_capability_rejection(error: Exception) -> bool:
    message = str(error).lower()
    mentions_tools = "tool" in message or "function" in message
    rejection = any(
        phrase in message
        for phrase in (
            "not support",
            "unsupported",
            "unknown parameter",
            "unrecognized",
            "not allowed",
            "invalid parameter",
        )
    )
    return mentions_tools and rejection


def _vision_capability_rejection(error: Exception) -> bool:
    message = str(error).lower()
    mentions_vision = any(term in message for term in ("image", "vision", "multimodal", "image_url"))
    rejection = any(
        phrase in message
        for phrase in (
            "not support",
            "unsupported",
            "unknown parameter",
            "unrecognized",
            "not allowed",
            "invalid content",
            "invalid message",
        )
    )
    return mentions_vision and rejection


async def _probe_model_vision_capability(
    client: Any,
    settings: LLMProviderSettings,
    provider: dict[str, Any],
) -> tuple[str, str]:
    # One opaque 1x1 PNG. Neither the prompt nor provider response is persisted.
    probe_image = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/C/HgAGgwJ/lK3Q6wAAAABJRU5ErkJggg=="
    )
    completion_options: dict[str, Any] = {}
    if settings.model in Approach.GPT_REASONING_MODELS:
        completion_options["max_completion_tokens"] = 16
    else:
        completion_options.update({"max_tokens": 16, "temperature": 0})
    completion_options = apply_llm_vendor_chat_policy(
        infer_llm_vendor(provider).id, completion_options
    )
    try:
        response = await client.chat.completions.create(
            model=settings.deployment or settings.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Reply with OK if you can process this image."},
                        {"type": "image_url", "image_url": {"url": probe_image}},
                    ],
                }
            ],
            **completion_options,
        )
    except Exception as error:
        if _vision_capability_rejection(error):
            return "unsupported", "provider_rejected_image_input"
        return "unknown", "probe_inconclusive"
    if response.choices:
        return "supported", "image_request_accepted"
    return "unknown", "empty_probe_response"


async def _probe_model_tool_capability(
    client: Any,
    settings: LLMProviderSettings,
    provider: dict[str, Any],
) -> tuple[str, str]:
    completion_options: dict[str, Any] = {}
    if settings.model in Approach.GPT_REASONING_MODELS:
        completion_options["max_completion_tokens"] = 32
    else:
        completion_options.update({"max_tokens": 32, "temperature": 0})
    completion_options = apply_llm_vendor_chat_policy(
        infer_llm_vendor(provider).id, completion_options
    )
    messages = [
        {
            "role": "user",
            "content": "Call report_tool_support with supported=true. Do not answer with text.",
        }
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "report_tool_support",
                "description": "Reports that tool calling is available.",
                "parameters": {
                    "type": "object",
                    "properties": {"supported": {"type": "boolean"}},
                    "required": ["supported"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    required_choice = True
    try:
        response = await client.chat.completions.create(
            model=settings.deployment or settings.model,
            messages=messages,
            tools=tools,
            tool_choice="required",
            **completion_options,
        )
    except Exception as error:
        if "tool_choice" in str(error).lower() and _tool_capability_rejection(error):
            required_choice = False
            try:
                response = await client.chat.completions.create(
                    model=settings.deployment or settings.model,
                    messages=messages,
                    tools=tools,
                    **completion_options,
                )
            except Exception as retry_error:
                if _tool_capability_rejection(retry_error):
                    return "unsupported", "provider_rejected_tool_calling"
                return "unknown", "probe_inconclusive"
        elif _tool_capability_rejection(error):
            return "unsupported", "provider_rejected_tool_calling"
        else:
            return "unknown", "probe_inconclusive"
    if response.choices:
        tool_calls = getattr(response.choices[0].message, "tool_calls", None) or []
        if any(
            getattr(getattr(call, "function", None), "name", None) == "report_tool_support"
            for call in tool_calls
        ):
            return "supported", "tool_call_returned"
    if not required_choice:
        return "unknown", "tool_choice_not_enforced"
    return "unsupported", "no_tool_call_returned"


def _store_model_tool_capability(
    provider: dict[str, Any], model_id: str, status: str, detail: str
) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    models = []
    for item in provider.get("models", []):
        updated = dict(item)
        if item.get("id") == model_id:
            updated["tool_capability_status"] = status
            updated["tool_capability_checked_at"] = checked_at
            updated["tool_capability_detail"] = detail
            if status == "supported":
                updated["supports_tools"] = True
            elif status == "unsupported":
                updated["supports_tools"] = False
        models.append(updated)
    return update_llm_provider(str(provider["_id"]), {"models": models}) or provider


def _store_model_vision_capability(
    provider: dict[str, Any], model_id: str, status: str, detail: str
) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    models = []
    for item in provider.get("models", []):
        updated = dict(item)
        if item.get("id") == model_id:
            updated["vision_capability_status"] = status
            updated["vision_capability_checked_at"] = checked_at
            updated["vision_capability_detail"] = detail
            if status == "supported":
                updated["supports_vision"] = True
            elif status == "unsupported":
                updated["supports_vision"] = False
        models.append(updated)
    return update_llm_provider(str(provider["_id"]), {"models": models}) or provider


def _load_managed_profiles(base_profiles: dict[str, LLMProfile]) -> dict[str, LLMProfile]:
    profiles = dict(base_profiles)
    for provider in list_llm_providers():
        if not provider.get("enabled", True):
            continue
        for model in provider.get("models", []):
            profile_id = managed_profile_id(str(provider["_id"]), model["id"])
            profiles[profile_id] = LLMProfile(
                profile_id=profile_id,
                label=f"{provider['name']} — {model.get('label') or model['model']}",
                settings=_settings_for_managed_model(provider, model),
                managed_provider_id=str(provider["_id"]),
                managed_model_id=model["id"],
                supports_tools=model.get("supports_tools", True),
                supports_vision=model.get("supports_vision", False),
            )
    return profiles


def _refresh_llm_profile_registry() -> None:
    runtime_settings: RuntimeSettings = current_app.config[CONFIG_RUNTIME_SETTINGS]
    profiles = load_llm_profiles(os.environ, runtime_settings.llm)
    profiles = _load_managed_profiles(profiles)
    credential = current_app.config[CONFIG_CREDENTIAL]
    clients = {
        profile_id: create_llm_client(profile.settings, credential)
        for profile_id, profile in profiles.items()
    }
    current_app.config[CONFIG_LLM_PROFILES] = profiles
    current_app.config[CONFIG_LLM_PROFILE_CLIENTS] = clients


class NamedBytesIO(io.BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


bp = Blueprint("routes", __name__, static_folder="static")
# Fix Windows registry issue with mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


@bp.route("/")
async def index():
    # These two shell assets are small. Returning their bytes directly avoids
    # keeping an aiofiles executor task alive during Quart test shutdown on
    # Python 3.13.
    response = await make_response((Path(__file__).resolve().parent / "static" / "index.html").read_bytes())
    response.content_type = "text/html; charset=utf-8"
    return response


# Empty page is recommended for login redirect to work.
# See https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/initialization.md#redirecturi-considerations for more information
@bp.route("/redirect")
async def redirect():
    return ""


@bp.route("/favicon.ico")
async def favicon():
    response = await make_response((Path(__file__).resolve().parent / "static" / "favicon.ico").read_bytes())
    response.content_type = "image/x-icon"
    return response


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory(Path(__file__).resolve().parent / "static" / "assets", path)


@bp.route("/content/<path>")
@authenticated_path
async def content_file(path: str, auth_claims: dict[str, Any]):
    """
    Serve content files from blob storage from within the app to keep the example self-contained.
    *** NOTE *** if you are using app services authentication, this route will return unauthorized to all users that are not logged in
    if AZURE_ENFORCE_ACCESS_CONTROL is not set or false, logged in users can access all files regardless of access control
    if AZURE_ENFORCE_ACCESS_CONTROL is set to true, logged in users can only access files they have access to
    This is also slow and memory hungry.
    """
    # Remove page number from path, filename-1.txt -> filename.txt
    # This shouldn't typically be necessary as browsers don't send hash fragments to servers
    if "|" in path:
        path = path.replace("|", "/")
    if path.find("#page=") > 0:
        path_parts = path.rsplit("#page=", 1)
        path = path_parts[0]
    current_app.logger.info("Opening file %s", path)
    blob_container_client: ContainerClient = current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]
    blob: Union[BlobDownloader, DatalakeDownloader]
    try:
        blob = await blob_container_client.get_blob_client(path).download_blob()
    except ResourceNotFoundError:
        current_app.logger.info(
            "Path not found in general Blob container: %s", path)
        if current_app.config[CONFIG_USER_UPLOAD_ENABLED]:
            try:
                user_oid = auth_claims["oid"]
                user_blob_container_client = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
                user_directory_client: FileSystemClient = user_blob_container_client.get_directory_client(
                    user_oid)
                file_client = user_directory_client.get_file_client(path)
                blob = await file_client.download_file()
            except ResourceNotFoundError:
                try:
                    blob_container_client: ContainerClient = current_app.config[
                        CONFIG_GROUP_BLOB_CONTAINER_CLIENT]
                    blob: Union[BlobDownloader, DatalakeDownloader]
                    blob = await blob_container_client.get_blob_client(path).download_blob()
                except ResourceNotFoundError:
                    current_app.logger.exception(
                        "Path not found in DataLake: %s", path)
                    abort(404)
        else:
            abort(404)
    if not blob.properties or not blob.properties.has_key("content_settings"):
        abort(404)
    mime_type = blob.properties["content_settings"]["content_type"]
    if mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    blob_file = io.BytesIO()
    await blob.readinto(blob_file)
    blob_file.seek(0)
    return await send_file(blob_file, mimetype=mime_type, as_attachment=False, attachment_filename=path)


@bp.route("/ask", methods=["POST"])
@authenticated
async def ask(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    data_groups_id = request_json.get("data_groups_id")
    selected_scopes = request_json.get("selected_scopes")
    team_id = request_json.get("team_id")
    agent_id = request_json.get("agent_id")
    if team_id:
        new_auth = auth_claims
        new_auth['data_groups_id'] = data_groups_id
        new_auth['selected_scopes'] = selected_scopes
        new_auth['team_id'] = team_id
        context["auth_claims"] = new_auth
    else:
        context["auth_claims"] = auth_claims
    try:
        context["conversation_id"] = ensure_conversation_id(request_json.get("conversation_id"))
        _apply_agent_llm_profile(context, agent_id)
        overrides = context.get("overrides", {})
        _apply_inline_image_attachments(
            request_json,
            context,
            vision_enabled=overrides.get("_agent_image_input_enabled", False),
            vision_available=CONFIG_ASK_VISION_APPROACH in current_app.config,
            select_vision_from_attachments=bool(agent_id),
        )
        await _apply_temporary_attachment_retrieval(request_json, context, auth_claims)
        approach: Approach
        if _use_vision_approach(context) and CONFIG_ASK_VISION_APPROACH in current_app.config:
            approach = cast(
                Approach, current_app.config[CONFIG_ASK_VISION_APPROACH])
        else:
            approach = cast(Approach, current_app.config[CONFIG_ASK_APPROACH])
        r = await approach.run(
            request_json["messages"], context=context, session_state=request_json.get(
                "session_state")
        )

        async def _bg():
            try:
                await asyncio.to_thread(insert_user_usage, auth_claims, r, "ask")
            except Exception:
                current_app.logger.exception("Can't insert user usage")
        if os.getenv("DISABLE_USAGE_PERSISTENCE", "").lower() != "true":
            asyncio.create_task(_bg())
        return jsonify(r)
    except Exception as error:
        return error_response(error, "/ask")


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    try:
        async for event in r:
            yield json.dumps(event, ensure_ascii=False, cls=JSONEncoder) + "\n"
    except Exception as error:
        logging.exception(
            "Exception while generating response stream: %s", error)
        yield json.dumps(error_dict(error))


def _apply_inline_image_attachments(
    request_json: dict[str, Any],
    context: dict[str, Any],
    *,
    vision_enabled: bool,
    vision_available: bool,
    use_langgraph_runtime: bool = False,
    select_vision_from_attachments: bool = False,
) -> None:
    overrides = context.setdefault("overrides", {})
    overrides.pop("_image_attachments", None)
    attachments = validate_chat_attachments(request_json.get("attachments"))
    if not attachments:
        if select_vision_from_attachments:
            overrides["use_gpt4v"] = False
        return
    if use_langgraph_runtime:
        raise ChatAttachmentError("Image attachments are not yet supported by the LangGraph runtime")
    if not vision_enabled:
        raise ChatAttachmentError("Image input is disabled for this agent")
    if not context.get("overrides", {}).get("_llm_supports_vision", False):
        raise ChatAttachmentError("The model selected for this agent does not support image input")
    if not vision_available:
        raise ChatAttachmentError("The vision processing service is not configured for this deployment")
    if select_vision_from_attachments:
        overrides["use_gpt4v"] = True
    overrides["_image_attachments"] = [item["data_url"] for item in attachments]
    overrides["_rag_vision_enabled"] = current_app.config.get(CONFIG_KNOWLEDGE_VISION_ENABLED, False)


def _use_vision_approach(context: dict[str, Any]) -> bool:
    overrides = context.get("overrides", {})
    return bool(
        overrides.get("use_gpt4v", False)
        and (
            current_app.config.get(CONFIG_GPT4V_DEPLOYED, False)
            or overrides.get("_llm_supports_vision", False)
        )
    )


async def _apply_temporary_attachment_retrieval(
    request_json: dict[str, Any],
    context: dict[str, Any],
    auth_claims: dict[str, Any],
) -> None:
    overrides = context.setdefault("overrides", {})
    for key in (
        "_temporary_attachment_sources",
        "_temporary_attachment_ids",
        "_temporary_attachment_index",
        "_temporary_attachment_owner_id",
        "_temporary_attachment_conversation_id",
        "_temporary_attachments_only",
        "_attachment_evidence_scope",
    ):
        overrides.pop(key, None)
    attachment_ids = normalize_attachment_ids(request_json.get("document_attachment_ids"))
    if not attachment_ids:
        return
    if overrides.get("_agent_document_attachments_enabled", True) is not True:
        raise AttachmentRetrievalError("Document attachments are disabled for this agent")
    index: AttachmentIndex | None = current_app.config.get(CONFIG_CHAT_ATTACHMENT_INDEX)
    if index is None:
        raise AttachmentRetrievalError("Temporary document retrieval is not enabled")
    owner_id = str(auth_claims.get("oid") or "")
    conversation_id = str(context.get("conversation_id") or "")
    for attachment_id in attachment_ids:
        item = await asyncio.to_thread(
            get_attachment_metadata,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        if not item:
            raise AttachmentRetrievalError("Document attachment not found for this conversation")
        status = str(item.get("status") or "")
        if status in {"stored", "extracting"}:
            raise AttachmentRetrievalError("Document attachment is still processing")
        if status != "ready":
            error_code = str(item.get("error_code") or "processing_failed")
            raise AttachmentRetrievalError(f"Document attachment is unavailable: {error_code}")
    query = next(
        (
            str(message.get("content") or "").strip()
            for message in reversed(request_json.get("messages") or [])
            if message.get("role") == "user"
        ),
        "",
    )
    if not query:
        raise AttachmentRetrievalError("A user question is required for document retrieval")
    evidence_scope = classify_attachment_evidence_scope(query)
    overrides["_attachment_evidence_scope"] = evidence_scope
    if evidence_scope == ATTACHMENT_EVIDENCE_KNOWLEDGE_ONLY:
        return
    results = await index.search(
        owner_id=owner_id,
        conversation_id=conversation_id,
        query=query,
        attachment_ids=attachment_ids,
    )
    sources = format_attachment_sources(results)
    if not sources:
        raise AttachmentRetrievalError("No readable text was found in the selected document attachments")
    overrides["_temporary_attachment_sources"] = sources
    overrides["_temporary_attachment_ids"] = attachment_ids
    overrides["_temporary_attachment_index"] = index
    overrides["_temporary_attachment_owner_id"] = owner_id
    overrides["_temporary_attachment_conversation_id"] = conversation_id
    overrides["_temporary_attachments_only"] = evidence_scope == ATTACHMENT_EVIDENCE_UPLOADED_ONLY


def _use_langgraph_runtime(agent_id: str | None) -> bool:
    mode = os.getenv("AGENT_RUNTIME_MODE", "per_agent").strip().lower()
    if mode in ("legacy", "langgraph"):
        return mode == "langgraph"
    if agent_id:
        agent = get_agent_by_id(agent_id)
        configured = str((agent or {}).get("config", {}).get("runtime") or "").strip().lower()
        if configured in ("legacy", "langgraph"):
            return configured == "langgraph"
    return False


async def _run_langgraph_as_chat_stream(
    *,
    approach: Approach,
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    auth_claims: dict[str, Any],
    agent_id: str,
    team_id: str | None,
    system_prompt: str,
    session_state: Any,
) -> AsyncGenerator[dict, None]:
    runtime = await create_agent_runtime(
        agent_id=agent_id,
        team_id=team_id,
        auth_claims=auth_claims,
        approach=approach,
        overrides=context.get("overrides") or {},
        system_prompt=system_prompt,
    )
    result = await runtime.run(messages)
    current_app.logger.info(
        "LangGraph agent %s completed in %s model iteration(s); tools=%s",
        agent_id,
        result["iterations"],
        [event["name"] for event in result.get("tool_trace", [])],
    )
    citations = []
    chart_spec = (result.get("artifacts") or {}).get("chart")
    rag_diagnostics = {"called": False, "result_count": 0}
    for event in result.get("tool_trace", []):
        if event.get("source") != "rag" or event.get("is_error"):
            continue
        rag_diagnostics["called"] = True
        try:
            rag_output = json.loads(event.get("output") or "{}")
            citations.extend(rag_output.get("citations") or [])
            rag_diagnostics["result_count"] += len(rag_output.get("results") or [])
        except (json.JSONDecodeError, AttributeError):
            current_app.logger.warning("Unable to parse RAG tool citations for agent %s", agent_id)
    yield {
        "delta": {"role": "assistant"},
        "context": {
            "data_points": {"text": citations, "images": []},
            "thoughts": [
                {
                    "title": "LangGraph agent runtime",
                    "description": {
                        "iterations": result["iterations"],
                        "tools": [event["name"] for event in result.get("tool_trace", [])],
                        "rag": rag_diagnostics,
                        "trace": result.get("trace"),
                    },
                }
            ],
            **({"chart": chart_spec} if chart_spec else {}),
        },
        "session_state": session_state,
    }
    yield {"delta": {"role": "assistant", "content": result["content"]}}


# ⭐ CHART CAPABILITY: โหลด prompt template จากไฟล์ครั้งเดียวตอน startup
_CHART_PROMPT_DIR = Path(__file__).resolve().parent / "approaches" / "prompts"
_chart_prompt_header_tpl: str = (_CHART_PROMPT_DIR / "chart_capability_header.txt").read_text(encoding="utf-8")
_chart_prompt_body: str = (_CHART_PROMPT_DIR / "chart_capability_body.txt").read_text(encoding="utf-8")

# ⭐ CHART CAPABILITY: แยก BLOCKED_TYPE_MESSAGE section ออกจาก header template
# เพื่อใช้สร้าง error message แบบ dynamic เมื่อ chart type ถูก block server-side
import re as _re
_blocked_msg_pattern = _re.compile(
    r"BLOCKED_TYPE_INTRO:\s*(.+)\n"
    r"BLOCKED_TYPE_SUGGEST:\s*(.+)\n"
    r"BLOCKED_TYPE_OPTIONS:\s*.+\n"
    r"BLOCKED_TYPE_QUESTION:\s*(.+)",
    _re.MULTILINE,
)
_blocked_msg_match = _blocked_msg_pattern.search(_chart_prompt_header_tpl)
# ใน template ใช้ {{blocked_types_str}} เพื่อ escape จาก .format() → ดึงมาแล้ว unescape เป็น {blocked_types_str}
_BLOCKED_INTRO_TPL: str = (_blocked_msg_match.group(1).strip().replace("{{blocked_types_str}}", "{blocked_types_str}").replace("{{allowed_types_str}}", "{allowed_types_str}")) if _blocked_msg_match else "ไม่สามารถสร้างกราฟประเภท **{blocked_types_str}** ได้ เนื่องจากไม่ได้รับอนุญาตสำหรับ agent นี้"
_BLOCKED_SUGGEST_TPL: str = _blocked_msg_match.group(2).strip() if _blocked_msg_match else "แต่สามารถสร้างกราฟด้วยประเภทที่รองรับแทนได้ เช่น:"
_BLOCKED_QUESTION_TPL: str = _blocked_msg_match.group(3).strip() if _blocked_msg_match else "ต้องการให้สร้างกราฟประเภทใดแทนครับ?"


# แผนที่ blocked type → ประเภทกราฟทดแทนที่เหมาะสม พร้อมคำอธิบาย
_CHART_TYPE_LABELS: dict[str, str] = {
    "bar": "กราฟแท่ง (bar)", "line": "กราฟเส้น (line)", "pie": "กราฟวงกลม (pie)",
    "area": "กราฟพื้นที่ (area)", "scatter": "กราฟกระจาย (scatter)",
    "radar": "กราฟเรดาร์ (radar)", "heatmap": "กราฟความร้อน (heatmap)",
    "sunburst": "กราฟซันเบิร์ส (sunburst)", "gauge": "มาตรวัด (gauge)",
    "funnel": "กราฟกรวย (funnel)", "boxplot": "กราฟกล่อง (boxplot)",
    "candlestick": "กราฟแท่งเทียน (candlestick)", "sankey": "กราฟซังกี้ (sankey)",
    "graph": "กราฟเครือข่าย (graph)", "bar3D": "กราฟแท่ง 3D (bar3D)",
    "line3D": "กราฟเส้น 3D (line3D)", "scatter3D": "กราฟกระจาย 3D (scatter3D)",
    "surface": "กราฟพื้นผิว 3D (surface)", "treemap": "treemap",
}

_CHART_ALTERNATIVES: dict[str, list[tuple[str, str]]] = {
    # hierarchical / proportions
    "treemap":    [("bar",     "เปรียบเทียบค่าระหว่างหมวดหมู่ได้ชัดเจน"),
                   ("line",    "แสดงแนวโน้มตามช่วงเวลา"),
                   ("pie",     "แสดงสัดส่วนของแต่ละรายการ"),
                   ("area",    "แสดงแนวโน้มพร้อมเน้นปริมาณสะสม"),
                   ("scatter", "แสดงความสัมพันธ์ระหว่างสองตัวแปร")],
    "sunburst":   [("pie",     "แสดงสัดส่วนในรูปแบบวงกลมที่เข้าใจง่าย"),
                   ("bar",     "เปรียบเทียบค่าระหว่างกลุ่มได้โดยตรง")],
    # network / flow
    "graph":      [("bar",     "แสดงความสัมพันธ์เชิงขนาดระหว่าง node"),
                   ("scatter", "แสดงการกระจายตัวของจุดข้อมูล")],
    "sankey":     [("bar",     "เปรียบเทียบปริมาณการไหลของแต่ละเส้นทาง"),
                   ("funnel",  "แสดงการลดลงของปริมาณในแต่ละขั้นตอน")],
    # 3D → 2D fallback
    "bar3D":      [("bar",     "แสดงข้อมูลเดียวกันในรูปแบบ 2D ที่อ่านง่ายกว่า"),
                   ("heatmap", "แสดงความหนาแน่นของข้อมูล 2 มิติ")],
    "line3D":     [("line",    "แสดงแนวโน้มในรูปแบบ 2D ที่ชัดเจน"),
                   ("area",    "เน้นปริมาณสะสมตามแนวโน้ม")],
    "scatter3D":  [("scatter", "แสดงการกระจายตัวใน 2D ได้ดีเช่นกัน"),
                   ("heatmap", "แสดงความหนาแน่นของจุดข้อมูล")],
    "surface":    [("heatmap", "แสดง z = f(x,y) ในรูปแบบ 2D ที่อ่านง่ายกว่า"),
                   ("bar3D",   "แสดงข้อมูล 3 มิติในรูปแบบแท่ง")],
    # distribution
    "boxplot":    [("bar",     "แสดงค่าเฉลี่ยหรือผลรวมของแต่ละกลุ่ม"),
                   ("area",    "แสดงการกระจายตัวของข้อมูลตามช่วงเวลา")],
    # geo
    "map":        [("scatter", "แสดงตำแหน่งของจุดข้อมูลบนแกน x/y"),
                   ("heatmap", "แสดงความหนาแน่นของข้อมูลในพื้นที่")],
    # multi-metric
    "radar":      [("bar",     "เปรียบเทียบหลายตัวชี้วัดระหว่างกลุ่ม"),
                   ("line",    "แสดงแนวโน้มของตัวชี้วัดหลายรายการ")],
}
_CHART_ALTERNATIVES_DEFAULT = [
    ("bar",     "เปรียบเทียบค่าระหว่างหมวดหมู่ได้ชัดเจน"),
    ("line",    "แสดงแนวโน้มตามช่วงเวลา"),
    ("pie",     "แสดงสัดส่วนของแต่ละรายการ"),
    ("area",    "แสดงแนวโน้มพร้อมเน้นปริมาณสะสม"),
    ("scatter", "แสดงความสัมพันธ์ระหว่างสองตัวแปร"),
]


def build_blocked_message(blocked_types: list[str], allowed_types: list[str], llm_content: str = "") -> str:
    """
    สร้าง consultative message เมื่อ chart type ถูก block
    - วิเคราะห์ blocked type แล้วแนะนำ alternative ที่เหมาะสม 5 ตัว
    - กรองเฉพาะ alternative ที่อยู่ใน allowed_types จริงๆ
    - ถ้าหา alternative ไม่ได้เลย fallback แสดง allowed list สั้นๆ
    - แนบ llm_content เป็น hidden context เพื่อให้ LLM รอบถัดไปรู้ข้อมูลเดิม
    """
    blocked_str = ", ".join(
        _CHART_TYPE_LABELS.get(t.lower(), t) for t in blocked_types
    )
    allowed_lower = {t.strip().lower() for t in allowed_types}

    # หา alternatives จาก blocked type แรก (กรณีส่วนใหญ่มีแค่ตัวเดียว)
    primary_blocked = blocked_types[0].lower() if blocked_types else ""
    candidates = _CHART_ALTERNATIVES.get(primary_blocked, _CHART_ALTERNATIVES_DEFAULT)

    # กรองเฉพาะที่อยู่ใน allowed list จริงๆ
    suggestions = [(t, desc) for t, desc in candidates if t.lower() in allowed_lower]

    # ถ้าไม่มีเลย ใช้ top-5 จาก allowed list พร้อม label
    if not suggestions:
        suggestions = [
            (t, "รองรับโดย agent นี้")
            for t in allowed_types[:5]
        ]

    intro = _BLOCKED_INTRO_TPL.replace("{blocked_types_str}", blocked_str)
    question = _BLOCKED_QUESTION_TPL

    lines = [f"📊 {intro}", ""]
    lines.append("กราฟที่แนะนำสำหรับข้อมูลนี้:")
    for chart_type, desc in suggestions:
        label = _CHART_TYPE_LABELS.get(chart_type.lower(), chart_type)
        lines.append(f"  • **{label}** — {desc}")
    lines.append("")
    lines.append(question)

    # แนบ LLM content เดิมเป็น hidden context เพื่อให้ LLM รอบถัดไปรู้ข้อมูลที่ถูกถามมา
    # frontend จะเห็นแค่ blocked message แต่ LLM จะเห็น context นี้ใน history
    if llm_content and llm_content.strip():
        lines.append(
            f"\n<!-- DATA_CONTEXT: {llm_content.strip()} -->"
        )

    return "\n".join(lines)


def build_chart_prompt(chart_binding_cfg: dict) -> str:
    """
    สร้าง system prompt สั่ง LLM ให้สร้าง chart spec (Apache ECharts format)
    โดย inject ค่า config จาก chart_binding_cfg เข้าไปใน header template
    ส่วน body (examples, rules) อ่านมาจากไฟล์ chart_capability_body.txt โดยตรง

    chart_selection_mode:
      "auto"   → LLM เลือก chart type เองจาก configured allowed list
      "manual" → enforce allowed_chart_types (พฤติกรรมเดิม)
    """
    from mongo_table_connecters.chart_binding import ALL_SUPPORTED_CHART_TYPES

    palette = chart_binding_cfg.get("color_palette", [])
    title_template = chart_binding_cfg.get("title_template", "")
    keywords = chart_binding_cfg.get("trigger_keywords", [])
    auto_generate = chart_binding_cfg.get("auto_generate", False)
    chart_selection_mode = chart_binding_cfg.get("chart_selection_mode", "manual")
    is_auto = chart_selection_mode == "auto"

    # auto mode: LLM เลือกเอง แต่ยังอยู่ภายใน allowlist ของ binding
    # manual mode: enforce allowed_chart_types จาก config
    if is_auto:
        allowed_types = chart_binding_cfg.get("allowed_chart_types") or ALL_SUPPORTED_CHART_TYPES
        default_type = "auto"
    else:
        allowed_types = chart_binding_cfg.get("allowed_chart_types", ["bar", "line", "pie", "area"])
        default_type = chart_binding_cfg.get("default_chart_type", "bar")

    allowed_types_str = ", ".join(allowed_types) if allowed_types else "(any supported chart type)"
    palette_str = ", ".join(palette) if palette else "(use vibrant, distinct colors for each series/item)"
    keywords_str = ", ".join(keywords) if keywords else "(any data-related question)"

    # ── สร้าง conditional sections ตาม mode ──────────────────────────────
    # auto_generate ควบคุมว่า LLM จะสร้างกราฟเองอัตโนมัติหรือรอ user สั่ง
    # chart_selection_mode ควบคุมว่า LLM เลือก type เองหรือต้อง enforce allowed list
    # NOTE: auto_generate=True หมายความว่าสร้างเมื่อมี numeric data โดยไม่ต้องรอ user
    #       แต่ถ้า False (default) → ต้องรอ user ขอเสมอ ไม่ว่า chart_selection_mode จะเป็นอะไร
    if auto_generate:
        when_to_generate = (
            "- AUTO MODE is ON: Automatically generate the most suitable chart whenever your answer "
            "contains numeric or statistical data, even if the user did not explicitly ask for one.\n"
            "- Choose the chart type that BEST visualizes the data — do NOT default to bar every time."
        )
    else:
        when_to_generate = (
            f'- ONLY generate a chart when the user EXPLICITLY requests one (e.g. "สร้างกราฟ", "แสดงกราฟ", "plot", "chart", "visualize", "ทำกราฟ", "วาดกราฟ")\n'
            f"- OR when the user's message contains a trigger keyword from the configured list: {keywords_str}\n"
            "- Do NOT generate a chart automatically just because the answer contains numeric data.\n"
            "- Do NOT generate a chart proactively to 'help' the user without being asked.\n"
            "- If the user did not ask for a chart and no trigger keyword is present → answer in plain text ONLY, do NOT append any chart-spec block."
        )

    if is_auto:
        chart_type_selection = f"""- You have FULL FREEDOM to choose any chart type from: {allowed_types_str}
- Select the type that BEST represents the data structure. Use these guidelines:
  - Comparisons across categories → bar (vertical or horizontal based on label length)
  - Trends over time / sequences → line or area
  - Part-of-whole proportions (≤8 items) → pie or donut; (>8 items or hierarchical) → treemap or sunburst
  - Correlation between two numeric variables → scatter
  - Multi-metric performance across items → radar
  - Intensity / density on a 2D categorical grid → heatmap
  - Flow / transfer between nodes → sankey
  - Conversion funnel / process stages → funnel
  - Single KPI speedometer → gauge
  - Financial OHLC price data → candlestick
  - Entity relationship network → graph
  - Statistical distribution / outliers → boxplot
  - Accumulation over time → area
  - 3D multi-dimensional data → bar3D, scatter3D, or surface
  - Proportional pictographic icons → pictorialBar
  - Multi-dimensional parallel comparison → parallel
  - Time-based topic stream → themeRiver
  - Daily/calendar activity heatmap → calendar
- NEVER default to bar when another type would be more insightful.
- If you are unsure, use bar or line as a safe default.
- CHART QUALITY RULES (apply to ALL chart types, whether you choose or user requests):
  - Choose the BEST VARIANT of the chart type for the data (e.g. donut over plain pie for cleaner look, horizontal bar when labels are long, stacked bar when comparing part-of-whole across groups)
  - ALWAYS set appropriate layout: grid margins, legend position, label rotation to prevent overlap
  - ALWAYS use DISTINCT colors for each series/category — never repeat colors
  - For many data points (>10): reduce label density (show every 2nd label or use smaller font)
  - For bar3D: ALWAYS use formatter: "{{@[2]}}" on labels to show only the value, not the full array
  - For pie/donut: limit to ≤12 slices; if more, group smallest into "Others"
  - For multi-series: always include a legend
  - Prefer donut (radius: ["40%","70%"]) over plain pie for modern look
  - DATA INTEGRITY: ONLY plot data that actually exists in the source. If one series has fewer items than another (e.g. 2024 has 10 items but 2025 has 5), include BOTH series with whatever data is available — never omit a series just because it has partial data. Only omit a series if it has ZERO data points, and explain this in the text."""
    else:
        chart_type_selection = f"""- You MUST ONLY use chart types from the supported list: {allowed_types_str}
- Do NOT use any chart type NOT in the list above.
- If the user requests a type IN the list → generate it directly using the BEST VARIANT for the data.
- If you see <!-- DATA_CONTEXT: ... --> in chat history → use that data for the next chart request.
- If the user requests a type NOT in {allowed_types_str}:
  1. Do NOT generate any chart-spec block.
  2. Do NOT explain how to use the requested type.
  3. Recommend up to 5 alternatives STRICTLY from: {allowed_types_str}. NEVER suggest a type outside that list.
  4. Respond in a helpful, consultative tone — not like an error.
- CHART QUALITY RULES (apply regardless of who chose the chart type):
  - Choose the BEST VARIANT of the requested chart type (e.g. horizontal bar if labels are long, stacked if comparing proportions)
  - ALWAYS use DISTINCT colors, proper legend, and non-overlapping labels
  - For bar3D: ALWAYS use formatter: "{{@[2]}}" on labels
  - For pie/donut: limit to ≤12 slices; group smallest into "Others" if more
  - Prefer donut (radius: ["40%","70%"]) over plain pie for modern look
  - DATA INTEGRITY: ONLY plot data that actually exists in the source. If one series has fewer items than another, include BOTH with whatever data is available. Only omit a series if it has ZERO data points, and explain this in the text answer."""

    header = _chart_prompt_header_tpl.format(
        default_type=default_type,
        allowed_types_str=allowed_types_str,
        palette_str=palette_str,
        title_template=title_template or "(auto-generated)",
        keywords_str=keywords_str,
        auto_generate_mode="true" if auto_generate else "false",
        chart_selection_mode=chart_selection_mode,
        when_to_generate=when_to_generate,
        chart_type_selection=chart_type_selection,
    )

    return header + _chart_prompt_body


# ⭐ CHART CAPABILITY: ดึง chart-spec block ออกจาก LLM response
def extract_chart_spec(content: str):
    """
    หา ```chart-spec ... ``` หรือ ```json ... ``` หรือ ``` ... ``` block ในเนื้อหา LLM response
    แล้วตรวจสอบว่ามีโครงสร้างของ chart spec (เช่น คีย์ "option" หรือ "chartType") หรือไม่
    แล้ว parse เป็น dict คืน (cleaned_content_without_block, chart_spec_dict_or_None)
    ถ้าไม่เจอ code block ให้ลอง fallback หา bare JSON object ที่มีคีย์ "option" ด้วย
    """
    if not content:
        return content, None

    # ── Pass 1: หา ```chart-spec / ```json / ``` block ──────────────────────
    pattern = r"```(?:chart-spec|json)?\s*\n?(.*?)\n?```"
    for match in re.finditer(pattern, content, re.DOTALL):
        spec_raw = match.group(1).strip()
        if '"option"' in spec_raw or '"chartType"' in spec_raw:
            # ลบ JS-style comments (// ...) ก่อน parse เพราะ LLM บางครั้งใส่มา
            spec_clean = re.sub(r'//[^\n]*', '', spec_raw)
            try:
                spec = json.loads(spec_clean)
                cleaned = content.replace(match.group(0), "").strip()
                return cleaned, spec
            except (json.JSONDecodeError, ValueError):
                continue

    # ── Pass 2: fallback — หา bare JSON object { "option": ... } ────────────
    # LLM บางครั้ง dump JSON โดยไม่มี code fence
    bare_pattern = r'(\{[^`]*?"option"\s*:\s*\{.*?\}\s*,?\s*"height"\s*:\s*\d+\s*\})'
    for match in re.finditer(bare_pattern, content, re.DOTALL):
        spec_raw = match.group(1).strip()
        spec_clean = re.sub(r'//[^\n]*', '', spec_raw)
        try:
            spec = json.loads(spec_clean)
            if "option" in spec:
                cleaned = content.replace(match.group(0), "").strip()
                return cleaned, spec
        except (json.JSONDecodeError, ValueError):
            continue

    return content, None


# ⭐ CHART CAPABILITY: enforce allowed chart types บน spec ที่ LLM สร้างมา
def _check_chart_types(chart_spec: dict, allowed_types: list[str]) -> list[str]:
    """
    คืนรายการ chart type ที่ LLM ใช้แต่ไม่ได้รับอนุญาต
    ถ้า allowed_types ว่างหรือไม่มี series ให้คืน list ว่าง (ไม่บล็อก)
    รองรับชื่อภาษาไทยและ alias ต่างๆ ที่ LLM อาจใช้
    """
    if not allowed_types:
        return []

    # normalize allowed_types เป็น lowercase set
    # รองรับ case เช่น "bar3D" → "bar3d"
    allowed_set = {t.strip().lower() for t in allowed_types}

    # alias map: ชื่อที่ LLM อาจใช้ (lowercase) → canonical lowercase ECharts type
    _ALIAS: dict[str, str] = {
        # ── ภาษาไทย ──────────────────────────────────────────────────────────
        "แท่ง": "bar", "กราฟแท่ง": "bar",
        "เส้น": "line", "กราฟเส้น": "line",
        "วงกลม": "pie", "กราฟวงกลม": "pie", "โดนัท": "pie", "โดนัต": "pie",
        "พื้นที่": "area", "กราฟพื้นที่": "area",
        "กระจาย": "scatter", "จุดกระจาย": "scatter",
        "เรดาร์": "radar", "แมงมุม": "radar",
        "ความร้อน": "heatmap", "แผนที่ความร้อน": "heatmap",
        "แผนผัง": "treemap", "ทรีแมป": "treemap",
        "ซันเบิร์ส": "sunburst", "ดวงอาทิตย์": "sunburst",
        "มาตรวัด": "gauge", "เกจ": "gauge",
        "ช่องทาง": "funnel", "กรวย": "funnel",
        "กล่อง": "boxplot", "boxplot": "boxplot", "กล่องหนวด": "boxplot",
        "เทียน": "candlestick", "แท่งเทียน": "candlestick",
        "ซังกี้": "sankey", "แผนภาพซังกี้": "sankey",
        "กราฟสัมพันธ์": "graph", "โครงข่าย": "graph", "เครือข่าย": "graph",
        "แท่ง3d": "bar3d", "3dแท่ง": "bar3d",
        "เส้น3d": "line3d", "3dเส้น": "line3d",
        "กระจาย3d": "scatter3d", "3dกระจาย": "scatter3d",
        "พื้นผิว": "surface", "3dพื้นผิว": "surface",
        # ── English aliases / variants ────────────────────────────────────────
        "bar chart": "bar", "column": "bar", "column chart": "bar", "histogram": "bar",
        "line chart": "line",
        "pie chart": "pie", "donut": "pie", "doughnut": "pie", "donut chart": "pie",
        "area chart": "area",
        "scatter plot": "scatter", "scatterplot": "scatter", "scatter chart": "scatter",
        "radar chart": "radar", "spider chart": "radar", "web chart": "radar",
        "heat map": "heatmap", "heatmap chart": "heatmap",
        "tree map": "treemap", "treemap chart": "treemap",
        "sunburst chart": "sunburst",
        "gauge chart": "gauge",
        "funnel chart": "funnel",
        "box plot": "boxplot", "box-plot": "boxplot", "whisker": "boxplot",
        "candlestick chart": "candlestick", "ohlc": "candlestick",
        "sankey diagram": "sankey", "sankey chart": "sankey",
        "graph chart": "graph", "network graph": "graph", "relationship graph": "graph",
        "3d bar": "bar3d", "3d bar chart": "bar3d", "bar3d": "bar3d",
        "3d line": "line3d", "3d line chart": "line3d", "line3d": "line3d",
        "3d scatter": "scatter3d", "3d scatter plot": "scatter3d", "scatter3d": "scatter3d",
        "surface chart": "surface", "surface3d": "surface",
    }

    option = chart_spec.get("option", {})
    series = option.get("series")
    if not isinstance(series, list):
        return []

    blocked = []
    for item in series:
        if isinstance(item, dict):
            raw_type = item.get("type", "").strip()
            normalized = raw_type.lower()
            # แปลง alias → canonical type
            canonical = _ALIAS.get(normalized, normalized)
            if canonical and canonical not in allowed_set and canonical not in blocked:
                blocked.append(raw_type)  # report ชื่อที่ LLM ใช้จริง

    return blocked


# ⭐ CHART CAPABILITY: wrap streaming generator เพื่อสกัด chart-spec ตอนจบ
async def wrap_stream_with_chart_extraction(
    r: AsyncGenerator[dict, None],
    allowed_types: list[str] | None = None,
    chart_binding_cfg: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """
    ครอบ chat stream generator เพื่อ:
    1. Buffer event ทั้งหมดและสะสม content ขณะ stream
    2. พอ stream จบ → parse ```chart-spec block ออกจาก content รวม
    3. ตรวจสอบ series[].type ว่าอยู่ใน allowed_types หรือไม่
       - ถ้าผ่าน: emit events เดิมทั้งหมด + event chart spec ท้าย
       - ถ้าไม่อนุญาต: emit events เดิมที่ลบ chart-spec block ออกแล้ว
                        + error message แทน chart spec
    """
    buffered_events = []
    accumulated_content = ""

    # Buffer events ทั้งหมดก่อน ไม่ yield ออกไปเลยจนกว่าจะตรวจสอบเสร็จ
    async for event in r:
        buffered_events.append(event)
        delta = event.get("delta", {})
        if delta.get("content"):
            accumulated_content += delta["content"]

    # ตรวจสอบว่ามี chart-spec block หรือไม่
    cleaned_content, chart_spec = extract_chart_spec(accumulated_content)

    if chart_spec:
        try:
            chart_spec = validate_echarts_spec(chart_spec, allowed_types or None)
            blocked_types = []
        except ChartValidationError as error:
            logging.warning("Rejecting invalid chart spec: %s", error)
            blocked_types = [str(error)]
        if blocked_types:
            # ── กรณี chart type ไม่อนุญาต ──
            logging.warning(
                "Chart type(s) %s not in allowed list %s — rejecting chart spec",
                blocked_types, allowed_types,
            )
            error_msg = "ไม่สามารถแสดงกราฟนี้ได้ เนื่องจากข้อมูลหรือรูปแบบกราฟไม่ผ่านการตรวจสอบความปลอดภัย"

            # Re-emit เฉพาะ non-content events (role, context ฯลฯ) ก่อน
            # แล้ว emit blocked message เพียงอย่างเดียวแทน LLM content ทั้งหมด
            # เพื่อไม่ให้ข้อความ LLM ที่พูดถึง blocked type ปรากฏซ้ำกับ message ของเรา
            for event in buffered_events:
                delta = event.get("delta", {})
                if delta.get("content"):
                    # ข้าม LLM content ทั้งหมด จะแทนที่ด้วย error_msg เพียงก้อนเดียว
                    continue
                else:
                    # non-content events (role, context ฯลฯ) yield ตามปกติ
                    yield event
            # emit blocked message แทน content ของ LLM
            yield {
                "delta": {"role": "assistant", "content": error_msg.strip()},
            }
        else:
            # ── กรณีผ่าน: emit events ตามปกติ + chart spec ท้าย ──
            for event in buffered_events:
                yield event
            yield {
                "delta": {"role": "assistant"},
                "context": {"chart": chart_spec},
            }
    else:
        # ── ไม่มี chart-spec block เลย: emit events ตามปกติ ──
        for event in buffered_events:
            yield event


@bp.route("/chat", methods=["POST"])
@authenticated
async def chat(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    add_group = request_json.get("gid")
    if add_group:
        new_auth = auth_claims
        new_auth['addition_group'] = add_group
        context["auth_claims"] = new_auth  
    else:
        context["auth_claims"] = auth_claims
    try:
        context["conversation_id"] = ensure_conversation_id(request_json.get("conversation_id"))
        agent_id = request_json.get("agent_id")
        _apply_agent_llm_profile(context, agent_id)
        overrides = context.get("overrides", {})
        _apply_inline_image_attachments(
            request_json,
            context,
            vision_enabled=overrides.get("_agent_image_input_enabled", False),
            vision_available=CONFIG_CHAT_VISION_APPROACH in current_app.config,
            select_vision_from_attachments=bool(agent_id),
        )
        await _apply_temporary_attachment_retrieval(request_json, context, auth_claims)
        approach: Approach
        if _use_vision_approach(context) and CONFIG_CHAT_VISION_APPROACH in current_app.config:
            approach = cast(
                Approach, current_app.config[CONFIG_CHAT_VISION_APPROACH])
        else:
            approach = cast(Approach, current_app.config[CONFIG_CHAT_APPROACH])

        # If session state is provided, persists the session state,
        # else creates a new session_id depending on the chat history options enabled.
        session_state = request_json.get("session_state")
        if session_state is None:
            session_state = create_session_id(
                current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
                current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            )
        result = await approach.run(
            request_json["messages"],
            context=context,
            session_state=session_state,
        )
        return jsonify(result)
    except Exception as error:
        return error_response(error, "/chat")


@bp.route("/chat/stream", methods=["POST"])
@authenticated
async def chat_stream(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    base_prompt_template = str((context.get("overrides") or {}).get("prompt_template") or "")
    data_groups_id = request_json.get("data_groups_id")
    selected_scopes = request_json.get("selected_scopes")
    team_id = request_json.get("team_id")
    agent_id = request_json.get("agent_id")
    use_langgraph_runtime = bool(agent_id and _use_langgraph_runtime(agent_id))
    api_result = request_json.get("api_result",None)
    app_message = request_json["messages"]
    has_chart_capability = False
    chart_binding_cfg = None
    chart_bindings = []
    if agent_id:
        try:
            chart_bindings = get_enabled_chart_bindings_by_agent_id(agent_id)
        except Exception:
            current_app.logger.exception("Failed to retrieve chart bindings for agent %s", agent_id)
    has_chart_capability = len(chart_bindings) > 0
    chart_binding_cfg = chart_bindings[0] if chart_bindings else None
    if team_id:
        new_auth = auth_claims
        new_auth['data_groups_id'] = data_groups_id
        new_auth['selected_scopes'] = selected_scopes
        new_auth['team_id'] = team_id
        context["auth_claims"] = new_auth
        agent_bindings = get_all_agent_bindings_by_agent_id(agent_id)

        db_sources = []
        try:
            if agent_id and not use_langgraph_runtime:
                db_sources = get_agent_mongodb_sources(agent_id, query=None)
                db_sources = db_sources[:5] if db_sources else []
        except Exception:
            current_app.logger.exception("Failed to retrieve external MongoDB sources for agent %s", agent_id)
            db_sources = []

        overrides = context.get("overrides")
        if overrides is None:
            overrides = {}
            context["overrides"] = overrides
        prompt_template = overrides.get("prompt_template", "")

        db_prompt = ""
        if db_sources:
            db_source_lines = []
            for source in db_sources:
                db_source_lines.append(source.get("source_text", ""))
            db_prompt = f"""
========================
EXTERNAL MONGODB SOURCES
========================
{chr(10).join(db_source_lines)}

Use the external MongoDB sources above to answer user questions when relevant.
Only answer based on the information included in these sources.
Do not invent values that are not present in the documents above.
"""

        if len(agent_bindings) > 0 and not use_langgraph_runtime:
            api_registry = ""
            for binding in agent_bindings:
                full_api = get_apis_by_id(binding['integration_id'])
                parameter = ""
                for para in binding['request_fields']:
                    parameter = f"{parameter}- {para['field']}: {para['description']}\n"
                trig_key = ', '.join(binding['trigger_keywords'])
                api_registry = f"{api_registry}API NAME: {full_api['name']}\nENDPOINT NAME: {binding['endpoint_name']}\nTRIGGER KEYWORDS: {trig_key}\nREQUIRED PARAMETERS:\n{parameter}\n"
            api_prompt = f"""
You are an AI assistant that can:
1) Answer questions using provided sources (RAG)
2) Execute external APIs based on user intent

========================
AVAILABLE APIs
========================
{api_registry}
Each API includes:
- api_name (service name)
- endpoint_name (specific endpoint)
- trigger_keywords
- required parameters

API SELECTION RULES:
- If user message matches trigger_keywords → select that API
- If multiple APIs match → DO NOT select immediately
- If no API matches → go to RAG MODE

========================
MULTIPLE API MATCH HANDLING
========================

If more than one API matches the user intent:

1) You MUST ask a clarification question to the user
2) The question should help differentiate between the matched APIs
3) Use differences in trigger_keywords to guide the question

Rules:
- Ask ONLY one clear question
- Do NOT include [y/n]
- Do NOT mention API names
- DO NOT expand or generalize keywords
- Use natural language based on user language

========================
API WORKFLOW MODE
========================

When an API is selected, follow this 2-step workflow:

STEP 1: PARAMETER COLLECTION (NO [y/n])

- You must collect ONLY the parameters explicitly listed in REQUIRED PARAMETERS
- Ask for missing parameters only
- Ask in the same language as the user
- Do NOT confirm yet
- Do NOT include [y/n]
- Do NOT use any sources
- Do NOT include any source references
- DO NOT assume or add any extra parameters

If REQUIRED PARAMETERS is empty:
- Do NOT ask any follow-up questions
- Immediately proceed to confirmation step

Parameter validation rules:
- If parameter is a date → validate format (DD/MM/YY, DD/MM/YYYY, YYYY-MM-DD)
- If API specifies constraints → enforce them
- If values are invalid → ask user to correct

STEP 2: CONFIRMATION (MUST end with [y/n])

Once ALL parameters are collected and valid, respond EXACTLY in this format:

ยืนยันการเรียกใช้ API

api_name: <api_name>
endpoint_name: <endpoint_name>

Parameters
<param1>: <value>
<param2>: <value>

[y/n]

Formatting rules:
- There MUST be one empty line after the title
- api_name and endpoint_name must be on separate lines
- Parameters must be on separate lines
- There MUST be one empty line before [y/n]
- The response MUST end with EXACTLY: [y/n]
- No text is allowed after [y/n]

IMPORTANT:
- NEVER include source references in API workflow
- NEVER mix API workflow with RAG

========================
RAG MODE
========================

If no API is matched, follow rules below:
"""
            if db_prompt:
                context['overrides']['prompt_template'] = f"{api_prompt}{db_prompt}{prompt_template}"
            else:
                context['overrides']['prompt_template'] = f"{api_prompt}{prompt_template}"
        elif db_prompt:
            context['overrides']['prompt_template'] = f"{db_prompt}{prompt_template}"
        else:
            context['overrides']['prompt_template'] = prompt_template

        # ⭐ CHART CAPABILITY: ถ้า agent มี chart binding เปิดอยู่ → inject chart prompt
        #    สั่ง LLM ให้คืน chart spec เป็น mui-x-charts native props JSON ใน ```chart-spec block
        #    ใช้ APPEND แทน prepend เพื่อให้ chart prompt อยู่ท้ายสุด (override คำสั่ง RAG
        #    ที่ห้าม generate นอกเหนือจาก facts ใน source)
        if has_chart_capability and chart_binding_cfg:
            chart_prompt = build_chart_prompt(chart_binding_cfg)
            context['overrides']['prompt_template'] = f"{context['overrides']['prompt_template']}{chart_prompt}"
    else:
        context["auth_claims"] = auth_claims
    if api_result:
        app_message.append({"role": "system","content": f"API_RESPONSE: {json.dumps(api_result, ensure_ascii=False)}"})
        response_promtp = """========================
API RESPONSE HANDLING
========================

When API response is provided:

- The response will be given in a message with role "system" or "tool"
- You must analyze the API response and explain it to the user
- Summarize the result in a clear and user-friendly way
- Do NOT show raw JSON unless explicitly asked
- Extract key information and present it naturally

If the API response indicates success:
- Explain what was successful
- Show important returned data

If the API response indicates error:
- Explain the error clearly
- Suggest what the user should do next

Always respond in the same language as the user"""
        final_prompt = f"{context['overrides']['prompt_template']}{response_promtp}"
        context['overrides']['prompt_template'] = final_prompt 
    try:
        context["conversation_id"] = ensure_conversation_id(request_json.get("conversation_id"))
        _apply_agent_llm_profile(context, agent_id)
        overrides = context.get("overrides", {})
        _apply_inline_image_attachments(
            request_json,
            context,
            vision_enabled=overrides.get("_agent_image_input_enabled", False),
            vision_available=CONFIG_CHAT_VISION_APPROACH in current_app.config,
            use_langgraph_runtime=use_langgraph_runtime,
            select_vision_from_attachments=bool(agent_id),
        )
        await _apply_temporary_attachment_retrieval(request_json, context, auth_claims)
        approach: Approach
        if _use_vision_approach(context) and CONFIG_CHAT_VISION_APPROACH in current_app.config:
            approach = cast(
                Approach, current_app.config[CONFIG_CHAT_VISION_APPROACH])
        else:
            approach = cast(Approach, current_app.config[CONFIG_CHAT_APPROACH])

        # If session state is provided, persists the session state,
        # else creates a new session_id depending on the chat history options enabled.
        session_state = request_json.get("session_state")
        if session_state is None:
            session_state = create_session_id(
                current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
                current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            )
        if use_langgraph_runtime:
            runtime_system_prompt = base_prompt_template
            result = _run_langgraph_as_chat_stream(
                approach=approach,
                messages=app_message,
                context=context,
                auth_claims=context.get("auth_claims") or auth_claims,
                agent_id=agent_id,
                team_id=team_id,
                system_prompt=runtime_system_prompt,
                session_state=session_state,
            )
        else:
            result = await approach.run_stream(
                app_message,
                context=context,
                session_state=session_state,
            )

        # ⭐ CHART CAPABILITY: ถ้า agent มี chart capability ให้ wrap generator
        #    เพื่อ buffer ทั้งหมด ตรวจสอบ chart type แล้วค่อยส่งออก
        if has_chart_capability and not use_langgraph_runtime:
            _default_allowed = ["bar", "line", "pie", "area"]
            _is_auto = (chart_binding_cfg or {}).get("chart_selection_mode", "manual") == "auto"
            if _is_auto:
                from mongo_table_connecters.chart_binding import ALL_SUPPORTED_CHART_TYPES
                _allowed = chart_binding_cfg.get("allowed_chart_types") or ALL_SUPPORTED_CHART_TYPES
            else:
                _allowed = chart_binding_cfg.get("allowed_chart_types") or _default_allowed if chart_binding_cfg else _default_allowed
            result = wrap_stream_with_chart_extraction(
                result,
                allowed_types=_allowed,
                chart_binding_cfg=chart_binding_cfg,
            )

        # Stream NDJSON immediately. Legacy chart extraction still buffers internally,
        # while normal and LangGraph responses are no longer buffered by this route.
        @stream_with_context
        async def stream_and_record_usage():
            ndjson_lines = []
            try:
                async for line in format_as_ndjson(result):
                    ndjson_lines.append(line)
                    yield line
            finally:
                if ndjson_lines and os.getenv("DISABLE_USAGE_PERSISTENCE", "").lower() != "true":
                    data_str = "".join(ndjson_lines)

                    async def _bg():
                        try:
                            await asyncio.to_thread(insert_user_usage, auth_claims, data_str, "chat")
                        except Exception:
                            logging.exception("Can't insert user usage")

                    asyncio.create_task(_bg())

        response = await make_response(stream_and_record_usage())
        response.timeout = None  # type: ignore
        response.mimetype = "application/json-lines"
        return response
    except Exception as error:
        return error_response(error, "/chat")


# Send MSAL.js settings to the client UI
@bp.route("/auth_setup", methods=["GET"])
def auth_setup():
    auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
    return jsonify(auth_helper.get_auth_setup_for_client())


@bp.get("/admin/llm-providers")
@authenticated
async def admin_list_llm_providers(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify({"providers": [_serialize_llm_provider(item) for item in list_llm_providers()]})


@bp.post("/admin/llm-providers")
@authenticated
async def admin_create_llm_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        provider = insert_llm_provider(_normalize_llm_provider_payload(body or {}))
        _refresh_llm_profile_registry()
        return jsonify(_serialize_llm_provider(provider)), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/llm-providers/<provider_id>")
@authenticated
async def admin_update_llm_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    existing = get_llm_provider(provider_id)
    if not existing:
        return jsonify({"error": "LLM provider not found"}), 404
    try:
        body = await request.get_json()
        normalized = _normalize_llm_provider_payload(body or {}, existing=existing)
        new_model_ids = {model["id"] for model in normalized["models"]}
        removed_model_ids = {
            model["id"] for model in existing.get("models", []) if model["id"] not in new_model_ids
        }
        if removed_model_ids:
            removed_profiles = [managed_profile_id(provider_id, model_id) for model_id in removed_model_ids]
            reference_count = get_database().agents.count_documents(
                {"delete_at": None, "config.llm_profile_id": {"$in": removed_profiles}}
            )
            if reference_count:
                return jsonify(
                    {"error": f"Removed model(s) are used by {reference_count} agent(s)"}
                ), 409
        provider = update_llm_provider(
            provider_id,
            normalized,
        )
        _refresh_llm_profile_registry()
        return jsonify(_serialize_llm_provider(provider))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/llm-providers/<provider_id>")
@authenticated
async def admin_delete_llm_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    provider = get_llm_provider(provider_id)
    if not provider:
        return jsonify({"error": "LLM provider not found"}), 404
    profile_prefix = f"managed:{provider_id}:"
    reference_count = get_database().agents.count_documents(
        {"delete_at": None, "config.llm_profile_id": {"$regex": f"^{re.escape(profile_prefix)}"}}
    )
    if reference_count:
        return jsonify({"error": f"Provider is used by {reference_count} agent(s); disable it instead"}), 409
    soft_delete_llm_provider(provider_id)
    _refresh_llm_profile_registry()
    return jsonify({"success": True})


@bp.post("/admin/llm-providers/<provider_id>/test")
@authenticated
async def admin_test_llm_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    provider = get_llm_provider(provider_id)
    if not provider:
        return jsonify({"error": "LLM provider not found"}), 404
    body = await request.get_json() or {}
    model_id = body.get("model_id")
    model = next(
        (item for item in provider.get("models", []) if not model_id or item["id"] == model_id),
        None,
    )
    if not model:
        return jsonify({"error": "Model not found"}), 404
    client = None
    try:
        settings = _settings_for_managed_model(provider, model)
        client = create_llm_client(settings, current_app.config[CONFIG_CREDENTIAL])
        completion_options: dict[str, Any] = {}
        if settings.model in Approach.GPT_REASONING_MODELS:
            completion_options["max_completion_tokens"] = 16
        else:
            completion_options.update({"max_tokens": 3, "temperature": 0})
        completion_options = apply_llm_vendor_chat_policy(
            infer_llm_vendor(provider).id, completion_options
        )
        response = await client.chat.completions.create(
            model=settings.deployment or settings.model,
            messages=[{"role": "user", "content": "Reply with OK"}],
            **completion_options,
        )
        content = response.choices[0].message.content if response.choices else None
        capability_status, capability_detail = await _probe_model_tool_capability(
            client, settings, provider
        )
        provider = _store_model_tool_capability(
            provider, str(model["id"]), capability_status, capability_detail
        )
        vision_status, vision_detail = await _probe_model_vision_capability(
            client, settings, provider
        )
        provider = _store_model_vision_capability(
            provider, str(model["id"]), vision_status, vision_detail
        )
        try:
            _refresh_llm_profile_registry()
        except Exception:
            current_app.logger.exception(
                "Unable to refresh LLM profiles after tool-capability test"
            )
        updated_model = next(
            (item for item in provider.get("models", []) if item.get("id") == model["id"]),
            model,
        )
        return jsonify(
            {
                "success": True,
                "model": model["model"],
                "response": content,
                "tool_capability": {
                    "status": capability_status,
                    "supports_tools": (
                        True
                        if capability_status == "supported"
                        else False if capability_status == "unsupported" else None
                    ),
                    "detail": capability_detail,
                    "checked_at": updated_model.get("tool_capability_checked_at"),
                },
                "vision_capability": {
                    "status": vision_status,
                    "supports_vision": (
                        True
                        if vision_status == "supported"
                        else False if vision_status == "unsupported" else None
                    ),
                    "detail": vision_detail,
                    "checked_at": updated_model.get("vision_capability_checked_at"),
                },
            }
        )
    except Exception as error:
        current_app.logger.warning("LLM provider connection test failed: %s", error)
        return jsonify({"success": False, "error": str(error)}), 400
    finally:
        if client is not None:
            await client.close()


@bp.get("/admin/mcp-servers")
@authenticated
async def admin_list_mcp_servers(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    servers = []
    for item in list_mcp_servers():
        serialized = serialize_mcp_server(item)
        serialized["agent_usage_count"] = get_database().agents.count_documents(
            {
                "delete_at": None,
                "config.tool_settings.mcp_server_ids": str(item["_id"]),
            }
        )
        servers.append(serialized)
    return jsonify(
        {"servers": servers}
    )


@bp.get("/mcp-servers/available")
@authenticated
async def available_mcp_servers(auth_claims: dict[str, Any]):
    return jsonify(
        {
            "servers": [
                serialize_mcp_server(item)
                for item in list_mcp_servers(enabled_only=True)
            ]
        }
    )


@bp.post("/admin/mcp-servers")
@authenticated
async def admin_create_mcp_server(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json() or {}
        server = insert_mcp_server(normalize_mcp_server_payload(body))
        return jsonify(serialize_mcp_server(server)), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/mcp-servers/<server_id>")
@authenticated
async def admin_update_mcp_server(auth_claims: dict[str, Any], server_id: str):
    _require_system_admin(auth_claims)
    existing = get_mcp_server(server_id)
    if not existing:
        return jsonify({"error": "MCP server not found"}), 404
    try:
        body = await request.get_json() or {}
        server = update_mcp_server(
            server_id, normalize_mcp_server_payload(body, existing=existing)
        )
        return jsonify(serialize_mcp_server(server or existing))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/mcp-servers/<server_id>")
@authenticated
async def admin_delete_mcp_server(auth_claims: dict[str, Any], server_id: str):
    _require_system_admin(auth_claims)
    if not get_mcp_server(server_id):
        return jsonify({"error": "MCP server not found"}), 404
    reference_count = get_database().agents.count_documents(
        {
            "delete_at": None,
            "config.tool_settings.mcp_server_ids": server_id,
        }
    )
    if reference_count:
        return jsonify(
            {"error": f"MCP server is used by {reference_count} agent(s); disable it instead"}
        ), 409
    soft_delete_mcp_server(server_id)
    return jsonify({"success": True})


@bp.post("/admin/mcp-servers/<server_id>/test")
@authenticated
async def admin_test_mcp_server(auth_claims: dict[str, Any], server_id: str):
    _require_system_admin(auth_claims)
    server = get_mcp_server(server_id)
    if not server:
        return jsonify({"error": "MCP server not found"}), 404
    try:
        config = MCPServerConfig(
            server_id=str(server["_id"]),
            name=str(server["name"]),
            url=str(server["url"]),
            headers=decrypt_mcp_headers(server),
            allowed_tools=tuple(server.get("allowed_tools") or ()),
            timeout_seconds=float(server.get("timeout_seconds") or 60),
        )
        tools = await discover_mcp_tools(config)
        return jsonify(
            {
                "success": True,
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                    }
                    for tool in tools
                ],
            }
        )
    except Exception as error:
        current_app.logger.warning("MCP server connection test failed: %s", error)
        return jsonify({"success": False, "error": str(error)}), 400


@bp.get("/admin/agent-audit-events")
@authenticated
async def admin_agent_audit_events(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        events = list_agent_audit_events(
            agent_id=request.args.get("agent_id"),
            run_id=request.args.get("run_id"),
            event_type=request.args.get("event_type"),
            status=request.args.get("status"),
            hours=int(request.args.get("hours") or 24),
            limit=int(request.args.get("limit") or 200),
        )
    except ValueError:
        return jsonify({"error": "hours and limit must be integers"}), 400
    return jsonify({"events": events})


@bp.route("/config", methods=["GET"])
async def config():
    runtime_settings: RuntimeSettings = current_app.config[CONFIG_RUNTIME_SETTINGS]
    llm_profiles: dict[str, LLMProfile] = current_app.config[CONFIG_LLM_PROFILES]
    return jsonify(
        {
            "runtimeMode": runtime_settings.mode.value,
            "agentRuntimeMode": (
                os.getenv("AGENT_RUNTIME_MODE", "per_agent").strip().lower()
                if os.getenv("AGENT_RUNTIME_MODE", "per_agent").strip().lower() in {"legacy", "langgraph"}
                else "per_agent"
            ),
            "llmProvider": runtime_settings.llm.provider.value,
            "embeddingProvider": runtime_settings.embedding.provider.value,
            "llmProfiles": [profile.public_dict() for profile in llm_profiles.values()],
            "showGPT4VOptions": current_app.config[CONFIG_GPT4V_DEPLOYED],
            "showSemanticRankerOption": current_app.config[CONFIG_SEMANTIC_RANKER_DEPLOYED],
            "showQueryRewritingOption": current_app.config[CONFIG_QUERY_REWRITING_ENABLED],
            "showReasoningEffortOption": current_app.config[CONFIG_REASONING_EFFORT_ENABLED],
            "streamingEnabled": current_app.config[CONFIG_STREAMING_ENABLED],
            "defaultReasoningEffort": current_app.config[CONFIG_DEFAULT_REASONING_EFFORT],
            "showVectorOption": current_app.config[CONFIG_VECTOR_SEARCH_ENABLED],
            "showUserUpload": current_app.config[CONFIG_USER_UPLOAD_ENABLED],
            "showLanguagePicker": current_app.config[CONFIG_LANGUAGE_PICKER_ENABLED],
            "showSpeechInput": current_app.config[CONFIG_SPEECH_INPUT_ENABLED],
            "showSpeechOutputBrowser": current_app.config[CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED],
            "showSpeechOutputAzure": current_app.config[CONFIG_SPEECH_OUTPUT_AZURE_ENABLED],
            "showChatHistoryBrowser": current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            "showChatHistoryCosmos": current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
            "showAgenticRetrievalOption": current_app.config[CONFIG_AGENTIC_RETRIEVAL_ENABLED],
            "chatDocumentAttachmentsEnabled": current_app.config.get(CONFIG_CHAT_ATTACHMENT_STORE) is not None,
        }
    )


@bp.route("/speech", methods=["POST"])
async def speech():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415

    speech_token = current_app.config.get(CONFIG_SPEECH_SERVICE_TOKEN)
    if speech_token is None or speech_token.expires_on < time.time() + 60:
        speech_token = await current_app.config[CONFIG_CREDENTIAL].get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        current_app.config[CONFIG_SPEECH_SERVICE_TOKEN] = speech_token

    request_json = await request.get_json()
    text = request_json["text"]
    try:
        # Construct a token as described in documentation:
        # https://learn.microsoft.com/azure/ai-services/speech-service/how-to-configure-azure-ad-auth?pivots=programming-language-python
        auth_token = (
            "aad#"
            + current_app.config[CONFIG_SPEECH_SERVICE_ID]
            + "#"
            + current_app.config[CONFIG_SPEECH_SERVICE_TOKEN].token
        )
        speech_config = SpeechConfig(
            auth_token=auth_token, region=current_app.config[CONFIG_SPEECH_SERVICE_LOCATION])
        speech_config.speech_synthesis_voice_name = current_app.config[
            CONFIG_SPEECH_SERVICE_VOICE]
        speech_config.speech_synthesis_output_format = SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        synthesizer = SpeechSynthesizer(
            speech_config=speech_config, audio_config=None)
        result: SpeechSynthesisResult = synthesizer.speak_text_async(
            text).get()
        if result.reason == ResultReason.SynthesizingAudioCompleted:
            return result.audio_data, 200, {"Content-Type": "audio/mp3"}
        elif result.reason == ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            current_app.logger.error(
                "Speech synthesis canceled: %s %s", cancellation_details.reason, cancellation_details.error_details
            )
            raise Exception(
                "Speech synthesis canceled. Check logs for details.")
        else:
            current_app.logger.error(
                "Unexpected result reason: %s", result.reason)
            raise Exception("Speech synthesis failed. Check logs for details.")
    except Exception as e:
        current_app.logger.exception("Exception in /speech")
        return jsonify({"error": str(e)}), 500
    
def convert_value(value):
    try:
        if "." in value:
            return float(value)
        return value
    except:
        return value
def extract_parameters(text: str):
    lines = text.splitlines()
    params = {}
    is_param_section = False
    for line in lines:
        line = line.strip()
        if line.lower() == "parameters":
            is_param_section = True
            continue
        if is_param_section and line.lower() == "[y/n]":
            break
        if is_param_section and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            value = convert_value(value)
            params[key] = value
    return params


def _mail_binding_response(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in document.items()
        if key not in {"created_at", "updated_at", "delete_at"}
    }


@bp.get("/mail_configs")
@authenticated
async def mail_configs(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "")
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400
    results = []
    for document in list_mail_connections(team_id):
        usage_count = mail_bindings_collection.count_documents(
            {"email_id": str(document["_id"]), "delete_at": None}
        )
        results.append(serialize_mail_connection(document, usage_count=usage_count))
    return jsonify(results)


@bp.post("/insert_mail_config")
@authenticated
async def create_mail_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        normalized = normalize_mail_connection(body)
        if not normalized["team_id"]:
            raise ValueError("team_id is required")
        document = insert_mail_connection(normalized)
        return jsonify({"message": "Mail connection created", "connection": serialize_mail_connection(document)}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/edit_mail_config")
@authenticated
async def edit_mail_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("config_id") or "")
        existing = get_mail_connection(connection_id)
        if not existing:
            return jsonify({"error": "Mail connection not found"}), 404
        document = update_mail_connection(
            connection_id, normalize_mail_connection(body, existing=existing)
        )
        return jsonify({"message": "Mail connection updated", "connection": serialize_mail_connection(document or existing)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/delete_mail_config")
@authenticated
async def remove_mail_config(auth_claims: dict[str, Any]):
    body = await request.get_json()
    connection_id = str(body.get("config_id") or "")
    in_use = mail_bindings_collection.count_documents({"email_id": connection_id, "delete_at": None})
    if in_use:
        return jsonify({"error": f"Connection is assigned to {in_use} Agent(s); remove those bindings first"}), 409
    if not soft_delete_mail_connection(connection_id):
        return jsonify({"error": "Mail connection not found"}), 404
    return jsonify({"message": "Mail connection deleted"})


@bp.post("/test_mail_connection")
@authenticated
async def test_mail_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection = get_mail_connection(str(body.get("connection_id") or body.get("config_id") or ""))
        if not connection:
            raise ValueError("Save the mail connection before testing it")
        result = await test_mail_connection(connection, decrypt_mail_secrets(connection))
        return jsonify(result)
    except (ValueError, OSError) as exc:
        current_app.logger.warning("Mail connection test failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.get("/mail_bindings")
@authenticated
async def mail_bindings(auth_claims: dict[str, Any]):
    agent_id = str(request.args.get("agent_id") or "")
    return jsonify([_mail_binding_response(item) for item in list_mail_bindings(agent_id)])


@bp.post("/insert_mail_binding")
@authenticated
async def create_mail_binding(auth_claims: dict[str, Any]):
    try:
        normalized = normalize_mail_binding(await request.get_json())
        if not normalized["agent_id"] or not get_agent_by_id(normalized["agent_id"]):
            raise ValueError("A valid agent_id is required")
        if not get_mail_connection(normalized["email_id"]):
            raise ValueError("A valid email_id is required")
        existing = mail_bindings_collection.find_one({
            "agent_id": normalized["agent_id"], "email_id": normalized["email_id"], "delete_at": None
        })
        if existing:
            return jsonify({"error": "This mail connection is already assigned to the Agent"}), 409
        document = insert_mail_binding(normalized)
        return jsonify({"message": "Mail binding created", "binding": _mail_binding_response(document)}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/toggle_mail_binding")
@authenticated
async def toggle_mail_binding(auth_claims: dict[str, Any]):
    body = await request.get_json()
    if not update_mail_binding(str(body.get("binding_id") or ""), enabled=body.get("enabled") is True):
        return jsonify({"error": "Mail binding not found or unchanged"}), 404
    return jsonify({"message": "Mail binding updated"})


@bp.post("/update_mail_binding")
@authenticated
async def edit_mail_binding(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        binding_id = str(body.get("binding_id") or "")
        existing = get_mail_binding(binding_id)
        if not existing:
            return jsonify({"error": "Mail binding not found"}), 404
        normalized = normalize_mail_binding({**existing, **body})
        if not get_mail_connection(normalized["email_id"]):
            raise ValueError("A valid email_id is required")
        duplicate = mail_bindings_collection.find_one({
            "_id": {"$ne": binding_id}, "agent_id": normalized["agent_id"],
            "email_id": normalized["email_id"], "delete_at": None,
        })
        if duplicate:
            return jsonify({"error": "This mail connection is already assigned to the Agent"}), 409
        update_mail_binding(binding_id, **normalized)
        return jsonify({"message": "Mail binding updated"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/delete_mail_binding")
@authenticated
async def remove_mail_binding(auth_claims: dict[str, Any]):
    body = await request.get_json()
    if not delete_mail_binding(str(body.get("binding_id") or "")):
        return jsonify({"error": "Mail binding not found"}), 404
    return jsonify({"message": "Mail binding deleted"})


@bp.get("/messaging_connections")
@authenticated
async def messaging_connections(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "")
    results = []
    for item in list_messaging_connections(team_id):
        count = messaging_bindings_collection.count_documents({"connection_id": str(item["_id"]), "delete_at": None})
        results.append(serialize_messaging_connection(item, count))
    return jsonify(results)


@bp.post("/save_messaging_connection")
@authenticated
async def save_messaging_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("connection_id") or "")
        existing = get_messaging_connection(connection_id) if connection_id else None
        normalized = normalize_messaging_connection(body, existing=existing)
        if not normalized["team_id"]: raise ValueError("team_id is required")
        document = update_messaging_connection(connection_id, normalized) if existing else insert_messaging_connection(normalized)
        return jsonify({"message": "Messaging connection saved", "connection": serialize_messaging_connection(document or existing)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/test_messaging_connection")
@authenticated
async def test_messaging_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection = get_messaging_connection(str(body.get("connection_id") or ""))
        if not connection: raise ValueError("Messaging connection not found")
        return jsonify(await test_messaging_connection(connection, decrypt_messaging_secrets(connection)))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.post("/delete_messaging_connection")
@authenticated
async def remove_messaging_connection(auth_claims: dict[str, Any]):
    body = await request.get_json(); connection_id = str(body.get("connection_id") or "")
    if messaging_bindings_collection.count_documents({"connection_id": connection_id, "delete_at": None}):
        return jsonify({"error": "Remove Agent bindings before deleting this connection"}), 409
    if not delete_messaging_connection(connection_id): return jsonify({"error": "Connection not found"}), 404
    return jsonify({"message": "Messaging connection deleted"})


@bp.get("/messaging_bindings")
@authenticated
async def messaging_bindings(auth_claims: dict[str, Any]):
    return jsonify([_mail_binding_response(item) for item in list_messaging_bindings(str(request.args.get("agent_id") or ""))])


@bp.post("/save_messaging_binding")
@authenticated
async def save_messaging_binding(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json(); binding_id = str(body.get("binding_id") or "")
        existing = get_messaging_binding(binding_id) if binding_id else None
        normalized = normalize_messaging_binding({**(existing or {}), **body})
        if not get_agent_by_id(normalized["agent_id"]): raise ValueError("A valid agent_id is required")
        if not get_messaging_connection(normalized["connection_id"]): raise ValueError("A valid connection_id is required")
        duplicate = messaging_bindings_collection.find_one({"_id": {"$ne": binding_id}, "agent_id": normalized["agent_id"], "connection_id": normalized["connection_id"], "delete_at": None})
        if duplicate: return jsonify({"error": "Connection is already assigned to this Agent"}), 409
        document = existing
        if existing: update_messaging_binding(binding_id, normalized)
        else: document = insert_messaging_binding(normalized)
        return jsonify({"message": "Messaging binding saved", "binding": _mail_binding_response(document or normalized)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/delete_messaging_binding")
@authenticated
async def remove_messaging_binding(auth_claims: dict[str, Any]):
    body = await request.get_json()
    if not delete_messaging_binding(str(body.get("binding_id") or "")): return jsonify({"error": "Binding not found"}), 404
    return jsonify({"message": "Messaging binding deleted"})


@bp.get("/document_processing/providers")
@authenticated
async def document_processing_providers(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    ensure_system_providers(bool(os.getenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE")))
    return jsonify([serialize_document_provider(item) for item in list_document_providers()])


@bp.post("/document_processing/providers/save")
@authenticated
async def save_document_processing_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json(); provider_id = str(body.get("provider_id") or "")
        existing = get_document_provider(provider_id) if provider_id else None
        if provider_id and not existing:
            raise ValueError("Document provider not found")
        requested_type = str(body.get("provider_type") or "").strip().lower()
        if not existing and requested_type not in {"docling", "google_document_ai", "generic_ocr_api", "paddleocr"}:
            raise ValueError("Azure and Local Text are system-managed providers")
        if existing and existing.get("system_managed") and requested_type != existing.get("provider_type"):
            raise ValueError("The type of a system-managed provider cannot be changed")
        item = save_document_provider(normalize_document_provider(body, existing), provider_id)
        return jsonify({"message": "Document provider saved", "provider": serialize_document_provider(item)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/document_processing/providers/test")
@authenticated
async def test_document_processing_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    body = await request.get_json(); provider = get_document_provider(str(body.get("provider_id") or ""))
    if not provider: return jsonify({"error": "Provider not found"}), 404
    provider_type = provider.get("provider_type")
    if provider_type == "azure_document_intelligence" and not os.getenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE"):
        return jsonify({"ok": False, "error": "AZURE_DOCUMENTINTELLIGENCE_SERVICE is not configured"}), 400
    try:
        from prepdocslib.documentprocessing import check_document_provider

        message = await check_document_provider(provider)
        return jsonify({"ok": True, "message": message})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.post("/document_processing/providers/delete")
@authenticated
async def remove_document_processing_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    body = await request.get_json(); provider_id = str(body.get("provider_id") or "")
    if any(item.get("provider_id") == provider_id for item in list_document_profiles()):
        return jsonify({"error": "Delete profiles using this provider first"}), 409
    if not delete_document_provider(provider_id): return jsonify({"error": "Provider is system managed or not found"}), 409
    return jsonify({"message": "Document provider deleted"})


@bp.get("/document_processing/profiles")
@authenticated
async def document_processing_profiles(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify([_mail_binding_response(item) for item in list_document_profiles()])


@bp.post("/document_processing/profiles/save")
@authenticated
async def save_document_processing_profile(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        import importlib.util
        body = await request.get_json(); profile_id = str(body.get("profile_id") or "")
        client_request_id = str(body.get("client_request_id") or "").strip()
        profiles = list_document_profiles()
        existing = next((item for item in profiles if str(item.get("_id")) == profile_id), None)
        if profile_id and not existing:
            raise ValueError("Document profile not found")
        if not profile_id and client_request_id:
            try:
                client_request_id = str(uuid.UUID(client_request_id))
            except ValueError as exc:
                raise ValueError("client_request_id must be a valid UUID") from exc
            repeated = next(
                (item for item in profiles if str(item.get("_id")) == client_request_id),
                None,
            )
            if repeated:
                return jsonify({"message": "Document profile saved", "profile": _mail_binding_response(repeated)})
        normalized = normalize_document_profile(body, existing)
        duplicate = next(
            (
                item
                for item in profiles
                if str(item.get("_id")) != profile_id
                and str(item.get("name") or "").strip().casefold()
                == normalized["name"].strip().casefold()
            ),
            None,
        )
        if duplicate:
            return jsonify({"error": "A document profile with this name already exists"}), 409
        provider = get_document_provider(normalized["provider_id"])
        provider_config = (provider or {}).get("config") or {}
        if normalized["is_default"] and provider and provider.get("provider_type") == "docling" and provider_config.get("execution_mode", "service") == "embedded" and importlib.util.find_spec("docling") is None:
            raise ValueError("Install the optional local OCR runtime and pass the provider Test before setting Docling as Default")
        item = save_document_profile(normalized, profile_id, client_request_id)
        return jsonify({"message": "Document profile saved", "profile": _mail_binding_response(item)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/document_processing/profiles/delete")
@authenticated
async def remove_document_processing_profile(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    body = await request.get_json()
    profile_id = str(body.get("profile_id") or "")
    if any(rule.get("profile_id") == profile_id for rule in list_document_routing_rules()):
        return jsonify({"error": "Delete routing rules using this profile first"}), 409
    if not delete_document_profile(profile_id): return jsonify({"error": "Profile not found"}), 404
    return jsonify({"message": "Document profile deleted"})


@bp.get("/document_processing/routing-rules")
@authenticated
async def document_processing_routing_rules(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify([_mail_binding_response(item) for item in list_document_routing_rules()])


@bp.post("/document_processing/routing-rules/save")
@authenticated
async def save_document_processing_routing_rule(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        rule_id = str(body.get("rule_id") or "")
        existing = get_document_routing_rule(rule_id) if rule_id else None
        if rule_id and not existing:
            raise ValueError("Routing rule not found")
        normalized = normalize_document_routing_rule(body, existing)
        item = save_document_routing_rule(normalized, rule_id)
        return jsonify({"message": "Document routing rule saved", "rule": _mail_binding_response(item)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/document_processing/routing-rules/delete")
@authenticated
async def remove_document_processing_routing_rule(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    body = await request.get_json()
    if not delete_document_routing_rule(str(body.get("rule_id") or "")):
        return jsonify({"error": "Routing rule not found"}), 404
    return jsonify({"message": "Document routing rule deleted"})


def _document_route_response(route: dict[str, Any]) -> dict[str, Any]:
    response = {
        "source": route.get("source"),
        "status": route.get("status"),
        "reason": route.get("reason"),
        "candidates": route.get("candidates") or [],
    }
    profile = route.get("profile")
    provider = route.get("provider")
    rule = route.get("rule")
    response["profile"] = _mail_binding_response(profile) if profile else None
    response["provider"] = serialize_document_provider(provider) if provider else None
    response["rule"] = _mail_binding_response(rule) if rule else None
    return response


@bp.post("/document_processing/explain-route")
@authenticated
async def explain_document_processing_route(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        filename = str(body.get("filename") or body.get("file_extension") or "").strip()
        extension = filename.lower() if filename.startswith(".") else Path(filename).suffix.lower()
        if not extension or "/" in extension or "\\" in extension:
            raise ValueError("A filename or file extension is required")
        route = resolve_processing_route(
            file_extension=extension,
            scope=str(body.get("scope") or "personal"),
            team_id=str(body.get("team_id") or ""),
            explicit_profile_id=str(body.get("profile_id") or ""),
        )
        return jsonify(_document_route_response(route))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.get("/document_processing/upload-options")
@authenticated
async def document_processing_upload_options(auth_claims: dict[str, Any]):
    can_override = _is_system_admin(auth_claims)
    profiles = []
    if can_override:
        enabled_provider_ids = {
            str(item.get("_id")) for item in list_document_providers() if item.get("enabled") is not False
        }
        profiles = [
            _mail_binding_response(item)
            for item in list_document_profiles()
            if item.get("enabled") is not False and str(item.get("provider_id")) in enabled_provider_ids
        ]
    return jsonify({"can_override": can_override, "profiles": profiles})


def _required_attachment_uuid(value: object, label: str) -> str:
    if value in (None, ""):
        raise DocumentAttachmentError(f"{label} is required")
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as error:
        raise DocumentAttachmentError(f"{label} must be a valid UUID") from error


async def _rollback_chat_attachment(
    store: AttachmentStore,
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
) -> None:
    try:
        await store.delete(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
    except Exception:
        # The periodic expiry/orphan cleanup is the second line of defense.
        current_app.logger.exception("Unable to roll back Chat attachment object")


@bp.get("/chat/attachments")
@authenticated
async def list_chat_attachments(auth_claims: dict[str, Any]):
    try:
        conversation_id = _required_attachment_uuid(request.args.get("conversation_id"), "conversation_id")
        limit = int(request.args.get("limit") or 20)
    except (DocumentAttachmentError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    items = await asyncio.to_thread(
        list_attachment_metadata,
        owner_id=str(auth_claims["oid"]),
        conversation_id=conversation_id,
        limit=limit,
    )
    return jsonify({"attachments": [serialize_attachment_metadata(item) for item in items]})


@bp.get("/chat/attachments/<attachment_id>/content")
@authenticated
async def get_chat_attachment_content(auth_claims: dict[str, Any], attachment_id: str):
    store: AttachmentStore | None = current_app.config.get(CONFIG_CHAT_ATTACHMENT_STORE)
    if store is None:
        return jsonify({"error": "Private Chat document storage is not enabled"}), 503
    try:
        normalized_attachment_id = _required_attachment_uuid(attachment_id, "attachment_id")
        conversation_id = _required_attachment_uuid(request.args.get("conversation_id"), "conversation_id")
    except DocumentAttachmentError as error:
        return jsonify({"error": str(error)}), 400

    owner_id = str(auth_claims["oid"])
    item = await asyncio.to_thread(
        get_attachment_metadata,
        normalized_attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    if not item or str(item.get("status") or "") != "ready":
        return jsonify({"error": "Document attachment not found"}), 404
    try:
        stored = await store.get(
            normalized_attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
    except (AttachmentAccessError, AttachmentNotFoundError):
        return jsonify({"error": "Document attachment not found"}), 404
    except AttachmentIntegrityError:
        current_app.logger.exception("Private Chat attachment failed integrity validation")
        return jsonify({"error": "Document attachment is temporarily unavailable"}), 503

    response = await send_file(
        BytesIO(stored.content),
        mimetype=stored.record.content_type,
        as_attachment=False,
        attachment_filename=stored.record.filename,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/chat/attachments")
@authenticated
async def upload_chat_attachment(auth_claims: dict[str, Any]):
    store: AttachmentStore | None = current_app.config.get(CONFIG_CHAT_ATTACHMENT_STORE)
    if store is None:
        return jsonify({"error": "Private Chat document storage is not enabled"}), 503

    request_files = await request.files
    request_form = await request.form
    files = request_files.getlist("file")
    if len(files) != 1:
        return jsonify({"error": "Exactly one document file is required"}), 400
    try:
        conversation_id = _required_attachment_uuid(request_form.get("conversation_id"), "conversation_id")
        upload_id = _required_attachment_uuid(
            request_form.get("upload_id") or request.headers.get("Idempotency-Key"),
            "upload_id",
        )
    except DocumentAttachmentError as error:
        return jsonify({"error": str(error)}), 400

    agent_id = str(request_form.get("agent_id") or "").strip()
    if agent_id:
        agent = await asyncio.to_thread(get_agent_by_id, agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404
        if (agent.get("config") or {}).get("document_attachments_enabled", True) is False:
            return jsonify({"error": "Document attachments are disabled for this agent"}), 403

    owner_id = str(auth_claims["oid"])
    existing = await asyncio.to_thread(
        get_attachment_metadata_by_upload_id,
        upload_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    if existing:
        return jsonify({"attachment": serialize_attachment_metadata(existing), "duplicate": True}), 200

    file = files[0]
    max_bytes = min(int(getattr(store, "max_bytes", MAX_DOCUMENT_BYTES)), MAX_DOCUMENT_BYTES)
    content = await asyncio.to_thread(file.read, max_bytes + 1)
    try:
        document = validate_document_attachment(
            filename=file.filename,
            declared_mime=file.mimetype,
            content=content,
            max_bytes=max_bytes,
        )
        scanner: MalwareScanner = current_app.config[CONFIG_CHAT_ATTACHMENT_SCANNER]
        scan_status = await scanner.scan(
            filename=document.filename,
            content_type=document.content_type,
            content=document.content,
        )
        if scan_status not in {"not_configured", "clean"}:
            raise RuntimeError("Malware scanner returned an unsupported status")
    except MalwareDetectedError as error:
        return jsonify({"error": str(error)}), 422
    except DocumentAttachmentError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        current_app.logger.exception("Chat document malware scan failed")
        return jsonify({"error": "Document security scan is temporarily unavailable"}), 503

    try:
        record = await store.put(
            owner_id=owner_id,
            conversation_id=conversation_id,
            filename=document.filename,
            content_type=document.content_type,
            content=document.content,
        )
    except Exception:
        current_app.logger.exception("Unable to write private Chat attachment object")
        return jsonify({"error": "Private document storage is temporarily unavailable"}), 503
    try:
        item = await asyncio.to_thread(
            create_attachment_metadata,
            record,
            storage_backend=store.backend_name,
            storage_key=record.attachment_id,
            upload_id=upload_id,
            page_count=document.page_count,
            scan_status=scan_status,
        )
    except DuplicateKeyError:
        await _rollback_chat_attachment(
            store,
            record.attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        existing = await asyncio.to_thread(
            get_attachment_metadata_by_upload_id,
            upload_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        if existing:
            return jsonify({"attachment": serialize_attachment_metadata(existing), "duplicate": True}), 200
        return jsonify({"error": "Document upload idempotency conflict"}), 409
    except Exception:
        await _rollback_chat_attachment(
            store,
            record.attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        current_app.logger.exception("Unable to save Chat attachment metadata")
        return jsonify({"error": "Unable to save document attachment"}), 500

    _schedule_chat_attachment_extraction(
        record.attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    return jsonify({"attachment": serialize_attachment_metadata(item), "duplicate": False}), 201


@bp.delete("/chat/attachments/<attachment_id>")
@authenticated
async def delete_chat_attachment(auth_claims: dict[str, Any], attachment_id: str):
    store: AttachmentStore | None = current_app.config.get(CONFIG_CHAT_ATTACHMENT_STORE)
    if store is None:
        return jsonify({"error": "Private Chat document storage is not enabled"}), 503
    try:
        normalized_attachment_id = _required_attachment_uuid(attachment_id, "attachment_id")
        request_json = await request.get_json()
        conversation_id = _required_attachment_uuid(
            (request_json or {}).get("conversation_id"),
            "conversation_id",
        )
    except DocumentAttachmentError as error:
        return jsonify({"error": str(error)}), 400

    owner_id = str(auth_claims["oid"])
    item = await asyncio.to_thread(
        get_attachment_metadata,
        normalized_attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    if not item:
        return jsonify({"error": "Document attachment not found"}), 404
    deleted = await asyncio.to_thread(
        soft_delete_attachment_metadata,
        normalized_attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    if not deleted:
        return jsonify({"error": "Document attachment not found"}), 404
    index: AttachmentIndex | None = current_app.config.get(CONFIG_CHAT_ATTACHMENT_INDEX)
    if index:
        try:
            await index.delete_attachment(
                normalized_attachment_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
        except Exception:
            current_app.logger.exception("Unable to delete revoked Chat attachment chunks")
    try:
        await store.delete(
            normalized_attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
    except AttachmentNotFoundError:
        current_app.logger.warning("Chat attachment object was already absent: %s", normalized_attachment_id)
    except Exception:
        current_app.logger.exception("Unable to delete revoked Chat attachment object")
        return jsonify({"error": "Document access was revoked but object cleanup is pending"}), 202
    return "", 204

# ⭐ CHART CAPABILITY: ลบ /generate_chart route เดิมแล้ว
#    chart generation ทำใน /chat/stream flow ผ่าน chart binding ของ agent แทน
#    (เดิมเป็น endpoint เดี่ยวที่ยิง external API แล้วคืนผลลัพธ์ ไม่ใช่การสร้างกราฟจริงๆ)

BACKGROUND_TASKS = set()
ATTACHMENT_EXTRACTION_TASKS: set[asyncio.Task] = set()
INGEST_SEM = asyncio.Semaphore(3)
INGESTION_WORKER_ID = str(uuid.uuid4())


def _file_size(stream: io.BufferedReader) -> int:
    position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(position)
    return size


def _resolve_upload_route(filename: str, routing_context: dict[str, str]) -> dict[str, Any]:
    route = resolve_processing_route(
        file_extension=Path(filename).suffix.lower(),
        scope=routing_context["scope"],
        team_id=routing_context.get("team_id", ""),
        explicit_profile_id=routing_context.get("explicit_profile_id", ""),
    )
    if route.get("status") == "error":
        raise ValueError(str(route.get("reason") or "Document processing route failed"))
    profile = route.get("profile") or {}
    if profile.get("_id"):
        routing_context["resolved_profile_id"] = str(profile["_id"])
    return route


def _schedule_ingestion_job(job_id: str) -> None:
    task = asyncio.create_task(_run_ingestion_job(job_id))
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)


def _schedule_chat_attachment_extraction(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
) -> None:
    store: AttachmentStore = current_app.config[CONFIG_CHAT_ATTACHMENT_STORE]
    index: AttachmentIndex = current_app.config[CONFIG_CHAT_ATTACHMENT_INDEX]
    task = asyncio.create_task(
        _run_chat_attachment_extraction(
            store,
            index,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
    )
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    ATTACHMENT_EXTRACTION_TASKS.add(task)
    task.add_done_callback(ATTACHMENT_EXTRACTION_TASKS.discard)


async def _run_chat_attachment_extraction(
    store: AttachmentStore,
    index: AttachmentIndex,
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
) -> None:
    started = await asyncio.to_thread(
        update_attachment_status,
        attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
        status="extracting",
    )
    if not started:
        return
    try:
        stored = await store.get(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        chunks = await asyncio.to_thread(
            extract_attachment_chunks,
            filename=stored.record.filename,
            content_type=stored.record.content_type,
            content=stored.content,
        )
        chunk_count = await index.replace_attachment(stored.record, chunks)
        completed = await asyncio.to_thread(
            update_attachment_status,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            status="ready",
            chunk_count=chunk_count,
            extracted_characters=sum(len(chunk.text) for chunk in chunks),
        )
        if not completed:
            await index.delete_attachment(
                attachment_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
    except asyncio.CancelledError:
        raise
    except AttachmentExtractionError as error:
        await index.delete_attachment(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        error_code = "ocr_required" if "OCR is required" in str(error) else "extraction_failed"
        await asyncio.to_thread(
            update_attachment_status,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            status="failed",
            error_code=error_code,
        )
    except Exception:
        try:
            await index.delete_attachment(
                attachment_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
        except Exception:
            current_app.logger.exception("Unable to clean partial Chat attachment index")
        await asyncio.to_thread(
            update_attachment_status,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            status="failed",
            error_code="extraction_failed",
        )
        current_app.logger.exception("Chat attachment extraction failed: %s", attachment_id)


async def _set_job_blob_status(job: dict[str, Any], status: str) -> None:
    if job.get("scope") == "personal":
        return
    config_key = CONFIG_GROUP_BLOB_CONTAINER_CLIENT if job.get("scope") == "team" else CONFIG_BLOB_CONTAINER_CLIENT
    container: ContainerClient = current_app.config[config_key]
    blob = container.get_blob_client(str(job["storage_path"]))
    tags = {"status": status}
    if job.get("scope") == "team":
        tags["data_groups"] = "/".join(job.get("data_group_ids") or [])
    try:
        await blob.set_blob_tags(tags=tags)
    except Exception:
        current_app.logger.warning("Unable to update blob status for ingestion job %s", job.get("_id"), exc_info=True)


async def _run_attachment_cleanup(
    store: AttachmentStore,
    index: AttachmentIndex,
    interval_seconds: float,
) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            result = await cleanup_expired_attachments(
                store,
                delete_expired_attachment_metadata,
                index=index,
            )
            if result.deleted_objects or result.deleted_chunks or result.deleted_metadata:
                current_app.logger.info(
                    "Expired Chat attachments removed: objects=%d chunks=%d metadata=%d",
                    result.deleted_objects,
                    result.deleted_chunks,
                    result.deleted_metadata,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            current_app.logger.exception("Unable to clean up expired Chat attachments")


async def _run_ingestion_job(job_id: str) -> None:
    job = await asyncio.to_thread(claim_ingestion_job, job_id, INGESTION_WORKER_ID)
    if not job:
        return

    async def update_stage(status: str) -> None:
        await asyncio.to_thread(
            update_ingestion_job_status,
            job_id,
            status,
            worker_id=INGESTION_WORKER_ID,
        )
        await _set_job_blob_status(job, "InProgress")

    try:
        scope = str(job["scope"])
        if scope == "personal":
            file_system: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
            storage_client = file_system.get_file_client(str(job["storage_path"]))
            downloader = await storage_client.download_file()
            acls = {"oids": [str(job["owner_id"])]}
            folder = ""
        else:
            config_key = CONFIG_GROUP_BLOB_CONTAINER_CLIENT if scope == "team" else CONFIG_BLOB_CONTAINER_CLIENT
            container: ContainerClient = current_app.config[config_key]
            storage_client = container.get_blob_client(str(job["storage_path"]))
            downloader = await storage_client.download_blob()
            acls = {"oids": [], "groups": list(job.get("data_group_ids") or [])}
            folder = os.path.dirname(str(job["storage_path"]))
            folder = folder + os.sep if folder else ""

        data = await downloader.readall()
        stream = BytesIO(data)
        stream.name = str(job["filename"])
        ingester: UploadUserFileStrategy = current_app.config[CONFIG_INGESTER]
        async with INGEST_SEM:
            if scope == "personal":
                is_docintel, count = await ingester.add_file(
                    File(content=stream, acls=acls, url=storage_client.url),
                    routing_context=job.get("routing_context") or {},
                    status_callback=update_stage,
                )
            else:
                is_docintel, count = await ingester.add_global_file(
                    File(content=stream, acls=acls, url=storage_client.url),
                    folder,
                    routing_context=job.get("routing_context") or {},
                    status_callback=update_stage,
                )
            if is_docintel:
                usage_scope = "personal" if scope == "personal" else ("team" if scope == "team" else "public")
                insert_docintel_usage(str(job.get("owner_name") or ""), str(job.get("team_id") or ""), usage_scope, count)
        await asyncio.to_thread(
            update_ingestion_job_status,
            job_id,
            "indexed",
            worker_id=INGESTION_WORKER_ID,
        )
        await _set_job_blob_status(job, "Pass")
    except Exception as error:
        current_app.logger.exception("Ingestion job %s failed", job_id)
        await asyncio.to_thread(
            update_ingestion_job_status,
            job_id,
            "failed",
            error=error,
            worker_id=INGESTION_WORKER_ID,
        )
        await _set_job_blob_status(job, "Failed")


async def _recover_ingestion_jobs() -> None:
    while True:
        try:
            jobs = await asyncio.to_thread(list_recoverable_ingestion_jobs)
            for job in jobs:
                _schedule_ingestion_job(str(job["_id"]))
        except Exception:
            current_app.logger.exception("Unable to recover persistent ingestion jobs")
        await asyncio.sleep(30)


@bp.get("/ingestion-jobs")
@authenticated
async def ingestion_jobs(auth_claims: dict[str, Any]):
    scope = str(request.args.get("scope") or "").strip().lower()
    if scope and scope not in {"personal", "team", "global"}:
        return jsonify({"error": "scope must be personal, team or global"}), 400
    team_id = str(request.args.get("team_id") or "").strip()
    try:
        limit = int(request.args.get("limit") or 20)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    jobs = list_ingestion_jobs(str(auth_claims["oid"]), scope=scope, team_id=team_id, limit=limit)
    return jsonify({"jobs": [serialize_ingestion_job(job) for job in jobs]})


@bp.post("/ingestion-jobs/<job_id>/retry")
@authenticated
async def retry_ingestion_job(auth_claims: dict[str, Any], job_id: str):
    job = restart_failed_ingestion_job(job_id, str(auth_claims["oid"]))
    if not job:
        return jsonify({"error": "Failed ingestion job not found"}), 404
    _schedule_ingestion_job(job_id)
    return jsonify({"message": "Ingestion retry submitted", "job": serialize_ingestion_job(job)}), 202


@bp.post("/upload")
@authenticated
async def upload(auth_claims: dict[str, Any]):
    request_files = await request.files
    request_form = await request.form
    if "file" not in request_files:
        return jsonify({"message": "No file part in the request", "status": "failed"}), 400

    user_oid = str(auth_claims["oid"])
    user_name = str(auth_claims["preferred_username"])
    explicit_profile_id = str(request_form.get("processing_profile_id") or "").strip()
    if explicit_profile_id:
        _require_system_admin(auth_claims)
    file = request_files.getlist("file")[0]
    routing_context = {
        "scope": "personal",
        "team_id": "",
        "user_id": user_oid,
        "explicit_profile_id": explicit_profile_id,
    }
    try:
        route = _resolve_upload_route(file.filename, routing_context)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    user_file_system: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    user_directory = user_file_system.get_directory_client(user_oid)
    try:
        await user_directory.get_directory_properties()
    except ResourceNotFoundError:
        current_app.logger.info("Creating directory for user %s", user_oid)
        await user_directory.create_directory()
    await user_directory.set_access_control(owner=user_oid)
    file_client = user_directory.get_file_client(file.filename)
    file_io = io.BufferedReader(file)
    size = _file_size(file_io)
    await file_client.upload_data(file_io, overwrite=True, metadata={"UploadedBy": user_oid})
    job = create_ingestion_job(
        owner_id=user_oid,
        owner_name=user_name,
        scope="personal",
        filename=file.filename,
        storage_path=f"{user_oid}/{file.filename}",
        file_size=size,
        routing_context=routing_context,
        route=route,
    )
    _schedule_ingestion_job(str(job["_id"]))
    return jsonify({"message": "Upload accepted for processing", "jobs": [serialize_ingestion_job(job)]}), 202


@bp.post("/delete_uploaded")
@authenticated
async def delete_uploaded(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    filename = request_json.get("filename")
    user_oid = auth_claims["oid"]
    user_blob_container_client: FileSystemClient = current_app.config[
        CONFIG_USER_BLOB_CONTAINER_CLIENT]
    user_directory_client = user_blob_container_client.get_directory_client(
        user_oid)
    file_client = user_directory_client.get_file_client(filename)
    await file_client.delete_file()
    ingester = current_app.config[CONFIG_INGESTER]
    await ingester.remove_file(filename, user_oid)
    return jsonify({"message": f"File {filename} deleted successfully"}), 200

@bp.post("/global_upload")
@authenticated
async def global_upload(auth_claims: dict[str, Any]):
    request_files = await request.files
    request_form = await request.form
    if "file" not in request_files:
        # If no files were included in the request, return an error response
        return jsonify({"message": "No file part in the request", "status": "failed"}), 400

    user_oid = str(auth_claims["oid"])
    user_name = str(auth_claims["preferred_username"])
    explicit_profile_id = str(request_form.get("processing_profile_id") or "").strip()
    if explicit_profile_id:
        _require_system_admin(auth_claims)
    # file = request_files.getlist("file")[0]
    container_client: ContainerClient = current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]

    existing_files: dict[str, int] = {}
    async for blob in container_client.list_blobs():
        filename = str(blob.name).split("/")[-1]
        existing_files[filename] = blob.size

    jobs = []
    for file in request_files.getlist("file"):
        new_filename = (file.filename).split("/")[-1]
        blob_path = f"{file.filename}"
        blob_client: BlobClient = container_client.get_blob_client(blob_path)
        file_io = io.BufferedReader(file)
        size = _file_size(file_io)
        routing_context = {
            "scope": "global",
            "team_id": "",
            "user_id": user_oid,
            "explicit_profile_id": explicit_profile_id,
        }
        try:
            route = _resolve_upload_route(file.filename, routing_context)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        await blob_client.upload_blob(file_io, overwrite=True, metadata={"UploadedBy": user_oid})
        job = create_ingestion_job(
            owner_id=user_oid,
            owner_name=user_name,
            scope="global",
            filename=file.filename,
            storage_path=blob_path,
            file_size=size,
            routing_context=routing_context,
            route=route,
        )
        if new_filename in existing_files and size == existing_files[new_filename]:
            update_ingestion_job_status(str(job["_id"]), "indexed", result_message="Duplicate file already exists")
            await blob_client.set_blob_tags(tags={"status": "Duplicate"})
            job = get_ingestion_job(str(job["_id"])) or job
        else:
            await blob_client.set_blob_tags(tags={"status": "Pending"})
            _schedule_ingestion_job(str(job["_id"]))
        jobs.append(serialize_ingestion_job(job))
    return jsonify({"message": "Upload accepted for processing", "jobs": jobs}), 202


@bp.post("/team_upload")
@authenticated
async def teams_upload(auth_claims: dict[str, Any]):
    request_files = await request.files
    request_form = await request.form

    if "file" not in request_files:
        # If no files were included in the request, return an error response
        return jsonify({"message": "No file part in the request", "status": "failed"}), 400
    user_oid = auth_claims["oid"]
    team_id = request_form.get("team_id")
    data_groups_id = request_form.get("data_groups_id")
    try:
        data_groups_list = json.loads(data_groups_id or "[]")
    except json.JSONDecodeError:
        return jsonify({"error": "data_groups_id must be a JSON array"}), 400
    if not isinstance(data_groups_list, list) or not all(isinstance(item, str) for item in data_groups_list):
        return jsonify({"error": "data_groups_id must be a JSON array of IDs"}), 400
    data_groups_tag = "/".join(data_groups_list)
    user_name = str(auth_claims["preferred_username"])
    explicit_profile_id = str(request_form.get("processing_profile_id") or "").strip()
    if explicit_profile_id:
        _require_system_admin(auth_claims)
    # file = request_files.getlist("file")[0]
    container_client: ContainerClient = current_app.config[CONFIG_GROUP_BLOB_CONTAINER_CLIENT]

    jobs = []
    for file in request_files.getlist("file"):

        blob_path = f"{str(team_id)}/{file.filename}"
        blob_client: BlobClient = container_client.get_blob_client(blob_path)
        file_io = io.BufferedReader(file)
        size = _file_size(file_io)
        routing_context = {
            "scope": "team",
            "team_id": str(team_id or ""),
            "user_id": str(user_oid),
            "explicit_profile_id": explicit_profile_id,
        }
        try:
            route = _resolve_upload_route(file.filename, routing_context)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        await blob_client.upload_blob(file_io, overwrite=True, metadata={"UploadedBy": user_oid})
        await blob_client.set_blob_tags(tags={"status": "Pending", "data_groups": data_groups_tag})
        job = create_ingestion_job(
            owner_id=str(user_oid),
            owner_name=user_name,
            scope="team",
            team_id=str(team_id or ""),
            data_group_ids=data_groups_list,
            filename=file.filename,
            storage_path=blob_path,
            file_size=size,
            routing_context=routing_context,
            route=route,
        )
        _schedule_ingestion_job(str(job["_id"]))
        jobs.append(serialize_ingestion_job(job))
    return jsonify({"message": "Upload accepted for processing", "jobs": jobs}), 202


@bp.post("/global_delete_uploaded")
@authenticated
async def global_delete_uploaded(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    filename = request_json.get("filename")
    print(filename)
    container_client: ContainerClient = current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]
    blob_path = f"{filename}"
    blob_client = container_client.get_blob_client(blob_path)
    await blob_client.delete_blob()
    ingester = current_app.config[CONFIG_INGESTER]
    await ingester.remove_global_file(filename)
    return jsonify({"message": f"File {filename} deleted successfully"}), 200


@bp.post("/team_delete_uploaded")
@authenticated
async def team_delete_uploaded(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    filename = request_json.get("filename")
    tid = request_json.get("team_id")
    print(filename)
    container_client: ContainerClient = current_app.config[CONFIG_GROUP_BLOB_CONTAINER_CLIENT]
    blob_path = f"{tid}/{filename}"
    blob_client = container_client.get_blob_client(blob_path)
    tag_resp = await blob_client.get_blob_tags()
    data_groups_id_list = str(tag_resp['data_groups']).split("/")
    await blob_client.delete_blob()
    ingester = current_app.config[CONFIG_INGESTER]
    for data_group_id in data_groups_id_list:
        await ingester.remove_groups_file(blob_path, str(data_group_id))
    return jsonify({"message": f"File {filename} deleted successfully"}), 200


@bp.get("/list_uploaded")
@authenticated
async def list_uploaded(auth_claims: dict[str, Any]):
    user_oid = auth_claims["oid"]
    user_blob_container_client: FileSystemClient = current_app.config[
        CONFIG_USER_BLOB_CONTAINER_CLIENT]
    files = []
    try:
        all_paths = user_blob_container_client.get_paths(path=user_oid)
        async for path in all_paths:
            files.append([path.name.split("/", 1)[1],
                         int(path.content_length)])
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing uploaded files", error)
    storage_paths = [f"{user_oid}/{item[0]}" for item in files]
    try:
        indexed_times = await asyncio.to_thread(
            latest_indexed_times,
            "personal",
            storage_paths,
            owner_id=str(user_oid),
        )
    except Exception:
        current_app.logger.exception("Unable to load Personal file indexing times")
        indexed_times = {}
    files = [item + [indexed_times.get(f"{user_oid}/{item[0]}")] for item in files]
    return jsonify(files), 200


@bp.post("/list_team_uploaded")
@authenticated
async def list_team_uploaded(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    user_blob_container_client: FileSystemClient = current_app.config[
        CONFIG_GROUP_BLOB_CONTAINER_CLIENT]
    files = []
    tid = request_json.get("team_id")
    try:
        async for blob in user_blob_container_client.list_blobs():
            blob_client = user_blob_container_client.get_blob_client(blob.name)
            tag_resp = await blob_client.get_blob_tags()
            if str(blob.name).startswith(str(tid)):
                data_groups_id_list = str(tag_resp['data_groups']).split("/")
                data_groups_list = []
                for data_group_id in data_groups_id_list:
                    data_group = get_data_group_by_id(data_group_id)
                    data_groups_list.append(data_group["name"])
                files.append([str(blob.name).replace(
                    f"{tid}/", ""), tag_resp['status'], blob['last_modified'].isoformat() if 'last_modified' in blob else None, int(blob.size), data_groups_list])
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing uploaded files", error)
    storage_paths = [f"{tid}/{item[0]}" for item in files]
    try:
        indexed_times = await asyncio.to_thread(
            latest_indexed_times,
            "team",
            storage_paths,
            team_id=str(tid or ""),
        )
    except Exception:
        current_app.logger.exception("Unable to load Team file indexing times")
        indexed_times = {}
    files = [item + [indexed_times.get(f"{tid}/{item[0]}")] for item in files]
    return jsonify(files), 200


@bp.get("/list_global_uploaded")
@authenticated
async def list_global_uploaded(auth_claims: dict[str, Any]):
    user_blob_container_client: FileSystemClient = current_app.config[
        CONFIG_BLOB_CONTAINER_CLIENT]
    files = []
    try:
        async for blob in user_blob_container_client.list_blobs():
            blob_client = user_blob_container_client.get_blob_client(blob.name)
            tag_resp = await blob_client.get_blob_tags()
            files.append([blob.name, tag_resp['status'], blob['last_modified'].isoformat(
            ) if 'last_modified' in blob else None, int(blob.size)])
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing uploaded files", error)
    try:
        indexed_times = await asyncio.to_thread(
            latest_indexed_times,
            "global",
            [str(item[0]) for item in files],
        )
    except Exception:
        current_app.logger.exception("Unable to load Global file indexing times")
        indexed_times = {}
    files = [item + [indexed_times.get(str(item[0]))] for item in files]
    return jsonify(files), 200

PER_FILE_CONC = 3
FILES_CONCURRENT = 48


async def upload_path(data: str, blob_name: str, metadata: dict, gid=None, data_groups_id=None):
    if gid:
        user_blob_container_client = current_app.config[CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT]
        blob_name = f"{gid}/{blob_name}"
    else:
        user_blob_container_client = current_app.config[CONFIG_WEB_BLOB_CONTAINER_CLIENT]
    async for blob in user_blob_container_client.list_blobs():
        if str(blob.name).split("||")[-1] == blob_name.split("||")[-1]:
            return True
    ingester: UploadUserFileStrategy = current_app.config[CONFIG_INGESTER]
    blob = user_blob_container_client.get_blob_client(blob_name)
    # ใช้ to_thread เปิดไฟล์ เพื่อไม่บล็อค event loop
    delay = 1.0
    for attempt in range(6):
        try:
            await blob.upload_blob(
                data.encode("utf-8"), overwrite=True, metadata=metadata,
                max_concurrency=PER_FILE_CONC,
            )
            buf = NamedBytesIO(data.encode("utf-8"), blob_name)
            folder = os.path.dirname(str(blob_name).replace(
                str(blob_name).split("/")[-1], ""))
            folder = folder + os.sep if folder else ""
            if gid:
                await blob.set_blob_tags(tags={"data_groups": "/".join(data_groups_id)})
                buf.seek(0)
                await ingester.add_global_file(File(content=buf, acls={"groups": data_groups_id, "oids": []}, url=blob.url), folder)
            else:
                buf.seek(0)
                await ingester.add_global_file(File(content=buf, acls={"oids": []}, url=blob.url), folder)
            return True
        except ResourceExistsError:
            return True  # ถ้าไม่ overwrite ก็ข้ามได้
        except (ServiceResponseError, TimeoutError, OSError) as e:
            if attempt == 5:
                return False
            await asyncio.sleep(delay + random.random() * 0.2)
            delay = min(delay * 2, 20)


async def upload_many(paths, folder, user_oid: str, gid=None, data_groups_id=None):

    sem = asyncio.Semaphore(FILES_CONCURRENT)
    done = 0

    async def worker(p):
        nonlocal done
        nonlocal folder
        async with sem:
            if gid:
                ok = await upload_path(
                    p[1],
                    f"{folder}/{p[0]}",
                    {"UploadedBy": user_oid},
                    gid,
                    data_groups_id
                )
            else:
                ok = await upload_path(
                    p[1],
                    f"{folder}/{p[0]}",
                    {"UploadedBy": user_oid}
                )
            done += 1
            if done % 100 == 0:
                print(f"progress: {done}/{len(paths)}")
            return (f"{folder}/{p[0]}", ok)

    tasks = [asyncio.create_task(worker(p)) for p in paths]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


@bp.post("/scrape")
@authenticated
async def scrape_website(auth_claims: dict[str, Any]):
    try:
        data = await request.get_json()
        user_oid = auth_claims["oid"]
        start_url = data.get('url', None)
        tid = data.get('team_id', None)
        data_groups_id = data.get('data_groups_id', None)
        folder_name = start_url.replace("/", "_")

        if not start_url:
            return jsonify({"error": "Missing 'url' in payload"}), 400

        result, files = await asyncio.to_thread(run_scraping_job, start_url)
        if tid:
            await upload_many(files, folder_name, user_oid, tid, data_groups_id)
        else:
            await upload_many(files, folder_name, user_oid)
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.exception(
            "An error occurred during the scraping process")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.get("/list_web_contents")
@authenticated
async def list_web_contents(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    team_id = request.args.get("team_id")
    if team_id:
        user_blob_container_client: FileSystemClient = current_app.config[
            CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT]
    else:
        user_blob_container_client: FileSystemClient = current_app.config[
            CONFIG_WEB_BLOB_CONTAINER_CLIENT]
    files = []
    try:
        async for blob in user_blob_container_client.list_blobs():
            if team_id:
                if str(blob.name).startswith(str(team_id)):
                    blob_client = user_blob_container_client.get_blob_client(
                        blob.name)
                    tag_resp = await blob_client.get_blob_tags()
                    groups_id_list = str(tag_resp["data_groups"]).split("/")
                    group_list = []
                    for group_id in groups_id_list:
                        data_group = get_data_group_by_id(group_id)
                        group_list.append(data_group["name"])
                    files.append([str(blob.name).replace(
                        f"{team_id}/", "").split("/")[0].replace("_", "/"), group_list])
                    seen = set()
                    result = []
                    for key, names in files:
                        item = (key, tuple(names))
                        if item not in seen:
                            seen.add(item)
                            result.append([key, names])
                    files = result
            else:
                files.append(str(blob.name))
                files = list(
                    {p.split("/")[0].replace("_", "/") for p in files})
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing web contents", error)
    return jsonify(files), 200


async def delete_path(data: str, gid=None):
    if gid:
        container_client: ContainerClient = current_app.config[CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT]
    else:
        container_client: ContainerClient = current_app.config[CONFIG_WEB_BLOB_CONTAINER_CLIENT]
    ingester = current_app.config[CONFIG_INGESTER]
    blob_client = container_client.get_blob_client(data)
    # ใช้ to_thread เปิดไฟล์ เพื่อไม่บล็อค event loop
    delay = 1.0
    for attempt in range(6):
        try:
            if gid:
                tag_resp = await blob_client.get_blob_tags()
                data_groups = tag_resp["data_groups"].split("/")
                await blob_client.delete_blob()
                for data_group in data_groups:
                    await ingester.remove_groups_file(data, data_group)
            else:
                await ingester.remove_global_file(data)
            return True
        except ResourceExistsError:
            return True  # ถ้าไม่ overwrite ก็ข้ามได้
        except (ServiceResponseError, TimeoutError, OSError) as e:
            if attempt == 5:
                return False
            await asyncio.sleep(delay + random.random() * 0.2)
            delay = min(delay * 2, 20)


async def delete_many(paths, gid=None):

    sem = asyncio.Semaphore(FILES_CONCURRENT)
    done = 0

    async def worker(p):
        nonlocal done
        async with sem:
            if gid:
                ok = await delete_path(p, gid)
            else:
                ok = await delete_path(p)
            done += 1
            if done % 100 == 0:
                print(f"progress: {done}/{len(paths)}")
            return ("p", ok)

    tasks = [asyncio.create_task(worker(p)) for p in paths]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


@bp.post("/delete_web_content")
@authenticated
async def delete_web_content(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    in_url = request_json.get("url")
    team_id = request_json.get("team_id")
    url = str(in_url).replace("/", "_")
    if team_id:
        container_client: ContainerClient = current_app.config[CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT]
    else:
        container_client: ContainerClient = current_app.config[CONFIG_WEB_BLOB_CONTAINER_CLIENT]
    try:
        files = []
        async for blob in container_client.list_blobs():
            if url == str(blob.name).split("/")[1 if team_id else 0]:
                files.append(blob.name)
                # blob_client = container_client.get_blob_client(blob.name)
                # await blob_client.delete_blob()
                # await ingester.remove_global_file(blob.name)
        if team_id:
            await delete_many(files, team_id)
        else:
            await delete_many(files)
    except Exception as error:
        current_app.logger.exception("Error to delete web content", error)
    return jsonify({"message": f"url {in_url} deleted successfully"}), 200


@bp.get("/list_roles")
@authenticated
async def list_roles(auth_claims: dict[str, Any]):
    try:
        roles = get_all_roles()
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing roles", error)
    return jsonify(roles), 200


@bp.post("/update_fixed_prompt")
async def modify_prompt():
    db = get_database()
    request_json = await request.get_json()
    prompt_id = request_json.get("prompt_id")
    prompt = request_json.get("prompt")

    try:
        update_data = {
            "updated_at": datetime.utcnow(),
            "fixed_prompt": prompt,
        }

        result = db.fixed_prompt.update_one(
            {"_id": prompt_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            return jsonify({"warning": "No prompt updated"}), 200

    except Exception as error:
        current_app.logger.exception("Error to update prompt", error)
        return jsonify({"error": "update prompt failed"}), 500

    return jsonify("update prompt success"), 200


@bp.get("/fixed_prompt")
@authenticated
async def get_fixed_prompt(auth_claims: dict[str, Any]):
    db = get_database()
    try:
        prompt_collection = db["fixed_prompt"]
        prompts = list(prompt_collection.find({"delete_at": None}))
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing groups", error)
    return jsonify(prompts[0]), 200


@bp.get("/get_usage")
@authenticated
async def get_usage(auth_claims: dict[str, Any]):
    try:
        usages = get_all_usage()
        users = get_all_users()
        
        user_map = {}
        for u in users:
            if u.get("_id"):
                user_map[str(u["_id"])] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                
        for usage in usages:
            if usage.get("user") and usage["user"].get("_id"):
                uid = str(usage["user"]["_id"])
                if uid in user_map:
                    usage["user"]["name"] = user_map[uid]

        data = {
            "data": usages,
            "total_chunk": int(current_app.config[CONFIG_SEARCH_INDEX_CLIENT]['document_count']),
            "total_size": int(current_app.config[CONFIG_SEARCH_INDEX_CLIENT]['storage_size'])
        }
        return jsonify(data), 200
    except Exception as error:
        current_app.logger.exception("Error to get uasge", error)
        return jsonify({"error": "Error to get uasge"}), 500


@bp.get("/get_docintel_usage")
@authenticated
async def get_docintel_usage(auth_claims: dict[str, Any]):
    try:
        usages = get_all_docintel_usage()
        users = get_all_users()
        
        user_map = {}
        for u in users:
            if u.get("ad_email"):
                user_map[u["ad_email"]] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                
        for usage in usages:
            if usage.get("user") in user_map:
                usage["user"] = user_map[usage["user"]]

        data = {
            "data": usages
        }
        return jsonify(data), 200
    except Exception as error:
        current_app.logger.exception("Error to get uasge", error)
        return jsonify({"error": "Error to get uasge"}), 500


@bp.post("/add_feedback_page")
@authenticated
async def add_feedback_page(auth_claims: dict[str, Any]):
    try:
        request_form = await request.form
        request_files = await request.files
        request_user = request_form.get("user")
        request_feedback = request_form.get("comment")
        insert_feedback(request_user, request_feedback, request_files)
        return jsonify({"message": "Create feedback successfully"}), 200
    except Exception as error:
        current_app.logger.exception(
            "Error creating feedback page", exc_info=error)
        return jsonify({"error": "creating feedback page failed"}), 500


@bp.get("/get_all_feedback_page")
@authenticated
async def get_all_feedback_page(auth_claims: dict[str, Any]):
    try:
        feedback = get_all_feedback()
        users = get_all_users()

        user_map = {}
        for u in users:
            if u.get("_id"):
                user_map[str(u["_id"])] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()

        for fb in feedback:
            if fb.get("user") and fb["user"].get("_id"):
                uid = str(fb["user"]["_id"])
                if uid in user_map:
                    fb["user"]["name"] = user_map[uid]

        data = {
            "data": feedback
        }
        return jsonify(data), 200
    except Exception as error:
        current_app.logger.exception("Error to get uasge", error)
        return jsonify({"error": "Error to get uasge"}), 500


@bp.post("/feedbacks")
@authenticated
async def feedbacks(auth_claims: dict[str, Any]):
    try:
        db = get_database()
        data = await request.get_json(silent=True) or {}

        # ตรวจค่าบังคับ
        _require_fields(data, ["sentiment", "question_text", "answer_text"])
        if data["sentiment"] not in ("like", "dislike"):
            return jsonify({"error": "sentiment must be 'like' or 'dislike'"}), 400

        user_id = auth_claims.get("oid") or auth_claims.get("sub")
        username = auth_claims.get("name") or auth_claims.get(
            "preferred_username") or ""

        # คีย์ธรรมชาติของ feedback ต่อ “คำตอบหนึ่งใน session หนึ่ง ต่อผู้ใช้หนึ่ง”
        key = {
            "session_state": data.get("session_state"),
            "answer_index": data.get("answer_index"),
            "user.id": user_id,
        }

        now = datetime.now(timezone.utc)

        # upsert: ถ้ามีอยู่แล้ว → อัปเดต sentiment/ข้อความ; ถ้าไม่มีก็ insert
        result = db.answer_feedback.update_one(
            filter=key,
            update={
                # สร้างครั้งแรก
                "$setOnInsert": {
                    "_id": str(uuid.uuid4()),
                    "create_at": now,           # ✅ สะกดตามมาตรฐาน
                    "delete_at": None,
                    "user": {"id": user_id, "name": username},
                },
                # อัปเดตทุกครั้ง (และครั้งแรกด้วย)
                "$set": {
                    "update_at": now,
                    "sentiment": data["sentiment"],
                    "question_text": data["question_text"],
                    "answer_text": data["answer_text"],
                    "session_state": data.get("session_state"),
                    "answer_index": data.get("answer_index"),
                    "agent_name": data.get("agent_name"),
                    "metadata": data.get("metadata") or {},
                },
            },
            upsert=True,
        )

        # บอก caller ว่ามัน insert ใหม่หรืออัปเดต
        ok_payload = {
            "ok": True,
            "upserted": bool(getattr(result, "upserted_id", None)),
        }
        # คืน _id เฉพาะเคส insert ใหม่ (ถ้าอยากคืนทุกเคส ให้ find_one หลังอัปเดต)
        if getattr(result, "upserted_id", None):
            ok_payload["id"] = str(result.upserted_id)

        return jsonify(ok_payload), 201 if getattr(result, "upserted_id", None) else 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as error:
        current_app.logger.exception(
            "Error creating/updating feedback", exc_info=error)
        return jsonify({"error": "create/update feedback failed"}), 500


@bp.delete("/feedbacks")
@authenticated
async def delete_feedback(auth_claims: dict[str, Any]):
    db = get_database()
    try:
        session_state = request.args.get("session_state")
        answer_index = request.args.get("answer_index", type=int)

        if not session_state or answer_index is None:
            return jsonify({"error": "session_state and answer_index are required"}), 400
        result = db.feedback_db.delete_one({
            "session_state": session_state,
            "answer_index": answer_index
        })
        return jsonify({"ok": True, "deleted": result.deleted_count}), 200

    except Exception as error:
        current_app.logger.exception("Error deleting feedback", exc_info=error)
        return jsonify({"error": "delete feedback failed"}), 500


def serialize_agent(doc: Dict[str, Any]) -> Dict[str, Any]:
    """แปลง Mongo document เป็น JSON-friendly"""
    return {
        "_id": str(doc.get("_id")),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "is_active": doc.get("is_active", True),
        "temperature": doc.get("temperature"),
        "seed": doc.get("seed"),
        "min_search_score": doc.get("min_search_score"),
        "max_search_results": doc.get("max_search_results"),
        "max_tokens": doc.get("max_tokens"),
        "groups": doc.get("groups", []),
        "create_at": doc.get("create_at").isoformat() if doc.get("create_at") else None,
        "update_at": doc.get("update_at").isoformat() if doc.get("update_at") else None,
        "delete_at": doc.get("delete_at").isoformat() if doc.get("delete_at") else None,
    }


def to_bytes(value: float, unit: str) -> int:
    unit = unit.upper()

    if unit == "KB":
        return int(value * 1024)
    elif unit == "MB":
        return int(value * 1024 * 1024)
    elif unit == "GB":
        return int(value * 1024 * 1024 * 1024)
    elif unit == "TB":
        return int(value * 1024 * 1024 * 1024 * 1024)
    else:
        raise ValueError(f"Unsupported unit: {unit}")


def parse_size(size_str: str) -> int:
    match = re.match(r"([\d.]+)\s*(KB|MB|GB|TB)",
                     size_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")

    value, unit = match.groups()
    return to_bytes(float(value), unit.upper())


@bp.post("/limit_size_conf")
async def create_limit_size_conf():
    db = get_database()
    try:
        body = await request.get_json()

        # set default values when missing
        size_personal = body.get("personal", "1GB")
        size_group = body.get("group", "1GB")
        size_global = body.get("global", "1GB")

        now = datetime.now(timezone.utc)
        limit_conf = db["limit_size_config"]

        doc = {
            "_id": str(uuid.uuid4()),
            "name": "Limit Size Config",
            "size_limit_personal": parse_size(size_personal),
            "size_limit_group": parse_size(size_group),
            "size_limit_global": parse_size(size_global),
            "create_at": now,
            "update_at": now,
            "delete_at": None,
        }

        data = limit_conf.insert_one(doc)

    except Exception as error:
        current_app.logger.exception("Error saving limit config", error)
        return jsonify({"error": str(error)}), 400

    return jsonify({"result": str(data.inserted_id)}), 200


@bp.get("/limit_size_conf")
@authenticated
async def limit_size_conf(auth_claims: dict[str, Any]):
    try:
        limit_confs = get_all_limit_size_configs()
        data = limit_confs[0]
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error get limit config", error)
    return jsonify(data), 200


@bp.post("/delete_all_search_document")
async def delete_all_search_document():
    try:
        total_deleted = 0
        search_client = current_app.config[CONFIG_SEARCH_CLIENT]
        max_rounds = 100000
        key_field = 'id'
        count = await search_client.get_document_count()
        print(f"Found {count} documents in indexes")
        for round_no in range(1, max_rounds + 1):
            results = await search_client.search(search_text="*", select=[key_field, "sourcefile", "groups", "sourcepage", "content"], top=1000)
            batch = []
            async for i in results:
                if i['sourcefile'].startswith("9e2fa6ed-769b-4809-84e8-8c1636c08f2b/C220-Part0e"):
                    print(
                        f"page: {i['sourcepage']}, content: {i['sourcefile']}\n\n")
                    batch.append({key_field: i[key_field]})
            # batch = [{key_field: doc[key_field]} async for doc in results]
            await search_client.delete_documents(documents=batch)
            total_deleted += len(batch)
            if batch:
                break
            await asyncio.sleep(0.2)
        return jsonify({"success": f"Delete {total_deleted} documents in search service success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

# New DB API


@bp.get("/check_user_login")
@authenticated
async def check_user_login(auth_claims: dict[str, Any]):
    try:
        user_name = auth_claims["preferred_username"]
        user = get_user_by_ad_email(user_name)
        sys_pers = []
        if user:
            if user["is_sys_admin"]:
                teams = get_all_teams()
            else:
                teams = get_team_by_user_id(user.get("_id"))
            if teams == None or teams == []:
                result_teams = []
            else:
                user_pers = get_user_permission_by_user_id(user.get("_id"))
                if user_pers == []:
                    result_teams = [
                        {"_id": item["_id"], "name": item["name"], "permissions": []} for item in teams]
                else:
                    permissions = get_all_permissions()
                    user_pers_map = {
                        item["team_id"]: item["permission_id"] for item in user_pers}
                    permissions_map = {item["_id"]: item["name"]
                                       for item in permissions}
                    for user_per in user_pers:
                        if user_per["team_id"] == "":
                            for per in user_per["permission_id"]:
                                sys_pers.append(permissions_map.get(str(per)))
                            break
                    result_teams = []
                    for team in teams:
                        per_id_list = user_pers_map.get(team.get("_id"), [])
                        per_list = []
                        for per_id in per_id_list:
                            per_list.append(permissions_map.get(str(per_id)))
                        team_dict = {"_id": team.get(
                            "_id"), "name": team["name"], "permissions": per_list}
                        result_teams.append(team_dict)
            return jsonify({"user": user, "teams": result_teams, "sys_permissions": sys_pers}), 200
        else:
            return jsonify({"error": "Can't find user"}), 404
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/create_team")
@authenticated
async def create_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_name = body.get("team_name", None)
        if team_name:
            agent_config = {"temperature": 0.2, "seed": None,
                            "min_search_score": 0, "max_search_results": 2, "max_tokens": 1024,
                            "llm_profile_id": DEFAULT_LLM_PROFILE_ID}
            result, agent_id = insert_agent("default", None, agent_config)
            result, data_group_id = insert_data_group("default", [])
            insert_team(team_name, [data_group_id], [agent_id], [], [])
        else:
            raise ValueError("Team name is required")
        return jsonify({"success": f"Create team {team_name} success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/edit_team_name")
@authenticated
async def edit_team_name(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        team_name = body.get("team_name", None)
        if team_name and team_id:
            update_team(team_id=team_id, name=team_name)
        else:
            raise ValueError("Team ID and Team name is required")
        return jsonify({"success": f"Edit team name success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.get("/get_all_teams")
@authenticated
async def get_all_teams_function(auth_claims: dict[str, Any]):
    try:
        allteam = get_all_teams()
        return jsonify({"result": allteam}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_team_detail")
@authenticated
async def get_team_detail(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        team_data = get_team_by_id(team_id=team_id)
        user_list, agent_list, data_group_list = [], [], []
        for user_id in team_data.get("user_id"):
            user_list.append(get_user_by_id(str(user_id)))
        for agent_id in team_data.get("agent_id"):
            agent_list.append(get_agent_by_id(str(agent_id)))
        for data_group_id in team_data.get("data_group_id"):
            user_data_group = []
            data_group = get_data_group_by_id(str(data_group_id))
            for user_id in data_group.get("user_id"):
                user_data_group.append(get_user_by_id(str(user_id)))
            data_group.pop("user_id", None)
            data_group["users"] = user_data_group
            data_group_list.append(data_group)
        return jsonify({"user": user_list, "agent": agent_list, "data_group": data_group_list}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_team_users")
@authenticated
async def get_team_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        team_data = get_team_by_id(team_id=team_id)
        user_list = []
        for user_id in team_data.get("user_id"):
            user = get_user_by_id(str(user_id))
            if user:
                if not bool(user["is_sys_admin"]):
                    fname = user["first_name"]
                    lname = user["last_name"]
                    user_list.append(
                        {"_id": user["_id"], "name": f"{fname} {lname}", "email": user["email"]})
        return jsonify({"user": user_list}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/insert_user")
@authenticated
async def insert_user_function(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        email = body.get("email", None)
        ad_email = body.get("ad_email", None)
        first_name = body.get("first_name", None)
        last_name = body.get("last_name", None)
        tel = body.get("tel", None)
        employee_id = body.get("employee_id", None)
        insert_user(email, ad_email, first_name, last_name,
                    employee_id, tel, True, False)
        return jsonify({"success": f"Insert user success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/delete_user")
@authenticated
async def delete_user(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        user_id = body.get("user_id", None)
        user_per_list = get_user_permission_by_user_id(user_id)
        if user_per_list:
            for user_per in user_per_list:
                delete_user_permission_by_id(user_per.get("_id"))
        group_list = get_all_data_groups_by_user_id(user_id)
        if group_list:
            for group in group_list:
                user_in_group = group.get("user_id").copy()
                user_in_group.remove(user_id)
                update_data_group(group.get("_id"), None, user_in_group)
        team_list = get_team_by_user_id(user_id)
        if team_list:
            for team in team_list:
                user_in_team = team.get("user_id").copy()
                user_in_team.remove(user_id)
                update_team(team_id=team.get("_id"), user_id=user_in_team)
        delete_user_by_id(user_id)
        return jsonify({"success": f"Delete user success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/update_user")
@authenticated
async def update_user_function(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        user_id = body.get("user_id", None)
        email = body.get("email", None)
        ad_email = body.get("ad_email", None)
        first_name = body.get("first_name", None)
        last_name = body.get("last_name", None)
        tel = body.get("tel", None)
        employee_id = body.get("employee_id", None)
        active = body.get("active", None)
        update_user(user_id, email, ad_email, first_name,
                    last_name, employee_id, tel, active, False)
        return jsonify({"success": f"Update user success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_users_by_team_id")
@authenticated
async def get_users_by_team_id(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        team = get_team_by_id(team_id)
        waiting_approve = team["waiting_approve"]
        user_list = []
        for user_id in team["user_id"]:
            user_list.append(get_user_by_id(str(user_id)))
        return jsonify({"users": user_list, "waiting_approve": waiting_approve}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.get("/get_all_users")
@authenticated
async def get_all_users_function(auth_claims: dict[str, Any]):
    try:
        allusers = get_all_user_by_is_sys_admin(False)
        return jsonify({"result": allusers}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/register")
@authenticated
async def register_function(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        email = body.get("email", None)
        ad_email = auth_claims["preferred_username"]
        first_name = body.get("first_name", None)
        last_name = body.get("last_name", None)
        tel = body.get("tel", None)
        employee_id = body.get("employee_id", None)
        user_data = {
            "email": email,
            "ad_email": ad_email,
            "first_name": first_name,
            "last_name": last_name,
            "employee_id": employee_id,
            "tel": tel
        }
        permis = get_permission_by_name("Manage team users")
        mail_comp = current_app.config[CONFIG_MAIL_COMPONENT]
        for team in team_id:
            team_data = get_team_by_id(str(team))
            team_user = team_data["user_id"]
            team_ad_list = []
            for team_user_id in team_user:
                user_pers = get_user_permission_by_user_team_id(
                    team_user_id, str(team))
                for user_per in user_pers:
                    if permis["_id"] in user_per["permission_id"]:
                        team_ad_user = get_user_by_id(team_user_id)
                        if not team_ad_user["is_sys_admin"]:
                            team_ad_list.append(team_ad_user)
            if team_ad_list != []:
                team_ad_mail = ", ".join([item['email']
                                         for item in team_ad_list])
                send_approve_mail(mail_comp['host'], int(mail_comp['port']), mail_comp['sender'], mail_comp['password'],
                                  team_ad_mail, team_data['name'], f"{first_name} {last_name}", employee_id, email, tel, mail_comp['attach_url'])
            waiting_list = team_data["waiting_approve"]
            waiting_list.append(user_data)
            update_team(team_id=str(team), waiting_approve=waiting_list)
        return jsonify({"success": f"Register success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/approve_users")
@authenticated
async def approve_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        users = body.get("users", None)
        new_user_list = []
        team = get_team_by_id(team_id)
        waiting_user_list = team.get("waiting_approve")
        mail_comp = current_app.config[CONFIG_MAIL_COMPONENT]
        permis = get_permission_by_name("Manage team users")
        team_ad_list = []
        for team_user_id in team['user_id']:
            user_pers = get_user_permission_by_user_team_id(
                team_user_id, str(team_id))
            for user_per in user_pers:
                if permis["_id"] in user_per["permission_id"]:
                    team_ad_user = get_user_by_id(team_user_id)
                    if not team_ad_user["is_sys_admin"]:
                        team_ad_list.append(team_ad_user)
        team_ad_list = [item['email'] for item in team_ad_list]
        for user in users:
            old_user = get_user_by_ad_email(user["ad_email"])
            if old_user:
                user_id = old_user["_id"]
            else:
                result, user_id = insert_user(
                    user["email"], user["ad_email"], user["first_name"], user["last_name"], user["employee_id"], user["tel"], True, False)
            mod_user = user.copy()
            mod_user.pop('__temp_id')
            waiting_user_list.remove(mod_user)
            new_user_list.append(user_id)
            fname = user["first_name"]
            lname = user["last_name"]
            approved_mail(mail_comp['host'], int(mail_comp['port']), mail_comp['sender'], mail_comp['password'],
                          user["email"], team_ad_list, team["name"], f"{fname} {lname}", mail_comp['attach_url'])
        user_id_list = team.get("user_id")
        user_id_list.extend(new_user_list)
        update_team(team_id=team_id, user_id=user_id_list,
                    waiting_approve=waiting_user_list)
        return jsonify({"success": f"Approve users success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/reject_users")
@authenticated
async def reject_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        users = body.get("users", None)
        # users.pop('__temp_id')
        team = get_team_by_id(team_id)
        waiting_user_list = team.get("waiting_approve")
        mail_comp = current_app.config[CONFIG_MAIL_COMPONENT]
        permis = get_permission_by_name("Manage team users")
        team_ad_list = []

        for team_user_id in team['user_id']:
            user_pers = get_user_permission_by_user_team_id(
                team_user_id, str(team_id))
            for user_per in user_pers:
                if permis["_id"] in user_per["permission_id"]:
                    team_ad_user = get_user_by_id(team_user_id)
                    if not team_ad_user["is_sys_admin"]:
                        team_ad_list.append(team_ad_user)
        team_ad_list = [item['email'] for item in team_ad_list]
        for user in users:
            mod_user = user.copy()
            mod_user.pop('__temp_id')
            waiting_user_list.remove(mod_user)
            fname = user["first_name"]
            lname = user["last_name"]
            rejected_mail(mail_comp['host'], int(mail_comp['port']), mail_comp['sender'], mail_comp['password'],
                          user["email"], team_ad_list, team["name"], f"{fname} {lname}", mail_comp['attach_url'])
        update_team(team_id=team_id, waiting_approve=waiting_user_list)
        return jsonify({"success": f"Reject users success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.get("/check_waiting_approve")
@authenticated
async def check_waiting_approve(auth_claims: dict[str, Any]):
    try:
        ad_email = auth_claims["preferred_username"]
        teams = get_all_teams()
        is_waiting = False
        for team in teams:
            waiting_approves = team["waiting_approve"]
            for wait_user in waiting_approves:
                if wait_user["ad_email"] == ad_email:
                    is_waiting = True
                    break
        return jsonify({"is_waiting": is_waiting}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/delete_team_user")
@authenticated
async def delete_team_user(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        user_id = body.get("user_id", None)
        if user_id and team_id:
            team = get_team_by_id(team_id)
            user_id_list = team.get("user_id")
            user_id_list.remove(user_id)
            users_per = get_user_permission_by_user_team_id(user_id, team_id)
            for user_per in users_per:
                delete_user_by_id(user_per["_id"])
            update_team(team_id=team_id, user_id=user_id_list)
        else:
            raise ValueError("Team ID and User ID is required")
        return jsonify({"success": f"Delete user in team success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/insert_team_users")
@authenticated
async def insert_team_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        user_id = body.get("user_id", None)
        if user_id and team_id:
            team = get_team_by_id(team_id)
            user_id_list = team.get("user_id")
            user_id_list.extend(user_id)
            update_team(team_id=team_id, user_id=user_id_list)
        else:
            raise ValueError("Team ID and User ID is required")
        return jsonify({"success": f"Insert users to team success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


async def delete_data_group_function(team_id, data_group_id):
    user_blob_container_client: FileSystemClient = current_app.config[
        CONFIG_GROUP_BLOB_CONTAINER_CLIENT]
    ingester = current_app.config[CONFIG_INGESTER]
    async for blob in user_blob_container_client.list_blobs():
        blob_client = user_blob_container_client.get_blob_client(blob.name)
        tag_resp = await blob_client.get_blob_tags()
        if str(blob.name).startswith(str(team_id)):
            status = str(tag_resp['status'])
            data_group_tags = str(tag_resp['data_groups'])
            data_groups_id_list = data_group_tags.split("/")
            if data_group_id in data_groups_id_list:
                if len(data_groups_id_list) == 1:
                    await ingester.remove_groups_file(str(blob.name), str(data_group_id))
                    await blob_client.delete_blob()
                else:
                    data_groups_id_list.remove(data_group_id)
                    await ingester.remove_groups_file(str(blob.name), str(data_group_id))
                    await blob_client.set_blob_tags(tags={"status": status, "data_groups": "/".join(data_groups_id_list)})


@bp.post("/delete_team")
@authenticated
async def delete_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        if team_id:
            team = get_team_by_id(team_id)
            user_per_list = get_user_permission_by_team_id(team_id)
            roles_list = get_all_roles_by_team(team_id)
            agent_id_list = team.get("agent_id")
            group_id_list = team.get("data_group_id")
            for role in roles_list:
                delete_role_by_id(role["_id"])
            for agent_id in agent_id_list:
                delete_agent_by_id(str(agent_id))
            for group_id in group_id_list:
                await delete_data_group_function(team_id, group_id)
                delete_data_group_by_id(str(group_id))
            for user_per in user_per_list:
                delete_user_permission_by_id(user_per.get("_id"))
            delete_team_by_id(team_id)
        else:
            raise ValueError("Team ID is required")
        return jsonify({"success": f"Delete team success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/create_agent")
@authenticated
async def create_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        agent_name = body.get("agent_name", None)
        agent_config = _validate_agent_model_config(body.get("config", None))
        agent_prompt = body.get("prompt", None)
        result, agent_id = insert_agent(agent_name, agent_prompt, agent_config)
        agent_team = get_team_by_id(team_id=team_id).get("agent_id")
        if agent_team:
            agent_team.append(str(agent_id))
        else:
            agent_team = [str(agent_id)]
        update_team(team_id=team_id, agent_id=agent_team)
        return jsonify({"success": f"Create agent {agent_name} success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_agent_by_team")
@authenticated
async def get_agent_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        team = get_team_by_id(team_id=team_id)
        if not team:
            return jsonify({"error": "Team not found"}), 404
        agents = []
        for agent_id in team.get("agent_id") or []:
            agent = get_agent_by_id(str(agent_id))
            if agent:
                agents.append(agent)
        return jsonify({"result": agents}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/edit_agent")
@authenticated
async def edit_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_id = body.get("agent_id", None)
        agent_name = body.get("agent_name", None)
        agent_config = _validate_agent_model_config(body.get("config", None))
        agent_prompt = body.get("prompt", None)
        update_agent(agent_id, agent_name, agent_prompt, agent_config)
        return jsonify({"success": f"Edit agent success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/delete_agent")
@authenticated
async def delete_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        agent_id = body.get("agent_id", None)
        agent_team = get_team_by_id(team_id=team_id).get("agent_id")
        agent_team.remove(agent_id)
        update_team(team_id=team_id, agent_id=agent_team)
        delete_agent_by_id(agent_id)
        return jsonify({"success": f"Delete agent success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/create_data_group")
@authenticated
async def create_data_group(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        data_group_name = body.get("data_group_name", None)
        users_id = body.get("users_id", None)
        result, data_group_id = insert_data_group(data_group_name, users_id)
        data_group_team = get_team_by_id(team_id=team_id).get("data_group_id")
        if data_group_team:
            data_group_team.append(str(data_group_id))
        else:
            data_group_team = [str(data_group_id)]
        update_team(team_id=team_id, data_group_id=data_group_team)
        return jsonify({"success": f"Create data group {data_group_name} success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_data_group_by_team")
@authenticated
async def get_data_group_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        data_group_team = get_team_by_id(team_id=team_id).get("data_group_id")
        data_group = []
        for data_group_id in data_group_team:
            data_group_info = get_data_group_by_id(str(data_group_id))
            if data_group_info["user_id"] != []:
                user_list = []
                for user in data_group_info["user_id"]:
                    user_list.append(get_user_by_id(str(user)))
                data_group_info["user_id"] = user_list
            data_group.append(data_group_info)
        return jsonify({"result": data_group}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/edit_data_group")
@authenticated
async def edit_data_group(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        data_group_id = body.get("data_group_id", None)
        data_group_name = body.get("data_group_name", None)
        users_id = body.get("users_id", None)
        update_data_group(data_group_id, data_group_name, users_id)
        return jsonify({"success": f"Edit data group success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/delete_data_group")
@authenticated
async def delete_data_group(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        data_group_id = body.get("data_group_id", None)
        data_group_team = get_team_by_id(team_id=team_id).get("data_group_id")
        data_group_team.remove(data_group_id)
        update_team(team_id=team_id, data_group_id=data_group_team)
        await delete_data_group_function(team_id, data_group_id)
        delete_data_group_by_id(data_group_id)
        return jsonify({"success": f"Delete data group success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/create_role")
@authenticated
async def create_role(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        name = body.get("name", None)
        permissions_id = body.get("permissions_id", None)
        team_id = body.get("team_id", None)
        insert_role(name, permissions_id, team_id)
        return jsonify({"success": f"Create role {name} success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/delete_role")
@authenticated
async def delete_role(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        role_id = body.get("role_id", None)
        delete_role_by_id(role_id)
        return jsonify({"success": f"Delete role success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/edit_role")
@authenticated
async def edit_role(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        role_id = body.get("role_id", None)
        name = body.get("name", None)
        permissions_id = body.get("permissions_id", None)
        team_id = body.get("team_id", None)
        update_role(role_id, name, permissions_id, team_id)
        return jsonify({"success": f"Edit role success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_roles_by_team")
@authenticated
async def get_roles_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        all_roles = get_all_roles_by_team(team_id)
        return jsonify({"roles": all_roles}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


async def insert_permissions():
    try:
        sys_permission = ["Manage teams", "Manage users", "Manage global uploads",
                          "View feedback dashboard", "View system dashboard", "Manage user groups"]
        team_permission = ["Manage team users", "Manage team data groups", "Manage agents",
                           "Manage team uploads", "Manage team permissions"]
        for permis in sys_permission:
            insert_permission(permis, "System Permissions")
        for permis in team_permission:
            insert_permission(permis, "Team Permissions")
        return True
    except Exception as error_txt:
        return False


@bp.get("/get_all_permissions")
@authenticated
async def get_all_permissions_function(auth_claims: dict[str, Any]):
    try:
        permissions = get_all_permissions()
        return jsonify({"permissions": permissions}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/get_user_permissions")
@authenticated
async def get_user_permissions(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        user_id = body.get("user_id", None)
        team_id = body.get("team_id", None)
        if team_id:
            user_per = get_user_permission_by_user_team_id(user_id, team_id)
        else:
            user_per = get_user_permission_by_user_team_id(user_id, "")
        if user_per == []:
            return jsonify({"user_permissions": None}), 200
        else:
            return jsonify({"user_permissions": user_per}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/create_edit_user_permissions")
@authenticated
async def create_edit_user_permissions(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        user_id = body.get("user_id", None)
        team_id = body.get("team_id", None)
        permissions_id = body.get("permission_id", None)
        is_sys_admin = body.get("is_sys_admin", None)
        update_user(user_id=user_id, is_sys_admin=is_sys_admin)
        if not is_sys_admin:
            if team_id:
                user_per = get_user_permission_by_user_team_id(
                    user_id, team_id)
                if user_per == []:
                    insert_user_permission(team_id, user_id, permissions_id)
                else:
                    update_user_permission(
                        user_per[0]["_id"], team_id, user_id, permissions_id)
            else:
                user_per = get_user_permission_by_user_team_id(user_id, "")
                if user_per == []:
                    insert_user_permission("", user_id, permissions_id)
                else:
                    update_user_permission(
                        user_per[0]["_id"], "", user_id, permissions_id)
        return jsonify({"Success": "Create/Edit User permissions success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/insert_database_connection")
@authenticated
async def insert_database_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = str(body.get("team_id") or "").strip()
        name = str(body.get("name") or "").strip()
        if not team_id or not name:
            raise ValueError("team_id and connection name are required")
        config = normalize_database_config(body)
        insert_external_database(
            team_id,
            name,
            config["db_type"],
            config["host"],
            config["port"],
            config["database"],
            config["username"],
            body.get("password"),
            config["options"],
        )
        return jsonify({"success": f"Create external database {name} success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/delete_database_connection")
@authenticated
async def delete_database_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        database_id = body.get("database_id", None)
        reference_count = get_database().database_bindings.count_documents(
            {"integration_id": database_id, "delete_at": None}
        )
        if reference_count:
            return (
                jsonify(
                    {
                        "error": f"Database connection is used by {reference_count} Agent binding(s); remove those bindings first"
                    }
                ),
                409,
            )
        delete_external_database_by_id(database_id)
        return jsonify({"success": f"Delete external database success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/edit_database_connection")
@authenticated
async def edit_database_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        database_id = str(body.get("database_id") or "").strip()
        existing = get_external_database_by_id(database_id)
        if not existing:
            return jsonify({"error": "Database connection not found"}), 404
        merged = {**existing, **{key: value for key, value in body.items() if value is not None}}
        config = normalize_database_config(merged)
        name = str(merged.get("name") or "").strip()
        team_id = str(merged.get("team_id") or "").strip()
        if not team_id or not name:
            raise ValueError("team_id and connection name are required")
        password_update = body.get("password")
        if not password_update and existing.get("password") and not existing.get("password_ciphertext"):
            password_update = existing["password"]
        update_external_database(
            database_id,
            team_id,
            name,
            config["db_type"],
            config["host"],
            config["port"],
            config["database"],
            config["username"],
            password_update,
            config["options"],
            body.get("clear_password") is True,
        )
        return jsonify({"success": f"Edit external database success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/get_database_connection_by_team")
@authenticated
async def get_database_connection_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        all_database_connections = get_external_databases_by_team_id(team_id)
        serialized_connections = []
        for item in all_database_connections:
            serialized = serialize_external_database(item)
            serialized["agent_usage_count"] = len(
                get_database().database_bindings.distinct(
                    "agent_id", {"integration_id": str(item["_id"]), "delete_at": None}
                )
            )
            serialized_connections.append(serialized)
        return jsonify({"result": serialized_connections}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/test_database_connection")
@authenticated
async def test_database_connection_route(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        database_id = str(body.get("database_id") or body.get("connection_id") or "").strip()
        existing = get_external_database_by_id(database_id) if database_id else None
        if database_id and not existing:
            return jsonify({"error": "Database connection not found"}), 404

        connection = {**(existing or {}), **{key: value for key, value in body.items() if value is not None}}
        if not body.get("password") and existing:
            connection.pop("password", None)
            connection["password_ciphertext"] = existing.get("password_ciphertext")
            if not connection["password_ciphertext"] and existing.get("password"):
                connection["password"] = existing["password"]
        normalize_database_config(connection)
        result = await asyncio.to_thread(test_database_connection, connection)
        return jsonify(result), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/insert_database_binding")
@authenticated
async def insert_database_binding_func(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_id = body.get("agent_id", None)
        integration_id = body.get("integration_id", None)
        alias = body.get("alias", None)
        trigger_keywords = body.get("trigger_keywords", None)
        enabled = body.get("enabled", True)
        query_profile = body.get("query_profile")
        insert_database_binding(agent_id, integration_id, alias, trigger_keywords, enabled, query_profile)
        return jsonify({"success": f"Create database binding success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/get_database_bindings_by_agent")
@authenticated
async def get_database_bindings_by_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_id = body.get("agent_id", None)
        all_bindings = get_database_bindings_by_agent_id(agent_id)
        return jsonify({"result": all_bindings}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/delete_database_binding_by_id")
@authenticated
async def delete_database_binding_by_id_func(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        binding_id = body.get("database_binding_id", None)
        delete_database_binding_by_id(binding_id)
        return jsonify({"success": f"Delete database binding success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/toggle_database_binding_by_id")
@authenticated
async def toggle_database_binding_by_id(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        database_binding_id = body.get("database_binding_id", None)
        enabled = body.get("enabled", None)
        update_database_binding(database_binding_id, enabled=enabled)
        return jsonify({"success": f"Toggle database binding success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/update_database_binding")
@authenticated
async def update_database_binding_func(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        binding_id = str(body.get("database_binding_id") or "").strip()
        if not binding_id or not get_database_binding_by_id(binding_id):
            return jsonify({"error": "Database binding not found"}), 404
        update_database_binding(
            binding_id,
            integration_id=body.get("integration_id"),
            alias=body.get("alias"),
            trigger_keywords=body.get("trigger_keywords"),
            enabled=body.get("enabled"),
            query_profile=body.get("query_profile"),
        )
        return jsonify({"success": "Database query profile updated"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

# ⭐ CHART CAPABILITY: Routes สำหรับจัดการ chart bindings (CRUD)
#    Pattern เดียวกับ database binding routes
@bp.get("/chart_bindings")
@authenticated
async def get_chart_bindings(auth_claims: dict[str, Any]):
    """ดึง chart bindings ทั้งหมดของ agent ตาม agent_id"""
    try:
        agent_id = request.args.get("agent_id")
        if not agent_id:
            return jsonify({"error": "agent_id is required"}), 400
        bindings = get_chart_bindings_by_agent_id(agent_id)
        return jsonify(bindings), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/insert_chart_binding")
@authenticated
async def insert_chart_binding_func(auth_claims: dict[str, Any]):
    """สร้าง chart binding ใหม่ ผูกกับ agent"""
    try:
        body = await request.get_json()
        insert_chart_binding(
            agent_id=body.get("agent_id"),
            color_palette=body.get("color_palette"),
            title_template=body.get("title_template", ""),
            trigger_keywords=body.get("trigger_keywords", []),
            enabled=body.get("enabled", True),
            auto_generate=body.get("auto_generate", False),
            chart_selection_mode=body.get("chart_selection_mode", "auto"),
            default_chart_type=body.get("default_chart_type"),
            allowed_chart_types=body.get("allowed_chart_types"),
        )
        return jsonify({"message": "Chart binding created successfully"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/delete_chart_binding")
@authenticated
async def delete_chart_binding(auth_claims: dict[str, Any]):
    """ลบ chart binding"""
    try:
        body = await request.get_json()
        binding_id = body.get("binding_id", None)
        delete_chart_binding_by_id(binding_id)
        return jsonify({"message": "Chart binding deleted successfully"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/toggle_chart_binding")
@authenticated
async def toggle_chart_binding(auth_claims: dict[str, Any]):
    """เปิด/ปิด chart binding"""
    try:
        body = await request.get_json()
        binding_id = body.get("binding_id", None)
        enabled = body.get("enabled", None)
        update_chart_binding(binding_id, enabled=enabled)
        return jsonify({"message": "Chart binding toggled successfully"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/update_chart_binding")
@authenticated
async def update_chart_binding_route(auth_claims: dict[str, Any]):
    """อัปเดตข้อมูล chart binding"""
    try:
        body = await request.get_json()
        binding_id = body.get("binding_id", None)
        if not binding_id:
            return jsonify({"error": "binding_id is required"}), 400
        update_chart_binding(
            binding_id=binding_id,
            color_palette=body.get("color_palette"),
            title_template=body.get("title_template"),
            trigger_keywords=body.get("trigger_keywords"),
            enabled=body.get("enabled"),
            auto_generate=body.get("auto_generate"),
            chart_selection_mode=body.get("chart_selection_mode", "auto"),
            default_chart_type=body.get("default_chart_type"),
            allowed_chart_types=body.get("allowed_chart_types"),
        )
        return jsonify({"message": "Chart binding updated successfully"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/insert_external_api")
@authenticated
async def insert_external_api(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        name = body.get("name", None)
        type = body.get("type", None)
        team_id = body.get("team_id", None)
        base_url = body.get("base_url", None)
        auth = body.get("auth", None)
        endpoints = body.get("endpoints", None)
        insert_apis(team_id, name, type, base_url, auth, endpoints)
        return jsonify({"success": f"Create external api {name} success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/delete_external_api")
@authenticated
async def delete_external_api(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        api_id = body.get("api_id", None)
        reference_count = get_database().agent_bindings.count_documents(
            {"integration_id": api_id, "delete_at": None}
        )
        if reference_count:
            return (
                jsonify(
                    {
                        "error": f"REST API is used by {reference_count} Agent binding(s); remove those bindings first"
                    }
                ),
                409,
            )
        delete_apis_by_id(api_id)
        return jsonify({"success": f"Delete external api success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/edit_external_api")
@authenticated
async def edit_external_api(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        api_id = body.get("api_id", None)
        name = body.get("name", None)
        type = body.get("type", None)
        team_id = body.get("team_id", None)
        base_url = body.get("base_url", None)
        auth = body.get("auth", None)
        endpoints = body.get("endpoints", None)
        update_apis(api_id, team_id, name, type, base_url, auth, endpoints)
        return jsonify({"success": f"Edit external api success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/get_external_apis_by_team")
@authenticated
async def get_external_apis_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        all_apis = get_all_apis_by_team_id(team_id)
        for api in all_apis:
            api["agent_usage_count"] = len(
                get_database().agent_bindings.distinct(
                    "agent_id", {"integration_id": str(api["_id"]), "delete_at": None}
                )
            )
        return jsonify({"result": all_apis}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/get_external_api_by_id")
@authenticated
async def get_external_api_by_id(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        api_id = body.get("api_id", None)
        apis = get_apis_by_id(api_id)
        return jsonify({"result": apis}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/insert_agent_binding")
@authenticated
async def insert_agent_binding_func(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_id = body.get("agent_id", None)
        integration_id = body.get("integration_id", None)
        integration_type = body.get("integration_type", None)
        endpoint_name = body.get("endpoint_name", None)
        trigger_keywords = body.get("trigger_keywords", None)
        async_val = body.get("async", None)
        enabled = body.get("enabled", None)
        request_fields = body.get("request_fields", None)
        response_fields = body.get("response_fields", None)
        insert_agent_binding(agent_id, integration_id, integration_type, endpoint_name, trigger_keywords, async_val, enabled, request_fields, response_fields)
        return jsonify({"success": f"Create agent binding success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/delete_agent_binding_by_id")
@authenticated
async def delete_agent_binding_by_id_func(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_binding_id = body.get("agent_binding_id", None)
        delete_agent_binding_by_id(agent_binding_id)
        return jsonify({"success": f"Delete agent binding success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

@bp.post("/toggle_agent_binding_by_id")
@authenticated
async def toggle_agent_binding_by_id(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_binding_id = body.get("agent_bindin_id", None)
        enabled = body.get("enabled", None)
        update_agent_binding(agent_binding_id,enabled=enabled)
        return jsonify({"success": f"Toggle agent binding success"}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/get_agent_bindings_by_agent")
@authenticated
async def get_agent_bindings_by_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        agent_id = body.get("agent_id", None)
        all_apis = get_all_agent_bindings_by_agent_id(agent_id)
        return jsonify({"result": all_apis}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400
    
@bp.post("/get_integrations_by_team")
@authenticated
async def get_integrations_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        all_apis = get_all_apis_by_team_id(team_id)
        new_all_apis = [{"_id":api["_id"],"name":api["name"],"type":api["type"],"endpoints":api["endpoints"]} for api in all_apis]
        return jsonify({"result": new_all_apis}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400

async def insert_first_limit_size(global_limit, team_limit, personal_limit):
    try:
        insert_limit_size_config(global_limit, team_limit, personal_limit)
        return True
    except Exception:
        return False


async def insert_first_fixed_prompt(prompt):
    try:
        insert_fixed_prompt(prompt)
        return True
    except Exception:
        return False


async def insert_first_user(email, ad_email, fname, lname, em_id, tel):
    try:
        insert_user(email, ad_email, fname, lname, em_id, tel, True, True)
        return True
    except Exception:
        return False


async def insert_first_mail_template(name, subject, body):
    try:
        insert_mail_template(name, subject, body)
        return True
    except Exception:
        return False


@bp.before_app_serving
async def setup_clients():
    # Replace these with your own values, either in environment variables or directly here
    AZURE_STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
    AZURE_STORAGE_CONTAINER = os.environ["AZURE_STORAGE_CONTAINER"]
    AZURE_WEB_STORAGE_CONTAINER = os.environ["AZURE_WEB_STORAGE_CONTAINER"]
    AZURE_WEB_GROUP_STORAGE_CONTAINER = os.environ["AZURE_WEB_GROUP_STORAGE_CONTAINER"]
    AZURE_GROUP_STORAGE_CONTAINER = os.environ["AZURE_GROUP_STORAGE_CONTAINER"]
    AZURE_USERSTORAGE_ACCOUNT = os.environ.get("AZURE_USERSTORAGE_ACCOUNT")
    AZURE_USERSTORAGE_CONTAINER = os.environ.get("AZURE_USERSTORAGE_CONTAINER")
    AZURE_SEARCH_SERVICE = os.environ["AZURE_SEARCH_SERVICE"]
    AZURE_SEARCH_ENDPOINT = f"https://{AZURE_SEARCH_SERVICE}.search.windows.net"
    AZURE_SEARCH_INDEX = os.environ["AZURE_SEARCH_INDEX"]
    AZURE_SEARCH_AGENT = os.getenv("AZURE_SEARCH_AGENT", "")
    # Model provider settings support both the legacy OPENAI_* variables and
    # the new provider-specific LLM_*/EMBEDDING_* variables.
    runtime_settings = RuntimeSettings.from_env(os.environ)
    OPENAI_CHATGPT_MODEL = runtime_settings.llm.model
    AZURE_OPENAI_SEARCHAGENT_MODEL = os.getenv(
        "AZURE_OPENAI_SEARCHAGENT_MODEL")
    AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT = os.getenv(
        "AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT")
    OPENAI_EMB_MODEL = runtime_settings.embedding.model
    OPENAI_EMB_DIMENSIONS = runtime_settings.embedding.dimensions
    OPENAI_REASONING_EFFORT = os.getenv("AZURE_OPENAI_REASONING_EFFORT")
    # Used with Azure OpenAI deployments
    AZURE_OPENAI_GPT4V_DEPLOYMENT = os.environ.get(
        "AZURE_OPENAI_GPT4V_DEPLOYMENT")
    AZURE_OPENAI_GPT4V_MODEL = os.environ.get("AZURE_OPENAI_GPT4V_MODEL")
    AZURE_OPENAI_CHATGPT_DEPLOYMENT = runtime_settings.llm.deployment
    AZURE_OPENAI_EMB_DEPLOYMENT = runtime_settings.embedding.deployment
    AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "")

    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    AZURE_USE_AUTHENTICATION = os.getenv(
        "AZURE_USE_AUTHENTICATION", "").lower() == "true"
    AZURE_ENFORCE_ACCESS_CONTROL = os.getenv(
        "AZURE_ENFORCE_ACCESS_CONTROL", "").lower() == "true"
    AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS = os.getenv(
        "AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS", "").lower() == "true"
    AZURE_ENABLE_UNAUTHENTICATED_ACCESS = os.getenv(
        "AZURE_ENABLE_UNAUTHENTICATED_ACCESS", "").lower() == "true"
    AZURE_SERVER_APP_ID = os.getenv("AZURE_SERVER_APP_ID")
    AZURE_SERVER_APP_SECRET = os.getenv("AZURE_SERVER_APP_SECRET")
    AZURE_CLIENT_APP_ID = os.getenv("AZURE_CLIENT_APP_ID")
    AZURE_AUTH_TENANT_ID = os.getenv("AZURE_AUTH_TENANT_ID", AZURE_TENANT_ID)

    KB_FIELDS_CONTENT = os.getenv("KB_FIELDS_CONTENT", "content")
    KB_FIELDS_SOURCEPAGE = os.getenv("KB_FIELDS_SOURCEPAGE", "sourcepage")

    AZURE_SEARCH_QUERY_LANGUAGE = os.getenv(
        "AZURE_SEARCH_QUERY_LANGUAGE") or "en-us"
    AZURE_SEARCH_QUERY_SPELLER = os.getenv(
        "AZURE_SEARCH_QUERY_SPELLER") or "lexicon"
    AZURE_SEARCH_SEMANTIC_RANKER = os.getenv(
        "AZURE_SEARCH_SEMANTIC_RANKER", "free").lower()
    AZURE_SEARCH_QUERY_REWRITING = os.getenv(
        "AZURE_SEARCH_QUERY_REWRITING", "false").lower()
    # This defaults to the previous field name "embedding", for backwards compatibility
    AZURE_SEARCH_FIELD_NAME_EMBEDDING = os.getenv(
        "AZURE_SEARCH_FIELD_NAME_EMBEDDING", "embedding")

    AZURE_SPEECH_SERVICE_ID = os.getenv("AZURE_SPEECH_SERVICE_ID")
    AZURE_SPEECH_SERVICE_LOCATION = os.getenv("AZURE_SPEECH_SERVICE_LOCATION")
    AZURE_SPEECH_SERVICE_VOICE = os.getenv(
        "AZURE_SPEECH_SERVICE_VOICE") or "en-US-AndrewMultilingualNeural"

    USE_GPT4V = os.getenv("USE_GPT4V", "").lower() == "true"
    USE_USER_UPLOAD = os.getenv("USE_USER_UPLOAD", "").lower() == "true"
    ENABLE_LANGUAGE_PICKER = os.getenv(
        "ENABLE_LANGUAGE_PICKER", "").lower() == "true"
    USE_SPEECH_INPUT_BROWSER = os.getenv(
        "USE_SPEECH_INPUT_BROWSER", "").lower() == "true"
    USE_SPEECH_OUTPUT_BROWSER = os.getenv(
        "USE_SPEECH_OUTPUT_BROWSER", "").lower() == "true"
    USE_SPEECH_OUTPUT_AZURE = os.getenv(
        "USE_SPEECH_OUTPUT_AZURE", "").lower() == "true"
    USE_CHAT_HISTORY_BROWSER = os.getenv(
        "USE_CHAT_HISTORY_BROWSER", "").lower() == "true"
    USE_CHAT_HISTORY_COSMOS = os.getenv(
        "USE_CHAT_HISTORY_COSMOS", "").lower() == "true"
    USE_AGENTIC_RETRIEVAL = os.getenv(
        "USE_AGENTIC_RETRIEVAL", "").lower() == "true"

    # WEBSITE_HOSTNAME is always set by App Service, RUNNING_IN_PRODUCTION is set in main.bicep
    RUNNING_ON_AZURE = os.getenv("WEBSITE_HOSTNAME") is not None or os.getenv(
        "RUNNING_IN_PRODUCTION") is not None
    MAIL_HOST = os.getenv("MAIL_HOST")
    MAIL_PORT = os.getenv("MAIL_PORT")
    MAIL_SENDER = os.getenv("MAIL_SENDER")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_ATTACH = os.getenv("MAIL_ATTACH_URL")
    EXTERNAL_API_ENPOINT = os.getenv("EXTERNAL_API_ENPOINT")
    SKIP_STARTUP_BOOTSTRAP = os.getenv("SKIP_STARTUP_BOOTSTRAP", "").lower() == "true"

    # Use the current user identity for keyless authentication to Azure services.
    # This assumes you use 'azd auth login' locally, and managed identity when deployed on Azure.
    # The managed identity is setup in the infra/ folder.
    azure_credential: Union[AzureDeveloperCliCredential,
                            ManagedIdentityCredential]
    if RUNNING_ON_AZURE:
        current_app.logger.info(
            "Setting up Azure credential using ManagedIdentityCredential")
        if AZURE_CLIENT_ID := os.getenv("AZURE_CLIENT_ID"):
            # ManagedIdentityCredential should use AZURE_CLIENT_ID if set in env, but its not working for some reason,
            # so we explicitly pass it in as the client ID here. This is necessary for user-assigned managed identities.
            current_app.logger.info(
                "Setting up Azure credential using ManagedIdentityCredential with client_id %s", AZURE_CLIENT_ID
            )
            azure_credential = ManagedIdentityCredential(
                client_id=AZURE_CLIENT_ID)
        else:
            current_app.logger.info(
                "Setting up Azure credential using ManagedIdentityCredential")
            azure_credential = ManagedIdentityCredential()
    elif AZURE_TENANT_ID:
        current_app.logger.info(
            "Setting up Azure credential using AzureDeveloperCliCredential with tenant_id %s", AZURE_TENANT_ID
        )
        azure_credential = AzureDeveloperCliCredential(
            tenant_id=AZURE_TENANT_ID, process_timeout=60)
    else:
        current_app.logger.info(
            "Setting up Azure credential using AzureDeveloperCliCredential for home tenant")
        azure_credential = AzureDeveloperCliCredential(process_timeout=60)

    # Set the Azure credential in the app config for use in other parts of the app
    current_app.config[CONFIG_CREDENTIAL] = azure_credential

    # Set up clients for AI Search and Storage
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=azure_credential,
    )
    agent_client = KnowledgeAgentRetrievalClient(
        endpoint=AZURE_SEARCH_ENDPOINT, agent_name=AZURE_SEARCH_AGENT, credential=azure_credential
    )

    blob_container_client = ContainerClient(
        f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net", AZURE_STORAGE_CONTAINER, credential=azure_credential
    )
    web_blob_container_client = ContainerClient(
        f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net", AZURE_WEB_STORAGE_CONTAINER, credential=azure_credential
    )
    web_group_blob_container_client = ContainerClient(
        f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net", AZURE_WEB_GROUP_STORAGE_CONTAINER, credential=azure_credential
    )
    group_blob_container_client = ContainerClient(
        f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net", AZURE_GROUP_STORAGE_CONTAINER, credential=azure_credential
    )

    attachment_backend = os.getenv("CHAT_ATTACHMENT_STORE", "disabled").strip().lower()
    attachment_container_client = None
    if attachment_backend == "azure":
        attachment_container_name = os.getenv("AZURE_CHAT_ATTACHMENTS_CONTAINER", "").strip()
        if not attachment_container_name:
            raise ValueError(
                "AZURE_CHAT_ATTACHMENTS_CONTAINER must be set when CHAT_ATTACHMENT_STORE=azure"
            )
        attachment_container_client = ContainerClient(
            f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net",
            attachment_container_name,
            credential=azure_credential,
        )
    attachment_store = create_attachment_store(
        os.environ,
        azure_container=attachment_container_client,
    )
    current_app.config[CONFIG_CHAT_ATTACHMENT_STORE] = attachment_store
    current_app.config[CONFIG_CHAT_ATTACHMENT_SCANNER] = DisabledMalwareScanner()
    attachment_index = MongoAttachmentIndex() if attachment_store else None
    current_app.config[CONFIG_CHAT_ATTACHMENT_INDEX] = attachment_index
    if attachment_container_client:
        current_app.config[CONFIG_CHAT_ATTACHMENT_CONTAINER_CLIENT] = attachment_container_client
    if attachment_store:
        try:
            cleanup_interval = float(os.getenv("CHAT_ATTACHMENT_CLEANUP_INTERVAL_SECONDS", "3600"))
        except ValueError as error:
            raise ValueError("CHAT_ATTACHMENT_CLEANUP_INTERVAL_SECONDS must be numeric") from error
        if not math.isfinite(cleanup_interval) or cleanup_interval < 60:
            raise ValueError("CHAT_ATTACHMENT_CLEANUP_INTERVAL_SECONDS must be at least 60")
        ensure_attachment_metadata_indexes()
        ensure_attachment_index_indexes()
        cleanup_task = asyncio.create_task(
            _run_attachment_cleanup(attachment_store, attachment_index, cleanup_interval)
        )
        BACKGROUND_TASKS.add(cleanup_task)
        cleanup_task.add_done_callback(BACKGROUND_TASKS.discard)
        current_app.config[CONFIG_CHAT_ATTACHMENT_CLEANUP_TASK] = cleanup_task

    # Set up authentication helper
    search_index = None
    search_index_stats = {"document_count": 0, "storage_size": 0}
    if AZURE_USE_AUTHENTICATION:
        current_app.logger.info(
            "AZURE_USE_AUTHENTICATION is true, setting up search index client")
        search_index_client = SearchIndexClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            credential=azure_credential,
        )
        search_index = await search_index_client.get_index(AZURE_SEARCH_INDEX)
        search_index_stats = await search_index_client.get_index_statistics(AZURE_SEARCH_INDEX)
        await search_index_client.close()
    auth_helper = AuthenticationHelper(
        search_index=search_index,
        use_authentication=AZURE_USE_AUTHENTICATION,
        server_app_id=AZURE_SERVER_APP_ID,
        server_app_secret=AZURE_SERVER_APP_SECRET,
        client_app_id=AZURE_CLIENT_APP_ID,
        tenant_id=AZURE_AUTH_TENANT_ID,
        require_access_control=AZURE_ENFORCE_ACCESS_CONTROL,
        enable_global_documents=AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS,
        enable_unauthenticated_access=AZURE_ENABLE_UNAUTHENTICATED_ACCESS,
    )

    text_embeddings_service = create_embedding_service(
        runtime_settings.embedding,
        azure_credential,
        disable_vectors=os.getenv("USE_VECTORS", "").lower() == "false",
        disable_batch=os.getenv("OPENAI_EMB_DISABLE_BATCH", "").lower() == "true",
    )

    if USE_USER_UPLOAD:
        current_app.logger.info(
            "USE_USER_UPLOAD is true, setting up user upload feature")
        if not AZURE_USERSTORAGE_ACCOUNT or not AZURE_USERSTORAGE_CONTAINER:
            raise ValueError(
                "AZURE_USERSTORAGE_ACCOUNT and AZURE_USERSTORAGE_CONTAINER must be set when USE_USER_UPLOAD is true"
            )
        user_blob_container_client = FileSystemClient(
            f"https://{AZURE_USERSTORAGE_ACCOUNT}.dfs.core.windows.net",
            AZURE_USERSTORAGE_CONTAINER,
            credential=azure_credential,
        )
        current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT] = user_blob_container_client

        # Set up ingester
        file_processors = setup_file_processors(
            azure_credential=azure_credential,
            document_intelligence_service=os.getenv(
                "AZURE_DOCUMENTINTELLIGENCE_SERVICE"),
            document_intelligence_api_version=os.getenv(
                "AZURE_DOCUMENTINTELLIGENCE_API_VERSION", "2024-11-30"),
            local_pdf_parser=os.getenv(
                "USE_LOCAL_PDF_PARSER", "").lower() == "true",
            local_html_parser=os.getenv(
                "USE_LOCAL_HTML_PARSER", "").lower() == "true",
            search_images=USE_GPT4V,
        )
        search_info = await setup_search_info(
            search_service=AZURE_SEARCH_SERVICE, index_name=AZURE_SEARCH_INDEX, azure_credential=azure_credential
        )
        ingester = UploadUserFileStrategy(
            search_info=search_info,
            embeddings=text_embeddings_service,
            file_processors=file_processors,
            search_field_name_embedding=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
        )
        current_app.config[CONFIG_INGESTER] = ingester
        if os.getenv("DISABLE_INGESTION_JOB_RECOVERY", "").lower() != "true":
            recovery_task = asyncio.create_task(_recover_ingestion_jobs())
            BACKGROUND_TASKS.add(recovery_task)
            recovery_task.add_done_callback(BACKGROUND_TASKS.discard)

    # Used by the OpenAI SDK
    openai_client: AsyncOpenAI

    if USE_SPEECH_OUTPUT_AZURE:
        current_app.logger.info(
            "USE_SPEECH_OUTPUT_AZURE is true, setting up Azure speech service")
        if not AZURE_SPEECH_SERVICE_ID or AZURE_SPEECH_SERVICE_ID == "":
            raise ValueError(
                "Azure speech resource not configured correctly, missing AZURE_SPEECH_SERVICE_ID")
        if not AZURE_SPEECH_SERVICE_LOCATION or AZURE_SPEECH_SERVICE_LOCATION == "":
            raise ValueError(
                "Azure speech resource not configured correctly, missing AZURE_SPEECH_SERVICE_LOCATION")
        current_app.config[CONFIG_SPEECH_SERVICE_ID] = AZURE_SPEECH_SERVICE_ID
        current_app.config[CONFIG_SPEECH_SERVICE_LOCATION] = AZURE_SPEECH_SERVICE_LOCATION
        current_app.config[CONFIG_SPEECH_SERVICE_VOICE] = AZURE_SPEECH_SERVICE_VOICE
        # Wait until token is needed to fetch for the first time
        current_app.config[CONFIG_SPEECH_SERVICE_TOKEN] = None

    current_app.logger.info(
        "Setting up model providers: runtime=%s, llm=%s, embedding=%s",
        runtime_settings.mode.value,
        runtime_settings.llm.provider.value,
        runtime_settings.embedding.provider.value,
    )
    llm_profiles = load_llm_profiles(os.environ, runtime_settings.llm)
    if os.getenv("SKIP_MANAGED_LLM_PROVIDER_LOAD", "").lower() != "true":
        try:
            llm_profiles = _load_managed_profiles(llm_profiles)
        except Exception:
            current_app.logger.exception("Unable to load managed LLM providers; continuing with environment profiles")
    openai_client = create_llm_client(runtime_settings.llm, azure_credential)
    llm_profile_clients = {DEFAULT_LLM_PROFILE_ID: openai_client}
    for profile_id, profile in llm_profiles.items():
        if profile_id != DEFAULT_LLM_PROFILE_ID:
            llm_profile_clients[profile_id] = create_llm_client(profile.settings, azure_credential)

    current_app.config[CONFIG_OPENAI_CLIENT] = openai_client
    current_app.config[CONFIG_RUNTIME_SETTINGS] = runtime_settings
    current_app.config[CONFIG_LLM_PROFILES] = llm_profiles
    current_app.config[CONFIG_LLM_PROFILE_CLIENTS] = llm_profile_clients
    current_app.config[CONFIG_SEARCH_CLIENT] = search_client
    current_app.config[CONFIG_SEARCH_INDEX_CLIENT] = search_index_stats
    current_app.config[CONFIG_AGENT_CLIENT] = agent_client
    current_app.config[CONFIG_BLOB_CONTAINER_CLIENT] = blob_container_client
    current_app.config[CONFIG_WEB_BLOB_CONTAINER_CLIENT] = web_blob_container_client
    current_app.config[CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT] = web_group_blob_container_client
    current_app.config[CONFIG_GROUP_BLOB_CONTAINER_CLIENT] = group_blob_container_client
    current_app.config[CONFIG_AUTH_CLIENT] = auth_helper

    current_app.config[CONFIG_GPT4V_DEPLOYED] = bool(USE_GPT4V)
    current_app.config[CONFIG_KNOWLEDGE_VISION_ENABLED] = _has_configured_knowledge_vision(
        bool(USE_GPT4V), AZURE_VISION_ENDPOINT
    )
    if USE_GPT4V and not current_app.config[CONFIG_KNOWLEDGE_VISION_ENABLED]:
        current_app.logger.warning(
            "USE_GPT4V is enabled without a valid AZURE_VISION_ENDPOINT; "
            "Azure Knowledge image-vector retrieval is disabled"
        )
    current_app.config[CONFIG_SEMANTIC_RANKER_DEPLOYED] = AZURE_SEARCH_SEMANTIC_RANKER != "disabled"
    current_app.config[CONFIG_QUERY_REWRITING_ENABLED] = (
        AZURE_SEARCH_QUERY_REWRITING == "true" and AZURE_SEARCH_SEMANTIC_RANKER != "disabled"
    )
    current_app.config[CONFIG_DEFAULT_REASONING_EFFORT] = OPENAI_REASONING_EFFORT
    current_app.config[CONFIG_REASONING_EFFORT_ENABLED] = OPENAI_CHATGPT_MODEL in Approach.GPT_REASONING_MODELS
    current_app.config[CONFIG_STREAMING_ENABLED] = (
        bool(USE_GPT4V)
        or OPENAI_CHATGPT_MODEL not in Approach.GPT_REASONING_MODELS
        or Approach.GPT_REASONING_MODELS[OPENAI_CHATGPT_MODEL].streaming
    )
    current_app.config[CONFIG_VECTOR_SEARCH_ENABLED] = os.getenv(
        "USE_VECTORS", "").lower() != "false"
    current_app.config[CONFIG_USER_UPLOAD_ENABLED] = bool(USE_USER_UPLOAD)
    current_app.config[CONFIG_LANGUAGE_PICKER_ENABLED] = ENABLE_LANGUAGE_PICKER
    current_app.config[CONFIG_SPEECH_INPUT_ENABLED] = USE_SPEECH_INPUT_BROWSER
    current_app.config[CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED] = USE_SPEECH_OUTPUT_BROWSER
    current_app.config[CONFIG_SPEECH_OUTPUT_AZURE_ENABLED] = USE_SPEECH_OUTPUT_AZURE
    current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED] = USE_CHAT_HISTORY_BROWSER
    current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED] = USE_CHAT_HISTORY_COSMOS
    current_app.config[CONFIG_AGENTIC_RETRIEVAL_ENABLED] = USE_AGENTIC_RETRIEVAL
    current_app.config[CONFIG_MAIL_COMPONENT] = {
        "host": MAIL_HOST,
        "port": MAIL_PORT,
        "sender": MAIL_SENDER,
        "password": MAIL_PASSWORD,
        "attach_url": MAIL_ATTACH
    }
    current_app.config[CONFIG_EXTERNAL_API_ENPOINT] = EXTERNAL_API_ENPOINT

    prompt_manager = PromptyManager()

    # Set up the two default RAG approaches for /ask and /chat
    # RetrieveThenReadApproach is used by /ask for single-turn Q&A
    current_app.config[CONFIG_ASK_APPROACH] = RetrieveThenReadApproach(
        search_client=search_client,
        search_index_name=AZURE_SEARCH_INDEX,
        agent_model=AZURE_OPENAI_SEARCHAGENT_MODEL,
        agent_deployment=AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT,
        agent_client=agent_client,
        openai_client=openai_client,
        auth_helper=auth_helper,
        chatgpt_model=OPENAI_CHATGPT_MODEL,
        chatgpt_deployment=AZURE_OPENAI_CHATGPT_DEPLOYMENT,
        embedding_model=OPENAI_EMB_MODEL,
        embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
        embedding_dimensions=OPENAI_EMB_DIMENSIONS,
        embedding_field=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
        sourcepage_field=KB_FIELDS_SOURCEPAGE,
        content_field=KB_FIELDS_CONTENT,
        query_language=AZURE_SEARCH_QUERY_LANGUAGE,
        query_speller=AZURE_SEARCH_QUERY_SPELLER,
        prompt_manager=prompt_manager,
        reasoning_effort=OPENAI_REASONING_EFFORT,
        embedding_service=text_embeddings_service,
    )

    # ChatReadRetrieveReadApproach is used by /chat for multi-turn conversation
    current_app.config[CONFIG_CHAT_APPROACH] = ChatReadRetrieveReadApproach(
        search_client=search_client,
        search_index_name=AZURE_SEARCH_INDEX,
        agent_model=AZURE_OPENAI_SEARCHAGENT_MODEL,
        agent_deployment=AZURE_OPENAI_SEARCHAGENT_DEPLOYMENT,
        agent_client=agent_client,
        openai_client=openai_client,
        auth_helper=auth_helper,
        chatgpt_model=OPENAI_CHATGPT_MODEL,
        chatgpt_deployment=AZURE_OPENAI_CHATGPT_DEPLOYMENT,
        embedding_model=OPENAI_EMB_MODEL,
        embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
        embedding_dimensions=OPENAI_EMB_DIMENSIONS,
        embedding_field=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
        sourcepage_field=KB_FIELDS_SOURCEPAGE,
        content_field=KB_FIELDS_CONTENT,
        query_language=AZURE_SEARCH_QUERY_LANGUAGE,
        query_speller=AZURE_SEARCH_QUERY_SPELLER,
        prompt_manager=prompt_manager,
        reasoning_effort=OPENAI_REASONING_EFFORT,
        embedding_service=text_embeddings_service,
    )

    if USE_GPT4V:
        if current_app.config[CONFIG_KNOWLEDGE_VISION_ENABLED]:
            current_app.logger.info("Azure Knowledge image retrieval is enabled")
        if not AZURE_OPENAI_GPT4V_MODEL:
            raise ValueError(
                "AZURE_OPENAI_GPT4V_MODEL must be set when USE_GPT4V is true")
        if any(
            model in Approach.GPT_REASONING_MODELS
            for model in [
                OPENAI_CHATGPT_MODEL,
                AZURE_OPENAI_GPT4V_MODEL,
                AZURE_OPENAI_CHATGPT_DEPLOYMENT,
                AZURE_OPENAI_GPT4V_DEPLOYMENT,
            ]
        ):
            raise ValueError(
                "AZURE_OPENAI_CHATGPT_MODEL and AZURE_OPENAI_GPT4V_MODEL must not be a reasoning model when USE_GPT4V is true"
            )

    token_provider = get_bearer_token_provider(
        azure_credential, "https://cognitiveservices.azure.com/.default")
    fallback_vision_model = AZURE_OPENAI_GPT4V_MODEL if USE_GPT4V else OPENAI_CHATGPT_MODEL
    fallback_vision_deployment = (
        AZURE_OPENAI_GPT4V_DEPLOYMENT if USE_GPT4V else AZURE_OPENAI_CHATGPT_DEPLOYMENT
    )

    # Always prepare the provider-neutral vision prompt path so a managed model
    # selected in the Portal can accept user attachments. Azure Vision remains
    # optional and is used only for Knowledge image vectors when USE_GPT4V=true.
    current_app.config[CONFIG_ASK_VISION_APPROACH] = RetrieveThenReadVisionApproach(
        search_client=search_client,
        openai_client=openai_client,
        blob_container_client=blob_container_client,
        auth_helper=auth_helper,
        vision_endpoint=AZURE_VISION_ENDPOINT,
        vision_token_provider=token_provider,
        gpt4v_deployment=fallback_vision_deployment,
        gpt4v_model=fallback_vision_model,
        embedding_model=OPENAI_EMB_MODEL,
        embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
        embedding_dimensions=OPENAI_EMB_DIMENSIONS,
        embedding_field=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
        sourcepage_field=KB_FIELDS_SOURCEPAGE,
        content_field=KB_FIELDS_CONTENT,
        query_language=AZURE_SEARCH_QUERY_LANGUAGE,
        query_speller=AZURE_SEARCH_QUERY_SPELLER,
        prompt_manager=prompt_manager,
        embedding_service=text_embeddings_service,
    )

    current_app.config[CONFIG_CHAT_VISION_APPROACH] = ChatReadRetrieveReadVisionApproach(
        search_client=search_client,
        openai_client=openai_client,
        blob_container_client=blob_container_client,
        auth_helper=auth_helper,
        vision_endpoint=AZURE_VISION_ENDPOINT,
        vision_token_provider=token_provider,
        chatgpt_model=OPENAI_CHATGPT_MODEL,
        chatgpt_deployment=AZURE_OPENAI_CHATGPT_DEPLOYMENT,
        gpt4v_deployment=fallback_vision_deployment,
        gpt4v_model=fallback_vision_model,
        embedding_model=OPENAI_EMB_MODEL,
        embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
        embedding_dimensions=OPENAI_EMB_DIMENSIONS,
        embedding_field=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
        sourcepage_field=KB_FIELDS_SOURCEPAGE,
        content_field=KB_FIELDS_CONTENT,
        query_language=AZURE_SEARCH_QUERY_LANGUAGE,
        query_speller=AZURE_SEARCH_QUERY_SPELLER,
        prompt_manager=prompt_manager,
        embedding_service=text_embeddings_service,
    )
    if SKIP_STARTUP_BOOTSTRAP:
        current_app.logger.info("Skipping application data bootstrap")
        return

    system_permissions = get_all_permissions()
    if system_permissions == []:
        await insert_permissions()
    limit_sizes = get_all_limit_size_configs()
    if limit_sizes == []:
        await insert_first_limit_size(524288000, 1073741824, 209715200)
    fixed_prompts = get_all_fixed_prompt()
    if fixed_prompts == []:
        instruction_text = """Answer ONLY with the facts listed in the list of sources below.
If there isn't enough information below, respond with "I don't know" in English, or the equivalent phrase in the language the user asked in.
Do not generate answers that don't use the sources below.

Always respond in the SAME language that the user asked the question.
If the information in the sources is written in a different language, you MUST translate it into the user’s language BEFORE answering.
- Translation of the source text IS considered a valid use of the source.
- Do NOT copy the original source text in another language; always provide the translated version.
- Never mix languages. The answer language must exactly match the user’s question language.
For example, if the source is in Thai and the user asks in Chinese,
you MUST provide the answer fully in Chinese, translating the Thai source.
Do not output any Thai text in the final answer.
Important: For Chinese queries, never output other languages. Always output Chinese translation of the other languages source.

Each source has a name followed by colon and the actual information.
Always include the source name for each fact you use in the response.
Use square brackets to reference the source, for example [info1.txt].
Don’t combine sources, list each source separately, for example [info1.txt][info2.pdf].
"""
        insert_fixed_prompt(instruction_text)
    users = get_all_users()
    if users == []:
        SYSTEM_ADMIN_EMAIL = os.environ["SYSTEM_ADMIN_EMAIL"]
        SYSTEM_ADMIN_AZURE_EMAIL = os.environ["SYSTEM_ADMIN_AZURE_EMAIL"]
        SYSTEM_ADMIN_FIRST_NAME = os.environ["SYSTEM_ADMIN_FIRST_NAME"]
        SYSTEM_ADMIN_LAST_NAME = os.environ["SYSTEM_ADMIN_LAST_NAME"]
        SYSTEM_ADMIN_EMPLOYEE_ID = os.environ["SYSTEM_ADMIN_EMPLOYEE_ID"]
        SYSTEM_ADMIN_TEL = os.environ["SYSTEM_ADMIN_TEL"]
        await insert_first_user(SYSTEM_ADMIN_EMAIL, SYSTEM_ADMIN_AZURE_EMAIL, SYSTEM_ADMIN_FIRST_NAME, SYSTEM_ADMIN_LAST_NAME, SYSTEM_ADMIN_EMPLOYEE_ID, SYSTEM_ADMIN_TEL)
    mail_templates = get_all_mail_template()
    if mail_templates == []:
        mail_template = [
            {
                "name": "send_approve",
                "subject": "[Insight Sphere] Team Join Request Pending Approval - {team_name}",
                "body": "<html>\n  <body style=\"font-family: Arial, sans-serif; color: #333;\">\n    <p>Dear Team Leader,</p>\n\n    <p>\n      A new user has submitted a request to join the team\n      <strong>{team_name}</strong> through the\n      <strong>Insight Sphere</strong> system.\n    </p>\n\n    <table>\n      <tr><td><strong>Full Name</strong></td><td>: {full_name}</td></tr>\n      <tr><td><strong>Employee ID</strong></td><td>: {employee_id}</td></tr>\n      <tr><td><strong>Company Email</strong></td><td>: {company_email}</td></tr>\n      <tr><td><strong>Phone Number</strong></td><td>: {phone_number}</td></tr>\n      <tr><td><strong>Requested Team</strong></td><td>: {team_name}</td></tr>\n    </table>\n\n    <p style=\"margin: 20px 0;\">\n      <a href=\"{system_url}\"\n         style=\"background:#2563eb;color:#fff;padding:12px 20px;\n                text-decoration:none;border-radius:6px;font-weight:bold;\">\n        Insight Sphere Portal\n      </a>\n    </p>\n\n    <p>\n      Insight Sphere System<br>\n      <small>(Automated message. Do not reply.)</small>\n    </p>\n  </body>\n</html>"
            },
            {
                "name": "approved",
                "subject": "[Insight Sphere] You Have Been Approved to Join Team - {team_name}",
                "body": "<html>\n  <body style=\"font-family: Arial, sans-serif; color: #333;\">\n    \n    <p>Dear {full_name},</p>\n\n    <p>\n      We are pleased to inform you that your request to join the team\n      <strong>{team_name}</strong> has been <strong>approved</strong>\n      in the <strong>Insight Sphere</strong> system.\n    </p>\n\n    <p>\n      You are now officially a member of the team and can access\n      team-related information and resources through the system.\n    </p>\n\n    <h4>Team Information</h4>\n    <table>\n      <tr>\n        <td><strong>Team Name</strong></td>\n        <td>: {team_name}</td>\n      </tr>\n       </table>\n\n    <p style=\"margin: 20px 0;\">\n      <a href=\"{system_url}\"\n         style=\"background:#16a34a;color:#fff;padding:12px 20px;\n                text-decoration:none;border-radius:6px;font-weight:bold;\">\n        Insight Sphere Portal\n      </a>\n    </p>\n\n    <p>\n      If you have any questions or encounter any issues,\n      please contact your team leader or system administrator.\n    </p>\n\n    <p>\n      Welcome aboard, and we look forward to your collaboration.\n    </p>\n\n    <p>\n      <strong>Insight Sphere System</strong><br>\n      <small>(This is an automated message. Please do not reply.)</small>\n    </p>\n\n  </body>\n</html>"
            },
            {
                "name": "rejected",
                "subject": "[Insight Sphere] Team Join Request Not Approved - {team_name}",
                "body": "<html>\n  <body style=\"font-family: Arial, sans-serif; color: #333;\">\n\n    <p>Dear {full_name},</p>\n\n    <p>\n      Thank you for your interest in joining the team\n      <strong>{team_name}</strong> on the\n      <strong>Insight Sphere</strong> system.\n    </p>\n\n    <p>\n      After review, we regret to inform you that your request to join this team\n      was <strong>not approved</strong> at this time.\n    </p>\n\n    <h4>Request Details</h4>\n    <table>\n      <tr>\n        <td><strong>Applicant Name</strong></td>\n        <td>: {full_name}</td>\n      </tr>\n      <tr>\n        <td><strong>Requested Team</strong></td>\n        <td>: {team_name}</td>\n      </tr>\n    </table>\n\n    <p>\n      If you believe this decision was made in error or require further clarification,\n      please contact the team leader directly.\n    </p>\n\n    <p>\n      Alternatively, you may log in to the Insight Sphere system to submit a new request\n      to join the correct team.\n    </p>\n\n    <p style=\"margin: 20px 0;\">\n      <a href=\"{system_url}\"\n         style=\"background:#dc2626;color:#fff;padding:12px 20px;\n                text-decoration:none;border-radius:6px;font-weight:bold;\">\n        Insight Sphere Portal\n      </a>\n    </p>\n\n    <p>\n      We appreciate your understanding and cooperation.\n    </p>\n\n    <p>\n      <strong>Insight Sphere System</strong><br>\n      <small>(This is an automated message. Please do not reply.)</small>\n    </p>\n\n  </body>\n</html>"
            }
        ]
        for mail in mail_template:
            await insert_first_mail_template(mail["name"], mail["subject"], mail["body"])


@bp.after_app_serving
async def close_clients():
    for extraction_task in tuple(ATTACHMENT_EXTRACTION_TASKS):
        extraction_task.cancel()
    if ATTACHMENT_EXTRACTION_TASKS:
        await asyncio.gather(*tuple(ATTACHMENT_EXTRACTION_TASKS), return_exceptions=True)
    if cleanup_task := current_app.config.get(CONFIG_CHAT_ATTACHMENT_CLEANUP_TASK):
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    if attachment_container := current_app.config.get(CONFIG_CHAT_ATTACHMENT_CONTAINER_CLIENT):
        await attachment_container.close()
    await current_app.config[CONFIG_SEARCH_CLIENT].close()
    await current_app.config[CONFIG_BLOB_CONTAINER_CLIENT].close()
    await current_app.config[CONFIG_WEB_BLOB_CONTAINER_CLIENT].close()
    await current_app.config[CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT].close()
    await current_app.config[CONFIG_GROUP_BLOB_CONTAINER_CLIENT].close()
    if current_app.config.get(CONFIG_USER_BLOB_CONTAINER_CLIENT):
        await current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT].close()


def create_app():
    app = Quart(__name__)
    # For specific upload size
    # app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
    app.register_blueprint(bp)
    app.register_blueprint(chat_history_cosmosdb_bp)

    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        app.logger.info(
            "APPLICATIONINSIGHTS_CONNECTION_STRING is set, enabling Azure Monitor")
        configure_azure_monitor()
        # This tracks HTTP requests made by aiohttp:
        AioHttpClientInstrumentor().instrument()
        # This tracks HTTP requests made by httpx:
        HTTPXClientInstrumentor().instrument()
        # This tracks OpenAI SDK requests:
        OpenAIInstrumentor().instrument()
        # This middleware tracks app route requests:
        app.asgi_app = OpenTelemetryMiddleware(
            app.asgi_app)  # type: ignore[assignment]

    # Log levels should be one of https://docs.python.org/3/library/logging.html#logging-levels
    # Set root level to WARNING to avoid seeing overly verbose logs from SDKS
    logging.basicConfig(level=logging.WARNING)
    # Set our own logger levels to INFO by default
    app_level = os.getenv("APP_LOG_LEVEL", "INFO")
    app.logger.setLevel(os.getenv("APP_LOG_LEVEL", app_level))
    logging.getLogger("scripts").setLevel(app_level)

    if allowed_origin := os.getenv("ALLOWED_ORIGIN"):
        allowed_origins = allowed_origin.split(";")
        if len(allowed_origins) > 0:
            app.logger.info("CORS enabled for %s", allowed_origins)
            cors(app, allow_origin=allowed_origins,
                 allow_methods=["GET", "POST"])

    return app
