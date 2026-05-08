"""Interactive sequential play-calling session mode."""

from __future__ import annotations

import argparse
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
from recommendation import build_situation, recommend_plays
from recommendation.game_state import DefenseState, GameState
from recommendation.situation_parser import (
    parse_defense_update,
    parse_initial_session_state,
)


TendencySnapshot = Mapping[str, Mapping[str, float]]


@dataclass(frozen=True)
class BlockSpec:
    """Describe one compact recommendation output block."""

    title: str
    labels: frozenset[str]
    intent: str = "balanced"
    fallback_labels: frozenset[str] = frozenset()


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
    parser.add_argument("--block-size", type=positive_int, default=3, dest="block_size")
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
    if not block_specs:
        return [
            (
                f"Top {top_n} recommended plays:",
                recommend_plays(
                    playbook,
                    situation,
                    tendencies=tendencies,
                    top_n=top_n,
                    intent=intent,
                ),
            )
        ]

    play_rows = load_play_rows(playbook)
    pool_size = max(top_n * 8, effective_block_size * 8, 36)
    candidate_pools = {
        pool_intent: recommend_plays(
            playbook,
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

    if groups:
        return groups

    return [
        (
            f"Top {top_n} recommended plays:",
            recommend_plays(
                playbook,
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
    labels: set[str] = set()
    tags = parse_labels(play.get("tags", ""))
    preferred_dd = parse_labels(play.get("preferred_down_distance", ""))
    preferred_zones = parse_labels(play.get("preferred_field_zone", ""))
    play_type = row_value(play, "play_type")
    play_family = row_value(play, "play_family")
    run_scheme = row_value(play, "run_scheme")
    run_modifier = row_value(play, "run_modifier")
    pass_concept = row_value(play, "pass_concept")
    pass_modifier = row_value(play, "pass_modifier")
    rpo_tag = row_value(play, "rpo_tag")
    beats_pressure = parse_labels(play.get("beats_pressure", ""))
    play_action = row_value(play, "play_action") == "true"
    formation_id = row_value(play, "formation_id")
    personnel = row_value(play, "personnel")

    shot_concepts = {
        "four_verts",
        "verts",
        "yankee",
        "mills",
        "dagger",
        "y_cross",
        "post",
        "go",
        "seams",
    }
    quick_concepts = {
        "stick",
        "hitch",
        "slant_flat",
        "curl_flat",
        "spacing",
        "mesh",
        "snag",
        "beamer",
        "quick_out",
        "glance",
    }
    physical_short_run_schemes = {"duo", "inside_zone", "power", "counter", "trap"}
    perimeter_schemes = {"outside_zone", "wide_zone", "pin_pull", "jet", "toss", "sweep"}

    if play_type == "run":
        labels.add("run")
    if play_type == "rpo":
        labels.update({"rpo", "run_threat"})
    if play_type == "pass" and not play_action:
        labels.add("dropback_pass")
    if play_action:
        labels.add("play_action")
    if "screen" in tags or play_family == "screen" or "screen" in pass_concept or "screen" in pass_modifier:
        labels.update({"screen", "constraint_call"})
    if (
        "deep_shot" in tags
        or "shot_play" in tags
        or "explosive" in tags
        or pass_concept in shot_concepts
        or pass_modifier == "deep_shot"
    ):
        labels.add("shot")
    if "quick_game" in tags or pass_concept in quick_concepts or rpo_tag in quick_concepts:
        labels.add("quick_game")
    if (
        (play_type in {"run", "rpo"})
        and (
            run_scheme in physical_short_run_schemes
            or run_modifier in {"insert", "split_zone", "gt", "gy"}
            or {"inside_run", "gap_scheme", "insert", "split_zone"} & tags
        )
        and not (play_type == "rpo" and rpo_tag in {"bubble", "now"})
        and run_scheme not in perimeter_schemes
    ):
        labels.add("short_yardage_run")
    if play_type == "run" and (
        "short_yardage_run" in labels or run_scheme in physical_short_run_schemes or {"inside_run", "gap_scheme"} & tags
    ):
        labels.add("physical_run")
    if run_scheme in perimeter_schemes or {"perimeter_run", "outside_run", "space_play"} & tags:
        labels.add("perimeter_run")
    if (
        "pressure_beater" in tags
        or "blitz_beater" in tags
        or "anti_pressure" in tags
        or "hot_answer" in tags
        or beats_pressure - {"none"}
    ):
        labels.add("pressure_answer")
    if {"redzone", "red_zone"} & tags or preferred_zones & {"redzone", "goal_line"}:
        labels.add("red_zone_answer")
    if "goal_line" in tags or preferred_zones & {"goal_line"}:
        labels.add("goal_line_answer")
    if (
        "short_yardage_run" in labels
        or "quick_game" in labels
        or (play_type == "rpo" and rpo_tag in {"glance", "quick_out", "hitch", "stick", "bubble", "now", "double_slant", "go_out"})
        or pass_concept in {"stick", "hitch", "slant_flat", "curl_flat", "spacing", "mesh", "beamer", "glance"}
    ):
        labels.add("safe_conversion")
    if "constraint_call" in labels or "screen" in labels or "play_action" in labels:
        labels.add("constraint_call")
    if "man_beater" in tags or pass_concept in {"mesh", "option", "choice", "beamer"}:
        labels.add("man_beater")
    if pass_concept in {"spacing", "curl_flat", "flood", "snag", "stick", "y_cross"}:
        labels.add("zone_beater")
    if play_type == "rpo" and (
        {"conflict_defender", "hot_answer"} & tags
        or rpo_tag in {"glance", "quick_out", "hitch", "stick", "bubble", "now", "double_slant", "go_out"}
    ):
        labels.add("rpo_conflict")
    if play_type == "pass" and "screen" not in labels:
        labels.add("pass")
    if formation_id and any(token in formation_id for token in {"bunch", "wing", "te_on", "te_attached", "2te", "condensed"}):
        labels.add("condensed_surface")
    if personnel == "12":
        labels.add("heavy_personnel")
    if preferred_dd & {"third_short", "fourth_short", "second_short"}:
        labels.add("short_yardage_call")

    return labels


def choose_output_blocks(situation: Mapping[str, object]) -> list[BlockSpec]:
    """Choose compact coordinator-style output blocks for the situation."""
    down = int(situation["down"])
    distance = int(situation["distance"]) if isinstance(situation["distance"], int) else int(str(situation["distance"]))
    tag = normalize_text(situation.get("down_distance_tag"))
    field_zone = normalize_text(situation.get("field_zone"))
    pressure_id = normalize_text(situation.get("pressure_id"))
    pressure_block_labels = frozenset({"pressure_answer", "quick_game", "man_beater"})

    if field_zone in {"redzone", "goal_line"} and distance <= 3:
        return [
            BlockSpec("Physical run options:", frozenset({"physical_run"}), fallback_labels=frozenset({"run"})),
            BlockSpec("RPO / quick answer options:", frozenset({"rpo", "quick_game", "safe_conversion"}), fallback_labels=frozenset({"man_beater"})),
            BlockSpec("Man-pressure answers:", frozenset({"man_beater", "pressure_answer"}), fallback_labels=pressure_block_labels),
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
            BlockSpec("Conversion pass options:", frozenset({"pass", "dropback_pass", "shot"})),
            BlockSpec("Pressure answers:", pressure_block_labels),
            BlockSpec("Constraint / screen / draw options:", frozenset({"screen", "constraint_call"})),
        ]
    if tag in {"third_short", "fourth_short"}:
        return [
            BlockSpec("Physical run options:", frozenset({"physical_run"}), fallback_labels=frozenset({"run"})),
            BlockSpec("RPO / quick answer options:", frozenset({"rpo", "quick_game", "safe_conversion"})),
            BlockSpec("Man-pressure answers:", frozenset({"man_beater", "pressure_answer"}), fallback_labels=pressure_block_labels if pressure_id else frozenset({"man_beater"})),
        ]
    if tag in {"third_medium", "fourth_medium"}:
        return [
            BlockSpec("Conversion pass options:", frozenset({"pass", "dropback_pass", "safe_conversion"})),
            BlockSpec("RPO / quick answers:", frozenset({"rpo", "quick_game", "safe_conversion"})),
            BlockSpec("Pressure answers:", pressure_block_labels),
        ]
    if tag in {"third_long", "fourth_long"}:
        return [
            BlockSpec("Conversion pass options:", frozenset({"pass", "dropback_pass", "shot"})),
            BlockSpec("Pressure answers:", pressure_block_labels),
            BlockSpec("Constraint / screen options:", frozenset({"screen", "constraint_call"})),
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
    return strength


def filter_candidates_for_block(
    candidates: list[Mapping[str, object]],
    play_rows: Mapping[str, Mapping[str, object]],
    spec: BlockSpec,
    *,
    block_size: int,
    used_play_ids: set[str],
) -> list[Mapping[str, object]]:
    """Filter a ranked candidate pool down to one compact output block."""
    matches: list[tuple[Mapping[str, object], set[str], int]] = []
    fallbacks: list[tuple[Mapping[str, object], set[str], int]] = []
    used_seen: set[str] = set()

    for candidate in candidates:
        play_id = str(candidate.get("play_id", ""))
        if not play_id or play_id in used_seen:
            continue
        labels = classify_play(play_rows.get(play_id, candidate))
        strength = block_match_strength(labels, spec)
        if labels & set(spec.labels):
            matches.append((candidate, labels, strength))
            used_seen.add(play_id)
        elif spec.fallback_labels and labels & set(spec.fallback_labels):
            fallbacks.append((candidate, labels, strength))
            used_seen.add(play_id)

    ordered = sorted(matches, key=lambda item: (-item[2], -float(item[0]["score"])))
    fallback_ordered = sorted(fallbacks, key=lambda item: (-item[2], -float(item[0]["score"])))

    selected: list[Mapping[str, object]] = []
    selected_ids: set[str] = set()
    for pool, allow_duplicates in ((ordered, False), (fallback_ordered, False), (ordered, True), (fallback_ordered, True)):
        for candidate, _, _ in pool:
            play_id = str(candidate["play_id"])
            if play_id in selected_ids:
                continue
            if not allow_duplicates and play_id in used_play_ids:
                continue
            selected.append(candidate)
            selected_ids.add(play_id)
            if len(selected) >= block_size:
                return selected
    return selected


def print_recommendations_for_state(
    playbook: pd.DataFrame,
    state: GameState,
    defense_state: DefenseState,
    *,
    args: argparse.Namespace,
    analyzer: OpponentTendencyAnalyzer | None,
    drive_context: DriveContext | None = None,
) -> None:
    """Build the shared situation payload and print top recommendations."""
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
    print_tendency_status(
        args=args,
        tendencies=tendencies,
        reason=tendency_reason,
        metadata=tendency_metadata,
    )
    for heading, recommendations in recommendation_groups:
        print(heading)
        for index, play in enumerate(recommendations[: args.top_n], start=1):
            print(f"{index}. {play['play_name']} | score={float(play['score']):.2f}")
            if args.show_reasons:
                reasons = "; ".join(play["reasons"]) if play["reasons"] else "no positive matches"
                print(f"   reasons: {reasons}")
        print()


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


def main() -> None:
    """Run an interactive sequence of recommendations and updates."""
    args = parse_args()
    playbook = pd.read_csv(Path(args.playbook_path))
    analyzer, _ = load_tendency_analyzer(args)
    state, defense_state = prompt_initial_state()
    drive_context = DriveContext()

    while True:
        print_situation(state, defense_state)
        print_recommendations_for_state(
            playbook,
            state,
            defense_state,
            args=args,
            analyzer=analyzer,
            drive_context=drive_context,
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

        if state.status != "active":
            print(f"Drive ended: {state.status}")
            return


if __name__ == "__main__":
    main()
