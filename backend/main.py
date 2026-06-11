"""
FastAPI application for Dangerous Goods Compliance System
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import json
import os
import re

from database import get_connection, init_db, import_goods_csv, seed_regulations, seed_cn_names, get_stats, import_cn_batch, import_regulations_batch, rebuild_name_index, search_name_index

app = FastAPI(title="危险货物合规查询系统", version="0.1.0")

# Data models
class GoodsItem(BaseModel):
    un_number: str
    name_en: str
    name_cn: str
    class_or_division: str
    subsidiary_hazard: str
    packing_group: str
    special_provisions: str
    limited_quantity: str
    excepted_quantity: str
    packing_instructions: str
    special_packing_provisions: str
    tank_bulk_instructions: str
    tank_special_provisions: str
    source_page: Optional[int]

class RegulationItem(BaseModel):
    code: str
    rule_type: str
    title_en: str
    title_cn: str
    summary_en: str
    summary_cn: str
    original_text: str
    key_points: list
    source_volume: str
    source_page: Optional[int]
    source_section: str


# Startup
@app.on_event("startup")
def startup():
    if not os.path.exists(os.environ.get("DB_PATH", "/workspace/projects/dangerous-goods-compliance/data/compliance.db")):
        init_db()
        import_goods_csv()
        seed_regulations()
        seed_cn_names()
        print("Database initialized on startup")


# --- Routes ---

@app.get("/api/health")
def health():
    return {"status": "ok", "stats": get_stats()}


@app.get("/api/goods/{un_number}")
def get_goods(un_number: str):
    """Query a single UN number"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dangerous_goods WHERE un_number = ?", (un_number,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, f"UN{un_number} 未找到")

    goods = dict(row)
    goods["special_provisions_list"] = goods["special_provisions"].split("|") if goods["special_provisions"] else []
    goods["packing_instructions_list"] = goods["packing_instructions"].split("|") if goods["packing_instructions"] else []
    goods["special_packing_provisions_list"] = goods["special_packing_provisions"].split("|") if goods["special_packing_provisions"] else []
    goods["tank_bulk_instructions_list"] = goods["tank_bulk_instructions"].split("|") if goods["tank_bulk_instructions"] else []
    goods["tank_special_provisions_list"] = goods["tank_special_provisions"].split("|") if goods["tank_special_provisions"] else []

    return goods


