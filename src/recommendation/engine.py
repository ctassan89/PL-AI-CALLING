"""Recommendation engine with situation-first football scoring.

The core design principle is that down, distance, and territory drive the base
recommendation. Defensive matchup signals still matter, but they are secondary
and cannot override obviously bad situational football such as a pure run on
3rd-and-15.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


Situation = Mapping[str, Any]
TendencySnapshot = Mapping[str, Mapping[str, float]]

# Secondary matchup weights. These remain important, but are intentionally
# smaller than situation-fit weights so they cannot overpower down/distance.
MATCHUP_SCORE_WEIGHTS = {
    "front_match": 1.5,
    "coverage_match": 2.5,
    "box_match": 1.5,
    "formation_match": 1.0,
    "distance_match": 0.5,
    "field_zone_match": 0.5,
}

# Situation-first weights. These are the strongest levers in the system.
SITUATION_SCORE_WEIGHTS = {
    "balanced_run": 3.0,
    "balanced_pass": 2.5,
    "balanced_rpo": 3.0,
    "aggressive_shot": 3.5,
    "attacks_sticks": 5.5,
    "quick_answer": 3.5,
    "screen_answer": 4.0,
    "short_yardage_boost": 5.0,
    "medium_conversion_boost": 4.5,
    "long_run_penalty": -9.0,
    "very_long_run_penalty": -13.0,
    "second_long_run_penalty": -3.5,
    "deep_shot_short_penalty": -4.0,
    "backed_up_safe_call": 3.0,
    "backed_up_risk_penalty": -4.0,
    "plus_territory_aggression": 1.5,
    "red_zone_boost": 3.0,
    "red_zone_space_penalty": -3.0,
    "goal_line_boost": 5.0,
    "goal_line_bad_space_penalty": -6.0,
}

# Tendency adjustments layer on top of base football logic and are capped below
# the hard situational penalties.
TENDENCY_SCORE_WEIGHTS = {
    "coverage_match": 2.0,
    "box_match": 1.25,
    "pressure_answer": 2.5,
    "pressure_risk": -3.5,
    "light_box_run": 1.5,
    "heavy_box_run": -2.0,
    "heavy_box_pass": 1.0,
}

# Guardrails are still implemented as score penalties so recommendations remain
# explainable, but they are large enough to keep nonsense out of the top calls.
GUARDRAIL_SCORE_WEIGHTS = {
    "money_very_long_pure_run": -18.0,
    "money_long_pure_run": -10.0,
    "backed_up_shot": -8.0,
    "red_zone_vertical": -7.0,
}

SHORT_YARDAGE_CONCEPTS = {"stick", "choice", "slant_flat", "spacing", "curl_flat"}
ATTACKS_STICKS_CONCEPTS = {
    "flood",
    "mesh",
    "drive",
    "levels",
    "dagger",
    "y_cross",
    "four_verts",
    "choice",
    "curl_flat",
}
SHOT_CONCEPTS = {"four_verts", "mills", "wheel"}
VERTICAL_SPACE_CONCEPTS = {"four_verts", "mills", "wheel"}
SLOW_DEVELOPING_CONCEPTS = {"four_verts", "mills", "dagger", "y_cross", "flood"}
PRESSURE_ANSWER_CONCEPTS = {"slant_flat", "stick", "spacing", "curl_flat"}
RED_ZONE_FRIENDLY_CONCEPTS = {"slant_flat", "stick", "spacing", "flood"}
GOAL_LINE_FRIENDLY_SCHEMES = {"inside_zone", "duo", "power", "trap", "iso"}
GOAL_LINE_FRIENDLY_CONCEPTS = {"slant_flat", "flood", "stick"}

NUMERIC_DISTANCE_TO_BUCKET = (
    (2, "short"),
    (6, "medium"),
    (10, "long"),
)
FIELD_ZONE_TO_TERRITORY = {
    "own_redzone": "backed_up",
    "own_territory": "own_side",
    "midfield": "midfield",
    "opp_territory": "plus_territory",
    "redzone": "red_zone",
    "goal_line": "goal_line",
}
FIELD_ZONE_TO_LABEL = {
    "own_redzone": "backed up",
    "own_territory": "own side",
    "midfield": "midfield",
    "opp_territory": "plus territory",
    "redzone": "red zone",
    "goal_line": "goal line",
}
FIELD_ZONE_TO_PLAYBOOK_VALUE = {
    "backed_up": "own_redzone",
    "own_side": "own_territory",
    "midfield": "midfield",
    "plus_territory": "opp_territory",
    "red_zone": "redzone",
    "goal_line": "goal_line",
}

DISTANCE_ALIASES = {
    "xlong": "very_long",
    "very_long": "very_long",
    "very long": "very_long",
    "long": "long",
    "medium": "medium",
    "short": "short",
}


def parse_list(value: object) -> list[str]:
    """Split a semicolon-separated field into normalized values."""
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def normalize_text(value: object) -> str:
    """Normalize a free-form value for comparisons."""
    return str(value).strip().lower()


def parse_numeric(value: object) -> int | None:
    """Parse an integer from a value when possible."""
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


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


def classify_distance_bucket(distance: object) -> tuple[str, int | None]:
    """Map numeric or legacy string distance values to football buckets."""
    numeric_distance = parse_numeric(distance)
    if numeric_distance is not None:
        for max_yards, bucket in NUMERIC_DISTANCE_TO_BUCKET:
            if numeric_distance <= max_yards:
                return bucket, numeric_distance
        return "very_long", numeric_distance

    distance_key = normalize_text(distance).replace("-", "_")
    bucket = DISTANCE_ALIASES.get(distance_key)
    if bucket is None:
        raise ValueError(f"Unsupported distance value: {distance}")
    return bucket, None


def classify_down_bucket(down: object) -> str:
    """Map down number to early-down or money-down bucket."""
    numeric_down = parse_numeric(down)
    if numeric_down in {1, 2}:
        return "early_down"
    if numeric_down in {3, 4}:
        return "money_down"
    raise ValueError(f"Unsupported down value: {down}")


def classify_field_position(field_zone: object) -> str:
    """Map existing field-zone strings to explicit territory buckets."""
    field_zone_key = normalize_text(field_zone)
    territory = FIELD_ZONE_TO_TERRITORY.get(field_zone_key)
    if territory is None:
        raise ValueError(f"Unsupported field zone value: {field_zone}")
    return territory


def describe_distance_bucket(bucket: str) -> str:
    """Return a readable distance label."""
    return bucket.replace("_", " ")


def classify_combined_situation(
    down: int,
    distance_bucket: str,
    raw_distance: int | None,
) -> str:
    """Build a combined situation key used by the scoring rules."""
    if down == 1 and (raw_distance == 10 or distance_bucket == "medium"):
        return "first_and_10"
    if down == 2:
        return {
            "short": "second_and_short",
            "medium": "second_and_medium",
            "long": "second_and_long",
            "very_long": "second_and_very_long",
        }[distance_bucket]
    if down in {3, 4}:
        return {
            "short": "money_down_short",
            "medium": "money_down_medium",
            "long": "money_down_long",
            "very_long": "money_down_very_long",
        }[distance_bucket]
    return "early_down"


def describe_combined_situation(situation_key: str) -> str:
    """Return a readable label for score explanations."""
    labels = {
        "first_and_10": "1st & 10",
        "second_and_short": "2nd & short",
        "second_and_medium": "2nd & medium",
        "second_and_long": "2nd & long",
        "second_and_very_long": "2nd & very long",
        "money_down_short": "3rd/4th & short",
        "money_down_medium": "3rd/4th & medium",
        "money_down_long": "3rd/4th & long",
        "money_down_very_long": "3rd/4th & very long",
    }
    return labels.get(situation_key, situation_key.replace("_", " "))


def build_situation(
    *,
    down: int | str,
    distance: str | int,
    field_zone: str,
    formation_id: str,
    front_id: str,
    coverage_id: str,
    box_count: int,
    personnel: str | None = None,
    opponent: str | None = None,
) -> dict[str, str | int]:
    """Create the normalized situation payload used by the recommender."""
    numeric_down = parse_numeric(down)
    if numeric_down is None:
        raise ValueError(f"Unsupported down value: {down}")

    distance_bucket, raw_distance = classify_distance_bucket(distance)
    territory = classify_field_position(field_zone)
    combined_situation = classify_combined_situation(
        numeric_down, distance_bucket, raw_distance
    )

    situation: dict[str, str | int] = {
        "down": str(numeric_down),
        "down_bucket": classify_down_bucket(numeric_down),
        "distance": str(distance),
        "distance_bucket": distance_bucket,
        "raw_distance": raw_distance if raw_distance is not None else "",
        "combined_situation": combined_situation,
        "combined_situation_label": describe_combined_situation(combined_situation),
        "field_zone": str(field_zone),
        "territory": territory,
        "territory_label": FIELD_ZONE_TO_LABEL[str(field_zone)],
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


def play_series_value(play: pd.Series, column_name: str, default: str = "") -> str:
    """Safely read a play field from a Series."""
    if column_name not in play.index:
        return default
    value = play[column_name]
    if pd.isna(value):
        return default
    return str(value)


def infer_play_tags(play: pd.Series) -> set[str]:
    """Build semantic tags from explicit tags plus existing schema fields."""
    tags = set(parse_list(play_series_value(play, "tags")))
    play_family = play_series_value(play, "play_family")
    play_type = play_series_value(play, "play_type")
    run_scheme = play_series_value(play, "run_scheme")
    run_modifier = play_series_value(play, "run_modifier")
    pass_concept = play_series_value(play, "pass_concept")
    pass_modifier = play_series_value(play, "pass_modifier")
    rpo_tag = play_series_value(play, "rpo_tag")
    play_action = normalize_text(play_series_value(play, "play_action")) == "true"

    if play_type == "run":
        tags.add("pure_run")
    if play_type == "screen" or play_family == "screen":
        tags.update({"screen", "pressure_answer", "safe_call"})
    if play_family == "quick_game" or pass_concept in PRESSURE_ANSWER_CONCEPTS:
        tags.update({"quick_game", "pressure_answer", "safe_call"})
    if play_type == "rpo" or play_family == "rpo" or rpo_tag != "none":
        tags.update({"rpo", "pressure_answer"})
    if play_action or play_family in {"play_action", "boot"}:
        tags.add("play_action")
    if play_family == "boot":
        tags.add("boot")

    if run_scheme in {"inside_zone", "duo", "power", "counter", "trap", "iso"}:
        tags.add("inside_run")
    if run_scheme in {"outside_zone", "option"}:
        tags.add("outside_run")
    if run_scheme in {"power", "duo", "trap", "iso", "qb_run"}:
        tags.add("short_yardage")
    if run_scheme == "draw" or run_modifier == "draw":
        tags.update({"draw", "safe_call"})

    if pass_concept in ATTACKS_STICKS_CONCEPTS:
        tags.add("attacks_sticks")
    if pass_concept in SHOT_CONCEPTS or pass_modifier == "switch":
        tags.update({"shot", "vertical"})
    if pass_concept in VERTICAL_SPACE_CONCEPTS:
        tags.add("vertical")
    if pass_concept in SLOW_DEVELOPING_CONCEPTS:
        tags.add("slow_developing")
    if pass_concept in RED_ZONE_FRIENDLY_CONCEPTS:
        tags.add("red_zone")

    if run_scheme in GOAL_LINE_FRIENDLY_SCHEMES or pass_concept in GOAL_LINE_FRIENDLY_CONCEPTS:
        tags.add("goal_line")
    if "screen" in tags:
        tags.add("attacks_sticks")

    return tags


def is_pure_run(play: pd.Series) -> bool:
    """Return whether the play is a true run rather than RPO/pass."""
    return "pure_run" in infer_play_tags(play)


def is_pressure_answer(play: pd.Series) -> bool:
    """Return whether the play gives a quick answer versus pressure."""
    return "pressure_answer" in infer_play_tags(play)


def is_valid_money_down_run(play: pd.Series) -> bool:
    """Return whether a run has a special tag that makes it less absurd on long yardage."""
    tags = infer_play_tags(play)
    return bool({"draw", "safe_call"} & tags)


def add_score_reason(reasons: list[str], delta: float, text: str) -> float:
    """Record a scored reason using a consistent explainable format."""
    reasons.append(f"{delta:+.1f} {text}")
    return delta


def score_situational_fit(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score football realism for down, distance, and territory."""
    tags = infer_play_tags(play)
    situation_key = str(situation["combined_situation"])
    territory = str(situation["territory"])
    reasons: list[str] = []
    score = 0.0

    if situation_key == "first_and_10":
        if "pure_run" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["balanced_run"],
                "situation fit: 1st & 10 allows balanced run game",
            )
        if "rpo" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["balanced_rpo"],
                "situation fit: 1st & 10 is favorable for RPOs",
            )
        if "play_action" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["balanced_pass"],
                "situation fit: 1st & 10 supports play action",
            )
        if tags & {"quick_game", "attacks_sticks", "screen"}:
            score += add_score_reason(
                reasons,
                2.0,
                "situation fit: 1st & 10 keeps base pass concepts available",
            )

    elif situation_key == "second_and_short":
        if "play_action" in tags or "shot" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["aggressive_shot"],
                "situation fit: 2nd & short allows aggressive play-action or shot calls",
            )
        if "pure_run" in tags or "rpo" in tags:
            score += add_score_reason(
                reasons,
                2.5,
                "situation fit: 2nd & short still supports efficient run/RPO calls",
            )
        if "quick_game" in tags:
            score += add_score_reason(
                reasons,
                1.5,
                "situation fit: 2nd & short supports high-percentage quick game",
            )

    elif situation_key == "second_and_medium":
        if "pure_run" in tags or "rpo" in tags:
            score += add_score_reason(
                reasons,
                2.0,
                "situation fit: 2nd & medium allows balanced run/RPO calls",
            )
        if tags & {"quick_game", "attacks_sticks", "screen"}:
            score += add_score_reason(
                reasons,
                2.0,
                "situation fit: 2nd & medium supports balanced pass concepts",
            )

    elif situation_key in {"second_and_long", "second_and_very_long"}:
        if "pure_run" in tags and "draw" not in tags:
            penalty = SITUATION_SCORE_WEIGHTS["second_long_run_penalty"]
            if situation_key == "second_and_very_long":
                penalty -= 1.5
            score += add_score_reason(
                reasons,
                penalty,
                f"situation penalty: {describe_combined_situation(situation_key)} reduces low-upside pure runs",
            )
        if tags & {"quick_game", "rpo", "screen"}:
            boost = 3.0 if situation_key == "second_and_very_long" else 2.5
            score += add_score_reason(
                reasons,
                boost,
                f"situation fit: {describe_combined_situation(situation_key)} favors efficient pass answers",
            )
        if "attacks_sticks" in tags:
            boost = 3.5 if situation_key == "second_and_very_long" else 2.5
            score += add_score_reason(
                reasons,
                boost,
                f"situation fit: {describe_combined_situation(situation_key)} favors concepts attacking the sticks",
            )
        if "play_action" in tags and situation_key == "second_and_short":
            score += add_score_reason(
                reasons,
                2.0,
                "situation fit: 2nd & short supports play action",
            )

    elif situation_key == "money_down_short":
        if "short_yardage" in tags or "inside_run" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["short_yardage_boost"],
                "situation fit: 3rd/4th & short favors short-yardage run concepts",
            )
        if tags & {"quick_game", "rpo", "pressure_answer"}:
            score += add_score_reason(
                reasons,
                4.0,
                "situation fit: 3rd/4th & short favors quick, high-percentage answers",
            )
        if "shot" in tags and "play_action" not in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["deep_shot_short_penalty"],
                "situation penalty: deep shot is low percentage on 3rd/4th & short",
            )

    elif situation_key == "money_down_medium":
        if tags & {"quick_game", "attacks_sticks", "rpo"}:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["medium_conversion_boost"],
                "situation fit: 3rd/4th & medium favors efficient concepts near the sticks",
            )
        if "pure_run" in tags and "draw" not in tags:
            score += add_score_reason(
                reasons,
                -5.0,
                "situation penalty: pure run is low percentage on 3rd/4th & medium",
            )
        if "shot" in tags and "play_action" not in tags:
            score += add_score_reason(
                reasons,
                -2.5,
                "situation penalty: low-percentage deep shot is risky on 3rd/4th & medium",
            )

    elif situation_key == "money_down_long":
        if "pure_run" in tags and "draw" not in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["long_run_penalty"],
                "situation penalty: pure run on 3rd/4th & long is strongly discouraged",
            )
        if tags & {"attacks_sticks", "screen"}:
            score += add_score_reason(
                reasons,
                5.0,
                "situation fit: 3rd/4th & long favors concepts attacking the sticks or using screens",
            )
        if "pressure_answer" in tags and "quick_game" in tags:
            score += add_score_reason(
                reasons,
                2.5,
                "situation fit: quick answers can still help on 3rd/4th & long",
            )

    elif situation_key == "money_down_very_long":
        if "pure_run" in tags and "draw" not in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["very_long_run_penalty"],
                "situation penalty: pure run on 3rd/4th & very long is near-disqualifying",
            )
        if tags & {"attacks_sticks", "screen"}:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["attacks_sticks"],
                "situation fit: 3rd/4th & very long favors pass concepts attacking the sticks",
            )
        if "quick_game" in tags and "attacks_sticks" not in tags:
            score += add_score_reason(
                reasons,
                1.5,
                "situation fit: quick game is a better answer than a pure run on 3rd/4th & very long",
            )

    if territory == "backed_up":
        if tags & {"safe_call", "quick_game", "screen"} or "pure_run" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["backed_up_safe_call"],
                "territory fit: backed-up offense favors safe field-position calls",
            )
        if "shot" in tags or ("slow_developing" in tags and "play_action" not in tags):
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["backed_up_risk_penalty"],
                "territory penalty: backed-up offense should avoid risky deep or slow-developing calls",
            )

    elif territory == "plus_territory":
        if tags & {"shot", "play_action", "attacks_sticks"}:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["plus_territory_aggression"],
                "territory fit: plus territory allows a bit more aggression",
            )

    elif territory == "red_zone":
        if tags & {"red_zone", "goal_line", "inside_run", "quick_game", "play_action"}:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["red_zone_boost"],
                "territory fit: red zone favors condensed-space concepts",
            )
        if "vertical" in tags or "shot" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["red_zone_space_penalty"],
                "territory penalty: red zone limits deep-vertical spacing concepts",
            )

    elif territory == "goal_line":
        if tags & {"goal_line", "inside_run", "short_yardage", "quick_game", "play_action"}:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["goal_line_boost"],
                "territory fit: goal line favors condensed, high-percentage concepts",
            )
        if "vertical" in tags or "shot" in tags:
            score += add_score_reason(
                reasons,
                SITUATION_SCORE_WEIGHTS["goal_line_bad_space_penalty"],
                "territory penalty: goal line is a poor place for deep-space concepts",
            )

    return score, reasons


