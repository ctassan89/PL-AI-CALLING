"""CLI tests for sequential play-calling sessions."""

from __future__ import annotations

import csv
import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

from scripts import playcaller_session
from scripts.validate_data import PLAYBOOK_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SESSION_SCRIPT = PROJECT_ROOT / "scripts" / "playcaller_session.py"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write a CSV file with dict rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_play(
    play_id: str,
    play_name: str,
    *,
    pass_concept: str = "stick",
    beats_coverage: str = "cover3",
    beats_pressure: str = "none",
    preferred_down_distance: str = "early_down;second_medium;third_short",
    preferred_field_zone: str = "open_field;redzone;goal_line",
    personnel: str = "10",
    tags: str = "quick_game",
    **overrides: str,
) -> dict[str, str]:
    """Build a playbook row for session CLI tests."""
    play = {
        "play_id": play_id,
        "play_name": play_name,
        "play_family": "dropback",
        "play_type": "pass",
        "run_scheme": "none",
        "run_modifier": "none",
        "pass_concept": pass_concept,
        "pass_modifier": "none",
        "protection": "6man",
        "rpo_tag": "none",
        "play_action": "false",
        "formation_id": "gun_1rb_2x2_spread_no_te",
        "personnel": personnel,
        "beats_front": "even;over;under",
        "beats_coverage": beats_coverage,
        "beats_pressure": beats_pressure,
        "beats_box": "light_box;normal_box;heavy_box",
        "preferred_down_distance": preferred_down_distance,
        "preferred_field_zone": preferred_field_zone,
        "tags": tags,
    }
    play.update(overrides)
    return play


def run_session(
    playbook_path: Path,
    session_input: str,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    """Run the session CLI against a temp playbook."""
    command = [
        sys.executable,
        str(SESSION_SCRIPT),
        "--playbook-path",
        str(playbook_path),
        *extra_args,
    ]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        input=session_input,
        capture_output=True,
        text=True,
        check=False,
    )


def test_session_numeric_input_updates_offense_and_preserves_defense(tmp_path: Path) -> None:
    """Numeric updates should move the ball without changing defensive context."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("stick", "Stick TRIPS"),
            make_play("drive", "Drive TOP", pass_concept="spacing"),
            make_play("screen", "RB Screen TREY", pass_concept="rb_screen"),
        ],
    )

    result = run_session(
        playbook_path,
        "primo e 10 own 25 cover3 even box 6 personnel 10\n3\nq\n",
        "--top-n",
        "3",
    )

    assert result.returncode == 0
    assert "Current situation: 1st & 10, own 25, own_territory | front=even, coverage=cover3, pressure=none, box=6, personnel=10" in result.stdout
    assert "Current situation: 2nd & 7, own 28, own_territory | front=even, coverage=cover3, pressure=none, box=6, personnel=10" in result.stdout


def test_session_defense_update_preserves_offense(tmp_path: Path) -> None:
    """Defense-only text updates should keep down, distance, and field position unchanged."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("stick", "Stick TRIPS"),
            make_play(
                "screen",
                "RB Screen TREY",
                pass_concept="rb_screen",
                beats_pressure="nickel_blitz;any_pressure",
                tags="screen;quick_game;pressure_beater",
            ),
        ],
    )

    result = run_session(
        playbook_path,
        "primo e 10 own 25 cover3 even box 6 personnel 10\ncover1 nickel blitz box 6\nq\n",
        "--top-n",
        "2",
    )

    assert result.returncode == 0
    assert "Current situation: 1st & 10, own 25, own_territory | front=even, coverage=cover3, pressure=none, box=6, personnel=10" in result.stdout
    assert "Current situation: 1st & 10, own 25, own_territory | front=even, coverage=cover1, pressure=nickel_blitz, box=6, personnel=10" in result.stdout


