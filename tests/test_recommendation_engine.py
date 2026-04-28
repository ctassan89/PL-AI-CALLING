"""Tests for football-realistic recommendation scoring."""

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


def make_playbook() -> pd.DataFrame:
    """Build a synthetic playbook with explicit semantic tags."""
    rows = [
        {
            "play_id": "inside_zone",
            "play_name": "Inside Zone",
            "play_family": "run",
            "play_type": "run",
            "run_scheme": "inside_zone",
            "run_modifier": "none",
            "pass_concept": "none",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "even_4;odd_3",
            "beats_coverage": "any",
            "beats_box": "light_box;neutral_box",
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "own_territory;midfield",
            "tags": "pure_run;inside_run",
        },
        {
            "play_id": "duo",
            "play_name": "Duo",
            "play_family": "run",
            "play_type": "run",
            "run_scheme": "duo",
            "run_modifier": "none",
            "pass_concept": "none",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "even_4;odd_tite",
            "beats_coverage": "any",
            "beats_box": "neutral_box;heavy_box",
            "preferred_down_distance": "short",
            "preferred_field_zone": "redzone;goal_line",
            "tags": "pure_run;inside_run;short_yardage;goal_line;red_zone",
        },
        {
            "play_id": "draw",
            "play_name": "RB Draw",
            "play_family": "run",
            "play_type": "run",
            "run_scheme": "draw",
            "run_modifier": "none",
            "pass_concept": "none",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "odd_mint;even_over",
            "beats_coverage": "any",
            "beats_box": "light_box",
            "preferred_down_distance": "long;xlong",
            "preferred_field_zone": "midfield;opp_territory",
            "tags": "pure_run;draw;safe_call",
        },
        {
            "play_id": "slant_flat",
            "play_name": "Slant Flat",
            "play_family": "quick_game",
            "play_type": "pass",
            "run_scheme": "none",
            "run_modifier": "none",
            "pass_concept": "slant_flat",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "none",
            "beats_coverage": "cover3;cover1",
            "beats_box": "any",
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "any",
            "tags": "quick_game;pressure_answer;safe_call;red_zone;goal_line",
        },
        {
            "play_id": "mesh",
            "play_name": "Mesh",
            "play_family": "dropback",
            "play_type": "pass",
            "run_scheme": "none",
            "run_modifier": "none",
            "pass_concept": "mesh",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "none",
            "beats_coverage": "cover1;cover2",
            "beats_box": "any",
            "preferred_down_distance": "medium;long;xlong",
            "preferred_field_zone": "midfield;opp_territory",
            "tags": "attacks_sticks",
        },
        {
            "play_id": "flood",
            "play_name": "Boot Flood",
            "play_family": "boot",
            "play_type": "pass",
            "run_scheme": "outside_zone",
            "run_modifier": "none",
            "pass_concept": "flood",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "true",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "even_4;odd_3",
            "beats_coverage": "cover3;cover1",
            "beats_box": "neutral_box;heavy_box",
            "preferred_down_distance": "medium;long;xlong",
            "preferred_field_zone": "midfield;opp_territory;redzone",
            "tags": "play_action;boot;attacks_sticks;red_zone",
        },
        {
            "play_id": "verts",
            "play_name": "Four Verts",
            "play_family": "dropback",
            "play_type": "pass",
            "run_scheme": "none",
            "run_modifier": "none",
            "pass_concept": "four_verts",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "none",
            "beats_coverage": "cover3;cover4_quarters",
            "beats_box": "any",
            "preferred_down_distance": "long;xlong",
            "preferred_field_zone": "midfield;opp_territory",
            "tags": "shot;vertical;slow_developing;attacks_sticks",
        },
        {
            "play_id": "screen",
            "play_name": "Now Screen",
            "play_family": "screen",
            "play_type": "screen",
            "run_scheme": "none",
            "run_modifier": "none",
            "pass_concept": "screens",
            "pass_modifier": "now_screen",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "none",
            "beats_coverage": "cover3",
            "beats_box": "any",
            "preferred_down_distance": "medium;long;xlong",
            "preferred_field_zone": "any",
            "tags": "screen;pressure_answer;safe_call",
        },
        {
            "play_id": "rpo",
            "play_name": "Glance RPO",
            "play_family": "rpo",
            "play_type": "rpo",
            "run_scheme": "inside_zone",
            "run_modifier": "none",
            "pass_concept": "none",
            "pass_modifier": "none",
            "rpo_tag": "glance",
            "play_action": "true",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "odd_tite;odd_3",
            "beats_coverage": "cover3;cover1",
            "beats_box": "heavy_box",
            "preferred_down_distance": "short;medium;long",
            "preferred_field_zone": "midfield;opp_territory;redzone",
            "tags": "rpo;pressure_answer;short_yardage;red_zone",
        },
    ]
    return pd.DataFrame(rows)


