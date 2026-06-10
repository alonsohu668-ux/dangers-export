"""
Dangerous Goods Compliance System - Database Models & Setup
SQLite database with 3 tables: dangerous_goods, regulations, source_references
"""
import sqlite3
import csv
import os
import json

DB_PATH = os.environ.get("DB_PATH", "/workspace/projects/dangerous-goods-compliance/data/compliance.db")
DATA_DIR = os.environ.get("DATA_DIR", "/workspace/projects/dangerous-goods-compliance/data/extracted_csv")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if not exist"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dangerous_goods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        un_number TEXT UNIQUE NOT NULL,
        name_en TEXT DEFAULT '',
        name_cn TEXT DEFAULT '',
        class_or_division TEXT DEFAULT '',
        subsidiary_hazard TEXT DEFAULT '',
        packing_group TEXT DEFAULT '',
        special_provisions TEXT DEFAULT '',
        limited_quantity TEXT DEFAULT '',
        excepted_quantity TEXT DEFAULT '',
        packing_instructions TEXT DEFAULT '',
        special_packing_provisions TEXT DEFAULT '',
        tank_bulk_instructions TEXT DEFAULT '',
        tank_special_provisions TEXT DEFAULT '',
        source_page INTEGER,
        reviewed INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS regulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        rule_type TEXT NOT NULL,
        title_en TEXT DEFAULT '',
        title_cn TEXT DEFAULT '',
        summary_en TEXT DEFAULT '',
        summary_cn TEXT DEFAULT '',
        original_text TEXT DEFAULT '',
        key_points TEXT DEFAULT '[]',
        source_volume TEXT DEFAULT '',
        source_page INTEGER,
        source_section TEXT DEFAULT '',
        reviewed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_code TEXT NOT NULL,
        volume TEXT DEFAULT '',
        page_number INTEGER,
        section_number TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_un ON dangerous_goods(un_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_class ON dangerous_goods(class_or_division)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regs_code ON regulations(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regs_type ON regulations(rule_type)")

    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")


def import_goods_csv(csv_path=None):
    """Import Vol.1 extracted goods data"""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "goods_vol1.csv")

    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize special_provisions: convert "188 230 310" to "188|230|310"
            sp = row.get('special_provisions', '').strip()
            sp_normalized = '|'.join(sp.split()) if sp else ''

            # Normalize packing_instructions
            pi = row.get('packing_instructions', '').strip()
            pi_normalized = '|'.join(pi.split()) if pi else ''

            spi = row.get('special_packing_provisions', '').strip()
            spi_normalized = '|'.join(spi.split()) if spi else ''

            tbi = row.get('tank_bulk_instructions', '').strip()
            tbi_normalized = '|'.join(tbi.split()) if tbi else ''

            tsp = row.get('tank_special_provisions', '').strip()
            tsp_normalized = '|'.join(tsp.split()) if tsp else ''

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO dangerous_goods
                    (un_number, name_en, class_or_division, subsidiary_hazard,
                     packing_group, special_provisions, limited_quantity,
                     excepted_quantity, packing_instructions, special_packing_provisions,
                     tank_bulk_instructions, tank_special_provisions, source_page)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['un_number'], row['name_en'], row['class_or_division'],
                    row['subsidiary_hazard'], row['packing_group'],
                    sp_normalized, row['limited_quantity'], row['excepted_quantity'],
                    pi_normalized, spi_normalized, tbi_normalized, tsp_normalized,
                    int(row['source_page']) if row['source_page'].isdigit() else None
                ))
                count += 1
            except Exception as e:
                print(f"  Error importing UN{row['un_number']}: {e}")

    conn.commit()
    conn.close()
    print(f"Imported {count} goods entries from {csv_path}")
    return count


