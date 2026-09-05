from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from pathlib import Path

try:
    from invoice_date_migration import repair_legacy_input_dates
except ImportError:
    from .invoice_date_migration import repair_legacy_input_dates


CONNECTOR_VARIABLES = (
    "MSMI_API_BASE_URL",
    "MSMI_API_TOKEN",
    "MINVOICE_API_BASE_URL",
    "MINVOICE_USERNAME",
    "MINVOICE_PASSWORD",
    "MINVOICE_UNIT_CODE",
)
REQUIRED_CONNECTOR_VARIABLES = set(CONNECTOR_VARIABLES[:5])


def snapshot_database(source_path: Path, target_path: Path) -> int:
    temporary = target_path.with_name(f".{target_path.name}.{uuid.uuid4().hex}.tmp")
    source = destination = None
    try:
        source = sqlite3.connect(
            f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True, timeout=30
        )
        destination = sqlite3.connect(temporary)
        source.backup(destination)
        # Correct only this snapshot, never the operational source database.
        date_repair = repair_legacy_input_dates(destination)
        if date_repair["blocked"]:
            raise sqlite3.DatabaseError(
                f"DB khởi tạo còn {date_repair['blocked']} hóa đơn cần đối chiếu ngày; dừng đóng gói"
            )
        destination.commit()
        integrity = str(destination.execute("PRAGMA quick_check(1)").fetchone()[0])
        destination.close()
        destination = None
        source.close()
        source = None
        if integrity.lower() != "ok":
            raise sqlite3.DatabaseError("Dữ liệu nguồn không vượt qua kiểm tra toàn vẹn")
        os.replace(temporary, target_path)
        return target_path.stat().st_size
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
        temporary.unlink(missing_ok=True)


def write_connector_config(source_path: Path, target_path: Path) -> list[str]:
    selected: dict[str, str] = {}
    for raw_line in source_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _separator, value = line.partition("=")
        key = key.strip()
        if key in CONNECTOR_VARIABLES:
            selected[key] = f"{key}={value}"
    missing = sorted(REQUIRED_CONNECTOR_VARIABLES - selected.keys())
    if missing:
        raise RuntimeError("Thiếu tên biến kết nối bắt buộc: " + ", ".join(missing))
    target_path.write_text(
        "\n".join(selected[key] for key in CONNECTOR_VARIABLES if key in selected) + "\n",
        encoding="utf-8",
    )
    return sorted(selected)


def write_version_file(target_path: Path):
    target_path.write_text(
        """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2026, 9, 5, 2), prodvers=(2026, 9, 5, 2),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Xandro'),
        StringStruct('FileDescription', 'Thanh Dat Phat - He thong quan ly'),
        StringStruct('FileVersion', '2026.09.05.2'),
        StringStruct('InternalName', 'Thanh_Dat_Phat'),
        StringStruct('LegalCopyright', 'Copyright 2026 Xandro'),
        StringStruct('OriginalFilename', 'Thanh_Dat_Phat.exe'),
        StringStruct('ProductName', 'Thanh Dat Phat'),
        StringStruct('ProductVersion', '2026.09.05.2')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if not args.database.is_file():
        raise FileNotFoundError(args.database)
    if not args.env_file.is_file():
        raise FileNotFoundError(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    seed_path = args.output_dir / "tdp_seed.sqlite3"
    connector_path = args.output_dir / "connector.env"
    version_path = args.output_dir / "version_info.txt"
    seed_size = snapshot_database(args.database, seed_path)
    variable_names = write_connector_config(args.env_file, connector_path)
    write_version_file(version_path)
    print(json.dumps({
        "ok": True,
        "database_integrity": "ok",
        "database_size": seed_size,
        "connector_variable_names": variable_names,
        "secret_values_logged": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
