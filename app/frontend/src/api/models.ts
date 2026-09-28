export const enum RetrievalMode {
    Hybrid = "hybrid",
    Vectors = "vectors",
    Text = "text"
}

export const enum GPT4VInput {
    TextAndImages = "textAndImages",
    Images = "images",
    Texts = "texts"
}

export const enum VectorFields {
    Embedding = "textEmbeddingOnly",
    ImageEmbedding = "imageEmbeddingOnly",
    TextAndImageEmbeddings = "textAndImageEmbeddings"
}

export type ChatAppRequestOverrides = {
    retrieval_mode?: RetrievalMode;
    semantic_ranker?: boolean;
    semantic_captions?: boolean;
    query_rewriting?: boolean;
    reasoning_effort?: string;
    include_category?: string;
    exclude_category?: string;
    seed?: number;
    top?: number;
    max_subqueries?: number;
    results_merge_strategy?: string;
    temperature?: number;
    minimum_search_score?: number;
    minimum_reranker_score?: number;
    prompt_template?: string;
    prompt_template_prefix?: string;
    prompt_template_suffix?: string;
    suggest_followup_questions?: boolean;
    use_oid_security_filter?: boolean;
    use_groups_security_filter?: boolean;
    use_gpt4v?: boolean;
    gpt4v_input?: GPT4VInput;
    vector_fields: VectorFields;
    language: string;
    use_agentic_retrieval: boolean;
    max_tokens?: number;
};

export type ResponseMessage = {
    content: string;
    role: string;
};

export type ChatAttachmentInput = {
    id: string;
    kind: "image";
    name: string;
    mime_type: string;
    size: number;
    data_url: string;
};

export type ChatDocumentAttachment = {
    id: string;
    filename: string;
    content_type: string;
    size: number;
    status: "stored" | "extracting" | "ready" | "failed";
    page_count?: number | null;
    chunk_count: number;
    extracted_characters: number;
    error_code?: string | null;
    created_at?: string | null;
    expires_at?: string | null;
};

export type Thoughts = {
    title: string;
    description: any; // It can be any output from the api
    props?: { [key: string]: any };
};
export type ActionVariant = "contained" | "outlined" | "text";
export interface ActionButton {
    id: string;
    label: string;
    variant?: ActionVariant;
    disabled?: boolean;
}

export type ResponseContext = {
    data_points: string[];
    followup_questions: string[] | null;
    thoughts: Thoughts[];
    actions?: ActionButton[];
    chartUrl?: string;
    chart?: ChartSpec; // ⭐ CHART CAPABILITY: mui-x-charts native props spec ที่ backend คืนมา
    diagram?: {
        format: "drawio" | "mermaid";
        filename: string;
        mime_type: string;
        content: string;
    };
};

export type ChatAppResponseOrError = {
    message: ResponseMessage;
    delta: ResponseMessage;
    context: ResponseContext;
    session_state: any;
    error?: string;
};

export type ChatAppResponse = {
    message: ResponseMessage;
    delta: ResponseMessage;
    context: ResponseContext;
    session_state: any;
};

export type ChatAppRequestContext = {
    overrides?: ChatAppRequestOverrides;
};

export type ChatAppRequest = {
    usage_request_id?: string;
    messages: ResponseMessage[];
    attachments?: ChatAttachmentInput[];
    document_attachment_ids?: string[];
    evidence_matrix?: boolean;
    attachment_evidence_scope?: AttachmentEvidenceScope;
    conversation_id: string;
    context?: ChatAppRequestContext;
    session_state: any;
    gid?: string;
    agent_name?: string;
    agent_id?: string;
    team_id?: string | null;
    data_groups_id?: string[] | null;
    selected_scopes?: any[] | null;
    api_result?: any;
};

export type AttachmentEvidenceScope = "uploaded_only" | "knowledge_only" | "both";

export type EvidenceMatrixOptions = {
    evidenceMatrix: boolean;
    attachmentEvidenceScope: AttachmentEvidenceScope;
};

