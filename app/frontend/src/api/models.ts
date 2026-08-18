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
    messages: ResponseMessage[];
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

export type Config = {
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
    showAgenticRetrievalOption: boolean;
};

export type SimpleAPIResponse = {
    message?: string;
};

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
}

export interface AuthProfile {
    teams: TeamProfile[];
    user: User;
    sys_permissions: string[];
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
}

export interface DataGroupDisplay {
    _id: string;
    name: string;
    update_at?: string;
    create_at?: string;
    delete_at?: string;
    user_id: User[];
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
    config: AgentConf;
    prompt: Prompt;
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
}

export interface MailBindingData {
    _id: string;
    agent_id: string;
    email_id: string;
    is_html: boolean;
    enabled: boolean;
    // Mail template
    subject: string;
    body: string;
    default_to: string[];
    default_cc: string[];
    default_bcc: string[];
}

// ─── Chart Capability Binding ────────────────────────────────────────────────
export type ChartType =
    | "bar" | "line" | "pie" | "area" | "scatter"
    | "radar" | "heatmap" | "treemap" | "sunburst" | "gauge"
    | "funnel" | "boxplot" | "candlestick" | "sankey" | "graph"
    | "bar3D" | "line3D" | "scatter3D" | "surface"
    | "pictorialBar" | "parallel" | "themeRiver" | "calendar";

export type ChartSelectionMode = "auto" | "manual";

export interface ChartBindingData {
    _id: string;
    agent_id: string;
    enabled: boolean;
    // v2 fields
    chart_selection_mode: ChartSelectionMode; // "auto" = LLM เลือกเอง, "manual" = enforce allowed list
    auto_generate: boolean;                   // true = สร้างอัตโนมัติเมื่อมีข้อมูล, false = รอ user สั่ง
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
    // native props ที่จะ spread ลง component ตรงๆ เช่น { dataset, series, xAxis, height }
    [key: string]: any;
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
}

export type DbType = "postgresql" | "mysql" | "mssql" | "mongodb";

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
}

export type MailProtocol = "SMTP" | "IMAP";

export type MailEncryption = "STARTTLS" | "SSL" | "None";

export interface MailEmailConfig {
    _id: string;
    team_id: string;
    name: string;
    email: string;
    password?: string;
    server: string;
    port: number;
    protocol: MailProtocol;
    encryption: MailEncryption;
}
