#!/usr/bin/env python3
import argparse
import json
import os
import sys
import subprocess
import uuid
import time
from typing import Any, Dict, Optional

import httpx


def send_telegram_alert(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_OPS_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        httpx.post(url, json={"chat_id": chat_id, "text": message}, timeout=5.0)
    except Exception:
        # Silently ignore telegram failures – we never want to crash the monitor.
        pass


def check_livez(base_url: str) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    headers = {"X-Request-ID": request_id}
    result: Dict[str, Any] = {"ok": False, "status_code": None, "request_id_match": False}
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/livez", headers=headers, timeout=5.0)
        result["status_code"] = resp.status_code
        if resp.status_code == 200:
            try:
                data = resp.json()
                result["ok"] = data.get("status") in ("alive", "ok")
            except Exception:
                result["ok"] = False
            result["request_id_match"] = resp.headers.get("X-Request-ID") == request_id
    except Exception:
        pass
    return result


def check_readyz(base_url: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": False, "status_code": None, "latency_ms": None}
    start = time.time()
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/readyz", timeout=5.0)
        latency = (time.time() - start) * 1000
        result["latency_ms"] = round(latency, 2)
        result["status_code"] = resp.status_code
        if resp.status_code == 200:
            try:
                data = resp.json()
                # Assume a field `db` indicates DB connectivity
                result["ok"] = data.get("db") == "ok" or data.get("db_connected") is True
            except Exception:
                result["ok"] = False
    except Exception:
        pass
    return result


def check_docs(base_url: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": False, "status_code": None}
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/docs", timeout=5.0, follow_redirects=False)
        result["status_code"] = resp.status_code
        result["ok"] = resp.status_code == 404
    except Exception:
        pass
    return result


def _run_cmd(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()


def check_container(container: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"exists": False}
    try:
        inspect_json = _run_cmd(["docker", "inspect", container])
        inspect_data = json.loads(inspect_json)[0]
        result["exists"] = True
        state = inspect_data.get("State", {})
        config = inspect_data.get("Config", {})
        result["running"] = state.get("Running", False)
        result["user"] = config.get("User", "")
        result["restart_count"] = state.get("RestartCount", 0)

        # docker stats --no-stream --format "{{json .}}" <container>
        stats_json = _run_cmd(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", container]
        )
        stats = json.loads(stats_json)
        result["memory_usage"] = stats.get("MemUsage", "")
        result["memory_limit"] = stats.get("MemLimit", "")
    except Exception:
        # If any command fails we keep exists=False and no further keys.
        pass
    return result


def build_report(
    base_url: str,
    container: Optional[str],
) -> Dict[str, Any]:
    report: Dict[str, Any] = {}
    report["livez"] = check_livez(base_url)
    report["readyz"] = check_readyz(base_url)
    report["docs"] = check_docs(base_url)

    if container:
        report["container"] = check_container(container)

    # Determine overall health
    healthy = (
        report["livez"]["ok"]
        and report["livez"]["request_id_match"]
        and report["readyz"]["ok"]
        and report["docs"]["ok"]
    )
    if container:
        cont = report.get("container", {})
        healthy = healthy and cont.get("exists", False) and cont.get("running", False)

    report["overall_status"] = "healthy" if healthy else "unhealthy"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ops Health & Resource Monitor"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the service (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--container",
        help="Docker container name to inspect (optional)",
    )
    parser.add_argument(
        "--out-json",
        help="Path to write the health report JSON (optional)",
    )
    parser.add_argument(
        "--telegram-alert",
        action="store_true",
        help="Send Telegram alert if unhealthy and env vars are set",
    )
    args = parser.parse_args()

    report = build_report(args.base_url, args.container)

    json_output = json.dumps(report, indent=2)
    print(json_output)

    if args.out_json:
        try:
            with open(args.out_json, "w", encoding="utf-8") as f:
                f.write(json_output)
        except Exception:
            # Non‑critical – continue
            pass

    if args.telegram_alert and report["overall_status"] != "healthy":
        message = (
            f"⚠️ Ops health check failed.\n"
            f"Livez: {report['livez']}\n"
            f"Readyz: {report['readyz']}\n"
            f"Docs: {report['docs']}"
        )
        if args.container:
            message += f"\nContainer: {report.get('container', {})}"
        send_telegram_alert(message)

    sys.exit(0 if report["overall_status"] == "healthy" else 1)


if __name__ == "__main__":
    main()
