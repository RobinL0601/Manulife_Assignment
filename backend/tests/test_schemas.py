"""Tests for core data schemas."""

import pytest
from uuid import uuid4
from datetime import datetime

from app.core.schemas import (
    PageArtifact,
    DocumentArtifact,
    Chunk,
    EvidenceChunk,
    Quote,
    ComplianceResult,
    ComplianceState,
    Job,
    JobStatus
)


class TestPageArtifact:
    """Test PageArtifact model."""
    
    def test_create_page_artifact(self):
        """Test creating a valid PageArtifact."""
        page = PageArtifact(
            page_number=1,
            raw_text="This is a test page.",
            normalized_text="this is a test page",
            char_offset_start=0,
            char_offset_end=20,
            word_count=5
        )
        
        assert page.page_number == 1
        assert page.raw_text == "This is a test page."
        assert page.word_count == 5
    
    def test_invalid_char_offsets(self):
        """Test that invalid char offsets raise validation error."""
        with pytest.raises(ValueError):
            PageArtifact(
                page_number=1,
                raw_text="Test",
                char_offset_start=10,
                char_offset_end=5,  # End before start
                word_count=1
            )


class TestDocumentArtifact:
    """Test DocumentArtifact model."""
    
    def test_create_document_artifact(self):
        """Test creating a valid DocumentArtifact."""
        pages = [
            PageArtifact(
                page_number=1,
                raw_text="Page 1",
                normalized_text="page 1",
                char_offset_start=0,
                char_offset_end=6,
                word_count=2
            ),
            PageArtifact(
                page_number=2,
                raw_text="Page 2",
                normalized_text="page 2",
                char_offset_start=7,
                char_offset_end=13,
                word_count=2
            )
        ]
        
        doc = DocumentArtifact(
            filename="test.pdf",
            page_count=2,
            pages=pages
        )
        
        assert doc.filename == "test.pdf"
        assert doc.page_count == 2
        assert len(doc.pages) == 2
        assert isinstance(doc.doc_id, uuid4().__class__)
    
    def test_get_full_text(self):
        """Test getting full document text."""
        pages = [
            PageArtifact(
                page_number=1,
                raw_text="Page 1 text",
                char_offset_start=0,
                char_offset_end=11
            ),
            PageArtifact(
                page_number=2,
                raw_text="Page 2 text",
                char_offset_start=12,
                char_offset_end=23
            )
        ]
        
        doc = DocumentArtifact(
            filename="test.pdf",
            page_count=2,
            pages=pages
        )
        
        full_text = doc.get_full_text()
        assert "Page 1 text" in full_text
        assert "Page 2 text" in full_text
    
    def test_find_page_range(self):
        """Test finding page range for character offsets."""
        pages = [
            PageArtifact(
                page_number=1,
                raw_text="A" * 100,
                char_offset_start=0,
                char_offset_end=100
            ),
            PageArtifact(
                page_number=2,
                raw_text="B" * 100,
                char_offset_start=100,
                char_offset_end=200
            )
        ]
        
        doc = DocumentArtifact(
            filename="test.pdf",
            page_count=2,
            pages=pages
        )
        
        # Text in first page
        page_start, page_end = doc.find_page_range(10, 50)
        assert page_start == 1
        assert page_end == 1
        
        # Text in second page
        page_start, page_end = doc.find_page_range(150, 180)
        assert page_start == 2
        assert page_end == 2


class TestComplianceResult:
    """Test ComplianceResult model."""
    
    def test_create_compliance_result(self):
        """Test creating a valid ComplianceResult."""
        quote = Quote(
            text="Password must be 12 characters",
            page_start=5,
            page_end=5,
            validated=True
        )
        
        result = ComplianceResult(
            compliance_question="Does the contract require password policies?",
            compliance_state=ComplianceState.FULLY_COMPLIANT,
            confidence=85,
            relevant_quotes=[quote],
            rationale="Section 3.2 explicitly requires password policies",
            evidence_chunks_used=["chunk_1", "chunk_2"]
        )
        
        assert result.compliance_state == ComplianceState.FULLY_COMPLIANT
        assert result.confidence == 85
        assert len(result.relevant_quotes) == 1
        assert result.relevant_quotes[0].validated is True


class TestJob:
    """Test Job model."""
    
    def test_create_job(self):
        """Test creating a job."""
        job = Job(
            filename="contract.pdf",
            file_size_bytes=1024000
        )
        
        assert job.status == JobStatus.PENDING
        assert job.progress == 0
        assert job.filename == "contract.pdf"
        assert isinstance(job.job_id, uuid4().__class__)
    
    def test_update_status(self):
        """Test updating job status."""
        job = Job(
            filename="test.pdf",
            file_size_bytes=1000
        )
        
        job.update_status(JobStatus.PROCESSING)
        assert job.status == JobStatus.PROCESSING
        
        job.update_status(JobStatus.COMPLETED)
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100
        assert job.completed_at is not None
    
    def test_add_result(self):
        """Test adding compliance results to job."""
        job = Job(
            filename="test.pdf",
            file_size_bytes=1000
        )
        
        result = ComplianceResult(
            compliance_question="Test question?",
            compliance_state=ComplianceState.FULLY_COMPLIANT,
            confidence=90,
            rationale="Test rationale"
        )
        
        job.add_result(result)
        assert len(job.results) == 1
        assert job.results[0].compliance_question == "Test question?"
