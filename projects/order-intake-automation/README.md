# Customer order intake automation

A personal project by Abdeali Moiz, built on **synthetic data**. Every company, part, price and order here is invented by `generate_data.py`.

## The problem

A parts supplier gets purchase orders from car makers in whatever format each customer prefers: tidy email tables, chatty emails, PDF purchase orders, pasted spreadsheet rows, and email threads where the buyer corrects the order two messages later. Someone on the order desk reads each one, types it into the system and checks the part number, price, pack size and delivery date by hand. That is slow, and the mistakes turn into credit notes, re-invoices and late payments further down the line.

## What this does

```
inbox/ (emails + PDFs) → extract.py → validate.py → review queue + Teams card → person decides
                                                   → clean orders → ready to book
```

| Step | Script | What it does |
|---|---|---|
| 1. Read | `extract.py` | A rules reader handles the tidy formats for free. Orders it isn't sure about go to the **Claude API**, which reads the email or the PDF itself and returns JSON that has to match a fixed schema. It never guesses: unreadable fields come back empty and listed. |
| 2. Check | `validate.py` | Loads everything into SQLite and runs nine checks against the parts catalogue and customer contracts: missing PO, unknown customer, unknown part (with the closest catalogue match), contract price, pack size, lead time, unusual quantity, duplicate PO, and low reading confidence. |
| 3. Route | `validate.py` | Orders that pass every check are approved. Anything else goes to a review queue with a suggested fix. Nothing is changed or booked automatically. |
| 4. Alert | `notify.py` | Builds a Microsoft Teams card for each flagged order and an Excel table for Power Automate and SharePoint. See [docs/POWER_AUTOMATE_TEAMS.md](docs/POWER_AUTOMATE_TEAMS.md). |
| 5. Measure | `evaluate.py` | Compares the output with the answer key: how many orders were read right, and how many planted problems were caught. |
| 6. Value | `time_saved.py` | Turns the measured review rate into hours saved per week, from assumptions written down in `data/assumptions.csv`. |

## Results from the rules-only run (no API key)

| Measure | Result |
|---|---|
| Orders processed | 41 orders in 5 formats, from 5 customers |
| Read exactly right | 33 of 41 (98.5% of fields) |
| Planted problems caught | 13 of 13 |
| Wrongly read orders that were auto-approved | **0** |
| Orders sent to a person | 18 of 41 (44%) |
| Clean orders sent to a person anyway | 5, all correction threads the rules reader can't follow |

All 8 orders the rules reader got wrong were email threads where the buyer corrected a quantity. The reader spotted the correction, marked the order "low confidence" and sent it to a person instead of booking the wrong number. That is the gap the AI step is there to close.

The data has more problems planted in it than a real inbox would, so the checks have something to catch. A real review rate should be lower.

## Time saved

From `time_saved.py`, at 250 orders a week. **Every input is an assumption** until someone times the real process.

| Scenario | Manual h/week | Automated h/week | Saved h/week | Saved h/year |
|---|---|---|---|---|
| Low (4 min per order by hand) | 22.3 | 14.3 | 8.0 | 370 |
| Base (7 min) | 34.8 | 14.3 | 20.5 | 945 |
| High (10 min) | 47.3 | 14.3 | 33.0 | 1,520 |
| Base, if the AI reads the correction threads correctly (not yet measured) | 34.8 | 11.7 | 23.1 | 1,062 |

The first thing to do on a real team is time 20 orders by hand and replace the assumptions.

## Run it

Python 3.10 or later.

```
pip install -r requirements.txt
python3 run_all.py                    # rules only, no API key needed
export ANTHROPIC_API_KEY=your_key
python3 run_all.py --method hybrid    # rules first, AI for the doubtful orders
python3 run_all.py --method ai        # AI reads every order, to compare against rules
python3 -m unittest discover tests
```

`extract.py` prints the tokens used so you can see the cost per order.

## Design choices

- **The AI reads; Python checks.** The model only turns a document into data. Every business rule (prices, pack sizes, lead times) is plain code that can be tested and audited.
- **A person in the loop.** Anything doubtful goes to a person with a suggested fix. The system never edits an order on its own.
- **Measure, don't claim.** The answer key makes accuracy a number, not an opinion. Run the AI and compare it with the rules before trusting it.
- **Cheapest tool first.** The rules reader is free and handled 80% of orders. The AI is only paid for on the rest.

## Limits

- Synthetic data. I wrote the rules reader knowing the five formats, so its accuracy here is better than it would be on a real inbox.
- The AI step's code has been tested with a mock response, not yet against the live API on these orders.
- The Power Automate, Teams and SharePoint part needs a Microsoft 365 account, so it is a step-by-step guide rather than a live flow.
- Duplicate checks only look within one run. A real version would check against orders already booked in the ERP.
