from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

GuardrailAction = Literal["allow", "warn", "block", "redact"]


class GuardrailViolation(ValueError):
    def __init__(self, message: str, *, category: str, detector_ids: tuple[str, ...]):
        super().__init__(message)
        self.category = category
        self.detector_ids = detector_ids


@dataclass(frozen=True)
class GuardrailPolicy:
    enabled: bool = True
    max_input_chars: int = 20_000
    prompt_injection_action: GuardrailAction = "block"
    sensitive_input_action: GuardrailAction = "block"
    sensitive_output_action: GuardrailAction = "redact"
    pii_input_action: GuardrailAction = "block"
    pii_output_action: GuardrailAction = "redact"
    content_safety_input_action: GuardrailAction = "block"
    content_safety_output_action: GuardrailAction = "block"
    blocked_phrases: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, value: object) -> GuardrailPolicy:
        config = value if isinstance(value, dict) else {}
        return cls(
            enabled=config.get("enabled", True) is not False,
            max_input_chars=max(256, min(int(config.get("max_input_chars") or 20_000), 200_000)),
            prompt_injection_action=_action(
                config.get("prompt_injection_action"), {"allow", "warn", "block"}, "block"
            ),
            sensitive_input_action=_action(
                config.get("sensitive_input_action"), {"allow", "warn", "block"}, "block"
            ),
            sensitive_output_action=_action(
                config.get("sensitive_output_action"), {"allow", "warn", "block", "redact"}, "redact"
            ),
            pii_input_action=_action(
                config.get("pii_input_action"), {"allow", "warn", "block"}, "block"
            ),
            pii_output_action=_action(
                config.get("pii_output_action"), {"allow", "warn", "block", "redact"}, "redact"
            ),
            content_safety_input_action=_action(
                config.get("content_safety_input_action"), {"allow", "warn", "block"}, "block"
            ),
            content_safety_output_action=_action(
                config.get("content_safety_output_action"), {"allow", "warn", "block"}, "block"
            ),
            blocked_phrases=_phrases(config.get("blocked_phrases")),
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_input_chars": self.max_input_chars,
            "prompt_injection_action": self.prompt_injection_action,
            "sensitive_input_action": self.sensitive_input_action,
            "sensitive_output_action": self.sensitive_output_action,
            "pii_input_action": self.pii_input_action,
            "pii_output_action": self.pii_output_action,
            "content_safety_input_action": self.content_safety_input_action,
            "content_safety_output_action": self.content_safety_output_action,
            "blocked_phrases": list(self.blocked_phrases),
        }


@dataclass(frozen=True)
class GuardrailFinding:
    category: str
    detector_id: str


@dataclass(frozen=True)
class GuardrailResult:
    text: str
    findings: tuple[GuardrailFinding, ...] = ()
    blocked: bool = False
    redacted: bool = False

    def audit_details(self, *, direction: str) -> dict[str, Any]:
        categories = sorted({finding.category for finding in self.findings})
        detector_ids = sorted({finding.detector_id for finding in self.findings})
        return {
            "direction": direction,
            "categories": categories,
            "detector_ids": detector_ids,
            "finding_count": len(self.findings),
            "blocked": self.blocked,
            "redacted": self.redacted,
        }


_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(
            r"\b(?:ignore|disregard|override|forget)\s+(?:all\s+)?(?:previous|prior|system|developer)\s+(?:instructions?|prompts?|rules?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_hidden_prompt",
        re.compile(
            r"\b(?:reveal|show|print|repeat|extract|leak)\s+(?:the\s+)?(?:hidden\s+|original\s+|full\s+)?(?:system|developer)\s+(?:prompt|message|instructions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(?:act|behave|respond)\s+as\s+(?:if\s+you\s+(?:have|had)\s+no|an?\s+unrestricted)\s+(?:rules?|policy|assistant|model)\b",
            re.IGNORECASE,
        ),
    ),
)

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
    ),
    (
        "credential_assignment",
        re.compile(
            r"\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{12,}",
            re.IGNORECASE,
        ),
    ),
)

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    (
        "thai_phone_number",
        re.compile(r"(?<!\d)(?:\+66|0)(?:\s*[-.]?\s*\d){8,9}(?!\d)"),
    ),
    (
        "us_social_security_number",
        re.compile(r"(?<!\d)(?!000|666|9\d\d)\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}(?!\d)"),
    ),
)

