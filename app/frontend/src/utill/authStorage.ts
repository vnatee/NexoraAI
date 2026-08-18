import { AuthProfile } from "../api/models";
import { Storage } from "./storage";
import { STORAGE_KEYS } from "./storageKeys";

export const AuthStorage = {
    get(): AuthProfile | null {
        return Storage.get<AuthProfile>(STORAGE_KEYS.AUTH_PROFILE);
    },

    set(data: AuthProfile) {
        Storage.set(STORAGE_KEYS.AUTH_PROFILE, data);
    },

    clear() {
        Storage.remove(STORAGE_KEYS.AUTH_PROFILE);
    }
};
