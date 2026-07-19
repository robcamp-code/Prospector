#!/usr/bin/env python3
"""Load uszips.csv data into PostgreSQL."""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_settings
from src.models.uszips import USZip

# Create sync engine and session for this script
settings = get_settings()
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def load_uszips(csv_path: str = "uszips.csv") -> int:
    """Load ZIP code data from CSV into database.

    Args:
        csv_path: Path to the uszips.csv file

    Returns:
        Number of rows loaded
    """
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path, dtype=str)

    # Convert boolean columns
    bool_cols = ["zcta", "imprecise", "military", "cbsa_metro"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map({"TRUE": True, "FALSE": False, "True": True, "False": False})

    # Convert numeric columns
    numeric_cols = [
        "lat", "lng", "population", "density",
        "age_median", "age_under_10", "age_10_to_19", "age_20s", "age_30s",
        "age_40s", "age_50s", "age_60s", "age_70s", "age_over_80", "age_over_65",
        "age_18_to_24", "age_over_18", "male", "female", "married", "divorced",
        "never_married", "widowed", "family_size", "family_dual_income",
        "income_household_median", "income_household_under_5", "income_household_5_to_10",
        "income_household_10_to_15", "income_household_15_to_20", "income_household_20_to_25",
        "income_household_25_to_35", "income_household_35_to_50", "income_household_50_to_75",
        "income_household_75_to_100", "income_household_100_to_150", "income_household_150_over",
        "income_household_six_figure", "income_individual_median", "home_ownership",
        "housing_units", "home_value", "rent_median", "rent_burden",
        "education_less_highschool", "education_highschool", "education_some_college",
        "education_bachelors", "education_graduate", "education_college_or_above",
        "education_stem_degree", "labor_force_participation", "unemployment_rate",
        "self_employed", "farmer", "race_white", "race_black", "race_asian",
        "race_native", "race_pacific", "race_other", "race_multiple", "hispanic",
        "disabled", "poverty", "limited_english", "commute_time", "health_uninsured",
        "veteran", "charitable_givers",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Replace empty strings with None
    df = df.replace("", None)

    print(f"Loaded {len(df)} rows from CSV")

    # Clear existing data
    with SessionLocal() as db:
        db.query(USZip).delete()
        db.commit()
        print("Cleared existing uszips data")

    # Insert in batches
    batch_size = 1000
    total_inserted = 0

    with SessionLocal() as db:
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]
            records = batch.to_dict(orient="records")

            for record in records:
                zip_obj = USZip(**record)
                db.add(zip_obj)

            db.commit()
            total_inserted += len(batch)
            print(f"Inserted {total_inserted}/{len(df)} rows...")

    print(f"Successfully loaded {total_inserted} ZIP codes")
    return total_inserted


def main():
    """Main entry point."""
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "uszips.csv"
    load_uszips(csv_path)


if __name__ == "__main__":
    main()
