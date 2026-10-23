"""QuickMart Signal core: data gate and analysis behind the weekly market brief for grocery-delivery strategy and operations analysts.

Wraps the QuickMart data pipeline (Assignments 3-4) in a Streamlit interface. Every number is
calculated in code from the verified dataset, and every alert and action cites the record IDs behind it.
"""
import html
import io
import math
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

DATA_FILE = Path(__file__).parent / "data" / "quickmart_dataset.csv"
REQUIRED_COLUMNS = ["record_id", "record_type", "source", "title", "date", "category",
                    "subcategory", "metric_name", "metric_value", "unit", "url", "details", "is_complete"]
SOURCE_PREFIX = {"QM-DMD": "Ordering patterns (Instacart orders)",
                 "QM-MKT": "Prices and labor (US Bureau of Labor Statistics)",
                 "QM-NEWS": "Competitor and industry news (10 publisher feeds)"}
COMPETITORS = {
    "Instacart": [r"instacart"], "DoorDash": [r"doordash"], "Gopuff": [r"gopuff"],
    "Uber Eats": [r"uber eats", r"\buber\b"], "Walmart": [r"walmart"], "Amazon": [r"amazon", r"whole foods"],
    "Kroger": [r"kroger"], "Albertsons": [r"albertsons", r"safeway"], "Aldi": [r"\baldi\b"],
    "Costco": [r"costco"], "Target": [r"\btarget\b"], "Shipt": [r"shipt"],
}
CATEGORY_WEIGHT = {"Competitor Moves": 2, "Quick Commerce & Ultrafast Delivery": 3, "Dark Stores & Fulfillment": 3,
                   "Funding & M&A": 2, "Delivery Labor & Regulation": 2, "Grocery E-commerce": 2,
                   "Pricing & Consumer Demand": 2, "Grocery Industry": 1}
# (theme, keywords, what it means for a 10-minute grocery delivery business)
THEMES = [
    ("Delivery speed", [r"drone", r"same.day", r"\bminute", r"instant", r"ultrafast", r"quick commerce", r"\bfast",
                        r"rapid", r"express", r"one.hour"],
     "A rival is closing the speed gap. Check that our 10-minute promise still holds at the busiest hours, "
     "and say it louder in the app and in ads."),
    ("Membership and fees", [r"membership", r"subscription", r"\bfee", r"\bplus\b", r"\bpass\b", r"free delivery"],
     "Customers may compare our delivery fee with this offer. Review fees and the free-delivery minimum "
     "before the next promo cycle."),
    ("Labor and couriers", [r"courier", r"driver", r"dasher", r"\bgig", r"worker", r"\bwage", r"labor", r"union"],
     "Courier costs or rules may change. Check rider pay and supply in the cities where this applies."),
    ("Price war", [r"price", r"discount", r"\bdeal", r"cheap", r"low.cost", r"promo", r"coupon", r"surge"],
     "Price-sensitive shoppers may switch. Compare our prices on the 50 most-bought items with this rival this week."),
    ("Expansion and deals", [r"expand", r"launch", r"\bopen", r"acqui", r"merger", r"partner", r"funding", r"raise"],
     "A rival is adding reach or money. Watch for new launches in our delivery zones over the next 30 days."),
    ("AI and technology", [r"\bai\b", r"artificial intelligence", r"automat", r"robot", r"agentic"],
     "Rivals are using technology to cut cost or personalise. Note it for the product roadmap; no action needed this week."),
]
LEVELS = {"High": 4, "Medium": 3, "Low": 1}


def md(text) -> str:
    """Make text safe for Streamlit markdown ($ starts LaTeX, * and _ start emphasis)."""
    return re.sub(r"([\\$*_`<>#|\[\]])", r"\\\1", str(text))


def detail(row, key):
    m = re.search(rf"(?:^|; ){key}=([^;]*)", str(row.get("details", "")))
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------- data + GIGO gate
class DataProblem(Exception):
    """A data problem the user can fix. The message is shown as is, in plain English."""


