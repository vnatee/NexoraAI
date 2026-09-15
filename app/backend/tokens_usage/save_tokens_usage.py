import json
from collections import defaultdict
import uuid
from datetime import datetime, timezone
from mongo_table_connecters.mongo_connector import get_database
from mongo_table_connecters.users import get_user_by_ad_email
from mongo_table_connecters.teams import get_team_by_id
import re

db = get_database()
usage_collection = db["users_usage"]
group_collection = db["groups"]
user_collection = db["users"]

def is_citation_valid(citation_candidate: str) -> bool:
    regex = re.compile(
        r'^(?:[^\/#?]+\.[^\/\s#?]+|.+\/[^\/#?]+(?:\.[^\/\s#?]+)?\/?)(?:\?\S*)?(?:#\S*)?$',
        re.UNICODE
    )
    
    if not regex.match(citation_candidate):
        return False
    return True

def iter_events_from_response_text(data_str: str):
    s = data_str.strip()
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
            if line == "[DONE]":
                break
        if not line or line == "[DONE]":
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            # ข้ามบรรทัดที่ไม่ใช่ JSON สมบูรณ์
            continue

def extract_token_usage(obj: dict):
    per_stage = []
    totals = defaultdict(int)

    ctx = obj.get("context", {})
    thoughts = ctx.get("thoughts", []) or []

    for th in thoughts:
        title = th.get("title")
        props = th.get("props") or {}
        tu = props.get("token_usage")
        if not tu:
            continue
        # บางระบบไม่มี reasoning_tokens
        prompt = int(tu.get("prompt_tokens", 0) or 0)
        completion = int(tu.get("completion_tokens", 0) or 0)
        reasoning = int(tu.get("reasoning_tokens", 0) or 0)
        total = int(tu.get("total_tokens", prompt + completion + reasoning))

        per_stage.append({
            "title": title,
            "model": props.get("model"),
            "deployment": props.get("deployment"),
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "reasoning_tokens": reasoning,
            "total_tokens": total,
        })

        totals["prompt_tokens_sum"] += prompt
        totals["completion_tokens_sum"] += completion
        totals["reasoning_tokens_sum"] += reasoning
        totals["total_tokens_sum"] += total

    return per_stage, dict(totals)

def summarize_turn(data_str: str):
    per_stage_all = []
    sums = defaultdict(int)
    session_state = None
    gpt_response_text = ""
    for event in iter_events_from_response_text(data_str):
        if session_state is None:
            session_state = event.get("session_state")
        if "delta" in event and "context" not in event:
            gpt_response_text = f"{gpt_response_text}{event['delta']['content']}"
        per_stage, totals = extract_token_usage(event)
        per_stage_all.extend(per_stage)
        for k, v in totals.items():
            sums[k] += v
    matches = re.findall(r"\[([^\[\]]+)\]", gpt_response_text)
    seen = set()
    unique = []
    for m in matches:
        final_m = str(m)
        if "#" in final_m:
            final_m = final_m.split("#")[0]
        if final_m not in seen and is_citation_valid(final_m):
            unique.append(final_m)
            seen.add(final_m)
    result = {
        "session_state": session_state,
        "tokens_prompt_sum": sums.get("prompt_tokens_sum", 0),
        "tokens_completion_sum": sums.get("completion_tokens_sum", 0),
        "tokens_reasoning_sum": sums.get("reasoning_tokens_sum", 0),
        "tokens_total_sum": sums.get("total_tokens_sum", 0),
        "model_calls": per_stage_all,
        "files": unique
    }
    return result

