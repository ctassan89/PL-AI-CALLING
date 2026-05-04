"""CLI tests for play suggestions."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.validate_data import PLAYBOOK_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUGGEST_SCRIPT = PROJECT_ROOT / "scripts" / "suggest_play.py"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write a CSV file with dict rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_play(
    play_id: str,
    play_name: str,
    formation_id: str,
    *,
    play_type: str = "pass",
    play_family: str = "dropback",
    run_scheme: str = "none",
    run_modifier: str = "none",
    pass_concept: str = "spacing",
    rpo_tag: str = "none",
    play_action: str = "false",
    beats_coverage: str = "cover3",
    beats_pressure: str = "none",
    preferred_down_distance: str = "second_medium",
    tags: str = "quick_game",
) -> dict[str, str]:
    """Build a playbook row for CLI tests."""
    return {
        "play_id": play_id,
        "play_name": play_name,
        "play_family": play_family,
        "play_type": play_type,
        "run_scheme": run_scheme,
        "run_modifier": run_modifier,
        "pass_concept": pass_concept,
        "pass_modifier": "none",
        "protection": "6man",
        "rpo_tag": rpo_tag,
        "play_action": play_action,
        "formation_id": formation_id,
        "personnel": "10",
        "beats_front": "even",
        "beats_coverage": beats_coverage,
        "beats_pressure": beats_pressure,
        "beats_box": "light_box;normal_box;heavy_box",
        "preferred_down_distance": preferred_down_distance,
        "preferred_field_zone": "open_field",
        "tags": tags,
    }


def run_suggest(playbook_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    """Run the suggest CLI against a temp playbook."""
    command = [
        sys.executable,
        str(SUGGEST_SCRIPT),
        "--down",
        "2",
        "--distance",
        "4",
        "--field-zone",
        "open_field",
        "--front",
        "even",
        "--coverage",
        "cover3",
        "--box-count",
        "6",
        "--personnel",
        "10",
        "--playbook-path",
        str(playbook_path),
        *extra_args,
    ]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_suggest_play_top_n_compact_output_and_concept_dedup(tmp_path: Path) -> None:
    """Default output should be compact and prefer unique concepts."""
    playbook_path = tmp_path / "playbook.csv"
    rows = [
        make_play(
            "spacing_dbls",
            "Spacing DBLS",
            "gun_1rb_2x2_spread_no_te",
            pass_concept="spacing",
        ),
        make_play(
            "spacing_dot",
            "Spacing DOT",
            "gun_1rb_2x2_spread_te_off",
            pass_concept="spacing",
        ),
        make_play(
            "stick_tango",
            "Stick TANGO",
            "gun_1rb_3x1_spread_y_middle",
            pass_concept="stick",
        ),
        make_play(
            "rpo_glance",
            "Power RPO Glance TRIPS",
            "gun_1rb_3x1_spread_no_te",
            play_type="rpo",
            play_family="rpo",
            run_scheme="power",
            pass_concept="glance",
            rpo_tag="glance",
            tags="quick_game",
        ),
        make_play(
            "pa_flood",
            "PA Flood DEUCE",
            "gun_1rb_2x2_spread_te_on",
            pass_concept="flood",
            play_action="true",
            tags="play_action",
        ),
    ]
    write_csv(playbook_path, list(PLAYBOOK_COLUMNS), rows)

    result = run_suggest(playbook_path, "--top-n", "3")

    assert result.returncode == 0
    assert "Top 3 recommended plays:" in result.stdout
    assert "Reasons:" not in result.stdout
    assert result.stdout.count("\n1. ") == 1
    assert result.stdout.count("\n2. ") == 1
    assert result.stdout.count("\n3. ") == 1
    assert "4." not in result.stdout
    assert "Spacing DBLS" in result.stdout
    assert "Spacing DOT" not in result.stdout


def test_suggest_play_shows_reasons_only_when_requested(tmp_path: Path) -> None:
    """Reasons should only appear behind the explicit flag."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play(
                "stick_tango",
                "Stick TANGO",
                "gun_1rb_3x1_spread_y_middle",
                pass_concept="stick",
            )
        ],
    )

    default_result = run_suggest(playbook_path, "--top-n", "1")
    verbose_result = run_suggest(playbook_path, "--top-n", "1", "--show-reasons")

    assert default_result.returncode == 0
    assert "Reasons:" not in default_result.stdout
    assert verbose_result.returncode == 0
    assert "Reasons:" in verbose_result.stdout


def test_suggest_play_accepts_pressure_id(tmp_path: Path) -> None:
    """The CLI should accept --pressure-id and surface pressure context."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play(
                "screen",
                "RB Screen DBLS",
                "gun_1rb_2x2_spread_no_te",
                pass_concept="rb_screen",
                beats_pressure="any_pressure;inside_blitz;double_a_gap;zero_pressure",
                tags="screen;quick_game;hot_answer",
            )
        ],
    )

    result = run_suggest(
        playbook_path,
        "--top-n",
        "1",
        "--pressure-id",
        "nickel_blitz",
        "--show-reasons",
    )

    assert result.returncode == 0
    assert "Pressure context: nickel_blitz" in result.stdout
    assert "pressure:" in result.stdout


def test_suggest_play_defaults_pressure_id_to_none(tmp_path: Path) -> None:
    """Omitting --pressure-id should behave like none."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TANGO", "gun_1rb_3x1_spread_y_middle")],
    )

    result = run_suggest(playbook_path, "--top-n", "1")

    assert result.returncode == 0
    assert "Pressure context:" not in result.stdout
