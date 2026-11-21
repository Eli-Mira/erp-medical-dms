import os
import sys
import json
import time
import hashlib
import argparse
import threading
from urllib import parse, request
from http import server


def redacted_token(token):
    return "<redacted>"


def build_receipt(data):
    receipt = {
        "timestamp": int(time.time()),
        "token_redacted": True,
        **data,
    }
    return receipt


def write_receipt(receipt, filename):
    json_bytes = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8")
    with open(filename, "wb") as f:
        f.write(json_bytes)
    sha256 = hashlib.sha256(json_bytes).hexdigest()
    with open(f"{filename}.sha256", "w") as f:
        f.write(sha256)


def telegram_api_request(base_url, token, method, data=None, timeout=10):
    url = f"{base_url}/bot{token}/{method}"
    if data is not None:
        encoded = parse.urlencode(data).encode()
        req = request.Request(url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    else:
        req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body.decode()), resp.getcode()
    except request.HTTPError as e:
        try:
            body = e.read()
            return json.loads(body.decode()), e.code
        except Exception:
            return {"ok": False, "error_code": e.code, "description": str(e)}, e.code
    except Exception as e:
        return {"ok": False, "description": str(e)}, None


class MockTelegramHandler(server.BaseHTTPRequestHandler):
    token = None
    allowed_chat_ids = set()

    def _send_json(self, obj, code=200):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _unauthorized(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":false,"error_code":401,"description":"Unauthorized"}')

    def do_GET(self):
        parts = self.path.split("/")
        if len(parts) < 3:
            self.send_error(404)
            return
        token_part = parts[1][3:]  # strip leading 'bot'
        method = parts[2]
        if token_part != self.token:
            self._unauthorized()
            return
        if method == "getMe":
            resp = {"ok": True, "result": {"id": 123456, "is_bot": True, "first_name": "MockBot"}}
            self._send_json(resp)
        else:
            self.send_error(404)

    def do_POST(self):
        parts = self.path.split("/")
        if len(parts) < 3:
            self.send_error(404)
            return
        token_part = parts[1][3:]  # strip leading 'bot'
        method = parts[2]
        if token_part != self.token:
            self._unauthorized()
            return
        if method == "sendMessage":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            params = parse.parse_qs(body)
            chat_id = params.get("chat_id", [""])[0]
            text = params.get("text", [""])[0]
            if chat_id not in self.allowed_chat_ids:
                self._send_json({"ok": False, "error_code": 400, "description": "Bad Request: chat not allowed"}, code=400)
                return
            resp = {"ok": True, "result": {"message_id": 1, "chat": {"id": int(chat_id)}, "text": text}}
            self._send_json(resp)
        else:
            self.send_error(404)

    def log_message(self, *args, **kwargs):
        # suppress logging
        pass


def run_dry_run():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "000000:MOCK_LOCAL_TOKEN")
    allowed_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "10001")
    allowed_set = set(id_.strip() for id_ in allowed_ids.split(",") if id_.strip())

    MockTelegramHandler.token = token
    MockTelegramHandler.allowed_chat_ids = allowed_set

    httpd = server.HTTPServer(("127.0.0.1", 0), MockTelegramHandler)
    port = httpd.server_address[1]

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    receipt = {}

    # getMe success
    resp, code = telegram_api_request(base_url, token, "getMe")
    receipt["getMe"] = {"ok": resp.get("ok", False), "code": code}
    # sendMessage success
    chat_id = next(iter(allowed_set))
    resp, code = telegram_api_request(
        base_url,
        token,
        "sendMessage",
        data={"chat_id": chat_id, "text": "/start"},
    )
    receipt["sendMessage"] = {"ok": resp.get("ok", False), "code": code}
    # unauthorized token test
    bad_token = "bad:token"
    resp, code = telegram_api_request(base_url, bad_token, "getMe")
    receipt["unauthorized"] = {"code": code, "ok": resp.get("ok", False)}

    httpd.shutdown()
    server_thread.join()

    redacted = build_receipt(receipt)
    print(json.dumps(redacted, indent=2, sort_keys=True))
    sys.exit(0)


def run_live_throwaway():
    required_env = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_READONLY_DB_URL", "TELEGRAM_ALLOWED_CHAT_IDS"]
    missing = [var for var in required_env if not os.getenv(var)]
    if missing:
        sys.stderr.write(f"Missing environment variables: {', '.join(missing)}\n")
        sys.exit(2)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    allowed_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS")
    allowed_set = [id_.strip() for id_ in allowed_ids.split(",") if id_.strip()]
    if not allowed_set:
        sys.stderr.write("No allowed chat ids provided.\n")
        sys.exit(2)

    api_base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")
    receipt = {}

    # getMe
    resp, code = telegram_api_request(api_base, token, "getMe")
    receipt["getMe"] = {"ok": resp.get("ok", False), "code": code}
    if not resp.get("ok"):
        write_receipt(build_receipt(receipt), "telegram_live_smoke_receipt.json")
        sys.exit(2)

    # sendMessage
    chat_id = allowed_set[0]
    resp, code = telegram_api_request(
        api_base,
        token,
        "sendMessage",
        data={"chat_id": chat_id, "text": "/start"},
    )
    receipt["sendMessage"] = {"ok": resp.get("ok", False), "code": code}
    if not resp.get("ok"):
        write_receipt(build_receipt(receipt), "telegram_live_smoke_receipt.json")
        sys.exit(2)

    write_receipt(build_receipt(receipt), "telegram_live_smoke_receipt.json")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Telegram live smoke test")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run-local-mock", action="store_true", help="Run against a local mock server")
    group.add_argument("--live-throwaway", action="store_true", help="Run against real Telegram API")
    args = parser.parse_args()

    if args.dry_run_local_mock:
        run_dry_run()
    elif args.live_throwaway:
        run_live_throwaway()
    else:
        parser.error("No mode selected")


if __name__ == "__main__":
    main()
