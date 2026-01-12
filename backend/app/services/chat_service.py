"""
Chat service for answering questions about completed contract analysis jobs.

Uses evidence-first RAG: retrieves relevant chunks via BM25, then asks LLM
to answer based ONLY on retrieved evidence.
"""

import json
from typing import List, Optional
from uuid import UUID

from app.core.schemas import (
    ChatSession, ChatMessage, ChatMessageResponse, DocumentArtifact, Chunk, 
    EvidenceChunk, Quote
)
from app.pipeline.retriever import BM25Retriever
from app.pipeline.quote_validator import QuoteValidator
from app.services.llm_client import LLMClient
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ChatServiceError(Exception):
    """Exception raised by ChatService."""
    pass


class ChatService:
    """
    Service for answering user questions about contracts.
    
    Evidence-first: Retrieves top-k chunks using BM25, then asks LLM to answer
    based only on that evidence. Validates quotes deterministically.
    """
    
    def __init__(self, llm_client: LLMClient):
        """
        Initialize chat service.
        
        Args:
            llm_client: LLM client for generating answers
        """
        self.llm_client = llm_client
        self.retriever = BM25Retriever()
        self.validator = QuoteValidator()
    
    async def answer(
        self,
        session: ChatSession,
        user_message: str,
        doc: DocumentArtifact,
        chunks: List[Chunk]
    ) -> ChatMessageResponse:
        """
        Generate an answer to a user question about the contract.
        
        Process:
        1. Retrieve top-k evidence chunks using BM25
        2. Build prompt with evidence + recent chat history (last 4 messages)
        3. Call LLM with JSON output requirement
        4. Validate quotes against evidence
        5. Return ChatMessageResponse
        
        Args:
            session: Current chat session
            user_message: User's question
            doc: Document artifact
            chunks: Document chunks
            
        Returns:
            ChatMessageResponse with answer, quotes, confidence
            
        Raises:
            ChatServiceError: If answer generation fails
        """
        try:
            # Step 1: Retrieve evidence using BM25
            logger.info(f"Chat: Retrieving evidence for query length={len(user_message)}")
            evidence_chunks = self.retriever.retrieve(
                query=user_message,
                chunks=chunks,
                top_k=5
            )
            
            if not evidence_chunks:
                # No relevant evidence found
                return ChatMessageResponse(
                    answer="I cannot find relevant information in the contract to answer your question.",
                    relevant_quotes=[],
                    confidence=0
                )
            
            # Step 2: Build prompt with evidence + context
            prompt = self._build_chat_prompt(
                user_message=user_message,
                evidence=evidence_chunks,
                recent_messages=session.messages[-4:] if len(session.messages) > 0 else []
            )
            
            system_prompt = (
                "You are a contract analysis assistant. Answer questions based ONLY on the "
                "provided evidence from the contract. If the evidence does not contain enough "
                "information to answer, say 'I cannot find that information in the contract.' "
                "Provide verbatim quotes to support your answer."
            )
            
            # Step 3: Call LLM for answer
            logger.info("Chat: Calling LLM for answer")
            response_text = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # Lower temp for factual answers
                max_tokens=500
            )
            
            # Step 4: Parse JSON response
            answer_data = self._parse_llm_response(response_text)
            
            # Step 5: Validate quotes
            if answer_data.get("relevant_quotes"):
                validated_quotes = self._validate_chat_quotes(
                    quotes_data=answer_data["relevant_quotes"],
                    evidence=evidence_chunks
                )
            else:
                validated_quotes = []
            
            # Step 6: Calculate simple confidence
            confidence = self._calculate_confidence(
                answer=answer_data.get("answer", ""),
                validated_quotes=validated_quotes,
                evidence_count=len(evidence_chunks)
            )
            
            logger.info(
                f"Chat: Generated answer length={len(answer_data.get('answer', ''))}, "
                f"quotes={len(validated_quotes)}, confidence={confidence}"
            )
            
            return ChatMessageResponse(
                answer=answer_data.get("answer", "I could not generate an answer."),
                relevant_quotes=validated_quotes,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Chat service error: {str(e)}", exc_info=True)
            raise ChatServiceError(f"Failed to generate answer: {str(e)}")
    
    def _build_chat_prompt(
        self,
        user_message: str,
        evidence: List[EvidenceChunk],
        recent_messages: List[ChatMessage]
    ) -> str:
        """
        Build prompt with evidence and conversation context.
        
        Args:
            user_message: Current user question
            evidence: Retrieved evidence chunks
            recent_messages: Last 4 messages for context
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # Add recent conversation context (last 4 messages only)
        if recent_messages:
            prompt_parts.append("CONVERSATION HISTORY (last 4 messages):")
            for msg in recent_messages:
                role_label = "User" if msg.role == "user" else "Assistant"
                prompt_parts.append(f"{role_label}: {msg.content}")
            prompt_parts.append("")
        
        # Add evidence chunks with page references
        prompt_parts.append("EVIDENCE FROM CONTRACT:")
        for i, chunk in enumerate(evidence, 1):
            page_ref = f"[Pages {chunk.page_start}"
            if chunk.page_end != chunk.page_start:
                page_ref += f"-{chunk.page_end}"
            page_ref += "]"
            prompt_parts.append(f"\n{i}. {page_ref}")
            prompt_parts.append(chunk.text)
        
        prompt_parts.append("\n---")
        prompt_parts.append(f"\nUSER QUESTION: {user_message}")
        prompt_parts.append(
            "\nINSTRUCTIONS: Answer the question using ONLY the evidence above. "
            "If the evidence does not contain the information needed, say "
            "'I cannot find that information in this contract.' "
            "Return your response as JSON with this exact format:\n"
            '{\n'
            '  "answer": "your answer here",\n'
            '  "relevant_quotes": [{"text": "exact quote from evidence"}]\n'
            '}'
        )
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(self, response_text: str) -> dict:
        """
        Parse LLM JSON response with fallback.
        
        Args:
            response_text: Raw LLM response
            
        Returns:
            Parsed dict with 'answer' and 'relevant_quotes'
        """
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # Handle markdown code blocks
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            
            data = json.loads(response_text)
            
            # Ensure required keys exist
            if "answer" not in data:
                data["answer"] = response_text  # Fallback to raw text
            if "relevant_quotes" not in data:
                data["relevant_quotes"] = []
            
            return data
            
        except json.JSONDecodeError:
            logger.warning(f"Chat: Failed to parse JSON, using text fallback. Response: {response_text[:100]}...")
            return {
                "answer": response_text,
                "relevant_quotes": []
            }
    
    def _validate_chat_quotes(
        self,
        quotes_data: List[dict],
        evidence: List[EvidenceChunk]
    ) -> List[Quote]:
        """
        Validate chat quotes against evidence.
        
        Args:
            quotes_data: List of quote dicts from LLM
            evidence: Evidence chunks to validate against
            
        Returns:
            List of validated Quote objects with page ranges
        """
        validated_quotes = []
        normalizer = QuoteValidator()
        
        # Sort evidence in document order
        sorted_evidence = sorted(
            evidence,
            key=lambda c: (c.page_start, c.page_end, c.chunk_id)
        )
        
        for quote_dict in quotes_data:
            quote_text = quote_dict.get("text", "")
            if not quote_text:
                continue
            
            normalized_quote = normalizer._normalize_for_matching(quote_text)
            
            # Try to find quote in evidence
            page_start, page_end, found = self._find_quote_in_evidence(
                normalized_quote, quote_text, sorted_evidence, normalizer
            )
            
            if found:
                validated_quotes.append(Quote(
                    text=quote_text,
                    page_start=page_start,
                    page_end=page_end,
                    validated=True
                ))
            else:
                # Skip invalid quotes (don't include)
                logger.warning(f"Chat quote not found in evidence: '{quote_text[:30]}...'")
        
        return validated_quotes
    
    def _find_quote_in_evidence(
        self,
        normalized_quote: str,
        original_quote: str,
        evidence: List[EvidenceChunk],
        normalizer: QuoteValidator
    ) -> tuple[int, int, bool]:
        """
        Find quote in evidence chunks.
        
        Returns:
            (page_start, page_end, found_boolean)
        """
        # Try single chunks
        for chunk in evidence:
            normalized_chunk = normalizer._normalize_for_matching(chunk.text)
            if normalized_quote in normalized_chunk:
                return (chunk.page_start, chunk.page_end, True)
        
        # Try adjacent pairs
        for i in range(len(evidence) - 1):
            combined = evidence[i].text + " " + evidence[i+1].text
            normalized_combined = normalizer._normalize_for_matching(combined)
            if normalized_quote in normalized_combined:
                page_start = min(evidence[i].page_start, evidence[i+1].page_start)
                page_end = max(evidence[i].page_end, evidence[i+1].page_end)
                return (page_start, page_end, True)
        
        # Not found
        return (1, 1, False)
    
    def _calculate_confidence(
        self,
        answer: str,
        validated_quotes: List[Quote],
        evidence_count: int
    ) -> int:
        """
        Calculate simple confidence score for chat answer.
        
        Heuristic:
        - Starts at 70% if evidence found
        - +10% for each validated quote (max +30%)
        - Special cases: "cannot find" = 0%, empty answer = 10%
        
        Args:
            answer: Generated answer text
            validated_quotes: Validated quotes
            evidence_count: Number of evidence chunks retrieved
            
        Returns:
            Confidence score (0-100)
        """
        # Check for explicit "not found" answers
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in [
            "cannot find", "can't find", "not found", "no information",
            "does not contain", "doesn't contain"
        ]):
            return 0
        
        if not answer or len(answer) < 10:
            return 10
        
        # Base confidence if we have evidence
        if evidence_count == 0:
            confidence = 30
        else:
            confidence = 70
        
        # Add points for validated quotes (10% each, max 30%)
        quote_bonus = min(30, len(validated_quotes) * 10)
        confidence += quote_bonus
        
        return min(100, confidence)


# Global chat service instance (initialized with LLM client later)
_chat_service: Optional[ChatService] = None


def get_chat_service(llm_client: LLMClient) -> ChatService:
    """
    Get or create chat service instance.
    
    Args:
        llm_client: LLM client to use
        
    Returns:
        ChatService instance
    """
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService(llm_client)
    return _chat_service
