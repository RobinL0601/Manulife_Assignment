"""
End-to-end job processing orchestration.

Wires together all pipeline stages: Parse → Chunk → Retrieve → Analyze → Validate
"""

import tempfile
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

from app.core.schemas import Job, JobStatus, DocumentArtifact
from app.core.storage import job_store
from app.config import settings
from app.pipeline.parse_pdf import PDFParser
from app.pipeline.chunker import PageBasedChunker
from app.pipeline.retriever import BM25Retriever, get_requirement_ids
from app.pipeline.compliance_analyzer import ComplianceAnalyzer
from app.pipeline.quote_validator import QuoteValidator
from app.services.llm_client import get_llm_client
from app.utils.logger import setup_logger, log_job_event

logger = setup_logger(__name__)


async def process_job(job_id: str, pdf_bytes: bytes) -> None:
    """
    Process a compliance analysis job end-to-end.
    
    Pipeline stages:
    1. Parse PDF → DocumentArtifact (10% progress)
    2. Chunk document → List[Chunk] (20% progress)
    3. For each of 5 requirements (20% → 100%):
       a. Retrieve evidence → List[EvidenceChunk]
       b. Analyze with LLM → ComplianceResult
       c. Validate quotes → ComplianceResult (validated)
    4. Save results and mark COMPLETED
    
    Args:
        job_id: Job UUID string
        pdf_bytes: PDF file content as bytes
    """
    # Convert string job_id to UUID for lookup
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        logger.error(f"Invalid job_id format: {job_id}")
        return
    
    job = job_store.get_job(job_uuid)
    if not job:
        logger.error(f"Job {job_id} not found")
        return
    
    try:
        # Start timing
        start_time = time.time()
        timings = {}
        
        log_job_event(logger, job_id, "Started processing")
        job.update_status(JobStatus.PROCESSING)
        job_store.update_job(job_uuid, job)
        
        # Stage 1: Parse PDF
        log_job_event(logger, job_id, "Stage 1: Parsing PDF")
        job.update_progress(5, "Parsing PDF")
        job_store.update_job(job_uuid, job)
        
        parse_start = time.time()
        document = await _parse_pdf(job_id, pdf_bytes, job)
        timings['parse_ms'] = int((time.time() - parse_start) * 1000)
        
        job.document_artifact = document
        job.update_progress(10)
        job_store.update_job(job_uuid, job)
        
        # Check if OCR needed
        if document.metadata.get("needs_ocr"):
            logger.warning(
                f"Job {job_id}: Document may need OCR (avg chars/page: "
                f"{document.metadata.get('avg_chars_per_page', 0)})"
            )
            # Proceed anyway - results will likely have low confidence
        
        # Stage 2: Chunk document
        log_job_event(logger, job_id, "Stage 2: Chunking document")
        job.update_progress(15, "Chunking document")
        job_store.update_job(job_uuid, job)
        
        chunk_start = time.time()
        chunks = _chunk_document(document)
        timings['chunk_ms'] = int((time.time() - chunk_start) * 1000)
        
        # Store chunks for chat functionality
        job.chunks = chunks
        job.update_progress(20)
        job_store.update_job(job_uuid, job)
        
        # Stage 3-5: Process each requirement
        requirement_ids = get_requirement_ids()
        llm_client = get_llm_client()
        retriever = BM25Retriever()
        analyzer = ComplianceAnalyzer(llm_client=llm_client)
        validator = QuoteValidator()
        
        progress_per_requirement = 80 // len(requirement_ids)  # 80% / 5 = 16%
        
        # Initialize timing accumulators
        retrieve_total_ms = 0
        llm_total_ms = 0
        validate_total_ms = 0
        
        for i, req_id in enumerate(requirement_ids, 1):
            log_job_event(
                logger, job_id,
                f"Stage 3-5 ({i}/{len(requirement_ids)}): Processing requirement",
                requirement=req_id
            )
            
            # Set stage for this requirement (will persist during slow LLM call)
            stage_text = f"Analyzing requirement {i}/{len(requirement_ids)}"
            job.update_progress(20 + ((i-1) * progress_per_requirement), stage_text)
            job_store.update_job(job_uuid, job)
            
            # 3a. Retrieve evidence (fast)
            retrieve_start = time.time()
            evidence_chunks = retriever.retrieve(
                query=req_id,
                chunks=chunks,
                top_k=5
            )
            retrieve_total_ms += int((time.time() - retrieve_start) * 1000)
            
            # 3b. Analyze with LLM (slow - stage text will be visible here)
            llm_start = time.time()
            result = await analyzer.analyze(
                question=req_id,
                evidence_chunks=evidence_chunks
            )
            llm_total_ms += int((time.time() - llm_start) * 1000)
            
            # 3c. Validate quotes (fast)
            validate_start = time.time()
            validated_result = validator.validate_quotes(
                result=result,
                evidence=evidence_chunks,
                doc=document
            )
            validate_total_ms += int((time.time() - validate_start) * 1000)
            
            # Add to job results
            job.add_result(validated_result)
            
            # Update progress (keep stage text)
            current_progress = 20 + (i * progress_per_requirement)
            job.update_progress(current_progress)
            job_store.update_job(job_uuid, job)
        
        # Mark complete
        job.update_progress(100, "Finalizing results")
        job_store.update_job(job_uuid, job)
        
        # Save timings
        total_ms = int((time.time() - start_time) * 1000)
        timings['retrieve_total_ms'] = retrieve_total_ms
        timings['llm_total_ms'] = llm_total_ms
        timings['validate_total_ms'] = validate_total_ms
        timings['total_ms'] = total_ms
        job.timings_ms = timings
        
        job.update_status(JobStatus.COMPLETED)
        job.stage = "Completed"
        job_store.update_job(job_uuid, job)
        
        log_job_event(
            logger, job_id, "Completed",
            results_count=len(job.results),
            llm_mode=settings.llm_mode.value,
            model=settings.external_model if settings.llm_mode.value == 'external' else settings.local_model,
            total_ms=total_ms
        )
        
    except Exception as e:
        # Error handling - set job as failed with safe message
        error_msg = f"Processing failed: {str(e)}"
        logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True)
        
        job.update_status(JobStatus.FAILED, error_message=error_msg)
        job_store.update_job(job_uuid, job)
        
        log_job_event(logger, job_id, "Failed", error=error_msg)


async def _parse_pdf(
    job_id: str,
    pdf_bytes: bytes,
    job: Job
) -> DocumentArtifact:
    """
    Parse PDF to DocumentArtifact.
    
    Args:
        job_id: Job UUID
        pdf_bytes: PDF content
        job: Job object
        
    Returns:
        DocumentArtifact
    """
    try:
        parser = PDFParser()
        
        # Write bytes to temp file (PyMuPDF needs file path or bytes)
        document = await parser.parse(pdf_bytes)
        
        log_job_event(
            logger, job_id, "PDF parsed",
            pages=document.page_count,
            needs_ocr=document.metadata.get("needs_ocr", False)
        )
        
        return document
        
    except Exception as e:
        logger.error(f"PDF parsing failed for job {job_id}: {str(e)}")
        raise


def _chunk_document(document: DocumentArtifact) -> list:
    """
    Chunk document into chunks with page provenance.
    
    Args:
        document: Parsed document
        
    Returns:
        List of Chunk objects
    """
    chunker = PageBasedChunker(pages_per_chunk=1, overlap_pages=0)
    chunks = chunker.chunk(document)
    
    logger.info(f"Created {len(chunks)} chunks from document")
    
    return chunks
