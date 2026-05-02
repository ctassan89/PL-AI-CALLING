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
        self.assertTrue(any("coverage: family match via zone" in reason for reason in generic["reasons"]))

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
        self.assertTrue(any("coverage: family match via zone" in reason for reason in zone["reasons"]))
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


if __name__ == "__main__":
    unittest.main()
