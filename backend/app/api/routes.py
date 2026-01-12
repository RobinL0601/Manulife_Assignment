"""API route handlers for Contract Analyzer."""

from fastapi import APIRouter, File, UploadFile, HTTPException, status, BackgroundTasks
from uuid import UUID

from app.config import settings
from app.core.schemas import (
    UploadResponse,
    JobStatusResponse,
    JobResultResponse,
    Job,
    JobStatus,
    ChatStartRequest,
    ChatStartResponse,
    ChatMessageRequest,
    ChatMessageResponse
)
from app.core.storage import job_store
from app.core.chat_storage import chat_store
from app.services.chat_service import get_chat_service, ChatServiceError
from app.services.llm_client import get_llm_client
from app.utils.logger import setup_logger, log_job_event
from app.pipeline.job_processor import process_job

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix=settings.api_v1_prefix, tags=["contract-analysis"])


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload contract for analysis"
)
async def upload_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF contract file")
) -> UploadResponse:
    """
    Upload a PDF contract for compliance analysis.
    
    Creates a new analysis job and returns a job ID for tracking.
    Processing happens asynchronously in the background.
    
    Args:
        file: PDF file upload
        
    Returns:
        UploadResponse with job_id and initial status
        
    Raises:
        HTTPException 400: Invalid file type or size
        HTTPException 500: Server error
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Read file content
    try:
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum of {settings.max_upload_size_mb}MB"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )
        
    except Exception as e:
        logger.error(f"Error reading uploaded file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read uploaded file"
        )
    
    # Create job
    job = Job(
        filename=file.filename,
        file_size_bytes=file_size,
        status=JobStatus.PENDING
    )
    
    # Save to store
    job_id = job_store.save_job(job)
    log_job_event(logger, str(job_id), "Created", filename=file.filename, size=file_size)
    
    # Trigger background processing
    background_tasks.add_task(process_job, str(job_id), content)
    
    return UploadResponse(
        job_id=job_id,
        status=job.status,
        message="File uploaded successfully. Processing started."
    )


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status"
)
async def get_job_status(job_id: UUID) -> JobStatusResponse:
    """
    Get the current status of an analysis job.
    
    Args:
        job_id: Job UUID from upload response
        
    Returns:
        JobStatusResponse with current status and progress
        
    Raises:
        HTTPException 404: Job not found
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        stage=job.stage if job.stage else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
        timings_ms=job.timings_ms if job.timings_ms else None
    )


@router.get(
    "/result/{job_id}",
    response_model=JobResultResponse,
    summary="Get analysis results"
)
async def get_job_result(job_id: UUID) -> JobResultResponse:
    """
    Get the compliance analysis results for a completed job.
    
    Args:
        job_id: Job UUID from upload response
        
    Returns:
        JobResultResponse with compliance results
        
    Raises:
        HTTPException 404: Job not found
        HTTPException 425: Job not yet completed (still processing)
        HTTPException 500: Job failed
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    if job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job failed: {job.error_message or 'Unknown error'}"
        )
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Job is still {job.status.value}. Current progress: {job.progress}%"
        )
    
    # Extract metadata
    llm_mode = settings.llm_mode.value
    model_name = settings.external_model if settings.llm_mode.value == 'external' else settings.local_model
    needs_ocr = job.document_artifact.metadata.get("needs_ocr", False) if job.document_artifact else False
    
    return JobResultResponse(
        job_id=job.job_id,
        filename=job.filename,
        status=job.status,
        results=job.results,
        completed_at=job.completed_at,
        llm_mode=llm_mode,
        model_name=model_name,
        needs_ocr=needs_ocr,
        timings_ms=job.timings_ms if job.timings_ms else None
    )


# ============================================================================
# Chat Endpoints (Bonus Feature)
# ============================================================================

@router.post(
    "/chat/start",
    response_model=ChatStartResponse,
    summary="Start a chat session (bonus)"
)
async def start_chat(request: ChatStartRequest) -> ChatStartResponse:
    """
    Start a new chat session for a completed job.
    
    Args:
        request: ChatStartRequest with job_id
        
    Returns:
        ChatStartResponse with session_id
        
    Raises:
        HTTPException 404: Job not found
        HTTPException 409: Job not completed yet
    """
    job = job_store.get_job(request.job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {request.job_id} not found"
        )
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot start chat: job is {job.status.value}. Only completed jobs can be chatted with."
        )
    
    # Create chat session
    session_id = chat_store.create_session(job_id=request.job_id)
    
    logger.info(f"Chat session started: session={session_id}, job={request.job_id}")
    
    return ChatStartResponse(
        session_id=session_id,
        job_id=request.job_id,
        message="Chat session created. Ask questions about the contract."
    )


@router.post(
    "/chat/message",
    response_model=ChatMessageResponse,
    summary="Send a chat message (bonus)"
)
async def send_chat_message(request: ChatMessageRequest) -> ChatMessageResponse:
    """
    Send a message in a chat session and get AI response.
    
    Args:
        request: ChatMessageRequest with session_id and message
        
    Returns:
        ChatMessageResponse with answer, quotes, confidence
        
    Raises:
        HTTPException 404: Session or job not found
        HTTPException 400: Processing error
    """
    # Get session
    session = chat_store.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {request.session_id} not found"
        )
    
    # Get associated job
    job = job_store.get_job(session.job_id)
    if not job or not job.document_artifact or not job.chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job data not available for chat"
        )
    
    # Append user message to session
    chat_store.append_message(request.session_id, role="user", content=request.message)
    
    try:
        # Generate answer using chat service
        llm_client = get_llm_client()
        chat_service = get_chat_service(llm_client)
        
        response = await chat_service.answer(
            session=session,
            user_message=request.message,
            doc=job.document_artifact,
            chunks=job.chunks
        )
        
        # Append assistant response to session
        chat_store.append_message(
            request.session_id, 
            role="assistant", 
            content=response.answer
        )
        
        logger.info(
            f"Chat message processed: session={request.session_id}, "
            f"confidence={response.confidence}, quotes={len(response.relevant_quotes)}"
        )
        
        return response
        
    except ChatServiceError as e:
        logger.error(f"Chat service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chat response: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health check"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "llm_mode": settings.llm_mode.value
    }
