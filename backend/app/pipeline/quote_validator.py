"""
Deterministic quote validation for compliance analysis.

Validates that LLM-generated quotes are verbatim excerpts from retrieved evidence.
Uses exact substring matching after deterministic normalization.
"""

import re
from typing import List

from app.core.schemas import ComplianceResult, Quote, EvidenceChunk, DocumentArtifact
from app.pipeline.interfaces import IQuoteValidator, ValidatorError
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class QuoteValidator(IQuoteValidator):
    """
    Validates quotes against source evidence using deterministic normalization.
    
    Ensures all quotes are verbatim excerpts from retrieved evidence chunks.
    No fuzzy matching - exact substring match after normalization only.
    """
    
    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        """
        Deterministic normalization for quote matching.
        
        Transformations (order matters for determinism):
        1. Lowercase
        2. Normalize Unicode quotes and dashes (explicit codepoints)
        3. Collapse all whitespace to single space
        4. Strip leading/trailing whitespace
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text suitable for substring matching
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Normalize Unicode quotes and dashes using explicit codepoints
        # U+201C (") U+201D (") → " (straight double quote)
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        # U+2018 (') U+2019 (') → ' (straight single quote)
        text = text.replace('\u2018', "'").replace('\u2019', "'")
        # U+2013 (–) U+2014 (—) → - (hyphen-minus)
        text = text.replace('\u2013', '-').replace('\u2014', '-')
        
        # Collapse all whitespace to single space
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def validate(
        self,
        quotes: List[str],
        document: DocumentArtifact
    ) -> List[dict]:
        """
        Validate quotes against source document.
        
        This is the interface-mandated method, but for MVP we use
        validate_quotes() which works with evidence chunks directly.
        
        Args:
            quotes: List of quote strings
            document: Source document
            
        Returns:
            List of validated quote dicts
        """
        # For MVP, this method is not used - we validate against evidence chunks
        # to avoid scanning entire document. Implemented for interface compliance.
        raise NotImplementedError(
            "Use validate_quotes() with evidence chunks for MVP implementation"
        )
    
    def validate_quotes(
        self,
        result: ComplianceResult,
        evidence: List[EvidenceChunk],
        doc: DocumentArtifact
    ) -> ComplianceResult:
        """
        Validate quotes in ComplianceResult against evidence chunks.
        
        Args:
            result: ComplianceResult with quotes to validate
            evidence: Evidence chunks used to generate the result
            doc: Full document (used for fallback only)
            
        Returns:
            Updated ComplianceResult with validated quotes
        """
        try:
            if not result.relevant_quotes:
                # No quotes to validate
                return result
            
            # Sort evidence in stable document order: (page_start, page_end, chunk_id)
            sorted_evidence = sorted(
                evidence, 
                key=lambda c: (c.page_start, c.page_end, c.chunk_id)
            )
            evidence_texts = [chunk.text for chunk in sorted_evidence]
            combined_evidence = " ".join(evidence_texts)
            normalized_evidence = self._normalize_for_matching(combined_evidence)
            
            # Validate each quote
            validated_quotes = []
            for quote in result.relevant_quotes:
                quote_text = quote.text
                normalized_quote = self._normalize_for_matching(quote_text)
                
                # Check if normalized quote is substring of evidence
                if normalized_quote in normalized_evidence:
                    # Find which chunk(s) contain this quote
                    page_start, page_end = self._find_page_range(
                        quote_text, sorted_evidence
                    )
                    
                    validated_quote = Quote(
                        text=quote_text,
                        page_start=page_start,
                        page_end=page_end,
                        validated=True
                    )
                    validated_quotes.append(validated_quote)
                    logger.debug(
                        f"Quote validated: pages {page_start}-{page_end}, "
                        f"prefix='{quote_text[:30]}...'"
                    )
                else:
                    # Quote not found - log warning with short prefix only
                    quote_prefix = quote_text[:30] if len(quote_text) > 30 else quote_text
                    logger.warning(
                        f"Quote validation failed: quote not found in evidence. "
                        f"Prefix: '{quote_prefix}...'. "
                        f"Requirement: {result.compliance_question[:50]}..."
                    )
                    # Drop this quote (do not add to validated_quotes)
            
            # Update result with validated quotes
            original_count = len(result.relevant_quotes)
            validated_count = len(validated_quotes)
            removed_count = original_count - validated_count
            
            if validated_count == 0 and original_count > 0:
                # All quotes were invalid - reduce confidence and update rationale
                logger.warning(
                    f"All {original_count} quotes invalid for requirement: "
                    f"{result.compliance_question[:50]}..."
                )
                result.confidence = min(result.confidence, 30)
                result.rationale += (
                    f" [{removed_count} quotes removed during validation - "
                    "not found in retrieved evidence]"
                )
            elif removed_count > 0:
                # Some quotes dropped - adjust confidence proportionally
                confidence_penalty = min(20, removed_count * 10)
                result.confidence = max(20, result.confidence - confidence_penalty)
                result.rationale += (
                    f" [{removed_count} of {original_count} quotes removed during validation]"
                )
                logger.info(
                    f"Quote validation: {validated_count}/{original_count} quotes valid, "
                    f"removed {removed_count}"
                )
            
            result.relevant_quotes = validated_quotes
            return result
            
        except Exception as e:
            logger.error(f"Quote validation failed: {str(e)}", exc_info=True)
            raise ValidatorError(f"Failed to validate quotes: {str(e)}")
    
    def _find_page_range(
        self,
        quote_text: str,
        evidence_chunks: List[EvidenceChunk]
    ) -> tuple[int, int]:
        """
        Find page range for a quote within evidence chunks.
        
        Strategy:
        1. Try to find quote in a single chunk
        2. If not found, try adjacent chunk pairs (i, i+1)
        3. If still not found, use first chunk range as fallback
        
        Args:
            quote_text: Quote text to locate
            evidence_chunks: Evidence chunks (sorted by document order)
            
        Returns:
            Tuple of (page_start, page_end)
        """
        normalized_quote = self._normalize_for_matching(quote_text)
        
        # Strategy 1: Search in single chunks
        for chunk in evidence_chunks:
            normalized_chunk = self._normalize_for_matching(chunk.text)
            if normalized_quote in normalized_chunk:
                # Found in this chunk - use its page range
                return (chunk.page_start, chunk.page_end)
        
        # Strategy 2: Search in adjacent chunk pairs
        for i in range(len(evidence_chunks) - 1):
            chunk1 = evidence_chunks[i]
            chunk2 = evidence_chunks[i + 1]
            combined_text = chunk1.text + " " + chunk2.text
            normalized_combined = self._normalize_for_matching(combined_text)
            
            if normalized_quote in normalized_combined:
                # Found spanning two chunks - use combined page range
                page_start = min(chunk1.page_start, chunk2.page_start)
                page_end = max(chunk1.page_end, chunk2.page_end)
                logger.debug(
                    f"Quote spans chunks {chunk1.chunk_id} and {chunk2.chunk_id}, "
                    f"pages {page_start}-{page_end}"
                )
                return (page_start, page_end)
        
        # Fallback: not found in any single chunk or adjacent pairs
        # Use page range from first chunk (stable choice)
        if evidence_chunks:
            logger.warning(
                f"Quote not found in evidence chunks, using first chunk page range. "
                f"Quote prefix: '{quote_text[:30]}...'"
            )
            return (evidence_chunks[0].page_start, evidence_chunks[0].page_end)
        
        # Edge case: no evidence chunks (shouldn't happen)
        logger.error("No evidence chunks available for page range mapping")
        return (1, 1)
