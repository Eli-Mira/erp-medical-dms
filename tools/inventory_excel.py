#!/usr/bin/env python3
"""
Phase 0 - Excel structural inventory for the Medical Company System.

READ-ONLY. Never writes to the source workbooks.

Produces:
  docs/inventory.json    - full machine-readable inventory
  docs/inventory_raw.md  - human-readable summary

Usage:
  python tools/inventory_excel.py
  python tools/inventory_excel.py --root "C:\\Desktop\\Huge system"
"""

import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import openpyxl
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_HEADER_ROWS = 8
MAX_SAMPLE_COLS = 40
SAMPLE_VALUES_PER_COL = 6
MAX_HEADER_COL_SAMPLES = 8
MAX_FORMULA_SAMPLES = 5
MAX_MERGED_SAMPLES = 8
MAX_VALIDATION_SAMPLES = 12


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cell_kind(v) -> str:
    if v is None:
        return "blank"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, datetime):
        return "datetime"
    s = str(v)
    if s.startswith("="):
        return "formula"
    return "text"


def scan_sheet(ws) -> dict:
    """Aggregate a sheet without storing all values (memory-bounded)."""
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    ncols = min(max_col, MAX_SAMPLE_COLS)

    col_stats = [
        {"col": get_column_letter(c + 1), "nonempty": 0, "number": 0, "text": 0,
         "datetime": 0, "formula": 0, "samples": [], "distinct": set()}
        for c in range(ncols)
    ]
    header_rows = []
    formula_samples = []
    formula_total = 0
    nonempty_rows = 0
    first_data_samples = []

    r = 0
    for row in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col, values_only=False):
        r += 1
        row_has = False
        for c, cell in enumerate(row):
            if c >= ncols:
                break
            v = cell.value
            if v is None or (isinstance(v, str) and v.strip() == ""):
                continue
            row_has = True
            st = col_stats[c]
            st["nonempty"] += 1
            kind = cell_kind(v)
            if kind == "number":
                st["number"] += 1
            elif kind == "datetime":
                st["datetime"] += 1
            elif kind == "formula":
                st["formula"] += 1
                formula_total += 1
                if len(formula_samples) < MAX_FORMULA_SAMPLES:
                    formula_samples.append({"cell": f"{get_column_letter(c+1)}{r}", "formula": str(v)[:200]})
            else:
                st["text"] += 1
            if len(st["samples"]) < SAMPLE_VALUES_PER_COL:
                sv = str(v)[:60]
                if sv not in st["samples"]:
                    st["samples"].append(sv)
            if len(st["distinct"]) < 200:
                st["distinct"].add(str(v)[:60])
        if row_has:
            nonempty_rows += 1
        if r <= MAX_HEADER_ROWS:
            header_rows.append([("" if c.value is None else str(c.value)[:40]) for c in row[:ncols]])
        if len(first_data_samples) < 4 and row_has and r > MAX_HEADER_ROWS:
            first_data_samples.append([("" if c.value is None else str(c.value)[:40]) for c in row[:ncols]])

    for st in col_stats:
        st["distinct_count"] = len(st["distinct"])
        del st["distinct"]

    try:
        merged = list(ws.merged_cells.ranges) if ws.merged_cells else []
    except Exception:
        merged = []
    validations = []
    try:
        for dv in (ws.data_validations.dataValidation or []):
            if len(validations) < MAX_VALIDATION_SAMPLES:
                validations.append({
                    "type": dv.type,
                    "sqref": str(dv.sqref),
                    "formula1": None if dv.formula1 is None else str(dv.formula1)[:120],
                })
    except Exception:
        pass

    return {
        "title": ws.title,
        "state": ws.sheet_state,
        "max_row": max_row,
        "max_col": max_col,
        "nonempty_rows": nonempty_rows,
        "has_formulas": formula_total > 0,
        "formula_total": formula_total,
        "formula_samples": formula_samples,
        "header_rows_sample": header_rows,
        "first_data_rows_sample": first_data_samples,
        "columns": col_stats,
        "merged_count": len(merged),
        "merged_samples": [str(m) for m in merged[:MAX_MERGED_SAMPLES]],
        "data_validations": validations,
    }


def scan_workbook(path: str) -> dict:
    name = os.path.basename(path)
    info = {"file": name, "size_bytes": os.path.getsize(path), "sha256": sha256(path)}
    print(f"  loading {name} ...", flush=True)
    wb = openpyxl.load_workbook(path, read_only=False, data_only=False, keep_links=True)

    defined = []
    try:
        dn = wb.defined_names
        it = dn.values() if hasattr(dn, "values") else dn
        for d in it:
            defined.append({"name": getattr(d, "name", str(d)),
                            "value": str(getattr(d, "value", ""))[:160]})
    except Exception as e:
        defined.append({"error": str(e)})

    ext = []
    try:
        for el in getattr(wb, "_external_links", []):
            ext.append(str(el))
    except Exception:
        pass

    sheets = []
    for ws in wb.worksheets:
        print(f"    sheet: {ws.title}", flush=True)
        try:
            sheets.append(scan_sheet(ws))
        except Exception as e:
            sheets.append({"title": ws.title, "state": ws.sheet_state, "error": str(e)})

    wb.close()
    info["defined_names"] = defined
    info["external_links"] = ext
    info["sheet_count"] = len(sheets)
    info["sheets"] = sheets
    return info


def main():
    ap = argparse.ArgumentParser()
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--root", default=default_root)
    args = ap.parse_args()
    root = args.root
    docs = os.path.join(root, "docs")
    os.makedirs(docs, exist_ok=True)

    xlsx = sorted(glob.glob(os.path.join(root, "*.xlsx")))
    print(f"Found {len(xlsx)} workbooks in {root}", flush=True)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": root,
        "files": [],
    }
    for f in xlsx:
        result["files"].append(scan_workbook(f))

    out = os.path.join(docs, "inventory.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print(f"\nWROTE {out}", flush=True)


if __name__ == "__main__":
    main()