export type Config = {
    runtimeMode?: "azure" | "local";
    knowledgeStorageProvider?: "azure" | "minio";
    knowledgeSearchProvider?: "azure" | "qdrant";
    agentRuntimeMode?: "legacy" | "langgraph" | "per_agent";
    webSearchProvider?: "brave" | "searxng" | null;
    webSearchConfigured?: boolean;
    llmProvider?: string;
    embeddingProvider?: string;
    embeddingProfileId?: string;
    embeddingModel?: string;
    embeddingDimensions?: number;
    llmProfiles: LLMProfile[];
    defaultReasoningEffort: string;
    showGPT4VOptions: boolean;
    showSemanticRankerOption: boolean;
    showQueryRewritingOption: boolean;
    showReasoningEffortOption: boolean;
    streamingEnabled: boolean;
    showVectorOption: boolean;
    showUserUpload: boolean;
    showLanguagePicker: boolean;
    showSpeechInput: boolean;
    showSpeechOutputBrowser: boolean;
    showSpeechOutputAzure: boolean;
    showChatHistoryBrowser: boolean;
    showChatHistoryCosmos: boolean;
    showChatHistoryDatabase: boolean;
    showAgenticRetrievalOption: boolean;
    chatDocumentAttachmentsEnabled: boolean;
    maxUploadSizeBytes: number;
};

export type LLMProfile = {
    id: string;
    label: string;
    provider: string;
    model: string;
    managedProviderId?: string;
    managedModelId?: string;
    quotaProviderId?: string;
    supportsTools?: boolean;
    supportsVision?: boolean;
};

export type LLMProviderModel = {
    id: string;
    label: string;
    model: string;
    deployment?: string | null;
    supports_tools?: boolean;
    tool_capability_status?: "unknown" | "supported" | "unsupported";
    tool_capability_checked_at?: string;
    tool_capability_detail?: string;
    supports_vision?: boolean;
    vision_capability_status?: "unknown" | "supported" | "unsupported";
    vision_capability_checked_at?: string;
    vision_capability_detail?: string;
};

export type LLMVendor =
    | "azure_openai"
    | "openai"
    | "google_gemini"
    | "anthropic_claude"
    | "ollama"
    | "groq"
    | "openrouter"
    | "mistral"
    | "deepseek"
    | "together"
    | "vllm"
    | "localai"
    | "other_openai_compatible";

export type LLMProviderAdapter = "azure_openai" | "openai" | "openai_compatible";

export type ManagedLLMProvider = {
    _id: string;
    name: string;
    vendor: LLMVendor;
    vendor_label: string;
    provider: LLMProviderAdapter;
    endpoint?: string | null;
    base_url?: string | null;
    api_version?: string | null;
    organization?: string | null;
    models: LLMProviderModel[];
    enabled: boolean;
    has_api_key: boolean;
    create_at?: string | null;
    update_at?: string | null;
};

export type LLMProviderPayload = Omit<ManagedLLMProvider, "_id" | "vendor_label" | "has_api_key" | "create_at" | "update_at"> & {
    api_key?: string;
    clear_api_key?: boolean;
};

export type EmbeddingProviderAdapter = "azure_openai" | "openai" | "openai_compatible";

export type ManagedEmbeddingProfile = {
    _id: string;
    name: string;
    provider: EmbeddingProviderAdapter;
    model: string;
    deployment?: string | null;
    dimensions: number;
    collection_name: string;
    endpoint?: string | null;
    base_url?: string | null;
    api_version?: string | null;
    organization?: string | null;
    enabled: boolean;
    has_api_key: boolean;
    environment: boolean;
    created_at?: string | null;
    updated_at?: string | null;
};

export type EmbeddingProfilePayload = Omit<ManagedEmbeddingProfile, "_id" | "has_api_key" | "environment" | "created_at" | "updated_at"> & {
    api_key?: string;
    clear_api_key?: boolean;
};

export type EmbeddingProfileSettings = {
    active_profile_id: string;
    runtime_profile_id: string;
    restart_required: boolean;
    reindex_required: boolean;
    activated_at?: string | null;
    runtime_started_at?: string | null;
};

export interface ManagedMCPServer {
    _id: string;
    team_id: string;
    name: string;
    url: string;
    vendor: "generic" | "datadog" | "azure" | "drawio" | "atlassian" | "servicenow";
    category: MCPCategory;
    auth_type: "headers" | "bearer" | "datadog_keys" | "entra_client_credentials";
    deployment_mode: "external" | "managed";
    operation_mode: "read_only" | "read_write";
    enabled: boolean;
    allowed_tools: string[];
    timeout_seconds: number;
    has_headers: boolean;
    entra_tenant_id?: string;
    entra_client_id?: string;
    entra_scope?: string;
    has_entra_client_secret?: boolean;
    azure_tenant_id?: string;
    azure_client_id?: string;
    azure_subscription_ids?: string[];
    has_azure_client_secret?: boolean;
    provisioning_status?: "external" | "pending" | "ready" | "stopped" | "stop_pending" | "cleanup_pending" | "failed" | "deleted";
    provisioning_error?: string;
    agent_usage_count?: number;
    create_at?: string;
    update_at?: string;
}

