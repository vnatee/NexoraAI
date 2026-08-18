import { useEffect } from "react";
import { useMsal } from "@azure/msal-react";
import { getToken } from "./authConfig";
import { useContext } from "react";
import { LoginContext } from "./loginContext";
import { UserProfileWithActiveGroup } from "./api/models";

const defaultUser: UserProfileWithActiveGroup = {
    _id: "",
    name: "",
    groups: [],
    role_id: "",
    role_name: "",
    create_at: "",
    update_at: "",
    delete_at: "",
    activeGroup: null
};

export const AuthWatcher = () => {
    const { instance: msalInstance } = useMsal();
    const { loggedIn, setLoggedIn, setUserDetails } = useContext(LoginContext);

    useEffect(() => {
        if (!loggedIn) return;

        let idleTimer: any;
        let interval: any;

        const checkToken = async () => {
            const accounts = msalInstance.getAllAccounts();
            if (accounts.length === 0) {
                // 👈 ไม่มี session อยู่แล้ว → ไม่ต้อง reload
                return;
            }

            const token = await getToken(msalInstance);
            if (!token) {
                console.warn("⏰ Token expired → auto logout");
                setLoggedIn(false);
                setUserDetails(defaultUser);
                localStorage.clear();
            }
        };

        const resetIdleTimer = () => {
            clearTimeout(idleTimer);
            idleTimer = setTimeout(checkToken, 60 * 1000); // 1 นาทีหลัง user active
        };

        // 🔄 background check ทุก 10 นาที
        interval = setInterval(checkToken, 10 * 60 * 1000);

        // 🎯 listen event user activity
        window.addEventListener("mousemove", resetIdleTimer);
        window.addEventListener("keydown", resetIdleTimer);
        window.addEventListener("click", resetIdleTimer);

        resetIdleTimer();

        return () => {
            clearTimeout(idleTimer);
            clearInterval(interval);
            window.removeEventListener("mousemove", resetIdleTimer);
            window.removeEventListener("keydown", resetIdleTimer);
            window.removeEventListener("click", resetIdleTimer);
        };
    }, [loggedIn, msalInstance, setLoggedIn, setUserDetails]);

    return null; // 👈 ไม่ render อะไร
};
