"""C9 demo mask contract; these source references are synthetic canaries only."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import importlib.util
import json
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/load_masked_demo.py"
    assert path.is_file(), "C9 masked-demo loader capability is missing"
    spec = importlib.util.spec_from_file_location("c9_masked_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def structure():
    return {
        "branches": [{"key": "SYNTHETIC_PRIVATE_BRANCH_CANARY"}],
        "territories": [{"key": "SYNTHETIC_PRIVATE_TERRITORY_CANARY"}],
        "warehouses": [
            {
                "key": "SYNTHETIC_PRIVATE_WAREHOUSE_CANARY",
                "branch": "SYNTHETIC_PRIVATE_BRANCH_CANARY",
            }
        ],
        "products": [{"key": "SYNTHETIC_PRIVATE_PRODUCT_CANARY"}],
        "customers": [
            {
                "key": "SYNTHETIC_PRIVATE_CUSTOMER_CANARY",
                "branch": "SYNTHETIC_PRIVATE_BRANCH_CANARY",
                "territory": "SYNTHETIC_PRIVATE_TERRITORY_CANARY",
            }
        ],
        "routes": [
            {
                "branch": "SYNTHETIC_PRIVATE_BRANCH_CANARY",
                "warehouse": "SYNTHETIC_PRIVATE_WAREHOUSE_CANARY",
            }
        ],
        "users": [
            {
                "key": "SYNTHETIC_PRIVATE_STAFF_CANARY",
                "role": "warehouse_staff",
                "branches": ["SYNTHETIC_PRIVATE_BRANCH_CANARY"],
            }
        ],
        "opening_stock": [
            {
                "warehouse": "SYNTHETIC_PRIVATE_WAREHOUSE_CANARY",
                "product": "SYNTHETIC_PRIVATE_PRODUCT_CANARY",
            }
        ],
        "opening_ar": [{"customer": "SYNTHETIC_PRIVATE_CUSTOMER_CANARY"}],
    }


def test_masked_packet_has_fictional_decimals_linked_parents_and_staff_grants():
    source = structure()
    original = deepcopy(source)
    packet = load_module().masked_packet(source, as_of=date(2026, 1, 1))
    exported = json.dumps(packet, default=str)
    assert "SYNTHETIC_PRIVATE_" not in exported
    assert source == original
    assert (
        len(packet["branches"])
        == len(packet["products"])
        == len(packet["customers"])
        == 1
    )
    branch = packet["branches"][0]["id"]
    warehouse = packet["warehouses"][0]["id"]
    product = packet["products"][0]["id"]
    customer = packet["customers"][0]["id"]
    assert packet["warehouses"][0]["branch_id"] == branch
    assert packet["customers"][0]["branch_id"] == branch
    assert packet["customers"][0]["territory_id"] == packet["territories"][0]["id"]
    assert packet["opening_stock"][0]["warehouse_id"] == warehouse
    assert packet["opening_stock"][0]["product_id"] == product
    assert packet["opening_ar"][0]["customer_id"] == customer
    assert isinstance(packet["products"][0]["base_price"], Decimal)
    assert isinstance(packet["opening_ar"][0]["debit"], Decimal)
    assert isinstance(packet["opening_stock"][0]["unit_cost"], Decimal)
    assert packet["opening_ar"][0]["debit"] > 0
    assert packet["opening_stock"][0]["quantity"] > 0
    staff = next(user for user in packet["users"] if user["role"] == "warehouse_staff")
    assert {"user_id": staff["id"], "branch_id": branch} in packet["grants"]
    assert packet["as_of"] == date(2026, 1, 1)
