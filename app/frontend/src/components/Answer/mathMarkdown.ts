const LATEX_COMMAND = /\\(?:sqrt|frac|dfrac|tfrac|sum|prod|int|lim|sin|cos|tan|log|ln|exp|left|right|begin|end|mathbf|mathrm|text|overline|underline|vec|hat|bar|pm|mp|times|div|cdot|leq|geq|neq|approx|infty|alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega)\b/;
const BARE_LATEX_COMMAND = /\\(?:sqrt|frac|dfrac|tfrac|sum|prod|int|lim|sin|cos|tan|log|ln|exp|mathbf|mathrm|text|overline|underline|vec|hat|bar|pm|mp|times|div|cdot|leq|geq|neq|approx|infty|alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega)\b/g;
const LIST_PREFIX = /^(\s*(?:(?:[-*+] |\d+[.)] |[◦○•] ))?)(.*)$/;

const hasMathDelimiter = (value: string) => /(^|[^\\])\$/.test(value);

const isStandaloneFormula = (value: string) => {
    const withoutCommands = value.replace(/\\[A-Za-z]+/g, "");
    const residual = withoutCommands.replace(/[0-9A-Za-z\s{}()[\].,+\-*/^_=<>|:;!]+/g, "");
    return residual.length === 0;
};

const balancedEnd = (value: string, start: number, opening: string, closing: string) => {
    let depth = 0;
    for (let index = start; index < value.length; index += 1) {
        if (value[index] === opening) depth += 1;
        if (value[index] === closing) depth -= 1;
        if (depth === 0) return index + 1;
    }
    return null;
};

const wrapBareLatexCommands = (value: string) => {
    let result = "";
    let cursor = 0;
    BARE_LATEX_COMMAND.lastIndex = 0;

    for (let match = BARE_LATEX_COMMAND.exec(value); match; match = BARE_LATEX_COMMAND.exec(value)) {
        const start = match.index;
        let end = BARE_LATEX_COMMAND.lastIndex;

        if (value[end] === "[") {
            const optionalEnd = balancedEnd(value, end, "[", "]");
            if (optionalEnd === null) break;
            end = optionalEnd;
        }
        while (value[end] === "{") {
            const argumentEnd = balancedEnd(value, end, "{", "}");
            if (argumentEnd === null) return `${result}${value.slice(cursor)}`;
            end = argumentEnd;
        }

        result += `${value.slice(cursor, start)}$${value.slice(start, end)}$`;
        cursor = end;
        BARE_LATEX_COMMAND.lastIndex = end;
    }

    return `${result}${value.slice(cursor)}`;
};

const normalizeMathLine = (line: string) => {
    if (!LATEX_COMMAND.test(line) || hasMathDelimiter(line)) return line;

    const match = line.match(LIST_PREFIX);
    const prefix = match?.[1] ?? "";
    const content = match?.[2] ?? line;
    const trimmed = content.trim();

    if ((trimmed.startsWith("(") && trimmed.endsWith(")")) || isStandaloneFormula(trimmed)) {
        return `${prefix}$${trimmed}$`;
    }

    // Mixed prose remains prose; only parenthesized formula fragments are wrapped.
    const withParenthesizedMath = content.replace(/\(([^()\n]*\\[A-Za-z]+[^()\n]*)\)/g, "$($1)$");
    const withBareMath = withParenthesizedMath
        .split(/(\$[^$]*\$)/g)
        .map(part => (part.startsWith("$") ? part : wrapBareLatexCommands(part)))
        .join("");
    return `${prefix}${withBareMath}`;
};

/** Normalize common model-produced LaTeX without touching fenced code blocks. */
export const normalizeMathMarkdown = (source: string) => {
    const withStandardDelimiters = source
        .replace(/\\\[([\s\S]*?)\\\]/g, (_, formula: string) => `$$${formula}$$`)
        .replace(/\\\(([\s\S]*?)\\\)/g, (_, formula: string) => `$${formula}$`);

    let insideFence = false;
    return withStandardDelimiters
        .split("\n")
        .map(line => {
            if (/^\s*```/.test(line)) {
                insideFence = !insideFence;
                return line;
            }
            return insideFence ? line : normalizeMathLine(line);
        })
        .join("\n");
};