export interface MCPServerPayload {
    team_id: string;
    name: string;
    url: string;
    vendor: "generic" | "datadog" | "azure" | "drawio" | "atlassian" | "servicenow";
    category: MCPCategory;
    auth_type: "headers" | "bearer" | "datadog_keys" | "entra_client_credentials";
    deployment_mode: "external" | "managed";
    operation_mode: "read_only" | "read_write";
    enabled: boolean;
    allowed_tools: string[];
    timeout_seconds: number;
    headers?: Record<string, string>;
    clear_headers?: boolean;
    entra_tenant_id?: string;
    entra_client_id?: string;
    entra_client_secret?: string;
    clear_entra_client_secret?: boolean;
    entra_scope?: string;
    azure_tenant_id?: string;
    azure_client_id?: string;
    azure_client_secret?: string;
    clear_azure_client_secret?: boolean;
    azure_subscription_ids?: string[];
}

export type MCPCategory = "observability" | "diagram_collaboration" | "cloud_platform" | "developer_tools" | "business_workflows" | "data_search" | "custom";

export type IntegrationKind = "rest_api" | "database" | "mail" | "messaging" | "mcp" | "business_documents" | "web_search";

export interface IntegrationConnectionSummary {
    id: string;
    kind: IntegrationKind;
    connection_type: "mcp" | "native";
    provider: string;
    name: string;
    team_id: string;
    enabled: boolean;
    status: string;
    detail: string;
    agent_usage_count: number;
}

export type SystemHealthStatus = "healthy" | "configured" | "degraded" | "unavailable" | "not_configured" | "running" | "stopped" | "unknown";

export interface SystemHealthService {
    id: string;
    name: string;
    status: SystemHealthStatus;
    detail: string;
    provider: string;
    latency_ms?: number;
}

export interface SystemHealthSnapshot {
    status: "healthy" | "degraded";
    checked_at: string;
    services: SystemHealthService[];
    resources: {
        scope: "runtime_environment";
        scope_label: string;
        status: "healthy" | "warning" | "critical" | "unavailable";
        cpu?: { usage_percent: number; logical_cores: number; load_average_1m: number | null };
        memory?: { used_bytes: number; total_bytes: number; available_bytes: number; usage_percent: number };
        disk?: { mount: string; used_bytes: number; total_bytes: number; free_bytes: number; usage_percent: number };
        process?: { resident_memory_bytes: number };
        thresholds?: { warning_percent: number; critical_percent: number };
    };
    integrations: {
        total: number;
        enabled: number;
        disabled: number;
        attention: number;
        by_kind: Array<{ kind: IntegrationKind; total: number; enabled: number; attention: number }>;
    };
    jobs: {
        ingestion: { queued: number; processing: number; failed: number; worker_status: SystemHealthStatus };
        attachments: { queued: number; processing: number; failed: number; worker_status: SystemHealthStatus; cleanup_status: SystemHealthStatus };
        agent_invocations: { queued: number; processing: number; failed: number; worker_status: SystemHealthStatus };
    };
}

export type LicenseStatus = "unlicensed" | "active" | "grace" | "expired" | "revoked" | "invalid";

export interface LicenseStatusResponse {
    status: LicenseStatus;
    reason: string;
    source: "none" | "trial" | "license";
    installation_id: string;
    audit_mode: boolean;
    trial_available: boolean;
    evaluated_at?: string;
    trial?: {
        started_at: string;
        expires_at: string;
        duration_days: number;
    };
    license?: {
        license_id: string;
        customer_id: string;
        product: string;
        edition: string;
        issuer: string;
        key_id: string;
        not_before: string;
        expires_at: string;
        grace_days: number;
        features: Record<string, boolean>;
        capacities: Record<string, number | null>;
        installation_id?: string | null;
    };
}

export interface AgentToolPolicy {
    max_total_calls: number;
    max_calls_per_tool: number;
    max_argument_chars: number;
    max_output_chars: number;
    max_timeout_seconds: number;
    blocked_tools: string[];
    blocked_sources: string[];
}

export interface AgentAuditEvent {
    _id: string;
    run_id: string;
    parent_run_id?: string;
    agent_id: string;
    team_id?: string;
    actor_id: string;
    event_type: string;
    status: string;
    tool_name?: string;
    source?: string;
    details: Record<string, unknown>;
    created_at: string;
}

