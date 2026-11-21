import argparse, json, sys
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

CENT = Decimal("0.01")
QTY_Q = Decimal("0.001")
RECONCILE_ONLY_TAGS = ("الفيوم قديم", "fayoum_old")
CONSIGNMENT_TAGS = ("تحت التصريف", "consignment")


def extract_net_and_vat_from_public_price(public_price: Any, vat_rate: Any) -> Tuple[Decimal, Decimal]:
    pub = Decimal(str(public_price))
    vr = Decimal(str(vat_rate))
    if vr == 0:
        return pub.quantize(CENT, ROUND_HALF_UP), Decimal("0.00")
    net = (pub / (Decimal("1") + vr / Decimal("100"))).quantize(CENT, ROUND_HALF_UP)
    vat = (pub - net).quantize(CENT, ROUND_HALF_UP)
    return net, vat


def _contains_tag(value: Any, tags: Tuple[str, ...]) -> bool:
    if not value:
        return False
    s = str(value)
    return any(t in s for t in tags)


def _ar_amount(row: Dict[str, Any]) -> Decimal:
    for key in ("amount", "store_balance", "grid_balance"):
        if key in row and row[key] is not None:
            return Decimal(str(row[key]))
    return Decimal("0")


def validate_and_plan(
    packet: Dict[str, Any],
    *,
    official_codes: List[str] | None,
    cutoff_date: date,
) -> Dict[str, Any]:
    required = ("branches", "territories", "warehouses", "products", "customers", "opening_stock", "opening_ar")
    for sec in required:
        if sec not in packet:
            raise ValueError(f"Missing required section: {sec}")

    exceptions: List[Dict[str, Any]] = []

    if official_codes is not None:
        for cust in packet["customers"]:
            if cust.get("code") not in official_codes:
                exceptions.append({"kind": "unapproved_code", "entity": "customer", "code": cust.get("code")})
        for prod in packet["products"]:
            if prod.get("sku") not in official_codes:
                exceptions.append({"kind": "unapproved_code", "entity": "product", "code": prod.get("sku")})

    for row in packet["opening_ar"]:
        sb = row.get("store_balance")
        gb = row.get("grid_balance")
        if sb is not None and gb is not None:
            if Decimal(str(sb)) != Decimal(str(gb)):
                delta = (Decimal(str(sb)) - Decimal(str(gb))).quantize(CENT)
                exceptions.append(
                    {
                        "kind": "store_grid_conflict",
                        "customer_code": row.get("customer_code"),
                        "store_balance": str(sb),
                        "grid_balance": str(gb),
                        "delta": str(delta),
                    }
                )

    active_ar_total = Decimal("0")
    reconcile_only_ar_total = Decimal("0")
    active_ar_rows: List[Dict[str, Any]] = []
    reconcile_only_ar_rows: List[Dict[str, Any]] = []
    for row in packet["opening_ar"]:
        is_reconcile = bool(row.get("reconcile_only"))
        for field in ("account_tag", "branch_code", "name_ar"):
            if _contains_tag(row.get(field), RECONCILE_ONLY_TAGS):
                is_reconcile = True
                break
        if not is_reconcile:
            cust = next((c for c in packet["customers"] if c.get("code") == row.get("customer_code")), {})
            if cust.get("reconcile_only") or _contains_tag(cust.get("name_ar"), RECONCILE_ONLY_TAGS):
                is_reconcile = True
        amt = _ar_amount(row)
        if is_reconcile:
            reconcile_only_ar_total += amt
            reconcile_only_ar_rows.append(row)
        else:
            active_ar_total += amt
            active_ar_rows.append(row)

    warehouse_stock_qty = Decimal("0")
    customer_held_qty = Decimal("0")
    opening_stock_rows: List[Dict[str, Any]] = []
    customer_held_stock_rows: List[Dict[str, Any]] = []
    for row in packet["opening_stock"]:
        qty = Decimal(str(row.get("quantity", 0)))
        is_consignment = bool(row.get("consignment"))
        for field in ("custody", "warehouse_tag"):
            if _contains_tag(row.get(field), CONSIGNMENT_TAGS):
                is_consignment = True
                break
        if is_consignment:
            customer_held_qty += qty
            customer_held_stock_rows.append(row)
        else:
            warehouse_stock_qty += qty
            opening_stock_rows.append(row)

    summary = {
        "active_ar_total": f"{active_ar_total.quantize(CENT):.2f}",
        "reconcile_only_ar_total": f"{reconcile_only_ar_total.quantize(CENT):.2f}",
        "warehouse_stock_qty": f"{warehouse_stock_qty.quantize(QTY_Q):.3f}",
        "customer_held_qty": f"{customer_held_qty.quantize(QTY_Q):.3f}",
    }

    return {
        "exceptions": exceptions,
        "summary": summary,
        "active_ar_rows": active_ar_rows,
        "reconcile_only_ar_rows": reconcile_only_ar_rows,
        "opening_stock_rows": opening_stock_rows,
        "customer_held_stock_rows": customer_held_stock_rows,
    }


