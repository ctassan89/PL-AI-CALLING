"""Rule-based parsing for human-readable initial play-calling situations."""

from __future__ import annotations

import re
import unicodedata

from recommendation.game_state import GameState


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


def normalize_text(text: str) -> str:
    """Lowercase and strip accents for permissive rule-based parsing."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def parse_initial_situation(text: str) -> GameState:
    """Parse a simple human-readable situation into a GameState."""
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

    position_tokens = tokens[index + 1 :]
    if not position_tokens:
        raise ValueError("Could not parse initial situation: missing field position.")

    field_position = parse_field_position(position_tokens)
    return GameState(down=down, distance=distance, field_position=field_position)


def parse_field_position(tokens: list[str]) -> int:
    """Parse a field-position token slice into the 0-100 coordinate."""
    if tokens == ["midfield"] or tokens == ["meta", "campo"]:
        return 50

    if len(tokens) >= 2 and tokens[0] in OWN_TOKENS and tokens[1].isdigit():
        return int(tokens[1])

    if len(tokens) >= 2 and tokens[0] in OPP_TOKENS and tokens[1].isdigit():
        return 100 - int(tokens[1])

    raise ValueError("Could not parse initial situation: missing or unsupported field position.")