export type SimpleAPIResponse = {
    message?: string;
    jobs?: IngestionJob[];
};

export type IngestionJobStatus = "uploaded" | "extracting" | "chunking" | "embedding" | "indexed" | "failed";

export interface IngestionJob {
    _id: string;
    scope: "personal" | "team" | "global";
    team_id: string;
    filename: string;
    file_size: number;
    status: IngestionJobStatus;
    attempt: number;
    route_source: string;
    profile_id: string;
    profile_name: string;
    provider_id: string;
    provider_name: string;
    rule_id: string;
    rule_name: string;
    error?: { code: string; message: string } | null;
    result_message?: string;
    stage_history: Array<{ status: IngestionJobStatus; at: string | null }>;
    created_at: string;
    updated_at: string;
    started_at?: string | null;
    completed_at?: string | null;
}

export interface SpeechConfig {
    speechUrls: (string | null)[];
    setSpeechUrls: (urls: (string | null)[]) => void;
    audio: HTMLAudioElement;
    isPlaying: boolean;
    setIsPlaying: (isPlaying: boolean) => void;
}

export type HistoryListApiResponse = {
    sessions: {
        id: string;
        entra_oid: string;
        title: string;
        timestamp: number;
    }[];
    continuation_token?: string;
};

export type HistoryApiResponse = {
    id: string;
    entra_oid: string;
    answers: any;
};

export type GroupPrompt = {
    role: string;
    task: string;
    detail_context: string;
    output_format: string;
    constraints: string;
};

export type GroupDetail = {
    _id: string;
    name: string;
    agent_name?: string;
    group_promt: GroupPrompt;
    create_at: string;
    update_at: string;
    delete_at: string | null;
};

export type UserProfile = {
    _id: string;
    name: string;
    groups: GroupDetail[];
    role_id: string;
    role_name: string;
    create_at: string;
    update_at: string;
    delete_at: string;
    activeGroup?: GroupDetail | null; // 👈 เพิ่มตรงนี้
};

export type RoleDetail = {
    _id: string;
    name: string;
    create_at: string;
    update_at: string;
    delete_at: string;
};

export type UserProfileWithActiveGroup = UserProfile & {
    activeGroup?: GroupDetail | null;
};

export interface FeedbackPayload {
    sentiment: "like" | "dislike";
    question_text: string;
    answer_text: string;
    session_state?: string | null;
    answer_index?: number;
    agent_name?: string | null;
    metadata?: Record<string, any>;
}

export interface AgentConfig {
    _id?: string;
    name?: string;
    description?: string;
    is_active?: boolean;

    // 🆕 เพิ่ม
    temperature?: number;
    seed?: number | null;
    min_search_score?: number;
    max_search_results?: number;
    max_tokens?: number | null;
    llm_profile_id?: string;
    runtime?: "legacy" | "langgraph";
    image_input_enabled?: boolean;
    document_attachments_enabled?: boolean;
    tool_settings?: AgentToolSettings;
    guardrails?: AgentGuardrailPolicy;

    create_at?: string;
    update_at?: string;
    delete_at?: string;

    groups?: GroupDetail[];
}

export interface User {
    _id: string;
    active: boolean;
    ad_email: string;
    create_at?: string;
    delete_at?: string;
    email: string;
    employee_id: string;
    first_name: string;
    is_sys_admin?: boolean;
    last_name: string;
    tel?: string;
    update_at?: string;
    local_username?: string;
    local_password?: string;
    auth_providers?: string[];
}

export interface AuthProfile {
    teams: TeamProfile[];
    user: User;
    sys_permissions: string[];
}

export interface AuthenticationSettings {
    local_enabled: boolean;
    entra_enabled: boolean;
    tenant_id: string;
    server_app_id: string;
    client_app_id: string;
    has_client_secret: boolean;
    oidc_enabled: boolean;
    oidc_display_name: string;
    oidc_issuer: string;
    oidc_client_id: string;
    oidc_client_secret?: string;
    oidc_token_auth_method: "client_secret_basic" | "client_secret_post";
    oidc_has_client_secret: boolean;
    oidc_jit_enabled: boolean;
    oidc_allowed_domains: string[];
    oidc_callback_url?: string;
    source?: "environment" | "managed";
}

