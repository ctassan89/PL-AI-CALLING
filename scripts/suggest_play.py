"""Suggest the best offensive plays for a given game situation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = BASE_DIR / "data" / "playbook.csv"
DEFAULT_TENDENCIES_PATH = BASE_DIR / "data" / "opponent_tendencies.csv"
FORMATION_TAXONOMY_PATH = BASE_DIR / "data" / "taxonomy" / "formations.csv"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

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


def positive_int(value: str) -> int:
    """Parse a positive integer CLI argument."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


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
    parser.add_argument("--top-n", type=positive_int, default=3, dest="top_n")
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
        "--playbook-path",
        default=str(PLAYBOOK_PATH),
        dest="playbook_path",
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


def formation_label(play: dict[str, object], formation_names: dict[str, str]) -> str:
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
    if is_meaningful(
        pass_modifier,
        ignore={"", "none", "base", "vertical", "intermediate"},
    ):
        parts.append(humanize_token(pass_modifier))
    return " ".join(parts).strip()


def load_playbook_rows(playbook: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Build a play_id lookup for presentation details."""
    return {
        str(row.get("play_id", "")): {column: row.get(column, "") for column in row.index}
        for _, row in playbook.iterrows()
    }


def print_recommendations(
    plays: list[dict[str, object]],
    *,
    top_n: int,
    show_reasons: bool,
    formation_names: dict[str, str],
    playbook_rows: dict[str, dict[str, object]],
) -> None:
    """Print a compact recommendation list."""
    print(f"Top {top_n} recommended plays:\n")

    for rank, play in enumerate(plays, start=1):
        play_details = playbook_rows.get(str(play.get("play_id", "")), play)
        play_name = normalize_text(play_details.get("play_name")) or str(
            play.get("play_name", "")
        )
        formation = formation_label(play_details, formation_names)
        play_call = format_play_call(play_details, formation_names)
        print(f"{rank}. {play_name}")
        print(
            "   "
            f"score={float(play['score']):.2f} | "
            f"formation={formation or normalize_text(play.get('formation_id', ''))} | "
            f"personnel={normalize_text(play.get('personnel', ''))} | "
            f"type={normalize_text(play.get('play_type', ''))} | "
            f"call={play_call or play_name}"
        )
        if show_reasons:
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

    playbook = pd.read_csv(Path(args.playbook_path))
    formation_names = load_formation_names()
    playbook_rows = load_playbook_rows(playbook)

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

    top_plays = recommend_plays(
        playbook,
        situation,
        tendencies=tendencies,
        top_n=args.top_n,
        intent=args.intent,
    )

    if not top_plays:
        print("No plays matched the current filters.")
        return

    print_recommendations(
        top_plays,
        top_n=min(args.top_n, len(top_plays)),
        show_reasons=args.show_reasons,
        formation_names=formation_names,
        playbook_rows=playbook_rows,
    )


if __name__ == "__main__":
    main()
