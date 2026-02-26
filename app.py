import streamlit as st
import pandas as pd
import plotly.express as px

# STEP 2 — Page Config
st.set_page_config(layout="wide")
st.title("Nova Retail Data Dashboard")
st.subheader("Customer Behavior Lead Growth")


def _normalize_cols(cols):
    return [str(c).strip().lower().replace(" ", "_") for c in cols]


def _resolve_required_columns(df):
    """
    Dynamically match required logical fields to actual dataframe columns.
    Columns are already normalized (strip/lower/spaces->_).
    """
    colset = set(df.columns)

    aliases = {
        "idx": ["idx", "index", "row_id", "rowid"],
        "label": ["label", "segment", "customer_segment", "behavior_segment", "behaviour_segment"],
        "customerid": ["customerid", "customer_id", "custid", "cust_id", "customer"],
        "transactionid": ["transactionid", "transaction_id", "txnid", "txn_id", "purchaseid", "purchase_id"],
        "transactiondate": ["transactiondate", "transaction_date", "date", "purchase_date", "order_date", "transaction_dt"],
        "productcategory": ["productcategory", "product_category", "category", "product_cat"],
        "purchaseamount": ["purchaseamount", "purchase_amount", "amount", "sales", "revenue", "value", "transaction_amount"],
        "customeragegroup": ["customeragegroup", "customer_age_group", "agegroup", "age_group", "age_band"],
        "customergender": ["customergender", "customer_gender", "gender", "sex"],
        "customerregion": ["customerregion", "customer_region", "region", "geo_region", "location_region"],
        "customersatisfaction": ["customersatisfaction", "customer_satisfaction", "satisfaction", "rating", "csat"],
        "retailchannel": ["retailchannel", "retail_channel", "channel", "sales_channel", "purchase_channel"],
    }

    resolved = {}
    for logical, candidates in aliases.items():
        found = None
        for c in candidates:
            if c in colset:
                found = c
                break
        if found is not None:
            resolved[logical] = found

    missing = [k for k in aliases.keys() if k not in resolved]
    return resolved, missing


@st.cache_data(show_spinner=False)
def load_data():
    # STEP 3 — Load Data
    try:
        df = pd.read_csv("NR_dataset.csv")
    except FileNotFoundError:
        # Streamlit Cloud uses repo root; local grading may mount at /mnt/data
        try:
            df = pd.read_csv("/mnt/data/NR_dataset.csv")
        except FileNotFoundError:
            st.error("Dataset file not found in repository.")
            return None

    df.columns = _normalize_cols(df.columns)

    resolved, missing = _resolve_required_columns(df)
    if missing:
        st.error(
            "Required logical fields are missing: "
            + ", ".join(missing)
            + ". Please verify the dataset headers."
        )
        st.write(df.columns)
        return None

    # Rename to standard logical names (keeps only required names standardized; does not fabricate columns)
    rename_map = {resolved[k]: k for k in resolved}
    df = df.rename(columns=rename_map)

    # Convert TransactionDate to datetime (non-parsable -> NaT)
    df["transactiondate"] = pd.to_datetime(df["transactiondate"], errors="coerce")

    # Convert label to numeric (Promising=4, Growth=3, Stable=2, Decline=1)
    label_map = {"promising": 4, "growth": 3, "stable": 2, "decline": 1}
    if df["label"].dtype == object:
        df["label"] = df["label"].astype(str).str.strip().str.lower().map(label_map)
    else:
        df["label"] = pd.to_numeric(df["label"], errors="coerce")

    # Convert RetailChannel to numeric (Online=1, Physical Store=2)
    channel_map = {
        "online": 1,
        "physical store": 2,
        "physical_store": 2,
        "store": 2,
        "in_store": 2,
        "instore": 2,
    }
    if df["retailchannel"].dtype == object:
        ch = df["retailchannel"].astype(str).str.strip().str.lower()
        ch = ch.replace({"physical store": "physical_store", "in store": "in_store"})
        df["retailchannel"] = ch.map(channel_map)
    else:
        df["retailchannel"] = pd.to_numeric(df["retailchannel"], errors="coerce")

    # Ensure numeric types where appropriate
    df["purchaseamount"] = pd.to_numeric(df["purchaseamount"], errors="coerce")
    df["customersatisfaction"] = pd.to_numeric(df["customersatisfaction"], errors="coerce")

    # Drop any null data
    df = df.dropna().copy()

    return df


df = load_data()
if df is None:
    st.stop()