def load_csv(uploaded):
    if uploaded is None:
        return pd.read_csv(DATA_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if not uploaded.name.lower().endswith(".csv"):
        raise DataProblem(f"“{uploaded.name}” is not a CSV file. Upload the quickmart_dataset.csv file that the "
                          "QuickMart data pipeline saves, or switch back to the verified dataset.")
    raw = uploaded.getvalue()
    if not raw.strip():
        raise DataProblem("The file you uploaded is empty. Re-export it from the data pipeline and try again.")
    try:
        return pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception:
        raise DataProblem("This file could not be read as a table. Make sure it is a comma-separated CSV, "
                          "not an Excel workbook renamed to .csv.")


def gate(df):
    """Phase gate from the Conductor Brief (Parts 4-5). Hard stops raise DataProblem; flags are returned."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataProblem("This file is missing columns the brief needs: " + ", ".join(missing) +
                          ". It does not look like a QuickMart dataset. Use the file the pipeline saves "
                          "(quickmart_dataset.csv), or switch back to the verified dataset.")
    if len(df) < 50:
        raise DataProblem(f"Only {len(df)} records were found. The brief needs at least 50 to be trustworthy. "
                          "Run the data pipeline again and upload the new file.")
    df = df.copy()
    df["prefix"] = df["record_id"].str.extract(r"^(QM-[A-Z]+)")[0]
    absent = [name for p, name in SOURCE_PREFIX.items() if not (df["prefix"] == p).any()]
    if absent:
        raise DataProblem("One of the three sources is missing from this file: " + "; ".join(absent) +
                          ". A brief built on part of the market would look complete but mislead you, "
                          "so it was not created. Re-run the pipeline and check its run log.")
    complete_pct = (df["is_complete"].str.lower() == "yes").mean() * 100
    if complete_pct < 80:
        raise DataProblem(f"Only {complete_pct:.0f}% of records are complete (the minimum is 80%). "
                          "The cleaning step is probably failing. Check the pipeline’s run log before using this data.")
    df["date_parsed"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    flags = []
    bad_dates = int(df["date_parsed"].isna().sum())
    if bad_dates:
        flags.append(f"{bad_dates} records have a date that is not in YYYY-MM-DD format. They were left out.")
    future = int((df["date_parsed"] > pd.Timestamp(date.today() + timedelta(days=1))).sum())
    if future:
        flags.append(f"{future} records are dated in the future. They were left out.")
    dupes = int(df.duplicated(subset=["record_id"]).sum())
    if dupes:
        flags.append(f"{dupes} duplicate record IDs were found. Only the first copy of each was kept.")
    df = df[df["date_parsed"].notna() & ~(df["date_parsed"] > pd.Timestamp(date.today() + timedelta(days=1)))]
    df = df.drop_duplicates(subset=["record_id"])
    df["value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    incomplete = df[df["is_complete"].str.lower() != "yes"]
    if len(incomplete):
        flags.append(f"{len(incomplete)} records are incomplete (for example, values the publisher never released). "
                     "They are kept for the record but never used in a calculation.")
    stats = {"total": len(df), "complete_pct": complete_pct,
             "by_source": {SOURCE_PREFIX[p]: int((df["prefix"] == p).sum()) for p in SOURCE_PREFIX}}
    return df, flags, stats


# --------------------------------------------------------------------------- analysis (all numbers in code)
def score_article(row, focus):
    text = f"{row['title']} {detail(row, 'summary')}".lower()
    named = [c for c, pats in COMPETITORS.items() if any(re.search(p, text) for p in pats)]
    themes = [(t, why) for t, pats, why in THEMES if any(re.search(p, text) for p in pats)]
    score = CATEGORY_WEIGHT.get(row["category"], 1)
    reasons = [f"topic: {row['category']}"]
    if any(c in focus for c in named):
        score += 1
        reasons.append("names a competitor you are tracking")
    if themes and themes[0][0] in ("Delivery speed", "Membership and fees", "Price war"):
        score += 1
        reasons.append(f"touches {themes[0][0].lower()}, which our customers notice first")
    if not themes:
        score = min(score, 3)  # no clear theme: never more than Medium
    score = max(1, min(5, score))
    level = "High" if score >= 4 else "Medium" if score == 3 else "Low"
    so_what = themes[0][1] if themes else "Background on the market. Read it if you have time; no action needed."
    return {"id": row["record_id"], "title": row["title"], "date": row["date_parsed"].date(), "url": row["url"],
            "publisher": row["subcategory"], "competitors": named, "theme": themes[0][0] if themes else "General",
            "score": score, "level": level, "so_what": so_what, "why": "; ".join(reasons)}


def demand_view(df):
    hours = df[(df["category"] == "Demand by hour of day") & df["value"].notna()].copy()
    hours["hour"] = hours["subcategory"].str[:2].astype(int)
    hours = hours.sort_values("hour")
    shares = hours.set_index("hour")["value"]
    ids = hours.set_index("hour")["record_id"]
    best = max(range(24), key=lambda h: sum(shares.get((h + k) % 24, 0) for k in range(4)))
    window = [(best + k) % 24 for k in range(4)]
    return hours, shares, ids, window, sum(shares.get(h, 0) for h in window)


def series_change(df, category_prefix):
    out = []
    rows = df[df["subcategory"].str.startswith(category_prefix) & df["value"].notna()]
    for name, g in rows.groupby("subcategory"):
        g = g.sort_values("date_parsed")
        if len(g) < 2:
            continue
        first, last = g.iloc[0], g.iloc[-1]
        pct = (last["value"] / first["value"] - 1) * 100
        out.append({"name": name.split(": ", 1)[-1], "pct": pct, "from": first["date_parsed"], "to": last["date_parsed"],
                    "ids": [first["record_id"], last["record_id"]], "unit": last["unit"]})
    return sorted(out, key=lambda r: -r["pct"])


def build_actions(alerts, window, window_share, ids, prices, labor):
    acts = []
    acts.append({"p": "P1", "owner": "Operations",
                 "do": f"Put most pickers and riders on shift from {window[0]:02d}:00 to {(window[-1] + 1) % 24:02d}:00.",
                 "why": f"{window_share:.1f}% of all orders arrive in these four hours, so this is where the "
                        "10-minute promise is most at risk.",
                 "kpi": "Share of orders delivered in 10 minutes or less during these hours", "when": "This week",
                 "ids": [ids[h] for h in window]})
    top = [a for a in alerts if a["level"] == "High"][:1] or alerts[:1]
    if top:
        a = top[0]
        who = ", ".join(a["competitors"]) or "A competitor"
        acts.append({"p": "P1", "owner": "Strategy", "do": f"Brief leadership on: {a['title']}",
                     "why": f"{who}: {a['so_what']}", "kpi": "Decision recorded in Monday's leadership meeting",
                     "when": "Monday", "ids": [a["id"]]})
    food = next((p for p in prices if p["name"].lower() == "food at home"), None)
    if food:
        up = food["pct"] > 0
        acts.append({"p": "P2", "owner": "Pricing",
                     "do": ("Hold prices on everyday staples and push own-label items." if up else
                            "Use the flat grocery prices to run a staples promotion."),
                     "why": f"Grocery prices (food at home) moved {food['pct']:+.1f}% between "
                            f"{food['from']:%b %Y} and {food['to']:%b %Y}.",
                     "kpi": "Basket size and repeat rate of price-sensitive customers", "when": "30 days",
                     "ids": food["ids"]})
    courier = next((l for l in labor if "courier" in l["name"].lower()), None)
    if courier:
        acts.append({"p": "P3", "owner": "Operations",
                     "do": ("More couriers are being hired across the US: review rider pay before the holiday peak."
                            if courier["pct"] >= 0 else
                            "Courier jobs are shrinking: hire holiday riders early while supply is available."),
                     "why": f"US courier jobs changed {courier['pct']:+.1f}% between {courier['from']:%b %Y} "
                            f"and {courier['to']:%b %Y}.",
                     "kpi": "Open rider shifts filled", "when": "60 days", "ids": courier["ids"]})
    return acts


def staffing_table(shares, ids, daily_orders, picks_per_hour, drops_per_hour):
    rows = []
    for h in range(24):
        share = shares.get(h, 0.0)
        orders = daily_orders * share / 100
        rows.append({"Hour": f"{h:02d}:00", "Share of orders": f"{share:.1f}%", "Expected orders": round(orders),
                     "Pickers needed": math.ceil(orders / picks_per_hour) if orders >= 0.5 else 0,
                     "Riders needed": math.ceil(orders / drops_per_hour) if orders >= 0.5 else 0,
                     "Source": ids.get(h, "")})
    return pd.DataFrame(rows)


def brief_html(headline, acts, alerts, stats, settings):
    esc = html.escape
    act_rows = "".join(f"<tr><td>{a['p']}</td><td><b>{esc(a['do'])}</b><br><small>{esc(a['why'])}</small></td>"
                       f"<td>{a['owner']}</td><td>{esc(a['kpi'])}</td><td>{a['when']}</td>"
                       f"<td><small>{' '.join(a['ids'])}</small></td></tr>" for a in acts)
    alert_rows = "".join(f"<tr><td>{a['level']}</td><td><a href='{esc(a['url'])}'>{esc(a['title'])}</a><br>"
                         f"<small>{esc(a['so_what'])}</small></td><td>{a['date']}</td><td><small>{a['id']}</small></td></tr>"
                         for a in alerts[:10])
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>QuickMart Signal brief</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:24px auto;color:#14213d}}
table{{border-collapse:collapse;width:100%;margin:8px 0 18px}}td,th{{border:1px solid #dde;padding:6px;text-align:left;vertical-align:top}}
th{{background:#eef5f0}}h1{{color:#0a6b3d}}</style></head><body>
<h1>QuickMart Signal: weekly market brief</h1><p><i>Generated {date.today():%B %d, %Y} · {stats['total']} verified records ·
{settings}</i></p><h2>{esc(headline)}</h2><h3>Recommended actions</h3>
<table><tr><th>Priority</th><th>Action</th><th>Owner</th><th>Measure</th><th>When</th><th>Sources</th></tr>{act_rows}</table>
<h3>Competitor alerts</h3><table><tr><th>Level</th><th>What happened / so what</th><th>Date</th><th>Source</th></tr>{alert_rows}</table>
<p><small>Every number is calculated from the records listed. Record IDs match quickmart_dataset.csv.</small></p></body></html>"""


