import json
from collections import defaultdict
import uuid
from datetime import datetime
from mongo_table_connecters.mongo_connector import get_database
import re

db = get_database()
usage_collection = db["users_usage"]
group_collection = db["teams"]
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
        
def get_user_by_username(username):
    username = user_collection.find_one({"name": username, "delete_at": None})
    return username

def get_group_by_id(gid):
    group = group_collection.find_one({"_id": gid, "delete_at": None})
    return group

def insert_user_usage(auth_claims,response,mode="chat"):
    if mode == "chat":
        tokens = summarize_turn(response)
    else:
        tokens = summarize_turn_for_ask(response)
    usage_data = {
        "_id": str(uuid.uuid4()),       
        "create_at": datetime.utcnow(), 
        "update_at": datetime.utcnow(),  
        "delete_at": None,
        "user": {
            "_id": get_user_by_username(auth_claims["preferred_username"])['_id'],
            "name": auth_claims["preferred_username"]
        },               
        "group": {
            "_id": auth_claims["addition_group"],
            "name": get_group_by_id(auth_claims["addition_group"])['name']
        },                                          
        "tokens_prompt_sum": tokens["tokens_prompt_sum"],             
        "tokens_completion_sum": tokens["tokens_completion_sum"],
        "tokens_total_sum": tokens["tokens_total_sum"],
        "reference_files": tokens["files"]       
    }
    usage_collection.insert_one(usage_data)

def get_all_usage():
    cursor = usage_collection.find({})         
    usages = [usage for usage in cursor]
    return usages
