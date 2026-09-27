import React, { useEffect, useState } from "react";
import { Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField } from "@mui/material";
import DriveFileMoveOutlinedIcon from "@mui/icons-material/DriveFileMoveOutlined";
import { useMsal } from "@azure/msal-react";

import { assign_integration_team, get_teams, IntegrationCatalogType } from "../../../api/api";
import { TeamProfile } from "../../../api/models";
import { getToken } from "../../../authConfig";
import { useNotification } from "../../../utill/NotificationProvider";

interface Props {
    integrationId: string;
    integrationType: IntegrationCatalogType;
    onAssigned: () => void | Promise<void>;
}

export function AssignIntegrationTeamButton({ integrationId, integrationType, onAssigned }: Props) {
    const client = useMsal().instance;
    const { showNotification } = useNotification();
    const [open, setOpen] = useState(false);
    const [teams, setTeams] = useState<TeamProfile[]>([]);
    const [teamId, setTeamId] = useState("");
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (!open) return;
        let active = true;
        setLoading(true);
        getToken(client)
            .then(token => (token ? get_teams(token) : []))
            .then(result => {
                if (!active) return;
                const teamList = Array.isArray(result)
                    ? result
                    : Array.isArray(result?.result)
                      ? result.result
                      : [];
                setTeams(
                    teamList
                        .map((team: Partial<TeamProfile>) => ({
                            _id: String(team._id ?? ""),
                            name: String(team.name ?? ""),
                            permissions: Array.isArray(team.permissions) ? team.permissions : []
                        }))
                        .filter((team: TeamProfile) => team._id && team.name)
                );
            })
            .catch(error => showNotification(error instanceof Error ? error.message : "Unable to load teams", "error"))
            .finally(() => active && setLoading(false));
        return () => {
            active = false;
        };
    }, [client, open, showNotification]);

    const assign = async () => {
        try {
            setSaving(true);
            const token = await getToken(client);
            if (!token) throw new Error("No authentication token");
            await assign_integration_team(integrationType, integrationId, teamId, token);
            showNotification("Integration assigned to team", "success");
            setOpen(false);
            setTeamId("");
            await onAssigned();
        } catch (error) {
            showNotification(error instanceof Error ? error.message : "Unable to assign integration", "error");
        } finally {
            setSaving(false);
        }
    };

    return (
        <>
            <Button size="small" startIcon={<DriveFileMoveOutlinedIcon />} onClick={() => setOpen(true)}>
                Assign team
            </Button>
            <Dialog open={open} onClose={() => !saving && setOpen(false)} fullWidth maxWidth="xs">
                <DialogTitle>Assign integration to team</DialogTitle>
                <DialogContent dividers>
                    <TextField
                        select
                        fullWidth
                        label="Team"
                        value={teamId}
                        onChange={event => setTeamId(event.target.value)}
                        disabled={loading || saving}
                        helperText={loading ? "Loading teams…" : teams.length ? "Assignment cannot be changed from this dialog." : "Create a team before assigning this integration."}
                    >
                        {teams.map(team => (
                            <MenuItem key={team._id} value={team._id}>
                                {team.name}
                            </MenuItem>
                        ))}
                    </TextField>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
                    <Button variant="contained" onClick={assign} disabled={!teamId || saving}>
                        {saving ? <CircularProgress size={20} color="inherit" /> : "Assign"}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}
