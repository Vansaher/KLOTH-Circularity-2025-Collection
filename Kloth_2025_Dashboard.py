# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="KLOTH Malaysia Week 33", layout="wide")

DATA_PATH = "KLOTH_Malaysia_Week33_Enriched.xlsx"

@st.cache_data
def load_data(path: str):
    df = pd.read_excel(path)
    # Ensure numeric
    for col in ["Total Acceptable (KG)", "Total Rejected (KG)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    # Normalize key text cols to string
    for col in ["Site Contract ID", "Location Name", "Site Address", "State/Federal Territory"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df

if not Path(DATA_PATH).exists():
    st.error(f"Data file not found: {DATA_PATH}")
    st.stop()

df = load_data(DATA_PATH)

st.title("KLOTH Malaysia Week 33 Dashboard")
st.caption("Dataset: KLOTH_Malaysia_Week33_Enriched.xlsx")

# -----------------------
# Sidebar – Filters
# -----------------------
st.sidebar.header("Filters")

# State/FT
state_options = sorted(df["State/Federal Territory"].dropna().unique())
state_filter = st.sidebar.multiselect("State / Federal Territory", state_options)

# Site ID
site_options = sorted(df["Site Contract ID"].dropna().unique())
site_filter = st.sidebar.multiselect("Site Contract ID", site_options)

# Text search
name_query = st.sidebar.text_input("Search Location Name (contains)", value="")
addr_query = st.sidebar.text_input("Search Site Address (contains)", value="")

# Sliders for range
acc_min, acc_max = float(df["Total Acceptable (KG)"].min()), float(df["Total Acceptable (KG)"].max())
rej_min, rej_max = float(df["Total Rejected (KG)"].min()), float(df["Total Rejected (KG)"].max())
acc_range = st.sidebar.slider(
    "Acceptable (KG) range", min_value=0.0, max_value=max(acc_max, 1.0), value=(0.0, max(acc_max, 1.0))
)

# Top N control for charts
top_n = st.sidebar.number_input("Top N (locations)", min_value=3, max_value=50, value=10, step=1)

# -----------------------
# Apply filters
# -----------------------
filtered = df.copy()

if state_filter:
    filtered = filtered[filtered["State/Federal Territory"].isin(state_filter)]

if site_filter:
    filtered = filtered[filtered["Site Contract ID"].isin(site_filter)]

if name_query.strip():
    q = name_query.lower().strip()
    filtered = filtered[filtered["Location Name"].str.lower().str.contains(q)]

if addr_query.strip():
    q2 = addr_query.lower().strip()
    filtered = filtered[filtered["Site Address"].str.lower().str.contains(q2)]

filtered = filtered[
    (filtered["Total Acceptable (KG)"].between(acc_range[0], acc_range[1]))
]

# -----------------------
# KPIs
# -----------------------
total_acc = float(filtered["Total Acceptable (KG)"].sum())
total_rej = float(filtered["Total Rejected (KG)"].sum())
acc_rate = (total_acc / (total_acc + total_rej) * 100.0) if (total_acc + total_rej) > 0 else 0.0
site_count = filtered["Site Contract ID"].nunique()
avg_acc_per_site = (total_acc / site_count) if site_count else 0.0

# Top State/FT & Location
state_totals = (
    filtered.groupby("State/Federal Territory", as_index=False)["Total Acceptable (KG)"].sum()
    .sort_values("Total Acceptable (KG)", ascending=False)
)
top_state = state_totals.iloc[0]["State/Federal Territory"] if not state_totals.empty else "-"
top_state_val = float(state_totals.iloc[0]["Total Acceptable (KG)"]) if not state_totals.empty else 0.0

loc_totals = (
    filtered.groupby("Location Name", as_index=False)["Total Acceptable (KG)"].sum()
    .sort_values("Total Acceptable (KG)", ascending=False)
)
top_loc = loc_totals.iloc[0]["Location Name"] if not loc_totals.empty else "-"
top_loc_val = float(loc_totals.iloc[0]["Total Acceptable (KG)"]) if not loc_totals.empty else 0.0

st.markdown(f"**Total Records:** {len(filtered)}")

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("Total Acceptable (KG)", f"{total_acc:,.1f}")
k2.metric("Total Rejected (KG)", f"{total_rej:,.1f}")
k3.metric("Acceptance Rate", f"{acc_rate:,.1f}%")
k4.metric("# Unique Sites", f"{site_count:,}")
k5.metric("Avg Acceptable / Site (KG)", f"{avg_acc_per_site:,.1f}")
k6.metric("Top State/FT", f"{top_state}")
k7.metric("Top State Acceptable (KG)", f"{top_state_val:,.1f}")

# -----------------------
# Raw table + download
# -----------------------
with st.expander("Show filtered table"):
    st.dataframe(filtered, use_container_width=True, height=400)
    st.download_button(
        "Download filtered CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="kloth_week33_filtered.csv",
        mime="text/csv"
    )

# -----------------------
# 1) Your requested bar: Acceptable by Location
# -----------------------
st.subheader("Total Acceptable (KG) by Location")
bar_data = (
    filtered.groupby("Location Name", as_index=False)["Total Acceptable (KG)"]
    .sum()
    .sort_values("Total Acceptable (KG)", ascending=False)
    .head(int(top_n))
)
bar_chart = px.bar(
    bar_data,
    x="Location Name",
    y="Total Acceptable (KG)",
    title=f"Acceptable Collection by Location (Top {int(top_n)})",
    text_auto=True,
    color="Total Acceptable (KG)",
    color_continuous_scale="Blues",
)
bar_chart.update_layout(xaxis_tickangle=-30)
st.plotly_chart(bar_chart, use_container_width=True)

# -----------------------
# 2) Your requested pie: Acceptable share by State/FT
# -----------------------
state_pie_data = (
    filtered.groupby("State/Federal Territory", as_index=False)["Total Acceptable (KG)"]
    .sum()
    .sort_values("Total Acceptable (KG)", ascending=False)
)
state_pie = px.pie(
    state_pie_data,
    values="Total Acceptable (KG)",
    names="State/Federal Territory",
    title="Share of Acceptable Collection by State / Federal Territory",
    hole=0.3
)
st.plotly_chart(state_pie, use_container_width=True)

# -----------------------
# 3) Accepted per State/FT (stacked)
# -----------------------
state_compare = (
    filtered.groupby("State/Federal Territory", as_index=False)[["Total Acceptable (KG)", "Total Rejected (KG)"]]
    .sum()
    .sort_values("Total Acceptable (KG)", ascending=False)
)
fig_compare = px.bar(
    state_compare,
    x="State/Federal Territory",
    y=["Total Acceptable (KG)", "Total Rejected (KG)"],
    title="Accepted (KG) by State / Federal Territory",
    barmode="stack",
)
st.plotly_chart(fig_compare, use_container_width=True)

st.caption("Tip: Use the sidebar filters to drill into specific sites or regions.")

