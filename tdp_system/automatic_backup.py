"""Verified, atomic local snapshots. Never run a worker at import time."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

INTERVAL_SECONDS = 30 * 60
RETENTION_DAYS = 14
_lock = threading.RLock()
_status_cache: dict[str, dict] = {}


def sqlite_snapshot(source: Path, target: Path, *, timeout: float = 30) -> Path:
    """Publish only a complete verified backup; keep any previous target on failure."""
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise ValueError("Backup must not replace the working database")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    reader = writer = None
    deadline = time.monotonic() + timeout

    def progress(_status, _remaining, _total):
        if time.monotonic() >= deadline:
            raise TimeoutError("Database snapshot timed out")

    try:
        # mode=ro must not create an empty source if the customer database is missing.
        reader = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=timeout)
        writer = sqlite3.connect(temporary)
        reader.backup(writer, pages=128, progress=progress, sleep=0.05)
        if writer.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise sqlite3.DatabaseError("Backup integrity check failed")
        writer.close()
        writer = None
        reader.close()
        reader = None
        # Windows _commit requires a writable file descriptor.
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return target
    finally:
        if writer is not None:
            writer.close()
        if reader is not None:
            reader.close()
        temporary.unlink(missing_ok=True)


def backup_status(data_dir: Path) -> dict:
    directory = Path(data_dir) / "auto_backups"
    with _lock:
        state = dict(_status_cache.get(str(directory.resolve()), {}))
        if not state:
            try:
                loaded = json.loads((directory / "status.json").read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    state = loaded
            except (OSError, ValueError):
                pass
        return {"ok": True, "interval_minutes": INTERVAL_SECONDS // 60,
                "retention_days": RETENTION_DAYS, "last_success": state.get("last_success"),
                "last_attempt": state.get("last_attempt"), "error": state.get("error", ""),
                "warning": state.get("warning", ""), "filename": state.get("filename", "")}


def _save_status(directory: Path, state: dict) -> None:
    _status_cache[str(directory.resolve())] = dict(state)
    temporary = directory / f".status-{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, directory / "status.json")
    except OSError:
        # The UI can still show the failure even when the disk is full/read-only.
        state["warning"] = "Không lưu được nhật ký sao lưu trên máy."
        _status_cache[str(directory.resolve())] = dict(state)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def automatic_backup(db_path: Path, data_dir: Path, *, now: datetime | None = None,
                     force: bool = False) -> dict:
    """Refresh today's snapshot every 30 minutes. Failures never delete good copies."""
    now = now or datetime.now()
    directory = Path(data_dir) / "auto_backups"
    with _lock:
        state = backup_status(data_dir)
        target = directory / f"tdp_{now:%Y-%m-%d}.sqlite3"
        try:
            last = datetime.fromisoformat(state["last_success"] or "")
        except (ValueError, TypeError):
            last = None
        if last is not None and last.tzinfo is not None:
            last = None  # Ignore malformed/foreign status instead of stopping the worker.
        if (not force and not state["error"] and last is not None and target.is_file()
                and timedelta(0) <= now - last < timedelta(seconds=INTERVAL_SECONDS)):
            return state
        state.update(last_attempt=now.isoformat(timespec="seconds"), warning="")
        try:
            sqlite_snapshot(Path(db_path), target)
        except (OSError, sqlite3.Error, TimeoutError, ValueError):
            state["error"] = "Chưa sao lưu được. Kiểm tra dung lượng/quyền ghi ổ đĩa; hệ thống sẽ thử lại."
        else:
            state.update(last_success=now.isoformat(timespec="seconds"), filename=target.name, error="")
            try:
                # Only manage our own daily files, never customer files or links.
                copies = [target] + sorted((p for p in directory.iterdir()
                                 if re.fullmatch(r"tdp_\d{4}-\d{2}-\d{2}\.sqlite3", p.name)
                                 and p != target
                                 and p.is_file() and not p.is_symlink()
                                 and p.resolve().parent == directory.resolve()), reverse=True)
                for old in copies[RETENTION_DAYS:]:
                    old.unlink()
            except OSError:
                state["warning"] = "Bản mới đã an toàn; chưa dọn được một số bản sao cũ."
        _save_status(directory, state)
        return dict(state)


def start_backup_worker(callback, *, check_seconds: float = 60):
    """Start once in the application lifecycle, not for API requests or imports."""
    stopped = threading.Event()

    def run():
        while not stopped.wait(check_seconds):
            callback()

    worker = threading.Thread(target=run, name="tdp-auto-backup", daemon=True)
    worker.start()
    return stopped, worker
