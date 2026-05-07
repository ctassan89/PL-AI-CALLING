"""Interactive sequential play-calling session mode."""

from __future__ import annotations

import argparse
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
) -> tuple[TendencySnapshot | None, str | None, dict[str, str] | None]:
    """Load optional opponent tendencies using the standard lookup contract."""
    if not args.opponent:
        return None, None, None
    if analyzer is None:
        return None, "no tendency file loaded", None

    situation = build_tendency_lookup_situation(args.opponent, state, defense_state)
    if not situation["personnel"]:
        return None, "missing personnel", situation

    matched = analyzer.tendencies
    matched = matched[matched["opponent"] == situation["opponent"]]
    if matched.empty:
        return None, "unknown opponent", situation
    for key in ("down", "distance_bucket", "field_zone", "personnel"):
        matched = matched[matched[key] == situation[key]]
    if matched.empty:
        return None, "no matching tendency bucket found", situation

    tendencies = analyzer.lookup(situation)
    if not any(tendencies.values()):
        return None, "no matching tendency bucket found", situation
    return tendencies, None, situation


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

    print("Opponent tendency snapshot:")
    print(f"- coverage: {format_probability_snapshot(tendencies.get('coverage', {}))}")
    print(f"- front: {format_probability_snapshot(tendencies.get('def_front', {}))}")
    print(f"- box: {format_probability_snapshot(tendencies.get('box_count', {}))}")
    pressure_snapshot = format_probability_snapshot(tendencies.get("pressure", {}))
    if pressure_snapshot != "none":
        print(f"- pressure: {pressure_snapshot}")
    print()


def print_recommendations_for_state(
    playbook: pd.DataFrame,
    state: GameState,
    defense_state: DefenseState,
    *,
    args: argparse.Namespace,
    analyzer: OpponentTendencyAnalyzer | None,
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
    )
    tendencies, tendency_reason, _ = lookup_tendencies(analyzer, args, state, defense_state)
    recommendations = recommend_plays(
        playbook,
        situation,
        tendencies=tendencies,
        top_n=args.top_n,
        intent=args.intent,
    )
    top_count = min(args.top_n, len(recommendations))
    print_tendency_status(args=args, tendencies=tendencies, reason=tendency_reason)
    print(f"Top {top_count} recommended plays:")
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
) -> tuple[GameState, DefenseState]:
    """Apply either a yardage update or a defensive-context update."""
    try:
        gain = int(raw_input)
    except ValueError:
        return state, parse_defense_update(raw_input, defense_state)

    state.apply_gain(gain)
    return state, defense_state


def main() -> None:
    """Run an interactive sequence of recommendations and updates."""
    args = parse_args()
    playbook = pd.read_csv(Path(args.playbook_path))
    analyzer, _ = load_tendency_analyzer(args)
    state, defense_state = prompt_initial_state()

    while True:
        print_situation(state, defense_state)
        print_recommendations_for_state(
            playbook,
            state,
            defense_state,
            args=args,
            analyzer=analyzer,
        )

        if state.status != "active":
            print(f"Drive ended: {state.status}")
            return

        raw_update = input("Yards gained/lost or defense update: ").strip()
        if raw_update.lower() in {"q", "quit", "exit"}:
            return

        try:
            state, defense_state = apply_session_update(raw_update, state, defense_state)
        except ValueError as exc:
            print(exc)


if __name__ == "__main__":
    main()
