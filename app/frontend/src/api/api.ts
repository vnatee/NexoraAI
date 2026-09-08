const BACKEND_URI = "";

import {
    ChatAppResponse,
    ChatAppResponseOrError,
    ChatAppRequest,
    Config,
    SimpleAPIResponse,
    HistoryListApiResponse,
    HistoryApiResponse,
    UserProfile,
    RoleDetail,
    GroupDetail,
    GroupPrompt,
    FeedbackPayload,
    AgentConfig,
    LLMProviderPayload,
    ManagedLLMProvider,
    ManagedMCPServer,
    MCPServerPayload,
    AgentAuditEvent,
    User,
    RegisterUserPayload,
    Prompt,
    DatabaseConnection,
    MailEmailConfig,
    IngestionJob,
    ChatDocumentAttachment,
    EffectiveAccessResponse,
    AuthenticationSettings,
    AgentGuardrailPolicy,
    UsageQuotaPolicy,
    UsageQuotaSettingsResponse,
    GuardrailSettingsResponse,
    ChatHistoryRetentionSettingsResponse
} from "./models";
import { useLogin, getToken, isUsingAppServicesLogin } from "../authConfig";

export async function getHeaders(idToken: string | undefined): Promise<Record<string, string>> {
    if (idToken?.startsWith("nx_local_")) {
        return { Authorization: `Bearer ${idToken}` };
    }
    // If using login and not using app services, add the id token of the logged in account as the authorization
    if (useLogin && !isUsingAppServicesLogin) {
        if (idToken) {
            return { Authorization: `Bearer ${idToken}` };
        }
    }

    return {};
}

