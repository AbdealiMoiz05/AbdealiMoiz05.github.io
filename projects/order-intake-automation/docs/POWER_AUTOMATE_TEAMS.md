# Power Automate, Teams and SharePoint setup

This connects the review queue to where an order desk already works. You need a Microsoft 365 account with Teams, SharePoint and Power Automate (a Brunel student account usually has all three). Microsoft renames menu items now and then, so if a name below doesn't match exactly, search for the closest one.

There are two parts. Part A takes about 20 minutes. Part B takes about an hour.

---

## Part A: a Teams alert for every flagged order (20 minutes)

`notify.py` already builds a Teams card for each flagged order. This part gives it somewhere to send them.

1. In Teams, create a team called **Order Desk (demo)** with a channel called **Order review**.
2. In the channel, click the **⋯** next to the channel name, then **Workflows**.
3. Pick the template **Send webhook alerts to a channel**. Name it `Order intake alerts` and click **Next**, then **Add workflow**.
4. Copy the URL it gives you. Treat it like a password: anyone with it can post in the channel.
5. On your Mac, in the project folder:
   ```
   export TEAMS_WEBHOOK_URL="paste the URL here"
   python3 notify.py
   ```
6. Check the channel. You should see 18 cards, one per flagged order, each with the problem and the suggested fix.
7. Take a screenshot of two or three cards for the portfolio page.

**If nothing arrives:** open Power Automate (make.powerautomate.com), go to **My flows**, open `Order intake alerts` and check the **run history**. A failed run shows the step that broke.

---

## Part B: a SharePoint review list the team can work through (about 1 hour)

A Teams message is easy to miss. A SharePoint list gives the team one place to see every open problem, who owns it, and when it was resolved.

### B1. Create the list
1. In the team's SharePoint site (Teams → the team → **Files** → **Open in SharePoint**), click **New → List → Blank list**. Name it **Order Review Queue**.
2. Add these columns:

| Column | Type |
|---|---|
| Title | (exists already, holds the doc ID) |
| Customer | Single line of text |
| PONumber | Single line of text |
| Check | Choice: MISSING_PO, UNKNOWN_CUSTOMER, LOW_CONFIDENCE, DUPLICATE_PO, UNKNOWN_PART, PRICE_MISMATCH, PACK_SIZE, LEAD_TIME, UNUSUAL_QTY |
| Detail | Multiple lines of text |
| SuggestedFix | Multiple lines of text |
| Status | Choice: Pending, In progress, Resolved (default Pending) |
| Owner | Person |

### B2. Put the queue where the flow can read it
1. Run `python3 run_all.py`. It writes `output/review_queue.xlsx`, which holds an Excel table called **ReviewQueue**.
2. Upload `review_queue.xlsx` to the team's **Documents** library in SharePoint.

### B3. Build the flow
1. In Power Automate, click **Create → Automated cloud flow**. Name it `Review queue to SharePoint`. Choose the trigger **When a file is created or modified (properties only)** (SharePoint). Pick the site and the Documents library.
2. Add **Condition**: `File name with extension` is equal to `review_queue.xlsx`. Do the rest inside **If yes**.
3. Add **List rows present in a table** (Excel Online (Business)). Location: the SharePoint site. Document library: Documents. File: `review_queue.xlsx`. Table: `ReviewQueue`.
4. Add **Apply to each** on the `value` output from step 3. Inside it:
   - **Create item** (SharePoint). List: Order Review Queue. Map Title → `doc_id`, Customer → `customer`, PONumber → `po_number`, Check → `check`, Detail → `detail`, SuggestedFix → `suggested_fix`.
   - **Post card in a chat or channel** (Microsoft Teams). Post as: Flow bot. Post in: Channel. Team: Order Desk (demo). Channel: Order review. For the card, paste the JSON from any file in `output/teams_cards/` (only the part inside `"content"`) and swap the text values for the dynamic content from step 3.
5. **Save**, then re-upload `review_queue.xlsx` to trigger it. Check the list fills up and the cards appear.

### B4. Close the loop (optional, 15 minutes)
1. A second flow: **When an item is modified** (SharePoint, Order Review Queue).
2. Condition: `Status` equals `Resolved`.
3. **Post message in a chat or channel**: "✅ @{Owner} resolved @{Title}: @{Check}".

This gives you the full cycle to describe in an interview: problem found → person alerted → owner assigned → resolved → logged.

---

## What to capture for the portfolio
- A screenshot of the Teams channel with the cards.
- A screenshot of the SharePoint list with a few items set to Resolved.
- A screenshot of the flow designer showing the steps.
- One line on anything that broke and how you fixed it. Interviewers like this more than a perfect run.

## Only claim what you've built
Until Parts A and B are done, describe this part as "designed, with a step-by-step build guide". Once they're done, you can say you built the Power Automate flows.
