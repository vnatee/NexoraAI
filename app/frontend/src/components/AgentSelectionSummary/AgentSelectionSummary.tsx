import { Box, Button, Chip, Tooltip, Typography } from "@mui/material";

type AgentSelectionSummaryProps = {
    agentName?: string;
    modelName?: string;
    selectedScopes: string[];
    selectedDataGroups: string[];
    onClick: (element: HTMLButtonElement) => void;
};

const scopeLabel = (scope: string) => scope.charAt(0).toUpperCase() + scope.slice(1);

export const AgentSelectionSummary = ({
    agentName,
    modelName,
    selectedScopes,
    selectedDataGroups,
    onClick
}: AgentSelectionSummaryProps) => {
    const entries = [
        ...selectedScopes.map(scope => ({ label: scopeLabel(scope), scope: true })),
        ...selectedDataGroups.map(label => ({ label, scope: false }))
    ];
    const visibleEntries = entries.slice(0, 3);
    const hiddenCount = Math.max(entries.length - visibleEntries.length, 0);
    const fullSelection = entries.length > 0 ? entries.map(entry => entry.label).join(", ") : "No data selected";

    return (
        <Tooltip title={`Data scope: ${fullSelection}`} arrow placement="bottom-start">
            <Button
                variant="outlined"
                size="small"
                onClick={event => onClick(event.currentTarget)}
                aria-label={`${agentName ?? "Select Agent"}. Model ${modelName ?? "not selected"}. Data scope ${fullSelection}`}
                sx={{
                    textTransform: "none",
                    borderRadius: 2.5,
                    px: 1.25,
                    py: 0.7,
                    minHeight: 56,
                    maxWidth: { xs: 300, sm: 520 },
                    justifyContent: "flex-start",
                    color: "text.primary",
                    borderColor: "rgba(100, 116, 139, 0.28)",
                    bgcolor: "rgba(255, 255, 255, 0.92)",
                    boxShadow: "0 1px 3px rgba(15, 23, 42, 0.05)",
                    "&:hover": {
                        borderColor: "primary.main",
                        bgcolor: "background.paper",
                        boxShadow: "0 5px 16px rgba(15, 23, 42, 0.08)"
                    }
                }}
            >
                <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-start", minWidth: 0, gap: 0.55 }}>
                    <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.75, minWidth: 0, maxWidth: "100%" }}>
                        <Typography component="span" variant="body2" fontWeight={600} noWrap>
                            🤖 {agentName ?? "Select Agent"}
                        </Typography>
                        {agentName && modelName && (
                            <Typography component="span" variant="caption" color="text.secondary" noWrap sx={{ minWidth: 0 }}>
                                · {modelName}
                            </Typography>
                        )}
                    </Box>

                    {agentName && (
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, minWidth: 0, maxWidth: "100%", overflow: "hidden" }}>
                            <Typography component="span" variant="caption" color="text.secondary" sx={{ fontSize: "0.66rem", flexShrink: 0 }}>
                                Data scope
                            </Typography>
                            {visibleEntries.length === 0 ? (
                                <Chip
                                    label="Not selected"
                                    size="small"
                                    variant="outlined"
                                    sx={{ height: 20, fontSize: "0.66rem", color: "text.secondary" }}
                                />
                            ) : (
                                visibleEntries.map((entry, index) => (
                                    <Chip
                                        key={`${entry.scope ? "scope" : "group"}-${entry.label}-${index}`}
                                        label={entry.label}
                                        size="small"
                                        variant={entry.scope ? "filled" : "outlined"}
                                        color={entry.scope ? "primary" : "default"}
                                        sx={{
                                            height: 20,
                                            maxWidth: 130,
                                            minWidth: 0,
                                            fontSize: "0.66rem",
                                            ...(entry.scope && {
                                                color: "#1d4ed8",
                                                bgcolor: "rgba(37, 99, 235, 0.1)"
                                            }),
                                            "& .MuiChip-label": { px: 0.8, overflow: "hidden", textOverflow: "ellipsis" }
                                        }}
                                    />
                                ))
                            )}
                            {hiddenCount > 0 && (
                                <Chip label={`+${hiddenCount}`} size="small" sx={{ height: 20, fontSize: "0.66rem", "& .MuiChip-label": { px: 0.7 } }} />
                            )}
                        </Box>
                    )}
                </Box>
            </Button>
        </Tooltip>
    );
};
