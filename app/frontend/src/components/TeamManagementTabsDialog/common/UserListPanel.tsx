import { Stack, Button, List, ListItemButton, ListItemText, TextField, Box, Typography, Chip } from "@mui/material";
import { useMemo, useState } from "react";
import { User } from "../../../api/models";

type Props = {
    users: User[];
    selected: User | null;
    onSelect: (u: User) => void;
    fullWidth?: boolean;
    onCreate: () => void;
};

export function UserListPanel({ users, selected, onSelect, fullWidth, onCreate }: Props) {
    const [search, setSearch] = useState("");

    // 🔍 filter user
    const filteredUsers = useMemo(() => {
        const q = search.toLowerCase();
        return users.filter(u => `${u.first_name} ${u.last_name} ${u.employee_id} ${u.email} ${u.ad_email} ${u.local_username || ""}`.toLowerCase().includes(q));
    }, [users, search]);

    return (
        <Stack spacing={2} height="100%">
            {/* Header */}
            <Stack direction="row" spacing={1} alignItems="center">
                <Button variant="contained" size="small" sx={{ px: 2 }} onClick={onCreate}>
                    + New User
                </Button>
            </Stack>

            {/* Search */}
            <TextField size="small" placeholder="Search user..." value={search} onChange={e => setSearch(e.target.value)} />

            {/* List */}
            <Box
                sx={{
                    flex: 1,
                    overflowY: "auto",
                    borderRadius: 1,
                    border: "1px solid",
                    borderColor: "divider"
                }}
            >
                {filteredUsers.length === 0 && (
                    <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                        No users found
                    </Typography>
                )}

                <List disablePadding>
                    {filteredUsers.map(u => (
                        <ListItemButton
                            key={u._id}
                            selected={selected?._id === u._id}
                            onClick={() => onSelect(u)}
                            sx={{
                                px: 2,
                                py: 1.5,
                                minWidth: 0,
                                "&.Mui-selected": {
                                    bgcolor: "action.selected"
                                }
                            }}
                        >
                            <Box
                                sx={{
                                    display: "grid",
                                    gridTemplateColumns: fullWidth ? { xs: "minmax(0, 1fr)", md: "minmax(0, 1fr) auto" } : "minmax(0, 1fr)",
                                    alignItems: "center",
                                    gap: 1,
                                    width: "100%",
                                    minWidth: 0
                                }}
                            >
                                <ListItemText
                                    primary={`${u.first_name || ""} ${u.last_name || ""}`.trim() || u.email || u.ad_email}
                                    secondary={u.employee_id || u.email || u.ad_email}
                                    sx={{ minWidth: 0, m: 0 }}
                                    primaryTypographyProps={{ fontWeight: 500, sx: { overflowWrap: "anywhere" } }}
                                    secondaryTypographyProps={{ sx: { overflowWrap: "anywhere" } }}
                                />

                                <Stack
                                    direction="row"
                                    spacing={0.5}
                                    flexWrap="wrap"
                                    useFlexGap
                                    justifyContent={fullWidth ? { xs: "flex-start", md: "flex-end" } : "flex-start"}
                                >
                                    {u.is_sys_admin && <Chip label="System admin" size="small" color="primary" variant="outlined" />}
                                    <Chip
                                        label={u.active ? "Active" : "Inactive"}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                            fontWeight: 500,
                                            borderColor: u.active ? "success.main" : "grey.400",
                                            color: u.active ? "success.main" : "text.secondary",
                                            height: 22
                                        }}
                                    />
                                </Stack>
                            </Box>
                        </ListItemButton>
                    ))}
                </List>
            </Box>
        </Stack>
    );
}
