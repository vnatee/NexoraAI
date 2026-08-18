import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Typography,
    Stack,
    Chip,
    CircularProgress,
    Divider,
    Box,
    TextField,
    useMediaQuery,
    useTheme
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { TeamDetail, User, team_detail, Agent, DataGroupWithView } from "../../api";
import { getToken } from "../../authConfig";
import { useMsal } from "@azure/msal-react";

interface Props {
    open: boolean;
    teamId: string | null;
    onClose: () => void;
    teamName?: string;
}

export function TeamViewDialog({ open, teamId, onClose, teamName }: Props) {
    const [data, setData] = useState<TeamDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const { instance: msalInstance } = useMsal();
    const [searchUsers, setSearchUsers] = useState("");
    const [searchAgents, setSearchAgents] = useState("");
    const [searchGroups, setSearchGroups] = useState("");

    const [viewAll, setViewAll] = useState<{
        title: string;
        items: React.ReactNode[];
    } | null>(null);

    const [detailItem, setDetailItem] = useState<{
        type: "user" | "agent" | "group";
        data: any;
    } | null>(null);

    const theme = useTheme();
    const isMdUp = useMediaQuery(theme.breakpoints.up("md"));

    const fetchTeamDetail = async (teamId: string) => {
        try {
            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("Token expired → force logout");
                localStorage.clear();
                return;
            }

            const res = await team_detail(teamId, token);

            setData({
                users: res.user ?? [],
                agents: (res.agent ?? []).map((a: any) => ({
                    _id: a._id,
                    agent_name: a.agent_name, // 🔁 สำคัญ
                    prompt: a.prompt,
                    conf: a.config
                })),
                data_groups: res.data_group ?? []
            });
        } catch (error) {
            console.error("Error fetching team detail:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!open || !teamId) {
            setData(null);
            return;
        }

        setLoading(true);
        fetchTeamDetail(teamId);
    }, [open, teamId]);

    const users = useMemo(
        () => data?.users.filter(u => `${u.first_name} ${u.last_name}`.toLowerCase().includes(searchUsers.toLowerCase())) ?? [],
        [data, searchUsers]
    );

    const agents = useMemo(() => data?.agents.filter(a => a.agent_name.toLowerCase().includes(searchAgents.toLowerCase())) ?? [], [data, searchAgents]);

    const groups = useMemo(() => data?.data_groups.filter(g => g.name.toLowerCase().includes(searchGroups.toLowerCase())) ?? [], [data, searchGroups]);

    return (
        <>
            {/* ================= TEAM DETAIL ================= */}
            <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>{data ? `Team: ${teamName ? teamName : "System"}` : "Team Detail"}</DialogTitle>

                <DialogContent dividers sx={{ maxHeight: "65vh", overflowY: "auto" }}>
                    {loading ? (
                        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
                            <CircularProgress />
                        </Box>
                    ) : !data ? (
                        <Typography color="text.secondary">No data</Typography>
                    ) : (
                        <Box
                            sx={{
                                display: "grid",
                                gridTemplateColumns: isMdUp ? "1fr 1fr" : "1fr",
                                gap: 3
                            }}
                        >
                            <Section
                                title="Users"
                                search={searchUsers}
                                onSearch={setSearchUsers}
                                items={users.map(u => (
                                    <Chip key={u._id} label={`${u.first_name} ${u.last_name}`} onClick={() => setDetailItem({ type: "user", data: u })} />
                                ))}
                                onViewAll={items => setViewAll({ title: "Users", items })}
                                emptyText="No users"
                            />

                            <Section
                                title="Agents"
                                search={searchAgents}
                                onSearch={setSearchAgents}
                                items={agents.map(a => (
                                    <Chip key={a._id} label={a.agent_name} color="info" onClick={() => setDetailItem({ type: "agent", data: a })} />
                                ))}
                                onViewAll={items => setViewAll({ title: "Agents", items })}
                                emptyText="No agents"
                            />

                            <Section
                                title="Data Groups"
                                search={searchGroups}
                                onSearch={setSearchGroups}
                                items={groups.map(g => (
                                    <Chip key={g.name} label={g.name} color="success" onClick={() => setDetailItem({ type: "group", data: g })} />
                                ))}
                                onViewAll={items => setViewAll({ title: "Data Groups", items })}
                                emptyText="No data groups"
                            />
                        </Box>
                    )}
                </DialogContent>

                <DialogActions>
                    <Button onClick={onClose}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* ================= VIEW ALL ================= */}
            <Dialog open={!!viewAll} onClose={() => setViewAll(null)} maxWidth="sm" fullWidth>
                <DialogTitle>{viewAll?.title}</DialogTitle>
                <DialogContent dividers>
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>{viewAll?.items.map((item, i) => <Box key={i}>{item}</Box>)}</Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setViewAll(null)}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* ================= DETAIL ================= */}
            <Dialog open={!!detailItem} onClose={() => setDetailItem(null)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 600 }}>
                    {detailItem?.type === "user" && `User: ${detailItem.data.first_name} ${detailItem.data.last_name}`}
                    {detailItem?.type === "agent" && `Agent: ${detailItem.data.agent_name}`}
                    {detailItem?.type === "group" && `Data Group: ${detailItem.data.name}`}
                </DialogTitle>

                <DialogContent dividers>
                    {detailItem?.type === "user" && <UserDetail user={detailItem.data as User} />}
                    {detailItem?.type === "agent" && <AgentDetail agent={detailItem.data as Agent} />}
                    {detailItem?.type === "group" && <DataGroupDetail group={detailItem.data as DataGroupWithView} />}
                </DialogContent>

                <DialogActions>
                    <Button onClick={() => setDetailItem(null)}>Close</Button>
                </DialogActions>
            </Dialog>
        </>
    );
}

