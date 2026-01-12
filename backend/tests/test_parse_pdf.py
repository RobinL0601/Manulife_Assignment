"""Tests for PDF parsing functionality."""

import pytest
import fitz  # PyMuPDF

from app.pipeline.parse_pdf import PDFParser
from app.pipeline.chunker import PageBasedChunker
from app.core.schemas import DocumentArtifact
from app.pipeline.interfaces import ParserError


# Helper function to create a test PDF
def create_test_pdf(pages_content: list[str]) -> bytes:
    """Create a simple PDF with given page contents."""
    doc = fitz.open()
    
    for content in pages_content:
        page = doc.new_page(width=595, height=842)  # A4 size
        page.insert_text((72, 72), content)
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    return pdf_bytes


class TestPDFParser:
    """Test PDFParser class."""
    
    @pytest.mark.asyncio
    async def test_parse_simple_pdf(self):
        """Test parsing a simple PDF with text content."""
        # Create test PDF
        pdf_bytes = create_test_pdf([
            "This is page 1.\nIt has some text.",
            "This is page 2.\nIt has more text.",
        ])
        
        # Parse
        parser = PDFParser()
        document = await parser.parse(pdf_bytes)
        
        # Assertions
        assert isinstance(document, DocumentArtifact)
        assert document.page_count == 2
        assert len(document.pages) == 2
        
        # Check page 1
        page1 = document.pages[0]
        assert page1.page_number == 1
        assert "page 1" in page1.raw_text.lower()
        assert page1.char_offset_start == 0
        assert page1.char_offset_end > 0
        assert page1.word_count > 0
        
        # Check page 2
        page2 = document.pages[1]
        assert page2.page_number == 2
        assert "page 2" in page2.raw_text.lower()
        assert page2.char_offset_start > page1.char_offset_end
        
        # Check metadata
        assert document.metadata["parser_used"] == "PyMuPDF"
        assert "needs_ocr" in document.metadata
        assert document.metadata["needs_ocr"] is False  # Has text
    
    @pytest.mark.asyncio
    async def test_parse_empty_pdf(self):
        """Test parsing a PDF with minimal/no text (scanned document)."""
        # Create PDF with very little text
        pdf_bytes = create_test_pdf([" ", "  "])
        
        parser = PDFParser(min_text_length=50)
        document = await parser.parse(pdf_bytes)
        
        # Should flag as needing OCR
        assert document.metadata["needs_ocr"] is True
        assert document.page_count == 2
    
    @pytest.mark.asyncio
    async def test_parse_with_headers_footers(self):
        """Test parsing with repeated headers/footers."""
        # Create PDF with repeated headers
        pages = [
            "Header Text\nPage 1 content here.\nFooter Text",
            "Header Text\nPage 2 content here.\nFooter Text",
            "Header Text\nPage 3 content here.\nFooter Text",
        ]
        pdf_bytes = create_test_pdf(pages)
        
        parser = PDFParser(remove_headers_footers=True)
        document = await parser.parse(pdf_bytes)
        
        # Headers/footers should be detected and removed
        assert document.metadata["headers_footers_removed"] is True
    
    @pytest.mark.asyncio
    async def test_char_offset_consistency(self):
        """Test that character offsets are consistent."""
        pdf_bytes = create_test_pdf([
            "Page 1 text",
            "Page 2 text",
            "Page 3 text",
        ])
        
        parser = PDFParser()
        document = await parser.parse(pdf_bytes)
        
        # Check offsets don't overlap
        for i in range(len(document.pages) - 1):
            page_curr = document.pages[i]
            page_next = document.pages[i + 1]
            
            assert page_curr.char_offset_end <= page_next.char_offset_start
            assert page_curr.char_offset_start < page_curr.char_offset_end
    
    @pytest.mark.asyncio
    async def test_normalized_text(self):
        """Test that normalized text is generated."""
        pdf_bytes = create_test_pdf([
            "This   has    MULTIPLE   spaces\nAnd   CaPiTaLs"
        ])
        
        parser = PDFParser()
        document = await parser.parse(pdf_bytes)
        
        page1 = document.pages[0]
        
        # Normalized text should be lowercase and collapsed whitespace
        assert "multiple spaces" in page1.normalized_text
        assert "capitals" in page1.normalized_text
        # Should not have multiple spaces
        assert "   " not in page1.normalized_text
    
    @pytest.mark.asyncio
    async def test_parse_invalid_pdf(self):
        """Test parsing invalid PDF raises error."""
        parser = PDFParser()
        
        with pytest.raises(ParserError):
            await parser.parse(b"not a pdf")


class TestPageBasedChunker:
    """Test PageBasedChunker class."""
    
    @pytest.mark.asyncio
    async def test_chunk_by_single_pages(self):
        """Test chunking with 1 page per chunk."""
        pdf_bytes = create_test_pdf([
            "Page 1 content",
            "Page 2 content",
            "Page 3 content",
        ])
        
        parser = PDFParser()
        document = await parser.parse(pdf_bytes)
        
        # Chunk by single pages
        chunker = PageBasedChunker(pages_per_chunk=1, overlap_pages=0)
        chunks = chunker.chunk(document)
        
        # Should have 3 chunks (1 per page)
        assert len(chunks) == 3
        
        # Check first chunk
        assert chunks[0].page_start == 1
        assert chunks[0].page_end == 1
        assert "page 1" in chunks[0].text.lower()
    
    @pytest.mark.asyncio
    async def test_parse_and_chunk_workflow(self):
        """Test complete parse → chunk workflow."""
        pdf_bytes = create_test_pdf([
            "Contract Introduction\nThis is the introduction section.",
            "Section 1: Terms\nThese are the terms of the contract.",
            "Section 2: Conditions\nThese are the conditions.",
        ])
        
        # Parse
        parser = PDFParser()
        document = await parser.parse(pdf_bytes)
        
        assert document.page_count == 3
        assert document.metadata["needs_ocr"] is False
        
        # Chunk
        chunker = PageBasedChunker(pages_per_chunk=1)
        chunks = chunker.chunk(document)
        
        assert len(chunks) == 3
        
        # Verify chunk structure
        for chunk in chunks:
            assert chunk.chunk_id
            assert chunk.text
            assert chunk.normalized_text
            assert chunk.page_start >= 1
            assert chunk.page_end >= chunk.page_start
            assert len(chunk.text) > 0
