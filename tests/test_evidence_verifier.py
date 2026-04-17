"""
Tests for Evidence Verifier — unit tests for decision logic.
Run: pytest tests/test_evidence_verifier.py -v
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from medagent.application.agents.kg_sub_graph.agentic_rag_agents.components.evidence_verifier.node import (
    DefaultVerifierStrategy,
    VerifierDecision,
    create_evidence_verifier_node,
)


# ---------------------------------------------------------------------------
# DefaultVerifierStrategy unit tests
# ---------------------------------------------------------------------------

class TestDefaultVerifierStrategy:
    def setup_method(self):
        self.strategy = DefaultVerifierStrategy()

    def test_empty_contexts_triggers_refine(self):
        decision = self.strategy.verify("感冒怎么治", [], refine_round=0, refined_queries=[])
        assert decision == VerifierDecision.REFINE

    def test_sufficient_contexts_proceeds(self):
        contexts = [
            {"content": "感冒可以服用对乙酰氨基酚退烧", "score": 0.85},
            {"content": "多喝水、充分休息有助于恢复", "score": 0.78},
        ]
        decision = self.strategy.verify("感冒怎么治", contexts, refine_round=0, refined_queries=[])
        assert decision == VerifierDecision.PROCEED

    def test_too_few_chunks_triggers_refine(self):
        contexts = [{"content": "感冒相关信息", "score": 0.9}]  # only 1, MIN_CHUNKS=2
        decision = self.strategy.verify("感冒怎么治", contexts, refine_round=0, refined_queries=[])
        assert decision == VerifierDecision.REFINE

    def test_low_score_triggers_refine(self):
        contexts = [
            {"content": "一些不相关内容", "score": 0.1},
            {"content": "另一些不相关内容", "score": 0.05},
        ]
        decision = self.strategy.verify("感冒怎么治", contexts, refine_round=0, refined_queries=[])
        assert decision == VerifierDecision.REFINE

    def test_max_rounds_triggers_refusal(self):
        contexts = []  # would normally trigger REFINE
        decision = self.strategy.verify(
            "感冒怎么治", contexts,
            refine_round=DefaultVerifierStrategy().max_refine_rounds,
            refined_queries=["query1", "query2"],
        )
        assert decision == VerifierDecision.REFUSE

    def test_max_rounds_overrides_empty_contexts(self):
        """Even with empty contexts, max rounds should give REFUSE not REFINE."""
        decision = self.strategy.verify(
            "问题", [],
            refine_round=2,
            refined_queries=["q1", "q2"],
        )
        assert decision == VerifierDecision.REFUSE

    def test_empty_content_chunks_not_counted(self):
        """Chunks with empty content should not count toward MIN_CHUNKS."""
        contexts = [
            {"content": "", "score": 0.9},
            {"content": "   ", "score": 0.8},
        ]
        decision = self.strategy.verify("问题", contexts, refine_round=0, refined_queries=[])
        assert decision == VerifierDecision.REFINE

    def test_score_from_similarity_field(self):
        """Should also read 'similarity' field as score."""
        contexts = [
            {"content": "内容A", "similarity": 0.85},
            {"content": "内容B", "similarity": 0.75},
        ]
        decision = self.strategy.verify("问题", contexts, refine_round=0, refined_queries=[])
        assert decision == VerifierDecision.PROCEED


# ---------------------------------------------------------------------------
# create_evidence_verifier_node integration tests (mock LLM)
# ---------------------------------------------------------------------------

class TestEvidenceVerifierNode:
    def _make_mock_llm(self, refine_response: str = "改进后的查询"):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = refine_response
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        return mock_llm

    def test_proceed_state_unchanged(self):
        llm = self._make_mock_llm()
        node = create_evidence_verifier_node(llm=llm)
        state = {
            "question": "高血压怎么治疗",
            "local_results": [
                {"content": "高血压一线用药包括ACEI类药物", "score": 0.88},
                {"content": "生活方式干预是高血压治疗的基础", "score": 0.82},
            ],
            "refine_round": 0,
            "refined_queries": [],
        }
        result = asyncio.get_event_loop().run_until_complete(node(state))
        assert result["verifier_decision"] == VerifierDecision.PROCEED
        assert result["question"] == "高血压怎么治疗"
        assert result["refine_round"] == 0

    def test_refine_updates_question_and_round(self):
        llm = self._make_mock_llm("高血压药物治疗方案详细")
        node = create_evidence_verifier_node(llm=llm)
        state = {
            "question": "高血压",
            "local_results": [],  # empty → REFINE
            "refine_round": 0,
            "refined_queries": [],
        }
        result = asyncio.get_event_loop().run_until_complete(node(state))
        assert result["verifier_decision"] == VerifierDecision.REFINE
        assert result["refine_round"] == 1
        assert len(result["refined_queries"]) == 1

    def test_refuse_after_max_rounds(self):
        llm = self._make_mock_llm()
        node = create_evidence_verifier_node(llm=llm)
        state = {
            "question": "问题",
            "local_results": [],
            "refine_round": 2,  # MAX_REFINE_ROUNDS
            "refined_queries": ["q1", "q2"],
        }
        result = asyncio.get_event_loop().run_until_complete(node(state))
        assert result["verifier_decision"] == VerifierDecision.REFUSE

    def test_loop_detection_triggers_refuse(self):
        """If embedding_fn detects loop (high similarity), should REFUSE."""
        llm = self._make_mock_llm("高血压")  # same as original → loop

        # Mock embedding that returns identical vectors → cosine sim = 1.0
        def mock_embed(text: str):
            return [1.0, 0.0, 0.0]

        node = create_evidence_verifier_node(llm=llm, embedding_fn=mock_embed)
        state = {
            "question": "高血压",
            "local_results": [],
            "refine_round": 0,
            "refined_queries": ["高血压"],  # same as what LLM will generate
        }
        result = asyncio.get_event_loop().run_until_complete(node(state))
        assert result["verifier_decision"] == VerifierDecision.REFUSE
