"""QuickMart Signal: a weekly market brief for grocery-delivery strategy and operations analysts.

Streamlit interface over signal_core.py. Every number is calculated in code from the verified dataset,
and every alert and action cites the record IDs behind it.
"""
import html
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from signal_core import (COMPETITORS, LEVELS, DataProblem, brief_html, build_actions, demand_view, gate, load_csv,
                         md, score_article, series_change, staffing_table)

# --------------------------------------------------------------------------- interface
st.set_page_config(page_title="QuickMart Signal", page_icon="🛒", layout="wide")
st.markdown("""<style>.block-container{padding-top:2rem;max-width:1200px}
.src{font-size:.78rem;color:#5b6b7f}.lvl{font-weight:700;padding:1px 8px;border-radius:10px;font-size:.8rem}
.High{background:#fde2e1;color:#a61b1b}.Medium{background:#fff1d6;color:#8a5a00}.Low{background:#e6eef7;color:#33506e}</style>""",
            unsafe_allow_html=True)

st.title("🛒 QuickMart Signal")
st.markdown("**Your weekly grocery-delivery market brief, with every number traced to its source.**  \n"
            "Pick the competitors you care about and your store’s order volume on the left, then press "
            "**Create my brief**. You get a one-line headline, ranked actions, competitor alerts and an hour-by-hour "
            "staffing plan.")

with st.sidebar:
    st.header("1. Your data")
    data_choice = st.radio("Which data should the brief use?",
                           ["Verified QuickMart dataset (collected Oct 14, 2026)", "Upload my own dataset file"],
                           help="The verified dataset has 232 records from 3 sources: Instacart ordering patterns, "
                                "US government price and labor data, and 10 grocery news feeds.")
    uploaded = None
    if data_choice.startswith("Upload"):
        uploaded = st.file_uploader("Dataset file (quickmart_dataset.csv from the data pipeline)", type=None)
    st.header("2. What to watch")
    focus = st.multiselect("Competitors you track", list(COMPETITORS),
                           default=["Instacart", "DoorDash", "Gopuff", "Walmart", "Amazon"],
                           help="News that names one of these gets a higher alert level.")
    days = st.slider("Include news from the last … days", 7, 365, 90, step=7,
                     help="Shorter = only the freshest moves. Longer = more context.")
    min_level = st.select_slider("Show competitor alerts at or above", ["Low", "Medium", "High"], value="Medium")
    st.header("3. Your dark store")
    daily_orders = st.number_input("Orders a typical day at one dark store", min_value=0, max_value=20000,
                                   value=800, step=50,
                                   help="Used only for the staffing plan. Enter your own store’s average.")
    with st.expander("Staffing assumptions"):
        picks = st.number_input("Orders one picker can pack per hour", 1, 60, 12)
        drops = st.number_input("Orders one rider can deliver per hour", 1, 20, 3)
    go = st.button("Create my brief", type="primary", use_container_width=True)

if not go and "last" not in st.session_state:
    st.info("👈 Choose your settings on the left and press **Create my brief**. The default settings work as they are: "
            "try them first.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**What you get**  \n• One-line headline for leadership  \n• Top actions with owner, measure and deadline"
                "  \n• Competitor alerts ranked by threat")
    c2.markdown("**Built from**  \n• 10,428 real grocery orders (Instacart)  \n• Grocery price and courier job data (US BLS)"
                "  \n• 10 grocery and delivery news publishers")
    c3.markdown("**Why trust it**  \n• Numbers are calculated, not written by AI  \n• Every action shows its source record"
                "  \n• Bad or partial data stops the brief, with a reason")
    st.stop()

if go:
    st.session_state["last"] = True

# Plain-English validation of the settings themselves
problems = []
if not focus:
    problems.append("Pick at least one competitor to track, so the alerts know what matters to you.")
if daily_orders == 0:
    problems.append("Enter how many orders one dark store handles on a typical day (for example 800). "
                    "With 0 orders the staffing plan would be empty.")
if data_choice.startswith("Upload") and uploaded is None:
    problems.append("You chose to upload your own dataset, but no file is attached yet. Attach "
                    "quickmart_dataset.csv, or switch back to the verified dataset.")
if problems:
    st.error("**The brief was not created.**  \n" + "  \n".join(f"• {p}" for p in problems))
    st.stop()

try:
    df, flags, stats = gate(load_csv(uploaded))
except DataProblem as e:
    st.error(f"**The brief was not created: the data did not pass the quality check.**  \n{e}")
    st.stop()