def test_session_missing_defense_context_uses_defaults(tmp_path: Path) -> None:
    """Initial situations without defensive text should use the documented defaults."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS")],
    )

    result = run_session(playbook_path, "primo e 10 own 25\nq\n", "--top-n", "1")

    assert result.returncode == 0
    assert "front=none, coverage=none, pressure=none, box=none, personnel=none" in result.stdout


def test_session_top_n_controls_number_of_recommendations(tmp_path: Path) -> None:
    """The session CLI should respect unified top-N output when blocks are not used."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("stick", "Stick TRIPS"),
            make_play("drive", "Drive TOP", pass_concept="spacing"),
            make_play("screen", "RB Screen TREY", pass_concept="rb_screen"),
        ],
    )

    result = run_session(playbook_path, "third and 6 midfield\nq\n", "--top-n", "2")

    assert result.returncode == 0
    assert "Intermediate conversion options:" in result.stdout
    assert "Man / pressure answers:" in result.stdout
    assert "Top 2 recommended plays:" not in result.stdout
    assert result.stdout.count("Intermediate conversion options:") == 1


def test_session_touchdown_stops_before_rendering_next_block(tmp_path: Path) -> None:
    """A touchdown update should end the drive before another recommendation render."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS")],
    )

    result = run_session(playbook_path, "first and 1 opp 1 personnel 11\n1\n", "--top-n", "2")

    assert result.returncode == 0
    assert "Drive ended: touchdown" in result.stdout
    assert "Current situation: 1st & 1, opp 1, goal_line" in result.stdout
    assert "Current situation: 1st & 10, opp 0, goal_line" not in result.stdout
    assert result.stdout.count("Drive ended: touchdown") == 1


def test_session_first_and_ten_uses_run_rpo_pass_blocks(tmp_path: Path) -> None:
    """1st-and-10 should print run, RPO, and pass blocks."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("run", "Duo", play_type="run", play_family="run", run_scheme="duo", pass_concept="none", personnel="11", tags="inside_run;gap_scheme;physical_run;short_yardage_run"),
            make_play("rpo", "Power RPO Stick", play_type="rpo", play_family="rpo", run_scheme="power", rpo_tag="stick", pass_concept="stick", personnel="11", tags="rpo;quick_game;conflict_call;safe_conversion"),
            make_play("pass", "Stick TRIPS", pass_concept="stick", personnel="11", tags="quick_game;safe_conversion"),
        ],
    )

    result = run_session(playbook_path, "first and 10 own 25 personnel 11\nq\n", "--top-n", "5", "--block-size", "2")

    assert result.returncode == 0
    assert "Run options:" in result.stdout
    assert "RPO options:" in result.stdout
    assert "Pass options:" in result.stdout