export async function getAuthenticationSettings(idToken: string): Promise<AuthenticationSettings> {
    const response = await fetch("/admin/auth-settings", { headers: await getHeaders(idToken) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load authentication settings");
    return data;
}

export async function updateAuthenticationSettings(
    settings: Partial<AuthenticationSettings> & { client_secret?: string },
    idToken: string
): Promise<AuthenticationSettings> {
    const response = await fetch("/admin/auth-settings", {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(settings)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save authentication settings");
    return data;
}

export async function resetAuthenticationSettings(idToken: string): Promise<void> {
    const response = await fetch("/admin/auth-settings", {
        method: "DELETE",
        headers: await getHeaders(idToken)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to restore environment settings");
}

export async function getGuardrailSettings(
    idToken: string,
    teamId?: string
): Promise<GuardrailSettingsResponse> {
    const path = teamId
        ? `/teams/${encodeURIComponent(teamId)}/guardrail-settings`
        : "/admin/guardrail-settings";
    const response = await fetch(path, { headers: await getHeaders(idToken) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load guardrail settings");
    return data;
}

export async function updateGuardrailSettings(
    policy: AgentGuardrailPolicy,
    idToken: string,
    teamId?: string
): Promise<GuardrailSettingsResponse> {
    const path = teamId
        ? `/teams/${encodeURIComponent(teamId)}/guardrail-settings`
        : "/admin/guardrail-settings";
    const response = await fetch(path, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(policy)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save guardrail settings");
    return data;
}

export async function getChatHistoryRetentionSettings(
    idToken: string,
    teamId?: string
): Promise<ChatHistoryRetentionSettingsResponse> {
    const path = teamId
        ? `/teams/${encodeURIComponent(teamId)}/chat-history-retention`
        : "/admin/chat-history-retention";
    const response = await fetch(path, { headers: await getHeaders(idToken) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load chat history retention settings");
    return data;
}

export async function updateChatHistoryRetentionSettings(
    retentionDays: number,
    idToken: string,
    teamId?: string
): Promise<ChatHistoryRetentionSettingsResponse> {
    const path = teamId
        ? `/teams/${encodeURIComponent(teamId)}/chat-history-retention`
        : "/admin/chat-history-retention";
    const response = await fetch(path, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ retention_days: retentionDays })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save chat history retention settings");
    return data;
}

export async function getQuotaSettings(idToken: string, teamId?: string): Promise<UsageQuotaSettingsResponse> {
    const path = teamId ? `/teams/${encodeURIComponent(teamId)}/quota-settings` : "/admin/quota-settings";
    const response = await fetch(path, { headers: await getHeaders(idToken) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load quota settings");
    return data;
}

export async function updateQuotaSettings(policy: UsageQuotaPolicy, idToken: string, teamId?: string): Promise<UsageQuotaSettingsResponse> {
    const path = teamId ? `/teams/${encodeURIComponent(teamId)}/quota-settings` : "/admin/quota-settings";
    const response = await fetch(path, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(policy)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save quota settings");
    return data;
}

export async function getUserQuotaSettings(idToken: string, userId: string): Promise<UsageQuotaSettingsResponse> {
    const response = await fetch(`/admin/users/${encodeURIComponent(userId)}/quota-settings`, { headers: await getHeaders(idToken) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load user quota settings");
    return data;
}

export async function updateUserQuotaSettings(policy: UsageQuotaPolicy, idToken: string, userId: string): Promise<UsageQuotaSettingsResponse> {
    const response = await fetch(`/admin/users/${encodeURIComponent(userId)}/quota-settings`, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(policy)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save user quota settings");
    return data;
}

export async function getTeamUserQuotaSettings(idToken: string, teamId: string, userId: string): Promise<UsageQuotaSettingsResponse> {
    const response = await fetch(`/teams/${encodeURIComponent(teamId)}/users/${encodeURIComponent(userId)}/quota-settings`, { headers: await getHeaders(idToken) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load Team member quota settings");
    return data;
}

export async function updateTeamUserQuotaSettings(policy: UsageQuotaPolicy, idToken: string, teamId: string, userId: string): Promise<UsageQuotaSettingsResponse> {
    const response = await fetch(`/teams/${encodeURIComponent(teamId)}/users/${encodeURIComponent(userId)}/quota-settings`, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(policy)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save Team member quota settings");
    return data;
}

export async function configApi(): Promise<Config> {
    const response = await fetch(`${BACKEND_URI}/config`, {
        method: "GET"
    });

    return (await response.json()) as Config;
}

async function parseProviderAdminResponse(response: Response): Promise<any> {
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || `LLM provider request failed (${response.status})`);
    }
    return data;
}

export async function listLLMProvidersApi(idToken: string): Promise<ManagedLLMProvider[]> {
    const response = await fetch("/admin/llm-providers", { headers: await getHeaders(idToken) });
    const data = await parseProviderAdminResponse(response);
    return data.providers;
}

export async function createLLMProviderApi(payload: LLMProviderPayload, idToken: string): Promise<ManagedLLMProvider> {
    const response = await fetch("/admin/llm-providers", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return parseProviderAdminResponse(response);
}

export async function updateLLMProviderApi(providerId: string, payload: LLMProviderPayload, idToken: string): Promise<ManagedLLMProvider> {
    const response = await fetch(`/admin/llm-providers/${providerId}`, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return parseProviderAdminResponse(response);
}

export async function deleteLLMProviderApi(providerId: string, idToken: string): Promise<void> {
    const response = await fetch(`/admin/llm-providers/${providerId}`, {
        method: "DELETE",
        headers: await getHeaders(idToken)
    });
    await parseProviderAdminResponse(response);
}

export type LLMProviderTestResult = {
    success: boolean;
    model: string;
    response?: string;
    tool_capability: {
        status: "unknown" | "supported" | "unsupported";
        supports_tools: boolean | null;
        detail: string;
        checked_at?: string;
    };
    vision_capability: {
        status: "unknown" | "supported" | "unsupported";
        supports_vision: boolean | null;
        detail: string;
        checked_at?: string;
    };
};

export async function testLLMProviderApi(providerId: string, modelId: string, idToken: string): Promise<LLMProviderTestResult> {
    const response = await fetch(`/admin/llm-providers/${providerId}/test`, {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId })
    });
    return parseProviderAdminResponse(response);
}

export async function askApi(request: ChatAppRequest, idToken: string | undefined): Promise<ChatAppResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`${BACKEND_URI}/ask`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(request)
    });

    if (response.status > 299 || !response.ok) {
        const errorResponse = await response.json().catch(() => undefined);
        throw Error(errorResponse?.error || `Request failed with status ${response.status}`);
    }
    const parsedResponse: ChatAppResponseOrError = await response.json();
    if (parsedResponse.error) {
        throw Error(parsedResponse.error);
    }

    return parsedResponse as ChatAppResponse;
}

export async function chatApi(request: ChatAppRequest, shouldStream: boolean, idToken: string | undefined): Promise<Response> {
    let url = `${BACKEND_URI}/chat`;
    if (shouldStream) {
        url += "/stream";
    }
    const headers = await getHeaders(idToken);
    return await fetch(url, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(request)
    });
}

async function parseChatAttachmentResponse(response: Response): Promise<any> {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || `Document attachment request failed (${response.status})`);
    }
    return payload;
}

export async function uploadChatDocumentApi(
    file: File,
    conversationId: string,
    uploadId: string,
    agentId: string | undefined,
    idToken: string | undefined
): Promise<ChatDocumentAttachment> {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("conversation_id", conversationId);
    form.append("upload_id", uploadId);
    if (agentId) form.append("agent_id", agentId);
    const response = await fetch(`${BACKEND_URI}/chat/attachments`, {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Idempotency-Key": uploadId },
        body: form
    });
    const payload = await parseChatAttachmentResponse(response);
    return payload.attachment as ChatDocumentAttachment;
}

export async function listChatDocumentsApi(
    conversationId: string,
    idToken: string | undefined
): Promise<ChatDocumentAttachment[]> {
    const query = new URLSearchParams({ conversation_id: conversationId, limit: "20" });
    const response = await fetch(`${BACKEND_URI}/chat/attachments?${query}`, {
        headers: await getHeaders(idToken)
    });
    const payload = await parseChatAttachmentResponse(response);
    return (payload.attachments || []) as ChatDocumentAttachment[];
}

export async function deleteChatDocumentApi(
    attachmentId: string,
    conversationId: string,
    idToken: string | undefined
): Promise<void> {
    const response = await fetch(`${BACKEND_URI}/chat/attachments/${encodeURIComponent(attachmentId)}`, {
        method: "DELETE",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_id: conversationId })
    });
    await parseChatAttachmentResponse(response);
}

export async function getSpeechApi(text: string): Promise<string | null> {
    return await fetch("/speech", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            text: text
        })
    })
        .then(response => {
            if (response.status == 200) {
                return response.blob();
            } else if (response.status == 400) {
                console.log("Speech synthesis is not enabled.");
                return null;
            } else {
                console.error("Unable to get speech synthesis.");
                return null;
            }
        })
        .then(blob => (blob ? URL.createObjectURL(blob) : null));
}

export function getCitationFilePath(citation: string): string {
    return `${BACKEND_URI}/content/${citation}`;
}

export function getTemporaryCitationFilePath(citation: string, conversationId: string): string | undefined {
    const match = citation.match(/chat-attachment-([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})--/i);
    if (!match) return undefined;
    const hashIndex = citation.indexOf("#");
    const hash = hashIndex >= 0 ? citation.slice(hashIndex) : "";
    const query = new URLSearchParams({ conversation_id: conversationId });
    return `${BACKEND_URI}/chat/attachments/${match[1]}/content?${query}${hash}`;
}

async function uploadErrorMessage(response: Response): Promise<string> {
    try {
        const payload = await response.json();
        if (typeof payload?.error === "string" && payload.error.trim()) return payload.error;
        if (typeof payload?.message === "string" && payload.message.trim()) return payload.message;
    } catch {
        // Reverse proxies can return an HTML or empty error body.
    }
    if (response.status === 413) return "Upload request is larger than the server limit.";
    return `Uploading files failed (${response.status} ${response.statusText})`;
}

export async function uploadFileApi(request: FormData, idToken: string): Promise<SimpleAPIResponse> {
    const response = await fetch("/upload", {
        method: "POST",
        headers: await getHeaders(idToken),
        body: request
    });

    if (!response.ok) throw new Error(await uploadErrorMessage(response));

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function uploadGlobalFileApi(request: FormData, idToken: string): Promise<SimpleAPIResponse> {
    const response = await fetch("/global_upload", {
        method: "POST",
        headers: await getHeaders(idToken),
        body: request
    });

    if (!response.ok) throw new Error(await uploadErrorMessage(response));

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function listIngestionJobsApi(
    idToken: string,
    filters: { scope?: "personal" | "team" | "global"; teamId?: string; limit?: number } = {}
): Promise<IngestionJob[]> {
    const query = new URLSearchParams();
    if (filters.scope) query.set("scope", filters.scope);
    if (filters.teamId) query.set("team_id", filters.teamId);
    query.set("limit", String(filters.limit ?? 10));
    const response = await fetch(`/ingestion-jobs?${query}`, { headers: await getHeaders(idToken) });
    if (!response.ok) throw new Error(`Loading ingestion jobs failed: ${response.statusText}`);
    const payload = await response.json();
    return payload.jobs ?? [];
}

export async function retryIngestionJobApi(jobId: string, idToken: string): Promise<IngestionJob> {
    const response = await fetch(`/ingestion-jobs/${jobId}/retry`, {
        method: "POST",
        headers: await getHeaders(idToken)
    });
    if (!response.ok) throw new Error(`Retrying ingestion failed: ${response.statusText}`);
    const payload = await response.json();
    return payload.job;
}

export type ScrapingAPIResponse = {
    message?: string;
    [key: string]: any; // รองรับ fields อื่นๆ จาก backend
};

export type ErrorResponse = {
    error?: string;
    status?: string;
    message?: string;
};

export async function scrapingApi(url: string, idToken: string, team_id?: string | null, data_groups_id?: string[]): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    // ✨ เตรียม body แบบ dynamic
    const body: any = { url };
    if (team_id) {
        body.team_id = team_id; // เพิ่ม team_id เฉพาะถ้ามีค่า
        if (data_groups_id && data_groups_id.length > 0) {
            body.data_groups_id = data_groups_id; // เพิ่ม data_group_id เฉพาะถ้ามีค่า
        }
    }

    const response = await fetch("/scrape", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });

    if (!response.ok) {
        // พยายาม parse error response จาก backend
        try {
            const errorData: ErrorResponse = await response.json();

            // ใช้ error message จาก backend ถ้ามี
            let errorMessage = `Scraping data failed: ${response.statusText}`;

            if (errorData.error) {
                errorMessage = errorData.error;
            } else if (errorData.message) {
                errorMessage = errorData.message;
            }

            throw new Error(errorMessage);
        } catch (parseError) {
            // ถ้า parse JSON ไม่ได้ (response ไม่ใช่ JSON)
            throw new Error(`Scraping data failed: ${response.statusText}`);
        }
    }

    const dataResponse: ScrapingAPIResponse = await response.json();
    return dataResponse;
}

export async function deleteUploadedFileApi(filename: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_uploaded", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ filename })
    });

    if (!response.ok) {
        throw new Error(`Deleting file failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function deleteGlobalUploadedFileApi(filename: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/global_delete_uploaded", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ filename })
    });

    if (!response.ok) {
        throw new Error(`Deleting file failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function listUploadedFilesApi(idToken: string): Promise<[string, number, string | null][]> {
    const response = await fetch(`/list_uploaded`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing files failed: ${response.statusText}`);
    }

    const dataResponse: [string, number, string | null][] = await response.json();
    return dataResponse;
}

export async function listUploadedGlobalFilesApi(idToken: string): Promise<Array<[string, string, string, number, string | null] | string>> {
    const response = await fetch(`/list_global_uploaded`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing files failed: ${response.statusText}`);
    }

    const dataResponse: Array<[string, string, string, number, string | null] | string> = await response.json();
    return dataResponse;
}

export async function listWebApi(idToken: string, team_id?: string | null): Promise<string[]> {
    const url = team_id ? `/list_web_contents?team_id=${team_id}` : `/list_web_contents`;
    const response = await fetch(url, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing webs failed: ${response.statusText}`);
    }

    const dataResponse: string[] = await response.json();
    return dataResponse;
}

export async function deleteWebContentApi(url: string, idToken: string, team_id?: string | null): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const body: any = { url };
    if (team_id) {
        body.team_id = team_id; // เพิ่ม gid เฉพาะถ้ามีค่า
    }
    const response = await fetch("/delete_web_content", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });

    if (!response.ok) {
        throw new Error(`Deleting web content failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function createUserApi(username: string, idToken: string, groups?: GroupDetail[] | null, role_id?: string | null): Promise<string> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/create_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ username, groups, role_id })
    });

    if (!response.ok) {
        throw new Error(`Create user failed: ${response.statusText}`);
    }

    const dataResponse: string = await response.json();
    return dataResponse;
}

export async function userDetailsApi(username: string, idToken: string): Promise<UserProfile> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/user_details", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ username })
    });

    if (!response.ok) {
        throw new Error(`Get user details failed: ${response.statusText}`);
    }

    const dataResponse: UserProfile = await response.json();
    return dataResponse;
}

