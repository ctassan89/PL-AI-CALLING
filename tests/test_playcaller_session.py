"""CLI tests for sequential play-calling sessions."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.validate_data import PLAYBOOK_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SESSION_SCRIPT = PROJECT_ROOT / "scripts" / "playcaller_session.py"


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
    *,
    pass_concept: str = "stick",
    beats_coverage: str = "cover3",
    beats_pressure: str = "none",
    preferred_down_distance: str = "early_down;second_medium;third_short",
    tags: str = "quick_game",
) -> dict[str, str]:
    """Build a playbook row for session CLI tests."""
    return {
        "play_id": play_id,
        "play_name": play_name,
        "play_family": "dropback",
        "play_type": "pass",
        "run_scheme": "none",
        "run_modifier": "none",
        "pass_concept": pass_concept,
        "pass_modifier": "none",
        "protection": "6man",
        "rpo_tag": "none",
        "play_action": "false",
        "formation_id": "gun_1rb_2x2_spread_no_te",
        "personnel": "10",
        "beats_front": "even;over;under",
        "beats_coverage": beats_coverage,
        "beats_pressure": beats_pressure,
        "beats_box": "light_box;normal_box;heavy_box",
        "preferred_down_distance": preferred_down_distance,
        "preferred_field_zone": "open_field;redzone;goal_line",
        "tags": tags,
    }


def run_session(
    playbook_path: Path,
    session_input: str,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    """Run the session CLI against a temp playbook."""
    command = [
        sys.executable,
        str(SESSION_SCRIPT),
        "--playbook-path",
        str(playbook_path),
        *extra_args,
    ]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        input=session_input,
        capture_output=True,
        text=True,
        check=False,
    )


def test_session_numeric_input_updates_offense_and_preserves_defense(tmp_path: Path) -> None:
    """Numeric updates should move the ball without changing defensive context."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("stick", "Stick TRIPS"),
            make_play("drive", "Drive TOP", pass_concept="spacing"),
            make_play("screen", "RB Screen TREY", pass_concept="rb_screen"),
        ],
    )

    result = run_session(
        playbook_path,
        "primo e 10 own 25 cover3 even box 6 personnel 10\n3\nq\n",
        "--top-n",
        "3",
    )

    assert result.returncode == 0
    assert "Current situation: 1st & 10, own 25, own_territory | front=even, coverage=cover3, pressure=none, box=6, personnel=10" in result.stdout
    assert "Current situation: 2nd & 7, own 28, own_territory | front=even, coverage=cover3, pressure=none, box=6, personnel=10" in result.stdout


def test_session_defense_update_preserves_offense(tmp_path: Path) -> None:
    """Defense-only text updates should keep down, distance, and field position unchanged."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("stick", "Stick TRIPS"),
            make_play(
                "screen",
                "RB Screen TREY",
                pass_concept="rb_screen",
                beats_pressure="nickel_blitz;any_pressure",
                tags="screen;quick_game;pressure_beater",
            ),
        ],
    )

    result = run_session(
        playbook_path,
        "primo e 10 own 25 cover3 even box 6 personnel 10\ncover1 nickel blitz box 6\nq\n",
        "--top-n",
        "2",
    )

    assert result.returncode == 0
    assert "Current situation: 1st & 10, own 25, own_territory | front=even, coverage=cover3, pressure=none, box=6, personnel=10" in result.stdout
    assert "Current situation: 1st & 10, own 25, own_territory | front=even, coverage=cover1, pressure=nickel_blitz, box=6, personnel=10" in result.stdout


def test_session_missing_defense_context_uses_defaults(tmp_path: Path) -> None:
    """Initial situations without defensive text should use the documented defaults."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS")],
    )

    result = run_session(playbook_path, "primo e 10 own 25\nq\n", "--top-n", "1")

    assert result.returncode == 0
    assert "front=none, coverage=none, pressure=none, box=none, personnel=none" in result.stdout


def test_session_top_n_controls_number_of_recommendations(tmp_path: Path) -> None:
    """The session CLI should respect --top-n."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("stick", "Stick TRIPS"),
            make_play("drive", "Drive TOP", pass_concept="spacing"),
            make_play("screen", "RB Screen TREY", pass_concept="rb_screen"),
        ],
    )

    result = run_session(playbook_path, "primo e 10 own 25\nq\n", "--top-n", "2")

    assert result.returncode == 0
    assert "Top 2 recommended plays:" in result.stdout
    assert result.stdout.count("\n1. ") == 1
    assert result.stdout.count("\n2. ") == 1
    assert "\n3. " not in result.stdout


def test_session_show_reasons_toggles_reason_output(tmp_path: Path) -> None:
    """Detailed reasons should stay behind the explicit flag."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS")],
    )

    default_result = run_session(playbook_path, "primo e 10 own 25\nq\n", "--top-n", "1")
    verbose_result = run_session(
        playbook_path,
        "primo e 10 own 25\nq\n",
        "--top-n",
        "1",
        "--show-reasons",
    )

    assert default_result.returncode == 0
    assert "reasons:" not in default_result.stdout
    assert verbose_result.returncode == 0
    assert "reasons:" in verbose_result.stdout
