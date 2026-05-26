"""设备维修数据库查询引擎 — MySQL 版"""

import re
import math
import json
import os
import urllib.request
import urllib.error
import pymysql
from collections import Counter
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL

MYSQL_CONFIG = {
    "host":     os.environ.get("MYSQL_HOST", "10.0.6.86"),
    "port":     int(os.environ.get("MYSQL_PORT", "33306")),
    "user":     os.environ.get("MYSQL_USER", "powerbi"),
    "password": os.environ.get("MYSQL_PASSWORD", "!Q1234567"),
    "database": os.environ.get("MYSQL_DATABASE", "erp_data"),
    "charset":  os.environ.get("MYSQL_CHARSET", "utf8mb4"),
}

TABLE_NAME = "设备维修数据库_v2"

# MySQL 列名（去掉了 Path, ItemType→附件, 维修时长(分钟)→维修时长_分钟）
COL_EQUIPMENT       = "设备名称"
COL_EQUIP_CODE      = "设备编号"
COL_FAULT_CAT       = "机器故障类别"
COL_FAULT_DETAIL    = "机器故障类别明细"
COL_PHENOMENON      = "故障现象描述"
COL_PRODUCT_DEFECT  = "故障可能导致的产品不良描述"
COL_ROOT_CAUSE      = "故障根本原因分析"
COL_ACTION          = "维修采取措施"
COL_PREVENTION      = "预防改进措施"
COL_DURATION        = "维修时长_分钟"
COL_TECHNICIAN      = "维修技术员"
COL_SUBMIT_TIME     = "提交时间"
COL_ATTACHMENT      = "附件"


def _get_conn():
    return pymysql.connect(**MYSQL_CONFIG)


def get_equipment_list():
    """获取设备列表（名称 + 记录数）"""
    conn = _get_conn()
    try:
        with conn.cursor() as c:
            c.execute(f"SELECT `{COL_EQUIPMENT}`, COUNT(*) FROM `{TABLE_NAME}` GROUP BY `{COL_EQUIPMENT}` ORDER BY COUNT(*) DESC")
            return [{"name": row[0], "count": row[1]} for row in c.fetchall()]
    finally:
        conn.close()


def _safe(val):
    """NaN/None → 空字符串"""
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return str(val).strip()


def _to_records(rows, col_names):
    """MySQL 查询结果 → dict 列表"""
    records = []
    for row in rows:
        rec = {}
        for i, name in enumerate(col_names):
            val = row[i]
            # datetime → 字符串
            if hasattr(val, "strftime"):
                val = val.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(val, float) and math.isnan(val):
                val = None
            rec[name] = val
        records.append(rec)
    return records


def _tokenize(text):
    """提取 2-4 字中文滑窗 + 英文词"""
    tokens = set()
    cn_chunks = re.sub(r'[^\u4e00-\u9fff]', ' ', text).split()
    for chunk in cn_chunks:
        for size in (2, 3, 4):
            for i in range(len(chunk) - size + 1):
                tokens.add(chunk[i:i+size])
    for w in re.findall(r'[a-zA-Z0-9]{2,}', text):
        tokens.add(w)
    return tokens or {text}


