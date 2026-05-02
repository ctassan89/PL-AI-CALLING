"""Tests for the CSV data validator."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.validate_data import PLAYBOOK_COLUMNS, validate_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = PROJECT_ROOT / "scripts" / "validate_data.py"
OPPONENT_TENDENCY_COLUMNS = [
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


def project_rows(
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Project row dictionaries onto the requested CSV field list."""
    return [{fieldname: row.get(fieldname, "") for fieldname in fieldnames} for row in rows]


def write_single_column_taxonomy(path: Path, values: list[str]) -> None:
    """Write a one-column taxonomy file."""
    write_csv(path, ["value"], [{"value": value} for value in values])


def build_valid_playbook_row(**overrides: str) -> dict[str, str]:
    """Create a valid playbook row and allow targeted overrides."""
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


def build_valid_opponent_tendency_row(**overrides: str) -> dict[str, str]:
    """Create a valid opponent tendency row."""
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
    opponent_rows: list[dict[str, str]] | None = None,
    playbook_columns: list[str] | None = None,
    include_opponent_file: bool = True,
    valid_run_pairs: list[tuple[str, str]] | None = None,
) -> Path:
    """Create a minimal fake repo layout with valid taxonomy and data."""
    taxonomy_dir = tmp_path / "data" / "taxonomy"
    playbook_path = tmp_path / "data" / "playbook.csv"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)

    single_column_taxonomies = {
        "play_family.csv": ["run", "pass", "rpo"],
        "play_type.csv": ["run", "pass", "rpo"],
        "run_scheme.csv": ["power", "inside_zone"],
        "run_modifier.csv": ["none", "read"],
        "pass_concept.csv": ["none", "stick"],
        "pass_modifier.csv": ["none"],
        "protection.csv": ["none"],
        "rpo_tag.csv": ["none", "stick"],
        "play_action.csv": ["false", "true"],
        "personnel.csv": ["10"],
        "beats_front.csv": ["any", "none", "even", "over", "under"],
        "beats_coverage.csv": ["none", "any", "zone", "cover3"],
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
            "fourth_long",
        ],
        "preferred_field_zone.csv": [
            "any",
            "open_field",
            "high_redzone",
            "redzone",
            "goal_line",
        ],
        "tags.csv": ["inside_run", "gap_scheme", "quick_game"],
    }
    for filename, values in single_column_taxonomies.items():
        write_single_column_taxonomy(taxonomy_dir / filename, values)

    write_csv(
        taxonomy_dir / "valid_run_scheme_modifier_pairs.csv",
        ["run_scheme", "run_modifier"],
        [
            {"run_scheme": run_scheme, "run_modifier": run_modifier}
            for run_scheme, run_modifier in (valid_run_pairs or [("power", "none")])
        ],
    )
    write_csv(taxonomy_dir / "fronts.csv", ["front_id"], [{"front_id": "even"}])
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
        taxonomy_dir / "formations.csv",
        ["formation_id", "formation_name"],
        [{"formation_id": "gun_1rb_2x2_spread_no_te", "formation_name": "DBLS"}],
    )

    write_csv(
        playbook_path,
        playbook_columns or list(PLAYBOOK_COLUMNS),
        project_rows(
            playbook_columns or list(PLAYBOOK_COLUMNS),
            playbook_rows or [build_valid_playbook_row()],
        ),
    )

    if include_opponent_file:
        write_csv(
            tmp_path / "data" / "opponent_tendencies.csv",
            OPPONENT_TENDENCY_COLUMNS,
            opponent_rows or [build_valid_opponent_tendency_row()],
        )

    return tmp_path


def run_validator_cli(base_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the validator CLI against a temporary repo."""
    return subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "--base-dir", str(base_dir)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_data_accepts_valid_dataset(tmp_path: Path) -> None:
    """A valid fake repo should pass importable and CLI validation."""
    create_fake_repo(tmp_path)

    assert validate_data(base_dir=tmp_path) == []

    result = run_validator_cli(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "Data validation passed."


def test_validate_data_allows_missing_optional_opponent_file(tmp_path: Path) -> None:
    """Opponent tendencies should be validated only when present."""
    create_fake_repo(tmp_path, include_opponent_file=False)

    assert validate_data(base_dir=tmp_path) == []


def test_validate_data_reports_missing_required_playbook_columns(tmp_path: Path) -> None:
    """The validator should report missing playbook columns."""
    create_fake_repo(
        tmp_path,
        playbook_columns=[column for column in PLAYBOOK_COLUMNS if column != "tags"],
    )

    errors = validate_data(base_dir=tmp_path)

    assert any("playbook.csv is missing required columns: tags" in error for error in errors)


def test_validate_data_rejects_invalid_taxonomy_value(tmp_path: Path) -> None:
    """Invalid taxonomy values should produce row-specific errors."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[
            build_valid_playbook_row(play_id="bad_front", beats_front="even;ghost_front")
        ],
    )

    errors = validate_data(base_dir=tmp_path)

    assert any(
        "playbook row 2 (bad_front): invalid beats_front token(s): 'ghost_front'."
        == error
        for error in errors
    )


def test_validate_data_cli_reports_errors_for_temp_repo(tmp_path: Path) -> None:
    """The CLI should fail cleanly for invalid temporary input."""
    create_fake_repo(
        tmp_path,
        opponent_rows=[build_valid_opponent_tendency_row(coverage_id="bad_coverage")],
    )

    result = run_validator_cli(tmp_path)

    assert result.returncode == 1
    assert "Data validation failed:" in result.stdout
    assert "coverage_id 'bad_coverage'" in result.stdout
