"""Validate taxonomy, defensive tendency, and playbook CSV files."""

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
RAW_DIR = DATA_DIR / "raw"

ALLOWED_DOWNS = {1, 2, 3, 4}
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
ALLOWED_FORMATION_FAMILIES = {"gun", "pistol", "under"}
ALLOWED_BACKFIELDS = {"empty", "1rb", "2rb", "fb"}
ALLOWED_RECEIVER_STRUCTURES = {"1x1", "2x1", "2x2", "3x1", "3x2", "4x1", "heavy"}
ALLOWED_SPACING_TAGS = {"spread", "tight"}
ALLOWED_TE_TAGS = {
    "no_te",
    "te_off",
    "te_on",
    "y_middle",
    "2te_off",
    "2te_on",
    "te_attached_away",
    "wing",
}
ALLOWED_FORMATION_MODIFIERS = {"none", "stack", "tight", "nasty"}
ALLOWED_MOTION_MODIFIERS = {
    "none",
    "jet",
    "orbit",
    "return",
    "yo_yo",
    "shift",
    "trade",
    "zip",
    "fast",
}
ALLOWED_STRENGTHS = {"left", "right", "balanced"}
ALLOWED_PLAY_FAMILIES = {
    "run",
    "quick_game",
    "dropback",
    "play_action",
    "screen",
    "rpo",
    "boot",
    "trick",
}
ALLOWED_PLAY_TYPES = {"run", "pass", "rpo", "screen", "play_action", "boot", "trick"}
ALLOWED_RUN_SCHEMES = {
    "none",
    "inside_zone",
    "outside_zone",
    "duo",
    "power",
    "counter",
    "trap",
    "iso",
    "draw",
    "qb_run",
    "option",
}
ALLOWED_RUN_MODIFIERS = {
    "none",
    "sweep",
    "toss",
    "pin_pull",
    "read",
    "bash",
    "split_zone",
    "arc",
}
ALLOWED_PASS_CONCEPTS = {
    "none",
    "slant_flat",
    "stick",
    "spacing",
    "mesh",
    "drive",
    "levels",
    "curl_flat",
    "smash",
    "flood",
    "dagger",
    "mills",
    "y_cross",
    "four_verts",
    "screens",
    "wheel",
    "choice",
}
ALLOWED_PASS_MODIFIERS = {
    "none",
    "switch",
    "bunch",
    "stack",
    "motion",
    "play_action",
    "max_protect",
}
ALLOWED_RPO_TAGS = {
    "none",
    "bubble",
    "now_screen",
    "stick",
    "slant",
    "glance",
    "peek",
    "arrow",
    "flat",
}
ALLOWED_PLAY_ACTION = {"true", "false"}
ALLOWED_PERSONNEL = {"10", "11", "12", "13", "20", "21", "22", "empty"}
ALLOWED_BEATS_BOX = {"light_box", "neutral_box", "heavy_box", "loaded_box", "any", "none"}
ALLOWED_PREFERRED_DOWN_DISTANCE = {"short", "medium", "long", "xlong", "any"}
ALLOWED_PREFERRED_FIELD_ZONE = {
    "own_redzone",
    "own_territory",
    "midfield",
    "opp_territory",
    "redzone",
    "goal_line",
    "any",
}


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file from disk."""
    return pd.read_csv(path)


def add_missing_id_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
    allowed_ids: set[str],
    taxonomy_name: str,
) -> None:
    """Add validation errors for IDs missing from a taxonomy table."""
    values = set(df[column_name].dropna().astype(str))
    missing = sorted(values - allowed_ids)
    if missing:
        errors.append(
            f"{column_name} contains unknown values not found in {taxonomy_name}: "
            + ", ".join(missing)
        )


def add_invalid_value_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
    allowed_values: set,
) -> None:
    """Add validation errors for invalid categorical values."""
    values = set(df[column_name].dropna())
    invalid = sorted(values - allowed_values)
    if invalid:
        errors.append(
            f"{column_name} contains invalid values: " + ", ".join(map(str, invalid))
        )


def add_invalid_semicolon_value_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
    allowed_values: set[str],
) -> None:
    """Add validation errors for semicolon-separated categorical values."""
    invalid_entries: list[str] = []

    for index, value in df[column_name].items():
        items = [item.strip() for item in str(value).split(";")]
        if any(not item for item in items):
            invalid_entries.append(f"row {index + 2}: empty value")
            continue

        invalid_items = [item for item in items if item not in allowed_values]
        if invalid_items:
            invalid_entries.append(
                f"row {index + 2}: " + ", ".join(invalid_items)
            )

    if invalid_entries:
        errors.append(
            f"{column_name} contains invalid semicolon-separated values -> "
            + "; ".join(invalid_entries)
        )


def add_non_numeric_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
) -> None:
    """Add validation errors when a column cannot be parsed as numeric."""
    numeric_values = pd.to_numeric(df[column_name], errors="coerce")
    invalid_rows = df.index[numeric_values.isna()].tolist()
    if invalid_rows:
        row_numbers = ", ".join(str(index + 2) for index in invalid_rows)
        errors.append(
            f"{column_name} must be numeric. Invalid values found at CSV rows: "
            f"{row_numbers}"
        )


def add_blank_value_errors(
    errors: list[str],
    df: pd.DataFrame,
    column_name: str,
) -> None:
    """Add validation errors for blank or missing values."""
    invalid_rows = df.index[df[column_name].isna() | (df[column_name].astype(str).str.strip() == "")].tolist()
    if invalid_rows:
        row_numbers = ", ".join(str(index + 2) for index in invalid_rows)
        errors.append(f"{column_name} contains blank values at CSV rows: {row_numbers}")


def main() -> None:
    """Run validation checks for defensive tendency input data."""
    fronts = load_csv(TAXONOMY_DIR / "fronts.csv")
    coverages = load_csv(TAXONOMY_DIR / "coverages.csv")
    defensive_personnel = load_csv(TAXONOMY_DIR / "defensive_personnel.csv")
    offensive_formations = load_csv(TAXONOMY_DIR / "offensive_formations.csv")
    defensive_tendencies = load_csv(RAW_DIR / "defensive_tendencies.csv")
    playbook = load_csv(RAW_DIR / "playbook.csv")

    errors: list[str] = []
    front_ids = set(fronts["front_id"].dropna().astype(str))
    coverage_ids = set(coverages["coverage_id"].dropna().astype(str))
    formation_ids = set(offensive_formations["formation_id"].dropna().astype(str))

    add_invalid_value_errors(
        errors, offensive_formations, "formation_family", ALLOWED_FORMATION_FAMILIES
    )
    add_invalid_value_errors(errors, offensive_formations, "backfield", ALLOWED_BACKFIELDS)
    add_invalid_value_errors(
        errors,
        offensive_formations,
        "receiver_structure",
        ALLOWED_RECEIVER_STRUCTURES,
    )
    add_invalid_value_errors(
        errors, offensive_formations, "spacing_tag", ALLOWED_SPACING_TAGS
    )
    add_invalid_value_errors(errors, offensive_formations, "te_tag", ALLOWED_TE_TAGS)
    add_invalid_value_errors(
        errors,
        offensive_formations,
        "formation_modifier",
        ALLOWED_FORMATION_MODIFIERS,
    )
    add_invalid_value_errors(
        errors, offensive_formations, "motion_modifier", ALLOWED_MOTION_MODIFIERS
    )
    add_invalid_value_errors(errors, offensive_formations, "strength", ALLOWED_STRENGTHS)

    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "front_id",
        front_ids,
        "fronts.csv",
    )
    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "coverage_id",
        coverage_ids,
        "coverages.csv",
    )
    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "defensive_personnel_id",
        set(defensive_personnel["defensive_personnel_id"].dropna().astype(str)),
        "defensive_personnel.csv",
    )
    add_missing_id_errors(
        errors,
        defensive_tendencies,
        "offensive_formation_id",
        formation_ids,
        "offensive_formations.csv",
    )

    add_invalid_value_errors(errors, defensive_tendencies, "down", ALLOWED_DOWNS)
    add_invalid_value_errors(
        errors, defensive_tendencies, "distance", ALLOWED_DISTANCES
    )
    add_invalid_value_errors(
        errors, defensive_tendencies, "field_zone", ALLOWED_FIELD_ZONES
    )
    add_invalid_value_errors(errors, defensive_tendencies, "hash", ALLOWED_HASHES)

    for column_name in ["frequency", "success_rate_allowed", "epa_allowed"]:
        add_non_numeric_errors(errors, defensive_tendencies, column_name)

    for column_name in [
        "formation_id",
        "play_family",
        "play_type",
        "run_scheme",
        "run_modifier",
        "pass_concept",
        "pass_modifier",
        "rpo_tag",
        "play_action",
        "personnel",
        "beats_box",
        "preferred_down_distance",
        "preferred_field_zone",
        "beats_front",
        "beats_coverage",
    ]:
        add_blank_value_errors(errors, playbook, column_name)

    add_missing_id_errors(
        errors,
        playbook,
        "formation_id",
        formation_ids,
        "offensive_formations.csv",
    )
    add_invalid_value_errors(errors, playbook, "play_family", ALLOWED_PLAY_FAMILIES)
    add_invalid_value_errors(errors, playbook, "play_type", ALLOWED_PLAY_TYPES)
    add_invalid_value_errors(errors, playbook, "run_scheme", ALLOWED_RUN_SCHEMES)
    add_invalid_value_errors(errors, playbook, "run_modifier", ALLOWED_RUN_MODIFIERS)
    add_invalid_value_errors(errors, playbook, "pass_concept", ALLOWED_PASS_CONCEPTS)
    add_invalid_value_errors(errors, playbook, "pass_modifier", ALLOWED_PASS_MODIFIERS)
    add_invalid_value_errors(errors, playbook, "rpo_tag", ALLOWED_RPO_TAGS)
    add_invalid_value_errors(errors, playbook, "play_action", ALLOWED_PLAY_ACTION)
    add_invalid_value_errors(
        errors, playbook.astype({"personnel": "string"}), "personnel", ALLOWED_PERSONNEL
    )
    add_invalid_semicolon_value_errors(errors, playbook, "beats_box", ALLOWED_BEATS_BOX)
    add_invalid_semicolon_value_errors(
        errors,
        playbook,
        "preferred_down_distance",
        ALLOWED_PREFERRED_DOWN_DISTANCE,
    )
    add_invalid_semicolon_value_errors(
        errors,
        playbook,
        "preferred_field_zone",
        ALLOWED_PREFERRED_FIELD_ZONE,
    )
    add_invalid_semicolon_value_errors(
        errors,
        playbook,
        "beats_front",
        front_ids | {"any", "none"},
    )
    add_invalid_semicolon_value_errors(
        errors,
        playbook,
        "beats_coverage",
        coverage_ids | {"any", "none"},
    )

    if errors:
        print("Data validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Data validation passed.")


if __name__ == "__main__":
    main()