def summarize_turn_for_ask(data_str: str):
    per_stage_all = []
    gpt_response_text = data_str['message']['content']
    matches = re.findall(r"\[([^\[\]]+)\]", gpt_response_text)
    seen = set()
    unique = []
    for m in matches:
        final_m = str(m)
        if "#" in final_m:
            final_m = final_m.split("#")[0]
        if final_m not in seen and is_citation_valid(final_m):
            unique.append(final_m)
            seen.add(final_m)
    tokens = None
    for th in data_str["context"].thoughts:
        if th.props:
            if 'token_usage' in th.props:
                tokens = th.props['token_usage']
                break
    result = {
        "tokens_prompt_sum": int(tokens.prompt_tokens),
        "tokens_completion_sum": int(tokens.completion_tokens),
        "tokens_reasoning_sum": int(tokens.reasoning_tokens),
        "tokens_total_sum": int(tokens.total_tokens),
        "model_calls": per_stage_all,
        "files": unique
    }
    return result

def insert_user_usage(auth_claims, response, mode="chat", metadata=None):
    if mode == "chat":
        tokens = summarize_turn(response)
    else:
        tokens = summarize_turn_for_ask(response)
    username = str(
        auth_claims.get("preferred_username")
        or auth_claims.get("email")
        or auth_claims.get("upn")
        or ""
    )
    application_user = get_user_by_ad_email(username) if username else None
    display_name = " ".join(
        str((application_user or {}).get(field) or "").strip()
        for field in ("first_name", "last_name")
    ).strip() or username
    team_id = str(auth_claims.get("team_id") or "").strip()
    team = get_team_by_id(team_id) if team_id else None
    metadata = metadata if isinstance(metadata, dict) else {}
    model_calls = []
    for call in tokens.get("model_calls") or []:
        if not isinstance(call, dict):
            continue
        model_calls.append({
            "stage": str(call.get("title") or "")[:100],
            "model": str(call.get("model") or metadata.get("model") or "unknown")[:200],
            "deployment": str(call.get("deployment") or metadata.get("deployment") or "")[:200],
            "provider": str(metadata.get("provider") or "unknown")[:100],
            "provider_id": str(metadata.get("provider_id") or "")[:200],
            "prompt_tokens": max(0, int(call.get("prompt_tokens") or 0)),
            "completion_tokens": max(0, int(call.get("completion_tokens") or 0)),
            "reasoning_tokens": max(0, int(call.get("reasoning_tokens") or 0)),
            "total_tokens": max(0, int(call.get("total_tokens") or 0)),
        })
    usage_event_id = str(metadata.get("usage_event_id") or uuid.uuid4())[:100]
    usage_data = {
        "_id": usage_event_id,
        "schema_version": 3,
        "create_at": datetime.now(timezone.utc),
        "update_at": datetime.now(timezone.utc),
        "delete_at": None,
        "user": {
            "_id": str(auth_claims.get("application_user_id") or (application_user or {}).get("_id") or ""),
            "name": display_name,
        },
        "group": (
            {"_id": team_id, "name": str(team.get("name") or team_id)}
            if team
            else None
        ),
        "tokens_prompt_sum": tokens["tokens_prompt_sum"],             
        "tokens_completion_sum": tokens["tokens_completion_sum"],
        "tokens_reasoning_sum": tokens.get("tokens_reasoning_sum", 0),
        "tokens_total_sum": tokens["tokens_total_sum"],
        "reference_files": tokens["files"],
        "model_calls": model_calls,
        "metadata": {
            "agent_id": str(metadata.get("agent_id") or "")[:100],
            "agent_name": str(metadata.get("agent_name") or "")[:200],
            "provider": str(metadata.get("provider") or "unknown")[:100],
            "model": str(metadata.get("model") or "unknown")[:200],
            "deployment": str(metadata.get("deployment") or "")[:200],
            "profile_id": str(metadata.get("profile_id") or "")[:100],
            "runtime": str(metadata.get("runtime") or "legacy")[:50],
            "request_mode": str(mode or "chat")[:20],
            "workload": str(metadata.get("workload") or mode or "chat")[:20],
            "usage_event_id": usage_event_id,
        },
    }
    result = usage_collection.update_one(
        {"_id": usage_event_id},
        {"$setOnInsert": usage_data},
        upsert=True,
    )
    return {
        "usage_event_id": usage_event_id,
        "tokens_total": tokens["tokens_total_sum"],
        "inserted": result.upserted_id is not None,
    }
