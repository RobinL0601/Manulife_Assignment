"""
Pipeline interface definitions.

This module defines abstract interfaces for each stage of the
evidence-first compliance analysis pipeline.
"""

from abc import ABC, abstractmethod
from typing import List

from app.core.schemas import (
    DocumentArtifact,
    Chunk,
    EvidenceChunk,
    ComplianceResult
)


class IParser(ABC):
    """Interface for PDF parsing to DocumentArtifact."""
    
    @abstractmethod
    async def parse(self, pdf_path: str) -> DocumentArtifact:
        """
        Parse PDF file to DocumentArtifact.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            DocumentArtifact with pages and metadata
            
        Raises:
            ParserError: If parsing fails
        """
        pass


class IChunker(ABC):
    """Interface for document chunking."""
    
    @abstractmethod
    def chunk(self, document: DocumentArtifact) -> List[Chunk]:
        """
        Break document into chunks with page provenance.
        
        Args:
            document: DocumentArtifact to chunk
            
        Returns:
            List of Chunk objects with page references
        """
        pass


class IRetriever(ABC):
    """Interface for evidence retrieval."""
    
    @abstractmethod
    def retrieve(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: int = 5
    ) -> List[EvidenceChunk]:
        """
        Retrieve top-k most relevant chunks for a query.
        
        Args:
            query: Compliance question or search query
            chunks: List of document chunks
            top_k: Number of chunks to retrieve
            
        Returns:
            List of EvidenceChunk with relevance scores
        """
        pass


class IComplianceAnalyzer(ABC):
    """Interface for compliance analysis using LLM."""
    
    @abstractmethod
    async def analyze(
        self,
        question: str,
        evidence_chunks: List[EvidenceChunk]
    ) -> ComplianceResult:
        """
        Analyze compliance based on evidence chunks.
        
        Args:
            question: Compliance requirement question
            evidence_chunks: Retrieved evidence chunks
            
        Returns:
            ComplianceResult with state, confidence, quotes, and rationale
            
        Raises:
            AnalyzerError: If analysis fails
        """
        pass


class IQuoteValidator(ABC):
    """Interface for quote validation."""
    
    @abstractmethod
    def validate(
        self,
        quotes: List[str],
        document: DocumentArtifact
    ) -> List[dict]:
        """
        Validate quotes against source document.
        
        Uses deterministic normalization + exact substring matching.
        
        Args:
            quotes: List of quote strings from LLM output
            document: Source DocumentArtifact
            
        Returns:
            List of dicts with {text, page_start, page_end, validated}
        """
        pass


# Exception classes for pipeline errors

class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass


class ParserError(PipelineError):
    """Raised when PDF parsing fails."""
    pass


class ChunkerError(PipelineError):
    """Raised when chunking fails."""
    pass


class RetrieverError(PipelineError):
    """Raised when retrieval fails."""
    pass


class AnalyzerError(PipelineError):
    """Raised when analysis fails."""
    pass


class ValidatorError(PipelineError):
    """Raised when validation fails."""
    pass
