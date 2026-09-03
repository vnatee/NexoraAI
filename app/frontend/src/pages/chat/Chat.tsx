import { useRef, useState, useEffect, useContext, useCallback, useLayoutEffect } from "react";
import { useTranslation } from "react-i18next";
import { Helmet } from "react-helmet-async";
import { Panel, DefaultButton, IconButton } from "@fluentui/react";
import readNDJSONStream from "ndjson-readablestream";
import { Button as Button2 } from "@fluentui/react-components";

import appLogo from "../../assets/classic_icon-bg.png";
import styles from "./Chat.module.css";

import {
    chatApi,
    configApi,
    RetrievalMode,
    ChatAppResponse,
    ChatAppResponseOrError,
    ChatAppRequest,
    ChatAttachmentInput,
    ChatDocumentAttachment,
    EvidenceMatrixOptions,
    ResponseMessage,
    VectorFields,
    GPT4VInput,
    SpeechConfig,
    createFeedbackApi,
    deleteFeedbackApi,
    getEffectiveAccess,
    get_agent_by_team,
    getFixedPromptsApi,
    getTemporaryCitationFilePath
} from "../../api";
import { Answer, AnswerError, AnswerLoading } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import { ExampleList } from "../../components/Example";
import { UserChatMessage } from "../../components/UserChatMessage";
import { AnalysisPanel, AnalysisPanelTabs } from "../../components/AnalysisPanel";
import { HistoryPanel } from "../../components/HistoryPanel";
import { HistoryProviderOptions, useHistoryManager } from "../../components/HistoryProviders";
import { HistoryButton } from "../../components/HistoryButton";
import { SettingsButton } from "../../components/SettingsButton";
import { ClearChatButton } from "../../components/ClearChatButton";
import { UploadFile } from "../../components/UploadFile";
import { GlobalUpload } from "../../components/GlobalUpload/GlobalUpload";
import { ScrapData } from "../../components/ScrapData/ScrapData";
import { useLogin, getToken, requireAccessControl, getUsername } from "../../authConfig";
import { useMsal } from "@azure/msal-react";
import { TokenClaimsDisplay } from "../../components/TokenClaimsDisplay";
import { LoginContext } from "../../loginContext";
import { LanguagePicker } from "../../i18n/LanguagePicker";
import { Settings } from "../../components/Settings/Settings";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    List,
    ListItem,
    ListItemText,
    ListItemButton,
    Typography,
    Paper,
    Stack,
    Menu,
    MenuItem,
    Divider,
    ListItemIcon
} from "@mui/material";
import { Add24Regular } from "@fluentui/react-icons";
import LibraryAddCheckIcon from "@mui/icons-material/LibraryAddCheck";
import { Skeleton, Box } from "@mui/material";
import { UserManagement } from "../../components/UserManagment/UserManagement";
import { Dashboard } from "../../components/DashBoard/Dashboard";
import { HistoryList } from "../../components/HistoryPanel/HistoryList";
import { AgentSelectionSummary } from "../../components/AgentSelectionSummary";
import ChatIcon from "@mui/icons-material/Chat";
import SearchIcon from "@mui/icons-material/Search";
import FeedIcon from "@mui/icons-material/Feed";
import FeedbackDialog from "../../components/FeedbackPage/FeedbackDialog";
import FeedbackDashboardDialog from "../../components/FeedbackDashboard/FeedbackDashboardDialog";
import { TeamManagementTabsDialog } from "../../components/TeamManagementTabsDialog/TeamManagementTabsDialog";
import CheckIcon from "@mui/icons-material/Check";
import Checkbox from "@mui/material/Checkbox";
import { AuthStorage } from "../../utill/authStorage";
import { hasPermission } from "../../utill/hasPermission";
import { Agent, EffectiveDataGroup, LLMProfile, TeamProfile, User } from "../../api/models";
import { Storage } from "../../utill/storage";
import { ACTIVE_TEAM_CHANGED_EVENT, STORAGE_KEYS } from "../../utill/storageKeys";
import { useNotification } from "../../utill/NotificationProvider";

const DATA_SCOPES = [
    { key: "global", label: "Global" },
    { key: "personal", label: "Personal" }
] as const;

type DataScope = (typeof DATA_SCOPES)[number]["key"];

type AgentUIPrefs = {
    selectedScopes: DataScope[];
    selectedDataGroupIds: string[];
};

type AgentUIPrefsResolved = {
    agentId: string | null;
    selectedScopes: DataScope[];
    selectedDataGroupIds: any[];
};

