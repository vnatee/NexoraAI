import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Button,
    Chip,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import FileDownloadIcon from "@mui/icons-material/FileDownload";

import { ChartDataAudit } from "../../api/models";

interface ChartDataPanelProps {
    data?: ChartDataAudit;
}

function csvCell(value: unknown): string {
    let text = value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
    // Prevent spreadsheet formula injection when an exported value is opened in Excel/Sheets.
    if (/^[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
}

export function ChartDataPanel({ data }: ChartDataPanelProps) {
    if (!data?.columns?.length || !data.rows?.length) return null;

    const downloadCsv = () => {
        const lines = [
            data.columns.map(csvCell).join(","),
            ...data.rows.map(row => data.columns.map(column => csvCell(row[column])).join(","))
        ];
        const blob = new Blob(["\uFEFF", lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `chart-data-${Date.now()}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    };

    const renderedQuery = typeof data.query === "string" ? data.query : data.query ? JSON.stringify(data.query, null, 2) : "";

    return (
        <Accordion disableGutters variant="outlined" sx={{ mt: 1, borderRadius: 2, "&:before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="body2" fontWeight={600}>Chart data</Typography>
                    <Chip size="small" variant="outlined" label={`${data.rowCount} rows`} />
                    <Chip size="small" variant="outlined" label={data.sourceTool} />
                    {data.fullDataset === true && (
                        <Chip size="small" color="success" variant="outlined" label="Full dataset statistics" />
                    )}
                    {data.resultTruncated && (
                        <Chip size="small" color="warning" variant="outlined" label="Displayed groups truncated" />
                    )}
                </Stack>
            </AccordionSummary>
            <AccordionDetails>
                <Stack spacing={1.5}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" gap={1}>
                        <Typography variant="caption" color="text.secondary">
                            Source: {data.sourceType} · Category: {data.categoryField} · Values: {data.valueFields.join(", ")}
                        </Typography>
                        <Button size="small" startIcon={<FileDownloadIcon />} onClick={downloadCsv}>Download CSV</Button>
                    </Box>
                    {data.aggregation && (
                        <Typography variant="caption" color="text.secondary">
                            Aggregation: {data.aggregation.method ?? data.aggregation.aggregation ?? data.aggregation.type}
                            {data.sourceRecordCount != null ? ` · ${data.sourceRecordCount} source records analyzed` : ""}
                            {data.aggregateRowCount != null ? ` · ${data.aggregateRowCount} aggregate groups` : ""}
                        </Typography>
                    )}
                    {renderedQuery && (
                        <Box component="details">
                            <Typography component="summary" variant="caption" sx={{ cursor: "pointer", fontWeight: 600 }}>
                                Source query
                            </Typography>
                            <Box component="pre" sx={{ m: 0, mt: 1, p: 1.5, bgcolor: "grey.100", borderRadius: 1, overflowX: "auto", fontSize: 12 }}>
                                {renderedQuery}
                            </Box>
                        </Box>
                    )}
                    <TableContainer sx={{ maxHeight: 320, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                        <Table size="small" stickyHeader aria-label="Chart source data">
                            <TableHead>
                                <TableRow>
                                    {data.columns.map(column => <TableCell key={column} sx={{ fontWeight: 600 }}>{column}</TableCell>)}
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {data.rows.map((row, index) => (
                                    <TableRow key={index} hover>
                                        {data.columns.map(column => <TableCell key={column}>{String(row[column] ?? "")}</TableCell>)}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    {data.sourceRowCount > data.rowCount && (
                        <Typography variant="caption" color="text.secondary">
                            Showing {data.rowCount} of {data.sourceRowCount} source rows.
                        </Typography>
                    )}
                    {data.resultTruncated && (
                        <Typography variant="caption" color="warning.main">
                            Statistics use the full filtered dataset, but only the first {data.rowCount} aggregate groups are displayed.
                        </Typography>
                    )}
                </Stack>
            </AccordionDetails>
        </Accordion>
    );
}
