"""Tests for sequential play-calling game-state updates."""

from __future__ import annotations

from recommendation.game_state import GameState


def test_gain_three_from_own_25_updates_down_distance() -> None:
    state = GameState(down=1, distance=10, field_position=25)

    state.apply_gain(3)

    assert state.field_position == 28
    assert state.down == 2
    assert state.distance == 7
    assert state.status == "active"


def test_first_down_resets_down_and_distance() -> None:
    state = GameState(down=2, distance=7, field_position=28)

    state.apply_gain(8)

    assert state.field_position == 36
    assert state.down == 1
    assert state.distance == 10
    assert state.status == "active"


def test_gain_to_goal_line_marks_touchdown() -> None:
    state = GameState(down=1, distance=10, field_position=95)

    state.apply_gain(5)

    assert state.field_position == 100
    assert state.status == "touchdown"


def test_negative_gain_updates_position_and_distance() -> None:
    state = GameState(down=2, distance=7, field_position=28)

    state.apply_gain(-2)

    assert state.field_position == 26
    assert state.down == 3
    assert state.distance == 9
    assert state.status == "active"


def test_touchdown_status_when_gain_crosses_goal_line() -> None:
    state = GameState(down=3, distance=2, field_position=99)

    state.apply_gain(3)

    assert state.field_position == 100
    assert state.status == "touchdown"