# Human-friendly display fields for filters
label_display_map = {4: "Promising", 3: "Growth", 2: "Stable", 1: "Decline"}
channel_display_map = {1: "Online", 2: "Physical Store"}

df_display = df.copy()
df_display["label_display"] = df_display["label"].astype(int).map(label_display_map)
df_display["channel_display"] = df_display["retailchannel"].astype(int).map(channel_display_map)

# STEP 4 — Filtering Logic
with st.sidebar:
    st.header("Filters")

    label_options = ["All"] + [label_display_map[v] for v in sorted(label_display_map.keys(), reverse=True)]
    selected_labels = st.multiselect("Customer Segment (Label)", options=label_options, default=["All"])

    categories = sorted(df_display["productcategory"].astype(str).unique().tolist())
    category_options = ["All"] + categories  # Sort ProductCategory alphabetically
    selected_categories = st.multiselect("Product Category", options=category_options, default=["All"])

    regions = sorted(df_display["customerregion"].astype(str).unique().tolist())
    region_options = ["All"] + regions
    selected_regions = st.multiselect("Customer Region", options=region_options, default=["All"])

    genders = sorted(df_display["customergender"].astype(str).unique().tolist())
    gender_options = ["All"] + genders
    selected_genders = st.multiselect("Customer Gender", options=gender_options, default=["All"])

    ages = sorted(df_display["customeragegroup"].astype(str).unique().tolist())
    age_options = ["All"] + ages
    selected_ages = st.multiselect("Customer Age Group", options=age_options, default=["All"])

    channel_options = ["All", "Online", "Physical Store"]
    selected_channels = st.multiselect("Retail Channel", options=channel_options, default=["All"])

    date_min = df_display["transactiondate"].min()
    date_max = df_display["transactiondate"].max()
    date_range = st.date_input(
        "Transaction Date Range",
        value=(date_min.date(), date_max.date()),
        min_value=date_min.date(),
        max_value=date_max.date(),
    )

df_filt = df_display.copy()

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df_filt = df_filt[(df_filt["transactiondate"] >= start_date) & (df_filt["transactiondate"] <= end_date)]

if "All" not in selected_labels:
    df_filt = df_filt[df_filt["label_display"].isin(selected_labels)]

if "All" not in selected_categories:
    df_filt = df_filt[df_filt["productcategory"].isin(selected_categories)]

if "All" not in selected_regions:
    df_filt = df_filt[df_filt["customerregion"].isin(selected_regions)]

if "All" not in selected_genders:
    df_filt = df_filt[df_filt["customergender"].isin(selected_genders)]

if "All" not in selected_ages:
    df_filt = df_filt[df_filt["customeragegroup"].isin(selected_ages)]

if "All" not in selected_channels:
    df_filt = df_filt[df_filt["channel_display"].isin(selected_channels)]

# STEP 6 — Edge Case Handling
if df_filt.empty:
    st.warning("No data matches the selected filters. Please broaden your selections.")
    st.stop()

# KPIs
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
total_revenue = float(df_filt["purchaseamount"].sum())
num_txns = int(df_filt["transactionid"].nunique())
num_customers = int(df_filt["customerid"].nunique())
avg_satisfaction = float(df_filt["customersatisfaction"].mean())

kpi1.metric("Total Revenue", f"${total_revenue:,.2f}")
kpi2.metric("Unique Transactions", f"{num_txns:,}")
kpi3.metric("Unique Customers", f"{num_customers:,}")
kpi4.metric("Avg Satisfaction", f"{avg_satisfaction:.2f} / 5")

# Main Chart Controls
c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
with c1:
    chart_type = st.selectbox(
        "Chart",
        options=[
            "Revenue by Product Category",
            "Revenue Trend Over Time",
            "Revenue by Customer Segment",
            "Satisfaction by Segment",
            "Revenue by Region",
            "Channel Mix (Revenue)",
        ],
    )
with c2:
    agg = st.selectbox("Aggregation", options=["Sum", "Average"], index=0)
with c3:
    top_n = st.slider("Top N Product Categories (where applicable)", min_value=3, max_value=25, value=10)

# Build Chart Data
def _agg_series(df_in, group_cols, value_col, agg_choice):
    if agg_choice == "Average":
        return df_in.groupby(group_cols, as_index=False)[value_col].mean()
    return df_in.groupby(group_cols, as_index=False)[value_col].sum()

chart_df = df_filt.copy()

