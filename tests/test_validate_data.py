"""Tests for the CSV data validator."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.validate_data import COVERAGES_COLUMNS, PLAYBOOK_COLUMNS, validate_data


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
        "beats_pressure": "none",
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
    taxonomy_overrides: dict[str, list[str]] | None = None,
) -> Path:
    """Create a minimal fake repo layout with valid taxonomy and data."""
    taxonomy_dir = tmp_path / "data" / "taxonomy"
    playbook_values_dir = taxonomy_dir / "playbook_values"
    coverage_values_dir = taxonomy_dir / "coverage_values"
    playbook_path = tmp_path / "data" / "playbook.csv"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)
    playbook_values_dir.mkdir(parents=True, exist_ok=True)
    coverage_values_dir.mkdir(parents=True, exist_ok=True)

    playbook_value_taxonomies = {
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
    coverage_value_taxonomies = {
        "coverage_id.csv": ["cover3"],
        "base_coverage.csv": ["cover3"],
        "coverage_family.csv": ["zone"],
        "pre_snap_shell.csv": ["one_high"],
        "post_snap_shell.csv": ["one_high"],
        "coverage_type.csv": ["zone"],
        "rotation_type.csv": ["none"],
        "rotation_target.csv": ["none"],
        "rotation_reference.csv": ["none"],
        "strength_rule.csv": ["none"],
        "weakness_tags.csv": ["seam", "curl_window", "flat_late"],
    }
    for filename, values in (taxonomy_overrides or {}).items():
        if filename in coverage_value_taxonomies:
            coverage_value_taxonomies[filename] = values
        else:
            playbook_value_taxonomies[filename] = values
    for filename, values in playbook_value_taxonomies.items():
        write_single_column_taxonomy(playbook_values_dir / filename, values)
    for filename, values in coverage_value_taxonomies.items():
        write_single_column_taxonomy(coverage_values_dir / filename, values)
    write_single_column_taxonomy(
        playbook_values_dir / "pressure.csv",
        ["none", "any_pressure", "edge_blitz", "field_blitz", "boundary_blitz", "nickel_blitz", "inside_blitz", "double_a_gap", "zero_pressure", "sim_pressure", "creeper"],
    )

    write_csv(
        playbook_values_dir / "valid_run_scheme_modifier_pairs.csv",
        ["run_scheme", "run_modifier"],
        [
            {"run_scheme": run_scheme, "run_modifier": run_modifier}
            for run_scheme, run_modifier in (valid_run_pairs or [("power", "none")])
        ],
    )
    write_csv(taxonomy_dir / "fronts.csv", ["front_id"], [{"front_id": "even"}])
    write_csv(
        taxonomy_dir / "coverages.csv",
        list(COVERAGES_COLUMNS),
        [
            {
                "coverage_id": "cover3",
                "coverage_name": "Cover 3",
                "base_coverage": "cover3",
                "coverage_family": "zone",
                "pre_snap_shell": "one_high",
                "post_snap_shell": "one_high",
                "coverage_type": "zone",
                "rotation_type": "none",
                "rotation_target": "none",
                "rotation_reference": "none",
                "strength_rule": "none",
                "weakness_tags": "seam;curl_window;flat_late",
                "offensive_notes": "baseline",
                "source_url": "none",
            }
        ],
    )
    write_csv(
        playbook_values_dir / "defensive_personnel.csv",
        ["defensive_personnel_id"],
        [{"defensive_personnel_id": "nickel"}],
    )
    write_csv(
        taxonomy_dir / "formations.csv",
        ["formation_id", "formation_name", "personnel"],
        [
            {
                "formation_id": "gun_1rb_2x2_spread_no_te",
                "formation_name": "DBLS",
                "personnel": "10",
            }
        ],
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


def test_playbook_columns_include_beats_pressure_after_coverage() -> None:
    """The playbook schema should place beats_pressure after beats_coverage."""
    coverage_index = PLAYBOOK_COLUMNS.index("beats_coverage")
    assert PLAYBOOK_COLUMNS[coverage_index + 1] == "beats_pressure"


def test_validate_data_accepts_new_pass_concepts_and_protections(tmp_path: Path) -> None:
    """New pass concepts should validate with the normalized protection values."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[
            build_valid_playbook_row(
                play_id="drive_dbls",
                play_name="Drive DBLS",
                play_family="pass",
                play_type="pass",
                run_scheme="none",
                pass_concept="drive",
                protection="5man",
                beats_front="none",
                beats_coverage="zone;cover3",
                beats_pressure="sim_pressure;creeper",
                beats_box="none",
                preferred_down_distance="second_medium;third_medium",
                preferred_field_zone="open_field;midfield",
                tags="intermediate_pass",
            ),
            build_valid_playbook_row(
                play_id="wr_tunnel_screen_dbls",
                play_name="WR Tunnel Screen DBLS",
                play_family="pass",
                play_type="pass",
                run_scheme="none",
                pass_concept="wr_tunnel_screen",
                protection="quick",
                beats_front="none",
                beats_coverage="zone;cover3",
                beats_pressure="edge_blitz;field_blitz;nickel_blitz;sim_pressure",
                beats_box="light_box;normal_box",
                preferred_down_distance="early_down;second_medium",
                preferred_field_zone="open_field;midfield",
                tags="quick_game",
            ),
            build_valid_playbook_row(
                play_id="rb_screen_dbls",
                play_name="RB Screen DBLS",
                play_family="pass",
                play_type="pass",
                run_scheme="none",
                pass_concept="rb_screen",
                protection="screen",
                beats_front="none",
                beats_coverage="zone;cover3",
                beats_pressure="any_pressure;inside_blitz;double_a_gap;zero_pressure",
                beats_box="light_box;normal_box",
                preferred_down_distance="second_long;third_long",
                preferred_field_zone="open_field;midfield",
                tags="quick_game",
            ),
        ],
        taxonomy_overrides={
            "run_scheme.csv": ["power", "inside_zone", "none"],
            "pass_concept.csv": ["none", "stick", "drive", "wr_tunnel_screen", "rb_screen"],
            "protection.csv": ["none", "quick", "5man", "6man", "boot", "screen"],
            "beats_front.csv": ["any", "none", "even", "over", "under"],
            "beats_coverage.csv": ["none", "any", "zone", "cover3"],
            "beats_box.csv": ["none", "light_box", "normal_box", "heavy_box", "loaded_box"],
            "preferred_down_distance.csv": [
                "any",
                "early_down",
                "second_medium",
                "third_medium",
                "second_long",
                "third_long",
            ],
            "preferred_field_zone.csv": ["any", "open_field", "midfield"],
            "tags.csv": ["inside_run", "gap_scheme", "quick_game", "intermediate_pass"],
        },
        valid_run_pairs=[("power", "none"), ("inside_zone", "none"), ("none", "none")],
    )

    assert validate_data(base_dir=tmp_path) == []


