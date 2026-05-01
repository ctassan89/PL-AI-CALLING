"""Explainable football-coherent recommendation engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

import pandas as pd


Situation = Mapping[str, Any]
TendencySnapshot = Mapping[str, Mapping[str, float]]


class Recommendation(TypedDict, total=False):
    """Structured recommendation payload for scoring and ranking."""

    play_id: str
    play_name: str
    score: float
    base_score: float
    tendency_adjustment: float
    reasons: list[str]
    formation_id: str
    personnel: str
    play_type: str
    concept_scheme: str
    component_scores: dict[str, float]
    tie_breakers: dict[str, Any]
    used_tendencies: bool


FIELD_ZONE_ALIASES = {
    "midfield": "open_field",
    "own_territory": "open_field",
    "opp_territory": "open_field",
    "open_field": "open_field",
    "high_red_zone": "high_redzone",
    "high_redzone": "high_redzone",
    "red_zone": "redzone",
    "redzone": "redzone",
    "goal_line": "goal_line",
    "own_redzone": "high_redzone",
}

RELATED_ZONES = {
    "high_redzone": {"redzone"},
    "redzone": {"high_redzone", "goal_line"},
    "goal_line": {"redzone"},
    "open_field": set(),
}

COVERAGE_FAMILY = {
    "cover0": {"man"},
    "cover1": {"man"},
    "cover2": {"zone"},
    "cover3": {"zone"},
    "cover4": {"zone", "match"},
    "cover4_quarters": {"zone", "match"},
    "soft_zone": {"zone"},
    "match": {"match"},
    "man": {"man"},
    "zone": {"zone"},
}

RELATED_BOXES = {
    "light_box": {"normal_box"},
    "normal_box": {"light_box"},
    "heavy_box": {"loaded_box"},
    "loaded_box": {"heavy_box"},
    "neutral_box": {"light_box"},
}

SHORT_TAGS = {"third_short", "fourth_short", "second_short"}
MEDIUM_LONG_TAGS = {
    "second_medium",
    "second_long",
    "third_medium",
    "third_long",
    "fourth_medium",
}
SLOW_DEVELOPING_CONCEPTS = {"flood", "four_verts", "verts", "dagger", "y_cross", "levels"}
DEEP_SHOT_CONCEPTS = {"four_verts", "verts", "post", "go", "mills"}
QUICK_GAME_CONCEPTS = {"slant_flat", "spacing", "stick", "curl_flat", "snag", "hitch", "mesh"}
SCREEN_CONCEPTS = {"screen", "screens", "now_screen", "bubble"}
GAP_SCHEMES = {"duo", "power", "counter", "trap", "iso", "pin_pull"}
ZONE_SCHEMES = {"inside_zone", "outside_zone", "wide_zone", "stretch"}
PERIMETER_RUN_SCHEMES = {"outside_zone", "wide_zone", "jet", "toss", "sweep"}
INSIDE_RUN_SCHEMES = {"inside_zone", "duo", "power", "counter", "trap", "iso"}


def normalize_text(value: object) -> str:
    """Normalize a free-form value for comparisons."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "" if text == "nan" else text


def parse_list(value: object) -> list[str]:
    """Split a semicolon-separated field into normalized values."""
    text = normalize_text(value)
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def parse_numeric(value: object) -> int | None:
    """Parse an integer when possible."""
    text = normalize_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def play_series_value(play: pd.Series, column_name: str, default: str = "") -> str:
    """Safely read a play field from a Series."""
    if column_name not in play.index:
        return default
    value = play[column_name]
    if pd.isna(value):
        return default
    return str(value)