export async function listRolesApi(idToken: string): Promise<RoleDetail[]> {
    const response = await fetch(`/list_roles`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing webs failed: ${response.statusText}`);
    }

    const dataResponse: RoleDetail[] = await response.json();
    return dataResponse;
}

export async function listGroupsApi(idToken: string): Promise<GroupDetail[]> {
    const response = await fetch(`/list_groups`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing webs failed: ${response.statusText}`);
    }

    const dataResponse: GroupDetail[] = await response.json();
    return dataResponse;
}

export async function createGroupApi(group_name: string, idToken: string, agent_name?: string, group_promt?: GroupPrompt): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/create_group", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ group_name, agent_name, group_promt })
    });

    if (!response.ok) {
        throw new Error(`Create group failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function updateGroupApi(
    group_id: string,
    group_name: string,
    idToken: string,
    group_promt?: GroupPrompt,
    agent_name?: string
): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/update_group", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ group_id, group_name, group_promt, agent_name })
    });

    if (!response.ok) {
        throw new Error(`Update group failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function deleteGroupApi(group_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_group", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ group_id })
    });

    if (!response.ok) {
        throw new Error(`Delete group failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function uploadGroupFileApi(request: FormData, idToken: string, gid: string): Promise<SimpleAPIResponse> {
    request.append("gid", gid);

    const headers = await getHeaders(idToken);
    if ("Content-Type" in headers) {
        delete (headers as any)["Content-Type"];
    }

    const response = await fetch("/groups_upload", {
        method: "POST",
        headers,
        body: request
    });

    if (!response.ok) throw new Error(await uploadErrorMessage(response));

    return await response.json();
}

export async function uploadTeamFileApi(request: FormData, data_groups_id: string[], team_id: string, idToken: string): Promise<SimpleAPIResponse> {
    request.append("data_groups_id", JSON.stringify(data_groups_id));
    request.append("team_id", team_id);

    const headers = await getHeaders(idToken);
    if ("Content-Type" in headers) {
        delete (headers as any)["Content-Type"];
    }

    const response = await fetch("/team_upload", {
        method: "POST",
        headers,
        body: request
    });

    if (!response.ok) throw new Error(await uploadErrorMessage(response));

    return await response.json();
}

export async function deleteTeamUploadedFileApi(filename: string, idToken: string, team_id: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/team_delete_uploaded", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ filename, team_id })
    });

    if (!response.ok) {
        throw new Error(`Deleting file failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function listUploadedteamFilesApi(team_id: string, idToken: string): Promise<Array<[string, string, string, number, string[], string | null] | string>> {
    const headers = await getHeaders(idToken);

    const response = await fetch(`/list_team_uploaded`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`Listing files failed: ${response.statusText}`);
    }

    const dataResponse: string[] = await response.json();
    return dataResponse;
}

export async function listUsersApi(idToken: string): Promise<UserProfile[]> {
    const response = await fetch(`/list_users`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing webs failed: ${response.statusText}`);
    }

    const dataResponse: UserProfile[] = await response.json();
    return dataResponse;
}

export async function getFixedPromptsApi(idToken: string | undefined): Promise<any> {
    const response = await fetch(`/fixed_prompt`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Getting fixed prompts failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function listUsageApi(idToken: string): Promise<any> {
    const response = await fetch(`/get_usage`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing usage failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export type UsageAnalyticsParams = {
    scope: "system" | "team" | "personal";
    team_id?: string;
    user_id?: string;
    agent_id?: string;
    provider?: string;
    model?: string;
    profile_id?: string;
    file_type?: string;
    document_scope?: string;
    from?: string;
    to?: string;
    bucket?: "day" | "week" | "month";
};

export async function getUsageAnalyticsApi(idToken: string, params: UsageAnalyticsParams): Promise<any> {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value) query.set(key, value);
    });
    const response = await fetch(`/usage-analytics?${query.toString()}`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `Loading usage analytics failed (${response.status})`);
    }
    return response.json();
}

export async function updateUserApi(
    user_id: string,
    username: string,
    idToken: string,
    groups?: GroupDetail[] | null,
    role_id?: string | null
): Promise<UserProfile> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/update_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ user_id, username, groups, role_id })
    });

    if (!response.ok) {
        throw new Error(`Update user failed: ${response.statusText}`);
    }

    const dataResponse: UserProfile = await response.json();
    return dataResponse;
}

export async function deleteUserApi(user_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ user_id })
    });

    if (!response.ok) {
        throw new Error(`Delete user failed: ${response.statusText}`);
    }

    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function postChatHistoryApi(item: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/chat_history", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(item)
    });

    if (!response.ok) {
        throw new Error(`Posting chat history failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function getChatHistoryListApi(count: number, continuationToken: string | undefined, idToken: string): Promise<HistoryListApiResponse> {
    const headers = await getHeaders(idToken);
    let url = `${BACKEND_URI}/chat_history/sessions?count=${count}`;
    if (continuationToken) {
        url += `&continuationToken=${continuationToken}`;
    }

    const response = await fetch(url.toString(), {
        method: "GET",
        headers: { ...headers, "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error(`Getting chat histories failed: ${response.statusText}`);
    }

    const dataResponse: HistoryListApiResponse = await response.json();
    return dataResponse;
}

export async function getChatHistoryApi(id: string, idToken: string): Promise<HistoryApiResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/chat_history/sessions/${id}`, {
        method: "GET",
        headers: { ...headers, "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error(`Getting chat history failed: ${response.statusText}`);
    }

    const dataResponse: HistoryApiResponse = await response.json();
    return dataResponse;
}

export async function deleteChatHistoryApi(id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/chat_history/sessions/${id}`, {
        method: "DELETE",
        headers: { ...headers, "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error(`Deleting chat history failed: ${response.statusText}`);
    }
}

export async function createFeedbackApi(payload: FeedbackPayload, idToken: string): Promise<void> {
    try {
        const headers = await getHeaders(idToken);

        fetch(`/feedbacks`, {
            method: "POST",
            headers: { ...headers, "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).catch(err => console.error("feedback send error:", err));
    } catch (err) {
        console.error("feedback setup error:", err);
    }
}

export async function deleteFeedbackApi(session_state: string, answer_index: number, idToken: string): Promise<void> {
    try {
        const headers = await getHeaders(idToken);
        const query = new URLSearchParams({
            session_state,
            answer_index: String(answer_index)
        });

        fetch(`/feedbacks?${query.toString()}`, {
            method: "DELETE",
            headers
        }).catch(err => console.error("feedback delete error:", err));
    } catch (err) {
        console.error("delete setup error:", err);
    }
}

export async function listAgentsApi(idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/list_agent`, {
        method: "GET",
        headers: { ...headers, "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error(`Getting agent list failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function deleteAgentApi(agent_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/deleteAgentApi`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id })
    });

    if (!response.ok) {
        throw new Error(`Deleting agent failed: ${response.statusText}`);
    }
}

export async function createAgentApi(payload: AgentConfig, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/createAgentApi`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        let err = {};
        try {
            err = await response.json(); // <--- ดึง JSON error จริง
        } catch (_) {}

        throw {
            status: response.status,
            ...err
        };
    }

    return response.json();
}

export async function updateAgentApi(payload: AgentConfig, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/updateAgentApi`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        let err = {};
        try {
            err = await response.json(); // <--- ดึง JSON error จริง
        } catch (_) {}

        throw {
            status: response.status,
            ...err
        };
    }

    return response.json();
}

export async function currentAgentConfig(group_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/current_agent_config`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ group_id })
    });

    if (!response.ok) {
        throw new Error(`Current agent config failed: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
}

export async function feedBackPageApi(request: FormData, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/add_feedback_page", {
        method: "POST",
        headers,
        body: request
    });

    if (!response.ok) {
        throw new Error(`Feedback submission failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function listFeedback(idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/get_all_feedback_page`, {
        method: "GET",
        headers: { ...headers, "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error(`get feedback list failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function limit_size(idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch(`/limit_size_conf`, {
        method: "GET",
        headers: { ...headers, "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error(`get limit size conf failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function list_doc_ai(idToken: string): Promise<any> {
    const response = await fetch(`/get_docintel_usage`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Listing usage failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function check_user_login(idToken: string): Promise<any> {
    const response = await fetch(`/check_user_login`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        const error: any = new Error("check_user_login failed");
        error.status = response.status; // ⭐ สำคัญมาก
        throw error;
    }

    return await response.json();
}

export async function get_teams(idToken: string): Promise<any> {
    const response = await fetch(`/get_all_teams`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function create_team(team_name: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/create_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_name })
    });

    if (!response.ok) {
        throw new Error(`Create team failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function delete_team(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/delete_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`Create team failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function team_detail(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_team_detail", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`Get team detail failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function edit_team_name(team_id: string, team_name: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/edit_team_name", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, team_name })
    });

    if (!response.ok) {
        throw new Error(`Get team detail failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function insert_team_users(team_id: string, user_id: string[], idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/insert_team_users", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, user_id })
    });

    if (!response.ok) {
        throw new Error(`Insert user failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function delete_team_user(team_id: string, user_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/delete_team_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, user_id })
    });

    if (!response.ok) {
        throw new Error(`Delete user failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function get_all_users(idToken: string): Promise<any> {
    const response = await fetch(`/get_all_users`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function updateMyProfile(
    profile: Pick<User, "first_name" | "last_name" | "email" | "tel">,
    idToken: string
): Promise<User> {
    const response = await fetch("/auth/profile", {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(profile)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to update profile");
    return data.user as User;
}

export async function changeMyLocalPassword(
    currentPassword: string,
    newPassword: string,
    idToken: string
): Promise<{ success: boolean; reauthentication_required: boolean }> {
    const response = await fetch("/auth/local/password", {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to change password");
    return data;
}

export async function get_team_users(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_team_users", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`get team user failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function add_users(user: User, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    if (user.local_username && user.local_password) {
        const response = await fetch("/admin/local-users", {
            method: "POST",
            headers: { ...headers, "Content-Type": "application/json" },
            body: JSON.stringify({
                username: user.local_username,
                password: user.local_password,
                ad_email: user.ad_email,
                email: user.email,
                first_name: user.first_name,
                last_name: user.last_name,
                tel: user.tel,
                employee_id: user.employee_id,
                active: user.active
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Create local user failed (${response.status})`);
        return data;
    }
    let ad_email = user.ad_email;
    let email = user.email;
    let first_name = user.first_name;
    let last_name = user.last_name;
    let tel = user.tel;
    let employee_id = user.employee_id;

    const response = await fetch("/insert_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ ad_email, email, first_name, last_name, tel, employee_id })
    });

    if (!response.ok) {
        throw new Error(`get team user failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function update_user(user: User, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    let user_id = user._id;
    let ad_email = user.ad_email;
    let email = user.email;
    let first_name = user.first_name;
    let last_name = user.last_name;
    let tel = user.tel;
    let employee_id = user.employee_id;
    let active = user.active;

    const response = await fetch("/update_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ ad_email, email, first_name, last_name, tel, employee_id, active, user_id })
    });

    if (!response.ok) {
        throw new Error(`get team user failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function resetLocalUserPassword(userId: string, password: string, idToken: string): Promise<void> {
    const response = await fetch(`/admin/local-users/${encodeURIComponent(userId)}/password`, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ password })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to reset local password");
}

export async function delete_user(user_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/delete_user", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ user_id })
    });

    if (!response.ok) {
        throw new Error(`get team user failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function get_all_permission(idToken: string): Promise<any> {
    const response = await fetch(`/get_all_permissions`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse.permissions;
}

export async function get_user_permissions(user_id: string, team_id: string | null, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_user_permissions", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ user_id, team_id })
    });

    if (!response.ok) {
        throw new Error(`get user permission failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse.user_permissions;
}

export async function create_edit_user_permissions(
    user_id: string,
    team_id: string | null,
    permission_id: string[] | null,
    is_sys_admin: boolean,
    idToken: string
): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/create_edit_user_permissions", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ user_id, team_id, permission_id, is_sys_admin })
    });

    if (!response.ok) {
        throw new Error(`get user permission failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse.user_permissions;
}

export async function get_users_by_team_id(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_users_by_team_id", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`get user permission failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function register(team_id: string[], user: RegisterUserPayload, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    let email = user.email;
    let first_name = user.first_name;
    let last_name = user.last_name;
    let tel = user.tel;
    let employee_id = user.employee_id;

    const response = await fetch("/register", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, email, first_name, last_name, tel, employee_id })
    });

    if (!response.ok) {
        throw new Error(`register failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}
export async function approve_users(team_id: string, users: User[], idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/approve_users", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, users })
    });

    if (!response.ok) {
        throw new Error(`approve users failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function reject_users(team_id: string, users: User[], idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/reject_users", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, users })
    });

    if (!response.ok) {
        throw new Error(`reject users failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function check_waiting_approve(idToken: string): Promise<any> {
    const response = await fetch(`/check_waiting_approve`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });

    if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function create_agent(team_id: string, agent_name: string, config: AgentConfig, prompt: Prompt, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/create_agent", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, agent_name, config, prompt })
    });

    if (!response.ok) {
        throw new Error(`create agent failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function get_agent_by_team(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_agent_by_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`get agent by team failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse.result;
}

export async function edit_agent(team_id: string, agent_id: string, agent_name: string, config: AgentConfig, prompt: Prompt, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/edit_agent", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, agent_id, agent_name, config, prompt })
    });

    if (!response.ok) {
        throw new Error(`create agent failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function delete_agent(team_id: string, agent_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/delete_agent", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, agent_id })
    });

    if (!response.ok) {
        throw new Error(`get agent by team failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function get_data_group_by_team(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_data_group_by_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`get data group by team failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse.result;
}

export async function getEffectiveAccess(
    teamId: string,
    idToken: string,
    agentId?: string | null,
    dataGroupIds?: string[],
    selectedScopes?: string[]
): Promise<EffectiveAccessResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/effective-access", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
            team_id: teamId,
            ...(agentId ? { agent_id: agentId } : {}),
            ...(dataGroupIds ? { data_groups_id: dataGroupIds } : {}),
            ...(selectedScopes ? { selected_scopes: selectedScopes } : {})
        })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload?.error || `Unable to resolve effective access (${response.status})`);
    }
    return payload as EffectiveAccessResponse;
}

export async function create_data_group(
    team_id: string,
    data_group_name: string,
    users_id: string[],
    access_mode: "team" | "selected_users",
    idToken: string
): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/create_data_group", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, data_group_name, users_id, access_mode })
    });

    const dataResponse: any = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(dataResponse?.error || `create data group failed: ${response.statusText}`);
    }
    return await dataResponse;
}

export async function edit_data_group(
    data_group_id: string,
    data_group_name: string,
    users_id: string[],
    access_mode: "team" | "selected_users",
    idToken: string
): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/edit_data_group", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ data_group_id, data_group_name, users_id, access_mode })
    });

    const dataResponse: any = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(dataResponse?.error || `edit data group failed: ${response.statusText}`);
    }
    return await dataResponse;
}

export async function delete_data_group(team_id: string, data_group_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/delete_data_group", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, data_group_id })
    });

    if (!response.ok) {
        throw new Error(`delete data group failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function create_role(team_id: string, name: string, permissions_id: string[], idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/create_role", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id, name, permissions_id })
    });

    if (!response.ok) {
        throw new Error(`create role failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function edit_role(team_id: string, role_id: string, name: string, permissions_id: string[], idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/edit_role", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ role_id, team_id, name, permissions_id })
    });

    if (!response.ok) {
        throw new Error(`edit role failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function delete_role(role_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/delete_role", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ role_id })
    });

    if (!response.ok) {
        throw new Error(`delete role failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse;
}

export async function get_roles_by_team(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);

    const response = await fetch("/get_roles_by_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });

    if (!response.ok) {
        throw new Error(`get roles by team failed: ${response.statusText}`);
    }

    const dataResponse: any = await response.json();
    return await dataResponse.roles;
}

export async function get_external_apis_by_team(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/get_external_apis_by_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });
    if (!response.ok) {
        throw new Error(`get external apis failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function insert_external_api(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_external_api", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        throw new Error(`insert external api failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function edit_external_api(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/edit_external_api", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        throw new Error(`edit external api failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function delete_external_api(api_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_external_api", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ api_id })
    });
    if (!response.ok) {
        const errorResponse = await response.json().catch(() => ({}));
        throw new Error(errorResponse.error || `delete external api failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function insert_agent_binding(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_agent_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        throw new Error(`insert agent binding failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

// TODO: เปลี่ยน endpoint เมื่อได้ API จริง
export async function insert_database_binding(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_database_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const errorResponse = await response.json().catch(() => ({}));
        throw new Error(errorResponse.error || `insert database binding failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

// TODO: เปลี่ยน endpoint เมื่อได้ API จริง
export async function get_database_bindings_by_agent(agent_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/get_database_bindings_by_agent", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id })
    });
    if (!response.ok) {
        throw new Error(`get database bindings failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

// TODO: เปลี่ยน endpoint เมื่อได้ API จริง
export async function delete_database_binding_by_id(database_binding_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_database_binding_by_id", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ database_binding_id })
    });
    if (!response.ok) {
        throw new Error(`delete database binding failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

// TODO: เปลี่ยน endpoint เมื่อได้ API จริง
export async function toggle_database_binding_by_id(database_binding_id: string, enabled: boolean, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/toggle_database_binding_by_id", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ database_binding_id, enabled })
    });
    if (!response.ok) {
        throw new Error(`toggle database binding failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

async function parseMCPResponse(response: Response): Promise<any> {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `MCP request failed (${response.status})`);
    return data;
}

export async function listMCPServersApi(teamId: string, idToken: string): Promise<ManagedMCPServer[]> {
    const query = new URLSearchParams({ team_id: teamId });
    const response = await fetch(`/admin/mcp-servers?${query}`, { headers: await getHeaders(idToken) });
    return (await parseMCPResponse(response)).servers;
}

export async function listAvailableMCPServersApi(teamId: string, idToken: string, agentId?: string): Promise<ManagedMCPServer[]> {
    const query = new URLSearchParams({ team_id: teamId });
    if (agentId) query.set("agent_id", agentId);
    const response = await fetch(`/mcp-servers/available?${query}`, { headers: await getHeaders(idToken) });
    return (await parseMCPResponse(response)).servers;
}

export async function createMCPServerApi(payload: MCPServerPayload, idToken: string): Promise<ManagedMCPServer> {
    const response = await fetch("/admin/mcp-servers", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return parseMCPResponse(response);
}

export async function updateMCPServerApi(serverId: string, payload: MCPServerPayload, idToken: string): Promise<ManagedMCPServer> {
    const response = await fetch(`/admin/mcp-servers/${serverId}`, {
        method: "PUT",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return parseMCPResponse(response);
}

export async function deleteMCPServerApi(serverId: string, idToken: string): Promise<void> {
    const response = await fetch(`/admin/mcp-servers/${serverId}`, {
        method: "DELETE",
        headers: await getHeaders(idToken)
    });
    await parseMCPResponse(response);
}

export async function testMCPServerApi(serverId: string, idToken: string): Promise<{ success: boolean; blocked_tool_count?: number; tools: Array<{ name: string; description?: string }> }> {
    const response = await fetch(`/admin/mcp-servers/${serverId}/test`, {
        method: "POST",
        headers: await getHeaders(idToken)
    });
    return parseMCPResponse(response);
}

export async function listAgentAuditEventsApi(
    filters: { agent_id?: string; run_id?: string; event_type?: string; status?: string; hours?: number; limit?: number },
    idToken: string
): Promise<AgentAuditEvent[]> {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") query.set(key, String(value));
    });
    const response = await fetch(`/admin/agent-audit-events?${query}`, { headers: await getHeaders(idToken) });
    const data = await parseMCPResponse(response);
    return data.events ?? [];
}

export async function update_database_binding(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/update_database_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const dataResponse: any = await response.json();
    if (!response.ok) {
        throw new Error(dataResponse.error || `update database binding failed: ${response.statusText}`);
    }
    return dataResponse;
}

export async function delete_agent_binding_by_id(agent_binding_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_agent_binding_by_id", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_binding_id })
    });
    if (!response.ok) {
        throw new Error(`delete agent binding failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function toggle_agent_binding_by_id(agent_bindin_id: string, enabled: boolean, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/toggle_agent_binding_by_id", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_bindin_id, enabled })
    });
    if (!response.ok) {
        throw new Error(`toggle agent binding failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function get_agent_bindings_by_agent(agent_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/get_agent_bindings_by_agent", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id })
    });
    if (!response.ok) {
        throw new Error(`get agent bindings failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function get_integrations_by_team(team_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/get_integrations_by_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });
    if (!response.ok) {
        throw new Error(`get integrations failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export type IntegrationCatalogType = "rest_api" | "database" | "mail" | "messaging" | "mcp" | "business_documents";

export async function assign_integration_team(
    integration_type: IntegrationCatalogType,
    integration_id: string,
    team_id: string,
    idToken: string
): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/assign_integration_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ integration_type, integration_id, team_id })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.error || `assign integration failed: ${response.statusText}`);
    }
    return result;
}

export async function get_db_connections(team_id: string, _idToken: string): Promise<DatabaseConnection[]> {
    const headers = await getHeaders(_idToken);
    const response = await fetch("/get_database_connection_by_team", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ team_id })
    });
    if (!response.ok) {
        throw new Error(`get database connections failed: ${response.statusText}`);
    }
    const dataResponse: { result?: DatabaseConnection[]; data?: DatabaseConnection[] } | DatabaseConnection[] = await response.json();

    if (Array.isArray(dataResponse)) {
        return dataResponse;
    }

    return dataResponse.result || dataResponse.data || [];
}

export async function insert_db_connection(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_database_connection", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const errorResponse = await response.json().catch(() => ({}));
        throw new Error(errorResponse.error || `insert database connection failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function edit_db_connection(payload: any, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const normalizedPayload = {
        ...payload,
        database_id: payload.database_id ?? payload.connection_id
    };
    delete normalizedPayload.connection_id;

    const response = await fetch("/edit_database_connection", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(normalizedPayload)
    });
    if (!response.ok) {
        const errorResponse = await response.json().catch(() => ({}));
        throw new Error(errorResponse.error || `edit database connection failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function delete_db_connection(connection_id: string, idToken: string): Promise<any> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_database_connection", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ database_id: connection_id })
    });
    if (!response.ok) {
        const errorResponse = await response.json().catch(() => ({}));
        throw new Error(errorResponse.error || `delete database connection failed: ${response.statusText}`);
    }
    const dataResponse: any = await response.json();
    return dataResponse;
}

export async function test_db_connection(
    payload: Partial<DatabaseConnection> & { database_id?: string },
    idToken: string
): Promise<{ ok: boolean; message: string }> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/test_database_connection", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const dataResponse: { ok?: boolean; message?: string; error?: string } = await response.json();
    if (!response.ok) {
        throw new Error(dataResponse.error || `test database connection failed: ${response.statusText}`);
    }
    return { ok: dataResponse.ok === true, message: dataResponse.message || "Connection succeeded" };
}

export async function get_mail_configs(team_id: string, idToken: string): Promise<MailEmailConfig[]> {
    const response = await fetch(`/mail_configs?team_id=${team_id}`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `get mail configs failed: ${response.statusText}`);
    }
    const dataResponse: MailEmailConfig[] = await response.json();
    return dataResponse;
}

export async function insert_mail_config(payload: any, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_mail_config", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `insert mail config failed: ${response.statusText}`);
    }
    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function edit_mail_config(payload: any, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/edit_mail_config", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `edit mail config failed: ${response.statusText}`);
    }
    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function delete_mail_config(config_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_mail_config", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ config_id })
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `delete mail config failed: ${response.statusText}`);
    }
    const dataResponse: SimpleAPIResponse = await response.json();
    return dataResponse;
}

export async function test_mail_connection(config_id: string, idToken: string): Promise<{ ok: boolean; message: string }> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/test_mail_connection", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ connection_id: config_id })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `test mail connection failed: ${response.statusText}`);
    return result;
}

// ─── Microsoft 365 Documents / Google Workspace ────────────────────────────

import { BusinessDocumentBindingData, BusinessDocumentConnection } from "./models";

export async function get_business_document_connections(team_id: string, idToken: string): Promise<BusinessDocumentConnection[]> {
    const response = await fetch(`/business_document_connections?team_id=${encodeURIComponent(team_id)}`, {
        headers: await getHeaders(idToken)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `get document connections failed: ${response.statusText}`);
    return result;
}

export async function save_business_document_connection(payload: Record<string, unknown>, idToken: string): Promise<SimpleAPIResponse> {
    const response = await fetch("/save_business_document_connection", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `save document connection failed: ${response.statusText}`);
    return result;
}

export async function test_business_document_connection(connection_id: string, idToken: string): Promise<{ ok: boolean; message: string }> {
    const response = await fetch("/test_business_document_connection", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ connection_id })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `test document connection failed: ${response.statusText}`);
    return result;
}

export async function delete_business_document_connection(connection_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const response = await fetch("/delete_business_document_connection", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ connection_id })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `delete document connection failed: ${response.statusText}`);
    return result;
}

