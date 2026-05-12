"""Interactive sequential play-calling session mode."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
import sys

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "playbook.csv"
DEFAULT_TENDENCIES_PATH = BASE_DIR / "data" / "opponent_tendencies.csv"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

from opponent.tendencies import OpponentTendencyAnalyzer
from recommendation.engine import (
    build_situation,
    concept_group_key,
    formation_similarity_key,
    infer_play_tags,
    is_physical_run_play,
    is_short_yardage_run,
    is_true_screen_play,
    recommend_plays,
)
from recommendation.game_state import DefenseState, GameState
from recommendation.situation_parser import (
    parse_defense_update,
    parse_initial_session_state,
)


TendencySnapshot = Mapping[str, Mapping[str, float]]

SESSION_LOG_COLUMNS = [
    "drive_id",
    "snap_number",
    "down",
    "distance",
    "yardline",
    "field_position_label",
    "field_zone",
    "personnel",
    "front",
    "coverage",
    "pressure",
    "box",
    "opponent",
    "opponent_tendencies_used",
    "matched_tendency_bucket",
    "tendency_fallback_used",
    "top_recommendations",
    "displayed_recommendations",
    "recommendation_blocks",
    "yards_input",
    "next_down",
    "next_distance",
    "next_yardline",
    "drive_result",
]


@dataclass(frozen=True)
class BlockSpec:
    """Describe one compact recommendation output block."""

    title: str
    labels: frozenset[str]
    intent: str = "balanced"
    fallback_labels: frozenset[str] = frozenset()
    exclude_labels: frozenset[str] = frozenset()
    allow_any: bool = False


@dataclass
class DriveContext:
    """Track lightweight prior-play context for the sequential session."""

    previous_gain: int | None = None

    def apply_gain(self, gain: int) -> None:
        """Store the most recent numeric gain/loss."""
        self.previous_gain = gain

    def as_situation_kwargs(self) -> dict[str, int]:
        """Expose context fields consumed by the shared recommendation engine."""
        if self.previous_gain is None:
            return {}
        return {"previous_gain": self.previous_gain}


@dataclass
class SessionLogWriter:
    """Write one CSV row per completed recommendation step."""

    path: Path
    drive_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=SESSION_LOG_COLUMNS)
        self._writer.writeheader()
        self._handle.flush()

    def write_row(self, row: Mapping[str, object]) -> None:
        """Write and flush a single normalized log row."""
        serialized = {
            column: normalize_text_for_log(row.get(column, ""))
            for column in SESSION_LOG_COLUMNS
        }
        self._writer.writerow(serialized)
        self._handle.flush()

    def close(self) -> None:
        """Close the underlying log file cleanly."""
        self._handle.close()


def format_matched_tendency_bucket(
    situation: Mapping[str, str],
    matched_keys: tuple[str, ...],
) -> str:
    """Format the matched tendency bucket with only the keys actually used."""
    labels = {
        "distance_bucket": "distance",
        "field_zone": "field_zone",
        "personnel": "personnel",
        "opponent": "opponent",
        "down": "down",
    }
    parts = [
        f"{labels.get(key, key)}={situation[key]}"
        for key in matched_keys
        if situation.get(key)
    ]
    return ", ".join(parts) if parts else "global"


def positive_int(value: str) -> int:
    """Parse a positive integer CLI argument."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def parse_args() -> argparse.Namespace:
    """Parse session CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run a sequential play-calling session with persistent defensive context."
    )
    parser.add_argument(
        "--playbook-path",
        default=str(PLAYBOOK_PATH),
        dest="playbook_path",
    )
    parser.add_argument(
        "--opponent-tendencies-path",
        default=str(DEFAULT_TENDENCIES_PATH),
        dest="opponent_tendencies_path",
    )
    parser.add_argument("--top-n", type=positive_int, default=3, dest="top_n")
    parser.add_argument("--block-size", type=positive_int, default=2, dest="block_size")
    parser.add_argument("--opponent")
    parser.add_argument(
        "--intent",
        choices=["shot", "safe", "balanced"],
        default="balanced",
        help="Optional second-and-short recommendation intent.",
    )
    parser.add_argument(
        "--show-reasons",
        action="store_true",
        help="Print detailed scoring reasons for each recommendation.",
    )
    parser.add_argument(
        "--save-log",
        dest="save_log",
        help="Optional CSV path for one row per completed recommendation step.",
    )
    return parser.parse_args()


def print_situation(state: GameState, defense_state: DefenseState) -> None:
    """Print the current offensive and defensive situation concisely."""
    print(
        "\nCurrent situation: "
        f"{state.display_down_distance()}, "
        f"{state.display_yardline()}, {state.field_zone()} | "
        f"{defense_state.display()}\n"
    )


def normalize_text(value: object) -> str:
    """Normalize missing-like scalar values."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def normalize_text_for_log(value: object) -> str:
    """Normalize a scalar into a stable CSV-safe text field."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def csv_flag(value: bool) -> str:
    """Serialize a boolean to a simple yes/no token."""
    return "yes" if value else "no"


def normalize_tendency_distance_bucket_for_session(state: GameState) -> str:
    """Normalize live session distance into the canonical tendency buckets."""
    if state.down == 1 and state.distance == 10:
        return "medium"
    yards = int(state.distance)
    if yards <= 3:
        return "short"
    if yards <= 6:
        return "medium"
    if yards <= 10:
        return "long"
    return "very_long"


def normalize_tendency_field_zone_for_session(field_zone: str) -> str:
    """Normalize session field zones into the canonical tendency zones."""
    normalized = normalize_text(field_zone).lower().replace("-", "_")
    if normalized in {"own_territory", "opp_territory", "open_field"}:
        return "open_field"
    return normalized


def build_tendency_lookup_situation(
    opponent: str,
    state: GameState,
    defense_state: DefenseState,
) -> dict[str, str]:
    """Build the analyzer lookup keys from the live session state."""
    return {
        "opponent": normalize_text(opponent).lower(),
        "down": str(state.down),
        "distance_bucket": normalize_tendency_distance_bucket_for_session(state),
        "field_zone": normalize_tendency_field_zone_for_session(state.field_zone()),
        "personnel": normalize_text(defense_state.personnel).lower(),
    }


def load_tendency_analyzer(
    args: argparse.Namespace,
) -> tuple[OpponentTendencyAnalyzer | None, str | None]:
    """Load the optional tendency analyzer for a session."""
    if not args.opponent:
        return None, None
    tendencies_path = Path(args.opponent_tendencies_path)
    if not tendencies_path.exists():
        return None, "no tendency file loaded"
    return OpponentTendencyAnalyzer.from_csv(tendencies_path), None


def lookup_tendencies(
    analyzer: OpponentTendencyAnalyzer | None,
    args: argparse.Namespace,
    state: GameState,
    defense_state: DefenseState,
) -> tuple[TendencySnapshot | None, str | None, dict[str, object] | None]:
    """Load optional opponent tendencies using the standard lookup contract."""
    if not args.opponent:
        return None, None, None
    if analyzer is None:
        return None, "no tendency file loaded", None

    situation = build_tendency_lookup_situation(args.opponent, state, defense_state)
    matched = analyzer.tendencies
    matched = matched[matched["opponent"] == situation["opponent"]]
    if matched.empty:
        return None, "unknown opponent", {"situation": situation}

    metadata = analyzer.lookup_with_metadata(situation)
    tendencies = metadata["tendencies"]
    if not any(tendencies.values()):
        return None, "no matching tendency bucket found", {"situation": situation, **metadata}
    return tendencies, None, {"situation": situation, **metadata}


def format_probability_snapshot(probabilities: Mapping[str, float], *, limit: int = 3) -> str:
    """Format a compact top-N probability snapshot."""
    if not probabilities:
        return "none"
    ranked = sorted(probabilities.items(), key=lambda item: (-float(item[1]), item[0]))[:limit]
    return ", ".join(f"{label} {float(probability):.0%}" for label, probability in ranked)


def print_tendency_status(
    *,
    args: argparse.Namespace,
    tendencies: TendencySnapshot | None,
    reason: str | None,
    metadata: dict[str, object] | None,
) -> None:
    """Print compact tendency usage and snapshot details."""
    if not args.opponent:
        return

    used = tendencies is not None
    print(f"Opponent tendencies used: {'yes' if used else 'no'}")
    if not used:
        print(reason or "no matching tendency bucket found")
        print()
        return

    if metadata is not None:
        situation = metadata.get("situation")
        matched_keys = metadata.get("matched_keys")
        if isinstance(situation, Mapping) and isinstance(matched_keys, tuple):
            print(
                "Matched tendency bucket: "
                f"{format_matched_tendency_bucket(situation, matched_keys)}"
            )
        if metadata.get("fallback_used"):
            print(
                "tendency fallback: no exact personnel bucket, using broader bucket without personnel"
            )

    print("Opponent tendency snapshot:")
    print(f"- coverage: {format_probability_snapshot(tendencies.get('coverage', {}))}")
    print(f"- front: {format_probability_snapshot(tendencies.get('def_front', {}))}")
    print(f"- box: {format_probability_snapshot(tendencies.get('box_count', {}))}")
    pressure_snapshot = format_probability_snapshot(tendencies.get("pressure", {}))
    if pressure_snapshot != "none":
        print(f"- pressure: {pressure_snapshot}")
    print()


def serialize_top_recommendations(
    recommendation_groups: list[tuple[str, list[Mapping[str, object]]]],
    *,
    limit: int,
) -> str:
    """Serialize the overall top recommendations into one compact log field."""
    flattened: list[Mapping[str, object]] = []
    seen_play_ids: set[str] = set()
    for _, recommendations in recommendation_groups:
        for play in recommendations:
            play_id = str(play.get("play_id", ""))
            if play_id and play_id in seen_play_ids:
                continue
            if play_id:
                seen_play_ids.add(play_id)
            flattened.append(play)
            if len(flattened) >= limit:
                break
        if len(flattened) >= limit:
            break
    return "; ".join(
        f"{index}. {play['play_name']} ({float(play['score']):.1f})"
        for index, play in enumerate(flattened, start=1)
    )


def serialize_recommendation_blocks(
    recommendation_groups: list[tuple[str, list[Mapping[str, object]]]],
) -> str:
    """Serialize each printed recommendation block into one compact string."""
    blocks: list[str] = []
    for heading, recommendations in recommendation_groups:
        title = heading.rstrip(":")
        names = ", ".join(
            f"{play['play_name']} ({float(play['score']):.1f})"
            for play in recommendations
        )
        if names:
            blocks.append(f"{title}: {names}")
    return " | ".join(blocks)


def build_session_log_row(
    *,
    drive_id: str,
    snap_number: int,
    state: GameState,
    defense_state: DefenseState,
    args: argparse.Namespace,
    tendency_metadata: dict[str, object] | None,
    recommendation_groups: list[tuple[str, list[Mapping[str, object]]]],
    tendencies: TendencySnapshot | None,
) -> dict[str, object]:
    """Build the pending log row for the current recommendation step."""
    matched_bucket = ""
    fallback_used = False
    if tendency_metadata is not None:
        situation = tendency_metadata.get("situation")
        matched_keys = tendency_metadata.get("matched_keys")
        if isinstance(situation, Mapping) and isinstance(matched_keys, tuple):
            matched_bucket = format_matched_tendency_bucket(situation, matched_keys)
        fallback_used = bool(tendency_metadata.get("fallback_used"))
    return {
        "drive_id": drive_id,
        "snap_number": snap_number,
        "down": state.down,
        "distance": state.distance,
        "yardline": state.field_position,
        "field_position_label": state.display_yardline(),
        "field_zone": state.field_zone(),
        "personnel": normalize_text(defense_state.personnel),
        "front": normalize_text(defense_state.front_id),
        "coverage": normalize_text(defense_state.coverage_id),
        "pressure": normalize_text(defense_state.pressure_id),
        "box": "" if defense_state.box_count is None else defense_state.box_count,
        "opponent": normalize_text(args.opponent),
        "opponent_tendencies_used": csv_flag(tendencies is not None),
        "matched_tendency_bucket": matched_bucket,
        "tendency_fallback_used": csv_flag(fallback_used),
        # TODO: top_recommendations reflects the displayed recommendation mix today.
        # Keep it stable for backward compatibility and expose the same view explicitly.
        "top_recommendations": serialize_top_recommendations(
            recommendation_groups,
            limit=args.top_n,
        ),
        "displayed_recommendations": serialize_top_recommendations(
            recommendation_groups,
            limit=args.top_n,
        ),
        "recommendation_blocks": serialize_recommendation_blocks(recommendation_groups),
        "yards_input": "",
        "next_down": "",
        "next_distance": "",
        "next_yardline": "",
        "drive_result": "",
    }


def build_recommendation_groups(
    playbook: pd.DataFrame,
    situation: Mapping[str, object],
    *,
    tendencies: TendencySnapshot | None,
    top_n: int,
    block_size: int | None = None,
    intent: str,
) -> list[tuple[str, list[Mapping[str, object]]]]:
    """Build situational recommendation blocks or a fallback unified list."""
    block_specs = choose_output_blocks(situation)
    effective_block_size = top_n if block_size is None else block_size
    requested_personnel = normalize_text(situation.get("personnel")).lower()
    filtered_playbook = playbook
    if requested_personnel:
        filtered_playbook = playbook[
            playbook["personnel"].astype(str).str.strip().str.lower() == requested_personnel
        ].copy()
    if not block_specs:
        return [
            (
                f"Top {top_n} recommended plays:",
                recommend_plays(
                    filtered_playbook,
                    situation,
                    tendencies=tendencies,
                    top_n=top_n,
                    intent=intent,
                ),
            )
        ]

    play_rows = load_play_rows(filtered_playbook)
    pool_size = max(top_n * 8, effective_block_size * 8, 36)
    candidate_pools = {
        pool_intent: recommend_plays(
            filtered_playbook,
            situation,
            tendencies=tendencies,
            top_n=pool_size,
            intent=pool_intent,
        )
        for pool_intent in {spec.intent for spec in block_specs}
    }

    groups: list[tuple[str, list[Mapping[str, object]]]] = []
    used_play_ids: set[str] = set()
    for spec in block_specs:
        candidates = filter_candidates_for_block(
            candidate_pools[spec.intent],
            play_rows,
            spec,
            block_size=effective_block_size,
            used_play_ids=used_play_ids,
        )
        if candidates:
            groups.append((spec.title, candidates))
            used_play_ids.update(str(play["play_id"]) for play in candidates)

    if groups and len(groups) >= min(2, len(block_specs)):
        return groups

    return [
        (
            f"Top {top_n} recommended plays:",
            recommend_plays(
                filtered_playbook,
                situation,
                tendencies=tendencies,
                top_n=top_n,
                intent=intent,
            ),
        )
    ]


def row_value(row: Mapping[str, object], key: str) -> str:
    """Read and normalize a mapping value for classification."""
    return normalize_text(row.get(key, "")).lower()


def parse_labels(value: object) -> set[str]:
    """Split a semicolon-separated schema cell into normalized tokens."""
    text = row_value({"value": value}, "value")
    if not text:
        return set()
    return {item.strip() for item in text.split(";") if item.strip()}


def load_play_rows(playbook: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Build a play_id lookup so session blocks can classify recommendations."""
    return {
        str(row.get("play_id", "")): {str(column): row.get(column, "") for column in row.index}
        for _, row in playbook.iterrows()
    }


