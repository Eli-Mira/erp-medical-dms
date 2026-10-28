"""Management-summary figures from the real sales/AR/receipt ledgers.

Read-only; no new tables and no business policy beyond the already-approved
scoping model: owner/finance/read_only_auditor are global, sales managers and
district managers are restricted to their platform.user_territory grants
(mirroring GET /invoices). Drafts and reversed invoices never appear; voided
receipts are excluded; the alert counts reuse the approved cover report.
"""

from sqlalchemy import text

from app.inventory.service import cover_report
from app.settings import service as settings_service

GLOBAL_ROLES = {"owner", "finance", "read_only_auditor"}
SCOPED_ROLES = {"sales_manager", "district_manager"}


def territory_ids(db, user):
    """Territory grants for a non-global caller; None means unrestricted."""
    rows = db.execute(
        text("SELECT territory_id FROM platform.user_territory WHERE user_id = :uid"),
        {"uid": user["id"]},
    ).fetchall()
    return [row[0] for row in rows] or []


def _sales(db, as_of, territories):
    """Posted-only sales for the as-of date and its month to date."""
    clauses, params = "", {}
    if territories is not None:
        clauses = " AND i.territory_id = ANY(CAST(:territories AS uuid[]))"
        params["territories"] = [str(t) for t in territories]
    rows = (
        db.execute(
            text(
                "SELECT"
                " count(*) FILTER (WHERE i.invoice_date = :as_of) AS invoices_today,"
                " COALESCE(SUM(i.grand_total) FILTER (WHERE i.invoice_date = :as_of), 0.00) AS grand_today,"
                " COALESCE(SUM(i.total_net) FILTER (WHERE i.invoice_date = :as_of), 0.00) AS net_today,"
                " COALESCE(SUM(i.vat_amount) FILTER (WHERE i.invoice_date = :as_of), 0.00) AS vat_today,"
                " count(*) AS invoices_mtd,"
                " COALESCE(SUM(i.grand_total), 0.00) AS grand_mtd,"
                " COALESCE(SUM(i.total_net), 0.00) AS net_mtd,"
                " COALESCE(SUM(i.vat_amount), 0.00) AS vat_mtd"
                " FROM sales.sales_invoice i"
                " WHERE i.posting_status = 'Posted' AND i.posted_at IS NOT NULL"
                " AND i.invoice_date >= date_trunc('month', CAST(:as_of AS date))"
                " AND i.invoice_date <= :as_of" + clauses
            ),
            {"as_of": as_of, **params},
        )
        .mappings()
        .one()
    )
    return {
        "invoices_today": int(rows["invoices_today"]),
        "grand_total_today": rows["grand_today"],
        "net_today": rows["net_today"],
        "vat_today": rows["vat_today"],
        "invoices_mtd": int(rows["invoices_mtd"]),
        "grand_total_mtd": rows["grand_mtd"],
        "net_mtd": rows["net_mtd"],
        "vat_mtd": rows["vat_mtd"],
    }


def _collections(db, as_of, territories):
    """Active receipts only; scoped through the customer's territory."""
    clauses, params = "", {}
    if territories is not None:
        clauses = (
            " JOIN master_data.master_customer c ON c.id = r.customer_id"
            " AND c.territory_id = ANY(CAST(:territories AS uuid[]))"
        )
        params["territories"] = [str(t) for t in territories]
    rows = (
        db.execute(
            text(
                "SELECT"
                " count(*) FILTER (WHERE r.receipt_date = :as_of) AS receipts_today,"
                " COALESCE(SUM(r.amount) FILTER (WHERE r.receipt_date = :as_of), 0.00) AS amount_today,"
                " count(*) AS receipts_mtd,"
                " COALESCE(SUM(r.amount), 0.00) AS amount_mtd"
                " FROM finance.payment_receipt r"
                + clauses
                + " WHERE r.status = 'Active'"
                " AND r.receipt_date >= date_trunc('month', CAST(:as_of AS date))"
                " AND r.receipt_date <= :as_of"
            ),
            {"as_of": as_of, **params},
        )
        .mappings()
        .one()
    )
    return {
        "receipts_today": int(rows["receipts_today"]),
        "amount_today": rows["amount_today"],
        "receipts_mtd": int(rows["receipts_mtd"]),
        "amount_mtd": rows["amount_mtd"],
    }


def _receivables(db, as_of, territories):
    """Outstanding AR as of the date = Σdebit − Σcredit for entries dated
    on/before it (Excel الرصيد = مدين − دائن, point-in-time)."""
    clauses, params = "", {"as_of": as_of}
    if territories is not None:
        clauses = (
            " JOIN master_data.master_customer c ON c.id = a.customer_id"
            " AND c.territory_id = ANY(CAST(:territories AS uuid[]))"
        )
        params["territories"] = [str(t) for t in territories]
    row = (
        db.execute(
            text(
                "SELECT COALESCE(SUM(balance), 0.00) AS outstanding,"
                " count(*) FILTER (WHERE balance <> 0) AS customers_with_balance"
                " FROM (SELECT a.customer_id, SUM(a.debit - a.credit) AS balance"
                " FROM finance.ar_entry a"
                + clauses
                + " WHERE a.entry_date <= :as_of GROUP BY a.customer_id) balances"
            ),
            params,
        )
        .mappings()
        .one()
    )
    return {
        "outstanding_total": row["outstanding"],
        "customers_with_balance": int(row["customers_with_balance"] or 0),
    }


def _alert_counts(db, user, territories):
    """Overstock/no-history counts from the approved cover report (D41).

    Warehouse scoping mirrors the inventory read grants exactly: global roles
    see all warehouses; managers see the warehouses of their
    platform.user_branch branches (territory grants never map to warehouses).
    """
    policy = settings_service.read_policy(db)
    warehouse_ids = None
    if territories is not None:
        rows = db.execute(
            text(
                "SELECT w.id FROM platform.user_branch ub"
                " JOIN master_data.master_warehouse w ON w.branch_id = ub.branch_id"
                " WHERE ub.user_id = :uid AND w.is_active"
            ),
            {"uid": user["id"]},
        ).fetchall()
        warehouse_ids = [row[0] for row in rows]
        if not warehouse_ids:
            return {
                "overstock_count": 0,
                "no_sales_history_count": 0,
                "window_days": policy["stock_cover_window_days"],
                "threshold_days": policy["overstock_threshold_days"],
            }
    report = cover_report(
        db,
        policy["stock_cover_window_days"],
        policy["overstock_threshold_days"],
        warehouse_ids=warehouse_ids,
    )
    return {
        "overstock_count": sum(1 for r in report if r["status"] == "overstock"),
        "no_sales_history_count": sum(
            1 for r in report if r["status"] == "no_sales_history"
        ),
        "window_days": policy["stock_cover_window_days"],
        "threshold_days": policy["overstock_threshold_days"],
    }


def management_summary(db, user, as_of):
    """Full summary dict for the caller's approved scope."""
    if user["role"] in GLOBAL_ROLES:
        territories = None
    else:
        territories = territory_ids(db, user)
    return {
        "as_of": as_of,
        "sales": _sales(db, as_of, territories),
        "collections": _collections(db, as_of, territories),
        "receivables": _receivables(db, as_of, territories),
        "inventory_alerts": _alert_counts(db, user, territories),
    }
