from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


QUOTA_DIMENSIONS = {"provider", "profile"}
QUOTA_WORKLOADS = {"all", "chat", "ask"}


@dataclass(frozen=True)
class LLMTokenQuotaRule:
    dimension: str
    target_id: str
    target_label: str
    monthly_tokens: int
    workload: str = "all"
    enabled: bool = True

    @classmethod
    def from_config(cls, value: object) -> "LLMTokenQuotaRule":
        data = value if isinstance(value, dict) else {}
        dimension = str(data.get("dimension") or "").strip().lower()
        target_id = str(data.get("target_id") or "").strip()
        workload = str(data.get("workload") or "all").strip().lower()
        if dimension not in QUOTA_DIMENSIONS:
            raise ValueError("LLM token rule dimension must be provider or profile")
        if not target_id or len(target_id) > 200:
            raise ValueError("LLM token rule target_id is required and must not exceed 200 characters")
        if workload not in QUOTA_WORKLOADS:
            raise ValueError("LLM token rule workload must be all, chat, or ask")
        try:
            monthly_tokens = int(data.get("monthly_tokens") or 0)
        except (TypeError, ValueError) as error:
            raise ValueError("LLM token rule monthly_tokens must be an integer") from error
        if monthly_tokens < 0:
            raise ValueError("LLM token rule monthly_tokens must be zero or greater")
        return cls(
            dimension=dimension,
            target_id=target_id,
            target_label=str(data.get("target_label") or target_id).strip()[:200],
            monthly_tokens=monthly_tokens,
            workload=workload,
            enabled=data.get("enabled") is not False,
        )

    @property
    def key(self) -> tuple[str, str, str]:
        return self.dimension, self.target_id, self.workload

    def serialize(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "target_id": self.target_id,
            "target_label": self.target_label,
            "monthly_tokens": self.monthly_tokens,
            "workload": self.workload,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class UsageQuotaPolicy:
    enabled: bool = False
    monthly_llm_tokens: int = 0
    monthly_document_pages: int = 0
    llm_requests_per_minute: int = 0
    monthly_llm_tokens_per_user: int = 0
    llm_token_rules: tuple[LLMTokenQuotaRule, ...] = ()

    @classmethod
    def from_config(cls, value: object) -> "UsageQuotaPolicy":
        data = value if isinstance(value, dict) else {}

        def limit(name: str) -> int:
            try:
                result = int(data.get(name) or 0)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{name} must be an integer") from error
            if result < 0:
                raise ValueError(f"{name} must be zero or greater")
            return result

        rules_value = data.get("llm_token_rules") or []
        if not isinstance(rules_value, list):
            raise ValueError("llm_token_rules must be an array")
        rules = tuple(LLMTokenQuotaRule.from_config(item) for item in rules_value[:200])
        keys = [rule.key for rule in rules]
        if len(keys) != len(set(keys)):
            raise ValueError("Only one LLM token rule is allowed per target and workload")

        return cls(
            enabled=data.get("enabled") is True,
            monthly_llm_tokens=limit("monthly_llm_tokens"),
            monthly_llm_tokens_per_user=limit("monthly_llm_tokens_per_user"),
            monthly_document_pages=limit("monthly_document_pages"),
            llm_requests_per_minute=limit("llm_requests_per_minute"),
            llm_token_rules=rules,
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "monthly_llm_tokens": self.monthly_llm_tokens,
            "monthly_llm_tokens_per_user": self.monthly_llm_tokens_per_user,
            "monthly_document_pages": self.monthly_document_pages,
            "llm_requests_per_minute": self.llm_requests_per_minute,
            "llm_token_rules": [rule.serialize() for rule in self.llm_token_rules],
        }


def effective_quota_policy(*policies: UsageQuotaPolicy | None) -> UsageQuotaPolicy:
    enabled = [policy for policy in policies if policy and policy.enabled]
    if not enabled:
        return UsageQuotaPolicy()

    def strictest(field: str) -> int:
        values = [int(getattr(policy, field)) for policy in enabled if int(getattr(policy, field)) > 0]
        return min(values) if values else 0

    strictest_rules: dict[tuple[str, str, str], LLMTokenQuotaRule] = {}
    for policy in enabled:
        for rule in policy.llm_token_rules:
            if not rule.enabled or not rule.monthly_tokens:
                continue
            existing = strictest_rules.get(rule.key)
            if existing is None or rule.monthly_tokens < existing.monthly_tokens:
                strictest_rules[rule.key] = rule

    return UsageQuotaPolicy(
        enabled=True,
        monthly_llm_tokens=strictest("monthly_llm_tokens"),
        monthly_llm_tokens_per_user=strictest("monthly_llm_tokens_per_user"),
        monthly_document_pages=strictest("monthly_document_pages"),
        llm_requests_per_minute=strictest("llm_requests_per_minute"),
        llm_token_rules=tuple(strictest_rules.values()),
    )