def import_manual_cn(csv_path=None):
    """Import manually created Chinese data (name_cn, reviewed status)"""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "..", "manual_cn", "goods_cn.csv")

    if not os.path.exists(csv_path):
        print(f"No manual CN data found at {csv_path}")
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                UPDATE dangerous_goods
                SET name_cn = ?, reviewed = 1
                WHERE un_number = ?
            """, (row.get('name_cn', ''), row['un_number']))
            if cursor.rowcount > 0:
                count += 1

    conn.commit()
    conn.close()
    print(f"Updated {count} entries with Chinese names")
    return count


def seed_regulations():
    """Seed lithium battery related regulations as initial data"""
    conn = get_connection()
    cursor = conn.cursor()

    regulations = [
        # Special Provisions
        {
            "code": "188", "rule_type": "special_provision",
            "title_en": "Lithium cells and batteries transport exception",
            "title_cn": "小型锂/钠电池和电池组的运输例外条件",
            "summary_en": "Batteries meeting SP188 may be transported under exception conditions.",
            "summary_cn": "交付运输的电池和电池组，如满足SP188条件，可不受本规章其他规定限制。该条款重点用于判断小容量锂电池/钠电池是否可按例外条件运输。",
            "original_text": "",
            "key_points": json.dumps(["锂离子单电池额定值通常不得超过20Wh", "锂离子电池组额定值通常不得超过100Wh", "应标明Wh额定值", "需符合测试和质量要求", "应防止短路", "包装件需锂电池组标记", "包装件总重通常不超过30kg"]),
            "source_volume": "Vol.I", "source_page": 334, "source_section": "3.3",
        },
        {
            "code": "230", "rule_type": "special_provision",
            "title_en": "Temperature control requirements",
            "title_cn": "温度控制要求",
            "summary_en": "Must be transported under temperature control.",
            "summary_cn": "本物质运输时必须保持在控温条件下，以确保物质处于液态。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 335, "source_section": "3.3",
        },
        {
            "code": "310", "rule_type": "special_provision",
            "title_en": "Production batch and prototype batteries",
            "title_cn": "生产批量、试验或原型电池相关规定",
            "summary_cn": "适用于小批量生产或原型锂离子电池和钠离子电池的运输规定。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 336, "source_section": "3.3",
        },
        {
            "code": "348", "rule_type": "special_provision",
            "title_en": "Lithium battery Wh marking",
            "title_cn": "锂离子电池组Wh标记相关规定",
            "summary_cn": "要求在锂离子电池组外壳上标明Wh额定值。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 337, "source_section": "3.3",
        },
        {
            "code": "360", "rule_type": "special_provision",
            "title_en": "Lithium ion batteries installed in equipment",
            "title_cn": "安装在设备中的锂离子电池组规定",
            "summary_cn": "UN3481设备中含锂离子电池组的特殊运输规定。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 338, "source_section": "3.3",
        },
        {
            "code": "376", "rule_type": "special_provision",
            "title_en": "Damaged or defective batteries",
            "title_cn": "损坏或有缺陷电池组相关规定",
            "summary_cn": "损坏或有缺陷的锂离子电池和电池组有特殊包装和运输要求。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 339, "source_section": "3.3",
        },
        {
            "code": "377", "rule_type": "special_provision",
            "title_en": "Batteries for disposal or recycling",
            "title_cn": "待处理或回收电池组相关规定",
            "summary_cn": "待回收处理的锂离子电池和电池组的特殊运输要求。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 339, "source_section": "3.3",
        },
        {
            "code": "384", "rule_type": "special_provision",
            "title_en": "9A label/ marking requirements",
            "title_cn": "9A标签/标志相关规定",
            "summary_cn": "关于锂电池第9类标签和标记的特殊要求。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 340, "source_section": "3.3",
        },
        {
            "code": "387", "rule_type": "special_provision",
            "title_en": "Mixed lithium metal and lithium ion batteries",
            "title_cn": "同时含锂金属和锂离子电池的电池组规定",
            "summary_cn": "同时含锂金属和锂离子电池的电池组的特殊运输规定。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 340, "source_section": "3.3",
        },
        {
            "code": "390", "rule_type": "special_provision",
            "title_en": "Lithium ion batteries manufactured after certain date",
            "title_cn": "特定日期后制造的锂离子电池规定",
            "summary_cn": "2023年1月1日后制造的锂离子电池的附加要求。",
            "key_points": "[]", "source_volume": "Vol.I", "source_page": 340, "source_section": "3.3",
        },
        # Packing Instructions
        {
            "code": "P903", "rule_type": "packing_instruction",
            "title_en": "Packing for UN3090/3091/3480/3481/3551/3552",
            "title_cn": "常规电池包装指南",
            "summary_en": "General packing for lithium/sodium batteries.",
            "summary_cn": "适用于UN3090、3091、3480、3481、3551和3552。用于普通锂/钠电池、电池组、与设备一起包装或安装在设备中的场景。",
            "original_text": '在本包装指南中，"设备"是指以电池或电池组为工作电源的仪器。允许使用下列包装，但须符合4.1.1和4.1.3的一般规定。',
            "key_points": json.dumps(["电池或电池组应防止因包装内移动或位置变化而造成损坏", "包装应符合包装类别II的性能水平", "总质量12kg以上且具有坚固耐碰撞外壳的电池可采用坚固外包装", "设备应固定在外包装中防止运输中移动"]),
            "source_volume": "Vol.II", "source_page": 90, "source_section": "4.1.4",
        },
        {
            "code": "P908", "rule_type": "packing_instruction",
            "title_en": "Packing for damaged or defective batteries",
            "title_cn": "损坏或有缺陷电池/电池组包装指南",
            "summary_cn": "适用于运输损坏或有缺陷的UN3090、3091、3480、3481电池和电池组。",
            "key_points": "[]", "source_volume": "Vol.II", "source_page": 91, "source_section": "4.1.4",
        },
        {
            "code": "P909", "rule_type": "packing_instruction",
            "title_en": "Packing for disposal or recycling batteries",
            "title_cn": "待处理或回收电池/电池组包装指南",
            "summary_cn": "适用于运输待处理或回收的UN3090、3091、3480、3481电池和电池组。",
            "original_text": "允许使用规定的桶、箱、罐等包装，但须符合4.1.1和4.1.3的一般规定。包装应符合包装类别II的性能水平。金属包装应安装不导电衬里。",
            "key_points": json.dumps(["金属包装应安装不导电衬里如塑料衬里", "包装应符合包装类别II的性能水平", "小容量电池在满足条件时可使用最大30kg坚固外包装"]),
            "source_volume": "Vol.II", "source_page": 94, "source_section": "4.1.4",
        },
        {
            "code": "P910", "rule_type": "packing_instruction",
            "title_en": "Packing for prototype batteries",
            "title_cn": "小批量生产或原型电池包装指南",
            "summary_cn": "适用于小批量生产、试验或原型的锂离子电池和电池组。",
            "key_points": "[]", "source_volume": "Vol.II", "source_page": 95, "source_section": "4.1.4",
        },
        {
            "code": "P911", "rule_type": "packing_instruction",
            "title_en": "Packing for batteries in special condition",
            "title_cn": "特殊危险状态电池/电池组包装指南",
            "summary_cn": "适用于特殊危险状态的锂离子电池和电池组。",
            "key_points": "[]", "source_volume": "Vol.II", "source_page": 96, "source_section": "4.1.4",
        },
        # Large Packings
        {
            "code": "LP903", "rule_type": "large_packing",
            "title_en": "Large packing for UN3090/3091/3480/3481/3551/3552",
            "title_cn": "大型电池/大型电池组包装指南",
            "summary_cn": "适用于总质量大于500克的大电池、总质量大于12千克的大电池组，以及内含UN3090、3091、3480、3481、3551和3552大电池或电池组的设备。",
            "original_text": "允许使用符合包装类别II性能水平的硬质大型包装。电池、电池组或设备应置于内包装内或用托盘等方式隔开。需要防止运输中移动、接触、叠压造成损坏。应保护电池组防止短路。",
            "key_points": json.dumps(["允许使用包装类别II性能水平的硬质大型包装", "应置于内包装内或用托盘等隔开", "防止运输中移动和接触损坏", "保护电池组防止短路"]),
            "source_volume": "Vol.II", "source_page": 111, "source_section": "4.1.4",
        },
        {
            "code": "LP904", "rule_type": "large_packing",
            "title_cn": "损坏或有缺陷电池大型包装指南",
            "summary_cn": "适用于运输损坏或有缺陷的锂离子电池和电池组的大型包装规定。",
            "key_points": "[]", "source_volume": "Vol.II", "source_page": 112, "source_section": "4.1.4",
        },
        {
            "code": "LP905", "rule_type": "large_packing",
            "title_cn": "待处理/回收电池大型包装指南",
            "summary_cn": "适用于待回收处理的锂离子电池和电池组的大型包装规定。",
            "key_points": "[]", "source_volume": "Vol.II", "source_page": 113, "source_section": "4.1.4",
        },
        {
            "code": "LP906", "rule_type": "large_packing",
            "title_cn": "特殊电池大型包装指南",
            "summary_cn": "适用于特殊危险状态的锂离子电池和电池组的大型包装规定。",
            "key_points": "[]", "source_volume": "Vol.II", "source_page": 114, "source_section": "4.1.4",
        },
    ]

    count = 0
    for reg in regulations:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO regulations
                (code, rule_type, title_en, title_cn, summary_en, summary_cn,
                 original_text, key_points, source_volume, source_page, source_section,
                 reviewed)
                VALUES (:code, :rule_type, :title_en, :title_cn, :summary_en, :summary_cn,
                 :original_text, :key_points, :source_volume, :source_page, :source_section,
                 0)
            """, reg)
            count += 1
        except Exception as e:
            print(f"  Error importing {reg['code']}: {e}")

    conn.commit()
    conn.close()
    print(f"Seeded {count} regulations")
    return count


