"""Suggest the best offensive plays for a given game situation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "raw" / "playbook.csv"
DEFAULT_TENDENCIES_PATH = BASE_DIR / "data" / "opponent_tendencies.csv"

if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

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
    parser.add_argument("--formation-id", required=True, dest="formation_id")
    parser.add_argument("--front-id", required=True, dest="front_id")
    parser.add_argument("--coverage-id", required=True, dest="coverage_id")
    parser.add_argument("--box-count", type=int, required=True, dest="box_count")
    parser.add_argument("--personnel")
    parser.add_argument("--opponent")
    parser.add_argument(
        "--opponent-tendencies-path",
        default=str(DEFAULT_TENDENCIES_PATH),
        dest="opponent_tendencies_path",
    )
    return parser.parse_args()


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

    top_plays = recommend_plays(playbook, situation, tendencies=tendencies, limit=3)

    print("Top 3 recommended plays:\n")
    for rank, play in enumerate(top_plays, start=1):
        print(
            f"{rank}. {play['play_name']} ({play['play_id']}) — score: {play['score']:.2f}"
        )
        print("   Reasons:")
        if play["reasons"]:
            for reason in play["reasons"]:
                print(f"   - {reason}")
        else:
            print("   - no positive matches")
        print()


if __name__ == "__main__":
    main()