def test_session_second_short_uses_shot_safe_rpo_blocks(tmp_path: Path) -> None:
    """2nd-and-short should print shot, safe, and RPO conflict blocks."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play("shot", "Yankee", pass_concept="yankee", play_action="true", preferred_down_distance="second_short", personnel="11", tags="shot_play;deep_pass;explosive;play_action;play_action_shot"),
            make_play("safe", "Duo", play_type="run", play_family="run", run_scheme="duo", pass_concept="none", preferred_down_distance="second_short", personnel="11", tags="inside_run;gap_scheme;physical_run;short_yardage_run;safe_conversion"),
            make_play("rpo", "Insert RPO Quick Out", play_type="rpo", play_family="rpo", run_scheme="inside_zone", run_modifier="insert", rpo_tag="quick_out", pass_concept="quick_out", preferred_down_distance="second_short", personnel="11", tags="rpo;quick_game;conflict_call;safe_conversion;quick_access;access_throw"),
        ],
    )

    result = run_session(playbook_path, "second and 2 own 25 personnel 11\nq\n", "--top-n", "5", "--block-size", "2")

    assert result.returncode == 0
    assert "Shot play options:" in result.stdout
    assert "Safe conversion options:" in result.stdout
    assert "RPO conflict options:" in result.stdout


def test_session_avoids_duplicate_play_ids_across_blocks_when_possible() -> None:
    """Block rendering should avoid reusing the same play across blocks when depth exists."""
    playbook = pd.DataFrame(
        [
            make_play("run", "Duo", play_type="run", play_family="run", run_scheme="duo", pass_concept="none", personnel="11", tags="inside_run;gap_scheme;physical_run"),
            make_play("rpo1", "Power RPO Stick", play_type="rpo", play_family="rpo", run_scheme="power", rpo_tag="stick", pass_concept="stick", personnel="11", tags="rpo;quick_game;conflict_call;safe_conversion"),
            make_play("rpo2", "Insert RPO Quick Out", play_type="rpo", play_family="rpo", run_scheme="inside_zone", run_modifier="insert", rpo_tag="quick_out", pass_concept="quick_out", personnel="11", tags="rpo;quick_game;conflict_call;safe_conversion;quick_access"),
            make_play("pass", "Stick", pass_concept="stick", personnel="11", tags="quick_game;safe_conversion"),
        ]
    )
    situation = playcaller_session.build_situation(
        down=1,
        distance=10,
        field_zone="midfield",
        personnel="11",
    )

    groups = playcaller_session.build_recommendation_groups(
        playbook,
        situation,
        tendencies=None,
        top_n=5,
        block_size=2,
        intent="balanced",
    )

    seen: set[str] = set()
    for _, plays in groups:
        for play in plays:
            play_id = str(play["play_id"])
            assert play_id not in seen
            seen.add(play_id)


def test_choose_output_blocks_maps_third_long_to_conversion_pressure_constraint() -> None:
    """3rd-and-long should use long-yardage coordinator blocks."""
    situation = playcaller_session.build_situation(
        down=3,
        distance=10,
        field_zone="midfield",
        personnel="11",
    )

    blocks = playcaller_session.choose_output_blocks(situation)

    assert [block.title for block in blocks] == [
        "Third-long conversion options:",
        "Pressure answers:",
        "Constraint / screen options:",
    ]


def test_build_recommendation_groups_returns_dual_lists_on_second_short() -> None:
    """Second-and-short should automatically split shot, safe, and RPO blocks."""
    playbook = pd.DataFrame(
        [
            make_play(
                "shot",
                "Yankee",
                pass_concept="yankee",
                preferred_down_distance="second_short",
                personnel="11",
                tags="shot_play;deep_pass;explosive;play_action;play_action_shot",
                play_action="true",
            ),
            make_play(
                "safe",
                "Stick",
                pass_concept="stick",
                preferred_down_distance="second_short",
                personnel="11",
                tags="quick_game;safe_conversion",
            ),
            make_play(
                "rpo",
                "Glance RPO",
                play_type="rpo",
                play_family="rpo",
                run_scheme="inside_zone",
                rpo_tag="glance",
                pass_concept="glance",
                preferred_down_distance="second_short",
                personnel="11",
                tags="rpo;conflict_call;safe_conversion;man_beater",
            ),
        ]
    )
    situation = playcaller_session.build_situation(
        down=2,
        distance=2,
        field_zone="midfield",
        personnel="11",
    )

    groups = playcaller_session.build_recommendation_groups(
        playbook,
        situation,
        tendencies=None,
        top_n=2,
        block_size=2,
        intent="balanced",
    )

    assert [heading for heading, _ in groups] == [
        "Shot play options:",
        "Safe conversion options:",
        "RPO conflict options:",
    ]
    shot_ids = {play["play_id"] for play in groups[0][1]}
    safe_ids = [play["play_id"] for play in groups[1][1]]
    rpo_ids = [play["play_id"] for play in groups[2][1]]
    assert "shot" in shot_ids
    assert "shot" not in safe_ids
    assert "rpo" in rpo_ids


def test_session_show_reasons_toggles_reason_output(tmp_path: Path) -> None:
    """Detailed reasons should stay behind the explicit flag."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS")],
    )

    default_result = run_session(playbook_path, "primo e 10 own 25\nq\n", "--top-n", "1")
    verbose_result = run_session(
        playbook_path,
        "primo e 10 own 25\nq\n",
        "--top-n",
        "1",
        "--show-reasons",
    )

    assert default_result.returncode == 0
    assert "reasons:" not in default_result.stdout
    assert verbose_result.returncode == 0
    assert "reasons:" in verbose_result.stdout


