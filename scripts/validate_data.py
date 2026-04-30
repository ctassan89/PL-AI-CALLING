"""Validate taxonomy, defensive tendency, and playbook CSV files."""

from __future__ import annotations

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
RAW_DIR = DATA_DIR / "raw"
FORMATION_TAXONOMY_PATH = TAXONOMY_DIR / "offensive_formations.csv"

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
}

MULTI_VALUE_TAXONOMIES = {
    "beats_front": "beats_front.csv",
    "beats_coverage": "beats_coverage.csv",
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


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    """Load CSV rows as dictionaries."""
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_columns(path: Path) -> list[str]:
    """Read the header row from a CSV file."""
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


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


def load_single_column_taxonomy(path: Path, errors: list[str]) -> set[str]:
    """Load a taxonomy file that must contain exactly one `value` column."""
    if not path.exists():
        errors.append(f"Missing taxonomy file: {path.relative_to(BASE_DIR)}")
        return set()

    columns = load_csv_columns(path)
    if columns != ["value"]:
        errors.append(
            f"{path.relative_to(BASE_DIR)} must contain exactly one column named 'value'."
        )
        return set()

    values = {get_row_value(row, "value") for row in load_csv_rows(path) if get_row_value(row, "value")}
    if not values:
        errors.append(f"{path.relative_to(BASE_DIR)} must contain at least one value.")
    return values


def load_id_set(path: Path, id_column: str) -> set[str]:
    """Load an ID column from a taxonomy CSV."""
    return {get_row_value(row, id_column) for row in load_csv_rows(path) if get_row_value(row, id_column)}


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


def main() -> None:
    """Run validation checks for defensive tendency input data."""
    errors: list[str] = []

    defensive_tendency_columns = load_csv_columns(RAW_DIR / "defensive_tendencies.csv")
    playbook_columns = load_csv_columns(RAW_DIR / "playbook.csv")
    add_missing_column_errors(
        errors,
        defensive_tendency_columns,
        REQUIRED_DEFENSIVE_TENDENCY_COLUMNS,
        "defensive_tendencies.csv",
    )
    add_missing_column_errors(
        errors,
        playbook_columns,
        set(PLAYBOOK_COLUMNS),
        "playbook.csv",
    )
    add_exact_column_order_error(errors, playbook_columns, PLAYBOOK_COLUMNS, "playbook.csv")

    taxonomy_values = {
        column_name: load_single_column_taxonomy(TAXONOMY_DIR / filename, errors)
        for column_name, filename in {
            **SINGLE_VALUE_TAXONOMIES,
            **MULTI_VALUE_TAXONOMIES,
        }.items()
    }

    valid_run_pair_path = TAXONOMY_DIR / "valid_run_scheme_modifier_pairs.csv"
    valid_run_pairs: set[tuple[str, str]] = set()
    if not valid_run_pair_path.exists():
        errors.append(
            f"Missing taxonomy file: {valid_run_pair_path.relative_to(BASE_DIR)}"
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

    if errors:
        print("Data validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    defensive_tendencies = load_csv_rows(RAW_DIR / "defensive_tendencies.csv")
    playbook = load_csv_rows(RAW_DIR / "playbook.csv")

    front_ids = load_id_set(TAXONOMY_DIR / "fronts.csv", "front_id")
    coverage_ids = load_id_set(TAXONOMY_DIR / "coverages.csv", "coverage_id")
    defensive_personnel_ids = load_id_set(
        TAXONOMY_DIR / "defensive_personnel.csv",
        "defensive_personnel_id",
    )
    formation_ids = load_id_set(FORMATION_TAXONOMY_PATH, "formation_id")

    add_unknown_id_errors(errors, defensive_tendencies, "front_id", front_ids)
    add_unknown_id_errors(errors, defensive_tendencies, "coverage_id", coverage_ids)
    add_unknown_id_errors(
        errors,
        defensive_tendencies,
        "defensive_personnel_id",
        defensive_personnel_ids,
    )
    add_unknown_id_errors(
        errors,
        defensive_tendencies,
        "offensive_formation_id",
        formation_ids,
    )

    add_invalid_value_errors(
        errors,
        defensive_tendencies,
        "down",
        ALLOWED_DOWNS,
        "defensive_tendencies.csv",
    )
    add_invalid_value_errors(
        errors,
        defensive_tendencies,
        "distance",
        ALLOWED_DISTANCES,
        "defensive_tendencies.csv",
    )
    add_invalid_value_errors(
        errors,
        defensive_tendencies,
        "field_zone",
        ALLOWED_FIELD_ZONES,
        "defensive_tendencies.csv",
    )
    add_invalid_value_errors(
        errors,
        defensive_tendencies,
        "hash",
        ALLOWED_HASHES,
        "defensive_tendencies.csv",
    )

    for column_name in ["frequency", "success_rate_allowed", "epa_allowed"]:
        add_non_numeric_errors(errors, defensive_tendencies, column_name)

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

    if errors:
        print("Data validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Data validation passed.")


if __name__ == "__main__":
    main()
