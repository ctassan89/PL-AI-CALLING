"""Validate playbook, taxonomy, and opponent tendency CSV files."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
PLAYBOOK_PATH = DATA_DIR / "playbook.csv"
OPPONENT_TENDENCIES_PATH = DATA_DIR / "opponent_tendencies.csv"
FORMATION_TAXONOMY_PATH = TAXONOMY_DIR / "formations.csv"

ALLOWED_DOWNS = {"1", "2", "3", "4"}
ALLOWED_DISTANCES = {"short", "medium", "long", "xlong"}
ALLOWED_FIELD_ZONES = {
    "own_redzone",
    "own_territory",
    "midfield",
    "opp_territory",
    "redzone",
    "goal_line",
}
ALLOWED_HASHES = {"left", "middle", "right"}

PLAYBOOK_COLUMNS = [
    "play_id",
    "play_name",
    "play_family",
    "play_type",
    "run_scheme",
    "run_modifier",
    "pass_concept",
    "pass_modifier",
    "protection",
    "rpo_tag",
    "play_action",
    "formation_id",
    "personnel",
    "beats_front",
    "beats_coverage",
    "beats_pressure",
    "beats_box",
    "preferred_down_distance",
    "preferred_field_zone",
    "tags",
]

SINGLE_VALUE_TAXONOMIES = {
    "play_family": "play_family.csv",
    "play_type": "play_type.csv",
    "run_scheme": "run_scheme.csv",
    "run_modifier": "run_modifier.csv",
    "pass_concept": "pass_concept.csv",
    "pass_modifier": "pass_modifier.csv",
    "protection": "protection.csv",
    "rpo_tag": "rpo_tag.csv",
    "play_action": "play_action.csv",
    "personnel": "personnel.csv",
}

MULTI_VALUE_TAXONOMIES = {
    "beats_front": "beats_front.csv",
    "beats_coverage": "beats_coverage.csv",
    "beats_pressure": "pressure.csv",
    "beats_box": "beats_box.csv",
    "preferred_down_distance": "preferred_down_distance.csv",
    "preferred_field_zone": "preferred_field_zone.csv",
    "tags": "tags.csv",
}

REQUIRED_DEFENSIVE_TENDENCY_COLUMNS = {
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
}

FORMATION_TAXONOMY_REQUIRED_COLUMNS = {
    "formation_id",
    "formation_name",
}


def format_relative_path(path: Path, base_dir: Path) -> str:
    """Format a path relative to the validation base directory when possible."""
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    """Load CSV rows as dictionaries."""
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_columns(path: Path) -> list[str]:
    """Read the header row from a CSV file."""
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def require_columns(
    path: Path,
    errors: list[str],
    base_dir: Path,
) -> list[str]:
    """Return CSV columns or record a missing-file error."""
    if not path.exists():
        errors.append(f"Missing CSV file: {format_relative_path(path, base_dir)}")
        return []
    return load_csv_columns(path)


def get_row_value(row: dict[str, str], column_name: str) -> str:
    """Read a CSV cell as a stripped string."""
    return str(row.get(column_name, "")).strip()


def add_missing_column_errors(
    errors: list[str],
    actual_columns: list[str],
    required_columns: set[str],
    dataset_name: str,
) -> None:
    """Add validation errors for required columns missing from a dataset."""
    missing = sorted(required_columns - set(actual_columns))
    if missing:
        errors.append(
            f"{dataset_name} is missing required columns: " + ", ".join(missing)
        )


def add_exact_column_order_error(
    errors: list[str],
    actual_columns: list[str],
    expected_columns: list[str],
    dataset_name: str,
) -> None:
    """Require an exact CSV column order."""
    if actual_columns != expected_columns:
        errors.append(
            f"{dataset_name} must use exact column order: "
            + ",".join(expected_columns)
            + " | actual: "
            + ",".join(actual_columns)
        )


def load_single_column_taxonomy(
    path: Path,
    errors: list[str],
    base_dir: Path,
) -> set[str]:
    """Load a taxonomy file that must contain exactly one `value` column."""
    if not path.exists():
        errors.append(f"Missing taxonomy file: {format_relative_path(path, base_dir)}")
        return set()

    columns = load_csv_columns(path)
    if columns != ["value"]:
        errors.append(
            f"{format_relative_path(path, base_dir)} must contain exactly one column named 'value'."
        )
        return set()

    values = {get_row_value(row, "value") for row in load_csv_rows(path) if get_row_value(row, "value")}
    if not values:
        errors.append(
            f"{format_relative_path(path, base_dir)} must contain at least one value."
        )
    return values


def taxonomy_source_path(
    data_dir: Path,
    taxonomy_dir: Path,
    source: str,
) -> Path:
    """Resolve a taxonomy source path from data/taxonomy or a relative data path."""
    if "/" in source:
        return data_dir / source
    return taxonomy_dir / source


def load_id_set(path: Path, id_column: str) -> set[str]:
    """Load an ID column from a taxonomy CSV."""
    return {get_row_value(row, id_column) for row in load_csv_rows(path) if get_row_value(row, id_column)}


def load_formation_personnel_map(
    path: Path,
    columns: list[str],
    allowed_personnel: set[str],
    errors: list[str],
) -> dict[str, str]:
    """Load the expected personnel for each formation when available."""
    if not columns:
        return {}
    if not FORMATION_TAXONOMY_REQUIRED_COLUMNS.issubset(columns):
        return {}

    if "personnel" not in columns:
        return {}

    formation_personnel: dict[str, str] = {}
    for index, row in enumerate(load_csv_rows(path), start=2):
        formation_id = get_row_value(row, "formation_id")
        personnel = get_row_value(row, "personnel")
        if not formation_id:
            errors.append(f"formations.csv row {index}: formation_id is blank.")
            continue
        if not personnel:
            errors.append(
                f"formations.csv row {index} ({formation_id}): personnel is blank."
            )
            continue
        if personnel not in allowed_personnel:
            errors.append(
                f"formations.csv row {index} ({formation_id}): invalid personnel '{personnel}'."
            )
            continue
        formation_personnel[formation_id] = personnel

    return formation_personnel


def add_unknown_id_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    column_name: str,
    allowed_ids: set[str],
    label_column: str | None = None,
) -> None:
    """Add row-specific errors for IDs missing from a taxonomy table."""
    for index, row in enumerate(rows, start=2):
        value = get_row_value(row, column_name)
        if value and value not in allowed_ids:
            label = f" ({get_row_value(row, label_column)})" if label_column else ""
            errors.append(
                f"row {index}{label}: {column_name} '{value}' was not found in its taxonomy."
            )


def add_formation_personnel_mismatch_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    formation_column: str,
    personnel_column: str,
    formation_personnel_map: dict[str, str],
    dataset_label: str,
    label_column: str | None = None,
) -> None:
    """Ensure row personnel matches the taxonomy for the selected formation."""
    for index, row in enumerate(rows, start=2):
        formation_id = get_row_value(row, formation_column)
        personnel = get_row_value(row, personnel_column)
        expected_personnel = formation_personnel_map.get(formation_id)
        if not formation_id or not personnel or not expected_personnel:
            continue
        if personnel != expected_personnel:
            label = f" ({get_row_value(row, label_column)})" if label_column else ""
            errors.append(
                f"{dataset_label} row {index}{label}: {personnel_column} '{personnel}' "
                f"does not match {formation_column} '{formation_id}' personnel '{expected_personnel}'."
            )


def add_invalid_scalar_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    column_name: str,
    allowed_values: set[str],
) -> None:
    """Add row-specific errors for single-value fields."""
    for index, row in enumerate(rows, start=2):
        value = get_row_value(row, column_name)
        play_id = get_row_value(row, "play_id")
        if not value:
            errors.append(f"playbook row {index} ({play_id}): {column_name} is blank.")
            continue
        if ";" in value:
            errors.append(
                f"playbook row {index} ({play_id}): {column_name} must contain a single value, not semicolons."
            )
            continue
        if value not in allowed_values:
            errors.append(
                f"playbook row {index} ({play_id}): invalid {column_name} '{value}'."
            )


def add_invalid_multi_value_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    column_name: str,
    allowed_values: set[str],
) -> None:
    """Add row-specific errors for semicolon-separated fields."""
    for index, row in enumerate(rows, start=2):
        value = get_row_value(row, column_name)
        play_id = get_row_value(row, "play_id")
        if not value:
            errors.append(f"playbook row {index} ({play_id}): {column_name} is blank.")
            continue

        tokens = [token.strip() for token in value.split(";")]
        invalid_tokens = [token for token in tokens if not token or token not in allowed_values]
        if invalid_tokens:
            formatted = ", ".join(repr(token) for token in invalid_tokens)
            errors.append(
                f"playbook row {index} ({play_id}): invalid {column_name} token(s): {formatted}."
            )


def add_invalid_value_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    column_name: str,
    allowed_values: set[str],
    dataset_label: str,
) -> None:
    """Add row-specific errors for flat categorical fields."""
    for index, row in enumerate(rows, start=2):
        value = get_row_value(row, column_name)
        if value and value not in allowed_values:
            errors.append(f"{dataset_label} row {index}: invalid {column_name} '{value}'.")


def add_non_numeric_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    column_name: str,
) -> None:
    """Add validation errors when a column cannot be parsed as numeric."""
    invalid_rows: list[str] = []
    for index, row in enumerate(rows, start=2):
        value = get_row_value(row, column_name)
        try:
            float(value)
        except ValueError:
            invalid_rows.append(str(index))
    if invalid_rows:
        errors.append(
            f"{column_name} must be numeric. Invalid values found at CSV rows: "
            + ", ".join(invalid_rows)
        )


def add_run_scheme_modifier_pair_errors(
    errors: list[str],
    rows: list[dict[str, str]],
    allowed_run_schemes: set[str],
    allowed_run_modifiers: set[str],
    valid_run_pairs: set[tuple[str, str]],
) -> None:
    """Validate playbook run scheme/modifier compatibility."""
    for index, row in enumerate(rows, start=2):
        run_scheme = get_row_value(row, "run_scheme")
        run_modifier = get_row_value(row, "run_modifier")
        if run_scheme not in allowed_run_schemes or run_modifier not in allowed_run_modifiers:
            continue
        if (run_scheme, run_modifier) not in valid_run_pairs:
            play_id = get_row_value(row, "play_id")
            errors.append(
                f"playbook row {index} ({play_id}): invalid run_scheme/run_modifier pair "
                f"run_scheme='{run_scheme}', run_modifier='{run_modifier}'."
            )


def add_run_pressure_errors(
    errors: list[str],
    rows: list[dict[str, str]],
) -> None:
    """Require pure run plays to use beats_pressure=none."""
    for index, row in enumerate(rows, start=2):
        play_type = get_row_value(row, "play_type")
        beats_pressure = get_row_value(row, "beats_pressure")
        if play_type != "run":
            continue
        if beats_pressure != "none":
            play_id = get_row_value(row, "play_id")
            errors.append(
                f"playbook row {index} ({play_id}): run plays must use beats_pressure='none', got '{beats_pressure}'."
            )


def validate_data(base_dir: Path | None = None) -> list[str]:
    """Validate CSV data files under a repository base dir."""
    base_dir = Path(base_dir) if base_dir is not None else BASE_DIR
    data_dir = base_dir / "data"
    taxonomy_dir = data_dir / "taxonomy"
    playbook_path = data_dir / "playbook.csv"
    opponent_tendencies_path = data_dir / "opponent_tendencies.csv"
    formation_taxonomy_path = taxonomy_dir / "formations.csv"

    errors: list[str] = []

    opponent_tendency_columns = (
        load_csv_columns(opponent_tendencies_path)
        if opponent_tendencies_path.exists()
        else []
    )
    playbook_columns = require_columns(playbook_path, errors, base_dir)
    if opponent_tendencies_path.exists():
        add_missing_column_errors(
            errors,
            opponent_tendency_columns,
            REQUIRED_DEFENSIVE_TENDENCY_COLUMNS,
            "opponent_tendencies.csv",
        )
    add_missing_column_errors(
        errors,
        playbook_columns,
        set(PLAYBOOK_COLUMNS),
        "playbook.csv",
    )
    add_exact_column_order_error(errors, playbook_columns, PLAYBOOK_COLUMNS, "playbook.csv")

    taxonomy_values = {
        column_name: load_single_column_taxonomy(
            taxonomy_source_path(data_dir, taxonomy_dir, filename),
            errors,
            base_dir,
        )
        for column_name, filename in {
            **SINGLE_VALUE_TAXONOMIES,
            **MULTI_VALUE_TAXONOMIES,
        }.items()
    }

    valid_run_pair_path = taxonomy_dir / "valid_run_scheme_modifier_pairs.csv"
    valid_run_pairs: set[tuple[str, str]] = set()
    if not valid_run_pair_path.exists():
        errors.append(
            f"Missing taxonomy file: {format_relative_path(valid_run_pair_path, base_dir)}"
        )
    elif load_csv_columns(valid_run_pair_path) != ["run_scheme", "run_modifier"]:
        errors.append(
            "data/taxonomy/valid_run_scheme_modifier_pairs.csv must contain exactly "
            "the columns run_scheme,run_modifier."
        )
    else:
        valid_run_pairs = {
            (get_row_value(row, "run_scheme"), get_row_value(row, "run_modifier"))
            for row in load_csv_rows(valid_run_pair_path)
        }

    formation_columns = require_columns(formation_taxonomy_path, errors, base_dir)
    if formation_columns:
        add_missing_column_errors(
            errors,
            formation_columns,
            FORMATION_TAXONOMY_REQUIRED_COLUMNS,
            "formations.csv",
        )

    formation_personnel_map = load_formation_personnel_map(
        formation_taxonomy_path,
        formation_columns,
        taxonomy_values["personnel"],
        errors,
    )

    if errors:
        return errors

    opponent_tendencies = (
        load_csv_rows(opponent_tendencies_path)
        if opponent_tendencies_path.exists()
        else []
    )
    playbook = load_csv_rows(playbook_path)

    front_ids = load_id_set(taxonomy_dir / "fronts.csv", "front_id")
    coverage_ids = load_id_set(taxonomy_dir / "coverages.csv", "coverage_id")
    defensive_personnel_ids = load_id_set(
        taxonomy_dir / "defensive_personnel.csv",
        "defensive_personnel_id",
    )
    formation_ids = load_id_set(formation_taxonomy_path, "formation_id")

    add_unknown_id_errors(errors, opponent_tendencies, "front_id", front_ids)
    add_unknown_id_errors(errors, opponent_tendencies, "coverage_id", coverage_ids)
    add_unknown_id_errors(
        errors,
        opponent_tendencies,
        "defensive_personnel_id",
        defensive_personnel_ids,
    )
    add_unknown_id_errors(
        errors,
        opponent_tendencies,
        "offensive_formation_id",
        formation_ids,
    )

    add_invalid_value_errors(
        errors,
        opponent_tendencies,
        "down",
        ALLOWED_DOWNS,
        "opponent_tendencies.csv",
    )
    add_invalid_value_errors(
        errors,
        opponent_tendencies,
        "distance",
        ALLOWED_DISTANCES,
        "opponent_tendencies.csv",
    )
    add_invalid_value_errors(
        errors,
        opponent_tendencies,
        "field_zone",
        ALLOWED_FIELD_ZONES,
        "opponent_tendencies.csv",
    )
    add_invalid_value_errors(
        errors,
        opponent_tendencies,
        "hash",
        ALLOWED_HASHES,
        "opponent_tendencies.csv",
    )

    for column_name in ["frequency", "success_rate_allowed", "epa_allowed"]:
        add_non_numeric_errors(errors, opponent_tendencies, column_name)

    add_unknown_id_errors(errors, playbook, "formation_id", formation_ids, "play_id")

    for column_name in SINGLE_VALUE_TAXONOMIES:
        add_invalid_scalar_errors(
            errors,
            playbook,
            column_name,
            taxonomy_values[column_name],
        )

    for column_name in MULTI_VALUE_TAXONOMIES:
        add_invalid_multi_value_errors(
            errors,
            playbook,
            column_name,
            taxonomy_values[column_name],
        )

    add_run_scheme_modifier_pair_errors(
        errors,
        playbook,
        taxonomy_values["run_scheme"],
        taxonomy_values["run_modifier"],
        valid_run_pairs,
    )
    add_run_pressure_errors(errors, playbook)

    add_formation_personnel_mismatch_errors(
        errors,
        playbook,
        "formation_id",
        "personnel",
        formation_personnel_map,
        "playbook",
        "play_id",
    )

    return errors


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the validator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=BASE_DIR,
        help="Repository base directory that contains the data/ folder.",
    )
    return parser.parse_args()


def main() -> None:
    """Run validation checks for repo data files."""
    args = parse_args()
    errors = validate_data(args.base_dir)

    if errors:
        print("Data validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Data validation passed.")


if __name__ == "__main__":
    main()