def seed_cn_names():
    """Seed Chinese names for lithium battery UN numbers"""
    cn_names = {
        "3480": "锂离子电池组（包括锂离子聚合物电池）",
        "3481": "装在设备中的锂离子电池组（包括锂离子聚合物电池）或同设备包装在一起的锂离子电池组",
        "3090": "锂金属电池组（包括锂合金电池组）",
        "3091": "装在设备中的锂金属电池组或同设备包装在一起的锂金属电池组",
        "1950": "气雾剂",
        "3551": "钠离子电池组（包括钠离子聚合物电池）",
        "3552": "装在设备中的钠离子电池组或同设备包装在一起的钠离子电池组",
    }

    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    for un, name in cn_names.items():
        cursor.execute("UPDATE dangerous_goods SET name_cn = ? WHERE un_number = ?", (name, un))
        if cursor.rowcount > 0:
            count += 1

    conn.commit()
    conn.close()
    print(f"Updated {count} entries with Chinese names")
    return count


def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    stats = {}
    cursor.execute("SELECT COUNT(*) FROM dangerous_goods")
    stats['total_goods'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM dangerous_goods WHERE name_cn != ''")
    stats['cn_named'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM regulations")
    stats['total_regs'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT class_or_division) FROM dangerous_goods")
    stats['classes'] = cursor.fetchone()[0]
    conn.close()
    return stats


if __name__ == "__main__":
    init_db()
    import_goods_csv()
    import_manual_cn()
    seed_regulations()
    seed_cn_names()
    stats = get_stats()
    print(f"\nDatabase stats: {stats}")
