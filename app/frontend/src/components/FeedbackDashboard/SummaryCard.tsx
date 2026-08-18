import { Card, CardContent, Typography } from "@mui/material";

const SummaryCard = ({ count }: { count: number }) => (
    <Card
        sx={{
            p: 3,
            background: "#1976d2",
            color: "white",
            borderRadius: 3,
            boxShadow: 3
        }}
    >
        <CardContent>
            <Typography variant="h6" sx={{ opacity: 0.9 }}>
                Total Feedback
            </Typography>
            <Typography variant="h2" fontWeight="bold">
                {count}
            </Typography>
        </CardContent>
    </Card>
);

export default SummaryCard;
