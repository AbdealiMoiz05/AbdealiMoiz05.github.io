"""Step 2: check every extracted order against the master data, then route it.

Loads the parts catalogue, customers and extracted orders into SQLite
(output/intake.db), runs nine business checks, and splits orders into:
  AUTO_APPROVE  every check passed, ready to book
  REVIEW        at least one check failed, so a person decides. Nothing is changed automatically.

Writes output/review_queue.csv (one row per problem, with a suggested fix),
output/approved_lines.csv and output/run_summary.json.
Usage: python3 validate.py   (after extract.py)
"""
import csv
import difflib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "output"
RECEIVED = date(2026, 11, 2)   # the day these orders hit the inbox
PRICE_TOLERANCE = 0.005        # 0.5% either way before a price counts as wrong
MAX_PACKS = 40                 # more than this many packs on one line looks like a typing error

SCHEMA = """
DROP TABLE IF EXISTS parts; DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS order_lines; DROP TABLE IF EXISTS issues;
CREATE TABLE parts (part_no TEXT PRIMARY KEY, description TEXT, list_price_gbp REAL,
                    pack_size INTEGER, lead_time_days INTEGER);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_name TEXT, site TEXT,
                        contract_discount_pct REAL, order_format TEXT, email_domain TEXT);
CREATE TABLE orders (doc_id TEXT PRIMARY KEY, file TEXT, method TEXT, po_number TEXT,
                     customer_name TEXT, order_date TEXT, confidence TEXT, status TEXT,
                     order_value_gbp REAL);
CREATE TABLE order_lines (doc_id TEXT, line_no INTEGER, part_no TEXT, quantity INTEGER,
                          unit_price REAL, requested_date TEXT);
CREATE TABLE issues (doc_id TEXT, line_no INTEGER, check_code TEXT, detail TEXT, suggested_fix TEXT);
"""

CHECKS = {
    "MISSING_PO": "No purchase order number",
    "UNKNOWN_CUSTOMER": "Sender not matched to a customer account",
    "LOW_CONFIDENCE": "Reader was not sure of some fields",
    "DUPLICATE_PO": "Same PO already received from this customer",
    "UNKNOWN_PART": "Part number not in the catalogue",
    "PRICE_MISMATCH": "Price differs from the contract price",
    "PACK_SIZE": "Quantity is not a whole number of packs",
    "LEAD_TIME": "Requested date is inside the part's lead time",
    "UNUSUAL_QTY": "Quantity far above normal for one line",
}


def load(db):
    db.executescript(SCHEMA)
    for table, fname in [("parts", "parts_catalogue.csv"), ("customers", "customers.csv")]:
        with open(HERE / "data" / fname) as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0])
        db.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                       [tuple(r[c] for c in cols) for r in rows])
    extracted = json.loads((OUT / "extracted.json").read_text())
    for o in extracted:
        db.execute("INSERT INTO orders (doc_id, file, method, po_number, customer_name, order_date, confidence) "
                   "VALUES (?,?,?,?,?,?,?)", (o["doc_id"], o["file"], o["method"], o["po_number"],
                                               o["customer_name"], o["order_date"], o["confidence"]))
        for i, l in enumerate(o["lines"], 1):
            db.execute("INSERT INTO order_lines VALUES (?,?,?,?,?,?)",
                       (o["doc_id"], i, l["part_no"], l["quantity"], l["unit_price"], l["requested_date"]))
    return extracted