def classify_play(play: Mapping[str, object]) -> set[str]:
    """Classify a play into coordinator-friendly football buckets."""
    play_series = pd.Series(play)
    tags = infer_play_tags(play_series)
    labels: set[str] = set()
    play_type = row_value(play, "play_type")
    pass_concept = row_value(play, "pass_concept")
    rpo_tag = row_value(play, "rpo_tag")
    true_screen = is_true_screen_play(play_series, tags)

    if play_type == "run":
        labels.add("run")
    if play_type == "rpo":
        labels.add("rpo")
    if play_type == "pass" and not true_screen:
        labels.add("pass")
    if true_screen:
        labels.update({"screen", "constraint_screen"})
    if {"shot_play", "deep_pass", "vertical_pass", "explosive", "play_action_shot"} & tags:
        labels.add("shot")
    if {"quick_game", "quick_access", "access_throw"} & tags:
        labels.update({"quick_answer", "quick_game"})
    if "safe_conversion" in tags:
        labels.add("safe_conversion")
    if is_short_yardage_run(play_series, tags):
        labels.add("short_yardage_run")
    if play_type == "run" and is_physical_run_play(play_series, tags):
        labels.add("physical_run")
    if play_type == "run" and "perimeter_run" in tags:
        labels.add("perimeter_run")
    if {"pressure_answer", "anti_pressure", "pressure_beater", "blitz_beater"} & tags:
        labels.add("pressure_answer")
    if "red_zone_answer" in tags:
        labels.add("red_zone_answer")
    if "goal_line_answer" in tags:
        labels.add("goal_line_answer")
    if "constraint_call" in tags or true_screen:
        labels.add("constraint_call")
    if "man_beater" in tags:
        labels.add("man_beater")
    if "zone_beater" in tags:
        labels.add("zone_beater")
    if "intermediate_passing_concept" in tags or "third_medium_answer" in tags:
        labels.add("intermediate_conversion")
    if "third_long_answer" in tags or {"deep_pass", "vertical_pass"} & tags:
        labels.add("third_long_conversion")
    if play_type == "rpo" and "conflict_call" in tags:
        labels.add("rpo_conflict")
    if play_type == "rpo" and rpo_tag in {"bubble", "now"}:
        labels.add("access_rpo")
    if play_type == "pass" and "goal_line_answer" in tags and not true_screen and "shot" not in labels:
        labels.add("goal_line_pass")
    if play_type == "run" and "goal_line_answer" in tags:
        labels.add("goal_line_run")
    if "safe_conversion" in tags and ("quick_answer" in labels or "red_zone_answer" in labels):
        labels.add("quick_safe")
    if "man_beater" in tags and ("quick_answer" in labels or "safe_conversion" in tags):
        labels.add("quick_man_beater")
    if play_type == "pass" and not true_screen:
        labels.add("pass")
    if pass_concept == "go_out":
        labels.update({"goal_line_pass", "quick_man_beater", "safe_conversion"})

    return labels


