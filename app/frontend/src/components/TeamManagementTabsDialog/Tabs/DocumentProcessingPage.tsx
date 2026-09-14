import React, { useEffect, useState } from "react";
import { Alert, Avatar, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton, MenuItem, Paper, Stack, Switch, Tab, Tabs, TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add"; import ArrowBackIcon from "@mui/icons-material/ArrowBack"; import DeleteIcon from "@mui/icons-material/Delete"; import EditIcon from "@mui/icons-material/Edit"; import DocumentScannerIcon from "@mui/icons-material/DocumentScanner"; import TuneIcon from "@mui/icons-material/Tune";
import { DocumentProcessingProfile, DocumentProcessingProvider, DocumentProcessingRoutingRule } from "../../../api/models";
import { delete_document_processing_profile, delete_document_processing_provider, get_document_processing_profiles, get_document_processing_providers, get_document_processing_routing_rules, save_document_processing_profile, save_document_processing_provider, test_document_processing_provider } from "../../../api/api";
import { getToken } from "../../../authConfig"; import { useMsal } from "@azure/msal-react"; import { useNotification } from "../../../utill/NotificationProvider";
import { DocumentProcessingRoutingRules } from "./DocumentProcessingRoutingRules";

export function DocumentProcessingPage({ onBack }: { onBack: () => void }) {
    const [tab, setTab] = useState("providers"); const [providers, setProviders] = useState<DocumentProcessingProvider[]>([]); const [profiles, setProfiles] = useState<DocumentProcessingProfile[]>([]); const [routingRules, setRoutingRules] = useState<DocumentProcessingRoutingRule[]>([]);
    const [providerDialog, setProviderDialog] = useState(false); const [profileDialog, setProfileDialog] = useState(false); const [editingProvider, setEditingProvider] = useState<DocumentProcessingProvider | null>(null); const [editingProfile, setEditingProfile] = useState<DocumentProcessingProfile | null>(null);
    const client = useMsal().instance; const { showNotification } = useNotification();
    const load = async (token?: string) => { const t = token ?? await getToken(client); if (!t) return; setProviders(await get_document_processing_providers(t)); setProfiles(await get_document_processing_profiles(t)); setRoutingRules(await get_document_processing_routing_rules(t)); };
    useEffect(() => { load().catch(e => showNotification(e.message, "error")); }, []);
    return <Box sx={{ p: { xs: 2, sm: 3 }, height: "100%", overflowY: "auto" }}><Stack direction="row" spacing={2} alignItems="center"><IconButton onClick={onBack}><ArrowBackIcon /></IconButton><Box sx={{ minWidth: 0 }}><Typography variant="h6">Document Processing & OCR</Typography><Typography variant="body2" color="text.secondary">Manage extraction engines and the profiles used by RAG ingestion.</Typography></Box></Stack><Alert severity="info" sx={{ my: 2 }}>Routing rules select profiles by team, upload scope and file type. With no match, the legacy Default profile and then the existing Azure/local startup configuration remain available as fallbacks.</Alert><Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto"><Tab value="providers" label={`Providers (${providers.length})`} /><Tab value="profiles" label={`Profiles (${profiles.length})`} /><Tab value="routing" label={`Routing Rules (${routingRules.length})`} /></Tabs>
        {tab === "providers" && <Box mt={2}><Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditingProvider(null); setProviderDialog(true); }} sx={{ mb: 2 }}>Add Provider</Button><Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))", gap: 2 }}>{providers.map(item => <Paper key={item._id} variant="outlined" sx={{ p: 2, minHeight: 280, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", position: "relative" }}><Chip size="small" color={item.enabled ? "success" : "default"} label={item.enabled ? "Enabled" : "Disabled"} sx={{ position: "absolute", top: 12, left: 12 }} /><Avatar variant="rounded" sx={{ width: 72, height: 72, mt: 3, mb: 2, bgcolor: "info.main", boxShadow: 1 }}><DocumentScannerIcon sx={{ fontSize: 42 }} /></Avatar><Typography fontWeight={700} sx={{ minHeight: 42, overflowWrap: "anywhere" }}>{item.name}</Typography><Typography variant="body2" color="text.secondary">{item.provider_type}</Typography><Box sx={{ flex: 1 }} /><Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap justifyContent="center" sx={{ mt: 2 }}>{item.has_credentials && <Chip size="small" variant="outlined" color="info" label="Credential stored" />}{item.system_managed && <Chip size="small" variant="outlined" label="System managed" />}</Stack><Stack direction="row" spacing={0.5} sx={{ mt: 1 }}><Button size="small" onClick={async () => { try { const t = await getToken(client); if (!t) return; const r = await test_document_processing_provider(item._id, t); showNotification(r.message, "success"); } catch (e) { showNotification(e instanceof Error ? e.message : "Test failed", "error"); } }}>Test</Button><IconButton aria-label={`Edit ${item.name}`} onClick={() => { setEditingProvider(item); setProviderDialog(true); }}><EditIcon /></IconButton>{!item.system_managed && <IconButton aria-label={`Delete ${item.name}`} color="error" onClick={async () => { try { const t = await getToken(client); if (!t) return; await delete_document_processing_provider(item._id, t); await load(t); } catch (e) { showNotification(e instanceof Error ? e.message : "Delete failed", "error"); } }}><DeleteIcon /></IconButton>}</Stack></Paper>)}</Box></Box>}
        {tab === "profiles" && <Box mt={2}><Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditingProfile(null); setProfileDialog(true); }} sx={{ mb: 2 }}>Add Processing Profile</Button><Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))", gap: 2 }}>{profiles.map(item => <Paper key={item._id} variant="outlined" role="button" tabIndex={0} onClick={() => { setEditingProfile(item); setProfileDialog(true); }} sx={{ p: 2, minHeight: 280, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", position: "relative", cursor: "pointer", "&:hover": { boxShadow: 3, borderColor: "primary.light", transform: "translateY(-2px)" }, transition: "transform 150ms ease, box-shadow 150ms ease" }}><Chip size="small" color={item.is_default ? "primary" : "default"} label={item.is_default ? "Default" : "Profile"} sx={{ position: "absolute", top: 12, left: 12 }} /><Avatar variant="rounded" sx={{ width: 72, height: 72, mt: 3, mb: 2, bgcolor: "secondary.main", boxShadow: 1 }}><TuneIcon sx={{ fontSize: 42 }} /></Avatar><Typography fontWeight={700} sx={{ minHeight: 42, overflowWrap: "anywhere" }}>{item.name}</Typography><Typography variant="body2" color="text.secondary">{providers.find(v => v._id === item.provider_id)?.name ?? item.provider_id}</Typography><Typography variant="caption" color="text.secondary" sx={{ mt: 1, overflowWrap: "anywhere" }}>{item.file_types.join(", ")}</Typography><Box sx={{ flex: 1 }} /><Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap justifyContent="center" sx={{ mt: 2 }}>{item.languages.map(language => <Chip key={language} size="small" variant="outlined" label={language} />)}</Stack><Box sx={{ mt: 1 }}><IconButton aria-label={`Edit ${item.name}`} onClick={event => { event.stopPropagation(); setEditingProfile(item); setProfileDialog(true); }}><EditIcon /></IconButton><IconButton aria-label={`Delete ${item.name}`} color="error" onClick={async event => { event.stopPropagation(); const t = await getToken(client); if (!t) return; await delete_document_processing_profile(item._id, t); await load(t); }}><DeleteIcon /></IconButton></Box></Paper>)}</Box></Box>}
        {tab === "routing" && <DocumentProcessingRoutingRules rules={routingRules} profiles={profiles} onReload={load} />}
        <ProviderDialog open={providerDialog} value={editingProvider} onClose={() => setProviderDialog(false)} onSave={async value => { try { const t = await getToken(client); if (!t) return; await save_document_processing_provider(value, t); await load(t); setProviderDialog(false); } catch (e) { showNotification(e instanceof Error ? e.message : "Save failed", "error"); } }} />
        <ProfileDialog open={profileDialog} value={editingProfile} providers={providers} onClose={() => setProfileDialog(false)} onSave={async value => { try { const t = await getToken(client); if (!t) throw new Error("No authentication token"); await save_document_processing_profile(value, t); await load(t); setProfileDialog(false); } catch (e) { showNotification(e instanceof Error ? e.message : "Save failed", "error"); throw e; } }} />
    </Box>;
}
function ProviderDialog({ open, value, onClose, onSave }: { open: boolean; value: DocumentProcessingProvider | null; onClose: () => void; onSave: (v: any) => void }) {
    const [name, setName] = useState("");
    const [type, setType] = useState<DocumentProcessingProvider["provider_type"]>("docling");
    const [enabled, setEnabled] = useState(true);
    const [mode, setMode] = useState("service");
    const [endpoint, setEndpoint] = useState("http://docling:5001");
    const [processPath, setProcessPath] = useState("/v1/ocr");
    const [healthPath, setHealthPath] = useState("/docs");
    const [authType, setAuthType] = useState("none");
    const [apiKeyHeader, setApiKeyHeader] = useState("X-API-Key");
    const [credentials, setCredentials] = useState("");
    const [requestMode, setRequestMode] = useState("multipart");
    const [fileField, setFileField] = useState("file");
    const [pagesPath, setPagesPath] = useState("pages");
    const [textPath, setTextPath] = useState("text");
    const [pageNumberPath, setPageNumberPath] = useState("page_number");
    const [tablesPath, setTablesPath] = useState("tables");
    const [confidencePath, setConfidencePath] = useState("confidence");
    const [projectId, setProjectId] = useState("");
    const [location, setLocation] = useState("us");
    const [processorId, setProcessorId] = useState("");
    const [processorVersion, setProcessorVersion] = useState("");
    const [apiEndpoint, setApiEndpoint] = useState("");
    useEffect(() => {
        if (!open) return;
        const config = value?.config ?? {};
        setName(value?.name ?? ""); setType(value?.provider_type ?? "docling"); setEnabled(value?.enabled ?? true);
        setMode(String(config.execution_mode ?? "service")); setEndpoint(String(config.endpoint ?? "http://docling:5001"));
        setProcessPath(String(config.process_path ?? (value?.provider_type === "paddleocr" ? "/ocr" : "/v1/ocr")));
        setHealthPath(String(config.health_path ?? "/docs")); setAuthType(String(config.auth_type ?? "none"));
        setApiKeyHeader(String(config.api_key_header ?? "X-API-Key")); setCredentials("");
        setRequestMode(String(config.request_mode ?? "multipart")); setFileField(String(config.file_field ?? "file"));
        const mapping = (config.response_mapping ?? {}) as Record<string, unknown>;
        setPagesPath(String(mapping.pages_path ?? "pages")); setTextPath(String(mapping.text_path ?? "text"));
        setPageNumberPath(String(mapping.page_number_path ?? "page_number")); setTablesPath(String(mapping.tables_path ?? "tables"));
        setConfidencePath(String(mapping.confidence_path ?? "confidence")); setProjectId(String(config.project_id ?? ""));
        setLocation(String(config.location ?? "us")); setProcessorId(String(config.processor_id ?? ""));
        setProcessorVersion(String(config.processor_version ?? "")); setApiEndpoint(String(config.api_endpoint ?? ""));
    }, [open, value]);
    const isRemoteOCR = type === "generic_ocr_api" || type === "paddleocr";
    const buildConfig = () => {
        if (type === "docling") return { execution_mode: mode, endpoint: endpoint.trim() };
        if (type === "google_document_ai") return { project_id: projectId.trim(), location: location.trim(), processor_id: processorId.trim(), processor_version: processorVersion.trim(), api_endpoint: apiEndpoint.trim() };
        if (isRemoteOCR) return { endpoint: endpoint.trim(), process_path: processPath.trim(), health_path: healthPath.trim(), auth_type: authType, api_key_header: apiKeyHeader.trim(), ...(type === "generic_ocr_api" ? { request_mode: requestMode, file_field: fileField.trim(), response_mapping: { pages_path: pagesPath.trim(), text_path: textPath.trim(), page_number_path: pageNumberPath.trim(), tables_path: tablesPath.trim(), confidence_path: confidencePath.trim() } } : {}) };
        return value?.config ?? {};
    };
    const invalid = !name.trim() || (type === "docling" && mode === "service" && !endpoint.trim()) || (isRemoteOCR && (!endpoint.trim() || !processPath.trim())) || (type === "google_document_ai" && (!projectId.trim() || !location.trim() || !processorId.trim() || (!value?.has_credentials && !credentials.trim())));
    return <Dialog open={open} onClose={onClose} fullWidth maxWidth="md"><DialogTitle>{value ? "Edit" : "Add"} Document Provider</DialogTitle><DialogContent dividers><Stack spacing={2}>
        <TextField label="Name" value={name} onChange={e => setName(e.target.value)} />
        <TextField select label="Provider Type" value={type} disabled={Boolean(value)} onChange={e => { const next = e.target.value as DocumentProcessingProvider["provider_type"]; setType(next); if (next === "paddleocr") { setEndpoint("http://paddleocr:8080"); setProcessPath("/ocr"); } }}>
            <MenuItem value="docling">Docling Local / Serve</MenuItem><MenuItem value="paddleocr">PaddleOCR / PaddleX API</MenuItem><MenuItem value="google_document_ai">Google Document AI</MenuItem><MenuItem value="generic_ocr_api">Generic OCR REST API</MenuItem><MenuItem value="local_text" disabled={!value}>Local Text (system)</MenuItem><MenuItem value="azure_document_intelligence" disabled={!value}>Azure Document Intelligence (system)</MenuItem>
        </TextField>
        {type === "docling" && <><TextField select label="Execution Mode" value={mode} onChange={e => setMode(e.target.value)}><MenuItem value="service">Docling Serve container (recommended)</MenuItem><MenuItem value="embedded">Embedded Python package</MenuItem></TextField>{mode === "service" && <TextField label="Docling Serve URL" value={endpoint} onChange={e => setEndpoint(e.target.value)} helperText="Dev container example: http://host.docker.internal:5001" />}<Alert severity="info">Service mode keeps large ML dependencies outside the web container.</Alert></>}
        {isRemoteOCR && <><TextField label="Base URL" value={endpoint} onChange={e => setEndpoint(e.target.value)} helperText={type === "paddleocr" ? "Example: http://host.docker.internal:8080" : "Base URL reachable from the backend"} />{type === "paddleocr" && <TextField select label="Paddle Pipeline" value={processPath} onChange={e => setProcessPath(e.target.value)}><MenuItem value="/ocr">General OCR</MenuItem><MenuItem value="/layout-parsing">Layout Parsing / PP-Structure</MenuItem></TextField>}{type === "generic_ocr_api" && <TextField label="Process Path" value={processPath} onChange={e => setProcessPath(e.target.value)} />}<TextField label="Health Path" value={healthPath} onChange={e => setHealthPath(e.target.value)} /><TextField select label="Authentication" value={authType} onChange={e => setAuthType(e.target.value)}><MenuItem value="none">None</MenuItem><MenuItem value="api_key">API Key</MenuItem><MenuItem value="bearer">Bearer Token</MenuItem></TextField>{authType === "api_key" && <TextField label="API Key Header" value={apiKeyHeader} onChange={e => setApiKeyHeader(e.target.value)} />}{authType !== "none" && <TextField type="password" label={value?.has_credentials ? "New credential (leave blank to keep existing)" : "Credential"} value={credentials} onChange={e => setCredentials(e.target.value)} />}</>}
        {type === "generic_ocr_api" && <><TextField select label="Request Mode" value={requestMode} onChange={e => setRequestMode(e.target.value)}><MenuItem value="multipart">Multipart file upload</MenuItem><MenuItem value="base64_json">Base64 JSON</MenuItem></TextField><TextField label="File Field" value={fileField} onChange={e => setFileField(e.target.value)} /><Typography fontWeight={700}>Response mapping</Typography><Stack direction={{ xs: "column", md: "row" }} spacing={1}><TextField fullWidth label="Pages Path" value={pagesPath} onChange={e => setPagesPath(e.target.value)} /><TextField fullWidth label="Text Path" value={textPath} onChange={e => setTextPath(e.target.value)} /><TextField fullWidth label="Page Number Path" value={pageNumberPath} onChange={e => setPageNumberPath(e.target.value)} /></Stack><Stack direction={{ xs: "column", md: "row" }} spacing={1}><TextField fullWidth label="Tables Path" value={tablesPath} onChange={e => setTablesPath(e.target.value)} /><TextField fullWidth label="Confidence Path" value={confidencePath} onChange={e => setConfidencePath(e.target.value)} /></Stack></>}
        {type === "google_document_ai" && <><Alert severity="info">Create an OCR, Layout, Form or specialized processor in Google Cloud and provide a service account with process/get permission.</Alert><Stack direction={{ xs: "column", md: "row" }} spacing={1}><TextField fullWidth label="Project ID" value={projectId} onChange={e => setProjectId(e.target.value)} /><TextField fullWidth label="Location" value={location} onChange={e => setLocation(e.target.value)} helperText="us, eu, asia-southeast1" /></Stack><Stack direction={{ xs: "column", md: "row" }} spacing={1}><TextField fullWidth label="Processor ID" value={processorId} onChange={e => setProcessorId(e.target.value)} /><TextField fullWidth label="Processor Version (optional)" value={processorVersion} onChange={e => setProcessorVersion(e.target.value)} /></Stack><TextField label="Custom API Endpoint (optional)" value={apiEndpoint} onChange={e => setApiEndpoint(e.target.value)} /><TextField multiline minRows={5} type="password" label={value?.has_credentials ? "New Service Account JSON (leave blank to keep existing)" : "Service Account JSON"} value={credentials} onChange={e => setCredentials(e.target.value)} /></>}
        <FormControlLabel control={<Switch checked={enabled} onChange={e => setEnabled(e.target.checked)} />} label="Enabled" />
    </Stack></DialogContent><DialogActions><Button onClick={onClose}>Cancel</Button><Button variant="contained" disabled={invalid} onClick={() => onSave({ provider_id: value?._id, name: name.trim(), provider_type: type, config: buildConfig(), credentials: credentials || undefined, enabled })}>Save</Button></DialogActions></Dialog>;
}
function ProfileDialog({ open, value, providers, onClose, onSave }: { open: boolean; value: DocumentProcessingProfile | null; providers: DocumentProcessingProvider[]; onClose: () => void; onSave: (v: any) => Promise<void> }) {
    const [name, setName] = useState("");
    const [provider, setProvider] = useState("");
    const [types, setTypes] = useState(".pdf,.png,.jpg,.jpeg,.tiff");
    const [languages, setLanguages] = useState("th,en");
    const [tables, setTables] = useState(true);
    const [isDefault, setDefault] = useState(false);
    const [saving, setSaving] = useState(false);
    const [clientRequestId, setClientRequestId] = useState("");
    useEffect(() => {
        if (!open) return;
        setName(value?.name ?? "");
        setProvider(value?.provider_id ?? "");
        setTypes((value?.file_types ?? [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]).join(","));
        setLanguages((value?.languages ?? ["th", "en"]).join(","));
        setTables(value?.extract_tables ?? true);
        setDefault(value?.is_default ?? false);
        setSaving(false);
        setClientRequestId(value ? "" : crypto.randomUUID());
    }, [open, value]);
    const save = async () => {
        if (saving) return;
        setSaving(true);
        try {
            await onSave({
                profile_id: value?._id,
                client_request_id: value ? undefined : clientRequestId,
                name,
                provider_id: provider,
                file_types: types.split(",").map(v => v.trim()).filter(Boolean),
                languages: languages.split(",").map(v => v.trim()).filter(Boolean),
                extract_tables: tables,
                is_default: isDefault,
                enabled: true
            });
        } finally {
            setSaving(false);
        }
    };
    return <Dialog open={open} onClose={saving ? undefined : onClose} fullWidth maxWidth="sm"><DialogTitle>{value ? "Edit" : "Add"} Processing Profile</DialogTitle><DialogContent dividers><Stack spacing={2}><TextField label="Profile Name" value={name} disabled={saving} onChange={e => setName(e.target.value)} /><TextField select label="Provider" value={provider} disabled={saving} onChange={e => setProvider(e.target.value)}>{providers.filter(v => v.enabled).map(v => <MenuItem key={v._id} value={v._id}>{v.name}</MenuItem>)}</TextField><TextField label="File Types" value={types} disabled={saving} onChange={e => setTypes(e.target.value)} helperText="Comma-separated extensions, for example .pdf,.png,.docx" /><TextField label="OCR Languages" value={languages} disabled={saving} onChange={e => setLanguages(e.target.value)} helperText="Provider language codes, for example th,en" /><FormControlLabel control={<Switch checked={tables} disabled={saving} onChange={e => setTables(e.target.checked)} />} label="Use accurate table structure extraction when supported" /><FormControlLabel control={<Switch checked={isDefault} disabled={saving} onChange={e => setDefault(e.target.checked)} />} label="Use as Default processing profile" /></Stack></DialogContent><DialogActions><Button onClick={onClose} disabled={saving}>Cancel</Button><Button variant="contained" disabled={saving || !name.trim() || !provider || !clientRequestId && !value} onClick={save}>{saving ? "Saving…" : "Save"}</Button></DialogActions></Dialog>;
}
