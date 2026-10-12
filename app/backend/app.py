
import dataclasses
import hashlib
import copy
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
import secrets
import uuid

import requests
# Scraping import
from bs4 import BeautifulSoup
from azure.storage.blob import BlobServiceClient
from urllib.parse import quote, urljoin, urlparse
import asyncio
# End of Scraping import
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Dict, Union, cast
from datetime import datetime, timedelta, timezone
from tokens_usage.save_tokens_usage import insert_user_usage
from feedback.createfeedback import insert_feedback
from feedback.getfeedback import get_all_feedback
from mongo_table_connecters.mongo_connector import get_database
from mongo_table_connecters.web_source_scans import (
    claim_web_source_scan,
    claim_web_source_scan_for_cleanup,
    complete_web_source_scan,
    create_web_source_scan,
    delete_web_source_scan,
    ensure_web_source_scan_indexes,
    get_web_source_scan,
    heartbeat_web_source_scan,
    list_expired_web_source_scans,
    list_recoverable_web_source_scans,
    list_web_source_scans,
    mark_web_source_scan_failed,
    queue_web_source_scan,
    release_web_source_scan,
    retry_web_source_scan,
    update_web_source_page,
)
from mongo_table_connecters.teams import insert_team, get_all_teams, get_team_by_id, get_team_by_data_group_id, get_team_by_agent_id, update_team, get_team_by_user_id, delete_team_by_id
from mongo_table_connecters.users import get_user_by_id, get_user_by_ad_email, get_all_user_by_is_sys_admin, get_all_users, insert_user, delete_user_by_id, update_user
from mongo_table_connecters.local_auth import (
    LocalAuthError,
    authenticate_local_user,
    bootstrap_local_superuser,
    change_local_password,
    create_managed_local_user,
    ensure_local_auth_indexes,
    enforce_local_login_rate_limit,
    get_local_identity_for_user,
    local_identity_exists,
    list_local_identities_by_user_ids,
    resolve_local_session,
    reset_local_password,
    revoke_local_session,
)
from mongo_table_connecters.oidc_auth import (
    OIDCAuthError,
    begin_oidc_login,
    complete_oidc_login,
    discover_oidc_provider,
    ensure_oidc_auth_indexes,
    oidc_provider_identity_key,
    resolve_oidc_session,
    revoke_oidc_session,
    revoke_oidc_provider_sessions,
)
from mongo_table_connecters.oidc_providers import (
    delete_oidc_provider,
    ensure_oidc_provider_indexes,
    get_oidc_provider,
    list_oidc_providers,
    public_oidc_providers,
    save_oidc_provider,
    serialize_oidc_provider,
)
from mongo_table_connecters.saml_auth import (
    SAMLAuthError,
    begin_saml_login,
    complete_saml_login,
    ensure_saml_auth_indexes,
    resolve_saml_session,
    revoke_saml_provider_sessions,
    revoke_saml_session,
    saml_metadata,
    saml_provider_identity_key,
)
from mongo_table_connecters.saml_providers import (
    delete_saml_provider,
    ensure_saml_provider_indexes,
    get_saml_provider,
    list_saml_providers,
    public_saml_providers,
    saml_settings,
    save_saml_provider,
    serialize_saml_provider,
)
from mongo_table_connecters.identity_management import (
    approve_identity_link,
    ensure_identity_management_indexes,
    federated_identity_types_by_user_ids,
    get_identity_link_request,
    list_identity_audit_events,
    list_identity_link_requests,
    list_federated_identities,
    reject_identity_link,
    unlink_federated_identity,
)
from mongo_table_connecters.auth_settings import (
    delete_auth_settings,
    get_auth_settings,
    save_auth_settings,
    serialize_auth_settings,
)
from mongo_table_connecters.license_settings import (
    ensure_license_indexes,
    get_license_status,
    import_license,
    start_trial,
)
from core.licensing import LicenseVerificationError, load_verification_keys
from mongo_table_connecters.chat_history import (
    configured_retention_days as configured_chat_history_retention_days,
    retention_days as effective_chat_history_retention_days,
    save_retention_days as save_chat_history_retention_days,
)
from mongo_table_connecters.guardrail_settings import (
    get_guardrail_settings,
    save_guardrail_settings,
)
from mongo_table_connecters.usage_quotas import (
    check_and_record_request,
    check_document_quota,
    current_llm_rule_usages,
    current_usage,
    effective_quota_settings,
    ensure_usage_quota_indexes,
    finish_llm_reservation,
    get_quota_settings,
    list_quota_audit_events,
    quota_status,
    save_quota_settings,
    save_team_user_quota_settings,
    team_member_quota_policy,
)
from core.usage_quotas import UsageQuotaPolicy
from mongo_table_connecters.agents import (
    activate_agent_by_id,
    delete_agent_cascade,
    ensure_agent_indexes,
    get_agent_by_id,
    insert_agent,
    is_active_agent,
    is_expired_agent_draft,
    list_expired_agent_draft_ids,
    update_agent,
)
from mongo_table_connecters.agent_invocation_jobs import (
    AgentInvocationJobError,
    claim_agent_invocation_job,
    complete_agent_invocation_job,
    create_agent_invocation_job,
    decrypt_agent_invocation_job_input,
    ensure_agent_invocation_job_indexes,
    get_agent_invocation_job,
    heartbeat_agent_invocation_job,
    list_recoverable_agent_invocation_jobs,
    release_agent_invocation_job,
    retry_agent_invocation_job,
    serialize_agent_invocation_job,
)
from mongo_table_connecters.agent_invocation_keys import (
    ACCESS_TYPE_EXTERNAL,
    ACCESS_TYPE_INTERNAL,
    AgentInvocationKeyError,
    authenticate_agent_invocation_key,
    create_agent_invocation_key,
    enforce_agent_invocation_rate_limit,
    ensure_agent_invocation_key_indexes,
    get_agent_invocation_key,
    insert_agent_invocation_audit,
    list_agent_invocation_keys,
    mark_agent_invocation_key_used,
    normalize_agent_invocation_access_type,
    revoke_agent_invocation_key,
    rotate_agent_invocation_key,
    validate_agent_invocation_key_document,
)
from mongo_table_connecters.agent_catalog import (
    ensure_agent_catalog_indexes,
    get_active_installation,
    get_catalog_item,
    get_catalog_version,
    insert_catalog_audit_event,
    is_visible_to_team,
    list_catalog_items,
    publish_agent,
    record_installation,
    update_catalog_item,
)
from mongo_table_connecters.llm_providers import (
    get_llm_provider,
    insert_llm_provider,
    list_llm_providers,
    soft_delete_llm_provider,
    update_llm_provider,
)
from mongo_table_connecters.embedding_profiles import (
    ENVIRONMENT_PROFILE_ID,
    activate_embedding_profile,
    get_embedding_profile,
    get_embedding_settings,
    insert_embedding_profile,
    list_embedding_profiles,
    mark_embedding_runtime_started,
    mark_embedding_reindex_complete,
    soft_delete_embedding_profile,
    update_embedding_profile,
)
from mongo_table_connecters.mcp_servers import (
    azure_mcp_runtime_config,
    decrypt_mcp_entra_client_secret,
    decrypt_mcp_headers,
    get_mcp_server,
    insert_mcp_server,
    list_pending_managed_azure_mcp_deletions,
    list_pending_managed_azure_mcp_stops,
    list_mcp_servers,
    list_enabled_managed_azure_mcp_servers,
    normalize_mcp_server_payload,
    serialize_mcp_server,
    soft_delete_mcp_server,
    complete_mcp_server_cleanup,
    update_mcp_server,
)
from mongo_table_connecters.agent_audit import list_agent_audit_events
from agent_runtime.observability import AuditTrail
from mongo_table_connecters.data_group import (
    EXPOSURE_EXTERNAL,
    get_data_group_by_id,
    insert_data_group,
    delete_data_group_by_id,
    get_all_data_groups_by_user_id,
    update_data_group,
    update_data_group_publication,
)
from mongo_table_connecters.permissions import insert_permission, get_all_permissions, get_permission_by_name
from mongo_table_connecters.user_permission import get_user_permission_by_user_id, get_user_permission_by_team_id, delete_user_permission_by_id, get_user_permission_by_user_team_id, insert_user_permission, update_user_permission
from mongo_table_connecters.roles import insert_role, update_role, get_all_roles, get_role_by_id, get_all_roles_by_team, delete_role_by_id
from mongo_table_connecters.limit_size_config import insert_limit_size_config, get_all_limit_size_configs
from mongo_table_connecters.external_apis import insert_apis, delete_apis_by_id, update_apis, get_all_apis_by_team_id, get_apis_by_id, get_apis_by_team_id_and_name
from mongo_table_connecters.agent_bindings import insert_agent_binding, get_all_agent_bindings_by_agent_id, delete_agent_binding_by_id, update_agent_binding,get_agent_binding_by_apisid_and_endpointname
from mongo_table_connecters.fixed_promts import insert_fixed_prompt, get_all_fixed_prompt
from mongo_table_connecters.external_database import insert_external_database, get_external_database_by_id, get_external_databases_by_team_id, get_all_external_databases, update_external_database, delete_external_database_by_id, serialize_external_database
from mongo_table_connecters.integration_catalog import (
    IntegrationAssignmentError,
    assign_unassigned_integration,
    list_integration_connections,
)
from mongo_table_connecters.integration_lifecycle_events import insert_integration_lifecycle_event
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
from business_document_connectors import test_business_document_connection
from mongo_table_connecters.business_document_connections import (
    decrypt_business_document_secrets,
    get_business_document_connection,
    insert_business_document_connection,
    list_business_document_connections,
    normalize_business_document_connection,
    serialize_business_document_connection,
    soft_delete_business_document_connection,
    update_business_document_connection,
)
from mongo_table_connecters.web_search_connections import (
    decrypt_web_search_api_key,
    get_web_search_connection,
    insert_web_search_connection,
    list_web_search_connections,
    normalize_web_search_connection,
    serialize_web_search_connection,
    soft_delete_web_search_connection,
    update_web_search_connection,
    web_search_connection_usage_count,
)
from mongo_table_connecters.business_document_bindings import (
    collection as business_document_bindings_collection,
    delete_business_document_binding,
    get_business_document_binding,
    insert_business_document_binding,
    list_business_document_bindings,
    normalize_business_document_binding,
    update_business_document_binding,
)
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
from core.knowledge_store import (
    AzureKnowledgeObjectStore,
    KnowledgeObjectNotFound,
    KnowledgeObjectStore,
    create_minio_knowledge_store,
)
from mongo_table_connecters.ingestion_jobs import (
    claim_ingestion_job,
    create_ingestion_job,
    get_ingestion_job,
    latest_indexed_times,
    list_ingestion_jobs,
    list_recoverable_ingestion_jobs,
    release_ingestion_job,
    restart_failed_ingestion_job,
    serialize_ingestion_job,
    update_ingestion_job_status,
)
from mongo_table_connecters.chat_attachment_metadata import (
    claim_attachment_extraction,
    create_attachment_metadata,
    delete_expired_attachment_metadata,
    ensure_attachment_metadata_indexes,
    get_attachment_metadata,
    get_attachment_metadata_by_upload_id,
    list_attachment_metadata,
    list_recoverable_attachment_metadata,
    release_attachment_extraction,
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
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import (
    AzureDeveloperCliCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
)
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.storage.blob.aio import ContainerClient
from azure.storage.filedatalake.aio import FileSystemClient
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
from agent_runtime.adapters.mcp import (
    MCPServerConfig,
    discover_mcp_tools,
    is_read_only_mcp_tool,
)
from core.chat_attachments import ChatAttachmentError, validate_chat_attachments
from core.attachment_cleanup import cleanup_expired_attachments
from core.attachment_extraction import (
    AttachmentExtractionError,
    chunk_attachment_pages,
    extract_attachment_chunks,
)
from core.attachment_index import AttachmentIndex
from core.attachment_retrieval import (
    ATTACHMENT_EVIDENCE_KNOWLEDGE_ONLY,
    ATTACHMENT_EVIDENCE_UPLOADED_ONLY,
    REQUIREMENTS_EVIDENCE_MATRIX_INSTRUCTION,
    AttachmentRetrievalError,
    bounded_attachment_evidence,
    format_attachment_sources,
    normalize_attachment_evidence_scope,
    normalize_attachment_ids,
    source_display_filename,
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
from core.effective_access import AccessControlError, EffectiveAccess, resolve_effective_access
from chat_history.cosmosdb import chat_history_cosmosdb_bp
from config import (
    CONFIG_AGENT_CLIENT,
    CONFIG_ACTIVE_EMBEDDING_PROFILE_ID,
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
    CONFIG_CHAT_ATTACHMENT_PROCESSORS,
    CONFIG_CHAT_ATTACHMENT_RECOVERY_TASK,
    CONFIG_CHAT_ATTACHMENT_SCANNER,
    CONFIG_CHAT_ATTACHMENT_STORE,
    CONFIG_CHAT_HISTORY_BROWSER_ENABLED,
    CONFIG_CHAT_HISTORY_COSMOS_ENABLED,
    CONFIG_CHAT_HISTORY_DATABASE_ENABLED,
    CONFIG_CHAT_VISION_APPROACH,
    CONFIG_CREDENTIAL,
    CONFIG_DEFAULT_REASONING_EFFORT,
    CONFIG_GPT4V_DEPLOYED,
    CONFIG_KNOWLEDGE_STORE,
    CONFIG_KNOWLEDGE_VISION_ENABLED,
    CONFIG_INGESTER,
    CONFIG_INGESTION_RECOVERY_TASK,
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
    CONFIG_WEB_SOURCE_SCAN_CLEANUP_TASK,
    CONFIG_WEB_SOURCE_INDEX_RECOVERY_TASK,
    CONFIG_MAIL_COMPONENT,
    CONFIG_EXTERNAL_API_ENPOINT
)
from core.authentication import AuthenticationHelper
from core.knowledge_search import QdrantKnowledgeSearchClient
from core.model_providers import create_embedding_service, create_llm_client
from core.llm_vendors import apply_llm_vendor_chat_policy, get_llm_vendor, infer_llm_vendor
from core.model_profiles import (
    DEFAULT_LLM_PROFILE_ID,
    LLMProfile,
    load_llm_profiles,
    managed_profile_id,
)
from core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret
from core.web_search import (
    WebSearchError,
    configured_web_search_provider,
    create_web_search_provider,
    normalize_allowed_domains,
)
from core.integration_controller import (
    AzureMCPProvisionRequest,
    IntegrationControllerClient,
    IntegrationControllerError,
)
from core.system_health import build_system_health_snapshot
from core.mcp_auth import EntraClientCredentials
from core.runtime_settings import EmbeddingProviderSettings, LLMProviderSettings, ModelProvider, RuntimeSettings, parse_model_provider
from agent_runtime.policy import normalize_tool_policy
from core.guardrails import (
    GuardrailPolicy,
    GuardrailResult,
    GuardrailViolation,
    blocked_message as guardrail_blocked_message,
    evaluate_input as evaluate_guardrail_input,
    evaluate_output as evaluate_guardrail_output,
    merge_guardrail_policies,
    sanitize_untrusted_context,
)
from core.sessionhelper import create_session_id, ensure_conversation_id
from decorators import authenticated, authenticated_path
from error import error_dict, error_response
from prepdocs import (
    setup_file_processors,
    setup_search_info,
)
from prepdocslib.filestrategy import UploadUserFileStrategy
from prepdocslib.listfilestrategy import File
from prepdocslib.docinteldb import insert_document_processing_usage
from mongo_table_connecters.usage_analytics import get_usage_analytics
from addons.scraping_web import (
    WebScrapingError,
    legacy_source_folder,
    normalize_stored_source_url,
    run_scraping_job,
    source_folder,
    source_url_from_folder,
)


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
    web_search_enabled = raw_tool_settings.get("web_search", False) is True
    web_search_connection_id = (
        str(raw_tool_settings.get("web_search_connection_id") or "").strip()
        if web_search_enabled
        else ""
    )
    web_search_domains = normalize_allowed_domains(
        raw_tool_settings.get("web_search_allowed_domains")
    )
    if web_search_enabled and not web_search_domains:
        raise ValueError("Web Search requires at least one allowed domain")
    if web_search_enabled and runtime != "langgraph":
        raise ValueError("Web Search requires the LangGraph runtime")
    tool_settings = {
        "knowledge_search": knowledge_search,
        "external_database": raw_tool_settings.get("external_database", True) is not False,
        "rest_integrations": raw_tool_settings.get("rest_integrations", True) is not False,
        "mail": raw_tool_settings.get("mail", True) is not False,
        "business_documents": raw_tool_settings.get("business_documents", True) is not False,
        "messaging": raw_tool_settings.get("messaging", True) is not False,
        "mcp": raw_tool_settings.get("mcp", True) is not False,
        "chart": raw_tool_settings.get("chart", False) is True,
        "web_search": web_search_enabled,
        "web_search_connection_id": web_search_connection_id,
        "web_search_allowed_domains": list(web_search_domains),
        "web_search_max_results": max(1, min(int(raw_tool_settings.get("web_search_max_results") or 5), 10)),
        "web_search_timeout_seconds": max(1, min(int(raw_tool_settings.get("web_search_timeout_seconds") or 15), 30)),
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
    guardrails = GuardrailPolicy.from_config(config.get("guardrails")).serialize()
    return {
        **config,
        "llm_profile_id": profile_id,
        "runtime": runtime,
        "image_input_enabled": image_input_enabled,
        "document_attachments_enabled": config.get("document_attachments_enabled", True) is not False,
        "tool_settings": tool_settings,
        "guardrails": guardrails,
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


def _validate_agent_mcp_connections(
    config: dict[str, Any],
    team_id: str,
    *,
    existing_config: dict[str, Any] | None = None,
) -> None:
    """Keep MCP credentials inside their owning Team at save time.

    Legacy connections without ``team_id`` may remain on an Agent that already
    referenced them, but they cannot be added to another Agent.
    """
    tool_settings = config.get("tool_settings") or {}
    selected_ids = tool_settings.get("mcp_server_ids") or []
    existing_ids = {
        str(item)
        for item in (
            ((existing_config or {}).get("tool_settings") or {}).get(
                "mcp_server_ids"
            )
            or []
        )
    }
    for server_id in selected_ids:
        document = get_mcp_server(str(server_id))
        if not document:
            raise AccessControlError("MCP connection not found", status_code=404)
        connection_team_id = str(document.get("team_id") or "")
        if connection_team_id == team_id:
            continue
        if not connection_team_id and str(server_id) in existing_ids:
            continue
        raise AccessControlError("MCP connection is not assigned to the Agent's team")

    unknown_allowlists = set(tool_settings.get("mcp_tool_allowlists") or {}) - set(
        selected_ids
    )
    if unknown_allowlists:
        raise AccessControlError(
            "MCP tool allowlists must reference an assigned MCP connection",
            status_code=400,
        )
    _validate_agent_web_search_connection(config, team_id)


def _validate_agent_web_search_connection(config: dict[str, Any], team_id: str) -> None:
    tool_settings = config.get("tool_settings") or {}
    connection_id = str(tool_settings.get("web_search_connection_id") or "").strip()
    if not connection_id:
        if tool_settings.get("web_search") is not True:
            return
        try:
            if configured_web_search_provider() is not None:
                return
        except WebSearchError as error:
            raise AccessControlError(str(error), status_code=400) from error
        raise AccessControlError(
            "Select a Team Web Search connection before enabling Web Search",
            status_code=400,
        )
    connection = get_web_search_connection(connection_id)
    if not connection:
        raise AccessControlError("Web Search connection not found", status_code=404)
    if connection.get("enabled") is False:
        raise AccessControlError("Web Search connection is disabled", status_code=400)
    if str(connection.get("team_id") or "") != str(team_id or ""):
        raise AccessControlError(
            "Web Search connection is not assigned to the Agent's team",
            status_code=403,
        )


def _apply_agent_llm_profile(context: dict[str, Any], agent_id: str | None) -> None:
    profile_id = DEFAULT_LLM_PROFILE_ID
    agent_config: dict[str, Any] = {}
    agent_found = not agent_id
    if agent_id:
        agent = get_agent_by_id(agent_id)
        if is_active_agent(agent):
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
    overrides["_llm_provider_id"] = (
        profile.managed_provider_id or f"configured:{profile.settings.provider.value}"
    )
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


def _usage_metadata(
    context: dict[str, Any], agent_id: str | None, workload: str = "chat"
) -> dict[str, str]:
    overrides = context.get("overrides") if isinstance(context.get("overrides"), dict) else {}
    agent = get_agent_by_id(agent_id) if agent_id else None
    agent_config = (agent or {}).get("config") or {}
    return {
        "agent_id": str(agent_id or ""),
        "agent_name": str((agent or {}).get("name") or "System default"),
        "provider": str(overrides.get("_llm_vendor") or "unknown"),
        "provider_id": str(overrides.get("_llm_provider_id") or ""),
        "model": str(overrides.get("_llm_model") or "unknown"),
        "deployment": str(overrides.get("_llm_deployment") or ""),
        "profile_id": str(overrides.get("_llm_profile_id") or ""),
        "runtime": str(agent_config.get("runtime") or "legacy"),
        "workload": workload,
        "usage_event_id": str(context.get("usage_request_id") or ""),
    }


def _prepare_usage_request(request_json: dict[str, Any], context: dict[str, Any]) -> str:
    supplied = str(request_json.get("usage_request_id") or "").strip()
    if supplied:
        try:
            request_id = str(uuid.UUID(supplied))
        except ValueError as error:
            raise AccessControlError("usage_request_id must be a valid UUID", status_code=400) from error
    else:
        request_id = str(uuid.uuid4())
    context["usage_request_id"] = request_id
    return request_id


def _estimated_request_tokens(request_json: dict[str, Any], context: dict[str, Any]) -> int:
    messages = request_json.get("messages") if isinstance(request_json.get("messages"), list) else []
    input_characters = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            input_characters += len(content)
        elif isinstance(content, list):
            input_characters += sum(len(str(part.get("text") or "")) for part in content if isinstance(part, dict))
    overrides = context.get("overrides") if isinstance(context.get("overrides"), dict) else {}
    try:
        output_limit = int(overrides.get("max_tokens") or 1024)
    except (TypeError, ValueError):
        output_limit = 1024
    return max(1, min(1_000_000, max(1, output_limit) + math.ceil(input_characters / 4)))


async def _enforce_llm_quota(
    auth_claims: dict[str, Any], context: dict[str, Any], request_json: dict[str, Any], *, workload: str
) -> None:
    if os.getenv("DISABLE_USAGE_QUOTAS", "").lower() == "true":
        return
    user_id = str(auth_claims.get("application_user_id") or "")
    team_id = str(auth_claims.get("team_id") or "")
    overrides = context.get("overrides") if isinstance(context.get("overrides"), dict) else {}
    try:
        await asyncio.to_thread(
            check_and_record_request,
            team_id,
            user_id,
            provider_id=str(overrides.get("_llm_provider_id") or ""),
            profile_id=str(overrides.get("_llm_profile_id") or ""),
            workload=workload,
            request_id=str(context.get("usage_request_id") or ""),
            reserved_tokens=_estimated_request_tokens(request_json, context),
        )
        context["usage_reservation_active"] = True
    except ValueError as error:
        raise AccessControlError(str(error), status_code=429) from error


async def _finish_usage_reservation(
    context: dict[str, Any], *, state: str, actual_tokens: int = 0
) -> None:
    request_id = str(context.get("usage_request_id") or "")
    if not request_id or not context.get("usage_reservation_active"):
        return
    try:
        await asyncio.to_thread(
            finish_llm_reservation,
            request_id,
            state=state,
            actual_tokens=actual_tokens,
        )
        context["usage_reservation_active"] = False
    except Exception:
        current_app.logger.exception("Unable to finalize usage reservation %s", request_id)


async def _persist_user_usage(
    auth_claims: dict[str, Any], response: Any, mode: str, metadata: dict[str, str], context: dict[str, Any]
) -> None:
    if os.getenv("DISABLE_USAGE_PERSISTENCE", "").lower() == "true":
        await _finish_usage_reservation(context, state="released")
        return
    try:
        result = await asyncio.to_thread(insert_user_usage, auth_claims, response, mode, metadata)
    except Exception:
        await _finish_usage_reservation(context, state="metering_failed")
        current_app.logger.exception("Unable to persist durable LLM usage event")
        return
    await _finish_usage_reservation(
        context,
        state="completed",
        actual_tokens=int((result or {}).get("tokens_total") or 0),
    )


def _require_system_admin(auth_claims: dict[str, Any]) -> dict[str, Any]:
    user = _application_user_for_claims(auth_claims)
    if not user or not user.get("active", True) or not user.get("is_sys_admin"):
        abort(403)
    return user


def _is_system_admin(auth_claims: dict[str, Any]) -> bool:
    user = _application_user_for_claims(auth_claims)
    return bool(user and user.get("active", True) and user.get("is_sys_admin"))


def _application_user_for_claims(auth_claims: dict[str, Any]) -> dict[str, Any] | None:
    application_user_id = str(auth_claims.get("application_user_id") or "").strip()
    if application_user_id:
        return get_user_by_id(application_user_id)
    username = (
        auth_claims.get("preferred_username")
        or auth_claims.get("email")
        or auth_claims.get("upn")
    )
    return get_user_by_ad_email(str(username)) if username else None


def _serialize_user_auth(
    user: dict[str, Any],
    identity: dict[str, Any] | None = None,
    *,
    has_oidc_identity: bool = False,
    has_saml_identity: bool = False,
) -> dict[str, Any]:
    result = dict(user)
    identity = identity if identity is not None else get_local_identity_for_user(str(user.get("_id") or ""))
    providers = []
    # Legacy users with an Entra login predate this marker. A user created by
    # the local administrator flow is local-only unless an identity-linking
    # flow explicitly records Entra ownership in a future migration.
    if user.get("ad_email") and user.get("created_by_auth_provider") not in {"local", "oidc", "saml"}:
        providers.append("entra")
    if identity:
        providers.append("local")
        result["local_username"] = identity.get("username")
    if has_oidc_identity or user.get("created_by_auth_provider") == "oidc":
        providers.append("oidc")
    if has_saml_identity or user.get("created_by_auth_provider") == "saml":
        providers.append("saml")
    result["auth_providers"] = providers
    return result


def _normalize_self_profile(body: Any) -> dict[str, str]:
    if not isinstance(body, dict):
        raise AccessControlError("request must be json", status_code=400)

    def required_text(field: str, maximum: int) -> str:
        value = str(body.get(field) or "").strip()
        if not value:
            raise AccessControlError(f"{field} is required", status_code=400)
        if len(value) > maximum:
            raise AccessControlError(f"{field} is too long", status_code=400)
        return value

    email = required_text("email", 254)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise AccessControlError("email is invalid", status_code=400)
    tel = str(body.get("tel") or "").strip()
    if len(tel) > 50:
        raise AccessControlError("tel is too long", status_code=400)
    return {
        "first_name": required_text("first_name", 100),
        "last_name": required_text("last_name", 100),
        "email": email,
        "tel": tel,
    }


def _require_team_access(
    auth_claims: dict[str, Any],
    team_id: str,
    *,
    permission: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    user = _application_user_for_claims(auth_claims)
    team = get_team_by_id(team_id)
    if not user or user.get("active", True) is not True:
        raise AccessControlError("The signed-in application user is unavailable")
    if not team:
        raise AccessControlError("Team not found", status_code=404)
    user_id = str(user.get("_id") or "")
    if user.get("is_sys_admin") is not True and user_id not in {
        str(item) for item in (team.get("user_id") or [])
    }:
        raise AccessControlError("You are not a member of this team")
    if permission and user.get("is_sys_admin") is not True:
        permission_ids = {
            str(item)
            for record in get_user_permission_by_user_team_id(user_id, team_id)
            for item in (record.get("permission_id") or [])
        }
        permission_names = {
            str(item.get("name"))
            for item in get_all_permissions()
            if str(item.get("_id")) in permission_ids
        }
        if permission not in permission_names:
            raise AccessControlError(f"{permission} permission is required")
    return user, team


def _require_system_permission(
    auth_claims: dict[str, Any], permission: str
) -> dict[str, Any]:
    user = _application_user_for_claims(auth_claims)
    if not user or user.get("active", True) is not True:
        raise AccessControlError("The signed-in application user is unavailable")
    if user.get("is_sys_admin") is True:
        return user
    permission_ids = {
        str(item)
        for record in get_user_permission_by_user_team_id(str(user.get("_id") or ""), "")
        for item in (record.get("permission_id") or [])
    }
    permission_names = {
        str(item.get("name"))
        for item in get_all_permissions()
        if str(item.get("_id")) in permission_ids
    }
    if permission not in permission_names:
        raise AccessControlError(f"{permission} permission is required")
    return user


def _require_integration_catalog_access(
    auth_claims: dict[str, Any], team_id: str, *, allow_agent_management: bool = False
) -> dict[str, Any]:
    """Authorize integration catalog access without making unassigned items public."""
    normalized_team_id = str(team_id or "").strip()
    if normalized_team_id:
        try:
            user, _ = _require_team_access(
                auth_claims, normalized_team_id, permission="Manage integrations"
            )
            return user
        except AccessControlError:
            if not allow_agent_management:
                raise
            user, _ = _require_team_access(
                auth_claims, normalized_team_id, permission="Manage agents"
            )
            return user
    user = _application_user_for_claims(auth_claims)
    if not user or user.get("active", True) is not True:
        raise AccessControlError("The signed-in application user is unavailable")
    if user.get("is_sys_admin") is not True:
        raise AccessControlError("Only a system administrator can manage unassigned integrations")
    return user


def _require_agent_integration_team(agent_id: str, integration: dict[str, Any] | None) -> None:
    team = get_team_by_agent_id(str(agent_id or ""))
    if not team or not integration:
        raise AccessControlError("Agent or integration not found", status_code=404)
    integration_team_id = str(integration.get("team_id") or "")
    if not integration_team_id or integration_team_id != str(team.get("_id") or ""):
        raise AccessControlError("Integration is not assigned to the Agent's team")


def _require_user_management_target(
    auth_claims: dict[str, Any], user_id: str, *, destructive: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    actor = _require_system_permission(auth_claims, "Manage users")
    target = get_user_by_id(str(user_id or ""))
    if not target:
        raise AccessControlError("User not found", status_code=404)
    if target.get("is_sys_admin") is True and actor.get("is_sys_admin") is not True:
        raise AccessControlError("Only a system administrator can manage another system administrator")
    if destructive and target.get("is_sys_admin") is True:
        if str(actor.get("_id") or "") == str(target.get("_id") or ""):
            raise AccessControlError("A system administrator cannot delete or deactivate their own account")
        active_admins = [
            item
            for item in get_all_user_by_is_sys_admin(True)
            if item.get("active", True) is True
        ]
        if len(active_admins) <= 1:
            raise AccessControlError("The last active system administrator cannot be removed")
    return actor, target


def _normalize_data_group_access(
    *,
    access_mode: Any,
    users_id: Any,
    team: dict[str, Any],
) -> tuple[str, list[str]]:
    normalized_mode = str(access_mode or "team").strip().lower()
    if normalized_mode not in {"team", "selected_users"}:
        raise AccessControlError("access_mode must be team or selected_users", status_code=400)
    if not isinstance(users_id, list) or not all(isinstance(item, str) for item in users_id):
        raise AccessControlError("users_id must be an array of user IDs", status_code=400)
    normalized_users = list(dict.fromkeys(item.strip() for item in users_id if item.strip()))
    if normalized_mode == "team":
        return normalized_mode, []
    team_user_ids = {str(item) for item in (team.get("user_id") or [])}
    if not normalized_users:
        raise AccessControlError("Selected users mode requires at least one user", status_code=400)
    if any(item not in team_user_ids for item in normalized_users):
        raise AccessControlError("A selected data-group user is not a member of this team")
    return normalized_mode, normalized_users


def _validate_permission_ids(permission_ids: Any, *, permission_type: str) -> list[str]:
    if not isinstance(permission_ids, list) or not all(isinstance(item, str) for item in permission_ids):
        raise AccessControlError("permissions_id must be an array of permission IDs", status_code=400)
    normalized = list(dict.fromkeys(item.strip() for item in permission_ids if item.strip()))
    permissions = {str(item.get("_id")): item for item in get_all_permissions()}
    invalid = [item for item in normalized if item not in permissions]
    if invalid:
        raise AccessControlError("One or more permissions do not exist", status_code=400)
    expected = permission_type.strip().lower()
    if any(expected not in str(permissions[item].get("type") or "").lower() for item in normalized):
        raise AccessControlError(f"Only {permission_type} permissions are allowed here", status_code=400)
    return normalized


def _effective_access_for_request(
    auth_claims: dict[str, Any],
    *,
    team_id: str,
    data_group_ids: Any = None,
    selected_scopes: Any = None,
    agent_id: str | None = None,
) -> EffectiveAccess:
    team = get_team_by_id(team_id)
    group_documents = [
        get_data_group_by_id(str(group_id))
        for group_id in ((team or {}).get("data_group_id") or [])
    ]
    return resolve_effective_access(
        user=_application_user_for_claims(auth_claims),
        team=team,
        data_groups=group_documents,
        requested_data_group_ids=data_group_ids,
        requested_scopes=selected_scopes,
        agent_id=agent_id,
    )


def _authorized_request_claims(
    request_json: dict[str, Any],
    auth_claims: dict[str, Any],
    *,
    agent_id: str | None,
) -> dict[str, Any]:
    if agent_id:
        selected_agent = get_agent_by_id(str(agent_id))
        if selected_agent and not is_active_agent(selected_agent):
            raise AccessControlError("The selected agent is still a draft", status_code=409)
    team_id = str(request_json.get("team_id") or request_json.get("gid") or "").strip()
    requested_groups = request_json.get("data_groups_id")
    requested_scopes = request_json.get("selected_scopes")
    if not team_id:
        if requested_groups:
            raise AccessControlError("A team is required when selecting data groups", status_code=400)
        claims = dict(auth_claims)
        if requested_scopes is not None:
            if not isinstance(requested_scopes, list) or len(requested_scopes) > 2:
                raise AccessControlError("selected_scopes must be an array", status_code=400)
            scopes = list(dict.fromkeys(str(item) for item in requested_scopes))
            if any(item not in {"global", "personal"} for item in scopes):
                raise AccessControlError("selected_scopes contains an unsupported scope", status_code=400)
            claims["selected_scopes"] = scopes
            claims["data_groups_id"] = []
        return claims

    access = _effective_access_for_request(
        auth_claims,
        team_id=team_id,
        data_group_ids=requested_groups,
        selected_scopes=requested_scopes,
        agent_id=agent_id,
    )
    claims = dict(auth_claims)
    claims["team_id"] = access.team_id
    claims["data_groups_id"] = list(access.selected_data_group_ids)
    claims["selected_scopes"] = list(access.selected_scopes)
    claims["application_user_id"] = access.user_id
    return claims


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


def _normalize_embedding_profile_payload(
    body: dict[str, Any], existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    provider = parse_model_provider(str(body.get("provider") or ""))
    model = str(body.get("model") or "").strip()
    deployment = str(body.get("deployment") or "").strip() or None
    endpoint = str(body.get("endpoint") or "").strip().rstrip("/") or None
    base_url = str(body.get("base_url") or "").strip().rstrip("/") or None
    collection_name = str(body.get("collection_name") or "").strip()
    try:
        dimensions = int(body.get("dimensions"))
    except (TypeError, ValueError) as error:
        raise ValueError("Embedding dimensions must be an integer") from error

    if not name:
        raise ValueError("Profile name is required")
    if not model:
        raise ValueError("Embedding model is required")
    if dimensions <= 0 or dimensions > 65536:
        raise ValueError("Embedding dimensions must be between 1 and 65536")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", collection_name):
        raise ValueError("Qdrant collection must use 1-128 letters, numbers, dots, underscores, or hyphens")
    if provider == ModelProvider.AZURE_OPENAI:
        parsed_endpoint = urlparse(endpoint or "")
        if not endpoint or parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
            raise ValueError("Azure OpenAI embedding profile requires an HTTP(S) endpoint")
        if parsed_endpoint.username or parsed_endpoint.password or parsed_endpoint.query or parsed_endpoint.fragment:
            raise ValueError("Embedding endpoint must not contain credentials, query parameters, or fragments")
        if not deployment:
            raise ValueError("Azure OpenAI embedding profile requires a deployment")
    if provider == ModelProvider.OPENAI_COMPATIBLE:
        parsed_base_url = urlparse(base_url or "")
        if not base_url or parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
            raise ValueError("OpenAI-compatible embedding profile requires an HTTP(S) base URL")
        if parsed_base_url.username or parsed_base_url.password or parsed_base_url.query or parsed_base_url.fragment:
            raise ValueError("Embedding base URL must not contain credentials, query parameters, or fragments")

    api_key_ciphertext = existing.get("api_key_ciphertext") if existing else None
    if body.get("clear_api_key"):
        api_key_ciphertext = None
    elif str(body.get("api_key") or "").strip():
        api_key_ciphertext = encrypt_provider_secret(str(body["api_key"]).strip())
    enabled = bool(body.get("enabled", True))
    if provider == ModelProvider.OPENAI and enabled and not api_key_ciphertext:
        raise ValueError("OpenAI embedding profile requires an API key")

    return {
        "name": name,
        "provider": provider.value,
        "model": model,
        "deployment": deployment if provider == ModelProvider.AZURE_OPENAI else None,
        "dimensions": dimensions,
        "collection_name": collection_name,
        "endpoint": endpoint if provider == ModelProvider.AZURE_OPENAI else None,
        "base_url": base_url if provider == ModelProvider.OPENAI_COMPATIBLE else None,
        "api_version": (
            str(body.get("api_version") or "").strip() or "2024-10-21"
            if provider == ModelProvider.AZURE_OPENAI
            else None
        ),
        "organization": str(body.get("organization") or "").strip() or None,
        "enabled": enabled,
        "api_key_ciphertext": api_key_ciphertext,
    }


def _serialize_embedding_profile(document: dict[str, Any], *, environment: bool = False) -> dict[str, Any]:
    def public_url(value: object) -> str | None:
        parsed = urlparse(str(value or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{host}{parsed.path}".rstrip("/")

    return {
        "_id": str(document["_id"]),
        "name": str(document["name"]),
        "provider": str(document["provider"]),
        "model": str(document["model"]),
        "deployment": document.get("deployment"),
        "dimensions": int(document["dimensions"]),
        "collection_name": str(document["collection_name"]),
        "endpoint": public_url(document.get("endpoint")),
        "base_url": public_url(document.get("base_url")),
        "api_version": document.get("api_version"),
        "organization": document.get("organization"),
        "enabled": bool(document.get("enabled", True)),
        "has_api_key": bool(document.get("api_key_ciphertext")) or bool(document.get("has_api_key")),
        "environment": environment,
        "created_at": document.get("created_at").isoformat() if document.get("created_at") else None,
        "updated_at": document.get("updated_at").isoformat() if document.get("updated_at") else None,
    }


def _environment_embedding_profile() -> dict[str, Any]:
    settings = RuntimeSettings.from_env(os.environ).embedding
    return {
        "_id": ENVIRONMENT_PROFILE_ID,
        "name": "Environment default",
        "provider": settings.provider.value,
        "model": settings.model,
        "deployment": settings.deployment,
        "dimensions": settings.dimensions,
        "collection_name": os.getenv("QDRANT_COLLECTION", os.getenv("AZURE_SEARCH_INDEX", "gptkbindex")),
        "endpoint": settings.endpoint,
        "base_url": settings.base_url,
        "api_version": settings.api_version,
        "organization": settings.organization,
        "enabled": True,
        "has_api_key": bool(settings.api_key),
    }


def _settings_for_embedding_profile(profile: dict[str, Any]) -> EmbeddingProviderSettings:
    return EmbeddingProviderSettings(
        provider=parse_model_provider(str(profile["provider"])),
        model=str(profile["model"]),
        deployment=profile.get("deployment"),
        dimensions=int(profile["dimensions"]),
        api_version=str(profile.get("api_version") or "2024-10-21"),
        endpoint=profile.get("endpoint"),
        base_url=profile.get("base_url"),
        api_key=decrypt_provider_secret(profile.get("api_key_ciphertext")),
        organization=profile.get("organization"),
    )


def _serialize_embedding_settings() -> dict[str, Any]:
    value = get_embedding_settings()
    return {
        **value,
        "activated_at": value["activated_at"].isoformat() if value.get("activated_at") else None,
        "runtime_started_at": value["runtime_started_at"].isoformat() if value.get("runtime_started_at") else None,
    }


async def _probe_embedding_profile(profile_id: str) -> tuple[EmbeddingProviderSettings, int]:
    profile = _environment_embedding_profile() if profile_id == ENVIRONMENT_PROFILE_ID else get_embedding_profile(profile_id)
    if not profile:
        raise ValueError("Embedding profile not found")
    settings = (
        RuntimeSettings.from_env(os.environ).embedding
        if profile_id == ENVIRONMENT_PROFILE_ID
        else _settings_for_embedding_profile(profile)
    )
    service = create_embedding_service(settings, current_app.config[CONFIG_CREDENTIAL])
    vectors = await service.create_embeddings(["NexoraAI embedding connection test"]) if service else []
    actual_dimensions = len(vectors[0]) if vectors else 0
    if actual_dimensions != settings.dimensions:
        raise ValueError(
            f"Provider returned {actual_dimensions} dimensions; profile expects {settings.dimensions}"
        )
    qdrant = QdrantKnowledgeSearchClient(
        endpoint=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
        collection_name=str(profile["collection_name"]),
        vector_size=settings.dimensions,
        vector_field=os.getenv("AZURE_SEARCH_FIELD_NAME_EMBEDDING", "embedding"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    await qdrant.ensure_ready()
    return settings, actual_dimensions


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
        completion_options["max_completion_tokens"] = 256
    else:
        # Thinking-capable local models such as Qwen can consume the first few
        # dozen tokens before emitting the required tool call. A 32-token probe
        # therefore produced a false "unsupported" result even though Ollama
        # advertised and successfully executed tools.
        completion_options.update({"max_tokens": 256, "temperature": 0})
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


def _knowledge_store() -> KnowledgeObjectStore:
    store = current_app.config.get(CONFIG_KNOWLEDGE_STORE)
    azure_clients = {
        "global": current_app.config.get(CONFIG_BLOB_CONTAINER_CLIENT),
        "team": current_app.config.get(CONFIG_GROUP_BLOB_CONTAINER_CLIENT),
        "personal": current_app.config.get(CONFIG_USER_BLOB_CONTAINER_CLIENT),
        "web_global": current_app.config.get(CONFIG_WEB_BLOB_CONTAINER_CLIENT),
        "web_team": current_app.config.get(CONFIG_WEB_GROUP_BLOB_CONTAINER_CLIENT),
    }
    if store is None or (
        isinstance(store, AzureKnowledgeObjectStore) and not store.matches_clients(azure_clients)
    ):
        store = AzureKnowledgeObjectStore(azure_clients)
        current_app.config[CONFIG_KNOWLEDGE_STORE] = store
    return store


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
    store = _knowledge_store()
    try:
        stored = await store.read("global", path)
    except KnowledgeObjectNotFound:
        current_app.logger.info(
            "Path not found in global Knowledge storage: %s", path)
        if current_app.config[CONFIG_USER_UPLOAD_ENABLED]:
            try:
                user_oid = auth_claims["oid"]
                stored = await store.read("personal", f"{user_oid}/{path}")
            except KnowledgeObjectNotFound:
                try:
                    stored = await store.read("team", path)
                except KnowledgeObjectNotFound:
                    current_app.logger.exception(
                        "Path not found in Knowledge storage: %s", path)
                    abort(404)
        else:
            abort(404)
    mime_type = stored.content_type
    blob_file = io.BytesIO(stored.data)
    blob_file.seek(0)
    return await send_file(blob_file, mimetype=mime_type, as_attachment=False, attachment_filename=path)


@bp.route("/ask", methods=["POST"])
@authenticated
async def ask(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    agent_id = request_json.get("agent_id")
    try:
        context["auth_claims"] = _authorized_request_claims(
            request_json, auth_claims, agent_id=agent_id
        )
        selected_scopes = context["auth_claims"].get("selected_scopes") or []
        current_app.logger.info(
            "Knowledge selection: personal=%s global=%s data_groups=%d",
            "personal" in selected_scopes,
            "global" in selected_scopes,
            len(context["auth_claims"].get("data_groups_id") or []),
        )
        _prepare_usage_request(request_json, context)
        context["conversation_id"] = ensure_conversation_id(request_json.get("conversation_id"))
        _apply_agent_llm_profile(context, agent_id)
        await _enforce_llm_quota(
            context.get("auth_claims") or auth_claims, context, request_json, workload="ask"
        )
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

        await _persist_user_usage(
            context.get("auth_claims") or auth_claims,
            r,
            "ask",
            _usage_metadata(context, agent_id, "ask"),
            context,
        )
        return jsonify(r)
    except Exception as error:
        await _finish_usage_reservation(context, state="released")
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
        "_requirements_evidence_matrix",
        "_requirements_attachment_id",
        "_knowledge_search_context",
    ):
        overrides.pop(key, None)
    attachment_ids = normalize_attachment_ids(request_json.get("document_attachment_ids"))
    evidence_matrix = request_json.get("evidence_matrix", False)
    if not isinstance(evidence_matrix, bool):
        raise AttachmentRetrievalError("evidence_matrix must be a boolean")
    if not attachment_ids:
        if evidence_matrix:
            raise AttachmentRetrievalError("Evidence matrix mode requires a requirements attachment")
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
    requested_scope = request_json.get("attachment_evidence_scope")
    if evidence_matrix and requested_scope is None:
        requested_scope = ATTACHMENT_EVIDENCE_KNOWLEDGE_ONLY
    evidence_scope = normalize_attachment_evidence_scope(requested_scope, query=query)
    overrides["_attachment_evidence_scope"] = evidence_scope
    if evidence_scope == ATTACHMENT_EVIDENCE_KNOWLEDGE_ONLY and not evidence_matrix:
        return
    search_arguments = {
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "query": query,
        "attachment_ids": attachment_ids,
    }
    if evidence_matrix:
        search_arguments["limit"] = 20
    results = await index.search(**search_arguments)
    matrix_evidence = (
        bounded_attachment_evidence(results, max_results=20, max_characters=24_000)
        if evidence_matrix
        else None
    )
    sources = (
        [
            f"{citation}: Display filename: {source_display_filename(result.filename)}. Content: {text}"
            for result, citation, text in matrix_evidence
        ]
        if matrix_evidence is not None
        else format_attachment_sources(results)
    )
    if not sources:
        raise AttachmentRetrievalError("No readable text was found in the selected document attachments")
    overrides["_temporary_attachment_sources"] = sources
    overrides["_temporary_attachment_ids"] = attachment_ids
    overrides["_temporary_attachment_index"] = index
    overrides["_temporary_attachment_owner_id"] = owner_id
    overrides["_temporary_attachment_conversation_id"] = conversation_id
    overrides["_temporary_attachments_only"] = evidence_scope == ATTACHMENT_EVIDENCE_UPLOADED_ONLY
    if evidence_matrix:
        checklist_id = attachment_ids[0]
        matrix_instruction = (
            f"{REQUIREMENTS_EVIDENCE_MATRIX_INSTRUCTION}\n"
            f"The checklist attachment ID is {checklist_id}. The allowed evidence scope is {evidence_scope}."
        )
        existing_prompt = str(overrides.get("prompt_template") or "").strip()
        overrides["prompt_template"] = (
            f"{existing_prompt}\n\nBackend-enforced workflow:\n{matrix_instruction}".strip()
        )
        overrides["_requirements_evidence_matrix"] = True
        overrides["_requirements_attachment_id"] = checklist_id
        # Legacy retrieval needs requirement terms before answer synthesis. Keep
        # this bounded and server-derived; clients cannot inject this override.
        overrides["_knowledge_search_context"] = "\n".join(
            text for _, _, text in matrix_evidence or []
        )[:4_000]
        overrides["top"] = max(10, min(int(overrides.get("top") or 10), 20))
        overrides["use_agentic_retrieval"] = False


def _use_langgraph_runtime(agent_id: str | None) -> bool:
    mode = os.getenv("AGENT_RUNTIME_MODE", "per_agent").strip().lower()
    if mode in ("legacy", "langgraph"):
        return mode == "langgraph"
    if agent_id:
        agent = get_agent_by_id(agent_id)
        configured = str((agent or {}).get("config", {}).get("runtime") or "").strip().lower() if is_active_agent(agent) else ""
        if configured in ("legacy", "langgraph"):
            return configured == "langgraph"
    return False


def _guardrail_policy_for_agent(
    agent_id: str | None, team_id: str | None = None
) -> GuardrailPolicy:
    agent = get_agent_by_id(agent_id) if agent_id else None
    if not is_active_agent(agent):
        agent = None
    system_config = get_guardrail_settings()
    team_config = get_guardrail_settings(team_id) if team_id else None
    return merge_guardrail_policies(
        GuardrailPolicy.from_config(system_config) if system_config is not None else None,
        GuardrailPolicy.from_config(team_config) if team_config is not None else None,
        GuardrailPolicy.from_config(((agent or {}).get("config") or {}).get("guardrails")),
    )


async def _enforce_input_guardrails(
    *,
    messages: object,
    agent_id: str | None,
    team_id: str | None,
    auth_claims: dict[str, Any],
) -> tuple[GuardrailPolicy, AuditTrail]:
    policy = _guardrail_policy_for_agent(agent_id, team_id)
    audit = AuditTrail(
        agent_id=str(agent_id or "system"),
        team_id=team_id,
        auth_claims=auth_claims,
    )
    result = evaluate_guardrail_input(messages, policy)
    if result.findings:
        await audit.emit(
            "guardrail_input_evaluated",
            status="denied" if result.blocked else "warning",
            source="guardrail",
            details=result.audit_details(direction="input"),
        )
    if result.blocked:
        raise GuardrailViolation(
            guardrail_blocked_message(result, direction="input"),
            category=result.findings[0].category,
            detector_ids=tuple(finding.detector_id for finding in result.findings),
        )
    return policy, audit


async def _prepare_guardrail_context(
    context: dict[str, Any], policy: GuardrailPolicy, audit: AuditTrail
) -> None:
    if not policy.enabled:
        return
    overrides = context.setdefault("overrides", {})
    sources = overrides.get("_temporary_attachment_sources")
    if not isinstance(sources, list):
        return
    sanitized_sources: list[str] = []
    findings = []
    redacted = False
    for source in sources:
        result = sanitize_untrusted_context(str(source), policy)
        sanitized_sources.append(result.text)
        findings.extend(result.findings)
        redacted = redacted or result.redacted
    overrides["_temporary_attachment_sources"] = sanitized_sources
    if findings:
        summary = GuardrailResult(
            text="",
            findings=tuple(findings),
            redacted=redacted,
        )
        await audit.emit(
            "guardrail_retrieval_evaluated",
            status="redacted" if redacted else "warning",
            source="guardrail",
            details=summary.audit_details(direction="retrieval"),
        )


async def _apply_guardrails_to_response(
    response: dict[str, Any], policy: GuardrailPolicy, audit: AuditTrail
) -> dict[str, Any]:
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        return response
    result = evaluate_guardrail_output(message["content"], policy)
    if result.findings:
        await audit.emit(
            "guardrail_output_evaluated",
            status="denied" if result.blocked else "redacted" if result.redacted else "warning",
            source="guardrail",
            details=result.audit_details(direction="output"),
        )
    message["content"] = (
        guardrail_blocked_message(result, direction="output") if result.blocked else result.text
    )
    return response


def _stream_event_content(event: dict[str, Any]) -> str | None:
    delta = event.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        return delta["content"]
    choices = event.get("choices")
    if isinstance(choices, list) and choices:
        choice_delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
        if isinstance(choice_delta, dict) and isinstance(choice_delta.get("content"), str):
            return choice_delta["content"]
    return None


def _clear_stream_event_content(event: dict[str, Any]) -> None:
    delta = event.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        delta["content"] = None
    choices = event.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            choice_delta = choice.get("delta") if isinstance(choice, dict) else None
            if isinstance(choice_delta, dict) and isinstance(choice_delta.get("content"), str):
                choice_delta["content"] = None


async def _guardrail_response_stream(
    result: AsyncGenerator[dict, None], policy: GuardrailPolicy, audit: AuditTrail
) -> AsyncGenerator[dict, None]:
    if not policy.enabled or (
        policy.sensitive_output_action == "allow"
        and policy.pii_output_action == "allow"
        and policy.content_safety_output_action == "allow"
    ):
        async for event in result:
            yield event
        return

    buffered_events: list[dict[str, Any]] = []
    content_parts: list[str] = []
    uses_choices = False
    async for event in result:
        # Some legacy approaches reuse and mutate context objects between
        # chunks. Snapshot each event at arrival so buffering does not change
        # the observable stream.
        buffered_events.append(copy.deepcopy(event))
        content = _stream_event_content(event)
        if content is not None:
            content_parts.append(content)
            uses_choices = uses_choices or isinstance(event.get("choices"), list)

    output = evaluate_guardrail_output("".join(content_parts), policy)
    if not output.findings:
        for event in buffered_events:
            yield event
        return

    await audit.emit(
        "guardrail_output_evaluated",
        status="denied" if output.blocked else "redacted" if output.redacted else "warning",
        source="guardrail",
        details=output.audit_details(direction="output"),
    )
    for event in buffered_events:
        _clear_stream_event_content(event)
        yield event
    safe_content = (
        guardrail_blocked_message(output, direction="output") if output.blocked else output.text
    )
    if uses_choices:
        yield {
            "choices": [
                {"delta": {"role": "assistant", "content": safe_content}, "index": 0, "finish_reason": None}
            ]
        }
    else:
        yield {"delta": {"role": "assistant", "content": safe_content}}


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
    diagram_artifact = (result.get("artifacts") or {}).get("diagram")
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
            **({"diagram": diagram_artifact} if diagram_artifact else {}),
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
    try:
        agent_id = request_json.get("agent_id")
        team_id = request_json.get("team_id")
        context["auth_claims"] = _authorized_request_claims(
            request_json, auth_claims, agent_id=agent_id
        )
        selected_scopes = context["auth_claims"].get("selected_scopes") or []
        current_app.logger.info(
            "Knowledge selection: personal=%s global=%s data_groups=%d",
            "personal" in selected_scopes,
            "global" in selected_scopes,
            len(context["auth_claims"].get("data_groups_id") or []),
        )
        _prepare_usage_request(request_json, context)
        guardrail_policy, guardrail_audit = await _enforce_input_guardrails(
            messages=request_json.get("messages"),
            agent_id=agent_id,
            team_id=team_id,
            auth_claims=context["auth_claims"],
        )
        context["conversation_id"] = ensure_conversation_id(request_json.get("conversation_id"))
        _apply_agent_llm_profile(context, agent_id)
        await _enforce_llm_quota(
            context.get("auth_claims") or auth_claims, context, request_json, workload="chat"
        )
        overrides = context.get("overrides", {})
        _apply_inline_image_attachments(
            request_json,
            context,
            vision_enabled=overrides.get("_agent_image_input_enabled", False),
            vision_available=CONFIG_CHAT_VISION_APPROACH in current_app.config,
            select_vision_from_attachments=bool(agent_id),
        )
        await _apply_temporary_attachment_retrieval(request_json, context, auth_claims)
        await _prepare_guardrail_context(context, guardrail_policy, guardrail_audit)
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
                current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]
                or current_app.config[CONFIG_CHAT_HISTORY_DATABASE_ENABLED],
                current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
            )
        result = await approach.run(
            request_json["messages"],
            context=context,
            session_state=session_state,
        )
        guarded_result = await _apply_guardrails_to_response(result, guardrail_policy, guardrail_audit)
        await _persist_user_usage(
            context.get("auth_claims") or auth_claims,
            guarded_result,
            "ask",
            _usage_metadata(context, agent_id, "chat"),
            context,
        )
        return jsonify(guarded_result)
    except Exception as error:
        await _finish_usage_reservation(context, state="released")
        return error_response(error, "/chat")


def _agent_invocation_prompt(agent: dict[str, Any]) -> str:
    prompt = agent.get("prompt") or {}
    if isinstance(prompt, str):
        return prompt.strip()
    if not isinstance(prompt, dict):
        return ""
    labels = (
        ("Role", "role"),
        ("Task", "task"),
        ("Detail Context", "detail_context"),
        ("Constraints", "constraints"),
        ("Output Format", "output_format"),
    )
    sections = [
        f"{label}:\n{str(prompt.get(field)).strip()}"
        for label, field in labels
        if str(prompt.get(field) or "").strip()
    ]
    return "\n\n".join(sections)


def _team_wide_invocation_data_groups(team: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for group_id in team.get("data_group_id") or []:
        group = get_data_group_by_id(str(group_id))
        if not group:
            continue
        member_ids = [str(item) for item in (group.get("user_id") or [])]
        access_mode = str(group.get("access_mode") or "").strip().lower()
        if not access_mode:
            access_mode = "team" if not member_ids else "selected_users"
        if access_mode == "team":
            result.append(
                {
                    "_id": str(group.get("_id") or ""),
                    "name": str(group.get("name") or group.get("_id") or ""),
                }
            )
    return result


def _external_published_invocation_data_groups(
    team: dict[str, Any],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in _team_wide_invocation_data_groups(team):
        group = get_data_group_by_id(item["_id"])
        if (
            group
            and str(group.get("exposure") or "internal").strip().lower()
            == EXPOSURE_EXTERNAL
            and str(group.get("publication_status") or "").strip().lower()
            == "published"
        ):
            result.append(item)
    return result


def _validate_agent_invocation_scope(
    team: dict[str, Any],
    *,
    agent_ids: object,
    data_group_ids: object,
    access_type: object = ACCESS_TYPE_INTERNAL,
) -> tuple[list[str], list[str]]:
    normalized_access_type = normalize_agent_invocation_access_type(access_type)
    if not isinstance(agent_ids, list) or not agent_ids:
        raise AgentInvocationKeyError(
            "allowed_agent_ids must contain at least one Agent"
        )
    normalized_agents = list(
        dict.fromkeys(
            str(item or "").strip() for item in agent_ids if str(item or "").strip()
        )
    )
    team_agent_ids = {str(item) for item in (team.get("agent_id") or [])}
    if any(item not in team_agent_ids for item in normalized_agents):
        raise AgentInvocationKeyError(
            "One or more Agents do not belong to this Team", status_code=403
        )
    for selected_agent_id in normalized_agents:
        selected_agent = get_agent_by_id(selected_agent_id)
        if not is_active_agent(selected_agent):
            raise AgentInvocationKeyError(
                "Only active Agents can be exposed through the API", status_code=409
            )
        runtime = str(
            ((selected_agent or {}).get("config") or {}).get("runtime") or "legacy"
        ).strip().lower()
        if runtime != "langgraph":
            raise AgentInvocationKeyError(
                "Agent Invocation API currently supports only LangGraph Agents",
                status_code=409,
            )

        agent_config = (selected_agent or {}).get("config") or {}
        agent_tools = agent_config.get("tool_settings") or {}
        knowledge_mode = str(agent_tools.get("knowledge_search") or "auto").lower()
        if (
            normalized_access_type == ACCESS_TYPE_EXTERNAL
            and knowledge_mode == "disabled"
        ):
            raise AgentInvocationKeyError(
                "External customer Agents must enable Knowledge Search",
                status_code=409,
            )
    if not isinstance(data_group_ids, list):
        raise AgentInvocationKeyError("allowed_data_group_ids must be an array")
    normalized_groups = list(
        dict.fromkeys(
            str(item or "").strip()
            for item in data_group_ids
            if str(item or "").strip()
        )
    )
    eligible_groups = (
        _external_published_invocation_data_groups(team)
        if normalized_access_type == ACCESS_TYPE_EXTERNAL
        else _team_wide_invocation_data_groups(team)
    )
    allowed_groups = {item["_id"] for item in eligible_groups}
    if any(item not in allowed_groups for item in normalized_groups):
        raise AgentInvocationKeyError(
            "The selected Knowledge scope is not eligible for this access type",
            status_code=403,
        )
    return normalized_agents, normalized_groups


def _agent_invocation_bearer_token() -> str:
    authorization = str(request.headers.get("Authorization") or "").strip()
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise AgentInvocationKeyError(
            "Authorization: Bearer <API key> is required", status_code=401
        )
    return token.strip()


def _agent_invocation_request_body(body: object) -> tuple[str, str | None]:
    if not isinstance(body, dict):
        raise AgentInvocationKeyError("request body must be an object")
    input_text = str(body.get("input") or "").strip()
    try:
        maximum = max(
            1,
            min(
                int(
                    os.getenv("AGENT_INVOCATION_MAX_INPUT_CHARACTERS", "32768")
                ),
                262144,
            ),
        )
    except ValueError:
        maximum = 32768
    if not input_text:
        raise AgentInvocationKeyError("input is required")
    if len(input_text) > maximum:
        raise AgentInvocationKeyError(
            f"input exceeds the {maximum} character limit", status_code=413
        )
    conversation_id = str(body.get("conversation_id") or "").strip() or None
    return input_text, conversation_id


def _validate_agent_invocation_target(
    key_document: dict[str, Any], agent_id: str
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    team_id = str(key_document.get("team_id") or "")
    team = get_team_by_id(team_id)
    if not team or agent_id not in {
        str(item) for item in (team.get("agent_id") or [])
    }:
        raise AgentInvocationKeyError(
            "Agent is unavailable to this API key", status_code=404
        )
    if agent_id not in {
        str(item) for item in (key_document.get("allowed_agent_ids") or [])
    }:
        raise AgentInvocationKeyError(
            "Agent is not allowed for this API key", status_code=403
        )
    agent = get_agent_by_id(agent_id)
    if not is_active_agent(agent):
        raise AgentInvocationKeyError("Agent is not active", status_code=409)
    if not _use_langgraph_runtime(agent_id):
        raise AgentInvocationKeyError(
            "Agent Invocation API currently requires the LangGraph runtime",
            status_code=409,
        )

    access_type = normalize_agent_invocation_access_type(
        key_document.get("access_type")
    )
    eligible_groups = (
        _external_published_invocation_data_groups(team)
        if access_type == ACCESS_TYPE_EXTERNAL
        else _team_wide_invocation_data_groups(team)
    )
    available_groups = {item["_id"] for item in eligible_groups}
    data_group_ids = [
        str(item) for item in (key_document.get("allowed_data_group_ids") or [])
    ]
    if any(item not in available_groups for item in data_group_ids):
        raise AgentInvocationKeyError(
            "The API key references Knowledge that is no longer eligible",
            status_code=403,
        )
    return team, agent or {}, data_group_ids


def _agent_invocation_public_response(
    result: dict[str, Any],
    *,
    request_id: str,
    agent_id: str,
    conversation_id: str,
    access_type: object = ACCESS_TYPE_INTERNAL,
) -> dict[str, Any]:
    result_context = result.get("context") or {}
    external_channel = (
        normalize_agent_invocation_access_type(access_type) == ACCESS_TYPE_EXTERNAL
    )
    return {
        "id": request_id,
        "object": "agent.invocation",
        "agent_id": agent_id,
        "conversation_id": conversation_id,
        "output": str((result.get("message") or {}).get("content") or ""),
        "citations": []
        if external_channel
        else ((result_context.get("data_points") or {}).get("text") or []),
        "chart": None if external_channel else result_context.get("chart"),
        "diagram": None if external_channel else result_context.get("diagram"),
    }


async def _execute_agent_invocation(
    *,
    key_document: dict[str, Any],
    agent_id: str,
    input_text: str,
    conversation_id: str | None,
    usage_context: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    team_id = str(key_document.get("team_id") or "")
    _team, agent, data_group_ids = _validate_agent_invocation_target(
        key_document, agent_id
    )

    access_type = normalize_agent_invocation_access_type(
        key_document.get("access_type")
    )
    normalized_conversation_id = ensure_conversation_id(conversation_id)
    service_id = f"service:{key_document['_id']}"
    auth_claims = {
        "oid": service_id,
        "application_user_id": service_id,
        "auth_provider": "agent_api_key",
        "service_principal_id": str(key_document["_id"]),
        "agent_api_access_type": access_type,
        "external_channel": access_type == ACCESS_TYPE_EXTERNAL,
        "team_id": team_id,
        "data_groups_id": data_group_ids,
        "selected_scopes": (
            ["global"]
            if access_type == ACCESS_TYPE_INTERNAL
            and key_document.get("allow_global_knowledge") is True
            else []
        ),
    }
    request_json: dict[str, Any] = {
        "agent_id": agent_id,
        "team_id": team_id,
        "conversation_id": normalized_conversation_id,
        "usage_request_id": str(uuid.uuid4()),
        "messages": [{"role": "user", "content": input_text}],
    }
    context = usage_context
    context.update({
        "auth_claims": auth_claims,
        "conversation_id": normalized_conversation_id,
        "overrides": {},
    })
    _prepare_usage_request(request_json, context)
    guardrail_policy, guardrail_audit = await _enforce_input_guardrails(
        messages=request_json["messages"],
        agent_id=agent_id,
        team_id=team_id,
        auth_claims=auth_claims,
    )
    _apply_agent_llm_profile(context, agent_id)
    await _enforce_llm_quota(
        auth_claims, context, request_json, workload="agent_api"
    )
    await _prepare_guardrail_context(context, guardrail_policy, guardrail_audit)
    approach = cast(Approach, current_app.config[CONFIG_CHAT_APPROACH])
    session_state = create_session_id(False, False)
    stream = _run_langgraph_as_chat_stream(
        approach=approach,
        messages=request_json["messages"],
        context=context,
        auth_claims=auth_claims,
        agent_id=agent_id,
        team_id=team_id,
        system_prompt=_agent_invocation_prompt(agent or {}),
        session_state=session_state,
    )
    guarded_stream = _guardrail_response_stream(
        stream, guardrail_policy, guardrail_audit
    )
    content_parts: list[str] = []
    response_context: dict[str, Any] = {}
    async for event in guarded_stream:
        content = _stream_event_content(event)
        if content:
            content_parts.append(content)
        event_context = event.get("context")
        if isinstance(event_context, dict):
            response_context.update(event_context)

    result = {
        "message": {"role": "assistant", "content": "".join(content_parts)},
        "context": response_context,
        "session_state": session_state,
    }
    await _persist_user_usage(
        auth_claims,
        result,
        "agent_api",
        _usage_metadata(context, agent_id, "agent_api"),
        context,
    )
    return result, normalized_conversation_id


@bp.get("/teams/<team_id>/agent-api-keys")
@authenticated
async def get_team_agent_api_keys(auth_claims: dict[str, Any], team_id: str):
    try:
        _actor, team = _require_team_access(
            auth_claims, team_id, permission="Manage agents"
        )
        agents = []
        for agent_id in team.get("agent_id") or []:
            agent = get_agent_by_id(str(agent_id))
            runtime = str(
                ((agent or {}).get("config") or {}).get("runtime") or "legacy"
            ).strip().lower()
            if is_active_agent(agent) and runtime == "langgraph":
                agents.append(
                    {
                        "_id": str(agent_id),
                        "name": str((agent or {}).get("agent_name") or agent_id),
                        "runtime": str(
                            ((agent or {}).get("config") or {}).get("runtime")
                            or "legacy"
                        ),
                    }
                )
        return jsonify(
            {
                "items": list_agent_invocation_keys(team_id),
                "available_agents": agents,
                "available_data_groups": _team_wide_invocation_data_groups(team),
                "available_external_data_groups": (
                    _external_published_invocation_data_groups(team)
                ),
            }
        )
    except Exception as error:
        return error_response(error, "/teams/<team_id>/agent-api-keys")


@bp.post("/teams/<team_id>/agent-api-keys")
@authenticated
async def create_team_agent_api_key(auth_claims: dict[str, Any], team_id: str):
    try:
        if not request.is_json:
            raise AgentInvocationKeyError("request must be json", status_code=415)
        actor, team = _require_team_access(
            auth_claims, team_id, permission="Manage agents"
        )
        body = await request.get_json()
        access_type = normalize_agent_invocation_access_type(
            (body or {}).get("access_type")
        )
        if access_type == ACCESS_TYPE_EXTERNAL:
            actor = _require_system_permission(
                auth_claims, "Manage external channels"
            )
        allow_global_knowledge = (
            (body or {}).get("allow_global_knowledge") is True
        )
        agent_ids, group_ids = _validate_agent_invocation_scope(
            team,
            agent_ids=(body or {}).get("allowed_agent_ids"),
            data_group_ids=(body or {}).get("allowed_data_group_ids") or [],
            access_type=access_type,
        )
        item, token = create_agent_invocation_key(
            team_id=team_id,
            name=(body or {}).get("name"),
            allowed_agent_ids=agent_ids,
            access_type=access_type,
            allowed_data_group_ids=group_ids,
            allow_global_knowledge=allow_global_knowledge,
            expiry_days=(body or {}).get("expiry_days", 90),
            rate_limit_per_minute=(
                (body or {}).get("rate_limit_per_minute", 60)
            ),
            created_by=str(actor.get("_id") or ""),
        )
        insert_agent_invocation_audit(
            request_id=str(uuid.uuid4()),
            key_id=item["_id"],
            team_id=team_id,
            agent_id="",
            event_type="api_key_created",
            status="success",
            access_type=access_type,
        )
        response = jsonify({"item": item, "api_key": token})
        response.status_code = 201
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        return error_response(error, "/teams/<team_id>/agent-api-keys")


@bp.post("/teams/<team_id>/agent-api-keys/<key_id>/rotate")
@authenticated
async def rotate_team_agent_api_key(
    auth_claims: dict[str, Any], team_id: str, key_id: str
):
    try:
        if not request.is_json:
            raise AgentInvocationKeyError("request must be json", status_code=415)
        actor, _team = _require_team_access(
            auth_claims, team_id, permission="Manage agents"
        )
        current = get_agent_invocation_key(key_id)
        if not current or str(current.get("team_id") or "") != team_id:
            raise AgentInvocationKeyError("API key not found", status_code=404)
        body = await request.get_json()
        item, token = rotate_agent_invocation_key(
            key_id,
            actor_id=str(actor.get("_id") or ""),
            expiry_days=(body or {}).get("expiry_days", 90),
        )
        insert_agent_invocation_audit(
            request_id=str(uuid.uuid4()),
            key_id=key_id,
            team_id=team_id,
            agent_id="",
            event_type="api_key_rotated",
            status="success",
            access_type=current.get("access_type"),
        )
        response = jsonify({"item": item, "api_key": token})
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        return error_response(
            error, "/teams/<team_id>/agent-api-keys/<key_id>/rotate"
        )


@bp.delete("/teams/<team_id>/agent-api-keys/<key_id>")
@authenticated
async def revoke_team_agent_api_key(
    auth_claims: dict[str, Any], team_id: str, key_id: str
):
    try:
        actor, _team = _require_team_access(
            auth_claims, team_id, permission="Manage agents"
        )
        current = get_agent_invocation_key(key_id)
        if not current or str(current.get("team_id") or "") != team_id:
            raise AgentInvocationKeyError("API key not found", status_code=404)
        revoked = revoke_agent_invocation_key(
            key_id, actor_id=str(actor.get("_id") or "")
        )
        if revoked:
            insert_agent_invocation_audit(
                request_id=str(uuid.uuid4()),
                key_id=key_id,
                team_id=team_id,
                agent_id="",
                event_type="api_key_revoked",
                status="success",
                access_type=current.get("access_type"),
            )
        return jsonify({"result": "revoked" if revoked else "unchanged"})
    except Exception as error:
        return error_response(error, "/teams/<team_id>/agent-api-keys/<key_id>")


@bp.get("/api/v1/openapi.yaml")
async def get_agent_invocation_openapi():
    response = await send_file(
        Path(__file__).with_name("agent-invocation-openapi.yaml"),
        mimetype="application/yaml",
        as_attachment=False,
    )
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/api/v1/agents/<agent_id>/invoke")
async def invoke_agent_api(agent_id: str):
    request_id = str(uuid.uuid4())
    key_document: dict[str, Any] | None = None
    context: dict[str, Any] = {}
    started = time.monotonic()
    try:
        if not request.is_json:
            raise AgentInvocationKeyError("request must be json", status_code=415)
        key_document = authenticate_agent_invocation_key(
            _agent_invocation_bearer_token()
        )
        enforce_agent_invocation_rate_limit(key_document)
        body = await request.get_json()
        input_text, requested_conversation_id = _agent_invocation_request_body(
            body
        )
        result, conversation_id = await _execute_agent_invocation(
            key_document=key_document,
            agent_id=str(agent_id or ""),
            input_text=input_text,
            conversation_id=requested_conversation_id,
            usage_context=context,
        )
        mark_agent_invocation_key_used(str(key_document["_id"]))
        insert_agent_invocation_audit(
            request_id=request_id,
            key_id=str(key_document["_id"]),
            team_id=str(key_document.get("team_id") or ""),
            agent_id=agent_id,
            event_type="agent_invoked",
            status="success",
            duration_ms=int((time.monotonic() - started) * 1000),
            access_type=key_document.get("access_type"),
        )
        response = jsonify(
            _agent_invocation_public_response(
                result,
                request_id=request_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                access_type=key_document.get("access_type"),
            )
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        await _finish_usage_reservation(context, state="released")
        if key_document:
            insert_agent_invocation_audit(
                request_id=request_id,
                key_id=str(key_document.get("_id") or ""),
                team_id=str(key_document.get("team_id") or ""),
                agent_id=agent_id,
                event_type="agent_invoked",
                status="failed",
                duration_ms=int((time.monotonic() - started) * 1000),
                error_code=type(error).__name__,
                access_type=key_document.get("access_type"),
            )
        return error_response(error, "/api/v1/agents/<agent_id>/invoke")


def _agent_invocation_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(
        data, ensure_ascii=False, separators=(",", ":"), default=str
    )
    return f"event: {event}\ndata: {payload}\n\n"


@bp.post("/api/v1/agents/<agent_id>/invoke/stream")
async def stream_agent_api(agent_id: str):
    request_id = str(uuid.uuid4())
    key_document: dict[str, Any] | None = None
    try:
        if not request.is_json:
            raise AgentInvocationKeyError("request must be json", status_code=415)
        key_document = authenticate_agent_invocation_key(
            _agent_invocation_bearer_token()
        )
        enforce_agent_invocation_rate_limit(key_document)
        body = await request.get_json()
        input_text, requested_conversation_id = _agent_invocation_request_body(
            body
        )
        _validate_agent_invocation_target(key_document, str(agent_id or ""))
    except Exception as error:
        return error_response(error, "/api/v1/agents/<agent_id>/invoke/stream")

    @stream_with_context
    async def generate():
        context: dict[str, Any] = {}
        started = time.monotonic()
        execution_task: asyncio.Task | None = None
        yield _agent_invocation_sse(
            "started",
            {"id": request_id, "agent_id": agent_id, "status": "running"},
        )
        try:
            execution_task = asyncio.create_task(
                _execute_agent_invocation(
                    key_document=key_document or {},
                    agent_id=str(agent_id or ""),
                    input_text=input_text,
                    conversation_id=requested_conversation_id,
                    usage_context=context,
                )
            )
            while not execution_task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(execution_task), timeout=15
                    )
                except asyncio.TimeoutError:
                    yield _agent_invocation_sse(
                        "heartbeat", {"id": request_id, "status": "running"}
                    )
            result, conversation_id = await execution_task
            await asyncio.to_thread(
                mark_agent_invocation_key_used, str((key_document or {})["_id"])
            )
            await asyncio.to_thread(
                insert_agent_invocation_audit,
                request_id=request_id,
                key_id=str((key_document or {}).get("_id") or ""),
                team_id=str((key_document or {}).get("team_id") or ""),
                agent_id=agent_id,
                event_type="agent_stream_completed",
                status="success",
                duration_ms=int((time.monotonic() - started) * 1000),
                access_type=(key_document or {}).get("access_type"),
            )
            yield _agent_invocation_sse(
                "completed",
                _agent_invocation_public_response(
                    result,
                    request_id=request_id,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    access_type=(key_document or {}).get("access_type"),
                ),
            )
        except asyncio.CancelledError:
            if execution_task and not execution_task.done():
                execution_task.cancel()
                await asyncio.gather(execution_task, return_exceptions=True)
            await _finish_usage_reservation(context, state="released")
            raise
        except Exception as error:
            await _finish_usage_reservation(context, state="released")
            await asyncio.to_thread(
                insert_agent_invocation_audit,
                request_id=request_id,
                key_id=str((key_document or {}).get("_id") or ""),
                team_id=str((key_document or {}).get("team_id") or ""),
                agent_id=agent_id,
                event_type="agent_stream_completed",
                status="failed",
                duration_ms=int((time.monotonic() - started) * 1000),
                error_code=type(error).__name__,
                access_type=(key_document or {}).get("access_type"),
            )
            current_app.logger.exception(
                "Streaming Agent invocation failed: id=%s", request_id
            )
            yield _agent_invocation_sse(
                "error",
                {
                    "id": request_id,
                    "status": "failed",
                    "error": {
                        "code": type(error).__name__,
                        "message": "The Agent invocation failed",
                    },
                },
            )

    response = await make_response(generate())
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Cache-Control"] = "no-cache, no-store"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@bp.post("/api/v1/agents/<agent_id>/jobs")
async def create_agent_api_job(agent_id: str):
    try:
        if not request.is_json:
            raise AgentInvocationKeyError("request must be json", status_code=415)
        key_document = authenticate_agent_invocation_key(
            _agent_invocation_bearer_token()
        )
        enforce_agent_invocation_rate_limit(key_document)
        body = await request.get_json()
        input_text, conversation_id = _agent_invocation_request_body(body)
        _validate_agent_invocation_target(key_document, str(agent_id or ""))
        job, created = await asyncio.to_thread(
            create_agent_invocation_job,
            key_id=str(key_document["_id"]),
            team_id=str(key_document.get("team_id") or ""),
            agent_id=str(agent_id or ""),
            input_text=input_text,
            conversation_id=conversation_id,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        if created:
            _schedule_agent_invocation_job(str(job["_id"]))
        payload = serialize_agent_invocation_job(job, include_result=False)
        payload["idempotent_replay"] = not created
        response = jsonify(payload)
        response.status_code = 202
        response.headers["Location"] = f"/api/v1/agent-jobs/{job['_id']}"
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        return error_response(error, "/api/v1/agents/<agent_id>/jobs")


@bp.get("/api/v1/agent-jobs/<job_id>")
async def get_agent_api_job(job_id: str):
    try:
        key_document = authenticate_agent_invocation_key(
            _agent_invocation_bearer_token()
        )
        job = await asyncio.to_thread(get_agent_invocation_job, job_id)
        if not job or str(job.get("key_id") or "") != str(key_document["_id"]):
            raise AgentInvocationJobError(
                "Invocation job not found", status_code=404
            )
        response = jsonify(serialize_agent_invocation_job(job))
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        return error_response(error, "/api/v1/agent-jobs/<job_id>")


@bp.post("/api/v1/agent-jobs/<job_id>/retry")
async def retry_agent_api_job(job_id: str):
    try:
        key_document = authenticate_agent_invocation_key(
            _agent_invocation_bearer_token()
        )
        existing = await asyncio.to_thread(get_agent_invocation_job, job_id)
        if not existing or str(existing.get("key_id") or "") != str(
            key_document["_id"]
        ):
            raise AgentInvocationJobError(
                "Invocation job not found", status_code=404
            )
        enforce_agent_invocation_rate_limit(key_document)
        job = await asyncio.to_thread(
            retry_agent_invocation_job, job_id, str(key_document["_id"])
        )
        if not job:
            raise AgentInvocationJobError(
                "Only a failed, unexpired invocation job can be retried",
                status_code=409,
            )
        _schedule_agent_invocation_job(str(job["_id"]))
        response = jsonify(
            serialize_agent_invocation_job(job, include_result=False)
        )
        response.status_code = 202
        response.headers["Location"] = f"/api/v1/agent-jobs/{job['_id']}"
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as error:
        return error_response(error, "/api/v1/agent-jobs/<job_id>/retry")


@bp.route("/chat/stream", methods=["POST"])
@authenticated
async def chat_stream(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    base_prompt_template = str((context.get("overrides") or {}).get("prompt_template") or "")
    team_id = request_json.get("team_id")
    agent_id = request_json.get("agent_id")
    try:
        context["auth_claims"] = _authorized_request_claims(
            request_json, auth_claims, agent_id=agent_id
        )
        selected_scopes = context["auth_claims"].get("selected_scopes") or []
        current_app.logger.info(
            "Knowledge selection: personal=%s global=%s data_groups=%d",
            "personal" in selected_scopes,
            "global" in selected_scopes,
            len(context["auth_claims"].get("data_groups_id") or []),
        )
        _prepare_usage_request(request_json, context)
        guardrail_policy, guardrail_audit = await _enforce_input_guardrails(
            messages=request_json.get("messages"),
            agent_id=agent_id,
            team_id=team_id,
            auth_claims=context["auth_claims"],
        )
    except Exception as error:
        return error_response(error, "/chat/stream")
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
        await _enforce_llm_quota(
            context.get("auth_claims") or auth_claims, context, request_json, workload="chat"
        )
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
        await _prepare_guardrail_context(context, guardrail_policy, guardrail_audit)
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
                current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]
                or current_app.config[CONFIG_CHAT_HISTORY_DATABASE_ENABLED],
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

        result = _guardrail_response_stream(result, guardrail_policy, guardrail_audit)

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
                if ndjson_lines:
                    data_str = "".join(ndjson_lines)
                    try:
                        await _persist_user_usage(
                            context.get("auth_claims") or auth_claims,
                            data_str,
                            "chat",
                            _usage_metadata(context, agent_id, "chat"),
                            context,
                        )
                    except Exception:
                        logging.exception("Can't insert user usage")
                else:
                    await _finish_usage_reservation(context, state="released")

        response = await make_response(stream_and_record_usage())
        response.timeout = None  # type: ignore
        response.mimetype = "application/json-lines"
        return response
    except Exception as error:
        await _finish_usage_reservation(context, state="released")
        return error_response(error, "/chat")


# Send MSAL.js settings to the client UI
@bp.route("/auth_setup", methods=["GET"])
def auth_setup():
    auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
    return jsonify(auth_helper.get_auth_setup_for_client())


def _oidc_callback_url() -> str:
    configured_base = str(os.getenv("NEXORA_PUBLIC_URL") or "").strip().rstrip("/")
    base = configured_base or request.url_root.rstrip("/")
    return f"{base}/auth/oidc/callback"


@bp.post("/auth/oidc/start")
async def oidc_login_start():
    try:
        enforce_local_login_rate_limit(request.remote_addr or "unknown")
        body = await request.get_json(silent=True) or {}
        provider_id = str(body.get("provider_id") or "legacy")
        settings = get_oidc_provider(provider_id, decrypt_client_secret=True) or {}
        authorization_url = await begin_oidc_login(settings, _oidc_callback_url())
        return jsonify({"authorization_url": authorization_url})
    except OIDCAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.post("/auth/oidc/route")
async def oidc_login_route():
    try:
        enforce_local_login_rate_limit(request.remote_addr or "unknown")
        body = await request.get_json(silent=True) or {}
        email = str(body.get("email") or "").strip().lower()
        if "@" not in email or len(email) > 254:
            raise OIDCAuthError("Enter a valid work email address")
        domain = email.rsplit("@", 1)[1]
        matches = [
            item
            for item in list_oidc_providers()
            if item.get("enabled") is True
            and domain in {str(value).lower() for value in (item.get("allowed_domains") or [])}
        ]
        if len(matches) != 1:
            raise OIDCAuthError("No unique SSO provider is configured for this email domain", status_code=404)
        return jsonify({"provider_id": str(matches[0]["_id"])})
    except (OIDCAuthError, LocalAuthError) as error:
        return jsonify({"error": str(error)}), error.status_code


async def _oidc_callback_page(payload: dict[str, Any], *, status_code: int = 200):
    # The session token is delivered to the same-origin opener and never placed
    # in a query string, browser history, referrer, or application log.
    encoded = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    html = f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>Sign in</title></head>
<body><p>You may close this window.</p><script>
if (window.opener) window.opener.postMessage({encoded}, window.location.origin);
window.close();
</script></body></html>"""
    response = await make_response(html, status_code)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'unsafe-inline'; style-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


@bp.get("/auth/oidc/callback")
async def oidc_login_callback():
    if request.args.get("error"):
        return await _oidc_callback_page(
            {"type": "nexora:oidc", "error": "The identity provider did not complete sign-in."},
            status_code=401,
        )
    try:
        state = str(request.args.get("state") or "")
        code = str(request.args.get("code") or "")
        if not state or not code:
            raise OIDCAuthError("OIDC callback is missing code or state", status_code=400)
        token, user = await complete_oidc_login(
            lambda provider_id: get_oidc_provider(provider_id, decrypt_client_secret=True),
            state,
            code,
        )
        return await _oidc_callback_page(
            {
                "type": "nexora:oidc",
                "access_token": token,
                "username": user.get("email") or user.get("ad_email") or "",
            }
        )
    except OIDCAuthError as error:
        return await _oidc_callback_page(
            {"type": "nexora:oidc", "error": str(error)}, status_code=error.status_code
        )
    except Exception:
        current_app.logger.exception("OIDC callback failed")
        return await _oidc_callback_page(
            {"type": "nexora:oidc", "error": "OIDC sign-in could not be completed."},
            status_code=500,
        )


@bp.post("/auth/oidc/logout")
@authenticated
async def oidc_auth_logout(auth_claims: dict[str, Any]):
    if auth_claims.get("auth_provider") != "oidc":
        return jsonify({"success": True}), 200
    try:
        token = current_app.config[CONFIG_AUTH_CLIENT].get_token_auth_header(request.headers)
        revoke_oidc_session(token)
    except Exception:
        pass
    return jsonify({"success": True}), 200


def _public_base_url() -> str:
    return str(os.getenv("NEXORA_PUBLIC_URL") or request.url_root).strip().rstrip("/")


def _saml_urls(provider_id: str) -> tuple[str, str]:
    base = _public_base_url()
    return (
        f"{base}/auth/saml/{provider_id}/acs",
        f"{base}/auth/saml/{provider_id}/metadata",
    )


def _saml_request_data(post_data: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = urlparse(_public_base_url())
    return {
        "https": "on" if parsed.scheme == "https" else "off",
        "http_host": parsed.netloc,
        "server_port": str(parsed.port or (443 if parsed.scheme == "https" else 80)),
        "script_name": request.path,
        "get_data": request.args.to_dict(flat=True),
        "post_data": post_data or {},
    }


@bp.post("/auth/saml/<provider_id>/start")
async def saml_login_start(provider_id: str):
    try:
        enforce_local_login_rate_limit(request.remote_addr or "unknown")
        provider = get_saml_provider(provider_id) or {}
        acs_url, metadata_url = _saml_urls(provider_id)
        redirect_url = begin_saml_login(
            provider,
            _saml_request_data(),
            acs_url=acs_url,
            metadata_url=metadata_url,
        )
        return jsonify({"authorization_url": redirect_url})
    except (SAMLAuthError, ValueError) as error:
        return jsonify({"error": str(error)}), getattr(error, "status_code", 400)


@bp.post("/auth/saml/<provider_id>/acs")
async def saml_login_acs(provider_id: str):
    try:
        form = (await request.form).to_dict(flat=True)
        relay_state = str(form.get("RelayState") or "")
        if not relay_state or not form.get("SAMLResponse"):
            raise SAMLAuthError("SAML response or RelayState is missing")
        provider = get_saml_provider(provider_id) or {}
        if provider.get("enabled") is not True:
            raise SAMLAuthError("SAML authentication is not enabled", status_code=404)
        acs_url, metadata_url = _saml_urls(provider_id)
        token, user = complete_saml_login(
            provider,
            _saml_request_data(form),
            relay_state,
            acs_url=acs_url,
            metadata_url=metadata_url,
        )
        return await _oidc_callback_page(
            {
                "type": "nexora:saml",
                "access_token": token,
                "username": user.get("email") or user.get("ad_email") or "",
            }
        )
    except SAMLAuthError as error:
        return await _oidc_callback_page(
            {"type": "nexora:saml", "error": str(error)}, status_code=error.status_code
        )
    except Exception:
        current_app.logger.exception("SAML ACS failed")
        return await _oidc_callback_page(
            {"type": "nexora:saml", "error": "SAML sign-in could not be completed."},
            status_code=500,
        )


@bp.get("/auth/saml/<provider_id>/metadata")
async def saml_service_provider_metadata(provider_id: str):
    try:
        provider = get_saml_provider(provider_id) or {}
        if not provider:
            return jsonify({"error": "SAML provider not found"}), 404
        acs_url, metadata_url = _saml_urls(provider_id)
        response = await make_response(
            saml_metadata(provider, acs_url=acs_url, metadata_url=metadata_url), 200
        )
        response.headers["Content-Type"] = "application/samlmetadata+xml; charset=utf-8"
        response.headers["Cache-Control"] = "no-store"
        return response
    except SAMLAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.post("/auth/saml/logout")
@authenticated
async def saml_auth_logout(auth_claims: dict[str, Any]):
    if auth_claims.get("auth_provider") != "saml":
        return jsonify({"success": True}), 200
    try:
        token = current_app.config[CONFIG_AUTH_CLIENT].get_token_auth_header(request.headers)
        revoke_saml_session(token)
    except Exception:
        pass
    return jsonify({"success": True}), 200


def _local_auth_enabled() -> bool:
    auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
    return bool(getattr(auth_helper, "local_authentication_enabled", False))


@bp.post("/auth/local/bootstrap")
async def local_auth_bootstrap():
    if not _local_auth_enabled():
        return jsonify({"error": "Local authentication is not enabled"}), 404
    expected_token = os.getenv("LOCAL_AUTH_BOOTSTRAP_TOKEN", "")
    supplied_token = request.headers.get("X-Bootstrap-Token", "")
    if not expected_token:
        return jsonify({"error": "LOCAL_AUTH_BOOTSTRAP_TOKEN is not configured"}), 503
    if not secrets.compare_digest(supplied_token, expected_token):
        return jsonify({"error": "Invalid bootstrap token"}), 403
    try:
        body = await request.get_json()
        user = bootstrap_local_superuser(
            username=(body or {}).get("username"),
            password=(body or {}).get("password"),
            email=(body or {}).get("email"),
            first_name=(body or {}).get("first_name"),
            last_name=(body or {}).get("last_name"),
        )
        return jsonify({"user_id": user["_id"], "username": user["ad_email"]}), 201
    except LocalAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.post("/auth/local/login")
async def local_auth_login():
    if not _local_auth_enabled():
        return jsonify({"error": "Local authentication is not enabled"}), 404
    try:
        body = await request.get_json()
        enforce_local_login_rate_limit(request.remote_addr or "unknown")
        token, user = authenticate_local_user(
            str((body or {}).get("username") or ""),
            str((body or {}).get("password") or ""),
        )
        return jsonify(
            {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": 12 * 60 * 60,
                "username": user.get("ad_email") or user.get("email"),
            }
        )
    except LocalAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.post("/auth/local/logout")
@authenticated
async def local_auth_logout(auth_claims: dict[str, Any]):
    if auth_claims.get("auth_provider") != "local":
        return jsonify({"success": True}), 200
    try:
        token = current_app.config[CONFIG_AUTH_CLIENT].get_token_auth_header(request.headers)
        revoke_local_session(token)
        return jsonify({"success": True}), 200
    except Exception:
        return jsonify({"success": True}), 200


@bp.get("/auth/local/me")
@authenticated
async def local_auth_me(auth_claims: dict[str, Any]):
    if auth_claims.get("auth_provider") != "local":
        return jsonify({"error": "Not a local authentication session"}), 400
    return jsonify(
        {
            "user_id": auth_claims.get("application_user_id"),
            "username": auth_claims.get("preferred_username"),
        }
    )


@bp.put("/auth/local/password")
@authenticated
async def change_own_local_password(auth_claims: dict[str, Any]):
    if not _local_auth_enabled():
        return jsonify({"error": "Local authentication is not enabled"}), 404
    try:
        user = _application_user_for_claims(auth_claims)
        if not user or user.get("active", True) is not True:
            raise LocalAuthError("The application user is disabled or unavailable", status_code=403)
        body = await request.get_json()
        enforce_local_login_rate_limit(request.remote_addr or "unknown")
        change_local_password(
            str(user["_id"]),
            str((body or {}).get("current_password") or ""),
            str((body or {}).get("new_password") or ""),
        )
        return jsonify(
            {
                "success": True,
                "reauthentication_required": auth_claims.get("auth_provider") == "local",
            }
        ), 200
    except LocalAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.post("/admin/local-users")
@authenticated
async def admin_create_local_user(auth_claims: dict[str, Any]):
    if not _local_auth_enabled():
        return jsonify({"error": "Local authentication is not enabled"}), 404
    try:
        _require_system_permission(auth_claims, "Manage users")
        body = await request.get_json()
        user = create_managed_local_user(
            username=(body or {}).get("username"),
            password=(body or {}).get("password"),
            user=body or {},
        )
        return jsonify({"user_id": user["_id"]}), 201
    except LocalAuthError as error:
        return jsonify({"error": str(error)}), error.status_code
    except Exception as error:
        return error_response(error, "/admin/local-users")


@bp.put("/admin/local-users/<user_id>/password")
@authenticated
async def admin_reset_local_password(auth_claims: dict[str, Any], user_id: str):
    try:
        _require_user_management_target(auth_claims, user_id)
        body = await request.get_json()
        reset_local_password(user_id, str((body or {}).get("password") or ""))
        return jsonify({"success": True}), 200
    except LocalAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.get("/admin/auth-settings")
@authenticated
async def admin_get_auth_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    managed = get_auth_settings()
    if managed:
        settings = serialize_auth_settings(managed)
        settings["source"] = "managed"
    else:
        auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
        settings = {
            "entra_enabled": auth_helper.entra_authentication_enabled,
            "tenant_id": auth_helper.tenant_id or "",
            "server_app_id": auth_helper.server_app_id or "",
            "client_app_id": auth_helper.client_app_id or "",
            "has_client_secret": bool(auth_helper.server_app_secret),
            "source": "environment",
            "oidc_enabled": False,
            "oidc_display_name": "Enterprise SSO",
            "oidc_issuer": "",
            "oidc_client_id": "",
            "oidc_token_auth_method": "client_secret_basic",
            "oidc_has_client_secret": False,
            "oidc_jit_enabled": False,
            "oidc_allowed_domains": [],
        }
    settings["local_enabled"] = _local_auth_enabled()
    settings["oidc_callback_url"] = _oidc_callback_url()
    return jsonify(settings)


@bp.put("/admin/auth-settings")
@authenticated
async def admin_update_auth_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        if (body or {}).get("oidc_enabled") is True and not _local_auth_enabled():
            return jsonify({"error": "Managed Generic OIDC requires Local authentication as a break-glass administrator path"}), 400
        if (body or {}).get("entra_enabled") is not True and not (
            _local_auth_enabled() and local_identity_exists()
        ):
            return jsonify({"error": "Create a local administrator before disabling Microsoft Entra ID"}), 400
        if (body or {}).get("oidc_enabled") is True:
            requested_domains = {
                str(value).strip().lower().lstrip("@")
                for value in ((body or {}).get("oidc_allowed_domains") or [])
                if str(value).strip()
            }
            if any(
                item.get("legacy") is not True
                and item.get("enabled") is True
                and requested_domains.intersection(item.get("allowed_domains") or [])
                for item in list_oidc_providers()
            ):
                return jsonify({"error": "An enabled managed OIDC provider already uses one of these email domains"}), 400
        previous_settings = get_auth_settings(decrypt_client_secret=True) or {}
        settings = save_auth_settings(body or {})
        runtime_settings = get_auth_settings(decrypt_client_secret=True) or {}
        if runtime_settings.get("oidc_enabled") is True:
            ensure_local_auth_indexes()
            ensure_oidc_auth_indexes()
            ensure_identity_management_indexes()
        current_app.config[CONFIG_AUTH_CLIENT].configure_entra(
            enabled=runtime_settings.get("entra_enabled") is True,
            tenant_id=runtime_settings.get("tenant_id"),
            server_app_id=runtime_settings.get("server_app_id"),
            server_app_secret=runtime_settings.get("client_secret"),
            client_app_id=runtime_settings.get("client_app_id"),
        )
        if previous_settings.get("oidc_enabled") is True and (
            runtime_settings.get("oidc_enabled") is not True
            or str(previous_settings.get("oidc_issuer") or "").rstrip("/")
            != str(runtime_settings.get("oidc_issuer") or "").rstrip("/")
        ):
            revoke_oidc_provider_sessions(
                "legacy", legacy_issuer=str(previous_settings.get("oidc_issuer") or "")
            )
        _refresh_oidc_runtime()
        return jsonify(serialize_auth_settings(settings))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/admin/auth-settings/oidc/test")
@authenticated
async def admin_test_oidc_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        issuer = str((body or {}).get("issuer") or "").strip().rstrip("/")
        discovery = await discover_oidc_provider(issuer)
        return jsonify(
            {
                "success": True,
                "issuer": discovery.get("issuer"),
                "authorization_endpoint": discovery.get("authorization_endpoint"),
                "token_endpoint": discovery.get("token_endpoint"),
            }
        )
    except OIDCAuthError as error:
        return jsonify({"error": str(error)}), error.status_code


def _refresh_oidc_runtime() -> None:
    providers = public_oidc_providers()
    current_app.config[CONFIG_AUTH_CLIENT].configure_oidc(
        enabled=bool(providers),
        display_name=providers[0]["display_name"] if providers else "Enterprise SSO",
        providers=providers,
    )


def _refresh_saml_runtime() -> None:
    providers = public_saml_providers()
    current_app.config[CONFIG_AUTH_CLIENT].configure_saml(
        enabled=bool(providers),
        providers=providers,
    )


@bp.get("/admin/oidc-providers")
@authenticated
async def admin_list_oidc_providers(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify({"providers": [serialize_oidc_provider(item) for item in list_oidc_providers()]})


@bp.post("/admin/oidc-providers")
@authenticated
async def admin_create_oidc_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    if not _local_auth_enabled():
        return jsonify({"error": "Managed Generic OIDC requires Local authentication as a break-glass administrator path"}), 400
    try:
        provider = save_oidc_provider(await request.get_json() or {})
        ensure_local_auth_indexes()
        ensure_oidc_auth_indexes()
        ensure_oidc_provider_indexes()
        ensure_identity_management_indexes()
        _refresh_oidc_runtime()
        return jsonify(serialize_oidc_provider(provider)), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/oidc-providers/<provider_id>")
@authenticated
async def admin_update_oidc_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json() or {}
        if body.get("enabled") is True and not _local_auth_enabled():
            return jsonify({"error": "Managed Generic OIDC requires Local authentication as a break-glass administrator path"}), 400
        provider = save_oidc_provider(body, provider_id)
        if provider.get("enabled") is not True:
            revoke_oidc_provider_sessions(provider_id)
        _refresh_oidc_runtime()
        return jsonify(serialize_oidc_provider(provider))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/oidc-providers/<provider_id>")
@authenticated
async def admin_delete_oidc_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    try:
        if not delete_oidc_provider(provider_id):
            return jsonify({"error": "OIDC provider not found"}), 404
        revoke_oidc_provider_sessions(provider_id)
        _refresh_oidc_runtime()
        return jsonify({"success": True})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/admin/saml-providers")
@authenticated
async def admin_list_saml_providers(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    providers = []
    for item in list_saml_providers():
        serialized = serialize_saml_provider(item)
        acs_url, metadata_url = _saml_urls(serialized["id"])
        serialized.update({"acs_url": acs_url, "metadata_url": metadata_url})
        providers.append(serialized)
    return jsonify({"providers": providers})


@bp.post("/admin/saml-providers/test")
@authenticated
async def admin_test_saml_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json() or {}
        provider_id = str(body.get("id") or "preview")
        acs_url, metadata_url = _saml_urls(provider_id)
        saml_settings(body, acs_url=acs_url, metadata_url=metadata_url)
        return jsonify({"success": True, "acs_url": acs_url, "metadata_url": metadata_url})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/admin/saml-providers")
@authenticated
async def admin_create_saml_provider(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    if not _local_auth_enabled():
        return jsonify({"error": "Managed SAML requires Local authentication as a break-glass administrator path"}), 400
    try:
        body = await request.get_json() or {}
        provider = save_saml_provider(body, str(body.get("id") or "") or None)
        provider_id = str(provider.get("_id") or "")
        acs_url, metadata_url = _saml_urls(provider_id)
        saml_settings(provider, acs_url=acs_url, metadata_url=metadata_url)
        ensure_local_auth_indexes()
        ensure_saml_auth_indexes()
        ensure_saml_provider_indexes()
        ensure_identity_management_indexes()
        _refresh_saml_runtime()
        result = serialize_saml_provider(provider)
        result.update({"acs_url": acs_url, "metadata_url": metadata_url})
        return jsonify(result), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/saml-providers/<provider_id>")
@authenticated
async def admin_update_saml_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json() or {}
        if body.get("enabled") is True and not _local_auth_enabled():
            return jsonify({"error": "Managed SAML requires Local authentication as a break-glass administrator path"}), 400
        provider = save_saml_provider(body, provider_id)
        acs_url, metadata_url = _saml_urls(provider_id)
        saml_settings(provider, acs_url=acs_url, metadata_url=metadata_url)
        if provider.get("enabled") is not True:
            revoke_saml_provider_sessions(provider_id)
        _refresh_saml_runtime()
        result = serialize_saml_provider(provider)
        result.update({"acs_url": acs_url, "metadata_url": metadata_url})
        return jsonify(result)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/saml-providers/<provider_id>")
@authenticated
async def admin_delete_saml_provider(auth_claims: dict[str, Any], provider_id: str):
    _require_system_admin(auth_claims)
    if not delete_saml_provider(provider_id):
        return jsonify({"error": "SAML provider not found"}), 404
    revoke_saml_provider_sessions(provider_id)
    _refresh_saml_runtime()
    return jsonify({"success": True})


def _federated_provider_names() -> dict[str, str]:
    names = {
        oidc_provider_identity_key(provider): str(provider.get("display_name") or "Enterprise SSO")
        for provider in list_oidc_providers()
    }
    names.update(
        {
            saml_provider_identity_key(provider): str(provider.get("display_name") or "Enterprise SAML")
            for provider in list_saml_providers()
        }
    )
    return names


@bp.get("/admin/auth-identities")
@authenticated
async def admin_list_auth_identities(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    provider_names = _federated_provider_names()
    pending = []
    for item in list_identity_link_requests():
        suggested = get_user_by_id(str(item.get("suggested_user_id") or ""))
        pending.append(
            {
                "id": str(item.get("_id") or ""),
                "provider_name": provider_names.get(str(item.get("provider") or ""), "Federated provider"),
                "email": str(item.get("email") or ""),
                "suggested_user_id": str(item.get("suggested_user_id") or ""),
                "suggested_user_name": " ".join(
                    filter(None, [str((suggested or {}).get("first_name") or ""), str((suggested or {}).get("last_name") or "")])
                ).strip(),
                "expires_at": item.get("expires_at"),
            }
        )
    links = []
    for identity in list_federated_identities():
        user = get_user_by_id(str(identity.get("user_id") or ""))
        links.append(
            {
                "id": str(identity.get("_id") or ""),
                "provider_name": provider_names.get(str(identity.get("provider") or ""), "Retired provider"),
                "username": str(identity.get("username") or ""),
                "user_id": str(identity.get("user_id") or ""),
                "user_name": " ".join(
                    filter(None, [str((user or {}).get("first_name") or ""), str((user or {}).get("last_name") or "")])
                ).strip(),
                "active": identity.get("active", True) is True,
                "created_at": identity.get("created_at"),
            }
        )
    audits = [
        {
            "id": str(item.get("_id") or ""),
            "action": str(item.get("action") or ""),
            "actor_id": str(item.get("actor_id") or ""),
            "target_user_id": str(item.get("target_user_id") or ""),
            "provider": str(item.get("provider") or ""),
            "created_at": item.get("created_at"),
        }
        for item in list_identity_audit_events()
    ]
    return jsonify({"pending": pending, "links": links, "audit_events": audits})


@bp.post("/admin/auth-identities/requests/<request_id>/approve")
@authenticated
async def admin_approve_auth_identity(auth_claims: dict[str, Any], request_id: str):
    actor = _require_system_admin(auth_claims)
    try:
        body = await request.get_json() or {}
        link_request = get_identity_link_request(request_id)
        enabled_provider_keys = {
            oidc_provider_identity_key(provider)
            for provider in list_oidc_providers()
            if provider.get("enabled") is True
        }
        enabled_provider_keys.update(
            saml_provider_identity_key(provider)
            for provider in list_saml_providers()
            if provider.get("enabled") is True
        )
        if not link_request or str(link_request.get("provider") or "") not in enabled_provider_keys:
            raise ValueError("The identity provider for this request is disabled or unavailable")
        identity = approve_identity_link(
            request_id,
            str(body.get("user_id") or ""),
            actor_id=str(actor.get("_id") or ""),
        )
        return jsonify({"identity_id": str(identity.get("_id") or "")}), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/admin/auth-identities/requests/<request_id>/reject")
@authenticated
async def admin_reject_auth_identity(auth_claims: dict[str, Any], request_id: str):
    actor = _require_system_admin(auth_claims)
    if not reject_identity_link(request_id, actor_id=str(actor.get("_id") or "")):
        return jsonify({"error": "Identity link request was not found or is no longer pending"}), 404
    return jsonify({"success": True})


@bp.delete("/admin/auth-identities/<identity_id>")
@authenticated
async def admin_unlink_auth_identity(auth_claims: dict[str, Any], identity_id: str):
    actor = _require_system_admin(auth_claims)
    try:
        if not unlink_federated_identity(identity_id, actor_id=str(actor.get("_id") or "")):
            return jsonify({"error": "Federated identity was not found"}), 404
        return jsonify({"success": True})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/auth-settings")
@authenticated
async def admin_reset_auth_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    env_enabled = os.getenv("AZURE_USE_AUTHENTICATION", "").lower() == "true"
    if not env_enabled and not (_local_auth_enabled() and local_identity_exists()):
        return jsonify({"error": "Environment authentication is not configured"}), 400
    delete_auth_settings()
    current_app.config[CONFIG_AUTH_CLIENT].configure_entra(
        enabled=env_enabled,
        tenant_id=os.getenv("AZURE_AUTH_TENANT_ID", os.getenv("AZURE_TENANT_ID")),
        server_app_id=os.getenv("AZURE_SERVER_APP_ID"),
        server_app_secret=os.getenv("AZURE_SERVER_APP_SECRET"),
        client_app_id=os.getenv("AZURE_CLIENT_APP_ID"),
    )
    _refresh_oidc_runtime()
    return jsonify({"success": True}), 200


@bp.get("/admin/guardrail-settings")
@authenticated
async def admin_get_guardrail_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    configured = get_guardrail_settings()
    return jsonify(
        {
            "configured": configured is not None,
            "policy": GuardrailPolicy.from_config(configured).serialize(),
        }
    )


@bp.put("/admin/guardrail-settings")
@authenticated
async def admin_update_guardrail_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        return jsonify({"configured": True, "policy": save_guardrail_settings(body or {})})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/admin/chat-history-retention")
@authenticated
async def admin_get_chat_history_retention(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify(
        {
            "configured_days": configured_chat_history_retention_days(),
            "effective_days": effective_chat_history_retention_days(),
        }
    )


@bp.put("/admin/chat-history-retention")
@authenticated
async def admin_update_chat_history_retention(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        body = await request.get_json()
        days = save_chat_history_retention_days((body or {}).get("retention_days"))
        return jsonify({"configured_days": days, "effective_days": days})
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/teams/<team_id>/chat-history-retention")
@authenticated
async def team_get_chat_history_retention(auth_claims: dict[str, Any], team_id: str):
    _require_team_access(auth_claims, team_id, permission="Manage agents")
    return jsonify(
        {
            "configured_days": configured_chat_history_retention_days(team_id),
            "system_days": effective_chat_history_retention_days(),
            "effective_days": effective_chat_history_retention_days(team_id),
        }
    )


@bp.put("/teams/<team_id>/chat-history-retention")
@authenticated
async def team_update_chat_history_retention(auth_claims: dict[str, Any], team_id: str):
    _require_team_access(auth_claims, team_id, permission="Manage agents")
    try:
        body = await request.get_json()
        days = save_chat_history_retention_days((body or {}).get("retention_days"), team_id)
        return jsonify(
            {
                "configured_days": days,
                "system_days": effective_chat_history_retention_days(),
                "effective_days": effective_chat_history_retention_days(team_id),
            }
        )
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/teams/<team_id>/guardrail-settings")
@authenticated
async def team_get_guardrail_settings(auth_claims: dict[str, Any], team_id: str):
    _require_team_access(auth_claims, team_id, permission="Manage agents")
    system_config = get_guardrail_settings()
    team_config = get_guardrail_settings(team_id)
    effective = merge_guardrail_policies(
        GuardrailPolicy.from_config(system_config) if system_config is not None else None,
        GuardrailPolicy.from_config(team_config) if team_config is not None else None,
    )
    return jsonify(
        {
            "configured": team_config is not None,
            "policy": GuardrailPolicy.from_config(team_config).serialize(),
            "system_policy": GuardrailPolicy.from_config(system_config).serialize()
            if system_config is not None
            else None,
            "effective_policy": effective.serialize(),
        }
    )


@bp.put("/teams/<team_id>/guardrail-settings")
@authenticated
async def team_update_guardrail_settings(auth_claims: dict[str, Any], team_id: str):
    _require_team_access(auth_claims, team_id, permission="Manage agents")
    try:
        body = await request.get_json()
        policy = save_guardrail_settings(body or {}, team_id)
        system_config = get_guardrail_settings()
        effective = merge_guardrail_policies(
            GuardrailPolicy.from_config(system_config) if system_config is not None else None,
            GuardrailPolicy.from_config(policy),
        )
        return jsonify(
            {"configured": True, "policy": policy, "effective_policy": effective.serialize()}
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


def _quota_settings_response(level: str, subject_id: str = "", *, team_id: str = "", user_id: str = ""):
    configured = get_quota_settings(level, subject_id)
    configured_policy = UsageQuotaPolicy.from_config(configured)
    effective, inherited = effective_quota_settings(team_id, user_id)
    usage = current_usage(team_id, user_id)
    events = list_quota_audit_events(level, subject_id)
    status_policy = configured_policy
    member_limit_source = ""
    if level == "team_user":
        status_policy, member_limit_source = team_member_quota_policy(team_id, user_id)
        status_policy = status_policy or UsageQuotaPolicy()
    return {
        "configured": configured is not None,
        "policy": configured_policy.serialize(),
        "effective_policy": effective.serialize(),
        "inherited": inherited,
        "usage": usage,
        "rule_usage": current_llm_rule_usages(configured_policy, team_id, user_id),
        "status": quota_status(status_policy, team_id, user_id),
        "member_limit_source": member_limit_source,
        "effective_member_limit": status_policy.monthly_llm_tokens if level == "team_user" else 0,
        "audit_events": [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in event.items()
                if key not in {"expires_at"}
            }
            for event in events
        ],
    }


@bp.get("/admin/quota-settings")
@authenticated
async def admin_get_quota_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify(_quota_settings_response("system"))


@bp.put("/admin/quota-settings")
@authenticated
async def admin_update_quota_settings(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        save_quota_settings("system", "", await request.get_json() or {})
        return jsonify(_quota_settings_response("system"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/teams/<team_id>/quota-settings")
@authenticated
async def team_get_quota_settings(auth_claims: dict[str, Any], team_id: str):
    _require_team_access(auth_claims, team_id, permission="Manage team permissions")
    return jsonify(_quota_settings_response("team", team_id, team_id=team_id))


@bp.put("/teams/<team_id>/quota-settings")
@authenticated
async def team_update_quota_settings(auth_claims: dict[str, Any], team_id: str):
    _require_team_access(auth_claims, team_id, permission="Manage team permissions")
    try:
        save_quota_settings("team", team_id, await request.get_json() or {})
        return jsonify(_quota_settings_response("team", team_id, team_id=team_id))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


def _require_team_quota_user(auth_claims: dict[str, Any], team_id: str, user_id: str) -> None:
    _actor, team = _require_team_access(
        auth_claims, team_id, permission="Manage team permissions"
    )
    if user_id not in {str(item) for item in (team.get("user_id") or [])}:
        raise AccessControlError("User is not a member of this team", status_code=404)
    if not get_user_by_id(user_id):
        raise AccessControlError("User not found", status_code=404)


@bp.get("/teams/<team_id>/users/<user_id>/quota-settings")
@authenticated
async def team_user_get_quota_settings(
    auth_claims: dict[str, Any], team_id: str, user_id: str
):
    try:
        _require_team_quota_user(auth_claims, team_id, user_id)
        subject_id = f"{team_id}:{user_id}"
        return jsonify(
            _quota_settings_response(
                "team_user", subject_id, team_id=team_id, user_id=user_id
            )
        )
    except Exception as error:
        return error_response(error, "/teams/<team_id>/users/<user_id>/quota-settings")


@bp.put("/teams/<team_id>/users/<user_id>/quota-settings")
@authenticated
async def team_user_update_quota_settings(
    auth_claims: dict[str, Any], team_id: str, user_id: str
):
    try:
        _require_team_quota_user(auth_claims, team_id, user_id)
        save_team_user_quota_settings(
            team_id, user_id, await request.get_json() or {}
        )
        subject_id = f"{team_id}:{user_id}"
        return jsonify(
            _quota_settings_response(
                "team_user", subject_id, team_id=team_id, user_id=user_id
            )
        )
    except Exception as error:
        return error_response(error, "/teams/<team_id>/users/<user_id>/quota-settings")


@bp.get("/admin/users/<user_id>/quota-settings")
@authenticated
async def user_get_quota_settings(auth_claims: dict[str, Any], user_id: str):
    _require_system_admin(auth_claims)
    if not get_user_by_id(user_id):
        raise AccessControlError("User not found", status_code=404)
    return jsonify(_quota_settings_response("user", user_id, user_id=user_id))


@bp.put("/admin/users/<user_id>/quota-settings")
@authenticated
async def user_update_quota_settings(auth_claims: dict[str, Any], user_id: str):
    _require_system_admin(auth_claims)
    if not get_user_by_id(user_id):
        raise AccessControlError("User not found", status_code=404)
    try:
        save_quota_settings("user", user_id, await request.get_json() or {})
        return jsonify(_quota_settings_response("user", user_id, user_id=user_id))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/admin/llm-providers")
@authenticated
async def admin_list_llm_providers(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    return jsonify({"providers": [_serialize_llm_provider(item) for item in list_llm_providers()]})


@bp.get("/admin/embedding-profiles")
@authenticated
async def admin_list_embedding_profiles(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    environment = _serialize_embedding_profile(_environment_embedding_profile(), environment=True)
    managed = [_serialize_embedding_profile(item) for item in list_embedding_profiles()]
    return jsonify({"profiles": [environment, *managed], "settings": _serialize_embedding_settings()})


def _embedding_collection_in_use(collection_name: str, *, exclude_id: str = "") -> bool:
    environment = _environment_embedding_profile()
    if exclude_id != ENVIRONMENT_PROFILE_ID and environment["collection_name"] == collection_name:
        return True
    return any(
        str(item.get("_id")) != exclude_id
        and str(item.get("collection_name") or "") == collection_name
        for item in list_embedding_profiles()
    )


@bp.post("/admin/embedding-profiles")
@authenticated
async def admin_create_embedding_profile(auth_claims: dict[str, Any]):
    _require_system_admin(auth_claims)
    try:
        normalized = _normalize_embedding_profile_payload(await request.get_json() or {})
        if _embedding_collection_in_use(normalized["collection_name"]):
            return jsonify({"error": "Qdrant collection is already assigned to another embedding profile"}), 409
        profile = insert_embedding_profile(normalized)
        return jsonify(_serialize_embedding_profile(profile)), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/embedding-profiles/<profile_id>")
@authenticated
async def admin_update_embedding_profile(auth_claims: dict[str, Any], profile_id: str):
    _require_system_admin(auth_claims)
    existing = get_embedding_profile(profile_id)
    if not existing:
        return jsonify({"error": "Embedding profile not found"}), 404
    state = get_embedding_settings()
    if profile_id in {state["active_profile_id"], state["runtime_profile_id"]}:
        return jsonify({"error": "Activate another profile before editing the active or running profile"}), 409
    try:
        normalized = _normalize_embedding_profile_payload(await request.get_json() or {}, existing)
        if _embedding_collection_in_use(normalized["collection_name"], exclude_id=profile_id):
            return jsonify({"error": "Qdrant collection is already assigned to another embedding profile"}), 409
        profile = update_embedding_profile(profile_id, normalized)
        return jsonify(_serialize_embedding_profile(profile or existing))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/embedding-profiles/<profile_id>")
@authenticated
async def admin_delete_embedding_profile(auth_claims: dict[str, Any], profile_id: str):
    _require_system_admin(auth_claims)
    existing = get_embedding_profile(profile_id)
    if not existing:
        return jsonify({"error": "Embedding profile not found"}), 404
    state = get_embedding_settings()
    if profile_id in {state["active_profile_id"], state["runtime_profile_id"]}:
        return jsonify({"error": "Activate another profile before deleting the active or running profile"}), 409
    soft_delete_embedding_profile(profile_id)
    return jsonify({"success": True})


@bp.post("/admin/embedding-profiles/<profile_id>/activate")
@authenticated
async def admin_activate_embedding_profile(auth_claims: dict[str, Any], profile_id: str):
    _require_system_admin(auth_claims)
    if os.getenv("KNOWLEDGE_SEARCH_PROVIDER", "azure").strip().lower() != "qdrant":
        return jsonify({"error": "Managed embedding profile activation currently requires Qdrant"}), 409
    if profile_id != ENVIRONMENT_PROFILE_ID:
        profile = get_embedding_profile(profile_id)
        if not profile:
            return jsonify({"error": "Embedding profile not found"}), 404
        if not profile.get("enabled", True):
            return jsonify({"error": "Enable the embedding profile before activation"}), 409
    try:
        await _probe_embedding_profile(profile_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.warning("Embedding profile activation probe failed: %s", type(error).__name__)
        return jsonify({"error": "Embedding connection or Qdrant validation failed"}), 400
    state = activate_embedding_profile(profile_id)
    return jsonify({"settings": {
        **state,
        "activated_at": state["activated_at"].isoformat() if state.get("activated_at") else None,
        "runtime_started_at": state["runtime_started_at"].isoformat() if state.get("runtime_started_at") else None,
    }})


@bp.post("/admin/embedding-profiles/<profile_id>/test")
@authenticated
async def admin_test_embedding_profile(auth_claims: dict[str, Any], profile_id: str):
    _require_system_admin(auth_claims)
    try:
        settings, actual_dimensions = await _probe_embedding_profile(profile_id)
        return jsonify({"success": True, "model": settings.model, "dimensions": actual_dimensions})
    except ValueError as error:
        status = 404 if str(error) == "Embedding profile not found" else 400
        return jsonify({"error": str(error)}), status
    except Exception as error:
        current_app.logger.warning("Embedding profile connection test failed: %s", type(error).__name__)
        return jsonify({"error": "Embedding connection test failed"}), 400


@bp.post("/admin/embedding-profiles/<profile_id>/reindex-complete")
@authenticated
async def admin_complete_embedding_reindex(auth_claims: dict[str, Any], profile_id: str):
    _require_system_admin(auth_claims)
    try:
        state = mark_embedding_reindex_complete(profile_id)
        return jsonify({"settings": {
            **state,
            "activated_at": state["activated_at"].isoformat() if state.get("activated_at") else None,
            "runtime_started_at": state["runtime_started_at"].isoformat() if state.get("runtime_started_at") else None,
        }})
    except ValueError as error:
        return jsonify({"error": str(error)}), 409


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
    try:
        team_id = str(request.args.get("team_id") or "").strip()
        _require_integration_catalog_access(auth_claims, team_id)
        servers = []
        for item in list_mcp_servers(team_id):
            serialized = serialize_mcp_server(item)
            serialized["agent_usage_count"] = get_database().agents.count_documents(
                {
                    "delete_at": None,
                    "config.tool_settings.mcp_server_ids": str(item["_id"]),
                }
            )
            servers.append(serialized)
        return jsonify({"servers": servers})
    except AccessControlError as error:
        return error_response(error, "/admin/mcp-servers")


@bp.get("/mcp-servers/available")
@authenticated
async def available_mcp_servers(auth_claims: dict[str, Any]):
    try:
        team_id = str(request.args.get("team_id") or "").strip()
        agent_id = str(request.args.get("agent_id") or "").strip()
        _require_integration_catalog_access(
            auth_claims, team_id, allow_agent_management=True
        )
        servers = list_mcp_servers(team_id, enabled_only=True)
        if agent_id:
            team = get_team_by_id(team_id)
            if not team or agent_id not in {
                str(item) for item in (team.get("agent_id") or [])
            }:
                raise AccessControlError(
                    "Agent does not belong to this team", status_code=404
                )
            agent = get_agent_by_id(agent_id) or {}
            selected_ids = (
                ((agent.get("config") or {}).get("tool_settings") or {}).get(
                    "mcp_server_ids"
                )
                or []
            )
            returned_ids = {str(item.get("_id")) for item in servers}
            for selected_id in selected_ids:
                legacy = get_mcp_server(str(selected_id))
                if (
                    legacy
                    and legacy.get("enabled") is not False
                    and not str(legacy.get("team_id") or "")
                    and str(legacy.get("_id")) not in returned_ids
                ):
                    servers.append(legacy)
        return jsonify(
            {
                "servers": [
                    serialize_mcp_server(item) for item in servers
                ]
            }
        )
    except AccessControlError as error:
        return error_response(error, "/mcp-servers/available")


@bp.post("/admin/mcp-servers")
@authenticated
async def admin_create_mcp_server(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json() or {}
        normalized = normalize_mcp_server_payload(body)
        actor = _require_integration_catalog_access(auth_claims, normalized["team_id"])
        managed_azure = (
            normalized["vendor"] == "azure"
            and normalized["deployment_mode"] == "managed"
        )
        if managed_azure:
            _require_system_admin(auth_claims)
        requested_enabled = normalized["enabled"]
        if managed_azure:
            normalized["provisioning_status"] = (
                "pending" if requested_enabled else "stopped"
            )
        server = insert_mcp_server(normalized)
        if managed_azure and requested_enabled:
            try:
                server = await _provision_managed_azure_mcp(server)
                insert_integration_lifecycle_event(
                    action="provision",
                    status="success",
                    connection_id=str(server["_id"]),
                    team_id=str(server.get("team_id") or ""),
                    actor_id=str(actor.get("_id") or ""),
                    vendor="azure",
                )
            except IntegrationControllerError as error:
                server = update_mcp_server(
                    str(server["_id"]),
                    {
                        "enabled": True,
                        "provisioning_status": "failed",
                        "provisioning_error": str(error)[:500],
                    },
                ) or server
                insert_integration_lifecycle_event(
                    action="provision",
                    status="error",
                    connection_id=str(server["_id"]),
                    team_id=str(server.get("team_id") or ""),
                    actor_id=str(actor.get("_id") or ""),
                    vendor="azure",
                    error_type=type(error).__name__,
                )
                return jsonify(serialize_mcp_server(server)), 202
        return jsonify(serialize_mcp_server(server)), 201
    except AccessControlError as error:
        return error_response(error, "/admin/mcp-servers")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/mcp-servers/<server_id>")
@authenticated
async def admin_update_mcp_server(auth_claims: dict[str, Any], server_id: str):
    try:
        existing = get_mcp_server(server_id)
        if not existing:
            return jsonify({"error": "MCP server not found"}), 404
        actor = _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        if (
            str(existing.get("vendor") or "") == "azure"
            and str(existing.get("deployment_mode") or "external") == "managed"
        ):
            _require_system_admin(auth_claims)
        body = await request.get_json() or {}
        if "team_id" in body and str(body.get("team_id") or "") != str(
            existing.get("team_id") or ""
        ):
            raise ValueError("Use Assign to team to change integration ownership")
        normalized = normalize_mcp_server_payload(body, existing=existing)
        managed_azure = (
            normalized["vendor"] == "azure"
            and normalized["deployment_mode"] == "managed"
        )
        requested_enabled = normalized["enabled"]
        if managed_azure:
            normalized["provisioning_status"] = (
                "pending" if requested_enabled else "stopping"
            )
        server = update_mcp_server(server_id, normalized) or existing
        if managed_azure:
            controller = IntegrationControllerClient()
            try:
                if requested_enabled:
                    server = await _provision_managed_azure_mcp(server)
                    action = "provision"
                else:
                    await controller.stop_azure_mcp(server_id)
                    action = "stop"
                    server = update_mcp_server(
                        server_id,
                        {
                            "enabled": False,
                            "provisioning_status": "stopped",
                            "provisioning_error": "",
                        },
                    ) or server
                insert_integration_lifecycle_event(
                    action=action,
                    status="success",
                    connection_id=server_id,
                    team_id=str(server.get("team_id") or ""),
                    actor_id=str(actor.get("_id") or ""),
                    vendor="azure",
                )
            except IntegrationControllerError as error:
                server = update_mcp_server(
                    server_id,
                    {
                        "enabled": requested_enabled,
                        "provisioning_status": (
                            "failed" if requested_enabled else "stop_pending"
                        ),
                        "provisioning_error": str(error)[:500],
                    },
                ) or server
                insert_integration_lifecycle_event(
                    action="provision" if requested_enabled else "stop",
                    status="error",
                    connection_id=server_id,
                    team_id=str(server.get("team_id") or ""),
                    actor_id=str(actor.get("_id") or ""),
                    vendor="azure",
                    error_type=type(error).__name__,
                )
                return jsonify(serialize_mcp_server(server)), 202
        return jsonify(serialize_mcp_server(server or existing))
    except AccessControlError as error:
        return error_response(error, "/admin/mcp-servers/<server_id>")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.delete("/admin/mcp-servers/<server_id>")
@authenticated
async def admin_delete_mcp_server(auth_claims: dict[str, Any], server_id: str):
    try:
        existing = get_mcp_server(server_id)
        if not existing:
            return jsonify({"error": "MCP server not found"}), 404
        actor = _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        managed_azure = (
            str(existing.get("vendor") or "") == "azure"
            and str(existing.get("deployment_mode") or "external") == "managed"
        )
        if managed_azure:
            _require_system_admin(auth_claims)
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
        cleanup_error = None
        if managed_azure:
            try:
                await IntegrationControllerClient().delete_azure_mcp(server_id)
            except IntegrationControllerError as error:
                cleanup_error = error
        soft_delete_mcp_server(
            server_id,
            provisioning_status=(
                "cleanup_pending" if cleanup_error else "deleted"
            ) if managed_azure else None,
            provisioning_error=str(cleanup_error or ""),
        )
        if managed_azure:
            insert_integration_lifecycle_event(
                action="delete",
                status="pending" if cleanup_error else "success",
                connection_id=server_id,
                team_id=str(existing.get("team_id") or ""),
                actor_id=str(actor.get("_id") or ""),
                vendor="azure",
                error_type=type(cleanup_error).__name__ if cleanup_error else "",
            )
        return jsonify(
            {"success": True, "cleanup_pending": bool(cleanup_error)}
        ), (202 if cleanup_error else 200)
    except AccessControlError as error:
        return error_response(error, "/admin/mcp-servers/<server_id>")


@bp.post("/admin/mcp-servers/<server_id>/test")
@authenticated
async def admin_test_mcp_server(auth_claims: dict[str, Any], server_id: str):
    try:
        server = get_mcp_server(server_id)
        if not server:
            return jsonify({"error": "MCP server not found"}), 404
        _require_integration_catalog_access(auth_claims, str(server.get("team_id") or ""))
        config = MCPServerConfig(
            server_id=str(server["_id"]),
            name=str(server["name"]),
            url=str(server["url"]),
            vendor=str(server.get("vendor") or "generic"),
            operation_mode=(
                "read_only"
                if str(server.get("vendor") or "generic") == "azure"
                else str(server.get("operation_mode") or "read_write")
            ),
            headers=decrypt_mcp_headers(server),
            entra_credentials=(
                EntraClientCredentials(
                    tenant_id=str(server.get("entra_tenant_id") or ""),
                    client_id=str(server.get("entra_client_id") or ""),
                    client_secret=decrypt_mcp_entra_client_secret(server),
                    scope=str(server.get("entra_scope") or ""),
                )
                if server.get("auth_type") == "entra_client_credentials"
                and server.get("deployment_mode") != "managed"
                else None
            ),
            managed=server.get("deployment_mode") == "managed",
            allowed_tools=tuple(server.get("allowed_tools") or ()),
            timeout_seconds=float(server.get("timeout_seconds") or 60),
        )
        discovered_tools = await discover_mcp_tools(config)
        tools = [
            tool
            for tool in discovered_tools
            if config.operation_mode != "read_only"
            or is_read_only_mcp_tool(tool.name)
        ]
        return jsonify(
            {
                "success": True,
                "blocked_tool_count": len(discovered_tools) - len(tools),
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                    }
                    for tool in tools
                ],
            }
        )
    except AccessControlError as error:
        return error_response(error, "/admin/mcp-servers/<server_id>/test")
    except Exception as error:
        current_app.logger.warning("MCP server connection test failed: %s", error)
        return jsonify({"success": False, "error": str(error)}), 400


async def _provision_managed_azure_mcp(server: dict[str, Any]) -> dict[str, Any]:
    try:
        runtime = azure_mcp_runtime_config(server)
    except ValueError as error:
        raise IntegrationControllerError(str(error)) from None
    result = await IntegrationControllerClient().provision_azure_mcp(
        AzureMCPProvisionRequest(
            connection_id=str(server["_id"]),
            azure_tenant_id=runtime["azure_tenant_id"],
            azure_client_id=runtime["azure_client_id"],
            azure_client_secret=runtime["azure_client_secret"],
            azure_subscription_ids=runtime["azure_subscription_ids"],
        )
    )
    url = str(result.get("url") or "").strip()
    parsed = urlparse(url)
    expected_host = f"nexora-azure-mcp-{server['_id']}"
    if (
        parsed.scheme != "http"
        or parsed.hostname != expected_host
        or parsed.port != 8080
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise IntegrationControllerError(
            "Integration controller returned an invalid Azure MCP URL"
        )
    if (
        str(server.get("url") or "") == url
        and server.get("enabled") is True
        and server.get("provisioning_status") == "ready"
        and not server.get("provisioning_error")
    ):
        return server
    return update_mcp_server(
        str(server["_id"]),
        {
            "url": url,
            "enabled": True,
            "provisioning_status": "ready",
            "provisioning_error": "",
        },
    ) or server


async def _reconcile_managed_azure_mcp_servers() -> None:
    while True:
        try:
            controller = IntegrationControllerClient()
            for stopped in await asyncio.to_thread(
                list_pending_managed_azure_mcp_stops
            ):
                try:
                    await controller.stop_azure_mcp(str(stopped["_id"]))
                    update_mcp_server(
                        str(stopped["_id"]),
                        {
                            "provisioning_status": "stopped",
                            "provisioning_error": "",
                        },
                    )
                    insert_integration_lifecycle_event(
                        action="stop",
                        status="success",
                        connection_id=str(stopped["_id"]),
                        team_id=str(stopped.get("team_id") or ""),
                        actor_id="system",
                        vendor="azure",
                    )
                except Exception as error:
                    current_app.logger.warning(
                        "Managed Azure MCP stop retry failed for %s: %s",
                        stopped.get("_id"),
                        type(error).__name__,
                    )
            for deleted in await asyncio.to_thread(
                list_pending_managed_azure_mcp_deletions
            ):
                try:
                    await controller.delete_azure_mcp(str(deleted["_id"]))
                    complete_mcp_server_cleanup(str(deleted["_id"]))
                    insert_integration_lifecycle_event(
                        action="cleanup",
                        status="success",
                        connection_id=str(deleted["_id"]),
                        team_id=str(deleted.get("team_id") or ""),
                        actor_id="system",
                        vendor="azure",
                    )
                except Exception as error:
                    current_app.logger.warning(
                        "Managed Azure MCP cleanup retry failed for %s: %s",
                        deleted.get("_id"),
                        type(error).__name__,
                    )
            for server in await asyncio.to_thread(
                list_enabled_managed_azure_mcp_servers
            ):
                previous_status = str(server.get("provisioning_status") or "")
                try:
                    updated = await _provision_managed_azure_mcp(server)
                    if previous_status != "ready":
                        insert_integration_lifecycle_event(
                            action="reconcile",
                            status="success",
                            connection_id=str(server.get("_id") or ""),
                            team_id=str(server.get("team_id") or ""),
                            actor_id="system",
                            vendor="azure",
                        )
                    server = updated
                except Exception as error:
                    update_mcp_server(
                        str(server.get("_id") or ""),
                        {
                            "provisioning_status": "failed",
                            "provisioning_error": str(error)[:500],
                        },
                    )
                    if previous_status != "failed":
                        insert_integration_lifecycle_event(
                            action="reconcile",
                            status="error",
                            connection_id=str(server.get("_id") or ""),
                            team_id=str(server.get("team_id") or ""),
                            actor_id="system",
                            vendor="azure",
                            error_type=type(error).__name__,
                        )
                    current_app.logger.warning(
                        "Managed Azure MCP reconciliation failed for %s: %s",
                        server.get("_id"),
                        type(error).__name__,
                    )
        except Exception:
            current_app.logger.exception("Managed Azure MCP reconciliation scan failed")
        await asyncio.sleep(30)


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


@bp.get("/admin/system-health")
@authenticated
async def admin_system_health(auth_claims: dict[str, Any]):
    """Return a secret-free operational snapshot for System Admins."""

    _require_system_admin(auth_claims)
    snapshot = await build_system_health_snapshot(
        get_database(), current_app.config, os.environ
    )
    return jsonify(snapshot)


def _license_verification_keys():
    return load_verification_keys(os.getenv("NEXORA_LICENSE_PUBLIC_KEY_DIR"))


@bp.get("/admin/license")
@authenticated
async def admin_get_license(auth_claims: dict[str, Any]):
    """Return safe licensing status without the imported license key."""

    _require_system_admin(auth_claims)
    try:
        return jsonify(get_license_status(_license_verification_keys()))
    except LicenseVerificationError as error:
        return jsonify({"error": str(error)}), 503


@bp.post("/admin/license/trial")
@authenticated
async def admin_start_license_trial(auth_claims: dict[str, Any]):
    user = _require_system_admin(auth_claims)
    try:
        return jsonify(start_trial(actor_id=str(user.get("_id") or ""))), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.put("/admin/license")
@authenticated
async def admin_import_license(auth_claims: dict[str, Any]):
    user = _require_system_admin(auth_claims)
    body = await request.get_json()
    license_key = (body or {}).get("license_key") if isinstance(body, dict) else None
    try:
        verification_keys = _license_verification_keys()
        if not verification_keys:
            return jsonify({"error": "No trusted license signing keys are configured"}), 503
        return jsonify(
            import_license(
                license_key,
                verification_keys,
                actor_id=str(user.get("_id") or ""),
            )
        )
    except LicenseVerificationError as error:
        return jsonify({"error": str(error)}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.route("/config", methods=["GET"])
async def config():
    runtime_settings: RuntimeSettings = current_app.config[CONFIG_RUNTIME_SETTINGS]
    llm_profiles: dict[str, LLMProfile] = current_app.config[CONFIG_LLM_PROFILES]
    web_search_provider = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()
    web_search_configured = (
        web_search_provider == "brave" and bool(os.getenv("WEB_SEARCH_API_KEY", "").strip())
    ) or (
        web_search_provider == "searxng" and bool(os.getenv("WEB_SEARCH_BASE_URL", "").strip())
    )
    return jsonify(
        {
            "runtimeMode": runtime_settings.mode.value,
            "knowledgeStorageProvider": os.getenv("KNOWLEDGE_STORAGE_PROVIDER", "azure").strip().lower(),
            "knowledgeSearchProvider": os.getenv("KNOWLEDGE_SEARCH_PROVIDER", "azure").strip().lower(),
            "agentRuntimeMode": (
                os.getenv("AGENT_RUNTIME_MODE", "per_agent").strip().lower()
                if os.getenv("AGENT_RUNTIME_MODE", "per_agent").strip().lower() in {"legacy", "langgraph"}
                else "per_agent"
            ),
            "webSearchProvider": web_search_provider or None,
            "webSearchConfigured": web_search_configured,
            "llmProvider": runtime_settings.llm.provider.value,
            "embeddingProvider": runtime_settings.embedding.provider.value,
            "embeddingProfileId": current_app.config.get(CONFIG_ACTIVE_EMBEDDING_PROFILE_ID, ENVIRONMENT_PROFILE_ID),
            "embeddingModel": runtime_settings.embedding.model,
            "embeddingDimensions": runtime_settings.embedding.dimensions,
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
            "showChatHistoryDatabase": current_app.config[CONFIG_CHAT_HISTORY_DATABASE_ENABLED],
            "showAgenticRetrievalOption": current_app.config[CONFIG_AGENTIC_RETRIEVAL_ENABLED],
            "chatDocumentAttachmentsEnabled": current_app.config.get(CONFIG_CHAT_ATTACHMENT_STORE) is not None,
            "maxUploadSizeBytes": current_app.config["MAX_CONTENT_LENGTH"],
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
    try:
        _require_integration_catalog_access(auth_claims, team_id, allow_agent_management=True)
    except AccessControlError as error:
        return error_response(error, "/mail_configs")
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
        _require_integration_catalog_access(auth_claims, normalized["team_id"])
        document = insert_mail_connection(normalized)
        return jsonify({"message": "Mail connection created", "connection": serialize_mail_connection(document)}), 201
    except AccessControlError as exc:
        return error_response(exc, "/insert_mail_config")
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
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        if "team_id" in body and str(body.get("team_id") or "") != str(existing.get("team_id") or ""):
            raise ValueError("Use Assign to team to change integration ownership")
        document = update_mail_connection(
            connection_id, normalize_mail_connection(body, existing=existing)
        )
        return jsonify({"message": "Mail connection updated", "connection": serialize_mail_connection(document or existing)})
    except AccessControlError as exc:
        return error_response(exc, "/edit_mail_config")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/delete_mail_config")
@authenticated
async def remove_mail_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("config_id") or "")
        existing = get_mail_connection(connection_id)
        if not existing:
            return jsonify({"error": "Mail connection not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
    except AccessControlError as error:
        return error_response(error, "/delete_mail_config")
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
        _require_integration_catalog_access(auth_claims, str(connection.get("team_id") or ""))
        result = await test_mail_connection(connection, decrypt_mail_secrets(connection))
        return jsonify(result)
    except AccessControlError as exc:
        return error_response(exc, "/test_mail_connection")
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
        mail_connection = get_mail_connection(normalized["email_id"])
        if not mail_connection:
            raise ValueError("A valid email_id is required")
        _require_agent_integration_team(normalized["agent_id"], mail_connection)
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
        mail_connection = get_mail_connection(normalized["email_id"])
        if not mail_connection:
            raise ValueError("A valid email_id is required")
        _require_agent_integration_team(normalized["agent_id"], mail_connection)
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


@bp.get("/web_search_connections")
@authenticated
async def web_search_connections(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "")
    try:
        _require_integration_catalog_access(auth_claims, team_id, allow_agent_management=True)
        return jsonify([
            serialize_web_search_connection(
                item,
                usage_count=web_search_connection_usage_count(str(item["_id"])),
            )
            for item in list_web_search_connections(team_id)
        ])
    except AccessControlError as error:
        return error_response(error, "/web_search_connections")


@bp.post("/save_web_search_connection")
@authenticated
async def save_web_search_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("connection_id") or "")
        existing = get_web_search_connection(connection_id) if connection_id else None
        if connection_id and not existing:
            return jsonify({"error": "Web Search connection not found"}), 404
        normalized = normalize_web_search_connection(body, existing=existing)
        current_team_id = str(existing.get("team_id") or "") if existing else normalized["team_id"]
        _require_integration_catalog_access(auth_claims, current_team_id)
        if existing and "team_id" in body and str(body.get("team_id") or "") != current_team_id:
            raise ValueError("Use Assign to team to change integration ownership")
        document = (
            update_web_search_connection(connection_id, normalized)
            if existing
            else insert_web_search_connection(normalized)
        )
        return jsonify({
            "message": "Web Search connection saved",
            "connection": serialize_web_search_connection(
                document or existing,
                usage_count=web_search_connection_usage_count(connection_id)
                if connection_id else 0,
            ),
        })
    except AccessControlError as error:
        return error_response(error, "/save_web_search_connection")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/test_web_search_connection")
@authenticated
async def test_web_search_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection = get_web_search_connection(str(body.get("connection_id") or ""))
        if not connection:
            raise ValueError("Save the Web Search connection before testing it")
        _require_integration_catalog_access(auth_claims, str(connection.get("team_id") or ""))
        provider = create_web_search_provider(
            connection.get("provider"),
            api_key=decrypt_web_search_api_key(connection),
            base_url=connection.get("base_url"),
            timeout_seconds=float(connection.get("timeout_seconds") or 10),
        )
        provider.search("official documentation", 1)
        return jsonify({"ok": True, "message": "Web Search connection succeeded"})
    except AccessControlError as error:
        return error_response(error, "/test_web_search_connection")
    except (ValueError, WebSearchError) as error:
        current_app.logger.warning("Web Search connection test failed: %s", error)
        return jsonify({"ok": False, "error": str(error)}), 400


@bp.post("/delete_web_search_connection")
@authenticated
async def delete_web_search_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("connection_id") or "")
        existing = get_web_search_connection(connection_id)
        if not existing:
            return jsonify({"error": "Web Search connection not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        if web_search_connection_usage_count(connection_id):
            return jsonify({"error": "Remove Agent bindings before deleting this connection"}), 409
        if not soft_delete_web_search_connection(connection_id):
            return jsonify({"error": "Web Search connection not found"}), 404
        return jsonify({"message": "Web Search connection deleted"})
    except AccessControlError as error:
        return error_response(error, "/delete_web_search_connection")


@bp.get("/business_document_connections")
@authenticated
async def business_document_connections(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "")
    try:
        _require_integration_catalog_access(auth_claims, team_id, allow_agent_management=True)
        results = []
        for document in list_business_document_connections(team_id):
            usage_count = business_document_bindings_collection.count_documents(
                {"connection_id": str(document["_id"]), "delete_at": None}
            )
            results.append(serialize_business_document_connection(document, usage_count=usage_count))
        return jsonify(results)
    except AccessControlError as error:
        return error_response(error, "/business_document_connections")


@bp.post("/save_business_document_connection")
@authenticated
async def save_business_document_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("connection_id") or "")
        existing = get_business_document_connection(connection_id) if connection_id else None
        if connection_id and not existing:
            return jsonify({"error": "Business document connection not found"}), 404
        normalized = normalize_business_document_connection(body, existing=existing)
        current_team_id = str(existing.get("team_id") or "") if existing else normalized["team_id"]
        _require_integration_catalog_access(auth_claims, current_team_id)
        if existing and "team_id" in body and str(body.get("team_id") or "") != current_team_id:
            raise ValueError("Use Assign to team to change integration ownership")
        document = (
            update_business_document_connection(connection_id, normalized)
            if existing
            else insert_business_document_connection(normalized)
        )
        return jsonify({
            "message": "Business document connection saved",
            "connection": serialize_business_document_connection(document or existing),
        })
    except AccessControlError as error:
        return error_response(error, "/save_business_document_connection")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/test_business_document_connection")
@authenticated
async def test_business_document_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection = get_business_document_connection(str(body.get("connection_id") or ""))
        if not connection:
            raise ValueError("Save the business document connection before testing it")
        _require_integration_catalog_access(auth_claims, str(connection.get("team_id") or ""))
        return jsonify(await test_business_document_connection(
            connection, decrypt_business_document_secrets(connection)
        ))
    except AccessControlError as error:
        return error_response(error, "/test_business_document_connection")
    except (ValueError, OSError) as error:
        current_app.logger.warning("Business document connection test failed: %s", error)
        return jsonify({"ok": False, "error": str(error)}), 400


@bp.post("/delete_business_document_connection")
@authenticated
async def remove_business_document_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection_id = str(body.get("connection_id") or "")
        existing = get_business_document_connection(connection_id)
        if not existing:
            return jsonify({"error": "Business document connection not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        if business_document_bindings_collection.count_documents({"connection_id": connection_id, "delete_at": None}):
            return jsonify({"error": "Remove Agent bindings before deleting this connection"}), 409
        if not soft_delete_business_document_connection(connection_id):
            return jsonify({"error": "Business document connection not found"}), 404
        return jsonify({"message": "Business document connection deleted"})
    except AccessControlError as error:
        return error_response(error, "/delete_business_document_connection")


@bp.get("/business_document_bindings")
@authenticated
async def business_document_bindings(auth_claims: dict[str, Any]):
    agent_id = str(request.args.get("agent_id") or "")
    agent = get_agent_by_id(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    team = get_team_by_agent_id(agent_id)
    if not team:
        return jsonify({"error": "Agent team not found"}), 404
    try:
        _require_team_access(auth_claims, str(team.get("_id") or ""), permission="Manage agents")
        return jsonify([_mail_binding_response(item) for item in list_business_document_bindings(agent_id)])
    except AccessControlError as error:
        return error_response(error, "/business_document_bindings")


@bp.post("/save_business_document_binding")
@authenticated
async def save_business_document_binding(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        binding_id = str(body.get("binding_id") or "")
        existing = get_business_document_binding(binding_id) if binding_id else None
        normalized = normalize_business_document_binding({**(existing or {}), **body})
        if not get_agent_by_id(normalized["agent_id"]):
            raise ValueError("A valid agent_id is required")
        connection = get_business_document_connection(normalized["connection_id"])
        if not connection:
            raise ValueError("A valid connection_id is required")
        _require_agent_integration_team(normalized["agent_id"], connection)
        team = get_team_by_agent_id(normalized["agent_id"])
        _require_team_access(auth_claims, str((team or {}).get("_id") or ""), permission="Manage agents")
        if "create" in normalized["permissions"] and connection.get("operation_mode") != "read_write":
            raise ValueError("Create permission requires a Read & create connection")
        duplicate = business_document_bindings_collection.find_one({
            "_id": {"$ne": binding_id},
            "agent_id": normalized["agent_id"],
            "connection_id": normalized["connection_id"],
            "delete_at": None,
        })
        if duplicate:
            return jsonify({"error": "This document connection is already assigned to the Agent"}), 409
        document = (
            update_business_document_binding(binding_id, normalized) and get_business_document_binding(binding_id)
            if existing
            else insert_business_document_binding(normalized)
        )
        return jsonify({"message": "Business document binding saved", "binding": _mail_binding_response(document or normalized)})
    except AccessControlError as error:
        return error_response(error, "/save_business_document_binding")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/delete_business_document_binding")
@authenticated
async def remove_business_document_binding(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        binding = get_business_document_binding(str(body.get("binding_id") or ""))
        if not binding:
            return jsonify({"error": "Business document binding not found"}), 404
        connection = get_business_document_connection(str(binding.get("connection_id") or ""))
        _require_agent_integration_team(str(binding.get("agent_id") or ""), connection)
        team = get_team_by_agent_id(str(binding.get("agent_id") or ""))
        _require_team_access(auth_claims, str((team or {}).get("_id") or ""), permission="Manage agents")
        if not delete_business_document_binding(str(binding["_id"])):
            return jsonify({"error": "Business document binding not found"}), 404
        return jsonify({"message": "Business document binding deleted"})
    except AccessControlError as error:
        return error_response(error, "/delete_business_document_binding")


@bp.get("/messaging_connections")
@authenticated
async def messaging_connections(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "")
    try:
        _require_integration_catalog_access(auth_claims, team_id, allow_agent_management=True)
    except AccessControlError as error:
        return error_response(error, "/messaging_connections")
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
        current_team_id = str(existing.get("team_id") or "") if existing else normalized["team_id"]
        _require_integration_catalog_access(auth_claims, current_team_id)
        if existing and "team_id" in body and str(body.get("team_id") or "") != current_team_id:
            raise ValueError("Use Assign to team to change integration ownership")
        document = update_messaging_connection(connection_id, normalized) if existing else insert_messaging_connection(normalized)
        return jsonify({"message": "Messaging connection saved", "connection": serialize_messaging_connection(document or existing)})
    except AccessControlError as exc:
        return error_response(exc, "/save_messaging_connection")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/test_messaging_connection")
@authenticated
async def test_messaging_config(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        connection = get_messaging_connection(str(body.get("connection_id") or ""))
        if not connection: raise ValueError("Messaging connection not found")
        _require_integration_catalog_access(auth_claims, str(connection.get("team_id") or ""))
        return jsonify(await test_messaging_connection(connection, decrypt_messaging_secrets(connection)))
    except AccessControlError as exc:
        return error_response(exc, "/test_messaging_connection")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.post("/delete_messaging_connection")
@authenticated
async def remove_messaging_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json(); connection_id = str(body.get("connection_id") or "")
        existing = get_messaging_connection(connection_id)
        if not existing: return jsonify({"error": "Connection not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
    except AccessControlError as error:
        return error_response(error, "/delete_messaging_connection")
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
        messaging_connection = get_messaging_connection(normalized["connection_id"])
        if not messaging_connection: raise ValueError("A valid connection_id is required")
        _require_agent_integration_team(normalized["agent_id"], messaging_connection)
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
INGESTION_TASKS: set[asyncio.Task] = set()
WEB_SOURCE_INDEX_TASKS: set[asyncio.Task] = set()
AGENT_INVOCATION_JOB_TASKS: set[asyncio.Task] = set()
AGENT_INVOCATION_JOB_IDS: set[str] = set()
ATTACHMENT_EXTRACTION_WORKER_ID = f"attachment-{uuid.uuid4()}"
WEB_SOURCE_INDEX_WORKER_ID = f"web-source-{uuid.uuid4()}"
AGENT_INVOCATION_JOB_WORKER_ID = f"agent-invocation-{uuid.uuid4()}"


async def _heartbeat_agent_invocation_job(job_id: str) -> None:
    while True:
        await asyncio.sleep(30)
        updated = await asyncio.to_thread(
            heartbeat_agent_invocation_job, job_id, AGENT_INVOCATION_JOB_WORKER_ID
        )
        if not updated:
            return


async def _run_agent_invocation_job(job_id: str) -> None:
    usage_context: dict[str, Any] = {}
    heartbeat_task: asyncio.Task | None = None
    started = time.monotonic()
    claimed: dict[str, Any] | None = None
    try:
        claimed = await asyncio.to_thread(
            claim_agent_invocation_job, job_id, AGENT_INVOCATION_JOB_WORKER_ID
        )
        if not claimed:
            return
        heartbeat_task = asyncio.create_task(
            _heartbeat_agent_invocation_job(job_id)
        )
        key_document = await asyncio.to_thread(
            get_agent_invocation_key, str(claimed.get("key_id") or "")
        )
        validate_agent_invocation_key_document(key_document)
        input_text = await asyncio.to_thread(
            decrypt_agent_invocation_job_input, claimed
        )
        result, conversation_id = await _execute_agent_invocation(
            key_document=key_document or {},
            agent_id=str(claimed.get("agent_id") or ""),
            input_text=input_text,
            conversation_id=claimed.get("conversation_id"),
            usage_context=usage_context,
        )
        public_result = _agent_invocation_public_response(
            result,
            request_id=str(claimed["_id"]),
            agent_id=str(claimed.get("agent_id") or ""),
            conversation_id=conversation_id,
            access_type=(key_document or {}).get("access_type"),
        )
        await asyncio.to_thread(
            complete_agent_invocation_job,
            job_id,
            AGENT_INVOCATION_JOB_WORKER_ID,
            result=public_result,
        )
        await asyncio.to_thread(
            mark_agent_invocation_key_used, str(claimed.get("key_id") or "")
        )
        await asyncio.to_thread(
            insert_agent_invocation_audit,
            request_id=job_id,
            key_id=str(claimed.get("key_id") or ""),
            team_id=str(claimed.get("team_id") or ""),
            agent_id=str(claimed.get("agent_id") or ""),
            event_type="agent_job_completed",
            status="success",
            duration_ms=int((time.monotonic() - started) * 1000),
            access_type=(key_document or {}).get("access_type"),
        )
    except asyncio.CancelledError:
        await _finish_usage_reservation(usage_context, state="released")
        if claimed:
            await asyncio.to_thread(
                release_agent_invocation_job,
                job_id,
                AGENT_INVOCATION_JOB_WORKER_ID,
            )
        raise
    except Exception as error:
        await _finish_usage_reservation(usage_context, state="released")
        if claimed:
            await asyncio.to_thread(
                complete_agent_invocation_job,
                job_id,
                AGENT_INVOCATION_JOB_WORKER_ID,
                error=error,
            )
            await asyncio.to_thread(
                insert_agent_invocation_audit,
                request_id=job_id,
                key_id=str(claimed.get("key_id") or ""),
                team_id=str(claimed.get("team_id") or ""),
                agent_id=str(claimed.get("agent_id") or ""),
                event_type="agent_job_completed",
                status="failed",
                duration_ms=int((time.monotonic() - started) * 1000),
                error_code=type(error).__name__,
                access_type=(key_document or {}).get("access_type"),
            )
        current_app.logger.exception("Agent invocation job failed: id=%s", job_id)
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)


def _schedule_agent_invocation_job(job_id: str) -> None:
    normalized_job_id = str(job_id)
    if normalized_job_id in AGENT_INVOCATION_JOB_IDS:
        return
    AGENT_INVOCATION_JOB_IDS.add(normalized_job_id)
    task = asyncio.create_task(_run_agent_invocation_job(normalized_job_id))
    AGENT_INVOCATION_JOB_TASKS.add(task)
    BACKGROUND_TASKS.add(task)

    def _discard(_task: asyncio.Task) -> None:
        AGENT_INVOCATION_JOB_IDS.discard(normalized_job_id)
        AGENT_INVOCATION_JOB_TASKS.discard(_task)
        BACKGROUND_TASKS.discard(_task)

    task.add_done_callback(_discard)


async def _recover_agent_invocation_jobs(interval_seconds: float) -> None:
    while True:
        try:
            jobs = await asyncio.to_thread(list_recoverable_agent_invocation_jobs)
            for job in jobs:
                _schedule_agent_invocation_job(str(job.get("_id") or ""))
        except asyncio.CancelledError:
            raise
        except Exception:
            current_app.logger.exception("Unable to recover Agent invocation jobs")
        await asyncio.sleep(interval_seconds)


def _agent_draft_retention_hours() -> float:
    try:
        value = float(os.getenv("AGENT_DRAFT_RETENTION_HOURS", "24"))
    except ValueError as error:
        raise ValueError("AGENT_DRAFT_RETENTION_HOURS must be numeric") from error
    if not math.isfinite(value) or value < 1 or value > 168:
        raise ValueError("AGENT_DRAFT_RETENTION_HOURS must be between 1 and 168")
    return value


async def _run_agent_draft_cleanup(interval_seconds: float) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            expired_ids = await asyncio.to_thread(list_expired_agent_draft_ids)
            for agent_id in expired_ids:
                await asyncio.to_thread(
                    delete_agent_cascade,
                    agent_id,
                    reason="draft_expired",
                )
            if expired_ids:
                current_app.logger.info("Expired Agent drafts removed: count=%d", len(expired_ids))
        except asyncio.CancelledError:
            raise
        except Exception:
            current_app.logger.exception("Unable to clean up expired Agent drafts")


class _NamedAttachmentBytesIO(BytesIO):
    def __init__(self, content: bytes, filename: str):
        super().__init__(content)
        self.name = filename
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
    INGESTION_TASKS.add(task)
    task.add_done_callback(INGESTION_TASKS.discard)


def _schedule_chat_attachment_extraction(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
) -> None:
    store: AttachmentStore = current_app.config[CONFIG_CHAT_ATTACHMENT_STORE]
    index: AttachmentIndex = current_app.config[CONFIG_CHAT_ATTACHMENT_INDEX]
    file_processors = current_app.config.get(CONFIG_CHAT_ATTACHMENT_PROCESSORS) or {}
    task = asyncio.create_task(
        _run_chat_attachment_extraction(
            store,
            index,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            file_processors=file_processors,
        )
    )
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    ATTACHMENT_EXTRACTION_TASKS.add(task)
    task.add_done_callback(ATTACHMENT_EXTRACTION_TASKS.discard)


async def _extract_chat_attachment_chunks(stored, file_processors: dict[str, Any]):
    try:
        return await asyncio.to_thread(
            extract_attachment_chunks,
            filename=stored.record.filename,
            content_type=stored.record.content_type,
            content=stored.content,
        )
    except AttachmentExtractionError as error:
        if "OCR is required" not in str(error):
            raise

    extension = Path(stored.record.filename).suffix.lower()
    processor = file_processors.get(extension)
    if processor is None:
        raise AttachmentExtractionError("Document has no machine-readable text; OCR is required")
    content = _NamedAttachmentBytesIO(stored.content, stored.record.filename)
    parser = processor.parser
    selected_parser = (
        parser.select_parser(content, routing_context={"scope": "personal"})
        if hasattr(parser, "select_parser")
        else parser
    )
    pages = [page async for page in selected_parser.parse(content=content)]
    return chunk_attachment_pages(
        (
            page.page_num + 1,
            str(page.page_num + 1),
            page.text,
        )
        for page in pages
    )


async def _run_chat_attachment_extraction(
    store: AttachmentStore,
    index: AttachmentIndex,
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    file_processors: dict[str, Any] | None = None,
) -> None:
    started = await asyncio.to_thread(
        claim_attachment_extraction,
        attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
        worker_id=ATTACHMENT_EXTRACTION_WORKER_ID,
    )
    if not started:
        return
    try:
        stored = await store.get(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        chunks = await _extract_chat_attachment_chunks(stored, file_processors or {})
        chunk_count = await index.replace_attachment(stored.record, chunks)
        completed = await asyncio.to_thread(
            update_attachment_status,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            status="ready",
            chunk_count=chunk_count,
            extracted_characters=sum(len(chunk.text) for chunk in chunks),
            worker_id=ATTACHMENT_EXTRACTION_WORKER_ID,
        )
        if not completed:
            active = await asyncio.to_thread(
                get_attachment_metadata,
                attachment_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
            if not active:
                await index.delete_attachment(
                    attachment_id,
                    owner_id=owner_id,
                    conversation_id=conversation_id,
                )
    except asyncio.CancelledError:
        await asyncio.to_thread(
            release_attachment_extraction,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            worker_id=ATTACHMENT_EXTRACTION_WORKER_ID,
        )
        raise
    except AttachmentExtractionError as error:
        error_code = "ocr_required" if "OCR is required" in str(error) else "extraction_failed"
        failed = await asyncio.to_thread(
            update_attachment_status,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            status="failed",
            error_code=error_code,
            worker_id=ATTACHMENT_EXTRACTION_WORKER_ID,
        )
        if failed:
            await index.delete_attachment(
                attachment_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
    except Exception:
        failed = await asyncio.to_thread(
            update_attachment_status,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            status="failed",
            error_code="extraction_failed",
            worker_id=ATTACHMENT_EXTRACTION_WORKER_ID,
        )
        if failed:
            try:
                await index.delete_attachment(
                    attachment_id,
                    owner_id=owner_id,
                    conversation_id=conversation_id,
                )
            except Exception:
                current_app.logger.exception("Unable to clean partial Chat attachment index")
        current_app.logger.exception("Chat attachment extraction failed: %s", attachment_id)


async def _recover_chat_attachment_extractions(interval_seconds: float = 30) -> None:
    while True:
        try:
            items = await asyncio.to_thread(list_recoverable_attachment_metadata)
            for item in items:
                _schedule_chat_attachment_extraction(
                    str(item["_id"]),
                    owner_id=str(item["owner_id"]),
                    conversation_id=str(item["conversation_id"]),
                )
        except Exception:
            current_app.logger.exception("Unable to recover private Chat attachment extractions")
        await asyncio.sleep(interval_seconds)


async def _set_job_blob_status(job: dict[str, Any], status: str) -> None:
    if job.get("scope") == "personal":
        return
    scope = "team" if job.get("scope") == "team" else "global"
    tags = {"status": status}
    if scope == "team":
        tags["data_groups"] = "/".join(job.get("data_group_ids") or [])
    try:
        await _knowledge_store().set_tags(scope, str(job["storage_path"]), tags)
    except Exception:
        current_app.logger.warning("Unable to update object status for ingestion job %s", job.get("_id"), exc_info=True)


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
    current_stage = str(job.get("status") or "extracting")

    async def update_stage(status: str) -> None:
        nonlocal current_stage
        if status == current_stage:
            return
        await asyncio.to_thread(
            update_ingestion_job_status,
            job_id,
            status,
            worker_id=INGESTION_WORKER_ID,
        )
        current_stage = status
        await _set_job_blob_status(job, "InProgress")

    started_at = time.monotonic()
    try:
        await _set_job_blob_status(job, "InProgress")
        scope = str(job["scope"])
        if os.getenv("DISABLE_USAGE_QUOTAS", "").lower() != "true":
            try:
                await asyncio.to_thread(
                    check_document_quota,
                    str(job.get("team_id") or ""),
                    str(job.get("owner_id") or ""),
                )
            except ValueError as error:
                raise AccessControlError(str(error), status_code=429) from error
        stored = await _knowledge_store().read(scope, str(job["storage_path"]))
        if scope == "personal":
            acls = {"oids": [str(job["owner_id"])]}
            folder = ""
        else:
            acls = {"oids": [], "groups": list(job.get("data_group_ids") or [])}
            folder = os.path.dirname(str(job["storage_path"]))
            folder = folder + os.sep if folder else ""

        stream = BytesIO(stored.data)
        stream.name = str(job["filename"])
        ingester: UploadUserFileStrategy = current_app.config[CONFIG_INGESTER]
        async with INGEST_SEM:
            if scope == "personal":
                _is_docintel, count = await ingester.add_file(
                    File(content=stream, acls=acls, url=stored.url),
                    routing_context=job.get("routing_context") or {},
                    status_callback=update_stage,
                )
            else:
                _is_docintel, count = await ingester.add_global_file(
                    File(content=stream, acls=acls, url=stored.url),
                    folder,
                    routing_context=job.get("routing_context") or {},
                    status_callback=update_stage,
                )
            usage_scope = "personal" if scope == "personal" else ("team" if scope == "team" else "global")
            await asyncio.to_thread(
                insert_document_processing_usage,
                owner_id=str(job.get("owner_id") or ""),
                owner_name=str(job.get("owner_name") or ""),
                team_id=str(job.get("team_id") or ""),
                scope=usage_scope,
                provider_id=str(job.get("provider_id") or ""),
                provider_name=str(job.get("provider_name") or "System parser"),
                profile_id=str(job.get("profile_id") or ""),
                profile_name=str(job.get("profile_name") or ""),
                page_count=count,
                file_type=Path(str(job.get("filename") or "")).suffix.lstrip("."),
                duration_ms=int((time.monotonic() - started_at) * 1000),
                event_id=f"ingestion:{job_id}",
            )
        await asyncio.to_thread(
            update_ingestion_job_status,
            job_id,
            "indexed",
            worker_id=INGESTION_WORKER_ID,
        )
        await _set_job_blob_status(job, "Pass")
    except asyncio.CancelledError:
        released = await asyncio.to_thread(
            release_ingestion_job,
            job_id,
            INGESTION_WORKER_ID,
        )
        if released:
            await _set_job_blob_status(job, "Pending")
        raise
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
    file_io = io.BufferedReader(file)
    size = _file_size(file_io)
    await _knowledge_store().put(
        "personal",
        f"{user_oid}/{file.filename}",
        file_io,
        size=size,
        metadata={"UploadedBy": user_oid},
    )
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
    await _knowledge_store().delete("personal", f"{user_oid}/{filename}")
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
    existing_files: dict[str, int] = {}
    for stored_object in await _knowledge_store().list("global"):
        filename = stored_object.key.split("/")[-1]
        existing_files[filename] = stored_object.size

    jobs = []
    for file in request_files.getlist("file"):
        new_filename = (file.filename).split("/")[-1]
        blob_path = f"{file.filename}"
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
        await _knowledge_store().put(
            "global", blob_path, file_io, size=size, metadata={"UploadedBy": user_oid}
        )
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
            await _knowledge_store().set_tags("global", blob_path, {"status": "Duplicate"})
            job = get_ingestion_job(str(job["_id"])) or job
        else:
            await _knowledge_store().set_tags("global", blob_path, {"status": "Pending"})
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
    jobs = []
    for file in request_files.getlist("file"):

        blob_path = f"{str(team_id)}/{file.filename}"
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
        await _knowledge_store().put(
            "team",
            blob_path,
            file_io,
            size=size,
            metadata={"UploadedBy": str(user_oid)},
            tags={"status": "Pending", "data_groups": data_groups_tag},
        )
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
    blob_path = f"{filename}"
    await _knowledge_store().delete("global", blob_path)
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
    blob_path = f"{tid}/{filename}"
    tag_resp = await _knowledge_store().get_tags("team", blob_path)
    data_groups_id_list = str(tag_resp['data_groups']).split("/")
    await _knowledge_store().delete("team", blob_path)
    ingester = current_app.config[CONFIG_INGESTER]
    for data_group_id in data_groups_id_list:
        await ingester.remove_groups_file(blob_path, str(data_group_id))
    return jsonify({"message": f"File {filename} deleted successfully"}), 200


@bp.get("/list_uploaded")
@authenticated
async def list_uploaded(auth_claims: dict[str, Any]):
    user_oid = auth_claims["oid"]
    files = []
    for stored_object in await _knowledge_store().list("personal", prefix=f"{user_oid}/"):
        files.append([stored_object.key.split("/", 1)[1], stored_object.size])
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
    files = []
    tid = request_json.get("team_id")
    for stored_object in await _knowledge_store().list("team", prefix=f"{tid}/"):
        data_groups_id_list = str(stored_object.tags.get("data_groups", "")).split("/")
        data_groups_list = []
        for data_group_id in filter(None, data_groups_id_list):
            data_group = get_data_group_by_id(data_group_id)
            if data_group:
                data_groups_list.append(data_group["name"])
        files.append([
            stored_object.key.removeprefix(f"{tid}/"),
            stored_object.tags.get("status", ""),
            stored_object.last_modified.isoformat() if stored_object.last_modified else None,
            stored_object.size,
            data_groups_list,
        ])
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
    files = []
    for stored_object in await _knowledge_store().list("global"):
        files.append([
            stored_object.key,
            stored_object.tags.get("status", ""),
            stored_object.last_modified.isoformat() if stored_object.last_modified else None,
            stored_object.size,
        ])
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


def _authorize_web_source_scope(
    auth_claims: dict[str, Any],
    team_id: Any,
    data_group_ids: Any = None,
    *,
    require_data_groups: bool = False,
) -> tuple[dict[str, Any], str | None, list[str]]:
    normalized_team_id = str(team_id or "").strip() or None
    if data_group_ids is None:
        normalized_groups: list[str] = []
    elif not isinstance(data_group_ids, list):
        raise AccessControlError("data_groups_id must be a list", status_code=400)
    else:
        normalized_groups = list(
            dict.fromkeys(
                str(item).strip() for item in data_group_ids if str(item).strip()
            )
        )

    if not normalized_team_id:
        if normalized_groups:
            raise AccessControlError(
                "Data Groups require a Team scope", status_code=400
            )
        return (
            _require_system_permission(auth_claims, "Manage global uploads"),
            None,
            [],
        )

    user, team = _require_team_access(
        auth_claims,
        normalized_team_id,
        permission="Manage team uploads",
    )
    allowed_groups = {str(item) for item in (team.get("data_group_id") or [])}
    if require_data_groups and not normalized_groups:
        raise AccessControlError("Select at least one Data Group", status_code=400)
    if any(
        group_id not in allowed_groups or not get_data_group_by_id(group_id)
        for group_id in normalized_groups
    ):
        raise AccessControlError("A selected Data Group does not belong to this Team")
    return user, normalized_team_id, normalized_groups


def _web_source_from_key(key: str, team_id: str | None = None) -> str:
    relative = key.removeprefix(f"{team_id}/") if team_id else key
    folder = relative.split("/", 1)[0]
    return source_url_from_folder(folder)


async def upload_path(
    data: str,
    blob_name: str,
    metadata: dict[str, str],
    *,
    source_url: str,
    source_id: str,
    content_hash: str,
    retrieved_at: str,
    crawl_depth: int,
    crawl_truncated: bool = False,
    limit_reason: str | None = None,
    gid: str | None = None,
    data_groups_id: list[str] | None = None,
    raise_on_failure: bool = False,
):
    scope = "web_team" if gid else "web_global"
    if gid:
        blob_name = f"{gid}/{blob_name}"
    ingester: UploadUserFileStrategy = current_app.config[CONFIG_INGESTER]
    tags = {
        "source_id": source_id,
        "content_hash": content_hash,
        "retrieved_at": retrieved_at.replace("-", "").replace(":", ""),
        "crawl_depth": str(crawl_depth),
        "crawl_truncated": "true" if crawl_truncated else "false",
        "crawl_limit_reason": str(limit_reason or ""),
        "status": "processing",
    }
    if gid:
        tags["data_groups"] = "/".join(data_groups_id or [])
    delay = 1.0
    for attempt in range(6):
        try:
            encoded = data.encode("utf-8")
            await _knowledge_store().put(
                scope,
                blob_name,
                encoded,
                size=len(encoded),
                metadata=metadata,
                tags=tags,
                content_type="text/plain; charset=utf-8",
            )
            buf = NamedBytesIO(encoded, blob_name)
            folder = os.path.dirname(blob_name)
            folder = f"{folder}{os.sep}" if folder else ""
            acls = (
                {"groups": data_groups_id or [], "oids": []}
                if gid
                else {"oids": []}
            )
            await ingester.add_global_file(
                File(content=buf, acls=acls, url=source_url), folder
            )
            tags["status"] = "indexed"
            await _knowledge_store().set_tags(scope, blob_name, tags)
            return True
        except Exception:
            if attempt == 5:
                current_app.logger.exception("Unable to index approved web source page")
                if raise_on_failure:
                    raise
                return False
            await asyncio.sleep(delay + random.random() * 0.2)
            delay = min(delay * 2, 20)


async def upload_many(
    paths,
    folder,
    user_oid: str,
    gid=None,
    data_groups_id=None,
    crawl_depth: int = 1,
    crawl_truncated: bool = False,
    limit_reason: str | None = None,
):
    sem = asyncio.Semaphore(min(FILES_CONCURRENT, 8))

    async def worker(page: dict[str, str]):
        async with sem:
            blob_name = f"{folder}/{page['storage_name']}"
            ok = await upload_path(
                page["text"],
                blob_name,
                {
                    "UploadedBy": str(user_oid),
                    "SourceUrl": quote(str(page["source_url"]), safe=""),
                    "RetrievedAt": str(page["retrieved_at"]),
                    "ContentHash": str(page["content_hash"]),
                },
                source_url=page["source_url"],
                source_id=folder.removeprefix("source-").split("||", 1)[0],
                content_hash=page["content_hash"],
                retrieved_at=page["retrieved_at"],
                crawl_depth=crawl_depth,
                crawl_truncated=crawl_truncated,
                limit_reason=limit_reason,
                gid=gid,
                data_groups_id=data_groups_id,
            )
            return (f"{gid}/" if gid else "") + blob_name, ok

    return await asyncio.gather(*(worker(page) for page in paths))


def _web_source_scan_retention_hours() -> float:
    try:
        value = float(os.getenv("WEB_SOURCE_SCAN_RETENTION_HOURS", "24"))
    except ValueError as error:
        raise ValueError("WEB_SOURCE_SCAN_RETENTION_HOURS must be numeric") from error
    if not math.isfinite(value) or value < 1 or value > 72:
        raise ValueError("WEB_SOURCE_SCAN_RETENTION_HOURS must be between 1 and 72")
    return value


def _bounded_web_scan_setting(name: str, default: int, maximum: int) -> int:
    try:
        return max(1, min(int(os.getenv(name, str(default))), maximum))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _web_source_scan_limits(profile: Any) -> tuple[str, int | None, int | None]:
    normalized = str(profile or "standard").strip().lower()
    if normalized == "standard":
        return normalized, None, None
    if normalized != "extended":
        raise WebScrapingError("limit_profile must be standard or extended")
    return (
        normalized,
        _bounded_web_scan_setting("WEB_SCRAPE_EXTENDED_MAX_PAGES", 250, 250),
        _bounded_web_scan_setting(
            "WEB_SCRAPE_EXTENDED_MAX_TOTAL_BYTES",
            100 * 1024 * 1024,
            100 * 1024 * 1024,
        ),
    )


def _web_source_scan_scope(scan: dict[str, Any]) -> str:
    return "web_team" if str(scan.get("team_id") or "") else "web_global"


def _web_source_stage_prefix(scan_id: str, team_id: str | None) -> str:
    base = f"__staging__/{scan_id}"
    return f"{team_id}/{base}" if team_id else base


def _serialize_web_source_scan(scan: dict[str, Any]) -> dict[str, Any]:
    result = scan.get("result") or {}
    pages = scan.get("pages") or []
    progress_items = scan.get("page_progress") or []
    progress_by_url = {
        str(item.get("url") or ""): item
        for item in progress_items
        if str(item.get("url") or "")
    }
    selected_total = sum(
        1 for item in progress_items if item.get("status") != "skipped"
    )
    indexed_pages = sum(
        1 for item in progress_items if item.get("status") == "indexed"
    )
    failed_pages = sum(
        1 for item in progress_items if item.get("status") == "failed"
    )
    active_pages = sum(
        1 for item in progress_items if item.get("status") == "indexing"
    )
    completed_pages = indexed_pages + failed_pages

    def timestamp(name: str) -> str | None:
        value = scan.get(name)
        return value.isoformat() if value else None

    return {
        "scan_id": str(scan.get("_id") or ""),
        "status": str(scan.get("status") or "ready"),
        "source_url": str(scan.get("source_url") or ""),
        "crawl_depth": int(scan.get("crawl_depth") or 0),
        "limit_profile": str(scan.get("limit_profile") or "standard"),
        "fetch_mode": str(scan.get("fetch_mode") or "auto"),
        "browser_pages": int(result.get("browser_pages") or 0),
        "expires_at": timestamp("expires_at"),
        "created_at": timestamp("created_at"),
        "started_at": timestamp("started_at"),
        "completed_at": timestamp("completed_at"),
        "attempt": int(scan.get("attempt") or 0),
        "last_error": str(scan.get("last_error") or ""),
        "pages_found": len(pages),
        "pages_selected": selected_total,
        "pages_completed": completed_pages,
        "pages_indexed": indexed_pages,
        "pages_failed": failed_pages,
        "pages_active": active_pages,
        "progress_percent": (
            int((completed_pages / selected_total) * 100) if selected_total else 0
        ),
        "bytes_found": int(result.get("bytes_indexed") or 0),
        "pages_skipped": int(result.get("pages_skipped") or 0),
        "truncated": bool(result.get("truncated")),
        "limit_reason": result.get("limit_reason"),
        "issues": list(result.get("issues") or [])[:50],
        "pages": [
            {
                "url": str(page.get("source_url") or ""),
                "title": str(page.get("title") or ""),
                "size": int(page.get("size") or 0),
                "status": str(
                    progress_by_url.get(str(page.get("source_url") or ""), {}).get("status")
                    or "pending"
                ),
                "attempt": int(
                    progress_by_url.get(str(page.get("source_url") or ""), {}).get("attempt")
                    or 0
                ),
                "error": progress_by_url.get(
                    str(page.get("source_url") or ""), {}
                ).get("error"),
            }
            for page in pages
        ],
    }


async def _delete_web_source_scan_stage(scan: dict[str, Any]) -> bool:
    scope = _web_source_scan_scope(scan)
    complete = True
    for page in scan.get("pages") or []:
        key = str(page.get("staging_key") or "")
        if not key:
            continue
        try:
            await _knowledge_store().delete(scope, key)
        except KnowledgeObjectNotFound:
            continue
        except Exception:
            complete = False
            current_app.logger.exception("Unable to delete staged web source object")
    return complete


def _schedule_web_source_index_job(scan_id: str) -> None:
    task = asyncio.create_task(_run_web_source_index_job(scan_id))
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    WEB_SOURCE_INDEX_TASKS.add(task)
    task.add_done_callback(WEB_SOURCE_INDEX_TASKS.discard)


async def _heartbeat_web_source_index_job(scan_id: str) -> None:
    while True:
        await asyncio.sleep(30)
        owns_job = await asyncio.to_thread(
            heartbeat_web_source_scan,
            scan_id,
            WEB_SOURCE_INDEX_WORKER_ID,
        )
        if not owns_job:
            return


async def _run_web_source_index_job(scan_id: str) -> None:
    claimed = await asyncio.to_thread(
        claim_web_source_scan,
        scan_id,
        WEB_SOURCE_INDEX_WORKER_ID,
    )
    if not claimed:
        return
    heartbeat_task = asyncio.create_task(_heartbeat_web_source_index_job(scan_id))
    try:
        scope = _web_source_scan_scope(claimed)
        team_id = str(claimed.get("team_id") or "") or None
        data_group_ids = list(claimed.get("data_group_ids") or [])
        result = claimed.get("result") or {}
        folder = source_folder(str(claimed["source_url"]))
        progress = claimed.get("page_progress") or []
        pages = claimed.get("pages") or []
        if len(progress) != len(pages):
            raise WebScrapingError("The indexing job manifest is incomplete")

        semaphore = asyncio.Semaphore(min(FILES_CONCURRENT, 4))

        async def process_page(index: int, page: dict[str, Any]) -> None:
            page_state = progress[index]
            if page_state.get("status") in {"indexed", "skipped"}:
                return
            async with semaphore:
                owns_job = await asyncio.to_thread(
                    update_web_source_page,
                    scan_id,
                    WEB_SOURCE_INDEX_WORKER_ID,
                    index,
                    "indexing",
                )
                if not owns_job:
                    raise RuntimeError("Web source indexing lease was lost")
                try:
                    staged = await _knowledge_store().read(
                        scope, str(page["staging_key"])
                    )
                    if hashlib.sha256(staged.data).hexdigest() != str(page["staged_hash"]):
                        raise WebScrapingError(
                            "Staged web source content failed integrity verification"
                        )
                    upload_page = {
                        "storage_name": str(page["storage_name"]),
                        "text": staged.data.decode("utf-8"),
                        "source_url": str(page["source_url"]),
                        "title": str(page.get("title") or ""),
                        "content_hash": str(page["content_hash"]),
                        "retrieved_at": str(page["retrieved_at"]),
                    }
                    storage_key = (f"{team_id}/" if team_id else "") + (
                        f"{folder}/{upload_page['storage_name']}"
                    )
                    indexed = await upload_path(
                        upload_page["text"],
                        f"{folder}/{upload_page['storage_name']}",
                        {
                            "UploadedBy": str(claimed.get("created_by") or ""),
                            "SourceUrl": quote(upload_page["source_url"], safe=""),
                            "RetrievedAt": upload_page["retrieved_at"],
                            "ContentHash": upload_page["content_hash"],
                        },
                        source_url=upload_page["source_url"],
                        source_id=folder.removeprefix("source-").split("||", 1)[0],
                        content_hash=upload_page["content_hash"],
                        retrieved_at=upload_page["retrieved_at"],
                        crawl_depth=int(claimed.get("crawl_depth") or 0),
                        crawl_truncated=bool(result.get("truncated")),
                        limit_reason=str(result.get("limit_reason") or "") or None,
                        gid=team_id,
                        data_groups_id=data_group_ids,
                        raise_on_failure=True,
                    )
                    if not indexed:
                        raise RuntimeError("Page indexing failed after retries")
                    await asyncio.to_thread(
                        update_web_source_page,
                        scan_id,
                        WEB_SOURCE_INDEX_WORKER_ID,
                        index,
                        "indexed",
                        storage_key=storage_key,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    await asyncio.to_thread(
                        update_web_source_page,
                        scan_id,
                        WEB_SOURCE_INDEX_WORKER_ID,
                        index,
                        "failed",
                        error=error,
                    )
                    current_app.logger.warning(
                        "Web source page indexing failed: scan=%s url=%s",
                        scan_id,
                        str(page.get("source_url") or ""),
                    )

        await asyncio.gather(*(
            process_page(index, page) for index, page in enumerate(pages)
        ))
        current = await asyncio.to_thread(get_web_source_scan, scan_id)
        if not current or str(current.get("worker_id") or "") != WEB_SOURCE_INDEX_WORKER_ID:
            return
        page_progress = current.get("page_progress") or []
        failed = [item for item in page_progress if item.get("status") == "failed"]
        unfinished = [
            item for item in page_progress
            if item.get("status") not in {"indexed", "failed", "skipped"}
        ]
        if failed or unfinished:
            await asyncio.to_thread(
                complete_web_source_scan,
                scan_id,
                WEB_SOURCE_INDEX_WORKER_ID,
                "failed",
                error=f"{len(failed) + len(unfinished)} page(s) could not be indexed",
            )
            return

        encoded_legacy_folder = legacy_source_folder(str(claimed["source_url"]))
        legacy_folder = str(claimed["source_url"]).replace("/", "_")
        all_existing = await _knowledge_store().list(
            scope, prefix=f"{team_id}/" if team_id else ""
        )
        previous = {
            item.key
            for item in all_existing
            if (item.key.removeprefix(f"{team_id}/") if team_id else item.key)
            .split("/", 1)[0]
            in {folder, encoded_legacy_folder, legacy_folder}
        }
        selected_keys = {
            str(item.get("storage_key") or "")
            for item in page_progress
            if item.get("status") == "indexed" and item.get("storage_key")
        }
        stale = sorted(previous - selected_keys)
        if stale:
            await delete_many(stale, team_id)
        if not await _delete_web_source_scan_stage(current):
            raise RuntimeError("Indexed pages are ready, but staging cleanup failed")
        await asyncio.to_thread(
            complete_web_source_scan,
            scan_id,
            WEB_SOURCE_INDEX_WORKER_ID,
            "indexed",
        )
    except asyncio.CancelledError:
        await asyncio.to_thread(
            release_web_source_scan,
            scan_id,
            WEB_SOURCE_INDEX_WORKER_ID,
        )
        raise
    except Exception as error:
        current_app.logger.exception("Web source indexing job failed: %s", scan_id)
        await asyncio.to_thread(
            complete_web_source_scan,
            scan_id,
            WEB_SOURCE_INDEX_WORKER_ID,
            "failed",
            error=error,
        )
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def _recover_web_source_index_jobs(interval_seconds: float) -> None:
    while True:
        try:
            jobs = await asyncio.to_thread(list_recoverable_web_source_scans)
            for job in jobs:
                _schedule_web_source_index_job(str(job["_id"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            current_app.logger.exception("Unable to recover Web Source indexing jobs")
        await asyncio.sleep(interval_seconds)


async def _cleanup_expired_web_source_scans_once() -> int:
    expired = await asyncio.to_thread(list_expired_web_source_scans)
    removed = 0
    for candidate in expired:
        scan = await asyncio.to_thread(
            claim_web_source_scan_for_cleanup,
            str(candidate.get("_id") or ""),
        )
        if not scan:
            continue
        if await _delete_web_source_scan_stage(scan):
            await asyncio.to_thread(delete_web_source_scan, str(scan["_id"]))
            removed += 1
        else:
            await asyncio.to_thread(
                mark_web_source_scan_failed,
                str(scan["_id"]),
                "staging_cleanup",
            )
    return removed


async def _run_web_source_scan_cleanup(interval_seconds: float) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            removed = await _cleanup_expired_web_source_scans_once()
            if removed:
                current_app.logger.info("Expired web source scans removed: count=%d", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            current_app.logger.exception("Unable to clean up expired web source scans")


@bp.post("/web-source-scans")
@authenticated
async def create_web_source_scan_route(auth_claims: dict[str, Any]):
    staged_scan: dict[str, Any] | None = None
    try:
        data = await request.get_json()
        if not isinstance(data, dict):
            raise WebScrapingError("Request body must be JSON")
        start_url = str(data.get("url") or "").strip()
        raw_crawl_depth = data.get("crawl_depth", 1)
        if isinstance(raw_crawl_depth, bool) or str(raw_crawl_depth) not in {"0", "1", "2"}:
            raise WebScrapingError("crawl_depth must be 0, 1, or 2")
        crawl_depth = int(raw_crawl_depth)
        fetch_mode = str(data.get("fetch_mode") or "auto").strip().lower()
        if fetch_mode not in {"auto", "http", "browser"}:
            raise WebScrapingError("fetch_mode must be auto, http, or browser")
        limit_profile, max_pages, max_total_bytes = _web_source_scan_limits(
            data.get("limit_profile")
        )
        user, team_id, data_group_ids = _authorize_web_source_scope(
            auth_claims,
            data.get("team_id"),
            data.get("data_groups_id"),
            require_data_groups=bool(data.get("team_id")),
        )
        result, pages = await asyncio.to_thread(
            run_scraping_job,
            start_url,
            max_depth=crawl_depth,
            max_pages=max_pages,
            max_total_bytes=max_total_bytes,
            fetch_mode=fetch_mode,
        )
        scan_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=_web_source_scan_retention_hours()
        )
        scope = "web_team" if team_id else "web_global"
        prefix = _web_source_stage_prefix(scan_id, team_id)
        staged_pages: list[dict[str, Any]] = []
        staged_scan = {"team_id": team_id, "pages": staged_pages}
        for page in pages:
            encoded = str(page["text"]).encode("utf-8")
            staging_key = f"{prefix}/{page['storage_name']}"
            await _knowledge_store().put(
                scope,
                staging_key,
                encoded,
                size=len(encoded),
                metadata={
                    "SourceUrl": quote(str(page["source_url"]), safe=""),
                    "RetrievedAt": str(page["retrieved_at"]),
                    "ContentHash": str(page["content_hash"]),
                },
                tags={
                    "status": "staged",
                    "scan_id": scan_id,
                    "expires_at": expires_at.strftime("%Y%m%dT%H%M%SZ"),
                },
                content_type="text/plain; charset=utf-8",
            )
            staged_pages.append({
                "staging_key": staging_key,
                "storage_name": str(page["storage_name"]),
                "source_url": str(page["source_url"]),
                "title": str(page.get("title") or ""),
                "content_hash": str(page["content_hash"]),
                "staged_hash": hashlib.sha256(encoded).hexdigest(),
                "retrieved_at": str(page["retrieved_at"]),
                "size": len(encoded),
            })
        staged_scan.update({
            "_id": scan_id,
            "created_by": str(user.get("_id") or auth_claims.get("oid") or ""),
            "data_group_ids": data_group_ids,
            "source_url": str(result["source_url"]),
            "crawl_depth": crawl_depth,
            "limit_profile": limit_profile,
            "fetch_mode": fetch_mode,
            "expires_at": expires_at,
            "result": result,
        })
        scan = await asyncio.to_thread(create_web_source_scan, staged_scan)
        return jsonify(_serialize_web_source_scan(scan)), 201
    except AccessControlError as error:
        return error_response(error, "/web-source-scans")
    except WebScrapingError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except Exception:
        current_app.logger.exception("Unable to create web source scan")
        if staged_scan:
            await _delete_web_source_scan_stage(staged_scan)
        return jsonify({"status": "error", "message": "The web source could not be scanned"}), 500


@bp.get("/web-source-scans")
@authenticated
async def list_web_source_scan_jobs_route(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "").strip() or None
    try:
        _authorize_web_source_scope(auth_claims, team_id)
        try:
            limit = int(request.args.get("limit") or 10)
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
        scans = await asyncio.to_thread(
            list_web_source_scans,
            team_id=team_id,
            limit=limit,
        )
        return jsonify({"jobs": [_serialize_web_source_scan(scan) for scan in scans]})
    except AccessControlError as error:
        return error_response(error, "/web-source-scans")


@bp.get("/web-source-scans/<scan_id>")
@authenticated
async def get_web_source_scan_route(auth_claims: dict[str, Any], scan_id: str):
    scan = await asyncio.to_thread(get_web_source_scan, scan_id)
    if not scan:
        return jsonify({"error": "Web source indexing job not found"}), 404
    try:
        _authorize_web_source_scope(
            auth_claims,
            scan.get("team_id"),
            scan.get("data_group_ids"),
        )
    except AccessControlError as error:
        return error_response(error, "/web-source-scans/status")
    return jsonify(_serialize_web_source_scan(scan))


@bp.post("/web-source-scans/<scan_id>/confirm")
@authenticated
async def confirm_web_source_scan_route(auth_claims: dict[str, Any], scan_id: str):
    scan = await asyncio.to_thread(get_web_source_scan, scan_id)
    if not scan:
        return jsonify({"error": "Web source scan not found"}), 404
    data = await request.get_json(silent=True) or {}
    selected_urls_value = data.get("selected_urls")
    if selected_urls_value is not None and not isinstance(selected_urls_value, list):
        return jsonify({"error": "selected_urls must be a list"}), 400
    selected_urls = (
        list(dict.fromkeys(
            value.strip()
            for value in selected_urls_value
            if isinstance(value, str) and value.strip()
        ))
        if selected_urls_value is not None
        else [
            str(page.get("source_url") or "")
            for page in scan.get("pages") or []
            if str(page.get("source_url") or "")
        ]
    )
    if not selected_urls:
        return jsonify({"error": "Select at least one page to index"}), 400
    available_urls = {
        str(page.get("source_url") or "")
        for page in scan.get("pages") or []
    }
    if any(source_url not in available_urls for source_url in selected_urls):
        return jsonify({
            "error": "A selected page is not part of this scan manifest"
        }), 400
    try:
        user, _team_id, _data_group_ids = _authorize_web_source_scope(
            auth_claims,
            scan.get("team_id"),
            scan.get("data_group_ids"),
            require_data_groups=bool(scan.get("team_id")),
        )
    except AccessControlError as error:
        return error_response(error, "/web-source-scans/confirm")
    queued = await asyncio.to_thread(
        queue_web_source_scan,
        scan_id,
        selected_urls,
        requested_by=str(user.get("_id") or auth_claims.get("oid") or ""),
    )
    if not queued:
        return jsonify({
            "error": "The scan expired or is no longer available for indexing"
        }), 409
    _schedule_web_source_index_job(scan_id)
    response = _serialize_web_source_scan(queued)
    response["message"] = "Web source indexing started in the background."
    return jsonify(response), 202


@bp.post("/web-source-scans/<scan_id>/retry")
@authenticated
async def retry_web_source_scan_route(auth_claims: dict[str, Any], scan_id: str):
    scan = await asyncio.to_thread(get_web_source_scan, scan_id)
    if not scan:
        return jsonify({"error": "Web source indexing job not found"}), 404
    try:
        _authorize_web_source_scope(
            auth_claims,
            scan.get("team_id"),
            scan.get("data_group_ids"),
            require_data_groups=bool(scan.get("team_id")),
        )
    except AccessControlError as error:
        return error_response(error, "/web-source-scans/retry")
    queued = await asyncio.to_thread(retry_web_source_scan, scan_id)
    if not queued:
        return jsonify({
            "error": "Only an unexpired failed indexing job can be retried"
        }), 409
    _schedule_web_source_index_job(scan_id)
    response = _serialize_web_source_scan(queued)
    response["message"] = "Failed pages were queued for retry."
    return jsonify(response), 202


@bp.delete("/web-source-scans/<scan_id>")
@authenticated
async def cancel_web_source_scan_route(auth_claims: dict[str, Any], scan_id: str):
    scan = await asyncio.to_thread(get_web_source_scan, scan_id)
    if not scan:
        return "", 204
    try:
        _authorize_web_source_scope(
            auth_claims,
            scan.get("team_id"),
            scan.get("data_group_ids"),
        )
    except AccessControlError as error:
        return error_response(error, "/web-source-scans/cancel")
    claimed = await asyncio.to_thread(claim_web_source_scan_for_cleanup, scan_id)
    if not claimed:
        return jsonify({"error": "The scan is currently being indexed"}), 409
    if await _delete_web_source_scan_stage(claimed):
        await asyncio.to_thread(delete_web_source_scan, scan_id)
        return "", 204
    await asyncio.to_thread(mark_web_source_scan_failed, scan_id, "staging_cleanup")
    return jsonify({"error": "Scan cancellation is pending storage cleanup"}), 202


@bp.post("/scrape")
@authenticated
async def scrape_website(auth_claims: dict[str, Any]):
    del auth_claims
    return jsonify({
        "status": "error",
        "message": (
            "Direct web-source indexing is disabled. "
            "Use Scan & Verify, then Confirm Index."
        ),
    }), 410


@bp.get("/list_web_contents")
@authenticated
async def list_web_contents(auth_claims: dict[str, Any]):
    team_id = str(request.args.get("team_id") or "").strip() or None
    try:
        _authorize_web_source_scope(auth_claims, team_id)
    except AccessControlError as error:
        return error_response(error, "/list_web_contents")
    scope = "web_team" if team_id else "web_global"
    entries: dict[str, dict[str, Any]] = {}
    for stored_object in await _knowledge_store().list(
        scope, prefix=f"{team_id}/" if team_id else ""
    ):
        if stored_object.tags.get("status") not in {None, "", "indexed"}:
            continue
        source_url = _web_source_from_key(stored_object.key, team_id)
        entry = entries.setdefault(
            source_url,
            {
                "groups": set(),
                "pages": 0,
                "last_refreshed_at": None,
                "crawl_depth": 1,
                "truncated": False,
                "limit_reason": None,
            },
        )
        stored_depth = str(stored_object.tags.get("crawl_depth", "1"))
        if stored_depth in {"0", "1", "2"}:
            entry["crawl_depth"] = int(stored_depth)
        if str(stored_object.tags.get("crawl_truncated", "false")).lower() == "true":
            entry["truncated"] = True
            stored_reason = str(stored_object.tags.get("crawl_limit_reason", ""))
            entry["limit_reason"] = stored_reason or None
        entry["pages"] += 1
        modified = (
            stored_object.last_modified.isoformat()
            if stored_object.last_modified
            else None
        )
        if modified and (
            entry["last_refreshed_at"] is None
            or modified > entry["last_refreshed_at"]
        ):
            entry["last_refreshed_at"] = modified
        if team_id:
            for group_id in filter(
                None, str(stored_object.tags.get("data_groups", "")).split("/")
            ):
                data_group = get_data_group_by_id(group_id)
                if data_group:
                    entry["groups"].add(str(data_group["name"]))
    result = [
        [
            url,
            sorted(entry["groups"]),
            entry["last_refreshed_at"],
            entry["pages"],
            entry["crawl_depth"],
            entry["truncated"],
            entry["limit_reason"],
        ]
        for url, entry in sorted(entries.items())
    ]
    return jsonify(result), 200


async def delete_path(data: str, gid=None):
    scope = "web_team" if gid else "web_global"
    ingester = current_app.config[CONFIG_INGESTER]
    delay = 1.0
    for attempt in range(6):
        try:
            if gid:
                tags = await _knowledge_store().get_tags(scope, data)
                data_groups = list(filter(None, tags.get("data_groups", "").split("/")))
                await _knowledge_store().delete(scope, data)
                for data_group in data_groups:
                    await ingester.remove_groups_file(data, data_group)
            else:
                await _knowledge_store().delete(scope, data)
                await ingester.remove_global_file(data)
            return True
        except KnowledgeObjectNotFound:
            return True
        except Exception:
            if attempt == 5:
                current_app.logger.exception(
                    "Unable to delete approved web source page"
                )
                return False
            await asyncio.sleep(delay + random.random() * 0.2)
            delay = min(delay * 2, 20)


async def delete_many(paths, gid=None):
    sem = asyncio.Semaphore(min(FILES_CONCURRENT, 8))

    async def worker(path):
        async with sem:
            return path, await delete_path(path, gid)

    return await asyncio.gather(*(worker(path) for path in paths))


@bp.post("/delete_web_content")
@authenticated
async def delete_web_content(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    if not isinstance(request_json, dict):
        return jsonify({"error": "Request body must be JSON"}), 400
    team_id = str(request_json.get("team_id") or "").strip() or None
    try:
        _authorize_web_source_scope(auth_claims, team_id)
        source_url = normalize_stored_source_url(str(request_json.get("url") or ""))
    except AccessControlError as error:
        return error_response(error, "/delete_web_content")
    except WebScrapingError as error:
        return jsonify({"error": str(error)}), 400
    scope = "web_team" if team_id else "web_global"
    new_folder = source_folder(source_url)
    encoded_legacy_folder = legacy_source_folder(source_url)
    legacy_folder = source_url.replace("/", "_")
    files = []
    for stored_object in await _knowledge_store().list(scope, prefix=f"{team_id}/" if team_id else ""):
        relative = stored_object.key.removeprefix(f"{team_id}/") if team_id else stored_object.key
        if relative.split("/", 1)[0] in {
            new_folder,
            encoded_legacy_folder,
            legacy_folder,
        }:
            files.append(stored_object.key)
    if not files:
        return jsonify({"error": "Approved web source not found"}), 404
    deleted = await delete_many(files, team_id)
    if any(not ok for _, ok in deleted):
        return jsonify({"error": "The approved web source could not be fully deleted"}), 500
    return jsonify({"message": f"Approved web source {source_url} deleted successfully", "deleted_pages": len(files)}), 200


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


@bp.get("/usage-analytics")
@authenticated
async def usage_analytics(auth_claims: dict[str, Any]):
    try:
        scope = str(request.args.get("scope") or "system").strip().lower()
        team_id = str(request.args.get("team_id") or "").strip()
        requested_user_id = str(request.args.get("user_id") or "").strip()
        actor = _application_user_for_claims(auth_claims)
        if not actor or actor.get("active", True) is not True:
            raise AccessControlError("The signed-in application user is unavailable")

        query: dict[str, Any] = {"delete_at": None}
        if scope == "system":
            _require_system_permission(auth_claims, "View system dashboard")
            if team_id:
                query["group._id"] = team_id
            if requested_user_id:
                query["user._id"] = requested_user_id
        elif scope == "team":
            if not team_id:
                raise AccessControlError("team_id is required for team scope", status_code=400)
            _require_team_access(auth_claims, team_id, permission="View team dashboard")
            query["group._id"] = team_id
            if requested_user_id:
                team = get_team_by_id(team_id) or {}
                if requested_user_id not in {str(item) for item in (team.get("user_id") or [])}:
                    raise AccessControlError("The selected user is not a member of this team", status_code=400)
                query["user._id"] = requested_user_id
        elif scope == "personal":
            query["user._id"] = str(actor.get("_id") or "")
        else:
            raise AccessControlError("scope must be system, team or personal", status_code=400)

        now = datetime.now(timezone.utc)
        default_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)

        def parse_date(value: str, fallback: datetime, *, end: bool = False) -> datetime:
            if not value:
                return fallback
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise AccessControlError("from and to must be ISO-8601 dates", status_code=400) from error
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if len(value) == 10 and end:
                parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            return parsed.astimezone(timezone.utc)

        start = parse_date(str(request.args.get("from") or ""), default_start)
        end = parse_date(str(request.args.get("to") or ""), now, end=True)
        if end < start or (end - start).days > 366:
            raise AccessControlError("The reporting period must be between 0 and 366 days", status_code=400)
        query["create_at"] = {"$gte": start, "$lte": end}

        bucket = str(request.args.get("bucket") or "day").strip().lower()
        if bucket not in {"day", "week", "month"}:
            raise AccessControlError("bucket must be day, week or month", status_code=400)
        data = await asyncio.to_thread(
            get_usage_analytics,
            query,
            bucket=bucket,
            agent_id=str(request.args.get("agent_id") or "").strip(),
            provider=str(request.args.get("provider") or "").strip(),
            model=str(request.args.get("model") or "").strip(),
            profile_id=str(request.args.get("profile_id") or "").strip(),
            file_type=str(request.args.get("file_type") or "").strip(),
            document_scope=str(request.args.get("document_scope") or "").strip(),
        )
        data["scope"] = scope
        data["period"] = {"from": start.isoformat(), "to": end.isoformat(), "bucket": bucket}
        return jsonify(data), 200
    except Exception as error:
        return error_response(error, "/usage-analytics")


@bp.get("/get_usage")
@authenticated
async def get_usage(auth_claims: dict[str, Any]):
    """Deprecated raw endpoint retained temporarily for compatible clients."""
    try:
        _require_system_permission(auth_claims, "View system dashboard")
        return jsonify({"error": "Use /usage-analytics"}), 410
    except Exception as error:
        return error_response(error, "/get_usage")


@bp.get("/get_docintel_usage")
@authenticated
async def get_docintel_usage(auth_claims: dict[str, Any]):
    try:
        _require_system_permission(auth_claims, "View system dashboard")
        return jsonify({"error": "Use /usage-analytics"}), 410
    except Exception as error:
        return error_response(error, "/get_docintel_usage")


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
        data = dict(limit_confs[0])
        data["max_upload_size_bytes"] = current_app.config["MAX_CONTENT_LENGTH"]
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


@bp.post("/effective-access")
@authenticated
async def effective_access(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        if not isinstance(body, dict):
            raise AccessControlError("request must be json", status_code=400)
        team_id = str(body.get("team_id") or "").strip()
        if not team_id:
            raise AccessControlError("team_id is required", status_code=400)
        access = _effective_access_for_request(
            auth_claims,
            team_id=team_id,
            data_group_ids=body.get("data_groups_id"),
            selected_scopes=body.get("selected_scopes"),
            agent_id=body.get("agent_id"),
        )
        return jsonify(access.serialize()), 200
    except Exception as error:
        return error_response(error, "/effective-access")


@bp.get("/check_user_login")
@authenticated
async def check_user_login(auth_claims: dict[str, Any]):
    try:
        user = _application_user_for_claims(auth_claims)
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
            return jsonify({"user": _serialize_user_auth(user, has_oidc_identity=auth_claims.get("auth_provider") == "oidc", has_saml_identity=auth_claims.get("auth_provider") == "saml"), "teams": result_teams, "sys_permissions": sys_pers}), 200
        else:
            return jsonify({"error": "Can't find user"}), 404
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.get("/auth/profile")
@authenticated
async def get_own_profile(auth_claims: dict[str, Any]):
    user = _application_user_for_claims(auth_claims)
    if not user or user.get("active", True) is not True:
        return jsonify({"error": "The application user is unavailable"}), 404
    return jsonify({"user": _serialize_user_auth(user, has_oidc_identity=auth_claims.get("auth_provider") == "oidc", has_saml_identity=auth_claims.get("auth_provider") == "saml")}), 200


@bp.put("/auth/profile")
@authenticated
async def update_own_profile(auth_claims: dict[str, Any]):
    try:
        user = _application_user_for_claims(auth_claims)
        if not user or user.get("active", True) is not True:
            raise AccessControlError("The application user is unavailable", status_code=404)
        profile = _normalize_self_profile(await request.get_json())
        update_user(
            str(user["_id"]),
            email=profile["email"],
            first_name=profile["first_name"],
            last_name=profile["last_name"],
            tel=profile["tel"],
        )
        updated = get_user_by_id(str(user["_id"]))
        return jsonify({"user": _serialize_user_auth(updated or user, has_oidc_identity=auth_claims.get("auth_provider") == "oidc", has_saml_identity=auth_claims.get("auth_provider") == "saml")}), 200
    except Exception as error:
        return error_response(error, "/auth/profile")


@bp.post("/create_team")
@authenticated
async def create_team(auth_claims: dict[str, Any]):
    try:
        actor = _require_system_permission(auth_claims, "Manage teams")
        body = await request.get_json()
        team_name = body.get("team_name", None)
        if team_name:
            normalized_team_name = str(team_name).strip()
            agent_config = {"temperature": 0.2, "seed": None,
                            "min_search_score": 0, "max_search_results": 2, "max_tokens": 1024,
                            "llm_profile_id": DEFAULT_LLM_PROFILE_ID}
            default_prompt = {
                "role": "",
                "task": "",
                "detail_context": "",
                "output_format": "",
                "constraints": "",
            }
            result, agent_id = insert_agent("default", default_prompt, agent_config)
            result, data_group_id = insert_data_group("default", [])
            team_result = insert_team(
                normalized_team_name,
                [data_group_id],
                [agent_id],
                [str(actor["_id"])],
                [],
            )
        else:
            raise ValueError("Team name is required")
        return jsonify(
            {
                "success": f"Create team {normalized_team_name} success",
                "team": {
                    "_id": str(team_result.inserted_id),
                    "name": normalized_team_name,
                    "permissions": [],
                },
            }
        ), 200
    except Exception as error_txt:
        return error_response(error_txt, "/create_team")


@bp.post("/edit_team_name")
@authenticated
async def edit_team_name(auth_claims: dict[str, Any]):
    try:
        _require_system_permission(auth_claims, "Manage teams")
        body = await request.get_json()
        team_id = body.get("team_id", None)
        team_name = body.get("team_name", None)
        if team_name and team_id:
            update_team(team_id=team_id, name=team_name)
        else:
            raise ValueError("Team ID and Team name is required")
        return jsonify({"success": f"Edit team name success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/edit_team_name")


@bp.get("/get_all_teams")
@authenticated
async def get_all_teams_function(auth_claims: dict[str, Any]):
    try:
        _require_system_permission(auth_claims, "Manage teams")
        allteam = get_all_teams()
        return jsonify({"result": allteam}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_all_teams")


@bp.post("/get_team_detail")
@authenticated
async def get_team_detail(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        _, team_data = _require_team_access(auth_claims, str(team_id or ""))
        user_list, agent_list, data_group_list = [], [], []
        for user_id in team_data.get("user_id"):
            user_list.append(get_user_by_id(str(user_id)))
        for agent_id in team_data.get("agent_id"):
            agent = get_agent_by_id(str(agent_id))
            if is_active_agent(agent):
                agent_list.append(agent)
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
        return error_response(error_txt, "/get_team_detail")


@bp.post("/get_team_users")
@authenticated
async def get_team_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        _, team_data = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team permissions"
        )
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
        return error_response(error_txt, "/get_team_users")


@bp.post("/insert_user")
@authenticated
async def insert_user_function(auth_claims: dict[str, Any]):
    try:
        _require_system_permission(auth_claims, "Manage users")
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
        return error_response(error_txt, "/insert_user")


@bp.post("/delete_user")
@authenticated
async def delete_user(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        user_id = body.get("user_id", None)
        _require_user_management_target(auth_claims, str(user_id or ""), destructive=True)
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
        return error_response(error_txt, "/delete_user")


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
        target = _require_user_management_target(
            auth_claims,
            str(user_id or ""),
            destructive=active is False,
        )[1]
        if target.get("is_sys_admin") is True and active is False:
            raise AccessControlError("System administrator accounts cannot be deactivated from User Management")
        update_user(user_id, email, ad_email, first_name,
                    last_name, employee_id, tel, active)
        return jsonify({"success": f"Update user success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/update_user")


@bp.post("/get_users_by_team_id")
@authenticated
async def get_users_by_team_id(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        _, team = _require_team_access(auth_claims, str(team_id or ""))
        waiting_approve = team.get("waiting_approve") or []
        user_list = []
        for user_id in team.get("user_id") or []:
            user = get_user_by_id(str(user_id))
            if user:
                user_list.append(user)
        return jsonify({"users": user_list, "waiting_approve": waiting_approve}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_users_by_team_id")


@bp.get("/teams/<team_id>/available-users")
@authenticated
async def get_available_team_users(auth_claims: dict[str, Any], team_id: str):
    """List active non-admin users that may be added to the selected Team."""

    try:
        _, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team users"
        )
        member_ids = {str(item) for item in (team.get("user_id") or [])}
        users = [
            user
            for user in get_all_user_by_is_sys_admin(False)
            if user.get("active", True) is True
            and str(user.get("_id") or "") not in member_ids
        ]
        local_identities = list_local_identities_by_user_ids(
            [str(user.get("_id") or "") for user in users]
        )
        auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
        federated_types = (
            federated_identity_types_by_user_ids([str(user.get("_id") or "") for user in users])
            if auth_helper.oidc_authentication_enabled or auth_helper.saml_authentication_enabled
            else {}
        )
        result = []
        for user in users:
            user_id = str(user.get("_id") or "")
            serialized = _serialize_user_auth(
                user,
                local_identities.get(user_id),
                has_oidc_identity="oidc" in federated_types.get(user_id, set()),
                has_saml_identity="saml" in federated_types.get(user_id, set()),
            )
            result.append(
                {
                    field: serialized.get(field)
                    for field in (
                        "_id",
                        "active",
                        "ad_email",
                        "email",
                        "employee_id",
                        "first_name",
                        "last_name",
                        "tel",
                        "local_username",
                        "auth_providers",
                    )
                }
            )
        return jsonify({"users": result}), 200
    except Exception as error:
        return error_response(error, "/teams/<team_id>/available-users")


@bp.get("/get_all_users")
@authenticated
async def get_all_users_function(auth_claims: dict[str, Any]):
    try:
        _require_system_permission(auth_claims, "Manage users")
        allusers = get_all_users()
        local_identities = list_local_identities_by_user_ids(
            [str(user.get("_id") or "") for user in allusers]
        )
        auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
        federated_types = (
            federated_identity_types_by_user_ids([str(user.get("_id") or "") for user in allusers])
            if auth_helper.oidc_authentication_enabled or auth_helper.saml_authentication_enabled
            else {}
        )
        for user in allusers:
            user_id = str(user.get("_id") or "")
            identity = local_identities.get(user_id)
            user.update(
                _serialize_user_auth(
                    user,
                    identity,
                    has_oidc_identity="oidc" in federated_types.get(user_id, set()),
                    has_saml_identity="saml" in federated_types.get(user_id, set()),
                )
            )
        return jsonify({"result": allusers}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_all_users")


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
        _, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team users"
        )
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
        return error_response(error_txt, "/approve_users")


@bp.post("/reject_users")
@authenticated
async def reject_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        users = body.get("users", None)
        # users.pop('__temp_id')
        _, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team users"
        )
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
        return error_response(error_txt, "/reject_users")


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
            _, team = _require_team_access(
                auth_claims, str(team_id), permission="Manage team users"
            )
            user_id_list = team.get("user_id")
            if user_id not in user_id_list:
                raise AccessControlError("User is not a member of this team", status_code=404)
            user_id_list.remove(user_id)
            users_per = get_user_permission_by_user_team_id(user_id, team_id)
            for user_per in users_per:
                delete_user_permission_by_id(user_per["_id"])
            update_team(team_id=team_id, user_id=user_id_list)
        else:
            raise ValueError("Team ID and User ID is required")
        return jsonify({"success": f"Delete user in team success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/delete_team_user")


@bp.post("/insert_team_users")
@authenticated
async def insert_team_users(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        user_id = body.get("user_id", None)
        if user_id and team_id:
            _, team = _require_team_access(
                auth_claims, str(team_id), permission="Manage team users"
            )
            user_id_list = team.get("user_id")
            known_user_ids = {
                str(item.get("_id"))
                for item in get_all_user_by_is_sys_admin(False)
                if item.get("active", True) is True
            }
            requested_user_ids = list(dict.fromkeys(str(item) for item in user_id))
            if any(item not in known_user_ids for item in requested_user_ids):
                raise AccessControlError("One or more users do not exist", status_code=400)
            user_id_list.extend(item for item in requested_user_ids if item not in user_id_list)
            update_team(team_id=team_id, user_id=user_id_list)
        else:
            raise ValueError("Team ID and User ID is required")
        return jsonify({"success": f"Insert users to team success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/insert_team_users")


async def delete_data_group_function(team_id, data_group_id):
    ingester = current_app.config[CONFIG_INGESTER]
    store = _knowledge_store()
    for stored_object in await store.list("team", prefix=f"{team_id}/"):
        tag_resp = stored_object.tags
        if stored_object.key.startswith(str(team_id)):
            status = str(tag_resp.get('status', ''))
            data_group_tags = str(tag_resp.get('data_groups', ''))
            data_groups_id_list = data_group_tags.split("/")
            if data_group_id in data_groups_id_list:
                if len(data_groups_id_list) == 1:
                    await ingester.remove_groups_file(stored_object.key, str(data_group_id))
                    await store.delete("team", stored_object.key)
                else:
                    data_groups_id_list.remove(data_group_id)
                    await ingester.remove_groups_file(stored_object.key, str(data_group_id))
                    await store.set_tags("team", stored_object.key, {"status": status, "data_groups": "/".join(data_groups_id_list)})


@bp.post("/delete_team")
@authenticated
async def delete_team(auth_claims: dict[str, Any]):
    try:
        actor = _require_system_permission(auth_claims, "Manage teams")
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
                delete_agent_cascade(
                    str(agent_id),
                    reason="team_deleted",
                    actor_id=str(actor.get("_id") or ""),
                )
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
        return error_response(error_txt, "/delete_team")


@bp.post("/create_agent")
@authenticated
async def create_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        actor, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage agents"
        )
        agent_name = str(body.get("agent_name") or "").strip()
        if not agent_name:
            raise AccessControlError("Agent name is required", status_code=400)
        draft = body.get("draft", False)
        if not isinstance(draft, bool):
            raise AccessControlError("draft must be a boolean", status_code=400)
        agent_config = _validate_agent_model_config(body.get("config", None))
        _validate_agent_mcp_connections(agent_config, str(team_id or ""))
        agent_prompt = body.get("prompt", None)
        draft_expires_at = None
        if draft:
            draft_expires_at = datetime.now(timezone.utc) + timedelta(
                hours=_agent_draft_retention_hours()
            )
            agent_id = insert_agent(
                agent_name,
                agent_prompt,
                agent_config,
                lifecycle_status="draft",
                draft_expires_at=draft_expires_at,
                created_by=str(actor.get("_id") or ""),
            )[1]
        else:
            _, agent_id = insert_agent(agent_name, agent_prompt, agent_config)
        agent_team = team.get("agent_id")
        if agent_team:
            agent_team.append(str(agent_id))
        else:
            agent_team = [str(agent_id)]
        update_team(team_id=team_id, agent_id=agent_team)
        created_agent = {
            "_id": str(agent_id),
            "agent_name": agent_name,
            "prompt": agent_prompt,
            "config": agent_config,
            "lifecycle_status": "draft" if draft else "active",
            "draft_expires_at": draft_expires_at,
        }
        return jsonify({"success": f"Create agent {agent_name} success", "agent": created_agent}), 201 if draft else 200
    except Exception as error_txt:
        return error_response(error_txt, "/create_agent")


@bp.post("/get_agent_by_team")
@authenticated
async def get_agent_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        include_drafts = body.get("include_drafts", False)
        if not isinstance(include_drafts, bool):
            raise AccessControlError("include_drafts must be a boolean", status_code=400)
        _, team = _require_team_access(
            auth_claims,
            str(team_id or ""),
            permission="Manage agents" if include_drafts else None,
        )
        agents = []
        for agent_id in team.get("agent_id") or []:
            agent = get_agent_by_id(str(agent_id))
            if agent and not is_expired_agent_draft(agent) and (include_drafts or is_active_agent(agent)):
                serialized_agent = dict(agent)
                prompt = dict(agent.get("prompt") or {})
                for field in ("role", "task", "detail_context", "output_format", "constraints"):
                    prompt[field] = str(prompt.get(field) or "")
                serialized_agent["prompt"] = prompt
                serialized_agent["config"] = dict(agent.get("config") or {})
                agents.append(serialized_agent)
        return jsonify({"result": agents}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_agent_by_team")


@bp.post("/edit_agent")
@authenticated
async def edit_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        agent_id = body.get("agent_id", None)
        _, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage agents"
        )
        if str(agent_id or "") not in {str(item) for item in (team.get("agent_id") or [])}:
            raise AccessControlError("Agent does not belong to this team", status_code=404)
        current_agent = get_agent_by_id(str(agent_id or ""))
        if not current_agent:
            raise AccessControlError("Agent not found", status_code=404)
        agent_name = body.get("agent_name", None)
        agent_config = _validate_agent_model_config(body.get("config", None))
        _validate_agent_mcp_connections(
            agent_config,
            str(team_id or ""),
            existing_config=current_agent.get("config") or {},
        )
        agent_prompt = body.get("prompt", None)
        update_agent(
            agent_id,
            agent_name,
            agent_prompt,
            agent_config,
            draft_expires_at=(
                datetime.now(timezone.utc) + timedelta(hours=_agent_draft_retention_hours())
                if not is_active_agent(current_agent)
                else None
            ),
        )
        return jsonify({"success": f"Edit agent success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/edit_agent")


@bp.post("/delete_agent")
@authenticated
async def delete_agent(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        agent_id = body.get("agent_id", None)
        actor, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage agents"
        )
        if str(agent_id or "") not in {str(item) for item in (team.get("agent_id") or [])}:
            raise AccessControlError("Agent does not belong to this team", status_code=404)
        delete_agent_cascade(
            str(agent_id),
            reason="user_deleted",
            actor_id=str(actor.get("_id") or ""),
        )
        return jsonify({"success": f"Delete agent success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/delete_agent")


@bp.post("/activate_agent_draft")
@authenticated
async def activate_agent_draft(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = str(body.get("team_id") or "")
        agent_id = str(body.get("agent_id") or "")
        actor, team = _require_team_access(
            auth_claims, team_id, permission="Manage agents"
        )
        if agent_id not in {str(item) for item in (team.get("agent_id") or [])}:
            raise AccessControlError("Agent does not belong to this team", status_code=404)
        agent = get_agent_by_id(agent_id)
        if not agent:
            raise AccessControlError("Agent not found", status_code=404)
        if is_active_agent(agent):
            return jsonify({"success": "Agent is already active", "agent": agent}), 200
        if is_expired_agent_draft(agent):
            delete_agent_cascade(agent_id, reason="draft_expired")
            raise AccessControlError("Agent draft has expired", status_code=410)
        _validate_agent_model_config(agent.get("config"))
        _validate_agent_mcp_connections(agent.get("config") or {}, team_id)
        if not str(agent.get("agent_name") or "").strip():
            raise AccessControlError("Agent name is required", status_code=400)
        if not activate_agent_by_id(agent_id):
            raise AccessControlError("Agent draft could not be activated", status_code=409)
        activated = get_agent_by_id(agent_id) or {**agent, "lifecycle_status": "active", "draft_expires_at": None}
        get_database()["agent_lifecycle_audit"].insert_one({
            "_id": str(uuid.uuid4()),
            "event_type": "agent_activated",
            "agent_id": agent_id,
            "actor_id": str(actor.get("_id") or ""),
            "team_id": team_id,
            "created_at": datetime.now(timezone.utc),
        })
        return jsonify({"success": "Agent activated", "agent": activated}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/activate_agent_draft")


def _catalog_text(value: object, field: str, maximum: int, *, required: bool = False) -> str:
    normalized = str(value or "").strip()
    if required and not normalized:
        raise AccessControlError(f"{field} is required", status_code=400)
    if len(normalized) > maximum:
        raise AccessControlError(f"{field} is too long", status_code=400)
    return normalized


def _catalog_tags(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AccessControlError("tags must be an array", status_code=400)
    result: list[str] = []
    for raw_tag in value[:12]:
        tag = _catalog_text(raw_tag, "tag", 40)
        if tag and tag.lower() not in {item.lower() for item in result}:
            result.append(tag)
    return result


def _serialize_catalog_item(
    item: dict[str, Any],
    *,
    team_id: str | None = None,
    include_governance: bool = False,
) -> dict[str, Any]:
    latest_version = int(item.get("latest_version") or 1)
    version = get_catalog_version(str(item.get("_id") or ""), latest_version) or {}
    publisher_team = get_team_by_id(str(item.get("publisher_team_id") or ""))
    creator = get_user_by_id(str(version.get("created_by") or item.get("created_by") or ""))
    creator_name = " ".join(
        value for value in (
            str((creator or {}).get("first_name") or "").strip(),
            str((creator or {}).get("last_name") or "").strip(),
        ) if value
    )
    publisher_type = str(item.get("publisher_type") or "team")
    installation = (
        get_active_installation(str(item.get("_id") or ""), team_id)
        if team_id
        else None
    )
    result = {
        "_id": str(item.get("_id") or ""),
        "name": str(item.get("name") or ""),
        "summary": str(item.get("summary") or ""),
        "usage_instructions": str(item.get("usage_instructions") or ""),
        "tags": [str(value) for value in item.get("tags") or []],
        "category": str(item.get("category") or "General"),
        "publisher_team": {
            "_id": str(item.get("publisher_team_id") or ""),
            "name": "System Administration" if publisher_type == "system" else str((publisher_team or {}).get("name") or "Unknown team"),
        },
        "publisher_type": publisher_type,
        "created_by": {
            "_id": str((creator or {}).get("_id") or ""),
            "name": creator_name or ("System administrator" if publisher_type == "system" else "Unknown user"),
        },
        "visibility": str(item.get("visibility") or "team"),
        "status": str(item.get("status") or "published"),
        "latest_version": latest_version,
        "requirements": version.get("requirements") or {},
        "installed": installation is not None,
        "installed_version": int((installation or {}).get("version") or 0) or None,
        "update_available": bool(installation and int(installation.get("version") or 0) < latest_version),
        "installed_agent_id": str((installation or {}).get("installed_agent_id") or "") or None,
        "updated_at": item.get("updated_at"),
    }
    if include_governance:
        result["source_agent_id"] = str(item.get("source_agent_id") or "")
        result["allowed_team_ids"] = [str(value) for value in item.get("allowed_team_ids") or []]
    return result


@bp.get("/agent-catalog")
@authenticated
async def get_agent_catalog(auth_claims: dict[str, Any]):
    try:
        team_id = str(request.args.get("team_id") or "").strip()
        if team_id:
            _require_team_access(auth_claims, team_id)
            items = list_catalog_items(team_id=team_id)
            return jsonify({
                "result": [_serialize_catalog_item(item, team_id=team_id) for item in items]
            }), 200
        _require_system_admin(auth_claims)
        return jsonify({
            "result": [
                _serialize_catalog_item(item, include_governance=True)
                for item in list_catalog_items(include_unpublished=True)
            ]
        }), 200
    except Exception as error_txt:
        return error_response(error_txt, "/agent-catalog")


@bp.post("/agent-catalog/publish")
@authenticated
async def publish_agent_to_catalog(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        if not isinstance(body, dict):
            raise AccessControlError("request must be json", status_code=400)
        team_id = _catalog_text(body.get("team_id"), "team_id", 128, required=True)
        actor, team = _require_team_access(auth_claims, team_id, permission="Manage agents")
        agent_id = _catalog_text(body.get("agent_id"), "agent_id", 128, required=True)
        if agent_id not in {str(value) for value in team.get("agent_id") or []}:
            raise AccessControlError("Agent does not belong to this team", status_code=404)
        agent = get_agent_by_id(agent_id)
        if not agent:
            raise AccessControlError("Agent not found", status_code=404)
        if not is_active_agent(agent):
            raise AccessControlError("Finish the Agent setup before publishing", status_code=409)

        visibility = str(body.get("visibility") or "team").strip()
        allowed_team_ids = _normalize_id_list(body.get("allowed_team_ids"), "allowed_team_ids")
        if actor.get("is_sys_admin") is not True:
            visibility = "team"
            allowed_team_ids = []
        if visibility not in {"team", "selected_teams", "all_teams"}:
            raise AccessControlError("Unsupported catalog visibility", status_code=400)
        if visibility == "selected_teams":
            if not allowed_team_ids:
                raise AccessControlError("Select at least one allowed team", status_code=400)
            known_team_ids = {str(value.get("_id")) for value in get_all_teams()}
            if any(value not in known_team_ids for value in allowed_team_ids):
                raise AccessControlError("One or more allowed teams do not exist", status_code=400)
        else:
            allowed_team_ids = []

        item, version = publish_agent(
            agent=agent,
            publisher_team_id=team_id,
            created_by=str(actor.get("_id") or ""),
            summary=_catalog_text(body.get("summary"), "summary", 500, required=True),
            usage_instructions=_catalog_text(body.get("usage_instructions"), "usage_instructions", 4000, required=True),
            tags=_catalog_tags(body.get("tags")),
            category=_catalog_text(body.get("category") or "General", "category", 80, required=True),
            visibility=visibility,
            allowed_team_ids=allowed_team_ids,
        )
        insert_catalog_audit_event(
            "published" if version == 1 else "version_published",
            actor_id=str(actor.get("_id") or ""),
            catalog_item_id=str(item.get("_id") or ""),
            team_id=team_id,
            version=version,
        )
        return jsonify({"result": _serialize_catalog_item(item, team_id=team_id), "version": version}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/agent-catalog/publish")


@bp.post("/admin/agent-catalog")
@authenticated
async def create_system_agent_catalog_item(auth_claims: dict[str, Any]):
    try:
        actor = _require_system_admin(auth_claims)
        body = await request.get_json()
        if not isinstance(body, dict):
            raise AccessControlError("request must be json", status_code=400)
        agent_name = _catalog_text(body.get("agent_name"), "agent_name", 200, required=True)
        prompt = body.get("prompt")
        if not isinstance(prompt, dict):
            raise AccessControlError("prompt must be an object", status_code=400)
        config = _validate_agent_model_config(body.get("config"))
        # A system-owned catalog template has no live Agent or Team identity.
        # Its generated source key exists only to retain immutable versions.
        template = {
            "_id": f"system-catalog:{uuid.uuid4()}",
            "agent_name": agent_name,
            "prompt": prompt,
            "config": config,
        }
        visibility = str(body.get("visibility") or "all_teams").strip()
        if visibility not in {"selected_teams", "all_teams"}:
            raise AccessControlError("System templates must target selected teams or all teams", status_code=400)
        allowed_team_ids = _normalize_id_list(body.get("allowed_team_ids"), "allowed_team_ids")
        if visibility == "selected_teams":
            known_team_ids = {str(value.get("_id")) for value in get_all_teams()}
            if not allowed_team_ids or any(value not in known_team_ids for value in allowed_team_ids):
                raise AccessControlError("Select valid allowed teams", status_code=400)
        else:
            allowed_team_ids = []
        item, version = publish_agent(
            agent=template,
            publisher_team_id="",
            created_by=str(actor.get("_id") or ""),
            summary=_catalog_text(body.get("summary"), "summary", 500, required=True),
            usage_instructions=_catalog_text(body.get("usage_instructions"), "usage_instructions", 4000, required=True),
            tags=_catalog_tags(body.get("tags")),
            category=_catalog_text(body.get("category") or "General", "category", 80, required=True),
            visibility=visibility,
            allowed_team_ids=allowed_team_ids,
            publisher_type="system",
        )
        insert_catalog_audit_event(
            "system_template_created",
            actor_id=str(actor.get("_id") or ""),
            catalog_item_id=str(item.get("_id") or ""),
            version=version,
        )
        return jsonify({"result": _serialize_catalog_item(item, include_governance=True), "version": version}), 201
    except Exception as error_txt:
        return error_response(error_txt, "/admin/agent-catalog")


@bp.post("/agent-catalog/<catalog_item_id>/install")
@authenticated
async def install_catalog_agent(auth_claims: dict[str, Any], catalog_item_id: str):
    try:
        body = await request.get_json()
        if not isinstance(body, dict):
            raise AccessControlError("request must be json", status_code=400)
        team_id = _catalog_text(body.get("team_id"), "team_id", 128, required=True)
        actor, team = _require_team_access(auth_claims, team_id, permission="Manage agents")
        item = get_catalog_item(catalog_item_id)
        if not item or not is_visible_to_team(item, team_id):
            raise AccessControlError("Catalog agent is not available to this team", status_code=404)
        version_number = int(body.get("version") or item.get("latest_version") or 1)
        if version_number != int(item.get("latest_version") or 1):
            raise AccessControlError("Phase 1 installs the latest published version only", status_code=400)
        existing = get_active_installation(catalog_item_id, team_id)
        if existing:
            return jsonify({
                "result": "already_installed",
                "agent_id": str(existing.get("installed_agent_id") or ""),
            }), 200
        version = get_catalog_version(catalog_item_id, version_number)
        if not version:
            raise AccessControlError("Catalog version not found", status_code=404)
        snapshot = version.get("snapshot") or {}
        config = _validate_agent_model_config(copy.deepcopy(snapshot.get("config") or {}))
        _validate_agent_mcp_connections(config, team_id)
        agent_name = _catalog_text(snapshot.get("agent_name"), "agent_name", 200, required=True)
        _, installed_agent_id = insert_agent(
            agent_name,
            copy.deepcopy(snapshot.get("prompt") or {}),
            config,
        )
        if (config.get("tool_settings") or {}).get("chart") is True:
            chart_settings = config.get("chart_settings") or {}
            if not isinstance(chart_settings, dict):
                delete_agent_cascade(
                    str(installed_agent_id),
                    reason="catalog_install_failed",
                    actor_id=str(actor.get("_id") or ""),
                )
                raise AccessControlError("Catalog chart settings must be an object", status_code=400)
            try:
                insert_chart_binding(
                    agent_id=str(installed_agent_id),
                    color_palette=chart_settings.get("color_palette"),
                    title_template=chart_settings.get("title_template", ""),
                    trigger_keywords=chart_settings.get("trigger_keywords", []),
                    enabled=chart_settings.get("enabled", True),
                    auto_generate=chart_settings.get("auto_generate", False),
                    chart_selection_mode=chart_settings.get("chart_selection_mode", "auto"),
                    default_chart_type=chart_settings.get("default_chart_type"),
                    allowed_chart_types=chart_settings.get("allowed_chart_types"),
                )
            except Exception:
                delete_agent_cascade(
                    str(installed_agent_id),
                    reason="catalog_install_failed",
                    actor_id=str(actor.get("_id") or ""),
                )
                raise
        team_agent_ids = [str(value) for value in team.get("agent_id") or []]
        if installed_agent_id not in team_agent_ids:
            team_agent_ids.append(installed_agent_id)
            update_team(team_id=team_id, agent_id=team_agent_ids)
        record_installation(
            catalog_item_id=catalog_item_id,
            version=version_number,
            team_id=team_id,
            agent_id=installed_agent_id,
            created_by=str(actor.get("_id") or ""),
        )
        insert_catalog_audit_event(
            "installed",
            actor_id=str(actor.get("_id") or ""),
            catalog_item_id=catalog_item_id,
            team_id=team_id,
            version=version_number,
        )
        return jsonify({"result": "installed", "agent_id": installed_agent_id}), 201
    except Exception as error_txt:
        return error_response(error_txt, f"/agent-catalog/{catalog_item_id}/install")


@bp.patch("/agent-catalog/<catalog_item_id>")
@authenticated
async def edit_agent_catalog_item(auth_claims: dict[str, Any], catalog_item_id: str):
    try:
        body = await request.get_json()
        if not isinstance(body, dict):
            raise AccessControlError("request must be json", status_code=400)
        item = get_catalog_item(catalog_item_id)
        if not item:
            raise AccessControlError("Catalog agent not found", status_code=404)
        actor = _application_user_for_claims(auth_claims)
        if not actor or actor.get("active", True) is not True:
            raise AccessControlError("The signed-in application user is unavailable")
        is_system_admin = actor.get("is_sys_admin") is True
        if not is_system_admin:
            publisher_team_id = str(item.get("publisher_team_id") or "")
            _require_team_access(auth_claims, publisher_team_id, permission="Manage agents")

        changes: dict[str, Any] = {}
        if "summary" in body:
            changes["summary"] = _catalog_text(body.get("summary"), "summary", 500, required=True)
        if "usage_instructions" in body:
            changes["usage_instructions"] = _catalog_text(
                body.get("usage_instructions"), "usage_instructions", 4000, required=True
            )
        if "tags" in body:
            changes["tags"] = _catalog_tags(body.get("tags"))
        if "category" in body:
            changes["category"] = _catalog_text(body.get("category"), "category", 80, required=True)
        if "status" in body:
            status = str(body.get("status") or "").strip()
            if status not in {"published", "unpublished"}:
                raise AccessControlError("Unsupported catalog status", status_code=400)
            changes["status"] = status
        if is_system_admin and "visibility" in body:
            visibility = str(body.get("visibility") or "").strip()
            if visibility not in {"team", "selected_teams", "all_teams"}:
                raise AccessControlError("Unsupported catalog visibility", status_code=400)
            if str(item.get("publisher_type") or "team") == "system" and visibility == "team":
                raise AccessControlError(
                    "System templates must target selected teams or all teams",
                    status_code=400,
                )
            allowed_team_ids = _normalize_id_list(body.get("allowed_team_ids"), "allowed_team_ids")
            if visibility == "selected_teams":
                known_team_ids = {str(value.get("_id")) for value in get_all_teams()}
                if not allowed_team_ids or any(value not in known_team_ids for value in allowed_team_ids):
                    raise AccessControlError("Select valid allowed teams", status_code=400)
            else:
                allowed_team_ids = []
            changes.update({"visibility": visibility, "allowed_team_ids": allowed_team_ids})
        if not changes:
            raise AccessControlError("No supported catalog changes were provided", status_code=400)
        update_catalog_item(catalog_item_id, changes)
        insert_catalog_audit_event(
            "catalog_updated",
            actor_id=str(actor.get("_id") or ""),
            catalog_item_id=catalog_item_id,
            team_id=str(item.get("publisher_team_id") or ""),
            version=int(item.get("latest_version") or 1),
        )
        updated = get_catalog_item(catalog_item_id) or item
        return jsonify({"result": _serialize_catalog_item(updated, include_governance=is_system_admin)}), 200
    except Exception as error_txt:
        return error_response(error_txt, f"/agent-catalog/{catalog_item_id}")


@bp.post("/create_data_group")
@authenticated
async def create_data_group(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        data_group_name = body.get("data_group_name", None)
        if not str(data_group_name or "").strip():
            raise AccessControlError("Data group name is required", status_code=400)
        _, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team data groups"
        )
        access_mode, users_id = _normalize_data_group_access(
            access_mode=body.get("access_mode"),
            users_id=body.get("users_id", []),
            team=team,
        )
        result, data_group_id = insert_data_group(
            str(data_group_name).strip(), users_id, access_mode
        )
        data_group_team = team.get("data_group_id")
        if data_group_team:
            data_group_team.append(str(data_group_id))
        else:
            data_group_team = [str(data_group_id)]
        update_team(team_id=team_id, data_group_id=data_group_team)
        return jsonify({"success": f"Create data group {data_group_name} success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/create_data_group")


@bp.post("/get_data_group_by_team")
@authenticated
async def get_data_group_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        _, team = _require_team_access(auth_claims, str(team_id or ""))
        data_group_team = team.get("data_group_id") or []
        data_group = []
        for data_group_id in data_group_team:
            data_group_info = get_data_group_by_id(str(data_group_id))
            if not data_group_info:
                continue
            data_group_info["access_mode"] = str(data_group_info.get("access_mode") or (
                "team" if not data_group_info.get("user_id") else "selected_users"
            ))
            data_group_info["exposure"] = str(
                data_group_info.get("exposure") or "internal"
            )
            data_group_info["publication_status"] = str(
                data_group_info.get("publication_status") or "not_applicable"
            )
            data_group_info["publication_version"] = int(
                data_group_info.get("publication_version") or 0
            )
            data_group_info.pop("publication_history", None)
            if data_group_info["user_id"] != []:
                user_list = []
                for user in data_group_info["user_id"]:
                    member = get_user_by_id(str(user))
                    if member:
                        user_list.append(member)
                data_group_info["user_id"] = user_list
            data_group.append(data_group_info)
        return jsonify({"result": data_group}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_data_group_by_team")


@bp.patch("/teams/<team_id>/data-groups/<data_group_id>/publication")
@authenticated
async def update_data_group_external_publication(
    auth_claims: dict[str, Any], team_id: str, data_group_id: str
):
    try:
        if not request.is_json:
            raise AccessControlError("request must be json", status_code=415)
        body = await request.get_json()
        exposure = str((body or {}).get("exposure") or "").strip().lower()
        publication_status = str(
            (body or {}).get("publication_status") or ""
        ).strip().lower()
        if exposure not in {"internal", "external"}:
            raise AccessControlError(
                "Unsupported Data Group exposure", status_code=400
            )
        if exposure == "external" and publication_status not in {
            "draft",
            "published",
            "retired",
        }:
            raise AccessControlError(
                "External publication status must be draft, published, or retired",
                status_code=400,
            )
        if exposure == "external" and publication_status == "draft":
            actor, team = _require_team_access(
                auth_claims,
                team_id,
                permission="Manage team data groups",
            )
        else:
            actor = _require_system_permission(
                auth_claims, "Manage external channels"
            )
            team = get_team_by_id(team_id)
        if not team or data_group_id not in {
            str(item) for item in (team.get("data_group_id") or [])
        }:
            raise AccessControlError(
                "Data group does not belong to this team", status_code=404
            )
        group = get_data_group_by_id(data_group_id)
        if not group:
            raise AccessControlError("Data group not found", status_code=404)
        member_ids = group.get("user_id") or []
        access_mode = str(group.get("access_mode") or "").strip().lower()
        if not access_mode:
            access_mode = "team" if not member_ids else "selected_users"
        if exposure == "external" and access_mode != "team":
            raise AccessControlError(
                "Only Team-wide Data Groups can be published externally",
                status_code=409,
            )
        updated = update_data_group_publication(
            data_group_id,
            exposure=exposure,
            publication_status=publication_status,
            actor_id=str(actor.get("_id") or ""),
        )
        if not updated:
            raise AccessControlError(
                "Publication state was not changed", status_code=409
            )
        current = get_data_group_by_id(data_group_id) or {}
        return jsonify(
            {
                "result": {
                    "_id": data_group_id,
                    "exposure": str(current.get("exposure") or "internal"),
                    "publication_status": str(
                        current.get("publication_status") or "not_applicable"
                    ),
                    "publication_version": int(
                        current.get("publication_version") or 0
                    ),
                    "published_at": current.get("published_at"),
                    "published_by": current.get("published_by"),
                }
            }
        )
    except Exception as error_txt:
        return error_response(
            error_txt,
            "/teams/<team_id>/data-groups/<data_group_id>/publication",
        )


@bp.post("/edit_data_group")
@authenticated
async def edit_data_group(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        data_group_id = body.get("data_group_id", None)
        data_group_name = body.get("data_group_name", None)
        team = get_team_by_data_group_id(str(data_group_id or ""))
        if not team:
            raise AccessControlError("Data group does not belong to an active team", status_code=404)
        _require_team_access(
            auth_claims, str(team["_id"]), permission="Manage team data groups"
        )
        access_mode, users_id = _normalize_data_group_access(
            access_mode=body.get("access_mode"),
            users_id=body.get("users_id", []),
            team=team,
        )
        update_data_group(data_group_id, data_group_name, users_id, access_mode)
        return jsonify({"success": f"Edit data group success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/edit_data_group")


@bp.post("/delete_data_group")
@authenticated
async def delete_data_group(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        data_group_id = body.get("data_group_id", None)
        _, team = _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team data groups"
        )
        data_group_team = team.get("data_group_id") or []
        if data_group_id not in data_group_team:
            raise AccessControlError("Data group does not belong to this team", status_code=404)
        data_group_team.remove(data_group_id)
        update_team(team_id=team_id, data_group_id=data_group_team)
        await delete_data_group_function(team_id, data_group_id)
        delete_data_group_by_id(data_group_id)
        return jsonify({"success": f"Delete data group success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/delete_data_group")


@bp.post("/create_role")
@authenticated
async def create_role(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        name = body.get("name", None)
        permissions_id = body.get("permissions_id", None)
        team_id = body.get("team_id", None)
        _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team permissions"
        )
        permissions_id = _validate_permission_ids(
            permissions_id, permission_type="team"
        )
        if not str(name or "").strip():
            raise AccessControlError("Role name is required", status_code=400)
        insert_role(name, permissions_id, team_id)
        return jsonify({"success": f"Create role {name} success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/create_role")


@bp.post("/delete_role")
@authenticated
async def delete_role(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        role_id = body.get("role_id", None)
        role = get_role_by_id(str(role_id or ""))
        if not role:
            raise AccessControlError("Role not found", status_code=404)
        _require_team_access(
            auth_claims, str(role.get("team_id") or ""), permission="Manage team permissions"
        )
        delete_role_by_id(role_id)
        return jsonify({"success": f"Delete role success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/delete_role")


@bp.post("/edit_role")
@authenticated
async def edit_role(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        role_id = body.get("role_id", None)
        name = body.get("name", None)
        permissions_id = body.get("permissions_id", None)
        team_id = body.get("team_id", None)
        role = get_role_by_id(str(role_id or ""))
        if not role or str(role.get("team_id") or "") != str(team_id or ""):
            raise AccessControlError("Role does not belong to this team", status_code=404)
        _require_team_access(
            auth_claims, str(team_id or ""), permission="Manage team permissions"
        )
        permissions_id = _validate_permission_ids(
            permissions_id, permission_type="team"
        )
        if not str(name or "").strip():
            raise AccessControlError("Role name is required", status_code=400)
        update_role(role_id, name, permissions_id, team_id)
        return jsonify({"success": f"Edit role success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/edit_role")


@bp.post("/get_roles_by_team")
@authenticated
async def get_roles_by_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = body.get("team_id", None)
        _require_team_access(auth_claims, str(team_id or ""))
        all_roles = get_all_roles_by_team(team_id)
        return jsonify({"roles": all_roles}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_roles_by_team")


async def insert_permissions():
    try:
        sys_permission = [
            "Manage teams",
            "Manage users",
            "Manage global uploads",
            "Manage external channels",
            "View feedback dashboard",
            "View system dashboard",
            "Manage user groups",
        ]
        team_permission = [
            "Manage team users",
            "Manage team data groups",
            "Manage agents",
            "Manage team uploads",
            "Manage team permissions",
            "View team dashboard",
        ]
        for permis in sys_permission:
            if not get_permission_by_name(permis):
                insert_permission(permis, "System Permissions")
        for permis in team_permission:
            if not get_permission_by_name(permis):
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
            _, team = _require_team_access(
                auth_claims, str(team_id), permission="Manage team permissions"
            )
            if str(user_id or "") not in {str(item) for item in (team.get("user_id") or [])}:
                raise AccessControlError("User is not a member of this team", status_code=404)
            user_per = get_user_permission_by_user_team_id(user_id, team_id)
        else:
            _require_system_permission(auth_claims, "Manage users")
            user_per = get_user_permission_by_user_team_id(user_id, "")
        if user_per == []:
            return jsonify({"user_permissions": None}), 200
        else:
            return jsonify({"user_permissions": user_per}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/get_user_permissions")


@bp.post("/create_edit_user_permissions")
@authenticated
async def create_edit_user_permissions(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        user_id = body.get("user_id", None)
        team_id = body.get("team_id", None)
        permissions_id = body.get("permission_id", None)
        is_sys_admin = body.get("is_sys_admin", None)
        if team_id:
            _, team = _require_team_access(
                auth_claims, str(team_id), permission="Manage team permissions"
            )
            if str(user_id or "") not in {str(item) for item in (team.get("user_id") or [])}:
                raise AccessControlError("User is not a member of this team", status_code=404)
            permissions_id = _validate_permission_ids(
                permissions_id, permission_type="team"
            )
            user_per = get_user_permission_by_user_team_id(user_id, team_id)
            if user_per == []:
                insert_user_permission(team_id, user_id, permissions_id)
            else:
                update_user_permission(
                    user_per[0]["_id"], team_id, user_id, permissions_id)
        else:
            actor, target_user = _require_user_management_target(
                auth_claims, str(user_id or "")
            )
            current_is_sys_admin = target_user.get("is_sys_admin") is True
            requested_is_sys_admin = bool(is_sys_admin)
            if current_is_sys_admin != requested_is_sys_admin and actor.get("is_sys_admin") is not True:
                raise AccessControlError(
                    "Only a system administrator can change the System Admin role"
                )
            if current_is_sys_admin and not requested_is_sys_admin:
                _require_user_management_target(
                    auth_claims, str(user_id or ""), destructive=True
                )
            if not requested_is_sys_admin:
                permissions_id = _validate_permission_ids(
                    permissions_id, permission_type="system"
                )
            update_user(user_id=user_id, is_sys_admin=requested_is_sys_admin)
            if not requested_is_sys_admin:
                user_per = get_user_permission_by_user_team_id(user_id, "")
                if user_per == []:
                    insert_user_permission("", user_id, permissions_id)
                else:
                    update_user_permission(
                        user_per[0]["_id"], "", user_id, permissions_id)
        return jsonify({"Success": "Create/Edit User permissions success"}), 200
    except Exception as error_txt:
        return error_response(error_txt, "/create_edit_user_permissions")


@bp.post("/insert_database_connection")
@authenticated
async def insert_database_connection(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        team_id = str(body.get("team_id") or "").strip()
        name = str(body.get("name") or "").strip()
        if not name:
            raise ValueError("connection name is required")
        _require_integration_catalog_access(auth_claims, team_id)
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
        existing = get_external_database_by_id(str(database_id or ""))
        if not existing:
            return jsonify({"error": "Database connection not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
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
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        if "team_id" in body and str(body.get("team_id") or "") != str(existing.get("team_id") or ""):
            raise ValueError("Use Assign to team to change integration ownership")
        merged = {**existing, **{key: value for key, value in body.items() if value is not None}}
        config = normalize_database_config(merged)
        name = str(merged.get("name") or "").strip()
        team_id = str(merged.get("team_id") or "").strip()
        if not name:
            raise ValueError("connection name is required")
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
        team_id = str(body.get("team_id") or "")
        _require_integration_catalog_access(auth_claims, team_id, allow_agent_management=True)
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
        if existing:
            _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        else:
            _require_integration_catalog_access(auth_claims, str(body.get("team_id") or ""))

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
        _require_agent_integration_team(
            str(agent_id or ""), get_external_database_by_id(str(integration_id or ""))
        )
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
        existing_binding = get_database_binding_by_id(binding_id) if binding_id else None
        if not existing_binding:
            return jsonify({"error": "Database binding not found"}), 404
        next_integration_id = str(body.get("integration_id") or existing_binding.get("integration_id") or "")
        _require_agent_integration_team(
            str(existing_binding.get("agent_id") or ""),
            get_external_database_by_id(next_integration_id),
        )
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
        team_id = str(body.get("team_id") or "")
        _require_integration_catalog_access(auth_claims, team_id)
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
        existing = get_apis_by_id(str(api_id or ""))
        if not existing:
            return jsonify({"error": "REST API not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
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
        existing = get_apis_by_id(str(api_id or ""))
        if not existing:
            return jsonify({"error": "REST API not found"}), 404
        _require_integration_catalog_access(auth_claims, str(existing.get("team_id") or ""))
        name = body.get("name", None)
        type = body.get("type", None)
        team_id = body.get("team_id", None)
        if team_id is not None and str(team_id or "") != str(existing.get("team_id") or ""):
            raise ValueError("Use Assign to team to change integration ownership")
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
        team_id = str(body.get("team_id") or "")
        _require_integration_catalog_access(auth_claims, team_id)
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
        if not apis:
            return jsonify({"error": "REST API not found"}), 404
        _require_integration_catalog_access(auth_claims, str(apis.get("team_id") or ""))
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
        _require_agent_integration_team(
            str(agent_id or ""), get_apis_by_id(str(integration_id or ""))
        )
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
        team_id = str(body.get("team_id") or "")
        _require_integration_catalog_access(auth_claims, team_id, allow_agent_management=True)
        all_apis = get_all_apis_by_team_id(team_id)
        new_all_apis = [{"_id":api["_id"],"name":api["name"],"type":api["type"],"endpoints":api["endpoints"]} for api in all_apis]
        return jsonify({"result": new_all_apis}), 200
    except Exception as error_txt:
        return jsonify({"error": str(error_txt)}), 400


@bp.post("/assign_integration_team")
@authenticated
async def assign_integration_team(auth_claims: dict[str, Any]):
    try:
        body = await request.get_json()
        if not isinstance(body, dict):
            raise IntegrationAssignmentError("request must be json")
        team_id = str(body.get("team_id") or "").strip()
        integration_id = str(body.get("integration_id") or "").strip()
        integration_type = str(body.get("integration_type") or "").strip()

        actor = _application_user_for_claims(auth_claims)
        if not actor or actor.get("active", True) is not True:
            raise AccessControlError("The signed-in application user is unavailable")
        if actor.get("is_sys_admin") is not True:
            raise AccessControlError("Only a system administrator can assign catalog integrations")
        _require_team_access(auth_claims, team_id)

        assignment = assign_unassigned_integration(
            integration_type, integration_id, team_id
        )
        return jsonify({"message": "Integration assigned", "assignment": assignment}), 200
    except IntegrationAssignmentError as error:
        return jsonify({"error": str(error)}), 400
    except AccessControlError as error:
        return error_response(error, "/assign_integration_team")


@bp.get("/admin/integration-connections")
@authenticated
async def admin_list_integration_connections(auth_claims: dict[str, Any]):
    try:
        team_id = str(request.args.get("team_id") or "").strip()
        _require_integration_catalog_access(auth_claims, team_id)
        return jsonify({"connections": list_integration_connections(team_id)})
    except AccessControlError as error:
        return error_response(error, "/admin/integration-connections")

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
    knowledge_storage_provider = os.getenv("KNOWLEDGE_STORAGE_PROVIDER", "azure").strip().lower()
    if knowledge_storage_provider not in {"azure", "minio"}:
        raise ValueError("KNOWLEDGE_STORAGE_PROVIDER must be azure or minio")
    azure_storage_settings = {
        name: os.getenv(name, "").strip()
        for name in (
            "AZURE_STORAGE_ACCOUNT",
            "AZURE_STORAGE_CONTAINER",
            "AZURE_WEB_STORAGE_CONTAINER",
            "AZURE_WEB_GROUP_STORAGE_CONTAINER",
            "AZURE_GROUP_STORAGE_CONTAINER",
        )
    }
    if knowledge_storage_provider == "azure":
        missing_storage_settings = [name for name, value in azure_storage_settings.items() if not value]
        if missing_storage_settings:
            raise ValueError(
                "The following settings are required when KNOWLEDGE_STORAGE_PROVIDER=azure: "
                + ", ".join(missing_storage_settings)
            )
    AZURE_STORAGE_ACCOUNT = azure_storage_settings["AZURE_STORAGE_ACCOUNT"]
    AZURE_STORAGE_CONTAINER = azure_storage_settings["AZURE_STORAGE_CONTAINER"]
    AZURE_WEB_STORAGE_CONTAINER = azure_storage_settings["AZURE_WEB_STORAGE_CONTAINER"]
    AZURE_WEB_GROUP_STORAGE_CONTAINER = azure_storage_settings["AZURE_WEB_GROUP_STORAGE_CONTAINER"]
    AZURE_GROUP_STORAGE_CONTAINER = azure_storage_settings["AZURE_GROUP_STORAGE_CONTAINER"]
    AZURE_USERSTORAGE_ACCOUNT = os.environ.get("AZURE_USERSTORAGE_ACCOUNT")
    AZURE_USERSTORAGE_CONTAINER = os.environ.get("AZURE_USERSTORAGE_CONTAINER")
    KNOWLEDGE_SEARCH_PROVIDER = os.getenv("KNOWLEDGE_SEARCH_PROVIDER", "azure").strip().lower()
    if KNOWLEDGE_SEARCH_PROVIDER not in {"azure", "qdrant"}:
        raise ValueError("KNOWLEDGE_SEARCH_PROVIDER must be azure or qdrant")
    AZURE_SEARCH_SERVICE = os.environ.get("AZURE_SEARCH_SERVICE", "")
    if KNOWLEDGE_SEARCH_PROVIDER == "azure" and not AZURE_SEARCH_SERVICE:
        raise ValueError("AZURE_SEARCH_SERVICE is required when KNOWLEDGE_SEARCH_PROVIDER=azure")
    AZURE_SEARCH_ENDPOINT = f"https://{AZURE_SEARCH_SERVICE}.search.windows.net"
    AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "gptkbindex")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", AZURE_SEARCH_INDEX)
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
    AZURE_SEARCH_AGENT = os.getenv("AZURE_SEARCH_AGENT", "")
    # Model provider settings support both the legacy OPENAI_* variables and
    # the new provider-specific LLM_*/EMBEDDING_* variables.
    runtime_settings = RuntimeSettings.from_env(os.environ)
    active_embedding_profile_id = ENVIRONMENT_PROFILE_ID
    if os.getenv("SKIP_MANAGED_EMBEDDING_PROFILE_LOAD", "").lower() != "true":
        try:
            embedding_state = get_embedding_settings()
            selected_profile_id = embedding_state["active_profile_id"]
            if selected_profile_id != ENVIRONMENT_PROFILE_ID:
                selected_profile = get_embedding_profile(selected_profile_id)
                if not selected_profile or not selected_profile.get("enabled", True):
                    raise ValueError("The active managed embedding profile is unavailable or disabled")
                if KNOWLEDGE_SEARCH_PROVIDER != "qdrant":
                    raise ValueError("Managed embedding profiles currently require Qdrant")
                runtime_settings = dataclasses.replace(
                    runtime_settings,
                    embedding=_settings_for_embedding_profile(selected_profile),
                )
                QDRANT_COLLECTION = str(selected_profile["collection_name"])
                active_embedding_profile_id = selected_profile_id
        except Exception:
            current_app.logger.exception(
                "Unable to load the active managed embedding profile; using environment configuration"
            )
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
    LOCAL_AUTH_ENABLED = os.getenv("LOCAL_AUTH_ENABLED", "").lower() == "true"
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
    managed_auth = None
    if LOCAL_AUTH_ENABLED:
        try:
            managed_auth = get_auth_settings(decrypt_client_secret=True)
        except Exception:
            current_app.logger.exception(
                "Unable to load managed authentication settings; using environment configuration"
            )
    OIDC_AUTHENTICATION_ENABLED = False
    OIDC_PUBLIC_PROVIDERS: list[dict[str, str]] = []
    SAML_AUTHENTICATION_ENABLED = False
    SAML_PUBLIC_PROVIDERS: list[dict[str, str]] = []
    if managed_auth:
        AZURE_USE_AUTHENTICATION = managed_auth.get("entra_enabled") is True
        AZURE_SERVER_APP_ID = managed_auth.get("server_app_id") or None
        AZURE_SERVER_APP_SECRET = managed_auth.get("client_secret") or None
        AZURE_CLIENT_APP_ID = managed_auth.get("client_app_id") or None
        AZURE_AUTH_TENANT_ID = managed_auth.get("tenant_id") or AZURE_TENANT_ID
        OIDC_AUTHENTICATION_ENABLED = managed_auth.get("oidc_enabled") is True
    if LOCAL_AUTH_ENABLED:
        OIDC_PUBLIC_PROVIDERS = public_oidc_providers()
        OIDC_AUTHENTICATION_ENABLED = bool(OIDC_PUBLIC_PROVIDERS)
        SAML_PUBLIC_PROVIDERS = public_saml_providers()
        SAML_AUTHENTICATION_ENABLED = bool(SAML_PUBLIC_PROVIDERS)

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
    USE_CHAT_HISTORY_DATABASE = os.getenv(
        "USE_CHAT_HISTORY_DATABASE", "").lower() == "true"
    USE_AGENTIC_RETRIEVAL = os.getenv(
        "USE_AGENTIC_RETRIEVAL", "").lower() == "true"
    if KNOWLEDGE_SEARCH_PROVIDER == "qdrant" and os.getenv("USE_VECTORS", "").lower() == "false":
        raise ValueError("Qdrant Knowledge search requires USE_VECTORS=true")
    if KNOWLEDGE_SEARCH_PROVIDER == "qdrant" and USE_AGENTIC_RETRIEVAL:
        current_app.logger.warning("Agentic retrieval is Azure AI Search-only; disabling it for Qdrant")
        USE_AGENTIC_RETRIEVAL = False

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
    if not SKIP_STARTUP_BOOTSTRAP:
        ensure_usage_quota_indexes()
        ensure_license_indexes()
        ensure_agent_catalog_indexes()
        ensure_agent_indexes()
        ensure_agent_invocation_key_indexes()
        ensure_agent_invocation_job_indexes()

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

    # Set up the selectable Knowledge search client. Azure remains the default.
    if KNOWLEDGE_SEARCH_PROVIDER == "qdrant":
        search_client = QdrantKnowledgeSearchClient(
            endpoint=QDRANT_URL,
            collection_name=QDRANT_COLLECTION,
            vector_size=OPENAI_EMB_DIMENSIONS,
            vector_field=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
            api_key=QDRANT_API_KEY,
        )
        await search_client.ensure_ready()
        agent_client = None
    else:
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX,
            credential=azure_credential,
        )
        agent_client = KnowledgeAgentRetrievalClient(
            endpoint=AZURE_SEARCH_ENDPOINT, agent_name=AZURE_SEARCH_AGENT, credential=azure_credential
        )

    blob_container_client = None
    web_blob_container_client = None
    web_group_blob_container_client = None
    group_blob_container_client = None
    user_blob_container_client = None
    if knowledge_storage_provider == "azure":
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
        if USE_USER_UPLOAD:
            if not AZURE_USERSTORAGE_ACCOUNT or not AZURE_USERSTORAGE_CONTAINER:
                raise ValueError(
                    "AZURE_USERSTORAGE_ACCOUNT and AZURE_USERSTORAGE_CONTAINER must be set when "
                    "USE_USER_UPLOAD is true and KNOWLEDGE_STORAGE_PROVIDER=azure"
                )
            user_blob_container_client = FileSystemClient(
                f"https://{AZURE_USERSTORAGE_ACCOUNT}.dfs.core.windows.net",
                AZURE_USERSTORAGE_CONTAINER,
                credential=azure_credential,
            )
        knowledge_store: KnowledgeObjectStore = AzureKnowledgeObjectStore(
            {
                "global": blob_container_client,
                "team": group_blob_container_client,
                "personal": user_blob_container_client,
                "web_global": web_blob_container_client,
                "web_team": web_group_blob_container_client,
            }
        )
    else:
        knowledge_store = create_minio_knowledge_store(os.environ)
    await knowledge_store.ensure_ready()
    current_app.config[CONFIG_KNOWLEDGE_STORE] = knowledge_store

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
    file_processors = None
    if attachment_store or USE_USER_UPLOAD:
        file_processors = setup_file_processors(
            azure_credential=azure_credential,
            document_intelligence_service=os.getenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE"),
            document_intelligence_api_version=os.getenv(
                "AZURE_DOCUMENTINTELLIGENCE_API_VERSION", "2024-11-30"
            ),
            local_pdf_parser=os.getenv("USE_LOCAL_PDF_PARSER", "").lower() == "true",
            local_html_parser=os.getenv("USE_LOCAL_HTML_PARSER", "").lower() == "true",
            search_images=USE_GPT4V,
        )
    current_app.config[CONFIG_CHAT_ATTACHMENT_STORE] = attachment_store
    current_app.config[CONFIG_CHAT_ATTACHMENT_SCANNER] = DisabledMalwareScanner()
    attachment_index = MongoAttachmentIndex() if attachment_store else None
    current_app.config[CONFIG_CHAT_ATTACHMENT_INDEX] = attachment_index
    current_app.config[CONFIG_CHAT_ATTACHMENT_PROCESSORS] = file_processors or {}
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
        try:
            recovery_interval = float(os.getenv("CHAT_ATTACHMENT_RECOVERY_INTERVAL_SECONDS", "30"))
        except ValueError as error:
            raise ValueError("CHAT_ATTACHMENT_RECOVERY_INTERVAL_SECONDS must be numeric") from error
        if not math.isfinite(recovery_interval) or recovery_interval < 5:
            raise ValueError("CHAT_ATTACHMENT_RECOVERY_INTERVAL_SECONDS must be at least 5")
        recovery_task = asyncio.create_task(
            _recover_chat_attachment_extractions(recovery_interval)
        )
        BACKGROUND_TASKS.add(recovery_task)
        recovery_task.add_done_callback(BACKGROUND_TASKS.discard)
        current_app.config[CONFIG_CHAT_ATTACHMENT_RECOVERY_TASK] = recovery_task

    # Set up authentication helper
    search_index = None
    search_index_stats = {"document_count": 0, "storage_size": 0}
    if (
        KNOWLEDGE_SEARCH_PROVIDER == "azure"
        and (AZURE_USE_AUTHENTICATION or (LOCAL_AUTH_ENABLED and AZURE_ENFORCE_ACCESS_CONTROL))
    ):
        current_app.logger.info(
            "Authentication ACLs are enabled, setting up search index client")
        search_index_client = SearchIndexClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            credential=azure_credential,
        )
        search_index = await search_index_client.get_index(AZURE_SEARCH_INDEX)
        search_index_stats = await search_index_client.get_index_statistics(AZURE_SEARCH_INDEX)
        await search_index_client.close()
    if LOCAL_AUTH_ENABLED:
        ensure_local_auth_indexes()
    if OIDC_AUTHENTICATION_ENABLED:
        # OIDC sessions share the encrypted/authenticated application identity
        # store but have their own one-time state collection.
        ensure_local_auth_indexes()
        ensure_oidc_auth_indexes()
        ensure_oidc_provider_indexes()
        ensure_identity_management_indexes()
    if SAML_AUTHENTICATION_ENABLED:
        ensure_local_auth_indexes()
        ensure_saml_auth_indexes()
        ensure_saml_provider_indexes()
        ensure_identity_management_indexes()
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
        local_authentication_enabled=LOCAL_AUTH_ENABLED,
        local_session_resolver=resolve_local_session,
        local_bootstrap_required=lambda: not local_identity_exists(),
        oidc_authentication_enabled=OIDC_AUTHENTICATION_ENABLED,
        oidc_display_name=str((managed_auth or {}).get("oidc_display_name") or "Enterprise SSO"),
        oidc_providers=OIDC_PUBLIC_PROVIDERS,
        oidc_session_resolver=resolve_oidc_session,
        saml_authentication_enabled=SAML_AUTHENTICATION_ENABLED,
        saml_providers=SAML_PUBLIC_PROVIDERS,
        saml_session_resolver=resolve_saml_session,
        search_has_auth_fields=True if KNOWLEDGE_SEARCH_PROVIDER == "qdrant" else None,
    )

    text_embeddings_service = create_embedding_service(
        runtime_settings.embedding,
        azure_credential,
        disable_vectors=os.getenv("USE_VECTORS", "").lower() == "false",
        disable_batch=os.getenv("OPENAI_EMB_DISABLE_BATCH", "").lower() == "true",
    )
    current_app.config[CONFIG_ACTIVE_EMBEDDING_PROFILE_ID] = active_embedding_profile_id
    if os.getenv("SKIP_MANAGED_EMBEDDING_PROFILE_LOAD", "").lower() != "true":
        try:
            mark_embedding_runtime_started(active_embedding_profile_id)
        except Exception:
            current_app.logger.exception("Unable to record the active embedding runtime profile")

    if USE_USER_UPLOAD:
        current_app.logger.info(
            "USE_USER_UPLOAD is true, setting up user upload feature")
        current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT] = user_blob_container_client

        # Set up ingester
        if file_processors is None:
            raise RuntimeError("Document processors were not initialized")
        search_info = await setup_search_info(
            search_service=AZURE_SEARCH_SERVICE,
            index_name=QDRANT_COLLECTION if KNOWLEDGE_SEARCH_PROVIDER == "qdrant" else AZURE_SEARCH_INDEX,
            azure_credential=azure_credential,
            provider=KNOWLEDGE_SEARCH_PROVIDER,
            qdrant_url=QDRANT_URL,
            qdrant_api_key=QDRANT_API_KEY,
            qdrant_vector_size=OPENAI_EMB_DIMENSIONS,
            qdrant_vector_field=AZURE_SEARCH_FIELD_NAME_EMBEDDING,
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
            current_app.config[CONFIG_INGESTION_RECOVERY_TASK] = recovery_task

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
    current_app.config[CONFIG_KNOWLEDGE_STORE] = knowledge_store
    current_app.config[CONFIG_AUTH_CLIENT] = auth_helper

    current_app.config[CONFIG_GPT4V_DEPLOYED] = bool(USE_GPT4V)
    current_app.config[CONFIG_KNOWLEDGE_VISION_ENABLED] = (
        knowledge_storage_provider == "azure"
        and KNOWLEDGE_SEARCH_PROVIDER == "azure"
        and _has_configured_knowledge_vision(bool(USE_GPT4V), AZURE_VISION_ENDPOINT)
    )
    if USE_GPT4V and not current_app.config[CONFIG_KNOWLEDGE_VISION_ENABLED]:
        current_app.logger.warning(
            "USE_GPT4V is enabled without a valid AZURE_VISION_ENDPOINT; "
            "Azure Knowledge image-vector retrieval is disabled"
        )
    current_app.config[CONFIG_SEMANTIC_RANKER_DEPLOYED] = (
        KNOWLEDGE_SEARCH_PROVIDER == "azure" and AZURE_SEARCH_SEMANTIC_RANKER != "disabled"
    )
    current_app.config[CONFIG_QUERY_REWRITING_ENABLED] = (
        KNOWLEDGE_SEARCH_PROVIDER == "azure"
        and AZURE_SEARCH_QUERY_REWRITING == "true"
        and AZURE_SEARCH_SEMANTIC_RANKER != "disabled"
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
    current_app.config[CONFIG_CHAT_HISTORY_DATABASE_ENABLED] = USE_CHAT_HISTORY_DATABASE
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
    controller = IntegrationControllerClient()
    if (
        controller.configured
        and os.getenv("DISABLE_MANAGED_MCP_RECONCILIATION", "").lower() != "true"
    ):
        current_app.config["MANAGED_MCP_RECONCILIATION_TASK"] = asyncio.create_task(
            _reconcile_managed_azure_mcp_servers()
        )

    _agent_draft_retention_hours()
    try:
        agent_draft_cleanup_interval = float(
            os.getenv("AGENT_DRAFT_CLEANUP_INTERVAL_SECONDS", "3600")
        )
    except ValueError as error:
        raise ValueError("AGENT_DRAFT_CLEANUP_INTERVAL_SECONDS must be numeric") from error
    if not math.isfinite(agent_draft_cleanup_interval) or agent_draft_cleanup_interval < 60:
        raise ValueError("AGENT_DRAFT_CLEANUP_INTERVAL_SECONDS must be at least 60")
    agent_draft_cleanup_task = asyncio.create_task(
        _run_agent_draft_cleanup(agent_draft_cleanup_interval)
    )
    BACKGROUND_TASKS.add(agent_draft_cleanup_task)
    agent_draft_cleanup_task.add_done_callback(BACKGROUND_TASKS.discard)
    current_app.config["AGENT_DRAFT_CLEANUP_TASK"] = agent_draft_cleanup_task

    if SKIP_STARTUP_BOOTSTRAP:
        current_app.logger.info("Skipping application data bootstrap")
        return

    try:
        agent_invocation_recovery_interval = float(
            os.getenv("AGENT_INVOCATION_JOB_RECOVERY_INTERVAL_SECONDS", "15")
        )
    except ValueError as error:
        raise ValueError(
            "AGENT_INVOCATION_JOB_RECOVERY_INTERVAL_SECONDS must be numeric"
        ) from error
    if (
        not math.isfinite(agent_invocation_recovery_interval)
        or agent_invocation_recovery_interval < 5
    ):
        raise ValueError(
            "AGENT_INVOCATION_JOB_RECOVERY_INTERVAL_SECONDS must be at least 5"
        )
    agent_invocation_recovery_task = asyncio.create_task(
        _recover_agent_invocation_jobs(agent_invocation_recovery_interval)
    )
    BACKGROUND_TASKS.add(agent_invocation_recovery_task)
    agent_invocation_recovery_task.add_done_callback(BACKGROUND_TASKS.discard)
    current_app.config["agent_invocation_job_recovery_task"] = (
        agent_invocation_recovery_task
    )

    _web_source_scan_retention_hours()
    try:
        web_scan_cleanup_interval = float(
            os.getenv("WEB_SOURCE_SCAN_CLEANUP_INTERVAL_SECONDS", "3600")
        )
    except ValueError as error:
        raise ValueError("WEB_SOURCE_SCAN_CLEANUP_INTERVAL_SECONDS must be numeric") from error
    if not math.isfinite(web_scan_cleanup_interval) or web_scan_cleanup_interval < 60:
        raise ValueError("WEB_SOURCE_SCAN_CLEANUP_INTERVAL_SECONDS must be at least 60")
    try:
        web_index_recovery_interval = float(
            os.getenv("WEB_SOURCE_INDEX_RECOVERY_INTERVAL_SECONDS", "15")
        )
    except ValueError as error:
        raise ValueError(
            "WEB_SOURCE_INDEX_RECOVERY_INTERVAL_SECONDS must be numeric"
        ) from error
    if not math.isfinite(web_index_recovery_interval) or web_index_recovery_interval < 5:
        raise ValueError(
            "WEB_SOURCE_INDEX_RECOVERY_INTERVAL_SECONDS must be at least 5"
        )
    await asyncio.to_thread(ensure_web_source_scan_indexes)
    web_index_recovery_task = asyncio.create_task(
        _recover_web_source_index_jobs(web_index_recovery_interval)
    )
    BACKGROUND_TASKS.add(web_index_recovery_task)
    web_index_recovery_task.add_done_callback(BACKGROUND_TASKS.discard)
    current_app.config[CONFIG_WEB_SOURCE_INDEX_RECOVERY_TASK] = web_index_recovery_task
    web_scan_cleanup_task = asyncio.create_task(
        _run_web_source_scan_cleanup(web_scan_cleanup_interval)
    )
    BACKGROUND_TASKS.add(web_scan_cleanup_task)
    web_scan_cleanup_task.add_done_callback(BACKGROUND_TASKS.discard)
    current_app.config[CONFIG_WEB_SOURCE_SCAN_CLEANUP_TASK] = web_scan_cleanup_task

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
    if recovery_task := current_app.config.get(
        "agent_invocation_job_recovery_task"
    ):
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass
    for invocation_task in tuple(AGENT_INVOCATION_JOB_TASKS):
        invocation_task.cancel()
    if AGENT_INVOCATION_JOB_TASKS:
        await asyncio.gather(
            *tuple(AGENT_INVOCATION_JOB_TASKS), return_exceptions=True
        )
    if recovery_task := current_app.config.get(CONFIG_WEB_SOURCE_INDEX_RECOVERY_TASK):
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass
    for web_source_task in tuple(WEB_SOURCE_INDEX_TASKS):
        web_source_task.cancel()
    if WEB_SOURCE_INDEX_TASKS:
        await asyncio.gather(*tuple(WEB_SOURCE_INDEX_TASKS), return_exceptions=True)
    if cleanup_task := current_app.config.get(CONFIG_WEB_SOURCE_SCAN_CLEANUP_TASK):
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    if cleanup_task := current_app.config.get("AGENT_DRAFT_CLEANUP_TASK"):
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    if reconciliation_task := current_app.config.get(
        "MANAGED_MCP_RECONCILIATION_TASK"
    ):
        reconciliation_task.cancel()
        try:
            await reconciliation_task
        except asyncio.CancelledError:
            pass
    if recovery_task := current_app.config.get(CONFIG_INGESTION_RECOVERY_TASK):
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass
    if recovery_task := current_app.config.get(CONFIG_CHAT_ATTACHMENT_RECOVERY_TASK):
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass
    for ingestion_task in tuple(INGESTION_TASKS):
        ingestion_task.cancel()
    if INGESTION_TASKS:
        await asyncio.gather(*tuple(INGESTION_TASKS), return_exceptions=True)
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
    if knowledge_store := current_app.config.get(CONFIG_KNOWLEDGE_STORE):
        await knowledge_store.close()


def create_app():
    app = Quart(__name__)
    try:
        max_upload_size_bytes = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024)))
    except ValueError as error:
        raise ValueError("MAX_UPLOAD_SIZE_BYTES must be a positive integer") from error
    if max_upload_size_bytes <= 0:
        raise ValueError("MAX_UPLOAD_SIZE_BYTES must be a positive integer")
    app.config["MAX_CONTENT_LENGTH"] = max_upload_size_bytes

    @app.errorhandler(413)
    async def request_too_large(_error):
        limit_mb = max_upload_size_bytes / (1024 * 1024)
        return jsonify({"error": f"Upload request exceeds the {limit_mb:g} MB limit"}), 413

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
