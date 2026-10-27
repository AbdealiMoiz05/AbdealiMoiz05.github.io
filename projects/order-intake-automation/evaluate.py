"""Step 3: measure how well the pipeline did, against the answer key.

Because the orders are synthetic, we know the truth for every one. This script
answers three questions:
  1. Reading: how many orders were read exactly right?
  2. Checking: of the problems planted in the orders, how many were caught?
  3. Risk: did any wrongly read order get auto-approved? (This is the number that matters most.)

Usage: python3 evaluate.py   (after extract.py and validate.py)
Writes output/evaluation.json.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "output"
PLANTED_TO_CHECK = {"unknown_part": "UNKNOWN_PART", "price_mismatch": "PRICE_MISMATCH",
                    "pack_size": "PACK_SIZE", "lead_time": "LEAD_TIME", "missing_po": "MISSING_PO",
                    "unusual_quantity": "UNUSUAL_QTY", "duplicate_po": "DUPLICATE_PO"}
LINE_FIELDS = ["part_no", "quantity", "unit_price", "requested_date"]


def compare(got, truth):
    """Return (fields right, fields total) for one order."""
    right = (got["po_number"] == truth["po_number"]) + (got["customer_name"] == truth["customer_name"])
    total = 2
    for i, t in enumerate(truth["lines"]):
        g = got["lines"][i] if i < len(got["lines"]) else {}
        for f in LINE_FIELDS:
            total += 1
            right += g.get(f) == t[f] if f != "unit_price" else abs((g.get(f) or 0) - t[f]) < 0.005
    total += max(0, len(got["lines"]) - len(truth["lines"]))  # extra invented lines count as wrong
    return right, total


def main():
    truth = {o["doc_id"]: o for o in json.loads((HERE / "data" / "answer_key.json").read_text())}
    got = {o["doc_id"]: o for o in json.loads((OUT / "extracted.json").read_text())}
    flagged = {}
    with open(OUT / "review_queue.csv") as f:
        for r in csv.DictReader(f):
            flagged.setdefault(r["doc_id"], set()).add(r["check"])

    fields_right = fields_total = exact = 0
    wrong_orders, booked_wrong = [], []
    for d, t in truth.items():
        r, n = compare(got[d], t)
        fields_right, fields_total = fields_right + r, fields_total + n
        if r == n:
            exact += 1
        else:
            wrong_orders.append(d)
            if d not in flagged:
                booked_wrong.append(d)

    planted = [(d, p) for d, t in truth.items() for p in t["planted_issues"]]
    caught = [(d, p) for d, p in planted if PLANTED_TO_CHECK[p] in flagged.get(d, set())]
    missed = [f"{d} ({p})" for d, p in planted if (d, p) not in caught]
    clean = [d for d, t in truth.items() if not t["planted_issues"]]
    clean_to_review = [d for d in clean if d in flagged]

    result = {
        "orders": len(truth),
        "read_exactly_right": exact,
        "field_accuracy_pct": round(100 * fields_right / fields_total, 1),
        "orders_read_wrong": wrong_orders,
        "planted_problems": len(planted),
        "planted_problems_caught": len(caught),
        "missed": missed,
        "clean_orders_sent_to_review": len(clean_to_review),
        "clean_orders_sent_to_review_ids": clean_to_review,
        "wrongly_read_but_auto_approved": booked_wrong,
    }
    (OUT / "evaluation.json").write_text(json.dumps(result, indent=2))
    print(f"Read exactly right: {exact}/{len(truth)} orders ({result['field_accuracy_pct']}% of fields).")
    print(f"Planted problems caught: {len(caught)}/{len(planted)}." + (f" Missed: {', '.join(missed)}" if missed else ""))
    print(f"Clean orders sent to review anyway: {len(clean_to_review)}.")
    print(f"Wrongly read AND auto-approved: {len(booked_wrong)}" + (f" ({', '.join(booked_wrong)})" if booked_wrong else ""))


if __name__ == "__main__":
    main()
