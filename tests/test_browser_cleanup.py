import subprocess
import sys

from app.browser_cleanup import (
    BrowserInstance,
    cleanup_owned_browsers,
    register_process,
)


def test_cleanup_terminates_only_tracked_owned_process():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    instance = register_process(process)
    assert process.poll() is None

    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        results = cleanup_owned_browsers([instance])
        assert any(r["pid"] == instance.pid and r["action"] == "terminated" for r in results)
        assert process.wait(timeout=5) is not None
        assert other.poll() is None
    finally:
        other.terminate()
        other.wait(timeout=5)


def test_cleanup_skips_pid_reuse():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    instance = register_process(process)
    process.terminate()
    process.wait(timeout=5)

    # Simulate PID reuse by changing the recorded creation time.
    reused = BrowserInstance(
        pid=instance.pid,
        created_at=instance.created_at + 1000,
        parent_pid=instance.parent_pid,
        command=instance.command,
        run_id=instance.run_id,
        launched_at=instance.launched_at,
    )
    results = cleanup_owned_browsers([reused])
    assert results[0]["action"] == "skipped"
    assert results[0]["reason"] == "not_owned_or_pid_reused"