_CONTENT_SAFETY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "credible_violence_instruction",
        re.compile(
            r"\b(?:how\s+to|instructions?\s+(?:to|for)|steps?\s+(?:to|for))\s+"
            r"(?:kill|murder|poison|bomb|shoot)\s+(?:a\s+|an\s+|the\s+)?(?:person|people|someone|crowd|school)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "self_harm_instruction",
        re.compile(
            r"\b(?:best|easiest|fastest|painless)\s+(?:way|method)\s+to\s+"
            r"(?:kill\s+myself|commit\s+suicide|self[- ]?harm)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "sexual_content_involving_minors",
        re.compile(
            r"\b(?:create|generate|write|show)\b.{0,40}\b(?:sexual|explicit|nude)\b.{0,40}"
            r"\b(?:child|minor|underage|เด็ก)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "thai_credible_violence_instruction",
        re.compile(r"(?:วิธี|ขั้นตอน|สอน).{0,20}(?:ฆ่า|วางยา|ทำระเบิด|ยิง).{0,20}(?:คน|ผู้อื่น|โรงเรียน)"),
    ),
    (
        "thai_self_harm_instruction",
        re.compile(r"(?:วิธี|ขั้นตอน|แบบไหน).{0,20}(?:ฆ่าตัวตาย|ทำร้ายตัวเอง).{0,20}(?:ง่าย|เร็ว|ไม่เจ็บ)?"),
    ),
)

_PII_REQUEST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "request_personal_identifier_en",
        re.compile(
            r"\b(?:show|reveal|give|find|tell|provide|what\s+is|list)\b.{0,80}"
            r"\b(?:social\s+security(?:\s+number)?|ssn|national\s+id|passport\s+number|"
            r"credit\s+card\s+number|bank\s+account|password|api\s+key)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "request_personal_identifier_th",
        re.compile(
            r"(?:ขอ|บอก|หา|แสดง|เปิดเผย|ดู|ทราบ|เลข).{0,60}"
            r"(?:เลขบัตรประชาชน|เลขประจำตัวประชาชน|เลขหนังสือเดินทาง|เลขบัตรเครดิต|"
            r"เลขบัญชี|รหัสผ่าน|เอพีไอคีย์|api\s*key).{0,24}(?:อะไร|คืออะไร|เท่าไหร่|ของ|ให้หน่อย)?",
            re.IGNORECASE,
        ),
    ),
    (
        "request_personal_identifier_th_suffix",
        re.compile(
            r"(?:ของ\s*\S+|\S+\s+)(?:เลขบัตรประชาชน|เลขประจำตัวประชาชน|เลขหนังสือเดินทาง|เลขบัตรเครดิต|"
            r"เลขบัญชี|รหัสผ่าน|เอพีไอคีย์|api\s*key)\s*(?:อะไร|คืออะไร|เท่าไหร่|ของใคร|ให้หน่อย)",
            re.IGNORECASE,
        ),
    ),
)


def _action(value: object, allowed: set[str], default: str) -> GuardrailAction:
    normalized = str(value or default).strip().lower()
    if normalized not in allowed:
        raise ValueError(f"Unsupported guardrail action '{normalized}'")
    return normalized  # type: ignore[return-value]


