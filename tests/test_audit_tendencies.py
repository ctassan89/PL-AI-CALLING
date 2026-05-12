"""Tests for the opponent tendency audit helpers."""

from __future__ import annotations

import pandas as pd

from scripts import audit_tendencies


def make_rich_rows() -> list[dict[str, object]]:
    """Build a small rich-schema dataset for audit coverage tests."""
    base = {
        "team": "Rhinos",
        "game_id": "g0",
        "hash": "middle",
        "offensive_formation_id": "gun_11_2x2",
        "defensive_personnel_id": "nickel",
        "movement_type": "none",
        "success_rate_allowed": 0.4,
        "epa_allowed": -0.02,
        "notes": "sample",
        "frequency": 1.0,
    }
    return [
        {
            **base,
            "game_id": "g1",
            "down": 1,
            "distance": "medium",
            "field_zone": "open_field",
            "offensive_personnel": "11",
            "front_id": "even_4",
            "box_count": 6,
            "coverage_id": "cover3_buzz_field",
            "blitzers": 0,
            "sample_size": 8,
        },
        {
            **base,
            "game_id": "g2",
            "down": 2,
            "distance": "short",
            "field_zone": "midfield",
            "offensive_personnel": "11",
            "front_id": "bear",
            "box_count": 8,
            "coverage_id": "cover1_man_free",
            "blitzers": 2,
            "sample_size": 3,
        },
        {
            **base,
            "game_id": "g3",
            "down": 2,
            "distance": "short",
            "field_zone": "midfield",
            "offensive_personnel": "11",
            "front_id": "bear",
            "box_count": 8,
            "coverage_id": "cover3_buzz_field",
            "blitzers": 1,
            "sample_size": 1,
        },
    ]


def test_build_audit_dataframe_normalizes_rich_schema() -> None:
    """Rich-schema rows should normalize into the audit view."""
    dataframe = pd.DataFrame(make_rich_rows())

    audit = audit_tendencies.build_audit_dataframe(dataframe)

    assert list(audit.columns) == [
        "opponent",
        "game_id",
        "down_bucket",
        "distance_bucket",
        "field_zone",
        "personnel",
        "coverage",
        "front",
        "box",
        "pressure",
        "sample_size",
    ]
    assert audit.loc[0, "opponent"] == "rhinos"
    assert audit.loc[1, "pressure"] == "yes"
    assert audit.loc[0, "distance_bucket"] == "medium"


def test_find_missing_important_buckets_flags_missing_personnel_buckets() -> None:
    """Missing-bucket detection should identify uncovered personnel combinations."""
    audit = audit_tendencies.build_audit_dataframe(pd.DataFrame(make_rich_rows()))

    missing = audit_tendencies.find_missing_important_buckets(
        audit,
        personnel_groups=("11",),
        important_buckets=[("1", "medium", "open_field"), ("3", "long", "open_field")],
    )

    assert missing == [("11", "3", "long", "open_field")]


def test_fallback_risk_messages_warn_on_low_coverage_and_broad_only_data() -> None:
    """Fallback risk detection should warn on both missing exact buckets and low coverage."""
    audit = audit_tendencies.build_audit_dataframe(pd.DataFrame(make_rich_rows()))

    risks = audit_tendencies.fallback_risk_messages(audit, min_sample_size=5)

    assert any("2/short/midfield has low coverage" in risk for risk in risks)
    assert any("10 personnel has no exact data" in risk for risk in risks)
