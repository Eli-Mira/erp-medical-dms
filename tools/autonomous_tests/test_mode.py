"""Isolated automation tests: no ERP imports, PostgreSQL, credentials or model calls."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "autonomous_development.py"


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="autonomous-test-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        (self.repo / "app").mkdir(parents=True)
        (self.repo / "app/item.py").write_text("value = 1\n", encoding="utf-8")
        self.state_path = self.base / "state.json"
        self.state = {"enabled": True, "board": "synthetic-autonomous", "root": str(self.repo),
                      "tasks": {"task-one": {"allowed_paths": ["app/item.py"], "approved": True,
                                                "approval_required": False, "attempts": 0}}}
        self.save()

    def save(self):
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    def hook(self, name, args, env_changes=None):
        env = {**os.environ, "HERMES_KANBAN_BOARD": self.state["board"],
               "HERMES_KANBAN_TASK": "task-one", "HERMES_KANBAN_RUN_ID": "1"}
        env.update(env_changes or {})
        result = subprocess.run([sys.executable, str(SCRIPT), "--state", str(self.state_path), "hook"],
                                check=False, input=json.dumps({"tool_name": name, "tool_input": args}),
                                text=True, capture_output=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_unapproved_invocations_are_blocked(self):
        self.state["tasks"]["task-one"]["allowed_paths"] += ["app/config.py", ".env", "source.xlsx"]
        self.save()
        calls = [
            ("write_file", {"path": str(self.repo / "app/config.py"), "content": "POSTING_ENABLED=True"}),
            ("read_file", {"path": str(self.repo / ".env")}),
            ("patch", {"path": str(self.repo / "source.xlsx")}),
            ("read_file", {"path": str(self.repo / "../state.json")}),
            ("terminal", {"command": "git push origin HEAD"}),
            ("terminal", {"command": "psql medical_dms -c 'DROP TABLE invoices'"}),
            ("execute_code", {"code": "print('bypass')"}),
            ("tool_call", {"calls": [{"name": "send_message", "arguments": {}}]}),
            ("search_files", {"path": str(self.repo), "pattern": "."}),
            ("kanban_complete", {"task_id": "task-one", "summary": "unreviewed"}),
        ]
        for name, args in calls:
            with self.subTest(tool=name, args=args):
                self.assertEqual(self.hook(name, args).get("decision"), "block")

    def test_native_queue_persists_between_processes(self):
        state_path = self.base / "durable.json"
        def cli(*args):
            result = subprocess.run([sys.executable, str(SCRIPT), "--state", str(state_path), *map(str, args)],
                                    check=False, text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        cli("init", "--root", self.repo, "--db", self.base / "native.sqlite", "--board", "synthetic-autonomous")
        manifest = self.base / "task.json"
        manifest.write_text(json.dumps({"title": "Synthetic code fix", "approved": True,
                                       "allowed_paths": ["app/item.py"], "kind": "synthetic",
                                       "requirement": "isolated workflow acceptance test"}), encoding="utf-8")
        created = cli("add", "--task", manifest)
        recovered = cli("status")
        self.assertFalse(recovered["enabled"])
        self.assertEqual(recovered["queue"][0]["id"], created["task_id"])
        self.assertIsNone(recovered["queue"][0]["assignee"])
        self.assertEqual(recovered["queue"][0]["model"], "stepfun/step-5-preview:free")

    def test_opt_in_admits_one_approved_task(self):
        state_path = self.base / "admission.json"
        def cli(*args):
            result = subprocess.run([sys.executable, str(SCRIPT), "--state", str(state_path), *map(str, args)],
                                    check=False, text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        cli("init", "--root", self.repo, "--db", self.base / "admission.sqlite", "--board", "synthetic-autonomous")
        identifiers = []
        for title, required, priority in [("Needs owner approval", True, 100), ("Ready first", False, 50),
                                           ("Ready second", False, 10)]:
            manifest = self.base / (title + ".json")
            manifest.write_text(json.dumps({"title": title, "approved": True, "approval_required": required,
                                           "priority": priority, "allowed_paths": ["app/item.py"],
                                           "kind": "synthetic", "requirement": "synthetic acceptance"}), encoding="utf-8")
            identifiers.append(cli("add", "--task", manifest)["task_id"])
        self.assertIsNone(cli("tick")["active_task"])
        cli("enable")
        self.assertEqual(cli("tick")["active_task"], identifiers[1])
        recovered = cli("status")
        self.assertEqual(sum(t["assignee"] == "default" for t in recovered["queue"]), 1)
        self.assertEqual(cli("tick")["active_task"], identifiers[1])
        cli("disable")
        self.assertIsNone(cli("tick")["active_task"])
        self.assertFalse(cli("status")["enabled"])

    def fixture_queue(self):
        self.state_path = self.base / "fixture-state.json"
        self.env = {**os.environ, "HERMES_HOME": str(self.base / "hermes-home"),
                    "TMPDIR": str(self.base), "HERMES_KANBAN_BOARD": "synthetic-autonomous"}
        self.invoke("init", "--root", self.repo, "--db", self.base / "fixture-queue.sqlite",
                    "--board", "synthetic-autonomous")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_item.py").write_text(
            "import unittest\nfrom app.item import value\nclass ItemTest(unittest.TestCase):\n"
            "    def test_expected_value(self): self.assertEqual(value, 2)\n", encoding="utf-8")
        for args in [["init", "-q", "-b", "synthetic-feature"], ["config", "user.email", "fixture@example.invalid"],
                     ["config", "user.name", "Synthetic workflow test"], ["add", "app/item.py", "tests/test_item.py"],
                     ["commit", "-q", "-m", "Synthetic fixture baseline"]]:
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, timeout=15)
        task = self.base / "fixture-task.json"
        task.write_text(json.dumps({"title": "Fix synthetic value", "approved": True,
                                    "allowed_paths": ["app/item.py", "tests/test_item.py"],
                                    "kind": "synthetic", "requirement": "synthetic failure/recovery acceptance"}), encoding="utf-8")
        task_id = self.invoke("add", "--task", task)["task_id"]
        self.invoke("enable")
        self.invoke("tick")
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        with connect_closing(self.base / "fixture-queue.sqlite") as conn:
            claimed = kb.claim_task(conn, task_id, claimer="synthetic-implementer")
            self.assertIsNotNone(claimed)
            self.env.update(HERMES_KANBAN_TASK=task_id, HERMES_KANBAN_RUN_ID=str(claimed.current_run_id))
        return task_id

    def invoke(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), "--state", str(self.state_path), *map(str, args)],
                                check=False, text=True, capture_output=True, timeout=30, env=self.env)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_failed_test_budget_survives_resumption(self):
        task_id = self.fixture_queue()
        for attempt in range(1, 4):
            result = self.invoke("verify", expected=1)
            self.assertFalse(result["passed"])
            self.assertEqual(result["test_exit"], 1)
            self.assertEqual(result["failed_attempts"], attempt)
        restored = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(restored["tasks"][task_id]["attempts"], 3)
        self.assertFalse(restored["tasks"][task_id]["verification"]["passed"])
        self.assertIsNone(self.invoke("tick")["active_task"])
        before = len(list((self.base / "evidence").rglob("verify.json")))
        self.invoke("verify", expected=1)
        self.assertEqual(len(list((self.base / "evidence").rglob("verify.json"))), before)
        self.assertEqual(before, 3)

    def native_hook(self, name, values):
        result = subprocess.run([sys.executable, str(SCRIPT), "--state", str(self.state_path), "hook"],
                                check=False, input=json.dumps({"tool_name": name, "tool_input": values}),
                                text=True, capture_output=True, env=self.env, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def finish_fixture_task(self, task_id):
        (self.repo / "app/item.py").write_text("value = 2\n", encoding="utf-8")
        receipt = self.invoke("verify")
        self.assertTrue(receipt["passed"])
        metadata = {"spec_pass": True, "quality_pass": True, "security_pass": True}
        completion = {"task_id": task_id, "summary": "Reviewed app/item.py and synthetic regression: exact scoped correction", "metadata": metadata}
        self.assertEqual(self.native_hook("kanban_complete", completion)["decision"], "block")
        self.assertNotEqual(self.native_hook("kanban_request_review", {"task_id": task_id})["decision"], "block")
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        with connect_closing(self.base / "fixture-queue.sqlite") as conn:
            self.assertTrue(kb.request_review(conn, task_id, summary="Ready for independent synthetic review",
                                             expected_run_id=int(self.env["HERMES_KANBAN_RUN_ID"])))
            reviewer = kb.claim_review_task(conn, task_id, claimer="synthetic-independent-reviewer")
            self.assertIsNotNone(reviewer)
            self.env["HERMES_KANBAN_RUN_ID"] = str(reviewer.current_run_id)
        self.assertEqual(self.native_hook("write_file", {"path": str(self.repo / "app/item.py"), "content": "value = 3"})["decision"], "block")
        self.assertEqual(self.native_hook("kanban_complete", completion)["decision"], "block")
        acceptance = self.base / "review.json"
        acceptance.write_text(json.dumps({"action": "accept", "summary": completion["summary"], "metadata": metadata}), encoding="utf-8")
        self.invoke("accept", "--task", acceptance)
        self.assertNotEqual(self.native_hook("kanban_complete", completion)["decision"], "block")
        restored = json.loads(self.state_path.read_text(encoding="utf-8"))
        commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(restored["last_verified_commit"], commit)
        self.assertNotEqual(int(self.env["HERMES_KANBAN_RUN_ID"]), receipt["implementer_run_id"])
        self.assertNotEqual(self.native_hook("kanban_complete", completion)["decision"], "block")
        again = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(commit, again)

    def test_verified_commit_requires_fresh_read_only_reviewer(self):
        self.finish_fixture_task(self.fixture_queue())

    def test_next_task_uses_verified_predecessor_checkpoint(self):
        task_id = self.fixture_queue()
        task = self.base / "next-task.json"
        task.write_text(json.dumps({"title": "Independent next synthetic task", "approved": True,
                                    "allowed_paths": ["app/second.py", "tests/test_second.py"],
                                    "kind": "synthetic", "requirement": "automatic next-task acceptance"}), encoding="utf-8")
        next_id = self.invoke("add", "--task", task)["task_id"]
        self.finish_fixture_task(task_id)
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        with connect_closing(self.base / "fixture-queue.sqlite") as conn:
            self.assertTrue(kb.complete_task(conn, task_id, summary="Synthetic independent review and checkpoint complete",
                                            expected_run_id=int(self.env["HERMES_KANBAN_RUN_ID"])))
        self.assertEqual(self.invoke("tick")["active_task"], next_id)
        recovered = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(recovered["tasks"][next_id]["base_commit"], saved["last_verified_commit"])

    def test_native_hook_engine_honors_denial(self):
        from unittest.mock import patch

        from agent.shell_hooks import ShellHookSpec, run_once
        command = subprocess.list2cmdline([sys.executable, str(SCRIPT), "--state", str(self.state_path), "hook"])
        spec = ShellHookSpec("pre_tool_call", command, timeout=10, fail_closed=True)
        with patch.dict(os.environ, {"HERMES_KANBAN_BOARD": self.state["board"],
                                     "HERMES_KANBAN_TASK": "task-one", "HERMES_KANBAN_RUN_ID": "1"}):
            denied = run_once(spec, {"tool_name": "terminal", "args": {"command": "git push origin HEAD"}})
            self.assertEqual(denied["parsed"].get("action"), "block", denied)
            permitted = run_once(spec, {"tool_name": "read_file", "args": {"path": str(self.repo / "app/item.py")}})
            # Native transport deliberately strips TASK/RUN identity. Unbound descendants must stay denied.
            self.assertEqual(permitted["parsed"].get("action"), "block", permitted)

    def test_native_inprocess_plugin_preserves_scoped_access(self):
        from unittest.mock import patch

        from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest
        from hermes_constants import get_hermes_home
        from tools.registry import registry
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(lambda: sys.path.remove(str(SCRIPT.parent)))
        import autonomous_plugin
        home = self.base / "native-plugin-home"
        with patch.dict(os.environ, {"HERMES_HOME": str(home), "HERMES_KANBAN_BOARD": self.state["board"],
                                     "HERMES_KANBAN_TASK": "task-one", "HERMES_KANBAN_RUN_ID": "1"}):
            self.assertEqual(get_hermes_home().resolve(), home.resolve())
            manager = PluginManager(scope_key=str(home))
            ctx = PluginContext(PluginManifest("autonomous-development", path=str(SCRIPT.parent / "autonomous_plugin")), manager)
            ctx.set_config("state_path", str(self.state_path))
            ctx.set_config("board", self.state["board"])
            autonomous_plugin.register(ctx)
            denied = manager.invoke_hook("pre_tool_call", tool_name="terminal", args={"command": "git push origin HEAD"})
            self.assertTrue(any(v and v.get("action") == "block" for v in denied), denied)
            permitted = manager.invoke_hook("pre_tool_call", tool_name="read_file", args={"path": str(self.repo / "app/item.py")})
            self.assertFalse(any(v and v.get("action") == "block" for v in permitted), permitted)
            self.assertIsNotNone(registry.get_entry("autonomous_development", scope=manager.scope_key))
            self.state["board"] = "synthetic-wrong-board"
            self.save()
            mismatched = manager.invoke_hook("pre_tool_call", tool_name="read_file", args={"path": str(self.base / "outside.env")})
            self.assertTrue(any(v and v.get("action") == "block" for v in mismatched), mismatched)

    def test_stale_snapshot_cannot_overwrite_pause(self):
        self.fixture_queue()
        stale = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.invoke("disable")
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(lambda: sys.path.remove(str(SCRIPT.parent)))
        from autonomous_plugin.runtime import save
        with self.assertRaises(ValueError):
            save(self.state_path, stale)
        self.assertFalse(json.loads(self.state_path.read_text(encoding="utf-8"))["enabled"])

    def test_interrupted_verification_invalidates_old_green(self):
        self.fixture_queue()
        (self.repo / "app/item.py").write_text("value = 2\n", encoding="utf-8")
        test_file = self.repo / "tests/test_item.py"
        test_file.write_text("import unittest, time\nfrom pathlib import Path\nfrom app.item import value\n"
                             "class ItemTest(unittest.TestCase):\n    def test_expected_value(self):\n"
                             "        root = Path(__file__).resolve().parents[1]\n"
                             "        if (root / 'hang').exists():\n"
                             "            (root / 'entered').write_text('synthetic interruption point')\n"
                             "            time.sleep(30)\n        self.assertEqual(value, 2)\n", encoding="utf-8")
        self.assertTrue(self.invoke("verify")["passed"])
        trigger = self.repo / "hang"
        trigger.write_text("synthetic test only", encoding="utf-8")
        process = subprocess.Popen([sys.executable, str(SCRIPT), "--state", str(self.state_path), "verify"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        import time

        from agent.shell_hooks import kill_process_tree
        deadline = time.monotonic() + 10
        try:
            while not (self.repo / "entered").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((self.repo / "entered").exists(), "actual synthetic test process did not enter interruption point")
        finally:
            kill_process_tree(process)
            process.communicate(timeout=5)
        restored = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertFalse(restored["tasks"][self.env["HERMES_KANBAN_TASK"]]["verification"]["passed"])
        trigger.unlink()
        self.assertTrue(self.invoke("verify")["passed"])

    def test_readonly_task_context_stays_readonly(self):
        context = self.repo / "AGENTS.md"
        context.write_text("Synthetic instructions only", encoding="utf-8")
        self.state["tasks"]["task-one"]["readonly_paths"] = ["AGENTS.md"]
        self.save()
        self.assertNotEqual(self.hook("read_file", {"path": str(context)})["decision"], "block")
        self.assertEqual(self.hook("write_file", {"path": str(context), "content": "changed"})["decision"], "block")

    def test_scoped_skill_reads_do_not_grant_skill_writes(self):
        self.assertNotEqual(self.hook("skill_view", {"name": "test-driven-development"})["decision"], "block")
        self.assertEqual(self.hook("skill_view", {"name": "test-driven-development", "file_path": "../../.env"})["decision"], "block")
        self.assertEqual(self.hook("skill_manage", {"operations": [{"name": "test-driven-development", "action": "delete"}]})["decision"], "block")

    def test_invalid_erp_receipts_never_clear_gates(self):
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(lambda: sys.path.remove(str(SCRIPT.parent)))
        from autonomous_plugin.runtime import erp_record_passed
        # Synthetic report-shape fixtures, not claimed PostgreSQL execution evidence.
        good = {"created": True, "removed": True, "exit_code": 0, "default_off_exit": 0,
                "database": "dms_cycle_test_" + "0" * 32, "unchanged": True,
                "before": {"app/item.py": "0" * 64}, "after": {"app/item.py": "0" * 64},
                "configuration": {"APP_ENV": "test", "POSTING_ENABLED": "false"},
                "counts": {"passed": 2, "failed": 0, "error": 0, "skipped": 0},
                "cases": [{"id": "fixture::one", "status": "passed"}, {"id": "fixture::two", "status": "passed"}],
                "steps": [{"action": "fresh-upgrade"}, {"action": "down-one-up-head"}]}
        self.assertTrue(erp_record_passed(good))
        mutations = [("exit_code", 1), ("default_off_exit", 1), ("database", "medical_dms"),
                     ("configuration", {"APP_ENV": "production", "POSTING_ENABLED": "true"}),
                     ("counts", {"passed": 0, "failed": 0, "error": 0, "skipped": 2}),
                     ("counts", {"passed": 2, "failed": 1, "error": 0, "skipped": 0}),
                     ("steps", []), ("cases", []), ("unchanged", False)]
        for key, value in mutations:
            with self.subTest(field=key, value=value):
                self.assertFalse(erp_record_passed({**good, key: value}))

    def test_scoped_source_read_remains_available(self):
        decision = self.hook("read_file", {"path": str(self.repo / "app/item.py")})
        self.assertNotEqual(decision.get("decision"), "block", decision)


if __name__ == "__main__":
    unittest.main(verbosity=2)
