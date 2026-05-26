#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OneDrive Excel → MySQL 设备维修数据库 迁移脚本"""

import pymysql
import pandas as pd
import sys

EXCEL_PATH = r"C:\Users\yan.shen\OneDrive - nai-group.com\MED设备保养计划\设备维修数据库.xlsx"

MYSQL_CONFIG = {
    "host": "10.0.6.86",
    "port": 33306,
    "user": "powerbi",
    "password": "!Q1234567",
    "database": "erp_data",
    "charset": "utf8mb4",
}

TABLE_NAME = "设备维修数据库"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS `设备维修数据库` (
    `ID` INT PRIMARY KEY,
    `设备名称` VARCHAR(100) NOT NULL,
    `设备编号` VARCHAR(100) NOT NULL,
    `机器故障类别` VARCHAR(100) NOT NULL,
    `机器故障类别明细` VARCHAR(200) NOT NULL,
    `故障现象描述` TEXT NOT NULL,
    `故障可能导致的产品不良描述` TEXT,
    `故障根本原因分析` TEXT NOT NULL,
    `维修采取措施` TEXT NOT NULL,
    `预防改进措施` TEXT,
    `维修时长_分钟` INT NOT NULL,
    `维修技术员` VARCHAR(50) NOT NULL,
    `提交时间` DATETIME NOT NULL,
    `ItemType` VARCHAR(50),
    `Path` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

INSERT_SQL = """
INSERT INTO `设备维修数据库` 
(`ID`, `设备名称`, `设备编号`, `机器故障类别`, `机器故障类别明细`, `故障现象描述`, 
 `故障可能导致的产品不良描述`, `故障根本原因分析`, `维修采取措施`, `预防改进措施`, 
 `维修时长_分钟`, `维修技术员`, `提交时间`, `ItemType`, `Path`)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def safe_str(val):
    """安全转为字符串，NaN 返回 None"""
    if pd.isna(val):
        return None
    return str(val)


def safe_int(val):
    """安全转为整数，NaN 返回 None"""
    if pd.isna(val):
        return None
    return int(val)


def safe_datetime(val):
    """安全转为 datetime，NaN 返回 None"""
    if pd.isna(val):
        return None
    return val.to_pydatetime()


def main():
    # 1. 连接 MySQL
    print("1/5 连接 MySQL...")
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    print("   ✓ MySQL 连接成功")

    # 2. 建表
    print("2/5 创建表...")
    cursor.execute(CREATE_SQL)
    conn.commit()
    print("   ✓ 表 `设备维修数据库` 已就绪")

    # 3. 清空旧数据（powerbi 用户无 DROP 权限，用 DELETE）
    print("3/5 清空旧数据...")
    cursor.execute("DELETE FROM `设备维修数据库`")
    conn.commit()
    print("   ✓ 旧数据已清除")

    # 4. 读取 Excel
    print("4/5 读取 Excel 数据...")
    df = pd.read_excel(EXCEL_PATH)
    print(f"   共 {len(df)} 条记录")

    # 5. 逐行插入
    print("5/5 迁移数据...")
    total = len(df)
    for idx, row in df.iterrows():
        vals = (
            safe_int(row.get("ID")),
            safe_str(row.get("设备名称")),
            safe_str(row.get("设备编号")),
            safe_str(row.get("机器故障类别")),
            safe_str(row.get("机器故障类别明细")),
            safe_str(row.get("故障现象描述")),
            safe_str(row.get("故障可能导致的产品不良描述")),
            safe_str(row.get("故障根本原因分析")),
            safe_str(row.get("维修采取措施")),
            safe_str(row.get("预防改进措施")),
            safe_int(row.get("维修时长(分钟)")),
            safe_str(row.get("维修技术员")),
            safe_datetime(row.get("提交时间")),
            safe_str(row.get("Item Type")),
            safe_str(row.get("Path")),
        )
        cursor.execute(INSERT_SQL, vals)
        if (idx + 1) % 100 == 0:
            conn.commit()
            print(f"   已插入 {idx + 1}/{total} 条...")

    conn.commit()
    print(f"   ✓ 迁移完成！共插入 {total} 条记录")

    # ── 验证 ──
    cursor.execute("SELECT COUNT(*) FROM `设备维修数据库`")
    db_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT `设备名称`) FROM `设备维修数据库`")
    eq_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT `机器故障类别`) FROM `设备维修数据库`")
    cat_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT `维修技术员`) FROM `设备维修数据库`")
    tech_count = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(`提交时间`), MAX(`提交时间`) FROM `设备维修数据库`")
    dates = cursor.fetchone()

    print("\n" + "=" * 50)
    print("  迁移结果验证")
    print("=" * 50)
    print(f"  总记录数:    {db_count}")
    print(f"  设备数:      {eq_count}")
    print(f"  故障类别:    {cat_count}")
    print(f"  技术员:      {tech_count}")
    print(f"  时间范围:    {str(dates[0])[:10]} ~ {str(dates[1])[:10]}")
    print("=" * 50)

    cursor.close()
    conn.close()
    print("\n✓ 连接已关闭，迁移完成！")


if __name__ == "__main__":
    main()
