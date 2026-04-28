"""Load and summarize opponent situational tendencies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
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

DEFAULT_GROUP_KEYS = ("opponent", "down", "distance_bucket", "field_zone", "personnel")


def _normalize_value(value: object) -> str:
    """Normalize a CSV value into a lowercase string token."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if text == "nan":
        return ""
    return text


def load_opponent_tendencies(path: str | Path) -> pd.DataFrame:
    """Load and normalize the opponent tendencies CSV."""
    dataframe = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(dataframe.columns))
    if missing:
        raise ValueError(
            "opponent tendencies CSV is missing required columns: "
            + ", ".join(missing)
        )

    normalized = dataframe.copy()
    for column in REQUIRED_COLUMNS:
        normalized[column] = normalized[column].map(_normalize_value)

    return normalized


def _filter_by_keys(
    dataframe: pd.DataFrame,
    situation: Mapping[str, Any],
    keys: Sequence[str],
) -> pd.DataFrame:
    """Return rows matching the provided situation keys."""
    filtered = dataframe
    for key in keys:
        raw_value = situation.get(key)
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
