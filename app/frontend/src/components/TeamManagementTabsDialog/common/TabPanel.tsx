import { Box } from "@mui/material";

interface Props {
    value: number;
    index: number;
    children: React.ReactNode;
}

export function TabPanel({ value, index, children }: Props) {
    return (
        <Box
            hidden={value !== index}
            sx={{
                height: "100%",
                p: 3,
                overflowY: "auto"
            }}
        >
            {value === index && children}
        </Box>
    );
}
