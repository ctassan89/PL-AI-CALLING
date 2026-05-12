"""Tests for the session log viewer helpers and CLI."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts import view_session_log


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIEWER_SCRIPT = PROJECT_ROOT / "scripts" / "view_session_log.py"


def write_log(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a small session log CSV for viewer tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sample_rows() -> list[dict[str, str]]:
    """Build representative old-style session log rows."""
    return [
        {
            "snap_number": "1",
            "down": "1",
            "distance": "10",
            "field_position_label": "own 10",
            "field_zone": "own_territory",
            "personnel": "11",
            "front": "none",
            "coverage": "none",
            "pressure": "none",
            "box": "none",
            "opponent": "Rhinos",
            "matched_tendency_bucket": "opponent=rhinos, down=1, distance=medium, field_zone=open_field, personnel=11",
            "tendency_fallback_used": "no",
            "recommendation_blocks": "Run options: IZ Insert DOT, Outside Zone Toss TREY | RPO options: IZ Insert RPO Quick Out DOT, GT Counter RPO Double Slant TOP | Pass options: Stick TREY, Hitch DOT",
            "top_recommendations": "1. IZ Insert DOT (59.8); 2. Stick TREY (55.1)",
            "yards_input": "4",
            "next_down": "2",
            "next_distance": "6",
            "next_yardline": "14",
            "drive_result": "",
        },
        {
            "snap_number": "2",
            "down": "2",
            "distance": "6",
            "field_position_label": "own 14",
            "field_zone": "own_territory",
            "personnel": "11",
            "front": "none",
            "coverage": "none",
            "pressure": "none",
            "box": "none",
            "opponent": "Rhinos",
            "matched_tendency_bucket": "",
            "tendency_fallback_used": "no",
            "recommendation_blocks": "",
            "top_recommendations": "1. Stick TREY (62.0); 2. Hitch DOT (60.1)",
            "yards_input": "6",
            "next_down": "1",
            "next_distance": "10",
            "next_yardline": "20",
            "drive_result": "touchdown",
        },
    ]


def run_viewer(log_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the viewer CLI against a temp log."""
    return subprocess.run(
        [sys.executable, str(VIEWER_SCRIPT), str(log_path), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_parse_recommendation_blocks_expands_titles_and_plays() -> None:
    """Recommendation block parsing should split titles from play lists."""
    blocks = view_session_log.parse_recommendation_blocks(
        "Run options: IZ Insert DOT, Outside Zone Toss TREY | Pass options: Stick TREY (66.0)"
    )

    assert blocks == [
        ("Run options", ["IZ Insert DOT", "Outside Zone Toss TREY"]),
        ("Pass options", ["Stick TREY (66.0)"]),
    ]


def test_clean_value_converts_empty_and_nan_to_placeholder() -> None:
    """Empty and nan-like values should render cleanly."""
    assert view_session_log.clean_value("") == "-"
    assert view_session_log.clean_value("nan") == "-"
    assert view_session_log.clean_value(None) == "-"
    assert view_session_log.clean_value("own 25") == "own 25"


def test_compact_summary_row_formats_core_fields() -> None:
    """Compact summary rows should be easy to scan in a terminal."""
    record = view_session_log.compact_summary_row(sample_rows()[0])

    assert record["Situation"] == "1st & 10 own 10"
    assert record["Gain"] == "+4"
    assert record["Next"] == "2nd & 6 own 14"
    assert record["Fallback"] == "no"


def test_render_recommendations_falls_back_to_top_recommendations() -> None:
    """Missing recommendation_blocks should fall back to top recommendations."""
    rendered = view_session_log.render_recommendations(sample_rows()[1], show_top=False)

    assert "Recommendations:" in rendered
    assert "1. Stick TREY (62.0)" in rendered
    assert "nan" not in rendered.lower()


def test_select_rows_filters_to_one_snap() -> None:
    """Snap filtering should return only the requested row."""
    rows = view_session_log.select_rows(sample_rows(), 2)

    assert len(rows) == 1
    assert rows[0]["snap_number"] == "2"


def test_viewer_cli_snap_and_compact_render_cleanly(tmp_path: Path) -> None:
    """The CLI should render compact and single-snap views without nan noise."""
    log_path = tmp_path / "logs" / "test_drive_01.csv"
    write_log(log_path, sample_rows())

    compact = run_viewer(log_path, "--compact")
    snap_one = run_viewer(log_path, "--snap", "1")

    assert compact.returncode == 0
    assert "Snap | Situation" in compact.stdout
    assert "1st & 10 own 10" in compact.stdout
    assert "nan" not in compact.stdout.lower()

    assert snap_one.returncode == 0
    assert "Snap 1 | 1st & 10 | own 10 | own_territory | personnel 11" in snap_one.stdout
    assert "Run options:" in snap_one.stdout
    assert "1. IZ Insert DOT" in snap_one.stdout
    assert "2. Outside Zone Toss TREY" in snap_one.stdout
    assert "gain +4 -> 2nd & 6 own 14" in snap_one.stdout
    assert "Snap 2" not in snap_one.stdout
    assert "nan" not in snap_one.stdout.lower()