export async function get_business_document_bindings(agent_id: string, idToken: string): Promise<BusinessDocumentBindingData[]> {
    const response = await fetch(`/business_document_bindings?agent_id=${encodeURIComponent(agent_id)}`, {
        headers: await getHeaders(idToken)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `get document bindings failed: ${response.statusText}`);
    return result;
}

export async function save_business_document_binding(payload: Record<string, unknown>, idToken: string): Promise<SimpleAPIResponse> {
    const response = await fetch("/save_business_document_binding", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `save document binding failed: ${response.statusText}`);
    return result;
}

export async function delete_business_document_binding(binding_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const response = await fetch("/delete_business_document_binding", {
        method: "POST",
        headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `delete document binding failed: ${response.statusText}`);
    return result;
}

// ─── Mail Binding ────────────────────────────────────────────────────────────

import { MailBindingData } from "./models";

export async function get_mail_bindings_by_agent(agent_id: string, idToken: string): Promise<MailBindingData[]> {
    const response = await fetch(`/mail_bindings?agent_id=${agent_id}`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });
    if (!response.ok) throw new Error(`get mail bindings failed: ${response.statusText}`);
    return response.json();
}

export async function insert_mail_binding(payload: Omit<MailBindingData, "_id">, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_mail_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`insert mail binding failed: ${response.statusText}`);
    return response.json();
}

