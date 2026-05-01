"""Tests for the CSV data validator."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.validate_data import PLAYBOOK_COLUMNS, validate_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = PROJECT_ROOT / "scripts" / "validate_data.py"
DEFENSIVE_TENDENCY_COLUMNS = [
    "team",
    "game_id",
    "down",
    "distance",
    "field_zone",
    "hash",
    "offensive_personnel",
    "offensive_formation_id",
    "defensive_personnel_id",
    "front_id",
    "box_count",
    "coverage_id",
    "blitzers",
    "movement_type",
    "sample_size",
    "frequency",
    "success_rate_allowed",
    "epa_allowed",
    "notes",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write a CSV file with dict rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_single_column_taxonomy(path: Path, values: list[str]) -> None:
    """Write a one-column taxonomy file."""
    write_csv(path, ["value"], [{"value": value} for value in values])


def build_valid_playbook_row(**overrides: str) -> dict[str, str]:
    """Create a minimal valid playbook row and allow targeted overrides."""
    row = {
        "play_id": "power_dbls",
        "play_name": "Power DBLS",
        "play_family": "run",
        "play_type": "run",
        "run_scheme": "power",
        "run_modifier": "none",
        "pass_concept": "none",
        "pass_modifier": "none",
        "protection": "none",
        "rpo_tag": "none",
        "play_action": "false",
        "formation_id": "gun_1rb_2x2_spread_no_te",
        "personnel": "10",
        "beats_front": "even;over;under",
        "beats_coverage": "none",
        "beats_box": "light_box;normal_box",
        "preferred_down_distance": "early_down;second_short;third_short;fourth_short",
        "preferred_field_zone": "any",
        "tags": "inside_run;gap_scheme",
    }
    row.update(overrides)
    return row


def build_valid_defensive_tendency_row(**overrides: str) -> dict[str, str]:
    """Create a minimal valid defensive tendency row."""
    row = {
        "team": "test_team",
        "game_id": "game_001",
        "down": "1",
        "distance": "short",
        "field_zone": "midfield",
        "hash": "middle",
        "offensive_personnel": "10",
        "offensive_formation_id": "gun_1rb_2x2_spread_no_te",
        "defensive_personnel_id": "nickel",
        "front_id": "even",
        "box_count": "6",
        "coverage_id": "cover3",
        "blitzers": "4",
        "movement_type": "static",
        "sample_size": "12",
        "frequency": "0.5",
        "success_rate_allowed": "0.42",
        "epa_allowed": "-0.1",
        "notes": "baseline",
    }
    row.update(overrides)
    return row


def create_fake_repo(
    tmp_path: Path,
    *,
    playbook_rows: list[dict[str, str]] | None = None,
    defensive_tendency_rows: list[dict[str, str]] | None = None,
    playbook_columns: list[str] | None = None,
    valid_run_pairs: list[tuple[str, str]] | None = None,
) -> Path:
    """Create a minimal fake repo layout with valid taxonomy and raw data."""
    taxonomy_dir = tmp_path / "data" / "taxonomy"
    raw_dir = tmp_path / "data" / "raw"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    single_column_taxonomies = {
        "play_family.csv": ["run", "pass"],
        "play_type.csv": ["run", "pass"],
        "run_scheme.csv": ["power"],
        "run_modifier.csv": ["none", "read"],
        "pass_concept.csv": ["none"],
        "pass_modifier.csv": ["none"],
        "protection.csv": ["none"],
        "rpo_tag.csv": ["none"],
        "play_action.csv": ["false", "true"],
        "personnel.csv": ["10"],
        "beats_front.csv": ["any", "none", "even", "odd", "odd_tite", "bear", "over", "under"],
        "beats_coverage.csv": ["none", "zone", "man", "cover1", "cover2", "cover3", "cover4", "match", "soft_zone"],
        "beats_box.csv": ["light_box", "normal_box", "heavy_box", "loaded_box"],
        "preferred_down_distance.csv": [
            "any",
            "early_down",
            "second_short",
            "second_medium",
            "second_long",
            "third_short",
            "third_medium",
            "third_long",
            "fourth_short",
            "fourth_medium",
            "shot_play",
        ],
        "preferred_field_zone.csv": [
            "any",
            "open_field",
            "backed_up",
            "coming_out",
            "plus_territory",
            "high_redzone",
            "redzone",
            "goal_line",
        ],
        "tags.csv": ["inside_run", "gap_scheme"],
    }
    for filename, values in single_column_taxonomies.items():
        write_single_column_taxonomy(taxonomy_dir / filename, values)

    write_csv(
        taxonomy_dir / "valid_run_scheme_modifier_pairs.csv",
        ["run_scheme", "run_modifier"],
        [
            {
                "run_scheme": run_scheme,
                "run_modifier": run_modifier,
            }
            for run_scheme, run_modifier in (valid_run_pairs or [("power", "none")])
        ],
    )
    write_csv(
        taxonomy_dir / "fronts.csv",
        ["front_id"],
        [{"front_id": "even"}],
    )
    write_csv(
        taxonomy_dir / "coverages.csv",
        ["coverage_id"],
        [{"coverage_id": "cover3"}],
    )
    write_csv(
        taxonomy_dir / "defensive_personnel.csv",
        ["defensive_personnel_id"],
        [{"defensive_personnel_id": "nickel"}],
    )
    write_csv(
        taxonomy_dir / "offensive_formations.csv",
        ["formation_id"],
        [{"formation_id": "gun_1rb_2x2_spread_no_te"}],
    )

    write_csv(
        raw_dir / "playbook.csv",
        playbook_columns or list(PLAYBOOK_COLUMNS),
        playbook_rows or [build_valid_playbook_row()],
    )
    write_csv(
        raw_dir / "defensive_tendencies.csv",
        DEFENSIVE_TENDENCY_COLUMNS,
        defensive_tendency_rows or [build_valid_defensive_tendency_row()],
    )
    return tmp_path


def run_validator_cli(base_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the validator CLI against a temporary fake repo."""
    return subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "--base-dir", str(base_dir)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_data_accepts_valid_dataset(tmp_path: Path) -> None:
    """A valid fake repo should pass both importable and CLI validation."""
    create_fake_repo(tmp_path)

    assert validate_data(tmp_path) == []

    result = run_validator_cli(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "Data validation passed."


def test_validate_data_rejects_invalid_scalar_value(tmp_path: Path) -> None:
    """An invalid scalar taxonomy value should produce a row-specific error."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_scalar", play_type="bad_type")],
    )

    errors = validate_data(tmp_path)

    assert errors
    assert any(
        "playbook row" in error
        and "bad_scalar" in error
        and "invalid play_type" in error
        and "bad_type" in error
        for error in errors
    )


def test_validate_data_rejects_invalid_multi_value_token(tmp_path: Path) -> None:
    """An invalid semicolon-delimited token should identify the bad token and row."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_front", beats_front="even;fake_front")],
    )

    errors = validate_data(tmp_path)

    assert errors
    assert any(
        "playbook row 2" in error
        and "bad_front" in error
        and "invalid beats_front token" in error
        and "fake_front" in error
        for error in errors
    )