def ids(recommendations: list[dict[str, object]]) -> list[str]:
    """Extract ordered play IDs."""
    return [str(play["play_id"]) for play in recommendations]


class RecommendationEngineTests(unittest.TestCase):
    """Exercise the redesigned football scoring rules."""

    def setUp(self) -> None:
        self.playbook = make_playbook()

    def recommend(self, **kwargs: object) -> list[dict[str, object]]:
        situation = build_situation(
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover3",
            box_count=6,
            **kwargs,
        )
        return recommend_plays(self.playbook, situation, limit=10)

    def score(self, play_id: str, **kwargs: object) -> tuple[float, list[str]]:
        situation = build_situation(
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover3",
            box_count=6,
            **kwargs,
        )
        play = self.playbook.loc[self.playbook["play_id"] == play_id].iloc[0]
        return score_play(play, situation)

    def test_first_and_ten_allows_balanced_run_and_pass(self) -> None:
        recommendations = self.recommend(down=1, distance=10, field_zone="own_territory")
        top_four = ids(recommendations[:4])
        self.assertIn("inside_zone", top_four)
        self.assertTrue({"slant_flat", "rpo"} & set(top_four))

    def test_second_and_short_allows_aggressive_play_action(self) -> None:
        recommendations = self.recommend(down=2, distance=2, field_zone="opp_territory")
        top_three = ids(recommendations[:3])
        self.assertIn("flood", top_three)

    def test_second_and_medium_stays_balanced(self) -> None:
        recommendations = self.recommend(down=2, distance=5, field_zone="midfield")
        top_five = set(ids(recommendations[:5]))
        self.assertIn("inside_zone", top_five)
        self.assertTrue({"slant_flat", "mesh", "rpo"} & top_five)

    def test_second_and_long_prefers_efficient_answers_over_pure_run(self) -> None:
        recommendations = self.recommend(down=2, distance=8, field_zone="midfield")
        order = ids(recommendations)
        self.assertLess(order.index("screen"), order.index("inside_zone"))
        self.assertLess(order.index("mesh"), order.index("inside_zone"))

    def test_third_and_short_favors_short_yardage_and_quick_game(self) -> None:
        recommendations = self.recommend(down=3, distance=1, field_zone="midfield")
        top_four = set(ids(recommendations[:4]))
        self.assertIn("duo", top_four)
        self.assertTrue({"slant_flat", "rpo"} & top_four)
        self.assertNotEqual(ids(recommendations)[0], "verts")

    def test_third_and_medium_favors_conversion_concepts(self) -> None:
        recommendations = recommend_plays(
            self.playbook,
            build_situation(
                down=3,
                distance=5,
                field_zone="midfield",
                formation_id="gun_11_2x2",
                front_id="even_4",
                coverage_id="cover2",
                box_count=6,
            ),
            limit=10,
        )
        top_four = set(ids(recommendations[:4]))
        self.assertIn("mesh", top_four)
        self.assertTrue({"slant_flat", "rpo", "screen"} & top_four)
        self.assertGreater(
            recommendations[ids(recommendations).index("mesh")]["score"],
            recommendations[ids(recommendations).index("inside_zone")]["score"],
        )

    def test_third_and_long_keeps_pass_concepts_above_pure_runs(self) -> None:
        recommendations = self.recommend(down=3, distance=9, field_zone="midfield")
        order = ids(recommendations)
        self.assertLess(order.index("mesh"), order.index("inside_zone"))
        self.assertLess(order.index("flood"), order.index("inside_zone"))

    def test_third_and_very_long_heavily_penalizes_pure_runs(self) -> None:
        recommendations = self.recommend(down=3, distance=15, field_zone="midfield")
        order = ids(recommendations)
        inside_zone = next(play for play in recommendations if play["play_id"] == "inside_zone")
        self.assertNotIn("inside_zone", ids(recommendations[:3]))
        self.assertLess(order.index("screen"), order.index("inside_zone"))
        self.assertLess(inside_zone["score"], 0)
        self.assertTrue(
            any("pure run on 3rd/4th & very long" in reason for reason in inside_zone["reasons"])
        )

    def test_backed_up_boosts_safe_calls_and_penalizes_risky_shots(self) -> None:
        recommendations = self.recommend(down=2, distance=8, field_zone="own_redzone")
        order = ids(recommendations)
        self.assertLess(order.index("screen"), order.index("verts"))
        self.assertLess(order.index("slant_flat"), order.index("verts"))

    def test_red_zone_penalizes_deep_space_concepts(self) -> None:
        recommendations = self.recommend(down=2, distance=6, field_zone="redzone")
        order = ids(recommendations)
        self.assertLess(order.index("slant_flat"), order.index("verts"))
        self.assertLess(order.index("duo"), order.index("verts"))

    def test_goal_line_prioritizes_goal_line_suitable_calls(self) -> None:
        recommendations = self.recommend(down=3, distance=1, field_zone="goal_line")
        top_three = ids(recommendations[:3])
        self.assertIn("duo", top_three)
        self.assertNotEqual(ids(recommendations)[0], "verts")

    def test_light_box_boosts_run_only_when_situation_allows_it(self) -> None:
        first_and_ten = build_situation(
            down=1,
            distance=10,
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover3",
            box_count=5,
        )
        third_and_fifteen = build_situation(
            down=3,
            distance=15,
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover3",
            box_count=5,
        )
        run_play = self.playbook.loc[self.playbook["play_id"] == "inside_zone"].iloc[0]
        first_score, _ = score_play(run_play, first_and_ten)
        third_score, _ = score_play(run_play, third_and_fifteen)

        self.assertGreater(first_score, third_score)
        self.assertNotIn(
            "inside_zone",
            ids(recommend_plays(self.playbook, third_and_fifteen, limit=3)),
        )

    def test_heavy_box_penalizes_pure_run_and_boosts_rpo(self) -> None:
        recommendations = recommend_plays(
            self.playbook,
            build_situation(
                down=2,
                distance=5,
                field_zone="midfield",
                formation_id="gun_11_2x2",
                front_id="odd_tite",
                coverage_id="cover3",
                box_count=8,
            ),
            limit=10,
        )
        order = ids(recommendations)
        self.assertLess(order.index("rpo"), order.index("inside_zone"))

    def test_cover3_boosts_cover3_beaters_without_breaking_third_and_fifteen(self) -> None:
        recommendations = recommend_plays(
            self.playbook,
            build_situation(
                down=3,
                distance=15,
                field_zone="midfield",
                formation_id="gun_11_2x2",
                front_id="even_4",
                coverage_id="cover3",
                box_count=5,
            ),
            limit=10,
        )
        top_four = set(ids(recommendations[:4]))
        self.assertTrue({"flood", "screen", "verts", "slant_flat"} & top_four)
        self.assertNotIn("inside_zone", ids(recommendations[:3]))

    def test_pressure_tendency_boosts_quick_answers(self) -> None:
        situation = build_situation(
            down=3,
            distance=9,
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover2",
            box_count=6,
        )
        base = recommend_plays(self.playbook, situation, limit=10)
        adjusted = recommend_plays(
            self.playbook,
            situation,
            tendencies={"pressure": {"yes": 0.9, "no": 0.1}},
            limit=10,
        )
        base_scores = {play["play_id"]: play["score"] for play in base}
        adjusted_scores = {play["play_id"]: play["score"] for play in adjusted}
        self.assertGreater(adjusted_scores["screen"], base_scores["screen"])
        self.assertGreater(adjusted_scores["rpo"], base_scores["rpo"])
        self.assertLess(adjusted_scores["verts"], base_scores["verts"])

    def test_recommendations_only_return_existing_playbook_plays(self) -> None:
        recommendations = self.recommend(down=1, distance=10, field_zone="midfield")
        play_ids = set(self.playbook["play_id"])
        self.assertTrue({play["play_id"] for play in recommendations} <= play_ids)


if __name__ == "__main__":
    unittest.main()
