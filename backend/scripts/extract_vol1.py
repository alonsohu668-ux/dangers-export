"""
从 Vol.1 PDF 提取危险货物一览表数据（3.2章）
输出 CSV: un_number, name_en, class_or_division, subsidiary_hazard, packing_group,
        special_provisions, limited_quantity, excepted_quantity,
        packing_instructions, special_packing_provisions,
        tank_bulk_instructions, tank_special_provisions, source_page
"""
import pdfplumber
import csv
import re
import os

PDF_PATH = os.environ.get("VOL1_PDF", "/workspace/projects/media/inbound/ST-SG-AC10-1r23c_Vol1_WEB_1---cc02dce4-929a-4c90-a6ef-66173f966130.pdf")
OUTPUT_PATH = os.environ.get("OUTPUT_CSV", "/workspace/projects/dangerous-goods-compliance/data/extracted_csv/goods_vol1.csv")

# 3.2 chapter table spans pages 166-371 in Vol.1 (0-indexed: 165-370)
TABLE_START = 165
TABLE_END = 371


def clean_cell(cell):
    """Remove CID codes and clean up text"""
    if not cell:
        return ""
    # Remove (cid:xxxxx) patterns
    cleaned = re.sub(r'\(cid:\d+\)', '', cell)
    # Remove copyright watermark
    cleaned = cleaned.replace("联合国版权©，2023 年。版权所有。", "")
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def extract_goods_table():
    pdf = pdfplumber.open(PDF_PATH)
    all_rows = []
    seen_un = set()

    for page_idx in range(TABLE_START, min(TABLE_END, len(pdf.pages))):
        page = pdf.pages[page_idx]
        tables = page.extract_tables()
        page_num = page_idx + 1

        for table in tables:
            for row in table:
                if not row or not row[0]:
                    continue
                un_num = clean_cell(row[0]).strip()

                # Skip non-UN rows (headers, sub-headers, page numbers)
                if not un_num.isdigit():
                    continue
                if un_num in seen_un:
                    # Allow duplicates (same UN with different packing groups)
                    pass
                else:
                    seen_un.add(un_num)

                # Extract columns: (1)UN (2)Name (3)Class (4)Sub (5)PG (6)SP (7a)LQ (7b)EQ (8)PI (9)SPP (10)TBI (11)TSP
                name_en = clean_cell(row[1]) if len(row) > 1 else ""
                class_div = clean_cell(row[2]) if len(row) > 2 else ""
                sub_hazard = clean_cell(row[3]) if len(row) > 3 else ""
                packing_group = clean_cell(row[4]) if len(row) > 4 else ""
                special_prov = clean_cell(row[5]) if len(row) > 5 else ""
                limited_qty = clean_cell(row[6]) if len(row) > 6 else ""
                excepted_qty = clean_cell(row[7]) if len(row) > 7 else ""
                packing_instr = clean_cell(row[8]) if len(row) > 8 else ""
                special_packing = clean_cell(row[9]) if len(row) > 9 else ""
                tank_instr = clean_cell(row[10]) if len(row) > 10 else ""
                tank_special = clean_cell(row[11]) if len(row) > 11 else ""

                all_rows.append({
                    "un_number": un_num,
                    "name_en": name_en,
                    "class_or_division": class_div,
                    "subsidiary_hazard": sub_hazard,
                    "packing_group": packing_group,
                    "special_provisions": special_prov,
                    "limited_quantity": limited_qty,
                    "excepted_quantity": excepted_qty,
                    "packing_instructions": packing_instr,
                    "special_packing_provisions": special_packing,
                    "tank_bulk_instructions": tank_instr,
                    "tank_special_provisions": tank_special,
                    "source_page": page_num
                })

    pdf.close()
    return all_rows


def main():
    print(f"Extracting from: {PDF_PATH}")
    print(f"Output to: {OUTPUT_PATH}")

    rows = extract_goods_table()
    print(f"Extracted {len(rows)} UN number entries")

    # Write CSV
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    fieldnames = [
        "un_number", "name_en", "class_or_division", "subsidiary_hazard",
        "packing_group", "special_provisions", "limited_quantity",
        "excepted_quantity", "packing_instructions", "special_packing_provisions",
        "tank_bulk_instructions", "tank_special_provisions", "source_page"
    ]
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV written: {OUTPUT_PATH}")

    # Stats
    unique_un = set(r["un_number"] for r in rows)
    classes = set(r["class_or_division"] for r in rows if r["class_or_division"])
    print(f"Unique UN numbers: {len(unique_un)}")
    print(f"Classes: {sorted(classes)}")

    # Show sample
    print("\nSample entries:")
    for r in rows[:3]:
        print(f"  UN{r['un_number']}: class={r['class_or_division']}, SP={r['special_provisions'][:30]}, PI={r['packing_instructions'][:30]}")


if __name__ == "__main__":
    main()
