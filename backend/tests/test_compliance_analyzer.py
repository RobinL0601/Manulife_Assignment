"""Tests for compliance analyzer functionality."""

import pytest
from unittest.mock import AsyncMock, Mock

from app.core.schemas import ComplianceState, EvidenceChunk
from app.pipeline.compliance_analyzer import ComplianceAnalyzer, get_requirement_ids


class TestComplianceAnalyzer:
    """Test ComplianceAnalyzer class."""
    
    @pytest.mark.asyncio
    async def test_valid_json_response_parsed_successfully(self):
        """Test that valid JSON response is parsed into ComplianceResult."""
        # Mock LLM client that returns valid JSON
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="""
{
  "compliance_state": "Fully Compliant",
  "confidence": 90,
  "relevant_quotes": [
    {
      "text": "All passwords must be at least 12 characters long.",
      "page_start": 5,
      "page_end": 5
    }
  ],
  "rationale": "The contract explicitly requires password length of 12 characters minimum."
}
""")
        
        # Create analyzer
        analyzer = ComplianceAnalyzer(llm_client=mock_llm)
        
        # Create evidence chunks
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="All passwords must be at least 12 characters long.",
                normalized_text="all passwords must be at least 12 characters long",
                page_start=5,
                page_end=5,
                char_range=(0, 100),
                relevance_score=0.95
            )
        ]
        
        # Analyze
        result = await analyzer.analyze(
            question="password_management",
            evidence_chunks=evidence
        )
        
        # Verify result
        assert result.compliance_state == ComplianceState.FULLY_COMPLIANT
        assert result.confidence == 90
        assert len(result.relevant_quotes) == 1
        assert result.relevant_quotes[0].text == \
            "All passwords must be at least 12 characters long."
        assert result.relevant_quotes[0].page_start == 5
        assert result.relevant_quotes[0].page_end == 5
        assert "12 characters" in result.rationale
        
        # Verify LLM was called with evidence
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs['prompt']
        assert "Evidence 1 [Pages 5]:" in prompt
        assert "All passwords must be at least 12 characters long" in prompt
    
    @pytest.mark.asyncio
    async def test_malformed_json_returns_fallback(self):
        """Test that malformed JSON triggers retry and eventually fallback."""
        # Mock LLM that returns invalid JSON twice
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=[
            "This is not JSON at all, just some text",  # First attempt
            "Still not valid {JSON here",  # Retry attempt
        ])
        
        # Create analyzer
        analyzer = ComplianceAnalyzer(llm_client=mock_llm)
        
        # Create evidence
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="Some evidence text.",
                normalized_text="some evidence text",
                page_start=1,
                page_end=1,
                char_range=(0, 50),
                relevance_score=0.8
            )
        ]
        
        # Analyze
        result = await analyzer.analyze(
            question="tls_encryption",
            evidence_chunks=evidence
        )
        
        # Should return fallback result
        assert result.compliance_state == ComplianceState.NON_COMPLIANT
        assert result.confidence == 10
        assert len(result.relevant_quotes) == 0
        assert result.rationale == "Model output could not be parsed."
        
        # Verify retry was attempted (2 calls total)
        assert mock_llm.generate.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_succeeds_with_valid_json(self):
        """Test that retry with fix prompt can succeed."""
        # Mock LLM: first call returns invalid, second returns valid
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=[
            "Invalid JSON response here",  # First attempt fails
            """{
  "compliance_state": "Partially Compliant",
  "confidence": 60,
  "relevant_quotes": [],
  "rationale": "Some requirements mentioned but incomplete."
}""",  # Retry succeeds
        ])
        
        analyzer = ComplianceAnalyzer(llm_client=mock_llm)
        
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="Training is required.",
                normalized_text="training is required",
                page_start=3,
                page_end=3,
                char_range=(0, 50),
                relevance_score=0.7
            )
        ]
        
        result = await analyzer.analyze(
            question="security_training",
            evidence_chunks=evidence
        )
        
        # Should parse successfully from retry
        assert result.compliance_state == ComplianceState.PARTIALLY_COMPLIANT
        assert result.confidence == 60
        assert result.rationale == "Some requirements mentioned but incomplete."
        
        # Both calls should have been made
        assert mock_llm.generate.call_count == 2


class TestRequirementDefinitions:
    """Test requirement definitions."""
    
    def test_all_five_requirements_defined(self):
        """Test that all 5 requirements have definitions."""
        requirement_ids = get_requirement_ids()
        
        assert len(requirement_ids) == 5
        assert "password_management" in requirement_ids
        assert "it_asset_management" in requirement_ids
        assert "security_training" in requirement_ids
        assert "tls_encryption" in requirement_ids
        assert "authn_authz" in requirement_ids
    
    def test_requirements_have_rubrics(self):
        """Test that requirements have questions and rubrics."""
        from app.pipeline.compliance_analyzer import COMPLIANCE_REQUIREMENTS
        
        for req_id in get_requirement_ids():
            req = COMPLIANCE_REQUIREMENTS[req_id]
            assert "question" in req
            assert "rubric" in req
            assert len(req["question"]) > 0
            assert len(req["rubric"]) > 50  # Rubrics should be detailed
