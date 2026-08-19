import React, { useEffect, useState } from "react";
import {
    Box,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    InputAdornment,
    MenuItem,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { ChartBindingData } from "../../../api/models";

export interface ChartBindingInput {
    _id?: string;
    auto_generate: boolean;
    color_palette: string[];
    title_template: string;
    trigger_keywords: string[];
    enabled: boolean;
    chart_selection_mode: ChartBindingData["chart_selection_mode"];
    default_chart_type: NonNullable<ChartBindingData["default_chart_type"]>;
    allowed_chart_types: NonNullable<ChartBindingData["allowed_chart_types"]>;
}

interface ChartBindingDialogProps {
    open: boolean;
    saving?: boolean;
    initialBinding?: ChartBindingData | null;
    onClose: () => void;
    onSave: (binding: ChartBindingInput) => void;
}

const DEFAULT_PALETTE = ["#2196f3", "#ff9800", "#4caf50", "#e91e63", "#9c27b0", "#00bcd4"];
const SAFE_CHART_TYPES = ["bar", "line", "area", "pie", "scatter", "radar", "heatmap", "treemap", "sunburst", "funnel", "gauge", "boxplot", "candlestick", "sankey", "graph"];

// ── Color chip input ──────────────────────────────────────────────────────────
function ColorChipInput({
    label, values, onChange, disabled, helperText
}: {
    label: string;
    values: string[];
    onChange: (v: string[]) => void;
    disabled?: boolean;
    helperText?: string;
}) {
    const [input, setInput] = useState("");

    const addColor = () => {
        const trimmed = input.trim();
        if (!trimmed) return;
        const colors = trimmed.split(",").map(c => c.trim()).filter(c => c && !values.includes(c));
        if (colors.length) onChange([...values, ...colors]);
        setInput("");
    };

    return (
        <Box sx={{ pt: 1 }}>
            <TextField
                label={label}
                value={input}
                disabled={disabled}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                    if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addColor(); }
                }}
                fullWidth
                size="small"
                helperText={helperText}
                InputProps={{
                    endAdornment: (
                        <InputAdornment position="end">
                            <IconButton size="small" onClick={addColor} disabled={disabled || !input.trim()}>
                                <AddIcon fontSize="small" />
                            </IconButton>
                        </InputAdornment>
                    )
                }}
            />
            {values.length > 0 && (
                <Stack direction="row" flexWrap="wrap" gap={0.5} mt={1} alignItems="center">
                    {values.map(color => (
                        <Chip
                            key={color}
                            label={color}
                            size="small"
                            onDelete={disabled ? undefined : () => onChange(values.filter(v => v !== color))}
                            deleteIcon={<CloseIcon />}
                            sx={{ backgroundColor: color, color: "#fff", fontWeight: 600, fontFamily: "monospace" }}
                        />
                    ))}
                </Stack>
            )}
        </Box>
    );
}