export interface OIDCProvider {
    id: string;
    enabled: boolean;
    display_name: string;
    issuer: string;
    client_id: string;
    client_secret?: string;
    token_auth_method: "client_secret_basic" | "client_secret_post";
    jit_enabled: boolean;
    allowed_domains: string[];
    has_client_secret: boolean;
    legacy?: boolean;
}

export type OIDCProviderPayload = Omit<OIDCProvider, "id" | "has_client_secret" | "legacy"> & {
    client_secret?: string;
    clear_client_secret?: boolean;
};

export interface SAMLProvider {
    id: string;
    enabled: boolean;
    display_name: string;
    entity_id: string;
    sso_url: string;
    x509_cert: string;
    email_attribute: string;
    first_name_attribute: string;
    last_name_attribute: string;
    jit_enabled: boolean;
    allowed_domains: string[];
    acs_url?: string;
    metadata_url?: string;
}

export type SAMLProviderPayload = Omit<SAMLProvider, "acs_url" | "metadata_url">;

export interface OIDCIdentityLinkRequest {
    id: string;
    provider_name: string;
    email: string;
    suggested_user_id: string;
    suggested_user_name: string;
    expires_at?: string;
}

export interface OIDCIdentityLink {
    id: string;
    provider_name: string;
    username: string;
    user_id: string;
    user_name: string;
    active: boolean;
    created_at?: string;
}

export interface IdentityManagementResponse {
    pending: OIDCIdentityLinkRequest[];
    links: OIDCIdentityLink[];
    audit_events: Array<{
        id: string;
        action: string;
        actor_id: string;
        target_user_id: string;
        provider: string;
        created_at?: string;
    }>;
}

export interface TeamProfile {
    _id: string;
    name: string;
    permissions: string[];
}

export interface Team {
    _id: string;
    name: string;
    data_group_id: string[];
    agent_id: string[];
    user_id: string[];
    waiting_approve: User[];
    create_at?: string;
    delete_at?: string;
    update_at?: string;
}

export interface TeamDetail {
    users: User[];
    agents: Agent[];
    data_groups: DataGroupWithView[];
}

export interface DataGroup {
    _id: string;
    name: string;
    update_at?: string;
    create_at?: string;
    delete_at?: string;
    user_id: string[];
    access_mode?: "team" | "selected_users";
}

export interface EffectiveDataGroup {
    _id: string;
    name: string;
    access_mode: "team" | "selected_users";
    member_count: number;
}

export interface EffectiveAccessResponse {
    user_id: string;
    team: { _id: string; name: string };
    data_groups: EffectiveDataGroup[];
    selected_data_group_ids: string[];
    selected_scopes: Array<"global" | "personal">;
    agent_id?: string | null;
    is_system_admin: boolean;
}

export interface DataGroupDisplay {
    _id: string;
    name: string;
    update_at?: string;
    create_at?: string;
    delete_at?: string;
    user_id: User[];
    access_mode: "team" | "selected_users";
}

export interface DataGroupWithView {
    _id: string;
    name: string;
    create_at?: string;
    update_at?: string;
    delete_at?: string;
    users: User[];
}

export interface AgentConf {
    temperature?: number;
    seed?: number | null;
    min_search_score?: number;
    max_search_results?: number;
    max_tokens?: number | null;
    llm_profile_id?: string;
    runtime?: "legacy" | "langgraph";
    image_input_enabled?: boolean;
    document_attachments_enabled?: boolean;
    tool_settings?: AgentToolSettings;
    guardrails?: AgentGuardrailPolicy;
}

export interface AgentGuardrailPolicy {
    enabled: boolean;
    max_input_chars: number;
    prompt_injection_action: "allow" | "warn" | "block";
    sensitive_input_action: "allow" | "warn" | "block";
    sensitive_output_action: "allow" | "warn" | "redact" | "block";
    pii_input_action: "allow" | "warn" | "block";
    pii_output_action: "allow" | "warn" | "redact" | "block";
    content_safety_input_action: "allow" | "warn" | "block";
    content_safety_output_action: "allow" | "warn" | "block";
    blocked_phrases: string[];
}

export interface GuardrailSettingsResponse {
    configured: boolean;
    policy: AgentGuardrailPolicy;
    system_policy?: AgentGuardrailPolicy | null;
    effective_policy?: AgentGuardrailPolicy;
}

export interface ChatHistoryRetentionSettingsResponse {
    configured_days: number | null;
    effective_days: number;
    system_days?: number;
}

export interface LLMTokenQuotaRule {
    dimension: "provider" | "profile";
    target_id: string;
    target_label: string;
    workload: "all" | "chat" | "ask";
    monthly_tokens: number;
    enabled: boolean;
}

