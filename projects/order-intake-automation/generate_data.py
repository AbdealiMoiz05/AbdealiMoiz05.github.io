"""Create the synthetic data for the order intake project.

Writes:
  data/parts_catalogue.csv   parts, list prices, pack sizes and lead times
  data/customers.csv         five fictional UK vehicle makers and their contract discounts
  inbox/                     40 customer orders in five different formats (.txt emails and .pdf POs)
  data/answer_key.json       what each order really says, and which problems were planted in it

Every company, part and number here is invented. Run: python3 generate_data.py
"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent
DATA = HERE / "data"
INBOX = HERE / "inbox"
TODAY = date(2026, 11, 2)  # the "received" date for every order in this run
random.seed(27)

PARTS = [
    # part_no, description, list price GBP, pack size, lead time days
    ("SP-1001", "Spark plug, iridium", 4.20, 50, 7),
    ("SP-1002", "Spark plug, double platinum", 3.10, 50, 7),
    ("BP-2210", "Brake pad set, front axle", 18.40, 10, 14),
    ("BP-2215", "Brake pad set, rear axle", 15.75, 10, 14),
    ("BD-2300", "Brake disc, vented 320mm", 27.90, 4, 21),
    ("WB-3300", "Wiper blade, flat 600mm", 6.80, 20, 7),
    ("WB-3320", "Wiper blade, rear 350mm", 4.95, 20, 7),
    ("INJ-4410", "Fuel injector, petrol direct", 64.00, 6, 28),
    ("INJ-4420", "Fuel injector, diesel common rail", 112.50, 6, 35),
    ("SEN-5520", "Lambda sensor, wideband", 38.25, 12, 14),
    ("SEN-5530", "Wheel speed sensor, ABS", 21.60, 12, 14),
    ("SEN-5540", "Parking sensor, ultrasonic", 17.30, 24, 21),
    ("ALT-6600", "Alternator, 150A", 142.00, 2, 42),
    ("STR-6700", "Starter motor, 1.4kW", 98.00, 2, 42),
    ("ECU-7710", "Engine control unit, gen 4", 386.00, 1, 56),
    ("FIL-8801", "Oil filter, cartridge", 3.45, 40, 7),
    ("FIL-8810", "Cabin air filter, carbon", 7.90, 25, 7),
    ("FIL-8820", "Fuel filter, diesel", 11.20, 20, 14),
    ("HRN-9100", "Horn, dual tone 12V", 9.60, 10, 14),
    ("BAT-9500", "EV battery cell monitor board", 54.00, 8, 49),
]

CUSTOMERS = [
    # id, name, site, contract discount %, order format, sender email domain
    ("C01", "Northfield Motors Ltd", "Coventry", 12.0, "table_email", "northfield-motors.example"),
    ("C02", "Severn Vehicle Assembly", "Swindon", 8.0, "free_text_email", "severn-va.example"),
    ("C03", "Pennine Automotive plc", "Sunderland", 15.0, "pdf_po", ""),
    ("C04", "Thames Valley EV Ltd", "Oxford", 5.0, "csv_paste", "tvev.example"),
    ("C05", "Midlands Commercial Vehicles", "Leyland", 10.0, "amended_email", "mcv-leyland.example"),
]

CATALOGUE = {p[0]: p for p in PARTS}
CONTACTS = {"C01": "Priya Shah", "C02": "Tom Hughes", "C03": "Gareth Lowe",
            "C04": "Amira Okafor", "C05": "Dan Whitfield"}


def contract_price(part_no, discount):
    return round(CATALOGUE[part_no][2] * (1 - discount / 100), 2)


def build_orders():
    """Decide what each order really contains, then plant known problems in some of them."""
    orders = []
    n = 0
    for cust in CUSTOMERS:
        for k in range(8):
            n += 1
            cid, name, site, disc, fmt, _ = cust
            lines = []
            for part_no in random.sample(list(CATALOGUE), random.randint(1, 4)):
                pack = CATALOGUE[part_no][3]
                lead = CATALOGUE[part_no][4]
                qty = pack * random.randint(2, 20)
                req = TODAY + timedelta(days=lead + random.randint(3, 30))
                lines.append({"part_no": part_no, "quantity": qty,
                              "unit_price": contract_price(part_no, disc),
                              "requested_date": req.isoformat()})
            orders.append({"doc_id": f"ORD-{n:03d}", "customer_id": cid, "customer_name": name,
                           "format": fmt, "po_number": f"45{cid[2]}{random.randint(10000, 99999)}",
                           "order_date": (TODAY - timedelta(days=random.randint(0, 3))).isoformat(),
                           "lines": lines, "planted_issues": []})

    # Plant problems in roughly a third of orders, so the checks have something real to catch.
    def plant(i, issue, fn):
        fn(orders[i])
        orders[i]["planted_issues"].append(issue)

    def typo_part(o):
        o["lines"][0]["part_no"] = {"BP-2210": "BP-2201"}.get(o["lines"][0]["part_no"],
                                                          o["lines"][0]["part_no"][:-1] + "9")

    def old_price(o):
        o["lines"][-1]["unit_price"] = round(o["lines"][-1]["unit_price"] * 0.93, 2)

    def bad_pack(o):
        o["lines"][0]["quantity"] += 3

    def too_soon(o):
        o["lines"][0]["requested_date"] = (TODAY + timedelta(days=2)).isoformat()

    def no_po(o):
        o["po_number"] = None

    def fat_finger(o):
        o["lines"][0]["quantity"] *= 100

    plan = [(1, "unknown_part", typo_part), (5, "price_mismatch", old_price),
            (9, "pack_size", bad_pack), (12, "lead_time", too_soon),
            (17, "missing_po", no_po), (20, "price_mismatch", old_price),
            (22, "unusual_quantity", fat_finger), (26, "lead_time", too_soon),
            (30, "unknown_part", typo_part), (33, "pack_size", bad_pack),
            (36, "missing_po", no_po), (38, "price_mismatch", old_price)]
    for i, issue, fn in plan:
        plant(i, issue, fn)

    # One customer sends the same PO twice (a classic double booking).
    dup = json.loads(json.dumps(orders[14]))
    dup["doc_id"] = "ORD-041"
    dup["planted_issues"] = ["duplicate_po"]
    orders.append(dup)
    return orders


def fmt_date_uk(iso):
    d = date.fromisoformat(iso)
    return d.strftime("%d/%m/%Y")


def fmt_date_words(iso):
    d = date.fromisoformat(iso)
    suffix = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}.get(d.day, "th")
    return f"{d.day}{suffix} {d.strftime('%B')}"


def write_table_email(o):
    po = f"PO number: {o['po_number']}" if o["po_number"] else "PO number: to follow"
    rows = "\n".join(
        f"{i:<5}| {l['part_no']:<9}| {CATALOGUE.get(l['part_no'], ('', 'Part as per drawing'))[1]:<34}| "
        f"{l['quantity']:>6} | £{l['unit_price']:>8.2f} | {fmt_date_uk(l['requested_date'])}"
        for i, l in enumerate(o["lines"], 1))
    return f"""From: {CONTACTS[o['customer_id']]} <purchasing@northfield-motors.example>
