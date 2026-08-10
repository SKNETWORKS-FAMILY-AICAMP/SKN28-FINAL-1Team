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
from apps.recommend.services.gender import (
    allowed_presentation_groups,
    normalize_gender,
)
from apps.recommend.services.retriever import (
    Reason,
    _score_context,
    _score_items,
    _score_weather,
    _season_from_weather,
    celsius_of,
)
from apps.recommend.services.style_rules import (
    RULES_DIR,
    Rule,
    load_body_rules,
    load_weather_rules,
    validate_rules,
    validate_weather_rules,
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



#: 지금 실제로 적재된 골든 코디의 모양. 분석 단계(analyses.jsonl)를 돌리지 않아
#: style/season/occasion이 전부 빈 배열이다.
UNTAGGED_OUTFIT = {
    "golden_id": "095",
    "style": [],
    "season": [],
    "occasion": [],
    "items": [{"category_large": "상의", "fit": "레귤러핏", "color": "화이트"}],
}
TAGGED_OUTFIT = dict(UNTAGGED_OUTFIT, season=["여름"], occasion=["출근"])


class ContextScoringTests(unittest.TestCase):
    """계절·상황은 가산이지 탈락 조건이 아니다.

    처음엔 날씨에서 뽑은 계절을 Qdrant의 must 조건으로 걸었다. 그러자 모든 추천이
    EMPTY로 끝났다 — 적재된 코디의 season이 전부 빈 배열이라 한 건도 안 걸린
    것이다. 있지도 않은 값에 must를 걸면 결과는 언제나 0건이다.
    """

    def setUp(self) -> None:
        self.weights = load_body_rules().weights

    def test_empty_season_is_neither_bonus_nor_penalty(self) -> None:
        total, reasons = _score_context(
            UNTAGGED_OUTFIT, season="여름", occasion="", weights=self.weights
        )
        self.assertEqual(total, 0.0)
        self.assertEqual(reasons, [])

    def test_matching_season_adds_bonus(self) -> None:
        total, reasons = _score_context(
            TAGGED_OUTFIT, season="여름", occasion="", weights=self.weights
        )
        self.assertEqual(total, self.weights.context_match)
        self.assertEqual(reasons[0].source, "context")

    def test_mismatching_season_is_not_penalised(self) -> None:
        """'안 맞음'을 감점하면 태그가 있는 코디가 없는 코디보다 불리해진다."""
        total, _ = _score_context(
            TAGGED_OUTFIT, season="겨울", occasion="", weights=self.weights
        )
        self.assertEqual(total, 0.0)

    def test_occasion_also_adds(self) -> None:
        total, _ = _score_context(
            TAGGED_OUTFIT, season="여름", occasion="출근", weights=self.weights
        )
        self.assertEqual(total, self.weights.context_match * 2)

    def test_context_never_outweighs_preference(self) -> None:
        """계절이 맞는다고 사용자가 기피한 항목을 이기면 안 된다 (가이드 Q2)."""
        self.assertLess(self.weights.context_match, abs(self.weights.preference_avoid))
        self.assertLess(self.weights.context_match, self.weights.preference_match)
        self.assertLessEqual(self.weights.context_match, self.weights.rule_prefer)

    def test_hard_season_filter_would_have_dropped_everything(self) -> None:
        """회귀 재현 — EMPTY의 정체."""
        points = [UNTAGGED_OUTFIT, dict(UNTAGGED_OUTFIT, golden_id="096")]
        survived = [p for p in points if "여름" in (p.get("season") or [])]
        self.assertEqual(survived, [], "must 조건이면 전부 탈락한다")
        # 소프트로 바꾼 뒤에는 전부 살아남고 가산만 0이다
        deltas = [
            _score_context(p, season="여름", occasion="", weights=self.weights)[0]
            for p in points
        ]
        self.assertEqual(deltas, [0.0, 0.0])


class BuildFilterTests(unittest.TestCase):
    """검색 필터에는 기피 요건만 들어간다 (가이드 6장)."""

    def test_weather_does_not_become_a_filter(self) -> None:
        from apps.recommend.services.retriever import RetrievalRequest, build_filter

        built = build_filter(RetrievalRequest(weather={"temperature": 28}))
        self.assertIsNone(built, "날씨만으로는 어떤 조건도 걸리지 않아야 한다")

    def test_occasion_does_not_become_a_filter(self) -> None:
        from apps.recommend.services.retriever import RetrievalRequest, build_filter

        self.assertIsNone(build_filter(RetrievalRequest(occasion="출근")))

    def test_avoided_style_becomes_must_not(self) -> None:
        from apps.recommend.services.retriever import RetrievalRequest, build_filter

        built = build_filter(
            RetrievalRequest(pursuit={"preferred": {}, "avoided": {"styles": ["street"]}})
        )
        self.assertIsNotNone(built)
        self.assertTrue(built.must_not)
        self.assertFalse(built.must)


OUTER = {"category_large": "아우터", "material": "코튼"}
SHORT_TEE = {"category_large": "상의", "sleeve": "반팔", "material": "코튼"}
KNIT_TOP = {"category_large": "상의", "sleeve": "긴팔", "material": "니트"}


class WeatherRuleTests(unittest.TestCase):
    """기온을 선택에 반영한다.

    실제 사고: 27도인데 아우터가 든 코디가 1위로 뽑혔고, LLM은 그걸 정당화하려고
    "선선한 날씨"라고 썼다. 모델이 온도를 잘못 읽은 게 아니라 모순을 봉합한
    것이다. 근본 원인은 기온이 선택에 전혀 관여하지 않았다는 것이었다.
    """

    def setUp(self) -> None:
        self.rules = load_weather_rules()
        self.weights = self.rules.weights

    def test_shipped_rules_validate(self) -> None:
        document = json.loads(
            (RULES_DIR / "weather_rules.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_weather_rules(document), [])

    def test_band_boundaries(self) -> None:
        for celsius, label in (
            (27, "더움"), (23, "더움"), (22.9, "선선"), (17, "선선"),
            (16.9, "쌀쌀"), (9, "쌀쌀"), (8.9, "추움"), (-10, "추움"),
        ):
            self.assertEqual(self.rules.band_for(celsius).label, label, f"{celsius}도")

    def test_unknown_temperature_disables_the_rules(self) -> None:
        self.assertIsNone(self.rules.band_for(None))
        self.assertEqual(_score_weather([OUTER], None, self.weights), (0.0, []))

    def test_outer_at_27_is_penalised(self) -> None:
        band = self.rules.band_for(27.4)
        total, reasons = _score_weather([OUTER, SHORT_TEE], band, self.weights)
        self.assertLess(total, 0)
        self.assertTrue(any(r.source == "weather" for r in reasons))
        self.assertTrue(any("겉옷" in r.text for r in reasons))

    def test_outer_when_cool_is_rewarded(self) -> None:
        total, _ = _score_weather([OUTER], self.rules.band_for(12), self.weights)
        self.assertEqual(total, self.weights.encourage)

    def test_knit_flips_with_temperature(self) -> None:
        self.assertLess(
            _score_weather([KNIT_TOP], self.rules.band_for(28), self.weights)[0], 0
        )
        self.assertGreater(
            _score_weather([KNIT_TOP], self.rules.band_for(12), self.weights)[0], 0
        )

    def test_reason_not_repeated_across_items(self) -> None:
        band = self.rules.band_for(27.4)
        _, reasons = _score_weather([OUTER] * 3, band, self.weights)
        self.assertEqual(len(reasons), len({r.text for r in reasons}))

    def test_penalty_is_weaker_than_user_avoidance(self) -> None:
        """사용자가 직접 고른 기피가 날씨 추정보다 우선이어야 한다 (가이드 Q2)."""
        self.assertLess(
            abs(self.weights.discourage), abs(load_body_rules().weights.preference_avoid)
        )

    def test_gap_between_bands_is_reported(self) -> None:
        """구간 사이에 구멍이 있으면 그 기온에서 규칙이 통째로 빠진다."""
        bad = {"bands": [{"label": "a", "min": 20, "max": 25}, {"label": "b", "min": 30}]}
        self.assertTrue(any("틈" in p for p in validate_weather_rules(bad)))

    def test_unbounded_band_is_reported(self) -> None:
        self.assertTrue(
            any("모든 기온" in p for p in validate_weather_rules({"bands": [{"label": "x"}]}))
        )


class CelsiusTests(unittest.TestCase):
    def test_parses_number_and_string(self) -> None:
        self.assertEqual(celsius_of({"temperature": 27.4}), 27.4)
        self.assertEqual(celsius_of({"temperature": "27.4"}), 27.4)

    def test_missing_or_garbage_is_none(self) -> None:
        for value in (None, {}, {"temperature": None}, {"temperature": "n/a"}):
            self.assertIsNone(celsius_of(value))


class GenderHardFilterTests(unittest.TestCase):
    """성별은 하드 필터다.

    남성 사용자에게 여성 코디를 "순위만 낮춰" 보여주는 건 추천이 아니라
    오작동으로 읽힌다. 계절·기온과 달리 감점으로 둘 수 없는 축이다.
    """

    def _filter(self, **kwargs):
        from apps.recommend.services.retriever import RetrievalRequest, build_filter

        return build_filter(RetrievalRequest(**kwargs))

    def test_male_user_gets_men_and_unisex(self) -> None:
        built = self._filter(gender="male")
        self.assertIsNotNone(built)
        condition = built.must[0]
        self.assertEqual(condition.key, "presentation_group")
        self.assertEqual(sorted(condition.match.any), ["men", "unisex"])

    def test_female_user_gets_women_and_unisex(self) -> None:
        condition = self._filter(gender="female").must[0]
        self.assertEqual(sorted(condition.match.any), ["unisex", "women"])

    def test_unknown_gender_disables_the_filter(self) -> None:
        """성별 미등록 사용자에게까지 걸면 아무것도 못 본다."""
        for value in ("", "   ", "other"):
            self.assertIsNone(self._filter(gender=value), repr(value))

    def test_case_and_whitespace_tolerated(self) -> None:
        condition = self._filter(gender="  MALE  ").must[0]
        self.assertEqual(sorted(condition.match.any), ["men", "unisex"])

    def test_gender_is_a_must_not_a_penalty(self) -> None:
        """감점 경로로 새면 여성 코디가 순위만 밀린 채 노출된다."""
        built = self._filter(gender="male")
        self.assertTrue(built.must)
        self.assertFalse(built.must_not)


class PresentationGroupNormalizeTests(unittest.TestCase):
    """CSV 표기가 흔들리면 그대로 검색 누락이 된다.

    golden_set 쪽 정규화 함수와 리트리버의 매핑이 같은 어휘를 써야 한다.
    """

    def test_retriever_vocabulary_matches_golden_set(self) -> None:
        from apps.recommend.services.retriever import (
            GENDER_TO_PRESENTATION,
            PRESENTATION_UNISEX,
        )

        self.assertEqual(set(GENDER_TO_PRESENTATION.values()), {"men", "women"})
        self.assertEqual(PRESENTATION_UNISEX, "unisex")

    def test_body_measurement_choices_are_covered(self) -> None:
        """users.BodyMeasurement.Gender의 값이 전부 매핑돼야 한다."""
        from apps.recommend.services.retriever import GENDER_TO_PRESENTATION
        from apps.users.models import BodyMeasurement

        for value in BodyMeasurement.Gender.values:
            self.assertIn(value, GENDER_TO_PRESENTATION, value)


class GenderNormalizationTests(unittest.TestCase):
    """성별 표기 해석은 한 곳에서만 한다.

    이 클래스는 실제로 난 사고의 재발 방지선이다. 83kg 남성 사용자에게 "캉캉
    끈나시 탑"이 추천됐는데, 원인은 검색 로직이 아니라 **값의 배관**이었다:

        BodyMeasurement.gender = ""           (미입력 허용 컬럼)
          → _serialize_measurement 의 `value or None`  → None
          → daily_look 의 `str(...)`                    → "None"
          → GENDER_TO_PRESENTATION.get("none")          → None
          → 성별 하드 필터가 통째로 사라짐 (예외도 로그도 없음)

    필터가 "적용됐는데 틀린" 것이 아니라 "조용히 사라진" 것이라 겉으로는 그냥
    추천이 하나 나온 것처럼 보였다. 그래서 아래 두 가지를 못 박는다.
    """

    def test_str_of_none_is_not_a_gender(self) -> None:
        """실제 사고 값. 이것 하나가 필터 전체를 무력화했다."""
        self.assertEqual(normalize_gender("None"), "")
        self.assertEqual(normalize_gender(None), "")
        self.assertEqual(allowed_presentation_groups("None"), ())

    def test_known_spellings(self) -> None:
        for value in ("male", "MALE", "  Male ", "m", "남성", "남자"):
            self.assertEqual(normalize_gender(value), "male", repr(value))
        for value in ("female", "F", "여성", "여자"):
            self.assertEqual(normalize_gender(value), "female", repr(value))

    def test_blank_like_values_are_blank(self) -> None:
        for value in ("", "   ", "unknown", "미지정", "null", "-"):
            self.assertEqual(normalize_gender(value), "", repr(value))

    def test_allowed_groups_never_include_the_other_side(self) -> None:
        self.assertEqual(allowed_presentation_groups("male"), ("men", "unisex"))
        self.assertEqual(allowed_presentation_groups("female"), ("women", "unisex"))
        # 라벨 없는 코디("")는 어느 쪽에도 없다. unisex로 봐주면 여성 코디가
        # 그대로 남성에게 나간다.
        self.assertNotIn("", allowed_presentation_groups("male"))

    def test_empty_tuple_means_unknown_not_unrestricted(self) -> None:
        """빈 튜플을 '제한 없음'으로 읽는 호출부가 생기면 다시 같은 사고가 난다."""
        self.assertEqual(allowed_presentation_groups(""), ())


class _FakePoint:
    def __init__(self, pid: str, payload: dict) -> None:
        self.id = pid
        self.payload = payload


class _IgnoresFilterClient:
    """필터를 **무시하는** Qdrant. 인덱스 누락·구버전 배포를 흉내낸다.

    Qdrant의 must는 payload 인덱스가 없거나 키가 빠지면 기대와 다르게 동작할 수
    있고, 오래된 이미지가 돌면 애초에 필터가 붙지 않는다. 어느 쪽이든 예외가
    나지 않아 조용히 통과한다. 그래서 리트리버는 파이썬에서 한 번 더 막는다.
    """

    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.last_filter = "unset"

    def scroll(self, *, scroll_filter=None, **kwargs):
        self.last_filter = scroll_filter
        return [_FakePoint(f"p{i}", p) for i, p in enumerate(self.payloads)], None


class GenderSecondLineOfDefenceTests(unittest.TestCase):
    def _run(self, gender: str, payloads: list[dict]):
        from apps.recommend.services.retriever import RetrievalRequest, retrieve_outfits

        client = _IgnoresFilterClient(payloads)
        got = retrieve_outfits(
            RetrievalRequest(gender=gender, limit=10), client=client
        )
        return client, got

    def test_womens_outfit_never_reaches_a_male_user(self) -> None:
        client, got = self._run(
            "male",
            [
                {"golden_id": "w1", "presentation_group": "women",
                 "items": [{"category": "탑", "name": "캉캉 끈나시 탑"}]},
                {"golden_id": "m1", "presentation_group": "men", "items": []},
                {"golden_id": "u1", "presentation_group": "unisex", "items": []},
            ],
        )
        # 검색 단계에도 조건이 붙어 있어야 한다 (왕복 낭비를 줄이는 1차 방어선)
        self.assertIsNotNone(client.last_filter)
        # 그리고 필터가 무시돼도 결과에는 없어야 한다 (2차 방어선)
        self.assertEqual(sorted(c.golden_id for c in got), ["m1", "u1"])

    def test_unlabelled_outfits_are_dropped_not_treated_as_unisex(self) -> None:
        _, got = self._run(
            "male",
            [
                {"golden_id": "x", "presentation_group": "", "items": []},
                {"golden_id": "y", "items": []},
                {"golden_id": "m1", "presentation_group": "men", "items": []},
            ],
        )
        self.assertEqual([c.golden_id for c in got], ["m1"])

    def test_str_none_gender_does_not_open_the_gate(self) -> None:
        """사고 재현. 예전 코드는 여기서 여성 코디를 그대로 돌려줬다."""
        client, got = self._run(
            "None",
            [{"golden_id": "w1", "presentation_group": "women", "items": []}],
        )
        # 성별을 모르면 리트리버는 제한하지 않는다 — 그 판단은 daily_look의 몫이다.
        # 다만 "None"이 성별로 해석되지 않는다는 점은 여기서 못 박는다.
        self.assertIsNone(client.last_filter)
        self.assertEqual([c.golden_id for c in got], ["w1"])
