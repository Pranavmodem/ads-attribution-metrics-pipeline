"""
data_generator.py
Synthetic ad event data with a known ground truth.

Each simulated user gets a journey of ad impressions. Upper-funnel channels
(Display, Video) tend to come early in a journey and lower-funnel channels
(Paid Search, Email) late. Whether a user converts depends only on which
channels reached them and how often, through a logistic model whose
coefficients are in CHANNELS. Because those coefficients are known,
`true_channel_credit` can compute each channel's real share of incremental
conversions, and every attribution model can be scored against it.

That setup reproduces the classic failure of last-touch attribution: Paid Search
sits at the end of most journeys, so it collects the credit, while the Video and
Display impressions that actually moved users get little.

The generator also plants defects the pipeline has to handle: duplicate
impression rows, re-sent conversions, and conversions that arrive days late.

Usage:
    python -m src.utils.data_generator --out data/raw --days 90 --daily-volume 2000
"""
import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Channel:
    funnel: float  # 0 = awareness, 1 = intent; where in a journey it tends to appear
    share: float   # share of impression volume
    ctr: float     # click-through rate
    cpm: float     # cost per 1,000 impressions, USD
    effect: float  # true lift in conversion log-odds once a user is saturated


CHANNELS = {
    "Display":     Channel(funnel=0.05, share=0.20, ctr=0.004, cpm=8.0,  effect=0.65),
    "Video":       Channel(funnel=0.15, share=0.12, ctr=0.010, cpm=28.0, effect=0.95),
    "Social":      Channel(funnel=0.35, share=0.21, ctr=0.012, cpm=12.0, effect=0.45),
    "Native":      Channel(funnel=0.45, share=0.08, ctr=0.008, cpm=8.0,  effect=0.10),
    "Affiliate":   Channel(funnel=0.70, share=0.06, ctr=0.015, cpm=14.0, effect=0.20),
    "Email":       Channel(funnel=0.85, share=0.10, ctr=0.025, cpm=4.0,  effect=0.30),
    "Paid Search": Channel(funnel=0.97, share=0.23, ctr=0.035, cpm=65.0, effect=0.25),
}
CHANNEL_NAMES = list(CHANNELS)

BASE_LOGIT = -4.7          # conversion log-odds with no advertising (~0.9% organic)
SEARCH_SYNERGY = 0.35      # extra lift when Paid Search follows Display or Video
UPPER_FUNNEL = ("Display", "Video")

ADVERTISERS = [
    "Northwind Outfitters", "Harbor & Pine", "Cedar Coffee Co.", "Brightline Fitness",
    "Mosaic Home", "Kettle & Crumb", "Summit Auto Care", "Lumen Eyewear",
]
THEMES = [
    "Spring Launch", "Back to School", "Holiday Push", "Always-On", "Loyalty",
    "New Store Openings", "Retargeting", "Brand Awareness", "Clearance", "Weekend Deals",
]
DEVICES, DEVICE_P = ["mobile", "desktop", "ctv", "tablet"], [0.52, 0.28, 0.12, 0.08]
GEOS, GEO_P = ["US", "CA", "UK", "DE", "FR", "AU"], [0.55, 0.10, 0.12, 0.08, 0.08, 0.07]
HOUR_WEIGHTS = np.array([
    0.010, 0.006, 0.004, 0.004, 0.006, 0.012, 0.022, 0.036, 0.042, 0.046, 0.050, 0.054,
    0.058, 0.055, 0.050, 0.047, 0.051, 0.057, 0.066, 0.072, 0.076, 0.069, 0.050, 0.030,
])


def true_logit(counts: np.ndarray) -> np.ndarray:
    """Ground-truth conversion log-odds from a (users, channels) impression-count matrix.

    Each channel's lift saturates with frequency: one impression gives half the
    effect, two give three quarters, and so on.
    """
    effects = np.array([CHANNELS[c].effect for c in CHANNEL_NAMES])
    logit = BASE_LOGIT + (1 - 0.5 ** counts) @ effects
    upper = counts[:, [CHANNEL_NAMES.index(c) for c in UPPER_FUNNEL]].sum(axis=1) > 0
    search = counts[:, CHANNEL_NAMES.index("Paid Search")] > 0
    return logit + SEARCH_SYNERGY * (upper & search)