except Exception:
    st.error("**Something unexpected went wrong while reading the data.** Nothing was created. Try the verified "
             "dataset, or re-export your file from the pipeline. If it keeps happening, send the file to the tool owner.")
    st.stop()

# ---- analysis
news = df[df["prefix"] == "QM-NEWS"]
newest = news["date_parsed"].max()
recent = news[news["date_parsed"] >= newest - pd.Timedelta(days=days)]
alerts = sorted((score_article(r, focus) for _, r in recent.iterrows()),
                key=lambda a: (-a["score"], -a["date"].toordinal()))
shown = [a for a in alerts if a["score"] >= LEVELS[min_level]]
hours, shares, ids, window, window_share = demand_view(df)
prices = series_change(df, "CPI: ")
labor = series_change(df, "Employees: ")
acts = build_actions(alerts, window, window_share, ids, prices, labor, shares)
n_high = sum(a["level"] == "High" for a in alerts)
mood = "heating up" if n_high >= 3 else "active" if n_high else "steady"
headline = (f"Market is {mood}: {n_high} high-threat competitor moves in the last {days} days; demand peaks "
            f"{window[0]:02d}:00–{(window[-1] + 1) % 24:02d}:00 ({window_share:.0f}% of orders).")

st.success(f"**This week in one line:** {md(headline)}")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Verified records used", stats["total"], help="Records that passed the quality check")
k2.metric("Complete records", f"{stats['complete_pct']:.1f}%", help="Must be 80% or more, or no brief is created")
k3.metric(f"News in last {days} days", len(recent))
k4.metric("High-threat alerts", n_high)
if flags:
    with st.expander(f"⚠️ {len(flags)} data note{'s' if len(flags) != 1 else ''} (the brief is still safe to use)"):
        for f in flags:
            st.write("• " + f)

t1, t2, t3, t4, t5 = st.tabs(["✅ Actions", "🚨 Competitor alerts", "👥 Staffing plan", "💲 Prices & labor",
                              "🔎 Sources & data check"])
with t1:
    st.subheader("Recommended actions")
    st.caption("Ranked P1 (do now) to P3 (plan). The record IDs under each action are the exact rows it is based on; "
               "look them up in the Sources tab.")
    for a in acts:
        with st.container(border=True):
            c1, c2 = st.columns([5, 2])
            c1.markdown(f"**{a['p']} · {md(a['do'])}**  \n{md(a['why'])}")
            c2.markdown(f"**Owner:** {a['owner']}  \n**Measure:** {md(a['kpi'])}  \n**When:** {a['when']}")
            with st.expander("How this was calculated"):
                for line in a["math"]:
                    st.markdown("• " + md(line))
            st.markdown(f"<span class='src'>Sources: {' · '.join(a['ids'])}</span>", unsafe_allow_html=True)
    st.download_button("⬇️ Download this brief (HTML, opens in any browser)",
                       brief_html(headline, acts, shown, stats,
                                  f"competitors: {', '.join(focus)}; news window {days} days"),
                       file_name=f"QuickMart_Signal_brief_{date.today():%Y-%m-%d}.html", mime="text/html")
with t2:
    st.subheader(f"Competitor alerts: {len(shown)} at {min_level} or above")
    st.caption("Threat level 1–5 = topic weight, +1 if it names a competitor you track, +1 if it touches speed, "
               "fees or price. Lower the alert level on the left to see more.")
    if not shown:
        st.info(f"No alerts at {min_level} or above in the last {days} days. Lower the alert level or widen the news "
                "window on the left.")
    for a in shown[:25]:
        with st.container(border=True):
            who = ", ".join(a["competitors"]) or "Industry"
            st.markdown(f"<span class='lvl {a['level']}'>{a['level']} · {a['score']}/5</span> &nbsp; "
                        f"**{html.escape(who)}** · {a['theme']} · {a['date']:%b %d, %Y} · {html.escape(a['publisher'])}",
                        unsafe_allow_html=True)
            st.markdown(f"[{md(a['title'])}]({a['url']})  \n**So what:** {md(a['so_what'])}")
            st.markdown(f"<span class='src'>Why this level: {html.escape(a['why'])} · Source: {a['id']}</span>",
                        unsafe_allow_html=True)
