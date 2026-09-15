import React, { useEffect, useState } from "react";
import { MenuItem, TextField } from "@mui/material";
import { useMsal } from "@azure/msal-react";

import { get_document_processing_upload_options } from "../../api/api";
import { DocumentProcessingProfile, DocumentProcessingUploadOptions } from "../../api/models";
import { getToken } from "../../authConfig";

interface Props {
    value: string;
    onChange: (profileId: string) => void;
}

export function DocumentProcessingUploadSelector({ value, onChange }: Props) {
    const client = useMsal().instance;
    const [profiles, setProfiles] = useState<DocumentProcessingProfile[]>([]);
    const [canOverride, setCanOverride] = useState(false);

    useEffect(() => {
        let active = true;
        getToken(client)
            .then(token => token ? get_document_processing_upload_options(token) : null)
            .then((options: DocumentProcessingUploadOptions | null) => {
                if (!active || !options) return;
                setCanOverride(options.can_override);
                setProfiles(options.profiles ?? []);
                if (!options.can_override) onChange("");
            })
            .catch(() => {
                if (active) {
                    setCanOverride(false);
                    onChange("");
                }
            });
        return () => { active = false; };
    }, [client]);

    if (!canOverride) return null;
    return (
        <TextField
            select
            fullWidth
            size="small"
            label="Document processing"
            value={value}
            onChange={event => onChange(event.target.value)}
            helperText="Auto uses OCR routing rules. Manual profile selection is restricted by the backend."
            InputLabelProps={{ shrink: true }}
            SelectProps={{
                displayEmpty: true,
                renderValue: selected => {
                    const profileId = String(selected ?? "");
                    if (!profileId) return "Auto — use routing rules";
                    const profile = profiles.find(item => item._id === profileId);
                    return profile ? `${profile.name} (${profile.file_types.join(", ")})` : "Auto — use routing rules";
                }
            }}
        >
            <MenuItem value="">Auto — use routing rules</MenuItem>
            {profiles.map(profile => (
                <MenuItem key={profile._id} value={profile._id}>
                    {profile.name} ({profile.file_types.join(", ")})
                </MenuItem>
            ))}
        </TextField>
    );
}