const Chat = () => {
    const [isConfigPanelOpen, setIsConfigPanelOpen] = useState(false);
    const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
    const [promptTemplate, setPromptTemplate] = useState<string>("");
    const [temperature, setTemperature] = useState<number>(0.3);
    const [seed, setSeed] = useState<number | null>(null);
    const [minimumRerankerScore, setMinimumRerankerScore] = useState<number>(0);
    const [minimumSearchScore, setMinimumSearchScore] = useState<number>(0);
    const [retrieveCount, setRetrieveCount] = useState<number>(3);
    const [maxSubqueryCount, setMaxSubqueryCount] = useState<number>(10);
    const [resultsMergeStrategy, setResultsMergeStrategy] = useState<string>("interleaved");
    const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>(RetrievalMode.Hybrid);
    const [useSemanticRanker, setUseSemanticRanker] = useState<boolean>(true);
    const [useQueryRewriting, setUseQueryRewriting] = useState<boolean>(false);
    const [reasoningEffort, setReasoningEffort] = useState<string>("");
    const [streamingEnabled, setStreamingEnabled] = useState<boolean>(true);
    const [shouldStream, setShouldStream] = useState<boolean>(true);
    const [useSemanticCaptions, setUseSemanticCaptions] = useState<boolean>(false);
    const [includeCategory, setIncludeCategory] = useState<string>("");
    const [excludeCategory, setExcludeCategory] = useState<string>("");
    const [useSuggestFollowupQuestions, setUseSuggestFollowupQuestions] = useState<boolean>(false);
    const [vectorFields, setVectorFields] = useState<VectorFields>(VectorFields.TextAndImageEmbeddings);
    const [useOidSecurityFilter, setUseOidSecurityFilter] = useState<boolean>(false);
    const [useGroupsSecurityFilter, setUseGroupsSecurityFilter] = useState<boolean>(false);
    const [gpt4vInput, setGPT4VInput] = useState<GPT4VInput>(GPT4VInput.TextAndImages);
    const [useGPT4V, setUseGPT4V] = useState<boolean>(false);

    const lastQuestionRef = useRef<string>("");
    const conversationIdRef = useRef<string>(crypto.randomUUID());
    const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [isStreaming, setIsStreaming] = useState<boolean>(false);
    const [error, setError] = useState<unknown>();

    const [activeCitation, setActiveCitation] = useState<string>();
    const [activeAnalysisPanelTab, setActiveAnalysisPanelTab] = useState<AnalysisPanelTabs | undefined>(undefined);

    const [selectedAnswer, setSelectedAnswer] = useState<number>(0);
    const [answers, setAnswers] = useState<[user: string, response: ChatAppResponse][]>([]);
    const [streamedAnswers, setStreamedAnswers] = useState<[user: string, response: ChatAppResponse][]>([]);
    const [turnAttachments, setTurnAttachments] = useState<Record<number, ChatAttachmentInput[]>>({});
    const [turnDocumentAttachments, setTurnDocumentAttachments] = useState<Record<number, ChatDocumentAttachment[]>>({});
    const isWaitingForStreamedTurn = isStreaming && streamedAnswers.length <= answers.length;
    const [speechUrls, setSpeechUrls] = useState<(string | null)[]>([]);

    const [showGPT4VOptions, setShowGPT4VOptions] = useState<boolean>(false);
    const [chatDocumentAttachmentsEnabled, setChatDocumentAttachmentsEnabled] = useState(false);
    const [agentRuntimeMode, setAgentRuntimeMode] = useState<"legacy" | "langgraph" | "per_agent">("per_agent");
    const [showSemanticRankerOption, setShowSemanticRankerOption] = useState<boolean>(false);
    const [showQueryRewritingOption, setShowQueryRewritingOption] = useState<boolean>(false);
    const [showReasoningEffortOption, setShowReasoningEffortOption] = useState<boolean>(false);
    const [showVectorOption, setShowVectorOption] = useState<boolean>(false);
    const [showUserUpload, setShowUserUpload] = useState<boolean>(false);
    const [showLanguagePicker, setshowLanguagePicker] = useState<boolean>(false);
    const [showSpeechInput, setShowSpeechInput] = useState<boolean>(false);
    const [showSpeechOutputBrowser, setShowSpeechOutputBrowser] = useState<boolean>(false);
    const [showSpeechOutputAzure, setShowSpeechOutputAzure] = useState<boolean>(false);
    const [showChatHistoryBrowser, setShowChatHistoryBrowser] = useState<boolean>(false);
    const [showChatHistoryCosmos, setShowChatHistoryCosmos] = useState<boolean>(false);
    const [showAgenticRetrievalOption, setShowAgenticRetrievalOption] = useState<boolean>(false);
    const [useAgenticRetrieval, setUseAgenticRetrieval] = useState<boolean>(false);
    const [llmProfiles, setLlmProfiles] = useState<LLMProfile[]>([]);
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const uploadDialogRef = useRef<HTMLDivElement>(null);
    const globalUploadDialogRef = useRef<HTMLDivElement>(null);
    const scrapDataDialogRef = useRef<HTMLDivElement>(null);
    const userManagementDialogRef = useRef<HTMLDivElement>(null);
    const dashboardDialogRef = useRef<HTMLDivElement>(null);

    const [open, setOpen] = useState(false);
    const [disabled, setDisabled] = useState(false);
    const [activeWebUrl, setActiveWebUrl] = useState<string | undefined>(undefined);
    const audio = useRef(new Audio()).current;
    const [isPlaying, setIsPlaying] = useState(false);
    const [confirmOpen, setConfirmOpen] = useState(false);
    const { instance } = useMsal();
    const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const [feedbacks, setFeedbacks] = useState<Record<number, "like" | "dislike" | null>>({});
    const [feedbackLoading, setFeedbackLoading] = useState<Record<number, boolean>>({});
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
    const feedbackKey = (sessionId?: string | null) => `chatFeedbacks:${sessionId ?? "no-session"}`;
    const client = useLogin ? useMsal().instance : undefined;
    const { loggedIn, userDetails, isUserLoading, isSwitchTeam, setIsSwitchTeam } = useContext(LoginContext);
    const role = userDetails?.role_name ?? "";
    const email = userDetails?.name ?? "";

    const [openSearch, setOpenSearch] = useState(false);
    const [keyword, setKeyword] = useState("");
    const [results, setResults] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [openFeedback, setOpenFeedback] = useState(false);
    const [openFeedbackDashboard, setOpenFeedbackDashboard] = useState(false);
    const [openTeamManagement, setOpenTeamManagement] = useState(false);
    const [openTeamAdminManagement, setOpenTeamAdminManagement] = useState(false);
    const [agents, setAgents] = useState<Agent[]>([]);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const [agentAnchorEl, setAgentAnchorEl] = useState<null | HTMLElement>(null);
    const agentMenuOpen = Boolean(agentAnchorEl);

    const [selectedScopes, setSelectedScopes] = useState<DataScope[]>(["global"]);
    const [draftScopes, setDraftScopes] = useState<DataScope[]>(["global"]);
    const [draftDataGroupIds, setDraftDataGroupIds] = useState<string[]>([]);

    const [dataGroups, setDataGroups] = useState<EffectiveDataGroup[]>([]);
    const [effectiveAccessError, setEffectiveAccessError] = useState("");

    const [selectedDataGroupIds, setSelectedDataGroupIds] = useState<string[]>([]);
    const [groupKeyword, setGroupKeyword] = useState("");
    const hasSelectedAgent = Boolean(selectedAgent);
    const [isInitialAgentSetup, setIsInitialAgentSetup] = useState(true);
    const defaultAgentId = agents[0]?._id;
    const isDefaultAgent = (agent: Agent | null) => agent?._id === defaultAgentId;
    const [userData, setUserData] = useState<User | null>(null);
    const [sysPers, setSysPers] = useState<string[] | null>(null);
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);
    const didLoadAgentsRef = useRef(false);
    const didLoadGroupsRef = useRef(false);
    const { showNotification } = useNotification();
    const [fixedPrompts, setFixedPrompts] = useState<any>(null);
    const usesLangGraph =
        agentRuntimeMode === "langgraph" || (agentRuntimeMode === "per_agent" && selectedAgent?.config?.runtime === "langgraph");
    const selectedLlmProfileId = selectedAgent?.config?.llm_profile_id || "system";
    const selectedLlmProfile = llmProfiles.find(profile => profile.id === selectedLlmProfileId);
    const modelSupportsVision = selectedLlmProfile?.supportsVision ?? (selectedLlmProfileId === "system" && showGPT4VOptions);
    const imageInputEnabled = selectedAgent?.config?.image_input_enabled === true;
    const documentAttachmentsEnabled = selectedAgent?.config?.document_attachments_enabled !== false;
    const visionAvailable = imageInputEnabled && modelSupportsVision && !usesLangGraph;
    const documentsAvailable = documentAttachmentsEnabled && chatDocumentAttachmentsEnabled;
    const showAttachmentButton = imageInputEnabled || documentAttachmentsEnabled;
    const selectedLlmProfileLabel = selectedLlmProfile?.label ?? (selectedLlmProfileId === "system" ? "System default" : selectedLlmProfileId);
    const visionDisabledReason = !imageInputEnabled
        ? "Image input is disabled in Agent Management."
        : !selectedLlmProfile && selectedLlmProfileId !== "system"
        ? `Agent ${selectedAgent?.agent_name ?? "selected"} references unavailable LLM profile ${selectedLlmProfileId}. Re-select its model in Agent Management.`
        : !modelSupportsVision
        ? `${selectedAgent?.agent_name ?? "The selected agent"} uses ${selectedLlmProfileLabel}, which is not marked as vision-capable. Select the tested Vision model in Agent Management.`
        : usesLangGraph
          ? "Vision attachments are not supported by the LangGraph runtime yet."
          : undefined;
    const attachmentDisabledReason = documentAttachmentsEnabled && !chatDocumentAttachmentsEnabled
        ? "Document attachment storage is not configured for this deployment."
        : visionDisabledReason;

    const [isAgentsLoading, setIsAgentsLoading] = useState(false);
    const [isGroupsLoading, setIsGroupsLoading] = useState(false);
    const isPageLoading = isUserLoading || isAgentsLoading || isGroupsLoading;

    const speechConfig: SpeechConfig = {
        speechUrls,
        setSpeechUrls,
        audio,
        isPlaying,
        setIsPlaying
    };

    const getActiveAgentConfigs = (username: string) => {
        try {
            const raw = localStorage.getItem("activeAgentConfigs") || "{}";
            const all = JSON.parse(raw);
            return all[username] ?? null;
        } catch (err) {
            console.error("Failed to read user agent config:", err);
            return null;
        }
    };

    const buildAgentUIPrefsPayload = async (): Promise<AgentUIPrefsResolved> => {
        try {
            const username = (await getUsername(instance)) ?? "";
            const teamId = await getTeamId();

            const agentId = selectedAgent?._id ?? null;

            // ถ้าไม่มีข้อมูลหลัก -> ส่งค่า default แบบปลอดภัย
            if (!username || !teamId || !agentId) {
                return {
                    agentId,
                    selectedScopes: [],
                    selectedDataGroupIds: []
                };
            }

            const prefsMap = readAgentUIPrefs(username, teamId);
            const prefs = prefsMap?.[agentId];

            const scopes = prefs?.selectedScopes ?? [];
            const availableGroupIds = new Set(dataGroups.map(group => group._id));
            const groups = (prefs?.selectedDataGroupIds ?? []).filter(groupId => availableGroupIds.has(groupId));

            return {
                agentId,
                selectedScopes: scopes,
                selectedDataGroupIds: groups
            };
        } catch (e) {
            console.error("buildAgentUIPrefsPayload failed:", e);
            return {
                agentId: selectedAgent?._id ?? null,
                selectedScopes: [],
                selectedDataGroupIds: []
            };
        }
    };

    const logRequestDebug = (label: string, data: any) => {
        try {
            console.log(`\n=========== ${label} ===========`);
            console.log(JSON.stringify(data, null, 2));
            console.log("================================\n");
        } catch {
            console.log(label, data);
        }
    };

    const loadFixedPrompts = async () => {
        const token = client ? await getToken(client) : undefined;
        const response = await getFixedPromptsApi(token);
        if (response) {
            setFixedPrompts(response.fixed_prompt);
        }
    };

    const readAgentUIPrefs = (username: string, teamId: string): Record<string, AgentUIPrefs> => {
        try {
            const raw = Storage.get(STORAGE_KEYS.ACTIVE_AGENT_UI_PREFS) as string | null;
            if (!raw) return {};

            const all = JSON.parse(raw);
            return all?.[username]?.[teamId] ?? {};
        } catch {
            return {};
        }
    };

    const writeAgentUIPrefs = (username: string, teamId: string, agentId: string, prefs: AgentUIPrefs) => {
        try {
            const raw = Storage.get(STORAGE_KEYS.ACTIVE_AGENT_UI_PREFS) as string | null;
            const all = raw ? JSON.parse(raw) : {};

            const userPrefs = all?.[username] ?? {};
            const teamPrefs = userPrefs?.[teamId] ?? {};

            all[username] = {
                ...userPrefs,
                [teamId]: {
                    ...teamPrefs,
                    [agentId]: prefs
                }
            };

            Storage.set(STORAGE_KEYS.ACTIVE_AGENT_UI_PREFS, JSON.stringify(all));
        } catch (err) {
            console.error("writeAgentUIPrefs failed:", err);
        }
    };

    const getTeamId = async (): Promise<string> => {
        const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
        const username = (await getUsername(instance)) ?? "";
        if (!activeTeams || !username) return "";

        return activeTeams?.[username]?._id ?? "";
    };

    const getAgentUIPrefs = async (agentId?: string | null): Promise<AgentUIPrefs | null> => {
        const username = (await getUsername(instance)) ?? "";
        const teamId = await getTeamId();

        if (!username || !teamId || !agentId) return null;

        const prefsMap = readAgentUIPrefs(username, teamId);
        return prefsMap?.[agentId] ?? null;
    };

    const setAgentUIPrefs = async (agentId: string, prefs: AgentUIPrefs) => {
        const username = (await getUsername(instance)) ?? "";
        const teamId = await getTeamId();

        if (!username || !teamId || !agentId) return;

        writeAgentUIPrefs(username, teamId, agentId, prefs);
    };

    const getConfig = async () => {
        configApi().then(config => {
            setLlmProfiles(config.llmProfiles ?? []);
            setShowGPT4VOptions(config.showGPT4VOptions);
            setChatDocumentAttachmentsEnabled(config.chatDocumentAttachmentsEnabled);
            setAgentRuntimeMode(config.agentRuntimeMode ?? "per_agent");
            setUseSemanticRanker(config.showSemanticRankerOption);
            setShowSemanticRankerOption(config.showSemanticRankerOption);
            setUseQueryRewriting(config.showQueryRewritingOption);
            setShowQueryRewritingOption(config.showQueryRewritingOption);
            setShowReasoningEffortOption(config.showReasoningEffortOption);
            setStreamingEnabled(config.streamingEnabled);
            if (!config.streamingEnabled) {
                setShouldStream(false);
            }
            if (config.showReasoningEffortOption) {
                setReasoningEffort(config.defaultReasoningEffort);
            }
            setShowVectorOption(config.showVectorOption);
            if (!config.showVectorOption) {
                setRetrievalMode(RetrievalMode.Text);
            }
            setShowUserUpload(config.showUserUpload);
            setshowLanguagePicker(config.showLanguagePicker);
            setShowSpeechInput(config.showSpeechInput);
            setShowSpeechOutputBrowser(config.showSpeechOutputBrowser);
            setShowSpeechOutputAzure(config.showSpeechOutputAzure);
            setShowChatHistoryBrowser(config.showChatHistoryBrowser);
            setShowChatHistoryCosmos(config.showChatHistoryCosmos);
            setShowAgenticRetrievalOption(config.showAgenticRetrievalOption);
            setUseAgenticRetrieval(config.showAgenticRetrievalOption);
            if (config.showAgenticRetrievalOption) {
                setRetrieveCount(10);
            }
        });
    };

    const getAgentModelName = (agent: Agent | null): string => {
        if (!agent) return "";
        const profileId = agent.config?.llm_profile_id ?? "system";
        return llmProfiles.find(profile => profile.id === profileId)?.model ?? profileId;
    };

    const selectedDataGroupNames = selectedDataGroupIds
        .map(groupId => dataGroups.find(group => group._id === groupId)?.name)
        .filter((name): name is string => Boolean(name));

    const handleAsyncRequest = async (question: string, answers: [string, ChatAppResponse][], responseBody: ReadableStream<any>) => {
        let answer: string = "";
        let askResponse: ChatAppResponse = {} as ChatAppResponse;

        const updateState = (newContent: string) => {
            return new Promise(resolve => {
                setTimeout(() => {
                    answer += newContent;
                    const latestResponse: ChatAppResponse = {
                        ...askResponse,
                        message: { content: answer, role: askResponse.message.role }
                    };
                    setStreamedAnswers([...answers, [question, latestResponse]]);
                    resolve(null);
                }, 33);
            });
        };
        try {
            setIsStreaming(true);
            for await (const event of readNDJSONStream(responseBody)) {
                if (event["context"] && event["context"]["data_points"]) {
                    event["message"] = event["delta"];
                    askResponse = event as ChatAppResponse;
                } else if (event["delta"] && event["delta"]["content"]) {
                    setIsLoading(false);
                    await updateState(event["delta"]["content"]);
                } else if (event["context"]) {
                    askResponse.context = { ...askResponse.context, ...event["context"] };
                } else if (event["error"]) {
                    throw Error(event["error"]);
                }
            }
        } finally {
            // isStreaming is now reset in makeApiRequest's finally block to avoid
            // an intermediate render cycle where isStreaming is false but answers isn't updated.
        }
        const fullResponse: ChatAppResponse = {
            ...askResponse,
            message: { content: answer, role: askResponse.message.role }
        };
        return fullResponse;
    };

    const historyProvider: HistoryProviderOptions = (() => {
        if (useLogin && showChatHistoryCosmos) return HistoryProviderOptions.CosmosDB;
        if (showChatHistoryBrowser) return HistoryProviderOptions.IndexedDB;
        return HistoryProviderOptions.None;
    })();
    const historyOwnerId = userDetails?._id;
    const historyManager = useHistoryManager(historyProvider, historyOwnerId);
    const previousHistoryOwnerId = useRef<string | undefined>(historyOwnerId);

    useLayoutEffect(() => {
        if (previousHistoryOwnerId.current === historyOwnerId) return;
        previousHistoryOwnerId.current = historyOwnerId;
        setAnswers([]);
        setStreamedAnswers([]);
        setTurnAttachments({});
        setTurnDocumentAttachments({});
        setActiveCitation(undefined);
        setActiveAnalysisPanelTab(undefined);
        setCurrentSessionId(null);
        setKeyword("");
        setResults([]);
        setSelectedAgent(null);
        conversationIdRef.current = crypto.randomUUID();
        lastQuestionRef.current = "";
    }, [historyOwnerId]);

    const handleSetFeedback = async (index: number, sentiment: "like" | "dislike") => {
        const base = isStreaming ? streamedAnswers : answers;
        if (index < 0 || index >= base.length || feedbackLoading[index]) return;
        setFeedbackLoading(prev => ({ ...prev, [index]: true }));

        try {
            const current = feedbacks[index] ?? null;
            const next = current === sentiment ? null : sentiment;

            // 🎯 อัปเดต UI ทันที
            setFeedbacks(prev => ({ ...prev, [index]: next }));

            const ans = (isStreaming ? streamedAnswers : answers)[index]?.[1];
            const token = client ? await getToken(client) : undefined;

            if (!ans || !token) return;

            // 🚀 Fire-and-forget — ไม่ await
            if (next) {
                createFeedbackApi(
                    {
                        sentiment: next,
                        question_text: (isStreaming ? streamedAnswers : answers)[index]?.[0] ?? "",
                        answer_text: ans.message?.content ?? "",
                        session_state: ans.session_state ?? null,
                        answer_index: index,
                        agent_name: (ans as any)?.agent_name ?? null,
                        metadata: { source: "chat-ui" }
                    },
                    token
                );
            } else if (ans.session_state) {
                deleteFeedbackApi(ans.session_state, index, token);
            }
        } finally {
            setFeedbackLoading(prev => ({ ...prev, [index]: false }));
        }
    };

    const handleAction = async (actionId: string, index: number) => {
        // 🔒 ปิดปุ่มตัวที่กดในข้อความนั้น ๆ
        setAnswers(prev => {
            const updated = [...prev];
            const current = { ...updated[index][1] };
            if (current.context?.actions) {
                current.context.actions = current.context.actions.map(a => (a.id === actionId ? { ...a, disabled: true } : a));
            }
            updated[index][1] = current;
            return updated;
        });
    };

    const buildAnswersWithFeedback = (base: [string, ChatAppResponse][], extraLast?: [string, ChatAppResponse]) => {
        const merged: [string, ChatAppResponse][] = base.map((a, i) => [
            a[0],
            {
                ...a[1],
                context: { ...(a[1]?.context || {}), ...(feedbacks[i] != null ? { _feedback: feedbacks[i] } : {}) }
            }
        ]);
        if (extraLast) {
            const idx = merged.length;
            merged.push([
                extraLast[0],
                {
                    ...extraLast[1],
                    context: { ...(extraLast[1]?.context || {}), ...(feedbacks[idx] != null ? { _feedback: feedbacks[idx] } : {}) }
                }
            ]);
        }
        return merged;
    };

    const buildPromptString = (agentPrompt: any, fixedPrompts?: string) => {
        const sections: string[] = [];

        if (!agentPrompt) return fixedPrompts ?? "";

        if (agentPrompt.role) {
            sections.push(`Role:\n${agentPrompt.role}`);
        }

        if (agentPrompt.task) {
            sections.push(`Task:\n${agentPrompt.task}`);
        }

        if (agentPrompt.detail_context) {
            sections.push(`Detail Context:\n${agentPrompt.detail_context}`);
        }

        if (agentPrompt.constraints) {
            sections.push(`Constraints:\n${agentPrompt.constraints}`);
        }

        if (agentPrompt.output_format) {
            sections.push(`Output Format:\n${agentPrompt.output_format}`);
        }

        let result = sections.join("\n\n");

        if (fixedPrompts && fixedPrompts.trim().length > 0) {
            result = `${result}\n\n${fixedPrompts}`;
        }

        return result;
    };

    function applyYesNoUI(resp: ChatAppResponse): ChatAppResponse {
        const raw = resp?.message?.content ?? "";
        // หา [y/n] หรือ [Y/N] (จะมีช่องว่างรอบๆ ก็ได้)
        const hasYN = /\[\s*y\s*\/\s*n\s*\]/i.test(raw);
        if (!hasYN) return resp;

        // ตัด [y/n] ออกทุกตำแหน่ง แล้ว trim
        const cleaned = raw.replace(/\s*\[\s*y\s*\/\s*n\s*\]\s*/gi, "").trim();

        const prevActions = resp.context?.actions ?? [];
        const nextActions = [
            ...prevActions,
            { id: "yn-yes", label: "Yes", variant: "contained" as const },
            { id: "yn-no", label: "No", variant: "outlined" as const }
        ];

        return {
            ...resp,
            message: { ...resp.message, content: cleaned },
            context: { ...(resp.context || {}), actions: nextActions }
        };
    }

    const makeApiRequest = async (
        question: string,
        api_result?: any,
        attachments: ChatAttachmentInput[] = [],
        documents: ChatDocumentAttachment[] = [],
        evidenceOptions?: EvidenceMatrixOptions
    ) => {
        lastQuestionRef.current = question;

        const requestIndex = answers.length;
        setTurnAttachments(current => {
            const next = { ...current };
            if (attachments.length > 0) next[requestIndex] = [...attachments];
            else delete next[requestIndex];
            return next;
        });
        setTurnDocumentAttachments(current => {
            const next = { ...current };
            if (documents.length > 0) next[requestIndex] = [...documents];
            else delete next[requestIndex];
            return next;
        });

        error && setError(undefined);
        setIsLoading(true);
        setActiveCitation(undefined);
        setActiveAnalysisPanelTab(undefined);

        // 1) ดึง username แบบ async
        const name = (await getUsername(instance)) ?? "";

        const savedPrompts = JSON.parse(localStorage.getItem("activePrompts") || "{}");
        const prompt = savedPrompts[email] || "";

        const token = client ? await getToken(client) : undefined;

        try {
            const rawActiveAgent = Storage.get(STORAGE_KEYS.ACTIVE_AGENT);
            const activeAgent = JSON.parse(rawActiveAgent as string);
            const agentName = activeAgent ? activeAgent?.agent_name : "";
            const uiPrefsPayload = await buildAgentUIPrefsPayload();
            const promptString = buildPromptString(activeAgent?.prompt, fixedPrompts);

            if (uiPrefsPayload) {
                if (uiPrefsPayload.selectedDataGroupIds.length == 0 && uiPrefsPayload.selectedScopes.length == 0) {
                    showNotification("Please select at least one data group or scope.", "warning");
                    return;
                }
            }

            const messages: ResponseMessage[] = answers.flatMap(a => [
                { content: a[0], role: "user" },
                { content: a[1].message.content, role: "assistant" }
            ]);

            const request: ChatAppRequest = {
                usage_request_id: crypto.randomUUID(),
                messages: [...messages, { content: question, role: "user" }],
                ...(attachments.length ? { attachments } : {}),
                ...(documents.length ? { document_attachment_ids: documents.map(document => document.id) } : {}),
                ...(evidenceOptions?.evidenceMatrix
                    ? {
                          evidence_matrix: true,
                          attachment_evidence_scope: evidenceOptions.attachmentEvidenceScope
                      }
                    : {}),
                conversation_id: conversationIdRef.current,
                context: {
                    overrides: {
                        prompt_template: promptString.length === 0 ? undefined : promptString,
                        include_category: includeCategory.length === 0 ? undefined : includeCategory,
                        exclude_category: excludeCategory.length === 0 ? undefined : excludeCategory,
                        top: activeAgent ? activeAgent?.config?.max_search_results : retrieveCount,
                        max_subqueries: maxSubqueryCount,
                        results_merge_strategy: resultsMergeStrategy,
                        temperature: activeAgent.config ? activeAgent?.config?.temperature : temperature,
                        minimum_reranker_score: minimumRerankerScore,
                        minimum_search_score: activeAgent.config ? activeAgent?.config?.min_search_score : minimumSearchScore,
                        retrieval_mode: retrievalMode,
                        semantic_ranker: useSemanticRanker,
                        semantic_captions: useSemanticCaptions,
                        query_rewriting: useQueryRewriting,
                        reasoning_effort: reasoningEffort,
                        suggest_followup_questions: useSuggestFollowupQuestions,
                        use_oid_security_filter: useOidSecurityFilter,
                        use_groups_security_filter: useGroupsSecurityFilter,
                        vector_fields: vectorFields,
                        use_gpt4v: attachments.length > 0 && visionAvailable,
                        gpt4v_input: gpt4vInput,
                        language: i18n.language,
                        use_agentic_retrieval: attachments.length > 0 ? false : useAgenticRetrieval,
                        max_tokens: activeAgent?.config?.max_tokens,
                        ...(seed !== null ? { seed: activeAgent ? (activeAgent?.config == null ? seed : activeAgent?.config?.seed) : seed } : {})
                    }
                },
                session_state: answers.length ? answers[answers.length - 1][1].session_state : null
            };

            request["team_id"] = selectTeamData ? selectTeamData?._id : null;
            request["agent_name"] = activeAgent ? activeAgent?.agent_name : null;
            request["agent_id"] = activeAgent ? activeAgent?._id : null;
            request["data_groups_id"] = uiPrefsPayload ? uiPrefsPayload.selectedDataGroupIds : null;
            request["selected_scopes"] = uiPrefsPayload ? uiPrefsPayload.selectedScopes : null;
            request["api_result"] = api_result ? api_result : null;
            const response = await chatApi(request, shouldStream, token);
            if (!response.body) {
                throw Error("No response body");
            }
            if (response.status > 299 || !response.ok) {
                const errorResponse = await response.json().catch(() => undefined);
                throw Error(errorResponse?.error || `Request failed with status ${response.status}`);
            }
            if (shouldStream) {
                const parsedResponse: ChatAppResponse = await handleAsyncRequest(question, answers, response.body);
                // ✨ inject agent_name จาก localStorage
                (parsedResponse as any).agent_name = agentName;
                const finalResponse = applyYesNoUI(parsedResponse);

                setAnswers([...answers, [question, finalResponse]]);
                if (typeof finalResponse.session_state === "string" && finalResponse.session_state !== "") {
                    const token = client ? await getToken(client) : undefined;
                    historyManager.addItem(finalResponse.session_state, [...answers, [question, finalResponse]], token);
                }
            } else {
                const parsedResponse: ChatAppResponseOrError = await response.json();
                if (parsedResponse.error) {
                    throw Error(parsedResponse.error);
                }
                // ✨ inject agent_name
                (parsedResponse as any).agent_name = agentName;
                const finalResponse = applyYesNoUI(parsedResponse);

                setAnswers([...answers, [question, finalResponse as ChatAppResponse]]);
                if (typeof finalResponse.session_state === "string" && finalResponse.session_state !== "") {
                    const token = client ? await getToken(client) : undefined;
                    historyManager.addItem(finalResponse.session_state, [...answers, [question, finalResponse as ChatAppResponse]], token);
                }
            }
            setSpeechUrls([...speechUrls, null]);
        } catch (e) {
            setError(e);
        } finally {
            setIsLoading(false);
            setIsStreaming(false);
        }
    };

    const clearChat = () => {
        lastQuestionRef.current = "";
        conversationIdRef.current = crypto.randomUUID();
        error && setError(undefined);
        setActiveCitation(undefined);
        setActiveAnalysisPanelTab(undefined);
        setAnswers([]);
        setSpeechUrls([]);
        setStreamedAnswers([]);
        setTurnAttachments({});
        setTurnDocumentAttachments({});
        setIsLoading(false);
        setIsStreaming(false);
    };

    useEffect(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" });
    }, [isLoading]);
    useEffect(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "auto" });
    }, [streamedAnswers]);
    useEffect(() => {
        getConfig();
        const refreshCapabilities = () => {
            void configApi().then(config => {
                setLlmProfiles(config.llmProfiles ?? []);
                setShowGPT4VOptions(config.showGPT4VOptions);
                setChatDocumentAttachmentsEnabled(config.chatDocumentAttachmentsEnabled);
                setAgentRuntimeMode(config.agentRuntimeMode ?? "per_agent");
            });
        };
        window.addEventListener("nexora:llm-profiles-changed", refreshCapabilities);
        return () => window.removeEventListener("nexora:llm-profiles-changed", refreshCapabilities);
    }, []);

    // Detect outside click
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as HTMLElement;

            const isInsideMenu = menuRef.current?.contains(target);
            const isInsideDropdown = dropdownRef.current?.contains(target); // 👈 เพิ่ม
            const isInsideMUIDialog = !!target.closest(".MuiDialog-container");
            const hasOpenDialog = !!document.querySelector(".MuiDialog-root");

            if (!isInsideMenu && !isInsideDropdown && !isInsideMUIDialog && !hasOpenDialog) {
                setMenuOpen(false);
            }
        };

        if (menuOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        }

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [menuOpen]);

    const handleSettingsChange = (field: string, value: any) => {
        switch (field) {
            case "promptTemplate":
                setPromptTemplate(value);
                break;
            case "temperature":
                setTemperature(value);
                break;
            case "seed":
                setSeed(value);
                break;
            case "minimumRerankerScore":
                setMinimumRerankerScore(value);
                break;
            case "minimumSearchScore":
                setMinimumSearchScore(value);
                break;
            case "retrieveCount":
                setRetrieveCount(value);
                break;
            case "maxSubqueryCount":
                setMaxSubqueryCount(value);
                break;
            case "resultsMergeStrategy":
                setResultsMergeStrategy(value);
                break;
            case "useSemanticRanker":
                setUseSemanticRanker(value);
                break;
            case "useQueryRewriting":
                setUseQueryRewriting(value);
                break;
            case "reasoningEffort":
                setReasoningEffort(value);
                break;
            case "useSemanticCaptions":
                setUseSemanticCaptions(value);
                break;
            case "excludeCategory":
                setExcludeCategory(value);
                break;
            case "includeCategory":
                setIncludeCategory(value);
                break;
            case "useOidSecurityFilter":
                setUseOidSecurityFilter(value);
                break;
            case "useGroupsSecurityFilter":
                setUseGroupsSecurityFilter(value);
                break;
            case "shouldStream":
                setShouldStream(value);
                break;
            case "useSuggestFollowupQuestions":
                setUseSuggestFollowupQuestions(value);
                break;
            case "useGPT4V":
                setUseGPT4V(value);
                break;
            case "gpt4vInput":
                setGPT4VInput(value);
                break;
            case "vectorFields":
                setVectorFields(value);
                break;
            case "retrievalMode":
                setRetrievalMode(value);
                break;
            case "useAgenticRetrieval":
                setUseAgenticRetrieval(value);
                if (value) setUseGPT4V(false);
        }
    };

    const onExampleClicked = (example: string) => {
        makeApiRequest(example);
    };

    const normalizeExternalUrl = (u: string) => {
        const s = u.trim();
        try {
            const url = new URL(s);
            url.hash = ""; // ไม่สน #anchor
            url.pathname = url.pathname.replace(/\/+$/, ""); // ตัด / ท้ายพาธ (ยกเว้น root)
            return url.toString();
        } catch {
            return s.replace(/#.*$/, "").replace(/\/+$/, "").trim();
        }
    };

    const onShowCitation = (citation: string, index: number) => {
        const temporaryCitation = getTemporaryCitationFilePath(citation, conversationIdRef.current);
        const resolvedCitation = temporaryCitation ?? citation;
        const raw = resolvedCitation.replace("/content/", "");
        const isExternal = !temporaryCitation && /^https?:\/\//i.test(raw);

        if (isExternal) {
            const nextUrl = normalizeExternalUrl(raw);
            const currentUrl = activeWebUrl ? normalizeExternalUrl(activeWebUrl) : undefined;

            // ✅ เหมือนเคสไฟล์: ถ้าคลิกลิงก์เดิม และแท็บเดิม → ปิด
            if (
                activeAnalysisPanelTab === AnalysisPanelTabs.WebTab &&
                currentUrl === nextUrl
                // ไม่บังคับ selectedAnswer === index เพื่อให้ปิดง่ายเหมือนรูป/ไฟล์
            ) {
                setActiveAnalysisPanelTab(undefined);
                setActiveWebUrl(undefined);
            } else {
                setActiveCitation(undefined);
                setActiveWebUrl(nextUrl);
                setActiveAnalysisPanelTab(AnalysisPanelTabs.WebTab);
            }
        } else {
            // พฤติกรรมเดิมสำหรับไฟล์/รูป (CitationTab)
            setActiveWebUrl(undefined);
            if (
                activeCitation === resolvedCitation &&
                activeAnalysisPanelTab === AnalysisPanelTabs.CitationTab
                // จะคงหรือเอา selectedAnswer === index ก็ได้ แต่เพื่อให้พฤติกรรมเหมือนกัน ให้ละออกได้
            ) {
                setActiveAnalysisPanelTab(undefined);
            } else {
                setActiveCitation(resolvedCitation);
                setActiveAnalysisPanelTab(AnalysisPanelTabs.CitationTab);
            }
        }

        setSelectedAnswer(index);
    };

    const onToggleTab = (tab: AnalysisPanelTabs, index: number) => {
        if (activeAnalysisPanelTab === tab && selectedAnswer === index) {
            setActiveAnalysisPanelTab(undefined);
        } else {
            setActiveAnalysisPanelTab(tab);
        }

        setSelectedAnswer(index);
    };

    const { t, i18n } = useTranslation();

    const toggleMenu = () => {
        setMenuOpen(!menuOpen);
    };

    const hasRole = (roles: string | string[] | undefined, check: string[]) => {
        if (!roles) return false;
        if (Array.isArray(roles)) {
            return roles.some(r => check.includes(r));
        }
        return check.includes(roles);
    };

    const startNewChat = async () => {
        if (answers.length === 0) {
            // 👉 ถ้าแชทว่าง: แค่เคลียร์ state, ไม่ต้องสร้าง history ใหม่
            clearChat();
            return;
        }

        // 👉 ถ้าไม่ว่าง: เก็บ history ปัจจุบัน แล้วเริ่ม session ใหม่
        clearChat();
        const newSessionId = `session-${Date.now()}`;
        const token = client ? await getToken(client) : undefined;
        historyManager.addItem(newSessionId, [], token);
    };

    const collectSearchableText = (item: any): string => {
        const parts: string[] = [];

        // 1. title
        if (typeof item?.title === "string") {
            parts.push(item.title);
        }

        // 2. answers: user questions + assistant answers
        if (Array.isArray(item?.answers)) {
            for (const ans of item.answers) {
                // คำถามของ user
                if (typeof ans?.[0] === "string") {
                    parts.push(ans[0]);
                }

                // คำตอบของ assistant
                const answer = ans?.[1]?.message?.content;
                if (typeof answer === "string") {
                    parts.push(answer);
                }
            }
        }

        return parts.join(" ");
    };

    const handleSearch = async (keyword: string) => {
        setKeyword(keyword);

        const q = keyword.trim();
        if (!q) {
            setResults([]);
            return;
        }

        setLoading(true);
        try {
            // @ts-ignore (ถ้าตัว type ของ historyManager ยังไม่รู้จัก getAllItems)
            const all = await historyManager.getAllItems();

            const lower = q.toLowerCase();
            // const next = (all || []).filter((it: any) => {
            //     const title = (it?.title ?? "").toLowerCase();
            //     const answers = (it?.answers ?? []).map((a: any) => (a?.[0] ?? "").toLowerCase());
            //     return title.includes(lower) || answers.some((t: string) => t.includes(lower));
            // });

            const next = (all || []).filter((it: any) => {
                const text = collectSearchableText(it).toLowerCase();
                return text.includes(lower);
            });

            setResults(next);
        } catch (e) {
            console.error("search error:", e);
            setResults([]);
        } finally {
            setLoading(false);
        }
    };

    const loadHistoryItem = (item: any) => {
        const answersFromHistory = (item.answers ?? []) as [string, ChatAppResponse][];
        const restoredSessionState = answersFromHistory.at(-1)?.[1]?.session_state;
        conversationIdRef.current =
            typeof restoredSessionState === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(restoredSessionState)
                ? restoredSessionState
                : crypto.randomUUID();

        // 1) อัปเดต state ให้แชทโหลดบทสนทนานี้
        setAnswers(answersFromHistory);
        // Inline images are deliberately session-only and are never restored
        // from browser/Cosmos history.
        setTurnAttachments({});
        setTurnDocumentAttachments({});

        // 2) เซ็ต last question
        if (answersFromHistory.length > 0) {
            lastQuestionRef.current = answersFromHistory[answersFromHistory.length - 1][0];
        } else {
            lastQuestionRef.current = "";
        }

        setKeyword("");
        setResults([]);

        // 3) ปิด dialog
        setOpenSearch(false);

        // 4) เลื่อนลงล่างสุดให้เห็นข้อความล่าสุด
        setTimeout(() => {
            chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" });
        }, 50);
    };

    const handleSelectAgent = async (agent: Agent) => {
        setSelectedAgent(agent);

        const username = (await getUsername(instance)) ?? "";
        const teamId = await getTeamId();
        const agentId = agent?._id;

        if (!username || !teamId || !agentId) return;

        // ✅ IMPORTANT: persist ACTIVE_AGENT ทันที
        try {
            const raw = Storage.get<string>(STORAGE_KEYS.ACTIVE_AGENT);
            const all = raw ? JSON.parse(raw) : {};
            Storage.set(STORAGE_KEYS.ACTIVE_AGENT, JSON.stringify(agent));
            // Storage.set(
            //     STORAGE_KEYS.ACTIVE_AGENT,
            //     JSON.stringify({
            //         ...all,
            //         [username]: {
            //             ...(all?.[username] ?? {}),
            //             [teamId]: agent
            //         }
            //     })
            // );
        } catch (err) {
            console.error("persist ACTIVE_AGENT failed:", err);
        }

        // ✅ โหลด prefs ของ agent นี้
        const prefsMap = readAgentUIPrefs(username, teamId);
        const prefs = prefsMap?.[agentId];

        if (prefs) {
            const scopes = prefs.selectedScopes ?? [];
            const groups = prefs.selectedDataGroupIds ?? [];

            setSelectedScopes(scopes);
            setSelectedDataGroupIds(groups);

            setDraftScopes(scopes);
            setDraftDataGroupIds(groups);
        } else {
            const scopes = isDefaultAgent(agent) ? (["global"] as DataScope[]) : [];
            const groups: string[] = [];

            setSelectedScopes(scopes);
            setSelectedDataGroupIds(groups);

            setDraftScopes(scopes);
            setDraftDataGroupIds(groups);

            // ✅ สร้าง prefs default ให้ agent นี้ทันที (กัน refresh แล้ว revert)
            await setAgentUIPrefs(agentId, {
                selectedScopes: scopes,
                selectedDataGroupIds: groups
            });
        }

        setIsInitialAgentSetup(false);
    };

    const restoreActiveTeam = async () => {
        const username = (await getUsername(instance)) ?? "";
        if (!username) return;

        const activeTeams = (Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, TeamProfile> | null) ?? {};
        const availableTeams = AuthStorage.get()?.teams ?? [];
        const savedTeam = activeTeams[username];
        const nextTeam = availableTeams.find(team => team._id === savedTeam?._id) ?? availableTeams[0] ?? null;

        if (nextTeam) {
            activeTeams[username] = nextTeam;
        } else {
            delete activeTeams[username];
        }

        Storage.set(STORAGE_KEYS.Active_Teams, activeTeams);
        setSelectTeamData(nextTeam);
    };

    const activateCreatedTeam = useCallback(
        async (team: TeamProfile) => {
            const username = (await getUsername(instance)) ?? "";
            if (!username) return;

            const activeTeams = (Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, TeamProfile> | null) ?? {};
            activeTeams[username] = team;
            Storage.set(STORAGE_KEYS.Active_Teams, activeTeams);
            Storage.remove(STORAGE_KEYS.ACTIVE_AGENT);

            const authProfile = AuthStorage.get();
            if (authProfile) {
                const teams = authProfile.teams.some(item => item._id === team._id)
                    ? authProfile.teams.map(item => (item._id === team._id ? team : item))
                    : [...authProfile.teams, team];
                AuthStorage.set({ ...authProfile, teams });
            }

            setSelectTeamData(team);
            window.dispatchEvent(new CustomEvent<TeamProfile>(ACTIVE_TEAM_CHANGED_EVENT, { detail: team }));
            setIsSwitchTeam(true);
        },
        [instance, setIsSwitchTeam]
    );

    const loadAgents = useCallback(async () => {
        // ✅ กัน StrictMode
        // if (didLoadAgentsRef.current) return;
        // didLoadAgentsRef.current = true;

        if (!loggedIn) return;

        setIsAgentsLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) return;

            const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
            if (!activeTeams) {
                console.warn("[loadAgents] Active_Teams not found");
                return;
            }

            const username = (await getUsername(instance)) ?? "";
            if (!username) return;

            const team = activeTeams[username];
            const teamId = team?._id;
            if (!teamId) return;

            // 1) โหลด agents
            const list = await get_agent_by_team(teamId, token);
            const agentsList: Agent[] = list ?? [];
            setAgents(agentsList);

            if (agentsList.length === 0) {
                setSelectedAgent(null);
                setSelectedScopes([]);
                setSelectedDataGroupIds([]);
                setDraftScopes([]);
                setDraftDataGroupIds([]);
                setIsInitialAgentSetup(false);
                return;
            }

            // 2) Restore ACTIVE_AGENT (agent object ตรง ๆ)
            let savedAgent: Agent | null = null;
            try {
                const raw = Storage.get<string>(STORAGE_KEYS.ACTIVE_AGENT);
                savedAgent = raw ? JSON.parse(raw) : null;
            } catch {
                savedAgent = null;
            }

            let restoredAgent: Agent | null = null;

            if (savedAgent?._id) {
                // The stored object only identifies the active Agent. Its prompt and
                // model configuration must always come from the backend so provider
                // capability changes cannot be masked by a stale local snapshot.
                restoredAgent = agentsList.find(a => a._id === savedAgent._id) ?? null;
            }

            // 3) agent ที่จะใช้จริง
            const nextSelectedAgent = restoredAgent ?? agentsList[0];
            setSelectedAgent(nextSelectedAgent);

            // 4) Keep the cache aligned with the backend snapshot.
            Storage.set(STORAGE_KEYS.ACTIVE_AGENT, JSON.stringify(nextSelectedAgent));

            // 5) Restore ACTIVE_AGENT_UI_PREFS (เหมือนเดิม)
            const prefsMap = readAgentUIPrefs(username, teamId);
            const prefs = prefsMap?.[nextSelectedAgent._id];

            const isDefault = nextSelectedAgent._id === agentsList[0]?._id;

            const scopes: DataScope[] = prefs?.selectedScopes ?? (isDefault ? (["global"] as DataScope[]) : []);
            const groups: string[] = prefs?.selectedDataGroupIds ?? [];

            setSelectedScopes(scopes);
            setSelectedDataGroupIds(groups);
            setDraftScopes(scopes);
            setDraftDataGroupIds(groups);

            if (!prefs) {
                await setAgentUIPrefs(nextSelectedAgent._id, {
                    selectedScopes: scopes,
                    selectedDataGroupIds: groups
                });
            }

            setIsInitialAgentSetup(false);
        } catch (err) {
            console.error("load agents failed:", err);

            setAgents([]);
            setSelectedAgent(null);
            setSelectedScopes([]);
            setSelectedDataGroupIds([]);
            setDraftScopes([]);
            setDraftDataGroupIds([]);
            setIsInitialAgentSetup(false);
        } finally {
            setIsAgentsLoading(false);
        }
    }, [loggedIn, instance]);

    const loadDataGroups = useCallback(async () => {
        // ✅ กัน StrictMode dev ยิงซ้ำ
        // if (didLoadGroupsRef.current) return;
        // didLoadGroupsRef.current = true;

        if (!loggedIn) return;

        setIsGroupsLoading(true);
        try {
            const token = await getToken(instance);
            if (!token) return;

            const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
            if (!activeTeams) return;

            const username = (await getUsername(instance)) ?? "";
            if (!username) return;

            const team = activeTeams[username];
            const teamId = team?._id;
            if (!teamId) return;

            const access = await getEffectiveAccess(teamId, token);
            setDataGroups(access.data_groups);
            setEffectiveAccessError("");
        } catch (err) {
            console.error("load data groups failed:", err);
            setDataGroups([]);
            setEffectiveAccessError(err instanceof Error ? err.message : "Unable to load effective data access.");
        } finally {
            setIsGroupsLoading(false);
        }
    }, [loggedIn, instance]);

    const reloadAll = useCallback(async () => {
        await restoreActiveTeam();
        await loadAgents();
        await loadDataGroups();
    }, [loadAgents, loadDataGroups]);

    useEffect(() => {
        if (!loggedIn || isUserLoading) return;

        const run = async () => {
            await reloadAll();

            // ✅ reset flag กันยิงซ้ำ
            if (isSwitchTeam) {
                setIsSwitchTeam(false);
            }
        };

        run();
    }, [loggedIn, isUserLoading, isSwitchTeam, reloadAll, setIsSwitchTeam]);

    useEffect(() => {
        if (!loggedIn || isUserLoading) return;

        const user = AuthStorage.get()?.user ?? null;
        const sys_permissions = AuthStorage.get()?.sys_permissions ?? null;
        setUserData(user);
        setSysPers(sys_permissions);

        loadFixedPrompts();
    }, [loggedIn, isUserLoading]);

    useEffect(() => {
        const ensureDefaultGroupPref = async () => {
            if (!selectedAgent?._id) return;
            if (dataGroups.length === 0) return;

            const username = (await getUsername(instance)) ?? "";
            const teamId = await getTeamId();
            if (!username || !teamId) return;

            // มีแล้วไม่ต้องทำ
            if (selectedDataGroupIds.length > 0) return;

            // ✅ default group: ตัวแรก
            const nextGroups = [dataGroups[0]._id];

            setSelectedDataGroupIds(nextGroups);
            setDraftDataGroupIds(nextGroups);

            // ✅ persist เข้า ACTIVE_AGENT_UI_PREFS ด้วยทันที
            await setAgentUIPrefs(selectedAgent._id, {
                selectedScopes,
                selectedDataGroupIds: nextGroups
            });
        };

        ensureDefaultGroupPref();
    }, [dataGroups, selectedAgent?._id]);

    useEffect(() => {
        if (isGroupsLoading) return;
        const availableIds = new Set(dataGroups.map(group => group._id));
        setSelectedDataGroupIds(current => current.filter(id => availableIds.has(id)));
        setDraftDataGroupIds(current => current.filter(id => availableIds.has(id)));
    }, [dataGroups, isGroupsLoading]);

    useEffect(() => {
        if (!loggedIn || isUserLoading) return;
        restoreActiveTeam();
    }, [loggedIn, isUserLoading]);

    const testLogPayload = async () => {
        const raw = Storage.get(STORAGE_KEYS.ACTIVE_AGENT_UI_PREFS);
        logRequestDebug("RAW ACTIVE_AGENT_UI_PREFS", raw);

        const rawActiveAgent = Storage.get(STORAGE_KEYS.ACTIVE_AGENT);
        const activeAgent = JSON.parse(rawActiveAgent as string);

        console.log(activeAgent); // "default"

        const uiPrefsPayload = await buildAgentUIPrefsPayload();
        console.log(uiPrefsPayload.selectedScopes);

        logRequestDebug("UI PREFS PAYLOAD", uiPrefsPayload);
    };

    // useEffect(() => {
    //     if (!loggedIn) return;
    //     if (!selectedAgent?._id) return;
    //     if (dataGroups.length === 0) return; // ✅ รอ group โหลดเสร็จ

    //     testLogPayload();
    // }, [loggedIn, selectedAgent?._id, dataGroups.length]);

    const canOpenAdminManagement = hasPermission({
        is_sys_admin: userData?.is_sys_admin ?? false,
        permissions: selectTeamData?.permissions ?? [],
        sys_permissions: sysPers ?? [],
        requiredPermissions: [
            "Manage team users",
            "Manage team data groups",
            "Manage agents",
            "Manage team permissions",
            "Approve team users",
            "Manage teams",
            "Manage users"
        ]
    });
    const canManageUploads = hasPermission({
        is_sys_admin: userData?.is_sys_admin ?? false,
        permissions: selectTeamData?.permissions ?? [],
        sys_permissions: sysPers ?? [],
        requiredPermissions: ["Manage team uploads", "Manage global uploads"]
    });
    const canViewFeedbackDashboard = hasPermission({
        is_sys_admin: userData?.is_sys_admin ?? false,
        permissions: selectTeamData?.permissions ?? [],
        sys_permissions: sysPers ?? [],
        requiredPermissions: ["View feedback dashboard"]
    });

    return (
        <div className={styles.container}>
            <Helmet>
                <title>{t("pageTitle")}</title>
            </Helmet>

            {/* Popup Confirm */}
            <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
                <DialogTitle>Confirm Clear Chat</DialogTitle>
                <DialogContent>Do you want to clear all chat history?</DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfirmOpen(false)} color="primary">
                        Cancel
                    </Button>
                    <Button
                        onClick={() => {
                            setConfirmOpen(false);
                            clearChat();
                        }}
                        color="error"
                        variant="contained"
                    >
                        Clear Chat
                    </Button>
                </DialogActions>
            </Dialog>
            <div className={styles.chatRoot} style={{ marginLeft: isHistoryCollapsed ? "72px" : "260px" }}>
                <div className={styles.chatContainer}>
                    <div className={styles.chatContextBar}>
                        {isPageLoading ? (
                            <Skeleton variant="rectangular" width={280} height={56} sx={{ borderRadius: 2.5 }} />
                        ) : (
                            <AgentSelectionSummary
                                agentName={selectedAgent?.agent_name}
                                modelName={getAgentModelName(selectedAgent)}
                                teamName={selectTeamData?.name}
                                selectedScopes={selectedScopes}
                                selectedDataGroups={selectedDataGroupNames}
                                onClick={setAgentAnchorEl}
                            />
                        )}
                    </div>

                    {!lastQuestionRef.current ? (
                        <div className={styles.chatEmptyState}>
                            {/* <img src={appLogo} alt="App logo" width="120" height="120" /> */}
                            <div className={styles.sparkleLogo}>
                                ✦<span className={styles.orb1}></span>
                                <span className={styles.orb2}></span>
                                <span className={styles.orb3}></span>
                            </div>

                            <h1 className={styles.chatEmptyStateTitle}>{t("chatEmptyStateTitle")}</h1>
                            {showLanguagePicker && <LanguagePicker onLanguageChange={newLang => i18n.changeLanguage(newLang)} />}
                        </div>
                    ) : (
                        <div className={styles.chatMessageStream}>
                            {isStreaming &&
                                streamedAnswers.map((streamedAnswer, index) => (
                                    <div key={index}>
                                        <UserChatMessage message={streamedAnswer[0]} attachments={turnAttachments[index]} documents={turnDocumentAttachments[index]} />
                                        <div className={styles.chatMessageGpt}>
                                            <Answer
                                                isStreaming={true}
                                                key={index}
                                                answer={streamedAnswer[1]}
                                                index={index}
                                                speechConfig={speechConfig}
                                                isSelected={false}
                                                onCitationClicked={c => onShowCitation(c, index)}
                                                onThoughtProcessClicked={() => onToggleTab(AnalysisPanelTabs.ThoughtProcessTab, index)}
                                                onSupportingContentClicked={() => onToggleTab(AnalysisPanelTabs.SupportingContentTab, index)}
                                                onFollowupQuestionClicked={q => makeApiRequest(q)}
                                                showFollowupQuestions={useSuggestFollowupQuestions && answers.length - 1 === index}
                                                showSpeechOutputAzure={showSpeechOutputAzure}
                                                showSpeechOutputBrowser={showSpeechOutputBrowser}
                                                agentName={(streamedAnswer[1] as any).agent_name}
                                                onAction={actionId => handleAction(actionId, index)}
                                                feedback={feedbacks[index] ?? null}
                                                feedbackSubmitting={!!feedbackLoading[index]}
                                                onSetFeedback={sentiment => handleSetFeedback(index, sentiment)}
                                            />
                                        </div>
                                    </div>
                                ))}
                            {!isStreaming &&
                                answers.map((answer, index) => (
                                    <div key={index}>
                                        <UserChatMessage message={answer[0]} attachments={turnAttachments[index]} documents={turnDocumentAttachments[index]} />
                                        <div className={styles.chatMessageGpt}>
                                            <Answer
                                                isStreaming={false}
                                                key={index}
                                                answer={answer[1]}
                                                index={index}
                                                speechConfig={speechConfig}
                                                isSelected={selectedAnswer === index && activeAnalysisPanelTab !== undefined}
                                                onCitationClicked={c => onShowCitation(c, index)}
                                                onThoughtProcessClicked={() => onToggleTab(AnalysisPanelTabs.ThoughtProcessTab, index)}
                                                onSupportingContentClicked={() => onToggleTab(AnalysisPanelTabs.SupportingContentTab, index)}
                                                onFollowupQuestionClicked={q => makeApiRequest(q)}
                                                showFollowupQuestions={useSuggestFollowupQuestions && answers.length - 1 === index}
                                                showSpeechOutputAzure={showSpeechOutputAzure}
                                                showSpeechOutputBrowser={showSpeechOutputBrowser}
                                                agentName={(answer[1] as any).agent_name}
                                                onAction={actionId => handleAction(actionId, index)}
                                                feedback={feedbacks[index] ?? null}
                                                feedbackSubmitting={!!feedbackLoading[index]}
                                                onSetFeedback={sentiment => handleSetFeedback(index, sentiment)}
                                            />
                                        </div>
                                    </div>
                                ))}
                            {(isLoading || isWaitingForStreamedTurn) && (
                                <>
                                    <UserChatMessage message={lastQuestionRef.current} attachments={turnAttachments[answers.length]} documents={turnDocumentAttachments[answers.length]} />
                                    <div className={styles.chatMessageGptMinWidth}>
                                        <AnswerLoading />
                                    </div>
                                </>
                            )}
                            {error ? (
                                <>
                                    <UserChatMessage message={lastQuestionRef.current} attachments={turnAttachments[answers.length]} documents={turnDocumentAttachments[answers.length]} />
                                    <div className={styles.chatMessageGptMinWidth}>
                                        <AnswerError
                                            error={error.toString()}
                                            onRetry={() =>
                                                makeApiRequest(
                                                    lastQuestionRef.current,
                                                    undefined,
                                                    turnAttachments[answers.length] ?? [],
                                                    turnDocumentAttachments[answers.length] ?? []
                                                )
                                            }
                                        />
                                    </div>
                                </>
                            ) : null}
                            <div ref={chatMessageStreamEnd} />
                        </div>
                    )}
                    {isPageLoading ? (
                        <>
                            <Skeleton variant="rectangular" width={980} height={90} sx={{ mb: 1, borderRadius: "0.5rem" }} />
                        </>
                    ) : (
                        <div className={styles.chatInput}>
                            <QuestionInput
                                clearOnSend
                                placeholder={t("defaultExamples.placeholder")}
                                disabled={isLoading}
                                onSend={(question, attachments, documents, evidenceOptions) =>
                                    makeApiRequest(question, undefined, attachments, documents, evidenceOptions)
                                }
                                conversationId={conversationIdRef.current}
                                agentId={selectedAgent?._id}
                                documentsAvailable={documentsAvailable}
                                getAccessToken={() => (client ? getToken(client) : Promise.resolve(undefined))}
                                showSpeechInput={showSpeechInput}
                                imagesAvailable={visionAvailable}
                                imageDisabledReason={visionDisabledReason}
                                showAttachmentButton={showAttachmentButton}
                                attachmentDisabledReason={attachmentDisabledReason}
                            />
                        </div>
                    )}
                </div>

                {answers.length > 0 && activeAnalysisPanelTab && (
                    <AnalysisPanel
                        // key={`${activeAnalysisPanelTab}:${activeWebUrl ?? ""}:${activeCitation ?? ""}`}
                        key={`${selectedAnswer}:${activeAnalysisPanelTab}:${activeWebUrl ?? ""}:${activeCitation ?? ""}`}
                        className={styles.chatAnalysisPanel}
                        activeCitation={activeCitation}
                        activeWebUrl={activeWebUrl}
                        onActiveTabChanged={x => onToggleTab(x, selectedAnswer)}
                        citationHeight="810px"
                        answer={answers[selectedAnswer][1]}
                        activeTab={activeAnalysisPanelTab}
                    />
                )}

                {((useLogin && showChatHistoryCosmos) || showChatHistoryBrowser) && (
                    <>
                        <div className={`${styles.sidebar} ${isHistoryCollapsed ? styles.sidebarCollapsed : styles.sidebarExpanded}`}>
                            {/* ปุ่ม toggle */}
                            <div className={styles.sidebarToggle}>
                                <IconButton
                                    iconProps={{ iconName: isHistoryCollapsed ? "ChevronRight" : "ChevronLeft" }}
                                    onClick={() => setIsHistoryCollapsed(!isHistoryCollapsed)}
                                    ariaLabel="Toggle Sidebar"
                                />
                            </div>

                            {/* เนื้อหา */}

                            {isHistoryCollapsed ? (
                                <>
                                    <div style={{ display: "flex", justifyContent: "center", marginTop: "10px" }}>
                                        <IconButton iconProps={{ iconName: "History" }} ariaLabel="History" className={styles.sidebarIconDisabled} />
                                    </div>
                                    {/* <div style={{ display: "flex", justifyContent: "center", marginTop: "10px" }}>
                                        <IconButton
                                            iconProps={{ iconName: "Settings" }}
                                            ariaLabel={t("labels.toggleMenu")}
                                            className={styles.sidebarIconDisabled}
                                        />
                                    </div> */}
                                </>
                            ) : (
                                <>
                                    {isUserLoading ? (
                                        <>
                                            <Skeleton variant="rectangular" width={200} height={36} sx={{ mb: 1 }} />
                                            <Skeleton variant="rectangular" width={200} height={36} sx={{ mb: 1 }} />
                                            <Skeleton variant="rectangular" width={200} height={36} />
                                        </>
                                    ) : (
                                        <>
                                            {/* ปุ่มด้านบน */}
                                            <div className={styles.historyButtons}>
                                                {loggedIn && (
                                                    <>
                                                        <div className={styles.sidebarMenuSection}>
                                                            <div className={styles.sidebarSectionLabel}>Workspace</div>
                                                            <Button
                                                                variant="text"
                                                                startIcon={<ChatIcon />}
                                                                onClick={startNewChat}
                                                                className={`${styles.newChatTextButton} ${styles.newChatPrimaryButton}`}
                                                            >
                                                                New Chat
                                                            </Button>
                                                            <Button
                                                                variant="text"
                                                                startIcon={<SearchIcon />}
                                                                className={styles.newChatTextButton}
                                                                onClick={() => setOpenSearch(true)}
                                                            >
                                                                Search History
                                                            </Button>
                                                            {userData && !userData?.is_sys_admin ? (
                                                                <Button
                                                                    variant="text"
                                                                    startIcon={<FeedIcon />}
                                                                    className={styles.newChatTextButton}
                                                                    onClick={() => setOpenFeedback(true)}
                                                                >
                                                                    Feedback
                                                                </Button>
                                                            ) : null}
                                                            <UploadFile className={styles.menuItem} disabled={!loggedIn} dialogRef={uploadDialogRef} />
                                                        </div>

                                                        {(canOpenAdminManagement || canManageUploads) && (
                                                            <div className={styles.sidebarMenuSection}>
                                                                <div className={styles.sidebarSectionLabel}>Management</div>
                                                                {canOpenAdminManagement && (
                                                                <Button
                                                                    variant="text"
                                                                    startIcon={<FeedIcon />}
                                                                    className={styles.newChatTextButton}
                                                                    onClick={() => setOpenTeamAdminManagement(true)}
                                                                >
                                                                    Admin Management
                                                                </Button>
                                                                )}

                                                                {canManageUploads && (
                                                                    <>
                                                                        <GlobalUpload
                                                                            className={styles.menuItem}
                                                                            disabled={!loggedIn}
                                                                            dialogRef={globalUploadDialogRef}
                                                                        />
                                                                        <ScrapData className={styles.menuItem} disabled={!loggedIn} dialogRef={scrapDataDialogRef} />
                                                                    </>
                                                                )}
                                                            </div>
                                                        )}

                                                        <div className={styles.sidebarMenuSection}>
                                                            <div className={styles.sidebarSectionLabel}>Insights</div>
                                                        <Dashboard
                                                            className={styles.menuItem}
                                                            disabled={!loggedIn}
                                                            dialogRef={dashboardDialogRef}
                                                            teamId={selectTeamData?._id}
                                                            teamName={selectTeamData?.name}
                                                            canViewSystem={Boolean(
                                                                userData?.is_sys_admin ||
                                                                sysPers?.some(permission => permission.toLowerCase() === "view system dashboard")
                                                            )}
                                                            canViewTeam={Boolean(
                                                                userData?.is_sys_admin ||
                                                                selectTeamData?.permissions?.some(permission => permission.toLowerCase() === "view team dashboard")
                                                            )}
                                                        />

                                                        {canViewFeedbackDashboard && (
                                                                <Button
                                                                    variant="text"
                                                                    startIcon={<FeedIcon />}
                                                                    className={styles.newChatTextButton}
                                                                    onClick={() => setOpenFeedbackDashboard(true)}
                                                                >
                                                                    Feedback Dashboard
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </>
                                                )}
                                            </div>

                                            {/* Scroll ได้เฉพาะ History */}
                                            <div className={styles.historyContent}>
                                                <div className={styles.historySectionLabel}>Recent chats</div>
                                                <HistoryList
                                                    key={historyOwnerId ?? "history-owner-unavailable"}
                                                    provider={historyProvider}
                                                    ownerId={historyOwnerId}
                                                    notify={!isStreaming && !isLoading}
                                                    onChatSelected={answers => {
                                                        if (answers.length === 0) return;
                                                        setAnswers(answers);
                                                        lastQuestionRef.current = answers[answers.length - 1][0];
                                                        const restoredSessionState = answers.at(-1)?.[1]?.session_state;
                                                        conversationIdRef.current =
                                                            typeof restoredSessionState === "string" &&
                                                            /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(restoredSessionState)
                                                                ? restoredSessionState
                                                                : crypto.randomUUID();
                                                    }}
                                                />
                                            </div>
                                        </>
                                    )}
                                </>
                            )}
                            <div className={styles.sidebarVersion}>Version &nbsp;{t("version")}</div>
                        </div>
                    </>
                )}

                <Panel
                    headerText={t("labels.headerText")}
                    isOpen={isConfigPanelOpen}
                    isBlocking={false}
                    onDismiss={() => setIsConfigPanelOpen(false)}
                    closeButtonAriaLabel={t("labels.closeButton")}
                    onRenderFooterContent={() => <DefaultButton onClick={() => setIsConfigPanelOpen(false)}>{t("labels.closeButton")}</DefaultButton>}
                    isFooterAtBottom={true}
                >
                    <Settings
                        promptTemplate={promptTemplate}
                        temperature={temperature}
                        retrieveCount={retrieveCount}
                        maxSubqueryCount={maxSubqueryCount}
                        resultsMergeStrategy={resultsMergeStrategy}
                        seed={seed}
                        minimumSearchScore={minimumSearchScore}
                        minimumRerankerScore={minimumRerankerScore}
                        useSemanticRanker={useSemanticRanker}
                        useSemanticCaptions={useSemanticCaptions}
                        useQueryRewriting={useQueryRewriting}
                        reasoningEffort={reasoningEffort}
                        excludeCategory={excludeCategory}
                        includeCategory={includeCategory}
                        retrievalMode={retrievalMode}
                        useGPT4V={useGPT4V}
                        gpt4vInput={gpt4vInput}
                        vectorFields={vectorFields}
                        showSemanticRankerOption={showSemanticRankerOption}
                        showQueryRewritingOption={showQueryRewritingOption}
                        showReasoningEffortOption={showReasoningEffortOption}
                        showGPT4VOptions={false}
                        showVectorOption={showVectorOption}
                        useOidSecurityFilter={useOidSecurityFilter}
                        useGroupsSecurityFilter={useGroupsSecurityFilter}
                        useLogin={!!useLogin}
                        loggedIn={loggedIn}
                        requireAccessControl={requireAccessControl}
                        shouldStream={shouldStream}
                        streamingEnabled={streamingEnabled}
                        useSuggestFollowupQuestions={useSuggestFollowupQuestions}
                        showSuggestFollowupQuestions={true}
                        showAgenticRetrievalOption={showAgenticRetrievalOption}
                        useAgenticRetrieval={useAgenticRetrieval}
                        onChange={handleSettingsChange}
                    />
                    {useLogin && <TokenClaimsDisplay />}
                </Panel>

                <Dialog
                    open={openSearch}
                    onClose={() => setOpenSearch(false)}
                    maxWidth="md" // ขยายให้กว้างขึ้นจาก sm -> md
                    fullWidth
                    scroll="paper"
                    PaperProps={{
                        sx: {
                            borderRadius: 2,
                            // ความสูงขั้นต่ำของ dialog ให้ไม่ย่อจนเล็กเกินไป
                            minHeight: 260
                            // (ถ้าต้องการ dialog สูงขึ้นอีก) ปรับค่า minHeight เป็น 360/420 ตามชอบ
                            // minHeight: 360,
                        }
                    }}
                >
                    <DialogTitle>Search History</DialogTitle>

                    <DialogContent
                        dividers
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 1.5,
                            px: 3,
                            pt: 2,
                            pb: 2
                        }}
                    >
                        <TextField
                            autoFocus
                            fullWidth
                            variant="outlined"
                            size="small"
                            placeholder="Type to search..."
                            value={keyword}
                            onChange={e => handleSearch(e.target.value)}
                        />

                        <Box
                            sx={{
                                mt: 1,
                                height: 320,
                                maxHeight: "60vh",
                                overflow: "auto",
                                borderRadius: 1,
                                px: 0
                            }}
                        >
                            {loading ? (
                                <Typography sx={{ mt: 1 }}>Searching...</Typography>
                            ) : results.length === 0 ? (
                                <Typography sx={{ py: 2 }} color="text.secondary">
                                    {keyword.trim() ? "No matching results." : "Type to begin searching."}
                                </Typography>
                            ) : (
                                <List>
                                    {results.map((item: any) => (
                                        <ListItem key={item.id} disablePadding>
                                            <ListItemButton onClick={() => loadHistoryItem(item)} sx={{ borderRadius: 1 }}>
                                                <ListItemText
                                                    primary={item.title || "(Untitled)"}
                                                    secondary={(item.answers?.[0]?.[0] || "").slice(0, 120)}
                                                    secondaryTypographyProps={{
                                                        sx: {
                                                            display: "-webkit-box",
                                                            WebkitLineClamp: 2,
                                                            WebkitBoxOrient: "vertical",
                                                            overflow: "hidden",
                                                            textOverflow: "ellipsis",
                                                            whiteSpace: "normal"
                                                        }
                                                    }}
                                                />
                                            </ListItemButton>
                                        </ListItem>
                                    ))}
                                </List>
                            )}
                        </Box>
                    </DialogContent>

                    <DialogActions sx={{ px: 3, pb: 2 }}>
                        <Button onClick={() => setOpenSearch(false)} variant="outlined">
                            Close
                        </Button>
                    </DialogActions>
                </Dialog>
                <FeedbackDialog
                    open={openFeedback}
                    onClose={() => setOpenFeedback(false)}
                // onSubmit={handleSubmitFeedback}
                />
                <FeedbackDashboardDialog
                    open={openFeedbackDashboard}
                    onClose={() => setOpenFeedbackDashboard(false)}
                // onSubmit={handleSubmitFeedback}
                />
                <TeamManagementTabsDialog
                    open={openTeamAdminManagement}
                    is_sys_admin={userData ? userData?.is_sys_admin! : false}
                    selectTeamData={selectTeamData}
                    sys_permissions={sysPers ? sysPers : []}
                    onAgentsChanged={() => void loadAgents()}
                    onTeamChanged={team => void activateCreatedTeam(team)}
                    onClose={() => setOpenTeamAdminManagement(false)}
                // onSubmit={handleSubmitFeedback}
                />
                <Menu
                    anchorEl={agentAnchorEl}
                    open={agentMenuOpen}
                    onClose={() => setAgentAnchorEl(null)}
                    anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
                    transformOrigin={{ vertical: "top", horizontal: "left" }}
                    PaperProps={{
                        sx: {
                            borderRadius: 2,
                            mt: 1,
                            overflow: "visible"
                        }
                    }}
                >
                    <Box sx={{ display: "flex", width: hasSelectedAgent ? 620 : 280 }}>
                        {/* ================= LEFT : AGENT ================= */}
                        <Box sx={{ width: 280, maxHeight: 360, overflowY: "auto" }}>
                            <MenuItem disabled>
                                <Typography variant="subtitle2">Select Agent</Typography>
                            </MenuItem>

                            <Divider />

                            {agents.map(agent => {
                                const selected = selectedAgent?._id === agent._id;

                                return (
                                    <MenuItem key={agent._id} selected={selected} onClick={() => handleSelectAgent(agent)} sx={{ alignItems: "flex-start" }}>
                                        <ListItemIcon sx={{ minWidth: 28 }}>{selected && <CheckIcon fontSize="small" />}</ListItemIcon>

                                        <ListItemText
                                            primary={
                                                <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.75, minWidth: 0 }}>
                                                    <Typography component="span" variant="body2" fontWeight={selected ? 600 : 400} noWrap sx={{ minWidth: 0 }}>
                                                        {agent.agent_name}
                                                    </Typography>
                                                    <Typography component="span" variant="caption" color="text.secondary" noWrap sx={{ fontSize: "0.68rem", maxWidth: 120, flexShrink: 1 }}>
                                                        · {getAgentModelName(agent)}
                                                    </Typography>
                                                </Box>
                                            }
                                            secondary={`Temp ${agent.config.temperature} · Max ${agent.config.max_tokens}`}
                                        />
                                    </MenuItem>
                                );
                            })}

                            {!hasSelectedAgent && (
                                <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1 }}>
                                    Select an agent to configure data source
                                </Typography>
                            )}
                        </Box>

                        {/* ================= RIGHT : DATA ================= */}
                        {hasSelectedAgent && (
                            <>
                                <Divider orientation="vertical" flexItem />

                                <Box
                                    sx={{
                                        width: 340,
                                        display: "flex",
                                        flexDirection: "column",
                                        height: 360 // ให้เท่ากับฝั่งซ้าย
                                    }}
                                >
                                    {/* ====== Content scroll area ====== */}
                                    <Box sx={{ flex: 1, overflowY: "auto" }}>
                                        {/* ---------- Data Scope ---------- */}
                                        <MenuItem disabled>
                                            <Typography variant="subtitle2">Data Scope</Typography>
                                        </MenuItem>

                                        {DATA_SCOPES.map(({ key, label }) => {
                                            const checked = draftScopes.includes(key);

                                            return (
                                                <MenuItem
                                                    key={key}
                                                    onClick={e => {
                                                        e.stopPropagation();
                                                        setDraftScopes(prev => (checked ? prev.filter(s => s !== key) : [...prev, key]));
                                                    }}
                                                >
                                                    <ListItemIcon>
                                                        <Checkbox checked={checked} />
                                                    </ListItemIcon>
                                                    <ListItemText primary={label} />
                                                </MenuItem>
                                            );
                                        })}

                                        <Divider sx={{ my: 1 }} />

                                        {/* ---------- Data Groups ---------- */}
                                        <MenuItem disabled>
                                            <Typography variant="subtitle2">Data Groups</Typography>
                                        </MenuItem>

                                        {effectiveAccessError && (
                                            <Box px={2} pb={1}>
                                                <Typography variant="caption" color="error">
                                                    {effectiveAccessError}
                                                </Typography>
                                            </Box>
                                        )}

                                        <Box px={1} pb={1}>
                                            <TextField
                                                size="small"
                                                fullWidth
                                                placeholder="Search data group..."
                                                value={groupKeyword}
                                                onChange={e => setGroupKeyword(e.target.value)}
                                            />
                                        </Box>

                                        <Box sx={{ maxHeight: 220, overflowY: "auto" }}>
                                            {dataGroups
                                                .filter(g => g.name.toLowerCase().includes(groupKeyword.toLowerCase()))
                                                .map(group => {
                                                    const checked = draftDataGroupIds.includes(group._id);

                                                    return (
                                                        <MenuItem
                                                            key={group._id}
                                                            onClick={e => {
                                                                e.stopPropagation();
                                                                setDraftDataGroupIds(prev =>
                                                                    checked ? prev.filter(id => id !== group._id) : [...prev, group._id]
                                                                );
                                                            }}
                                                        >
                                                            <ListItemIcon>
                                                                <Checkbox checked={checked} />
                                                            </ListItemIcon>
                                                            <ListItemText
                                                                primary={group.name}
                                                                secondary={group.access_mode === "team" ? "Available to entire team" : "Assigned to selected users"}
                                                            />
                                                        </MenuItem>
                                                    );
                                                })}
                                        </Box>
                                    </Box>

                                    {/* ====== Footer ====== */}
                                    <Divider />

                                    <Box
                                        sx={{
                                            px: 1.5,
                                            py: 1,
                                            display: "flex",
                                            justifyContent: "flex-end",
                                            gap: 1,
                                            bgcolor: "background.paper"
                                        }}
                                    >
                                        <Button
                                            variant="text"
                                            onClick={async e => {
                                                // e.stopPropagation();
                                                setDraftScopes(selectedScopes);
                                                setDraftDataGroupIds(selectedDataGroupIds);
                                                setAgentAnchorEl(null);
                                            }}
                                            sx={{ textTransform: "none" }}
                                        >
                                            Cancel
                                        </Button>

                                        <Button
                                            variant="contained"
                                            onClick={async e => {
                                                e.stopPropagation();

                                                if (!selectedAgent?._id) return;
                                                if (draftScopes.length === 0 && draftDataGroupIds.length === 0) {
                                                    showNotification("Please select at least one data group or scope.", "warning");
                                                    return;
                                                }

                                                setSelectedScopes(draftScopes);
                                                setSelectedDataGroupIds(draftDataGroupIds);

                                                const agentId = selectedAgent?._id;
                                                if (!agentId) return;

                                                await setAgentUIPrefs(agentId, {
                                                    selectedScopes: draftScopes,
                                                    selectedDataGroupIds: draftDataGroupIds
                                                });

                                                setAgentAnchorEl(null); // ✅ ปิดเมนูหลัง Apply (สวย)
                                            }}
                                            sx={{
                                                textTransform: "none",
                                                borderRadius: 2,
                                                px: 2.5
                                            }}
                                        >
                                            Apply
                                        </Button>
                                    </Box>
                                </Box>
                            </>
                        )}
                    </Box>
                </Menu>
            </div>
        </div>
    );
};

export default Chat;
