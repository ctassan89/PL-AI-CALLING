"""Tests for opponent tendency analysis and integration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from opponent.tendencies import OpponentTendencyAnalyzer, load_opponent_tendencies
from recommendation.engine import build_situation, recommend_plays


SAMPLE_TENDENCIES_PATH = PROJECT_ROOT / "data" / "opponent_tendencies.csv"


def make_playbook() -> pd.DataFrame:
    """Build a small playbook that can react to opponent tendencies."""
    return pd.DataFrame(
        [
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
                "beats_front": "even_4;odd_tite",
                "beats_coverage": "cover4_quarters",
                "beats_box": "light_box;neutral_box",
                "preferred_down_distance": "short;medium",
                "preferred_field_zone": "midfield",
                "tags": "pure_run;inside_run",
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
                "beats_front": "odd_tite",
                "beats_coverage": "cover3",
                "beats_box": "heavy_box",
                "preferred_down_distance": "short;medium;long;xlong",
                "preferred_field_zone": "midfield;opp_territory",
                "tags": "play_action;boot;attacks_sticks",
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
        ]
    )


class OpponentTendencyTests(unittest.TestCase):
    """Validate CSV loading, aggregation, and logical tendency integration."""

    def test_load_opponent_tendencies_normalizes_required_columns(self) -> None:
        tendencies = load_opponent_tendencies(SAMPLE_TENDENCIES_PATH)

        self.assertFalse(tendencies.empty)
        self.assertTrue(
            {
                "opponent",
                "down",
                "distance_bucket",
                "field_zone",
                "personnel",
                "def_front",
                "box_count",
                "coverage",
                "pressure",
                "play_result",
            }
            <= set(tendencies.columns)
        )
        self.assertEqual(tendencies.loc[0, "opponent"], "rhinos")
        self.assertEqual(tendencies.loc[0, "pressure"], "no")
        self.assertEqual(tendencies.loc[1, "pressure"], "yes")
        self.assertEqual(tendencies.loc[8, "distance_bucket"], "very_long")

    def test_analyzer_returns_expected_probabilities_for_exact_situation(self) -> None:
        analyzer = OpponentTendencyAnalyzer.from_csv(SAMPLE_TENDENCIES_PATH)
        result = analyzer.lookup(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "midfield",
                "personnel": "11",
            }
        )

        self.assertAlmostEqual(result["coverage"]["cover3"], 2 / 3)
        self.assertAlmostEqual(result["coverage"]["cover1"], 1 / 3)
        self.assertEqual(result["pressure"]["yes"], 1.0)
        self.assertAlmostEqual(result["box_count"]["8"], 2 / 3)
        self.assertEqual(result["def_front"]["odd_tite"], 1.0)

    def test_same_situation_changes_ranking_when_tendencies_are_added(self) -> None:
        playbook = make_playbook()
        situation = build_situation(
            down=2,
            distance=2,
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="odd_tite",
            coverage_id="cover2",
            box_count=6,
            opponent="rhinos",
            personnel="11",
        )

        base = recommend_plays(playbook, situation, limit=4)
        analyzer = OpponentTendencyAnalyzer.from_csv(SAMPLE_TENDENCIES_PATH)
        tendencies = analyzer.lookup(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "midfield",
                "personnel": "11",
            }
        )
        adjusted = recommend_plays(playbook, situation, tendencies=tendencies, limit=4)

        self.assertNotEqual(base[0]["play_id"], adjusted[0]["play_id"])
        self.assertIn(adjusted[0]["play_id"], {"flood", "screen"})

    def test_tendencies_cannot_make_inside_zone_top_call_on_third_and_fifteen(self) -> None:
        playbook = make_playbook()
        situation = build_situation(
            down=3,
            distance=15,
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="even_over",
            coverage_id="cover3",
            box_count=5,
            opponent="rhinos",
            personnel="11",
        )
        analyzer = OpponentTendencyAnalyzer.from_csv(SAMPLE_TENDENCIES_PATH)
        tendencies = analyzer.lookup(
            {
                "opponent": "rhinos",
                "down": 3,
                "distance_bucket": "very_long",
                "field_zone": "midfield",
                "personnel": "11",
            }
        )
        recommendations = recommend_plays(
            playbook, situation, tendencies=tendencies, limit=4
        )

        top_ids = [play["play_id"] for play in recommendations[:3]]
        inside_zone = next(play for play in recommendations if play["play_id"] == "inside_zone")

        self.assertNotIn("inside_zone", top_ids)
        self.assertGreaterEqual(inside_zone["score"], 0)
        self.assertLess(
            inside_zone["score"],
            next(play for play in recommendations if play["play_id"] == "screen")["score"],
        )
        self.assertTrue(
            any(
                "third_long" in reason or "light box profile improves inside runs" in reason
                for reason in inside_zone["reasons"]
            )
        )


if __name__ == "__main__":
    unittest.main()
