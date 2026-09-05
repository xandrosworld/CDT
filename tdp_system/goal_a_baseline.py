"""Reproducible Goal A baseline with a source-database mutation guard.

Run from the repository root on Windows with::

    $env:PYTHONUTF8 = "1"
    python -m tdp_system.goal_a_baseline

The command never reads or prints ``.env`` values. Unit tests and QC may use
temporary databases, but the canonical source database must remain byte-for-
byte unchanged throughout the run.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "tdp_system"
SOURCE_DB = APP_DIR / "data" / "tdp.sqlite3"


class BaselineGuardError(RuntimeError):
    """Raised when the baseline is unsafe or one of its checks fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_source_database(path: Path = SOURCE_DB) -> str:
    if not path.is_file() or path.stat().st_size <= 0:
        raise BaselineGuardError(f"Không tìm thấy database nguồn hợp lệ: {path}")
    return sha256_file(path)


def assert_database_unchanged(path: Path, expected_hash: str, stage: str) -> None:
    actual_hash = require_source_database(path)
    if actual_hash != expected_hash:
        raise BaselineGuardError(
            f"Database nguồn đã thay đổi ngoài ý muốn trong bước {stage}. "
            "Dừng Goal và kiểm tra bản sao lưu trước khi tiếp tục."
        )


def run_guarded_command(
    command: Iterable[str],
    *,
    stage: str,
    database_path: Path,
    expected_hash: str,
) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(list(command), cwd=ROOT, env=env, check=False)
    assert_database_unchanged(database_path, expected_hash, stage)
    if completed.returncode != 0:
        raise BaselineGuardError(f"Bước {stage} thất bại với mã {completed.returncode}")


def check_source_health(database_path: Path, expected_hash: str) -> dict[str, object]:
    try:
        from . import server
    except ImportError:  # pragma: no cover - direct file invocation fallback
        import server  # type: ignore

    previous_path = server.DB_PATH
    try:
        server.DB_PATH = database_path
        response = server.app.test_client().get("/health")
        payload = response.get_json(silent=True) or {}
    finally:
        server.DB_PATH = previous_path

    assert_database_unchanged(database_path, expected_hash, "/health")
    required = {
        "status": response.status_code,
        "ok": payload.get("ok"),
        "database_ready": payload.get("database_ready"),
        "schema_ready": payload.get("schema_ready"),
        "integrity": payload.get("integrity"),
    }
    if required != {
        "status": 200,
        "ok": True,
        "database_ready": True,
        "schema_ready": True,
        "integrity": "ok",
    }:
        raise BaselineGuardError(f"/health source không đạt: {required}")
    return required


def main() -> int:
    try:
        source_hash = require_source_database()
        print("[baseline] Database guard: ready")

        run_guarded_command(
            [sys.executable, "-m", "unittest", "discover", "-s", "tdp_system", "-p", "test_*.py"],
            stage="unit tests",
            database_path=SOURCE_DB,
            expected_hash=source_hash,
        )
        print("[baseline] Unit tests: passed; source database unchanged")

        run_guarded_command(
            [sys.executable, "-m", "tdp_system.qc_system"],
            stage="QC",
            database_path=SOURCE_DB,
            expected_hash=source_hash,
        )
        print("[baseline] QC: passed; source database unchanged")

        health = check_source_health(SOURCE_DB, source_hash)
        print(
            "[baseline] /health: "
            f"ok={str(health['ok']).lower()}, "
            f"database_ready={str(health['database_ready']).lower()}, "
            f"schema_ready={str(health['schema_ready']).lower()}, "
            f"integrity={health['integrity']}"
        )
        print(f"[baseline] Source database SHA-256 unchanged: {source_hash}")
        return 0
    except BaselineGuardError as error:
        print(f"[baseline] FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
