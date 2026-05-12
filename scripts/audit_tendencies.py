"""Audit opponent tendency coverage for manual QA and gameplanning."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TENDENCIES_PATH = BASE_DIR / "data" / "opponent_tendencies.csv"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

from opponent.tendencies import RICH_REQUIRED_COLUMNS, SIMPLIFIED_REQUIRED_COLUMNS


IMPORTANT_BUCKETS = [
    ("1", "medium", "open_field"),
    ("1", "medium", "midfield"),
    ("1", "medium", "red_zone"),
    ("2", "short", "open_field"),
    ("2", "short", "midfield"),
    ("2", "medium", "open_field"),
    ("2", "long", "open_field"),
    ("3", "short", "open_field"),
    ("3", "short", "red_zone"),
    ("3", "medium", "open_field"),
    ("3", "long", "open_field"),
    ("goal_line", "short", "goal_line"),
]
COMMON_PERSONNEL = ("10", "11", "12")


def normalize_text(value: object) -> str:
    """Normalize free-form values for grouping and comparisons."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "" if text == "nan" else text


def normalize_distance_bucket(value: object) -> str:
    """Normalize raw distance values into tendency buckets."""
    normalized = normalize_text(value).replace("-", "_")
    if not normalized:
        return ""
    if normalized in {"short", "medium", "long", "very_long"}:
        return normalized
    if normalized == "xlong":
        return "very_long"
    try:
        yards = int(float(normalized))
    except ValueError:
        return normalized
    if yards <= 2:
        return "short"
    if yards <= 6:
        return "medium"
    if yards <= 10:
        return "long"
    return "very_long"


def normalize_pressure(value: object) -> str:
    """Normalize rich-schema blitzers or simplified pressure into yes/no."""
    normalized = normalize_text(value)
    if normalized in {"yes", "no"}:
        return normalized
    if not normalized:
        return ""
    try:
        return "yes" if float(normalized) > 0 else "no"
    except ValueError:
        return ""