def _phrases(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("Guardrail blocked_phrases must be an array")
    phrases: list[str] = []
    for item in value[:100]:
        phrase = str(item or "").strip()
        if not phrase:
            continue
        if len(phrase) > 200:
            raise ValueError("Each guardrail blocked phrase must be 200 characters or fewer")
        if phrase.casefold() not in {existing.casefold() for existing in phrases}:
            phrases.append(phrase)
    return tuple(phrases)


def merge_guardrail_policies(*policies: GuardrailPolicy | None) -> GuardrailPolicy:
    """Merge active System → Team → Agent policies using the strictest value."""
    active = [policy for policy in policies if policy is not None and policy.enabled]
    if not active:
        fallback = next((policy for policy in reversed(policies) if policy is not None), None)
        return fallback or GuardrailPolicy(enabled=False)

    input_rank = {"allow": 0, "warn": 1, "block": 2}
    output_rank = {"allow": 0, "warn": 1, "redact": 2, "block": 3}

    def strictest(field: str, ranking: dict[str, int]) -> GuardrailAction:
        return max(
            (getattr(policy, field) for policy in active),
            key=lambda action: ranking[action],
        )

    phrases: list[str] = []
    for policy in active:
        for phrase in policy.blocked_phrases:
            if phrase.casefold() not in {item.casefold() for item in phrases}:
                phrases.append(phrase)

    return GuardrailPolicy(
        enabled=True,
        max_input_chars=min(policy.max_input_chars for policy in active),
        prompt_injection_action=strictest("prompt_injection_action", input_rank),
        sensitive_input_action=strictest("sensitive_input_action", input_rank),
        sensitive_output_action=strictest("sensitive_output_action", output_rank),
        pii_input_action=strictest("pii_input_action", input_rank),
        pii_output_action=strictest("pii_output_action", output_rank),
        content_safety_input_action=strictest("content_safety_input_action", input_rank),
        content_safety_output_action=strictest("content_safety_output_action", input_rank),
        blocked_phrases=tuple(phrases),
    )


def _find(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...], category: str) -> list[GuardrailFinding]:
    return [
        GuardrailFinding(category=category, detector_id=detector_id)
        for detector_id, pattern in patterns
        if pattern.search(text)
    ]


def _secret_findings(text: str) -> list[GuardrailFinding]:
    return _find(text, _SECRET_PATTERNS, "sensitive_data")


def _pii_findings(text: str) -> list[GuardrailFinding]:
    findings = _find(text, _PII_PATTERNS, "pii")
    for candidate in re.findall(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)", text):
        digits = re.sub(r"\D", "", candidate)
        if len(digits) == 13 and _valid_thai_national_id(digits):
            findings.append(GuardrailFinding(category="pii", detector_id="thai_national_id"))
        elif 13 <= len(digits) <= 19 and _valid_luhn(digits):
            findings.append(GuardrailFinding(category="pii", detector_id="payment_card_number"))
    return findings


def _valid_luhn(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        value = int(character)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _valid_thai_national_id(digits: str) -> bool:
    if len(digits) != 13 or digits == digits[0] * 13:
        return False
    checksum = sum(int(digits[index]) * (13 - index) for index in range(12))
    return (11 - checksum % 11) % 10 == int(digits[-1])


def _redact_secrets(text: str) -> str:
    redacted = text
    for _, pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED:SECRET]", redacted)
    return redacted


def _redact_pii(text: str) -> str:
    redacted = text
    for _, pattern in _PII_PATTERNS:
        redacted = pattern.sub("[REDACTED:PII]", redacted)
    return re.sub(
        r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)",
        lambda match: "[REDACTED:PII]"
        if (
            (len(digits := re.sub(r"\D", "", match.group(0))) == 13 and _valid_thai_national_id(digits))
            or (13 <= len(digits) <= 19 and _valid_luhn(digits))
        )
        else match.group(0),
        redacted,
    )


def latest_user_text(messages: object) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
    return ""


