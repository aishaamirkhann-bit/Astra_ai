"""Database backup utility.

PostgreSQL: pg_dump (custom format, gzip-compressed) into BACKUP_DIR.
SQLite:     timestamped file copy.

Usage:
    python -m scripts.backup_db [--keep 7] [--dir backups]

Credentials come from DATABASE_URL; the password is passed to pg_dump via
PGPASSWORD (never on the command line).
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def _find_pg_dump() -> str:
    if shutil.which("pg_dump"):
        return "pg_dump"
    for candidate in (
        Path("C:/Program Files/PostgreSQL/18/bin/pg_dump.exe"),
        Path("C:/Program Files/PostgreSQL/17/bin/pg_dump.exe"),
        Path("C:/Program Files/PostgreSQL/16/bin/pg_dump.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    raise SystemExit("pg_dump not found on PATH or in common Windows install locations.")


def backup_postgres(url: str, out_dir: Path) -> Path:
    parsed = urlparse(url)
    env = {
        **__import__("os").environ,
        "PGHOST": parsed.hostname or "localhost",
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": parsed.username or "postgres",
        "PGDATABASE": (parsed.path or "/postgres").lstrip("/"),
    }
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"astra_db_{stamp}.dump"
    cmd = [_find_pg_dump(), "--format=custom", "--compress=gzip:6", "--file", str(target)]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"pg_dump failed: {result.stderr.strip()[:500]}")
    return target


def backup_sqlite(url: str, out_dir: Path) -> Path:
    source = Path(url.replace("sqlite:///", ""))
    if not source.exists():
        raise SystemExit(f"SQLite file not found: {source}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"astra_db_{stamp}.sqlite.bak"
    shutil.copy2(source, target)
    return target


def prune(out_dir: Path, keep: int) -> list[Path]:
    dumps = sorted(out_dir.glob("astra_db_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = dumps[keep:]
    for stale in removed:
        stale.unlink()
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup the ASTRA AI database")
    parser.add_argument("--dir", default="backups", help="output directory (default: ./backups)")
    parser.add_argument("--keep", type=int, default=7, help="number of backups to retain (default: 7)")
    args = parser.parse_args()

    out_dir = Path(args.dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    url = settings.DATABASE_URL
    target = backup_postgres(url, out_dir) if url.startswith("postgres") else backup_sqlite(url, out_dir)
    removed = prune(out_dir, args.keep)
    size_kb = target.stat().st_size / 1024
    print(f"backup written: {target} ({size_kb:.0f} KB)")
    for stale in removed:
        print(f"pruned: {stale.name}")


if __name__ == "__main__":
    main()