def build_audit_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize either supported tendency schema into one audit view."""
    columns = set(dataframe.columns)
    if RICH_REQUIRED_COLUMNS <= columns:
        sample_sizes = pd.to_numeric(dataframe["sample_size"], errors="coerce").fillna(0)
        normalized = pd.DataFrame(
            {
                "opponent": dataframe["team"].map(normalize_text),
                "game_id": dataframe["game_id"].map(normalize_text),
                "down_bucket": dataframe["down"].map(normalize_down_bucket),
                "distance_bucket": dataframe["distance"].map(normalize_distance_bucket),
                "field_zone": dataframe["field_zone"].map(normalize_text),
                "personnel": dataframe["offensive_personnel"].map(normalize_text),
                "coverage": dataframe["coverage_id"].map(normalize_text),
                "front": dataframe["front_id"].map(normalize_text),
                "box": dataframe["box_count"].map(lambda value: normalize_text(value)),
                "pressure": dataframe["blitzers"].map(normalize_pressure),
                "sample_size": sample_sizes,
            }
        )
        return normalized

    if SIMPLIFIED_REQUIRED_COLUMNS <= columns:
        normalized = pd.DataFrame(
            {
                "opponent": dataframe["opponent"].map(normalize_text),
                "game_id": "",
                "down_bucket": dataframe["down"].map(normalize_down_bucket),
                "distance_bucket": dataframe["distance_bucket"].map(normalize_distance_bucket),
                "field_zone": dataframe["field_zone"].map(normalize_text),
                "personnel": dataframe["personnel"].map(normalize_text),
                "coverage": dataframe["coverage"].map(normalize_text),
                "front": dataframe["def_front"].map(normalize_text),
                "box": dataframe["box_count"].map(normalize_text),
                "pressure": dataframe["pressure"].map(normalize_pressure),
                "sample_size": 0,
            }
        )
        return normalized

    raise ValueError("Unsupported opponent tendencies schema.")


def normalize_down_bucket(value: object) -> str:
    """Normalize downs while allowing goal-line buckets in audits."""
    normalized = normalize_text(value)
    if normalized in {"1", "2", "3", "4", "goal_line"}:
        return normalized
    return normalized


def filter_opponent_rows(dataframe: pd.DataFrame, opponent: str) -> pd.DataFrame:
    """Return rows for the selected opponent, case-insensitively."""
    normalized_opponent = normalize_text(opponent)
    return dataframe[dataframe["opponent"] == normalized_opponent].copy()


def sum_sample_size(rows: pd.DataFrame) -> int:
    """Return the integer sample-size total when present."""
    if "sample_size" not in rows.columns or rows.empty:
        return 0
    return int(pd.to_numeric(rows["sample_size"], errors="coerce").fillna(0).sum())


def find_missing_important_buckets(
    rows: pd.DataFrame,
    *,
    personnel_groups: tuple[str, ...] = COMMON_PERSONNEL,
    important_buckets: list[tuple[str, str, str]] = IMPORTANT_BUCKETS,
) -> list[tuple[str, str, str, str]]:
    """Return personnel/down-distance-zone combinations with no exact rows."""
    missing: list[tuple[str, str, str, str]] = []
    for personnel in personnel_groups:
        personnel_rows = rows[rows["personnel"] == personnel]
        for down, distance_bucket, field_zone in important_buckets:
            matched = personnel_rows[
                (personnel_rows["down_bucket"] == down)
                & (personnel_rows["distance_bucket"] == distance_bucket)
                & (personnel_rows["field_zone"] == field_zone)
            ]
            if matched.empty:
                missing.append((personnel, down, distance_bucket, field_zone))
    return missing


def summarize_bucket_field(rows: pd.DataFrame, column: str, *, limit: int = 2) -> str:
    """Summarize the weighted top values for one categorical tendency field."""
    values = rows[rows[column] != ""]
    if values.empty:
        return "none"
    sample_sizes = pd.to_numeric(values["sample_size"], errors="coerce").fillna(1)
    weights = sample_sizes.where(sample_sizes > 0, 1)
    grouped = (
        values.assign(weight=weights)
        .groupby(column, sort=False)["weight"]
        .sum()
        .sort_values(ascending=False)
    )
    total = float(grouped.sum())
    top = grouped.head(limit)
    return ", ".join(
        f"{label} {float(weight) / total:.0%}" for label, weight in top.items()
    )


def fallback_risk_messages(rows: pd.DataFrame, *, min_sample_size: int) -> list[str]:
    """Identify low-coverage buckets that are likely to force broad fallbacks."""
    risks: list[str] = []
    for personnel in COMMON_PERSONNEL:
        personnel_rows = rows[rows["personnel"] == personnel]
        if personnel_rows.empty:
            risks.append(
                f"{personnel} personnel has no exact data; session may fallback to broader buckets."
            )
            continue
        total_sample = sum_sample_size(personnel_rows)
        if total_sample and total_sample < min_sample_size:
            risks.append(f"{personnel} personnel has low sample size ({total_sample}).")

        for down, distance_bucket, field_zone in IMPORTANT_BUCKETS:
            matched = personnel_rows[
                (personnel_rows["down_bucket"] == down)
                & (personnel_rows["distance_bucket"] == distance_bucket)
                & (personnel_rows["field_zone"] == field_zone)
            ]
            if matched.empty:
                broader = personnel_rows[
                    (personnel_rows["down_bucket"] == down)
                    & (personnel_rows["distance_bucket"] == distance_bucket)
                ]
                if broader.empty:
                    continue
                risks.append(
                    f"{personnel} personnel {down}/{distance_bucket}/{field_zone} has no exact data; session may fallback to broader buckets."
                )
            elif len(matched) < min_sample_size or (
                sum_sample_size(matched) and sum_sample_size(matched) < min_sample_size
            ):
                risks.append(
                    f"{personnel} personnel {down}/{distance_bucket}/{field_zone} has low coverage."
                )
    return risks


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for tendency auditing."""
    parser = argparse.ArgumentParser(description="Audit opponent tendency coverage.")
    parser.add_argument("--opponent", required=True)
    parser.add_argument("--path", default=str(DEFAULT_TENDENCIES_PATH))
    parser.add_argument("--show-rows", action="store_true")
    parser.add_argument("--min-sample-size", type=int, default=1, dest="min_sample_size")
    return parser.parse_args()


def print_basic_totals(rows: pd.DataFrame) -> None:
    """Print high-level availability totals for the selected opponent."""
    game_ids = sorted({value for value in rows["game_id"] if value})
    personnel = sorted({value for value in rows["personnel"] if value})
    field_zones = sorted({value for value in rows["field_zone"] if value})
    down_distance = sorted(
        {
            f"{down} {distance}"
            for down, distance in zip(rows["down_bucket"], rows["distance_bucket"], strict=False)
            if down and distance
        }
    )
    print("Basic totals:")
    print(f"- total rows: {len(rows)}")
    print(f"- total sample size: {sum_sample_size(rows)}")
    print(f"- game_ids: {', '.join(game_ids) if game_ids else 'none'}")
    print(f"- personnel: {', '.join(personnel) if personnel else 'none'}")
    print(f"- field zones: {', '.join(field_zones) if field_zones else 'none'}")
    print(f"- down/distance buckets: {', '.join(down_distance) if down_distance else 'none'}")
    print()