def choose_output_blocks(situation: Mapping[str, object]) -> list[BlockSpec]:
    """Choose compact coordinator-style output blocks for the situation."""
    down = int(situation["down"])
    distance = int(situation["distance"]) if isinstance(situation["distance"], int) else int(str(situation["distance"]))
    tag = normalize_text(situation.get("down_distance_tag"))
    field_zone = normalize_text(situation.get("field_zone"))
    pressure_block_labels = frozenset({"pressure_answer", "quick_answer", "man_beater"})

    if field_zone == "goal_line":
        return [
            BlockSpec("Physical run options:", frozenset({"goal_line_run", "physical_run", "short_yardage_run"}), fallback_labels=frozenset({"run"})),
            BlockSpec("Goal-line pass answers:", frozenset({"goal_line_pass", "quick_man_beater", "safe_conversion"}), fallback_labels=frozenset({"man_beater"}), exclude_labels=frozenset({"rpo", "screen", "shot"})),
        ]
    if field_zone in {"redzone", "high_redzone"}:
        return [
            BlockSpec("Quick / safe answers:", frozenset({"quick_safe", "quick_answer", "safe_conversion"}), fallback_labels=frozenset({"pass"}), exclude_labels=frozenset({"shot", "screen"})),
            BlockSpec("Man-beater answers:", frozenset({"man_beater", "quick_man_beater"}), fallback_labels=frozenset({"pass"}), exclude_labels=frozenset({"shot", "screen"})),
            BlockSpec("Run / physical answers:", frozenset({"goal_line_run", "physical_run", "run"}), fallback_labels=frozenset({"safe_conversion"}), exclude_labels=frozenset({"screen"})),
        ]
    if down == 1 and distance == 10:
        return [
            BlockSpec("Run options:", frozenset({"run"})),
            BlockSpec("RPO options:", frozenset({"rpo", "rpo_conflict"})),
            BlockSpec("Pass options:", frozenset({"pass", "dropback_pass", "play_action"})),
        ]
    if tag == "second_short":
        return [
            BlockSpec("Shot play options:", frozenset({"shot"}), intent="shot"),
            BlockSpec("Safe conversion options:", frozenset({"safe_conversion", "short_yardage_run"}), intent="safe"),
            BlockSpec("RPO conflict options:", frozenset({"rpo", "rpo_conflict"}), intent="balanced"),
        ]
    if tag == "second_medium":
        return [
            BlockSpec("Run options:", frozenset({"run"})),
            BlockSpec("RPO options:", frozenset({"rpo", "rpo_conflict"})),
            BlockSpec("Pass options:", frozenset({"pass", "dropback_pass", "play_action"})),
        ]
    if tag == "second_long":
        return [
            BlockSpec("Conversion pass options:", frozenset({"intermediate_conversion", "pass", "safe_conversion"}), fallback_labels=frozenset({"shot"}), exclude_labels=frozenset({"screen"})),
            BlockSpec("Pressure answers:", pressure_block_labels),
            BlockSpec("Constraint / screen options:", frozenset({"screen", "constraint_call"}), exclude_labels=frozenset({"access_rpo"})),
        ]
    if tag in {"third_short", "fourth_short"}:
        return [
            BlockSpec("Physical run options:", frozenset({"physical_run", "short_yardage_run", "goal_line_run"}), fallback_labels=frozenset({"run"}), exclude_labels=frozenset({"perimeter_run"})),
            BlockSpec("Quick / man-beater answers:", frozenset({"quick_man_beater", "quick_answer", "man_beater", "safe_conversion"}), fallback_labels=frozenset({"pass"}), exclude_labels=frozenset({"shot", "screen"})),
            BlockSpec("Best tendency answers:", frozenset(), fallback_labels=frozenset(), allow_any=True),
        ]
    if tag in {"third_medium", "fourth_medium"}:
        return [
            BlockSpec("Intermediate conversion options:", frozenset({"intermediate_conversion", "safe_conversion", "quick_answer"}), fallback_labels=frozenset({"pass"}), exclude_labels=frozenset({"shot"})),
            BlockSpec("Man / pressure answers:", frozenset({"man_beater", "pressure_answer", "quick_man_beater"}), fallback_labels=pressure_block_labels, exclude_labels=frozenset({"shot"})),
            BlockSpec("Best tendency answers:", frozenset(), fallback_labels=frozenset(), allow_any=True),
        ]
    if tag in {"third_long", "fourth_long"}:
        return [
            BlockSpec("Third-long conversion options:", frozenset({"third_long_conversion", "intermediate_conversion", "shot"}), fallback_labels=frozenset({"pass"}), exclude_labels=frozenset({"access_rpo"})),
            BlockSpec("Pressure answers:", pressure_block_labels),
            BlockSpec("Constraint / screen options:", frozenset({"screen", "constraint_call"}), exclude_labels=frozenset({"access_rpo"})),
        ]
    return []


