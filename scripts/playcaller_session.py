"""Interactive sequential play-calling session mode."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "playbook.csv"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

from recommendation import build_situation, recommend_plays
from recommendation.game_state import GameState
from recommendation.situation_parser import parse_initial_situation


def parse_args() -> argparse.Namespace:
    """Parse session CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run a simple sequential play-calling session."
    )
    parser.add_argument(
        "--playbook-path",
        default=str(PLAYBOOK_PATH),
        dest="playbook_path",
    )
    parser.add_argument("--top-n", type=int, default=3, dest="top_n")
    return parser.parse_args()


def print_situation(state: GameState) -> None:
    """Print the current game state concisely."""
    print(
        f"\nCurrent situation: {state.display_down_distance()}, "
        f"{state.display_yardline()}, {state.field_zone()}\n"
    )


def print_recommendations_for_state(
    playbook: pd.DataFrame,
    state: GameState,
    *,
    top_n: int,
) -> None:
    """Build the engine situation and print top recommendations."""
    situation = build_situation(
        down=state.down,
        distance=state.distance,
        field_zone=state.field_zone(),
        pressure_id="none",
    )
    recommendations = recommend_plays(playbook, situation, top_n=top_n)
    print(f"Top {min(top_n, len(recommendations))} recommended plays:")
    for index, play in enumerate(recommendations[:top_n], start=1):
        print(f"{index}. {play['play_name']} ({float(play['score']):.2f})")
    print()


def prompt_initial_state() -> GameState:
    """Prompt until the user enters a parseable starting situation."""
    while True:
        raw = input("Initial situation: ").strip()
        try:
            return parse_initial_situation(raw)
        except ValueError as exc:
            print(exc)


def main() -> None:
    """Run an interactive sequence of recommendations and yardage updates."""
    args = parse_args()
    playbook = pd.read_csv(Path(args.playbook_path))
    state = prompt_initial_state()

    while True:
        print_situation(state)
        print_recommendations_for_state(playbook, state, top_n=args.top_n)

        if state.status != "active":
            print(f"Drive ended: {state.status}")
            return

        raw_gain = input("Yards gained/lost: ").strip().lower()
        if raw_gain in {"q", "quit", "exit"}:
            return
        try:
            gain = int(raw_gain)
        except ValueError:
            print("Enter a whole number of yards, or q to quit.")
            continue

        state.apply_gain(gain)


if __name__ == "__main__":
    main()
