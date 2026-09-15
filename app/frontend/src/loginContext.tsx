/**
 * This file defines a context for managing login state in a React application.
 * Context provides a way to pass data through the component tree without having to pass props down manually at every level.
 * For more information, refer to the official React documentation:
 * https://react.dev/learn/passing-data-deeply-with-context
 */

import { createContext } from "react";
import { UserProfile } from "./api/models";

interface LoginContextType {
    loggedIn: boolean;
    setLoggedIn: (value: boolean) => void;

    userDetails: UserProfile | null;
    setUserDetails: (value: UserProfile | null) => void;

    isUserLoading: boolean;
    setIsUserLoading: (v: boolean) => void;

    // ✅ เพิ่ม 2 บรรทัดนี้
    isWaitingApprove: boolean;
    setIsWaitingApprove: (v: boolean) => void;

    isSwitchTeam: boolean;
    setIsSwitchTeam: (v: boolean) => void;
}

export const LoginContext = createContext<LoginContextType>({
    loggedIn: false,
    setLoggedIn: () => {},

    userDetails: null,
    setUserDetails: () => {},

    isUserLoading: false,
    setIsUserLoading: () => {},

    // ✅ เพิ่ม
    isWaitingApprove: false,
    setIsWaitingApprove: () => {},

    isSwitchTeam: false,
    setIsSwitchTeam: () => {}
});
