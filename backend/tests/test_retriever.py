"""Tests for BM25 retriever functionality."""

import pytest

from app.core.schemas import Chunk, EvidenceChunk
from app.pipeline.retriever import BM25Retriever, REQUIREMENT_QUERIES, get_requirement_ids


class TestBM25Retriever:
    """Test BM25Retriever class."""
    
    def test_retriever_returns_evidence_chunks_with_page_info(self):
        """Test that retriever returns EvidenceChunks with correct page information."""
        # Create test chunks with different page ranges
        chunks = [
            Chunk(
                chunk_id="doc:chunk_0",
                text="This document discusses password policies and requirements.",
                normalized_text="this document discusses password policies and requirements",
                page_start=1,
                page_end=1,
                char_range=(0, 100)
            ),
            Chunk(
                chunk_id="doc:chunk_1",
                text="Asset management procedures are defined in this section.",
                normalized_text="asset management procedures are defined in this section",
                page_start=2,
                page_end=2,
                char_range=(101, 200)
            ),
            Chunk(
                chunk_id="doc:chunk_2",
                text="Training requirements for security awareness are mandatory.",
                normalized_text="training requirements for security awareness are mandatory",
                page_start=3,
                page_end=4,
                char_range=(201, 300)
            )
        ]
        
        retriever = BM25Retriever()
        results = retriever.retrieve(
            query="password_management",
            chunks=chunks,
            top_k=2
        )
        
        # Should return EvidenceChunk objects
        assert len(results) == 2
        assert all(isinstance(chunk, EvidenceChunk) for chunk in results)
        
        # Check that page information is preserved
        for chunk in results:
            assert chunk.page_start >= 1
            assert chunk.page_end >= chunk.page_start
            assert chunk.chunk_id.startswith("doc:")
        
        # First result should be the password chunk
        assert results[0].chunk_id == "doc:chunk_0"
        assert results[0].page_start == 1
        assert results[0].page_end == 1
        assert results[0].relevance_score > 0
        
        # Check that original text is preserved (not mutated)
        assert "password" in results[0].text
        assert results[0].text == chunks[0].text
    
    def test_retriever_finds_tls_requirement(self):
        """Test that TLS requirement retrieves chunks with TLS 1.2 text."""
        # Create synthetic chunks
        chunks = [
            Chunk(
                chunk_id="doc:chunk_0",
                text="All communications must use TLS 1.2 or higher encryption.",
                normalized_text="all communications must use tls 1.2 or higher encryption",
                page_start=5,
                page_end=5,
                char_range=(0, 100)
            ),
            Chunk(
                chunk_id="doc:chunk_1",
                text="Certificates must be renewed annually by the CA.",
                normalized_text="certificates must be renewed annually by the ca",
                page_start=6,
                page_end=6,
                char_range=(101, 200)
            ),
            Chunk(
                chunk_id="doc:chunk_2",
                text="Employee training is required for all personnel.",
                normalized_text="employee training is required for all personnel",
                page_start=7,
                page_end=7,
                char_range=(201, 300)
            ),
            Chunk(
                chunk_id="doc:chunk_3",
                text="Data in transit requires encryption with approved cipher suites.",
                normalized_text="data in transit requires encryption with approved cipher suites",
                page_start=8,
                page_end=8,
                char_range=(301, 400)
            )
        ]
        
        retriever = BM25Retriever()
        results = retriever.retrieve(
            query="tls_encryption",
            chunks=chunks,
            top_k=3
        )
        
        # Should retrieve chunks
        assert len(results) == 3
        
        # TLS 1.2 chunk should be in top results (likely #1 or #2)
        chunk_ids = [chunk.chunk_id for chunk in results]
        assert "doc:chunk_0" in chunk_ids[:2], "TLS 1.2 chunk should be in top 2 results"
        
        # Check that the TLS chunk has high relevance
        tls_chunk = next(c for c in results if c.chunk_id == "doc:chunk_0")
        assert tls_chunk.relevance_score > 0
        assert "TLS 1.2" in tls_chunk.text
        
        # Verify all chunks have scores
        for chunk in results:
            assert chunk.relevance_score >= 0
            assert isinstance(chunk.relevance_score, float)
    
    def test_retriever_handles_empty_chunks(self):
        """Test that retriever handles empty chunk list gracefully."""
        retriever = BM25Retriever()
        results = retriever.retrieve(
            query="password_management",
            chunks=[],
            top_k=5
        )
        
        assert results == []
    
    def test_retriever_with_unknown_requirement(self):
        """Test that retriever handles unknown requirement IDs."""
        chunks = [
            Chunk(
                chunk_id="doc:chunk_0",
                text="Some contract text about various topics.",
                normalized_text="some contract text about various topics",
                page_start=1,
                page_end=1,
                char_range=(0, 100)
            )
        ]
        
        retriever = BM25Retriever()
        # Should not raise error, will use query string as-is
        results = retriever.retrieve(
            query="custom requirement text",
            chunks=chunks,
            top_k=1
        )
        
        assert len(results) == 1
        assert isinstance(results[0], EvidenceChunk)


class TestRequirementQueries:
    """Test requirement query mappings."""
    
    def test_all_requirements_have_queries(self):
        """Test that all requirement IDs have query definitions."""
        requirement_ids = get_requirement_ids()
        
        assert len(requirement_ids) == 5
        assert "password_management" in requirement_ids
        assert "it_asset_management" in requirement_ids
        assert "security_training" in requirement_ids
        assert "tls_encryption" in requirement_ids
        assert "authn_authz" in requirement_ids
    
    def test_queries_contain_relevant_keywords(self):
        """Test that queries contain expected keywords."""
        # Password management should have relevant keywords
        pwd_queries = REQUIREMENT_QUERIES["password_management"]
        assert "password" in pwd_queries
        assert "salted hash" in pwd_queries
        assert "MFA" in pwd_queries
        
        # TLS should have relevant keywords
        tls_queries = REQUIREMENT_QUERIES["tls_encryption"]
        assert "TLS" in tls_queries
        assert "TLS 1.2" in tls_queries
        assert "cipher suite" in tls_queries
        
        # AuthN/AuthZ should have relevant keywords
        authn_queries = REQUIREMENT_QUERIES["authn_authz"]
        assert "SAML" in authn_queries
        assert "OAuth" in authn_queries
        assert "RBAC" in authn_queries
