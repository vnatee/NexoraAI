import { DefaultButton } from "@fluentui/react";
import { useMsal } from "@azure/msal-react";
import { useTranslation } from "react-i18next";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, IconButton, Avatar, Menu, MenuItem, Typography, Box } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import CircularProgress from "@mui/material/CircularProgress";
import styles from "./LoginButton.module.css";
import { getRedirectUri, loginRequest, appServicesLogout, getUsername, checkLoggedIn, getUsernameTest } from "../../authConfig";
import { useState, useEffect, useContext } from "react";
import { LoginContext } from "../../loginContext";
import Divider from "@mui/material/Divider";

export const LoginButton = () => {
    const { instance } = useMsal();
    const { loggedIn, setLoggedIn } = useContext(LoginContext);
    // const loggedIn = true; // mock: เปลี่ยนเป็น false เพื่อทดสอบกรณี logout
    // const setLoggedIn = () => {}; // mock: ฟังก์ชันว่างสำหรับทดสอบ
    const activeAccount = instance.getActiveAccount();
    // const activeAccount = {
    //     username: "john.doe@example.com",
    //     name: "John Doe",
    //     localAccountId: "1234567890"
    //     // เพิ่ม field อื่นๆ ตามที่ MSAL คืนค่ามาได้
    // };
    const [username, setUsername] = useState("");
    const { t } = useTranslation();
    // สำหรับเมนู
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    useEffect(() => {
        const fetchUsername = async () => {
            setUsername((await getUsername(instance)) ?? "");
        };
        console.log("activeAccount: ", activeAccount);

        fetchUsername();
    }, []);

    const handleLoginPopup = () => {
        /**
         * When using popup and silent APIs, we recommend setting the redirectUri to a blank page or a page
         * that does not implement MSAL. Keep in mind that all redirect routes must be registered with the application
         * For more information, please follow this link: https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/login-user.md#redirecturi-considerations
         */
        instance
            .loginPopup({
                ...loginRequest,
                redirectUri: getRedirectUri()
            })
            .catch(error => console.log(error))
            .then(async () => {
                setLoggedIn(await checkLoggedIn(instance));
                setUsername((await getUsername(instance)) ?? "");
            });
    };
    const handleLogoutPopup = () => {
        if (activeAccount) {
            instance
                .logoutPopup({
                    mainWindowRedirectUri: "/", // redirects the top level app after logout
                    account: instance.getActiveAccount()
                })
                .catch(error => console.log(error))
                .then(async () => {
                    setLoggedIn(await checkLoggedIn(instance));
                    setUsername((await getUsername(instance)) ?? "");
                });
        } else {
            appServicesLogout();
        }
    };

    // สำหรับ Avatar + Menu
    const handleAvatarClick = (event: React.MouseEvent<HTMLElement>) => {
        // if (!loggedIn) {
        // handleLoginPopup();
        // } else {
        setAnchorEl(event.currentTarget);
        // }
    };
    const handleCloseMenu = () => setAnchorEl(null);

    const handleLogout = () => {
        handleCloseMenu();
        handleLogoutPopup();
    };

    function stringToColor(string: string) {
        let hash = 0;
        let i;

        /* eslint-disable no-bitwise */
        for (i = 0; i < string.length; i += 1) {
            hash = string.charCodeAt(i) + ((hash << 5) - hash);
        }

        let color = "#";

        for (i = 0; i < 3; i += 1) {
            const value = (hash >> (i * 8)) & 0xff;
            color += `00${value.toString(16)}`.slice(-2);
        }
        /* eslint-enable no-bitwise */

        return color;
    }

    function stringAvatar(name: string) {
        let children = "?";
        if (name && name.trim().length > 0) {
            const parts = name.trim().split(" ");
            if (parts.length >= 2) {
                children = `${parts[0][0]}${parts[1][0]}`;
            } else {
                children = parts[0][0];
            }
        }
        return {
            sx: {
                bgcolor: stringToColor(name)
            },
            children // ใช้ตัวแปร children ที่เช็คไว้แล้ว
        };
    }

    return (
        // <DefaultButton
        //     text={loggedIn ? `${t("logout")}\n${username}` : `${t("login")}`}
        //     className={styles.loginButton}
        //     onClick={loggedIn ? handleLogoutPopup : handleLoginPopup}
        // ></DefaultButton>

        <>
            {!loggedIn ? (
                <Button variant="contained" color="primary" onClick={handleLoginPopup} className={styles.loginButton}>
                    {t("login")}
                </Button>
            ) : (
                <>
                    <IconButton onClick={handleAvatarClick} sx={{ p: 0 }}>
                        <Avatar {...stringAvatar(username)} />
                    </IconButton>
                    <Menu
                        anchorEl={anchorEl}
                        open={Boolean(anchorEl)}
                        onClose={handleCloseMenu}
                        anchorOrigin={{
                            vertical: "bottom",
                            horizontal: "right"
                        }}
                        transformOrigin={{
                            vertical: "top",
                            horizontal: "right"
                        }}
                    >
                        <Box sx={{ px: 2, py: 1 }}>
                            <Typography variant="subtitle1" fontWeight={600}>
                                {username || "Username"}
                            </Typography>
                            <Divider component="li" />
                            <Typography variant="body2" color="text.secondary">
                                Role: {"Administrator"}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Team: {"DIG"}
                            </Typography>
                        </Box>
                        <MenuItem onClick={handleLogout} sx={{ color: "#d32f2f" }}>
                            Logout
                        </MenuItem>
                    </Menu>
                </>
            )}
        </>
    );
};
