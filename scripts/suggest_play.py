"""Suggest the best offensive plays for a given game situation."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "raw" / "playbook.csv"


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
    return parser.parse_args()


def parse_list(value: object) -> list[str]:
    """Split a semicolon-separated field into normalized values."""
    return [item.strip() for item in str(value).split(";") if item.strip()]


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


def score_play(play: pd.Series, situation: dict[str, str]) -> tuple[int, list[str]]:
    """Score a play against the current situation and collect match reasons."""
    score = 0
    reasons: list[str] = []

    front_values = parse_list(play["beats_front"])
    if matches_category(front_values, situation["front_id"]):
        score += 3
        reasons.append(f"front match: {situation['front_id']}")

    coverage_values = parse_list(play["beats_coverage"])
    if matches_category(coverage_values, situation["coverage_id"]):
        score += 3
        reasons.append(f"coverage match: {situation['coverage_id']}")

    box_values = parse_list(play["beats_box"])
    if matches_category(box_values, situation["box_label"]):
        score += 2
        reasons.append(f"box match: {situation['box_label']}")

    if str(play["formation_id"]) == situation["formation_id"]:
        score += 2
        reasons.append(f"formation match: {situation['formation_id']}")

    distance_values = parse_list(play["preferred_down_distance"])
    if matches_category(distance_values, situation["distance"]):
        score += 1
        reasons.append(f"distance match: {situation['distance']}")

    field_zone_values = parse_list(play["preferred_field_zone"])
    if matches_category(field_zone_values, situation["field_zone"]):
        score += 1
        reasons.append(f"field zone match: {situation['field_zone']}")

    return score, reasons


def main() -> None:
    """Load the playbook, score plays, and print the top recommendations."""
    args = parse_args()
    playbook = pd.read_csv(PLAYBOOK_PATH)

    situation = {
        "down": str(args.down),
        "distance": args.distance,
        "field_zone": args.field_zone,
        "formation_id": args.formation_id,
        "front_id": args.front_id,
        "coverage_id": args.coverage_id,
        "box_label": map_box_count(args.box_count),
    }

    recommendations: list[dict[str, object]] = []
    for _, play in playbook.iterrows():
        score, reasons = score_play(play, situation)
        recommendations.append(
            {
                "play_name": str(play["play_name"]),
                "play_id": str(play["play_id"]),
                "score": score,
                "reasons": reasons,
            }
        )

    top_plays = sorted(
        recommendations,
        key=lambda play: (-int(play["score"]), str(play["play_name"]), str(play["play_id"])),
    )[:3]

    print("Top 3 recommended plays:\n")
    for rank, play in enumerate(top_plays, start=1):
        print(
            f"{rank}. {play['play_name']} ({play['play_id']}) — score: {play['score']}"
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
