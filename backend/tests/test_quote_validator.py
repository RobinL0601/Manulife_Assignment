"""Tests for quote validation functionality."""

import pytest

from app.core.schemas import (
    ComplianceResult, ComplianceState, Quote, EvidenceChunk, DocumentArtifact, PageArtifact
)
from app.pipeline.quote_validator import QuoteValidator


class TestQuoteValidator:
    """Test QuoteValidator class."""
    
    def test_hallucinated_quote_is_removed(self):
        """Test that hallucinated (non-existent) quotes are removed."""
        # Create evidence chunks
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="All passwords must be at least 12 characters long.",
                normalized_text="all passwords must be at least 12 characters long",
                page_start=5,
                page_end=5,
                char_range=(0, 100),
                relevance_score=0.9
            ),
            EvidenceChunk(
                chunk_id="doc:chunk_1",
                text="Passwords must include uppercase and lowercase letters.",
                normalized_text="passwords must include uppercase and lowercase letters",
                page_start=5,
                page_end=5,
                char_range=(101, 200),
                relevance_score=0.8
            )
        ]
        
        # Create result with one real quote and one hallucinated quote
        result = ComplianceResult(
            compliance_question="Does the contract require password policies?",
            compliance_state=ComplianceState.FULLY_COMPLIANT,
            confidence=85,
            relevant_quotes=[
                Quote(
                    text="All passwords must be at least 12 characters long.",
                    page_start=5,
                    page_end=5,
                    validated=False
                ),
                Quote(
                    text="Passwords must be rotated every 90 days.",  # Hallucinated!
                    page_start=5,
                    page_end=5,
                    validated=False
                )
            ],
            rationale="The contract specifies password requirements."
        )
        
        # Create mock document
        doc = DocumentArtifact(
            filename="test.pdf",
            page_count=10,
            pages=[]
        )
        
        # Validate
        validator = QuoteValidator()
        validated_result = validator.validate_quotes(result, evidence, doc)
        
        # Should have only 1 quote (hallucinated one removed)
        assert len(validated_result.relevant_quotes) == 1
        assert validated_result.relevant_quotes[0].text == \
            "All passwords must be at least 12 characters long."
        assert validated_result.relevant_quotes[0].validated is True
        
        # Confidence should remain relatively high (not all quotes removed)
        assert validated_result.confidence >= 50
    
    def test_real_quote_found_with_correct_page_range(self):
        """Test that real quotes are found and get correct page ranges."""
        # Create evidence chunks with different page ranges
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="Section 1: General security requirements apply.",
                normalized_text="section 1 general security requirements apply",
                page_start=1,
                page_end=1,
                char_range=(0, 100),
                relevance_score=0.5
            ),
            EvidenceChunk(
                chunk_id="doc:chunk_1",
                text="All data in transit must use TLS 1.2 or higher encryption.",
                normalized_text="all data in transit must use tls 1.2 or higher encryption",
                page_start=7,
                page_end=7,
                char_range=(101, 200),
                relevance_score=0.95
            ),
            EvidenceChunk(
                chunk_id="doc:chunk_2",
                text="Certificate management procedures are documented.",
                normalized_text="certificate management procedures are documented",
                page_start=8,
                page_end=9,
                char_range=(201, 300),
                relevance_score=0.7
            )
        ]
        
        # Create result with quote from second chunk
        result = ComplianceResult(
            compliance_question="Does the contract mandate TLS encryption?",
            compliance_state=ComplianceState.FULLY_COMPLIANT,
            confidence=90,
            relevant_quotes=[
                Quote(
                    text="All data in transit must use TLS 1.2 or higher encryption.",
                    page_start=0,  # Wrong initially
                    page_end=0,
                    validated=False
                )
            ],
            rationale="TLS 1.2 is explicitly required."
        )
        
        # Create mock document
        doc = DocumentArtifact(
            filename="test.pdf",
            page_count=10,
            pages=[]
        )
        
        # Validate
        validator = QuoteValidator()
        validated_result = validator.validate_quotes(result, evidence, doc)
        
        # Should have 1 validated quote
        assert len(validated_result.relevant_quotes) == 1
        
        quote = validated_result.relevant_quotes[0]
        assert quote.validated is True
        assert quote.page_start == 7  # From chunk_1
        assert quote.page_end == 7
        assert "TLS 1.2" in quote.text
        
        # Confidence should be unchanged (quote validated successfully)
        assert validated_result.confidence == 90
    
    def test_all_quotes_removed_reduces_confidence(self):
        """Test that removing all quotes reduces confidence to ≤30."""
        # Create evidence that doesn't contain any quotes
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="This is some unrelated contract text.",
                normalized_text="this is some unrelated contract text",
                page_start=1,
                page_end=1,
                char_range=(0, 100),
                relevance_score=0.5
            )
        ]
        
        # Create result with hallucinated quotes
        result = ComplianceResult(
            compliance_question="Does the contract require security training?",
            compliance_state=ComplianceState.PARTIALLY_COMPLIANT,
            confidence=75,
            relevant_quotes=[
                Quote(
                    text="Annual security training is mandatory.",
                    page_start=1,
                    page_end=1,
                    validated=False
                ),
                Quote(
                    text="Background checks are required for all employees.",
                    page_start=1,
                    page_end=1,
                    validated=False
                )
            ],
            rationale="Training requirements found."
        )
        
        # Create mock document
        doc = DocumentArtifact(
            filename="test.pdf",
            page_count=10,
            pages=[]
        )
        
        # Validate
        validator = QuoteValidator()
        validated_result = validator.validate_quotes(result, evidence, doc)
        
        # All quotes should be removed
        assert len(validated_result.relevant_quotes) == 0
        
        # Confidence should be reduced to ≤30
        assert validated_result.confidence <= 30
        
        # Rationale should include note about missing quotes
        assert "No verifiable verbatim quotes" in validated_result.rationale
    
    def test_normalization_handles_unicode_quotes(self):
        """Test that normalization handles Unicode quotes and dashes."""
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="The policy states: "passwords must be complex".",
                normalized_text='the policy states "passwords must be complex"',
                page_start=3,
                page_end=3,
                char_range=(0, 100),
                relevance_score=0.9
            )
        ]
        
        # Quote with straight quotes (different from Unicode smart quotes in evidence)
        result = ComplianceResult(
            compliance_question="Password policy?",
            compliance_state=ComplianceState.FULLY_COMPLIANT,
            confidence=80,
            relevant_quotes=[
                Quote(
                    text='passwords must be complex',  # Straight quotes
                    page_start=0,
                    page_end=0,
                    validated=False
                )
            ],
            rationale="Found."
        )
        
        doc = DocumentArtifact(filename="test.pdf", page_count=10, pages=[])
        
        validator = QuoteValidator()
        validated_result = validator.validate_quotes(result, evidence, doc)
        
        # Should match despite quote style differences
        assert len(validated_result.relevant_quotes) == 1
        assert validated_result.relevant_quotes[0].validated is True
        assert validated_result.relevant_quotes[0].page_start == 3


