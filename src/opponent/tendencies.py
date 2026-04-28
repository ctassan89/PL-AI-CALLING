"""Load and summarize opponent situational tendencies.

The canonical on-disk CSV schema matches the richer defensive tendency format
used by `scripts/validate_data.py`. This module normalizes that rich schema into
the smaller internal tendency view used by the recommendation engine.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd


RICH_REQUIRED_COLUMNS = {
    "team",
    "game_id",
    "down",
    "distance",
    "field_zone",
    "hash",
    "offensive_personnel",
    "offensive_formation_id",
    "defensive_personnel_id",
    "front_id",
    "box_count",
    "coverage_id",
    "blitzers",
    "movement_type",
    "sample_size",
    "frequency",
    "success_rate_allowed",
    "epa_allowed",
    "notes",
}

SIMPLIFIED_REQUIRED_COLUMNS = {
    "opponent",
    "down",
    "distance_bucket",
    "field_zone",
    "personnel",
    "def_front",
    "box_count",
    "coverage",
    "pressure",
    "play_result",
}

NORMALIZED_COLUMNS = [
    "opponent",
    "down",
    "distance_bucket",
    "field_zone",
    "personnel",
    "def_front",
    "box_count",
    "coverage",
    "pressure",
    "play_result",
]

DEFAULT_GROUP_KEYS = ("opponent", "down", "distance_bucket", "field_zone", "personnel")


def _normalize_value(value: object) -> str:
    """Normalize a CSV value into a lowercase string token."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if text == "nan":
        return ""
    return text


def _normalize_distance_bucket(value: object) -> str:
    """Normalize legacy or numeric distance values into analyzer buckets."""
    normalized = _normalize_value(value).replace("-", "_")
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


def _normalize_pressure_from_blitzers(value: object) -> str:
    """Map blitzers count into a yes/no pressure indicator."""
    normalized = _normalize_value(value)
    if not normalized:
        return ""
    try:
        return "yes" if float(normalized) > 0 else "no"
    except ValueError:
        return ""


def _normalize_rich_schema(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Map the canonical rich schema to the internal analyzer schema."""
    normalized = pd.DataFrame(
        {
            "opponent": dataframe["team"].map(_normalize_value),
            "down": dataframe["down"].map(_normalize_value),
            "distance_bucket": dataframe["distance"].map(_normalize_distance_bucket),
            "field_zone": dataframe["field_zone"].map(_normalize_value),
            "personnel": dataframe["offensive_personnel"].map(_normalize_value),
            "def_front": dataframe["front_id"].map(_normalize_value),
            "box_count": dataframe["box_count"].map(_normalize_value),
            "coverage": dataframe["coverage_id"].map(_normalize_value),
            "pressure": dataframe["blitzers"].map(_normalize_pressure_from_blitzers),
            "play_result": dataframe["notes"].map(_normalize_value),
        }
    )
    return normalized


def _normalize_simplified_schema(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize the older simplified schema for backward compatibility."""
    normalized = dataframe.copy()
    for column in SIMPLIFIED_REQUIRED_COLUMNS:
        if column == "distance_bucket":
            normalized[column] = normalized[column].map(_normalize_distance_bucket)
        else:
            normalized[column] = normalized[column].map(_normalize_value)
    return normalized[NORMALIZED_COLUMNS]


def load_opponent_tendencies(path: str | Path) -> pd.DataFrame:
    """Load the canonical rich opponent tendencies CSV and normalize it."""
    dataframe = pd.read_csv(path)
    columns = set(dataframe.columns)

    if RICH_REQUIRED_COLUMNS <= columns:
        return _normalize_rich_schema(dataframe)

    if SIMPLIFIED_REQUIRED_COLUMNS <= columns:
        return _normalize_simplified_schema(dataframe)

    rich_missing = sorted(RICH_REQUIRED_COLUMNS - columns)
    simple_missing = sorted(SIMPLIFIED_REQUIRED_COLUMNS - columns)
    raise ValueError(
        "opponent tendencies CSV must use the rich schema "
        f"({', '.join(sorted(RICH_REQUIRED_COLUMNS))}). "
        "Backwards-compatible simplified schema is also accepted for now but is "
        f"missing columns: {', '.join(simple_missing)}. "
        f"Rich schema missing columns: {', '.join(rich_missing)}."
    )


def _filter_by_keys(
    dataframe: pd.DataFrame,
    situation: Mapping[str, Any],
    keys: Sequence[str],
) -> pd.DataFrame:
    """Return rows matching the provided situation keys."""
    filtered = dataframe
    for key in keys:
        raw_value = situation.get(key)
        if key == "distance_bucket":
            normalized_value = _normalize_distance_bucket(raw_value)
        else:
            normalized_value = _normalize_value(raw_value)
        if not normalized_value:
            continue
        filtered = filtered[filtered[key] == normalized_value]
    return filtered


def _value_probabilities(dataframe: pd.DataFrame, column: str) -> dict[str, float]:
    """Convert a categorical column into probabilities."""
    values = dataframe[column]
    values = values[values != ""]
    if values.empty:
        return {}
    probabilities = values.value_counts(normalize=True).sort_values(ascending=False)
    return {str(index): float(value) for index, value in probabilities.items()}


class OpponentTendencyAnalyzer:
    """Analyze defensive frequencies for a given situation."""

    def __init__(self, tendencies: pd.DataFrame):
        self.tendencies = tendencies.copy()

    @classmethod
    def from_csv(cls, path: str | Path) -> "OpponentTendencyAnalyzer":
        """Create an analyzer from a CSV file."""
        return cls(load_opponent_tendencies(path))

    def lookup(
        self,
        situation: Mapping[str, Any],
        *,
        min_rows: int = 1,
    ) -> dict[str, dict[str, float]]:
        """Return the most likely tendencies for the most specific matching bucket."""
        key_orders = [
            DEFAULT_GROUP_KEYS,
            ("opponent", "down", "distance_bucket", "field_zone"),
            ("opponent", "down", "distance_bucket"),
            ("opponent", "down"),
            ("opponent",),
            (),
        ]

        matched = self.tendencies
        for keys in key_orders:
            candidate = _filter_by_keys(self.tendencies, situation, keys)
            if len(candidate) >= min_rows:
                matched = candidate
                break

        return {
            "coverage": _value_probabilities(matched, "coverage"),
            "pressure": _value_probabilities(matched, "pressure"),
            "box_count": _value_probabilities(matched, "box_count"),
            "def_front": _value_probabilities(matched, "def_front"),
        }
