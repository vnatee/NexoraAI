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
    Autocomplete
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
import { scrapingApi, listWebApi, deleteWebContentApi, get_data_group_by_team } from "../../api/api";
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
}

export const ScrapData: React.FC<Props> = ({ disabled, dialogRef, className }) => {
    const [open, setOpen] = useState(false);
    const [url, setUrl] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingList, setIsLoadingList] = useState(true);
    const [listWebContents, setListWebContents] = useState<WebContentItem[]>([]);
    const [currentPage, setCurrentPage] = useState(1);
    const [deletingUrl, setDeletingUrl] = useState<string | null>(null);
    const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
    const [inProgressPage, setInProgressPage] = useState(1);
    const { userDetails } = useContext(LoginContext);
    const role = userDetails?.role_name ?? "";
    const email = userDetails?.name ?? "";
    const [userData, setUserData] = useState<User | null>(null);
    const [selectTeamData, setSelectTeamData] = useState<TeamProfile | null>(null);
    const [tab, setTab] = useState<"global" | "team">("global");
    const [dataGroups, setDataGroups] = useState<DataGroup[]>([]);
    const [selectedDataGroupIds, setSelectedDataGroupIds] = useState<string[]>([]);
    const [sysPers, setSysPers] = useState<string[] | null>(null);
    // state สำหรับ jobs ที่กำลัง scrape
    const [inProgressJobs, setInProgressJobs] = useState<string[]>([]);

    const IN_PROGRESS_PER_PAGE = 3;
    const inProgressPageCount = Math.ceil(inProgressJobs.length / IN_PROGRESS_PER_PAGE);
    const currentInProgressJobs = inProgressJobs.slice((inProgressPage - 1) * IN_PROGRESS_PER_PAGE, inProgressPage * IN_PROGRESS_PER_PAGE);

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

            const savedJobs = localStorage.getItem("inProgressJobs");
            if (savedJobs) setInProgressJobs(JSON.parse(savedJobs));
            else setInProgressJobs([]);

            fetchListWeb();
        }
    }, [open]);

    const updateInProgressJobs = (jobs: string[]) => {
        setInProgressJobs(jobs);
        localStorage.setItem("inProgressJobs", JSON.stringify(jobs));
    };

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
                        dataGroups: item[1] ?? []
                    };
                }

                // fallback (เผื่อ backend ยังมีของเก่า)
                return {
                    url: item,
                    dataGroups: []
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

    const handleUrlChange = (event: ChangeEvent<HTMLInputElement>) => {
        setUrl(event.target.value.trim());
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

    // ใช้ useEffect เพื่อ sync localStorage ทุกครั้งที่ inProgressJobs เปลี่ยน
    useEffect(() => {
        localStorage.setItem("inProgressJobs", JSON.stringify(inProgressJobs));
    }, [inProgressJobs]);

    // ฟังก์ชันจัดการลบ job ออกจาก inProgressJobs
    const removeJobFromInProgress = (urlToRemove: string) => {
        setInProgressJobs(prevJobs => prevJobs.filter(job => job !== urlToRemove));
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

    // Fire-and-forget background scraping
    const processScrapingInBackground = async (url: string, token: string) => {
        window.dispatchEvent(
            new CustomEvent("scrapingNotification", {
                detail: { message: "🚀 Scraping job submitted! Processing in the background...", severity: "info" }
            })
        );

        const teamId = tab === "team" ? await getTargetTeamId() : null; // ✅

        scrapingApi(url, token, teamId, tab === "team" ? selectedDataGroupIds : undefined)
            .then((response: SimpleAPIResponse) => {
                window.dispatchEvent(
                    new CustomEvent("scrapingNotification", {
                        detail: { message: response.message || "✅ Web scraping completed successfully!", severity: "success" }
                    })
                );
            })
            .catch((error: any) => {
                console.error("Background scraping error:", error);
                const errorMessage = error.message ? `❌ ${error.message}` : "❌ Scraping job failed in the background.";
                window.dispatchEvent(
                    new CustomEvent("scrapingNotification", {
                        detail: { message: errorMessage, severity: "error" }
                    })
                );
            })
            .finally(() => {
                removeJobFromInProgress(url);
                fetchListWeb();
            });
    };

    const handleSubmit = async () => {
        if (!url.trim() || !isValidUrl(url)) {
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: "Please enter a valid URL (starting with http:// or https://)", severity: "warning" }
                })
            );
            return;
        }

        setIsLoading(true);

        try {
            const token = await getToken(msalInstance);
            if (tab === "team" && selectedDataGroupIds.length === 0) {
                window.dispatchEvent(
                    new CustomEvent("scrapingNotification", {
                        detail: { message: "Please select at least one data group before uploading.", severity: "error" }
                    })
                );
                handleClose2();
                return;
            }
            if (!token) throw new Error("Unable to authenticate. Please sign in again.");

            // เพิ่มเข้า inProgressJobs ทันที
            setInProgressJobs(prevJobs => [...prevJobs, url]);

            handleClose2(); // ปิด dialog / clear input
            processScrapingInBackground(url, token); // fire-and-forget
        } catch (error: any) {
            console.error("Error during job submission:", error);
            window.dispatchEvent(
                new CustomEvent("scrapingNotification", {
                    detail: { message: `Failed to submit job: ${error.message}`, severity: "error" }
                })
            );
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        setOpen(false);
        setUrl("");
        setIsLoading(false);
        setDeletingUrl(null);
    };

    const handleClose2 = () => {
        setUrl("");
        setIsLoading(false);
    };

    const isValidUrl = (string: string): boolean => {
        try {
            const url = new URL(string);
            return url.protocol === "http:" || url.protocol === "https:";
        } catch {
            return false;
        }
    };

    const pageCount = Math.ceil(listWebContents.length / ITEMS_PER_PAGE);
    const currentListItems = listWebContents.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

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
                    Web Scraping
                </Button>
            </div>

            <Dialog
                open={open}
                onClose={handleClose}
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
                                <Tab value="global" label="Global Data" />
                                <Tab value="team" label="Team Data" />
                            </Tabs>
                        ) : (
                            <Typography variant="h6" component="div">
                                {canGlobal ? "Web Scraping for Company Data" : "Web Scraping for Team Data"}
                            </Typography>
                        )}
                    </Box>

                    {isLoading && (
                        <Chip
                            size="small"
                            label="Submitting job..."
                            icon={<CircularProgress size={16} color="inherit" />}
                            sx={{ backgroundColor: "rgba(255, 255, 255, 0.2)", color: "white" }}
                        />
                    )}

                    <IconButton onClick={handleClose} size="small" disabled={isLoading} sx={{ color: "white" }}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>

                <DialogContent sx={{ pt: 3, pb: 2 }}>
                    {tab === "global" && !canGlobal ? (
                        <Alert severity="warning">You don't have permission to view Company scraping.</Alert>
                    ) : tab === "team" && !canTeam ? (
                        <Alert severity="warning">You don't have permission to view Team scraping.</Alert>
                    ) : (
                        <>
                            <Paper elevation={0} sx={{ p: 3, background: "linear-gradient(145deg, #f8f9fa, #e9ecef)", borderRadius: "12px" }}>
                                <TextField
                                    fullWidth
                                    label="URL to Scrape"
                                    placeholder="https://example.com"
                                    value={url}
                                    onChange={handleUrlChange}
                                    variant="outlined"
                                    disabled={isLoading}
                                    error={url.length > 0 && !isValidUrl(url)}
                                    helperText={url.length > 0 && !isValidUrl(url) ? "Please enter a valid URL" : "Enter the website URL to collect all data."}
                                />
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
                                        disabled={!selectTeamData?._id} // ✅ ใช้ teamId/active team
                                        renderInput={params => <TextField {...params} size="small" placeholder="Search data group..." />}
                                        isOptionEqualToValue={(option, value) => option._id === value._id}
                                        noOptionsText="No data group found"
                                    />
                                </Box>
                            )}

                            {/* In Progress Jobs */}
                            {inProgressJobs.length > 0 && (
                                <>
                                    <Divider sx={{ my: 3 }}>
                                        <Chip label="In Progress Jobs" />
                                    </Divider>
                                    <Paper elevation={0} sx={{ p: 2, background: "#f8f9fa", borderRadius: "12px" }}>
                                        <List dense>
                                            {currentInProgressJobs.map(item => (
                                                <ListItem
                                                    key={item}
                                                    sx={{ borderRadius: "8px", border: "1px solid #ff9800", backgroundColor: "rgba(255, 152, 0, 0.05)" }}
                                                >
                                                    <Tooltip title={item} placement="top" arrow>
                                                        <ListItemText primary={truncateText(item, 60)} secondary="Status: In Progress..." />
                                                    </Tooltip>
                                                    <CircularProgress size={20} sx={{ ml: 2, color: "#ff9800" }} />
                                                </ListItem>
                                            ))}
                                        </List>
                                        {inProgressPageCount > 1 && (
                                            <Box sx={{ display: "flex", justifyContent: "center", mt: 1 }}>
                                                <Pagination
                                                    count={inProgressPageCount}
                                                    page={inProgressPage}
                                                    onChange={(e, value) => setInProgressPage(value)}
                                                    color="primary"
                                                    size="small"
                                                />
                                            </Box>
                                        )}
                                    </Paper>
                                </>
                            )}

                            <Divider sx={{ my: 3 }}>
                                <Chip label="Scraped Websites" />
                            </Divider>

                            <Paper elevation={0} sx={{ p: 2, background: "#f8f9fa", borderRadius: "12px" }}>
                                {isLoadingList ? (
                                    <Box sx={{ display: "flex", justifyContent: "center", my: 4 }}>
                                        <CircularProgress />
                                    </Box>
                                ) : listWebContents.length === 0 ? (
                                    <Typography variant="body2" color="text.secondary" align="center" sx={{ my: 4 }}>
                                        No websites have been scraped yet.
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
                                                            item.dataGroups.length > 0 && (
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
                                                            )
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
                    <MuiButton onClick={handleClose} variant="outlined" disabled={isLoading}>
                        Cancel
                    </MuiButton>
                    <MuiButton
                        onClick={handleSubmit}
                        variant="contained"
                        disabled={!url.trim() || !isValidUrl(url) || isLoading}
                        startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                    >
                        {isLoading ? "Submitting..." : "Submit Scraping Job"}
                    </MuiButton>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
