import pandas as pd
from datetime import datetime
import streamlit as st


def compute_time_and_pacing(df: pd.DataFrame, today: datetime) -> pd.DataFrame:
    df = df.copy()

    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])

    df["days_total"] = (df["end_date"] - df["start_date"]).dt.days
    df["days_elapsed"] = (today - df["start_date"]).dt.days
    df["days_remaining"] = (df["end_date"] - today).dt.days

    df["time_elapsed_pct"] = df["days_elapsed"] / df["days_total"]
    df["spend_pct"] = df["spend_to_date"] / df["budget_total"]

    df["pacing_ratio"] = df["spend_pct"] / df["time_elapsed_pct"]

    df["budget_remaining"] = df["budget_total"] - df["spend_to_date"]
    df["required_daily_spend"] = df["budget_remaining"] / df["days_remaining"]
    df["required_vs_actual_ratio"] = df["required_daily_spend"] / df["avg_daily_spend_7d"]

    return df


def enrich_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Text-derived flags from notes
    df["performance_decline"] = df["notes_main"].str.contains("declin", case=False).astype(int)
    df["premium_partner"] = df["notes_main"].str.contains("premium", case=False).astype(int)
    df["over_pacing_flag"] = df["notes_main"].str.contains("over pacing", case=False).astype(int)
    df["learning_phase"] = df["notes_main"].str.contains("learning", case=False).astype(int)

    return df


def compute_risk_score(
    row,
    w_delivery: float = 0.30,
    w_recovery: float = 0.25,
    w_time: float = 0.15,
    w_perf: float = 0.10,
    w_blocker: float = 0.20,
):
    # Delivery gap (under-pacing)
    delivery_gap = max(0, min(1, 1 - row["pacing_ratio"]))

    # How hard we need to push to catch up
    recovery_pressure = max(0, min(1, (row["required_vs_actual_ratio"] - 1) / 2))

    # Urgency based on time left
    time_urgency = max(0, min(1, 1 - (row["days_remaining"] / row["days_total"])))

    # Simple performance trend
    performance_risk = 1 if row.get("ctr_trend", "") == "down" else 0

    # Operational blockers
    blocker_score = min(
        row.get("creative_issue", 0) * 0.5
        + row.get("tracking_issue", 0) * 1.0
        + row.get("bid_issue", 0) * 0.5
        + row.get("legal_delay", 0) * 0.5
        + row.get("placement_issue", 0) * 0.5,
        1,
    )

    score = (
        w_delivery * delivery_gap
        + w_recovery * recovery_pressure
        + w_time * time_urgency
        + w_perf * performance_risk
        + w_blocker * blocker_score
    )

    # Premium partner boost
    if row.get("premium_partner", 0) == 1:
        score += 0.5

    # Learning phase dampener
    if row.get("learning_phase", 0) == 1 and row["days_elapsed"] < 7:
        score *= 0.7

    return round(score * 100, 1)


def map_risk_tier(score: float, high_thr: float = 70.0, med_thr: float = 30.0) -> str:
    if score >= high_thr:
        return "High"
    elif score >= med_thr:
        return "Medium"
    else:
        return "Low"


def explain_risk(row):
    reasons = []

    # Pacing
    if row["pacing_ratio"] < 0.9:
        reasons.append(f"spend is behind schedule (pacing {row['pacing_ratio']:.2f} vs 1.00 target).")
    elif row["pacing_ratio"] > 1.1:
        reasons.append(f"spend is ahead of schedule (pacing {row['pacing_ratio']:.2f}).")

    # Required daily spend vs actual
    if row["required_vs_actual_ratio"] > 1.5:
        reasons.append("needs to increase daily spend materially to hit budget.")
    elif row["required_vs_actual_ratio"] < 0.7:
        reasons.append("can reduce daily spend and still hit budget.")

    # Time pressure
    if row["days_remaining"] < 14:
        reasons.append(f"only {row['days_remaining']} days left in flight.")
    elif row.get("learning_phase", 0) == 1 and row["days_elapsed"] < 7:
        reasons.append("early in learning phase; performance may still stabilize.")

    # Blockers from operational flags
    blockers = []
    if row.get("tracking_issue", 0) == 1:
        blockers.append("tracking issues")
    if row.get("creative_issue", 0) == 1:
        blockers.append("creative problems")
    if row.get("bid_issue", 0) == 1:
        blockers.append("bid constraints")
    if row.get("legal_delay", 0) == 1:
        blockers.append("legal approvals")
    if row.get("placement_issue", 0) == 1:
        blockers.append("inventory/placement issues")
    if blockers:
        reasons.append("blocked by " + ", ".join(blockers) + ".")

    # Performance trend
    if row.get("ctr_trend", "") == "down":
        reasons.append("CTR trending down vs prior period.")

    # Relationship importance
    if row.get("premium_partner", 0) == 1:
        reasons.append("premium partner; under-delivery carries higher relationship risk.")

    if not reasons:
        return "Campaign is pacing close to plan with no major blockers detected."

    return " ".join(reasons)


