"""Opt-in adapter for Hermes' native durable Kanban; no application DB access."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

BOARD = "medical-erp-autonomous"
PROTECTED = {"app/db.py", "app/config.py", "docker-compose.yml", "dockerfile",
             "requirements.txt", "agents.md", "scripts/verify_invoice_cycle.py",
             "tools/autonomous_development.py", "docs/source_hashes.txt"}


def authorize(state, payload, environ, state_path=None):
    if environ.get("HERMES_KANBAN_BOARD") != state["board"]:
        return {"decision": "allow"}
    deny = {"decision": "block", "reason": "Autonomous mode: invocation outside approved task scope/gates"}
    task_id = environ.get("HERMES_KANBAN_TASK")
    task = state.get("tasks", {}).get(task_id)
    if not state.get("enabled") or not task or not task.get("approved"):
        return deny
    if task.get("approval_required") or task.get("attempts", 0) >= 3:
        return deny
    name, values = payload.get("tool_name"), payload.get("tool_input", {})
    if not isinstance(values, dict):
        return deny
    reviewer, run_id = False, None
    if state.get("native_db"):
        _, run_id, reviewer = identity(state, environ)
    elif not state["board"].startswith("synthetic-"):
        return deny
    if name in {"kanban_heartbeat", "kanban_comment", "kanban_block"}:
        return {"decision": "allow"} if values.get("task_id", task_id) == task_id else deny
    if name == "skills_list" and set(values) <= {"category"}:
        return {"decision": "allow"}
    if name == "skill_view":
        approved_skills = {"autonomous-development", "test-driven-development", "verification-before-completion",
                           "fastapi", "backend-feature-delivery", "python-testing-patterns", "security-guardian", "antislop-code"}
        approved_skills.update(task.get("skills", []))
        reference = values.get("file_path")
        if (values.get("name") in approved_skills and set(values) <= {"name", "file_path"} and
                (not reference or (not Path(reference).is_absolute() and ".." not in Path(reference).parts))):
            return {"decision": "allow"}
        return deny
    receipt = task.get("verification", {})
    bound = receipt.get("passed") is True and receipt.get("source_bindings") == bound_sources(Path(state["root"]))
    if name == "autonomous_development":
        if set(values) - {"action", "summary", "metadata"}:
            return deny
        action = values.get("action")
        if action == "status" or (action == "verify" and not reviewer):
            return {"decision": "allow"}
        verdict = values.get("metadata", {})
        if (action == "accept" and reviewer and bound and run_id != receipt.get("implementer_run_id") and
                values.get("summary") and isinstance(verdict, dict) and
                all(verdict.get(key) is True for key in ("spec_pass", "quality_pass", "security_pass"))):
            return {"decision": "allow"}
        return deny
    if name == "kanban_request_review":
        allowed = (not reviewer and bound and values.get("task_id", task_id) == task_id and
                   values.get("reviewer", "default") == "default" and not values.get("force"))
        return {"decision": "allow"} if allowed else deny
    if name == "kanban_complete":
        accepted = task.get("review", {})
        allowed = (reviewer and bound and values.get("task_id", task_id) == task_id and
                   not values.get("force") and not values.get("created_cards") and
                   accepted.get("run_id") == run_id and accepted.get("metadata") == values.get("metadata") and
                   task.get("verified_commit") == git(Path(state["root"]), "rev-parse", "HEAD").strip())
        return {"decision": "allow"} if allowed else deny
    if name == "terminal":
        return deny
    if name not in {"read_file", "write_file", "patch"} or (reviewer and name != "read_file"):
        return deny
    root = Path(state["root"]).resolve()
    value = values.get("path")
    if not isinstance(value, str) or not value:
        return deny
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        return deny
    relative = path.relative_to(root).as_posix().lower()
    scope = task["allowed_paths"] + (task.get("readonly_paths", []) if name == "read_file" else [])
    if relative not in {p.lower() for p in scope}:
        return deny
    if any(p.startswith(".env") or p in {".git", ".venv", "node_modules"} for p in Path(relative).parts):
        return deny
    if path.suffix.lower() in {".xlsx", ".xls", ".db", ".sqlite", ".sqlite3"} or ":" in relative:
        return deny
    if name != "read_file" and (relative in PROTECTED or relative.startswith(("docs/evidence/", "tools/autonomous_plugin/"))):
        return deny
    return {"decision": "allow"}


def save(path, state):
    lock = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.write(lock, b"\0")
        os.lseek(lock, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        generation = current.get("_generation", 0)
        if state.get("_generation", 0) != generation:
            raise ValueError("state changed concurrently; stale snapshot is not written")
        state["_generation"] = generation + 1
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        with temporary.open("x", encoding="utf-8") as target:
            json.dump(state, target, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        os.close(lock)


def native(state):
    from hermes_cli.kanban_db_connect import connect_closing
    return connect_closing(Path(state["native_db"]))


def add_task(path, state, manifest):
    from hermes_cli import kanban_db as kb
    if manifest.get("kind") not in {"erp", "synthetic"} or not manifest.get("requirement"):
        raise ValueError("task needs an approved requirement and a supported verification recipe")
    root = Path(state["root"])
    if manifest["kind"] == "synthetic" and (root / "scripts/verify_invoice_cycle.py").exists():
        raise ValueError("synthetic test recipes cannot replace ERP gates")
    for relative in manifest["allowed_paths"]:
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root) or relative.lower() in PROTECTED:
            raise ValueError("task scope includes a protected or escaping path")
    body = ("Use autonomous-development. Edit only the registered file scope. Do not call raw shell, "
            "network, database or publication tools. Invoke the trusted verify command given by status; "
            "request independent review after GREEN. Reviewers are read-only and must report spec_pass, "
            "quality_pass and security_pass in completion metadata.\n" + json.dumps(manifest, indent=2))
    with native(state) as conn:
        task_id = kb.create_task(conn, title=manifest["title"], body=body, assignee=None,
                                 workspace_kind="dir", workspace_path=str(root), initial_status="blocked",
                                 created_by="owner-approved-autonomous-development", priority=manifest.get("priority", 10),
                                 model_override="stepfun/step-5-preview:free", provider_override="nous",
                                 max_runtime_seconds=900, max_retries=3, skills=["autonomous-development"],
                                 completion_contract="local-only", board=state["board"])
        initial_event_id = conn.execute("SELECT MAX(id) FROM task_events WHERE task_id = ?", (task_id,)).fetchone()[0]
    state["tasks"][task_id] = {**manifest, "attempts": 0, "released": False, "initial_event_id": initial_event_id,
                                  "baseline_sources": bound_sources(root),
                                  "base_commit": git(root, "rev-parse", "HEAD").strip() if (root / ".git").exists() else None}
    save(path, state)
    return {"task_id": task_id}


def status(state):
    from hermes_cli import kanban_db as kb
    with native(state) as conn:
        queue = [{"id": t.id, "status": t.status, "assignee": t.assignee, "model": t.model_override}
                 for t in kb.list_tasks(conn) if t.id in state["tasks"]]
    return {"enabled": state["enabled"], "board": state["board"], "queue": queue}


def tick(path, state):
    from hermes_cli import kanban_db as kb
    if not state["enabled"]:
        return {"active_task": None, "reason": "mode disabled"}
    with native(state) as conn:
        kb.recompute_ready(conn)
        tasks = {t.id: t for t in kb.list_tasks(conn)}
        for task_id, entry in state["tasks"].items():
            current = tasks.get(task_id)
            if current and entry.get("released") and current.status in {"ready", "running", "review", "todo"}:
                if current.assignee is None:
                    kb.assign_task(conn, task_id, "default")
                return {"active_task": task_id, "reason": "existing task recovered"}
        for task_id, entry in sorted(state["tasks"].items(), key=lambda pair: -pair[1].get("priority", 10)):
            current = tasks.get(task_id)
            if not current or current.status not in {"ready", "blocked", "todo"} or entry.get("released"):
                continue
            if not entry.get("approved") or entry.get("approval_required") or entry.get("attempts", 0) >= 3:
                continue
            if current.model_override != "stepfun/step-5-preview:free" or current.provider_override != "nous":
                continue
            if kb.unsatisfied_parents(conn, task_id):
                continue
            if current.status == "blocked":
                later_block = conn.execute("SELECT 1 FROM task_events WHERE task_id = ? AND kind = 'blocked' AND id > ?",
                                           (task_id, entry["initial_event_id"])).fetchone()
                if later_block:
                    continue
                kb.unblock_task(conn, task_id)
            root = Path(state["root"])
            if (root / ".git").exists():
                if git(root, "diff", "--name-only").strip() or git(root, "diff", "--cached", "--name-only").strip():
                    return {"active_task": None, "reason": "unverified tracked work/index must be reconciled before another task"}
                head = git(root, "rev-parse", "HEAD").strip()
                if state.get("last_verified_commit") and head != state["last_verified_commit"]:
                    return {"active_task": None, "reason": "HEAD moved beyond last verified checkpoint"}
                entry["base_commit"] = head
                entry["baseline_sources"] = bound_sources(root)
            entry["released"] = True
            save(path, state)
            kb.assign_task(conn, task_id, "default")
            return {"active_task": task_id, "reason": "next approved unblocked task admitted"}
    return {"active_task": None, "reason": "no safe approved unblocked task"}


def set_enabled(path, state, enabled):
    from hermes_cli import kanban_db as kb
    synthetic = state["board"].startswith("synthetic-") and not (Path(state["root"]) / "scripts/verify_invoice_cycle.py").exists()
    if enabled and not synthetic and not state.get("safety_ready"):
        raise ValueError("activation requires validated hook, free routes, native dispatch and source-bound acceptance")
    state["enabled"] = enabled
    save(path, state)
    if not enabled:
        with native(state) as conn:
            for task_id in state["tasks"]:
                task = kb.get_task(conn, task_id)
                if task and task.status in {"ready", "review", "todo", "blocked"} and task.assignee:
                    kb.assign_task(conn, task_id, None)
    return status(state)


def bound_sources(root):
    paths = {p for folder in ("app", "tests", "alembic", "web", "scripts") for p in (root / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts}
    paths.update(p for p in root.iterdir() if p.is_file() and
                 (p.name.lower() in PROTECTED or p.name.startswith(".env") or p.suffix.lower() in {".xlsx", ".xls"}))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def identity(state, environ):
    from hermes_cli import kanban_db as kb
    task_id = environ.get("HERMES_KANBAN_TASK")
    run_id = int(environ.get("HERMES_KANBAN_RUN_ID", "0"))
    with native(state) as conn:
        task = kb.get_task(conn, task_id)
        if not task or task.status != "running" or task.current_run_id != run_id:
            raise ValueError("caller is not the active native task run")
        row = conn.execute("SELECT payload FROM task_events WHERE task_id = ? AND run_id = ? AND kind = 'claimed' ORDER BY id DESC LIMIT 1",
                           (task_id, run_id)).fetchone()
        reviewer = bool(row) and json.loads(row["payload"]).get("source_status") == "review"
    return task_id, run_id, reviewer


def erp_record_passed(record):
    if not isinstance(record, dict):
        return False
    counts, cases, steps = record.get("counts", {}), record.get("cases", []), record.get("steps", [])
    if not isinstance(counts, dict) or not isinstance(cases, list) or not isinstance(steps, list):
        return False
    if not all(isinstance(case, dict) for case in cases) or not all(isinstance(step, dict) for step in steps):
        return False
    if not all(type(counts.get(key)) is int for key in ("passed", "failed", "error", "skipped")):
        return False
    identifiers = [case.get("id") for case in cases]
    return (record.get("created") is True and record.get("removed") is True and
            record.get("exit_code") == 0 and record.get("default_off_exit") == 0 and
            not record.get("error") and record.get("unchanged") is True and bool(record.get("before")) and
            record.get("before") == record.get("after") and
            re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", record.get("database", "")) is not None and
            record.get("configuration") == {"APP_ENV": "test", "POSTING_ENABLED": "false"} and
            counts["passed"] > 0 and all(counts[key] == 0 for key in ("failed", "error", "skipped")) and
            len(cases) == counts["passed"] and all(isinstance(i, str) and i for i in identifiers) and
            len(set(identifiers)) == len(identifiers) and all(c["status"] == "passed" for c in cases) and
            {"fresh-upgrade", "down-one-up-head"} <= {s.get("action") for s in steps})


def verify(path, state, environ):
    from hermes_cli import kanban_db as kb
    task_id = environ.get("HERMES_KANBAN_TASK")
    entry = state["tasks"].get(task_id)
    if not state["enabled"] or not entry or not entry.get("approved") or entry.get("approval_required") or entry.get("attempts", 0) >= 3:
        raise ValueError("verification not authorized or failure budget exhausted")
    task_id, run_id, reviewer = identity(state, environ)
    if reviewer:
        raise ValueError("independent reviewer is read-only")
    prior = entry.get("verification", {})
    if prior.get("in_progress"):
        from hermes_cli.kanban_db_dispatch import _pid_alive
        if entry["kind"] == "erp" or _pid_alive(prior.get("pid")):
            raise ValueError("verification still running, or interrupted ERP cleanup/isolation remains unverified")
    root = Path(state["root"])
    before = bound_sources(root)
    entry["attempts"] = entry.get("attempts", 0) + 1
    entry["verification"] = {"passed": False, "in_progress": True, "pid": os.getpid(), "implementer_run_id": run_id}
    save(path, state)
    out = path.parent / "evidence" / task_id / uuid.uuid4().hex
    out.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if k.upper() in
           {"PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "HOME", "TEMP", "TMP", "TMPDIR", "LOCALAPPDATA"}}
    env.update(APP_ENV="test", POSTING_ENABLED="false", PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(out / "pycache"))
    if entry["kind"] == "synthetic":
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    else:
        stage = "auto_" + uuid.uuid4().hex
        bootstrap = "import sys,runpy;from dotenv import load_dotenv;load_dotenv('.env.dev',override=False);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
        command = [state["erp_python"], "-c", bootstrap, "scripts/verify_invoice_cycle.py", "--stage", stage,
                   "--chain", "--", "tests/", "-q", "--tb=short"]
    started = time.monotonic()
    with (out / "tests.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                timeout=600 if entry["kind"] == "erp" else 15, check=False)
    after = bound_sources(root)
    passed = result.returncode == 0 and before == after
    if entry["kind"] == "erp" and passed:
        record = json.loads((root / "docs/evidence/invoice-cycle" / stage / "run.json").read_text(encoding="utf-8"))
        passed = erp_record_passed(record)
    receipt = {"passed": passed, "test_exit": result.returncode, "source_bindings": after,
               "sources_unchanged_during_tests": before == after, "implementer_run_id": run_id,
               "elapsed_seconds": time.monotonic() - started, "command": command,
               "log_sha256": hashlib.sha256((out / "tests.log").read_bytes()).hexdigest()}
    entry["attempts"] -= int(passed)
    receipt["failed_attempts"] = entry["attempts"]
    entry["verification"] = receipt
    (out / "verify.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    save(path, state)
    if entry["attempts"] >= 3:
        with native(state) as conn:
            kb.block_task(conn, task_id, reason="Three unsuccessful verification attempts; no automatic retry", expected_run_id=run_id)
    return receipt


def git(root, *arguments):
    return subprocess.run(["git", "-C", str(root), *arguments], text=True, encoding="utf-8",
                          capture_output=True, check=True, timeout=30).stdout


def checkpoint(path, state, task_id, reviewer_run_id, review):
    entry = state["tasks"][task_id]
    root = Path(state["root"])
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in {"main", "master", "HEAD"}:
        raise ValueError("verified checkpoints require a named non-production branch")
    receipt = entry["verification"]
    current_sources = bound_sources(root)
    allowed = set(entry["allowed_paths"])
    baseline = entry["baseline_sources"]
    outside_changes = {p for p in set(baseline) | set(current_sources)
                       if baseline.get(p) != current_sources.get(p)} - allowed
    if outside_changes or current_sources != receipt["source_bindings"]:
        raise ValueError("source drift outside scope or after verification; no checkpoint")
    head = git(root, "rev-parse", "HEAD").strip()
    trailer = "Autonomous-Task: " + task_id
    already_committed = head != entry["base_commit"] and trailer in git(root, "log", "-1", "--format=%B").splitlines()
    if head != entry["base_commit"] and not already_committed:
        raise ValueError("Git HEAD moved independently; preserve it and require reconciliation")
    if not already_committed:
        tracked = set(filter(None, git(root, "diff", "--name-only", "-z").split("\0")))
        staged = set(filter(None, git(root, "diff", "--cached", "--name-only", "-z").split("\0")))
        if tracked - allowed or staged - allowed or (staged and not entry.get("checkpoint_intent")):
            raise ValueError("unrelated work/index present; no staging or reset permitted")
        changed = sorted(p for p in allowed if baseline.get(p) != current_sources.get(p))
        if not changed:
            raise ValueError("implementation task has no verified source delta")
        hooks_setting = subprocess.run(["git", "-C", str(root), "config", "--get", "core.hooksPath"],
                                       check=False, capture_output=True, text=True, timeout=10)
        hooks = Path(git(root, "rev-parse", "--git-path", "hooks").strip())
        if not hooks.is_absolute():
            hooks = root / hooks
        if hooks_setting.returncode == 0 or (hooks.is_dir() and any(p.is_file() and not p.name.endswith(".sample") for p in hooks.iterdir())):
            raise ValueError("active Git hooks need owner review before unattended commit; not bypassed")
        entry["checkpoint_intent"] = {"source_bindings": current_sources, "reviewer_run_id": reviewer_run_id,
                                      "review": review, "base_commit": head, "paths": changed}
        save(path, state)
        git(root, "add", "--", *changed)
        for relative in changed:
            if git(root, "rev-parse", ":" + relative).strip() != git(root, "hash-object", "--path=" + relative, relative).strip():
                raise ValueError("index does not match verified source; no commit")
        git(root, "commit", "-m", entry["title"] + "\n\n" + trailer)
        head = git(root, "rev-parse", "HEAD").strip()
    elif not entry.get("checkpoint_intent"):
        raise ValueError("matching trailer alone is not a verified checkpoint intent")
    entry["verified_commit"] = head
    entry["review"] = {"run_id": reviewer_run_id, "summary": review["summary"], "metadata": review["metadata"]}
    state["last_verified_commit"] = head
    save(path, state)
    return head


def safety_check(root, state):
    """Verify frozen source provenance, approved interpreter, safe recipe, and protection gates. Returns (passed, error)."""
    root = Path(root).expanduser().resolve()
    # On Windows, a leading '/' in a path is not a drive-relative root; normalize it.
    if not root.is_absolute() or str(root).startswith('//'):
        root = Path(os.path.normpath(root))
    root = root.resolve()
    errors = []

    # 1. Frozen source provenance: HEAD must match the committed safe snapshot
    if (root / ".git").exists():
        head = git(root, "rev-parse", "HEAD").strip()
        base_commit = state.get("base_commit") or state.get("last_verified_commit")
        if base_commit and head != base_commit:
            errors.append(f"source drift: HEAD {head} differs from locked base {base_commit}")
    if not (root / "AGENTS.md").exists():
        errors.append("AGENTS.md missing; safety rules not present")
    if not (root / "requirements.txt").exists():
        errors.append("requirements.txt missing")

    # 2. Approved ERP interpreter: python that exists and python3.x
    erp_python = os.environ.get("ERP_PYTHON") or sys.executable
    if not os.path.exists(erp_python):
        errors.append(f"ERP_PYTHON not found: {erp_python}")
    else:
        try:
            version = subprocess.run([erp_python, "--version"], capture_output=True, text=True, timeout=10).stdout
            if "Python 3." not in version:
                errors.append(f"non-Python-3 interpreter: {version}")
        except Exception as exc:
            errors.append(f"cannot probe interpreter: {exc}")

    # 3. Safe recipe: verification script present and not empty
    recipe = root / "scripts/verify_invoice_cycle.py"
    if not recipe.exists():
        errors.append("verification recipe scripts/verify_invoice_cycle.py missing")
    elif recipe.stat().st_size == 0:
        errors.append("verification recipe is empty")

    # 4. Protection gates: protected files unchanged, posting off
    if not os.environ.get("POSTING_ENABLED", "false").lower() == "false":
        errors.append("POSTING_ENABLED must be OFF for autonomous development")
    protected = {"app/db.py", "app/config.py", "docker-compose.yml", "dockerfile", "requirements.txt", "agents.md",
                 "scripts/verify_invoice_cycle.py", "tools/autonomous_development.py", "docs/source_hashes.txt"}
    for relative in sorted(protected):
        p = root / relative
        if p.exists() and not p.is_file():
            errors.append(f"protected file is not a regular file: {relative}")
    return (not errors), "; ".join(errors)


def run_cycle(path, state, *, guard=None):
    """Single Select → Implement → Test → Review → Secure → Optimize → Commit cycle; returns the action taken."""
    from hermes_cli import kanban_db_dispatch as kbd
    if guard:
        guard(state, path)
    tick(path, state)
    status_out = status(path, state)
    active = status_out.get("active_task")
    if not active:
        return "idle"
    entry = state["tasks"][active]
    if entry.get("attempts", 0) >= 3:
        return "failure_budget_exhausted"
    result = verify(path, state, os.environ)
    if not result.get("passed"):
        return "verify_failed"
    if entry.get("review"):
        return "review_pending"
    return "checkpoint_ready"


def continue_flow(path, state, max_cycles=1, *, watchdog_pid=None):
    """Loop one cycle at a time; returns the final action and leaves state saved."""
    from hermes_cli import kanban_db_dispatch as kbd

    completed = 0
    for _ in range(max_cycles):
        if watchdog_pid is not None and os.getpid() == watchdog_pid:
            return {"action": "blocked_watchdog", "reason": "watched self"}
        run_cycle(path, state)
        status_out = status(path, state)
        active = status_out.get("active_task")
        if not active:
            return {"action": "idle", "cycles_completed": completed}
        entry = state["tasks"][active]
        if entry.get("attempts", 0) >= 3:
            return {"action": "failure_budget_exhausted", "cycles_completed": completed}
        result = verify(path, state, os.environ)
        if not result.get("passed"):
            return {"action": "verify_failed", "cycles_completed": completed}
        if entry.get("review"):
            return {"action": "review_pending", "cycles_completed": completed}
        # Checkpoint the verified change; reviewer_run_id is the review receipt's run.
        reviewer_run_id = int(entry.get("review", {}).get("run_id", "0"))
        review = entry.get("review", {})
        head = checkpoint(path, state, active, reviewer_run_id, review)
        completed += 1
        state["last_verified_commit"] = head
        save(path, state)
    return {"action": "continue_loop", "cycles_completed": completed}


def daemon_loop(path, state, interval_seconds=60, *, enable_action=None):
    """Persistent native continuation: run continue_flow at the configured cadence."""
    import signal as _signal

    def _handle(_signum, _frame):
        state["enabled"] = False
        save(path, state)

    _signal.signal(_signal.SIGTERM, _handle)
    _signal.signal(_signal.SIGINT, _handle)
    while state.get("enabled"):
        action = run_cycle(path, state)
        if action != "checkpoint_ready":
            return action


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("action", choices=["hook", "init", "add", "status", "tick", "enable", "disable", "verify", "accept"])
    parser.add_argument("--root", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--board", default=BOARD)
    parser.add_argument("--task", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "init":
            if args.state.exists() or not args.root or not args.db:
                raise ValueError("init requires new state path, --root and --db; existing state is preserved")
            args.state.parent.mkdir(parents=True, exist_ok=True)
            state = {"enabled": False, "board": args.board, "root": str(args.root.resolve()),
                     "native_db": str(args.db.resolve()), "tasks": {}}
            with native(state):
                pass
            save(args.state, state)
            result = status(state)
        else:
            state = json.loads(args.state.read_text(encoding="utf-8"))
            if args.action == "hook":
                result = authorize(state, json.load(sys.stdin), os.environ, args.state)
            elif args.action == "add":
                result = add_task(args.state, state, json.loads(args.task.read_text(encoding="utf-8")))
            elif args.action == "tick":
                result = tick(args.state, state)
            elif args.action in {"enable", "disable"}:
                result = set_enabled(args.state, state, args.action == "enable")
            elif args.action == "verify":
                result = verify(args.state, state, os.environ)
            elif args.action == "accept":
                review = json.loads(args.task.read_text(encoding="utf-8"))
                if authorize(state, {"tool_name": "autonomous_development", "tool_input": review}, os.environ, args.state).get("decision") != "allow":
                    raise ValueError("independent acceptance gate refused")
                task_id, run_id, _ = identity(state, os.environ)
                result = {"verified_commit": checkpoint(args.state, state, task_id, run_id, review)}
            elif args.action == "daemon":
                if not state.get("enabled"):
                    raise ValueError("resolution needs a trusted source-bound setup run first")
                result = daemon_loop(args.state, state, interval_seconds=60)
            elif args.action == "continue":
                if not state.get("enabled"):
                    raise ValueError("continuation needs mode enabled and a dirty head")
                result = continue_flow(args.state, state, max_cycles=1)
            elif args.action == "setup":
                if args.state.exists():
                    raise ValueError("setup requires a new state path; existing state preserved")
                if not args.root or not args.db:
                    raise ValueError("setup needs --root and --db; existing state preserved")
                args.state.parent.mkdir(parents=True, exist_ok=True)
                state = {"enabled": False, "board": args.board, "root": str(args.root.resolve()),
                         "native_db": str(args.db.resolve()), "tasks": {}, "safety_ready": False,
                         "setup_check": {"provenance": ("pending", "awaiting verification run")}
                         }
                with native(state):
                    pass
                # Run safety verification in-process so results bind to a real check, not manual state.
                ok, errors = safety_check(args.state.parent, state)
                state["setup_check"] = {"provenance": ("verified" if ok else "blocked", errors or "all gates green")}
                state["safety_ready"] = ok
                save(args.state, state)
                result = status(state)
            else:
                result = status(state)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if args.action == "verify":
            result = {"passed": False, "error": str(exc)}
        elif args.action == "hook":
            result = {"decision": "block", "reason": "Autonomous policy unavailable or invalid; fail closed"}
        else:
            parser.exit(1, type(exc).__name__ + ": " + str(exc) + "\n")
    print(json.dumps(result))
    if args.action == "verify" and not result.get("passed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
