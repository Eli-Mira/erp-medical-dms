"""C9 demo masking from an approved local structural map, never raw workbook rows.

Only opaque keys and explicit relationships are admitted. Names, source IDs,
amounts, quantities, dates, notes and audit payloads are not copied. This is a
fictional demo generator, not approval for operational buyer-data cutover.
"""

from datetime import date
from decimal import Decimal
import argparse
import json
import os
from pathlib import Path
from random import SystemRandom
import re
import secrets
import sys
from uuid import uuid4


FIELDS = {
    "branches": {"key"},
    "territories": {"key"},
    "warehouses": {"key", "branch"},
    "products": {"key"},
    "customers": {"key", "branch", "territory"},
    "routes": {"branch", "warehouse"},
    "users": {"key", "role", "branches"},
    "opening_stock": {"warehouse", "product"},
    "opening_ar": {"customer"},
}
STAFF_ROLES = {
    "finance",
    "sales_manager",
    "district_manager",
    "medical_rep",
    "warehouse_staff",
    "read_only_auditor",
}


def masked_packet(structure, *, as_of):
    """Replace private identity/value material with a coherent fictional graph."""
    if type(structure) is not dict or set(structure) != set(FIELDS):
        raise ValueError("Unsupported structural groups")
    if type(as_of) is not date:
        raise ValueError("Explicit demo date required")
    rows = {}
    maps = {}
    for group, fields in FIELDS.items():
        source = structure[group]
        if type(source) is not list or not source or len(source) > 10000:
            raise ValueError("Invalid structural row count")
        copied = []
        keys = set()
        for row in source:
            allowed = fields | ({"territories"} if group == "users" else set())
            if type(row) is not dict or not fields <= set(row) <= allowed:
                raise ValueError("Unsupported structural fields")
            if "key" in fields:
                key = row["key"]
                if type(key) is not str or not key or len(key) > 256 or key in keys:
                    raise ValueError("Invalid or duplicate structural key")
                keys.add(key)
            copied.append(dict(row))
        SystemRandom().shuffle(copied)
        rows[group] = copied
        if "key" in fields:
            maps[group] = {row["key"]: uuid4() for row in copied}

    def reference(group, key):
        if type(key) is not str or key not in maps[group]:
            raise ValueError("Unresolved structural reference")
        return maps[group][key]

    packet = {"kind": "fictional-c9-demo-v1", "run_id": uuid4(), "as_of": as_of}
    for group, prefix, arabic in [
        ("branches", "B", "فرع"),
        ("territories", "T", "منطقة"),
        ("products", "P", "منتج"),
        ("warehouses", "W", "مخزن"),
        ("customers", "C", "عميل"),
    ]:
        result = []
        for index, row in enumerate(rows[group], 1):
            item = {
                "id": reference(group, row["key"]),
                "code": f"DEMO-{prefix}-{index:05d}",
                "name_ar": f"{arabic} تجريبي {index}",
                "name_en": f"Fictional {group} {index}",
            }
            if group in {"warehouses", "customers"}:
                item["branch_id"] = reference("branches", row["branch"])
            if group == "customers":
                item["territory_id"] = reference("territories", row["territory"])
            if group == "products":
                item["sku"] = item.pop("code")
                item["base_price"] = Decimal("50.00") + Decimal(index) * Decimal("7.25")
                item["vat_rate"] = Decimal("14.00") if index % 2 else Decimal("0.00")
            if group in {"products", "warehouses", "customers"}:
                item["is_active"] = True
            result.append(item)
        packet[group] = result

    packet["routes"] = [
        {
            "branch_id": reference("branches", row["branch"]),
            "warehouse_id": reference("warehouses", row["warehouse"]),
        }
        for row in rows["routes"]
    ]
    owner = {
        "id": uuid4(),
        "username": "masked_demo_owner",
        "first_name": "Fictional",
        "last_name": "Owner",
        "role": "owner",
        "is_owner": True,
        "is_active": True,
    }
    packet["users"] = [owner]
    packet["grants"] = []
    packet["territory_grants"] = []
    for index, row in enumerate(rows["users"], 1):
        branches = row["branches"]
        if (
            type(row["role"]) is not str
            or row["role"] not in STAFF_ROLES
            or type(branches) is not list
            or not branches
        ):
            raise ValueError("Staff role and explicit branch grants required")
        if any(type(value) is not str for value in branches) or len(
            set(branches)
        ) != len(branches):
            raise ValueError("Invalid staff branch grants")
        territories = row.get("territories", [])
        if type(territories) is not list or any(
            type(value) is not str for value in territories
        ):
            raise ValueError("Invalid staff territory grants")
        if len(set(territories)) != len(territories):
            raise ValueError("Duplicate staff territory grants")
        if row["role"] == "medical_rep" and not territories:
            raise ValueError(
                "Medical representatives require explicit territory grants"
            )
        user = {
            "id": reference("users", row["key"]),
            "username": f"masked_demo_staff_{index:05d}",
            "first_name": "Fictional",
            "last_name": f"Staff {index}",
            "role": row["role"],
            "is_owner": False,
            "is_active": True,
        }
        packet["users"].append(user)
        packet["grants"].extend(
            {"user_id": user["id"], "branch_id": reference("branches", branch)}
            for branch in branches
        )
        packet["territory_grants"].extend(
            {"user_id": user["id"], "territory_id": reference("territories", territory)}
            for territory in territories
        )

    # shortcut: unbatched demo openings only; require explicit batch/expiry mapping before admitting batched sources.
    stock_keys = set()
    packet["opening_stock"] = []
    for index, row in enumerate(rows["opening_stock"], 1):
        key = (
            reference("warehouses", row["warehouse"]),
            reference("products", row["product"]),
        )
        if key in stock_keys:
            raise ValueError("Duplicate opening-stock identity")
        stock_keys.add(key)
        packet["opening_stock"].append(
            {
                "warehouse_id": key[0],
                "product_id": key[1],
                "quantity": Decimal(index + 10),
                "unit_cost": Decimal("10.00") + Decimal(index),
                "batch_id": None,
            }
        )
    ar_keys = set()
    packet["opening_ar"] = []
    for index, row in enumerate(rows["opening_ar"], 1):
        customer = reference("customers", row["customer"])
        if customer in ar_keys:
            raise ValueError("One approved opening per customer required")
        ar_keys.add(customer)
        packet["opening_ar"].append(
            {
                "customer_id": customer,
                "debit": Decimal("137.25") * Decimal(index),
                "credit": Decimal("0.00"),
            }
        )
    return packet


