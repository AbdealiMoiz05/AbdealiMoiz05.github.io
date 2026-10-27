"""Generate synthetic order-to-cash data for the exception monitor.

Writes four CSV files into data/: customers, orders, deliveries, invoices and payments.
All data is invented. No real company data is used.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_ORDERS = 3000
START = date(2026, 1, 1)
OUT = Path(__file__).parent / "data"

CUSTOMERS = [
    ("C01", "Northgate Motors", "UK"),
    ("C02", "Ferncliff Vehicles", "UK"),
    ("C03", "Brightline Auto", "UK"),
    ("C04", "Ashford Cars", "UK"),
    ("C05", "Meridian Fleet", "UK"),
    ("C06", "Coastway Motors", "UK"),
    ("C07", "Redwell Automotive", "UK"),
    ("C08", "Harbour Lane Cars", "UK"),
]
PARTS = [("P100", "Brake pad set", 38.0), ("P200", "Fuel injector", 115.0),
         ("P300", "Alternator", 210.0), ("P400", "Sensor module", 64.5),
         ("P500", "Wiper motor", 88.0)]
PAYMENT_TERMS_DAYS = 30


def write(name, rows, header):
    OUT.mkdir(exist_ok=True)
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    rng = random.Random(SEED)
    write("customers.csv", CUSTOMERS, ["customer_id", "customer_name", "country"])

    orders, deliveries, invoices, payments = [], [], [], []
    for i in range(1, N_ORDERS + 1):
        oid = f"O{i:05d}"
        cust = rng.choice(CUSTOMERS)[0]
        part, _, unit = rng.choice(PARTS)
        qty = rng.randint(5, 400)
        order_date = START + timedelta(days=rng.randint(0, 270))
        due_delivery = order_date + timedelta(days=rng.randint(7, 21))
        # About 15% of deliveries arrive late, by 1 to 12 days.
        late = rng.random() < 0.15
        actual = due_delivery + timedelta(days=rng.randint(1, 12) if late else rng.randint(-1, 1))
        orders.append((oid, cust, part, qty, order_date.isoformat(), due_delivery.isoformat()))
        deliveries.append((oid, actual.isoformat(), qty if rng.random() > 0.05 else qty - rng.randint(1, 10)))

        inv_id = f"INV{i:05d}"
        amount = round(qty * unit, 2)
        inv_date = actual + timedelta(days=rng.randint(0, 3))
        due = inv_date + timedelta(days=PAYMENT_TERMS_DAYS)
        dispute = rng.random() < 0.06
        invoices.append((inv_id, oid, cust, amount, inv_date.isoformat(), due.isoformat(),
                         "disputed" if dispute else "open"))

        # About 85% of invoices are paid, some after the due date.
        if rng.random() < 0.85 and not dispute:
            paid = due + timedelta(days=rng.randint(-10, 25))
            payments.append((f"PAY{i:05d}", inv_id, round(amount, 2), paid.isoformat()))

    write("orders.csv", orders,
          ["order_id", "customer_id", "part_id", "quantity", "order_date", "promised_delivery_date"])
    write("deliveries.csv", deliveries, ["order_id", "actual_delivery_date", "quantity_delivered"])
    write("invoices.csv", invoices,
          ["invoice_id", "order_id", "customer_id", "amount", "invoice_date", "due_date", "status"])
    write("payments.csv", payments, ["payment_id", "invoice_id", "amount_paid", "paid_date"])
    print(f"Wrote {len(orders)} orders, {len(invoices)} invoices, {len(payments)} payments to {OUT}")


if __name__ == "__main__":
    main()