def test_validate_data_rejects_invalid_protection_value(tmp_path: Path) -> None:
    """Legacy protection labels should fail against the current taxonomy."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_protection", protection="quick_5man")],
        taxonomy_overrides={
            "protection.csv": ["none", "quick", "5man", "6man", "boot", "screen"],
        },
    )

    errors = validate_data(base_dir=tmp_path)

    assert any(
        error == "playbook row 2 (bad_protection): invalid protection 'quick_5man'."
        for error in errors
    )


def test_validate_data_rejects_invalid_pressure_value(tmp_path: Path) -> None:
    """beats_pressure must use the allowed pressure taxonomy values."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_pressure", beats_pressure="ghost_pressure")],
    )

    errors = validate_data(base_dir=tmp_path)

    assert any(
        error == "playbook row 2 (bad_pressure): invalid beats_pressure token(s): 'ghost_pressure'."
        for error in errors
    )


def test_validate_data_rejects_pressure_value_inside_beats_coverage(tmp_path: Path) -> None:
    """Pressure values should not be accepted inside beats_coverage."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_coverage", beats_coverage="cover3;nickel_blitz")],
        taxonomy_overrides={"beats_coverage.csv": ["none", "any", "zone", "cover3", "cover4", "man", "match", "soft_zone"]},
    )

    errors = validate_data(base_dir=tmp_path)

    assert any(
        error == "playbook row 2 (bad_coverage): invalid beats_coverage token(s): 'nickel_blitz'."
        for error in errors
    )


def test_validate_data_rejects_run_pressure_answers(tmp_path: Path) -> None:
    """Pure run plays should keep beats_pressure at none."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="run_pressure", beats_pressure="edge_blitz")],
    )

    errors = validate_data(base_dir=tmp_path)

    assert any(
        error == "playbook row 2 (run_pressure): run plays must use beats_pressure='none', got 'edge_blitz'."
        for error in errors
    )