def block_match_strength(labels: set[str], spec: BlockSpec) -> int:
    """Return a small priority score for block-local ordering."""
    strength = len(labels & set(spec.labels)) * 4
    strength += len(labels & set(spec.fallback_labels))
    if spec.title.startswith("Shot") and "shot" in labels:
        strength += 3
    if "short_yardage_run" in labels and "Physical run" in spec.title:
        strength += 3
    if "rpo_conflict" in labels and "RPO" in spec.title:
        strength += 3
    if "pressure_answer" in labels and "Pressure" in spec.title:
        strength += 3
    if "intermediate_conversion" in labels and "Intermediate" in spec.title:
        strength += 4
    if "third_long_conversion" in labels and "Third-long" in spec.title:
        strength += 4
    if "goal_line_pass" in labels and "Goal-line" in spec.title:
        strength += 4
    return strength


def candidate_matches_block(
    candidate: Mapping[str, object],
    spec: BlockSpec,
    labels: set[str],
) -> bool:
    """Return whether a ranked candidate fits the requested block."""
    if spec.exclude_labels and labels & set(spec.exclude_labels):
        return False
    if spec.allow_any:
        return True
    if labels & set(spec.labels):
        return True
    if spec.fallback_labels and labels & set(spec.fallback_labels):
        return True
    return False


