"""Interactive sequential play-calling session mode."""

from __future__ import annotations

import argparse
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


def lookup_tendencies(
    args: argparse.Namespace,
    state: GameState,
    defense_state: DefenseState,
) -> dict[str, dict[str, float]] | None:
    """Load optional opponent tendencies using the standard lookup contract."""
    if not args.opponent:
        return None

    tendencies_path = Path(args.opponent_tendencies_path)
    if not tendencies_path.exists():
        return None

    analyzer = OpponentTendencyAnalyzer.from_csv(tendencies_path)
    return analyzer.lookup(
        {
            "opponent": args.opponent,
            "down": state.down,
            "distance_bucket": state.distance,
            "field_zone": state.field_zone(),
            "personnel": defense_state.personnel or "",
        }
    )


def print_recommendations_for_state(
    playbook: pd.DataFrame,
    state: GameState,
    defense_state: DefenseState,
    *,
    args: argparse.Namespace,
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
    recommendations = recommend_plays(
        playbook,
        situation,
        tendencies=lookup_tendencies(args, state, defense_state),
        top_n=args.top_n,
        intent=args.intent,
    )
    top_count = min(args.top_n, len(recommendations))
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
    state, defense_state = prompt_initial_state()

    while True:
        print_situation(state, defense_state)
        print_recommendations_for_state(playbook, state, defense_state, args=args)

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