def owned_target(url):
    """Reject defaults/foreign targets before any connection is attempted."""
    if (
        not Path("/.dockerenv").is_file()
        or os.environ.get("APP_ENV") != "test"
        or url.get_backend_name() != "postgresql"
        or url.host != "127.0.0.1"
        or url.port != 5432
        or url.query
        or not re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", url.database or "")
    ):
        raise ValueError("Owned isolated target required")
    return url


def apply_packet(db, packet, *, owner_password=None):
    """Load a fictional graph into an empty owned target in the caller's transaction.

    This never creates/migrates a database, commits, deletes rows or changes the
    posting gate. Operational imports and batched openings remain out of scope.
    """
    from sqlalchemy import text

    url = owned_target(db.engine.url)
    if packet.get("kind") != "fictional-c9-demo-v1" or not db.in_transaction():
        raise ValueError("Owned isolated fictional-demo target required")
    if owner_password is not None and (
        type(owner_password) is not str or len(owner_password) < 16
    ):
        raise ValueError("A strong private owner credential is required")
    if db.scalar(text("SELECT current_database()")) != url.database:
        raise ValueError("Target identity mismatch")

    from app.auth.security import hash_password
    from app.finance.ar import record_entry
    from app.inventory.service import record_movement

    tables = {
        "branches": ("master_data.master_branch", "id code name_ar name_en"),
        "territories": ("master_data.master_territory", "id code name_ar name_en"),
        "warehouses": (
            "master_data.master_warehouse",
            "id code name_ar name_en branch_id is_active",
        ),
        "products": (
            "master_data.master_product",
            "id sku name_ar name_en base_price vat_rate is_active",
        ),
        "customers": (
            "master_data.master_customer",
            "id code name_ar name_en branch_id territory_id is_active",
        ),
        "users": (
            "platform.platform_user",
            "id username first_name last_name role is_owner is_active",
        ),
        "routes": ("inventory.branch_warehouse", "branch_id warehouse_id"),
        "grants": ("platform.user_branch", "user_id branch_id"),
        "territory_grants": ("platform.user_territory", "user_id territory_id"),
    }
    for group, (_, fields) in tables.items():
        if type(packet.get(group)) is not list:
            raise ValueError("Invalid masked packet group")
        for row in packet[group]:
            if type(row) is not dict or set(row) != set(fields.split()):
                raise ValueError("Unsupported masked packet fields")
    for table in [
        *(table for table, _ in tables.values()),
        "finance.ar_entry",
        "inventory.stock_movement",
        "inventory.stock_balance",
        "audit.audit_log",
    ]:
        if db.scalar(text(f"SELECT count(*) FROM {table}")):
            raise ValueError(
                "Fresh empty target required; no existing data is replaced"
            )

    # Fixed identifiers and validated schemas; only values come from the packet.
    for group, (table, fields) in tables.items():
        for original in packet[group]:
            row = dict(original)
            columns = fields.split()
            if group == "users":
                password = (
                    owner_password
                    if row["is_owner"] and owner_password
                    else secrets.token_urlsafe(32)
                )
                row["password_hash"] = hash_password(password)
                columns.append("password_hash")
            parameters = ", ".join(":" + name for name in columns)
            db.execute(
                text(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({parameters})"
                ),
                row,
            )

    owner = next(user["id"] for user in packet["users"] if user["is_owner"])
    for row in packet["opening_stock"]:
        record_movement(
            db,
            actor_id=owner,
            movement_type="opening",
            note="Fictional C9 demo opening",
            **row,
        )
    for row in packet["opening_ar"]:
        record_entry(
            db,
            actor_id=owner,
            entry_type="opening",
            on_date=packet["as_of"],
            note="Fictional C9 demo opening",
            **row,
        )
    missing_grants = db.scalar(
        text("""
        SELECT count(*) FROM platform.platform_user u
        WHERE NOT u.is_owner AND NOT EXISTS
        (SELECT 1 FROM platform.user_branch g WHERE g.user_id=u.id)
    """)
    )
    if missing_grants:
        raise ValueError("Every staff user must have explicit branch grants")
    counts = {
        group: len(packet[group]) for group in [*tables, "opening_stock", "opening_ar"]
    }
    db.execute(
        text("""
        INSERT INTO audit.audit_log(id, actor_user_id, action, entity_type, entity_id, new_values, created_at)
        VALUES (gen_random_uuid(), :actor, 'C9_DEMO_LOAD', 'fictional_demo', :run, CAST(:counts AS jsonb), now())
    """),
        {"actor": owner, "run": packet["run_id"], "counts": json.dumps(counts)},
    )
    return counts