def search_db(keyword=None, equipment=None, category=None, limit=10):
    """搜索维修记录（MySQL 版）"""
    conn = _get_conn()
    try:
        with conn.cursor() as c:
            conditions = []
            params = []

            if equipment:
                conditions.append(f"`{COL_EQUIPMENT}` LIKE %s")
                params.append(f"%{equipment}%")
            if category:
                conditions.append(f"`{COL_FAULT_CAT}` LIKE %s")
                params.append(f"%{category}%")

            if keyword:
                tokens = _tokenize(keyword)
                or_clauses = []
                for token in tokens:
                    # 优先字段：故障现象、设备名称、故障原因（高权重）
                    high_cols = [COL_PHENOMENON, COL_EQUIPMENT, COL_ROOT_CAUSE]
                    mid_cols  = [COL_ACTION, COL_FAULT_DETAIL, COL_FAULT_CAT]
                    for col in high_cols + mid_cols:
                        or_clauses.append(f"`{col}` LIKE %s")
                        params.append(f"%{token}%")
                        # 高权重字段重复一次（加分项，在ORDER BY中体现）
                        if col in high_cols:
                            or_clauses.append(f"`{col}` LIKE %s")
                            params.append(f"%{token}%")
                if or_clauses:
                    conditions.append("(" + " OR ".join(or_clauses) + ")")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 相关度排序：高权重字段命中次数越多越靠前
            if keyword:
                score_parts = []
                for token in _tokenize(keyword):
                    for col in [COL_PHENOMENON, COL_EQUIPMENT, COL_ROOT_CAUSE]:
                        score_parts.append(f"(CASE WHEN `{col}` LIKE %s THEN 3 ELSE 0 END)")
                        params.append(f"%{token}%")
                    for col in [COL_ACTION, COL_FAULT_DETAIL, COL_FAULT_CAT]:
                        score_parts.append(f"(CASE WHEN `{col}` LIKE %s THEN 1 ELSE 0 END)")
                        params.append(f"%{token}%")
                score_expr = " + ".join(score_parts)
                order_by = f"ORDER BY ({score_expr}) DESC, `{COL_SUBMIT_TIME}` DESC"
            else:
                order_by = f"ORDER BY `{COL_SUBMIT_TIME}` DESC"

            col_names = [
                "ID", COL_EQUIPMENT, COL_EQUIP_CODE, COL_FAULT_CAT, COL_FAULT_DETAIL,
                COL_PHENOMENON, COL_PRODUCT_DEFECT, COL_ROOT_CAUSE, COL_ACTION,
                COL_PREVENTION, COL_DURATION, COL_TECHNICIAN, COL_SUBMIT_TIME, COL_ATTACHMENT
            ]
            cols_str = ", ".join(f"`{c}`" for c in col_names)

            sql = f"SELECT {cols_str} FROM `{TABLE_NAME}` WHERE {where_clause} {order_by} LIMIT {limit}"
            c.execute(sql, params)
            rows = c.fetchall()

            return _to_records(rows, col_names)
    finally:
        conn.close()


# ───────────────────── 报告生成（逻辑不变，列名适配） ─────────────────────

def _clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _dedupe_list(items, max_items=5):
    seen = set()
    result = []
    for item in items:
        key = re.sub(r'\s+', '', item).lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
            if len(result) >= max_items:
                break
    return result


def _split_steps(text):
    if not text:
        return []
    parts = re.split(r'[；;、\n]+', text)
    steps = []
    for p in parts:
        p = p.strip().strip('。.')
        if p and len(p) > 2:
            steps.append(p)
    return steps


def _get_date_str(val):
    if val is None:
        return None
    s = _safe(val)
    if not s:
        return None
    m = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)
    return s[:10] if len(s) >= 10 else s


def generate_report(records, user_input):
    """老工程师风格归纳报告"""
    if not records:
        return None

    total = len(records)

    # 主要设备
    equip_counter = Counter(_safe(r.get(COL_EQUIPMENT)) for r in records if _safe(r.get(COL_EQUIPMENT)))
    main_equipment = equip_counter.most_common(1)[0][0] if equip_counter else ""

    # 最近维修日期
    dates = []
    for r in records:
        d = _get_date_str(r.get(COL_SUBMIT_TIME))
        if d:
            dates.append(d)
    latest_date = max(dates) if dates else None

    # 【可能原因】
    raw_causes = []
    for r in records:
        cause = _clean_text(_safe(r.get(COL_ROOT_CAUSE)))
        if cause and cause != "原因待分析":
            parts = re.split(r'[；;\n]+', cause)
            for p in parts:
                p = p.strip().strip('。.')
                if p and len(p) >= 4:
                    raw_causes.append(p)
    causes = _dedupe_list(raw_causes, max_items=5)
    if not causes:
        causes = ["暂无明确原因记录，建议现场排查"]

    # 【参考处理措施】
    all_steps_counter = Counter()
    for r in records:
        action = _clean_text(_safe(r.get(COL_ACTION)))
        if action:
            for step in _split_steps(action):
                all_steps_counter[step] += 1
    top_steps_raw = [step for step, _ in all_steps_counter.most_common(20)]
    top_steps = _dedupe_list(top_steps_raw, max_items=8)
    if not top_steps:
        top_steps = ["请参照设备维修手册进行排查"]

    # 【注意事项】
    caution_keywords = ["注意", "禁止", "必须", "不得", "小心", "确认", "检查前", "操作前",
                        "需要", "务必", "防止", "避免"]
    caution_sentences = []
    for r in records:
        for field in [COL_ACTION, COL_ROOT_CAUSE, COL_PHENOMENON]:
            text = _clean_text(_safe(r.get(field)))
            if not text:
                continue
            sentences = re.split(r'[；;\n。.！!？?]+', text)
            for s in sentences:
                s = s.strip()
                if len(s) >= 5 and any(kw in s for kw in caution_keywords):
                    caution_sentences.append(s)
    caution_list = _dedupe_list(caution_sentences, max_items=4)

    # 【风险提示】
    repeat_equips = [eq for eq, cnt in equip_counter.items() if cnt >= 3]
    is_frequent = len(repeat_equips) > 0 or total >= 5

    # 平均维修时长
    durations_all = []
    for r in records:
        d = r.get(COL_DURATION)
        if d and not (isinstance(d, float) and math.isnan(d)):
            try:
                durations_all.append(float(d))
            except Exception:
                pass
    avg_duration = round(sum(durations_all) / len(durations_all), 0) if durations_all else None

    return {
        "total":          total,
        "main_equipment": main_equipment,
        "latest_date":    latest_date,
        "causes":         causes,
        "steps":          top_steps,
        "cautions":       caution_list,
        "is_frequent":    is_frequent,
        "repeat_equips":  repeat_equips,
        "avg_duration":   avg_duration,
    }


