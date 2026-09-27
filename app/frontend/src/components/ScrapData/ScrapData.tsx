import React, { useState, ChangeEvent, useEffect, useContext } from "react";
import { Button } from "@fluentui/react-components";
import {
    Box,
    Button as MuiButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Typography,
    IconButton,
    TextField,
    CircularProgress,
    Chip,
    Paper,
    Slide,
    Backdrop,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    Pagination,
    Divider,
    Tooltip,
    Tabs,
    Tab,
    Alert,
    Autocomplete,
    MenuItem,
    Checkbox,
    LinearProgress
} from "@mui/material";
import { useMsal } from "@azure/msal-react";
import LibraryAddCheckIcon from "@mui/icons-material/LibraryAddCheck";
import CloseIcon from "@mui/icons-material/Close";
import SendIcon from "@mui/icons-material/Send";
import LinkIcon from "@mui/icons-material/Link";
import DeleteIcon from "@mui/icons-material/Delete";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import styles from "./ScrapData.module.css";
import {
    WebSourceScan,
    cancelWebSourceScanApi,
    confirmWebSourceScanApi,
    deleteWebContentApi,
    get_data_group_by_team,
    listWebApi,
    listWebSourceScansApi,
    retryWebSourceScanApi,
    scanWebSourceApi
} from "../../api/api";
import { getToken, getUsername } from "../../authConfig";
import { LoginContext } from "../../loginContext";
import { DataGroup, TeamProfile, User } from "../../api";
import { AuthStorage } from "../../utill/authStorage";
import { STORAGE_KEYS } from "../../utill/storageKeys";
import { Storage } from "../../utill/storage";
import { hasPermission } from "../../utill/hasPermission";

interface SimpleAPIResponse {
    message?: string;
    [key: string]: any;
}

interface Props {
    disabled?: boolean;
    className?: string;
    dialogRef?: React.RefObject<HTMLDivElement>;
}

const Transition = React.forwardRef(function Transition(props: any, ref: React.Ref<unknown>) {
    return <Slide direction="up" ref={ref} {...props} />;
});

const ITEMS_PER_PAGE = 5;

interface WebContentItem {
    url: string;
    dataGroups: string[];
    lastRefreshedAt?: string | null;
    pages?: number;
    crawlDepth: 0 | 1 | 2;
    truncated: boolean;
    limitReason?: string | null;
}

