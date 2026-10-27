"""Classify overdue invoices and draft chase emails with the Claude API.

Nothing is sent. Drafts go to review_queue.csv with status 'pending_approval',
so a person checks each one before it goes anywhere.

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python3 draft_chase_emails.py
Requires exceptions.db from load_and_flag.py.
"""
import csv
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "exceptions.db"
QUEUE = HERE / "review_queue.csv"
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5-5"
LIMIT = 10  # keep the first run small and cheap

OVERDUE = """
SELECT i.invoice_id, c.customer_name, i.amount, i.due_date,
       i.amount - COALESCE(SUM(p.amount_paid), 0) AS outstanding
FROM invoices i
JOIN customers c ON c.customer_id = i.customer_id
LEFT JOIN payments p ON p.invoice_id = i.invoice_id
WHERE i.status <> 'disputed' AND date(i.due_date) < date('2026-12-31')
GROUP BY i.invoice_id
HAVING outstanding > 0
ORDER BY outstanding DESC
LIMIT ?
"""

PROMPT = """You are helping an accounts receivable team at an automotive parts supplier.
Invoice {invoice_id} for {customer} shows {outstanding:.2f} GBP outstanding, due {due_date}.
Write a short, polite payment reminder email from the accounts team.
Rules: no threats, no invented facts, no payment deadlines beyond 14 days, British English.
Reply with JSON only: {{"category": "payment_reminder", "subject": "...", "body": "..."}}"""


def ask_claude(prompt, key):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


def main():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Set ANTHROPIC_API_KEY first.")
    if not DB.exists():
        raise SystemExit("Run load_and_flag.py first to create exceptions.db.")

    rows = sqlite3.connect(DB).execute(OVERDUE, (LIMIT,)).fetchall()
    with open(QUEUE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["invoice_id", "customer", "outstanding", "due_date",
                    "category", "subject", "body", "status"])
        for inv, cust, _amount, due, outstanding in rows:
            prompt = PROMPT.format(invoice_id=inv, customer=cust,
                                   outstanding=outstanding, due_date=due)
            try:
                draft = json.loads(ask_claude(prompt, key))
                w.writerow([inv, cust, f"{outstanding:.2f}", due, draft["category"],
                            draft["subject"], draft["body"], "pending_approval"])
            except (ValueError, KeyError) as err:
                w.writerow([inv, cust, f"{outstanding:.2f}", due, "error", "", str(err), "needs_review"])
    print(f"Wrote {len(rows)} drafts to {QUEUE}. Nothing has been sent.")


if __name__ == "__main__":
    main()
