# Power BI dashboard: step by step

You need Power BI Desktop (free, Windows only). Download it from the Microsoft Store.

## 1. Load the data
1. Run `python3 generate_data.py` and `python3 load_and_flag.py`. This creates `exceptions.db`.
2. In Power BI Desktop: **Get data > ODBC** or **SQLite** (install the ODBC driver if asked).
3. Point it at `exceptions.db` and load `invoices`, `payments`, `customers`, `deliveries` and `orders`.
   If SQLite isn't listed, export the five tables from `data/*.csv` instead. Use **Get data > Text/CSV**.

## 2. Build the model
1. Go to **Model view**. Link `invoices[customer_id]` to `customers[customer_id]`.
2. Link `payments[invoice_id]` to `invoices[invoice_id]`.
3. Link `deliveries[order_id]` to `orders[order_id]`.

## 3. Add measures
In **Modelling > New measure**, add:
```
Total invoiced = SUM(invoices[amount])
Total paid = SUM(payments[amount_paid])
Outstanding = [Total invoiced] - [Total paid]
Disputed value = CALCULATE(SUM(invoices[amount]), invoices[status] = "disputed")
```

## 4. Build one page
- **Card:** Outstanding.
- **Card:** Disputed value.
- **Bar chart:** Outstanding by customer name, sorted high to low.
- **Table:** invoice_id, customer, amount, due_date, Outstanding. Filter to Outstanding > 0.
- **Slicer:** customer name.

## 5. Check it
- Outstanding should equal invoiced minus paid. Compare one customer by hand to be sure.
- Save as `order-to-cash.pbix` and add a screenshot to the repo.