class TestQuoteNormalization:
    """Test normalization function."""
    
    def test_normalize_basic(self):
        """Test basic normalization."""
        validator = QuoteValidator()
        
        text = "This  Has   Multiple    Spaces"
        normalized = validator._normalize_for_matching(text)
        assert normalized == "this has multiple spaces"
    
    def test_normalize_unicode_quotes_explicit_codepoints(self):
        """Test Unicode quote normalization using explicit codepoints."""
        validator = QuoteValidator()
        
        # U+201C (") U+201D (") → straight double quote
        # U+2018 (') U+2019 (') → straight single quote
        text = "\u201cHello\u201d and \u2018world\u2019"
        normalized = validator._normalize_for_matching(text)
        assert '\u201c' not in normalized  # Left double quote removed
        assert '\u201d' not in normalized  # Right double quote removed
        assert '\u2018' not in normalized  # Left single quote removed
        assert '\u2019' not in normalized  # Right single quote removed
        assert '"hello" and \'world\'' == normalized
    
    def test_normalize_dashes_explicit_codepoints(self):
        """Test dash normalization using explicit codepoints."""
        validator = QuoteValidator()
        
        # U+2013 (–) U+2014 (—) → hyphen-minus
        text = "Range: 10\u201320 or 30\u201440"
        normalized = validator._normalize_for_matching(text)
        assert '\u2013' not in normalized  # En dash removed
        assert '\u2014' not in normalized  # Em dash removed
        assert "range: 10-20 or 30-40" == normalized


class TestCrossChunkMatching:
    """Test cross-chunk quote matching."""
    
    def test_quote_spanning_adjacent_chunks(self):
        """Test that quotes spanning adjacent chunks are found with correct page range."""
        # Create evidence chunks where a quote spans two chunks
        evidence = [
            EvidenceChunk(
                chunk_id="doc:chunk_0",
                text="The vendor must maintain proper security controls including",
                normalized_text="the vendor must maintain proper security controls including",
                page_start=5,
                page_end=5,
                char_range=(0, 100),
                relevance_score=0.9
            ),
            EvidenceChunk(
                chunk_id="doc:chunk_1",
                text="multi-factor authentication and regular security audits.",
                normalized_text="multi-factor authentication and regular security audits",
                page_start=6,
                page_end=6,
                char_range=(101, 200),
                relevance_score=0.85
            )
        ]
        
        # Quote that spans both chunks
        result = ComplianceResult(
            compliance_question="Does the contract require security controls?",
            compliance_state=ComplianceState.FULLY_COMPLIANT,
            confidence=85,
            relevant_quotes=[
                Quote(
                    text="security controls including multi-factor authentication",
                    page_start=0,
                    page_end=0,
                    validated=False
                )
            ],
            rationale="Security controls are specified."
        )
        
        doc = DocumentArtifact(filename="test.pdf", page_count=10, pages=[])
        
        validator = QuoteValidator()
        validated_result = validator.validate_quotes(result, evidence, doc)
        
        # Should find the quote spanning two chunks
        assert len(validated_result.relevant_quotes) == 1
        quote = validated_result.relevant_quotes[0]
        assert quote.validated is True
        # Page range should span both chunks (5-6)
        assert quote.page_start == 5
        assert quote.page_end == 6
        # Confidence should be maintained
        assert validated_result.confidence == 85