def score_matchup_fit(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score secondary matchup information such as coverage, front, and box."""
    score = 0.0
    reasons: list[str] = []

    front_values = parse_list(play_series_value(play, "beats_front"))
    if matches_category(front_values, str(situation["front_id"])):
        score += add_score_reason(
            reasons,
            MATCHUP_SCORE_WEIGHTS["front_match"],
            f"front fit: workable against {situation['front_id']}",
        )

    coverage_values = parse_list(play_series_value(play, "beats_coverage"))
    if matches_category(coverage_values, str(situation["coverage_id"])):
        score += add_score_reason(
            reasons,
            MATCHUP_SCORE_WEIGHTS["coverage_match"],
            f"coverage fit: strong versus {situation['coverage_id']}",
        )

    box_values = parse_list(play_series_value(play, "beats_box"))
    if matches_category(box_values, str(situation["box_label"])):
        score += add_score_reason(
            reasons,
            MATCHUP_SCORE_WEIGHTS["box_match"],
            f"box fit: favorable into {situation['box_label']}",
        )

    if play_series_value(play, "formation_id") == str(situation["formation_id"]):
        score += add_score_reason(
            reasons,
            MATCHUP_SCORE_WEIGHTS["formation_match"],
            f"formation fit: call is available from {situation['formation_id']}",
        )

    preferred_distance_values = parse_list(play_series_value(play, "preferred_down_distance"))
    playbook_distance = {
        "very_long" if value == "xlong" else value for value in preferred_distance_values
    }
    if matches_category(list(playbook_distance), str(situation["distance_bucket"])):
        score += add_score_reason(
            reasons,
            MATCHUP_SCORE_WEIGHTS["distance_match"],
            f"playbook fit: tagged for {describe_distance_bucket(str(situation['distance_bucket']))} distance",
        )

    preferred_field_zone_values = parse_list(play_series_value(play, "preferred_field_zone"))
    normalized_field_zone_values = [
        FIELD_ZONE_TO_PLAYBOOK_VALUE.get(value, value) for value in preferred_field_zone_values
    ]
    if matches_category(normalized_field_zone_values, str(situation["field_zone"])):
        score += add_score_reason(
            reasons,
            MATCHUP_SCORE_WEIGHTS["field_zone_match"],
            f"playbook fit: tagged for {situation['territory_label']}",
        )

    return score, reasons


def score_play(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score a play against the current situation and collect explainable reasons."""
    situational_score, situational_reasons = score_situational_fit(play, situation)
    matchup_score, matchup_reasons = score_matchup_fit(play, situation)
    return situational_score + matchup_score, [*situational_reasons, *matchup_reasons]


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

    tags = infer_play_tags(play)
    adjustment = 0.0
    reasons: list[str] = []

    coverage_probabilities = tendencies.get("coverage")
    if coverage_probabilities:
        for coverage_id in parse_list(play_series_value(play, "beats_coverage")):
            if coverage_id in {"any", "none"}:
                continue
            probability = float(coverage_probabilities.get(coverage_id, 0.0))
            if probability > 0:
                delta = probability * TENDENCY_SCORE_WEIGHTS["coverage_match"]
                adjustment += add_score_reason(
                    reasons,
                    delta,
                    f"tendency boost: opponent shows {coverage_id} often in this situation",
                )

    box_probabilities = aggregate_box_probabilities(tendencies.get("box_count"))
    play_box_values = parse_list(play_series_value(play, "beats_box"))
    for box_label in ("light_box", "neutral_box", "heavy_box", "loaded_box"):
        probability = box_probabilities.get(box_label, 0.0)
        if probability > 0 and box_label in play_box_values:
            delta = probability * TENDENCY_SCORE_WEIGHTS["box_match"]
            adjustment += add_score_reason(
                reasons,
                delta,
                f"tendency boost: opponent leans to {box_label}",
            )

    pressure_probabilities = tendencies.get("pressure")
    pressure_yes_probability = 0.0
    if pressure_probabilities:
        pressure_yes_probability = float(pressure_probabilities.get("yes", 0.0))

    if pressure_yes_probability > 0 and "pressure_answer" in tags:
        delta = pressure_yes_probability * TENDENCY_SCORE_WEIGHTS["pressure_answer"]
        adjustment += add_score_reason(
            reasons,
            delta,
            "tendency boost: pressure profile favors quick answers, screens, and RPOs",
        )

    if pressure_yes_probability > 0 and "slow_developing" in tags and "pressure_answer" not in tags:
        delta = pressure_yes_probability * TENDENCY_SCORE_WEIGHTS["pressure_risk"]
        adjustment += add_score_reason(
            reasons,
            delta,
            "pressure risk: long-developing concept against likely pressure",
        )

    heavy_box_probability = (
        box_probabilities.get("heavy_box", 0.0)
        + box_probabilities.get("loaded_box", 0.0)
    )
    light_box_probability = box_probabilities.get("light_box", 0.0)

    if "pure_run" in tags:
        if heavy_box_probability > 0:
            delta = heavy_box_probability * TENDENCY_SCORE_WEIGHTS["heavy_box_run"]
            adjustment += add_score_reason(
                reasons,
                delta,
                "tendency penalty: heavy box look reduces pure run value",
            )
        if light_box_probability > 0:
            delta = light_box_probability * TENDENCY_SCORE_WEIGHTS["light_box_run"]
            adjustment += add_score_reason(
                reasons,
                delta,
                "tendency boost: light box improves viable runs",
            )
    elif {"screen", "rpo", "attacks_sticks"} & tags and heavy_box_probability > 0:
        delta = heavy_box_probability * TENDENCY_SCORE_WEIGHTS["heavy_box_pass"]
        adjustment += add_score_reason(
            reasons,
            delta,
            "tendency boost: heavy box invites pass or RPO answers",
        )

    return adjustment, reasons


def apply_guardrail_adjustments(
    play: pd.Series,
    situation: Situation,
    viable_alternatives_exist: bool,
) -> tuple[float, list[str]]:
    """Apply explicit penalties for nonsensical top-call candidates."""
    tags = infer_play_tags(play)
    situation_key = str(situation["combined_situation"])
    territory = str(situation["territory"])
    adjustment = 0.0
    reasons: list[str] = []

    if viable_alternatives_exist and "pure_run" in tags and "draw" not in tags:
        if situation_key == "money_down_very_long":
            adjustment += add_score_reason(
                reasons,
                GUARDRAIL_SCORE_WEIGHTS["money_very_long_pure_run"],
                "guardrail: pure runs cannot be top calls on 3rd/4th & very long when pass answers exist",
            )
        elif situation_key == "money_down_long":
            adjustment += add_score_reason(
                reasons,
                GUARDRAIL_SCORE_WEIGHTS["money_long_pure_run"],
                "guardrail: pure runs are kept below pass answers on 3rd/4th & long",
            )

    if viable_alternatives_exist and territory == "backed_up" and "shot" in tags and "play_action" not in tags:
        adjustment += add_score_reason(
            reasons,
            GUARDRAIL_SCORE_WEIGHTS["backed_up_shot"],
            "guardrail: backed-up territory should not prioritize deep low-percentage shots",
        )

    if territory in {"red_zone", "goal_line"} and "vertical" in tags:
        adjustment += add_score_reason(
            reasons,
            GUARDRAIL_SCORE_WEIGHTS["red_zone_vertical"],
            "guardrail: condensed field removes most deep vertical value here",
        )

    return adjustment, reasons


def has_viable_non_run_alternative(playbook: pd.DataFrame, situation: Situation) -> bool:
    """Check whether the playbook contains pass/RPO/screen answers for the situation."""
    situation_key = str(situation["combined_situation"])
    if situation_key not in {"money_down_long", "money_down_very_long"}:
        return False

    for _, play in playbook.iterrows():
        tags = infer_play_tags(play)
        if "pure_run" not in tags:
            return True
        if "draw" in tags or "safe_call" in tags:
            return True
    return False


def recommend_plays(
    playbook: pd.DataFrame,
    situation: Situation,
    *,
    tendencies: TendencySnapshot | None = None,
    limit: int = 3,
) -> list[dict[str, object]]:
    """Score a playbook and return ranked recommendations."""
    recommendations: list[dict[str, object]] = []
    viable_alternatives_exist = has_viable_non_run_alternative(playbook, situation)

    for _, play in playbook.iterrows():
        base_score, base_reasons = score_play(play, situation)
        tendency_adjustment, tendency_reasons = apply_tendency_adjustments(
            play, tendencies
        )
        guardrail_adjustment, guardrail_reasons = apply_guardrail_adjustments(
            play, situation, viable_alternatives_exist
        )
        total_score = float(base_score) + tendency_adjustment + guardrail_adjustment

        recommendations.append(
            {
                "play_name": play_series_value(play, "play_name"),
                "play_id": play_series_value(play, "play_id"),
                "score": total_score,
                "base_score": base_score,
                "tendency_adjustment": tendency_adjustment,
                "guardrail_adjustment": guardrail_adjustment,
                "reasons": [*base_reasons, *tendency_reasons, *guardrail_reasons],
                "used_tendencies": tendencies is not None,
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
