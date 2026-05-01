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
    concept_group: str
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
GENERIC_COVERAGE_VALUES = {"zone", "man", "match", "soft_zone"}

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
VERTICAL_CONCEPTS = {"four_verts", "verts", "verticals"}
CONVERSION_MAN_CONCEPTS = {"mesh", "slant_flat", "stick", "snag", "option", "choice"}
CONVERSION_ZONE_CONCEPTS = {"flood", "curl_flat", "snag", "spacing", "stick", "y_cross"}
CONVERSION_STICKS_CONCEPTS = {
    "sticks",
    "stick",
    "spacing",
    "mesh",
    "snag",
    "slant_flat",
    "glance",
    "option",
    "curl_flat",
    "y_cross",
}
LONG_YARDAGE_PASS_CONCEPTS = {
    "y_cross",
    "flood",
    "curl_flat",
    "four_verts",
    "seams",
    "dagger",
    "mesh",
    "screen",
    "screens",
}
PASS_ORIENTED_LONG_RPO_TAGS = {"glance", "double_slant", "stick", "go_out", "slant_flat"}
RUN_FIRST_LONG_RPO_TAGS = {"bubble", "now", "hitch"}


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
    if (
        pass_concept in DEEP_SHOT_CONCEPTS
        or pass_concept in VERTICAL_CONCEPTS
        or pass_modifier == "deep_shot"
        or "deep_shot" in tags
        or "shot" in tags
        or "vertical" in tags
    ):
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


def is_deep_concept(play: pd.Series, tags: set[str] | None = None) -> bool:
    """Return whether the play is a true deep-shot concept."""
    if tags is None:
        tags = infer_play_tags(play)
    pass_concept = normalize_text(play_series_value(play, "pass_concept"))
    pass_modifier = normalize_text(play_series_value(play, "pass_modifier"))
    return (
        pass_concept in VERTICAL_CONCEPTS
        or pass_modifier == "deep_shot"
        or "deep_shot" in tags
    )


def is_four_verts(play: pd.Series) -> bool:
    """Return whether the play is a four verts concept."""
    return normalize_text(play_series_value(play, "pass_concept")) == "four_verts"


def has_explicit_conversion_answer(play: pd.Series, situation: Situation, tags: set[str]) -> bool:
    """Return whether the play has explicit traits that justify a deeper conversion call."""
    pass_concept = normalize_text(play_series_value(play, "pass_concept"))
    preferred = normalize_preferred_down_distance(play)
    return bool(
        {"quick_game", "option", "rub", "man_beater"} & tags
        or pass_concept in CONVERSION_MAN_CONCEPTS
        or "third_medium" in preferred
        or (normalize_text(play_series_value(play, "rpo_tag")) not in {"", "none"} and int(situation["distance"]) <= 6)
    )


def is_play_action(play: pd.Series, tags: set[str] | None = None) -> bool:
    """Return whether the play is tagged as play-action."""
    if tags is None:
        tags = infer_play_tags(play)
    return "play_action" in tags


def is_purely_deep(play: pd.Series, tags: set[str]) -> bool:
    """Return whether the play is deep without efficient constraint traits."""
    return is_deep_concept(play, tags) and not bool(
        {"quick_game", "option", "rub", "man_beater", "rpo"} & tags
    )


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


