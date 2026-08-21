import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Helmet } from "react-helmet-async";
import { Panel, DefaultButton, Spinner } from "@fluentui/react";

import styles from "./Ask.module.css";

import {
    askApi,
    configApi,
    ChatAppResponse,
    ChatAppRequest,
    ChatAttachmentInput,
    RetrievalMode,
    VectorFields,
    GPT4VInput,
    SpeechConfig,
    Agent,
    DataGroup,
    TeamProfile,
    get_agent_by_team,
    get_data_group_by_team,
    AuthProfile,
    User,
    getFixedPromptsApi
} from "../../api";
import { Answer, AnswerError } from "../../components/Answer";
import { QuestionInput } from "../../components/QuestionInput";
import { ExampleList } from "../../components/Example";
import { AnalysisPanel, AnalysisPanelTabs } from "../../components/AnalysisPanel";
import { SettingsButton } from "../../components/SettingsButton/SettingsButton";
import { useLogin, getToken, requireAccessControl, getUsername } from "../../authConfig";
import { UploadFile } from "../../components/UploadFile";
import { Settings } from "../../components/Settings/Settings";
import { useMsal } from "@azure/msal-react";
import { LLMProfile } from "../../api/models";
import { TokenClaimsDisplay } from "../../components/TokenClaimsDisplay";
import { LoginContext } from "../../loginContext";
import { LanguagePicker } from "../../i18n/LanguagePicker";
import { IconButton } from "@fluentui/react";
import { Box, Button, Checkbox, Divider, ListItemIcon, ListItemText, Menu, MenuItem, Skeleton, TextField, Typography } from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import { Storage } from "../../utill/storage";
import { STORAGE_KEYS } from "../../utill/storageKeys";
import { useNotification } from "../../utill/NotificationProvider";
import { AuthStorage } from "../../utill/authStorage";

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