def test_session_with_known_rhinos_bucket_prints_tendencies_used_yes(tmp_path: Path) -> None:
    """Known Rhinos buckets should show tendency usage and a compact snapshot."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [
            make_play(
                "stick_dot",
                "Stick DOT",
                preferred_down_distance="early_down;second_medium;third_medium",
                preferred_field_zone="open_field;midfield",
                beats_coverage="cover1_man_free",
                personnel="11",
            )
        ],
    )

    result = run_session(
        playbook_path,
        "third and 6 midfield cover1_man_free odd box 6 personnel 11\nq\n",
        "--top-n",
        "1",
        "--opponent",
        "Rhinos",
    )

    assert result.returncode == 0
    assert "Opponent tendencies used: yes" in result.stdout
    assert "Opponent tendency snapshot:" in result.stdout
    assert "- coverage:" in result.stdout
    assert "- front:" in result.stdout
    assert "- box:" in result.stdout


def test_session_unknown_opponent_prints_tendencies_used_no(tmp_path: Path) -> None:
    """Unknown opponents should report a compact no-match reason."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS", personnel="11")],
    )

    result = run_session(
        playbook_path,
        "third and 6 midfield cover1_man_free odd box 6 personnel 11\nq\n",
        "--top-n",
        "1",
        "--opponent",
        "Unknowns",
    )

    assert result.returncode == 0
    assert "Opponent tendencies used: no" in result.stdout
    assert "unknown opponent" in result.stdout


def test_session_without_opponent_keeps_old_output_behavior(tmp_path: Path) -> None:
    """Without --opponent the session should omit tendency status lines."""
    playbook_path = tmp_path / "playbook.csv"
    write_csv(
        playbook_path,
        list(PLAYBOOK_COLUMNS),
        [make_play("stick", "Stick TRIPS")],
    )

    result = run_session(playbook_path, "primo e 10 midfield\nq\n", "--top-n", "1")

    assert result.returncode == 0
    assert "Opponent tendencies used:" not in result.stdout
    assert "Opponent tendency snapshot:" not in result.stdout


def test_first_and_ten_midfield_matches_first_medium_midfield_personnel_11_bucket() -> None:
    """Session tendency lookup should map 1st-and-10 into the synthetic first-medium bucket."""
    state = playcaller_session.GameState(down=1, distance=10, field_position=50)
    defense_state = playcaller_session.DefenseState(personnel="11")

    situation = playcaller_session.build_tendency_lookup_situation("Rhinos", state, defense_state)

    assert situation == {
        "opponent": "rhinos",
        "down": "1",
        "distance_bucket": "medium",
        "field_zone": "midfield",
        "personnel": "11",
    }


def test_second_and_three_midfield_maps_to_second_short_tendency_bucket() -> None:
    """Session tendency lookup should treat 2nd-and-3 as short yardage."""
    state = playcaller_session.GameState(down=2, distance=3, field_position=50)
    defense_state = playcaller_session.DefenseState(personnel="11")

    situation = playcaller_session.build_tendency_lookup_situation("Rhinos", state, defense_state)

    assert situation == {
        "opponent": "rhinos",
        "down": "2",
        "distance_bucket": "short",
        "field_zone": "midfield",
        "personnel": "11",
    }


def test_session_passes_tendencies_into_recommend_plays(monkeypatch: object) -> None:
    """The session recommendation path should forward matched tendencies into the engine."""
    captured: dict[str, object] = {}

    def fake_recommend_plays(
        playbook: pd.DataFrame,
        situation: dict[str, object],
        *,
        tendencies: object = None,
        top_n: int = 3,
        intent: str = "balanced",
    ) -> list[dict[str, object]]:
        captured["tendencies"] = tendencies
        return [{"play_name": "Stub Call", "score": 50.0, "reasons": []}]

    monkeypatch.setattr(playcaller_session, "recommend_plays", fake_recommend_plays)

    playbook = pd.DataFrame([make_play("stub", "Stub Call", personnel="11")])
    state = playcaller_session.GameState(down=3, distance=6, field_position=50)
    defense_state = playcaller_session.DefenseState(
        front_id="odd",
        coverage_id="cover1_man_free",
        pressure_id="none",
        box_count=6,
        personnel="11",
    )
    args = argparse.Namespace(
        top_n=1,
        opponent="Rhinos",
        intent="balanced",
        show_reasons=False,
        opponent_tendencies_path=str(PROJECT_ROOT / "data" / "opponent_tendencies.csv"),
    )
    analyzer, _ = playcaller_session.load_tendency_analyzer(args)

    playcaller_session.print_recommendations_for_state(
        playbook,
        state,
        defense_state,
        args=args,
        analyzer=analyzer,
    )

    assert captured["tendencies"] is not None