def normalize_beats_coverage(play: pd.Series) -> set[str]:
    """Normalize playbook coverage answers."""
    return set(parse_list(play_series_value(play, "beats_coverage")))


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
    if coverage_id and coverage_id in normalize_beats_coverage(play):
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

    exact_scores = {
        "early_down": {1: 24.0, 2: 20.0},
        "second_short": 24.0,
        "second_medium": 20.0,
        "second_long": 20.0,
        "third_short": 30.0,
        "third_medium": 26.0,
        "third_long": 28.0,
        "fourth_short": 30.0,
        "fourth_medium": 28.0,
    }
    if tag in preferred:
        if tag == "early_down":
            if down == 1:
                return 24.0, ["+24 down-distance: exact early_down fit on 1st down"]
            return 3.0, ["+3 down-distance: early_down is only a weak fallback outside 1st down"]
        delta = exact_scores[tag]
        if tag == "second_long":
            delta = 26.0
        return float(delta), [f"{delta:+.0f} down-distance: exact match {tag}"]

    short_compatibility = {
        ("third_short", "fourth_short"): 22.0,
        ("third_short", "second_short"): 18.0,
        ("fourth_short", "third_short"): 22.0,
        ("fourth_short", "second_short"): 18.0,
        ("second_short", "third_short"): 18.0,
        ("second_short", "fourth_short"): 18.0,
    }
    for other_tag, delta in short_compatibility.items():
        if tag == other_tag[0] and other_tag[1] in preferred:
            return delta, [f"{delta:+.0f} down-distance: {other_tag[1]} is compatible with {tag}"]

    medium_compatible = {
        "second_medium",
        "third_medium",
        "fourth_medium",
    }
    long_compatible = {"second_long", "third_long", "fourth_medium"}
    if tag in medium_compatible and preferred & medium_compatible:
        return 14.0, [f"+14 down-distance: compatible medium situation fit for {tag}"]
    if tag in long_compatible and preferred & long_compatible:
        delta = 16.0 if tag == "second_long" else 14.0
        return delta, [f"{delta:+.0f} down-distance: compatible long situation fit for {tag}"]
    if tag == "second_long" and "second_medium" in preferred:
        return 10.0, ["+10 down-distance: second_medium has limited carryover to second_long"]
    if tag in {"second_short", "second_medium", "second_long"} and "early_down" in preferred:
        return 3.0, ["+3 down-distance: early_down is only a weak fallback outside 1st down"]
    if tag in {"third_medium", "third_long", "fourth_medium"} and "early_down" in preferred:
        return 3.0, ["+3 down-distance: early_down is only a weak fallback outside 1st down"]
    if bucket in preferred:
        return 12.0, [f"+12 down-distance: related {bucket} situation fit"]

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

    exact_scores = {
        "goal_line": 20.0,
        "redzone": 20.0,
        "high_redzone": 16.0,
        "open_field": 10.0,
    }
    if field_zone in preferred:
        delta = exact_scores[field_zone]
        return delta, [f"{delta:+.0f} field-zone: exact match {field_zone}"]
    if "any" in preferred:
        return 6.0, ["+6 field-zone: any zone flexibility"]
    if field_zone == "redzone" and "high_redzone" in preferred:
        return 12.0, ["+12 field-zone: high_redzone is related to redzone"]
    if field_zone == "high_redzone" and "redzone" in preferred:
        return 12.0, ["+12 field-zone: redzone is related to high_redzone"]
    if field_zone == "goal_line" and "redzone" in preferred:
        return 10.0, ["+10 field-zone: redzone is related to goal_line"]
    if field_zone == "redzone" and "goal_line" in preferred:
        return 10.0, ["+10 field-zone: goal_line is related to redzone"]
    if field_zone == "high_redzone" and "open_field" in preferred:
        return 6.0, ["+6 field-zone: open_field has some carryover to high_redzone"]
    if field_zone == "open_field" and "high_redzone" in preferred:
        return 6.0, ["+6 field-zone: high_redzone traits partially carry to open_field"]
    if field_zone == "open_field" and preferred & {"redzone", "goal_line"}:
        tags = infer_play_tags(play)
        if "deep_shot" in tags or "goal_line" in tags or "redzone" in tags:
            return -4.0, ["-4 field-zone: condensed-field play is a poor open_field fit"]
        return 0.0, []
    if preferred and "open_field" not in preferred:
        return -8.0, [f"-8 field-zone: mismatch for {field_zone}"]
    return 0.0, []


def coverage_families(value: str) -> set[str]:
    """Return normalized coverage families for a label."""
    return set(COVERAGE_FAMILY.get(value, set()))


