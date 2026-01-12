"""Deterministic text normalization for quote validation."""

import re
import unicodedata


class TextNormalizer:
    """
    Deterministic text normalizer for exact quote matching.
    
    Applies consistent transformations to enable reliable substring matching
    while handling whitespace and formatting variations.
    """
    
    @staticmethod
    def normalize(text: str) -> str:
        """
        Normalize text for matching.
        
        Transformations:
        1. Unicode normalization (NFC)
        2. Lowercase
        3. Collapse whitespace (spaces, tabs, newlines → single space)
        4. Strip leading/trailing whitespace
        5. Remove zero-width characters
        
        Args:
            text: Raw text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Unicode normalization
        text = unicodedata.normalize("NFC", text)
        
        # Lowercase
        text = text.lower()
        
        # Remove zero-width and control characters
        text = "".join(
            char for char in text
            if unicodedata.category(char) not in ("Cf", "Cc") or char in ("\n", "\r", "\t", " ")
        )
        
        # Collapse all whitespace to single spaces
        text = re.sub(r"\s+", " ", text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def normalize_aggressive(text: str) -> str:
        """
        More aggressive normalization that also removes punctuation.
        
        Use this for looser matching if needed (not default for quote validation).
        
        Args:
            text: Raw text to normalize
            
        Returns:
            Aggressively normalized text
        """
        text = TextNormalizer.normalize(text)
        
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        
        # Collapse multiple spaces again
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text


# Singleton instance
normalizer = TextNormalizer()
