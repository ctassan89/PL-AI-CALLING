"""Pretty-print saved playcaller session logs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from pprint import pformat


SEPARATOR = "=" * 80


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the session log viewer."""
    parser = argparse.ArgumentParser(description="Pretty-print a saved session log.")
    parser.add_argument("log_path")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--compact", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--snap", type=int)
    parser.add_argument("--no-recommendations", action="store_true", dest="no_recommendations")
    parser.add_argument("--show-top", action="store_true")
    parser.add_argument("--show-raw", action="store_true")
    return parser.parse_args()


def clean_value(value: object, *, placeholder: str = "-") -> str:
    """Normalize empty or nan-like values into a readable placeholder."""
    if value is None:
        return placeholder
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return placeholder
    return text


def clean_csv_value(value: object) -> str:
    """Normalize empty or nan-like values into an empty string for processing."""
    normalized = clean_value(value, placeholder="")
    return normalized


def load_log_rows(path: str | Path) -> list[dict[str, str]]:
    """Load session log rows with the built-in CSV reader."""
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def select_rows(rows: list[dict[str, str]], snap: int | None) -> list[dict[str, str]]:
    """Optionally filter rows down to one snap number."""
    if snap is None:
        return rows
    return [row for row in rows if clean_csv_value(row.get("snap_number")) == str(snap)]


def ordinal(value: str) -> str:
    """Format a numeric down as an ordinal football label."""
    text = clean_csv_value(value)
    if text == "1":
        return "1st"
    if text == "2":
        return "2nd"
    if text == "3":
        return "3rd"
    if text == "4":
        return "4th"
    return f"{text}th" if text else "-"


def format_situation(row: dict[str, str]) -> str:
    """Format the current snap situation."""
    return (
        f"{ordinal(row.get('down', ''))} & {clean_value(row.get('distance'))} "
        f"{clean_value(row.get('field_position_label'))}"
    )


def format_next_situation(row: dict[str, str]) -> str:
    """Format the next snap situation after the recorded gain."""
    next_down = clean_csv_value(row.get("next_down"))
    next_distance = clean_csv_value(row.get("next_distance"))
    next_yardline = clean_csv_value(row.get("next_yardline"))
    if not (next_down or next_distance or next_yardline):
        return "-"
    next_label = yardline_to_label(next_yardline)
    return f"{ordinal(next_down)} & {clean_value(next_distance)} {next_label}"


def yardline_to_label(value: str) -> str:
    """Convert a numeric next-yardline into the same human-readable field label."""
    text = clean_csv_value(value)
    if not text:
        return "-"
    try:
        field_position = int(float(text))
    except ValueError:
        return text
    if field_position == 50:
        return "midfield"
    if field_position < 50:
        return f"own {field_position}"
    if field_position >= 100:
        return "opp 0"
    return f"opp {100 - field_position}"


def format_gain(value: str) -> str:
    """Format a numeric gain with sign when possible."""
    text = clean_csv_value(value)
    if not text:
        return "-"
    try:
        yards = int(float(text))
    except ValueError:
        return text
    return f"{yards:+d}"


def parse_recommendation_blocks(value: object) -> list[tuple[str, list[str]]]:
    """Expand the serialized recommendation block string into titled lists."""
    text = clean_csv_value(value)
    if not text:
        return []
    blocks: list[tuple[str, list[str]]] = []
    for raw_block in text.split("|"):
        block = raw_block.strip()
        if not block:
            continue
        if ":" not in block:
            blocks.append((block, []))
            continue
        title, plays = block.split(":", 1)
        items = [item.strip() for item in plays.split(",") if item.strip()]
        blocks.append((title.strip(), items))
    return blocks