export interface UsageQuotaPolicy {
    enabled: boolean;
    monthly_llm_tokens: number;
    monthly_llm_tokens_per_user: number;
    monthly_document_pages: number;
    llm_requests_per_minute: number;
    llm_token_rules: LLMTokenQuotaRule[];
}

export interface UsageQuotaSettingsResponse {
    configured: boolean;
    policy: UsageQuotaPolicy;
    effective_policy?: UsageQuotaPolicy;
    member_limit_source?: "" | "team_default" | "override";
    effective_member_limit?: number;
    usage?: { monthly_llm_tokens: number; monthly_document_pages: number };
    rule_usage?: Array<Pick<LLMTokenQuotaRule, "dimension" | "target_id" | "workload"> & { monthly_tokens: number }>;
    status?: Array<{
        kind: string;
        label: string;
        used: number;
        reserved: number;
        limit: number;
        percentage: number;
        severity: "normal" | "warning" | "critical" | "exceeded";
    }>;
    audit_events?: Array<{
        _id: string;
        event_type: "quota_threshold" | "quota_blocked" | "metering_failed";
        level: "system" | "team" | "user" | "team_user";
        subject_id: string;
        limit: number;
        projected: number;
        threshold: number;
        created_at: string;
        provider_id?: string;
        profile_id?: string;
        workload?: string;
    }>;
}

export interface AgentToolSettings {
    knowledge_search: "auto" | "always" | "disabled";
    external_database: boolean;
    rest_integrations: boolean;
    mail: boolean;
    business_documents: boolean;
    messaging: boolean;
    mcp: boolean;
    mcp_execution: "auto" | "required";
    web_search: boolean;
    web_search_connection_id: string;
    web_search_allowed_domains: string[];
    web_search_max_results: number;
    web_search_timeout_seconds: number;
    subagents: boolean;
    mcp_server_ids: string[];
    mcp_tool_allowlists: Record<string, string[]>;
    mcp_timeout_seconds: number;
    subagent_ids: string[];
    subagent_max_depth: number;
    tool_policy: AgentToolPolicy;
}

export interface Prompt {
    role: string;
    task: string;
    detail_context: string;
    output_format: string;
    constraints: string;
}
export interface Agent {
    _id: string;
    agent_name: string;
    create_at?: string;
    update_at?: string;
    delete_at?: string;
    lifecycle_status?: "active" | "draft";
    draft_expires_at?: string | null;
    config: AgentConf;
    prompt: Prompt;
}

export interface AgentCatalogItem {
    _id: string;
    name: string;
    summary: string;
    usage_instructions: string;
    tags: string[];
    category: string;
    publisher_team: { _id: string; name: string };
    publisher_type: "team" | "system";
    created_by: { _id: string; name: string };
    visibility: "team" | "selected_teams" | "all_teams";
    status: "published" | "unpublished";
    latest_version: number;
    requirements: {
        llm_profile_id?: string;
        runtime?: string;
        uses_knowledge?: boolean;
        declared_tools?: string[];
    };
    installed: boolean;
    installed_version?: number | null;
    update_available?: boolean;
    installed_agent_id?: string | null;
    source_agent_id?: string;
    allowed_team_ids?: string[];
    updated_at?: string;
}

export interface UserPermission {
    _id?: string;
    team_id?: string;
    user_id?: string;
    create_at?: string;
    update_at?: string;
    delete_at?: string;
    permission_id: string[];
}

export interface Permission {
    _id?: string;
    name: string;
    type: string;
    create_at?: string;
    update_at?: string;
    delete_at?: string;
}

export interface UserPermissionWithDisplay {
    _id?: string;
    team_id?: string;
    user_id?: string;
    create_at?: string;
    update_at?: string;
    delete_at?: string;
    permission_id: Permission[];
}

export interface RegisterUserPayload {
    email: string;
    first_name: string;
    last_name: string;
    employee_id: string;
    tel?: string;
}

export type Role = {
    _id?: string;
    name: string;
    permission_id: string[];
    team_id?: string;
    create_at?: string;
    update_at?: string;
    delete_at?: string;
};

export interface IntegrationEndpoint {
    name: string;
    method: "GET" | "POST";
    path: string;
}

export type IntegrationType = "external_api" | "database" | "line" | "google_sheet";

export interface Integration {
    _id: string;
    name: string;
    type: "rest" | "line" | "google_sheet" | "database";
    endpoints: IntegrationEndpoint[];
}

