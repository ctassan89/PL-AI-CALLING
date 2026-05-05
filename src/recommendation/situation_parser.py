"""Rule-based parsing for human-readable play-calling situations."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from recommendation.game_state import DefenseState, GameState


DOWN_MAP = {
    "primo": 1,
    "first": 1,
    "1st": 1,
    "1": 1,
    "secondo": 2,
    "second": 2,
    "2nd": 2,
    "2": 2,
    "terzo": 3,
    "third": 3,
    "3rd": 3,
    "3": 3,
    "quarto": 4,
    "fourth": 4,
    "4th": 4,
    "4": 4,
}

DISTANCE_MAP = {
    "dieci": 10,
}

OWN_TOKENS = {"own", "our", "nostre", "nostra"}
OPP_TOKENS = {"opp", "their", "loro", "avversarie", "avversaria"}

DEFENSIVE_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    "coverage_id": (
        ("coverage none", "none"),
        ("no coverage", "none"),
        ("soft zone", "soft_zone"),
        ("cover 1", "cover1"),
        ("cover 2", "cover2"),
        ("cover 3", "cover3"),
        ("cover 4", "cover4"),
        ("cover1", "cover1"),
        ("cover2", "cover2"),
        ("cover3", "cover3"),
        ("cover4", "cover4"),
        ("match", "match"),
        ("zone", "zone"),
        ("man", "man"),
    ),
    "pressure_id": (
        ("pressure none", "none"),
        ("no pressure", "none"),
        ("double a gap", "double_a_gap"),
        ("nickel blitz", "nickel_blitz"),
        ("edge blitz", "edge_blitz"),
        ("field blitz", "field_blitz"),
        ("boundary blitz", "boundary_blitz"),
        ("inside blitz", "inside_blitz"),
        ("zero pressure", "zero_pressure"),
        ("sim pressure", "sim_pressure"),
        ("creeper", "creeper"),
    ),
    "front_id": (
        ("front none", "none"),
        ("odd tite", "odd_tite"),
        ("odd_tite", "odd_tite"),
        ("even", "even"),
        ("odd", "odd"),
        ("bear", "bear"),
        ("over", "over"),
        ("under", "under"),
    ),
}


@dataclass(frozen=True)
class ParsedSessionState:
    """Structured initial session parse output."""

    game_state: GameState
    defense_state: DefenseState


def normalize_text(text: str) -> str:
    """Lowercase and strip accents for permissive rule-based parsing."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = ascii_text.lower().replace("_", " ")
    return re.sub(r"\s+", " ", lowered).strip()


def parse_initial_situation(text: str) -> GameState:
    """Parse a simple human-readable situation into a GameState."""
    return parse_initial_session_state(text).game_state


def parse_initial_session_state(text: str) -> ParsedSessionState:
    """Parse the offensive state plus optional defensive context."""
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Could not parse initial situation: missing input text.")

    tokens = normalized.split()
    down = DOWN_MAP.get(tokens[0])
    if down is None:
        raise ValueError("Could not parse initial situation: missing or unsupported down.")

    index = 1
    if index < len(tokens) and tokens[index] in {"e", "and"}:
        index += 1
    if index >= len(tokens):
        raise ValueError("Could not parse initial situation: missing distance.")

    distance_token = tokens[index]
    if distance_token.isdigit():
        distance = int(distance_token)
    elif distance_token in DISTANCE_MAP:
        distance = DISTANCE_MAP[distance_token]
    else:
        raise ValueError("Could not parse initial situation: missing or unsupported distance.")

    field_position, consumed = parse_field_position(tokens[index + 1 :])
    remainder_tokens = tokens[index + 1 + consumed :]
    defense_state = (
        parse_defense_update(" ".join(remainder_tokens))
        if remainder_tokens
        else DefenseState()
    )

    return ParsedSessionState(
        game_state=GameState(down=down, distance=distance, field_position=field_position),
        defense_state=defense_state,
    )


def parse_field_position(tokens: list[str]) -> tuple[int, int]:
    """Parse a field-position token slice into the 0-100 coordinate."""
    if len(tokens) >= 2 and tokens[0] == "meta" and tokens[1] == "campo":
        return 50, 2
    if tokens and tokens[0] == "midfield":
        return 50, 1

    if len(tokens) >= 2 and tokens[0] in OWN_TOKENS and tokens[1].isdigit():
        return int(tokens[1]), 2

    if len(tokens) >= 2 and tokens[0] in OPP_TOKENS and tokens[1].isdigit():
        return 100 - int(tokens[1]), 2

    raise ValueError("Could not parse initial situation: missing or unsupported field position.")


def parse_defense_update(
    text: str,
    current_state: DefenseState | None = None,
) -> DefenseState:
    """Parse a defense-only update, preserving unspecified prior values."""
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Could not parse defense update: missing input text.")

    base_state = current_state or DefenseState()
    updated = DefenseState(
        front_id=base_state.front_id,
        coverage_id=base_state.coverage_id,
        pressure_id=base_state.pressure_id,
        box_count=base_state.box_count,
        personnel=base_state.personnel,
    )

    matched = False
    for field_name, aliases in DEFENSIVE_ALIASES.items():
        value = find_alias_value(normalized, aliases)
        if value is None:
            continue
        setattr(updated, field_name, value)
        matched = True

    box_count = parse_box_count(normalized)
    if box_count is not None:
        updated.box_count = box_count
        matched = True

    personnel = parse_personnel(normalized)
    if personnel is not None:
        updated.personnel = personnel
        matched = True

    if not matched:
        raise ValueError("Could not parse defense update: no supported defensive context found.")
    return updated


def find_alias_value(text: str, aliases: tuple[tuple[str, str], ...]) -> str | None:
    """Return the first canonical alias match from a normalized text input."""
    for phrase, canonical in aliases:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text):
            return canonical
    return None


def parse_box_count(text: str) -> int | None:
    """Extract a supported box count from normalized text."""
    match = re.search(r"\bbox\s+([5-8])\b", text)
    if match is None:
        return None
    return int(match.group(1))


def parse_personnel(text: str) -> str | None:
    """Extract offensive personnel from normalized text."""
    match = re.search(r"\bpersonnel\s+(\d{2})\b", text)
    if match is None:
        return None
    return match.group(1)
