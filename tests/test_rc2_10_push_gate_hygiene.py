import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
PUSH_SCRIPT = SCRIPTS_DIR / "push_if_signed.ps1"
BACKUP_SCRIPT = SCRIPTS_DIR / "backup_local_branches.ps1"


def read_script(path: Path) -> str:
    assert path.is_file(), f"Script not found: {path}"
    return path.read_text(encoding="utf-8")


def _assert_not_contains(content: str, substr: str, msg: str):
    assert substr not in content, msg


def _assert_contains(content: str, substr: str, msg: str):
    assert substr in content, msg


def test_push_if_signed_exists_and_enforces_owner_orders_4_and_6():
    content = read_script(PUSH_SCRIPT)

    # Owner Order 4 – no --no-verify bypass
    _assert_not_contains(
        content,
        "--no-verify",
        "The script should not allow '--no-verify' bypass.",
    )

    # Owner Order 6 – private‑repo stop precondition must NOT be a refusal gate
    _assert_not_contains(
        content,
        "private-repo",
        "The script must not abort on private‑repo visibility.",
    )

    # Author/committer identity check
    _assert_contains(
        content,
        "242167870+Eli-Mira@users.noreply.github.com",
        "Missing author/committer identity enforcement.",
    )

    # gitleaks check over pushed range
    _assert_contains(
        content,
        "gitleaks",
        "Missing gitleaks invocation.",
    )

    # .sha256 side‑car verification
    _assert_contains(
        content,
        ".sha256",
        "Missing .sha256 side‑car handling.",
    )

    # ELI_PUSH_OK controlled setting/cleanup
    _assert_contains(
        content,
        "ELI_PUSH_OK",
        "Missing ELI_PUSH_OK handling.",
    )

    # RC1Archival / R4 gate handling
    rc1_present = "RC1Archival" in content
    r4_present = "R4" in content
    assert rc1_present or r4_present, "Missing RC1Archival or R4 gate handling."


def test_backup_local_branches_exists_and_is_non_destructive():
    content = read_script(BACKUP_SCRIPT)

    # Must use git bundle create with --all
    _assert_contains(
        content,
        "git bundle create",
        "Missing 'git bundle create' command.",
    )
    _assert_contains(
        content,
        "--all",
        "Missing '--all' flag for git bundle.",
    )

    # Must create .sha256 side‑cars
    _assert_contains(
        content,
        ".sha256",
        "Missing .sha256 side‑car generation.",
    )

    # Keep last 3 backups (simple heuristic: reference to 3 and removal logic)
    _assert_contains(
        content,
        "3",
        "Script does not appear to limit retained backups to three.",
    )
    _assert_contains(
        content,
        "Remove-Item",
        "Script should remove old backups but not delete branches.",
    )

    # Must never contain destructive git worktree or branch commands
    destructive_patterns = [
        "git worktree remove",
        "git worktree prune",
        "git branch -D",
    ]
    for pat in destructive_patterns:
        _assert_not_contains(
            content,
            pat,
            f"Destructive command found in backup script: '{pat}'.",
        )


def _run_powershell_parser(pwsh_exe: str, script_path: Path) -> int:
    # PowerShell command to parse a file and output the number of parse errors
    cmd = [
        pwsh_exe,
        "-NoProfile",
        "-Command",
        (
            "$errors = $null; "
            "$null = [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script_path}', [ref]$null, [ref]$errors); "
            "$errors.Count"
        ),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"PowerShell parser invocation failed: {result.stderr.strip()}")
    try:
        return int(result.stdout.strip())
    except ValueError:
        pytest.fail(f"Unable to parse PowerShell error count from output: {result.stdout!r}")


@pytest.mark.parametrize(
    "script_path",
    [PUSH_SCRIPT, BACKUP_SCRIPT],
)
def test_powershell_scripts_parse_with_zero_syntax_errors(script_path: Path):
    pwsh = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not pwsh:
        pytest.skip("No PowerShell executable found on this system.")
    error_count = _run_powershell_parser(pwsh, script_path)
    assert error_count == 0, f"PowerShell syntax errors in {script_path.name}: {error_count}"
