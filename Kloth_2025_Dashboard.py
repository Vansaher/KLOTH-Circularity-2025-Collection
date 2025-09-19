import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="KLOTH Malaysia Week 33", layout="wide")

# --------- File paths (must exist in repo root) ----------
AGG_PATH = "KLOTH_Malaysia_Week33_Enriched.xlsx"  # Aggregated snapshot
FACT_PATH = "2025 Week 33.xlsx"                    # Contains sheet "Fact"

# -------------------- Loaders --------------------
@st.cache_data
def load_aggregated(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    for col in ["Total Acceptable (KG)", "Total Rejected (KG)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in ["Site Contract ID", "Location Name", "Site Address", "State/Federal Territory"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df

@st.cache_data
def load_fact(book_path: str, sheet: str = "Fact") -> pd.DataFrame:
    fact = pd.read_excel(book_path, sheet_name=sheet)
    # Expected cols: Name, Date (serial), LocationName, Site, SiteAddress, WeightKG, MonthStart, MonthText, Day of Week
    # Convert Excel serial dates
    if "Date" in fact.columns:
        fact["Date_dt"] = pd.to_datetime(fact["Date"], unit="D", origin="1899-12-30", errors="coerce")
    if "MonthStart" in fact.columns:
        fact["MonthStart_dt"] = pd.to_datetime(fact["MonthStart"], unit="D", origin="1899-12-30", errors="coerce")
    # Types
    fact["WeightKG"] = pd.to_numeric(fact.get("WeightKG", 0.0), errors="coerce").fillna(0.0)
    for col in ["Name","LocationName","Site","SiteAddress","MonthText","Day of Week"]:
        if col in fact.columns:
            fact[col] = fact[col].astype(str)
    # Normalize DOW capitalization
    if "Day of Week" in fact.columns:
        fact["Day of Week"] = fact["Day of Week"].str.title()
    return fact

# ------------------- Guard: files -------------------
if not Path(AGG_PATH).exists():
    st.error(f"Missing file: {AGG_PATH}")
    st.stop()
if not Path(FACT_PATH).exists():
    st.error(f"Missing file: {FACT_PATH} (expected sheet 'Fact')")
    st.stop()

df_agg = load_aggregated(AGG_PATH)
df_fact = load_fact(FACT_PATH, sheet="Fact")

# Map State/FT into time series by joining on Site
mapper = df_agg[["Site Contract ID","State/Federal Territory"]].drop_duplicates("Site Contract ID")
df_fact = df_fact.merge(mapper, left_on="Site", right_on="Site Contract ID", how="left")
df_fact["State/Federal Territory"] = df_fact["State/Federal Territory"].fillna("Unknown")

# ---------------- Title ----------------
st.title("KLOTH Malaysia Week 33 Dashboard")

# ======================================================
# Sidebar Filters (Time Series first -> used for KPIs)
# ======================================================
st.sidebar.header("Filters — Time Series")

ts_state_opts = sorted(df_fact["State/Federal Territory"].dropna().unique())
ts_state_sel = st.sidebar.multiselect("State / Federal Territory", ts_state_opts)

ts_week_opts = sorted(df_fact["Name"].dropna().unique()) if "Name" in df_fact.columns else []
ts_week_sel = st.sidebar.multiselect("Week (e.g., W01)", ts_week_opts)

ts_month_opts = sorted(df_fact["MonthText"].dropna().unique()) if "MonthText" in df_fact.columns else []
ts_month_sel = st.sidebar.multiselect("Month", ts_month_opts)

dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
ts_dow_opts = [d for d in dow_order if d in set(df_fact["Day of Week"])] if "Day of Week" in df_fact.columns else []
ts_dow_sel = st.sidebar.multiselect("Day of Week", ts_dow_opts)

date_min = pd.to_datetime(df_fact["Date_dt"].min()) if "Date_dt" in df_fact.columns else None
date_max = pd.to_datetime(df_fact["Date_dt"].max()) if "Date_dt" in df_fact.columns else None
if date_min is not None and date_max is not None:
    ts_date_range = st.sidebar.slider(
        "Date range",
        min_value=date_min.to_pydatetime(),
        max_value=date_max.to_pydatetime(),
        value=(date_min.to_pydatetime(), date_max.to_pydatetime())
    )
else:
    ts_date_range = None

# Apply Time Series filters
ts = df_fact.copy()
if ts_state_sel: ts = ts[ts["State/Federal Territory"].isin(ts_state_sel)]
if ts_week_sel and "Name" in ts.columns: ts = ts[ts["Name"].isin(ts_week_sel)]
if ts_month_sel and "MonthText" in ts.columns: ts = ts[ts["MonthText"].isin(ts_month_sel)]
if ts_dow_sel and "Day of Week" in ts.columns: ts = ts[ts["Day of Week"].isin(ts_dow_sel)]
if ts_date_range and "Date_dt" in ts.columns:
    start, end = pd.to_datetime(ts_date_range[0]), pd.to_datetime(ts_date_range[1])
    ts = ts[(ts["Date_dt"] >= start) & (ts["Date_dt"] <= end)]

# ---------------- KPI Bar (Time Series-based) ----------------
total_w = float(ts["WeightKG"].sum()) if not ts.empty else 0.0
days_count = ts["Date_dt"].nunique() if "Date_dt" in ts.columns else 0
sites_count = ts["Site"].nunique() if "Site" in ts.columns else 0
top_dow = (ts.groupby("Day of Week")["WeightKG"].sum().sort_values(ascending=False).index[0]
           if ("Day of Week" in ts.columns and not ts.empty) else "-")
peak_date = (ts.groupby("Date_dt")["WeightKG"].sum().sort_values(ascending=False).index[0].date().isoformat()
             if ("Date_dt" in ts.columns and not ts.empty) else "-")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Weight (KG)", f"{total_w:,.1f}")
k2.metric("# Active Days", f"{days_count:,}")
k3.metric("# Sites", f"{sites_count:,}")
k4.metric("Top Day of Week", top_dow)
k5.metric("Peak Date (by KG)", peak_date)

# ======================================================
# Additional Sidebar Filters — Aggregated (separate)
# ======================================================
st.sidebar.header("Filters — Aggregated")

ag_state_opts = sorted(df_agg["State/Federal Territory"].dropna().unique())
ag_state_sel = st.sidebar.multiselect("State / Federal Territory (Aggregated)", ag_state_opts)

ag_site_opts = sorted(df_agg["Site Contract ID"].dropna().unique())
ag_site_sel = st.sidebar.multiselect("Site Contract ID", ag_site_opts)

ag_name_q = st.sidebar.text_input("Search Location Name (contains)", value="")
ag_addr_q = st.sidebar.text_input("Search Site Address (contains)", value="")

acc_min = float(df_agg["Total Acceptable (KG)"].min())
acc_max = float(df_agg["Total Acceptable (KG)"].max())
ag_acc_range = st.sidebar.slider(
    "Acceptable (KG) range",
    min_value=0.0, max_value=max(acc_max, 1.0),
    value=(0.0, max(acc_max, 1.0))
)
top_n = st.sidebar.number_input("Top N (locations)", min_value=3, max_value=50, value=10, step=1)

# Apply Aggregated filters
ag = df_agg.copy()
if ag_state_sel: ag = ag[ag["State/Federal Territory"].isin(ag_state_sel)]
if ag_site_sel: ag = ag[ag["Site Contract ID"].isin(ag_site_sel)]
if ag_name_q.strip():
    q = ag_name_q.lower().strip()
    ag = ag[ag["Location Name"].str.lower().str.contains(q)]
if ag_addr_q.strip():
    q2 = ag_addr_q.lower().strip()
    ag = ag[ag["Site Address"].str.lower().str.contains(q2)]
ag = ag[ag["Total Acceptable (KG)"].between(ag_acc_range[0], ag_acc_range[1])]

# =======================
# Tabs
# =======================
tab_agg, tab_ts = st.tabs(["📦 Aggregated", "📈 Time Series"])

# ----------------------- Aggregated -----------------------
with tab_agg:
    st.subheader("Aggregated Views")

    # Bar: Acceptable by Location (Top N)
    bar_data = (
        ag.groupby("Location Name", as_index=False)["Total Acceptable (KG)"]
        .sum()
        .sort_values("Total Acceptable (KG)", ascending=False)
        .head(int(top_n))
    )
    fig_bar = px.bar(
        bar_data,
        x="Location Name",
        y="Total Acceptable (KG)",
        title=f"Acceptable Collection by Location (Top {int(top_n)})",
        text_auto=True,
        color="Total Acceptable (KG)",
        color_continuous_scale="Blues",
    )
    fig_bar.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig_bar, use_container_width=True)

    # Pie: Acceptable share by State/FT
    state_pie_data = (
        ag.groupby("State/Federal Territory", as_index=False)["Total Acceptable (KG)"]
        .sum()
        .sort_values("Total Acceptable (KG)", ascending=False)
    )
    fig_pie = px.pie(
        state_pie_data,
        values="Total Acceptable (KG)",
        names="State/Federal Territory",
        title="Share of Acceptable Collection by State / Federal Territory",
        hole=0.3,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("Show filtered table (Aggregated)"):
        st.dataframe(ag, use_container_width=True, height=380)
        st.download_button(
            "Download filtered CSV (Aggregated)",
            data=ag.to_csv(index=False).encode("utf-8"),
            file_name="aggregated_filtered.csv",
            mime="text/csv"
        )

# ----------------------- Time Series -----------------------
with tab_ts:
    st.subheader("Time Series Views")

    # A) Daily Weight
    daily = (ts.groupby("Date_dt", as_index=False)["WeightKG"].sum().sort_values("Date_dt"))
    if daily.empty:
        st.info("No data after filters.")
    else:
        fig_line = px.line(
            daily, x="Date_dt", y="WeightKG",
            markers=True, title="Daily Weight (KG)"
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # B) Total Weight by Day of Week
    dow = (ts.groupby("Day of Week", as_index=False)["WeightKG"].sum())
    dow["order"] = dow["Day of Week"].apply(lambda d: dow_order.index(d) if d in dow_order else 99)
    dow = dow.sort_values("order")
    fig_dow = px.bar(
        dow, x="Day of Week", y="WeightKG",
        title="Total Weight by Day of Week",
        text_auto=True, color="WeightKG", color_continuous_scale="Teal"
    )
    st.plotly_chart(fig_dow, use_container_width=True)

    # C) Heatmap: Week × Day of Week
    if "Name" in ts.columns and not ts.empty:
        heat = ts.pivot_table(index="Name", columns="Day of Week", values="WeightKG", aggfunc="sum", fill_value=0.0)
        ordered_cols = [d for d in dow_order if d in heat.columns]
        heat = heat.reindex(columns=ordered_cols)
        fig_heat = px.imshow(
            heat, labels=dict(x="Day of Week", y="Week", color="KG"),
            aspect="auto", title="Heatmap — Week × Day of Week (KG)"
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Heatmap unavailable (no Week data after filters).")
