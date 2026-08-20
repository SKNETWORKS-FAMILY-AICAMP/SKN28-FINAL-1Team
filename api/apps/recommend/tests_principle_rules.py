"""원칙 조건을 코디 조합에 대조하는 규칙.

여기서 조용히 틀리면 **엉뚱한 슬롯을 바꾼 추천**이 나간다. 에러가 아니라 잘못된
추천으로 드러나기 때문에 눈에 안 띈다. 그래서 세 가지를 고정한다.

- 모름은 어긋남이 아니다 (상품 태그가 대부분 비어 있다)
- 관여 문턱 아래의 원칙은 무시한다 (우연히 하나 맞은 원칙이 슬롯을 바꾸면 안 된다)
- 짧은 키워드가 다른 단어 안에 묻혀 걸리지 않는다 ("꽈배기"의 "배기")
"""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.recommend.services.principle_rules import (
    ENGAGE_MIN,
    Condition,
    PrincipleRule,
    _contains,
    evaluate,
    evaluate_rule,
    extract_attributes,
    violation_count,
)


def _rule(*conditions: Condition) -> PrincipleRule:
    return PrincipleRule(
        principle_key="댄디:A1:p01",
        cluster_id="댄디",
        statement="문장",
        conditions=conditions,
    )


def _single(slot: str, attribute: str, value: str) -> Condition:
    return Condition(kind="single", slot=slot, attribute=attribute, value=value)


def _relation(relation: str, a: str, b: str) -> Condition:
    return Condition(kind="relation", relation=relation, slot_a=a, slot_b=b)


class KeywordBoundaryTests(SimpleTestCase):
    def test_short_keyword_inside_another_word_is_ignored(self) -> None:
        """실제로 '꽈배기 헤어밴드'가 핏=배기로 읽혔다."""
        self.assertFalse(_contains("꽈배기 헤어밴드", "배기"))

    def test_short_keyword_standing_alone_is_found(self) -> None:
        self.assertTrue(_contains("배기 데님 팬츠", "배기"))

    def test_suffix_compound_is_still_found(self) -> None:
        """'배기핏'처럼 뒤에 붙는 건 한국어 합성의 정상 형태다."""
        self.assertTrue(_contains("배기핏 팬츠", "배기"))

    def test_long_keyword_needs_no_boundary(self) -> None:
        self.assertTrue(_contains("여름스트라이프티", "스트라이프"))


class ExtractAttributeTests(SimpleTestCase):
    def test_reads_from_tags_first(self) -> None:
        attributes = extract_attributes(
            {"color": ["블랙"], "pattern": ["스트라이프"], "title": ""}
        )
        self.assertEqual(attributes["명도"], "어두움")
        self.assertEqual(attributes["패턴"], "스트라이프")

    def test_falls_back_to_the_title(self) -> None:
        """상품 color 태그는 19퍼센트만 채워져 있다. 이름에는 거의 항상 있다."""
        attributes = extract_attributes({"title": "여성 아이보리 크롭 니트"})
        self.assertEqual(attributes["명도"], "밝음")
        self.assertEqual(attributes["기장"], "크롭")
        self.assertEqual(attributes["소재"], "니트")

    def test_mixed_brightness_is_left_unknown(self) -> None:
        """밝은 색과 어두운 색이 섞이면 명도를 단정할 수 없다."""
        attributes = extract_attributes({"color": ["화이트", "블랙"]})
        self.assertNotIn("명도", attributes)

    def test_achromatic_is_detected(self) -> None:
        attributes = extract_attributes({"color": ["블랙", "화이트"]})
        self.assertEqual(attributes["색"], "무채색")

    def test_unknown_payload_yields_nothing(self) -> None:
        self.assertEqual(extract_attributes({"title": "머리끈 세트"}), {})