def suggest_action(row):
    # Priority 1: unblock hard issues
    if row.get("tracking_issue", 0) == 1:
        return "Work with ad ops to resolve tracking issues today, then re-validate delivery and performance."
    if row.get("legal_delay", 0) == 1:
        return "Escalate with legal and the client to clear approvals or extend flight dates to protect delivery."

    # Priority 2: severe under-delivery pressure
    if row["pacing_ratio"] < 0.8 and row["required_vs_actual_ratio"] > 1.5:
        return "Increase bids or loosen targeting, and add high-volume placements to accelerate spend over the next week."

    # Priority 3: moderate under-pacing
    if row["pacing_ratio"] < 0.95:
        if row.get("ctr_trend", "") == "down" or row.get("creative_issue", 0) == 1:
            return "Refresh creatives and review messaging/format; keep bids and budget stable while testing new variants."
        if row.get("bid_issue", 0) == 1:
            return "Raise bid caps or switch to a less restrictive bid strategy to unlock additional inventory."
        return "Broaden targeting or add more inventory sources while monitoring performance daily."

    # Priority 4: over-pacing / efficiency
    if row["pacing_ratio"] > 1.1:
        return "Tighten audience or placement targeting and consider lowering bids to preserve efficiency."

    # Priority 5: performance-only concerns
    if row.get("ctr_trend", "") == "down":
        return "Test new creatives and adjust placements focusing on higher-engagement surfaces."

    # Default: stable campaigns
    return "No immediate intervention needed; monitor pacing and performance in the next check-in."


@st.cache_data
def load_data(csv_path: str) -> pd.DataFrame:
    today = datetime(2026, 3, 1)
    df = pd.read_csv(csv_path)
    df = compute_time_and_pacing(df, today)
    df = enrich_flags(df)
    return df