@app.get("/api/regulations/{code}")
def get_regulation(code: str):
    """Query a single regulation by code"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM regulations WHERE code = ?", (code.upper(),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, f"规则 {code} 未找到")

    reg = dict(row)
    reg["key_points_list"] = json.loads(reg["key_points"]) if reg["key_points"] else []
    return reg


# --- Admin Routes ---

@app.post("/api/admin/import-cn")
def admin_import_cn(items: list[dict]):
    """Batch import/update Chinese names for UN numbers.
    Body: [{"un_number": "3480", "name_cn": "锂离子电池组", "name_en": "Lithium ion batteries", "notes": "..."}]
    """
    if not items:
        raise HTTPException(400, "请求数据不能为空")
    count = import_cn_batch(items)
    return {"status": "ok", "updated": count}


@app.post("/api/admin/import-regulations")
def admin_import_regulations(items: list[dict]):
    """Batch import/update regulations.
    Body: [{"code": "188", "rule_type": "special_provision", "title_cn": "...", ...}]
    """
    if not items:
        raise HTTPException(400, "请求数据不能为空")
    count = import_regulations_batch(items)
    return {"status": "ok", "imported": count}


@app.post("/api/admin/rebuild-index")
def admin_rebuild_index():
    """Rebuild name index from goods data"""
    total = rebuild_name_index()
    return {"status": "ok", "total_entries": total}


# --- Enhanced Search ---

@app.get("/api/search")
def search(q: str = Query(..., min_length=1), type: str = "all"):
    """Search by UN number, name, or regulation code (bilingual)"""
    conn = get_connection()
    cursor = conn.cursor()

    results = {"goods": [], "regulations": []}

    query_upper = q.upper().strip()

    # If it looks like a UN number or rule code, do exact match first
    if query_upper.isdigit() or re.match(r'^(P|LP|IBC|T|TP|SP|BK|PP)\d+', query_upper, re.I):
        # Try UN number
        if query_upper.isdigit():
            cursor.execute("SELECT un_number, name_en, name_cn, class_or_division FROM dangerous_goods WHERE un_number = ?", (query_upper,))
            row = cursor.fetchone()
            if row:
                results["goods"].append(dict(row))

        # Try regulation code
        cursor.execute("SELECT code, rule_type, title_cn FROM regulations WHERE code = ?", (query_upper,))
        row = cursor.fetchone()
        if row:
            results["regulations"].append(dict(row))

    # Use name_index for bilingual fuzzy search
    if not results["goods"]:
        name_hits = search_name_index(q, limit=30)
        if name_hits:
            # Deduplicate by UN number, prefer CN name
            seen = set()
            for hit in name_hits:
                if hit["un_number"] not in seen:
                    seen.add(hit["un_number"])
                    cursor.execute("""
                        SELECT un_number, name_en, name_cn, class_or_division 
                        FROM dangerous_goods WHERE un_number = ?
                    """, (hit["un_number"],))
                    row = cursor.fetchone()
                    if row:
                        results["goods"].append(dict(row))

    # Fallback: direct SQL LIKE if name_index has no results
    if not results["goods"]:
        like = f"%{q}%"
        cursor.execute("SELECT un_number, name_en, name_cn, class_or_division FROM dangerous_goods WHERE un_number LIKE ? OR name_en LIKE ? OR name_cn LIKE ? LIMIT 20", (like, like, like))
        for row in cursor.fetchall():
            results["goods"].append(dict(row))

    if not results["regulations"]:
        like = f"%{q}%"
        cursor.execute("SELECT code, rule_type, title_cn, summary_cn FROM regulations WHERE code LIKE ? OR title_cn LIKE ? OR summary_cn LIKE ? LIMIT 20", (like, like, like))
        for row in cursor.fetchall():
            results["regulations"].append(dict(row))

    conn.close()
    return results


@app.get("/api/compliance/{un_number}")
def get_compliance(un_number: str):
    """Comprehensive compliance result for a UN number"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get basic goods info
    cursor.execute("SELECT * FROM dangerous_goods WHERE un_number = ?", (un_number,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"UN{un_number} 未找到")

    goods = dict(row)
    sp_codes = goods["special_provisions"].split("|") if goods["special_provisions"] else []
    pi_codes = goods["packing_instructions"].split("|") if goods["packing_instructions"] else []
    spi_codes = goods["special_packing_provisions"].split("|") if goods["special_packing_provisions"] else []
    tbi_codes = goods["tank_bulk_instructions"].split("|") if goods["tank_bulk_instructions"] else []
    tsp_codes = goods["tank_special_provisions"].split("|") if goods["tank_special_provisions"] else []

    # Get special provisions
    special_provisions = []
    for code in sp_codes:
        cursor.execute("SELECT * FROM regulations WHERE code = ?", (code,))
        sp_row = cursor.fetchone()
        if sp_row:
            r = dict(sp_row)
            r["key_points_list"] = json.loads(r["key_points"]) if r["key_points"] else []
            special_provisions.append(r)
        else:
            special_provisions.append({"code": code, "title_cn": "", "summary_cn": "", "source_page": None, "key_points_list": []})

    # Get packing instructions
    packing_instructions = []
    for code in pi_codes:
        cursor.execute("SELECT * FROM regulations WHERE code = ?", (code,))
        pi_row = cursor.fetchone()
        if pi_row:
            r = dict(pi_row)
            r["key_points_list"] = json.loads(r["key_points"]) if r["key_points"] else []
            packing_instructions.append(r)
        else:
            packing_instructions.append({"code": code, "title_cn": "", "summary_cn": "", "source_page": None, "key_points_list": []})

    # Get special packing provisions
    special_packing = []
    for code in spi_codes:
        cursor.execute("SELECT * FROM regulations WHERE code = ?", (code,))
        sp_row = cursor.fetchone()
        if sp_row:
            r = dict(sp_row)
            r["key_points_list"] = json.loads(r["key_points"]) if r["key_points"] else []
            special_packing.append(r)
        else:
            special_packing.append({"code": code, "title_cn": "", "summary_cn": "", "source_page": None, "key_points_list": []})

    # Get tank/bulk instructions
    tank_rules = []
    for code in tbi_codes + tsp_codes:
        cursor.execute("SELECT * FROM regulations WHERE code = ?", (code,))
        t_row = cursor.fetchone()
        if t_row:
            r = dict(t_row)
            r["key_points_list"] = json.loads(r["key_points"]) if r["key_points"] else []
            tank_rules.append(r)

    # Build checklist
    checklist = _build_checklist(goods, special_provisions, packing_instructions)

    # Sources
    sources = []
    if goods["source_page"]:
        sources.append(f"Vol.I，第 3.2 章，第 {goods['source_page']} 页")

    conn.close()

    return {
        "basic": {
            "un_number": goods["un_number"],
            "name_en": goods["name_en"],
            "name_cn": goods["name_cn"],
            "class_or_division": goods["class_or_division"],
            "subsidiary_hazard": goods["subsidiary_hazard"],
            "packing_group": goods["packing_group"],
            "limited_quantity": goods["limited_quantity"],
            "excepted_quantity": goods["excepted_quantity"],
        },
        "special_provisions": special_provisions,
        "packing_instructions": packing_instructions,
        "special_packing_provisions": special_packing,
        "tank_bulk_rules": tank_rules,
        "checklist": checklist,
        "sources": sources
    }


def _build_checklist(goods, special_provisions, packing_instructions):
    """Build a basic compliance checklist"""
    checklist = []

    # Class-based items
    cls = goods.get("class_or_division", "")
    un = goods.get("un_number", "")

    if cls == "9" and un in ("3480", "3481", "3090", "3091", "3551", "3552"):
        checklist.append("确认运输对象的具体UN编号和描述")
        checklist.append("确认电池是否完好无损（非损坏/缺陷/待回收）")
        checklist.append("确认电池端子是否已防短路处理")
        checklist.append("确认是否满足SP188条件（如适用，可按例外条件运输）")
        checklist.append("确认包装是否符合对应包装指南要求")
        checklist.append("确认包装件上是否正确标注UN编号")
        checklist.append("确认是否需要锂电池组标记（9A标记）")
        checklist.append("确认运输单据是否注明危险货物信息")
        if goods["limited_quantity"] == "0":
            checklist.append("注意：有限数量为0，不能按有限数量运输")
    else:
        checklist.append("确认UN编号和正确运输名称")
        checklist.append("确认货物分类和包装类别")
        checklist.append("确认包装符合对应包装指南要求")
        checklist.append("确认特殊规定是否适用")

    # Add rule-specific items from key_points
    for sp in special_provisions:
        for kp in sp.get("key_points_list", []):
            if kp and kp not in checklist:
                checklist.append(kp)

    for pi in packing_instructions:
        for kp in pi.get("key_points_list", []):
            if kp and kp not in checklist:
                checklist.append(kp)

    return checklist


@app.get("/api/browse")
def browse(class_or_division: str = None, page: int = 1, size: int = 50):
    """Browse goods by class"""
    conn = get_connection()
    cursor = conn.cursor()

    if class_or_division:
        cursor.execute("SELECT COUNT(*) FROM dangerous_goods WHERE class_or_division = ?", (class_or_division,))
        total = cursor.fetchone()[0]
        offset = (page - 1) * size
        cursor.execute("SELECT un_number, name_en, name_cn, class_or_division, packing_group FROM dangerous_goods WHERE class_or_division = ? ORDER BY CAST(un_number AS INTEGER) LIMIT ? OFFSET ?", (class_or_division, size, offset))
    else:
        cursor.execute("SELECT COUNT(*) FROM dangerous_goods")
        total = cursor.fetchone()[0]
        offset = (page - 1) * size
        cursor.execute("SELECT un_number, name_en, name_cn, class_or_division, packing_group FROM dangerous_goods ORDER BY CAST(un_number AS INTEGER) LIMIT ? OFFSET ?", (size, offset))

    rows = [dict(r) for r in cursor.fetchall()]

    # Get distinct classes
    cursor.execute("SELECT DISTINCT class_or_division FROM dangerous_goods ORDER BY class_or_division")
    classes = [r[0] for r in cursor.fetchall()]

    conn.close()

    return {
        "items": rows,
        "total": total,
        "page": page,
        "size": size,
        "classes": classes,
        "filter": class_or_division
    }


# Serve static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Frontend not built yet. API is running.</h1>")
