"""리트리버 베이스 테스트.

"오늘의 룩", "옷장 기반", "추구미 기반" 세 기능이 전부 이 계층 위에 올라가므로,
여기서 조용히 틀리면 세 곳에서 동시에 틀린다. 특히 두 가지를 붙잡아 둔다.

- 어휘 번역이 값을 조용히 버리지 않는가 (넥라인처럼 대응 태그가 없는 축)
- 취향이 체형 규칙보다 항상 우선하는가 (가이드 7장 Q2)
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from apps.recommend.services import vocabulary
from apps.recommend.services.body_profile import (
    HOURGLASS,
    INVERTED_TRIANGLE,
    NORMAL,
    OBESE,
    OVERWEIGHT,
    RECTANGLE,
    ROUND,
    TRIANGLE,
    UNDERWEIGHT,
    UNKNOWN,
    BodyProfile,
    build_profile,
)
from apps.recommend.services.retriever import (
    Reason,
    _score_items,
    _season_from_weather,
)
from apps.recommend.services.style_rules import (
    RULES_DIR,
    Rule,
    load_body_rules,
    validate_rules,
)

translate = vocabulary.translate


class BodyProfileTests(unittest.TestCase):
    def test_shoulder_wider_than_hip_is_inverted(self):
        p = build_profile({"height":175,"weight":70,"shoulder":48,"hip":42,"waist":34})
        self.assertEqual(p.silhouette, INVERTED_TRIANGLE)
    def test_hip_wider_than_shoulder_is_triangle(self):
        self.assertEqual(build_profile({"shoulder":38,"hip":45,"waist":32}).silhouette, TRIANGLE)
    def test_balanced_with_small_waist_is_hourglass(self):
        self.assertEqual(build_profile({"shoulder":40,"hip":40,"waist":29}).silhouette, HOURGLASS)
    def test_balanced_with_dominant_waist_is_round(self):
        self.assertEqual(build_profile({"shoulder":40,"hip":40,"waist":39}).silhouette, ROUND)
    def test_balanced_middle_waist_is_rectangle(self):
        self.assertEqual(build_profile({"shoulder":40,"hip":40,"waist":34}).silhouette, RECTANGLE)
    def test_balanced_without_waist_stays_unknown(self):
        p = build_profile({"shoulder":40,"hip":40})
        self.assertEqual(p.silhouette, UNKNOWN)
        self.assertIn("waist", p.missing)
    def test_bmi_bands(self):
        for w, band in ((50,UNDERWEIGHT),(62,NORMAL),(70,OVERWEIGHT),(85,OBESE)):
            p = build_profile({"height":170,"weight":w})
            self.assertEqual(p.bmi_band, band, f"{w}kg bmi={p.bmi}")
    def test_no_measurement_is_empty(self):
        self.assertTrue(build_profile(None).is_empty)
        self.assertTrue(build_profile({}).is_empty)
    def test_leg_volume_ratio(self):
        self.assertEqual(build_profile({"thigh":62,"calf":38}).ratios["leg_volume"], "thigh_dominant")
        self.assertEqual(build_profile({"thigh":52,"calf":37}).ratios["leg_volume"], "balanced")
    def test_garbage_values_are_ignored(self):
        self.assertTrue(build_profile({"height":"abc","weight":-5,"shoulder":None}).is_empty)
    def test_describe_is_human_readable(self):
        p = build_profile({"height":170,"weight":85,"shoulder":40,"hip":40,"waist":39})
        self.assertIn("라운드형", p.describe()); self.assertIn("비만", p.describe())

class VocabularyTests(unittest.TestCase):
    def test_maps_to_tag_labels(self):
        t = translate({"top_fits":["oversized"],"styles":["minimal"]})
        self.assertEqual(t.labels("fit"), {"오버핏"}); self.assertEqual(t.labels("style"), {"미니멀"})
    def test_necklines_are_all_unmapped(self):
        t = translate({"necklines":["vneck","turtle"]})
        self.assertEqual(t.tags, {})
        self.assertEqual(set(t.unmapped), {("necklines","vneck"),("necklines","turtle")})
    def test_style_without_tag_equivalent_is_reported(self):
        t = translate({"styles":["business_casual","minimal"]})
        self.assertEqual(t.labels("style"), {"미니멀"})
        self.assertIn(("styles","business_casual"), t.unmapped)
    def test_approximate_is_flagged(self):
        t = translate({"top_fits":["loose"]})
        self.assertEqual(t.labels("fit"), {"오버핏"}); self.assertIn(("top_fits","loose"), t.approximate)
    def test_pants_fits_collapse_to_four_labels(self):
        t = translate({"pants_fits":["wide","semi_wide","slacks","skinny"]})
        self.assertEqual(t.labels("fit"), {"와이드핏","레귤러핏","슬림핏"})
    def test_empty_input(self):
        t = translate(None); self.assertEqual(t.tags, {}); self.assertEqual(t.unmapped, ())

class RulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_body_rules()
    def test_loads_clean(self):
        self.assertEqual(self.rules.schema_version, "body-fit-rules-v1")
    def test_preference_outweighs_rules(self):
        w = self.rules.weights
        self.assertGreater(abs(w.preference_avoid), abs(w.rule_avoid))
        self.assertGreater(w.preference_match, w.rule_prefer)
    def test_typo_in_rules_is_caught(self):
        bad = {"silhouette":{"triangle":{"prefer":[{"fit":"레귤귤핏","reason":"x"}],"avoid":[]}}}
        problems = validate_rules(bad)
        self.assertEqual(len(problems), 1); self.assertIn("레귤귤핏", problems[0])
    def test_unknown_field_is_caught(self):
        bad = {"bmi_band":{"obese":{"prefer":[{"neckline":"브이넥","reason":"x"}],"avoid":[]}}}
        self.assertIn("알 수 없는 태그 필드", validate_rules(bad)[0])
    def test_shipped_rules_have_no_problems(self):
        import json
        doc = json.loads(open(str(RULES_DIR / "body_fit_rules.json"), encoding="utf-8").read())
        self.assertEqual(validate_rules(doc), [])
    def test_unknown_axis_contributes_nothing(self):
        empty = self.rules.for_profile(BodyProfile())
        self.assertEqual(empty.prefer, ()); self.assertEqual(empty.avoid, ())
    def test_hard_rule_flag_survives_parsing(self):
        hard = [r for r in self.rules.for_profile(BodyProfile(silhouette=ROUND)).avoid if r.hard]
        self.assertTrue(hard)
        self.assertEqual(hard[0].match, {"category_large":"상의","length":"크롭"})
    def test_axes_combine(self):
        p = BodyProfile(silhouette=TRIANGLE, bmi_band=OBESE, ratios={"leg_volume":"thigh_dominant"})
        axis = self.rules.for_profile(p)
        self.assertGreater(len(axis.avoid), 3)
    def test_rule_matches_list_payload(self):
        r = Rule(match={"style":"미니멀"}, reason="")
        self.assertTrue(r.matches({"style":["미니멀","시크"]}))
        self.assertFalse(r.matches({"style":["스트릿"]}))

class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_body_rules()
        self.w = self.rules.weights
    def test_avoided_preference_dominates_rule_bonus(self):
        axis = self.rules.for_profile(BodyProfile(silhouette=TRIANGLE))
        total, reasons = _score_items(
            [{"category_large":"상의","fit":"오버핏","color":"핑크"}],
            rules_prefer=axis.prefer, rules_avoid=axis.avoid,
            preferred_tags={}, avoided_tags={"color":{"핑크"}}, weights=self.w)
        self.assertLess(total, 0)
        self.assertTrue(any(r.source == "preference" for r in reasons))
    def test_rule_violation_lowers_score(self):
        axis = self.rules.for_profile(BodyProfile(silhouette=ROUND))
        total, _ = _score_items([{"category_large":"상의","length":"크롭"}],
            rules_prefer=axis.prefer, rules_avoid=axis.avoid,
            preferred_tags={}, avoided_tags={}, weights=self.w)
        self.assertEqual(total, self.w.rule_avoid)
    def test_reason_is_not_repeated(self):
        axis = self.rules.for_profile(BodyProfile(silhouette=TRIANGLE))
        _, reasons = _score_items([{"category_large":"상의","fit":"오버핏"}]*3,
            rules_prefer=axis.prefer, rules_avoid=axis.avoid,
            preferred_tags={}, avoided_tags={}, weights=self.w)
        self.assertEqual(len(reasons), len({r.text for r in reasons}))
    def test_score_still_accumulates_when_reason_deduped(self):
        axis = self.rules.for_profile(BodyProfile(silhouette=TRIANGLE))
        one, _ = _score_items([{"category_large":"상의","fit":"오버핏"}],
            rules_prefer=axis.prefer, rules_avoid=(), preferred_tags={}, avoided_tags={}, weights=self.w)
        three, _ = _score_items([{"category_large":"상의","fit":"오버핏"}]*3,
            rules_prefer=axis.prefer, rules_avoid=(), preferred_tags={}, avoided_tags={}, weights=self.w)
        self.assertEqual(three, one*3)
    def test_empty_profile_scores_nothing(self):
        total, reasons = _score_items([{"category_large":"상의","fit":"슬림핏"}],
            rules_prefer=(), rules_avoid=(), preferred_tags={}, avoided_tags={}, weights=self.w)
        self.assertEqual(total, 0.0); self.assertEqual(reasons, [])

class WeatherTests(unittest.TestCase):
    def test_temperature_to_season(self):
        for t, s in ((28,"여름"),(23,"여름"),(19,"간절기"),(12,"가을"),(3,"겨울"),(-5,"겨울")):
            self.assertEqual(_season_from_weather({"temperature":t}), s, t)
    def test_missing_weather(self):
        self.assertEqual(_season_from_weather(None), "")
        self.assertEqual(_season_from_weather({}), "")
        self.assertEqual(_season_from_weather({"temperature":"n/a"}), "")

