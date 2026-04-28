"""Recommendation engine helpers for scoring playbook entries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


Situation = Mapping[str, Any]
TendencySnapshot = Mapping[str, Mapping[str, float]]

BASE_SCORE_WEIGHTS = {
    "front_match": 3,
    "coverage_match": 3,
    "box_match": 2,
    "formation_match": 2,
    "distance_match": 1,
    "field_zone_match": 1,
}

COVERAGE_TENDENCY_WEIGHT = 2.0
BOX_TENDENCY_MATCH_WEIGHT = 1.5
PRESSURE_TENDENCY_WEIGHT = 2.0
LIGHT_BOX_RUN_WEIGHT = 1.5
HEAVY_BOX_RUN_PENALTY = -1.5
HEAVY_BOX_PASS_WEIGHT = 1.0

QUICK_PRESSURE_FAMILIES = {"quick_game", "screen", "rpo"}
QUICK_PRESSURE_TYPES = {"screen", "rpo"}
HOT_ANSWER_CONCEPTS = {"slant_flat", "stick", "spacing", "curl_flat"}


def parse_list(value: object) -> list[str]:
    """Split a semicolon-separated field into normalized values."""
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def map_box_count(box_count: int) -> str:
    """Map a numeric box count to a categorical box label."""
    if box_count <= 5:
        return "light_box"
    if box_count == 6:
        return "neutral_box"
    if box_count == 7:
        return "heavy_box"
    return "loaded_box"


def matches_category(play_values: list[str], target_value: str) -> bool:
    """Return whether a category matches, respecting any/none rules."""
    if "any" in play_values:
        return True
    if "none" in play_values:
        return False
    return target_value in play_values


def build_situation(
    *,
    down: int | str,
    distance: str,
    field_zone: str,
    formation_id: str,
    front_id: str,
    coverage_id: str,
    box_count: int,
    personnel: str | None = None,
    opponent: str | None = None,
) -> dict[str, str]:
    """Create the normalized situation payload used by the recommender."""
    situation = {
        "down": str(down),
        "distance": str(distance),
        "field_zone": str(field_zone),
        "formation_id": str(formation_id),
        "front_id": str(front_id),
        "coverage_id": str(coverage_id),
        "box_label": map_box_count(int(box_count)),
        "box_count": str(int(box_count)),
    }
    if personnel:
        situation["personnel"] = str(personnel)
    if opponent:
        situation["opponent"] = str(opponent)
    return situation


def score_play(play: pd.Series, situation: Situation) -> tuple[int, list[str]]:
    """Score a play against the current situation and collect base-match reasons."""
    score = 0
    reasons: list[str] = []

    front_values = parse_list(play["beats_front"])
    if matches_category(front_values, str(situation["front_id"])):
        score += BASE_SCORE_WEIGHTS["front_match"]
        reasons.append(f"front match: {situation['front_id']}")

    coverage_values = parse_list(play["beats_coverage"])
    if matches_category(coverage_values, str(situation["coverage_id"])):
        score += BASE_SCORE_WEIGHTS["coverage_match"]
        reasons.append(f"coverage match: {situation['coverage_id']}")

    box_values = parse_list(play["beats_box"])
    if matches_category(box_values, str(situation["box_label"])):
        score += BASE_SCORE_WEIGHTS["box_match"]
        reasons.append(f"box match: {situation['box_label']}")

    if str(play["formation_id"]) == str(situation["formation_id"]):
        score += BASE_SCORE_WEIGHTS["formation_match"]
        reasons.append(f"formation match: {situation['formation_id']}")

    distance_values = parse_list(play["preferred_down_distance"])
    if matches_category(distance_values, str(situation["distance"])):
        score += BASE_SCORE_WEIGHTS["distance_match"]
        reasons.append(f"distance match: {situation['distance']}")

    field_zone_values = parse_list(play["preferred_field_zone"])
    if matches_category(field_zone_values, str(situation["field_zone"])):
        score += BASE_SCORE_WEIGHTS["field_zone_match"]
        reasons.append(f"field zone match: {situation['field_zone']}")

    return score, reasons


def is_pure_run(play: pd.Series) -> bool:
    """Return whether the play is a true run rather than RPO/pass."""
    return str(play["play_type"]) == "run"


def is_pressure_answer(play: pd.Series) -> bool:
    """Return whether the play gives a quick answer versus pressure."""
    play_family = str(play["play_family"])
    play_type = str(play["play_type"])
    pass_concept = str(play["pass_concept"])
    rpo_tag = str(play["rpo_tag"])
    return (
        play_family in QUICK_PRESSURE_FAMILIES
        or play_type in QUICK_PRESSURE_TYPES
        or pass_concept in HOT_ANSWER_CONCEPTS
        or rpo_tag != "none"
    )


def aggregate_box_probabilities(
    probabilities: Mapping[str, float] | None,
) -> dict[str, float]:
    """Normalize numeric or categorical box-count probabilities into box labels."""
    aggregated = {
        "light_box": 0.0,
        "neutral_box": 0.0,
        "heavy_box": 0.0,
        "loaded_box": 0.0,
    }
    if not probabilities:
        return aggregated

    for raw_value, probability in probabilities.items():
        value = str(raw_value)
        if value in aggregated:
            aggregated[value] += float(probability)
            continue
        try:
            label = map_box_count(int(value))
        except ValueError:
            continue
        aggregated[label] += float(probability)
    return aggregated


def apply_tendency_adjustments(
    play: pd.Series,
    tendencies: TendencySnapshot | None,
) -> tuple[float, list[str]]:
    """Calculate additive score adjustments from opponent tendency probabilities."""
    if not tendencies:
        return 0.0, []

    adjustment = 0.0
    reasons: list[str] = []

    coverage_probabilities = tendencies.get("coverage")
    if coverage_probabilities:
        for coverage_id in parse_list(play["beats_coverage"]):
            if coverage_id in {"any", "none"}:
                continue
            probability = float(coverage_probabilities.get(coverage_id, 0.0))
            if probability > 0:
                delta = probability * COVERAGE_TENDENCY_WEIGHT
                adjustment += delta
                reasons.append(f"tendency boost: {coverage_id} {probability:.0%}")

    box_probabilities = aggregate_box_probabilities(tendencies.get("box_count"))
    play_box_values = parse_list(play["beats_box"])
    for box_label in ("light_box", "neutral_box", "heavy_box", "loaded_box"):
        probability = box_probabilities.get(box_label, 0.0)
        if probability > 0 and box_label in play_box_values:
            delta = probability * BOX_TENDENCY_MATCH_WEIGHT
            adjustment += delta
            reasons.append(f"tendency boost: {box_label} {probability:.0%}")

    pressure_probabilities = tendencies.get("pressure")
    pressure_yes_probability = 0.0
    if pressure_probabilities:
        pressure_yes_probability = float(pressure_probabilities.get("yes", 0.0))

    if pressure_yes_probability > 0 and is_pressure_answer(play):
        delta = pressure_yes_probability * PRESSURE_TENDENCY_WEIGHT
        adjustment += delta
        reasons.append(
            f"tendency boost: pressure answer {pressure_yes_probability:.0%}"
        )

    heavy_box_probability = (
        box_probabilities.get("heavy_box", 0.0)
        + box_probabilities.get("loaded_box", 0.0)
    )
    light_box_probability = box_probabilities.get("light_box", 0.0)

    if is_pure_run(play):
        if heavy_box_probability > 0:
            delta = heavy_box_probability * HEAVY_BOX_RUN_PENALTY
            adjustment += delta
            reasons.append(
                f"tendency penalty: heavy box {heavy_box_probability:.0%}"
            )
        if light_box_probability > 0:
            delta = light_box_probability * LIGHT_BOX_RUN_WEIGHT
            adjustment += delta
            reasons.append(
                f"tendency boost: light box {light_box_probability:.0%}"
            )
    elif (
        str(play["play_type"]) in {"pass", "rpo", "screen"}
        and heavy_box_probability > 0
    ):
        delta = heavy_box_probability * HEAVY_BOX_PASS_WEIGHT
        adjustment += delta
        reasons.append(
            f"tendency boost: throw into heavy box {heavy_box_probability:.0%}"
        )

    return adjustment, reasons


def recommend_plays(
    playbook: pd.DataFrame,
    situation: Situation,
    *,
    tendencies: TendencySnapshot | None = None,
    limit: int = 3,
) -> list[dict[str, object]]:
    """Score a playbook and return ranked recommendations."""
    recommendations: list[dict[str, object]] = []

    for _, play in playbook.iterrows():
        base_score, base_reasons = score_play(play, situation)
        tendency_adjustment, tendency_reasons = apply_tendency_adjustments(
            play, tendencies
        )
        total_score = float(base_score) + tendency_adjustment

        recommendations.append(
            {
                "play_name": str(play["play_name"]),
                "play_id": str(play["play_id"]),
                "score": total_score,
                "base_score": base_score,
                "tendency_adjustment": tendency_adjustment,
                "reasons": [*base_reasons, *tendency_reasons],
            }
        )

    return sorted(
        recommendations,
        key=lambda play: (
            -float(play["score"]),
            str(play["play_name"]),
            str(play["play_id"]),
        ),
    )[:limit]
