"""Tests for the rule-based situation parsers."""

from __future__ import annotations

from recommendation.game_state import DefenseState
from recommendation.situation_parser import (
    parse_defense_update,
    parse_initial_session_state,
    parse_initial_situation,
)


def test_parse_italian_first_and_ten_own_25() -> None:
    state = parse_initial_situation("primo e 10 own 25")

    assert state.down == 1
    assert state.distance == 10
    assert state.field_position == 25


def test_parse_english_first_and_ten_own_25() -> None:
    state = parse_initial_situation("1st and 10 own 25")

    assert state.down == 1
    assert state.distance == 10
    assert state.field_position == 25


def test_parse_third_and_six_opp_45() -> None:
    state = parse_initial_situation("third and 6 opp 45")

    assert state.down == 3
    assert state.distance == 6
    assert state.field_position == 55


def test_parse_third_and_four_midfield() -> None:
    state = parse_initial_situation("3rd and 4 midfield")

    assert state.down == 3
    assert state.distance == 4
    assert state.field_position == 50


def test_parse_italian_midfield_variant() -> None:
    state = parse_initial_situation("3 e 4 metà campo")

    assert state.down == 3
    assert state.distance == 4
    assert state.field_position == 50


def test_parse_initial_session_state_with_cover3_even_box_and_personnel() -> None:
    parsed = parse_initial_session_state("primo e 10 own 25 cover3 even box 6 personnel 10")

    assert parsed.game_state.down == 1
    assert parsed.game_state.distance == 10
    assert parsed.game_state.field_position == 25
    assert parsed.defense_state == DefenseState(
        front_id="even",
        coverage_id="cover3",
        pressure_id="none",
        box_count=6,
        personnel="10",
    )


def test_parse_initial_session_state_with_cover1_nickel_blitz() -> None:
    parsed = parse_initial_session_state(
        "1st and 10 own 25 cover1 nickel blitz box 6 personnel 11"
    )

    assert parsed.defense_state == DefenseState(
        front_id="none",
        coverage_id="cover1",
        pressure_id="nickel_blitz",
        box_count=6,
        personnel="11",
    )


def test_parse_initial_session_state_with_cover3_odd_tite() -> None:
    parsed = parse_initial_session_state("third and 6 opp 45 cover3 odd_tite box 7")

    assert parsed.defense_state == DefenseState(
        front_id="odd_tite",
        coverage_id="cover3",
        pressure_id="none",
        box_count=7,
        personnel=None,
    )


def test_parse_initial_session_state_with_man_zero_pressure() -> None:
    parsed = parse_initial_session_state("3rd and 4 midfield man zero pressure box 6")

    assert parsed.defense_state == DefenseState(
        front_id="none",
        coverage_id="man",
        pressure_id="zero_pressure",
        box_count=6,
        personnel=None,
    )


def test_parse_defense_update_cover1_nickel_blitz_box_6() -> None:
    updated = parse_defense_update("cover1 nickel blitz box 6")

    assert updated == DefenseState(
        front_id="none",
        coverage_id="cover1",
        pressure_id="nickel_blitz",
        box_count=6,
        personnel=None,
    )


def test_parse_defense_update_cover3_no_pressure_clears_pressure() -> None:
    current = DefenseState(
        front_id="even",
        coverage_id="cover1",
        pressure_id="nickel_blitz",
        box_count=6,
        personnel="10",
    )

    updated = parse_defense_update("cover3 no pressure", current)

    assert updated == DefenseState(
        front_id="even",
        coverage_id="cover3",
        pressure_id="none",
        box_count=6,
        personnel="10",
    )


def test_parse_defense_update_odd_tite_box_7_personnel_12() -> None:
    updated = parse_defense_update("odd_tite box 7 personnel 12")

    assert updated == DefenseState(
        front_id="odd_tite",
        coverage_id="none",
        pressure_id="none",
        box_count=7,
        personnel="12",
    )