def coverage_match_kind(play: pd.Series, situation: Situation) -> tuple[str, str]:
    """Return the coverage match kind and matched label."""
    coverage_id = normalize_text(situation.get("coverage_id"))
    if not coverage_id:
        return "none", ""

    coverage_values = normalize_beats_coverage(play)
    if coverage_id in coverage_values:
        return "exact", coverage_id
    if "any" in coverage_values:
        return "any", "any"

    situation_families = coverage_families(coverage_id)
    generic_matches = sorted(
        value
        for value in coverage_values
        if value in GENERIC_COVERAGE_VALUES
        and (value in situation_families or coverage_families(value) & situation_families)
    )
    if generic_matches:
        return "family", generic_matches[0]
    return "none", ""


def supports_specific_coverage(play: pd.Series, coverage_id: str) -> bool:
    """Return whether the play explicitly supports the specific coverage."""
    if not coverage_id:
        return False
    coverage_values = normalize_beats_coverage(play)
    return coverage_id in coverage_values or "any" in coverage_values


def coverage_score_value(play: pd.Series, situation: Situation) -> float:
    """Return the numeric coverage structure score for gating tactical bonuses."""
    match_kind, _ = coverage_match_kind(play, situation)
    if match_kind == "exact":
        return 7.0
    if match_kind == "family":
        return 4.0
    if match_kind == "any":
        return 2.0
    return 0.0