def print_coverage_by_personnel(rows: pd.DataFrame) -> None:
    """Print per-personnel coverage by down, distance bucket, and field zone."""
    print("Coverage by personnel:")
    personnel_groups = sorted({value for value in rows["personnel"] if value})
    if not personnel_groups:
        print("- none")
        print()
        return
    for personnel in personnel_groups:
        print(f"Personnel {personnel}:")
        personnel_rows = rows[rows["personnel"] == personnel]
        grouped = (
            personnel_rows.groupby(["down_bucket", "distance_bucket", "field_zone"], dropna=False)
            .size()
            .reset_index(name="row_count")
            .sort_values(by=["down_bucket", "distance_bucket", "field_zone"])
        )
        for entry in grouped.itertuples(index=False):
            matched = personnel_rows[
                (personnel_rows["down_bucket"] == entry.down_bucket)
                & (personnel_rows["distance_bucket"] == entry.distance_bucket)
                & (personnel_rows["field_zone"] == entry.field_zone)
            ]
            print(
                f"- {entry.down_bucket} {entry.distance_bucket} {entry.field_zone}: "
                f"{int(entry.row_count)} rows, sample_size={sum_sample_size(matched)}"
            )
    print()


def print_missing_buckets(rows: pd.DataFrame) -> None:
    """Print missing important buckets for common personnel groups."""
    print("Missing important buckets:")
    missing = find_missing_important_buckets(rows)
    if not missing:
        print("- none")
        print()
        return
    for personnel, down, distance_bucket, field_zone in missing:
        print(f"- personnel {personnel}, {down}, {distance_bucket}, {field_zone}")
    print()


def print_tendency_summary(rows: pd.DataFrame) -> None:
    """Print top tendencies for each populated major bucket."""
    print("Tendencies summary:")
    grouped = (
        rows.groupby(["personnel", "down_bucket", "distance_bucket", "field_zone"], dropna=False)
        .size()
        .reset_index(name="row_count")
        .sort_values(by=["personnel", "down_bucket", "distance_bucket", "field_zone"])
    )
    if grouped.empty:
        print("- none")
        print()
        return
    for entry in grouped.itertuples(index=False):
        matched = rows[
            (rows["personnel"] == entry.personnel)
            & (rows["down_bucket"] == entry.down_bucket)
            & (rows["distance_bucket"] == entry.distance_bucket)
            & (rows["field_zone"] == entry.field_zone)
        ]
        print(
            f"{entry.personnel} | {entry.down_bucket} {entry.distance_bucket} | {entry.field_zone}:"
        )
        print(f"- coverage: {summarize_bucket_field(matched, 'coverage')}")
        print(f"- front: {summarize_bucket_field(matched, 'front')}")
        print(f"- box: {summarize_bucket_field(matched, 'box')}")
        print(f"- pressure: {summarize_bucket_field(matched, 'pressure')}")
    print()


def print_fallback_risks(rows: pd.DataFrame, *, min_sample_size: int) -> None:
    """Print warnings for buckets likely to fall back broadly."""
    print("Fallback risks:")
    risks = fallback_risk_messages(rows, min_sample_size=min_sample_size)
    if not risks:
        print("- none")
        print()
        return
    for risk in risks:
        print(f"- {risk}")
    print()


def main() -> None:
    """Run the tendency coverage audit."""
    args = parse_args()
    raw = pd.read_csv(Path(args.path))
    audit = build_audit_dataframe(raw)
    rows = filter_opponent_rows(audit, args.opponent)
    if rows.empty:
        raise SystemExit(f"No opponent tendency rows found for {args.opponent}.")

    print(f"Opponent tendency audit: {normalize_text(args.opponent)}")
    print()
    print_basic_totals(rows)
    print_coverage_by_personnel(rows)
    print_missing_buckets(rows)
    print_tendency_summary(rows)
    print_fallback_risks(rows, min_sample_size=args.min_sample_size)

    if args.show_rows:
        print("Rows:")
        print(
            rows[
                [
                    "opponent",
                    "personnel",
                    "down_bucket",
                    "distance_bucket",
                    "field_zone",
                    "coverage",
                    "front",
                    "box",
                    "pressure",
                    "sample_size",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
