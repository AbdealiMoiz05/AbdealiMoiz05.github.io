"""Step 1: read every order in inbox/ and turn it into structured data.

Two ways to read an order:
  rules  pattern matching in plain Python. Free, fast, and fine for tidy formats.
         It marks an order "low confidence" when it sees something it can't
         handle safely, such as a correction later in an email thread.
  ai     the Claude API reads the email text or the PDF itself and returns JSON
         that must match a fixed schema. Fields it can't read are left empty
         and listed, never guessed.

  --method hybrid (the default) runs rules first and sends only the
  low-confidence orders to the AI. Without an API key, hybrid acts like rules
  and the low-confidence orders go to a person instead.

Usage:
    python3 extract.py                    # hybrid
    python3 extract.py --method rules
    export ANTHROPIC_API_KEY=...; python3 extract.py --method ai
Writes output/extracted.json.
"""
import argparse
import base64
import csv
import json
import os
import re
from datetime import date
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).parent
INBOX = HERE / "inbox"
OUT = HERE / "output"
MODEL = "claude-opus-5-5"
PRICE_PER_MTOK = {"input": 4.00, "output": 20.00}  # USD, for the cost log

PART_RE = re.compile(r"\b[A-Z]{2,3}-\d{4}\b")
DATE_NUM_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_WORD_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\s+(January|February|March|April|May|June|July|"
                          r"August|September|October|November|December)\b")
PRICE_RE = re.compile(r"£\s*(\d+\.\d{2})|(?<![\d/.-])(\d+\.\d{2})(?![\d/])")
INT_RE = re.compile(r"(?<![\w.£/-])(\d+)(?![\w./])")
PO_RE = re.compile(r"(?:PO\s*(?:No|number)?\s*[:#]?|ref is|order|call-off)\s*(45\d{6})", re.I)
CORRECTION_RE = re.compile(r"\b(correction|should be|amend|revised|instead of)\b", re.I)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def load_customers():
    with open(HERE / "data" / "customers.csv") as f:
        return list(csv.DictReader(f))


def read_document(path):
    if path.suffix == ".pdf":
        return "\n".join(p.extract_text(extraction_mode="layout") for p in PdfReader(path).pages)
    return path.read_text()


# ---------- rules-based reader ----------

def parse_date(text, ref):
    m = DATE_NUM_RE.search(text)
    if m:
        if m.group(1):
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        return date(int(m.group(4)), int(m.group(5)), int(m.group(6))).isoformat()
    m = DATE_WORD_RE.search(text)
    if m:  # "18th November" has no year: assume the next one on or after the order date
        d = date(ref.year, MONTHS.index(m.group(2)) + 1, int(m.group(1)))
        return (d if d >= ref else d.replace(year=ref.year + 1)).isoformat()
    return None


def rules_extract(text, customers):
    reasons = []
    po = PO_RE.search(text)
    customer = next((c["customer_name"] for c in customers
                     if (c["email_domain"] and c["email_domain"] in text)
                     or c["customer_name"].upper() in text.upper()), None)
    header_date = DATE_NUM_RE.search(text[text.find("Date:"):]) if "Date:" in text else None
    order_date = parse_date(header_date.group(0), date.today()) if header_date else None
    if not order_date:
        m = re.search(r"Order date:\s*(\S+)", text)
        order_date = parse_date(m.group(1), date.today()) if m else None
    ref = date.fromisoformat(order_date) if order_date else date.today()

    lines = []
    for raw in text.splitlines():
        part = PART_RE.search(raw)
        price = PRICE_RE.search(raw)
        if not part or not price:  # a part code with no price is a remark, not an order line
            continue
        rest = PART_RE.sub(" ", raw)
        rest = DATE_NUM_RE.sub(" ", rest)
        rest = PRICE_RE.sub(" ", rest)
        rest = re.sub(r"\b45\d{6}\b", " ", rest)  # PO number on CSV rows
        ints = [int(x) for x in INT_RE.findall(rest)]
        if len(ints) > 1 and re.match(r"\s*\d+\s*[|\s]", raw):
            ints = ints[1:]  # drop the line/item number at the start of table rows
        lines.append({"part_no": part.group(0),
                      "quantity": max(ints) if ints else None,
                      "unit_price": float(price.group(1) or price.group(2)),
                      "requested_date": parse_date(raw, ref)})

    if not po:
        reasons.append("po_number")
    if not customer:
        reasons.append("customer_name")
    if not lines:
        reasons.append("lines")
    if any(None in l.values() for l in lines):
        reasons.append("line_fields")
    if CORRECTION_RE.search(text):
        reasons.append("correction_in_thread")
    return {"po_number": po.group(1) if po else None, "customer_name": customer,
            "order_date": order_date, "lines": lines,
            "confidence": "low" if reasons else "high", "uncertain_fields": reasons, "notes": ""}


