"""B1 dry run: read-only extraction of candidate master data from the 7 workbooks.

NO database writes. NO source-workbook writes. Reports counts, duplicates and
unresolved mappings only. Company records are never persisted to Git.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "b1_dry_run_20261019")
os.makedirs(OUT, exist_ok=True)

SALES_WBS = sorted(glob.glob("مبيعات *2026.xlsx"))
FINANCE_WB = "الميزانية العمومية 2026.xlsx"
EXCLUDE_SHEETS = {"الرئيسية", "رصيد الارصدة المباعة", "كامل الكمية", "تحت التصريف"}


def norm(s):
    return " ".join(str(s).split()).strip().lower()


def extract_branches():
    # one candidate per sales workbook (workbook name -> branch). Unambiguous count.
    return [{"source": os.path.basename(f)} for f in SALES_WBS]


def extract_warehouses():
    # per-workbook warehouse-sheet candidates (names). Ambiguity: sheet may be
    # a company warehouse OR a customer-held stock location. Report counts only.
    per_wb = {}
    all_names = []
    for f in SALES_WBS:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        wh = [s for s in wb.sheetnames if s not in EXCLUDE_SHEETS]
        per_wb[os.path.basename(f)] = len(wh)
        all_names.extend(wh)
    c = Counter(norm(n) for n in all_names)
    dupes = {k: v for k, v in c.items() if v > 1}
    return per_wb, len(all_names), len(c), len(dupes)


def extract_products():
    names = set()
    per_wb = {}
    for f in SALES_WBS:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb["كامل الكمية"]
        cnt = 0
        for row in ws.iter_rows(min_row=2):
            v = row[0].value
            if isinstance(v, str) and v.strip():
                names.add(v.strip())
                cnt += 1
        per_wb[os.path.basename(f)] = cnt
    # common across all workbooks
    sets = []
    for f in SALES_WBS:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb["كامل الكήμ"] if False else wb["كامل الكمية"]
        s = set()
        for row in ws.iter_rows(min_row=2):
            v = row[0].value
            if isinstance(v, str) and v.strip():
                s.add(v.strip())
        sets.append(s)
    common = set.intersection(*sets) if sets else set()
    return len(names), len(common), per_wb


def extract_customers_and_territories():
    wb = openpyxl.load_workbook(FINANCE_WB, read_only=True, data_only=True)
    ws = wb["العملاء"]
    names = []
    for c in range(4, ws.max_column + 1, 6):
        v = ws.cell(row=2, column=c).value
        if isinstance(v, str) and v.strip():
            names.append(v.strip())
    # territory/branch hints: column 3 of each block row 2 (external ref) —
    # often a sheet-name reference like 'مخزن اشرف المنزلة'!A1
    refs = []
    for c in range(4, ws.max_column + 1, 6):
        v = ws.cell(row=2, column=c - 1).value
        if v is not None:
            refs.append(str(v)[:60])
    return len(names), len(set(refs))


def main():
    branches = extract_branches()
    wh_per_wb, wh_total, wh_unique, wh_dupes = extract_warehouses()
    prod_unique, prod_common, _pp = extract_products()
    cust_count, terr_ref_count = extract_customers_and_territories()

    report = {
        "source_workbooks": [os.path.basename(f) for f in SALES_WBS] + [FINANCE_WB],
        "source_counts": {
            "branches (sales workbooks)": len(branches),
            "warehouse_sheet_candidates (all sales wbs, includes customer-held stock)": wh_total,
            "warehouse_sheet_unique_names": wh_unique,
            "warehouse_sheet_duplicate_names": wh_dupes,
            "products (union across workbooks)": prod_unique,
            "products (common to all 5 workbooks)": prod_common,
            "customers (AR customer blocks)": cust_count,
            "territory_branch_refs_in_AR_header": terr_ref_count,
        },
        "per_workbook_warehouses": wh_per_wb,
        "per_workbook_products": None,
        "unresolved_mappings": [
            "Customer -> branch/territory: AR sheet customer blocks reference warehouse sheets; mapping not explicit. Needs owner confirmation of key.",
            "Warehouse sheet vs customer-held stock location: 291 candidate sheets include both company warehouses and customer/pharmacy stock locations. Distinction not unambiguous from sheet names alone.",
            "Product identity across workbooks: 10 common names + 5 workbook-specific. Whether these are the same SKU or branch-specific items is unverified.",
            "Territory assignment: no explicit territory column found in AR header; inferred from sheet references only.",
            "UOM: discovery-gated (UQ-6); no conversion applied.",
        ],
        "duplicates": {
            "warehouse_sheet_name_duplicates": wh_dupes,
        },
        "rejected_records": [],
        "db_writes": "NONE (dry run; no DB created or modified)",
        "source_file_writes": "NONE",
    }
    # per-workbook product counts
    prod_per = {}
    for f in SALES_WBS:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb["كامل الكمية"]
        cnt = sum(1 for row in ws.iter_rows(min_row=2) if isinstance(row[0].value, str) and row[0].value.strip())
        prod_per[os.path.basename(f)] = cnt
    report["per_workbook_products"] = prod_per

    out_path = os.path.join(OUT, "b1_dry_run_summary.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