class EvaluateRuleTests(SimpleTestCase):
    def test_all_conditions_matched_has_no_violation(self) -> None:
        rule = _rule(
            _single("top", "명도", "어두움"), _single("bottom", "명도", "밝음")
        )
        outcome = evaluate_rule(
            rule, {"top": {"명도": "어두움"}, "bottom": {"명도": "밝음"}}
        )
        self.assertEqual(outcome.matched, 2)
        self.assertEqual(outcome.violations, ())
        self.assertTrue(outcome.engaged)

    def test_violation_points_at_the_offending_slot(self) -> None:
        rule = _rule(
            _single("top", "명도", "어두움"),
            _single("bottom", "명도", "밝음"),
            _single("shoes", "명도", "어두움"),
        )
        outcome = evaluate_rule(
            rule,
            {
                "top": {"명도": "어두움"},
                "bottom": {"명도": "밝음"},
                "shoes": {"명도": "밝음"},
            },
        )
        self.assertEqual(outcome.matched, 2)
        self.assertEqual(outcome.violation_slots, ("shoes",))

    def test_unknown_attribute_is_neither_match_nor_violation(self) -> None:
        """태그가 비어 있다는 이유로 벌점을 주면 안 된다."""
        rule = _rule(
            _single("top", "명도", "어두움"), _single("shoes", "패턴", "무지")
        )
        outcome = evaluate_rule(rule, {"top": {"명도": "어두움"}, "shoes": {}})
        self.assertEqual(outcome.matched, 1)
        self.assertEqual(outcome.violations, ())

    def test_relation_contrast(self) -> None:
        rule = _rule(_relation("명도대비", "top", "bottom"))
        hit = evaluate_rule(
            rule, {"top": {"명도": "어두움"}, "bottom": {"명도": "밝음"}}
        )
        miss = evaluate_rule(
            rule, {"top": {"명도": "밝음"}, "bottom": {"명도": "밝음"}}
        )
        self.assertEqual(hit.matched, 1)
        self.assertEqual(len(miss.violations), 1)

    def test_relation_needs_both_sides_known(self) -> None:
        rule = _rule(_relation("명도대비", "top", "bottom"))
        outcome = evaluate_rule(rule, {"top": {"명도": "어두움"}, "bottom": {}})
        self.assertEqual(outcome.matched, 0)
        self.assertEqual(outcome.violations, ())

    def test_unknown_relation_is_ignored(self) -> None:
        rule = _rule(_relation("존재하지않는관계", "top", "bottom"))
        outcome = evaluate_rule(
            rule, {"top": {"명도": "어두움"}, "bottom": {"명도": "밝음"}}
        )
        self.assertEqual(outcome.matched, 0)
        self.assertEqual(outcome.violations, ())


class EngagementTests(SimpleTestCase):
    def test_barely_matching_rule_is_not_engaged(self) -> None:
        """3개 중 1개만 우연히 맞은 원칙이 슬롯을 바꾸면 안 된다."""
        rule = _rule(
            _single("top", "명도", "어두움"),
            _single("bottom", "명도", "밝음"),
            _single("shoes", "명도", "어두움"),
        )
        slots = {
            "top": {"명도": "어두움"},
            "bottom": {"명도": "어두움"},
            "shoes": {"명도": "밝음"},
        }
        self.assertEqual(evaluate_rule(rule, slots).matched, 1)
        self.assertEqual(evaluate([rule], slots), ())
        self.assertEqual(violation_count([rule], slots), 0)

    def test_engaged_rule_contributes_its_violations(self) -> None:
        rule = _rule(
            _single("top", "명도", "어두움"),
            _single("bottom", "명도", "밝음"),
            _single("shoes", "명도", "어두움"),
        )
        slots = {
            "top": {"명도": "어두움"},
            "bottom": {"명도": "밝음"},
            "shoes": {"명도": "밝음"},
        }
        self.assertEqual(violation_count([rule], slots), 1)

    def test_threshold_is_the_documented_value(self) -> None:
        self.assertEqual(ENGAGE_MIN, 2)
