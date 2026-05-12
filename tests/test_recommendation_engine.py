"""Tests for the explainable recommendation scoring model."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from recommendation.engine import build_situation, recommend_plays, score_play


def make_play(**overrides: object) -> dict[str, object]:
    """Create a play row with sensible defaults for tests."""
    play = {
        "play_id": "play",
        "play_name": "Play",
        "play_family": "dropback",
        "play_type": "pass",
        "run_scheme": "none",
        "run_modifier": "none",
        "pass_concept": "spacing",
        "pass_modifier": "none",
        "protection": "6man",
        "rpo_tag": "none",
        "play_action": "false",
        "formation_id": "gun_11_2x2",
        "personnel": "11",
        "beats_front": "any",
        "beats_coverage": "any",
        "beats_pressure": "none",
        "beats_box": "any",
        "preferred_down_distance": "early_down",
        "preferred_field_zone": "any",
        "tags": "",
    }
    play.update(overrides)
    return play


def ids(recommendations: list[dict[str, object]]) -> list[str]:
    """Extract ordered play IDs."""
    return [str(play["play_id"]) for play in recommendations]


class RecommendationEngineTests(unittest.TestCase):
    """Validate the modular football scoring rules."""

    def recommend(
        self,
        plays: list[dict[str, object]],
        **kwargs: object,
    ) -> list[dict[str, object]]:
        intent = str(kwargs.pop("intent", "balanced"))
        tendencies = kwargs.pop("tendencies", None)
        drive_memory = kwargs.pop("drive_memory", None)
        situation = build_situation(
            down=kwargs.pop("down", 1),
            distance=kwargs.pop("distance", 10),
            field_zone=kwargs.pop("field_zone", "midfield"),
            formation_id=kwargs.pop("formation_id", "gun_11_2x2"),
            front_id=kwargs.pop("front_id", "odd_tite"),
            coverage_id=kwargs.pop("coverage_id", "cover3"),
            pressure_id=kwargs.pop("pressure_id", "none"),
            box_count=kwargs.pop("box_count", 6),
            personnel=kwargs.pop("personnel", "11"),
            previous_gain=kwargs.pop("previous_gain", None),
        )
        self.assertFalse(kwargs)
        return recommend_plays(
            pd.DataFrame(plays),
            situation,
            top_n=10,
            intent=intent,
            tendencies=tendencies,
            drive_memory=drive_memory,
        )

    def score(self, play: dict[str, object], **kwargs: object) -> dict[str, object]:
        situation = build_situation(
            down=kwargs.pop("down", 1),
            distance=kwargs.pop("distance", 10),
            field_zone=kwargs.pop("field_zone", "midfield"),
            formation_id=kwargs.pop("formation_id", "gun_11_2x2"),
            front_id=kwargs.pop("front_id", "odd_tite"),
            coverage_id=kwargs.pop("coverage_id", "cover3"),
            pressure_id=kwargs.pop("pressure_id", "none"),
            box_count=kwargs.pop("box_count", 6),
            personnel=kwargs.pop("personnel", "11"),
            previous_gain=kwargs.pop("previous_gain", None),
        )
        self.assertFalse(kwargs)
        return score_play(pd.Series(play), situation)

    def recommend_raw(
        self,
        plays: list[dict[str, object]],
        situation: dict[str, object],
        **kwargs: object,
    ) -> list[dict[str, object]]:
        """Call recommend_plays directly for advanced cases."""
        return recommend_plays(pd.DataFrame(plays), situation, **kwargs)

    def test_third_short_exact_match_beats_early_down(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="exact",
                    preferred_down_distance="third_short",
                ),
                make_play(
                    play_id="early",
                    preferred_down_distance="early_down",
                ),
            ],
            down=3,
            distance=2,
        )
        self.assertEqual(ids(recommendations)[:2], ["exact", "early"])

    def test_drive_memory_penalizes_repeated_pass_concept(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="stick", pass_concept="stick", tags="quick_game"),
                make_play(play_id="mesh", pass_concept="mesh", tags="quick_game;man_beater"),
            ],
            down=2,
            distance=5,
            field_zone="midfield",
            drive_memory={"recent_main_concepts": ["stick"], "recent_pass_concepts": ["stick"]},
        )

        stick = next(play for play in recommendations if play["play_id"] == "stick")
        self.assertTrue(any("drive memory: repeated" in reason for reason in stick["reasons"]))

    def test_drive_memory_boosts_play_action_after_strong_run(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="pa", pass_concept="flood", play_action="true", tags="play_action;play_action_shot"),
                make_play(play_id="quick", pass_concept="stick", tags="quick_game"),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            drive_memory={"play_action_boost_window": 2, "previous_run_like_gain": 7},
        )

        play_action = next(play for play in recommendations if play["play_id"] == "pa")
        self.assertTrue(any("PA boosted after successful run" in reason for reason in play_action["reasons"]))

    def test_drive_memory_does_not_boost_play_action_after_short_run(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="pa", pass_concept="flood", play_action="true", tags="play_action;play_action_shot"),
                make_play(play_id="quick", pass_concept="stick", tags="quick_game"),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            drive_memory={"play_action_boost_window": 0, "previous_run_like_gain": 2},
        )

        play_action = next(play for play in recommendations if play["play_id"] == "pa")
        self.assertFalse(any("PA boosted after successful run" in reason for reason in play_action["reasons"]))

    def test_fourth_short_penalizes_deep_shot(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="run",
                    play_type="run",
                    play_family="run",
                    run_scheme="duo",
                    pass_concept="none",
                    preferred_down_distance="fourth_short",
                    tags="inside_run;gap_scheme",
                    beats_box="heavy_box;loaded_box",
                ),
                make_play(
                    play_id="shot",
                    preferred_down_distance="fourth_short",
                    pass_concept="four_verts",
                    tags="deep_shot;slow_developing",
                ),
            ],
            down=4,
            distance=1,
        )
        deep_shot_play = next(play for play in recommendations if play["play_id"] == "shot")
        self.assertEqual(ids(recommendations)[:2], ["run", "shot"])
        self.assertTrue(any("deep_shot" in reason for reason in deep_shot_play["reasons"]))

    def test_redzone_specific_beats_any(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="specific", preferred_field_zone="redzone"),
                make_play(play_id="any", preferred_field_zone="any"),
            ],
            field_zone="redzone",
        )
        self.assertEqual(ids(recommendations)[:2], ["specific", "any"])

    def test_goal_line_beats_redzone_in_goal_line(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="goal", preferred_field_zone="goal_line"),
                make_play(play_id="red", preferred_field_zone="redzone"),
            ],
            field_zone="goal_line",
        )
        self.assertEqual(ids(recommendations)[:2], ["goal", "red"])

    def test_exact_coverage_beats_family_match(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="exact", beats_coverage="cover3"),
                make_play(play_id="family", beats_coverage="zone"),
            ],
            coverage_id="cover3",
        )
        self.assertEqual(ids(recommendations)[:2], ["exact", "family"])

    def test_specific_coverage_input_matches_base_coverage(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="base", beats_coverage="cover3"),
                make_play(play_id="family", beats_coverage="zone"),
            ],
            coverage_id="cover3_buzz_field",
        )

        base = next(play for play in recommendations if play["play_id"] == "base")
        self.assertEqual(ids(recommendations)[:2], ["base", "family"])
        self.assertTrue(any("coverage: base match cover3" in reason for reason in base["reasons"]))

    def test_specific_coverage_input_family_match_scores_below_base_match(self) -> None:
        base = self.score(make_play(play_id="base", beats_coverage="cover3"), coverage_id="cover3_buzz_field")
        family = self.score(make_play(play_id="family", beats_coverage="zone"), coverage_id="cover3_buzz_field")

        self.assertGreater(float(base["score"]), float(family["score"]))
        self.assertTrue(any("coverage: family match zone" in reason for reason in family["reasons"]))

    def test_cover3_boosts_flood_or_curl_flat(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="flood",
                    pass_concept="flood",
                    preferred_down_distance="second_medium",
                    play_action="true",
                ),
                make_play(
                    play_id="generic",
                    pass_concept="spacing",
                    preferred_down_distance="second_medium",
                ),
            ],
            down=2,
            distance=5,
            coverage_id="cover3",
        )
        flood = next(play for play in recommendations if play["play_id"] == "flood")
        self.assertEqual(ids(recommendations)[:2], ["flood", "generic"])
        self.assertTrue(any("cover3" in reason and "flood" in reason for reason in flood["reasons"]))

    def test_heavy_box_boosts_play_action_or_rpo(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="action",
                    play_action="true",
                    pass_concept="flood",
                    beats_box="heavy_box",
                    preferred_down_distance="second_medium",
                ),
                make_play(
                    play_id="dropback",
                    play_action="false",
                    pass_concept="spacing",
                    preferred_down_distance="second_medium",
                ),
            ],
            down=2,
            distance=5,
            box_count=7,
        )
        action = next(play for play in recommendations if play["play_id"] == "action")
        self.assertEqual(ids(recommendations)[:2], ["action", "dropback"])
        self.assertTrue(any("heavy_box" in reason for reason in action["reasons"]))

    def test_loaded_box_penalizes_inside_run_without_box_fit(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="bad_run",
                    play_type="run",
                    play_family="run",
                    run_scheme="inside_zone",
                    pass_concept="none",
                    beats_box="light_box",
                    preferred_down_distance="second_medium",
                    tags="inside_run",
                ),
                make_play(
                    play_id="answer",
                    play_action="true",
                    pass_concept="flood",
                    beats_box="heavy_box;loaded_box",
                    preferred_down_distance="second_medium",
                    tags="play_action",
                ),
            ],
            down=2,
            distance=5,
            box_count=8,
        )
        bad_run = next(play for play in recommendations if play["play_id"] == "bad_run")
        self.assertEqual(ids(recommendations)[:2], ["answer", "bad_run"])
        self.assertTrue(any("lacks proven fit" in reason for reason in bad_run["reasons"]))

    def test_light_box_boosts_inside_run(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="run",
                    play_type="run",
                    play_family="run",
                    run_scheme="duo",
                    pass_concept="none",
                    preferred_down_distance="second_medium",
                    tags="inside_run;gap_scheme",
                ),
                make_play(
                    play_id="shot",
                    pass_concept="four_verts",
                    preferred_down_distance="second_medium",
                    tags="deep_shot",
                ),
            ],
            down=2,
            distance=5,
            box_count=5,
        )
        self.assertEqual(ids(recommendations)[:2], ["run", "shot"])

    def test_contextual_run_scoring_avoids_flat_identical_run_ties(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="inside", play_type="run", play_family="run", run_scheme="inside_zone", pass_concept="none", tags="inside_run;zone_run", preferred_down_distance="early_down"),
                make_play(play_id="counter", play_type="run", play_family="run", run_scheme="counter", run_modifier="gt", pass_concept="none", tags="gap_scheme", preferred_down_distance="early_down"),
                make_play(play_id="wide", play_type="run", play_family="run", run_scheme="outside_zone", pass_concept="none", tags="perimeter_run", preferred_down_distance="early_down"),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            front_id="odd_tite",
            box_count=7,
            personnel="11",
        )
        scores = [round(float(play["score"]), 2) for play in recommendations[:3]]
        self.assertGreater(len(set(scores)), 1)

    def test_first_and_ten_without_context_does_not_make_bootleg_automatic_top_call(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="base",
                    play_name="Stick",
                    pass_concept="stick",
                    tags="quick_game",
                    preferred_down_distance="early_down",
                ),
                make_play(
                    play_id="boot",
                    play_name="PA Bootleg",
                    pass_concept="bootleg",
                    play_action="true",
                    tags="play_action;bootleg;outside_zone_fake",
                    preferred_down_distance="early_down",
                ),
                make_play(
                    play_id="spacing",
                    play_name="Spacing",
                    pass_concept="spacing",
                    tags="quick_game",
                    preferred_down_distance="early_down",
                ),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            front_id=None,
            coverage_id=None,
            box_count=None,
            personnel=None,
        )
        self.assertEqual(ids(recommendations)[0], "base")
        boot = next(play for play in recommendations if play["play_id"] == "boot")
        self.assertTrue(any("guardrail: play action bootleg needs stronger run-threat context" in reason for reason in boot["reasons"]))

    def test_first_and_ten_without_pressure_keeps_tunnel_screen_out_of_top_three(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="stick", pass_concept="stick", tags="quick_game", preferred_down_distance="early_down"),
                make_play(play_id="spacing", pass_concept="spacing", tags="quick_game", preferred_down_distance="early_down"),
                make_play(play_id="run", play_type="run", play_family="run", run_scheme="inside_zone", pass_concept="none", tags="inside_run;zone_run", preferred_down_distance="early_down"),
                make_play(play_id="screen", play_name="WR Tunnel Screen", pass_concept="wr_tunnel_screen", tags="screen;quick_game;yac", preferred_down_distance="early_down"),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            pressure_id="none",
        )
        self.assertNotIn("screen", ids(recommendations)[:3])

    def test_first_and_ten_rpo_competes_when_box_and_coverage_are_readable(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="run",
                    play_type="run",
                    play_family="run",
                    run_scheme="inside_zone",
                    pass_concept="none",
                    tags="inside_run;zone_run",
                    preferred_down_distance="early_down",
                ),
                make_play(
                    play_id="boot",
                    pass_concept="bootleg",
                    play_action="true",
                    tags="play_action;bootleg",
                    preferred_down_distance="early_down",
                ),
                make_play(
                    play_id="rpo",
                    play_type="rpo",
                    play_family="rpo",
                    run_scheme="inside_zone",
                    run_modifier="insert",
                    rpo_tag="glance",
                    pass_concept="glance",
                    tags="rpo;quick_game;insert;conflict_defender;hot_answer",
                    preferred_down_distance="early_down",
                    beats_coverage="cover3",
                    beats_box="normal_box;heavy_box",
                ),
                make_play(
                    play_id="stick",
                    pass_concept="stick",
                    tags="quick_game",
                    preferred_down_distance="early_down",
                ),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            coverage_id="cover3",
            box_count=6,
            personnel="11",
            tendencies={
                "coverage": {"cover3_buzz_field": 0.55, "cover1_man_free": 0.45},
                "pressure": {"yes": 0.2},
                "box_count": {"6": 0.6, "7": 0.4},
                "def_front": {"even_over": 0.5, "odd_tite": 0.5},
            },
        )
        self.assertIn("rpo", ids(recommendations)[:3])
        rpo = next(play for play in recommendations if play["play_id"] == "rpo")
        self.assertTrue(any("1st down RPO creates conflict" in reason for reason in rpo["reasons"]))

    def test_third_and_one_prefers_physical_short_yardage_runs_over_dropback(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="duo",
                    play_type="run",
                    play_family="run",
                    run_scheme="duo",
                    pass_concept="none",
                    preferred_down_distance="third_short",
                    tags="inside_run;gap_scheme",
                    beats_box="heavy_box;loaded_box",
                ),
                make_play(
                    play_id="insert",
                    play_type="run",
                    play_family="run",
                    run_scheme="inside_zone",
                    run_modifier="insert",
                    pass_concept="none",
                    preferred_down_distance="third_short",
                    tags="inside_run;insert",
                    beats_box="heavy_box;loaded_box",
                ),
                make_play(
                    play_id="pass",
                    pass_concept="drive",
                    preferred_down_distance="third_short",
                    tags="intermediate_pass",
                ),
            ],
            down=3,
            distance=1,
            field_zone="midfield",
            front_id="bear",
            box_count=8,
        )
        self.assertEqual(ids(recommendations)[0], "duo")
        self.assertIn(ids(recommendations)[1], {"insert", "duo"})

    def test_goal_line_short_yardage_keeps_physical_runs_above_generic_quick_game(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="duo",
                    play_type="run",
                    play_family="run",
                    run_scheme="duo",
                    pass_concept="none",
                    preferred_down_distance="third_short",
                    preferred_field_zone="goal_line",
                    tags="inside_run;gap_scheme",
                ),
                make_play(
                    play_id="insert_rpo",
                    play_type="rpo",
                    play_family="rpo",
                    run_scheme="inside_zone",
                    run_modifier="insert",
                    rpo_tag="quick_out",
                    pass_concept="quick_out",
                    preferred_down_distance="third_short",
                    preferred_field_zone="goal_line",
                    tags="rpo;quick_game;insert;conflict_defender;goal_line_answer",
                ),
                make_play(
                    play_id="stick",
                    pass_concept="stick",
                    preferred_down_distance="third_short",
                    preferred_field_zone="goal_line",
                    tags="quick_game",
                ),
            ],
            down=3,
            distance=1,
            field_zone="goal_line",
            front_id="odd_tite",
            box_count=8,
        )
        self.assertEqual(ids(recommendations)[0], "duo")
        self.assertGreater(
            next(play for play in recommendations if play["play_id"] == "duo")["score"],
            next(play for play in recommendations if play["play_id"] == "stick")["score"],
        )

    def test_successful_previous_gain_can_raise_bootleg(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="boot", pass_concept="bootleg", play_action="true", tags="play_action;bootleg", preferred_down_distance="early_down"),
                make_play(play_id="stick", pass_concept="stick", tags="quick_game", preferred_down_distance="early_down"),
            ],
            down=1,
            distance=10,
            field_zone="midfield",
            box_count=7,
            coverage_id="cover3",
            previous_gain=6,
        )
        self.assertEqual(ids(recommendations)[0], "boot")

    def test_third_long_bootleg_is_not_top_five_without_explicit_justification(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="dagger", pass_concept="dagger", tags="intermediate_pass;attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="curl", pass_concept="curl_flat", tags="quick_game;attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="flood", pass_concept="flood", tags="attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="mesh", pass_concept="mesh", tags="quick_game;man_beater", preferred_down_distance="third_long"),
                make_play(play_id="screen", pass_concept="rb_screen", tags="screen;anti_pressure;constraint", preferred_down_distance="third_long"),
                make_play(play_id="boot", pass_concept="bootleg", play_action="true", tags="play_action;bootleg", preferred_down_distance="third_long"),
            ],
            down=3,
            distance=10,
            field_zone="midfield",
            pressure_id="none",
        )
        self.assertNotIn("boot", ids(recommendations)[:5])

    def test_second_short_shot_intent_prefers_real_shot_play(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="shot", pass_concept="yankee", play_action="true", tags="shot_play;deep_shot;play_action", preferred_down_distance="second_short"),
                make_play(play_id="safe", pass_concept="stick", tags="quick_game", preferred_down_distance="second_short"),
                make_play(play_id="rpo", play_type="rpo", play_family="rpo", run_scheme="inside_zone", rpo_tag="bubble", pass_concept="none", tags="rpo;quick_game", preferred_down_distance="second_short"),
            ],
            down=2,
            distance=2,
            intent="shot",
        )
        self.assertEqual(ids(recommendations)[0], "shot")

    def test_second_short_shot_intent_avoids_stick_when_true_shots_exist(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="yankee", pass_concept="yankee", play_action="true", tags="shot_play;deep_shot;play_action", preferred_down_distance="second_short"),
                make_play(play_id="mills", pass_concept="mills", play_action="true", tags="shot_play;deep_shot;play_action", preferred_down_distance="second_short"),
                make_play(play_id="stick", pass_concept="stick", tags="quick_game", preferred_down_distance="second_short"),
            ],
            down=2,
            distance=1,
            intent="shot",
        )
        self.assertEqual(ids(recommendations)[:2], ["yankee", "mills"])

    def test_second_short_safe_intent_prefers_conversion_profile(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="shot", pass_concept="yankee", play_action="true", tags="shot_play;deep_shot;play_action", preferred_down_distance="second_short"),
                make_play(play_id="safe", pass_concept="stick", tags="quick_game", preferred_down_distance="second_short"),
                make_play(play_id="rpo", play_type="rpo", play_family="rpo", run_scheme="inside_zone", rpo_tag="stick", pass_concept="none", tags="rpo;quick_game;insert", preferred_down_distance="second_short"),
            ],
            down=2,
            distance=2,
            intent="safe",
        )
        self.assertIn(ids(recommendations)[0], {"safe", "rpo"})
        self.assertGreater(
            next(play for play in recommendations if play["play_id"] == "safe")["score"],
            next(play for play in recommendations if play["play_id"] == "shot")["score"],
        )

    def test_second_short_safe_intent_keeps_physical_run_above_deep_shot(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="shot", pass_concept="mills", play_action="true", tags="shot_play;deep_shot;play_action", preferred_down_distance="second_short"),
                make_play(play_id="duo", play_type="run", play_family="run", run_scheme="duo", pass_concept="none", tags="inside_run;gap_scheme", preferred_down_distance="second_short"),
                make_play(play_id="rpo", play_type="rpo", play_family="rpo", run_scheme="power", rpo_tag="stick", pass_concept="stick", tags="rpo;quick_game;conflict_defender", preferred_down_distance="second_short"),
            ],
            down=2,
            distance=1,
            intent="safe",
            box_count=8,
            front_id="bear",
        )
        self.assertIn(ids(recommendations)[0], {"duo", "rpo"})

    def test_third_long_without_pressure_keeps_rb_screen_below_real_conversion_calls(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="dagger", pass_concept="dagger", tags="intermediate_pass;attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="flood", pass_concept="flood", tags="attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="curl", pass_concept="curl_flat", tags="quick_game;attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="screen", pass_concept="rb_screen", tags="screen;anti_pressure;constraint", preferred_down_distance="third_long"),
            ],
            down=3,
            distance=10,
            pressure_id="none",
        )
        self.assertLess(ids(recommendations).index("screen"), len(recommendations))
        self.assertNotIn("screen", ids(recommendations)[:3])

    def test_third_long_with_pressure_can_keep_screen_viable(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="dagger", pass_concept="dagger", tags="intermediate_pass;attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="curl", pass_concept="curl_flat", tags="quick_game;attacks_sticks", preferred_down_distance="third_long"),
                make_play(play_id="screen", pass_concept="rb_screen", beats_pressure="nickel_blitz;any_pressure", tags="screen;anti_pressure;pressure_beater;constraint", preferred_down_distance="third_long"),
            ],
            down=3,
            distance=10,
            pressure_id="nickel_blitz",
        )
        self.assertIn("screen", ids(recommendations)[:3])

    def test_reasons_are_explainable(self) -> None:
        scored = self.score(
            make_play(
                play_id="explain",
                preferred_down_distance="third_short",
                preferred_field_zone="redzone",
                beats_front="odd_tite",
                beats_coverage="cover3",
                beats_box="heavy_box",
                play_action="true",
                pass_concept="flood",
                tags="redzone",
            ),
            down=3,
            distance=2,
            field_zone="redzone",
            front_id="odd_tite",
            coverage_id="cover3",
            box_count=7,
        )
        text = " ".join(scored["reasons"])
        for category in [
            "down-distance",
            "field-zone",
            "front",
            "coverage",
            "box",
            "tactical",
        ]:
            self.assertIn(category, text)

    def test_score_is_clamped_between_0_and_100(self) -> None:
        low = self.score(
            make_play(
                play_id="low",
                preferred_down_distance="third_long",
                preferred_field_zone="goal_line",
                pass_concept="four_verts",
                tags="deep_shot;slow_developing",
                formation_id="under_center",
                personnel="12",
                beats_box="light_box",
            ),
            down=4,
            distance=1,
            field_zone="goal_line",
            box_count=8,
            formation_id="gun_11_2x2",
            personnel="11",
        )
        high = self.score(
            make_play(
                play_id="high",
                play_type="run",
                play_family="run",
                run_scheme="duo",
                pass_concept="none",
                preferred_down_distance="third_short",
                preferred_field_zone="goal_line",
                beats_front="odd_tite",
                beats_coverage="cover3",
                beats_box="heavy_box",
                tags="inside_run;gap_scheme;redzone",
            ),
            down=3,
            distance=1,
            field_zone="goal_line",
            front_id="odd_tite",
            coverage_id="cover3",
            box_count=7,
        )
        self.assertGreaterEqual(low["score"], 0.0)
        self.assertLessEqual(high["score"], 100.0)

    def test_stable_tie_breaking(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="first", play_name="First"),
                make_play(play_id="second", play_name="Second"),
            ],
            down=1,
            distance=10,
        )
        self.assertEqual(ids(recommendations)[:2], ["first", "second"])

    def test_open_field_exact_is_not_overweighted(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="weak_open",
                    preferred_field_zone="open_field",
                    preferred_down_distance="early_down",
                    pass_concept="four_verts",
                    tags="deep_shot",
                    beats_front="any",
                    beats_coverage="cover3",
                    beats_box="normal_box",
                ),
                make_play(
                    play_id="better_any",
                    play_type="rpo",
                    play_family="rpo",
                    rpo_tag="bubble",
                    preferred_field_zone="any",
                    preferred_down_distance="second_medium",
                    pass_concept="glance",
                    tags="quick_game",
                    beats_front="even",
                    beats_coverage="cover3",
                    beats_box="normal_box",
                ),
            ],
            down=2,
            distance=7,
            field_zone="open_field",
            front_id="even",
            coverage_id="cover3",
            box_count=6,
            personnel="10",
            formation_id="gun_11_2x2",
        )
        self.assertEqual(ids(recommendations)[:2], ["better_any", "weak_open"])

    def test_third_medium_prefers_conversion_concept_over_four_verts(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="conversion",
                    pass_concept="stick",
                    preferred_down_distance="third_medium",
                    beats_coverage="cover1",
                    tags="quick_game;man_beater",
                ),
                make_play(
                    play_id="verts",
                    pass_concept="four_verts",
                    preferred_down_distance="third_medium",
                    beats_coverage="cover1",
                    tags="deep_shot",
                ),
            ],
            down=3,
            distance=5,
            field_zone="open_field",
            coverage_id="cover1",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        verts = next(play for play in recommendations if play["play_id"] == "verts")
        self.assertEqual(ids(recommendations)[:2], ["conversion", "verts"])
        self.assertTrue(any("third_medium" in reason or "deep concept" in reason for reason in verts["reasons"]))

    def test_second_medium_does_not_automatically_rank_four_verts_first(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="rpo",
                    play_type="rpo",
                    play_family="rpo",
                    rpo_tag="bubble",
                    pass_concept="glance",
                    preferred_down_distance="second_medium",
                    beats_coverage="cover3",
                    tags="quick_game",
                ),
                make_play(
                    play_id="verts",
                    pass_concept="four_verts",
                    preferred_down_distance="second_medium",
                    beats_coverage="cover3",
                    tags="deep_shot",
                ),
            ],
            down=2,
            distance=7,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="under",
            box_count=6,
            personnel="10",
        )
        self.assertEqual(ids(recommendations)[:2], ["rpo", "verts"])

    def test_four_verts_not_man_beater_without_explicit_tag(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="mesh",
                    pass_concept="mesh",
                    preferred_down_distance="third_medium",
                    beats_coverage="cover1",
                    tags="man_beater;quick_game",
                ),
                make_play(
                    play_id="verts",
                    pass_concept="four_verts",
                    preferred_down_distance="third_medium",
                    beats_coverage="cover1",
                    tags="deep_shot",
                ),
            ],
            down=3,
            distance=5,
            field_zone="open_field",
            coverage_id="cover1",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        mesh = next(play for play in recommendations if play["play_id"] == "mesh")
        verts = next(play for play in recommendations if play["play_id"] == "verts")
        self.assertTrue(any("man_beater" in reason for reason in mesh["reasons"]))
        self.assertFalse(any("man_beater" in reason for reason in verts["reasons"]))

    def test_third_and_one_with_pressure_tendencies_keeps_true_short_yardage_answer_near_top(self) -> None:
        situation = build_situation(
            down=3,
            distance=1,
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="odd_tite",
            coverage_id="cover1_man_free",
            pressure_id="none",
            box_count=7,
            personnel="11",
        )
        tendencies = {
            "coverage": {
                "cover0_pressure": 1 / 3,
                "cover1_man_free": 1 / 3,
                "cover1_robber_strong": 1 / 3,
            },
            "pressure": {"yes": 1.0},
            "box_count": {"7": 0.5, "8": 0.5},
            "def_front": {
                "bear": 1 / 3,
                "odd_5": 1 / 3,
                "odd_tite": 1 / 3,
            },
        }

        recommendations = self.recommend_raw(
            [
                make_play(
                    play_id="run",
                    play_name="Duo",
                    play_type="run",
                    play_family="run",
                    run_scheme="duo",
                    pass_concept="none",
                    preferred_down_distance="third_short;fourth_short",
                    beats_box="heavy_box;loaded_box",
                    beats_coverage="cover1",
                    tags="inside_run;gap_scheme",
                ),
                make_play(
                    play_id="access_rpo",
                    play_name="Insert Glance",
                    play_type="rpo",
                    play_family="rpo",
                    run_scheme="inside_zone",
                    pass_concept="glance",
                    rpo_tag="glance",
                    preferred_down_distance="third_short;fourth_short",
                    beats_box="heavy_box;loaded_box",
                    beats_coverage="cover1",
                    tags="rpo;quick_game;insert;conflict_defender;hot_answer",
                ),
                make_play(
                    play_id="mesh",
                    play_name="Mesh",
                    pass_concept="mesh",
                    preferred_down_distance="third_short;fourth_short",
                    beats_box="heavy_box",
                    beats_coverage="cover1",
                    tags="quick_game;mesh;man_beater",
                ),
                make_play(
                    play_id="beamer",
                    play_name="Beamer",
                    pass_concept="beamer",
                    preferred_down_distance="third_short;fourth_short",
                    beats_box="heavy_box",
                    beats_coverage="cover1",
                    tags="quick_game;beamer;man_beater;spacing",
                ),
            ],
            situation,
            tendencies=tendencies,
            top_n=4,
        )

        top_ids = ids(recommendations[:2])
        self.assertTrue(any(play_id in {"run", "access_rpo"} for play_id in top_ids))

        run = next(play for play in recommendations if play["play_id"] == "run")
        access_rpo = next(play for play in recommendations if play["play_id"] == "access_rpo")
        mesh = next(play for play in recommendations if play["play_id"] == "mesh")
        beamer = next(play for play in recommendations if play["play_id"] == "beamer")

        self.assertGreater(float(run["score"]), float(mesh["score"]))
        self.assertGreater(float(access_rpo["score"]), float(beamer["score"]))
        self.assertTrue(any("run-first answer is preferred in short yardage" in reason for reason in run["reasons"]))
        self.assertTrue(any("immediate RPO access throw can convert critical short yardage" in reason for reason in access_rpo["reasons"]))
        self.assertTrue(any("generic man-beater is less reliable" in reason for reason in mesh["reasons"]))

    def test_four_verts_cover3_bonus_is_contextual(self) -> None:
        plays = [
            make_play(
                play_id="verts",
                pass_concept="four_verts",
                preferred_down_distance="early_down;third_medium",
                beats_coverage="cover3",
                tags="deep_shot",
            ),
                make_play(
                    play_id="curl",
                    pass_concept="curl_flat",
                    preferred_down_distance="early_down;third_medium",
                    beats_coverage="cover3",
                    tags="quick_game",
                ),
            ]
        early = self.recommend(
            plays,
            down=1,
            distance=10,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        conversion = self.recommend(
            plays,
            down=3,
            distance=5,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        self.assertIn(ids(early)[0], {"verts", "curl"})
        self.assertEqual(ids(conversion)[:2], ["curl", "verts"])

    def test_rpo_or_quick_game_can_beat_deep_shot_on_second_medium(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="rpo",
                    play_type="rpo",
                    play_family="rpo",
                    rpo_tag="hitch",
                    pass_concept="glance",
                    preferred_down_distance="second_medium",
                    beats_coverage="cover3",
                    tags="quick_game",
                ),
                make_play(
                    play_id="verts",
                    play_type="pass",
                    pass_concept="four_verts",
                    preferred_down_distance="second_medium",
                    beats_coverage="cover3",
                    tags="deep_shot",
                ),
            ],
            down=2,
            distance=7,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="under",
            box_count=6,
            personnel="10",
        )
        self.assertEqual(ids(recommendations)[:2], ["rpo", "verts"])

    def test_early_down_only_counts_strongly_on_first_down(self) -> None:
        play = make_play(play_id="early", preferred_down_distance="early_down")
        first = self.score(play, down=1, distance=10)
        second = self.score(play, down=2, distance=5)
        third = self.score(play, down=3, distance=5)

        self.assertTrue(any("+24 down-distance: exact early_down fit on 1st down" in reason for reason in first["reasons"]))
        self.assertFalse(any("+18 down-distance" in reason or "+20 down-distance" in reason for reason in second["reasons"]))
        self.assertFalse(any("+18 down-distance" in reason or "+20 down-distance" in reason for reason in third["reasons"]))
        self.assertTrue(any("weak fallback outside 1st down" in reason for reason in second["reasons"]))
        self.assertTrue(any("weak fallback outside 1st down" in reason for reason in third["reasons"]))

    def test_second_long_does_not_overreward_early_down(self) -> None:
        recommendations = self.recommend(
            [
                make_play(play_id="long", preferred_down_distance="second_long"),
                make_play(play_id="early", preferred_down_distance="early_down"),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            front_id="even",
            coverage_id="cover4",
            box_count=5,
            personnel="10",
        )
        early = next(play for play in recommendations if play["play_id"] == "early")
        self.assertEqual(ids(recommendations)[:2], ["long", "early"])
        self.assertFalse(any("+18 down-distance" in reason or "+20 down-distance" in reason for reason in early["reasons"]))
        self.assertTrue(
            any("weak fallback outside 1st down" in reason for reason in early["reasons"])
            or not any("down-distance" in reason for reason in early["reasons"])
        )

    def test_second_long_penalizes_run_first_rpo_bubble(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="pass",
                    play_type="pass",
                    pass_concept="y_cross",
                    preferred_down_distance="second_long",
                    tags="intermediate_pass",
                    beats_front="even",
                    beats_coverage="cover4",
                    beats_box="light_box",
                ),
                make_play(
                    play_id="bubble",
                    play_type="rpo",
                    play_family="rpo",
                    rpo_tag="bubble",
                    run_scheme="counter",
                    preferred_down_distance="early_down",
                    tags="inside_run;gap_scheme",
                    beats_front="even",
                    beats_coverage="cover4",
                    beats_box="light_box",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            front_id="even",
            coverage_id="cover4",
            box_count=5,
            personnel="10",
        )
        self.assertEqual(ids(recommendations)[:2], ["pass", "bubble"])

    def test_light_box_run_bonus_disabled_in_long_yardage(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="run",
                    play_type="run",
                    play_family="run",
                    run_scheme="duo",
                    pass_concept="none",
                    beats_box="light_box",
                    preferred_down_distance="second_long",
                    tags="inside_run;gap_scheme",
                ),
                make_play(
                    play_id="pass",
                    play_type="pass",
                    pass_concept="curl_flat",
                    beats_box="light_box",
                    preferred_down_distance="second_long",
                    tags="intermediate_pass",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            box_count=5,
            coverage_id="cover4",
            front_id="even",
            personnel="10",
        )
        run = next(play for play in recommendations if play["play_id"] == "run")
        self.assertEqual(ids(recommendations)[:2], ["pass", "run"])
        self.assertFalse(any("inside_run should attack a light_box" in reason for reason in run["reasons"]))
        self.assertFalse(any("gap_scheme can punish a light_box" in reason for reason in run["reasons"]))

    def test_cover4_second_long_prefers_chunk_pass_over_rpo_now(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="chunk",
                    play_type="pass",
                    pass_concept="y_cross",
                    preferred_down_distance="second_long",
                    beats_coverage="cover4",
                    tags="intermediate_pass",
                ),
                make_play(
                    play_id="now",
                    play_type="rpo",
                    play_family="rpo",
                    rpo_tag="now",
                    run_scheme="counter",
                    preferred_down_distance="early_down",
                    beats_coverage="cover4",
                    tags="inside_run;gap_scheme",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            coverage_id="cover4",
            front_id="even",
            box_count=5,
            personnel="10",
        )
        self.assertEqual(ids(recommendations)[:2], ["chunk", "now"])

    def test_specific_coverages_do_not_family_match_other_specific_coverages(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="specific",
                    beats_coverage="cover2;cover3;man",
                    preferred_down_distance="second_long",
                    pass_concept="four_verts",
                ),
                make_play(
                    play_id="generic",
                    beats_coverage="zone",
                    preferred_down_distance="second_long",
                    pass_concept="curl_flat",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            coverage_id="cover4",
            front_id="even",
            box_count=5,
            personnel="10",
        )
        specific = next(play for play in recommendations if play["play_id"] == "specific")
        generic = next(play for play in recommendations if play["play_id"] == "generic")
        self.assertEqual(ids(recommendations)[:2], ["generic", "specific"])
        self.assertFalse(any("coverage: family match" in reason for reason in specific["reasons"]))
        self.assertTrue(any("coverage: family match zone" in reason for reason in generic["reasons"]))

    def test_four_verts_does_not_get_cover4_bonus_without_cover4_tag(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="verts",
                    pass_concept="four_verts",
                    beats_coverage="cover2;cover3;man",
                    preferred_down_distance="second_long",
                    tags="seam_read;middle_field_read;deep_shot",
                ),
                make_play(
                    play_id="curl",
                    pass_concept="curl_flat",
                    beats_coverage="cover4",
                    preferred_down_distance="second_long",
                    tags="",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            coverage_id="cover4",
            front_id="even",
            box_count=5,
            personnel="10",
        )
        verts = next(play for play in recommendations if play["play_id"] == "verts")
        self.assertEqual(ids(recommendations)[:2], ["curl", "verts"])
        for forbidden in [
            "contextual value versus cover4",
            "seams profile helps versus cover4",
            "family match via cover2",
        ]:
            self.assertFalse(any(forbidden in reason for reason in verts["reasons"]))

    def test_zone_coverage_traits_do_not_rescue_missing_specific_coverage(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="miss",
                    beats_coverage="cover2;cover3",
                    preferred_down_distance="second_long",
                    pass_concept="four_verts",
                    tags="deep_shot",
                ),
                make_play(
                    play_id="hit",
                    beats_coverage="cover4",
                    preferred_down_distance="second_long",
                    pass_concept="curl_flat",
                    tags="",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            coverage_id="cover4",
            front_id="even",
            box_count=5,
            personnel="10",
        )
        miss = next(play for play in recommendations if play["play_id"] == "miss")
        self.assertEqual(ids(recommendations)[:2], ["hit", "miss"])
        self.assertFalse(any("zone-coverage traits fit zone coverage" in reason for reason in miss["reasons"]))

    def test_generic_zone_beats_specific_mismatch_for_cover4(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="specific",
                    beats_coverage="cover2;cover3",
                    preferred_down_distance="second_long",
                    pass_concept="four_verts",
                ),
                make_play(
                    play_id="zone",
                    beats_coverage="zone",
                    preferred_down_distance="second_long",
                    pass_concept="curl_flat",
                ),
            ],
            down=2,
            distance=15,
            field_zone="open_field",
            coverage_id="cover4",
            front_id="even",
            box_count=5,
            personnel="10",
        )
        specific = next(play for play in recommendations if play["play_id"] == "specific")
        zone = next(play for play in recommendations if play["play_id"] == "zone")
        self.assertTrue(any("coverage: family match zone" in reason for reason in zone["reasons"]))
        self.assertFalse(any("coverage: family match" in reason for reason in specific["reasons"]))

    def test_top_n_prefers_unique_concepts_before_duplicates(self) -> None:
        plays = [
            make_play(play_id="verts1", pass_concept="four_verts", pass_modifier="base", play_action="false", preferred_down_distance="second_long", beats_coverage="cover4"),
            make_play(play_id="verts2", pass_concept="four_verts", pass_modifier="base", play_action="false", preferred_down_distance="second_long", beats_coverage="cover4"),
            make_play(play_id="verts3", pass_concept="four_verts", pass_modifier="base", play_action="false", preferred_down_distance="second_long", beats_coverage="cover4"),
            make_play(play_id="verts4", pass_concept="four_verts", pass_modifier="base", play_action="false", preferred_down_distance="second_long", beats_coverage="cover4"),
            make_play(play_id="curl1", pass_concept="curl_flat", preferred_down_distance="second_long", beats_coverage="cover4"),
            make_play(play_id="flood1", pass_concept="flood", preferred_down_distance="second_long", beats_coverage="cover4"),
        ]
        situation = build_situation(
            down=2,
            distance=15,
            field_zone="open_field",
            front_id="even",
            coverage_id="cover4",
            box_count=5,
            personnel="10",
            formation_id=None,
        )
        recommendations = self.recommend_raw(
            plays,
            situation,
            top_n=10,
            max_per_concept=2,
        )
        self.assertEqual(
            {play["concept_scheme"] for play in recommendations[:3]},
            {"four_verts", "curl_flat", "flood"},
        )
        self.assertTrue(recommendations[3]["duplicate_fallback"])
        self.assertEqual(len(recommendations), 4)
        self.assertLessEqual(
            sum(1 for play in recommendations if play.get("concept_scheme") == "four_verts"),
            2,
        )

    def test_second_short_shot_intent_prefers_shot_profile(self) -> None:
        recommendations = self.recommend_raw(
            [
                make_play(
                    play_id="shot",
                    pass_concept="four_verts",
                    preferred_down_distance="second_short",
                    beats_coverage="cover3",
                    tags="shot_play;deep_shot",
                ),
                make_play(
                    play_id="safe",
                    pass_concept="stick",
                    preferred_down_distance="second_short",
                    beats_coverage="cover3",
                    tags="quick_game",
                ),
            ],
            build_situation(
                down=2,
                distance=2,
                field_zone="open_field",
                front_id="even",
                coverage_id="cover3",
                box_count=6,
                personnel="10",
            ),
            top_n=5,
            intent="shot",
        )
        shot = next(play for play in recommendations if play["play_id"] == "shot")
        self.assertEqual(ids(recommendations)[:2], ["shot", "safe"])
        self.assertTrue(any("aggressive shot play profile" in reason for reason in shot["reasons"]))

    def test_second_short_safe_intent_prefers_safe_profile(self) -> None:
        recommendations = self.recommend_raw(
            [
                make_play(
                    play_id="shot",
                    pass_concept="mills",
                    preferred_down_distance="second_short",
                    beats_coverage="cover3",
                    tags="shot_play;deep_shot",
                ),
                make_play(
                    play_id="safe",
                    play_type="rpo",
                    play_family="rpo",
                    run_scheme="inside_zone",
                    rpo_tag="stick",
                    pass_concept="stick",
                    preferred_down_distance="second_short",
                    beats_coverage="cover3",
                    tags="quick_game",
                ),
            ],
            build_situation(
                down=2,
                distance=2,
                field_zone="open_field",
                front_id="even",
                coverage_id="cover3",
                box_count=6,
                personnel="10",
            ),
            top_n=5,
            intent="safe",
        )
        safe = next(play for play in recommendations if play["play_id"] == "safe")
        self.assertEqual(ids(recommendations)[:2], ["safe", "shot"])
        self.assertTrue(any("safe move-the-chains answer" in reason for reason in safe["reasons"]))

    def test_third_long_penalizes_play_action(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="pa",
                    pass_concept="dagger",
                    play_action="true",
                    preferred_down_distance="second_medium",
                    beats_coverage="cover3",
                    tags="intermediate_pass;play_action",
                ),
                make_play(
                    play_id="dropback",
                    pass_concept="dagger",
                    play_action="false",
                    preferred_down_distance="third_long",
                    beats_coverage="cover3",
                    tags="intermediate_pass",
                ),
            ],
            down=3,
            distance=10,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        pa = next(play for play in recommendations if play["play_id"] == "pa")
        self.assertEqual(ids(recommendations)[:2], ["dropback", "pa"])
        self.assertTrue(
            any(
                "third/fourth long unless explicitly tagged for that situation"
                in reason
                for reason in pa["reasons"]
            )
        )

    def test_rerank_suppresses_pa_duplicate_pair_in_bad_pa_situation(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="y_cross_pa",
                    pass_concept="y_cross",
                    pass_modifier="intermediate",
                    play_action="true",
                    preferred_down_distance="third_long",
                    beats_coverage="cover3",
                    tags="intermediate_pass;play_action",
                ),
                make_play(
                    play_id="y_cross_dropback",
                    pass_concept="y_cross",
                    pass_modifier="intermediate",
                    play_action="false",
                    preferred_down_distance="third_long",
                    beats_coverage="cover3",
                    tags="intermediate_pass",
                ),
                make_play(
                    play_id="stick",
                    pass_concept="stick",
                    preferred_down_distance="third_long",
                    beats_coverage="cover3",
                    tags="quick_game",
                ),
            ],
            down=3,
            distance=10,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        top_two = ids(recommendations[:2])
        self.assertNotEqual(set(top_two), {"y_cross_pa", "y_cross_dropback"})
        self.assertLess(
            top_two.count("y_cross_pa") + top_two.count("y_cross_dropback"),
            2,
        )
        self.assertLess(
            recommendations.index(next(play for play in recommendations if play["play_id"] == "y_cross_dropback")),
            recommendations.index(next(play for play in recommendations if play["play_id"] == "y_cross_pa")),
        )

    def test_good_pa_situation_can_prefer_pa_variant(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="flood_pa",
                    pass_concept="flood",
                    pass_modifier="intermediate",
                    play_action="true",
                    preferred_down_distance="early_down",
                    beats_coverage="cover3",
                    beats_box="heavy_box;loaded_box",
                    tags="play_action;intermediate_pass",
                ),
                make_play(
                    play_id="flood_dropback",
                    pass_concept="flood",
                    pass_modifier="intermediate",
                    play_action="false",
                    preferred_down_distance="early_down",
                    beats_coverage="cover3",
                    beats_box="heavy_box;loaded_box",
                    tags="intermediate_pass",
                ),
            ],
            down=1,
            distance=10,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=7,
            personnel="11",
        )
        self.assertEqual(ids(recommendations)[:2], ["flood_pa", "flood_dropback"])

    def test_normal_situation_suppresses_screens(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="screen_one",
                    pass_concept="rb_screen",
                    preferred_down_distance="early_down",
                    tags="screen;quick_game",
                ),
                make_play(
                    play_id="screen_two",
                    pass_concept="wr_tunnel_screen",
                    preferred_down_distance="early_down",
                    tags="screen;quick_game",
                ),
                make_play(
                    play_id="stick",
                    pass_concept="stick",
                    preferred_down_distance="early_down",
                    tags="quick_game",
                ),
                make_play(
                    play_id="flood",
                    pass_concept="flood",
                    preferred_down_distance="early_down",
                    tags="intermediate_pass",
                ),
            ],
            down=1,
            distance=10,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        top_three = recommendations[:3]
        self.assertNotIn(top_three[0]["play_id"], {"screen_one", "screen_two"})
        self.assertLessEqual(
            sum(
                1
                for play in top_three
                if str(play.get("play_id")) in {"screen_one", "screen_two"}
            ),
            1,
        )

    def test_pressure_context_can_boost_one_screen(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="screen",
                    pass_concept="rb_screen",
                    protection="screen",
                    beats_pressure="nickel_blitz;any_pressure",
                    preferred_down_distance="third_long",
                    tags="screen;quick_game;hot_answer",
                ),
                make_play(
                    play_id="dagger",
                    pass_concept="dagger",
                    preferred_down_distance="third_long",
                    tags="intermediate_pass",
                ),
                make_play(
                    play_id="stick",
                    pass_concept="stick",
                    preferred_down_distance="third_long",
                    tags="quick_game",
                ),
            ],
            down=3,
            distance=9,
            field_zone="open_field",
            coverage_id="cover1",
            pressure_id="nickel_blitz",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        self.assertEqual(recommendations[0]["play_id"], "screen")

    def test_top_five_has_better_concept_diversity(self) -> None:
        recommendations = self.recommend_raw(
            [
                make_play(play_id="spacing_dbls", pass_concept="spacing", formation_id="gun_1rb_2x2_spread_no_te", preferred_down_distance="second_medium"),
                make_play(play_id="spacing_dot", pass_concept="spacing", formation_id="gun_1rb_2x2_spread_te_off", preferred_down_distance="second_medium"),
                make_play(play_id="spacing_tango", pass_concept="spacing", formation_id="gun_1rb_3x1_spread_y_middle", preferred_down_distance="second_medium"),
                make_play(play_id="stick_trips", pass_concept="stick", formation_id="gun_1rb_3x1_spread_no_te", preferred_down_distance="second_medium", tags="quick_game"),
                make_play(play_id="flood_deuce", pass_concept="flood", formation_id="gun_1rb_2x2_spread_te_on", preferred_down_distance="second_medium", tags="intermediate_pass"),
                make_play(
                    play_id="power_trey",
                    play_type="run",
                    play_family="run",
                    run_scheme="power",
                    pass_concept="none",
                    formation_id="gun_1rb_3x1_spread_te_on",
                    preferred_down_distance="second_medium",
                    tags="inside_run;gap_scheme",
                ),
                make_play(
                    play_id="power_top",
                    play_type="run",
                    play_family="run",
                    run_scheme="power",
                    pass_concept="none",
                    formation_id="gun_1rb_3x1_spread_te_off",
                    preferred_down_distance="second_medium",
                    tags="inside_run;gap_scheme",
                ),
            ],
            build_situation(
                down=2,
                distance=5,
                field_zone="open_field",
                front_id="even",
                coverage_id="cover3",
                box_count=6,
                personnel="10",
            ),
            top_n=5,
        )
        top_five_schemes = [str(play["concept_scheme"]) for play in recommendations[:5]]
        self.assertGreaterEqual(len(set(top_five_schemes)), 4)
        self.assertLessEqual(top_five_schemes[:3].count("spacing"), 1)

    def test_third_long_only_lightly_penalizes_explicit_play_action_answer(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="pa_tagged",
                    pass_concept="dagger",
                    play_action="true",
                    preferred_down_distance="third_long",
                    beats_coverage="cover3",
                    tags="intermediate_pass;play_action",
                ),
                make_play(
                    play_id="pa_untagged",
                    pass_concept="dagger",
                    play_action="true",
                    preferred_down_distance="second_medium",
                    beats_coverage="cover3",
                    tags="intermediate_pass;play_action",
                ),
            ],
            down=3,
            distance=10,
            field_zone="open_field",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        tagged = next(play for play in recommendations if play["play_id"] == "pa_tagged")
        untagged = next(
            play for play in recommendations if play["play_id"] == "pa_untagged"
        )

        self.assertEqual(ids(recommendations)[:2], ["pa_tagged", "pa_untagged"])
        self.assertTrue(
            any(
                "explicitly tags it for this long-yardage situation" in reason
                for reason in tagged["reasons"]
            )
        )
        self.assertGreater(tagged["score"], untagged["score"])

    def test_build_situation_uses_fourth_long_tag(self) -> None:
        situation = build_situation(
            down=4,
            distance=10,
            field_zone="open_field",
            front_id="even",
            coverage_id="cover3",
            box_count=6,
            personnel="10",
        )
        self.assertEqual(situation["down_distance_tag"], "fourth_long")

    def test_pressure_match_boosts_exact_pressure_answer(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="stick_answer",
                    pass_concept="stick",
                    beats_pressure="edge_blitz;field_blitz;nickel_blitz;sim_pressure",
                    tags="quick_game;hot_answer",
                    preferred_down_distance="third_medium",
                ),
                make_play(
                    play_id="generic",
                    pass_concept="y_cross",
                    beats_pressure="none",
                    preferred_down_distance="third_medium",
                ),
            ],
            down=3,
            distance=6,
            field_zone="open_field",
            coverage_id="cover1",
            pressure_id="nickel_blitz",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        answer = next(play for play in recommendations if play["play_id"] == "stick_answer")
        self.assertEqual(ids(recommendations)[:2], ["stick_answer", "generic"])
        self.assertTrue(any("exact match nickel_blitz" in reason for reason in answer["reasons"]))

    def test_rb_screen_gets_inside_blitz_pressure_bonus(self) -> None:
        scored = self.score(
            make_play(
                play_id="rb_screen",
                pass_concept="rb_screen",
                protection="screen",
                beats_pressure="any_pressure;inside_blitz;double_a_gap;zero_pressure",
                tags="screen;quick_game;hot_answer",
                preferred_down_distance="third_long",
            ),
            down=3,
            distance=9,
            field_zone="open_field",
            pressure_id="inside_blitz",
            coverage_id="cover1",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        text = " ".join(scored["reasons"])
        self.assertIn("exact match inside_blitz", text)
        self.assertIn("screen is useful against pressure", text)

    def test_pressure_beaters_do_not_get_free_points_when_pressure_is_none(self) -> None:
        with_pressure = self.score(
            make_play(
                play_id="quick",
                pass_concept="stick",
                protection="quick",
                beats_pressure="edge_blitz;field_blitz;nickel_blitz;sim_pressure",
                tags="quick_game;hot_answer",
                preferred_down_distance="third_medium",
            ),
            down=3,
            distance=6,
            pressure_id="nickel_blitz",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        no_pressure = self.score(
            make_play(
                play_id="quick",
                pass_concept="stick",
                protection="quick",
                beats_pressure="edge_blitz;field_blitz;nickel_blitz;sim_pressure",
                tags="quick_game;hot_answer",
                preferred_down_distance="third_medium",
            ),
            down=3,
            distance=6,
            pressure_id="none",
            coverage_id="cover3",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        self.assertGreater(with_pressure["score"], no_pressure["score"])
        self.assertFalse(any("pressure:" in reason for reason in no_pressure["reasons"]))

    def test_pressure_penalizes_slow_play_action_vs_quick_answer(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="slow_pa",
                    pass_concept="dagger",
                    play_action="true",
                    protection="6man",
                    beats_pressure="none",
                    preferred_down_distance="third_long",
                    tags="deep_shot;play_action",
                ),
                make_play(
                    play_id="quick_answer",
                    pass_concept="stick",
                    protection="quick",
                    beats_pressure="edge_blitz;field_blitz;nickel_blitz;sim_pressure",
                    preferred_down_distance="third_medium",
                    tags="quick_game;hot_answer",
                ),
            ],
            down=3,
            distance=8,
            field_zone="open_field",
            coverage_id="cover1",
            pressure_id="sim_pressure",
            front_id="even",
            box_count=6,
            personnel="10",
        )
        slow = next(play for play in recommendations if play["play_id"] == "slow_pa")
        self.assertEqual(ids(recommendations)[:2], ["quick_answer", "slow_pa"])
        self.assertTrue(any("play_action is risky against pressure" in reason for reason in slow["reasons"]))


if __name__ == "__main__":
    unittest.main()
