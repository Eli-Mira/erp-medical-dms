"""B Master Data slice: read-only lookups for suppliers, chart of accounts, doctors.

These three tables are confirmed by the planning docs (PRD B-02 suppliers,
B-12 minimal COA, B-13 doctor/KOL list — D11/D13/D22) but no migration created
them. The tests assert authorization (role set + branch scope), soft-delete
visibility, and the database invariants each table must carry (unique codes,
COA type domain, no self-parent, FK integrity).

Runs only on the disposable ``dms_cycle_test_*`` database (conftest guard).
"""
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

B_PATHS = ("/master/suppliers", "/master/accounts", "/master/doctors")


def _login_as(db, user_id):
    sid = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_session(id,user_id,expires_at) "
            "VALUES (:sid,:uid,now() + interval '1 hour')"
        ),
        {"sid": sid, "uid": user_id},
    )
    db.commit()
    return {"Authorization": f"Bearer {sid}"}


def _make_user(db, role, is_owner=False):
    uid = uuid4()
    db.execute(
        text(
            "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused',:r,:o)"
        ),
        {"id": uid, "u": f"{role}_{uid.hex}", "r": role, "o": is_owner},
    )
    db.commit()
    return uid


def _seed_supplier(db, code=None):
    row_id = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_supplier(id,code,name_ar) "
            "VALUES (:id,:code,'Test supplier')"
        ),
        {"id": row_id, "code": code or row_id.hex[:20]},
    )
    db.commit()
    return row_id


def _seed_account(db, code, account_type):
    row_id = uuid4()
    db.execute(
        text(
            "INSERT INTO finance.coa_account(id,code,name_ar,account_type) "
            "VALUES (:id,:code,'Test account',:t)"
        ),
        {"id": row_id, "code": code, "t": account_type},
    )
    db.commit()
    return row_id


def _seed_doctor(db, branch_id, code=None):
    row_id = uuid4()
    db.execute(
        text(
            "INSERT INTO marketing.marketing_kol(id,code,name_ar,branch_id) "
            "VALUES (:id,:code,'Test doctor',:b)"
        ),
        {"id": row_id, "code": code or row_id.hex[:20], "b": branch_id},
    )
    db.commit()
    return row_id


def _seed_branch(db):
    branch = uuid4()
    db.execute(
        text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) "
            "VALUES (:id,:c,'Test branch')"
        ),
        {"id": branch, "c": branch.hex[:20]},
    )
    db.commit()
    return branch


def test_master_b_reads_require_a_session(posting_env):
    client, *_ = posting_env
    for path in B_PATHS:
        assert client.get(path).status_code in (401, 403), path


def test_owner_sees_seeded_rows(posting_env):
    client, db, ids, auth, *_ = posting_env
    supplier = _seed_supplier(db)
    account = _seed_account(db, "1000", "asset")
    doctor = _seed_doctor(db, ids["branch"])

    suppliers = {row["id"] for row in client.get("/master/suppliers", headers=auth).json()}
    accounts = {row["id"] for row in client.get("/master/accounts", headers=auth).json()}
    doctors = {row["id"] for row in client.get("/master/doctors", headers=auth).json()}
    assert str(supplier) in suppliers
    assert str(account) in accounts
    assert str(doctor) in doctors


def test_least_privilege_role_sets(posting_env):
    client, db, ids, _owner_auth, *_ = posting_env
    own = _seed_doctor(db, ids["branch"])
    elsewhere = _seed_doctor(db, _seed_branch(db))

    warehouse_staff = _make_user(db, "warehouse_staff")
    rep = _make_user(db, "medical_rep")
    sales_manager = _make_user(db, "sales_manager")
    district_manager = _make_user(db, "district_manager")
    finance = _make_user(db, "finance")
    auditor = _make_user(db, "read_only_auditor")
    # Only the rep holds a branch grant. The managers below hold none, so their
    # doctor list must be empty — never silently global.
    db.execute(
        text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
        {"u": rep, "b": ids["branch"]},
    )
    db.commit()

    rep_auth = _login_as(db, rep)
    assert {r["id"] for r in client.get("/master/doctors", headers=rep_auth).json()} == {
        str(own)
    }
    assert client.get("/master/suppliers", headers=rep_auth).status_code == 403
    assert client.get("/master/accounts", headers=rep_auth).status_code == 403

    for manager in (sales_manager, district_manager):
        auth = _login_as(db, manager)
        assert client.get("/master/doctors", headers=auth).status_code == 200
        assert client.get("/master/doctors", headers=auth).json() == []
        assert client.get("/master/suppliers", headers=auth).status_code == 403
        assert client.get("/master/accounts", headers=auth).status_code == 403

    fin_auth = _login_as(db, finance)
    assert client.get("/master/suppliers", headers=fin_auth).status_code == 200
    assert client.get("/master/accounts", headers=fin_auth).status_code == 200
    assert client.get("/master/doctors", headers=fin_auth).status_code == 403

    auditor_auth = _login_as(db, auditor)
    for path in B_PATHS:
        assert client.get(path, headers=auditor_auth).status_code == 200, path
    assert {r["id"] for r in client.get("/master/doctors", headers=auditor_auth).json()} == {
        str(own),
        str(elsewhere),
    }

    ws_auth = _login_as(db, warehouse_staff)
    for path in B_PATHS:
        assert client.get(path, headers=ws_auth).status_code == 403, path


