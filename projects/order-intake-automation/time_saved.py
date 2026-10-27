"""Step 5: put a number on the time saved, with every assumption written down.

Reads data/assumptions.csv (edit it, then re-run) and the review rate measured
in this run (output/run_summary.json). Shows a range, not one number, because
the inputs are assumptions until someone times the real process.

Usage: python3 time_saved.py   (after validate.py)
Writes output/time_saved.csv.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "output"


def weekly_hours(a, review_rate, manual_minutes):
    v = a["orders_per_week"]
    manual = v * manual_minutes + v * a["manual_error_rate_pct"] / 100 * a["rework_minutes_per_error"]
    automated = (v * review_rate * a["review_minutes_per_flagged_order"]
                 + v * (1 - review_rate) * a["spot_check_minutes_per_auto_order"]
                 + v * a["residual_error_rate_pct"] / 100 * a["rework_minutes_per_error"])
    return manual / 60, automated / 60


def main():
    with open(HERE / "data" / "assumptions.csv") as f:
        a = {r["name"]: float(r["value"]) for r in csv.DictReader(f)}
    s = json.loads((OUT / "run_summary.json").read_text())
    review_rate = s["sent_to_review"] / s["orders"]
    low_conf_only = s["flagged_only_for_low_confidence"]
    # What-if: the AI step reads the correction emails correctly, so those orders stop needing a person.
    ai_review_rate = (s["sent_to_review"] - low_conf_only) / s["orders"]

    scenarios = []
    for label, minutes, rate in [("Low (4 min manual)", 4, review_rate),
                                 ("Base", a["manual_minutes_per_order"], review_rate),
                                 ("High (10 min manual)", 10, review_rate),
                                 ("Base + AI reads threads*", a["manual_minutes_per_order"], ai_review_rate)]:
        manual, auto = weekly_hours(a, rate, minutes)
        saved = manual - auto
        year = saved * a["working_weeks_per_year"]
        scenarios.append({"scenario": label, "review_rate_pct": round(100 * rate, 1),
                          "manual_hours_per_week": round(manual, 1), "automated_hours_per_week": round(auto, 1),
                          "hours_saved_per_week": round(saved, 1), "hours_saved_per_year": round(year),
                          "fte_equivalent": round(year / (a["hours_per_fte_week"] * a["working_weeks_per_year"]), 2)})

    with open(OUT / "time_saved.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(scenarios[0]))
        w.writeheader()
        w.writerows(scenarios)

    print(f"Review rate measured in this run: {100 * review_rate:.0f}% of orders "
          f"({low_conf_only} orders were flagged only because the rules reader was not sure).")
    print(f"{'Scenario':<27}{'Manual h/wk':>12}{'Automated h/wk':>16}{'Saved h/wk':>12}{'Saved h/yr':>12}{'FTE':>7}")
    for r in scenarios:
        print(f"{r['scenario']:<27}{r['manual_hours_per_week']:>12}{r['automated_hours_per_week']:>16}"
              f"{r['hours_saved_per_week']:>12}{r['hours_saved_per_year']:>12}{r['fte_equivalent']:>7}")
    print("* What-if, not measured yet: run extract.py with an API key and check evaluate.py first.")
    print("All inputs are assumptions in data/assumptions.csv. Time a real sample before quoting these.")


if __name__ == "__main__":
    main()
