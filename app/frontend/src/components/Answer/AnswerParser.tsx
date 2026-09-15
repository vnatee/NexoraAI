import { renderToStaticMarkup } from "react-dom/server";
import { ChatAppResponse, getCitationFilePath } from "../../api";

type HtmlParsedAnswer = {
    answerHtml: string;
    citations: string[];
};

// Function to validate citation format and check if dataPoint starts with possible citation
function isCitationValid(contextDataPoints: any, citationCandidate: string): boolean {
    const regex = /^(?:[^/#?]+\.[^/\s#?]+|.+\/[^/#?]+(?:\.[^/\s#?]+)?\/?)(?:\?\S*)?(?:#\S*)?$/u;

    if (!regex.test(citationCandidate)) {
        return false;
    }

    // Check if contextDataPoints is an object with a text property that is an array
    let dataPointsArray: string[];
    if (Array.isArray(contextDataPoints)) {
        dataPointsArray = contextDataPoints;
    } else if (contextDataPoints && Array.isArray(contextDataPoints.text)) {
        dataPointsArray = contextDataPoints.text;
    } else {
        return false;
    }

    // ── Pass 1: exact prefix match (filename + page ตรงกัน) ──────────────
    if (dataPointsArray.some(dataPoint => dataPoint.startsWith(citationCandidate))) {
        return true;
    }

    // ── Pass 2: filename-only match (ตัด #page= ออก) ─────────────────────
    // LLM อาจเขียน page number ผิด แต่ filename ถูก → ยังถือว่า valid
    const filenamePart = citationCandidate.split("#")[0].split("?")[0];
    if (filenamePart && dataPointsArray.some(dataPoint => dataPoint.startsWith(filenamePart))) {
        return true;
    }

    return false;
}

export function parseAnswerToHtml(answer: ChatAppResponse, isStreaming: boolean, onCitationClicked: (citationFilePath: string) => void): HtmlParsedAnswer {
    const contextDataPoints = answer.context.data_points;
    const citations: string[] = [];

    // Trim any whitespace from the end of the answer after removing follow-up questions
    let parsedAnswer = answer.message.content.trim();

    // ── Pre-process: แปลง plain-text citation เป็น [bracket] format ──────────
    // LLM บางครั้งเขียน "ข้อมูลอ้างอิงจาก file.pdf#page=1" หรือ "จาก file.pdf" แทน [file.pdf#page=1]
    parsedAnswer = parsedAnswer.replace(
        /(?:ข้อมูลอ้างอิงจาก|ข้อมูลอ้างอิง\s*:|อ้างอิงจาก|อ้างอิง\s*:|ที่มา\s*:|Source\s*:|from)\s+([^\s[\]]+\.(?:pdf|docx?|xlsx?|txt|csv|md)(?:#\S*)?)/gi,
        (_, filename) => `[${filename}]`
    );

    // Omit a citation that is still being typed during streaming
    if (isStreaming) {
        let lastIndex = parsedAnswer.length;
        for (let i = parsedAnswer.length - 1; i >= 0; i--) {
            if (parsedAnswer[i] === "]") {
                break;
            } else if (parsedAnswer[i] === "[") {
                lastIndex = i;
                break;
            }
        }
        const truncatedAnswer = parsedAnswer.substring(0, lastIndex);
        parsedAnswer = truncatedAnswer;
    }

    const parts = parsedAnswer.split(/\[([^\]]+)\]/g);

    const fragments: string[] = parts.map((part, index) => {
        if (index % 2 === 0) {
            return part;
        } else {
            let citationIndex: number;

            if (!isCitationValid(contextDataPoints, part)) {
                return `[${part}]`;
            }

            if (citations.indexOf(part) !== -1) {
                citationIndex = citations.indexOf(part) + 1;
            } else {
                citations.push(part);
                citationIndex = citations.length;
            }

            const path = getCitationFilePath(part);

            return renderToStaticMarkup(
                <a className="supContainer" title={part} onClick={() => onCitationClicked(path)}>
                    <sup>{citationIndex}</sup>
                </a>
            );
        }
    });

    return {
        answerHtml: fragments.join(""),
        citations
    };
}
