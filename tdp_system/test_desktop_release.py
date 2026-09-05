from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

try:
    from . import server
    from .build_release_inputs import snapshot_database, write_connector_config
except ImportError:
    import server
    from build_release_inputs import snapshot_database, write_connector_config


class DesktopReleaseTests(unittest.TestCase):
    def test_seed_database_installs_once_and_never_overwrites_user_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.sqlite3"
            target = root / "data" / "tdp.sqlite3"
            with closing(sqlite3.connect(seed)) as connection:
                connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
                connection.execute("INSERT INTO marker(value) VALUES('seed')")
                connection.commit()

            self.assertTrue(server.install_seed_database_if_missing(seed, target))
            with closing(sqlite3.connect(target)) as connection:
                connection.execute("UPDATE marker SET value='customer-change'")
                connection.commit()
            self.assertFalse(server.install_seed_database_if_missing(seed, target))
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual("customer-change", connection.execute(
                    "SELECT value FROM marker"
                ).fetchone()[0])

    def test_release_input_snapshot_is_consistent_and_config_is_filtered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            snapshot = root / "snapshot.sqlite3"
            env_file = root / ".env"
            connector_file = root / "connector.env"
            with closing(sqlite3.connect(source)) as connection:
                connection.execute("CREATE TABLE marker(value INTEGER NOT NULL)")
                connection.execute("INSERT INTO marker(value) VALUES(7)")
                connection.commit()
            env_file.write_text(
                "MSMI_API_BASE_URL=http://example.invalid\n"
                "MSMI_API_TOKEN=test-token\n"
                "MINVOICE_API_BASE_URL=http://example.invalid\n"
                "MINVOICE_USERNAME=test-user\n"
                "MINVOICE_PASSWORD=test-password\n"
                "GEMINI_API_KEY=must-not-be-packaged\n",
                encoding="utf-8",
            )

            self.assertGreater(snapshot_database(source, snapshot), 0)
            names = write_connector_config(env_file, connector_file)
            self.assertNotIn("GEMINI_API_KEY", names)
            self.assertNotIn("GEMINI_API_KEY", connector_file.read_text(encoding="utf-8"))
            with closing(sqlite3.connect(snapshot)) as connection:
                self.assertEqual("ok", connection.execute("PRAGMA quick_check(1)").fetchone()[0])
                self.assertEqual(7, connection.execute("SELECT value FROM marker").fetchone()[0])

    def test_single_exe_build_contract_and_runtime_port_are_wired(self):
        root = Path(__file__).resolve().parent.parent
        build_script = (root / "BUILD_SINGLE_EXE.ps1").read_text(encoding="utf-8")
        server_source = (Path(server.__file__)).read_text(encoding="utf-8")
        for marker in (
            "--onefile", "--name Thanh_Dat_Phat_candidate",
            "connector.env;config", "tdp_seed.sqlite3;seed",
            "BAN_GIAO_TDP_MOT_FILE_20260905", "Thanh_Dat_Phat.exe",
        ):
            self.assertIn(marker, build_script)
        self.assertIn("open_browser(runtime_port", server_source)
        self.assertIn("Local\\\\ThanhDatPhatDesktopApplication", server_source)
        self.assertIn("install_seed_database_if_missing()", server_source)

    def test_packaged_smoke_instance_is_limited_to_windows_temp_paths(self):
        self.assertEqual(
            "Local\\ThanhDatPhatDesktopApplication",
            server.single_instance_mutex_name(),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            smoke_environment = {
                "TDP_SMOKE_INSTANCE_ID": "release-20260904",
                "TDP_DATA_DIR": str(root / "data"),
                "TDP_DB_PATH": str(root / "data" / "smoke.sqlite3"),
                "TDP_EXPORT_DIR": str(root / "exports"),
                "TDP_PORT": "18804",
            }
            with patch.dict(os.environ, smoke_environment, clear=False), patch.object(
                sys, "argv", ["server.py", "--smoke-test-instance"]
            ):
                mutex_name = server.single_instance_mutex_name()
                self.assertTrue(mutex_name.startswith(
                    "Local\\ThanhDatPhatDesktopApplicationSmoke_"
                ))
                self.assertNotEqual("Local\\ThanhDatPhatDesktopApplication", mutex_name)

                os.environ["TDP_DATA_DIR"] = str(Path.cwd())
                with self.assertRaisesRegex(RuntimeError, "thư mục tạm Windows"):
                    server.single_instance_mutex_name()


if __name__ == "__main__":
    unittest.main()
