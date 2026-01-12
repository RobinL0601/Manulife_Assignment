"""
PDF parsing with page provenance.

Extracts text from PDF files page-by-page, building DocumentArtifact
with PageArtifact objects containing character offsets and normalized text.
"""

import re
from pathlib import Path
from typing import Union, List
from collections import Counter

import fitz  # PyMuPDF

from app.core.schemas import DocumentArtifact, PageArtifact
from app.pipeline.interfaces import IParser, ParserError
from app.utils.text_normalizer import normalizer
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class PDFParser(IParser):
    """
    Fast digital PDF text extraction with page provenance.
    
    Uses PyMuPDF (fitz) for efficient text extraction.
    Does not perform OCR - flags scanned documents for later processing.
    """
    
    def __init__(
        self,
        min_text_length: int = 50,
        header_footer_threshold: int = 3,
        remove_headers_footers: bool = True
    ):
        """
        Initialize PDF parser.
        
        Args:
            min_text_length: Minimum text length to consider page valid (chars)
            header_footer_threshold: Number of repetitions to consider line as header/footer
            remove_headers_footers: Whether to attempt header/footer removal
        """
        self.min_text_length = min_text_length
        self.header_footer_threshold = header_footer_threshold
        self.remove_headers_footers = remove_headers_footers
    
    async def parse(self, pdf_path: Union[str, Path, bytes]) -> DocumentArtifact:
        """
        Parse PDF to DocumentArtifact.
        
        Args:
            pdf_path: Path to PDF file or bytes content
            
        Returns:
            DocumentArtifact with pages and metadata
            
        Raises:
            ParserError: If parsing fails
        """
        try:
            # Open PDF document
            if isinstance(pdf_path, bytes):
                doc = fitz.open(stream=pdf_path, filetype="pdf")
                filename = "uploaded_contract.pdf"
            else:
                pdf_path = Path(pdf_path)
                doc = fitz.open(pdf_path)
                filename = pdf_path.name
            
            logger.info(f"Parsing PDF: {filename} ({doc.page_count} pages)")
            
            # Extract text from all pages
            pages = []
            char_offset = 0
            all_lines = []  # For header/footer detection
            
            # First pass: extract raw text
            raw_pages = []
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text("text")
                raw_pages.append((page_num + 1, text))
                
                # Collect lines for header/footer detection
                if text.strip():
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    all_lines.append(lines)
            
            doc.close()
            
            # Detect common headers/footers
            headers_footers = set()
            if self.remove_headers_footers and len(all_lines) > 2:
                headers_footers = self._detect_repeated_lines(all_lines)
            
            # Second pass: build PageArtifacts with cleanup
            total_text_length = 0
            for page_num, raw_text in raw_pages:
                # Clean text (remove headers/footers)
                cleaned_text = self._clean_text(raw_text, headers_footers)
                
                # Normalize text
                normalized = normalizer.normalize(cleaned_text)
                
                # Calculate word count
                word_count = len(cleaned_text.split())
                
                # Calculate char offsets
                char_start = char_offset
                char_end = char_offset + len(cleaned_text)
                char_offset = char_end + 2  # +2 for "\n\n" separator between pages
                
                # Create PageArtifact
                page_artifact = PageArtifact(
                    page_number=page_num,
                    raw_text=cleaned_text,
                    normalized_text=normalized,
                    char_offset_start=char_start,
                    char_offset_end=char_end,
                    word_count=word_count
                )
                
                pages.append(page_artifact)
                total_text_length += len(cleaned_text.strip())
            
            # Determine if document needs OCR
            avg_text_per_page = total_text_length / len(pages) if pages else 0
            needs_ocr = avg_text_per_page < self.min_text_length
            
            # Build metadata
            metadata = {
                "parser_used": "PyMuPDF",
                "parser_version": fitz.version[0],
                "needs_ocr": needs_ocr,
                "total_pages": len(pages),
                "avg_chars_per_page": int(avg_text_per_page),
                "headers_footers_removed": len(headers_footers) > 0
            }
            
            if needs_ocr:
                logger.warning(
                    f"Document {filename} has minimal text (avg {avg_text_per_page:.0f} chars/page). "
                    f"May need OCR."
                )
            
            # Create DocumentArtifact
            document = DocumentArtifact(
                filename=filename,
                page_count=len(pages),
                pages=pages,
                metadata=metadata
            )
            
            logger.info(
                f"Parsed {filename}: {len(pages)} pages, "
                f"{total_text_length} chars, needs_ocr={needs_ocr}"
            )
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to parse PDF: {str(e)}", exc_info=True)
            raise ParserError(f"PDF parsing failed: {str(e)}")
    
    def _detect_repeated_lines(
        self,
        all_pages_lines: List[List[str]]
    ) -> set:
        """
        Detect repeated lines across pages (likely headers/footers).
        
        Args:
            all_pages_lines: List of line lists for each page
            
        Returns:
            Set of repeated line texts
        """
        if len(all_pages_lines) < 3:
            return set()
        
        # Look at first and last 3 lines of each page
        first_lines = []
        last_lines = []
        
        for lines in all_pages_lines:
            if len(lines) >= 3:
                first_lines.extend(lines[:3])
                last_lines.extend(lines[-3:])
        
        # Count occurrences
        first_counter = Counter(first_lines)
        last_counter = Counter(last_lines)
        
        # Lines that appear on multiple pages are likely headers/footers
        repeated = set()
        
        for line, count in first_counter.items():
            if count >= self.header_footer_threshold and len(line) < 100:
                repeated.add(line)
        
        for line, count in last_counter.items():
            if count >= self.header_footer_threshold and len(line) < 100:
                repeated.add(line)
        
        return repeated
    
    def _clean_text(self, text: str, headers_footers: set) -> str:
        """
        Clean extracted text by removing headers/footers and normalizing whitespace.
        
        Args:
            text: Raw extracted text
            headers_footers: Set of header/footer lines to remove
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        lines = text.split('\n')
        
        # Remove header/footer lines
        if headers_footers:
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and stripped not in headers_footers:
                    cleaned_lines.append(line)
        else:
            cleaned_lines = lines
        
        # Rejoin and normalize whitespace
        cleaned = '\n'.join(cleaned_lines)
        
        # Collapse multiple blank lines to max 2 newlines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # Remove excessive spaces (but preserve single spaces and newlines)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        
        # Strip leading/trailing whitespace
        cleaned = cleaned.strip()
        
        return cleaned
