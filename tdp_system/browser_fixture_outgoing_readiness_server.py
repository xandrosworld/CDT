"""Disposable, synthetic-only server for the outgoing-readiness browser check."""
import os
import tempfile
from pathlib import Path
from datetime import date


def main():
    from waitress import serve
    with tempfile.TemporaryDirectory(prefix="tdp_outgoing_browser_") as temp:
        os.environ["TDP_DATA_DIR"] = str(Path(temp) / "data")
        os.environ["TDP_DB_PATH"] = str(Path(temp) / "fixture.sqlite3")
        os.environ["TDP_EXPORT_DIR"] = str(Path(temp) / "exports")
        from . import server
        from .test_outgoing_readiness import OutgoingReadinessTests
        server.init_database()
        server.app.config["TESTING"] = True
        today = date.today().isoformat()
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO products(code,name,unit) VALUES('HH-01','Hàng kiểm thử','kg')")
            OutgoingReadinessTests.add_opening(conn, 7)
            batch_id, _ = OutgoingReadinessTests.add_batch(conn, today, [{"qty": 10}])
        @server.app.post("/fixture/add-three")
        def add_three():
            with server.db() as conn:
                OutgoingReadinessTests.add_canonical_event(conn, 3, "input", "BROWSER-INPUT-3", work_date=today)
            return {"ok": True, "batch_id": batch_id}
        print("SYNTHETIC_FIXTURE_READY", flush=True)
        serve(server.app, host="127.0.0.1", port=18799, threads=4)


if __name__ == "__main__":
    main()
