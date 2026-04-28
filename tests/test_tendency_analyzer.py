"""Tests for opponent tendency analysis and integration."""

from __future__ import annotations

import unittest
import sys
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
    """Build a small playbook that can shift with opponent tendencies."""
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
                "preferred_down_distance": "short;medium",
                "preferred_field_zone": "midfield",
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
                "preferred_field_zone": "midfield",
            },
        ]
    )


class OpponentTendencyTests(unittest.TestCase):
    """Validate CSV loading, aggregation, and score adjustment integration."""

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

    def test_tendency_adjusted_recommendations_change_same_situation_ranking(
        self,
    ) -> None:
        playbook = make_playbook()
        situation = build_situation(
            down=2,
            distance="short",
            field_zone="midfield",
            formation_id="gun_11_2x2",
            front_id="odd_tite",
            coverage_id="cover2",
            box_count=6,
            opponent="rhinos",
            personnel="11",
        )

        base = recommend_plays(playbook, situation, limit=3)

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
        adjusted = recommend_plays(playbook, situation, tendencies=tendencies, limit=3)

        self.assertEqual(base[0]["play_id"], "inside_zone")
        self.assertNotEqual(adjusted[0]["play_id"], base[0]["play_id"])
        self.assertIn(adjusted[0]["play_id"], {"flood", "screen"})


if __name__ == "__main__":
    unittest.main()
