import LinkIcon from "@mui/icons-material/Link";
import ApiIcon from "@mui/icons-material/Api";
import StorageIcon from "@mui/icons-material/Storage";
import ChatIcon from "@mui/icons-material/Chat";
import TableChartIcon from "@mui/icons-material/TableChart";
import BarChartIcon from "@mui/icons-material/BarChart";

export function getIntegrationIcon(type?: string): JSX.Element {
    switch (type) {
        case "rest":
            return <ApiIcon fontSize="small" />;

        case "database":
            return <StorageIcon fontSize="small" />;

        case "line":
            return <ChatIcon fontSize="small" />;

        case "google_sheet":
            return <TableChartIcon fontSize="small" />;

        case "chart": // ⭐ CHART CAPABILITY
            return <BarChartIcon fontSize="small" />;

        default:
            return <ApiIcon fontSize="small" />;
    }
}
