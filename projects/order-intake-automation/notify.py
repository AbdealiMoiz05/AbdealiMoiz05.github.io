"""Step 4: tell the order desk what needs a human, where they already work.

Builds one Microsoft Teams Adaptive Card per order in the review queue, and
writes output/review_queue.xlsx (an Excel table the Power Automate flow can read).

- If TEAMS_WEBHOOK_URL is set, each card is posted to it. Use the URL from a
  Power Automate / Teams Workflows flow (see docs/POWER_AUTOMATE_TEAMS.md).
- If not, the cards are saved to output/teams_cards/ so you can preview them at
  https://adaptivecards.io/designer/

Usage: python3 notify.py   (after validate.py)
"""
import csv
import json
import os
import urllib.request
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo

HERE = Path(__file__).parent
OUT = HERE / "output"


def card_for(doc_id, rows):
    first = rows[0]
    facts = [{"title": r["check"].replace("_", " ").title(), "value": r["detail"]} for r in rows]
    fixes = list(dict.fromkeys(r["suggested_fix"] for r in rows))
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {"type": "TextBlock", "text": f"Order needs review: {doc_id}", "weight": "Bolder",
                     "size": "Medium"},
                    {"type": "TextBlock", "text": f"{first['customer'] or 'Unknown customer'} · "
                                                  f"PO {first['po_number'] or 'missing'}", "isSubtle": True,
                     "spacing": "None"},
                    {"type": "FactSet", "facts": facts},
                    {"type": "TextBlock", "text": "Suggested next step: " + "; ".join(fixes), "wrap": True},
                ],
            },
        }],
    }


def write_excel(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "ReviewQueue"
    headers = list(rows[0]) if rows else ["doc_id"]
    ws.append(headers)
    for r in rows:
        ws.append([r[h] for h in headers])
    ref = f"A1:{chr(64 + len(headers))}{len(rows) + 1}"
    table = Table(displayName="ReviewQueue", ref=ref)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)
    wb.save(OUT / "review_queue.xlsx")


def main():
    with open(OUT / "review_queue.csv") as f:
        rows = list(csv.DictReader(f))
    write_excel(rows)

    by_order = {}
    for r in rows:
        by_order.setdefault(r["doc_id"], []).append(r)

    url = os.environ.get("TEAMS_WEBHOOK_URL")
    cards_dir = OUT / "teams_cards"
    cards_dir.mkdir(exist_ok=True)
    for f in cards_dir.glob("*.json"):
        f.unlink()
    for doc_id, items in by_order.items():
        card = card_for(doc_id, items)
        if url:
            req = urllib.request.Request(url, data=json.dumps(card).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30)
        else:
            (cards_dir / f"{doc_id}.json").write_text(json.dumps(card, indent=2))
    where = "posted to Teams" if url else f"saved to {cards_dir.relative_to(HERE)}/"
    print(f"{len(by_order)} review cards {where}. Excel queue: output/review_queue.xlsx")


if __name__ == "__main__":
    main()