def test_owner_role_without_the_flag_is_denied(posting_env):
    client, db, _ids, _owner_auth, *_ = posting_env
    fake_owner = _make_user(db, "owner", is_owner=False)
    auth = _login_as(db, fake_owner)
    for path in B_PATHS:
        assert client.get(path, headers=auth).status_code == 403, path


def test_doctors_are_branch_scoped(posting_env):
    client, db, ids, owner_auth, *_ = posting_env
    other_branch = _seed_branch(db)
    own = _seed_doctor(db, ids["branch"])
    elsewhere = _seed_doctor(db, other_branch)
    unassigned = _seed_doctor(db, None)

    rep = _make_user(db, "medical_rep")
    db.execute(
        text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
        {"u": rep, "b": ids["branch"]},
    )
    db.commit()
    rep_auth = _login_as(db, rep)

    visible = {row["id"] for row in client.get("/master/doctors", headers=rep_auth).json()}
    assert str(own) in visible
    assert str(elsewhere) not in visible
    assert str(unassigned) not in visible  # no branch grant can never match NULL

    # An explicit branch_id narrows within the grant; it can never widen it.
    own_only = client.get(
        "/master/doctors", params={"branch_id": str(ids["branch"])}, headers=rep_auth
    ).json()
    assert {row["id"] for row in own_only} == {str(own)}
    out_of_grant = client.get(
        "/master/doctors", params={"branch_id": str(other_branch)}, headers=rep_auth
    ).json()
    assert out_of_grant == []

    owner_visible = {row["id"] for row in client.get("/master/doctors", headers=owner_auth).json()}
    assert {str(own), str(elsewhere), str(unassigned)} <= owner_visible


def test_inactive_rows_are_soft_deleted(posting_env):
    client, db, ids, auth, *_ = posting_env
    supplier = _seed_supplier(db)
    account = _seed_account(db, "1000", "asset")
    doctor = _seed_doctor(db, ids["branch"])
    db.execute(text("UPDATE master_data.master_supplier SET is_active=false WHERE id=:i"), {"i": supplier})
    db.execute(text("UPDATE finance.coa_account SET is_active=false WHERE id=:i"), {"i": account})
    db.execute(text("UPDATE marketing.marketing_kol SET is_active=false WHERE id=:i"), {"i": doctor})
    db.commit()

    suppliers = {row["id"] for row in client.get("/master/suppliers", headers=auth).json()}
    accounts = {row["id"] for row in client.get("/master/accounts", headers=auth).json()}
    doctors = {row["id"] for row in client.get("/master/doctors", headers=auth).json()}
    assert str(supplier) not in suppliers
    assert str(account) not in accounts
    assert str(doctor) not in doctors


def test_account_type_filter_and_domain(posting_env):
    client, db, _ids, auth, *_ = posting_env
    asset = _seed_account(db, "1000", "asset")
    revenue = _seed_account(db, "4000", "revenue")
    rows = client.get("/master/accounts?account_type=asset", headers=auth).json()
    visible = {row["id"] for row in rows}
    assert str(asset) in visible
    assert str(revenue) not in visible
    assert client.get("/master/accounts?account_type=nonsense", headers=auth).status_code == 422


