"""
data_generator.py
Generates synthetic ad event data for local development and testing.

Produces realistic distributions: impression volumes, click-through rates,
conversion funnels, time-decay patterns, and late-arriving events.
"""
import argparse
import os
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()


def generate_campaigns(n_campaigns: int = 20) -> pd.DataFrame:
    """Generate campaign metadata."""
    advertisers = [fake.company() for _ in range(8)]
    campaigns = []
    for i in range(n_campaigns):
        campaigns.append({
            "campaign_id": f"camp_{i:04d}",
            "campaign_name": f"{fake.catch_phrase()} Campaign",
            "advertiser_name": np.random.choice(advertisers),
            "budget_usd": np.random.choice([10000, 25000, 50000, 100000, 250000]),
            "start_date": fake.date_between(start_date="-90d", end_date="-30d"),
            "status": np.random.choice(["active", "active", "paused", "completed"]),
        })
    return pd.DataFrame(campaigns)


def generate_impressions(
    campaigns: pd.DataFrame, n_days: int = 90, impressions_per_day: int = 50000
) -> pd.DataFrame:
    """Generate impression events with realistic patterns."""
    records = []
    campaign_ids = campaigns["campaign_id"].tolist()
    devices = ["mobile", "desktop", "ctv", "tablet"]
    device_weights = [0.45, 0.25, 0.20, 0.10]
    geos = ["US", "CA", "UK", "DE", "FR", "JP", "BR", "AU"]

    start_date = datetime.utcnow() - timedelta(days=n_days)

    for day_offset in range(n_days):
        date = start_date + timedelta(days=day_offset)
        # Weekday/weekend variation
        daily_volume = int(impressions_per_day * (1.0 if date.weekday() < 5 else 0.7))

        for _ in range(daily_volume):
            hour = np.random.choice(range(24), p=_hour_distribution())
            ts = date.replace(hour=hour, minute=np.random.randint(0, 60), second=np.random.randint(0, 60))

            records.append({
                "impression_id": str(uuid.uuid4()),
                "timestamp": ts,
                "campaign_id": np.random.choice(campaign_ids),
                "placement_id": f"placement_{np.random.randint(1, 50):03d}",
                "creative_id": f"creative_{np.random.randint(1, 100):04d}",
                "user_id": f"user_{np.random.randint(1, 200000):06d}",
                "user_segment_id": f"seg_{np.random.randint(1, 30):02d}",
                "device_type": np.random.choice(devices, p=device_weights),
                "geo_country": np.random.choice(geos, p=[0.40, 0.10, 0.12, 0.08, 0.08, 0.07, 0.08, 0.07]),
                "bid_price_usd": round(np.random.lognormal(mean=1.5, sigma=0.8), 4),
            })

    return pd.DataFrame(records)


def generate_conversions(
    impressions: pd.DataFrame, conversion_rate: float = 0.008
) -> pd.DataFrame:
    """Generate conversions attributed to impressions.

    Includes realistic patterns: time delays, multi-touch sequences,
    and late-arriving conversions.
    """
    # Sample impressions that led to conversions
    n_conversions = int(len(impressions) * conversion_rate)
    converting_impressions = impressions.sample(n=n_conversions)

    conversions = []
    for _, imp in converting_impressions.iterrows():
        # Conversion happens 0-30 days after impression (time-decay distribution)
        delay_hours = int(np.random.exponential(scale=48))  # Mean 48 hours
        delay_hours = min(delay_hours, 30 * 24)  # Cap at 30 days

        conv_time = imp["timestamp"] + timedelta(hours=delay_hours)
        conv_type = np.random.choice(
            ["purchase", "store_visit", "signup"],
            p=[0.30, 0.50, 0.20],
        )

        revenue = {
            "purchase": lambda: round(np.random.lognormal(mean=3.0, sigma=1.0), 2),
            "store_visit": lambda: round(np.random.uniform(5, 50), 2),
            "signup": lambda: 0.0,
        }

        conversions.append({
            "conversion_id": str(uuid.uuid4()),
            "timestamp": conv_time,
            "user_id": imp["user_id"],
            "conversion_type": conv_type,
            "revenue_usd": revenue[conv_type](),
            "attributed_impression_id": imp["impression_id"],
        })

    return pd.DataFrame(conversions)


def _hour_distribution():
    """Realistic ad impression distribution by hour (peaks during evening)."""
    weights = [
        0.01, 0.005, 0.003, 0.003, 0.005, 0.01,  # 0-5am (low)
        0.02, 0.035, 0.04, 0.045, 0.05, 0.055,     # 6-11am (morning ramp)
        0.06, 0.055, 0.05, 0.045, 0.05, 0.055,     # 12-5pm (afternoon)
        0.065, 0.07, 0.075, 0.07, 0.055, 0.03,     # 6-11pm (evening peak)
    ]
    total = sum(weights)
    return [w / total for w in weights]


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ad event data")
    parser.add_argument("--output", default="data/raw/", help="Output directory")
    parser.add_argument("--days", type=int, default=90, help="Days of data to generate")
    parser.add_argument("--daily-volume", type=int, default=10000, help="Impressions per day")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print(f"Generating {args.days} days of synthetic ad data...")

    campaigns = generate_campaigns(n_campaigns=20)
    campaigns.to_parquet(os.path.join(args.output, "campaigns.parquet"), index=False)
    print(f"  Campaigns: {len(campaigns):,}")

    impressions = generate_impressions(campaigns, n_days=args.days, impressions_per_day=args.daily_volume)
    impressions.to_parquet(os.path.join(args.output, "impressions.parquet"), index=False)
    print(f"  Impressions: {len(impressions):,}")

    conversions = generate_conversions(impressions)
    conversions.to_parquet(os.path.join(args.output, "conversions.parquet"), index=False)
    print(f"  Conversions: {len(conversions):,}")

    print(f"Data written to {args.output}")


if __name__ == "__main__":
    main()