To: orders@supplier.example
Subject: New purchase order - Northfield Motors
Date: {fmt_date_uk(o['order_date'])}

Hello,

Please find our order below. {po}
Deliver to: Northfield Motors Ltd, Gate 4, Coventry CV6 5RS

Line | Part No  | Description                       |    Qty | Unit price | Required by
{rows}

Please confirm receipt.
Kind regards,
{CONTACTS[o['customer_id']]}
Purchasing, Northfield Motors Ltd
"""


def write_free_text(o):
    bits = []
    for l in o["lines"]:
        desc = CATALOGUE.get(l["part_no"], ("", "part"))[1].split(",")[0].lower()
        bits.append(f"{l['quantity']} x {desc} ({l['part_no']}) at £{l['unit_price']:.2f} each, "
                    f"needed by the {fmt_date_words(l['requested_date'])}")
    body = ";\n".join(bits)
    ref = f"Our ref is {o['po_number']}." if o["po_number"] else "I'll send the PO ref when finance raise it."
    return f"""From: {CONTACTS[o['customer_id']]} <t.hughes@severn-va.example>
To: orders@supplier.example
Subject: parts for next month
Date: {fmt_date_uk(o['order_date'])}

Hi all,

Hope you're well. Could you get the following over to the Swindon line please:
{body}.

{ref} Same delivery address as usual. Shout if anything's a problem.