def exposure_counts(impressions: pd.DataFrame) -> pd.DataFrame:
    """Impressions per user per channel, deduplicated on impression_id."""
    imps = impressions.drop_duplicates("impression_id")
    return (
        pd.crosstab(imps["user_id"], imps["channel"])
        .reindex(columns=CHANNEL_NAMES, fill_value=0)
    )


def true_channel_credit(impressions: pd.DataFrame) -> pd.DataFrame:
    """Each channel's true share of incremental conversions.

    Computed from the generator's own coefficients: exact per-user Shapley
    values of the true conversion model, summed over every user reached.
    """
    from src.metrics.advanced_attribution import exposure_shapley

    counts = exposure_counts(impressions).to_numpy(dtype=float)
    lift = exposure_shapley(counts, true_logit)
    return pd.DataFrame({
        "channel": CHANNEL_NAMES,
        "incremental_conversions": lift,
        "credit": lift / lift.sum(),
    })


def generate_campaigns(rng: np.random.Generator, n_campaigns: int = 20) -> pd.DataFrame:
    """Campaign metadata. Every channel gets at least two campaigns."""
    channels = CHANNEL_NAMES * 2
    extra = rng.choice(CHANNEL_NAMES, n_campaigns - len(channels),
                       p=[CHANNELS[c].share for c in CHANNEL_NAMES])
    channels = channels + list(extra)
    rng.shuffle(channels)
    rows = []
    for i, channel in enumerate(channels):
        rows.append({
            "campaign_id": f"camp_{i:04d}",
            "campaign_name": f"{rng.choice(ADVERTISERS)} · {rng.choice(THEMES)}",
            "advertiser_name": None,
            "channel": channel,
            "budget_usd": int(rng.choice([10_000, 25_000, 50_000, 100_000])),
            "status": rng.choice(["active", "active", "paused", "completed"]),
            "cpm_multiplier": round(float(rng.lognormal(0, 0.18)), 3),
            "ctr_multiplier": round(float(rng.lognormal(0, 0.25)), 3),
        })
    campaigns = pd.DataFrame(rows)
    campaigns["advertiser_name"] = campaigns["campaign_name"].str.split(" · ").str[0]
    return campaigns


