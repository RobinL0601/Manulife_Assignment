"""Integration tests for job processing."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import fitz  # PyMuPDF

from app.core.schemas import Job, JobStatus
from app.core.storage import job_store
from app.pipeline.job_processor import process_job


def create_test_pdf_bytes(pages_content: list[str]) -> bytes:
    """Create a simple PDF with given page contents."""
    doc = fitz.open()
    
    for content in pages_content:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), content)
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    return pdf_bytes


class TestJobProcessor:
    """Integration tests for job processing."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_job_processing(self):
        """Test complete job processing with synthetic PDF and mocked LLM."""
        # Create synthetic PDF with content relevant to all 5 requirements
        pdf_content = [
            """CONTRACT AGREEMENT
            
Section 1: Password Management
All user passwords must be at least 12 characters long with complexity requirements.
Passwords must include uppercase, lowercase, numbers, and special characters.
Multi-factor authentication (MFA) is required for all user accounts.
""",
            """Section 2: IT Asset Management
All IT assets must be tracked in the central inventory system.
Quarterly reconciliation of assets is mandatory.
Asset lifecycle procedures must be documented and followed.
""",
            """Section 3: Security Training
Annual security awareness training is required for all employees.
Background checks must be completed before granting system access.
Training completion certificates must be maintained.
""",
            """Section 4: Data Encryption
All data in transit must use TLS 1.2 or higher encryption.
Certificate management procedures must be documented.
Only approved cipher suites may be used.
""",
            """Section 5: Access Control
Single sign-on (SSO) with SAML must be implemented.
Role-based access control (RBAC) is required.
Session logging must be enabled for all privileged access.
Bastion hosts must be used for administrative access.
"""
        ]
        
        pdf_bytes = create_test_pdf_bytes(pdf_content)
        
        # Create job
        job = Job(
            filename="test_contract.pdf",
            file_size_bytes=len(pdf_bytes)
        )
        job_id = job_store.save_job(job)
        job_id_str = str(job_id)
        
        # Mock LLM client to return valid JSON for all requirements
        mock_responses = {
            "password_management": """{
  "compliance_state": "Fully Compliant",
  "confidence": 90,
  "relevant_quotes": [
    {"text": "All user passwords must be at least 12 characters long", "page_start": 1, "page_end": 1}
  ],
  "rationale": "Contract explicitly requires password complexity and MFA."
}""",
            "it_asset_management": """{
  "compliance_state": "Fully Compliant",
  "confidence": 85,
  "relevant_quotes": [
    {"text": "Quarterly reconciliation of assets is mandatory", "page_start": 2, "page_end": 2}
  ],
  "rationale": "Asset tracking and quarterly reconciliation are mandated."
}""",
            "security_training": """{
  "compliance_state": "Fully Compliant",
  "confidence": 88,
  "relevant_quotes": [
    {"text": "Annual security awareness training is required", "page_start": 3, "page_end": 3}
  ],
  "rationale": "Training and background checks are explicitly required."
}""",
            "tls_encryption": """{
  "compliance_state": "Fully Compliant",
  "confidence": 92,
  "relevant_quotes": [
    {"text": "All data in transit must use TLS 1.2 or higher", "page_start": 4, "page_end": 4}
  ],
  "rationale": "TLS 1.2+ is explicitly mandated with certificate management."
}""",
            "authn_authz": """{
  "compliance_state": "Fully Compliant",
  "confidence": 95,
  "relevant_quotes": [
    {"text": "Single sign-on (SSO) with SAML must be implemented", "page_start": 5, "page_end": 5}
  ],
  "rationale": "SSO, RBAC, session logging, and bastion hosts are all required."
}"""
        }
        
        # Track which requirement is being analyzed to return appropriate response
        call_count = [0]
        requirement_order = [
            "password_management",
            "it_asset_management", 
            "security_training",
            "tls_encryption",
            "authn_authz"
        ]
        
        async def mock_generate(*args, **kwargs):
            """Mock LLM generate that returns appropriate response."""
            req_id = requirement_order[call_count[0] % 5]
            call_count[0] += 1
            return mock_responses[req_id]
        
        # Patch get_llm_client to return mocked client
        mock_llm_client = AsyncMock()
        mock_llm_client.generate = mock_generate
        
        with patch('app.pipeline.job_processor.get_llm_client', return_value=mock_llm_client):
            # Process job
            await process_job(job_id_str, pdf_bytes)
        
        # Retrieve updated job
        processed_job = job_store.get_job(job_id)
        
        # Verify job completed
        assert processed_job is not None
        assert processed_job.status == JobStatus.COMPLETED
        assert processed_job.progress == 100
        
        # Verify all 5 requirements were analyzed
        assert len(processed_job.results) == 5
        
        # Verify document artifact was created
        assert processed_job.document_artifact is not None
        assert processed_job.document_artifact.page_count == 5
        
        # Verify results have expected structure
        for result in processed_job.results:
            assert result.compliance_state is not None
            assert 0 <= result.confidence <= 100
            assert result.rationale is not None
            # Quotes may or may not be present after validation
    
    @pytest.mark.asyncio
    async def test_job_processing_handles_errors(self):
        """Test that job processing handles errors gracefully."""
        # Create invalid PDF bytes
        invalid_pdf_bytes = b"This is not a PDF file"
        
        # Create job
        job = Job(
            filename="invalid.pdf",
            file_size_bytes=len(invalid_pdf_bytes)
        )
        job_id = job_store.save_job(job)
        job_id_str = str(job_id)
        
        # Process job (should fail gracefully)
        await process_job(job_id_str, invalid_pdf_bytes)
        
        # Retrieve updated job
        processed_job = job_store.get_job(job_id)
        
        # Verify job failed
        assert processed_job is not None
        assert processed_job.status == JobStatus.FAILED
        assert processed_job.error_message is not None
        assert "Processing failed" in processed_job.error_message