def _upsert_master(
    db: Connection,
    table: str,
    cols: List[str],
    values: Tuple[Any, ...],
    conflict_cols: List[str],
) -> str:
    sel = f"SELECT id FROM {table} WHERE " + " AND ".join([f"{c}=:{c}" for c in conflict_cols])
    sel_params = dict(zip(conflict_cols, [values[cols.index(c)] for c in conflict_cols]))
    res = db.execute(text(sel), sel_params).fetchone()
    if res:
        return str(res[0])
    col_list = ", ".join(cols)
    ph = ", ".join([f":{c}" for c in cols])
    stmt = f"""
        INSERT INTO {table} ({col_list})
        VALUES ({ph})
        RETURNING id
    """
    res = db.execute(text(stmt), dict(zip(cols, values))).fetchone()
    return str(res[0]) if res else ""


def run_reconcile(
    db: Connection,
    packet: Dict[str, Any],
    *,
    official_codes: List[str] | None = None,
    cutoff_date: date,
    apply: bool = False,
    actor_user_id: str | None = None,
) -> Dict[str, Any]:
    plan = validate_and_plan(packet, official_codes=official_codes, cutoff_date=cutoff_date)
    if plan["exceptions"]:
        db.rollback()
        return {
            "status": "REJECTED_EXCEPTIONS",
            "applied": False,
            "exceptions": plan["exceptions"],
            "summary": plan["summary"],
        }
    if not apply:
        return {
            "status": "DRY_RUN_OK",
            "applied": False,
            "exceptions": [],
            "summary": plan["summary"],
        }

    inserted = {"stock": 0, "held": 0, "ar": 0}
    skipped_idempotent = {"stock": 0, "held": 0, "ar": 0}

    try:
        # resolve actor
        if actor_user_id:
            actor_id = actor_user_id
        else:
            sql = "SELECT id FROM platform.platform_user WHERE is_active AND is_owner LIMIT 1"
            actor_id = str(db.execute(text(sql)).scalar())

        # upsert master data
        branch_ids = {}
        for b in packet["branches"]:
            branch_ids[b["code"]] = _upsert_master(
                db,
                "master_data.master_branch",
                ["code", "name_ar", "name_en"],
                (b["code"], b.get("name_ar"), b.get("name_en")),
                ["code"],
            )
        territory_ids = {}
        for t in packet["territories"]:
            territory_ids[t["code"]] = _upsert_master(
                db,
                "master_data.master_territory",
                ["code", "name_ar", "name_en"],
                (t["code"], t.get("name_ar"), t.get("name_en")),
                ["code"],
            )
        warehouse_ids = {}
        for w in packet["warehouses"]:
            branch_id = branch_ids.get(w["branch_code"])
            warehouse_ids[w["code"]] = _upsert_master(
                db,
                "master_data.master_warehouse",
                ["code", "name_ar", "name_en", "branch_id", "is_active"],
                (w["code"], w.get("name_ar"), w.get("name_en"), branch_id, w.get("is_active", True)),
                ["code"],
            )
        product_ids = {}
        for p in packet["products"]:
            net, _ = extract_net_and_vat_from_public_price(p["public_price"], p["vat_rate"])
            product_ids[p["sku"]] = _upsert_master(
                db,
                "master_data.master_product",
                ["sku", "name_ar", "name_en", "base_price", "vat_rate", "is_active"],
                (p["sku"], p.get("name_ar"), p.get("name_en"), net, p["vat_rate"], p.get("is_active", True)),
                ["sku"],
            )
        customer_ids = {}
        for c in packet["customers"]:
            branch_id = branch_ids.get(c["branch_code"])
            territory_id = territory_ids.get(c["territory_code"])
            customer_ids[c["code"]] = _upsert_master(
                db,
                "master_data.master_customer",
                ["code", "name_ar", "name_en", "branch_id", "territory_id", "is_active"],
                (
                    c["code"],
                    c.get("name_ar"),
                    c.get("name_en"),
                    branch_id,
                    territory_id,
                    c.get("is_active", True),
                ),
                ["code"],
            )

        # opening stock (warehouse saleable only)
        for row in plan["opening_stock_rows"]:
            wh_code = row["warehouse_code"]
            sku = row["sku"]
            qty = Decimal(str(row.get("quantity", 0)))
            note = f"C9-OPEN:{cutoff_date.isoformat()}:{wh_code}:{sku}"
            exists = db.execute(
                text("SELECT 1 FROM inventory.stock_movement WHERE note = :note LIMIT 1"), {"note": note}
            ).scalar()
            if exists:
                skipped_idempotent["stock"] += 1
                continue
            wh_id = warehouse_ids[wh_code]
            prod_id = product_ids[sku]
            db.execute(
                text(
                    """
                    INSERT INTO inventory.stock_movement
                    (warehouse_id, product_id, batch_id, movement_type, quantity, note, created_by)
                    VALUES (:w, :p, NULL, 'opening', :q, :note, :actor)
                    """
                ),
                {"w": wh_id, "p": prod_id, "q": str(qty), "note": note, "actor": actor_id},
            )
            # upsert balance
            bal = db.execute(
                text(
                    """
                    SELECT id, quantity FROM inventory.stock_balance
                    WHERE warehouse_id=:w AND product_id=:p AND batch_id IS NULL
                    """
                ),
                {"w": wh_id, "p": prod_id},
            ).fetchone()
            if bal:
                new_qty = Decimal(str(bal.quantity)) + qty
                db.execute(
                    text(
                        """
                        UPDATE inventory.stock_balance SET quantity=:q WHERE id=:id
                        """
                    ),
                    {"q": str(new_qty.quantize(QTY_Q)), "id": bal.id},
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO inventory.stock_balance
                        (warehouse_id, product_id, batch_id, quantity)
                        VALUES (:w, :p, NULL, :q)
                        """
                    ),
                    {"w": wh_id, "p": prod_id, "q": str(qty.quantize(QTY_Q))},
                )
            inserted["stock"] += 1

        # customer held stock (consignment)
        for row in plan["customer_held_stock_rows"]:
            cust_code = row["customer_code"]
            sku = row["sku"]
            qty = Decimal(str(row.get("quantity", 0)))
            cust_id = customer_ids[cust_code]
            prod_id = product_ids[sku]
            res = db.execute(
                text(
                    """
                    INSERT INTO sales.customer_held_stock
                    (customer_id, product_id, batch_id, quantity_on_hand, updated_at)
                    VALUES (:c, :p, NULL, :q, now())
                    ON CONFLICT ON CONSTRAINT uq_customer_held_stock_tuple DO NOTHING
                    RETURNING id
                    """
                ),
                {"c": cust_id, "p": prod_id, "q": str(qty.quantize(QTY_Q))},
            ).fetchone()
            if res:
                inserted["held"] += 1
            else:
                skipped_idempotent["held"] += 1

        # AR entries (active only; reconcile-only excluded per Eli A4)
        for row in plan["active_ar_rows"]:
            cust_code = row["customer_code"]
            amt = _ar_amount(row)
            note = f"C9-AR-OPEN:{cutoff_date.isoformat()}:{cust_code}"
            exists = db.execute(
                text("SELECT 1 FROM finance.ar_entry WHERE note = :note LIMIT 1"), {"note": note}
            ).scalar()
            if exists:
                skipped_idempotent["ar"] += 1
                continue
            cust_id = customer_ids[cust_code]
            debit = amt if amt > 0 else Decimal("0")
            credit = -amt if amt < 0 else Decimal("0")
            db.execute(
                text(
                    """
                    INSERT INTO finance.ar_entry
                    (customer_id, entry_type, entry_date, debit, credit, note, created_by)
                    VALUES (:c, 'opening', :d, :debit, :credit, :note, :actor)
                    """
                ),
                {
                    "c": cust_id,
                    "d": cutoff_date,
                    "debit": str(debit.quantize(CENT)),
                    "credit": str(credit.quantize(CENT)),
                    "note": note,
                    "actor": actor_id,
                },
            )
            inserted["ar"] += 1

        # reconciliation check
        ar_actual = Decimal(
            str(
                db.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(debit - credit), 0)
                        FROM finance.ar_entry
                        WHERE note LIKE :p
                        """
                    ),
                    {"p": f"C9-AR-OPEN:{cutoff_date.isoformat()}:%"},
                ).scalar()
            )
        ).quantize(CENT)
        stock_actual = Decimal(
            str(
                db.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(quantity), 0)
                        FROM inventory.stock_movement
                        WHERE note LIKE :p
                        """
                    ),
                    {"p": f"C9-OPEN:{cutoff_date.isoformat()}:%"},
                ).scalar()
            )
        ).quantize(QTY_Q)

        ar_expected = Decimal(plan["summary"]["active_ar_total"])
        stock_expected = Decimal(plan["summary"]["warehouse_stock_qty"])
        ar_delta = (ar_actual - ar_expected).quantize(CENT)
        stock_delta = (stock_actual - stock_expected).quantize(QTY_Q)

        if ar_delta != Decimal("0.00") or stock_delta != Decimal("0.000"):
            db.rollback()
            raise RuntimeError(
                f"Reconciliation mismatch: AR delta {ar_delta}, Stock delta {stock_delta}"
            )

        db.commit()
        return {
            "status": "APPLIED_RECONCILED",
            "applied": True,
            "inserted": inserted,
            "skipped_idempotent": skipped_idempotent,
            "reconciliation": {
                "ar_expected": plan["summary"]["active_ar_total"],
                "ar_actual": f"{ar_actual:.2f}",
                "ar_delta": f"{ar_delta:.2f}",
                "stock_expected": plan["summary"]["warehouse_stock_qty"],
                "stock_actual": f"{stock_actual:.3f}",
                "stock_delta": f"{stock_delta:.3f}",
                "reconcile_only_ar_total": plan["summary"]["reconcile_only_ar_total"],
                "customer_held_qty": plan["summary"]["customer_held_qty"],
            },
            "summary": plan["summary"],
        }
    except Exception:
        db.rollback()
        raise


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, help="Path to JSON packet")
    parser.add_argument("--cutoff-date", required=True, help="Cutoff date YYYY-MM-DD")
    parser.add_argument("--official-codes", help="Comma separated list of approved codes")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--actor-user-id", help="Actor user UUID")
    args = parser.parse_args(argv)

    with open(args.packet, "r", encoding="utf-8") as f:
        packet = json.load(f)

    cutoff = datetime.strptime(args.cutoff_date, "%Y-%m-%d").date()
    official_codes = args.official_codes.split(",") if args.official_codes else None

    # obtain a DB connection (placeholder – replace with actual engine)
    engine: Engine = ...  # type: ignore
    with engine.begin() as conn:
        result = run_reconcile(
            conn,
            packet,
            official_codes=official_codes,
            cutoff_date=cutoff,
            apply=args.apply,
            actor_user_id=args.actor_user_id,
        )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