def test_validate_data_rejects_invalid_run_scheme_modifier_pair(tmp_path: Path) -> None:
    """A valid scalar pair that is not allowed together should be rejected clearly."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_pair", run_modifier="read")],
        valid_run_pairs=[("power", "none")],
    )

    errors = validate_data(tmp_path)

    assert errors
    assert any(
        "bad_pair" in error
        and "invalid run_scheme/run_modifier pair" in error
        and "run_scheme='power'" in error
        and "run_modifier='read'" in error
        for error in errors
    )


def test_validate_data_rejects_bad_column_order(tmp_path: Path) -> None:
    """The playbook must keep the exact documented column order."""
    swapped_columns = list(PLAYBOOK_COLUMNS)
    swapped_columns[0], swapped_columns[1] = swapped_columns[1], swapped_columns[0]
    create_fake_repo(
        tmp_path,
        playbook_columns=swapped_columns,
        playbook_rows=[build_valid_playbook_row()],
    )

    errors = validate_data(tmp_path)

    assert errors
    assert any("playbook.csv must use exact column order" in error for error in errors)


def test_validate_data_cli_prints_clear_errors(tmp_path: Path) -> None:
    """The CLI should exit non-zero and print bullet-pointed, row-specific errors."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="cli_bad", beats_front="even;fake_front")],
    )

    result = run_validator_cli(tmp_path)

    assert result.returncode == 1
    stdout_lines = result.stdout.strip().splitlines()
    assert stdout_lines[0] == "Data validation failed:"
    assert any(line.startswith("- ") for line in stdout_lines[1:])
    assert "playbook row 2" in result.stdout
    assert "cli_bad" in result.stdout
    assert "fake_front" in result.stdout
