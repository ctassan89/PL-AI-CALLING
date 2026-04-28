"""Tests for the rule-based recommendation engine."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from recommendation.engine import build_situation, recommend_plays, score_play


def make_playbook() -> pd.DataFrame:
    """Build a small synthetic playbook using the current project schema."""
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
            "preferred_field_zone": "midfield;opp_territory",
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
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "midfield;opp_territory",
        },
        {
            "play_id": "curl_flat",
            "play_name": "Curl Flat",
            "play_family": "quick_game",
            "play_type": "pass",
            "run_scheme": "none",
            "run_modifier": "none",
            "pass_concept": "curl_flat",
            "pass_modifier": "none",
            "rpo_tag": "none",
            "play_action": "false",
            "formation_id": "gun_11_2x2",
            "personnel": "11",
            "beats_front": "none",
            "beats_coverage": "cover3;cover4_quarters",
            "beats_box": "any",
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "any",
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
            "preferred_down_distance": "medium;long",
            "preferred_field_zone": "midfield;opp_territory",
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
            "beats_coverage": "cover2",
            "beats_box": "any",
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "any",
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
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "any",
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
            "preferred_down_distance": "short;medium",
            "preferred_field_zone": "midfield;opp_territory",
        },
    ]
    return pd.DataFrame(rows)


class RecommendationEngineTests(unittest.TestCase):
    """Exercise the existing if/then style recommendation rules."""

    def test_cover3_favors_cover3_answers_present_in_playbook(self) -> None:
        playbook = make_playbook()
        situation = build_situation(
            down=2,
            distance="medium",
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover3",
            box_count=6,
        )

        recommendations = recommend_plays(playbook, situation, limit=4)
        top_ids = {play["play_id"] for play in recommendations[:4]}

        self.assertTrue({"flood", "curl_flat", "verts"} <= top_ids)
        self.assertNotIn("mesh", top_ids)

    def test_heavy_box_reduces_pure_run_recommendations(self) -> None:
        playbook = make_playbook()
        heavy_box = build_situation(
            down=2,
            distance="short",
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="odd_tite",
            coverage_id="cover3",
            box_count=8,
        )

        run_score, _ = score_play(
            playbook.loc[playbook["play_id"] == "inside_zone"].iloc[0], heavy_box
        )
        pass_score, _ = score_play(
            playbook.loc[playbook["play_id"] == "curl_flat"].iloc[0], heavy_box
        )

        self.assertLess(run_score, pass_score)

    def test_light_box_increases_run_recommendations(self) -> None:
        playbook = make_playbook()
        light_box = build_situation(
            down=2,
            distance="short",
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover2",
            box_count=5,
        )

        run_score, _ = score_play(
            playbook.loc[playbook["play_id"] == "inside_zone"].iloc[0], light_box
        )
        pass_score, _ = score_play(
            playbook.loc[playbook["play_id"] == "mesh"].iloc[0], light_box
        )

        self.assertGreater(run_score, pass_score)

    def test_pressure_tendencies_boost_quick_answers(self) -> None:
        playbook = make_playbook()
        situation = build_situation(
            down=3,
            distance="medium",
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover2",
            box_count=6,
        )

        base = recommend_plays(playbook, situation, limit=7)
        adjusted = recommend_plays(
            playbook,
            situation,
            tendencies={"pressure": {"yes": 0.9, "no": 0.1}},
            limit=7,
        )

        base_scores = {play["play_id"]: play["score"] for play in base}
        adjusted_scores = {play["play_id"]: play["score"] for play in adjusted}
        base_order = [play["play_id"] for play in base]
        adjusted_order = [play["play_id"] for play in adjusted]

        self.assertLess(adjusted_order.index("screen"), base_order.index("screen"))
        self.assertGreater(adjusted_scores["screen"], base_scores["screen"])
        self.assertGreater(adjusted_scores["rpo"], base_scores["rpo"])

    def test_recommendations_only_return_existing_playbook_plays(self) -> None:
        playbook = make_playbook()
        situation = build_situation(
            down=1,
            distance="medium",
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_4",
            coverage_id="cover3",
            box_count=6,
        )

        recommendations = recommend_plays(playbook, situation, limit=5)
        play_ids = set(playbook["play_id"])

        self.assertTrue(recommendations)
        self.assertTrue({play["play_id"] for play in recommendations} <= play_ids)


if __name__ == "__main__":
    unittest.main()