export interface FieldSchema {
    field: string;
    description: string;
    location: "query" | "path" | "body";
}

export interface ResponseField {
    field: string;
    description: string;
}

export interface BindingInput {
    integration_id: string;
    endpoint_name: string;
    trigger_keywords: string[];
    async: boolean;
    integration_type: "rest" | "line" | "google_sheet" | "database";
    enabled?: boolean;

    request_fields: FieldSchema[];
    response_fields: ResponseField[];
}

export interface DatabaseBindingData {
    _id: string;
    agent_id: string;
    integration_id: string;
    alias: string;
    trigger_keywords: string[];
    enabled: boolean;
    query_profile?: DatabaseQueryProfile;
}

export interface DatabaseQueryProfile {
    business_context: string;
    business_rules: string;
    glossary: string;
    allowed_objects: string[];
    query_examples: { question: string; query: string }[];
}

export interface MailBindingData {
    _id: string;
    agent_id: string;
    email_id: string;
    is_html: boolean;
    enabled: boolean;
    permissions: Array<"read" | "send">;
    allowed_recipient_domains: string[];
    max_recipients: number;
    // Mail template
    subject: string;
    body: string;
    default_to: string[];
    default_cc: string[];
    default_bcc: string[];
}

// ─── Chart Capability Binding ────────────────────────────────────────────────
export type ChartType =
    | "bar"
    | "line"
    | "pie"
    | "area"
    | "scatter"
    | "radar"
    | "heatmap"
    | "treemap"
    | "sunburst"
    | "gauge"
    | "funnel"
    | "boxplot"
    | "candlestick"
    | "sankey"
    | "graph"
    | "bar3D"
    | "line3D"
    | "scatter3D"
    | "surface"
    | "pictorialBar"
    | "parallel"
    | "themeRiver"
    | "calendar";

export type ChartSelectionMode = "auto" | "manual";

export interface ChartBindingData {
    _id: string;
    agent_id: string;
    enabled: boolean;
    // v2 fields
    chart_selection_mode: ChartSelectionMode; // "auto" = LLM เลือกเอง, "manual" = enforce allowed list
    auto_generate: boolean; // true = สร้างอัตโนมัติเมื่อมีข้อมูล, false = รอ user สั่ง
    // shared styling
    color_palette?: string[];
    title_template?: string;
    trigger_keywords?: string[];
    // v1 fields — backward compat, ignored when chart_selection_mode="auto"
    default_chart_type?: ChartType;
    allowed_chart_types?: ChartType[];
}

// ⭐ CHART CAPABILITY: chart spec ที่ backend/LLM คืนกลับมา
//    เก็บ mui-x-charts native props ตรงๆ เพื่อ spread ลง component ได้ทันที
export interface ChartSpec {
    chartType: ChartType;
    data?: ChartDataAudit;
    // native props ที่จะ spread ลง component ตรงๆ เช่น { dataset, series, xAxis, height }
    [key: string]: any;
}

export interface ChartDataAudit {
    sourceTool: string;
    sourceType: string;
    categoryField: string;
    valueFields: string[];
    columns: string[];
    rows: Array<Record<string, unknown>>;
    rowCount: number;
    sourceRowCount: number;
    sourceRecordCount?: number;
    aggregateRowCount?: number;
    fullDataset?: boolean;
    resultTruncated?: boolean;
    aggregation?: {
        type?: string;
        method?: string;
        aggregation?: string;
        metric?: string;
        statistic?: string;
        [key: string]: unknown;
    };
    query?: string | Record<string, unknown>;
}

export interface AuthConfig {
    type: "none" | "api_key" | "bearer";
    header?: string;
    value?: string;
}
export interface Endpoint {
    name: string;
    method: "GET" | "POST";
    path: string;
}

export interface ExternalApi {
    _id: string;
    team_id: string;
    name: string;
    base_url: string;
    type: string;

    auth: AuthConfig;

    endpoints: Endpoint[];
    agent_usage_count?: number;
}

export type DbType = "postgresql" | "mysql" | "mssql" | "mongodb" | "sqlite";

export interface DatabaseConnectionOptions {
    ssl_mode?: "disable" | "prefer" | "require" | "verify-ca" | "verify-full";
    auth_source?: string;
    tls?: boolean;
    connect_timeout_seconds?: number;
}