def apply_block_diversity(
    entries: list[tuple[Mapping[str, object], Mapping[str, object], set[str], int]],
    *,
    block_size: int,
    used_play_ids: set[str],
) -> list[Mapping[str, object]]:
    """Select a compact block while relaxing diversity only when needed."""
    phases = [
        {"allow_used": False, "allow_same_concept": False, "allow_same_formation": False},
        {"allow_used": False, "allow_same_concept": False, "allow_same_formation": True},
        {"allow_used": False, "allow_same_concept": True, "allow_same_formation": True},
        {"allow_used": True, "allow_same_concept": True, "allow_same_formation": True},
    ]
    selected: list[Mapping[str, object]] = []
    selected_ids: set[str] = set()
    selected_concepts: set[str] = set()
    selected_formations: set[str] = set()

    for rules in phases:
        for candidate, play_row, _, _ in entries:
            play_id = str(candidate.get("play_id", ""))
            if not play_id or play_id in selected_ids:
                continue
            if not rules["allow_used"] and play_id in used_play_ids:
                continue
            play_series = pd.Series(play_row)
            concept_key = concept_group_key(play_series)
            formation_key = formation_similarity_key(play_series) or row_value(play_row, "formation_id")
            if not rules["allow_same_concept"] and concept_key in selected_concepts:
                continue
            if not rules["allow_same_formation"] and formation_key and formation_key in selected_formations:
                continue
            selected.append(candidate)
            selected_ids.add(play_id)
            selected_concepts.add(concept_key)
            if formation_key:
                selected_formations.add(formation_key)
            if len(selected) >= block_size:
                return selected
    return selected


