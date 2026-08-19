# ⭐ CHART CAPABILITY: MongoDB connector สำหรับ chart binding
#    ผูก "ความสามารถสร้างกราฟ" เข้ากับ agent แต่ละตัว
#    Pattern เดียวกับ database_binding.py — collection "chart_bindings"
#
#  Schema v2 (backward compatible):
#   - auto_generate: bool  — ถ้า True LLM จะสร้างกราฟอัตโนมัติเมื่อตอบคำถามที่มีข้อมูลตัวเลข
#   - chart_selection_mode: "auto" | "manual"
#       "auto"   → LLM เลือก chart type ที่เหมาะสมเองจาก allowed_chart_types
#       "manual" → พฤติกรรมเดิม user ต้องบอก type และ enforce allowed_chart_types
#   - allowed_chart_types เป็น server-side allowlist สำหรับทั้ง auto และ manual mode
#   - default_chart_type ใช้เป็นค่าเริ่มต้นใน manual mode

import uuid
from datetime import datetime

from agent_runtime.charting import SAFE_CHART_TYPES
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
chart_binding_collection = db["chart_bindings"]

# Chart types ทั้งหมดที่ระบบรองรับ (ใช้เป็น default เมื่อ auto mode)
ALL_SUPPORTED_CHART_TYPES = list(SAFE_CHART_TYPES)


def _normalize_selection(
    chart_selection_mode: str,
    default_chart_type: str | None,
    allowed_chart_types: list | None,
) -> tuple[str, str, list[str]]:
    mode = str(chart_selection_mode or "auto").strip().lower()
    if mode not in ("auto", "manual"):
        raise ValueError("chart_selection_mode must be 'auto' or 'manual'")
    allowed = []
    for item in allowed_chart_types or ALL_SUPPORTED_CHART_TYPES:
        normalized = str(item).strip()
        if normalized not in ALL_SUPPORTED_CHART_TYPES:
            raise ValueError(f"Unsupported chart type '{normalized}'")
        if normalized not in allowed:
            allowed.append(normalized)
    if not allowed:
        raise ValueError("At least one allowed chart type is required")
    default = str(default_chart_type or allowed[0]).strip()
    if default not in allowed:
        # Automatic mode does not expose/use a user-selected default. Older
        # bindings can therefore contain a stale default after their allowlist
        # changes. Repair it on save instead of rejecting an otherwise valid
        # configuration. Restricted/manual mode remains strict.
        if mode == "auto":
            default = allowed[0]
        else:
            raise ValueError("default_chart_type must be included in allowed_chart_types")
    return mode, default, allowed


def insert_chart_binding(
    agent_id: str,
    color_palette: list = None,
    title_template: str = None,
    trigger_keywords: list = None,
    enabled: bool = True,
    auto_generate: bool = False,
    chart_selection_mode: str = "auto",
    default_chart_type: str = None,
    allowed_chart_types: list = None,
):
    """สร้าง chart binding ใหม่ผูกกับ agent"""
    if not str(agent_id or "").strip():
        raise ValueError("agent_id is required")
    if chart_binding_collection.find_one({"agent_id": agent_id, "delete_at": None}):
        raise ValueError("This agent already has a chart binding")
    mode, default_type, allowed_types = _normalize_selection(
        chart_selection_mode, default_chart_type, allowed_chart_types
    )
    binding_id = str(uuid.uuid4())
    binding_data = {
        "_id": binding_id,
        "agent_id": agent_id,
        "color_palette": color_palette
        or ["#2196f3", "#ff9800", "#4caf50", "#e91e63", "#9c27b0", "#00bcd4"],
        "title_template": title_template or "",
        "trigger_keywords": trigger_keywords or [],
        "enabled": enabled,
        "auto_generate": auto_generate,
        "chart_selection_mode": mode,
        "default_chart_type": default_type,
        "allowed_chart_types": allowed_types,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "delete_at": None,
    }

    result = chart_binding_collection.insert_one(binding_data)
    return result


def get_chart_binding_by_id(binding_id: str):
    """ดึง chart binding ตาม ID"""
    return chart_binding_collection.find_one({"_id": binding_id})


def get_chart_bindings_by_agent_id(agent_id: str):
    """ดึง chart bindings ทั้งหมดของ agent (รวม disabled)"""
    return list(
        chart_binding_collection.find({"agent_id": agent_id, "delete_at": None})
    )


def get_enabled_chart_bindings_by_agent_id(agent_id: str):
    """⭐ ดึง chart bindings ที่เปิดใช้งาน เท่านั้น — ใช้ตอน chat/stream"""
    return list(
        chart_binding_collection.find(
            {"agent_id": agent_id, "enabled": True, "delete_at": None}
        )
    )


def update_chart_binding(
    binding_id: str,
    default_chart_type: str = None,
    allowed_chart_types: list = None,
    color_palette: list = None,
    title_template: str = None,
    trigger_keywords: list = None,
    enabled: bool = None,
    auto_generate: bool = None,
    chart_selection_mode: str = None,
):
    """อัปเดต chart binding"""
    existing = get_chart_binding_by_id(binding_id)
    if not existing:
        return False
    mode, default_type, allowed_types = _normalize_selection(
        chart_selection_mode
        if chart_selection_mode is not None
        else existing.get("chart_selection_mode", "auto"),
        default_chart_type
        if default_chart_type is not None
        else existing.get("default_chart_type"),
        allowed_chart_types
        if allowed_chart_types is not None
        else existing.get("allowed_chart_types"),
    )
    update_data = {
        "updated_at": datetime.utcnow(),
        "chart_selection_mode": mode,
        "default_chart_type": default_type,
        "allowed_chart_types": allowed_types,
    }

    if color_palette is not None:
        update_data["color_palette"] = color_palette
    if title_template is not None:
        update_data["title_template"] = title_template
    if trigger_keywords is not None:
        update_data["trigger_keywords"] = trigger_keywords
    if enabled is not None:
        update_data["enabled"] = enabled
    if auto_generate is not None:
        update_data["auto_generate"] = auto_generate
    result = chart_binding_collection.update_one(
        {"_id": binding_id}, {"$set": update_data}
    )
    return result.modified_count > 0


def delete_chart_binding_by_id(binding_id: str):
    """ลบ chart binding (hard delete)"""
    result = chart_binding_collection.delete_one({"_id": binding_id})
    return result
