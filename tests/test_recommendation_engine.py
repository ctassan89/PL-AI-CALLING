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
        situation = build_situation(
            down=kwargs.pop("down", 1),
            distance=kwargs.pop("distance", 10),
            field_zone=kwargs.pop("field_zone", "midfield"),
            formation_id=kwargs.pop("formation_id", "gun_11_2x2"),
            front_id=kwargs.pop("front_id", "odd_tite"),
            coverage_id=kwargs.pop("coverage_id", "cover3"),
            box_count=kwargs.pop("box_count", 6),
            personnel=kwargs.pop("personnel", "11"),
        )
        self.assertFalse(kwargs)
        return recommend_plays(pd.DataFrame(plays), situation, top_n=10)

    def score(self, play: dict[str, object], **kwargs: object) -> dict[str, object]:
        situation = build_situation(
            down=kwargs.pop("down", 1),
            distance=kwargs.pop("distance", 10),
            field_zone=kwargs.pop("field_zone", "midfield"),
            formation_id=kwargs.pop("formation_id", "gun_11_2x2"),
            front_id=kwargs.pop("front_id", "odd_tite"),
            coverage_id=kwargs.pop("coverage_id", "cover3"),
            box_count=kwargs.pop("box_count", 6),
            personnel=kwargs.pop("personnel", "11"),
        )
        self.assertFalse(kwargs)
        return score_play(pd.Series(play), situation)

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

    def test_cover3_boosts_flood_or_curl_flat(self) -> None:
        recommendations = self.recommend(
            [
                make_play(
                    play_id="flood",
                    pass_concept="flood",
                    preferred_down_distance="second_medium",
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


if __name__ == "__main__":
    unittest.main()