export function Component(): JSX.Element {
    const [isConfigPanelOpen, setIsConfigPanelOpen] = useState(false);
    const [promptTemplate, setPromptTemplate] = useState<string>("");
    const [promptTemplatePrefix, setPromptTemplatePrefix] = useState<string>("");
    const [promptTemplateSuffix, setPromptTemplateSuffix] = useState<string>("");
    const [temperature, setTemperature] = useState<number>(0.3);
    const [seed, setSeed] = useState<number | null>(null);
    const [minimumRerankerScore, setMinimumRerankerScore] = useState<number>(0);
    const [minimumSearchScore, setMinimumSearchScore] = useState<number>(0);
    const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>(RetrievalMode.Hybrid);
    const [retrieveCount, setRetrieveCount] = useState<number>(3);
    const [maxSubqueryCount, setMaxSubqueryCount] = useState<number>(10);
    const [resultsMergeStrategy, setResultsMergeStrategy] = useState<string>("interleaved");
    const [useSemanticRanker, setUseSemanticRanker] = useState<boolean>(true);
    const [useSemanticCaptions, setUseSemanticCaptions] = useState<boolean>(false);
    const [useQueryRewriting, setUseQueryRewriting] = useState<boolean>(false);
    const [reasoningEffort, setReasoningEffort] = useState<string>("");
    const [useGPT4V, setUseGPT4V] = useState<boolean>(false);
    const [gpt4vInput, setGPT4VInput] = useState<GPT4VInput>(GPT4VInput.TextAndImages);
    const [includeCategory, setIncludeCategory] = useState<string>("");
    const [excludeCategory, setExcludeCategory] = useState<string>("");
    const [question, setQuestion] = useState<string>("");
    const [vectorFields, setVectorFields] = useState<VectorFields>(VectorFields.TextAndImageEmbeddings);
    const [useOidSecurityFilter, setUseOidSecurityFilter] = useState<boolean>(false);
    const [useGroupsSecurityFilter, setUseGroupsSecurityFilter] = useState<boolean>(false);
    const [showGPT4VOptions, setShowGPT4VOptions] = useState<boolean>(false);
    const [agentRuntimeMode, setAgentRuntimeMode] = useState<"legacy" | "langgraph" | "per_agent">("per_agent");
    const [llmProfiles, setLlmProfiles] = useState<LLMProfile[]>([]);
    const [showSemanticRankerOption, setShowSemanticRankerOption] = useState<boolean>(false);
    const [showQueryRewritingOption, setShowQueryRewritingOption] = useState<boolean>(false);
    const [showReasoningEffortOption, setShowReasoningEffortOption] = useState<boolean>(false);
    const [showVectorOption, setShowVectorOption] = useState<boolean>(false);
    const [showUserUpload, setShowUserUpload] = useState<boolean>(false);
    const [showLanguagePicker, setshowLanguagePicker] = useState<boolean>(false);
    const [showSpeechInput, setShowSpeechInput] = useState<boolean>(false);
    const [showSpeechOutputBrowser, setShowSpeechOutputBrowser] = useState<boolean>(false);
    const [showSpeechOutputAzure, setShowSpeechOutputAzure] = useState<boolean>(false);
    const audio = useRef(new Audio()).current;
    const [isPlaying, setIsPlaying] = useState(false);
    const [showAgenticRetrievalOption, setShowAgenticRetrievalOption] = useState<boolean>(false);
    const [useAgenticRetrieval, setUseAgenticRetrieval] = useState<boolean>(false);
    const { instance } = useMsal();

    const lastQuestionRef = useRef<string>("");

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<unknown>();
    const [answer, setAnswer] = useState<ChatAppResponse>();
    // For the Ask tab, this array will hold a maximum of one URL
    const [speechUrls, setSpeechUrls] = useState<(string | null)[]>([]);

    const speechConfig: SpeechConfig = {
        speechUrls,
        setSpeechUrls,
        audio,
        isPlaying,
        setIsPlaying
    };

    const [activeCitation, setActiveCitation] = useState<string>();
    const [activeAnalysisPanelTab, setActiveAnalysisPanelTab] = useState<AnalysisPanelTabs | undefined>(undefined);

    const client = useLogin ? useMsal().instance : undefined;
    const { loggedIn, userDetails, isUserLoading, isSwitchTeam, setIsSwitchTeam } = useContext(LoginContext);
    const role = userDetails?.role_name ?? "";
    const email = userDetails?.name ?? "";

    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const uploadDialogRef = useRef<HTMLDivElement>(null);
    const [activeWebUrl, setActiveWebUrl] = useState<string | undefined>(undefined);
    const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
    const [isAgentsLoading, setIsAgentsLoading] = useState(false);
    const [isGroupsLoading, setIsGroupsLoading] = useState(false);
    const isPageLoading = isUserLoading || isAgentsLoading || isGroupsLoading;
    const [agentAnchorEl, setAgentAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const agentMenuOpen = Boolean(agentAnchorEl);
    const hasSelectedAgent = Boolean(selectedAgent);
    const agentSelectorLeft = isHistoryCollapsed ? 88 : 276;
    const [agents, setAgents] = useState<Agent[]>([]);
    const [selectedScopes, setSelectedScopes] = useState<DataScope[]>(["global"]);
    const [draftScopes, setDraftScopes] = useState<DataScope[]>(["global"]);
    const [draftDataGroupIds, setDraftDataGroupIds] = useState<string[]>([]);
    const [selectedDataGroupIds, setSelectedDataGroupIds] = useState<string[]>([]);
    const defaultAgentId = agents[0]?._id;
    const isDefaultAgent = (agent: Agent | null) => agent?._id === defaultAgentId;
    const [isInitialAgentSetup, setIsInitialAgentSetup] = useState(true);
    const [groupKeyword, setGroupKeyword] = useState("");
    const [dataGroups, setDataGroups] = useState<DataGroup[]>([]);
    const { showNotification } = useNotification();
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);
    const [userData, setUserData] = useState<User | null>(null);
    const [sysPers, setSysPers] = useState<string[] | null>(null);
    const [fixedPrompts, setFixedPrompts] = useState<any>(null);
    const usesLangGraph =
        agentRuntimeMode === "langgraph" || (agentRuntimeMode === "per_agent" && selectedAgent?.config?.runtime === "langgraph");
    const selectedLlmProfileId = selectedAgent?.config?.llm_profile_id || "system";
    const selectedLlmProfile = llmProfiles.find(profile => profile.id === selectedLlmProfileId);
    const modelSupportsVision = selectedLlmProfile?.supportsVision ?? (selectedLlmProfileId === "system" && showGPT4VOptions);
    const visionAvailable = modelSupportsVision && !usesLangGraph;
    const selectedLlmProfileLabel = selectedLlmProfile?.label ?? (selectedLlmProfileId === "system" ? "System default" : selectedLlmProfileId);
    const visionDisabledReason = !selectedLlmProfile && selectedLlmProfileId !== "system"
        ? `Agent ${selectedAgent?.agent_name ?? "selected"} references unavailable LLM profile ${selectedLlmProfileId}. Re-select its model in Agent Management.`
        : !modelSupportsVision
        ? `${selectedAgent?.agent_name ?? "The selected agent"} uses ${selectedLlmProfileLabel}, which is not marked as vision-capable. Select the tested Vision model in Agent Management.`
        : usesLangGraph
          ? "Vision attachments are not supported by the LangGraph runtime yet."
          : undefined;

    useEffect(() => {
        if (!visionAvailable) setUseGPT4V(false);
    }, [visionAvailable]);

    const getConfig = async () => {
        configApi().then(config => {
            setShowGPT4VOptions(config.showGPT4VOptions);
            setAgentRuntimeMode(config.agentRuntimeMode ?? "per_agent");
            setLlmProfiles(config.llmProfiles ?? []);
            setUseSemanticRanker(config.showSemanticRankerOption);
            setShowSemanticRankerOption(config.showSemanticRankerOption);
            setUseQueryRewriting(config.showQueryRewritingOption);
            setShowQueryRewritingOption(config.showQueryRewritingOption);
            setShowReasoningEffortOption(config.showReasoningEffortOption);
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
            setShowAgenticRetrievalOption(config.showAgenticRetrievalOption);
            setUseAgenticRetrieval(config.showAgenticRetrievalOption);
            if (config.showAgenticRetrievalOption) {
                setRetrieveCount(10);
            }
        });
    };

    useEffect(() => {
        getConfig();
        const refreshCapabilities = () => {
            void configApi().then(config => {
                setLlmProfiles(config.llmProfiles ?? []);
                setShowGPT4VOptions(config.showGPT4VOptions);
                setAgentRuntimeMode(config.agentRuntimeMode ?? "per_agent");
            });
        };
        window.addEventListener("nexora:llm-profiles-changed", refreshCapabilities);
        return () => window.removeEventListener("nexora:llm-profiles-changed", refreshCapabilities);
    }, []);

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
            const groups = prefs?.selectedDataGroupIds ?? [];

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

    const makeApiRequest = async (question: string, attachments: ChatAttachmentInput[] = []) => {
        lastQuestionRef.current = question;

        error && setError(undefined);
        setIsLoading(true);
        setActiveCitation(undefined);
        setActiveAnalysisPanelTab(undefined);

        const savedPrompts = JSON.parse(localStorage.getItem("activePrompts") || "{}");
        const prompt = savedPrompts[email] || "";

        const token = client ? await getToken(client) : undefined;

        // 1) ดึง username แบบ async
        const name = (await getUsername(instance)) ?? "";

        // 2) อ่าน activeAgentConfigs จาก localStorage แบบ sync (ไม่ใช้ hook)
        const activeConfigForUser = getActiveAgentConfigs(name);

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
            const request: ChatAppRequest = {
                messages: [
                    {
                        content: question,
                        role: "user"
                    }
                ],
                ...(attachments.length ? { attachments } : {}),
                context: {
                    overrides: {
                        prompt_template: promptString.length === 0 ? undefined : promptString,
                        prompt_template_prefix: promptTemplatePrefix.length === 0 ? undefined : promptTemplatePrefix,
                        prompt_template_suffix: promptTemplateSuffix.length === 0 ? undefined : promptTemplateSuffix,
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
                        use_oid_security_filter: useOidSecurityFilter,
                        use_groups_security_filter: useGroupsSecurityFilter,
                        vector_fields: vectorFields,
                        use_gpt4v: useGPT4V,
                        gpt4v_input: gpt4vInput,
                        language: i18n.language,
                        use_agentic_retrieval: useAgenticRetrieval,
                        max_tokens: activeAgent?.config?.max_tokens,
                        ...(seed !== null ? { seed: activeAgent ? (activeAgent?.config == null ? seed : activeAgent?.config?.seed) : seed } : {})
                    }
                },
                // AI Chat Protocol: Client must pass on any session state received from the server
                session_state: answer ? answer.session_state : null
            };

            request["team_id"] = selectTeamData ? selectTeamData?._id : null;
            request["agent_name"] = activeAgent ? activeAgent?.agent_name : null; // ✨ เพิ่มตรงนี้
            request["agent_id"] = activeAgent ? activeAgent?._id : undefined;
            request["data_groups_id"] = uiPrefsPayload ? uiPrefsPayload.selectedDataGroupIds : null;
            request["selected_scopes"] = uiPrefsPayload ? uiPrefsPayload.selectedScopes : null;
            const result = await askApi(request, token);
            setAnswer(result);
            setSpeechUrls([null]);
        } catch (e) {
            setError(e);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSettingsChange = (field: string, value: any) => {
        switch (field) {
            case "promptTemplate":
                setPromptTemplate(value);
                break;
            case "promptTemplatePrefix":
                setPromptTemplatePrefix(value);
                break;
            case "promptTemplateSuffix":
                setPromptTemplateSuffix(value);
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
            case "useSemanticCaptions":
                setUseSemanticCaptions(value);
                break;
            case "useQueryRewriting":
                setUseQueryRewriting(value);
                break;
            case "reasoningEffort":
                setReasoningEffort(value);
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
        setQuestion(example);
    };

    const onShowCitation = (citation: string) => {
        let citationSplit = citation.replace("/content/", "");
        const isExternal = /^https?:\/\//i.test(citationSplit);

        if (isExternal) {
            setActiveCitation(undefined);
            setActiveWebUrl(citationSplit);
            setActiveAnalysisPanelTab(AnalysisPanelTabs.WebTab);
        } else {
            setActiveWebUrl(undefined);
            if (activeCitation === citation && activeAnalysisPanelTab === AnalysisPanelTabs.CitationTab) {
                setActiveAnalysisPanelTab(undefined);
            } else {
                setActiveCitation(citation);
                setActiveAnalysisPanelTab(AnalysisPanelTabs.CitationTab);
            }
        }
    };

    const onToggleTab = (tab: AnalysisPanelTabs) => {
        if (activeAnalysisPanelTab === tab) {
            setActiveAnalysisPanelTab(undefined);
        } else {
            setActiveAnalysisPanelTab(tab);
        }
    };

    const onUseOidSecurityFilterChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseOidSecurityFilter(!!checked);
    };

    const onUseGroupsSecurityFilterChange = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        setUseGroupsSecurityFilter(!!checked);
    };

    const { t, i18n } = useTranslation();

    const toggleMenu = () => {
        setMenuOpen(!menuOpen);
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

    const setAgentUIPrefs = async (agentId: string, prefs: AgentUIPrefs) => {
        const username = (await getUsername(instance)) ?? "";
        const teamId = await getTeamId();

        if (!username || !teamId || !agentId) return;

        writeAgentUIPrefs(username, teamId, agentId, prefs);
    };

    const getTeamId = async (): Promise<string> => {
        const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
        const username = (await getUsername(instance)) ?? "";
        if (!activeTeams || !username) return "";

        return activeTeams?.[username]?._id ?? "";
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

    // Detect outside click
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as HTMLElement;

            const isInsideMenu = menuRef.current?.contains(target);
            const isInsideMUIDialog = !!target.closest(".MuiDialog-container");

            if (!isInsideMenu && !isInsideMUIDialog) {
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

    const hasRole = (roles: string | string[] | undefined, check: string[]) => {
        if (!roles) return false;
        if (Array.isArray(roles)) {
            return roles.some(r => check.includes(r));
        }
        return check.includes(roles);
    };

    const restoreActiveTeam = async () => {
        const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
        if (!activeTeams) {
            return;
        }

        const name = (await getUsername(instance)) ?? "";

        const selectTeam = activeTeams[name];
        setSelectTeamData(selectTeam);
    };

    const loadFixedPrompts = async () => {
        const token = client ? await getToken(client) : undefined;
        const response = await getFixedPromptsApi(token);
        if (response) {
            setFixedPrompts(response.fixed_prompt);
        }
    };

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
            if (!activeTeams) return;

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

            const authProfile = Storage.get(STORAGE_KEYS.AUTH_PROFILE) as AuthProfile;
            const user_id = authProfile?.user?._id ?? null;

            const list = await get_data_group_by_team(teamId, token);
            const filtered = (list ?? []).filter((group: any) => {
                if (!group.user_id || group.user_id.length === 0) return true;
                return group.user_id.some((u: any) => u?._id === user_id);
            });

            setDataGroups(filtered);
        } catch (err) {
            console.error("load data groups failed:", err);
            setDataGroups([]);
        } finally {
            setIsGroupsLoading(false);
        }
    }, [loggedIn, instance]);

    const reloadAll = useCallback(async () => {
        await loadAgents();
        await loadDataGroups();
    }, [loadAgents, loadDataGroups]);

    useEffect(() => {
        if (!loggedIn) return;

        const run = async () => {
            await reloadAll();

            // ✅ reset flag กันยิงซ้ำ
            if (isSwitchTeam) {
                setIsSwitchTeam(false);
            }
        };

        run();
    }, [loggedIn, isSwitchTeam, reloadAll, setIsSwitchTeam]);

    useEffect(() => {
        if (!loggedIn || isUserLoading) return;

        const user = AuthStorage.get()?.user ?? null;
        const sys_permissions = AuthStorage.get()?.sys_permissions ?? null;
        setUserData(user);
        setSysPers(sys_permissions);

        loadFixedPrompts();
    }, [loggedIn, isUserLoading]);

    useEffect(() => {
        const loadDataGroups = async () => {
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

                const authProfile = Storage.get(STORAGE_KEYS.AUTH_PROFILE) as AuthProfile;
                const user_id = authProfile ? (authProfile?.user ? authProfile?.user._id : null) : null;

                const list = await get_data_group_by_team(teamId, token);
                const filtered = (list ?? []).filter((group: any) => {
                    if (!group.user_id || group.user_id.length === 0) return true;
                    return group.user_id.some((u: any) => u?._id === user_id);
                });

                setDataGroups(filtered);
                // setDataGroups(list ?? []);
            } catch (err) {
                console.error("load data groups failed:", err);
                setDataGroups([]);
            } finally {
                setIsGroupsLoading(false);
            }
        };

        loadDataGroups();
    }, [loggedIn, instance]);

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
        if (!loggedIn || isUserLoading) return;
        restoreActiveTeam();
    }, [loggedIn, isUserLoading]);

    return (
        <div className={styles.askContainer}>
            {/* Setting the page title using react-helmet-async */}
            <Helmet>
                <title>{t("pageTitle")}</title>
            </Helmet>
            <div className={styles.askTopSection}>
                <div className={styles.commandsContainer}>
                    <div className={styles.loginMenuContainer} style={{ position: "relative" }}>
                        <Box
                            sx={{
                                position: "absolute",
                                // top: 88,
                                // left: agentSelectorLeft,
                                zIndex: 10,
                                transition: "left 0.2s ease"
                            }}
                        >
                            {isPageLoading ? (
                                <Skeleton variant="rectangular" width={180} height={36} sx={{ borderRadius: 2 }} />
                            ) : (
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={e => setAgentAnchorEl(e.currentTarget)}
                                    sx={{
                                        textTransform: "none",
                                        borderRadius: 2,
                                        px: 1.5,

                                        // 🔥 ทำให้อยู่บรรทัดเดียวเสมอ
                                        whiteSpace: "nowrap",
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 1,

                                        // กัน layout เพี้ยนจาก emoji + rem
                                        lineHeight: 1,
                                        minHeight: 36
                                    }}
                                >
                                    🤖 {selectedAgent?.agent_name ?? "Select Agent"}
                                </Button>
                            )}
                        </Box>
                    </div>
                </div>
                <div className={styles.chatEmptyState}>
                    {/* <img src={appLogo} alt="App logo" width="120" height="120" /> */}
                    <div className={styles.sparkleLogo}>
                        ✦<span className={styles.orb1}></span>
                        <span className={styles.orb2}></span>
                        <span className={styles.orb3}></span>
                    </div>

                    <h1 className={styles.askTitle}>{t("askTitle")}</h1>
                </div>
                <div className={styles.askQuestionInput}>
                    <QuestionInput
                        placeholder={t("gpt4vExamples.placeholder")}
                        disabled={isLoading}
                        initQuestion={question}
                        onSend={(question, attachments) => makeApiRequest(question, attachments)}
                        showSpeechInput={showSpeechInput}
                        visionAvailable={visionAvailable}
                        visionEnabled={useGPT4V}
                        visionDisabledReason={visionDisabledReason}
                        onVisionChange={enabled => {
                            setUseGPT4V(enabled);
                            if (enabled) setUseAgenticRetrieval(false);
                        }}
                    />
                </div>
            </div>
            <div className={styles.askBottomSection}>
                {isLoading && <Spinner label={t("generatingAnswer")} />}
                {!lastQuestionRef.current && (
                    <div className={styles.askTopSection}>
                        {showLanguagePicker && <LanguagePicker onLanguageChange={newLang => i18n.changeLanguage(newLang)} />}
                        {/* <ExampleList onExampleClicked={onExampleClicked} useGPT4V={useGPT4V} /> */}
                    </div>
                )}
                {!isLoading && answer && !error && (
                    <div className={styles.askAnswerContainer}>
                        <Answer
                            answer={answer}
                            index={0}
                            speechConfig={speechConfig}
                            isStreaming={false}
                            onCitationClicked={x => onShowCitation(x)}
                            onThoughtProcessClicked={() => onToggleTab(AnalysisPanelTabs.ThoughtProcessTab)}
                            onSupportingContentClicked={() => onToggleTab(AnalysisPanelTabs.SupportingContentTab)}
                            showSpeechOutputAzure={showSpeechOutputAzure}
                            showSpeechOutputBrowser={showSpeechOutputBrowser}
                        />
                    </div>
                )}
                {error ? (
                    <div className={styles.askAnswerContainer}>
                        <AnswerError error={error.toString()} onRetry={() => makeApiRequest(lastQuestionRef.current)} />
                    </div>
                ) : null}
                {activeAnalysisPanelTab && answer && (
                    <AnalysisPanel
                        key={`${activeAnalysisPanelTab}:${activeWebUrl ?? ""}:${activeCitation ?? ""}`}
                        className={styles.askAnalysisPanel}
                        activeCitation={activeCitation}
                        activeWebUrl={activeWebUrl}
                        onActiveTabChanged={x => onToggleTab(x)}
                        citationHeight="600px"
                        answer={answer}
                        activeTab={activeAnalysisPanelTab}
                    />
                )}
            </div>

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
                    promptTemplatePrefix={promptTemplatePrefix}
                    promptTemplateSuffix={promptTemplateSuffix}
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
                    showGPT4VOptions={showGPT4VOptions}
                    showVectorOption={showVectorOption}
                    useOidSecurityFilter={useOidSecurityFilter}
                    useGroupsSecurityFilter={useGroupsSecurityFilter}
                    useLogin={!!useLogin}
                    loggedIn={loggedIn}
                    requireAccessControl={requireAccessControl}
                    showAgenticRetrievalOption={showAgenticRetrievalOption}
                    useAgenticRetrieval={useAgenticRetrieval}
                    onChange={handleSettingsChange}
                />
                {useLogin && <TokenClaimsDisplay />}
            </Panel>

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
                                        primary={agent.agent_name}
                                        secondary={`Temp ${agent.config.temperature} · Max ${agent.config.max_tokens}`}
                                        primaryTypographyProps={{
                                            fontWeight: selected ? 600 : 400
                                        }}
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
                                                        <ListItemText primary={group.name} />
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
    );
}

Component.displayName = "Ask";