def add_reason(reasons: list[str], delta: float, text: str) -> float:
    """Record an explainable score reason."""
    reasons.append(f"{delta:+.0f} {text}")
    return delta


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value."""
    return max(minimum, min(value, maximum))


def normalize_field_zone(field_zone: object) -> str:
    """Normalize field-zone aliases into the engine vocabulary."""
    key = normalize_text(field_zone)
    normalized = FIELD_ZONE_ALIASES.get(key)
    if normalized is None:
        raise ValueError(f"Unsupported field zone value: {field_zone}")
    return normalized


def box_label_from_count(box_count: int) -> str:
    """Map numeric box count to the engine box labels."""
    if box_count <= 5:
        return "light_box"
    if box_count == 6:
        return "normal_box"
    if box_count == 7:
        return "heavy_box"
    return "loaded_box"


def normalize_box_label(value: object) -> str:
    """Normalize playbook box labels."""
    key = normalize_text(value)
    if key == "neutral_box":
        return "normal_box"
    return key


def classify_distance_bucket(distance: object) -> tuple[str, int | None]:
    """Normalize raw distance into short/medium/long."""
    numeric_distance = parse_numeric(distance)
    if numeric_distance is not None:
        if numeric_distance <= 3:
            return "short", numeric_distance
        if numeric_distance <= 7:
            return "medium", numeric_distance
        return "long", numeric_distance

    key = normalize_text(distance).replace("-", "_")
    aliases = {
        "short": "short",
        "medium": "medium",
        "long": "long",
        "xlong": "long",
        "very_long": "long",
    }
    bucket = aliases.get(key)
    if bucket is None:
        raise ValueError(f"Unsupported distance value: {distance}")
    return bucket, None


def classify_down_distance_tag(down: int, distance_bucket: str) -> str:
    """Map down and distance to the required down-distance tag."""
    if down == 1:
        return "early_down"
    if down == 2:
        return {
            "short": "second_short",
            "medium": "second_medium",
            "long": "second_long",
        }[distance_bucket]
    if down == 3:
        return {
            "short": "third_short",
            "medium": "third_medium",
            "long": "third_long",
        }[distance_bucket]
    if down == 4:
        return "fourth_short" if distance_bucket == "short" else "fourth_medium"
    raise ValueError(f"Unsupported down value: {down}")


def build_situation(
    *,
    down: int | str,
    distance: str | int,
    field_zone: str,
    formation_id: str | None = None,
    front_id: str | None = None,
    coverage_id: str | None = None,
    box_count: int | str | None = None,
    personnel: str | None = None,
    opponent: str | None = None,
) -> dict[str, str | int]:
    """Create the normalized situation payload used by the recommender."""
    numeric_down = parse_numeric(down)
    if numeric_down is None:
        raise ValueError(f"Unsupported down value: {down}")

    distance_bucket, raw_distance = classify_distance_bucket(distance)
    normalized_field_zone = normalize_field_zone(field_zone)

    situation: dict[str, str | int] = {
        "down": numeric_down,
        "distance": raw_distance if raw_distance is not None else str(distance),
        "distance_bucket": distance_bucket,
        "down_distance_tag": classify_down_distance_tag(numeric_down, distance_bucket),
        "field_zone": normalized_field_zone,
    }

    if formation_id is not None:
        situation["formation_id"] = normalize_text(formation_id)
    if front_id is not None:
        situation["front_id"] = normalize_text(front_id)
    if coverage_id is not None:
        situation["coverage_id"] = normalize_text(coverage_id)
        families = sorted(COVERAGE_FAMILY.get(normalize_text(coverage_id), set()))
        if families:
            situation["coverage_family"] = ";".join(families)
    if box_count is not None:
        numeric_box = int(box_count)
        situation["box_count"] = numeric_box
        situation["box_label"] = box_label_from_count(numeric_box)
    if personnel is not None:
        situation["personnel"] = normalize_text(personnel)
    if opponent is not None:
        situation["opponent"] = str(opponent)
    return situation


def infer_play_tags(play: pd.Series) -> set[str]:
    """Build normalized semantic tags from the play schema."""
    tags = set(parse_list(play_series_value(play, "tags")))
    play_type = normalize_text(play_series_value(play, "play_type"))
    play_family = normalize_text(play_series_value(play, "play_family"))
    run_scheme = normalize_text(play_series_value(play, "run_scheme"))
    run_modifier = normalize_text(play_series_value(play, "run_modifier"))
    pass_concept = normalize_text(play_series_value(play, "pass_concept"))
    pass_modifier = normalize_text(play_series_value(play, "pass_modifier"))
    protection = normalize_text(play_series_value(play, "protection"))
    rpo_tag = normalize_text(play_series_value(play, "rpo_tag"))
    play_action = normalize_text(play_series_value(play, "play_action")) == "true"

    for value in {
        play_type,
        play_family,
        run_scheme,
        run_modifier,
        pass_concept,
        pass_modifier,
        protection,
    }:
        if value and value != "none":
            tags.add(value)

    if play_type == "run":
        tags.add("run")
    if play_type == "pass":
        tags.add("pass")
    if play_type == "screen" or play_family == "screen" or pass_concept in SCREEN_CONCEPTS:
        tags.update({"screen", "quick_game"})
    if pass_concept in QUICK_GAME_CONCEPTS:
        tags.add("quick_game")
    if run_scheme in GAP_SCHEMES:
        tags.add("gap_scheme")
    if run_scheme in ZONE_SCHEMES:
        tags.add("zone_run")
    if run_scheme in INSIDE_RUN_SCHEMES or "inside_run" in tags:
        tags.add("inside_run")
    if run_scheme in PERIMETER_RUN_SCHEMES or "outside_run" in tags or "perimeter_run" in tags:
        tags.add("perimeter_run")
    if rpo_tag and rpo_tag != "none":
        tags.update({"rpo", rpo_tag})
    if play_action:
        tags.add("play_action")
    if pass_concept in DEEP_SHOT_CONCEPTS or "deep_shot" in tags or "shot" in tags or "vertical" in tags:
        tags.add("deep_shot")
    if pass_concept in SLOW_DEVELOPING_CONCEPTS or "slow_developing" in tags:
        tags.add("slow_developing")
    if "red_zone" in tags:
        tags.add("redzone")
    if "man_beater" in tags or pass_concept == "mesh":
        tags.add("man_beater")
    if "zone_beater" in tags:
        tags.add("zone_beater")
    return tags


def normalize_preferred_down_distance(play: pd.Series) -> set[str]:
    """Normalize playbook down-distance values."""
    values = set(parse_list(play_series_value(play, "preferred_down_distance")))
    normalized: set[str] = set()
    for value in values:
        if value == "xlong":
            normalized.add("long")
        else:
            normalized.add(value)
    return normalized


def normalize_preferred_field_zones(play: pd.Series) -> set[str]:
    """Normalize playbook field-zone values."""
    values = set(parse_list(play_series_value(play, "preferred_field_zone")))
    normalized: set[str] = set()
    for value in values:
        if value == "any":
            normalized.add("any")
            continue
        normalized.add(normalize_field_zone(value))
    return normalized


def normalize_beats_box(play: pd.Series) -> set[str]:
    """Normalize playbook box answers."""
    return {normalize_box_label(value) for value in parse_list(play_series_value(play, "beats_box"))}


def exact_down_distance_match(play: pd.Series, situation: Situation) -> bool:
    """Return whether the play has an exact down-distance tag match."""
    return str(situation["down_distance_tag"]) in normalize_preferred_down_distance(play)


def exact_field_zone_match(play: pd.Series, situation: Situation) -> bool:
    """Return whether the play has an exact field-zone match."""
    return str(situation["field_zone"]) in normalize_preferred_field_zones(play)


def exact_defensive_match_count(play: pd.Series, situation: Situation) -> int:
    """Count exact front, coverage, and box matches for tie-breaking."""
    count = 0
    front_id = normalize_text(situation.get("front_id"))
    coverage_id = normalize_text(situation.get("coverage_id"))
    box_label = normalize_text(situation.get("box_label"))
    if front_id and front_id in parse_list(play_series_value(play, "beats_front")):
        count += 1
    if coverage_id and coverage_id in parse_list(play_series_value(play, "beats_coverage")):
        count += 1
    if box_label and box_label in normalize_beats_box(play):
        count += 1
    return count


def score_down_distance(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score situational fit for down and distance."""
    preferred = normalize_preferred_down_distance(play)
    tag = str(situation["down_distance_tag"])
    down = int(situation["down"])
    bucket = str(situation["distance_bucket"])
    reasons: list[str] = []

    if tag in preferred:
        return 30.0, [f"+30 down-distance: exact match {tag}"]

    if tag == "third_short":
        if "fourth_short" in preferred:
            return 22.0, ["+22 down-distance: fourth_short is compatible with third_short"]
        if "second_short" in preferred:
            return 18.0, ["+18 down-distance: second_short is compatible with third_short"]
    if tag == "fourth_short" and "third_short" in preferred:
        return 22.0, ["+22 down-distance: third_short is compatible with fourth_short"]

    if "early_down" in preferred:
        if down == 1:
            return 30.0, ["+30 down-distance: early_down fit on 1st down"]
        if down == 2:
            return 24.0, ["+24 down-distance: early_down remains strong on 2nd down"]
        return 8.0, [f"+8 down-distance: early_down has limited carryover on down {down}"]

    if bucket in preferred or (
        bucket in {"medium", "long"}
        and preferred & MEDIUM_LONG_TAGS
    ):
        return 15.0, [f"+15 down-distance: related {bucket} situation fit"]

    tags = infer_play_tags(play)
    if tag == "third_short" and "third_long" in preferred:
        return -10.0, ["-10 down-distance: third_long play is a bad mismatch for third_short"]
    if tag == "fourth_short" and "deep_shot" in tags:
        return -15.0, ["-15 down-distance: deep_shot is a poor fourth_short answer"]
    if tag == "third_long" and (
        "early_down" in preferred or "short" in preferred or preferred & SHORT_TAGS
    ):
        return -12.0, ["-12 down-distance: short-yardage profile is a bad mismatch for third_long"]

    return 0.0, []


