"""Tests for opponent tendency analysis and integration."""

from __future__ import annotations

import sys
import tempfile
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


def make_rich_tendency_rows() -> list[dict[str, object]]:
    """Build a tiny rich-schema dataset for explicit personnel tests."""
    base = {
        "team": "Rhinos",
        "game_id": "game",
        "field_zone": "open_field",
        "hash": "middle",
        "offensive_formation_id": "gun_11_2x2",
        "defensive_personnel_id": "nickel",
        "movement_type": "none",
        "success_rate_allowed": 0.45,
        "epa_allowed": -0.01,
        "notes": "sample",
    }
    return [
        {
            **base,
            "game_id": "g1",
            "down": 2,
            "distance": "short",
            "offensive_personnel": "10",
            "front_id": "odd_tite",
            "box_count": 7,
            "coverage_id": "cover3_buzz_field",
            "blitzers": 1,
            "sample_size": 12,
            "frequency": 1.0,
        },
        {
            **base,
            "game_id": "g2",
            "down": 2,
            "distance": "short",
            "offensive_personnel": "11",
            "front_id": "bear",
            "box_count": 8,
            "coverage_id": "cover1_man_free",
            "blitzers": 0,
            "sample_size": 12,
            "frequency": 1.0,
        },
        {
            **base,
            "game_id": "g3",
            "down": 2,
            "distance": "short",
            "offensive_personnel": "11",
            "front_id": "bear",
            "box_count": 8,
            "coverage_id": "cover1_man_free",
            "blitzers": 0,
            "sample_size": 6,
            "frequency": 1.0,
        },
        {
            **base,
            "game_id": "g4",
            "down": 2,
            "distance": "short",
            "offensive_personnel": "12",
            "front_id": "even_over",
            "box_count": 6,
            "coverage_id": "cover2",
            "blitzers": 0,
            "sample_size": 4,
            "frequency": 1.0,
        },
    ]


def write_rich_tendency_csv(rows: list[dict[str, object]]) -> Path:
    """Write a temp rich-schema tendency CSV and return its path."""
    dataframe = pd.DataFrame(rows)
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    path = Path(handle.name)
    handle.close()
    dataframe.to_csv(path, index=False)
    return path


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
        result = analyzer.lookup_with_metadata(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "midfield",
                "personnel": "11",
            }
        )

        self.assertFalse(result["fallback_used"])
        self.assertEqual(
            result["matched_keys"],
            ("opponent", "down", "distance_bucket", "field_zone", "personnel"),
        )
        tendencies = result["tendencies"]
        self.assertEqual(
            set(tendencies["coverage"]),
            {
                "cover3_buzz_field",
                "cover1_man_free",
                "cover1_robber_strong",
                "cover0_pressure",
            },
        )
        self.assertAlmostEqual(tendencies["coverage"]["cover1_man_free"], 4 / 12)
        self.assertAlmostEqual(tendencies["coverage"]["cover3_buzz_field"], 4 / 12)
        self.assertAlmostEqual(tendencies["coverage"]["cover1_robber_strong"], 3 / 12)
        self.assertAlmostEqual(tendencies["coverage"]["cover0_pressure"], 1 / 12)
        self.assertNotIn("cover3", tendencies["coverage"])
        self.assertNotIn("cover1", tendencies["coverage"])
        self.assertAlmostEqual(tendencies["pressure"]["yes"], 1.0)
        self.assertAlmostEqual(tendencies["box_count"]["8"], 7 / 12)
        self.assertAlmostEqual(tendencies["def_front"]["bear"], 4 / 12)

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

        base_by_id = {play["play_id"]: play for play in base}
        adjusted_by_id = {play["play_id"]: play for play in adjusted}

        self.assertTrue(all(play["used_tendencies"] for play in adjusted))
        self.assertTrue(
            any(
                base_by_id[play_id]["score"] != adjusted_by_id[play_id]["score"]
                for play_id in adjusted_by_id
            )
        )

        flood = adjusted_by_id["flood"]
        screen = adjusted_by_id["screen"]
        inside_zone = adjusted_by_id["inside_zone"]

        self.assertLess(flood["score"], base_by_id["flood"]["score"])
        self.assertGreater(screen["score"], base_by_id["screen"]["score"])
        self.assertLess(inside_zone["score"], base_by_id["inside_zone"]["score"])

        self.assertTrue(
            any("tendency: pressure profile hurts slow-developing concepts" in reason for reason in flood["reasons"])
        )
        self.assertTrue(
            any("rerank: play_action is de-emphasized versus likely pressure" in reason for reason in flood["reasons"])
        )
        self.assertTrue(
            any("tendency: pressure profile favors quick answers" in reason for reason in screen["reasons"])
        )
        self.assertTrue(
            any(
                "tendency: heavy box profile hurts inside runs without box fit" in reason
                or "rerank: inside run is de-emphasized when tendency data suggests a loaded box" in reason
                for reason in inside_zone["reasons"]
            )
        )

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

    def test_personnel_buckets_can_return_different_snapshots(self) -> None:
        path = write_rich_tendency_csv(make_rich_tendency_rows())
        self.addCleanup(path.unlink)
        analyzer = OpponentTendencyAnalyzer.from_csv(path)

        ten = analyzer.lookup_with_metadata(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "open_field",
                "personnel": "10",
            }
        )
        eleven = analyzer.lookup_with_metadata(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "open_field",
                "personnel": "11",
            }
        )

        self.assertNotEqual(ten["tendencies"]["coverage"], eleven["tendencies"]["coverage"])
        self.assertEqual(ten["matched_keys"], ("opponent", "down", "distance_bucket", "field_zone", "personnel"))
        self.assertEqual(eleven["matched_keys"], ("opponent", "down", "distance_bucket", "field_zone", "personnel"))

    def test_exact_personnel_rows_are_used_when_present(self) -> None:
        path = write_rich_tendency_csv(make_rich_tendency_rows())
        self.addCleanup(path.unlink)
        analyzer = OpponentTendencyAnalyzer.from_csv(path)

        result = analyzer.lookup_with_metadata(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "open_field",
                "personnel": "11",
            }
        )

        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["matched_row_count"], 2)
        self.assertGreater(result["tendencies"]["coverage"]["cover1_man_free"], 0.99)

    def test_personnel_fallback_is_explicit_when_exact_bucket_missing(self) -> None:
        path = write_rich_tendency_csv(make_rich_tendency_rows())
        self.addCleanup(path.unlink)
        analyzer = OpponentTendencyAnalyzer.from_csv(path)

        result = analyzer.lookup_with_metadata(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "open_field",
                "personnel": "21",
            }
        )

        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["matched_keys"], ("opponent", "down", "distance_bucket", "field_zone"))
        self.assertEqual(result["matched_row_count"], 4)

    def test_lookup_without_personnel_is_not_marked_personnel_specific(self) -> None:
        path = write_rich_tendency_csv(make_rich_tendency_rows())
        self.addCleanup(path.unlink)
        analyzer = OpponentTendencyAnalyzer.from_csv(path)

        result = analyzer.lookup_with_metadata(
            {
                "opponent": "rhinos",
                "down": 2,
                "distance_bucket": "short",
                "field_zone": "open_field",
            }
        )

        self.assertFalse(result["fallback_used"])
        self.assertNotIn("personnel", result["matched_keys"])
        self.assertEqual(result["matched_keys"], ("opponent", "down", "distance_bucket", "field_zone"))


if __name__ == "__main__":
    unittest.main()
