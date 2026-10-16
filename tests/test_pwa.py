"""P2.7 PWA shell: manifest installability, RTL + service-worker wiring,
i18n key parity, and that FastAPI actually serves the shell.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

WEB = Path(__file__).resolve().parents[1] / "web"
client = TestClient(app)


def _json(name: str) -> dict:
    return json.loads((WEB / name).read_text(encoding="utf-8"))


def test_manifest_is_installable():
    m = _json("manifest.webmanifest")
    for key in ("name", "start_url", "display", "icons"):
        assert key in m, f"manifest missing {key}"
    assert m["display"] == "standalone"


def test_index_is_rtl_and_registers_sw():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'dir="rtl"' in html and 'lang="ar"' in html
    assert "serviceWorker" in html
    assert (WEB / "sw.js").exists()


def test_i18n_key_parity():
    assert set(_json("i18n/ar.json")) == set(_json("i18n/en.json"))


def test_pwa_is_served():
    assert client.get("/app/manifest.webmanifest").status_code == 200
    assert client.get("/app/index.html").status_code == 200
