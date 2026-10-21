"""Native in-process policy and supervised verification tool; inert outside its board."""
import json
import os
from pathlib import Path

from . import runtime


def register(ctx):
    from hermes_constants import get_hermes_home
    state_path = Path(ctx.get_config("state_path", str(get_hermes_home() / "autonomous-development/state.json")))
    board = ctx.get_config("board", runtime.BOARD)

    def active():
        return os.environ.get("HERMES_KANBAN_BOARD") == board

    def guard(tool_name, args, **kwargs):
        if not active():
            return None
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("board") != board:
                raise ValueError("configured board and private policy do not match")
            verdict = runtime.authorize(state, {"tool_name": tool_name, "tool_input": args}, os.environ, state_path)
            if verdict.get("decision") != "allow":
                return {"action": "block", "message": verdict.get("reason", "Autonomous scope/gate rejected")}
            return None
        except Exception:  # noqa: BLE001 - Native hook errors otherwise fail open.
            return {"action": "block", "message": "Autonomous policy/identity unavailable; fail closed"}

    def handle(args, **kwargs):
        if not active():
            return json.dumps({"error": "autonomous-development is not active for this board"})
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("board") != board:
                raise ValueError("configured board and private policy do not match")
            verdict = runtime.authorize(state, {"tool_name": "autonomous_development", "tool_input": args}, os.environ, state_path)
            if verdict.get("decision") != "allow":
                return json.dumps({"error": verdict.get("reason", "Autonomous gate rejected")})
            if args["action"] == "verify":
                receipt = runtime.verify(state_path, state, os.environ)
                return json.dumps({k: v for k, v in receipt.items() if k not in {"source_bindings", "command"}})
            if args["action"] == "accept":
                task_id, run_id, _ = runtime.identity(state, os.environ)
                return json.dumps({"verified_commit": runtime.checkpoint(state_path, state, task_id, run_id, args)})
            return json.dumps(runtime.status(state))
        except Exception as exc:  # noqa: BLE001 - Do not leak exception details or continue after a gate error.
            return json.dumps({"error": type(exc).__name__, "passed": False})

    ctx.register_hook("pre_tool_call", guard)
    ctx.register_tool(name="autonomous_development", toolset="autonomous-development", handler=handle, check_fn=active,
                      schema={"name": "autonomous_development", "description": "Run trusted verification, inspect queue, or accept a frozen change as the independent reviewer. No arbitrary commands.",
                              "parameters": {"type": "object", "properties": {
                                  "action": {"type": "string", "enum": ["status", "verify", "accept"]},
                                  "summary": {"type": "string"}, "metadata": {"type": "object"}},
                                  "required": ["action"], "additionalProperties": False}})
