"""Validate defensive tendency data against taxonomy CSV files."""

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
RAW_DIR = DATA_DIR / "raw"

ALLOWED_DOWNS = {1, 2, 3, 4}
ALLOWED_DISTANCES = {"short", "medium", "long", "xlong"}
ALLOWED_FIELD_ZONES = {
    "own_redzone",
    "own_territory",
    "midfield",
    "opp_territory",
    "redzone",
    "goal_line",
}
ALLOWED_HASHES = {"left", "middle", "right"}


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file from disk."""
    return pd.read_csv(path)


def add_missing_id_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
    allowed_ids: set[str],
    taxonomy_name: str,
) -> None:
    """Add validation errors for IDs missing from a taxonomy table."""
    values = set(df[column_name].dropna().astype(str))
    missing = sorted(values - allowed_ids)
    if missing:
        errors.append(
            f"{column_name} contains unknown values not found in {taxonomy_name}: "
            + ", ".join(missing)
        )


def add_invalid_value_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
    allowed_values: set,
) -> None:
    """Add validation errors for invalid categorical values."""
    values = set(df[column_name].dropna())
    invalid = sorted(values - allowed_values)
    if invalid:
        errors.append(
            f"{column_name} contains invalid values: " + ", ".join(map(str, invalid))
        )


def add_non_numeric_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
) -> None:
    """Add validation errors when a column cannot be parsed as numeric."""
    numeric_values = pd.to_numeric(df[column_name], errors="coerce")
    invalid_rows = df.index[numeric_values.isna()].tolist()
    if invalid_rows:
        row_numbers = ", ".join(str(index + 2) for index in invalid_rows)
        errors.append(
            f"{column_name} must be numeric. Invalid values found at CSV rows: "
            f"{row_numbers}"
        )


def main() -> None:
    """Run validation checks for defensive tendency input data."""
    fronts = load_csv(TAXONOMY_DIR / "fronts.csv")
    coverages = load_csv(TAXONOMY_DIR / "coverages.csv")
    defensive_personnel = load_csv(TAXONOMY_DIR / "defensive_personnel.csv")
    offensive_formations = load_csv(TAXONOMY_DIR / "offensive_formations.csv")
    defensive_tendencies = load_csv(RAW_DIR / "defensive_tendencies.csv")

    errors: list[str] = []

    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "front_id",
        set(fronts["front_id"].dropna().astype(str)),
        "fronts.csv",
    )
    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "coverage_id",
        set(coverages["coverage_id"].dropna().astype(str)),
        "coverages.csv",
    )
    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "defensive_personnel_id",
        set(defensive_personnel["defensive_personnel_id"].dropna().astype(str)),
        "defensive_personnel.csv",
    )
    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "offensive_formation_id",
        set(offensive_formations["formation_id"].dropna().astype(str)),
        "offensive_formations.csv",
    )

    add_invalid_value_errors(errors, defensive_tendencies, "down", ALLOWED_DOWNS)
    add_invalid_value_errors(
        errors, defensive_tendencies, "distance", ALLOWED_DISTANCES
    )
    add_invalid_value_errors(
        errors, defensive_tendencies, "field_zone", ALLOWED_FIELD_ZONES
    )
    add_invalid_value_errors(errors, defensive_tendencies, "hash", ALLOWED_HASHES)

    for column_name in ["frequency", "success_rate_allowed", "epa_allowed"]:
        add_non_numeric_errors(errors, defensive_tendencies, column_name)

    if errors:
        print("Data validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Data validation passed.")


if __name__ == "__main__":
    main()
