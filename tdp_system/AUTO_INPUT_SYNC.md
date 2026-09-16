# Automatic input invoice refresh

Hosted startup starts one daemon worker, with a persistent SQLite lease to cover
overlapping deployments. Enable with `TDP_AUTO_INPUT_SYNC=1` and set
`MSMI_SYNC_TAX_CODE` to the explicitly selected buyer tax code. Existing
`MSMI_USERNAME`, `MSMI_PASSWORD`, `MSMI_API_BASE_URL`, and `MSMI_API_TOKEN` are
read from server environment only. Never put credentials in frontend status.

Schedules: 02:30 and 06:00 Asia/Ho_Chi_Minh. Each run refreshes today and the
previous seven dates, including month/year boundaries. A restart catches up on
a missed slot. Failures retry after 30, 60, then at most 120 minutes; the next
daily slot can bring the retry forward. A 40-minute lease prevents overlap and
allows recovery after process death. The worker checks once per minute.

The mSMI portal contract was verified against its browser client on 2026-09-16:
login, select the exact connected tax account, refresh purchase and purchase_sco
lists via crawl-api/build-request, enumerate missing purchase details, request
each detail, and check again for missing details. These are vendor portal
endpoints, distinct from the public OpenAPI used to retrieve invoices. A changed
contract, expired tax connection, timeout, or unexpected response fails visibly
and retries; it does not masquerade as an empty successful import.

Only after source refresh succeeds does OpenAPI retrieve a complete snapshot.
Since the provider ignores dates and may order by updates, pagination does not
stop when one old invoice appears. Local filtering enforces dates and buyer.
Network calls hold no database write lock. Ingestion uses the existing validated,
idempotent input import inside a short transaction. Existing posted-invoice
protection and saved mapping rules remain in force. Nothing posts stock, signs,
issues, cancels invoices, or changes sales orders.

Workbench status shows last success, next attempt and any source failure. Stale
workers also produce a warning. Missing product mappings remain a separate user
task and do not mean synchronization failed. Disabling the environment flag on
the next deployment stops automatic work; manual sync remains available.

Regression coverage: `python -m unittest tdp_system.test_automatic_input_sync
tdp_system.test_invoice_workbench tdp_system.test_invoice_input_sync
tdp_system.test_invoice_input_integrity tdp_system.test_cloud_config`.