export const ScrapData: React.FC<Props> = ({ disabled, dialogRef, className }) => {
    const [open, setOpen] = useState(false);
    const [url, setUrl] = useState("");
    const [crawlDepth, setCrawlDepth] = useState<0 | 1 | 2>(1);
    const [limitProfile, setLimitProfile] = useState<"standard" | "extended">("standard");
    const [scanPreview, setScanPreview] = useState<WebSourceScan | null>(null);
    const [selectedPageUrls, setSelectedPageUrls] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isIndexing, setIsIndexing] = useState(false);
    const [isLoadingList, setIsLoadingList] = useState(true);
    const [listWebContents, setListWebContents] = useState<WebContentItem[]>([]);
    const [webSourceJobs, setWebSourceJobs] = useState<WebSourceScan[]>([]);
    const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [deletingUrl, setDeletingUrl] = useState<string | null>(null);
    const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
    const { userDetails } = useContext(LoginContext);
    const role = userDetails?.role_name ?? "";
    const email = userDetails?.name ?? "";
    const [userData, setUserData] = useState<User | null>(null);
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);
    const [tab, setTab] = useState<"global" | "team">("global");
    const [dataGroups, setDataGroups] = useState<DataGroup[]>([]);
    const [selectedDataGroupIds, setSelectedDataGroupIds] = useState<string[]>([]);
    const [sysPers, setSysPers] = useState<string[] | null>(null);
    const { instance: msalInstance } = useMsal();
    const { instance } = useMsal();

    const restoreActiveTeam = async () => {
        const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
        if (!activeTeams) {
            return;
        }

        const name = (await getUsername(instance)) ?? "";

        const selectTeam = activeTeams[name];
        setSelectTeamData(selectTeam);
    };

    useEffect(() => {
        if (!open) return;

        const user = AuthStorage.get()?.user ?? null;
        const sys_permission = AuthStorage.get()?.sys_permissions ?? null;
        setUserData(user);
        setSysPers(sys_permission);
        restoreActiveTeam();
    }, [open]);

    useEffect(() => {
        if (open) {
            const savedDeletingUrl = localStorage.getItem("deletingUrl");
            if (savedDeletingUrl) setDeletingUrl(savedDeletingUrl);
            else setDeletingUrl(null);

            fetchListWeb();
        }
    }, [open]);

    const fetchListWeb = async () => {
        setIsLoadingList(true);
        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Authentication failed.");

            const teamId = tab === "team" ? await getTargetTeamId() : null; // ✅ ใช้ tab + activeTeams

            const responseData: any[] = await listWebApi(token, teamId);

            const mapped: WebContentItem[] = (responseData || []).map(item => {
                if (Array.isArray(item)) {
                    return {
                        url: item[0],
                        dataGroups: item[1] ?? [],
                        lastRefreshedAt: item[2] ?? null,
                        pages: item[3] ?? undefined,
                        crawlDepth: item[4] === 0 || item[4] === 2 ? item[4] : 1,
                        truncated: item[5] === true,
                        limitReason: item[6] ?? null
                    };
                }

                // fallback (เผื่อ backend ยังมีของเก่า)
                return {
                    url: item,
                    dataGroups: [],
                    lastRefreshedAt: null,
                    pages: undefined,
                    crawlDepth: 1,
                    truncated: false,
                    limitReason: null
                };
            });

            setListWebContents(mapped);
        } catch (error) {
            console.error("Failed to fetch web list:", error);
            setListWebContents([]);
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: "❌ Could not load the list of websites.", severity: "error" }
                })
            );
        } finally {
            setIsLoadingList(false);
        }
    };

    const fetchIndexJobs = async () => {
        try {
            const token = await getToken(msalInstance);
            if (!token) return;
            const teamId = tab === "team" ? await getTargetTeamId() : null;
            const jobs = await listWebSourceScansApi(token, teamId, 10);
            setWebSourceJobs(current => {
                const wasActive = current.some(job => job.status === "queued" || job.status === "indexing");
                const isActive = jobs.some(job => job.status === "queued" || job.status === "indexing");
                if (wasActive && !isActive) void fetchListWeb();
                return jobs;
            });
        } catch (error) {
            console.error("Failed to load web source indexing jobs:", error);
        }
    };

    const handleRetryJob = async (scanId: string) => {
        setRetryingJobId(scanId);
        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Authentication failed.");
            const job = await retryWebSourceScanApi(scanId, token);
            setWebSourceJobs(current => [job, ...current.filter(item => item.scan_id !== scanId)]);
            window.dispatchEvent(new CustomEvent("scrapingNotification", {
                detail: { message: "Failed pages were queued for retry.", severity: "info" }
            }));
        } catch (error: any) {
            window.dispatchEvent(new CustomEvent("scrapingNotification", {
                detail: { message: `Retry failed: ${error.message}`, severity: "error" }
            }));
        } finally {
            setRetryingJobId(null);
        }
    };

    const handleUrlChange = (event: ChangeEvent<HTMLInputElement>) => {
        const nextUrl = event.target.value.trim();
        setUrl(nextUrl);
        const existingSource = listWebContents.find(item => item.url === nextUrl);
        if (existingSource) setCrawlDepth(existingSource.crawlDepth);
    };

    const truncateText = (text: string, maxLength: number) => {
        return text.length > maxLength ? text.substring(0, maxLength) + "..." : text;
    };

    const handleDelete = async (urlToDelete: string) => {
        setDeletingUrl(urlToDelete);
        setConfirmingDelete(null);

        window.dispatchEvent(
            new CustomEvent("scrapingNotification", {
                detail: { message: `🕒 Deleting "${truncateText(urlToDelete, 60)}"...`, severity: "info" }
            })
        );

        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Authentication failed.");

            const teamId = tab === "team" ? await getTargetTeamId() : null; // ✅

            await deleteWebContentApi(urlToDelete, token, teamId);

            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: "✅ URL deleted successfully!", severity: "success" }
                })
            );
            localStorage.removeItem("deletingUrl");
        } catch (error: any) {
            console.error("Failed to delete web content:", error);
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: `❌ Failed to delete URL: ${error.message}`, severity: "error" }
                })
            );
        } finally {
            setDeletingUrl(null);
            localStorage.removeItem("deletingUrl");
            await fetchListWeb();
        }
    };

    const hasRole = (roles: string | string[] | undefined, check: string[]) => {
        if (!roles) return false;
        if (Array.isArray(roles)) {
            return roles.some(r => check.includes(r));
        }
        return check.includes(roles);
    };

    const getActiveTeamId = async (): Promise<string | undefined> => {
        const activeTeams = Storage.get(STORAGE_KEYS.Active_Teams) as Record<string, any> | null;
        if (!activeTeams) return undefined;

        const username = (await getUsername(instance)) ?? "";
        if (!username) return undefined;

        const team = activeTeams[username];
        return team?._id;
    };

    const handleSubmit = async () => {
        if (!url.trim() || !isValidUrl(url)) {
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: "Enter a public HTTP(S) root URL without credentials, query parameters, or a custom port.", severity: "warning" }
                })
            );
            return;
        }
        if (tab === "team" && selectedDataGroupIds.length === 0) {
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: "Please select at least one data group before scanning.", severity: "error" }
                })
            );
            return;
        }
        setIsLoading(true);
        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Unable to authenticate. Please sign in again.");
            const teamId = tab === "team" ? await getTargetTeamId() : null;
            const preview = await scanWebSourceApi(
                url,
                token,
                teamId,
                tab === "team" ? selectedDataGroupIds : undefined,
                crawlDepth,
                limitProfile
            );
            setScanPreview(preview);
            setSelectedPageUrls(preview.pages.map(page => page.url));
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: {
                        message: `Scan complete: ${preview.pages_found} page(s), ${formatBytes(preview.bytes_found)}. Review before indexing.`,
                        severity: preview.truncated ? "warning" : "success"
                    }
                })
            );
        } catch (error: any) {
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: `Scan failed: ${error.message}`, severity: "error" }
                })
            );
        } finally {
            setIsLoading(false);
        }
    };

    const handleDiscardScan = async () => {
        const preview = scanPreview;
        setScanPreview(null);
        setSelectedPageUrls([]);
        if (!preview) return;
        try {
            const token = await getToken(msalInstance);
            if (token) await cancelWebSourceScanApi(preview.scan_id, token);
        } catch (error) {
            console.error("Failed to discard staged web source scan:", error);
        }
    };

    const handleConfirmScan = async () => {
        if (!scanPreview || selectedPageUrls.length === 0) return;
        setIsIndexing(true);
        try {
            const token = await getToken(msalInstance);
            if (!token) throw new Error("Unable to authenticate. Please sign in again.");
            const response = await confirmWebSourceScanApi(
                scanPreview.scan_id,
                selectedPageUrls,
                token
            );
            setWebSourceJobs(current => [response, ...current.filter(item => item.scan_id !== response.scan_id)]);
            setScanPreview(null);
            setSelectedPageUrls([]);
            setUrl("");
            setCrawlDepth(1);
            setLimitProfile("standard");
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: {
                        message: response.message || "Indexing started. You can close this page safely.",
                        severity: "info"
                    }
                })
            );
        } catch (error: any) {
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: `Indexing failed: ${error.message}`, severity: "error" }
                })
            );
        } finally {
            setIsIndexing(false);
        }
    };

    const handleClose = () => {
        void handleDiscardScan();
        setOpen(false);
        setUrl("");
        setCrawlDepth(1);
        setLimitProfile("standard");
        setSelectedPageUrls([]);
        setIsLoading(false);
        setIsIndexing(false);
        setDeletingUrl(null);
    };

    const formatBytes = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
    };

    const isValidUrl = (string: string): boolean => {
        try {
            const parsed = new URL(string);
            const expectedPort = parsed.protocol === "https:" ? "443" : "80";
            return (parsed.protocol === "http:" || parsed.protocol === "https:") &&
                !parsed.username && !parsed.password && !parsed.search &&
                (!parsed.port || parsed.port === expectedPort);
        } catch {
            return false;
        }
    };

    const pageCount = Math.ceil(listWebContents.length / ITEMS_PER_PAGE);
    const currentListItems = listWebContents.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);
    const selectedPageBytes = scanPreview
        ? scanPreview.pages
              .filter(page => selectedPageUrls.includes(page.url))
              .reduce((total, page) => total + page.size, 0)
        : 0;

    const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
        setCurrentPage(value);
    };

    const canGlobal = hasPermission({
        is_sys_admin: userData ? userData?.is_sys_admin : false,
        permissions: selectTeamData ? selectTeamData?.permissions : [],
        sys_permissions: sysPers ? sysPers : [],
        requiredPermissions: ["Manage global uploads"]
    });

    const canTeam = hasPermission({
        is_sys_admin: userData ? userData?.is_sys_admin : false,
        permissions: selectTeamData ? selectTeamData?.permissions : [],
        sys_permissions: [],
        requiredPermissions: ["Manage team uploads"]
    });

    const getTargetTeamId = async (): Promise<string | undefined> => {
        // global mode = ไม่ต้องส่ง team_id
        if (tab === "global") return undefined;

        // team mode
        return await getActiveTeamId();
    };

    useEffect(() => {
        if (!open) return;

        // ✅ default tab ตาม permission
        if (canGlobal) setTab("global");
        else if (canTeam) setTab("team");
    }, [open, canGlobal, canTeam]);

    useEffect(() => {
        if (!open) return;
        fetchListWeb();
    }, [tab]);

    useEffect(() => {
        if (!open) return;
        void fetchIndexJobs();
        const timer = window.setInterval(() => void fetchIndexJobs(), 3000);
        return () => window.clearInterval(timer);
    }, [open, tab]);

    useEffect(() => {
        const loadDataGroups = async () => {
            try {
                if (!open) return;
                if (tab !== "team") return;

                const token = await getToken(msalInstance);
                if (!token) return;

                const teamId = await getActiveTeamId();
                if (!teamId) {
                    setDataGroups([]);
                    setSelectedDataGroupIds([]);
                    return;
                }

                const list = await get_data_group_by_team(teamId, token); // ✅ call ของจริง
                setDataGroups(list ?? []);
                setSelectedDataGroupIds([]); // ✅ reset selection
            } catch (err) {
                console.error("load data groups failed:", err);
                setDataGroups([]);
                setSelectedDataGroupIds([]);
            }
        };

        loadDataGroups();
    }, [open, tab]);

    return (
        <Box>
            <div className={`${styles.container} ${className ?? ""}`} ref={dialogRef}>
                <Button
                    id="calloutButton"
                    icon={<LibraryAddCheckIcon />}
                    className="buttonText"
                    style={{ columnGap: "0.5rem" }}
                    onClick={() => setOpen(true)}
                    disabled={disabled}
                >
                    Approved Web Sources
                </Button>
            </div>

            <Dialog
                open={open}
                onClose={(_, reason) => {
                    if (reason !== "backdropClick" && reason !== "escapeKeyDown") handleClose();
                }}
                fullWidth
                maxWidth="md"
                TransitionComponent={Transition}
                BackdropComponent={Backdrop}
                BackdropProps={{ sx: { backgroundColor: "rgba(0, 0, 0, 0.7)", backdropFilter: "blur(4px)" } }}
                PaperProps={{
                    sx: { borderRadius: "16px", boxShadow: "0 24px 48px rgba(0, 0, 0, 0.2)", background: "linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%)" }
                }}
            >
                <DialogTitle
                    sx={{
                        pb: 1,
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        background: "linear-gradient(90deg, #1976d2, #42a5f5)",
                        color: "white",
                        margin: 0,
                        borderRadius: "16px 16px 0 0"
                    }}
                >
                    <LinkIcon />

                    <Box sx={{ flexGrow: 1 }}>
                        {/* ✅ ถ้ามีสิทธิ์ทั้งคู่ => ให้เลือก tab */}
                        {canGlobal && canTeam ? (
                            <Tabs
                                value={tab}
                                onChange={(_, v) => setTab(v)}
                                textColor="inherit"
                                indicatorColor="secondary"
                                sx={{
                                    minHeight: 32,
                                    "& .MuiTab-root": { minHeight: 32, color: "white", textTransform: "none" }
                                }}
                            >
                                <Tab value="global" label="Company Data" disabled={Boolean(scanPreview) || isLoading || isIndexing} />
                                <Tab value="team" label="Team Data" disabled={Boolean(scanPreview) || isLoading || isIndexing} />
                            </Tabs>
                        ) : (
                            <Typography variant="h6" component="div">
                                {canGlobal ? "Company Web Sources" : "Team Web Sources"}
                            </Typography>
                        )}
                    </Box>

                    {(isLoading || isIndexing) && (
                        <Chip
                            size="small"
                            label={isIndexing ? "Indexing..." : "Scanning..."}
                            icon={<CircularProgress size={16} color="inherit" />}
                            sx={{ backgroundColor: "rgba(255, 255, 255, 0.2)", color: "white" }}
                        />
                    )}

                    <IconButton onClick={handleClose} size="small" disabled={isLoading || isIndexing} sx={{ color: "white" }}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>

                <DialogContent sx={{ pt: 3, pb: 2 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                        Approved sources are fetched as bounded, point-in-time copies for RAG. This is not live web search.
                    </Alert>
                    {tab === "global" && !canGlobal ? (
                        <Alert severity="warning">You do not have permission to manage Company web sources.</Alert>
                    ) : tab === "team" && !canTeam ? (
                        <Alert severity="warning">You do not have permission to manage Team web sources.</Alert>
                    ) : (
                        <>
                            <Paper elevation={0} sx={{ p: 3, background: "linear-gradient(145deg, #f8f9fa, #e9ecef)", borderRadius: "12px" }}>
                                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1fr) 180px 210px" }, gap: 2 }}>
                                    <TextField
                                        fullWidth
                                        label="Approved website root URL"
                                        placeholder="https://docs.example.com/product/"
                                        value={url}
                                        onChange={handleUrlChange}
                                        variant="outlined"
                                        disabled={isLoading || isIndexing || Boolean(scanPreview)}
                                        error={url.length > 0 && !isValidUrl(url)}
                                        helperText={url.length > 0 && !isValidUrl(url) ? "Use a public HTTP(S) URL without credentials, query parameters, or a custom port." : "Indexes the root page and same-host links under this path. Re-submit the same URL to refresh its snapshot."}
                                    />
                                    <TextField
                                        select
                                        label="Crawl depth"
                                        value={crawlDepth}
                                        onChange={event => setCrawlDepth(Number(event.target.value) as 0 | 1 | 2)}
                                        disabled={isLoading || isIndexing || Boolean(scanPreview)}
                                        helperText="Maximum link levels"
                                    >
                                        <MenuItem value={0}>0 — Root only</MenuItem>
                                        <MenuItem value={1}>1 — Recommended</MenuItem>
                                        <MenuItem value={2}>2 — Extended</MenuItem>
                                    </TextField>
                                    <TextField
                                        select
                                        label="Scan limits"
                                        value={limitProfile}
                                        onChange={event => setLimitProfile(event.target.value as "standard" | "extended")}
                                        disabled={isLoading || isIndexing || Boolean(scanPreview)}
                                        helperText="Verify before indexing"
                                    >
                                        <MenuItem value="standard">Standard limits</MenuItem>
                                        <MenuItem value="extended">Extended (up to 250 / 100 MiB)</MenuItem>
                                    </TextField>
                                </Box>
                            </Paper>

                            {tab === "team" && (
                                <Box sx={{ mb: 2 }}>
                                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                                        Select Data Group
                                    </Typography>

                                    <Autocomplete
                                        multiple
                                        options={dataGroups}
                                        getOptionLabel={option => option.name}
                                        value={dataGroups.filter(g => selectedDataGroupIds.includes(g._id))}
                                        onChange={(_, values) => {
                                            setSelectedDataGroupIds(values.map(v => v._id));
                                        }}
                                        disabled={!selectTeamData?._id || Boolean(scanPreview) || isLoading || isIndexing}
                                        renderInput={params => <TextField {...params} size="small" placeholder="Search data group..." />}
                                        isOptionEqualToValue={(option, value) => option._id === value._id}
                                        noOptionsText="No data group found"
                                    />
                                </Box>
                            )}

                            {scanPreview && (
                                <Paper variant="outlined" sx={{ mt: 2, p: 2, borderColor: scanPreview.truncated ? "warning.main" : "success.main" }}>
                                    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap", mb: 1 }}>
                                        <Typography variant="h6">Review scan manifest</Typography>
                                        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                                            <Chip size="small" label={`${selectedPageUrls.length} of ${scanPreview.pages_found} selected`} color="primary" />
                                            <Chip size="small" label={`${formatBytes(selectedPageBytes)} selected`} />
                                            <Chip size="small" label={`Depth ${scanPreview.crawl_depth}`} />
                                            <Chip size="small" label={scanPreview.limit_profile === "extended" ? "Extended limits" : "Standard limits"} />
                                        </Box>
                                    </Box>
                                    <Alert severity={scanPreview.truncated ? "warning" : "success"} sx={{ mb: 1.5 }}>
                                        {scanPreview.truncated
                                            ? `The scan reached the ${scanPreview.limit_reason === "page_limit" ? "page" : "total size"} limit. Review this partial manifest before indexing.`
                                            : "Scan completed. Nothing has been added to RAG yet."}
                                    </Alert>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.5 }}>
                                        <Checkbox
                                            checked={selectedPageUrls.length === scanPreview.pages.length}
                                            indeterminate={
                                                selectedPageUrls.length > 0 &&
                                                selectedPageUrls.length < scanPreview.pages.length
                                            }
                                            onChange={event => {
                                                setSelectedPageUrls(
                                                    event.target.checked
                                                        ? scanPreview.pages.map(page => page.url)
                                                        : []
                                                );
                                            }}
                                            disabled={isIndexing}
                                            inputProps={{ "aria-label": "Select all scanned pages" }}
                                        />
                                        <Typography variant="body2">
                                            Select all pages
                                        </Typography>
                                    </Box>
                                    <List dense sx={{ maxHeight: 260, overflow: "auto", border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                                        {scanPreview.pages.map(page => (
                                            <ListItem key={page.url} divider>
                                                <Checkbox
                                                    edge="start"
                                                    checked={selectedPageUrls.includes(page.url)}
                                                    onChange={event => {
                                                        setSelectedPageUrls(current =>
                                                            event.target.checked
                                                                ? [...new Set([...current, page.url])]
                                                                : current.filter(item => item !== page.url)
                                                        );
                                                    }}
                                                    disabled={isIndexing}
                                                    inputProps={{ "aria-label": `Select ${page.title || page.url}` }}
                                                />
                                                <ListItemText
                                                    primary={page.title || page.url}
                                                    secondary={`${page.url} · ${formatBytes(page.size)}`}
                                                    secondaryTypographyProps={{ sx: { overflowWrap: "anywhere" } }}
                                                />
                                            </ListItem>
                                        ))}
                                    </List>
                                    {selectedPageUrls.length === 0 && (
                                        <Alert severity="warning" sx={{ mt: 1 }}>
                                            Select at least one page before confirming the index.
                                        </Alert>
                                    )}
                                    {scanPreview.issues.length > 0 && (
                                        <Box sx={{ mt: 1.5 }}>
                                            <Typography variant="subtitle2" color="warning.main">Scan issues ({scanPreview.pages_skipped})</Typography>
                                            {scanPreview.issues.slice(0, 10).map((issue, index) => (
                                                <Typography key={`${issue.url}-${index}`} variant="caption" display="block" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
                                                    {issue.url}: {issue.reason}
                                                </Typography>
                                            ))}
                                        </Box>
                                    )}
                                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                                        Staged content expires {scanPreview.expires_at ? new Date(scanPreview.expires_at).toLocaleString() : "within 24 hours"} if it is not indexed.
                                    </Typography>
                                </Paper>
                            )}

                            {webSourceJobs.some(job => job.status !== "ready") && (
                                <Paper variant="outlined" sx={{ mt: 2, p: 2 }}>
                                    <Typography variant="h6" sx={{ mb: 1 }}>Recent indexing jobs</Typography>
                                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                                        Jobs continue in the background. You can close this page and return later.
                                    </Typography>
                                    {webSourceJobs.filter(job => job.status !== "ready").map(job => {
                                        const active = job.status === "queued" || job.status === "indexing";
                                        const failedPages = job.pages.filter(page => page.status === "failed");
                                        return (
                                            <Box key={job.scan_id} sx={{ py: 1.5, borderTop: "1px solid", borderColor: "divider", "&:first-of-type": { borderTop: 0 } }}>
                                                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                                                    <Typography variant="subtitle2" sx={{ overflowWrap: "anywhere" }}>{job.source_url}</Typography>
                                                    <Chip
                                                        size="small"
                                                        label={job.status}
                                                        color={job.status === "indexed" ? "success" : job.status === "failed" ? "error" : "primary"}
                                                        variant={active ? "filled" : "outlined"}
                                                    />
                                                </Box>
                                                <LinearProgress
                                                    variant="determinate"
                                                    value={Math.min(100, Math.max(0, job.progress_percent || 0))}
                                                    color={job.status === "failed" ? "error" : "primary"}
                                                    sx={{ mt: 1, mb: 0.5, height: 8, borderRadius: 4 }}
                                                />
                                                <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, flexWrap: "wrap" }}>
                                                    <Typography variant="caption" color="text.secondary">
                                                        {job.pages_completed}/{job.pages_selected} completed · {job.pages_indexed} indexed · Attempt {job.attempt}
                                                        {job.pages_failed > 0 ? ` · ${job.pages_failed} failed` : ""}
                                                    </Typography>
                                                    {job.status === "failed" && (
                                                        <MuiButton
                                                            size="small"
                                                            onClick={() => void handleRetryJob(job.scan_id)}
                                                            disabled={retryingJobId === job.scan_id}
                                                        >
                                                            {retryingJobId === job.scan_id ? "Retrying..." : "Retry failed pages"}
                                                        </MuiButton>
                                                    )}
                                                </Box>
                                                {failedPages.map(page => (
                                                    <Alert key={page.url} severity="error" sx={{ mt: 1 }}>
                                                        <Typography variant="caption" sx={{ overflowWrap: "anywhere" }}>
                                                            {page.url}: {page.error?.message || "Page indexing failed"}
                                                        </Typography>
                                                    </Alert>
                                                ))}
                                            </Box>
                                        );
                                    })}
                                </Paper>
                            )}

                            <Divider sx={{ my: 3 }}>
                                <Chip label="Approved Sources" />
                            </Divider>

                            <Paper elevation={0} sx={{ p: 2, background: "#f8f9fa", borderRadius: "12px" }}>
                                {isLoadingList ? (
                                    <Box sx={{ display: "flex", justifyContent: "center", my: 4 }}>
                                        <CircularProgress />
                                    </Box>
                                ) : listWebContents.length === 0 ? (
                                    <Typography variant="body2" color="text.secondary" align="center" sx={{ my: 4 }}>
                                        No approved web sources have been indexed yet.
                                    </Typography>
                                ) : (
                                    <>
                                        <List dense>
                                            {currentListItems.map(item => (
                                                <ListItem
                                                    key={item.url}
                                                    sx={{
                                                        borderRadius: "8px",
                                                        alignItems: "flex-start",
                                                        "&:hover": { backgroundColor: "#f1f3f5" }
                                                    }}
                                                >
                                                    <ListItemText
                                                        primary={
                                                            <Tooltip title={item.url} placement="top" arrow>
                                                                <span style={{ cursor: "default" }}>{truncateText(item.url, 60)}</span>
                                                            </Tooltip>
                                                        }
                                                        secondary={
                                                            <Box sx={{ mt: 0.5 }}>
                                                                {(item.pages || item.lastRefreshedAt) && (
                                                                    <Typography variant="caption" color="text.secondary" display="block">
                                                                        {item.pages ? `${item.pages} indexed page${item.pages === 1 ? "" : "s"}` : ""}
                                                                        {item.pages ? " · " : ""}Depth {item.crawlDepth}
                                                                        {item.lastRefreshedAt ? ` · Refreshed ${new Date(item.lastRefreshedAt).toLocaleString()}` : ""}
                                                                    </Typography>
                                                                )}
                                                                {item.truncated && (
                                                                    <Typography variant="caption" color="warning.main" display="block">
                                                                        Partial snapshot · {item.limitReason === "page_limit" ? "page limit reached" : "total size limit reached"}
                                                                    </Typography>
                                                                )}
                                                                {item.dataGroups.length > 0 && (
                                                                <Box
                                                                    sx={{
                                                                        mt: 0.5,
                                                                        display: "flex",
                                                                        gap: 0.5,
                                                                        flexWrap: "wrap"
                                                                    }}
                                                                >
                                                                    {/* แสดง 2 group แรก */}
                                                                    {item.dataGroups.slice(0, 2).map(g => (
                                                                        <Chip
                                                                            key={g}
                                                                            label={g}
                                                                            size="small"
                                                                            variant="outlined"
                                                                            sx={{
                                                                                fontSize: "0.7rem",
                                                                                height: 20
                                                                            }}
                                                                        />
                                                                    ))}

                                                                    {/* +N more */}
                                                                    {item.dataGroups.length > 2 && (
                                                                        <Tooltip title={item.dataGroups.join(", ")}>
                                                                            <Chip
                                                                                label={`+${item.dataGroups.length - 2} more`}
                                                                                size="small"
                                                                                sx={{
                                                                                    fontSize: "0.7rem",
                                                                                    height: 20
                                                                                }}
                                                                            />
                                                                        </Tooltip>
                                                                    )}
                                                                </Box>
                                                                )}
                                                            </Box>
                                                        }
                                                    />

                                                    <ListItemSecondaryAction>
                                                        {deletingUrl === item.url ? (
                                                            <CircularProgress size={20} />
                                                        ) : confirmingDelete === item.url ? (
                                                            <Box display="flex" gap={1}>
                                                                <Tooltip title="Confirm Delete">
                                                                    <IconButton
                                                                        color="success"
                                                                        onClick={() => {
                                                                            localStorage.setItem("deletingUrl", item.url);
                                                                            handleDelete(item.url); // ✅ ส่งแค่ URL
                                                                        }}
                                                                        disabled={deletingUrl !== null}
                                                                    >
                                                                        <CheckCircleIcon />
                                                                    </IconButton>
                                                                </Tooltip>

                                                                <Tooltip title="Cancel">
                                                                    <IconButton
                                                                        color="inherit"
                                                                        onClick={() => setConfirmingDelete(null)}
                                                                        disabled={deletingUrl !== null}
                                                                    >
                                                                        <CancelIcon />
                                                                    </IconButton>
                                                                </Tooltip>
                                                            </Box>
                                                        ) : (
                                                            <Tooltip title="Delete">
                                                                <IconButton
                                                                    edge="end"
                                                                    aria-label="delete"
                                                                    onClick={() => setConfirmingDelete(item.url)}
                                                                    disabled={deletingUrl !== null}
                                                                >
                                                                    <DeleteIcon />
                                                                </IconButton>
                                                            </Tooltip>
                                                        )}
                                                    </ListItemSecondaryAction>
                                                </ListItem>
                                            ))}
                                        </List>

                                        {pageCount > 1 && (
                                            <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
                                                <Pagination count={pageCount} page={currentPage} onChange={handlePageChange} color="primary" />
                                            </Box>
                                        )}
                                    </>
                                )}
                            </Paper>
                        </>
                    )}
                </DialogContent>

                <DialogActions sx={{ p: 3, gap: 2 }}>
                    {scanPreview ? (
                        <>
                            <MuiButton onClick={handleDiscardScan} variant="outlined" disabled={isIndexing}>
                                Discard Scan
                            </MuiButton>
                            <MuiButton
                                onClick={handleConfirmScan}
                                variant="contained"
                                disabled={isIndexing || selectedPageUrls.length === 0}
                                startIcon={isIndexing ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                            >
                                {isIndexing ? "Indexing..." : `Confirm Index (${selectedPageUrls.length})`}
                            </MuiButton>
                        </>
                    ) : (
                        <MuiButton
                            onClick={handleSubmit}
                            variant="contained"
                            disabled={!url.trim() || !isValidUrl(url) || isLoading || isIndexing}
                            startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                        >
                            {isLoading ? "Scanning..." : "Scan & Verify"}
                        </MuiButton>
                    )}
                </DialogActions>
            </Dialog>
        </Box>
    );
};