def chat_query(user_input):
    """对话式查询"""
    equipment_filter = None
    try:
        all_equipment = [e["name"] for e in get_equipment_list()]
        for eq in sorted(all_equipment, key=len, reverse=True):
            if eq in user_input:
                equipment_filter = eq
                break
    except Exception:
        pass

    records = search_db(keyword=user_input, equipment=equipment_filter, limit=10)
    report  = generate_report(records, user_input)

    return {
        "query":              user_input,
        "equipment_detected": equipment_filter,
        "report":             report,
        "raw_count":          len(records),
    }


# ───────────────────── AI 总结（千问 API） ─────────────────────

def ai_summary(query, report):
    """调用千问 API 生成故障分析总结。返回 (summary_text, error) 元组。"""
    if not QWEN_API_KEY or not QWEN_BASE_URL:
        return None, "AI 总结功能未配置 API Key"

    if not report:
        return None, "暂无报告数据，无法生成 AI 总结"

    # 构建上下文
    ctx_parts = [f"用户查询：{query}"]
    total = report.get("total", 0)
    if total:
        ctx_parts.append(f"历史记录数：{total} 条")
    if report.get("main_equipment"):
        ctx_parts.append(f"主要设备：{report['main_equipment']}")
    if report.get("latest_date"):
        ctx_parts.append(f"最近维修日期：{report['latest_date']}")
    if report.get("avg_duration"):
        ctx_parts.append(f"平均维修时长：{report['avg_duration']} 分钟")
    if report.get("causes"):
        ctx_parts.append(f"可能原因：{'；'.join(report['causes'])}")
    if report.get("steps"):
        ctx_parts.append(f"处理措施：{'；'.join(report['steps'])}")
    if report.get("cautions"):
        ctx_parts.append(f"注意事项：{'；'.join(report['cautions'])}")
    if report.get("is_frequent"):
        ctx_parts.append("⚠️ 该问题曾高频发生，需要排查根本原因")

    context = "\n".join(ctx_parts)

    system_prompt = (
        "你是一个设备维修专家助手，擅长分析历史维修记录，帮助现场技术员快速诊断设备故障。"
        "请用简洁、专业、实用的语言回答，语气像经验丰富的老师傅。"
    )
    user_prompt = f"""请根据以下历史维修记录，对用户的问题做一次「老技师」风格的分析总结：

{context}

要求：
1. 用 2-3 句话概括核心诊断结论
2. 按优先级排序给出排查建议（先查什么后查什么）
3. 如有特别注意事项或避坑经验，单独提醒
4. 语气像经验丰富的老师傅，不要太学术化
5. 总字数控制在 300 字以内"""

    try:
        req_data = json.dumps({
            "model": QWEN_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 600
        }).encode("utf-8")

        url = f"{QWEN_BASE_URL}/chat/completions"
        req = urllib.request.Request(url, data=req_data, headers={
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json"
        })

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]
        return content.strip(), None

    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            body = "(无法读取错误详情)"
        return None, f"千问 API 请求失败 (HTTP {e.code})：{body}"
    except Exception as e:
        return None, f"AI 总结生成失败：{str(e)}"
