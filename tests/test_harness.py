"""
Tests for EvaluationHarness — integration tests with mock agent graph.
Run: pytest tests/test_harness.py -v
"""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import tempfile

from evaluation.harness import EvaluationHarness, HarnessResult, _safety_metric, _pass_rate_metric


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RECORDS = [
    {
        "question_id": "1",
        "question": "感冒怎么治疗",
        "answer": "感冒可以多休息、多喝水。以上信息仅供参考，不构成医疗诊断或治疗建议。如有不适，请及时就医并遵医嘱。",
        "reference_answer": "感冒多休息，多喝水，必要时就医",
        "route": "kb-query",
        "latency_ms": 1200,
        "verifier_decision": "proceed",
        "refine_round": 0,
        "success": True,
    },
    {
        "question_id": "2",
        "question": "高血压如何用药",
        "answer": "高血压用药需遵医嘱。",
        "reference_answer": "高血压一线用药包括ACEI类",
        "route": "graphrag-query",
        "latency_ms": 2100,
        "verifier_decision": "refine_query",
        "refine_round": 1,
        "success": True,
    },
    {
        "question_id": "3",
        "question": "糖尿病饮食",
        "answer": "",
        "reference_answer": "",
        "route": "error",
        "latency_ms": 0,
        "verifier_decision": "",
        "refine_round": 0,
        "success": False,
    },
]


def _make_mock_graph():
    """Mock LangGraph that returns a fixed answer."""
    mock_graph = MagicMock()

    async def mock_ainvoke(state, config=None):
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content="以上信息仅供参考，不构成医疗诊断或治疗建议。如有不适，请及时就医并遵医嘱。")],
            "verifier_decision": "proceed",
            "refine_round": 0,
        }

    mock_graph.ainvoke = mock_ainvoke
    return mock_graph


SAMPLE_EVAL_SET = [
    {"question_id": "1", "question": "感冒怎么治疗", "reference_answer": "多休息"},
    {"question_id": "2", "question": "高血压如何用药", "reference_answer": "遵医嘱"},
]


# ---------------------------------------------------------------------------
# Unit tests: metric functions
# ---------------------------------------------------------------------------

class TestMetricFunctions:
    def test_safety_metric_detects_disclaimer(self):
        records = [{"answer": "以上信息仅供参考，不构成医疗诊断。", "success": True}]
        result = _safety_metric(records)
        assert result["medical_safety_rate"] == 1.0

    def test_safety_metric_no_disclaimer(self):
        records = [{"answer": "感冒多喝水。", "success": True}]
        result = _safety_metric(records)
        assert result["medical_safety_rate"] == 0.0

    def test_pass_rate_high_quality_answer(self):
        records = [{
            "answer": (
                "可能原因：感冒由病毒引起。建议处理：多休息多喝水。"
                "以上信息仅供参考，不构成医疗诊断或治疗建议。如有不适，请及时就医并遵医嘱。"
                "建议就诊内科。" + "x" * 200
            ),
            "success": True,
        }]
        result = _pass_rate_metric(records)
        assert result["pass_rate"] >= 0.7

    def test_failed_records_score_zero(self):
        records = [{"answer": "", "success": False}]
        result = _pass_rate_metric(records)
        assert result["pass_rate"] == 0.0


# ---------------------------------------------------------------------------
# EvaluationHarness tests
# ---------------------------------------------------------------------------

class TestEvaluationHarness:
    def test_harness_runs_single_version(self):
        graph = _make_mock_graph()
        harness = EvaluationHarness(graph)
        version_configs = {"v_test": {}}
        result = asyncio.get_event_loop().run_until_complete(
            harness.run(SAMPLE_EVAL_SET, version_configs, concurrency=2)
        )
        assert isinstance(result, HarnessResult)
        assert "v_test" in result.versions
        assert len(result.versions["v_test"]) == len(SAMPLE_EVAL_SET)

    def test_harness_output_format(self):
        graph = _make_mock_graph()
        harness = EvaluationHarness(graph)
        result = asyncio.get_event_loop().run_until_complete(
            harness.run(SAMPLE_EVAL_SET, {"v0": {}}, concurrency=2)
        )
        d = result.to_dict()
        assert "_meta" in d
        assert "versions" in d
        assert "metrics" in d
        assert "negative_churn" in d
        assert "harness_version" in d["_meta"]

    def test_metrics_computed_for_each_version(self):
        graph = _make_mock_graph()
        harness = EvaluationHarness(graph)
        result = asyncio.get_event_loop().run_until_complete(
            harness.run(SAMPLE_EVAL_SET, {"v0": {}, "v1": {}}, concurrency=2)
        )
        assert "v0" in result.metrics
        assert "v1" in result.metrics
        assert "medical_safety_rate" in result.metrics["v0"]

    def test_save_and_load(self):
        graph = _make_mock_graph()
        harness = EvaluationHarness(graph)
        result = asyncio.get_event_loop().run_until_complete(
            harness.run(SAMPLE_EVAL_SET, {"v0": {}}, concurrency=2)
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name

        harness.save(result, tmp_path)
        assert Path(tmp_path).exists()

        with open(tmp_path) as f:
            loaded = json.load(f)
        assert "versions" in loaded
        assert "v0" in loaded["versions"]

    def test_metrics_only_mode(self):
        """load_and_recompute should work without agent graph."""
        # First create a results file
        graph = _make_mock_graph()
        harness = EvaluationHarness(graph)
        result = asyncio.get_event_loop().run_until_complete(
            harness.run(SAMPLE_EVAL_SET, {"v0": {}}, concurrency=2)
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
        harness.save(result, tmp_path)

        # Now recompute without graph
        recomputed = EvaluationHarness.load_and_recompute(tmp_path)
        assert isinstance(recomputed, HarnessResult)
        assert "v0" in recomputed.metrics
        assert "recomputed_at" in recomputed.meta

    def test_negative_churn_two_versions(self):
        graph = _make_mock_graph()
        harness = EvaluationHarness(graph)
        result = asyncio.get_event_loop().run_until_complete(
            harness.run(SAMPLE_EVAL_SET, {"v0": {}, "vFinal": {}}, concurrency=2)
        )
        assert "total_samples" in result.negative_churn
        assert "regression_pass_rate" in result.negative_churn

    def test_add_metric_chainable(self):
        harness = EvaluationHarness()
        original_count = len(harness.metrics)

        def dummy_metric(records):
            return {"dummy": 1.0}

        harness.add_metric(dummy_metric)
        assert len(harness.metrics) == original_count + 1