with t3:
    st.subheader(f"Staffing plan for {daily_orders:,} orders a day")
    st.caption(f"Assumptions: one picker packs {picks} orders an hour; one rider delivers {drops} orders an hour; "
               "demand follows the hourly pattern of 10,428 real Instacart orders. Change them on the left.")
    plan = staffing_table(shares, ids, daily_orders, picks, drops)
    chart_df = pd.DataFrame({"Hour": [f"{h:02d}" for h in range(24)],
                             "Expected orders": [daily_orders * shares.get(h, 0) / 100 for h in range(24)],
                             "Peak window": ["Peak 4 hours" if h in window else "Other hours" for h in range(24)]})
    st.altair_chart(alt.Chart(chart_df).mark_bar().encode(
        x=alt.X("Hour:N", title="Hour of day"), y=alt.Y("Expected orders:Q", title="Expected orders"),
        color=alt.Color("Peak window:N", scale=alt.Scale(domain=["Peak 4 hours", "Other hours"],
                                                         range=["#0a6b3d", "#b9cfc2"]), legend=alt.Legend(title=None)),
        tooltip=["Hour", alt.Tooltip("Expected orders:Q", format=".0f")]).properties(height=280),
        use_container_width=True)
    peak = plan.loc[plan["Expected orders"].idxmax()]
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Busiest hour ({peak['Expected orders']} orders)", peak["Hour"])
    c2.metric("Pickers at the busiest hour", int(peak["Pickers needed"]))
    c3.metric("Riders at the busiest hour", int(peak["Riders needed"]))
    p_orders = daily_orders * shares.get(int(peak["Hour"][:2]), 0) / 100
    with st.expander(f"How the {peak['Hour']} numbers were calculated, and what could make them wrong", expanded=True):
        st.markdown(
            f"1. **Expected orders:** {daily_orders:,} orders a day × {shares.get(int(peak['Hour'][:2]), 0):.2f}% "
            f"(share of real Instacart orders placed at {peak['Hour']}) = **{p_orders:.1f} orders**, rounded to "
            f"{peak['Expected orders']}.  \n"
            f"2. **Riders:** {p_orders:.1f} orders ÷ {drops} deliveries per rider per hour = {p_orders / drops:.1f}, "
            f"rounded **up** to **{int(peak['Riders needed'])} riders** (you can't send part of a rider).  \n"
            f"3. **Pickers:** {p_orders:.1f} ÷ {picks} orders packed per picker per hour = {p_orders / picks:.1f}, "
            f"rounded up to **{int(peak['Pickers needed'])} pickers**.  \n\n"
            "**What could make this wrong:** the hourly pattern is the US Instacart average, not your store; "
            "weather, promotions and holidays are not included; the rider figure assumes short trips. "
            "Change the assumptions on the left to match your store and the numbers update.")
    st.dataframe(plan, hide_index=True, use_container_width=True, height=300)
with t4:
    st.subheader("Cost pressure: grocery prices and the labor we compete for")
    st.caption("Change between the first and last month available in the verified data (US BLS, seasonally adjusted).")
    cols = st.columns(3)
    for i, p in enumerate(prices):
        cols[i % 3].metric(f"Prices: {p['name']}", f"{p['pct']:+.1f}%", help=f"{p['from']:%b %Y} → {p['to']:%b %Y}; "
                           f"sources {', '.join(p['ids'])}", delta_color="off")
    st.markdown("**Jobs (people employed)**")
    cols = st.columns(3)
    for i, l in enumerate(labor):
        cols[i % 3].metric(l["name"], f"{l['pct']:+.1f}%", help=f"{l['from']:%b %Y} → {l['to']:%b %Y}; "
                           f"sources {', '.join(l['ids'])}", delta_color="off")
with t5:
    st.subheader("Where every number comes from")
    for name, n in stats["by_source"].items():
        st.markdown(f"• **{name}:** {n} records")
    st.caption("Search a record ID from any action or alert (for example QM-DMD-011) to see the row behind it.")
    q = st.text_input("Look up a record ID or word", placeholder="QM-DMD-011")
    view = df[["record_id", "title", "date", "metric_value", "unit", "url", "is_complete"]]
    if q.strip():
        view = view[view.apply(lambda r: q.strip().lower() in " ".join(r.astype(str)).lower(), axis=1)]
        if view.empty:
            st.warning(f"No record matches “{q}”. Record IDs look like QM-DMD-011, QM-MKT-001 or QM-NEWS-003.")
    st.dataframe(view.rename(columns={"record_id": "Record ID", "title": "What it is", "date": "Date",
                                      "metric_value": "Value", "unit": "Unit", "url": "Link",
                                      "is_complete": "Complete?"}),
                 hide_index=True, use_container_width=True,
                 column_config={"Link": st.column_config.LinkColumn("Link", display_text="open")})
