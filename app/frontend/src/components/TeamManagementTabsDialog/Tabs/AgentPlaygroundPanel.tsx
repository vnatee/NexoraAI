import React, { useEffect, useMemo, useRef, useState } from "react";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Divider,
    FormControl,
    IconButton,
    InputLabel,
    ListItemText,
    MenuItem,
    Paper,
    Select,
    Stack,
    Tab,
    Tabs,
    TextField,
    Tooltip,
    Typography
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import RefreshIcon from "@mui/icons-material/Refresh";
import SendIcon from "@mui/icons-material/Send";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useMsal } from "@azure/msal-react";
import {
    Agent,
    AgentPlaygroundResponse,
    EffectiveAccessResponse,
    getEffectiveAccess,
    runAgentPlaygroundApi
} from "../../../api";
import { getToken } from "../../../authConfig";

type PlaygroundMessage = {
    role: "user" | "assistant";
    content: string;
};

type Props = {
    agent: Agent | null;
    teamId?: string;
    disabled?: boolean;
    onPrepareRun: () => Promise<Agent>;
};

const SCOPE_OPTIONS = [
    { id: "global", label: "Company" },
    { id: "personal", label: "Personal" }
];

export function AgentPlaygroundPanel({ agent, teamId, disabled = false, onPrepareRun }: Props) {
    const { instance } = useMsal();
    const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
    const [input, setInput] = useState("");
    const [running, setRunning] = useState(false);
    const [status, setStatus] = useState("Private draft · not tested yet");
    const [error, setError] = useState("");
    const [lastResult, setLastResult] = useState<AgentPlaygroundResponse | null>(null);
    const [activeView, setActiveView] = useState<"chat" | "trace">("chat");
    const [access, setAccess] = useState<EffectiveAccessResponse | null>(null);
    const [selectedScopes, setSelectedScopes] = useState<string[]>(["global"]);
    const [selectedDataGroupIds, setSelectedDataGroupIds] = useState<string[]>([]);
    const conversationEndRef = useRef<HTMLDivElement | null>(null);

    const isDraft = agent?.lifecycle_status === "draft";
    const canRun = Boolean(teamId && isDraft && !disabled && !running && input.trim());

    useEffect(() => {
        setMessages([]);
        setLastResult(null);
        setActiveView("chat");
        setError("");
        setStatus(isDraft ? "Private draft · not tested yet" : "Playground requires a private draft");
    }, [agent?._id, isDraft]);

    useEffect(() => {
        if (!teamId || !agent?._id || !isDraft) {
            setAccess(null);
            return;
        }
        let cancelled = false;
        getToken(instance)
            .then(token => token ? getEffectiveAccess(teamId, token, agent._id) : null)
            .then(result => {
                if (!cancelled && result) setAccess(result);
            })
            .catch(reason => {
                if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load Playground data access");
            });
        return () => {
            cancelled = true;
        };
    }, [agent?._id, instance, isDraft, teamId]);

    useEffect(() => {
        conversationEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, [messages, running]);

    const selectedGroupNames = useMemo(() => {
        const names = new Map((access?.data_groups ?? []).map(group => [group._id, group.name]));
        return selectedDataGroupIds.map(id => names.get(id) ?? id);
    }, [access, selectedDataGroupIds]);

    const restart = () => {
        setMessages([]);
        setLastResult(null);
        setActiveView("chat");
        setError("");
        setStatus("Private draft · conversation cleared");
    };

    const run = async () => {
        if (!canRun || !teamId) return;
        const question = input.trim();
        setInput("");
        setError("");
        setRunning(true);
        setStatus("Saving draft before test…");
        const pendingMessages: PlaygroundMessage[] = [...messages, { role: "user", content: question }];
        setMessages(pendingMessages);
        try {
            const savedAgent = await onPrepareRun();
            if (savedAgent.lifecycle_status !== "draft") {
                throw new Error("Playground requires a private Agent draft");
            }
            setStatus("Draft saved · running safe test…");
            const token = await getToken(instance);
            if (!token) throw new Error("Authentication is required");
            const result = await runAgentPlaygroundApi(
                teamId,
                savedAgent._id,
                pendingMessages,
                selectedScopes,
                selectedDataGroupIds,
                token
            );
            setMessages(previous => [...previous, { role: "assistant", content: result.answer }]);
            setLastResult(result);
            if ((result.diagnostics.steps ?? []).some(step => step.status === "error" || step.status === "blocked")) {
                setActiveView("trace");
            }
            setStatus(`Draft saved · tested with ${result.diagnostics.runtime}`);
        } catch (reason) {
            const diagnostics = reason instanceof Error
                ? (reason as Error & { diagnostics?: AgentPlaygroundResponse["diagnostics"] }).diagnostics
                : undefined;
            if (diagnostics) {
                setLastResult({ answer: "", citations: [], diagnostics });
                setActiveView("trace");
            }
            setError(reason instanceof Error ? reason.message : "Playground run failed");
            setStatus("Draft test failed");
        } finally {
            setRunning(false);
        }
    };

    return (
        <Paper
            variant="outlined"
            sx={{
                display: "flex",
                flexDirection: "column",
                minHeight: { xs: 560, md: "calc(100vh - 210px)" },
                maxHeight: { md: "calc(100vh - 170px)" },
                overflow: "hidden",
                bgcolor: "background.default"
            }}
        >
            <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2} px={2} py={1.5} bgcolor="background.paper">
                <Box minWidth={0}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <ScienceOutlinedIcon color="primary" fontSize="small" />
                        <Typography fontWeight={700}>Playground</Typography>
                        <Chip label="Safe test" color="success" variant="outlined" size="small" />
                    </Stack>
                    <Typography variant="caption" color="text.secondary" noWrap>{status}</Typography>
                </Box>
                <Tooltip title="Clear only this test conversation">
                    <span>
                        <Button size="small" startIcon={<RefreshIcon />} disabled={running || messages.length === 0} onClick={restart}>
                            Restart
                        </Button>
                    </span>
                </Tooltip>
            </Stack>
            <Divider />

            {!agent && <Alert severity="info" sx={{ m: 2 }}>Enter an Agent name, then open Playground to create its private draft.</Alert>}
            {agent && !isDraft && <Alert severity="info" sx={{ m: 2 }}>Phase 1 Playground tests private drafts only. Active Agent revision testing will be added separately so live configuration is never overwritten.</Alert>}
            {isDraft && (
                <>
                    <Accordion disableGutters elevation={0} square>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Box>
                                <Typography variant="subtitle2">Test data access</Typography>
                                <Typography variant="caption" color="text.secondary">
                                    {selectedScopes.length + selectedDataGroupIds.length} scope(s) selected
                                </Typography>
                            </Box>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Stack spacing={1.5}>
                                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                    {SCOPE_OPTIONS.map(scope => {
                                        const selected = selectedScopes.includes(scope.id);
                                        return (
                                            <Chip
                                                key={scope.id}
                                                clickable
                                                color={selected ? "primary" : "default"}
                                                variant={selected ? "filled" : "outlined"}
                                                label={scope.label}
                                                onClick={() => setSelectedScopes(previous => selected ? previous.filter(item => item !== scope.id) : [...previous, scope.id])}
                                            />
                                        );
                                    })}
                                </Stack>
                                <FormControl fullWidth size="small">
                                    <InputLabel>Data Groups</InputLabel>
                                    <Select
                                        multiple
                                        label="Data Groups"
                                        value={selectedDataGroupIds}
                                        onChange={event => setSelectedDataGroupIds(event.target.value as string[])}
                                        renderValue={() => selectedGroupNames.join(", ") || "None"}
                                    >
                                        {(access?.data_groups ?? []).map(group => (
                                            <MenuItem key={group._id} value={group._id}>
                                                <Checkbox checked={selectedDataGroupIds.includes(group._id)} />
                                                <ListItemText primary={group.name} secondary={group.access_mode === "team" ? "Entire team" : "Selected users"} />
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                                {selectedScopes.length === 0 && selectedDataGroupIds.length === 0 && (
                                    <Alert severity="warning">Select at least one Knowledge scope before testing retrieval.</Alert>
                                )}
                            </Stack>
                        </AccordionDetails>
                    </Accordion>
                    <Divider />

                    <Tabs
                        value={activeView}
                        onChange={(_event, value: "chat" | "trace") => setActiveView(value)}
                        sx={{ px: 2, minHeight: 42, bgcolor: "background.paper" }}
                    >
                        <Tab value="chat" label="Chat" sx={{ minHeight: 42, textTransform: "none" }} />
                        <Tab
                            value="trace"
                            label={lastResult ? `Trace (${lastResult.diagnostics.steps?.length ?? 0})` : "Trace"}
                            sx={{ minHeight: 42, textTransform: "none" }}
                        />
                    </Tabs>
                    <Divider />

                    {activeView === "chat" && <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
                        {messages.length === 0 && (
                            <Stack alignItems="center" justifyContent="center" textAlign="center" minHeight={260} spacing={1} color="text.secondary">
                                <ScienceOutlinedIcon sx={{ fontSize: 40, opacity: 0.55 }} />
                                <Typography fontWeight={600} color="text.primary">Test before activation</Typography>
                                <Typography variant="body2" maxWidth={420}>
                                    Playground saves the private draft before each run and uses real model, Knowledge, guardrail, quota and audit policies. Write-capable tools stay blocked.
                                </Typography>
                            </Stack>
                        )}
                        <Stack spacing={1.5}>
                            {messages.map((message, index) => (
                                <Box
                                    key={`${message.role}-${index}`}
                                    sx={{
                                        alignSelf: message.role === "user" ? "flex-end" : "stretch",
                                        ml: message.role === "user" ? 6 : 0,
                                        mr: message.role === "assistant" ? 4 : 0,
                                        px: 1.5,
                                        py: 1.25,
                                        borderRadius: 2,
                                        bgcolor: message.role === "user" ? "primary.main" : "background.paper",
                                        color: message.role === "user" ? "primary.contrastText" : "text.primary",
                                        border: message.role === "assistant" ? "1px solid" : "none",
                                        borderColor: "divider",
                                        overflowWrap: "anywhere"
                                    }}
                                >
                                    {message.role === "assistant" ? (
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                                    ) : (
                                        <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{message.content}</Typography>
                                    )}
                                </Box>
                            ))}
                            {running && <Stack direction="row" alignItems="center" spacing={1} color="text.secondary"><CircularProgress size={16} /><Typography variant="body2">Running Agent…</Typography></Stack>}
                            <div ref={conversationEndRef} />
                        </Stack>
                    </Box>}

                    {activeView === "trace" && (
                        <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
                            {!lastResult ? (
                                <Stack alignItems="center" justifyContent="center" textAlign="center" minHeight={260} spacing={1} color="text.secondary">
                                    <ScienceOutlinedIcon sx={{ fontSize: 40, opacity: 0.55 }} />
                                    <Typography fontWeight={600} color="text.primary">Run the Agent to inspect its flow</Typography>
                                    <Typography variant="body2" maxWidth={440}>Trace shows safe execution summaries, timing and routing. It never displays hidden reasoning, raw prompts or tool data.</Typography>
                                </Stack>
                            ) : (
                                <Stack spacing={2}>
                                    <Paper variant="outlined" sx={{ p: 1.5 }}>
                                        <Stack spacing={1}>
                                            <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                                                <Typography variant="subtitle2">Configuration snapshot</Typography>
                                                <Typography variant="caption" color="text.secondary">Prompt rev {lastResult.diagnostics.configuration.prompt_revision}</Typography>
                                            </Stack>
                                            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                                                <Chip size="small" label={`${lastResult.diagnostics.configuration.model} · ${lastResult.diagnostics.configuration.route_type}`} />
                                                <Chip size="small" label={`Temperature ${lastResult.diagnostics.configuration.temperature}`} />
                                                <Chip size="small" label={`Max tokens ${lastResult.diagnostics.configuration.max_tokens}`} />
                                                <Chip size="small" label={`Knowledge ${lastResult.diagnostics.configuration.knowledge_search}`} />
                                                <Chip size="small" label={`${lastResult.diagnostics.configuration.selected_scopes.length + lastResult.diagnostics.configuration.data_group_count} data scope(s)`} />
                                            </Stack>
                                        </Stack>
                                    </Paper>

                                    <Box>
                                        {(lastResult.diagnostics.steps ?? []).map((step, index, allSteps) => {
                                            const color = step.status === "success" ? "success.main" : step.status === "info" ? "info.main" : step.status === "blocked" ? "warning.main" : "error.main";
                                            return (
                                                <Stack key={`${step.kind}-${step.label}-${index}`} direction="row" spacing={1.5} alignItems="stretch">
                                                    <Stack alignItems="center" sx={{ width: 20, flexShrink: 0 }}>
                                                        <Box sx={{ width: 12, height: 12, mt: 1.75, borderRadius: "50%", bgcolor: color, boxShadow: theme => `0 0 0 3px ${theme.palette.background.default}` }} />
                                                        {index < allSteps.length - 1 && <Box sx={{ width: 2, flex: 1, minHeight: 20, bgcolor: "divider" }} />}
                                                    </Stack>
                                                    <Paper variant="outlined" sx={{ p: 1.25, mb: 1.25, flex: 1, minWidth: 0 }}>
                                                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                                                            <Box minWidth={0}>
                                                                <Typography variant="subtitle2" sx={{ overflowWrap: "anywhere" }}>{step.label}</Typography>
                                                                {step.summary && <Typography variant="caption" color="text.secondary">{step.summary}</Typography>}
                                                            </Box>
                                                            <Stack direction="row" spacing={0.5} alignItems="center">
                                                                {step.duration_ms !== undefined && <Typography variant="caption" color="text.secondary">{Math.round(step.duration_ms)} ms</Typography>}
                                                                <Chip size="small" variant="outlined" color={step.status === "success" ? "success" : step.status === "blocked" ? "warning" : step.status === "error" ? "error" : "info"} label={step.status} />
                                                            </Stack>
                                                        </Stack>
                                                        {step.details && (
                                                            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap mt={1}>
                                                                {step.details.iteration !== undefined && <Chip size="small" label={`Iteration ${step.details.iteration}`} />}
                                                                {step.details.source && <Chip size="small" label={`Source ${step.details.source.split(":", 1)[0]}`} />}
                                                                {step.details.risk_level && <Chip size="small" label={`Risk ${step.details.risk_level}`} />}
                                                                {step.details.requested_tools?.map(tool => <Chip key={tool} size="small" variant="outlined" label={`Calls ${tool}`} />)}
                                                                {step.details.argument_keys && step.details.argument_keys.length > 0 && <Chip size="small" variant="outlined" label={`Inputs: ${step.details.argument_keys.join(", ")}`} />}
                                                                {step.details.token_usage && <Chip size="small" variant="outlined" label={`${step.details.token_usage.total_tokens} tokens`} />}
                                                            </Stack>
                                                        )}
                                                    </Paper>
                                                </Stack>
                                            );
                                        })}
                                    </Box>
                                    <Typography variant="caption" color="text.secondary">Run ID: {lastResult.diagnostics.run_id}</Typography>
                                </Stack>
                            )}
                        </Box>
                    )}

                    {error && <Alert severity="error" sx={{ mx: 2, mb: 1 }}>{error}</Alert>}

                    {lastResult && activeView === "chat" && (
                        <Box px={2} pb={1}>
                            <Accordion disableGutters elevation={0} variant="outlined">
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                        <Typography variant="subtitle2">Run diagnostics</Typography>
                                        <Chip size="small" label={`${Math.round(lastResult.diagnostics.duration_ms)} ms`} />
                                        <Chip size="small" label={`${lastResult.diagnostics.token_usage.total_tokens} tokens`} />
                                        <Chip size="small" label={`${lastResult.diagnostics.tools.length} tools`} />
                                    </Stack>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Stack spacing={1}>
                                        <Typography variant="body2">Runtime: {lastResult.diagnostics.runtime} · Model: {lastResult.diagnostics.model} · Route: {lastResult.diagnostics.route_type}</Typography>
                                        <Typography variant="caption" color="text.secondary">Run ID: {lastResult.diagnostics.run_id}</Typography>
                                        {lastResult.diagnostics.legacy_boundary && <Alert severity="info">Legacy safe testing covers Prompt, model and Knowledge retrieval. External API execution remains disabled.</Alert>}
                                        {lastResult.diagnostics.tools.map((tool, index) => (
                                            <Stack key={`${tool.name}-${index}`} direction="row" justifyContent="space-between" spacing={1}>
                                                <Typography variant="body2">{tool.name} · {tool.source}</Typography>
                                                <Chip size="small" color={tool.status === "success" ? "success" : tool.status === "blocked" ? "warning" : "error"} label={tool.status} />
                                            </Stack>
                                        ))}
                                        {lastResult.citations.length > 0 && <Typography variant="subtitle2" pt={1}>Citations</Typography>}
                                        {lastResult.citations.map((citation, index) => <Typography key={index} variant="caption" sx={{ overflowWrap: "anywhere" }}>{citation}</Typography>)}
                                    </Stack>
                                </AccordionDetails>
                            </Accordion>
                        </Box>
                    )}

                    <Divider />
                    <Stack direction="row" alignItems="flex-end" spacing={1} p={1.5} bgcolor="background.paper">
                        <TextField
                            fullWidth
                            multiline
                            maxRows={5}
                            size="small"
                            placeholder="Ask the draft Agent…"
                            value={input}
                            disabled={disabled || running}
                            onChange={event => setInput(event.target.value)}
                            onKeyDown={event => {
                                if (event.key === "Enter" && !event.shiftKey) {
                                    event.preventDefault();
                                    void run();
                                }
                            }}
                        />
                        <Tooltip title="Save draft and run safe test">
                            <span>
                                <IconButton color="primary" disabled={!canRun} onClick={() => void run()}>
                                    {running ? <CircularProgress size={22} /> : <SendIcon />}
                                </IconButton>
                            </span>
                        </Tooltip>
                    </Stack>
                </>
            )}
        </Paper>
    );
}
