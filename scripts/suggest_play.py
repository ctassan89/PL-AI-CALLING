"""Suggest the best offensive plays for a given game situation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "playbook.csv"
DEFAULT_TENDENCIES_PATH = BASE_DIR / "data" / "opponent_tendencies.csv"
FORMATION_TAXONOMY_PATH = BASE_DIR / "data" / "taxonomy" / "offensive_formations.csv"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

import pandas as pd

from opponent.tendencies import OpponentTendencyAnalyzer
from recommendation.engine import build_situation, recommend_plays


def load_formation_names() -> dict[str, str]:
    """Load formation_id to short display name mappings."""
    with FORMATION_TAXONOMY_PATH.open(newline="") as handle:
        return {
            str(row.get("formation_id", "")).strip(): str(
                row.get("formation_name", "")
            ).strip()
            for row in csv.DictReader(handle)
            if str(row.get("formation_id", "")).strip()
        }


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
        "--verbose",
        action="store_true",
        help="Print detailed scoring reasons.",
    )
    parser.add_argument(
        "--opponent-tendencies-path",
        default=str(DEFAULT_TENDENCIES_PATH),
        dest="opponent_tendencies_path",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    """Normalize missing-like scalar values."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def is_meaningful(value: object, *, ignore: set[str] | None = None) -> bool:
    """Return whether a value should be displayed."""
    normalized = normalize_text(value).lower()
    ignored = ignore or {"", "none"}
    return normalized not in ignored


def humanize_token(value: object) -> str:
    """Convert schema tokens into a readable play-call fragment."""
    replacements = {
        "gt": "GT",
        "gy": "GY",
        "qb": "QB",
        "rpo": "RPO",
        "pa": "PA",
        "te": "TE",
    }
    token = normalize_text(value)
    if not token:
        return ""
    words: list[str] = []
    for part in token.split("_"):
        lower = part.lower()
        words.append(replacements.get(lower, lower.capitalize()))
    return " ".join(words)


def formation_label(
    play: dict[str, object],
    formation_names: dict[str, str],
) -> str:
    """Return a short formation name for a play."""
    formation_id = normalize_text(play.get("formation_id", ""))
    if not formation_id:
        return ""
    return formation_names.get(formation_id, formation_id)


def format_play_call(
    play: dict[str, object],
    formation_names: dict[str, str],
) -> str:
    """Build a readable football play call from the play schema."""
    formation = formation_label(play, formation_names)
    play_type = normalize_text(play.get("play_type", "")).lower()
    run_scheme = normalize_text(play.get("run_scheme", ""))
    run_modifier = normalize_text(play.get("run_modifier", ""))
    pass_concept = normalize_text(play.get("pass_concept", ""))
    pass_modifier = normalize_text(play.get("pass_modifier", ""))
    rpo_tag = normalize_text(play.get("rpo_tag", ""))

    parts = [formation] if formation else []
    if play_type == "run":
        if is_meaningful(run_scheme):
            parts.append(humanize_token(run_scheme))
        if is_meaningful(run_modifier):
            parts.append(humanize_token(run_modifier))
        return " ".join(parts).strip()

    if play_type == "rpo":
        if is_meaningful(run_scheme):
            parts.append(humanize_token(run_scheme))
        if is_meaningful(run_modifier):
            parts.append(humanize_token(run_modifier))
        parts.append("RPO")
        target = rpo_tag if is_meaningful(rpo_tag) else pass_concept
        if is_meaningful(target):
            parts.append(humanize_token(target))
        return " ".join(parts).strip()

    if is_meaningful(pass_concept):
        parts.append(humanize_token(pass_concept))
    if is_meaningful(pass_modifier, ignore={"", "none", "base", "vertical", "intermediate"}):
        parts.append(humanize_token(pass_modifier))
    return " ".join(parts).strip()


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
    verbose: bool,
    formation_names: dict[str, str],
    playbook_rows: dict[str, dict[str, object]],
) -> None:
    """Print a formatted recommendation section."""
    print(title)
    print(f"Opponent tendencies used: {'yes' if tendencies_used else 'no'}\n")
    for rank, play in enumerate(plays, start=1):
        play_details = playbook_rows.get(str(play.get("play_id", "")), play)
        concept_scheme = play.get("concept_scheme", "")
        formation = formation_label(play_details, formation_names)
        play_call = format_play_call(play_details, formation_names)
        duplicate_label = " | fallback duplicate concept" if play.get("duplicate_fallback") else ""
        print(
            f"{rank}. {play_call or play['play_name']} | "
            f"play_id={play['play_id']} | "
            f"score={play['score']:.2f} | "
            f"formation={formation or play.get('formation_id', '')} | "
            f"personnel={play.get('personnel', '')} | "
            f"play_type={play.get('play_type', '')} | "
            f"concept/scheme={concept_scheme}{duplicate_label}"
        )
        if verbose:
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
    formation_names = load_formation_names()
    playbook_rows = {
        str(row.get("play_id", "")): {column: row.get(column, "") for column in row.index}
        for _, row in playbook.iterrows()
    }

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
                f"{section_title(intent)} (Top {args.top_n})",
                plays,
                top_n=args.top_n,
                tendencies_used=bool(tendencies),
                verbose=args.verbose,
                formation_names=formation_names,
                playbook_rows=playbook_rows,
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
        f"{section_title(selected_intent)} (Top {args.top_n})"
        if is_second_and_short(situation)
        else f"Top {args.top_n} recommended plays"
    )
    print_recommendations(
        title,
        top_plays,
        top_n=args.top_n,
        tendencies_used=bool(tendencies),
        verbose=args.verbose,
        formation_names=formation_names,
        playbook_rows=playbook_rows,
    )


if __name__ == "__main__":
    main()