Cheers,
Tom
"""


def write_pdf(o, path):
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 60, "PENNINE AUTOMOTIVE PLC")
    c.setFont("Helvetica", 9)
    c.drawString(40, h - 74, "Hylton Riverside, Sunderland SR5 3XB  |  Procurement Department")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, h - 110, "PURCHASE ORDER")
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 130, f"PO No: {o['po_number'] or ''}")
    c.drawString(40, h - 144, f"Order date: {fmt_date_uk(o['order_date'])}")
    c.drawString(300, h - 130, "Supplier: Automotive parts supplier (UK)")
    c.drawString(300, h - 144, f"Buyer: {CONTACTS[o['customer_id']]}")
    y = h - 180
    c.setFont("Helvetica-Bold", 9)
    for x, t in [(40, "Item"), (75, "Part number"), (160, "Description"), (350, "Qty"),
                 (400, "Unit price GBP"), (480, "Delivery date")]:
        c.drawString(x, y, t)
    c.setFont("Helvetica", 9)
    for i, l in enumerate(o["lines"], 1):
        y -= 16
        for x, t in [(40, str(i)), (75, l["part_no"]),
                     (160, CATALOGUE.get(l["part_no"], ("", "Part as per drawing"))[1]),
                     (350, str(l["quantity"])), (400, f"{l['unit_price']:.2f}"),
                     (480, fmt_date_uk(l["requested_date"]))]:
            c.drawString(x, y, t)
    c.drawString(40, y - 40, "Terms: 60 days end of month. Quote PO number on all delivery notes and invoices.")
    c.save()


def write_csv_paste(o):
    rows = "\n".join(f"{o['po_number'] or ''};{l['part_no']};{l['quantity']};{l['unit_price']:.2f};{l['requested_date']}"
                     for l in o["lines"])
    return f"""From: {CONTACTS[o['customer_id']]} <supply@tvev.example>
To: orders@supplier.example
Subject: TVEV call-off {o['po_number'] or ''}
Date: {fmt_date_uk(o['order_date'])}

Call-off below (export from our MRP, semicolon separated).

PO;PART;QTY;PRICE;DATE
{rows}

Amira
"""


def write_amended(o):
    """The first email has a wrong quantity; a later reply in the thread corrects it."""
    first = o["lines"][0]
    wrong_qty = first["quantity"] + CATALOGUE.get(first["part_no"], (0, 0, 0, 10))[3] * 5
    shown = []
    for i, l in enumerate(o["lines"]):
        q = wrong_qty if i == 0 else l["quantity"]
        shown.append(f"  - {l['part_no']}  qty {q}  @ £{l['unit_price']:.2f}  by {fmt_date_uk(l['requested_date'])}")
    po = o["po_number"] or "TBC"
    return f"""From: {CONTACTS[o['customer_id']]} <d.whitfield@mcv-leyland.example>
To: orders@supplier.example
Subject: RE: FW: Order {po}
Date: {fmt_date_uk(o['order_date'])}

Sorry, correction to the order below: line 1 ({first['part_no']}) should be {first['quantity']}, not {wrong_qty}. Everything else stands.

Dan

-----Original message-----
From: {CONTACTS[o['customer_id']]}
Subject: FW: Order {po}

Please supply against order {po}:
{chr(10).join(shown)}
Deliver to Leyland plant, goods in bay 2.
"""


def main():
    DATA.mkdir(exist_ok=True)
    INBOX.mkdir(exist_ok=True)
    for f in INBOX.iterdir():
        f.unlink()

    with open(DATA / "parts_catalogue.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["part_no", "description", "list_price_gbp", "pack_size", "lead_time_days"])
        w.writerows(PARTS)
    with open(DATA / "customers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["customer_id", "customer_name", "site", "contract_discount_pct", "order_format", "email_domain"])
        w.writerows(CUSTOMERS)

    orders = build_orders()
    writers = {"table_email": write_table_email, "free_text_email": write_free_text,
               "csv_paste": write_csv_paste, "amended_email": write_amended}
    for o in orders:
        if o["format"] == "pdf_po":
            o["file"] = f"{o['doc_id']}.pdf"
            write_pdf(o, INBOX / o["file"])
        else:
            o["file"] = f"{o['doc_id']}.txt"
            (INBOX / o["file"]).write_text(writers[o["format"]](o))

    (DATA / "answer_key.json").write_text(json.dumps(orders, indent=2))
    planted = sum(1 for o in orders if o["planted_issues"])
    print(f"Wrote {len(orders)} orders to inbox/ ({planted} with planted problems) and the answer key.")


if __name__ == "__main__":
    main()
