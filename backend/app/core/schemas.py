"""Canonical data models and schemas for the Contract Analyzer pipeline."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Enumerations
# ============================================================================

class ComplianceState(str, Enum):
    """Compliance state enumeration - exact values required by spec."""
    FULLY_COMPLIANT = "Fully Compliant"
    PARTIALLY_COMPLIANT = "Partially Compliant"
    NON_COMPLIANT = "Non-Compliant"


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Document Artifacts (Canonical Data Format)
# ============================================================================

class PageArtifact(BaseModel):
    """
    Represents a single page from a document with text and provenance.
    
    Attributes:
        page_number: 1-indexed page number
        raw_text: Original extracted text with formatting
        normalized_text: Lowercased, whitespace-collapsed text for matching
        char_offset_start: Character offset in full document (0-indexed)
        char_offset_end: End character offset in full document
        word_count: Number of words on page
    """
    model_config = ConfigDict(frozen=False)
    
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    raw_text: str = Field(..., description="Original extracted text")
    normalized_text: str = Field(default="", description="Normalized text for matching")
    char_offset_start: int = Field(..., ge=0, description="Start character offset in document")
    char_offset_end: int = Field(..., ge=0, description="End character offset in document")
    word_count: int = Field(default=0, ge=0, description="Word count")
    
    @field_validator("char_offset_end")
    @classmethod
    def validate_offsets(cls, v: int, info) -> int:
        """Ensure end offset >= start offset."""
        if "char_offset_start" in info.data and v < info.data["char_offset_start"]:
            raise ValueError("char_offset_end must be >= char_offset_start")
        return v


class DocumentArtifact(BaseModel):
    """
    Canonical representation of a parsed document.
    
    This is the primary data structure that flows through the pipeline.
    All downstream processing (chunking, retrieval, validation) operates on this.
    """
    model_config = ConfigDict(frozen=False)
    
    doc_id: UUID = Field(default_factory=uuid4, description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    page_count: int = Field(..., ge=1, description="Total number of pages")
    pages: List[PageArtifact] = Field(default_factory=list, description="List of page artifacts")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    
    @field_validator("pages")
    @classmethod
    def validate_page_count(cls, v: List[PageArtifact], info) -> List[PageArtifact]:
        """Ensure pages list matches page_count."""
        if "page_count" in info.data and len(v) != info.data["page_count"]:
            raise ValueError(f"Expected {info.data['page_count']} pages, got {len(v)}")
        return v
    
    def get_full_text(self) -> str:
        """Get concatenated raw text from all pages."""
        return "\n\n".join(page.raw_text for page in self.pages)
    
    def get_normalized_text(self) -> str:
        """Get concatenated normalized text from all pages."""
        return " ".join(page.normalized_text for page in self.pages)
    
    def get_text_range(self, char_start: int, char_end: int) -> str:
        """Extract text from character range."""
        full_text = self.get_full_text()
        return full_text[char_start:char_end]
    
    def find_page_range(self, char_start: int, char_end: int) -> tuple[int, int]:
        """
        Find page range for given character offsets.
        
        Returns:
            Tuple of (page_start, page_end) - both 1-indexed
        """
        page_start = None
        page_end = None
        
        for page in self.pages:
            if page_start is None and char_start >= page.char_offset_start and char_start < page.char_offset_end:
                page_start = page.page_number
            if char_end > page.char_offset_start and char_end <= page.char_offset_end:
                page_end = page.page_number
                break
        
        # Fallback to first/last page if not found
        if page_start is None:
            page_start = self.pages[0].page_number if self.pages else 1
        if page_end is None:
            page_end = self.pages[-1].page_number if self.pages else page_start
        
        return (page_start, page_end)


# ============================================================================
# Evidence and Chunking
# ============================================================================

class Chunk(BaseModel):
    """
    Text chunk with page provenance.
    
    Used for breaking documents into manageable pieces for retrieval.
    """
    model_config = ConfigDict(frozen=False)
    
    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Original chunk text")
    normalized_text: str = Field(..., description="Normalized chunk text")
    page_start: int = Field(..., ge=1, description="Starting page number (1-indexed)")
    page_end: int = Field(..., ge=1, description="Ending page number (1-indexed)")
    char_range: tuple[int, int] = Field(..., description="Character range in full document")
    
    @field_validator("page_end")
    @classmethod
    def validate_page_range(cls, v: int, info) -> int:
        """Ensure page_end >= page_start."""
        if "page_start" in info.data and v < info.data["page_start"]:
            raise ValueError("page_end must be >= page_start")
        return v


class EvidenceChunk(Chunk):
    """
    Evidence chunk with retrieval relevance score.
    
    Extends Chunk with relevance score added during retrieval phase.
    """
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Retrieval relevance score")
    
    model_config = ConfigDict(frozen=False)


# ============================================================================
# Compliance Analysis Output
# ============================================================================

class Quote(BaseModel):
    """
    Validated quote with page provenance.
    
    Quotes must pass deterministic validation (exact substring match after normalization).
    """
    model_config = ConfigDict(frozen=False)
    
    text: str = Field(..., description="Quote text (verbatim from document)")
    page_start: int = Field(..., ge=1, description="Starting page number")
    page_end: int = Field(..., ge=1, description="Ending page number")
    validated: bool = Field(default=False, description="Whether quote was validated against source")
    
    @field_validator("page_end")
    @classmethod
    def validate_page_range(cls, v: int, info) -> int:
        """Ensure page_end >= page_start."""
        if "page_start" in info.data and v < info.data["page_start"]:
            raise ValueError("page_end must be >= page_start")
        return v


class ComplianceResult(BaseModel):
    """
    Result of compliance analysis for a single requirement.
    
    This is the primary output schema returned to clients.
    """
    model_config = ConfigDict(frozen=False)
    
    compliance_question: str = Field(..., description="The compliance requirement being assessed")
    compliance_state: ComplianceState = Field(..., description="Compliance state")
    confidence: int = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    relevant_quotes: List[Quote] = Field(default_factory=list, description="Supporting quotes from document")
    rationale: str = Field(..., description="Explanation of the compliance determination")
    evidence_chunks_used: List[str] = Field(default_factory=list, description="IDs of evidence chunks used")


# ============================================================================
# Job Management
# ============================================================================

class Job(BaseModel):
    """
    Represents an analysis job.
    
    Tracks the complete lifecycle of a contract analysis request.
    """
    model_config = ConfigDict(frozen=False)
    
    job_id: UUID = Field(default_factory=uuid4, description="Unique job identifier")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current job status")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    stage: str = Field(default="", description="Current processing stage")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    completed_at: Optional[datetime] = Field(default=None, description="Completion time")
    
    # Input data
    filename: str = Field(..., description="Uploaded filename")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    
    # Processing artifacts (populated during processing)
    document_artifact: Optional[DocumentArtifact] = Field(default=None, description="Parsed document")
    chunks: List["Chunk"] = Field(default_factory=list, description="Document chunks for chat/reuse")
    results: List[ComplianceResult] = Field(default_factory=list, description="Analysis results")
    
    # Performance metrics
    timings_ms: dict = Field(default_factory=dict, description="Timing measurements in milliseconds")
    
    # Error handling
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    def update_progress(self, progress: int, stage: str = "") -> None:
        """Update job progress and stage."""
        self.progress = max(0, min(100, progress))
        if stage:
            self.stage = stage
        self.updated_at = datetime.utcnow()
    
    def update_status(self, status: JobStatus, error_message: Optional[str] = None) -> None:
        """Update job status."""
        self.status = status
        self.updated_at = datetime.utcnow()
        if status == JobStatus.COMPLETED:
            self.completed_at = datetime.utcnow()
            self.progress = 100
        elif status == JobStatus.FAILED:
            self.error_message = error_message
        
    def add_result(self, result: ComplianceResult) -> None:
        """Add a compliance result."""
        self.results.append(result)
        self.updated_at = datetime.utcnow()


# ============================================================================
# API Request/Response Models
# ============================================================================

class UploadResponse(BaseModel):
    """Response from file upload endpoint."""
    job_id: UUID = Field(..., description="Job identifier for tracking")
    status: JobStatus = Field(..., description="Initial job status")
    message: str = Field(default="File uploaded successfully")


class JobStatusResponse(BaseModel):
    """Response from status check endpoint."""
    job_id: UUID = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    stage: Optional[str] = Field(default=None, description="Current processing stage")
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    timings_ms: Optional[dict] = Field(default=None, description="Timing measurements (if available)")


class JobResultResponse(BaseModel):
    """Response from result retrieval endpoint."""
    model_config = ConfigDict(protected_namespaces=())
    
    job_id: UUID = Field(..., description="Job identifier")
    filename: str = Field(..., description="Original filename")
    status: JobStatus = Field(..., description="Job status")
    results: List[ComplianceResult] = Field(..., description="Compliance analysis results")
    completed_at: Optional[datetime] = Field(default=None, description="Completion time")
    llm_mode: Optional[str] = Field(default=None, description="LLM mode used")
    model_name: Optional[str] = Field(default=None, description="Model name used")
    needs_ocr: Optional[bool] = Field(default=None, description="Whether document needs OCR")
    timings_ms: Optional[dict] = Field(default=None, description="Timing measurements in milliseconds")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Additional details")


# ============================================================================
# Chat Models (Bonus Feature)
# ============================================================================

class ChatMessage(BaseModel):
    """Individual chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")


class ChatSession(BaseModel):
    """Chat session over a completed job."""
    model_config = ConfigDict(frozen=False)
    
    session_id: UUID = Field(default_factory=uuid4, description="Chat session identifier")
    job_id: UUID = Field(..., description="Associated job identifier")
    messages: List[ChatMessage] = Field(default_factory=list, description="Conversation history")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        message = ChatMessage(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.utcnow()


class ChatStartRequest(BaseModel):
    """Request to start a chat session."""
    job_id: UUID = Field(..., description="Job ID to chat about")


class ChatStartResponse(BaseModel):
    """Response from chat start."""
    session_id: UUID = Field(..., description="Created session ID")
    job_id: UUID = Field(..., description="Associated job ID")
    message: str = Field(default="Chat session created", description="Status message")


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    session_id: UUID = Field(..., description="Chat session ID")
    message: str = Field(..., min_length=1, max_length=1000, description="User message")


class ChatMessageResponse(BaseModel):
    """Response from chat message."""
    answer: str = Field(..., description="Assistant's answer")
    relevant_quotes: List[Quote] = Field(default_factory=list, description="Supporting quotes with page ranges")
    confidence: int = Field(..., ge=0, le=100, description="Answer confidence (0-100)")
