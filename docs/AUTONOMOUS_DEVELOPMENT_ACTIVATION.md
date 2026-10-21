# Autonomous Development — Activation & Deactivation Guide

## Overview

This guide documents how to activate and deactivate the **autonomous-development** opt-in mode for the Medical ERP project. The mode is a project-owned plugin that provides:

- Persistent task queue with claims and reviews
- Git checkpoints bound to frozen verified commits
- Verified commits with independent reviewer receipts
- Thread-safe atomic state writes with generation checks
- Native process-tree interruption recovery
- Fail-closed policy: unapproved invocation is blocked, missing identity is blocked

**Activation is NOT a shortcut.** It requires the `safety_ready` flag to be True, verified by a real source provenance check. You cannot set `safety_ready = True` manually to bypass the gates.

---

## Prerequisites

1. Working clone of `C:\Users\emadg\Desktop\Huge system`
2. Approved ERP Python interpreter (Python 3.x)
3. `scripts/verify_invoice_cycle.py` present and non-empty
4. `AGENTS.md` present (safety rules)
5. `requirements.txt` present
6. PostgreSQL server reachable for isolated test DBs (not production)
7. POSTING_ENABLED must be OFF for all autonomous work

---

## Step 1 — Setup/Activation (Trusted Source-Bound)

```bash
cd "C:\Users\emadg\Desktop\Huge system"

# 1. Create state at a fresh path
"C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" \
  tools\autonomous_development.py \
  --state "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\state.json" \
  --root "C:\Users\emadg\Desktop\Huge system" \
  --db "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\native.db" \
  setup
```

The `setup` action:

- Creates a new state file
- Runs `safety_check()`:
  - Frozen source provenance: `git rev-parse HEAD` matches the locked base commit
  - Approved interpreter: python3.x exists and is probeable
  - Safe recipe: `scripts/verify_invoice_cycle.py` present and non-empty
  - Protection gates: POSTING_ENABLED OFF, protected files are regular files
- Sets `safety_ready = True` only if all checks pass
- Records `setup_check.provenance` for audit trail

If any check fails, `safety_ready` remains False and the mode is NOT active. You must fix the failing gate before proceeding.

---

## Step 2 — Verify the Setup

```bash
"C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" \
  tools\autonomous_development.py \
  --state "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\state.json" \
  status
```

Expected output:

```json
{
  "enabled": false,
  "board": "medical-erp-autonomous",
  "queue": []
}
```

---

## Step 3 — Enable Autonomous Mode

```bash
"C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" \
  tools\autonomous_development.py \
  --state "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\state.json" \
  enable
```

`set_enabled()` enforces:

- For non-synthetic boards: `safety_ready` must be True
- For synthetic-only boards: safety check is skipped

Never set `safety_ready: True` manually. It is only set by a real `safety_check` run.

---

## Step 4 — Start Native Persistent Continuation (Daemon)

```bash
"C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" \
  tools\autonomous_development.py \
  --state "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\state.json" \
  daemon
```

The daemon loop:

- Runs `continue_flow()` at the configured cadence (default 60 seconds)
- Saves state atomically after each cycle
- Handles SIGTERM and SIGINT gracefully (sets `enabled: False`, saves state)
- Only runs when `enabled: True`

---

## Step 5 — Add an Approved Task (Opt-In)

Tasks must be approved before the autonomous loop picks them up. Use the `add` action with a manifest:

```bash
"C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" \
  tools\autonomous_development.py \
  --state "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\state.json" \
  add \
  --task "C:\Users\emadg\Desktop\Huge system\tools\autonomous_tests\manifest.json"
```

Task constraints enforced by the plugin:

- `kind` must be `erp` (real ERP tests) or `synthetic` (isolated tests only)
- `allowed_paths` must not include protected files
- `approved: true` required
- `approval_required: false` required

---

## Deactivation

```bash
"C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" \
  tools\autonomous_development.py \
  --state "C:\Users\emadg\Desktop\Huge system\.hermes\autonomous-development\state.json" \
  disable
```

Disabling:

- Sets `enabled: False`
- Revokes task assignments (all `ready`, `review`, `todo`, `blocked` tasks unattended)
- Persists state atomically

The daemon loop exits on the next cycle after `disabled: False` is persisted.

---

## Stopping Conditions

The autonomous loop stops when:

- No safe approved unblocked task remains
- Failure budget (3 attempts) exhausted for the active task
- Verification fails after retries
- A required business decision cannot be established
- Financial or inventory correctness cannot be verified
- A security concern cannot be resolved safely
- A destructive or irreversible operation requires authorization
- Protected production data, credentials, or deployment rules are at risk
- No safe authorized work remains

---

## Safety Boundaries

- Never enable production invoice posting
- Never run migrations against quarantined `medical_dms`
- Never modify source Excel workbooks
- Never modify protected configuration files
- Never merge into `master` or push code remotely
- Never publish or deploy the ERP
- Never ingest real company chats without approval
- Never transmit sensitive company data to unapproved model providers
- Never treat unverified code as completed work

---

## Activation / Deactivation Keys

| Key | Value | Meaning |
|-----|-------|---------|
| `enabled` | bool | Mode on/off (driver) |
| `safety_ready` | bool | Source/provenance verified (hard gate) |
| `setup_check.provenance` | `verified` \| `blocked` | Result of the real safety check |
| `last_verified_commit` | commit SHA | Last accepted autonomous checkpoint |
| `tasks.<id>.attempts` | int (0–3) | Failure budget remaining |
| `tasks.<id>.verified_commit` | commit SHA | Checkpointed commit |
| `tasks.<id>.review` | object | Independent reviewer receipt |

---

## Evidence Location

- Plan: `docs/AGENT_HANDOFF.md`
- Current gate status: `docs/PROGRESS_CHECKLIST.md`
- Risk-based gates: `docs/SPEC_COVERAGE_MATRIX.md`
- Native test evidence: `C:\Users\emadg\AppData\Local\hermes\audits\medical-dms\autonomous-core-20261021-034025\`

---

## Notes

- Activation is reversible: `disable` stops the loop and revokes assignments.
- `safety_ready` must never be manually True; the setup command runs real checks.
- Protected files (`app/db.py`, `app/config.py`, `scripts/verify_invoice_cycle.py`, etc.) are never writable by the autonomous loop.
- The daemon loop is a native process — it survives between Hermes turns.
