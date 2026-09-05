"""Temporary source server for the TDP-091 payroll browser smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18796
    server.init_database()
    with server.db() as conn:
        conn.execute("DELETE FROM payroll_adjustments")
        conn.execute("DELETE FROM attendance_entries")
        conn.execute("DELETE FROM staff")
        conn.execute("DELETE FROM kitchen_labor_costs")
        timestamp = server.now_iso()
        conn.execute(
            """INSERT INTO staff(
                   employee_code,full_name,role_name,kitchen,base_salary,standard_days,
                   standard_hours,bhxh_employee_rate,bhxh_company_rate,active,created_at,updated_at
               ) VALUES('NV01','Nguyễn An','Bếp trưởng','VINA',5200000,26,8,0,0,1,?,?)""",
            (timestamp, timestamp),
        )
    serve(server.app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":
    main()
