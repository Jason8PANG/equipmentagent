"""
设备维修助手 - Web 服务（MySQL 版）
│  /                  → 故障查询对话界面
│  /add               → 技术员录入维修记录
│  /api/chat          → 查询 API
│  /api/submit        → 提交维修记录 API（含文件上传）
│  /api/equip-codes   → 设备名称 → 设备编号 联动
│  /api/fault-details → 故障类别 → 故障明细 联动
│  /api/technicians   → 维修技术员列表
"""

import os
import socket
import json
import math
import re
import uuid
import pymysql
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename
from query_engine import chat_query, ai_summary, MYSQL_CONFIG, TABLE_NAME

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = None  # 不限制上传大小

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ATTACH_TABLE = "repair_attachments"

# Master 主数据表（下拉框数据源）
MASTER_EQUIPMENT  = "设备清单"
MASTER_FAULT      = "故障类别明细"
MASTER_TECHNICIAN = "维修技术员"

# MySQL 列名常量
COL_ID            = "ID"
COL_EQUIPMENT     = "设备名称"
COL_EQUIP_CODE    = "设备编号"
COL_FAULT_CAT     = "机器故障类别"
COL_FAULT_DETAIL  = "机器故障类别明细"
COL_PHENOMENON    = "故障现象描述"
COL_PRODUCT_DEFECT= "故障可能导致的产品不良描述"
COL_ROOT_CAUSE    = "故障根本原因分析"
COL_ACTION        = "维修采取措施"
COL_PREVENTION    = "预防改进措施"
COL_DURATION      = "维修时长_分钟"
COL_TECHNICIAN    = "维修技术员"
COL_SUBMIT_TIME   = "提交时间"
COL_ATTACHMENT    = "附件"

NOT_NULL_COLS = [
    COL_EQUIPMENT, COL_EQUIP_CODE, COL_FAULT_CAT, COL_FAULT_DETAIL,
    COL_PHENOMENON, COL_ROOT_CAUSE, COL_ACTION, COL_DURATION,
    COL_TECHNICIAN,
]


def json_response(data, status=200):
    """UTF-8 中文、NaN→null 的 JSON 响应"""
    def sanitize(obj):
        if isinstance(obj, float) and math.isnan(obj): return None
        if isinstance(obj, dict): return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list): return [sanitize(i) for i in obj]
        return obj
    return Response(json.dumps(sanitize(data), ensure_ascii=False),
                    status=status, mimetype="application/json; charset=utf-8")


def get_mysql_conn():
    return pymysql.connect(**MYSQL_CONFIG)


def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


# ══════════════════════════════════════════════
#  联动下拉 API
# ══════════════════════════════════════════════

@app.route("/api/equip-codes")
def equip_codes():
    """给定设备名称 → 返回对应的设备编号列表（来源：设备清单主数据表）"""
    equip = request.args.get("equipment", "").strip()
    if not equip:
        return jsonify({"success": False, "error": "缺少 equipment 参数"}), 400
    try:
        conn = get_mysql_conn()
        with conn.cursor() as c:
            c.execute(
                f"SELECT `设备编号` FROM `{MASTER_EQUIPMENT}` "
                f"WHERE `设备名称` = %s ORDER BY `设备编号`",
                (equip,)
            )
            codes = [row[0] for row in c.fetchall()]
        conn.close()
        return json_response({"success": True, "data": codes})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)


@app.route("/api/fault-details")
def fault_details():
    """给定故障类别 → 返回对应的故障明细列表（来源：故障类别明细主数据表）"""
    cat = request.args.get("category", "").strip()
    if not cat:
        return jsonify({"success": False, "error": "缺少 category 参数"}), 400
    try:
        conn = get_mysql_conn()
        with conn.cursor() as c:
            c.execute(
                f"SELECT `故障明细` FROM `{MASTER_FAULT}` "
                f"WHERE `故障类别` = %s ORDER BY `故障明细`",
                (cat,)
            )
            details = [row[0] for row in c.fetchall()]
        conn.close()
        return json_response({"success": True, "data": details})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)


@app.route("/api/technicians")
def technicians():
    """返回所有维修技术员（来源：维修技术员主数据表）"""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as c:
            c.execute(f"SELECT `姓名` FROM `{MASTER_TECHNICIAN}` ORDER BY `姓名`")
            techs = [row[0] for row in c.fetchall()]
        conn.close()
        return json_response({"success": True, "data": techs})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)


