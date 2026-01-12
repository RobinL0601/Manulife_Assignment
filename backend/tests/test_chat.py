"""Tests for chat functionality (bonus feature)."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.core.schemas import (
    ChatSession, ChatMessage, DocumentArtifact, Chunk, EvidenceChunk, Quote
)
from app.core.chat_storage import InMemoryChatStore
from app.services.chat_service import ChatService


class TestChatStore:
    """Test InMemoryChatStore."""
    
    def test_create_and_get_session(self):
        """Test creating and retrieving a chat session."""
        store = InMemoryChatStore()
        job_id = uuid4()
        
        # Create session
        session_id = store.create_session(job_id)
        assert session_id is not None
        
        # Retrieve session
        session = store.get_session(session_id)
        assert session is not None
        assert session.job_id == job_id
        assert len(session.messages) == 0
    
    def test_append_message(self):
        """Test appending messages to a session."""
        store = InMemoryChatStore()
        job_id = uuid4()
        session_id = store.create_session(job_id)
        
        # Append user message
        success = store.append_message(session_id, "user", "What is password policy?")
        assert success is True
        
        # Append assistant message
        success = store.append_message(session_id, "assistant", "The policy requires...")
        assert success is True
        
        # Verify messages
        session = store.get_session(session_id)
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "What is password policy?"
        assert session.messages[1].role == "assistant"
    
    def test_append_to_nonexistent_session(self):
        """Test appending to a session that doesn't exist."""
        store = InMemoryChatStore()
        fake_session_id = uuid4()
        
        success = store.append_message(fake_session_id, "user", "Hello")
        assert success is False


class TestChatService:
    """Test ChatService."""
    
    @pytest.mark.asyncio
    async def test_answer_with_valid_evidence(self):
        """Test chat service returns answer when evidence is found."""
        # Mock LLM client
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value='{"answer": "Passwords must be at least 12 characters.", "relevant_quotes": [{"text": "passwords must be at least 12 characters"}]}')
        
        # Create chat service
        chat_service = ChatService(llm_client=mock_llm)
        
        # Create test data
        session = ChatSession(job_id=uuid4())
        doc = DocumentArtifact(filename="test.pdf", page_count=5, pages=[])
        chunks = [
            Chunk(
                chunk_id="c1",
                text="All passwords must be at least 12 characters long.",
                normalized_text="all passwords must be at least 12 characters long",
                page_start=3,
                page_end=3,
                char_range=(0, 100)
            )
        ]
        
        # Generate answer
        response = await chat_service.answer(
            session=session,
            user_message="What is the password length requirement?",
            doc=doc,
            chunks=chunks
        )
        
        # Verify response
        assert response.answer == "Passwords must be at least 12 characters."
        assert len(response.relevant_quotes) == 1
        assert response.relevant_quotes[0].page_start == 3
        assert response.confidence > 0
    
    @pytest.mark.asyncio
    async def test_answer_when_no_evidence(self):
        """Test chat service returns 'cannot find' when no relevant evidence."""
        mock_llm = AsyncMock()
        
        chat_service = ChatService(llm_client=mock_llm)
        
        session = ChatSession(job_id=uuid4())
        doc = DocumentArtifact(filename="test.pdf", page_count=5, pages=[])
        chunks = [
            Chunk(
                chunk_id="c1",
                text="This contract covers general terms and conditions.",
                normalized_text="this contract covers general terms and conditions",
                page_start=1,
                page_end=1,
                char_range=(0, 100)
            )
        ]
        
        # Ask question about something not in the contract
        response = await chat_service.answer(
            session=session,
            user_message="What is the quantum computing policy?",
            doc=doc,
            chunks=chunks
        )
        
        # Should return low/zero confidence answer
        assert "cannot find" in response.answer.lower() or response.confidence == 0
    
    @pytest.mark.asyncio
    async def test_confidence_calculation(self):
        """Test confidence calculation based on quotes and evidence."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value='{"answer": "Training is required annually.", "relevant_quotes": []}')
        
        chat_service = ChatService(llm_client=mock_llm)
        
        session = ChatSession(job_id=uuid4())
        doc = DocumentArtifact(filename="test.pdf", page_count=5, pages=[])
        chunks = [
            Chunk(
                chunk_id="c1",
                text="Training is required annually for all staff.",
                normalized_text="training is required annually for all staff",
                page_start=4,
                page_end=4,
                char_range=(0, 100)
            )
        ]
        
        response = await chat_service.answer(
            session=session,
            user_message="How often is training required?",
            doc=doc,
            chunks=chunks
        )
        
        # Base confidence should be ~70% (evidence found, no quotes)
        assert 60 <= response.confidence <= 80
