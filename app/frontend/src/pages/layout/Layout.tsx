import React, { useState, useEffect, useRef, RefObject } from "react";
import { Outlet, NavLink, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import styles from "./Layout.module.css";

import { useLogin } from "../../authConfig";
// import appLogo from "../../../public/logo_2.svg";
import appLogo from "../../../public/insight_sphere_new.png";

import { LoginButton } from "../../components/LoginButton";
import { IconButton } from "@fluentui/react";
import { Backdrop, CircularProgress, Typography } from "@mui/material";
import { useContext } from "react";
import { LoginContext } from "../../loginContext";

const Layout = () => {
    const { t } = useTranslation();
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef: RefObject<HTMLDivElement> = useRef(null);
    const { isWaitingApprove } = useContext(LoginContext);
    const prevWaitingApproveRef = useRef<boolean>(isWaitingApprove);

    const toggleMenu = () => {
        setMenuOpen(!menuOpen);
    };

    const handleClickOutside = (event: MouseEvent) => {
        if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
            setMenuOpen(false);
        }
    };

    useEffect(() => {
        if (menuOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        } else {
            document.removeEventListener("mousedown", handleClickOutside);
        }
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [menuOpen]);

    useEffect(() => {
        const wasWaiting = prevWaitingApproveRef.current;

        if (wasWaiting && !isWaitingApprove) {
            window.location.reload();
        }

        prevWaitingApproveRef.current = isWaitingApprove;
    }, [isWaitingApprove]);

    return (
        <div className={styles.layout}>
            <header className={styles.header} role={"banner"}>
                <div className={styles.headerContainer} ref={menuRef}>
                    <Link to="/" className={styles.headerTitleContainer}>
                        {/* <img src={appLogo2} alt="App logo" width="120" height="80" /> */}
                        <img src={appLogo} alt="App logo" className={styles.appLogo} />
                    </Link>
                    <nav>
                        <ul className={`${styles.headerNavList} ${menuOpen ? styles.show : ""}`}>
                            <li>
                                <NavLink
                                    to="/"
                                    className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}
                                    onClick={() => setMenuOpen(false)}
                                >
                                    {t("chat")}
                                </NavLink>
                            </li>
                            {/* <li>
                                <NavLink
                                    to="/qa"
                                    className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}
                                    onClick={() => setMenuOpen(false)}
                                >
                                    {t("qa")}
                                </NavLink>
                            </li> */}
                        </ul>
                    </nav>
                    <div className={styles.loginMenuContainer}>
                        {useLogin && <LoginButton />}
                        {/* <IconButton
                            iconProps={{ iconName: "GlobalNavButton" }}
                            className={styles.menuToggle}
                            onClick={toggleMenu}
                            ariaLabel={t("labels.toggleMenu")}
                        /> */}
                    </div>
                </div>
            </header>
            <Backdrop
                open={isWaitingApprove}
                sx={{
                    color: "#fff",
                    zIndex: theme => theme.zIndex.modal + 10,
                    display: "flex",
                    flexDirection: "column"
                }}
            >
                <CircularProgress color="inherit" />
                <Typography sx={{ mt: 2 }} variant="h6">
                    Waiting for approval...
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                    Please wait until your account is approved
                </Typography>
            </Backdrop>

            <Outlet />
        </div>
    );
};

export default Layout;