def test_format_matched_tendency_bucket_uses_only_matched_keys() -> None:
    """Matched tendency bucket output should stay compact and explicit."""
    bucket = playcaller_session.format_matched_tendency_bucket(
        {
            "opponent": "rhinos",
            "down": "2",
            "distance_bucket": "long",
            "field_zone": "open_field",
            "personnel": "10",
        },
        ("opponent", "down", "distance_bucket", "field_zone", "personnel"),
    )

    assert bucket == "opponent=rhinos, down=2, distance=long, field_zone=open_field, personnel=10"


def test_lookup_tendencies_returns_explicit_personnel_fallback_metadata() -> None:
    """Session lookup should surface when it leaves the personnel-specific bucket."""
    analyzer = playcaller_session.OpponentTendencyAnalyzer.from_csv(
        PROJECT_ROOT / "data" / "opponent_tendencies.csv"
    )
    args = argparse.Namespace(opponent="Rhinos")
    state = playcaller_session.GameState(down=1, distance=10, field_position=50)
    defense_state = playcaller_session.DefenseState(personnel="12")

    tendencies, reason, metadata = playcaller_session.lookup_tendencies(
        analyzer,
        args,
        state,
        defense_state,
    )

    assert reason is None
    assert tendencies is not None
    assert metadata is not None
    assert metadata["fallback_used"] is True
    assert metadata["matched_keys"] == ("opponent", "down", "distance_bucket", "field_zone")


def test_goal_line_blocks_use_physical_runs_and_goal_line_pass_answers() -> None:
    """Goal-line mode should stay compact and avoid any RPO-specific block."""
    playbook = pd.DataFrame(
        [
            make_play(
                "duo",
                "Duo",
                play_type="run",
                play_family="run",
                run_scheme="duo",
                pass_concept="none",
                personnel="11",
                preferred_field_zone="goal_line",
                tags="inside_run;gap_scheme;physical_run;short_yardage_run;goal_line_answer",
            ),
            make_play(
                "go_out",
                "Go Out",
                pass_concept="go_out",
                personnel="11",
                preferred_field_zone="goal_line",
                tags="quick_game;quick_access;access_throw;safe_conversion;goal_line_answer;man_beater",
            ),
            make_play(
                "rpo",
                "Bubble RPO",
                play_type="rpo",
                play_family="rpo",
                run_scheme="inside_zone",
                rpo_tag="bubble",
                pass_concept="bubble",
                personnel="11",
                preferred_field_zone="goal_line",
                tags="rpo;conflict_call;quick_access;access_throw;constraint_call",
            ),
        ]
    )
    situation = playcaller_session.build_situation(
        down=3,
        distance=1,
        field_zone="goal_line",
        personnel="11",
    )

    groups = playcaller_session.build_recommendation_groups(
        playbook,
        situation,
        tendencies=None,
        top_n=4,
        block_size=2,
        intent="balanced",
    )

    assert [heading for heading, _ in groups] == [
        "Physical run options:",
        "Goal-line pass answers:",
    ]
    all_ids = [str(play["play_id"]) for _, plays in groups for play in plays]
    assert "duo" in all_ids
    assert "go_out" in all_ids
    assert "rpo" not in all_ids