def filter_candidates_for_block(
    candidates: list[Mapping[str, object]],
    play_rows: Mapping[str, Mapping[str, object]],
    spec: BlockSpec,
    *,
    block_size: int,
    used_play_ids: set[str],
) -> list[Mapping[str, object]]:
    """Filter a ranked candidate pool down to one compact output block."""
    matches: list[tuple[Mapping[str, object], Mapping[str, object], set[str], int]] = []
    fallbacks: list[tuple[Mapping[str, object], Mapping[str, object], set[str], int]] = []
    used_seen: set[str] = set()

    for candidate in candidates:
        play_id = str(candidate.get("play_id", ""))
        if not play_id or play_id in used_seen:
            continue
        play_row = play_rows.get(play_id, candidate)
        labels = classify_play(play_row)
        strength = block_match_strength(labels, spec)
        if candidate_matches_block(candidate, spec, labels):
            if spec.allow_any or labels & set(spec.labels):
                matches.append((candidate, play_row, labels, strength))
            else:
                fallbacks.append((candidate, play_row, labels, strength))
            used_seen.add(play_id)

    ordered = sorted(matches, key=lambda item: (-item[3], -float(item[0]["score"])))
    fallback_ordered = sorted(fallbacks, key=lambda item: (-item[3], -float(item[0]["score"])))
    return apply_block_diversity(
        [*ordered, *fallback_ordered],
        block_size=block_size,
        used_play_ids=used_play_ids,
    )


