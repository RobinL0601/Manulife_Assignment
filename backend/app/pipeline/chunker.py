"""
Document chunking implementation.

Provides IChunker interface implementation for breaking DocumentArtifact
into Chunk objects with page provenance.
"""

from typing import List

from app.core.schemas import DocumentArtifact, Chunk
from app.pipeline.interfaces import IChunker, ChunkerError
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class PageBasedChunker(IChunker):
    """
    Chunks documents by page or small page ranges.
    
    Designed for contracts where semantic boundaries often align with pages.
    Implements the IChunker interface.
    """
    
    def __init__(
        self,
        pages_per_chunk: int = 1,
        overlap_pages: int = 0
    ):
        """
        Initialize page-based chunker.
        
        Args:
            pages_per_chunk: Number of pages per chunk (default: 1)
            overlap_pages: Number of pages to overlap between chunks (default: 0)
        """
        if pages_per_chunk < 1:
            raise ValueError("pages_per_chunk must be >= 1")
        if overlap_pages < 0:
            raise ValueError("overlap_pages must be >= 0")
        if overlap_pages >= pages_per_chunk:
            raise ValueError("overlap_pages must be < pages_per_chunk")
        
        self.pages_per_chunk = pages_per_chunk
        self.overlap_pages = overlap_pages
    
    def chunk(self, document: DocumentArtifact) -> List[Chunk]:
        """
        Break document into chunks with page provenance.
        
        Args:
            document: DocumentArtifact to chunk
            
        Returns:
            List of Chunk objects with page references
            
        Raises:
            ChunkerError: If chunking fails
        """
        try:
            chunks = []
            pages = document.pages
            
            if not pages:
                logger.warning(f"Document {document.doc_id} has no pages")
                return chunks
            
            # Calculate stride (pages to advance each chunk)
            stride = max(1, self.pages_per_chunk - self.overlap_pages)
            
            i = 0
            chunk_id = 0
            
            while i < len(pages):
                # Get pages for this chunk
                end_idx = min(i + self.pages_per_chunk, len(pages))
                chunk_pages = pages[i:end_idx]
                
                # Combine text from pages
                chunk_text = "\n\n".join(page.raw_text for page in chunk_pages)
                normalized_text = " ".join(page.normalized_text for page in chunk_pages)
                
                # Get page range
                page_start = chunk_pages[0].page_number
                page_end = chunk_pages[-1].page_number
                
                # Get character range
                char_start = chunk_pages[0].char_offset_start
                char_end = chunk_pages[-1].char_offset_end
                
                # Create Chunk object
                chunk = Chunk(
                    chunk_id=f"{document.doc_id}:chunk_{chunk_id}",
                    text=chunk_text,
                    normalized_text=normalized_text,
                    page_start=page_start,
                    page_end=page_end,
                    char_range=(char_start, char_end)
                )
                
                chunks.append(chunk)
                chunk_id += 1
                
                # Advance by stride
                i += stride
            
            logger.info(
                f"Chunked document {document.doc_id} into {len(chunks)} chunks "
                f"(pages_per_chunk={self.pages_per_chunk}, overlap={self.overlap_pages})"
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Chunking failed: {str(e)}", exc_info=True)
            raise ChunkerError(f"Failed to chunk document: {str(e)}")