def run_checks(db, extracted):
    issues = []

    def flag(doc_id, line_no, code, detail, fix):
        issues.append((doc_id, line_no, code, detail, fix))

    known_parts = [r[0] for r in db.execute("SELECT part_no FROM parts")]
    seen_po = {}
    for o in extracted:
        d = o["doc_id"]
        if not o["po_number"]:
            flag(d, None, "MISSING_PO", CHECKS["MISSING_PO"], "Ask the buyer for the PO before booking")
        if not o["customer_name"]:
            flag(d, None, "UNKNOWN_CUSTOMER", CHECKS["UNKNOWN_CUSTOMER"], "Match the sender to an account")
        # A missing PO is already its own check; flag low confidence only for other reasons.
        other_doubts = [u for u in o["uncertain_fields"] if u != "po_number"]
        if o["confidence"] == "low" and other_doubts:
            flag(d, None, "LOW_CONFIDENCE", f"Unsure about: {', '.join(other_doubts)}",
                 "Check the original document")
        key = (o["customer_name"], o["po_number"])
        if o["po_number"] and key in seen_po:
            flag(d, None, "DUPLICATE_PO", f"PO {o['po_number']} already received in {seen_po[key]}",
                 "Confirm with the buyer before booking a second time")
        seen_po.setdefault(key, d)

    # Line checks are joins against master data. Unknown parts fall out of the LEFT JOIN.
    rows = db.execute("""
        SELECT l.doc_id, l.line_no, l.part_no, l.quantity, l.unit_price, l.requested_date,
               p.pack_size, p.lead_time_days,
               ROUND(p.list_price_gbp * (1 - c.contract_discount_pct / 100.0), 2) AS contract_price,
               o.order_date
        FROM order_lines l
        JOIN orders o ON o.doc_id = l.doc_id
        LEFT JOIN parts p ON p.part_no = l.part_no
        LEFT JOIN customers c ON c.customer_name = o.customer_name
        ORDER BY l.doc_id, l.line_no""").fetchall()
    for d, n, part, qty, price, req, pack, lead, contract, _ in rows:
        if pack is None:
            close = difflib.get_close_matches(part or "", known_parts, n=2, cutoff=0.7)
            flag(d, n, "UNKNOWN_PART", f"{part} is not a catalogue part",
                 f"Closest catalogue parts: {' or '.join(close)}. Confirm with the buyer" if close
                 else "Ask the buyer for the right part number")
            continue
        if contract is not None and price is not None and abs(price - contract) > contract * PRICE_TOLERANCE:
            flag(d, n, "PRICE_MISMATCH", f"{part}: ordered at £{price:.2f}, contract price £{contract:.2f}",
                 "Send a price correction before confirming")
        if qty and qty % pack:
            flag(d, n, "PACK_SIZE", f"{part}: {qty} is not a multiple of the pack size {pack}",
                 f"Round to {qty + pack - qty % pack} or {qty - qty % pack}, and confirm with the buyer")
        if qty and qty > pack * MAX_PACKS:
            flag(d, n, "UNUSUAL_QTY", f"{part}: {qty} units ({qty // pack} packs)",
                 "Confirm the quantity with the buyer")
        if req and date.fromisoformat(req) < RECEIVED + timedelta(days=lead):
            earliest = RECEIVED + timedelta(days=lead)
            flag(d, n, "LEAD_TIME", f"{part}: wanted {req}, lead time is {lead} days",
                 f"Offer {earliest.isoformat()}, or escalate for an expedite")
    db.executemany("INSERT INTO issues VALUES (?,?,?,?,?)", issues)
    return issues


def main():
    db_path = OUT / "intake.db"
    db = sqlite3.connect(db_path)
    extracted = load(db)
    issues = run_checks(db, extracted)
    flagged = {i[0] for i in issues}
    db.execute("UPDATE orders SET status = CASE WHEN doc_id IN (SELECT doc_id FROM issues) "
               "THEN 'REVIEW' ELSE 'AUTO_APPROVE' END")
    db.execute("UPDATE orders SET order_value_gbp = (SELECT ROUND(SUM(quantity * unit_price), 2) "
               "FROM order_lines l WHERE l.doc_id = orders.doc_id)")
    db.commit()

    with open(OUT / "review_queue.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "customer", "po_number", "line_no", "check", "detail", "suggested_fix", "status"])
        names = {o["doc_id"]: o for o in extracted}
        for d, n, code, detail, fix in issues:
            w.writerow([d, names[d]["customer_name"], names[d]["po_number"], n or "", code, detail, fix,
                        "pending_review"])
    with open(OUT / "approved_lines.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "customer", "po_number", "line_no", "part_no", "quantity", "unit_price",
                    "requested_date"])
        w.writerows(db.execute("""SELECT l.doc_id, o.customer_name, o.po_number, l.line_no, l.part_no,
                                  l.quantity, l.unit_price, l.requested_date
                                  FROM order_lines l JOIN orders o USING (doc_id)
                                  WHERE o.status = 'AUTO_APPROVE' ORDER BY l.doc_id, l.line_no"""))

    by_check = {}
    for i in issues:
        by_check[i[2]] = by_check.get(i[2], 0) + 1
    value = dict(db.execute("SELECT status, ROUND(SUM(order_value_gbp), 2) FROM orders GROUP BY status"))
    summary = {"orders": len(extracted), "auto_approved": len(extracted) - len(flagged),
               "sent_to_review": len(flagged), "issues": len(issues), "issues_by_check": by_check,
               "value_auto_approved_gbp": value.get("AUTO_APPROVE", 0),
               "value_held_for_review_gbp": value.get("REVIEW", 0),
               "read_by_ai": sum(o["method"] == "ai" for o in extracted),
               "flagged_only_for_low_confidence": sum(
                   1 for d in flagged if {i[2] for i in issues if i[0] == d} == {"LOW_CONFIDENCE"})}
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"{summary['auto_approved']} orders auto-approved, {summary['sent_to_review']} sent to review "
          f"({summary['issues']} problems).")
    for code, count in sorted(by_check.items(), key=lambda x: -x[1]):
        print(f"  {code:<17} {count}")


if __name__ == "__main__":
    main()