// ── Main dialog ───────────────────────────────────────────────────────────────
export function ChartBindingDialog({ open, saving, initialBinding, onClose, onSave }: ChartBindingDialogProps) {
    const [autoGenerate, setAutoGenerate] = useState(false);
    const [colorPalette, setColorPalette] = useState<string[]>(DEFAULT_PALETTE);
    const [titleTemplate, setTitleTemplate] = useState("");
    const [triggerKeywords, setTriggerKeywords] = useState("");
    const [enabled, setEnabled] = useState(true);
    const [selectionMode, setSelectionMode] = useState<"auto" | "manual">("auto");
    const [allowedTypes, setAllowedTypes] = useState<NonNullable<ChartBindingData["allowed_chart_types"]>>(SAFE_CHART_TYPES as NonNullable<ChartBindingData["allowed_chart_types"]>);
    const [defaultType, setDefaultType] = useState<NonNullable<ChartBindingData["default_chart_type"]>>("bar");

    useEffect(() => {
        if (!open) return;
        if (initialBinding) {
            const initialAllowed = initialBinding.allowed_chart_types?.length
                ? initialBinding.allowed_chart_types
                : SAFE_CHART_TYPES as NonNullable<ChartBindingData["allowed_chart_types"]>;
            setAutoGenerate(initialBinding.auto_generate ?? false);
            setColorPalette(initialBinding.color_palette ?? DEFAULT_PALETTE);
            setTitleTemplate(initialBinding.title_template ?? "");
            setTriggerKeywords(initialBinding.trigger_keywords ? initialBinding.trigger_keywords.join(", ") : "");
            setEnabled(initialBinding.enabled !== false);
            setSelectionMode(initialBinding.chart_selection_mode ?? "auto");
            setAllowedTypes(initialAllowed);
            setDefaultType(
                initialBinding.default_chart_type && initialAllowed.includes(initialBinding.default_chart_type)
                    ? initialBinding.default_chart_type
                    : initialAllowed[0]
            );
        } else {
            setAutoGenerate(false);
            setColorPalette(DEFAULT_PALETTE);
            setTitleTemplate("");
            setTriggerKeywords("");
            setEnabled(true);
            setSelectionMode("auto");
            setAllowedTypes(SAFE_CHART_TYPES as NonNullable<ChartBindingData["allowed_chart_types"]>);
            setDefaultType("bar");
        }
    }, [open, initialBinding]);

    const handleSave = () => {
        onSave({
            _id: initialBinding?._id,
            auto_generate: autoGenerate,
            color_palette: colorPalette,
            title_template: titleTemplate,
            trigger_keywords: triggerKeywords.split(",").map(k => k.trim()).filter(Boolean),
            enabled,
            chart_selection_mode: selectionMode,
            default_chart_type: defaultType,
            allowed_chart_types: allowedTypes
        });
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>{initialBinding ? "Edit Chart Capability" : "Add Chart Capability"}</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>

                    {/* ── Auto Generate toggle ── */}
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            px: 2,
                            py: 1.5,
                            border: "1px solid",
                            borderColor: "divider",
                            borderRadius: 2,
                            bgcolor: autoGenerate ? "primary.50" : "background.paper"
                        }}
                    >
                        <Box>
                            <Typography variant="body2" fontWeight={600}>
                                Auto-generate Charts
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {autoGenerate
                                    ? "สร้างกราฟอัตโนมัติเมื่อ LLM ตอบคำถามที่มีข้อมูลตัวเลข"
                                    : "สร้างกราฟเฉพาะเมื่อ user ขอหรือพิมพ์ trigger keyword เท่านั้น"}
                            </Typography>
                        </Box>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={autoGenerate}
                                    onChange={e => setAutoGenerate(e.target.checked)}
                                    disabled={saving}
                                    color="primary"
                                />
                            }
                            label=""
                        />
                    </Box>

                    <Divider />

                    <Typography variant="subtitle2" color="text.secondary">Chart selection</Typography>
                    <TextField
                        select
                        label="Selection Mode"
                        value={selectionMode}
                        disabled={saving}
                        onChange={e => setSelectionMode(e.target.value as "auto" | "manual")}
                        helperText={selectionMode === "auto" ? "LLM เลือกชนิดกราฟจากรายการที่อนุญาต" : "จำกัดชนิดกราฟและกำหนดค่าเริ่มต้น"}
                    >
                        <MenuItem value="auto">Automatic</MenuItem>
                        <MenuItem value="manual">Restricted</MenuItem>
                    </TextField>
                    <TextField
                        select
                        SelectProps={{ multiple: true }}
                        label="Allowed Chart Types"
                        value={allowedTypes}
                        disabled={saving}
                        onChange={e => {
                            const next = (typeof e.target.value === "string" ? e.target.value.split(",") : e.target.value) as NonNullable<ChartBindingData["allowed_chart_types"]>;
                            if (next.length) {
                                setAllowedTypes(next);
                                if (!next.includes(defaultType)) setDefaultType(next[0]);
                            }
                        }}
                        helperText="ใช้เป็น allowlist ทั้ง Automatic และ Restricted mode"
                    >
                        {SAFE_CHART_TYPES.map(type => <MenuItem key={type} value={type}>{type}</MenuItem>)}
                    </TextField>
                    {selectionMode === "manual" && (
                        <TextField
                            select
                            label="Default Chart Type"
                            value={defaultType}
                            disabled={saving}
                            onChange={e => setDefaultType(e.target.value as NonNullable<ChartBindingData["default_chart_type"]>)}
                        >
                            {allowedTypes.map(type => <MenuItem key={type} value={type}>{type}</MenuItem>)}
                        </TextField>
                    )}

                    <Divider />

                    {/* ── Styling ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Styling
                    </Typography>

                    <ColorChipInput
                        label="Color Palette (hex)"
                        values={colorPalette}
                        onChange={setColorPalette}
                        disabled={saving}
                        helperText="Press Enter or comma to add. e.g. #2196f3"
                    />

                    <TextField
                        label="Title Template"
                        value={titleTemplate}
                        disabled={saving}
                        onChange={e => setTitleTemplate(e.target.value)}
                        fullWidth
                        placeholder='e.g. "{{metric}} by {{dimension}}"'
                        helperText="Optional. Use {{variable}} for placeholders the agent will fill"
                    />

                    <Divider />

                    {/* ── Triggers & Status ── */}
                    <Typography variant="subtitle2" color="text.secondary">
                        Triggers &amp; Status
                    </Typography>

                    <TextField
                        label="Trigger Keywords"
                        value={triggerKeywords}
                        disabled={saving}
                        onChange={e => setTriggerKeywords(e.target.value)}
                        helperText="Optional, comma separated. e.g. chart, graph, กราฟ, สถิติ"
                    />

                    <TextField
                        select
                        label="Status"
                        value={enabled ? "enabled" : "disabled"}
                        disabled={saving}
                        size="small"
                        sx={{ minWidth: 130 }}
                        onChange={e => setEnabled(e.target.value === "enabled")}
                    >
                        <MenuItem value="enabled">Enabled</MenuItem>
                        <MenuItem value="disabled">Disabled</MenuItem>
                    </TextField>
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button variant="contained" onClick={handleSave} disabled={saving}>
                    {saving ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