# ---------- AI reader (Claude API) ----------

LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "part_no": {"type": ["string", "null"]},
        "quantity": {"type": ["integer", "null"]},
        "unit_price": {"type": ["number", "null"]},
        "requested_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
    },
    "required": ["part_no", "quantity", "unit_price", "requested_date"],
    "additionalProperties": False,
}
ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "po_number": {"type": ["string", "null"]},
        "customer_name": {"type": ["string", "null"]},
        "order_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
        "lines": {"type": "array", "items": LINE_SCHEMA},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "uncertain_fields": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["po_number", "customer_name", "order_date", "lines", "confidence",
                 "uncertain_fields", "notes"],
    "additionalProperties": False,
}

INSTRUCTIONS = """You read customer purchase orders for a UK automotive parts supplier's order desk.
Extract the order into the JSON schema.

Rules:
- Known customers: {customers}. Use the exact name from this list, or null if none fits.
- If a later message in an email thread corrects an earlier one, apply the correction and say so in notes.
- Never guess. If a field is missing or unreadable, set it to null and add its name to uncertain_fields.
- Copy part numbers exactly as written, even if they look wrong. Checking them is done later.
- Dates as YYYY-MM-DD. UK dates are day/month/year. If a date has no year, use the first one on or after the order date.
- Prices are GBP per unit. "confidence" is how sure you are that every field is right."""


def ai_extract(path, client, customers):
    names = ", ".join(c["customer_name"] for c in customers)
    if path.suffix == ".pdf":
        doc = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                              "data": base64.standard_b64encode(path.read_bytes()).decode()}}
    else:
        doc = {"type": "text", "text": f"<order_email>\n{path.read_text()}\n</order_email>"}
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ORDER_SCHEMA}},
        messages=[{"role": "user", "content": [doc, {"type": "text",
                                                     "text": INSTRUCTIONS.format(customers=names)}]}],
    )
    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    if response.stop_reason != "end_turn":  # refusal or cut off: a person reads this one
        return {"po_number": None, "customer_name": None, "order_date": None, "lines": [],
                "confidence": "low", "uncertain_fields": [f"stop_reason:{response.stop_reason}"],
                "notes": "AI could not read this order", "usage": usage}
    result = json.loads(next(b.text for b in response.content if b.type == "text"))
    result["usage"] = usage
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["rules", "ai", "hybrid"], default="hybrid")
    args = ap.parse_args()
    customers = load_customers()

    client = None
    if args.method in ("ai", "hybrid") and os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
    elif args.method == "ai":
        raise SystemExit("--method ai needs ANTHROPIC_API_KEY. Use --method rules to run without it.")

    results, tokens = [], {"input_tokens": 0, "output_tokens": 0}
    for path in sorted(INBOX.iterdir()):
        if args.method == "ai":
            r, method = ai_extract(path, client, customers), "ai"
        else:
            r, method = rules_extract(read_document(path), customers), "rules"
            if r["confidence"] == "low" and client:
                r, method = ai_extract(path, client, customers), "ai"
        for k in tokens:
            tokens[k] += r.pop("usage", {}).get(k, 0)
        results.append({"doc_id": path.stem, "file": path.name, "method": method, **r})

    OUT.mkdir(exist_ok=True)
    (OUT / "extracted.json").write_text(json.dumps(results, indent=2))
    ai_count = sum(r["method"] == "ai" for r in results)
    low = sum(r["confidence"] == "low" for r in results)
    cost = (tokens["input_tokens"] * PRICE_PER_MTOK["input"]
            + tokens["output_tokens"] * PRICE_PER_MTOK["output"]) / 1e6
    print(f"Read {len(results)} orders: {len(results) - ai_count} by rules, {ai_count} by AI. "
          f"{low} still low confidence.")
    if ai_count:
        print(f"AI usage: {tokens['input_tokens']} input + {tokens['output_tokens']} output tokens "
              f"(about ${cost:.2f}).")


if __name__ == "__main__":
    main()
