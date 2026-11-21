#!/usr/bin/env python3
"""
scripts/backup_and_restore_verified.py

Production‑grade CLI to create a verified PostgreSQL backup, optionally sync it off‑site,
and perform a disposable restore‑drill verification.

Implements the specification from RECOVERY_DRILL_INPUTS.md and Eli Phase 0 Decision T9.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

# --------------------------------------------------------------------------- #
# Logging configuration
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #


def run_subprocess(
    cmd: list[str],
    env: dict | None = None,
    input_data: bytes | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess, capture stdout/stderr, optionally raise on non‑zero exit."""
    log.debug("Running command: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result


def sha256_file(path: Path) -> Tuple[str, int]:
    """Return hex SHA256 digest and file size in bytes."""
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def prune_old_backups(backup_dir: Path, retention_days: int, keep_stem: str) -> None:
    """Delete backup files older than retention_days, never deleting the newly created one."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    pattern = "erp_backup_*.dump"
    for dump_path in backup_dir.glob(pattern):
        if dump_path.stem == keep_stem:
            continue
        try:
            ts_str = dump_path.stem.replace("erp_backup_", "")
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        except Exception:
            continue  # ignore files not matching timestamp pattern
        if ts < cutoff:
            log.info("Pruning old backup: %s", dump_path)
            for suffix in [".dump", ".sha256", "_manifest.json", "_receipt.json"]:
                target = dump_path.with_name(dump_path.stem + suffix)
                if target.exists():
                    target.unlink()


def copy_to_offsite(
    src_dump: Path,
    src_sha: Path,
    offsite_target: str,
) -> None:
    """Copy dump and sha256 side‑car to off‑site location."""
    if offsite_target.startswith("rclone:"):
        remote = offsite_target[len("rclone:") :]
        for p in (src_dump, src_sha):
            cmd = ["rclone", "copyto", str(p), f"{remote}/{p.name}"]
            result = run_subprocess(cmd, check=True)
            log.info("rclone copy %s -> %s completed", p, remote)
    else:
        dest_dir = Path(offsite_target).expanduser().resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        for p in (src_dump, src_sha):
            dest = dest_dir / p.name
            shutil.copy2(p, dest)
            log.info("Copied %s to %s", p, dest)
        # Verify SHA256 match locally
        src_hash, _ = sha256_file(src_dump)
        dest_hash, _ = sha256_file(dest_dir / src_dump.name)
        if src_hash != dest_hash:
            raise RuntimeError("SHA256 mismatch after off‑site copy (local verification)")


def build_pg_command(
    base_cmd: list[str],
    docker_container: str | None,
    env: dict,
) -> list[str]:
    """Wrap a pg_* command with docker exec if needed."""
    if docker_container:
        return ["docker", "exec", "-i", docker_container] + base_cmd
    return base_cmd


def parse_db_url(db_url: str) -> Dict[str, Any]:
    """Parse a PostgreSQL URL into components for psql/pg_dump."""
    url = make_url(db_url)
    return {
        "host": url.host or "localhost",
        "port": str(url.port or 5432),
        "user": url.username or "",
        "password": url.password or "",
        "dbname": url.database or "",
    }


def get_snapshot(engine: Engine) -> Dict[str, Any]:
    """Collect snapshot data from the given engine."""
    snapshot: Dict[str, Any] = {}
    with engine.connect() as conn:
        # alembic version
        version_res = conn.execute(text("SELECT version_num FROM alembic_version"))
        snapshot["alembic_version"] = version_res.scalar() or ""

        # row counts
        tables = [
            ("platform.platform_user", "platform_user"),
            ("master_data.master_branch", "master_branch"),
            ("master_data.master_customer", "master_customer"),
            ("master_data.master_product", "master_product"),
            ("master_data.master_warehouse", "master_warehouse"),
            ("inventory.batch_record", "batch_record"),
            ("inventory.stock_balance", "stock_balance"),
            ("inventory.stock_movement", "stock_movement"),
            ("sales.sales_invoice", "sales_invoice"),
            ("sales.sales_return", "sales_return"),
            ("finance.ar_entry", "ar_entry"),
            ("finance.payment_receipt", "payment_receipt"),
            ("audit.audit_log", "audit_log"),
        ]
        row_counts = {}
        for full_name, short_name in tables:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {full_name}")).scalar()
            row_counts[short_name] = int(cnt)
        snapshot["row_counts"] = row_counts

        # decimal sums
        sums = {}
        sums["stock_balance_quantity"] = float(
            conn.execute(
                text("SELECT COALESCE(SUM(quantity),0) FROM inventory.stock_balance")
            ).scalar()
        )
        sums["sales_invoice_grand_total"] = float(
            conn.execute(
                text(
                    "SELECT COALESCE(SUM(grand_total),0) FROM sales.sales_invoice"
                )
            ).scalar()
        )
        sums["ar_entry_debit"] = float(
            conn.execute(
                text("SELECT COALESCE(SUM(debit),0) FROM finance.ar_entry")
            ).scalar()
        )
        sums["ar_entry_credit"] = float(
            conn.execute(
                text("SELECT COALESCE(SUM(credit),0) FROM finance.ar_entry")
            ).scalar()
        )
        snapshot["decimal_sums"] = sums
    return snapshot


def compare_snapshots(
    before: Dict[str, Any], after: Dict[str, Any]
) -> Tuple[bool, bool, bool]:
    """Return tuple of (alembic_eq, row_counts_eq, decimal_sums_eq)."""
    alembic_eq = before.get("alembic_version") == after.get("alembic_version")
    row_counts_eq = before.get("row_counts") == after.get("row_counts")
    decimal_sums_eq = before.get("decimal_sums") == after.get("decimal_sums")
    return alembic_eq, row_counts_eq, decimal_sums_eq


# --------------------------------------------------------------------------- #
# Core CLI implementation
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verified PostgreSQL backup, off‑site sync, and restore‑drill."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL (default: env DATABASE_URL)",
    )
    parser.add_argument(
        "--backup-dir",
        required=True,
        type=Path,
        help="Directory to store timestamped backup files",
    )
    parser.add_argument(
        "--local-retention-days",
        type=int,
        default=30,
        help="Number of days to retain local backups (default: 30)",
    )
    parser.add_argument(
        "--offsite-target",
        default=os.getenv("BACKUP_OFFSITE_TARGET", ""),
        help="Off‑site target path or rclone remote (empty = local only)",
    )
    parser.add_argument(
        "--docker-pg-container",
        help="Docker container name to run pg_dump/pg_restore via docker exec",
    )
    parser.add_argument(
        "--verify-restore-db",
        help="Disposable DB name for verification (must match dms_cycle_test_<32 hex>)",
    )
    parser.add_argument(
        "--run-corrupt-control",
        action="store_true",
        help="Run a corrupt‑dump control test after successful restore verification",
    )
    args = parser.parse_args()

    if not args.database_url:
        log.error("Database URL must be supplied via --database-url or DATABASE_URL env")
        return 1

    # ------------------------------------------------------------------- #
    # Prepare paths and environment
    # ------------------------------------------------------------------- #
    backup_dir: Path = args.backup_dir.expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    stem = f"erp_backup_{timestamp}"
    dump_path = backup_dir / f"{stem}.dump"
    sha_path = backup_dir / f"{stem}.sha256"
    manifest_path = backup_dir / f"{stem}_manifest.json"
    receipt_path = backup_dir / f"{stem}_receipt.json"
    receipt_sha_path = backup_dir / f"{stem}_receipt.sha256"

    db_params = parse_db_url(args.database_url)

    # ------------------------------------------------------------------- #
    # 1. Capture before‑backup snapshot
    # ------------------------------------------------------------------- #
    engine = create_engine(args.database_url)
    before_snapshot = get_snapshot(engine)
    log.info("Captured before‑backup snapshot")

    # ------------------------------------------------------------------- #
    # 2. Run pg_dump
    # ------------------------------------------------------------------- #
    if args.docker_pg_container:
        pg_dump_cmd = [
            "docker", "exec", "-i", args.docker_pg_container,
            "pg_dump", "-U", db_params["user"], "-d", db_params["dbname"], "--format=custom",
        ]
        result = subprocess.run(pg_dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            log.error("pg_dump failed: %s", result.stderr.decode(errors="replace"))
            return 1
        dump_path.write_bytes(result.stdout)
    else:
        pg_dump_cmd = [
            "pg_dump",
            "--format=custom",
            f"--file={dump_path}",
            f"--dbname=postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}",
        ]
        result = run_subprocess(pg_dump_cmd, check=True)
        if result.returncode != 0:
            log.error("pg_dump failed: %s", result.stderr.decode(errors="replace"))
            return 1
    log.info("Backup dump created at %s", dump_path)

    # SHA256 side‑car
    dump_hash, dump_size = sha256_file(dump_path)
    sha_path.write_text(f"{dump_hash}  {dump_path.name}\n")
    log.info("SHA256 written to %s", sha_path)

    # Manifest (captures snapshot)
    manifest = {
        "timestamp": timestamp,
        "snapshot_before": before_snapshot,
        "dump_sha256": dump_hash,
        "dump_size_bytes": dump_size,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    log.info("Manifest written to %s", manifest_path)

    # Prune old local backups
    prune_old_backups(backup_dir, args.local_retention_days, stem)

    # ------------------------------------------------------------------- #
    # 3. Off‑site copy (if requested)
    # ------------------------------------------------------------------- #
    if args.offsite_target:
        try:
            copy_to_offsite(dump_path, sha_path, args.offsite_target)
            log.info("Off‑site copy completed")
        except Exception as exc:
            log.error("Off‑site copy failed: %s", exc)
            return 1

    # ------------------------------------------------------------------- #
    # 4. Optional restore verification
    # ------------------------------------------------------------------- #
    verification_passed = False
    corrupt_control_passed = None
    after_snapshot = {}
    if args.verify_restore_db:
        # Validate DB name pattern
        pattern = r"^dms_cycle_test_[0-9a-f]{32}$"
        if not re.fullmatch(pattern, args.verify_restore_db):
            log.error(
                "Invalid verify‑restore DB name. Must match %s", pattern
            )
            return 1

        # Build connection strings for admin operations (use postgres db with psycopg3 + AUTOCOMMIT)
        admin_url = f"postgresql+psycopg://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/postgres"
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

        # Drop & create disposable DB
        try:
            with admin_engine.connect() as conn:
                conn.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :dbname"),
                    {"dbname": args.verify_restore_db},
                )
                conn.execute(text(f"DROP DATABASE IF EXISTS {args.verify_restore_db}"))
                conn.execute(text(f"CREATE DATABASE {args.verify_restore_db}"))
            log.info("Disposable DB %s created", args.verify_restore_db)
        except Exception as exc:
            log.error("Failed to create disposable DB: %s", exc)
            return 1

        # Restore dump into disposable DB
        if args.docker_pg_container:
            pg_restore_cmd = [
                "docker", "exec", "-i", args.docker_pg_container,
                "pg_restore", "-U", db_params["user"], "-d", args.verify_restore_db,
                "--exit-on-error", "--no-owner", "--no-privileges",
            ]
            result = subprocess.run(pg_restore_cmd, input=dump_path.read_bytes(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        else:
            pg_restore_cmd = [
                "pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
                f"--dbname=postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{args.verify_restore_db}",
                str(dump_path),
            ]
            result = run_subprocess(pg_restore_cmd, check=False)
        if result.returncode != 0:
            log.error("pg_restore failed: %s", result.stderr.decode(errors="replace"))
            return 1
        log.info("Restore into disposable DB succeeded")

        # Capture after-restore snapshot
        restore_engine = create_engine(
            f"postgresql+psycopg://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{args.verify_restore_db}"
        )
        after_snapshot = get_snapshot(restore_engine)
        restore_engine.dispose()
        log.info("Captured after-restore snapshot")

        # Compare snapshots
        alembic_eq, rows_eq, sums_eq = compare_snapshots(before_snapshot, after_snapshot)
        if not (alembic_eq and rows_eq and sums_eq):
            log.error("Snapshot mismatch: alembic=%s rows=%s sums=%s", alembic_eq, rows_eq, sums_eq)
            verification_passed = False
        else:
            verification_passed = True
            log.info("Restore verification passed")

        # Corrupt control test
        if args.run_corrupt_control:
            corrupt_bytes = os.urandom(64)
            if args.docker_pg_container:
                corrupt_cmd = [
                    "docker", "exec", "-i", args.docker_pg_container,
                    "pg_restore", "-U", db_params["user"], "-d", args.verify_restore_db,
                    "--exit-on-error", "--no-owner", "--no-privileges",
                ]
                corrupt_res = subprocess.run(corrupt_cmd, input=corrupt_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            else:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(corrupt_bytes)
                    corrupt_path = Path(tmp.name)
                corrupt_cmd = [
                    "pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
                    f"--dbname=postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{args.verify_restore_db}",
                    str(corrupt_path),
                ]
                corrupt_res = run_subprocess(corrupt_cmd, check=False)
                corrupt_path.unlink(missing_ok=True)
            corrupt_control_passed = corrupt_res.returncode != 0
            log.info("Corrupt control rejected=%s", corrupt_control_passed)

        # Cleanup disposable DB
        try:
            with admin_engine.connect() as conn:
                conn.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :dbname"),
                    {"dbname": args.verify_restore_db},
                )
                conn.execute(text(f"DROP DATABASE IF EXISTS {args.verify_restore_db}"))
            admin_engine.dispose()
            log.info("Disposable DB %s dropped", args.verify_restore_db)
            restored_db_removed = True
        except Exception as exc:
            log.error("Failed to drop disposable DB: %s", exc)
            restored_db_removed = False

    # ------------------------------------------------------------------- #
    # 5. Write receipt
    # ------------------------------------------------------------------- #
    receipt = {
        "backup_dump": str(dump_path),
        "backup_sha256": dump_hash,
        "backup_size_bytes": dump_size,
        "timestamp_utc": timestamp,
        "local_retention_days": args.local_retention_days,
        "offsite_target": args.offsite_target,
        "verification": {
            "requested": bool(args.verify_restore_db),
            "db_name": args.verify_restore_db or None,
            "passed": verification_passed,
            "corrupt_control_requested": args.run_corrupt_control,
            "corrupt_control_passed": corrupt_control_passed,
            "restored_db_removed": restored_db_removed if args.verify_restore_db else None,
        },
        "snapshot_before": before_snapshot,
        "snapshot_after": after_snapshot if args.verify_restore_db else None,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, default=str))
    receipt_hash, _ = sha256_file(receipt_path)
    receipt_sha_path.write_text(f"{receipt_hash}  {receipt_path.name}\n")
    log.info("Receipt written to %s", receipt_path)

    # ------------------------------------------------------------------- #
    # Exit status
    # ------------------------------------------------------------------- #
    if args.verify_restore_db and not verification_passed:
        log.error("Verification failed – exiting with status 1")
        return 1
    if args.run_corrupt_control and not corrupt_control_passed:
        log.error("Corrupt control test failed – exiting with status 1")
        return 1
    log.info("All operations completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