def build_recommendation_payload(
    playbook: pd.DataFrame,
    state: GameState,
    defense_state: DefenseState,
    *,
    args: argparse.Namespace,
    analyzer: OpponentTendencyAnalyzer | None,
    drive_context: DriveContext | None = None,
) -> dict[str, object]:
    """Build the shared recommendation payload for output and logging."""
    situation = build_situation(
        down=state.down,
        distance=state.distance,
        field_zone=state.field_zone(),
        front_id=defense_state.front_id,
        coverage_id=defense_state.coverage_id,
        pressure_id=defense_state.pressure_id,
        box_count=defense_state.box_count,
        personnel=defense_state.personnel,
        opponent=args.opponent,
        **(drive_context.as_situation_kwargs() if drive_context is not None else {}),
    )
    tendencies, tendency_reason, tendency_metadata = lookup_tendencies(
        analyzer, args, state, defense_state
    )
    recommendation_groups = build_recommendation_groups(
        playbook,
        situation,
        tendencies=tendencies,
        top_n=args.top_n,
        block_size=getattr(args, "block_size", args.top_n),
        intent=args.intent,
    )
    return {
        "situation": situation,
        "tendencies": tendencies,
        "tendency_reason": tendency_reason,
        "tendency_metadata": tendency_metadata,
        "recommendation_groups": recommendation_groups,
    }


def print_recommendation_payload(
    payload: Mapping[str, object],
    *,
    args: argparse.Namespace,
) -> None:
    """Print recommendations from a precomputed payload."""
    print_tendency_status(
        args=args,
        tendencies=payload["tendencies"],
        reason=payload["tendency_reason"],
        metadata=payload["tendency_metadata"],
    )
    recommendation_groups = payload["recommendation_groups"]
    assert isinstance(recommendation_groups, list)
    for heading, recommendations in recommendation_groups:
        print(heading)
        for index, play in enumerate(recommendations[: args.top_n], start=1):
            print(f"{index}. {play['play_name']} | score={float(play['score']):.2f}")
            if args.show_reasons:
                reasons = "; ".join(play["reasons"]) if play["reasons"] else "no positive matches"
                print(f"   reasons: {reasons}")
        print()