export interface DatabaseConnection {
    _id: string;
    team_id: string;
    name: string;
    db_type: DbType;
    host: string;
    port: number;
    database: string;
    username: string;
    password?: string;
    has_password?: boolean;
    agent_usage_count?: number;
    options?: DatabaseConnectionOptions;
}

export type MailProvider = "microsoft365" | "gmail" | "generic";
export type MailReceiveProtocol = "imap" | "pop3";
export type MailSecurity = "ssl" | "starttls" | "none";

export interface MailPublicConfig {
    tenant_id?: string;
    client_id?: string;
    username?: string;
    receive_protocol?: MailReceiveProtocol;
    receive_host?: string;
    receive_port?: number;
    receive_security?: MailSecurity;
    smtp_host?: string;
    smtp_port?: number;
    smtp_security?: MailSecurity;
}

export interface MailEmailConfig {
    _id: string;
    team_id: string;
    name: string;
    provider: MailProvider;
    email_address: string;
    public_config: MailPublicConfig;
    enabled: boolean;
    has_credentials?: boolean;
    agent_usage_count?: number;
}

export type WebSearchProvider = "brave" | "searxng";
export interface WebSearchConnection {
    _id: string;
    team_id: string;
    name: string;
    provider: WebSearchProvider;
    base_url: string;
    timeout_seconds: number;
    enabled: boolean;
    has_api_key?: boolean;
    agent_usage_count?: number;
}

export type BusinessDocumentProvider = "microsoft365" | "google_workspace";
export interface BusinessDocumentPublicConfig {
    tenant_id?: string;
    client_id?: string;
    drive_id?: string;
    root_folder_id?: string;
    shared_drive_id?: string;
}
export interface BusinessDocumentConnection {
    _id: string;
    team_id: string;
    name: string;
    provider: BusinessDocumentProvider;
    public_config: BusinessDocumentPublicConfig;
    operation_mode: "read_only" | "read_write";
    enabled: boolean;
    has_credentials?: boolean;
    agent_usage_count?: number;
}
export interface BusinessDocumentBindingData {
    _id: string;
    agent_id: string;
    connection_id: string;
    enabled: boolean;
    permissions: Array<"read" | "create">;
}

export type MessagingProvider = "line" | "slack" | "discord";
export interface MessagingConnection {
    _id: string; team_id: string; name: string; provider: MessagingProvider;
    public_config: { default_target?: string }; enabled: boolean;
    has_credentials?: boolean; agent_usage_count?: number;
}
export interface MessagingBindingData {
    _id: string; agent_id: string; connection_id: string; enabled: boolean;
    default_target: string; message_template: string;
}
export interface DocumentProcessingProvider {
    _id: string; name: string;
    provider_type: "azure_document_intelligence" | "docling" | "google_document_ai" | "generic_ocr_api" | "paddleocr" | "local_text";
    config: Record<string, unknown>; enabled: boolean; system_managed: boolean; has_credentials?: boolean;
}
export interface DocumentProcessingProfile {
    _id: string; name: string; provider_id: string; file_types: string[];
    languages: string[]; extract_tables: boolean; is_default: boolean; enabled: boolean;
}
export interface DocumentProcessingRoutingRule {
    _id: string; name: string; scope: "all" | "personal" | "team" | "global";
    team_id: string; file_types: string[]; profile_id: string; priority: number;
    enabled: boolean; fallback_behavior: "continue" | "system" | "error";
}
export interface DocumentProcessingUploadOptions {
    can_override: boolean;
    profiles: DocumentProcessingProfile[];
}

export interface AgentInvocationKey {
    _id: string;
    team_id: string;
    name: string;
    key_prefix: string;
    allowed_agent_ids: string[];
    allowed_data_group_ids: string[];
    allow_global_knowledge: boolean;
    rate_limit_per_minute: number;
    active: boolean;
    expires_at: string;
    created_at: string;
    created_by: string;
    last_used_at?: string | null;
    revoked_at?: string | null;
    replaced_by?: string | null;
}

export interface AgentInvocationKeyOptions {
    items: AgentInvocationKey[];
    available_agents: Array<{ _id: string; name: string; runtime: string }>;
    available_data_groups: Array<{ _id: string; name: string }>;
}

export interface AgentInvocationKeyCreatePayload {
    name: string;
    allowed_agent_ids: string[];
    allowed_data_group_ids: string[];
    allow_global_knowledge: boolean;
    expiry_days: number;
    rate_limit_per_minute: number;
}

export interface AgentInvocationKeyCreatedResponse {
    item: AgentInvocationKey;
    api_key: string;
}
