"""Run-scoped browser process ownership and cleanup.

This module never terminates browsers by image name. It tracks only processes
launched by the current run, verifies that the original process is still the
same process before signaling it, and closes those instances on normal exit or
explicit cleanup.
"""

from __future__ import annotations

import atexit
import os
import time
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a project dependency
    psutil = None


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = uuid.uuid4().hex
TRACKED: list[BrowserInstance] = []
_CLEANUP_REGISTERED = False


@dataclass
class BrowserInstance:
    pid: int
    created_at: float
    parent_pid: int
    command: tuple[str, ...]
    run_id: str
    launched_at: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _process_markers(command: Iterable[str]) -> bool:
    joined = " ".join(command).lower()
    return any(marker in joined for marker in ("chrome", "chromium", "msedge", "playwright"))


def register_process(process: Any, *, run_id: str | None = None) -> BrowserInstance:
    """Register an OS process launched by this run."""
    if psutil is None:
        raise RuntimeError("psutil is required for owned browser cleanup")
    proc = psutil.Process(process.pid if hasattr(process, "pid") else int(process))
    instance = BrowserInstance(
        pid=proc.pid,
        created_at=proc.create_time(),
        parent_pid=proc.ppid(),
        command=tuple(proc.cmdline()),
        run_id=run_id or RUN_ID,
        launched_at=time.time(),
    )
    TRACKED.append(instance)
    _register_atexit()
    return instance


def _owned(instance: BrowserInstance) -> bool:
    if psutil is None:
        return False
    try:
        proc = psutil.Process(instance.pid)
    except psutil.NoSuchProcess:
        return False
    # PID-reuse protection: the process must still be the same one we launched.
    if abs(proc.create_time() - instance.created_at) > 0.001:
        return False
    # Verified ownership: the process must remain a child of this process tree.
    if instance.parent_pid != os.getpid() and instance.parent_pid not in _ancestor_pids():
        return False
    return tuple(proc.cmdline()) == instance.command


def _ancestor_pids() -> set[int]:
    pids: set[int] = set()
    try:
        current = psutil.Process(os.getpid())
    except (psutil.Error, OSError):
        return pids
    while True:
        pids.add(current.pid)
        try:
            parent = current.parent()
        except (psutil.Error, OSError):
            break
        if parent is None or parent.pid == current.pid:
            break
        current = parent
    return pids


def cleanup_owned_browsers(
    instances: list[BrowserInstance] | None = None,
) -> list[dict[str, object]]:
    """Terminate only owned, verified browser instances and their descendants."""
    targets = list(instances if instances is not None else TRACKED)
    results: list[dict[str, object]] = []
    for instance in reversed(targets):
        if not _owned(instance):
            results.append(
                {
                    "pid": instance.pid,
                    "action": "skipped",
                    "reason": "not_owned_or_pid_reused",
                }
            )
            continue
        try:
            proc = psutil.Process(instance.pid)
            descendants = []
            try:
                descendants = proc.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                descendants = []
            for child in reversed(descendants):
                try:
                    child.terminate()
                    child.wait(timeout=2)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                except (psutil.Error, OSError):  # pragma: no cover - defensive
                    pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            results.append({"pid": instance.pid, "action": "terminated"})
        except psutil.NoSuchProcess:
            results.append({"pid": instance.pid, "action": "already_exited"})
        except (psutil.Error, OSError) as exc:  # pragma: no cover - defensive
            results.append({"pid": instance.pid, "action": "error", "reason": str(exc)})

    if instances is None:
        TRACKED[:] = [item for item in TRACKED if item not in targets]
    return results


def _register_atexit() -> None:
    global _CLEANUP_REGISTERED
    if not _CLEANUP_REGISTERED:
        atexit.register(cleanup_owned_browsers)
        _CLEANUP_REGISTERED = True


def launch_owned_process(command: list[str], **popen_kwargs) -> tuple[Any, BrowserInstance]:
    """Launch a subprocess and register it for owned cleanup."""
    import subprocess

    process = subprocess.Popen(command, **popen_kwargs)
    instance = register_process(process)
    return process, instance
