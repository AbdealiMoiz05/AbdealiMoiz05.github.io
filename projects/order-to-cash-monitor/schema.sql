-- Exception rules for the order-to-cash monitor (SQLite).
-- Run after load_and_flag.py has created the base tables.

-- 1. Deliveries later than promised
SELECT o.order_id, o.customer_id, o.promised_delivery_date, d.actual_delivery_date,
       julianday(d.actual_delivery_date) - julianday(o.promised_delivery_date) AS days_late
FROM orders o
JOIN deliveries d ON d.order_id = o.order_id
WHERE julianday(d.actual_delivery_date) > julianday(o.promised_delivery_date);

-- 2. Invoices past due with no full payment
SELECT i.invoice_id, i.customer_id, i.amount, i.due_date,
       COALESCE(SUM(p.amount_paid), 0) AS paid,
       i.amount - COALESCE(SUM(p.amount_paid), 0) AS outstanding
FROM invoices i
LEFT JOIN payments p ON p.invoice_id = i.invoice_id
WHERE i.status <> 'disputed'
GROUP BY i.invoice_id
HAVING outstanding > 0 AND date(i.due_date) < date('2026-12-31');

-- 3. Customers with the most disputed invoices
SELECT customer_id, COUNT(*) AS disputed_invoices, SUM(amount) AS disputed_value
FROM invoices
WHERE status = 'disputed'
GROUP BY customer_id
ORDER BY disputed_value DESC;