def _simulate_impressions(rng, campaigns, start, n_days, daily_volume, mean_touches=6.0):
    """User journeys -> impression rows, ordered within each user by time."""
    target = n_days * daily_volume
    n_users = int(target / mean_touches / 0.8)  # ~20% of touches fall outside the window
    touches = rng.geometric(1 / mean_touches, n_users)
    user = np.repeat(np.arange(n_users), touches)
    first_idx = np.cumsum(touches) - touches
    pos = np.arange(touches.sum()) - np.repeat(first_idx, touches)
    # Position in the whole journey (0 = first touch, 1 = last), fixed before the
    # export window cuts journeys off, so a cut journey does not end on intent channels.
    n_rep = np.repeat(touches, touches)
    frac = np.where(n_rep > 1, pos / np.maximum(n_rep - 1, 1), rng.random(len(pos)))

    gaps = rng.exponential(1.6, len(user))
    gaps[pos == 0] = 0.0
    csum = np.cumsum(gaps)
    offset = csum - np.repeat(csum[first_idx], touches)
    day = np.repeat(rng.uniform(-14, n_days, n_users), touches) + offset
    # When each journey really ends, including touches after the export cutoff.
    # Users still mid-journey at the cutoff have not converted yet.
    journey_end = pd.Timestamp(start) + pd.to_timedelta(day[np.cumsum(touches) - 1] * 86400, unit="s")

    keep = (day >= 0) & (day < n_days)
    user, frac, day = user[keep], frac[keep], np.floor(day[keep]).astype(int)
    hour = rng.choice(24, len(day), p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    seconds = day * 86400 + hour * 3600 + rng.integers(0, 3600, len(day))
    ts = pd.Timestamp(start) + pd.to_timedelta(seconds, unit="s")

    weekend = ts.dayofweek >= 5
    keep = ~(weekend & (rng.random(len(ts)) < 0.3))
    df = pd.DataFrame({"user": user[keep], "timestamp": ts[keep], "frac": frac[keep]})
    df = df.sort_values(["user", "timestamp"], kind="mergesort").reset_index(drop=True)

    # Funnel position decides the channel: early touches lean awareness, late ones intent.
    frac = df["frac"].to_numpy()
    funnel = np.array([CHANNELS[c].funnel for c in CHANNEL_NAMES])
    share = np.array([CHANNELS[c].share for c in CHANNEL_NAMES])
    weights = share * np.exp(-((frac[:, None] - funnel) ** 2) / (2 * 0.22 ** 2))
    cum = np.cumsum(weights / weights.sum(axis=1, keepdims=True), axis=1)
    ch_idx = (rng.random(len(df))[:, None] > cum).sum(axis=1).clip(0, len(CHANNEL_NAMES) - 1)
    df["channel"] = np.array(CHANNEL_NAMES)[ch_idx]

    # Campaign within the channel, then campaign-level price and creative.
    campaign_ids = np.empty(len(df), dtype=object)
    for channel, ids in campaigns.groupby("channel")["campaign_id"]:
        rows = (df["channel"] == channel).to_numpy()
        campaign_ids[rows] = rng.choice(ids.to_numpy(), rows.sum())
    df["campaign_id"] = campaign_ids
    camp = campaigns.set_index("campaign_id")
    cpm = df["channel"].map({c: CHANNELS[c].cpm for c in CHANNEL_NAMES}).to_numpy()
    cpm = cpm * df["campaign_id"].map(camp["cpm_multiplier"]).to_numpy()
    df["bid_price_usd"] = np.round(cpm * rng.lognormal(0, 0.3, len(df)), 4)
    df["creative_id"] = df["campaign_id"] + "_cr" + rng.integers(1, 5, len(df)).astype(str)
    df["placement_id"] = "pl_" + pd.Series(rng.integers(1, 40, len(df))).map("{:03d}".format)

    users = pd.DataFrame({
        "user": np.arange(n_users),
        "user_id": [f"u{i:06d}" for i in range(n_users)],
        "user_segment_id": [f"seg_{i:02d}" for i in rng.integers(1, 25, n_users)],
        "device_type": rng.choice(DEVICES, n_users, p=DEVICE_P),
        "geo_country": rng.choice(GEOS, n_users, p=GEO_P),
    })
    df = df.merge(users, on="user", how="left")
    df = df.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    df["impression_id"] = [f"imp_{i:08d}" for i in range(len(df))]
    journey_end = pd.Series(journey_end, index=users["user_id"], name="journey_end")
    return journey_end, df[[
        "impression_id", "timestamp", "campaign_id", "channel", "placement_id",
        "creative_id", "user_id", "user_segment_id", "device_type", "geo_country",
        "bid_price_usd",
    ]]


def _simulate_clicks(rng, impressions, campaigns):
    ctr = impressions["channel"].map({c: CHANNELS[c].ctr for c in CHANNEL_NAMES}).to_numpy()
    ctr = ctr * impressions["campaign_id"].map(campaigns.set_index("campaign_id")["ctr_multiplier"]).to_numpy()
    clicked = impressions[rng.random(len(impressions)) < ctr]
    clicks = clicked[["impression_id", "user_id", "campaign_id", "channel"]].copy()
    clicks["timestamp"] = clicked["timestamp"] + pd.to_timedelta(rng.integers(2, 45, len(clicked)), unit="s")
    clicks.insert(0, "click_id", [f"clk_{i:07d}" for i in range(len(clicks))])
    return clicks.reset_index(drop=True)


def _simulate_conversions(rng, impressions, journey_end, end):
    """Each user converts with the true model's probability, after their journey ends.

    A journey still running at the export cutoff ends later, so its conversion
    (if any) falls after the cutoff and is not in the export, as in real data.
    """
    counts = exposure_counts(impressions)
    p = 1 / (1 + np.exp(-true_logit(counts.to_numpy(dtype=float))))
    converts = rng.random(len(p)) < p
    observed_last = impressions.groupby("user_id")["timestamp"].max().reindex(counts.index)
    last_touch = np.maximum(observed_last, journey_end.reindex(counts.index))

    users = counts.index[converts]
    delay_h = np.minimum(rng.exponential(20, len(users)), 240)
    ts = last_touch[converts].to_numpy() + pd.to_timedelta(delay_h, unit="h").to_numpy()
    conv = pd.DataFrame({"user_id": users, "timestamp": ts})
    conv = conv[conv["timestamp"] < end].sort_values("timestamp").reset_index(drop=True)
    conv["timestamp"] = conv["timestamp"].dt.floor("s")

    kind = rng.choice(["purchase", "store_visit", "signup"], len(conv), p=[0.35, 0.45, 0.20])
    revenue = np.select(
        [kind == "purchase", kind == "store_visit"],
        [rng.lognormal(np.log(30), 0.7, len(conv)), rng.uniform(5, 18, len(conv))],
        0.0,
    )
    conv.insert(0, "conversion_id", [f"cnv_{i:06d}" for i in range(len(conv))])
    conv["conversion_type"] = kind
    conv["revenue_usd"] = np.round(revenue, 2)

    # Most events land within minutes; 4% arrive two to five days late.
    lag = rng.exponential(600, len(conv))
    late = rng.random(len(conv)) < 0.04
    lag[late] = rng.uniform(2 * 86400, 5 * 86400, late.sum())
    conv["received_at"] = conv["timestamp"] + pd.to_timedelta(lag.astype(int), unit="s")
    return conv


def _inject_duplicates(rng, df, rate, shift_col=None):
    """Re-send a small share of rows unchanged, as upstream retries do."""
    dups = df.sample(frac=rate, random_state=int(rng.integers(1 << 31)))
    if shift_col:
        dups = dups.assign(**{shift_col: dups[shift_col] + pd.Timedelta(minutes=7)})
    return pd.concat([df, dups]).sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def generate_dataset(
    n_days: int = 90,
    daily_volume: int = 2000,
    seed: int = 42,
    end: datetime = None,
    n_campaigns: int = 20,
) -> dict:
    """Generate campaigns, impressions, clicks, and conversions.

    Returns a dict of DataFrames. Timestamps are naive UTC.
    """
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(end or datetime.utcnow()).floor("h")
    start = (end - timedelta(days=n_days)).normalize()

    campaigns = generate_campaigns(rng, n_campaigns)
    journey_end, impressions = _simulate_impressions(rng, campaigns, start, n_days, daily_volume)
    impressions = impressions[impressions["timestamp"] < end].reset_index(drop=True)
    clicks = _simulate_clicks(rng, impressions, campaigns)
    conversions = _simulate_conversions(rng, impressions, journey_end, end)

    conversions = _inject_duplicates(rng, conversions, 0.005, shift_col="received_at")
    return {
        "campaigns": campaigns.drop(columns=["cpm_multiplier", "ctr_multiplier"]),
        "impressions": _inject_duplicates(rng, impressions, 0.002),
        "clicks": clicks[clicks["timestamp"] < end].reset_index(drop=True),
        # A late conversion that has not arrived by the export time is not in the export.
        "conversions": conversions[conversions["received_at"] < end].reset_index(drop=True),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ad event data")
    parser.add_argument("--out", "--output", dest="out", default="data/raw/", help="Output directory")
    parser.add_argument("--days", type=int, default=90, help="Days of data")
    parser.add_argument("--daily-volume", type=int, default=2000, help="Impressions per day")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    data = generate_dataset(n_days=args.days, daily_volume=args.daily_volume, seed=args.seed)
    for name, df in data.items():
        df.to_parquet(os.path.join(args.out, f"{name}.parquet"), index=False)
        print(f"  {name:<12} {len(df):>9,} rows")

    imps = data["impressions"].drop_duplicates("impression_id")
    conv = data["conversions"].drop_duplicates("conversion_id")
    spend = imps["bid_price_usd"].sum() / 1000
    print(f"\nWrote {args.out}")
    print(f"  CTR            {len(data['clicks']) / len(imps):.2%}")
    print(f"  Users reached  {imps['user_id'].nunique():,}  "
          f"(conversion rate {conv['user_id'].nunique() / imps['user_id'].nunique():.2%})")
    print(f"  Spend ${spend:,.0f}  revenue ${conv['revenue_usd'].sum():,.0f}  "
          f"ROAS {conv['revenue_usd'].sum() / spend:.2f}x")


if __name__ == "__main__":
    main()
