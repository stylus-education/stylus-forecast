"""
Streamlit interactive revenue model for Stylus Education
=======================================================
Paste this file into a GitHub repo (e.g. stylus-forecast) and deploy on
https://share.streamlit.io – investors get a live playground with sliders.
"""

import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Stylus Forecast Model", layout="wide")
st.title("📈 Stylus Education – Interactive Revenue Forecast")

# ------------------------
# Assumption sliders
# ------------------------
st.sidebar.header("Adjust assumptions")

# UK school growth parameters
start_uk = st.sidebar.number_input("Starting UK schools (Q3 ’25)", 10, 1000, 100, step=10)
uk_growth_fast = st.sidebar.slider("Initial ‘hyper‑growth’ factor (× over first 2 years)", 1.0, 10.0, 5.0, 0.5)
uk_growth_taper = st.sidebar.slider("Annual growth after taper (‑%)", 0.0, 100.0, 20.0, 5.0) / 100

# MATs
trials_q = st.sidebar.number_input("MAT trials per quarter (after Q4 ’25)", 1, 100, 25)
conv_rate = st.sidebar.slider("MAT conversion rate", 0.0, 1.0, 0.70, 0.05)
mat_multiplier = st.sidebar.number_input("Average schools per MAT", 5, 25, 10)

# US districts
dist_add_q = st.sidebar.number_input("US districts per quarter (steady‑state)", 1, 50, 15)
dist_start_q = st.sidebar.selectbox("US launch quarter", ["2027Q1", "2027Q2", "2027Q3"], index=0)

# EAL
eal_start_q = st.sidebar.selectbox("EAL launch quarter", ["2028Q1", "2028Q2", "2028Q3"], index=0)
eal_start_learners = st.sidebar.number_input("EAL learners at launch (m)", 0.1, 10.0, 1.0, 0.1) * 1_000_000
eal_quarterly_multiplier = st.sidebar.slider("EAL learner growth per quarter (×)", 1.0, 4.0, 2.0, 0.25)

# Pricing (annual)
school_price_y1 = st.sidebar.number_input("School price Y1 (£k)", 1, 50, 5) * 1000
school_price_y2 = st.sidebar.number_input("School price Y2 (£k)", 1, 50, 10) * 1000
school_price_y3 = st.sidebar.number_input("School price Y3 (£k)", 1, 50, 15) * 1000

dist_price_y1 = st.sidebar.number_input("District price Y1 (£k)", 10, 500, 100) * 1000
dist_price_y2 = st.sidebar.number_input("District price Y2+ (£k)", 10, 500, 150) * 1000

eal_price_annual = 30  # fixed £/learner/year

# ------------------------
# Build forecast
# ------------------------
periods = pd.period_range("2025Q3", periods=12, freq="Q")
labels = periods.astype(str)

def build_uk_counts():
    counts = []
    prev = 0
    hyper_hc = [start_uk]
    # map back to half‑year growth logic: two years = 8 qtrs
    half_targets = [start_uk]
    # compute half‑year targets based on fast growth
    for i in range(1,6):
        if i <= 4:  # first 2 years (4 half‑years)
            target = int(round(start_uk * (uk_growth_fast ** i)))
        else:
            prev_target = half_targets[-1]
            target = int(round(prev_target * (1 + uk_growth_taper*2)))
        half_targets.append(target)
    # Interpolate each half‑year into 2 quarters (40/60 split)
    for h in range(len(half_targets)-1):
        base = half_targets[h]
        target = half_targets[h+1]
        delta = target - base
        counts.append(base + int(round(delta*0.4)))
        counts.append(target)
    return counts[:12]

uk_counts = build_uk_counts()

# UK revenue per quarter
ann_price_map = {2025: school_price_y1, 2026: school_price_y2*0.75 + school_price_y1*0.25,
                 2027: school_price_y2, 2028: school_price_y3}
school_price_q = [ann_price_map[p.year]/4 for p in periods]
uk_rev = [c*p for c,p in zip(uk_counts, school_price_q)]

# MATs
trial_schedule = [trials_q if idx>=1 else trials_q* (72/36) for idx in range(12)]
mat_conv = [0]*12
for i in range(2,12):
    mat_conv[i] = int(round(trial_schedule[i-2]*conv_rate))
mat_cum = pd.Series(mat_conv).cumsum()
mat_price_q = [ann_price_map[p.year]*mat_multiplier/4 for p in periods]
mat_rev = [c*p for c,p in zip(mat_cum, mat_price_q)]

# US districts
first_dist_idx = labels.tolist().index(dist_start_q)
base_adds = [0]*12
for i in range(first_dist_idx,12):
    base_adds[i] = dist_add_q
    if i==first_dist_idx:
        base_adds[i] = 1  # launch with 1

dist_cum = pd.Series(base_adds).cumsum()
ann_dist_price = {2025:0, 2026:0, 2027: dist_price_y1 if periods[0].year==2027 else dist_price_y1,
                  2028: dist_price_y2}
dist_price_q = [ (dist_price_y1 if p.year==2027 else dist_price_y2)/4 if p.year>=2027 else 0 for p in periods]
dist_rev = [c*p for c,p in zip(dist_cum, dist_price_q)]

# EAL learners
first_eal_idx = labels.tolist().index(eal_start_q)
eal_learners = [0]*12
if first_eal_idx < 12:
    learners = eal_start_learners
    for i in range(first_eal_idx, 12):
        eal_learners[i] = learners
        learners *= eal_quarterly_multiplier

eal_rev = [n*(eal_price_annual/4) for n in eal_learners]

# Totals DF
forecast = pd.DataFrame({
    "UK Schools": uk_rev,
    "MATs": mat_rev,
    "US Districts": dist_rev,
    "EAL": eal_rev
}, index=labels)
forecast["Total"] = forecast.sum(axis=1)

st.subheader("Quarterly Revenue (£)")
st.dataframe(forecast.style.format("{:.0f}"))

st.subheader("Revenue trajectory")
chart = (
    alt.Chart(forecast.reset_index().melt("index", var_name="Segment", value_name="Revenue"))
    .mark_line(point=True)
    .encode(
        x="index:N",
        y=alt.Y("Revenue:Q", title="£ per quarter", stack=None),
        color="Segment:N"
    )
    .properties(width=900, height=400)
)
st.altair_chart(chart, use_container_width=True)

st.caption("Adjust the sliders on the left to explore upside & downside scenarios. All figures are recognised revenue per quarter, not ARR.")