def test_third_long_screen_block_excludes_bubble_now_rpos() -> None:
    """Third-long screen blocks should only surface true screen answers."""
    playbook = pd.DataFrame(
        [
            make_play(
                "dagger",
                "Dagger",
                pass_concept="dagger",
                personnel="11",
                preferred_down_distance="third_long",
                tags="intermediate_passing_concept;third_long_answer;zone_beater",
            ),
            make_play(
                "screen",
                "RB Screen",
                pass_concept="rb_screen",
                personnel="11",
                preferred_down_distance="third_long",
                tags="screen;constraint_call;anti_pressure;pressure_answer",
            ),
            make_play(
                "bubble",
                "Bubble RPO",
                play_type="rpo",
                play_family="rpo",
                run_scheme="inside_zone",
                rpo_tag="bubble",
                pass_concept="bubble",
                personnel="11",
                preferred_down_distance="third_long",
                tags="rpo;conflict_call;quick_access;access_throw;constraint_call",
            ),
        ]
    )
    situation = playcaller_session.build_situation(
        down=3,
        distance=10,
        field_zone="midfield",
        personnel="11",
    )
    tendencies = {
        "pressure": {"yes": 0.9},
        "coverage": {"cover1_man_free": 0.6},
        "box_count": {"7": 0.6},
        "def_front": {"odd_tite": 0.6},
    }

    groups = playcaller_session.build_recommendation_groups(
        playbook,
        situation,
        tendencies=tendencies,
        top_n=5,
        block_size=2,
        intent="balanced",
    )

    block_lookup = {heading: plays for heading, plays in groups}
    screen_ids = [str(play["play_id"]) for play in block_lookup["Constraint / screen options:"]]
    assert "screen" in screen_ids
    assert "bubble" not in screen_ids


def test_live_session_personnel_filter_is_hard() -> None:
    """When live personnel is supplied, only matching plays should survive."""
    playbook = pd.DataFrame(
        [
            make_play("duo_11", "Duo 11", play_type="run", play_family="run", run_scheme="duo", pass_concept="none", personnel="11", tags="inside_run;gap_scheme;physical_run"),
            make_play("stick_10", "Stick 10", pass_concept="stick", personnel="10", tags="quick_game;safe_conversion"),
            make_play("mesh_11", "Mesh 11", pass_concept="mesh", personnel="11", tags="intermediate_passing_concept;man_beater;safe_conversion"),
        ]
    )
    situation = playcaller_session.build_situation(
        down=1,
        distance=10,
        field_zone="midfield",
        personnel="11",
    )

    groups = playcaller_session.build_recommendation_groups(
        playbook,
        situation,
        tendencies=None,
        top_n=5,
        block_size=2,
        intent="balanced",
    )

    returned_ids = {str(play["play_id"]) for _, plays in groups for play in plays}
    assert "stick_10" not in returned_ids
    assert returned_ids <= {"duo_11", "mesh_11"}


def test_block_diversity_avoids_same_concept_same_formation_spam() -> None:
    """Within a small block, diversity should avoid repeating the same concept/formation pair."""
    playbook = pd.DataFrame(
        [
            make_play("run", "Duo", play_type="run", play_family="run", run_scheme="duo", pass_concept="none", personnel="11", tags="inside_run;gap_scheme;physical_run"),
            make_play("rpo", "Stick RPO", play_type="rpo", play_family="rpo", run_scheme="power", rpo_tag="stick", pass_concept="stick", personnel="11", tags="rpo;quick_game;conflict_call;safe_conversion"),
            make_play("stick_dot", "Stick DOT", pass_concept="stick", formation_id="gun_1rb_2x2_spread_no_te", personnel="11", tags="quick_game;safe_conversion"),
            make_play("stick_dot_2", "Stick DOT 2", pass_concept="stick", formation_id="gun_1rb_2x2_spread_no_te", personnel="11", tags="quick_game;safe_conversion"),
            make_play("mesh_trips", "Mesh TRIPS", pass_concept="mesh", formation_id="gun_1rb_3x1_spread_no_te", personnel="11", tags="intermediate_passing_concept;man_beater;safe_conversion"),
        ]
    )
    situation = playcaller_session.build_situation(
        down=1,
        distance=10,
        field_zone="midfield",
        personnel="11",
    )

    groups = playcaller_session.build_recommendation_groups(
        playbook,
        situation,
        tendencies=None,
        top_n=5,
        block_size=2,
        intent="balanced",
    )

    pass_block = dict(groups)["Pass options:"]
    pass_ids = {str(play["play_id"]) for play in pass_block}
    assert not {"stick_dot", "stick_dot_2"} <= pass_ids