def evaluate_input(messages: object, policy: GuardrailPolicy) -> GuardrailResult:
    if not policy.enabled:
        return GuardrailResult(text=latest_user_text(messages))
    text = latest_user_text(messages)
    if len(text) > policy.max_input_chars:
        finding = GuardrailFinding(category="request_size", detector_id="max_input_chars")
        return GuardrailResult(text=text, findings=(finding,), blocked=True)

    findings: list[GuardrailFinding] = []
    injection = _find(text, _INJECTION_PATTERNS, "prompt_injection")
    secrets = _secret_findings(text)
    pii = _pii_findings(text)
    pii_requests = _find(text, _PII_REQUEST_PATTERNS, "pii_request")
    unsafe_content = _find(text, _CONTENT_SAFETY_PATTERNS, "content_safety")
    blocked_phrases = [
        GuardrailFinding(category="blocked_topic", detector_id="configured_phrase")
        for phrase in policy.blocked_phrases
        if phrase.casefold() in text.casefold()
    ]
    findings.extend(injection)
    findings.extend(secrets)
    findings.extend(pii)
    findings.extend(pii_requests)
    findings.extend(unsafe_content)
    findings.extend(blocked_phrases)
    blocked = bool(blocked_phrases)
    blocked = blocked or bool(injection and policy.prompt_injection_action == "block")
    blocked = blocked or bool(secrets and policy.sensitive_input_action == "block")
    blocked = blocked or bool((pii or pii_requests) and policy.pii_input_action == "block")
    blocked = blocked or bool(
        unsafe_content and policy.content_safety_input_action == "block"
    )
    return GuardrailResult(text=text, findings=tuple(findings), blocked=blocked)


def evaluate_output(text: str, policy: GuardrailPolicy) -> GuardrailResult:
    if not policy.enabled:
        return GuardrailResult(text=text)
    secrets = _secret_findings(text)
    pii = _pii_findings(text)
    unsafe_content = _find(text, _CONTENT_SAFETY_PATTERNS, "content_safety")
    findings = [*secrets, *pii, *unsafe_content]
    if not findings:
        return GuardrailResult(text=text)
    should_block = bool(secrets and policy.sensitive_output_action == "block")
    should_block = should_block or bool(pii and policy.pii_output_action == "block")
    should_block = should_block or bool(
        unsafe_content and policy.content_safety_output_action == "block"
    )
    if should_block:
        return GuardrailResult(text=text, findings=tuple(findings), blocked=True)
    redacted = text
    if secrets and policy.sensitive_output_action == "redact":
        redacted = _redact_secrets(redacted)
    if pii and policy.pii_output_action == "redact":
        redacted = _redact_pii(redacted)
    if redacted != text:
        return GuardrailResult(
            text=redacted,
            findings=tuple(findings),
            redacted=True,
        )
    return GuardrailResult(text=text, findings=tuple(findings))


def sanitize_untrusted_context(text: str, policy: GuardrailPolicy) -> GuardrailResult:
    """Neutralize high-confidence instruction injection in retrieved/uploaded text."""
    if not policy.enabled:
        return GuardrailResult(text=text)
    findings = _find(text, _INJECTION_PATTERNS, "retrieval_prompt_injection")
    sanitized = text
    for _, pattern in _INJECTION_PATTERNS:
        sanitized = pattern.sub("[REMOVED POTENTIAL INSTRUCTION]", sanitized)
    return GuardrailResult(
        text=sanitized,
        findings=tuple(findings),
        redacted=sanitized != text,
    )


def blocked_message(result: GuardrailResult, *, direction: str) -> str:
    categories = {finding.category for finding in result.findings}
    if "request_size" in categories:
        return "Your message is longer than this Agent's allowed input limit. Please shorten it and try again."
    if direction == "output":
        return "The response was blocked because it may contain sensitive information."
    if "sensitive_data" in categories:
        return "Your message may contain a credential or secret. Remove sensitive values and try again."
    if "pii" in categories or "pii_request" in categories:
        return "Your message may contain personal or regulated data that this Agent is not allowed to process."
    if "content_safety" in categories:
        return "This request was blocked by the Agent's content-safety policy."
    if "blocked_topic" in categories:
        return "This request is blocked by the Agent's configured guardrail policy."
    return "This request was blocked because it may attempt to override the Agent's safety instructions."
