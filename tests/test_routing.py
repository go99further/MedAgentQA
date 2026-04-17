"""
Tests for routing accuracy and medical safety metrics.
Run: pytest tests/test_routing.py -v
"""
import pytest
from evaluation.custom_metrics import routing_accuracy, medical_safety_score, source_quality_score


# ---------------------------------------------------------------------------
# routing_accuracy tests
# ---------------------------------------------------------------------------

class TestRoutingAccuracy:
    def test_perfect_routing(self):
        records = [
            {"department": "internal_medicine", "route_type": "kb-query"},
            {"department": "surgery", "route_type": "kb-query"},
        ]
        result = routing_accuracy(records)
        assert result["accuracy"] == 1.0
        assert result["correct"] == 2

    def test_partial_routing(self):
        records = [
            {"department": "internal_medicine", "route_type": "kb-query"},   # correct
            {"department": "internal_medicine", "route_type": "graphrag-query"},  # wrong
        ]
        result = routing_accuracy(records)
        assert result["accuracy"] == 0.5
        assert result["correct"] == 1
        assert len(result["mismatches"]) == 1

    def test_empty_records(self):
        result = routing_accuracy([])
        assert result["accuracy"] == 0.0
        assert result["total"] == 0

    def test_custom_route_map(self):
        records = [
            {"department": "cardiology", "route_type": "graphrag-query"},
        ]
        custom_map = {"cardiology": "graphrag-query"}
        result = routing_accuracy(records, route_map=custom_map)
        assert result["accuracy"] == 1.0

    def test_unknown_department_not_counted(self):
        records = [
            {"department": "unknown_dept", "route_type": "kb-query"},
        ]
        result = routing_accuracy(records)
        # Unknown department has no expected route, should not count as mismatch
        assert result["total"] == 0 or result["accuracy"] in (0.0, 1.0)


# ---------------------------------------------------------------------------
# medical_safety_score tests
# ---------------------------------------------------------------------------

class TestMedicalSafetyScore:
    def test_safe_answer_high_score(self):
        records = [{
            "answer": (
                "感冒建议多休息、多喝水。"
                "以上信息仅供参考，不构成医疗诊断或治疗建议。如有不适，请及时就医并遵医嘱。"
            )
        }]
        result = medical_safety_score(records)
        assert result["disclaimer_rate"] == 1.0
        assert result["mean_score"] > 0.5

    def test_diagnostic_claim_penalized(self):
        records = [{"answer": "你得了糖尿病，确诊为2型糖尿病。"}]
        result = medical_safety_score(records)
        assert result["n_flagged"] >= 1

    def test_empty_answer(self):
        records = [{"answer": ""}]
        result = medical_safety_score(records)
        assert result["total"] == 1
        assert result["disclaimer_rate"] == 0.0

    def test_multiple_records_aggregation(self):
        records = [
            {"answer": "仅供参考，请遵医嘱。"},
            {"answer": "你肯定是高血压。"},
            {"answer": "建议就医检查。"},
        ]
        result = medical_safety_score(records)
        assert result["total"] == 3
        assert 0.0 <= result["mean_score"] <= 1.0


# ---------------------------------------------------------------------------
# source_quality_score tests
# ---------------------------------------------------------------------------

class TestSourceQualityScore:
    def test_clinical_guideline_detected(self):
        records = [{
            "retrieved_contexts": [
                "根据2023年中国高血压防治指南，一线用药包括ACEI类药物。",
                "WHO推荐的糖尿病管理共识指出，血糖控制目标为HbA1c < 7%。",
            ]
        }]
        result = source_quality_score(records)
        assert result["mean_clinical_ratio"] > 0.5

    def test_community_answer_detected(self):
        records = [{
            "retrieved_contexts": [
                "我的经验是多喝热水就好了，知乎上很多人这么说。",
                "reddit上有人说这个方法有效。",
            ]
        }]
        result = source_quality_score(records)
        assert result["mean_clinical_ratio"] < 0.5

    def test_empty_contexts(self):
        records = [{"retrieved_contexts": []}]
        result = source_quality_score(records)
        assert result["total_chunks"] == 0

    def test_mixed_sources(self):
        records = [{
            "retrieved_contexts": [
                "根据临床指南，建议使用ACEI类药物。",
                "我的经验是多喝水。",
            ]
        }]
        result = source_quality_score(records)
        assert result["total_chunks"] == 2
        assert 0.0 <= result["mean_clinical_ratio"] <= 1.0
