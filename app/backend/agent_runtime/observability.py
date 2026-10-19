from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from core.observability import current_trace_identifiers
from mongo_table_connecters.agent_audit import insert_agent_audit_event


class AuditTrail:
    """Best-effort structured audit trail. Audit persistence never breaks an agent run."""

    def __init__(
        self,
        *,
        agent_id: str,
        auth_claims: dict[str, Any],
        team_id: str | None,
        run_id: str | None = None,
        parent_run_id: str | None = None,
    ):
        self.agent_id = agent_id
        self.team_id = team_id
        self.run_id = run_id or str(uuid.uuid4())
        self.parent_run_id = parent_run_id
        self.actor_id = str(
            auth_claims.get("oid")
            or auth_claims.get("sub")
            or auth_claims.get("preferred_username")
            or "unknown"
        )
        self.events: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        *,
        status: str = "ok",
        tool_name: str | None = None,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "_id": str(uuid.uuid4()),
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "agent_id": self.agent_id,
            "team_id": self.team_id,
            "actor_id": self.actor_id,
            "event_type": str(event_type),
            "status": str(status),
            "tool_name": tool_name,
            "source": source,
            "details": details or {},
            "created_at": datetime.now(timezone.utc),
        }
        trace_ids = current_trace_identifiers()
        if trace_ids:
            event.update(trace_ids)
        self.events.append(event)
        if os.getenv("DISABLE_AGENT_AUDIT_PERSISTENCE", "").lower() != "true":
            try:
                insert_agent_audit_event(event)
            except Exception:
                logging.exception("Unable to persist agent audit event %s", event_type)
        return event

    def public_summary(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "event_count": len(self.events)}