# ══════════════════════════════════════════════
#  查询界面
# ══════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求为空"}), 400
        user_input = data.get("message", "").strip()
        if not user_input:
            return jsonify({"success": False, "error": "请输入查询内容"}), 400
        result = chat_query(user_input)
        return json_response({"success": True, **result})
    except Exception as e:
        import traceback
        return json_response({"success": False, "error": f"查询失败：{str(e)}", "trace": traceback.format_exc()}, 500)


@app.route("/api/ai-summary", methods=["POST"])
def ai_summary_api():
    """AI 总结接口 —— 调用千问 API 生成故障分析总结"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求为空"}), 400

        query  = data.get("query", "").strip()
        report = data.get("report", {})

        if not query:
            return jsonify({"success": False, "error": "缺少查询内容"}), 400
        if not report or not report.get("total"):
            return jsonify({"success": False, "error": "暂无有效报告数据"}), 400

        summary, error = ai_summary(query, report)
        if error:
            return json_response({"success": False, "error": error})

        return json_response({"success": True, "summary": summary})

    except Exception as e:
        import traceback
        return json_response({"success": False, "error": f"AI 总结失败：{str(e)}"}, 500)


@app.route("/api/equipment-list")
def equipment_list():
    try:
        conn = get_mysql_conn()
        with conn.cursor() as c:
            c.execute(f"SELECT DISTINCT `设备名称` FROM `{MASTER_EQUIPMENT}` ORDER BY `设备名称`")
            eq_names = [row[0] for row in c.fetchall()]
        conn.close()
        return json_response({"success": True, "data": eq_names})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)


# ══════════════════════════════════════════════
#  录入界面
# ══════════════════════════════════════════════

@app.route("/add")
def add_page():
    """技术员录入维修记录页面（下拉选项来自主数据表）"""
    equip_names = []
    fault_cats = []
    techs = []
    try:
        conn = get_mysql_conn()
        with conn.cursor() as c:
            c.execute(f"SELECT DISTINCT `设备名称` FROM `{MASTER_EQUIPMENT}` ORDER BY `设备名称`")
            equip_names = [row[0] for row in c.fetchall()]
            c.execute(f"SELECT DISTINCT `故障类别` FROM `{MASTER_FAULT}` ORDER BY `故障类别`")
            fault_cats = [row[0] for row in c.fetchall()]
            c.execute(f"SELECT `姓名` FROM `{MASTER_TECHNICIAN}` ORDER BY `姓名`")
            techs = [row[0] for row in c.fetchall()]
        conn.close()
    except Exception:
        pass

    return render_template("add.html",
                           equipment_list=equip_names,
                           fault_categories=fault_cats,
                           technician_list=techs)


# ══════════════════════════════════════════════
#  提交 API（含文件上传）
# ══════════════════════════════════════════════

@app.route("/api/submit", methods=["POST"])
def submit_record():
    """技术员提交维修记录 + 照片上传 → 写 MySQL"""
    conn = None
    try:
        ensure_upload_dir()

        # ── 普通字段（JSON / form） ──
        if request.is_json:
            data = request.get_json()
            files = []
        else:
            data = request.form
            files = request.files.getlist("photos")

        if not data:
            return jsonify({"success": False, "error": "请求为空"}), 400

        def get_val(key):
            val = data.get(key, "")
            return val.strip() if isinstance(val, str) else val

        fields = {
            COL_EQUIPMENT:    get_val("equipment"),
            COL_EQUIP_CODE:   get_val("equip_code"),
            COL_FAULT_CAT:    get_val("fault_category"),
            COL_FAULT_DETAIL: get_val("fault_detail"),
            COL_PHENOMENON:   get_val("phenomenon"),
            COL_PRODUCT_DEFECT: get_val("product_defect") or None,
            COL_ROOT_CAUSE:   get_val("root_cause"),
            COL_ACTION:       get_val("action"),
            COL_PREVENTION:   get_val("prevention") or None,
            COL_DURATION:     get_val("duration"),
            COL_TECHNICIAN:   get_val("technician"),
        }

        # 验证必填
        missing = []
        for k in NOT_NULL_COLS:
            if k in [COL_PRODUCT_DEFECT, COL_PREVENTION]:
                continue
            val = fields.get(k)
            if val is None or (isinstance(val, str) and not val):
                missing.append(k)
        if missing:
            return jsonify({"success": False, "error": f"缺少必填字段：{', '.join(missing)}"}), 400

        # 验证维修时长
        try:
            fields[COL_DURATION] = int(fields[COL_DURATION])
            if fields[COL_DURATION] <= 0:
                return jsonify({"success": False, "error": "维修时长必须大于0"}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "维修时长必须为数字"}), 400

        # ── 写入 MySQL ──
        conn = get_mysql_conn()
        with conn.cursor() as c:
            c.execute(f"SELECT COALESCE(MAX(`{COL_ID}`), 0) + 1 FROM `{TABLE_NAME}`")
            new_id = c.fetchone()[0]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            insert_sql = f"""
                INSERT INTO `{TABLE_NAME}`
                (`{COL_ID}`, `{COL_EQUIPMENT}`, `{COL_EQUIP_CODE}`, `{COL_FAULT_CAT}`, `{COL_FAULT_DETAIL}`,
                 `{COL_PHENOMENON}`, `{COL_PRODUCT_DEFECT}`, `{COL_ROOT_CAUSE}`, `{COL_ACTION}`,
                 `{COL_PREVENTION}`, `{COL_DURATION}`, `{COL_TECHNICIAN}`, `{COL_SUBMIT_TIME}`, `{COL_ATTACHMENT}`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            c.execute(insert_sql, (
                new_id,
                fields[COL_EQUIPMENT], fields[COL_EQUIP_CODE],
                fields[COL_FAULT_CAT], fields[COL_FAULT_DETAIL],
                fields[COL_PHENOMENON], fields[COL_PRODUCT_DEFECT],
                fields[COL_ROOT_CAUSE], fields[COL_ACTION],
                fields[COL_PREVENTION], fields[COL_DURATION],
                fields[COL_TECHNICIAN], now,
                str(len(files)) if files else "",
            ))
            conn.commit()

        # ── 保存照片 + 写附件表 ──
        attachment_count = 0
        if files:
            record_dir = os.path.join(UPLOAD_DIR, str(new_id))
            os.makedirs(record_dir, exist_ok=True)

            for f in files:
                if not f or not f.filename:
                    continue
                # 安全的文件名 + uuid 防重名
                orig = secure_filename(f.filename) or "photo"
                name, ext = os.path.splitext(orig)
                if not ext:
                    ext = ".jpg"
                saved_name = f"{uuid.uuid4().hex[:12]}_{orig}"
                saved_path = os.path.join(record_dir, saved_name)

                try:
                    f.save(saved_path)
                except Exception:
                    # 文件过大或其他IO错误，跳过
                    continue

                attachment_count += 1
                rel_path = f"uploads/{new_id}/{saved_name}"
                with conn.cursor() as c:
                    c.execute(
                        f"INSERT INTO `{ATTACH_TABLE}` (`repair_id`, `orig_name`, `file_path`, `created_at`) "
                        f"VALUES (%s, %s, %s, %s)",
                        (new_id, orig, rel_path, now)
                    )
                conn.commit()

            # 更新主表附件数量
            if attachment_count > 0:
                with conn.cursor() as c:
                    c.execute(
                        f"UPDATE `{TABLE_NAME}` SET `{COL_ATTACHMENT}` = %s WHERE `{COL_ID}` = %s",
                        (str(attachment_count), new_id)
                    )
                conn.commit()

        return json_response({
            "success": True,
            "message": "维修记录已提交",
            "record_id": new_id,
            "submit_time": now,
            "attachment_count": attachment_count,
        })

    except pymysql.Error as e:
        return jsonify({"success": False, "error": f"数据库写入失败：{str(e)}"}), 500
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


# ══════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════

if __name__ == "__main__":
    ensure_upload_dir()
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except Exception:
        ip_address = "127.0.0.1"

    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 52)
    print("  [EquipMaintenance] MySQL Edition Started")
    print("=" * 52)
    print(f"  Query:    http://localhost:5000")
    print(f"  Add:      http://localhost:5000/add")
    print(f"  LAN:      http://{ip_address}:5000")
    print(f"  LAN Add:  http://{ip_address}:5000/add")
    print(f"  Uploads:  {UPLOAD_DIR}")
    print("=" * 52)

    app.run(host="0.0.0.0", port=5000, debug=False)