if chart_type == "Revenue by Product Category":
    tmp = _agg_series(chart_df, ["productcategory"], "purchaseamount", agg)
    tmp = tmp.sort_values("purchaseamount", ascending=False).head(int(top_n))
    fig = px.bar(tmp, x="productcategory", y="purchaseamount", title="Purchase Amount by Product Category")
    fig.update_layout(xaxis_title="Product Category", yaxis_title="Purchase Amount (USD)")

elif chart_type == "Revenue Trend Over Time":
    tmp = chart_df.copy()
    tmp["date"] = tmp["transactiondate"].dt.to_period("D").dt.to_timestamp()
    tmp = _agg_series(tmp, ["date"], "purchaseamount", agg)
    fig = px.line(tmp, x="date", y="purchaseamount", title="Purchase Amount Trend Over Time")
    fig.update_layout(xaxis_title="Date", yaxis_title="Purchase Amount (USD)")

elif chart_type == "Revenue by Customer Segment":
    tmp = _agg_series(chart_df, ["label_display"], "purchaseamount", agg)
    order = ["Promising", "Growth", "Stable", "Decline"]
    tmp["label_display"] = pd.Categorical(tmp["label_display"], categories=order, ordered=True)
    tmp = tmp.sort_values("label_display")
    fig = px.bar(tmp, x="label_display", y="purchaseamount", title="Purchase Amount by Customer Segment")
    fig.update_layout(xaxis_title="Customer Segment", yaxis_title="Purchase Amount (USD)")

elif chart_type == "Satisfaction by Segment":
    tmp = chart_df.groupby("label_display", as_index=False)["customersatisfaction"].mean()
    order = ["Promising", "Growth", "Stable", "Decline"]
    tmp["label_display"] = pd.Categorical(tmp["label_display"], categories=order, ordered=True)
    tmp = tmp.sort_values("label_display")
    fig = px.bar(tmp, x="label_display", y="customersatisfaction", title="Average Satisfaction by Segment")
    fig.update_layout(xaxis_title="Customer Segment", yaxis_title="Avg Satisfaction (1-5)")

elif chart_type == "Revenue by Region":
    tmp = _agg_series(chart_df, ["customerregion"], "purchaseamount", agg)
    tmp = tmp.sort_values("purchaseamount", ascending=False)
    fig = px.bar(tmp, x="customerregion", y="purchaseamount", title="Purchase Amount by Region")
    fig.update_layout(xaxis_title="Region", yaxis_title="Purchase Amount (USD)")

else:  # Channel Mix (Revenue)
    tmp = _agg_series(chart_df, ["channel_display"], "purchaseamount", "Sum")
    fig = px.pie(tmp, names="channel_display", values="purchaseamount", title="Revenue Mix by Retail Channel")

st.plotly_chart(fig, use_container_width=True)

# Insights Panel (streamlit elements only)
ins1, ins2, ins3 = st.columns(3)
with ins1:
    seg_rev = df_filt.groupby("label_display")["purchaseamount"].sum().sort_values(ascending=False)
    top_seg = seg_rev.index[0] if not seg_rev.empty else "N/A"
    st.metric("Top Revenue Segment", f"{top_seg}")
with ins2:
    cat_rev = df_filt.groupby("productcategory")["purchaseamount"].sum().sort_values(ascending=False)
    top_cat = cat_rev.index[0] if not cat_rev.empty else "N/A"
    st.metric("Top Revenue Category", f"{top_cat}")
with ins3:
    decline_share = 0.0
    if "Decline" in df_filt["label_display"].values:
        decline_rev = df_filt.loc[df_filt["label_display"] == "Decline", "purchaseamount"].sum()
        decline_share = float(decline_rev / total_revenue) if total_revenue > 0 else 0.0
    st.metric("Decline Segment Revenue Share", f"{decline_share:.1%}")

# STEP 5 — Show Filtered Table (below the chart)
st.subheader("Filtered Transactions")

# Clean display: remove index, keep normalized/standard columns plus display helpers
display_cols = [
    "idx",
    "label_display",
    "customerid",
    "transactionid",
    "transactiondate",
    "productcategory",
    "purchaseamount",
    "customeragegroup",
    "customergender",
    "customerregion",
    "customersatisfaction",
    "channel_display",
]

# Only keep columns that exist (no fabricated columns)
display_cols = [c for c in display_cols if c in df_filt.columns]

table_df = df_filt[display_cols].copy()
table_df = table_df.sort_values("transactiondate", ascending=False).reset_index(drop=True)

try:
    st.dataframe(table_df, use_container_width=True, hide_index=True)
except TypeError:
    st.dataframe(table_df, use_container_width=True)
