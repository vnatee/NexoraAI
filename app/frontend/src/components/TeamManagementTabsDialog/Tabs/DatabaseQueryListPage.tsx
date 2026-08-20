import React, { useEffect, useState } from "react";
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Skeleton,
    Stack,
    Switch,
    TextField,
    Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import StorageIcon from "@mui/icons-material/Storage";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";

import { DatabaseConnection, DbType, TeamProfile } from "../../../api/models";
import { delete_db_connection, edit_db_connection, get_db_connections, insert_db_connection, test_db_connection } from "../../../api/api";
import { getToken } from "../../../authConfig";
import { useMsal } from "@azure/msal-react";
import { useNotification } from "../../../utill/NotificationProvider";

const DB_TYPES: { value: DbType; label: string; defaultPort: number }[] = [
    { value: "postgresql", label: "PostgreSQL", defaultPort: 5432 },
    { value: "mysql", label: "MySQL / MariaDB", defaultPort: 3306 },
    { value: "mssql", label: "Microsoft SQL Server", defaultPort: 1433 },
    { value: "mongodb", label: "MongoDB", defaultPort: 27017 },
    { value: "sqlite", label: "SQLite (Local)", defaultPort: 0 }
];

export function DatabaseQueryListPage({ team, onBack }: { team: TeamProfile; onBack: () => void }) {
    const [connections, setConnections] = useState<DatabaseConnection[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState<DatabaseConnection | null>(null);

    const client = useMsal().instance;
    const { showNotification } = useNotification();

    const loadConnections = async (tokenOverride?: string) => {
        const token = tokenOverride ?? (await getToken(client));
        if (!token) throw new Error("No authentication token");

        const res = await get_db_connections(team._id, token);
        setConnections(Array.isArray(res) ? res : []);
    };

    useEffect(() => {
        async function load() {
            try {
                setLoading(true);
                await loadConnections();
            } catch (err) {
                console.error("load db connections failed", err);
                showNotification("Failed to load database connections", "error");
            } finally {
                setLoading(false);
            }
        }

        load();
    }, [client, team._id]);

    const handleSave = async (conn: DatabaseConnection) => {
        try {
            setSaving(true);
            setLoading(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");

            const payload: any = {
                team_id: team._id,
                name: conn.name,
                db_type: conn.db_type,
                host: conn.host,
                port: conn.port,
                database: conn.database,
                username: conn.username,
                password: conn.password,
                options: conn.options
            };

            if (editing) {
                payload.connection_id = conn._id;
                await edit_db_connection(payload, token);
                showNotification("Database connection updated successfully", "success");
            } else {
                await insert_db_connection(payload, token);
                showNotification("Database connection created successfully", "success");
            }

            await loadConnections(token);
            setOpen(false);
            setEditing(null);
        } catch (err) {
            console.error("save db connection failed", err);
            showNotification(err instanceof Error ? err.message : "Failed to save database connection", "error");
        } finally {
            setSaving(false);
            setLoading(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm("Delete this database connection? Agent database bindings that reference it will stop working.")) return;

        try {
            setDeletingId(id);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await delete_db_connection(id, token);
            setConnections(prev => prev.filter(item => item._id !== id));
            showNotification("Database connection deleted successfully", "success");
        } catch (err) {
            console.error("delete db connection failed", err);
            showNotification("Failed to delete database connection", "error");
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <Box p={3} sx={{ height: "100%", overflowY: "auto" }}>
            <Stack direction="row" alignItems="center" spacing={2} mb={2}>
                <IconButton onClick={onBack}>
                    <ArrowBackIcon />
                </IconButton>
                <Box>
                    <Typography variant="h6">Database Connections</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Connection catalog for read-only Agent database tools. Query profiles and table access are assigned per Agent.
                    </Typography>
                </Box>
            </Stack>

            <Stack direction={{ xs: "column", md: "row" }} spacing={2} mb={3}>
                <SummaryCard title="Connections" value={connections.length} subtitle="Configured database targets" />
            </Stack>

            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ mb: 2 }}>
                Add Connection
            </Button>

            {loading ? (
                <DatabaseConnectionSkeleton count={3} />
            ) : connections.length === 0 ? (
                <EmptyState
                    icon={<StorageIcon sx={{ fontSize: 48, opacity: 0.3 }} />}
                    title="No database connections yet"
                    description="Add a connection first so backend APIs can be wired to the right database later."
                />
            ) : (
                <Stack spacing={2}>
                    {connections.map(conn => (
                        <Paper
                            key={conn._id}
                            variant="outlined"
                            sx={{
                                p: 2.5,
                                borderRadius: 2
                            }}
                        >
                            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
                                <Box>
                                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                                        <Typography fontWeight={700}>{conn.name}</Typography>
                                        <Chip size="small" label={DB_TYPES.find(item => item.value === conn.db_type)?.label ?? conn.db_type} />
                                        <Chip size="small" label="Read-only" color="success" variant="outlined" />
                                        <Chip size="small" label={`${conn.agent_usage_count ?? 0} Agent(s)`} color="primary" variant="outlined" />
                                        <Chip
                                            size="small"
                                            label={conn.db_type === "sqlite" || conn.has_password ? "Credentials configured" : "Credential status unknown"}
                                            color={conn.db_type === "sqlite" || conn.has_password ? "success" : "default"}
                                            variant="outlined"
                                        />
                                    </Stack>

                                    <Typography variant="body2" color="text.secondary" mt={0.75}>
                                        {conn.db_type === "sqlite" ? "Local read-only file" : `${conn.host}:${conn.port}`}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Database: {conn.database}
                                    </Typography>
                                    {conn.db_type !== "sqlite" && (
                                        <Typography variant="caption" color="text.secondary">
                                            Username: {conn.username || "Not configured"}
                                        </Typography>
                                    )}
                                </Box>

                                <Stack direction="row" spacing={1} alignSelf={{ xs: "flex-start", md: "center" }}>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        disabled={testingId === conn._id}
                                        startIcon={testingId === conn._id ? <CircularProgress size={14} /> : undefined}
                                        onClick={async () => {
                                            try {
                                                setTestingId(conn._id);
                                                const token = await getToken(client);
                                                if (!token) throw new Error("No authentication token");
                                                const result = await test_db_connection({ database_id: conn._id }, token);
                                                showNotification(result.message, "success");
                                            } catch (error) {
                                                showNotification(error instanceof Error ? error.message : "Database connection test failed", "error");
                                            } finally {
                                                setTestingId(null);
                                            }
                                        }}
                                    >
                                        {testingId === conn._id ? "Testing..." : "Test"}
                                    </Button>
                                    <IconButton
                                        onClick={() => {
                                            setEditing(conn);
                                            setOpen(true);
                                        }}
                                    >
                                        <EditIcon />
                                    </IconButton>

                                    <IconButton color="error" disabled={deletingId === conn._id} onClick={() => handleDelete(conn._id)}>
                                        {deletingId === conn._id ? <CircularProgress size={20} color="inherit" /> : <DeleteIcon />}
                                    </IconButton>
                                </Stack>
                            </Stack>
                        </Paper>
                    ))}
                </Stack>
            )}

            <DatabaseConnectionDialog
                open={open}
                connection={editing}
                team={team}
                saving={saving}
                onClose={() => {
                    if (saving) return;
                    setOpen(false);
                    setEditing(null);
                }}
                onSave={handleSave}
                onTest={async conn => {
                    const token = await getToken(client);
                    if (!token) throw new Error("No authentication token");
                    const result = await test_db_connection({ ...conn, database_id: editing?._id || undefined }, token);
                    showNotification(result.message, "success");
                }}
            />
        </Box>
    );
}

function DatabaseConnectionDialog({
    open,
    connection,
    team,
    saving,
    onClose,
    onSave,
    onTest
}: {
    open: boolean;
    connection: DatabaseConnection | null;
    team: TeamProfile;
    saving?: boolean;
    onClose: () => void;
    onSave: (conn: DatabaseConnection) => void;
    onTest: (conn: DatabaseConnection) => Promise<void>;
}) {
    const [name, setName] = useState("");
    const [dbType, setDbType] = useState<DbType>("postgresql");
    const [host, setHost] = useState("");
    const [port, setPort] = useState(5432);
    const [database, setDatabase] = useState("");
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [sslMode, setSslMode] = useState<"disable" | "prefer" | "require" | "verify-ca" | "verify-full">("prefer");
    const [authSource, setAuthSource] = useState("admin");
    const [tls, setTls] = useState(false);
    const [connectTimeout, setConnectTimeout] = useState(10);
    const [testing, setTesting] = useState(false);
    const { showNotification } = useNotification();

    useEffect(() => {
        if (!open) return;

        if (connection) {
            setName(connection.name);
            setDbType(connection.db_type);
            setHost(connection.host);
            setPort(connection.port);
            setDatabase(connection.database);
            setUsername(connection.username);
            setPassword("");
            setSslMode(connection.options?.ssl_mode ?? "prefer");
            setAuthSource(connection.options?.auth_source ?? "admin");
            setTls(connection.options?.tls ?? false);
            setConnectTimeout(connection.options?.connect_timeout_seconds ?? 10);
        } else {
            setName("");
            setDbType("postgresql");
            setHost("");
            setPort(5432);
            setDatabase("");
            setUsername("");
            setPassword("");
            setSslMode("prefer");
            setAuthSource("admin");
            setTls(false);
            setConnectTimeout(10);
        }

        setShowPassword(false);
    }, [connection, open]);

    const handleDbTypeChange = (newType: DbType) => {
        const current = DB_TYPES.find(item => item.value === dbType);
        setDbType(newType);

        if (port === (current?.defaultPort ?? port)) {
            const next = DB_TYPES.find(item => item.value === newType);
            if (next) setPort(next.defaultPort);
        }
    };

    const isSqlite = dbType === "sqlite";
    const isValid = Boolean(name.trim() && database.trim() && (isSqlite || (host.trim() && port > 0)));
    const formValue = (): DatabaseConnection => ({
        _id: connection?._id ?? "",
        team_id: team._id,
        name,
        db_type: dbType,
        host: isSqlite ? "" : host,
        port: isSqlite ? 0 : port,
        database,
        username: isSqlite ? "" : username,
        password,
        options: {
            ssl_mode: sslMode,
            auth_source: authSource,
            tls,
            connect_timeout_seconds: connectTimeout
        }
    });

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>{connection ? "Edit Database Connection" : "Add Database Connection"}</DialogTitle>

            <DialogContent dividers>
                <Stack spacing={3}>
                    <TextField label="Connection Name" disabled={saving} value={name} onChange={e => setName(e.target.value)} fullWidth />

                    <TextField
                        select
                        label="Database Type"
                        disabled={saving}
                        value={dbType}
                        onChange={e => handleDbTypeChange(e.target.value as DbType)}
                        fullWidth
                    >
                        {DB_TYPES.map(item => (
                            <MenuItem key={item.value} value={item.value}>
                                {item.label}
                            </MenuItem>
                        ))}
                    </TextField>

                    {!isSqlite && (
                        <Stack direction="row" spacing={2}>
                            <TextField
                                label="Host"
                                disabled={saving}
                                value={host}
                                onChange={e => setHost(e.target.value)}
                                fullWidth
                                placeholder="e.g. localhost or 192.168.1.1"
                            />

                            <TextField
                                label="Port"
                                disabled={saving}
                                value={port}
                                onChange={e => setPort(Number(e.target.value))}
                                type="number"
                                sx={{ width: 120, flexShrink: 0 }}
                                inputProps={{ min: 1, max: 65535 }}
                            />
                        </Stack>
                    )}

                    <TextField
                        label={isSqlite ? "SQLite File" : "Database"}
                        disabled={saving}
                        value={database}
                        onChange={e => setDatabase(e.target.value)}
                        fullWidth
                        placeholder={isSqlite ? "e.g. analytics.db" : "Database name"}
                        helperText={isSqlite ? "Relative to LOCAL_DATABASE_ROOT (default: data/databases); existing files only." : undefined}
                    />

                    {!isSqlite && <TextField label="Username" disabled={saving} value={username} onChange={e => setUsername(e.target.value)} fullWidth />}

                    {!isSqlite && (
                        <TextField
                            label="Password"
                            disabled={saving}
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            type={showPassword ? "text" : "password"}
                            fullWidth
                            placeholder={connection?.has_password ? "Leave blank to keep the stored password" : undefined}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton size="small" onClick={() => setShowPassword(value => !value)} edge="end">
                                            {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                                        </IconButton>
                                    </InputAdornment>
                                )
                            }}
                        />
                    )}

                    {dbType === "postgresql" && (
                        <TextField
                            select
                            label="SSL Mode"
                            value={sslMode}
                            disabled={saving || testing}
                            onChange={e => setSslMode(e.target.value as typeof sslMode)}
                            fullWidth
                        >
                            {(["disable", "prefer", "require", "verify-ca", "verify-full"] as const).map(value => (
                                <MenuItem key={value} value={value}>
                                    {value}
                                </MenuItem>
                            ))}
                        </TextField>
                    )}

                    {dbType === "mongodb" && (
                        <TextField
                            label="Authentication Source"
                            value={authSource}
                            disabled={saving || testing}
                            onChange={e => setAuthSource(e.target.value)}
                            fullWidth
                        />
                    )}

                    {(dbType === "mongodb" || dbType === "mysql" || dbType === "mssql") && (
                        <FormControlLabel
                            control={<Switch checked={tls} onChange={e => setTls(e.target.checked)} disabled={saving || testing} />}
                            label={dbType === "mssql" ? "Require TLS" : "Use TLS"}
                        />
                    )}

                    <TextField
                        label="Connection Timeout (seconds)"
                        type="number"
                        value={connectTimeout}
                        disabled={saving || testing}
                        onChange={e => setConnectTimeout(Number(e.target.value))}
                        inputProps={{ min: 1, max: 60 }}
                        fullWidth
                    />
                </Stack>
            </DialogContent>

            <DialogActions>
                <Button
                    disabled={!isValid || saving || testing}
                    onClick={async () => {
                        try {
                            setTesting(true);
                            await onTest(formValue());
                        } catch (err) {
                            showNotification(err instanceof Error ? err.message : "Connection test failed", "error");
                        } finally {
                            setTesting(false);
                        }
                    }}
                >
                    {testing ? "Testing..." : "Test Connection"}
                </Button>
                <Button onClick={onClose} disabled={saving}>
                    Cancel
                </Button>

                <Button variant="contained" disabled={!isValid || saving || testing} onClick={() => onSave(formValue())}>
                    {saving ? "Saving..." : "Save"}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

function SummaryCard({ title, value, subtitle }: { title: string; value: number; subtitle: string }) {
    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                flex: 1,
                minWidth: 0,
                borderRadius: 2
            }}
        >
            <Typography variant="body2" color="text.secondary">
                {title}
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={0.5}>
                {value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
                {subtitle}
            </Typography>
        </Paper>
    );
}

function EmptyState({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
    return (
        <Box
            sx={{
                mt: 4,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                textAlign: "center",
                gap: 1.5,
                color: "text.secondary"
            }}
        >
            {icon}
            <Typography variant="body1">{title}</Typography>
            <Typography variant="body2" sx={{ maxWidth: 520 }}>
                {description}
            </Typography>
        </Box>
    );
}

function DatabaseConnectionSkeleton({ count = 3 }: { count?: number }) {
    return (
        <Stack spacing={2}>
            {Array.from({ length: count }).map((_, index) => (
                <Paper key={index} variant="outlined" sx={{ p: 2.5 }}>
                    <Skeleton variant="text" width="30%" height={28} />
                    <Skeleton variant="text" width="45%" height={22} />
                    <Skeleton variant="text" width="25%" height={18} />
                </Paper>
            ))}
        </Stack>
    );
}
