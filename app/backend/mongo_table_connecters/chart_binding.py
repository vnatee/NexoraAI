# ⭐ CHART CAPABILITY: MongoDB connector สำหรับ chart binding
#    ผูก "ความสามารถสร้างกราฟ" เข้ากับ agent แต่ละตัว
#    Pattern เดียวกับ database_binding.py — collection "chart_bindings"
#
#  Schema v2 (backward compatible):
#   - auto_generate: bool  — ถ้า True LLM จะสร้างกราฟอัตโนมัติเมื่อตอบคำถามที่มีข้อมูลตัวเลข
#   - chart_selection_mode: "auto" | "manual"
#       "auto"   → LLM เลือก chart type ที่เหมาะสมเองจากข้อมูล (ไม่ enforce allowed_chart_types)
#       "manual" → พฤติกรรมเดิม user ต้องบอก type และ enforce allowed_chart_types
#   - default_chart_type / allowed_chart_types ยังคงอยู่ใน schema เพื่อ backward compat
#     แต่จะถูก ignore เมื่อ chart_selection_mode = "auto"

from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
chart_binding_collection = db["chart_bindings"]

# Chart types ทั้งหมดที่ระบบรองรับ (ใช้เป็น default เมื่อ auto mode)
ALL_SUPPORTED_CHART_TYPES = [
    # 2D พื้นฐาน
    "bar", "line", "pie", "area", "scatter",
    # 2D เฉพาะทาง
    "radar", "heatmap", "treemap", "sunburst", "funnel",
    "gauge", "boxplot", "candlestick", "sankey", "graph",
    # 3D (ECharts GL)
    "bar3D", "line3D", "scatter3D", "surface",
    # เพิ่มเติม
    "pictorialBar", "themeRiver", "parallel", "calendar",
]


def insert_chart_binding(
    agent_id: str,
    color_palette: list = None,
    title_template: str = None,
    trigger_keywords: list = None,
    enabled: bool = True,
    auto_generate: bool = False,
    chart_selection_mode: str = "auto",
    # v1 backward-compat params — kept so old callers don't break, but NOT stored
    default_chart_type: str = None,
    allowed_chart_types: list = None,
):
    """สร้าง chart binding ใหม่ผูกกับ agent"""
    binding_id = str(uuid.uuid4())
    binding_data = {
        "_id": binding_id,
        "agent_id": agent_id,
        "color_palette": color_palette or [
            "#2196f3", "#ff9800", "#4caf50", "#e91e63", "#9c27b0", "#00bcd4"
        ],
        "title_template": title_template or "",
        "trigger_keywords": trigger_keywords or [],
        "enabled": enabled,
        "auto_generate": auto_generate,
        "chart_selection_mode": chart_selection_mode,
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
    return list(chart_binding_collection.find({"agent_id": agent_id, "delete_at": None}))


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
    update_data = {"updated_at": datetime.utcnow()}

    if default_chart_type is not None:
        update_data["default_chart_type"] = default_chart_type
    if allowed_chart_types is not None:
        update_data["allowed_chart_types"] = allowed_chart_types
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
    if chart_selection_mode is not None:
        update_data["chart_selection_mode"] = chart_selection_mode

    result = chart_binding_collection.update_one(
        {"_id": binding_id}, {"$set": update_data}
    )
    return result.modified_count > 0


def delete_chart_binding_by_id(binding_id: str):
    """ลบ chart binding (hard delete)"""
    result = chart_binding_collection.delete_one({"_id": binding_id})
    return result