def main(argv=None):
    """Local-only plan/apply CLI; stdout contains counts/flags, never row values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    try:
        path = args.structure
        if (
            path.suffix.lower() != ".json"
            or path.is_symlink()
            or path.stat().st_size > 16 * 1024 * 1024
        ):
            raise ValueError("Approved bounded structural JSON required")
        packet = masked_packet(
            json.loads(path.read_text(encoding="utf-8")),
            as_of=date.fromisoformat(args.as_of),
        )
        if args.apply:
            from sqlalchemy import create_engine
            from sqlalchemy.engine.url import make_url

            raw = os.environ.get("DATABASE_URL")
            if not raw:
                raise ValueError("Explicit target configuration required")
            url = owned_target(make_url(raw))
            password = os.environ.get("C9_DEMO_OWNER_PASSWORD")
            if not password or len(password) < 16:
                raise ValueError("Private owner credential required")
            root = str(Path(__file__).resolve().parents[1])
            if root not in sys.path:
                sys.path.insert(0, root)
            engine = create_engine(url)
            with engine.begin() as db:
                counts = apply_packet(db, packet, owner_password=password)
        else:
            counts = {
                key: len(value) for key, value in packet.items() if type(value) is list
            }
        print(json.dumps({"applied": args.apply, "counts": counts}, sort_keys=True))
        return 0
    except Exception as error:
        # Exception text can contain source rows, SQL parameters or credentials.
        print(
            json.dumps(
                {"applied": False, "failed": 1, "category": type(error).__name__}
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