export async function delete_mail_binding_by_id(binding_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_mail_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id })
    });
    if (!response.ok) throw new Error(`delete mail binding failed: ${response.statusText}`);
    return response.json();
}

export async function toggle_mail_binding_by_id(binding_id: string, enabled: boolean, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/toggle_mail_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id, enabled })
    });
    if (!response.ok) throw new Error(`toggle mail binding failed: ${response.statusText}`);
    return response.json();
}

export async function update_mail_binding(
    binding_id: string,
    payload: Omit<MailBindingData, "_id">,
    idToken: string
): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/update_mail_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id, ...payload })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `update mail binding failed: ${response.statusText}`);
    return result;
}

export async function get_messaging_connections(team_id: string, idToken: string) {
    const response = await fetch(`/messaging_connections?team_id=${encodeURIComponent(team_id)}`, { headers: await getHeaders(idToken) });
    const result = await response.json().catch(() => []);
    if (!response.ok) throw new Error(result.error || "Failed to load messaging connections");
    return result;
}
export async function save_messaging_connection(payload: any, idToken: string) {
    const response = await fetch("/save_messaging_connection", { method: "POST", headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || "Failed to save messaging connection"); return result;
}
export async function test_messaging_connection(connection_id: string, idToken: string) {
    const response = await fetch("/test_messaging_connection", { method: "POST", headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" }, body: JSON.stringify({ connection_id }) });
    const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || "Messaging test failed"); return result;
}
export async function delete_messaging_connection(connection_id: string, idToken: string) {
    const response = await fetch("/delete_messaging_connection", { method: "POST", headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" }, body: JSON.stringify({ connection_id }) });
    const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || "Delete failed"); return result;
}
export async function get_messaging_bindings(agent_id: string, idToken: string) {
    const response = await fetch(`/messaging_bindings?agent_id=${encodeURIComponent(agent_id)}`, { headers: await getHeaders(idToken) });
    if (!response.ok) throw new Error("Failed to load messaging bindings"); return response.json();
}
export async function save_messaging_binding(payload: any, idToken: string) {
    const response = await fetch("/save_messaging_binding", { method: "POST", headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || "Save binding failed"); return result;
}
export async function delete_messaging_binding(binding_id: string, idToken: string) {
    const response = await fetch("/delete_messaging_binding", { method: "POST", headers: { ...(await getHeaders(idToken)), "Content-Type": "application/json" }, body: JSON.stringify({ binding_id }) });
    const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || "Delete binding failed"); return result;
}
async function documentProcessingRequest(path: string, idToken: string, body?: unknown) {
    const response = await fetch(path, { method: body ? "POST" : "GET", headers: { ...(await getHeaders(idToken)), ...(body ? { "Content-Type": "application/json" } : {}) }, body: body ? JSON.stringify(body) : undefined });
    const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || "Document processing request failed"); return result;
}
export const get_document_processing_providers = (token: string) => documentProcessingRequest("/document_processing/providers", token);
export const save_document_processing_provider = (payload: any, token: string) => documentProcessingRequest("/document_processing/providers/save", token, payload);
export const test_document_processing_provider = (provider_id: string, token: string) => documentProcessingRequest("/document_processing/providers/test", token, { provider_id });
export const delete_document_processing_provider = (provider_id: string, token: string) => documentProcessingRequest("/document_processing/providers/delete", token, { provider_id });
export const get_document_processing_profiles = (token: string) => documentProcessingRequest("/document_processing/profiles", token);
export const save_document_processing_profile = (payload: any, token: string) => documentProcessingRequest("/document_processing/profiles/save", token, payload);
export const delete_document_processing_profile = (profile_id: string, token: string) => documentProcessingRequest("/document_processing/profiles/delete", token, { profile_id });
export const get_document_processing_routing_rules = (token: string) => documentProcessingRequest("/document_processing/routing-rules", token);
export const save_document_processing_routing_rule = (payload: any, token: string) => documentProcessingRequest("/document_processing/routing-rules/save", token, payload);
export const delete_document_processing_routing_rule = (rule_id: string, token: string) => documentProcessingRequest("/document_processing/routing-rules/delete", token, { rule_id });
export const explain_document_processing_route = (payload: any, token: string) => documentProcessingRequest("/document_processing/explain-route", token, payload);
export const get_document_processing_upload_options = (token: string) => documentProcessingRequest("/document_processing/upload-options", token);

// ─── Chart Capability Binding ────────────────────────────────────────────────
// ⭐ CHART CAPABILITY: CRUD สำหรับผูก "ความสามารถสร้างกราฟ" เข้ากับ agent
//    ใช้ pattern เดียวกับ mail binding (GET /chart_bindings + POST insert/delete/toggle)
import { ChartBindingData } from "./models";

async function chartBindingError(response: Response, operation: string): Promise<Error> {
    let detail = "";
    try {
        const body = await response.json();
        detail = typeof body?.error === "string" ? body.error : typeof body?.message === "string" ? body.message : "";
    } catch {
        // The status text is still useful if a proxy returned a non-JSON body.
    }
    return new Error(detail || `${operation} failed (${response.status} ${response.statusText})`);
}

export async function get_chart_bindings_by_agent(agent_id: string, idToken: string): Promise<ChartBindingData[]> {
    const response = await fetch(`/chart_bindings?agent_id=${agent_id}`, {
        method: "GET",
        headers: await getHeaders(idToken)
    });
    if (!response.ok) throw await chartBindingError(response, "Get chart bindings");
    return response.json();
}

export async function insert_chart_binding(payload: Omit<ChartBindingData, "_id">, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/insert_chart_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw await chartBindingError(response, "Add chart capability");
    return response.json();
}

export async function delete_chart_binding_by_id(binding_id: string, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/delete_chart_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id })
    });
    if (!response.ok) throw await chartBindingError(response, "Delete chart capability");
    return response.json();
}

export async function toggle_chart_binding_by_id(binding_id: string, enabled: boolean, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/toggle_chart_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id, enabled })
    });
    if (!response.ok) throw await chartBindingError(response, "Toggle chart capability");
    return response.json();
}

export async function update_chart_binding(payload: ChartBindingData, idToken: string): Promise<SimpleAPIResponse> {
    const headers = await getHeaders(idToken);
    const response = await fetch("/update_chart_binding", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
            binding_id: payload._id,
            chart_selection_mode: payload.chart_selection_mode ?? "auto",
            auto_generate: payload.auto_generate ?? false,
            color_palette: payload.color_palette,
            title_template: payload.title_template,
            trigger_keywords: payload.trigger_keywords,
            enabled: payload.enabled,
            default_chart_type: payload.default_chart_type,
            allowed_chart_types: payload.allowed_chart_types
        })
    });
    if (!response.ok) throw await chartBindingError(response, "Update chart capability");
    return response.json();
}
