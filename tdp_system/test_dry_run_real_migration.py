import json
import sqlite3

from tdp_system.dry_run_real_migration import (
    capture_existing_table_fingerprints,
    clone_sqlite,
    compare_table_fingerprints,
    fixture_work_date,
    safe_step_summary,
    sensitive_log_policy,
)


def test_fixture_work_date_matches_legacy_ui_fallback():
    assert fixture_work_date("Don hàng 29.08.xlsx", "29.08") == "2026-08-29"
    assert fixture_work_date("không có ngày", "31.02") == ""


def _create_source(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE balances(id INTEGER PRIMARY KEY, amount REAL, note TEXT);
            CREATE TABLE products(id INTEGER PRIMARY KEY, code TEXT, name TEXT);
            INSERT INTO balances(amount,note) VALUES (125.5,'opening');
            INSERT INTO products(code,name) VALUES ('P01','Sample');
            """
        )


def test_clone_and_schema_extension_preserve_original_values(tmp_path):
    source = tmp_path / "source.sqlite3"
    clone = tmp_path / "clone.sqlite3"
    _create_source(source)

    clone_sqlite(source, clone)
    with sqlite3.connect(clone) as conn:
        before = capture_existing_table_fingerprints(conn)
        conn.execute("ALTER TABLE balances ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        conn.execute("CREATE TABLE migration_only(id INTEGER PRIMARY KEY)")
        after = capture_existing_table_fingerprints(
            conn,
            table_names=sorted(before),
            baseline=before,
        )

    comparison = compare_table_fingerprints(before, after)
    assert comparison["counts_unchanged"] is True
    assert comparison["content_unchanged"] is True
    assert comparison["financial_values_unchanged"] is True

    with sqlite3.connect(source) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(balances)")]
        assert columns == ["id", "amount", "note"]


def test_financial_value_mutation_is_detected(tmp_path):
    database = tmp_path / "database.sqlite3"
    _create_source(database)
    with sqlite3.connect(database) as conn:
        before = capture_existing_table_fingerprints(conn)
        conn.execute("UPDATE balances SET amount=amount+1 WHERE id=1")
        after = capture_existing_table_fingerprints(
            conn,
            table_names=sorted(before),
            baseline=before,
        )

    comparison = compare_table_fingerprints(before, after)
    assert comparison["counts_unchanged"] is True
    assert comparison["content_unchanged"] is False
    assert comparison["financial_values_unchanged"] is False
    assert comparison["financial_changes"] == ["balances"]


def test_safe_step_summary_drops_raw_business_data():
    raw_step = {
        "name": "sample_import",
        "file": "customer workbook.xlsx",
        "preview": {
            "counts": {"rows": 2, "amount": 999},
            "rows": [{"full_name": "Do not log"}],
            "totals": {"amount": 999},
            "preview_rows_returned": 2,
            "issue_rows_returned": 1,
        },
        "confirm_first": {"supplier": "Do not log", "amount": 999},
        "rows_first": 2,
        "semantic_idempotent": True,
    }

    safe = safe_step_summary(raw_step)
    rendered = json.dumps(safe, ensure_ascii=False)
    assert safe["count_metrics"] == {"rows": 2}
    assert safe["rows_first"] == 2
    assert "Do not log" not in rendered
    assert "999" not in rendered
    assert "file" not in safe
    assert "confirm_first" not in safe


def test_sensitive_log_policy_rejects_unapproved_report_shape():
    valid = {
        "steps": [{
            "name": "sample",
            "status": "ready",
            "semantic_idempotent": True,
            "preview_row_count": 1,
            "preview_issue_count": 0,
            "preview_warning_count": 0,
            "count_metrics": {},
        }],
        "migration_passed": True,
    }
    assert sensitive_log_policy(valid)["allowlist_shape_valid"] is True

    invalid = {**valid, "raw_customer_rows": [{"name": "unsafe"}]}
    assert sensitive_log_policy(invalid)["allowlist_shape_valid"] is False

    invalid_count_key = {
        "steps": [{**valid["steps"][0], "count_metrics": {"amount": 999}}],
    }
    assert sensitive_log_policy(invalid_count_key)["allowlist_shape_valid"] is False
