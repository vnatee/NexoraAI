export const STORAGE_KEYS = {
    AUTH_PROFILE: "auth_profile",
    SELECT_TEAM: "select_team",
    Active_Teams: "activeTeams",
    ACTIVE_AGENT: "activeAgent",
    ACTIVE_AGENT_UI_PREFS: "ACTIVE_AGENT_UI_PREFS"
    // LANG: "lang",
    // SIDEBAR: "sidebar_state"
} as const;

export const ACTIVE_TEAM_CHANGED_EVENT = "nexora:active-team-changed";

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];