def test_validate_data_rejects_playbook_formation_personnel_mismatch(tmp_path: Path) -> None:
    """Playbook rows should match formation personnel when the taxonomy provides it."""
    create_fake_repo(
        tmp_path,
        playbook_rows=[build_valid_playbook_row(play_id="bad_personnel", personnel="11")],
        taxonomy_overrides={"personnel.csv": ["10", "11"]},
    )

    errors = validate_data(base_dir=tmp_path)

    assert any(
        error
        == "playbook row 2 (bad_personnel): personnel '11' does not match formation_id 'gun_1rb_2x2_spread_no_te' personnel '10'."
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


def test_real_coverages_taxonomy_keeps_specific_variants() -> None:
    """The full coverage taxonomy should retain specific scouting variants."""
    values = {
        row["coverage_id"].strip()
        for row in csv.DictReader((PROJECT_ROOT / "data" / "taxonomy" / "coverages.csv").open(newline=""))
        if row.get("coverage_id")
    }

    assert "cover3_buzz_field" in values
    assert "cover3_cloud_boundary" in values
    assert "cover4_poach_trips" in values
    assert "cover7_stubbie_trips" in values


def test_real_coverage_id_allowlist_keeps_specific_variants() -> None:
    """Defensive coverage_id allowlist should include specific taxonomy IDs."""
    values = {
        row["value"].strip()
        for row in csv.DictReader((PROJECT_ROOT / "data" / "taxonomy" / "coverage_values" / "coverage_id.csv").open(newline=""))
        if row.get("value")
    }

    assert "cover3_buzz_field" in values
    assert "cover4_poach_trips" in values
    assert "cover7_stubbie_trips" in values


def test_real_beats_coverage_allowlist_stays_conservative() -> None:
    """beats_coverage should stay playbook-facing, not scouting-variant-facing."""
    values = {
        row["value"].strip()
        for row in csv.DictReader((PROJECT_ROOT / "data" / "taxonomy" / "playbook_values" / "beats_coverage.csv").open(newline=""))
        if row.get("value")
    }

    assert "cover3_buzz_field" not in values
    assert "cover4_poach_trips" not in values
    assert "cover7_stubbie_trips" not in values
    assert "seam" not in values
    assert "curl_window" not in values
    assert "flat_late" not in values
    assert "mesh" not in values
    assert "four_verts" not in values
    assert "stick" not in values
    assert "inside_run" not in values
    assert "rb_checkdown" not in values


def test_real_taxonomy_subdirectories_exist_without_legacy_allowed_values_dir() -> None:
    """Allowed-value files should live under taxonomy subdirectories only."""
    assert not (PROJECT_ROOT / "data" / "allowed_values").exists()
    assert (PROJECT_ROOT / "data" / "taxonomy" / "playbook_values").is_dir()
    assert (PROJECT_ROOT / "data" / "taxonomy" / "coverage_values").is_dir()


def test_real_taxonomy_subdirectories_contain_expected_files() -> None:
    """The repo should keep playbook and coverage allowlists in the new folders."""
    playbook_values_dir = PROJECT_ROOT / "data" / "taxonomy" / "playbook_values"
    coverage_values_dir = PROJECT_ROOT / "data" / "taxonomy" / "coverage_values"

    for filename in [
        "beats_coverage.csv",
        "beats_box.csv",
        "beats_front.csv",
        "personnel.csv",
        "pressure.csv",
        "valid_run_scheme_modifier_pairs.csv",
    ]:
        assert (playbook_values_dir / filename).is_file()

    for filename in [
        "coverage_id.csv",
        "base_coverage.csv",
        "coverage_family.csv",
        "coverage_type.csv",
        "weakness_tags.csv",
    ]:
        assert (coverage_values_dir / filename).is_file()