def parse_top_recommendations(value: object) -> list[str]:
    """Parse the compact top_recommendations serialization."""
    text = clean_csv_value(value)
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def render_recommendations(
    row: dict[str, str],
    *,
    show_top: bool,
) -> str:
    """Render recommendation blocks with graceful fallback for older logs."""
    lines: list[str] = []
    blocks = parse_recommendation_blocks(row.get("recommendation_blocks"))
    if blocks:
        for title, plays in blocks:
            lines.append(title + ":")
            if plays:
                for index, play in enumerate(plays, start=1):
                    lines.append(f"{index}. {play}")
            else:
                lines.append("-")
            lines.append("")
    else:
        top = parse_top_recommendations(
            row.get("displayed_recommendations") or row.get("top_recommendations")
        )
        if top:
            lines.append("Recommendations:")
            for item in top:
                lines.append(item)
            lines.append("")
        else:
            lines.append("Recommendations: -")
            lines.append("")

    if show_top:
        top = parse_top_recommendations(
            row.get("displayed_recommendations") or row.get("top_recommendations")
        )
        lines.append("Top recommendations:")
        if top:
            lines.extend(top)
        else:
            lines.append("-")
        lines.append("")

    return "\n".join(lines).rstrip()


def render_result(row: dict[str, str]) -> str:
    """Render the gain and next-state summary cleanly."""
    gain = format_gain(clean_csv_value(row.get("yards_input")))
    next_state = format_next_situation(row)
    result = clean_csv_value(row.get("drive_result"))
    lines = [f"gain {gain} -> {next_state}"]
    if result and result != "ongoing":
        lines.append(f"Drive result: {result}")
    return "\n".join(lines)


def render_full_snap(
    row: dict[str, str],
    *,
    no_recommendations: bool,
    show_top: bool,
    show_raw: bool,
) -> str:
    """Render one snap in the default detailed view."""
    lines = [
        SEPARATOR,
        f"Snap {clean_value(row.get('snap_number'))} | {ordinal(row.get('down', ''))} & {clean_value(row.get('distance'))} | "
        f"{clean_value(row.get('field_position_label'))} | {clean_value(row.get('field_zone'))} | personnel {clean_value(row.get('personnel'))}",
        "Defense: "
        f"front={clean_value(row.get('front'))}, coverage={clean_value(row.get('coverage'))}, "
        f"pressure={clean_value(row.get('pressure'))}, box={clean_value(row.get('box'))}",
        f"Opponent: {clean_value(row.get('opponent'))}",
        f"Tendency bucket: {clean_value(row.get('matched_tendency_bucket'))}",
        f"Fallback: {clean_value(row.get('tendency_fallback_used'))}",
        "",
    ]
    if not no_recommendations:
        lines.append(render_recommendations(row, show_top=show_top) or "Recommendations: -")
        lines.append("")
    lines.append("Result:")
    lines.append(render_result(row))
    if show_raw:
        lines.append("")
        lines.append("Raw:")
        lines.append(pformat(row, sort_dicts=True))
    return "\n".join(lines).rstrip()


def compact_summary_row(row: dict[str, str]) -> dict[str, str]:
    """Build one compact summary record for table rendering."""
    return {
        "Snap": clean_value(row.get("snap_number")),
        "Situation": format_situation(row),
        "Personnel": clean_value(row.get("personnel")),
        "Gain": format_gain(clean_csv_value(row.get("yards_input"))),
        "Next": format_next_situation(row),
        "Fallback": clean_value(row.get("tendency_fallback_used")),
        "Result": clean_value(row.get("drive_result"), placeholder=""),
    }


def render_compact(rows: list[dict[str, str]]) -> str:
    """Render a compact table-like drive summary."""
    summary_rows = [compact_summary_row(row) for row in rows]
    headers = ["Snap", "Situation", "Personnel", "Gain", "Next", "Fallback", "Result"]
    widths = {
        header: max(len(header), *(len(record[header]) for record in summary_rows))
        for header in headers
    }
    lines = []
    header_line = " | ".join(header.ljust(widths[header]) for header in headers)
    lines.append(header_line)
    lines.append("-+-".join("-" * widths[header] for header in headers))
    for record in summary_rows:
        lines.append(" | ".join(record[header].ljust(widths[header]) for header in headers))
    return "\n".join(lines)


def main() -> None:
    """Run the session log viewer."""
    args = parse_args()
    rows = select_rows(load_log_rows(args.log_path), args.snap)
    if not rows:
        raise SystemExit("No matching session log rows found.")

    if args.compact:
        print(render_compact(rows))
        return

    for index, row in enumerate(rows):
        if index:
            print()
        print(
            render_full_snap(
                row,
                no_recommendations=args.no_recommendations,
                show_top=args.show_top,
                show_raw=args.show_raw,
            )
        )


if __name__ == "__main__":
    main()