def test_supplier_and_doctor_filters(posting_env):
    client, db, ids, auth, *_ = posting_env
    wanted = _seed_supplier(db, "SUP-UNIQUE-AAA")
    _seed_supplier(db, "SUP-OTHER-BBB")
    rows = client.get("/master/suppliers?q=SUP-UNIQUE-AAA", headers=auth).json()
    assert {row["id"] for row in rows} == {str(wanted)}
    assert len(client.get("/master/suppliers?limit=1", headers=auth).json()) == 1

    doctor = _seed_doctor(db, ids["branch"], code="KOL-UNIQUE-AAA")
    _seed_doctor(db, ids["branch"], code="KOL-OTHER-BBB")
    doctors = client.get("/master/doctors?q=KOL-UNIQUE-AAA", headers=auth).json()
    assert {row["id"] for row in doctors} == {str(doctor)}


def test_coa_parent_relationship(posting_env):
    client, db, _ids, auth, *_ = posting_env
    parent = _seed_account(db, "1000", "asset")
    child = uuid4()
    db.execute(
        text(
            "INSERT INTO finance.coa_account(id,code,name_ar,account_type,parent_id) "
            "VALUES (:i,'1001','Cash on hand','asset',:p)"
        ),
        {"i": child, "p": parent},
    )
    db.commit()
    row = next(
        r for r in client.get("/master/accounts", headers=auth).json()
        if r["id"] == str(child)
    )
    assert row["parent_id"] == str(parent)


def test_database_invariants(posting_env):
    db = posting_env[1]
    # invalid COA account_type
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO finance.coa_account(code,name_ar,account_type) "
                "VALUES ('9999','Bad type','nonsense')"
            )
        )
        db.commit()
    db.rollback()

    # an account may not be its own parent
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO finance.coa_account(id,code,name_ar,account_type,parent_id) "
                "VALUES (:i,'3000','Self parent','equity',:i)"
            ),
            {"i": uuid4()},
        )
        db.commit()
    db.rollback()

    # supplier codes are unique
    duplicate = "SUP-DUP-1"
    _seed_supplier(db, duplicate)
    with pytest.raises(IntegrityError):
        db.execute(
            text("INSERT INTO master_data.master_supplier(code,name_ar) VALUES (:c,'Duplicate')"),
            {"c": duplicate},
        )
        db.commit()
    db.rollback()

    # a doctor cannot point at a missing branch
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO marketing.marketing_kol(code,name_ar,branch_id) "
                "VALUES ('KOL-ORPHAN','Orphan',:b)"
            ),
            {"b": uuid4()},
        )
        db.commit()
    db.rollback()

    # whitespace-only codes are rejected (tabs/newlines are not codes)
    for statement in (
        "INSERT INTO master_data.master_supplier(code,name_ar) VALUES (:c,'Blank')",
        "INSERT INTO marketing.marketing_kol(code,name_ar) VALUES (:c,'Blank')",
    ):
        with pytest.raises(IntegrityError):
            db.execute(text(statement), {"c": " \t "})
            db.commit()
        db.rollback()

    # COA and doctor codes are unique too
    _seed_account(db, "7777", "asset")
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO finance.coa_account(code,name_ar,account_type) "
                "VALUES ('7777','Duplicate','asset')"
            )
        )
        db.commit()
    db.rollback()

    _seed_doctor(db, None, code="KOL-DUP-1")
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO marketing.marketing_kol(code,name_ar) "
                "VALUES ('KOL-DUP-1','Duplicate')"
            )
        )
        db.commit()
    db.rollback()

    # a self-parent is refused on UPDATE as well as on INSERT
    account = _seed_account(db, "8888", "asset")
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE finance.coa_account SET parent_id=id WHERE id=:i"),
            {"i": account},
        )
        db.commit()
    db.rollback()


def test_search_metacharacters_are_literal(posting_env):
    """``q`` is a literal substring search: % and _ must not act as wildcards."""
    client, db, _ids, auth, *_ = posting_env
    wanted = _seed_supplier(db, "SUP-LITERAL-1")
    _seed_supplier(db, "SUP-LITERAL-2")
    assert client.get("/master/suppliers", params={"q": "%"}, headers=auth).json() == []
    assert client.get("/master/suppliers", params={"q": "_"}, headers=auth).json() == []
    # A lone backslash must be a literal, not an unterminated LIKE escape.
    assert client.get("/master/suppliers", params={"q": "\\"}, headers=auth).json() == []
    found = client.get("/master/suppliers", params={"q": "LITERAL-1"}, headers=auth).json()
    assert {row["id"] for row in found} == {str(wanted)}