def print_recommendations_for_state(
    playbook: pd.DataFrame,
    state: GameState,
    defense_state: DefenseState,
    *,
    args: argparse.Namespace,
    analyzer: OpponentTendencyAnalyzer | None,
    drive_context: DriveContext | None = None,
) -> None:
    """Build and print recommendations using the historical public signature."""
    payload = build_recommendation_payload(
        playbook,
        state,
        defense_state,
        args=args,
        analyzer=analyzer,
        drive_context=drive_context,
    )
    print_recommendation_payload(payload, args=args)


def prompt_initial_state() -> tuple[GameState, DefenseState]:
    """Prompt until the user enters a parseable starting situation."""
    while True:
        raw = input("Initial situation: ").strip()
        try:
            parsed = parse_initial_session_state(raw)
            return parsed.game_state, parsed.defense_state
        except ValueError as exc:
            print(exc)


def apply_session_update(
    raw_input: str,
    state: GameState,
    defense_state: DefenseState,
    drive_context: DriveContext | None = None,
) -> tuple[GameState, DefenseState]:
    """Apply either a yardage update or a defensive-context update."""
    try:
        gain = int(raw_input)
    except ValueError:
        return state, parse_defense_update(raw_input, defense_state)

    state.apply_gain(gain)
    if drive_context is not None:
        drive_context.apply_gain(gain)
    return state, defense_state


def create_session_log_writer(args: argparse.Namespace) -> SessionLogWriter | None:
    """Create the optional session log writer."""
    if not args.save_log:
        return None
    drive_id = datetime.now().strftime("drive_%Y%m%d_%H%M%S")
    return SessionLogWriter(Path(args.save_log), drive_id)


def complete_pending_log_row(
    pending_row: dict[str, object] | None,
    raw_input: str,
    state: GameState,
) -> dict[str, object] | None:
    """Update a pending log row once a numeric yardage input is processed."""
    if pending_row is None:
        return None
    row = dict(pending_row)
    row["yards_input"] = raw_input
    row["next_down"] = state.down
    row["next_distance"] = state.distance
    row["next_yardline"] = state.field_position
    if state.status != "active":
        row["drive_result"] = state.status
    return row


def main() -> None:
    """Run an interactive sequence of recommendations and updates."""
    args = parse_args()
    playbook = pd.read_csv(Path(args.playbook_path))
    analyzer, _ = load_tendency_analyzer(args)
    state, defense_state = prompt_initial_state()
    drive_context = DriveContext()
    log_writer = create_session_log_writer(args)
    snap_number = 1
    pending_log_row: dict[str, object] | None = None

    try:
        while True:
            print_situation(state, defense_state)
            payload = build_recommendation_payload(
                playbook,
                state,
                defense_state,
                args=args,
                analyzer=analyzer,
                drive_context=drive_context,
            )
            print_recommendation_payload(payload, args=args)

            if log_writer is not None:
                pending_log_row = build_session_log_row(
                    drive_id=log_writer.drive_id,
                    snap_number=snap_number,
                    state=state,
                    defense_state=defense_state,
                    args=args,
                    tendency_metadata=payload["tendency_metadata"],
                    recommendation_groups=payload["recommendation_groups"],
                    tendencies=payload["tendencies"],
                )

            if state.status != "active":
                print(f"Drive ended: {state.status}")
                return

            raw_update = input("Yards gained/lost or defense update: ").strip()
            if raw_update.lower() in {"q", "quit", "exit"}:
                return

            try:
                state, defense_state = apply_session_update(
                    raw_update,
                    state,
                    defense_state,
                    drive_context,
                )
            except ValueError as exc:
                print(exc)
                continue

            try:
                gain = int(raw_update)
            except ValueError:
                pending_log_row = None
                continue

            if log_writer is not None:
                completed_row = complete_pending_log_row(pending_log_row, str(gain), state)
                if completed_row is not None:
                    log_writer.write_row(completed_row)
            pending_log_row = None
            snap_number += 1

            if state.status != "active":
                print(f"Drive ended: {state.status}")
                return
    finally:
        if log_writer is not None:
            log_writer.close()


if __name__ == "__main__":
    main()
