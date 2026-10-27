"""Load the synthetic CSVs into SQLite and report exceptions.

Usage: python load_and_flag.py
Creates exceptions.db in this folder and prints a summary of each exception type.
"""
import csv
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
DB = HERE / "exceptions.db"
TABLES = ["customers", "orders", "deliveries", "invoices", "payments"]


def load(conn):
    for name in TABLES:
        with open(DATA / f"{name}.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise SystemExit(f"{name}.csv is empty")
        cols = list(rows[0].keys())
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        conn.executemany(
            f"INSERT INTO {name} VALUES ({', '.join('?' for _ in cols)})",
            [tuple(r[c] for c in cols) for r in rows],
        )
    conn.commit()


def run_exceptions(conn):
    sql = (HERE / "schema.sql").read_text()
    queries = [q.strip() for q in sql.split(";") if q.strip() and "SELECT" in q]
    labels = ["Late deliveries", "Overdue unpaid invoices", "Disputes by customer"]
    for label, q in zip(labels, queries):
        rows = conn.execute(q).fetchall()
        print(f"{label}: {len(rows)} rows")
        for r in rows[:3]:
            print("   ", r)


def main():
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    load(conn)
    run_exceptions(conn)
    conn.close()


if __name__ == "__main__":
    main()
