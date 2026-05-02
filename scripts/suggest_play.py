"""Suggest the best offensive plays for a given game situation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "raw" / "playbook.csv"
DEFAULT_TENDENCIES_PATH = BASE_DIR / "data" / "opponent_tendencies.csv"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

import pandas as pd

from opponent.tendencies import OpponentTendencyAnalyzer
from recommendation.engine import build_situation, recommend_plays


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the play suggestion script."""
    parser = argparse.ArgumentParser(
        description="Recommend offensive plays from the playbook."
    )
    parser.add_argument("--down", type=int, required=True)
    parser.add_argument("--distance", required=True)
    parser.add_argument("--field-zone", required=True, dest="field_zone")
    parser.add_argument("--formation-id", dest="formation_id")
    parser.add_argument("--front-id", "--front", dest="front_id")
    parser.add_argument("--coverage-id", "--coverage", dest="coverage_id")
    parser.add_argument("--box-count", type=int, required=True, dest="box_count")
    parser.add_argument("--personnel")
    parser.add_argument("--opponent")
    parser.add_argument("--top-n", type=int, default=10, dest="top_n")
    parser.add_argument("--max-per-concept", type=int, default=3, dest="max_per_concept")
    parser.add_argument(
        "--intent",
        choices=["shot", "safe", "balanced"],
        help="Recommendation intent. On second-and-short, omit this to show both shot and safe sections.",
    )
    parser.add_argument(
        "--opponent-tendencies-path",
        default=str(DEFAULT_TENDENCIES_PATH),
        dest="opponent_tendencies_path",
    )
    return parser.parse_args()


def is_second_and_short(situation: dict[str, str | int]) -> bool:
    """Return whether the current situation is second and short."""
    return str(situation.get("down_distance_tag")) == "second_short"


def section_title(intent: str) -> str:
    """Return the user-facing section title for an intent."""
    return {
        "shot": "Aggressive / shot play options",
        "safe": "Safe / move-the-chains options",
        "balanced": "Balanced options",
    }[intent]


def print_recommendations(
    title: str,
    plays: list[dict[str, object]],
    *,
    top_n: int,
    tendencies_used: bool,
) -> None:
    """Print a formatted recommendation section."""
    print(f"{title} (Top {top_n})")
    print(f"Opponent tendencies used: {'yes' if tendencies_used else 'no'}\n")
    for rank, play in enumerate(plays, start=1):
        concept_scheme = play.get("concept_scheme", "")
        duplicate_label = " | fallback duplicate concept" if play.get("duplicate_fallback") else ""
        print(
            f"{rank}. {play['play_name']} | "
            f"play_id={play['play_id']} | "
            f"score={play['score']:.2f} | "
            f"formation_id={play.get('formation_id', '')} | "
            f"personnel={play.get('personnel', '')} | "
            f"play_type={play.get('play_type', '')} | "
            f"concept/scheme={concept_scheme}{duplicate_label}"
        )
        print("   Reasons:")
        if play["reasons"]:
            for reason in play["reasons"]:
                print(f"   - {reason}")
        else:
            print("   - no positive matches")
        print()


def main() -> None:
    """Load the playbook, score plays, and print the top recommendations."""
    args = parse_args()
    playbook = pd.read_csv(PLAYBOOK_PATH)

    situation = build_situation(
        down=args.down,
        distance=args.distance,
        field_zone=args.field_zone,
        formation_id=args.formation_id,
        front_id=args.front_id,
        coverage_id=args.coverage_id,
        box_count=args.box_count,
        personnel=args.personnel,
        opponent=args.opponent,
    )

    tendencies = None
    tendencies_path = Path(args.opponent_tendencies_path)
    if args.opponent and tendencies_path.exists():
        analyzer = OpponentTendencyAnalyzer.from_csv(tendencies_path)
        tendencies = analyzer.lookup(
            {
                "opponent": args.opponent,
                "down": args.down,
                "distance_bucket": args.distance,
                "field_zone": args.field_zone,
                "personnel": args.personnel or "",
            }
        )

    if is_second_and_short(situation):
        print(
            "Second and short is a dual-mode situation: you can either take a calculated shot or call a safer move-the-chains play.\n"
        )

    if is_second_and_short(situation) and not args.intent:
        for intent in ["shot", "safe"]:
            plays = recommend_plays(
                playbook,
                situation,
                tendencies=tendencies,
                top_n=args.top_n,
                max_per_concept=args.max_per_concept,
                intent=intent,
            )
            print_recommendations(
                section_title(intent),
                plays,
                top_n=args.top_n,
                tendencies_used=bool(tendencies),
            )
        return

    selected_intent = args.intent or "balanced"
    top_plays = recommend_plays(
        playbook,
        situation,
        tendencies=tendencies,
        top_n=args.top_n,
        max_per_concept=args.max_per_concept,
        intent=selected_intent,
    )
    title = (
        section_title(selected_intent)
        if is_second_and_short(situation)
        else f"Top {args.top_n} recommended plays"
    )
    print_recommendations(
        title,
        top_plays,
        top_n=args.top_n,
        tendencies_used=bool(tendencies),
    )


if __name__ == "__main__":
    main()