/* ================= SECTION ================= */
function Section({
    title,
    search,
    onSearch,
    items,
    onViewAll,
    emptyText
}: {
    title: string;
    search: string;
    onSearch: (v: string) => void;
    items: React.ReactNode[];
    onViewAll: (items: React.ReactNode[]) => void;
    emptyText: string;
}) {
    const MAX = 4;
    const visible = items.slice(0, MAX);
    const hidden = items.length - MAX;

    return (
        <Stack spacing={1}>
            <Typography variant="subtitle2">{title}</Typography>

            <TextField size="small" placeholder={`Search ${title}`} value={search} onChange={e => onSearch(e.target.value)} />

            {items.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                    {emptyText}
                </Typography>
            ) : (
                <>
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>{visible}</Box>
                    {hidden > 0 && (
                        <Typography variant="caption" color="primary" sx={{ cursor: "pointer" }} onClick={() => onViewAll(items)}>
                            +{hidden} more
                        </Typography>
                    )}
                </>
            )}
        </Stack>
    );
}

/* ================= DETAIL UI ================= */

function UserDetail({ user }: { user: User }) {
    return (
        <Stack spacing={2}>
            <DetailRow label="Email" value={user.email} />
            <DetailRow label="Employee ID" value={user.employee_id} />
            <DetailRow label="AD Email" value={user.ad_email} />
            {user.tel && <DetailRow label="Tel" value={user.tel} />}
            <DetailRow label="Status" value={<Chip label={user.active ? "Active" : "Inactive"} color={user.active ? "success" : "default"} size="small" />} />
        </Stack>
    );
}

function AgentDetail({ agent }: { agent: Agent }) {
    return (
        <Stack spacing={2}>
            <DetailRow label="Prompt" value={<CodeBox data={agent.prompt} />} />
            <DetailRow label="Config" value={<CodeBox data={agent.config} />} />
        </Stack>
    );
}

function DataGroupDetail({ group }: { group: DataGroupWithView }) {
    return (
        <Stack spacing={2}>
            <Typography variant="subtitle2">Users in group</Typography>

            {group.users && group.users.length > 0 ? (
                <Stack direction="row" spacing={1} flexWrap="wrap">
                    {group.users.map(u => (
                        <Chip key={u._id} label={`${u.first_name} ${u.last_name}`} />
                    ))}
                </Stack>
            ) : (
                <Typography variant="body2" color="text.secondary">
                    No users
                </Typography>
            )}
        </Stack>
    );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <Stack spacing={0.5}>
            <Typography variant="caption" color="text.secondary">
                {label}
            </Typography>
            <Typography variant="body2">{value}</Typography>
        </Stack>
    );
}

function CodeBox({ data }: { data: any }) {
    return (
        <Box
            sx={{
                backgroundColor: "#f5f5f5",
                borderRadius: 1,
                p: 1,
                fontFamily: "monospace",
                fontSize: 13,
                maxHeight: 200,
                overflow: "auto"
            }}
        >
            <pre style={{ margin: 0 }}>{JSON.stringify(data, null, 2)}</pre>
        </Box>
    );
}
