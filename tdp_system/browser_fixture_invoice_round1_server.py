"""Local-only fixture. Never opens the operational database or remote connectors."""
import os
import tempfile
from pathlib import Path


def main():
    from waitress import serve
    with tempfile.TemporaryDirectory(prefix="invoice_round1_", dir="D:/TDP_ROUND1") as temp:
        os.environ["TDP_DATA_DIR"] = str(Path(temp) / "data")
        os.environ["TDP_DB_PATH"] = str(Path(temp) / "fixture.sqlite3")
        os.environ["TDP_EXPORT_DIR"] = str(Path(temp) / "exports")
        from . import server
        from .test_invoice_workbench_listing import seed_round1
        server.init_database()
        with server.db() as conn:
            fixture = seed_round1(conn, extra_lines=18)
        # Hard block every network connector route in this browser fixture.
        @server.app.before_request
        def prevent_remote_access():
            from flask import request
            if request.method != "GET" and any(part in request.path for part in ["/sync", "/minvoice/"]):
                return {"ok":False,"error":"Remote writes disabled in browser fixture"}, 403
        @server.app.get("/fixture/ids")
        def ids():
            return {"ok":True, **fixture}
        @server.app.post("/fixture/scale-up")
        def scale_up():
            from .test_invoice_workbench_listing import prepare
            from .test_invoice_input_sync import DateBoundedMsmi, now_iso
            from .test_msmi_sync import remote_invoice
            from .invoice_input_sync import sync_input_batch
            rows = []
            for i in range(263):
                item = remote_invoice(i + 1000)
                item["tdlap"] = f"2026-08-{i % 31 + 1:02d}T00:00:00+07:00"
                rows.append(item)
            with server.db() as conn:
                batch = prepare(conn)
                sync_input_batch(conn, DateBoundedMsmi(rows), batch["id"], now_iso, page_size=50, max_pages=10)
            return {"ok":True}
        @server.app.post("/fixture/automatic-mapping")
        def automatic_mapping():
            from .test_invoice_workbench_listing import prepare
            from .test_invoice_input_sync import DateBoundedMsmi, now_iso
            from .test_msmi_sync import remote_invoice
            from .invoice_input_sync import sync_input_batch
            remote = remote_invoice(3333)
            remote['tdlap'] = '2026-08-30'
            remote['hdhhdvu'][0].update(ma='AUTO-3333', ten='Hàng kiểm thử kg', dvtinh='kg')
            with server.db() as conn:
                batch = prepare(conn)
                sync_input_batch(conn, DateBoundedMsmi([remote]), batch['id'], now_iso)
                item = conn.execute("SELECT id FROM msmi_invoice_items WHERE source_item_code='AUTO-3333'").fetchone()
            return {'ok':True, 'item_id':item['id']}
        print("ROUND1_SYNTHETIC_READY", flush=True)
        serve(server.app, host="127.0.0.1", port=18801, threads=4)


if __name__ == "__main__":
    main()
