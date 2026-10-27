# Power Automate alert: step by step

Use a Microsoft account with Power Automate access. The free developer plan works for a personal test.

## 1. Prepare a list
1. Open Excel and save `review_queue.csv` as a file in OneDrive (or use the Excel table from the Power BI step).
2. Format it as a table, called `OverdueInvoices`.

## 2. Build the flow
1. Go to **make.powerautomate.com > Create > Scheduled cloud flow**.
2. Set it to run **once a day** at 09:00.
3. Add the action **Excel Online (Business) > List rows present in a table**. Choose the file and `OverdueInvoices`.
4. Add a **Filter array** action. Set the filter to `status` equals `pending_approval`.
5. Add an **Apply to each** loop over the filtered rows.
6. Inside the loop, add **Outlook > Send an email (V2)**.
   - To: your own test address. Never a real customer while testing.
   - Subject: the `subject` field.
   - Body: the `body` field.
   - Better still, use **Outlook > Create draft**, so a person still sends it.

## 3. Test it
1. Click **Test > Manually**.
2. Check one email arrives in your test inbox.
3. Check the email text matches the draft in the CSV.

## 4. Keep the human step
- Use **Create draft**, not **Send**, for real use. Every email needs a person to approve it first.