def concept_group_key(play: pd.Series) -> str:
    """Return the grouping key used for concept diversity reranking."""
    play_type = normalize_text(play_series_value(play, "play_type"))
    pass_concept = normalize_text(play_series_value(play, "pass_concept"))
    pass_modifier = normalize_text(play_series_value(play, "pass_modifier"))
    run_scheme = normalize_text(play_series_value(play, "run_scheme"))
    run_modifier = normalize_text(play_series_value(play, "run_modifier"))
    rpo_tag = normalize_text(play_series_value(play, "rpo_tag"))
    play_action = normalize_text(play_series_value(play, "play_action"))

    if play_type == "pass":
        return f"pass:{pass_concept}:{pass_modifier}:{play_action}"
    if play_type == "run":
        return f"run:{run_scheme}:{run_modifier}"
    if play_type == "rpo":
        return f"rpo:{run_scheme}:{rpo_tag}"
    return f"{play_type}:{pass_concept or run_scheme}:{pass_modifier or run_modifier}"


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
            score += add_reason(reasons, 2.0, f"front: any front answer includes {front_id}")

    coverage_id = normalize_text(situation.get("coverage_id"))
    if coverage_id:
        match_kind, match_label = coverage_match_kind(play, situation)
        if match_kind == "exact":
            score += add_reason(reasons, 7.0, f"coverage: exact {coverage_id} match")
        elif match_kind == "family":
            score += add_reason(
                reasons,
                4.0,
                f"coverage: family match via {match_label}",
            )
        elif match_kind == "any":
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
    play_action = is_play_action(play, tags)
    deep_concept = is_deep_concept(play, tags)
    four_verts = is_four_verts(play)
    distance = int(situation["distance"]) if isinstance(situation.get("distance"), int) else parse_numeric(situation.get("distance")) or 0
    coverage_score = coverage_score_value(play, situation)
    has_specific_coverage_support = supports_specific_coverage(play, coverage_id)

    is_short = down_distance_tag in {"second_short", "third_short", "fourth_short"}
    is_redzone = field_zone == "redzone"
    is_goal_line = field_zone == "goal_line"
    is_third_medium = down_distance_tag == "third_medium"
    is_second_medium = down_distance_tag == "second_medium"
    is_second_long = down_distance_tag == "second_long"
    is_fourth_medium = down_distance_tag == "fourth_medium"
    is_long_context = down_distance_tag in {"second_long", "third_long"} or distance >= 7
    play_type = normalize_text(play_series_value(play, "play_type"))

    if is_short:
        if "inside_run" in tags:
            score += add_reason(reasons, 5.0, "tactical: inside_run fits short yardage")
        if "gap_scheme" in tags:
            score += add_reason(reasons, 5.0, "tactical: gap_scheme fits short yardage")
        if "quick_game" in tags:
            score += add_reason(reasons, 4.0, "tactical: quick_game fits short yardage")
        if rpo_tag and rpo_tag != "none":
            score += add_reason(reasons, 4.0, "tactical: rpo is useful in short yardage")
        if play_action and not deep_concept and "slow_developing" not in tags:
            score += add_reason(reasons, 2.0, "tactical: play_action is viable in short yardage")
        if deep_concept:
            penalty = -15.0 if down_distance_tag in {"third_short", "fourth_short"} else -6.0
            score += add_reason(reasons, penalty, "tactical: deep concept is risky in short-yardage conversion")
        if "slow_developing" in tags:
            score += add_reason(reasons, -5.0, "tactical: slow_developing call hurts short yardage")

    if is_second_medium:
        if "inside_run" in tags:
            score += add_reason(reasons, 3.0, "tactical: inside_run is a solid second_medium answer")
        if "rpo" in tags or (rpo_tag and rpo_tag != "none"):
            score += add_reason(reasons, 4.0, "tactical: rpo is a strong second_medium answer")
        if "quick_game" in tags:
            score += add_reason(reasons, 4.0, "tactical: quick_game is a strong second_medium answer")
        if play_action:
            score += add_reason(reasons, 3.0, "tactical: play_action can stress second_medium looks")
        if pass_concept in {"glance", "slant_flat", "stick", "curl_flat"}:
            score += add_reason(reasons, 3.0, f"tactical: {pass_concept} is efficient on second_medium")
        if deep_concept and not (play_action or (coverage_id in {"cover3", "zone"} and is_long_context)):
            score += add_reason(reasons, -4.0, "tactical: deep concept is too swingy for second_medium by default")

    if is_second_long or down_distance_tag == "third_long" or distance >= 8:
        if play_type == "pass":
            score += add_reason(reasons, 4.0, "tactical: pass game is preferred in long yardage")
        if pass_concept in LONG_YARDAGE_PASS_CONCEPTS:
            score += add_reason(reasons, 4.0, f"tactical: {pass_concept} is a real long-yardage answer")
        if "intermediate_pass" in tags:
            score += add_reason(reasons, 5.0, "tactical: intermediate_pass fits long yardage")
        if "screen" in tags:
            score += add_reason(reasons, 4.0, "tactical: screen is useful in long yardage")
        if deep_concept and is_second_long and field_zone == "open_field":
            score += add_reason(reasons, 3.0, "tactical: deep concept has some second_long open_field value")
        if play_action and is_second_long and field_zone == "open_field":
            score += add_reason(reasons, 2.0, "tactical: play_action can create a chunk on second_long")
        if rpo_tag in PASS_ORIENTED_LONG_RPO_TAGS:
            delta = 3.0 if rpo_tag in {"glance", "double_slant", "stick"} else 2.0
            score += add_reason(reasons, delta, f"tactical: {rpo_tag} is a viable long-yardage RPO answer")
        if play_type == "run":
            score += add_reason(reasons, -10.0, "tactical: run-first call is a poor long-yardage answer")
        if play_type == "rpo" and rpo_tag in RUN_FIRST_LONG_RPO_TAGS and not ({"screen", "explosive", "perimeter_answer"} & tags):
            score += add_reason(reasons, -5.0, f"tactical: {rpo_tag} RPO is too run-first for long yardage")
        if "inside_run" in tags and not ({"screen", "draw"} & tags):
            score += add_reason(reasons, -6.0, "tactical: inside_run profile is too run-first for long yardage")
        if (
            ("gap_scheme" in tags or run_scheme == "counter" or "counter" in tags)
            and not ({"screen", "draw"} & tags)
        ):
            score += add_reason(reasons, -4.0, "tactical: gap/counter profile is too run-first for long yardage")

    if is_third_medium:
        if "quick_game" in tags:
            score += add_reason(reasons, 5.0, "tactical: quick_game is strong on third_medium")
        if pass_concept in {"sticks", "stick"} or "sticks" in tags:
            score += add_reason(reasons, 5.0, "tactical: stick/sticks is a strong third_medium answer")
        if pass_concept == "spacing" or "spacing" in tags:
            score += add_reason(reasons, 4.0, "tactical: spacing fits third_medium")
        if pass_concept == "mesh" or "mesh" in tags:
            score += add_reason(reasons, 5.0, "tactical: mesh fits third_medium")
        if pass_concept == "snag" or "snag" in tags:
            score += add_reason(reasons, 4.0, "tactical: snag fits third_medium")
        if pass_concept == "slant_flat" or "slant_flat" in tags:
            score += add_reason(reasons, 4.0, "tactical: slant_flat fits third_medium")
        if pass_concept == "glance" or "glance" in tags:
            score += add_reason(reasons, 3.0, "tactical: glance can convert third_medium")
        if {"option", "man_beater"} & tags or pass_concept == "option":
            score += add_reason(reasons, 5.0, "tactical: option/man_beater traits help on third_medium")
        if pass_concept == "curl_flat" or "curl_flat" in tags:
            score += add_reason(reasons, 4.0, "tactical: curl_flat fits third_medium")
        if pass_concept == "y_cross" or "y_cross" in tags:
            score += add_reason(reasons, 3.0, "tactical: y_cross can convert third_medium")
        if rpo_tag and rpo_tag != "none" and distance <= 6:
            score += add_reason(reasons, 3.0, "tactical: rpo can help on manageable third_medium")
        if deep_concept and not has_explicit_conversion_answer(play, situation, tags):
            score += add_reason(reasons, -8.0, "tactical: deep concept is too volatile on third_medium")

    if is_fourth_medium and deep_concept and not has_explicit_conversion_answer(play, situation, tags):
        score += add_reason(reasons, -10.0, "tactical: deep concept is too volatile on fourth_medium")

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
        if deep_concept:
            score += add_reason(reasons, -8.0, "tactical: deep concept is risky in redzone")
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
        if deep_concept:
            score += add_reason(reasons, -12.0, "tactical: deep concept is a poor goal_line answer")

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
        if distance <= 7 and "inside_run" in tags:
            score += add_reason(reasons, 5.0, "tactical: inside_run should attack a light_box")
        if distance <= 7 and "gap_scheme" in tags:
            score += add_reason(reasons, 4.0, "tactical: gap_scheme can punish a light_box")
        if distance <= 7 and "zone_run" in tags:
            score += add_reason(reasons, 3.0, "tactical: zone_run is useful versus a light_box")
        if distance <= 7 and run_scheme in {"power", "counter"}:
            score += add_reason(reasons, 3.0, f"tactical: {run_scheme} fits a light_box")
        if distance >= 8 and ("draw" in tags or "screen" in tags or "perimeter_run" in tags or "explosive" in tags or "perimeter_answer" in tags):
            score += add_reason(reasons, 2.0, "tactical: light_box still helps a perimeter or draw answer in long yardage")

    if coverage_id == "cover3":
        if pass_concept == "flood" or "flood" in tags:
            score += add_reason(reasons, 3.0, "tactical: flood is strong versus cover3")
        if pass_concept == "curl_flat" or "curl_flat" in tags:
            score += add_reason(reasons, 3.0, "tactical: curl_flat is strong versus cover3")
        if pass_concept == "seams" or "seams" in tags:
            score += add_reason(reasons, 3.0, "tactical: seams can stress cover3")
        if play_action:
            score += add_reason(reasons, 2.0, "tactical: play_action can help versus cover3")
        if four_verts and has_specific_coverage_support and (is_long_context or int(situation["down"]) == 1 or play_action):
            score += add_reason(reasons, 2.0, "tactical: four_verts has contextual cover3 value here")

    if coverage_id == "cover4" and (is_second_long or down_distance_tag == "third_long" or distance >= 8):
        if pass_concept in {"seams", "y_cross", "flood", "curl_flat"} and (
            has_specific_coverage_support or "cover4_beater" in tags
        ):
            score += add_reason(reasons, 3.0, f"tactical: {pass_concept} has contextual value versus cover4")
        if (
            {"seams"} & tags
            and (has_specific_coverage_support or "cover4_beater" in tags)
        ):
            score += add_reason(reasons, 3.0, "tactical: seams profile helps versus cover4")

    coverage_fams = coverage_families(coverage_id)
    if "man" in coverage_fams or coverage_id in {"cover0", "cover1", "man"}:
        if pass_concept == "mesh" or "mesh" in tags:
            score += add_reason(reasons, 4.0, "tactical: mesh is strong versus man")
        if "rub" in tags:
            score += add_reason(reasons, 4.0, "tactical: rub concept fits man coverage")
        if (
            {"man_beater", "rub", "mesh", "option", "quick_game", "matchup_win"} & tags
            or pass_concept in CONVERSION_MAN_CONCEPTS
        ):
            score += add_reason(reasons, 4.0, "tactical: man_beater traits fit man coverage")
        if "quick_game" in tags:
            score += add_reason(reasons, 3.0, "tactical: quick_game is useful versus man")

    if "zone" in coverage_fams or coverage_id in {"cover2", "cover3", "soft_zone", "zone"}:
        if (
            {"zone_beater", "spacing", "curl_flat", "flood", "snag", "seams"} & tags
            or pass_concept in CONVERSION_ZONE_CONCEPTS
        ) and coverage_score > 0:
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
    deep_concept = is_deep_concept(play, tags)
    play_action = is_play_action(play, tags)
    pass_concept = normalize_text(play_series_value(play, "pass_concept"))
    rpo_tag = normalize_text(play_series_value(play, "rpo_tag"))
    play_type = normalize_text(play_series_value(play, "play_type"))

    if down_distance_tag in {"third_short", "fourth_short"}:
        if {"inside_run", "quick_game", "rpo", "gap_scheme"} & tags:
            score += add_reason(reasons, 3.0, "risk-reward: efficient answer for short conversion")
        if deep_concept:
            score += add_reason(reasons, -5.0, "risk-reward: deep_shot is too volatile here")

    if down_distance_tag == "third_medium":
        if deep_concept and not has_explicit_conversion_answer(play, situation, tags):
            score += add_reason(reasons, -4.0, "risk-reward: deep concept is risky on third_medium")

    if down_distance_tag == "second_long":
        if play_type == "pass" and (
            pass_concept in LONG_YARDAGE_PASS_CONCEPTS or "intermediate_pass" in tags
        ):
            score += add_reason(reasons, 3.0, "risk-reward: chunk or intermediate pass fits second_long")
        if deep_concept and field_zone == "open_field":
            score += add_reason(reasons, 2.0, "risk-reward: deep_shot is acceptable on second_long open field")
        if {"inside_run", "gap_scheme"} & tags:
            score += add_reason(reasons, -4.0, "risk-reward: run-first profile is low-upside on second_long")
        if rpo_tag in {"bubble", "now"}:
            score += add_reason(reasons, -3.0, f"risk-reward: {rpo_tag} RPO is too low-upside on second_long")

    if int(situation["down"]) == 1 and field_zone == "open_field":
        if play_action:
            score += add_reason(reasons, 3.0, "risk-reward: play_action is attractive on 1st down open field")
        if deep_concept:
            score += add_reason(reasons, 2.0, "risk-reward: deep_shot is acceptable on 1st down open field")

    if field_zone == "redzone":
        if {"quick_game", "rpo", "play_action"} & tags:
            score += add_reason(reasons, 3.0, "risk-reward: efficient redzone profile")
        if deep_concept:
            score += add_reason(reasons, -4.0, "risk-reward: deep_shot loses value in redzone")

    if field_zone == "goal_line":
        if {"inside_run", "quick_game", "rpo"} & tags:
            score += add_reason(reasons, 4.0, "risk-reward: high-percentage goal_line profile")
        if deep_concept:
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
    max_per_concept: int | None = 3,
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
        recommendation["concept_group"] = concept_group_key(play)

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

    apply_concept_cap = max_per_concept is not None and not normalize_text(situation.get("formation_id"))
    if apply_concept_cap:
        filtered: list[Recommendation] = []
        concept_counts: dict[str, int] = {}
        for recommendation in ranked:
            concept_group = str(recommendation.get("concept_group", ""))
            current_count = concept_counts.get(concept_group, 0)
            if current_count >= int(max_per_concept):
                continue
            concept_counts[concept_group] = current_count + 1
            filtered.append(recommendation)
        ranked = filtered

    for recommendation in ranked:
        recommendation.pop("_original_index", None)

    return ranked[:top_n]
