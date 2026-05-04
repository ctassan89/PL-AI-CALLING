"""Tests for the rule-based initial situation parser."""

from __future__ import annotations

from recommendation.situation_parser import parse_initial_situation


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