def main():
    st.title("HTS Media – Campaign Delivery Risk Prototype")
    st.write(
        """Lightweight internal view to quickly see which campaigns are at risk of
        under-delivery, why, and what to do next."""
    )

    csv_path = st.text_input(
        "Campaign CSV path",
        value="C:/Users/peili/Documents/AdsRanking/hts_media_campaigns.csv",
        help="Point this to the campaigns test dataset.",
    )

    try:
        df = load_data(csv_path)
    except Exception as e:
        st.error(f"Could not load data from `{csv_path}`. Error: {e}")
        st.stop()

    # Sidebar controls for risk model weights
    st.sidebar.header("Risk model weights")
    st.sidebar.caption(
        "Adjust how much each factor contributes to the overall risk score. "
        "Weights are normalized to sum to 1."
    )
    w_delivery_input = st.sidebar.number_input(
        "Delivery gap weight",
        min_value=0.0,
        max_value=1.0,
        value=0.30,
        step=0.05,
        help="Cumulative under- or over-spend versus a linear pacing plan.",
    )
    w_recovery_input = st.sidebar.number_input(
        "Recovery pressure weight",
        min_value=0.0,
        max_value=1.0,
        value=0.25,
        step=0.05,
        help="How aggressively daily spend must change to hit budget by the end date.",
    )
    w_time_input = st.sidebar.number_input(
        "Time urgency weight",
        min_value=0.0,
        max_value=1.0,
        value=0.15,
        step=0.05,
        help="How close the campaign is to its end date (less time left → higher urgency).",
    )
    w_perf_input = st.sidebar.number_input(
        "Performance trend weight",
        min_value=0.0,
        max_value=1.0,
        value=0.10,
        step=0.05,
        help="Recent CTR trend, especially when performance is declining.",
    )
    w_blocker_input = st.sidebar.number_input(
        "Operational blockers weight",
        min_value=0.0,
        max_value=1.0,
        value=0.20,
        step=0.05,
        help="Impact of hard blockers like tracking, creative, bid, legal, or placement issues.",
    )

    st.sidebar.header("Risk score tiers")
    st.sidebar.caption(
        "Define which risk scores are considered High, Medium, or Low. "
        "Defaults are High ≥ 70, Medium ≥ 30."
    )
    high_thr_input = st.sidebar.number_input(
        "High risk threshold",
        min_value=0.0,
        max_value=100.0,
        value=70.0,
        step=1.0,
        help="Scores at or above this value are labeled High risk.",
    )
    med_thr_input = st.sidebar.number_input(
        "Medium risk threshold",
        min_value=0.0,
        max_value=100.0,
        value=30.0,
        step=1.0,
        help="Scores at or above this value (and below High) are labeled Medium risk.",
    )

    # Ensure thresholds are in a sane order
    if med_thr_input >= high_thr_input:
        # Nudge medium just below high if user overlaps them
        high_thr = high_thr_input
        med_thr = max(0.0, high_thr_input - 1.0)
    else:
        high_thr = high_thr_input
        med_thr = med_thr_input

    # Normalize weights to sum to 1; if all zeros, fall back to defaults
    total_w = (
        w_delivery_input
        + w_recovery_input
        + w_time_input
        + w_perf_input
        + w_blocker_input
    )
    if total_w == 0:
        w_delivery, w_recovery, w_time, w_perf, w_blocker = 0.30, 0.25, 0.15, 0.10, 0.20
    else:
        w_delivery = w_delivery_input / total_w
        w_recovery = w_recovery_input / total_w
        w_time = w_time_input / total_w
        w_perf = w_perf_input / total_w
        w_blocker = w_blocker_input / total_w

    # Apply risk model with chosen weights
    df["risk_score"] = df.apply(
        lambda row: compute_risk_score(
            row,
            w_delivery=w_delivery,
            w_recovery=w_recovery,
            w_time=w_time,
            w_perf=w_perf,
            w_blocker=w_blocker,
        ),
        axis=1,
    )
    df["risk_level"] = df["risk_score"].apply(
        lambda s: map_risk_tier(s, high_thr=high_thr, med_thr=med_thr)
    )
    df["risk_reason"] = df.apply(explain_risk, axis=1)
    df["next_action"] = df.apply(suggest_action, axis=1)

    # Top summary: advertisers under-delivered / need attention (High or Medium risk)
    need_attention = df[df["risk_level"].isin(["High", "Medium"])]["advertiser"].unique().tolist()
    if need_attention:
        advertisers_text = ", ".join(need_attention)
        st.info(f"**Need attention (under-delivery risk):** {advertisers_text}")
    else:
        st.success("No campaigns currently flagged for under-delivery; all are Low risk.")

    st.subheader("Campaign overview")
    st.markdown(
        f"**Current risk score thresholds:** "
        f"High ≥ {high_thr:.0f}, Medium ≥ {med_thr:.0f}, Low < {med_thr:.0f}."
    )

    risk_filter = st.multiselect(
        "Filter by risk level",
        options=["High", "Medium", "Low"],
        default=["High", "Medium", "Low"],
    )

    view = df[df["risk_level"].isin(risk_filter)].copy()
    view = view.sort_values("risk_score", ascending=False)

    st.dataframe(
        view[
            [
                "campaign_id",
                "advertiser",
                "risk_level",
                "risk_score",
                "pacing_ratio",
                "required_vs_actual_ratio",
                "risk_reason",
                "next_action",
            ]
        ],
        use_container_width=True,
    )

    st.subheader("Campaign detail")
    if not view.empty:
        options = view["campaign_id"] + " – " + view["advertiser"]
        selection = st.selectbox("Select a campaign", options.tolist())
        selected_id = selection.split(" – ")[0]
        row = view[view["campaign_id"] == selected_id].iloc[0]

        st.markdown(f"**Advertiser:** {row['advertiser']}")
        st.markdown(f"**Risk level:** {row['risk_level']} (score {row['risk_score']:.1f})")
        st.markdown(f"**Pacing ratio:** {row['pacing_ratio']:.2f}")
        st.markdown(f"**Required vs actual daily spend:** {row['required_vs_actual_ratio']:.2f}×")

        st.markdown("**Why this is the current risk:**")
        st.write(row["risk_reason"])

        st.markdown("**Suggested next action:**")
        st.write(row["next_action"])
    else:
        st.info("No campaigns match the current filters.")


if __name__ == "__main__":
    main()