def score_field_zone(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score territory fit."""
    preferred = normalize_preferred_field_zones(play)
    field_zone = str(situation["field_zone"])

    if field_zone in preferred:
        return 20.0, [f"+20 field-zone: exact match {field_zone}"]
    if "any" in preferred:
        return 9.0, ["+9 field-zone: any zone flexibility"]
    if preferred & RELATED_ZONES.get(field_zone, set()):
        return 12.0, [f"+12 field-zone: related zone fit for {field_zone}"]
    if preferred and "open_field" not in preferred:
        return -8.0, [f"-8 field-zone: mismatch for {field_zone}"]
    return 0.0, []


def coverage_families(value: str) -> set[str]:
    """Return normalized coverage families for a label."""
    return set(COVERAGE_FAMILY.get(value, set()))


def score_defensive_structure(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score front, coverage, and box fit."""
    score = 0.0
    reasons: list[str] = []

    front_id = normalize_text(situation.get("front_id"))
    if front_id:
        front_values = parse_list(play_series_value(play, "beats_front"))
        if front_id in front_values:
            score += add_reason(reasons, 7.0, f"front: beats {front_id}")
        elif "any" in front_values:
            score += add_reason(reasons, 3.0, f"front: any front answer includes {front_id}")

    coverage_id = normalize_text(situation.get("coverage_id"))
    if coverage_id:
        coverage_values = parse_list(play_series_value(play, "beats_coverage"))
        if coverage_id in coverage_values:
            score += add_reason(reasons, 7.0, f"coverage: exact {coverage_id} match")
        else:
            situation_families = coverage_families(coverage_id)
            family_match = sorted(
                value
                for value in coverage_values
                if coverage_families(value) & situation_families or value in situation_families
            )
            if family_match:
                score += add_reason(
                    reasons,
                    4.0,
                    f"coverage: family match via {family_match[0]}",
                )
            elif "any" in coverage_values:
                score += add_reason(reasons, 2.0, "coverage: any coverage answer")

    box_label = normalize_text(situation.get("box_label"))
    if box_label:
        box_values = normalize_beats_box(play)
        if box_label in box_values:
            score += add_reason(reasons, 6.0, f"box: exact {box_label} match")
        elif box_values & RELATED_BOXES.get(box_label, set()):
            score += add_reason(reasons, 3.0, f"box: related fit for {box_label}")

    return score, reasons


def score_tactical_fit(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score tactical football fit from play traits and situation context."""
    score = 0.0
    reasons: list[str] = []
    tags = infer_play_tags(play)
    field_zone = str(situation["field_zone"])
    down_distance_tag = str(situation["down_distance_tag"])
    coverage_id = normalize_text(situation.get("coverage_id"))
    box_label = normalize_text(situation.get("box_label"))
    pass_concept = normalize_text(play_series_value(play, "pass_concept"))
    run_scheme = normalize_text(play_series_value(play, "run_scheme"))
    rpo_tag = normalize_text(play_series_value(play, "rpo_tag"))

    is_short = down_distance_tag in {"second_short", "third_short", "fourth_short"}
    is_redzone = field_zone == "redzone"
    is_goal_line = field_zone == "goal_line"

    if is_short:
        if "inside_run" in tags:
            score += add_reason(reasons, 4.0, "tactical: inside_run fits short yardage")
        if "gap_scheme" in tags:
            score += add_reason(reasons, 4.0, "tactical: gap_scheme fits short yardage")
        if "quick_game" in tags:
            score += add_reason(reasons, 3.0, "tactical: quick_game fits short yardage")
        if rpo_tag and rpo_tag != "none":
            score += add_reason(reasons, 3.0, "tactical: rpo is useful in short yardage")
        if "play_action" in tags and "deep_shot" not in tags and "slow_developing" not in tags:
            score += add_reason(reasons, 2.0, "tactical: play_action is viable in short yardage")
        if "deep_shot" in tags:
            score += add_reason(reasons, -6.0, "tactical: deep_shot is risky in short yardage")
        if "slow_developing" in tags:
            score += add_reason(reasons, -5.0, "tactical: slow_developing call hurts short yardage")

    if is_redzone:
        if "redzone" in tags:
            score += add_reason(reasons, 4.0, "tactical: redzone tag fits condensed field")
        if "quick_game" in tags:
            score += add_reason(reasons, 3.0, "tactical: quick_game is useful in redzone")
        if "inside_run" in tags:
            score += add_reason(reasons, 3.0, "tactical: inside_run works in redzone")
        if "play_action" in tags:
            score += add_reason(reasons, 3.0, "tactical: play_action stresses redzone defenders")
        if rpo_tag and rpo_tag != "none":
            score += add_reason(reasons, 3.0, "tactical: rpo is useful in redzone")
        if {"rub", "man_beater"} & tags:
            score += add_reason(reasons, 3.0, "tactical: rub/man_beater traits help in redzone")
        if "deep_shot" in tags:
            score += add_reason(reasons, -6.0, "tactical: deep_shot is risky in redzone")
        if "slow_developing" in tags:
            score += add_reason(reasons, -5.0, "tactical: slow_developing concept is tough in redzone")

    if is_goal_line:
        if "inside_run" in tags:
            score += add_reason(reasons, 5.0, "tactical: inside_run fits goal_line")
        if "gap_scheme" in tags:
            score += add_reason(reasons, 4.0, "tactical: gap_scheme fits goal_line")
        if "quick_game" in tags:
            score += add_reason(reasons, 4.0, "tactical: quick_game fits goal_line")
        if "play_action" in tags:
            score += add_reason(reasons, 3.0, "tactical: play_action can punish goal_line trigger")
        if rpo_tag and rpo_tag != "none":
            score += add_reason(reasons, 3.0, "tactical: rpo is viable at goal_line")
        if "deep_shot" in tags:
            score += add_reason(reasons, -8.0, "tactical: deep_shot is a poor goal_line answer")

    if box_label in {"heavy_box", "loaded_box"}:
        if "play_action" in tags:
            score += add_reason(reasons, 4.0, f"tactical: play_action is useful against {box_label}")
        if rpo_tag and rpo_tag != "none":
            score += add_reason(reasons, 4.0, f"tactical: rpo is useful against {box_label}")
        if "perimeter_run" in tags:
            score += add_reason(reasons, 3.0, f"tactical: perimeter_run can punish {box_label}")
        if "quick_game" in tags:
            score += add_reason(reasons, 3.0, f"tactical: quick_game is useful against {box_label}")
        if "screen" in tags:
            score += add_reason(reasons, 3.0, f"tactical: screen is useful against {box_label}")
        if "inside_run" in tags and not (normalize_beats_box(play) & {"heavy_box", "loaded_box"}):
            score += add_reason(reasons, -4.0, f"tactical: inside_run lacks proven fit versus {box_label}")

    if box_label == "light_box":
        if "inside_run" in tags:
            score += add_reason(reasons, 5.0, "tactical: inside_run should attack a light_box")
        if "gap_scheme" in tags:
            score += add_reason(reasons, 4.0, "tactical: gap_scheme can punish a light_box")
        if "zone_run" in tags:
            score += add_reason(reasons, 3.0, "tactical: zone_run is useful versus a light_box")
        if run_scheme in {"power", "counter"}:
            score += add_reason(reasons, 3.0, f"tactical: {run_scheme} fits a light_box")

    if coverage_id == "cover3":
        if pass_concept == "flood" or "flood" in tags:
            score += add_reason(reasons, 3.0, "tactical: flood is strong versus cover3")
        if pass_concept == "curl_flat" or "curl_flat" in tags:
            score += add_reason(reasons, 3.0, "tactical: curl_flat is strong versus cover3")
        if pass_concept == "seams" or "seams" in tags:
            score += add_reason(reasons, 3.0, "tactical: seams can stress cover3")
        if "play_action" in tags:
            score += add_reason(reasons, 2.0, "tactical: play_action can help versus cover3")

    coverage_fams = coverage_families(coverage_id)
    if "man" in coverage_fams or coverage_id in {"cover0", "cover1", "man"}:
        if pass_concept == "mesh" or "mesh" in tags:
            score += add_reason(reasons, 4.0, "tactical: mesh is strong versus man")
        if "rub" in tags:
            score += add_reason(reasons, 4.0, "tactical: rub concept fits man coverage")
        if "man_beater" in tags:
            score += add_reason(reasons, 4.0, "tactical: man_beater traits fit man coverage")
        if "quick_game" in tags:
            score += add_reason(reasons, 3.0, "tactical: quick_game is useful versus man")

    if "zone" in coverage_fams or coverage_id in {"cover2", "cover3", "soft_zone", "zone"}:
        if "zone_beater" in tags:
            score += add_reason(reasons, 3.0, "tactical: zone_beater traits fit zone coverage")
        if pass_concept == "spacing" or "spacing" in tags:
            score += add_reason(reasons, 3.0, "tactical: spacing fits zone coverage")
        if pass_concept == "curl_flat" or "curl_flat" in tags:
            score += add_reason(reasons, 3.0, "tactical: curl_flat fits zone coverage")
        if pass_concept == "snag" or "snag" in tags:
            score += add_reason(reasons, 3.0, "tactical: snag fits zone coverage")

    if coverage_id == "cover0":
        if "quick_game" in tags:
            score += add_reason(reasons, 5.0, "tactical: quick_game is critical versus cover0")
        if "man_beater" in tags:
            score += add_reason(reasons, 5.0, "tactical: man_beater traits help versus cover0")
        if "screen" in tags:
            score += add_reason(reasons, 4.0, "tactical: screen can punish cover0 pressure")
        if "slow_developing" in tags:
            score += add_reason(reasons, -8.0, "tactical: slow_developing concept is dangerous versus cover0")

    return clamp(score, -10.0, 15.0), reasons


def score_formation_personnel(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score formation and personnel alignment."""
    score = 0.0
    reasons: list[str] = []
    play_personnel = normalize_text(play_series_value(play, "personnel"))
    play_formation = normalize_text(play_series_value(play, "formation_id"))
    situation_personnel = normalize_text(situation.get("personnel"))
    situation_formation = normalize_text(situation.get("formation_id"))

    if situation_personnel:
        if play_personnel == situation_personnel:
            score += add_reason(reasons, 5.0, f"formation/personnel: personnel match {situation_personnel}")
        else:
            score += add_reason(reasons, -3.0, f"formation/personnel: personnel mismatch vs {situation_personnel}")

    if situation_formation:
        if play_formation == situation_formation:
            score += add_reason(reasons, 5.0, f"formation/personnel: formation match {situation_formation}")
        else:
            score += add_reason(reasons, -8.0, f"formation/personnel: formation mismatch vs {situation_formation}")

    return score, reasons


def score_risk_reward(play: pd.Series, situation: Situation) -> tuple[float, list[str]]:
    """Score risk/reward profile for the situation."""
    score = 0.0
    reasons: list[str] = []
    tags = infer_play_tags(play)
    down_distance_tag = str(situation["down_distance_tag"])
    field_zone = str(situation["field_zone"])

    if down_distance_tag in {"third_short", "fourth_short"}:
        if {"inside_run", "quick_game", "rpo", "gap_scheme"} & tags:
            score += add_reason(reasons, 3.0, "risk-reward: efficient answer for short conversion")
        if "deep_shot" in tags:
            score += add_reason(reasons, -5.0, "risk-reward: deep_shot is too volatile here")

    if int(situation["down"]) == 1 and field_zone == "open_field":
        if "play_action" in tags:
            score += add_reason(reasons, 3.0, "risk-reward: play_action is attractive on 1st down open field")
        if "deep_shot" in tags:
            score += add_reason(reasons, 2.0, "risk-reward: deep_shot is acceptable on 1st down open field")

    if field_zone == "redzone":
        if {"quick_game", "rpo", "play_action"} & tags:
            score += add_reason(reasons, 3.0, "risk-reward: efficient redzone profile")
        if "deep_shot" in tags:
            score += add_reason(reasons, -4.0, "risk-reward: deep_shot loses value in redzone")

    if field_zone == "goal_line":
        if {"inside_run", "quick_game", "rpo"} & tags:
            score += add_reason(reasons, 4.0, "risk-reward: high-percentage goal_line profile")
        if "deep_shot" in tags:
            score += add_reason(reasons, -5.0, "risk-reward: deep_shot is a poor goal_line gamble")

    return clamp(score, -5.0, 5.0), reasons


def score_play(play: pd.Series, situation: Situation) -> Recommendation:
    """Score a play with component breakdown and explainable reasons."""
    down_distance_score, down_distance_reasons = score_down_distance(play, situation)
    field_zone_score, field_zone_reasons = score_field_zone(play, situation)
    defensive_structure_score, defensive_structure_reasons = score_defensive_structure(
        play, situation
    )
    tactical_fit_score, tactical_fit_reasons = score_tactical_fit(play, situation)
    formation_personnel_score, formation_personnel_reasons = score_formation_personnel(
        play, situation
    )
    risk_reward_score, risk_reward_reasons = score_risk_reward(play, situation)

    base_score = clamp(
        down_distance_score
        + field_zone_score
        + defensive_structure_score
        + tactical_fit_score
        + formation_personnel_score
        + risk_reward_score,
        0.0,
        100.0,
    )
    reasons = [
        *down_distance_reasons,
        *field_zone_reasons,
        *defensive_structure_reasons,
        *tactical_fit_reasons,
        *formation_personnel_reasons,
        *risk_reward_reasons,
    ]

    concept_scheme = normalize_text(play_series_value(play, "pass_concept"))
    if not concept_scheme or concept_scheme == "none":
        concept_scheme = normalize_text(play_series_value(play, "run_scheme"))

    return Recommendation(
        play_id=play_series_value(play, "play_id"),
        play_name=play_series_value(play, "play_name"),
        score=base_score,
        base_score=base_score,
        reasons=reasons,
        formation_id=play_series_value(play, "formation_id"),
        personnel=play_series_value(play, "personnel"),
        play_type=play_series_value(play, "play_type"),
        concept_scheme=concept_scheme,
        component_scores={
            "down_distance": down_distance_score,
            "field_zone": field_zone_score,
            "defensive_structure": defensive_structure_score,
            "tactical_fit": tactical_fit_score,
            "formation_personnel": formation_personnel_score,
            "risk_reward": risk_reward_score,
        },
        tie_breakers={
            "exact_down_distance_match": exact_down_distance_match(play, situation),
            "exact_field_zone_match": exact_field_zone_match(play, situation),
            "exact_defensive_structure_match_count": exact_defensive_match_count(
                play, situation
            ),
            "tactical_fit_score": tactical_fit_score,
        },
        used_tendencies=False,
    )


def aggregate_box_probabilities(
    probabilities: Mapping[str, float] | None,
) -> dict[str, float]:
    """Normalize box-count probabilities into the engine box labels."""
    aggregated = {
        "light_box": 0.0,
        "normal_box": 0.0,
        "heavy_box": 0.0,
        "loaded_box": 0.0,
    }
    if not probabilities:
        return aggregated
    for raw_value, probability in probabilities.items():
        key = normalize_text(raw_value)
        if key in aggregated:
            aggregated[key] += float(probability)
            continue
        numeric_value = parse_numeric(raw_value)
        if numeric_value is not None:
            aggregated[box_label_from_count(numeric_value)] += float(probability)
    return aggregated


def apply_tendency_adjustments(
    play: pd.Series,
    tendencies: TendencySnapshot | None,
) -> tuple[float, list[str]]:
    """Apply lightweight additive tendency adjustments on top of the base score."""
    if not tendencies:
        return 0.0, []

    tags = infer_play_tags(play)
    adjustment = 0.0
    reasons: list[str] = []
    coverage_values = parse_list(play_series_value(play, "beats_coverage"))

    coverage_probabilities = tendencies.get("coverage")
    if coverage_probabilities:
        for coverage_id in coverage_values:
            if coverage_id in {"any", "none", "man", "zone", "match"}:
                continue
            probability = float(coverage_probabilities.get(coverage_id, 0.0))
            if probability > 0:
                adjustment += add_reason(
                    reasons,
                    clamp(probability * 6.0, 0.0, 6.0),
                    f"tendency: opponent shows {coverage_id} often",
                )

    box_probabilities = aggregate_box_probabilities(tendencies.get("box_count"))
    for box_label, probability in box_probabilities.items():
        if probability <= 0:
            continue
        if box_label in normalize_beats_box(play):
            adjustment += add_reason(
                reasons,
                clamp(probability * 3.0, 0.0, 3.0),
                f"tendency: opponent leans toward {box_label}",
            )

    pressure_probabilities = tendencies.get("pressure")
    if pressure_probabilities and float(pressure_probabilities.get("yes", 0.0)) > 0:
        pressure_probability = float(pressure_probabilities["yes"])
        if {"quick_game", "screen", "rpo"} & tags:
            adjustment += add_reason(
                reasons,
                clamp(pressure_probability * 5.0, 0.0, 5.0),
                "tendency: pressure profile favors quick answers",
            )
        if "slow_developing" in tags:
            adjustment += add_reason(
                reasons,
                -clamp(pressure_probability * 4.0, 0.0, 4.0),
                "tendency: pressure profile hurts slow-developing concepts",
            )

    heavy_box_probability = (
        box_probabilities.get("heavy_box", 0.0) + box_probabilities.get("loaded_box", 0.0)
    )
    light_box_probability = box_probabilities.get("light_box", 0.0)
    heavy_box_fit = bool(normalize_beats_box(play) & {"heavy_box", "loaded_box"})

    if heavy_box_probability > 0:
        if {"play_action", "rpo", "quick_game", "screen"} & tags:
            adjustment += add_reason(
                reasons,
                clamp(heavy_box_probability * 7.0, 0.0, 7.0),
                "tendency: heavy box profile invites pass or constraint answers",
            )
        if "inside_run" in tags and not heavy_box_fit:
            adjustment += add_reason(
                reasons,
                -clamp(heavy_box_probability * 9.0, 0.0, 9.0),
                "tendency: heavy box profile hurts inside runs without box fit",
            )

    if light_box_probability > 0 and "inside_run" in tags:
        adjustment += add_reason(
            reasons,
            clamp(light_box_probability * 5.0, 0.0, 5.0),
            "tendency: light box profile improves inside runs",
        )

    return adjustment, reasons


def recommend_plays(
    playbook: pd.DataFrame,
    situation: Situation,
    *,
    tendencies: TendencySnapshot | None = None,
    top_n: int = 10,
    min_score: float | None = None,
    limit: int | None = None,
) -> list[Recommendation]:
    """Score a playbook and return ranked recommendations."""
    if limit is not None:
        top_n = limit

    recommendations: list[Recommendation] = []

    for index, (_, play) in enumerate(playbook.iterrows()):
        recommendation = score_play(play, situation)
        tendency_adjustment, tendency_reasons = apply_tendency_adjustments(
            play, tendencies
        )
        final_score = clamp(
            float(recommendation["base_score"]) + tendency_adjustment,
            0.0,
            100.0,
        )
        recommendation["tendency_adjustment"] = tendency_adjustment
        recommendation["score"] = final_score
        recommendation["used_tendencies"] = tendencies is not None
        recommendation["reasons"] = [*recommendation["reasons"], *tendency_reasons]

        if min_score is not None and final_score < min_score:
            continue

        recommendation["_original_index"] = index
        recommendations.append(recommendation)

    ranked = sorted(
        recommendations,
        key=lambda play: (
            -float(play["score"]),
            -int(bool(play["tie_breakers"]["exact_down_distance_match"])),
            -int(bool(play["tie_breakers"]["exact_field_zone_match"])),
            -int(play["tie_breakers"]["exact_defensive_structure_match_count"]),
            -float(play["tie_breakers"]["tactical_fit_score"]),
            int(play["_original_index"]),
        ),
    )

    for recommendation in ranked:
        recommendation.pop("_original_index", None)

    return ranked[:top_n]
