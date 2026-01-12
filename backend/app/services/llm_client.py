"""LLM client abstraction with external and local implementations."""

from abc import ABC, abstractmethod
from typing import Optional
import httpx
import json

from app.config import settings


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.
    
    Provides a common interface for both external API providers
    (OpenAI, Anthropic) and local models (Ollama, vLLM).
    """
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate text completion from the LLM.
        
        Args:
            prompt: User prompt/query
            system_prompt: Optional system prompt for instruction
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
            
        Raises:
            LLMClientError: If generation fails
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the LLM service is available.
        
        Returns:
            True if service is reachable and ready
        """
        pass


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class ExternalLLMClient(LLMClient):
    """
    External API LLM client for OpenAI.
    
    Note: Only OpenAI is fully implemented. Other providers (Anthropic, etc.)
    can be added as needed following the same pattern.
    """
    
    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize external LLM client.
        
        Args:
            provider: Provider name (currently only 'openai' supported)
            api_key: API key for authentication
            model: Model identifier
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate text using OpenAI API.
        
        Args:
            prompt: User prompt
            system_prompt: System instruction
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            
        Returns:
            Generated text
            
        Raises:
            LLMClientError: If API call fails
        """
        if self.provider != "openai":
            raise LLMClientError(
                f"Provider '{self.provider}' not implemented. "
                f"Currently only 'openai' is supported."
            )
        
        return await self._call_openai(prompt, system_prompt, temperature, max_tokens)
    
    async def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Call OpenAI API."""
        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPError as e:
                raise LLMClientError(f"OpenAI API error: {str(e)}")
            except (KeyError, json.JSONDecodeError) as e:
                raise LLMClientError(f"Invalid OpenAI response format: {str(e)}")
    
    async def is_available(self) -> bool:
        """Check if external API is available."""
        try:
            # Simple health check with minimal prompt
            await self.generate("test", max_tokens=5)
            return True
        except LLMClientError:
            return False


class LocalLLMClient(LLMClient):
    """
    Local LLM client for Ollama/vLLM.
    
    Uses HTTP API to communicate with locally running LLM server.
    """
    
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 120
    ):
        """
        Initialize local LLM client.
        
        Args:
            base_url: Base URL of local LLM server (e.g., http://localhost:11434)
            model: Model identifier
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate text using local Ollama API.
        
        Args:
            prompt: User prompt
            system_prompt: System instruction
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            
        Returns:
            Generated text
            
        Raises:
            LLMClientError: If API call fails
        """
        endpoint = f"{self.base_url}/api/generate"
        
        # Build full prompt with system instruction
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["response"]
            except httpx.HTTPError as e:
                raise LLMClientError(f"Local LLM API error: {str(e)}")
            except (KeyError, json.JSONDecodeError) as e:
                raise LLMClientError(f"Invalid local LLM response format: {str(e)}")
    
    async def is_available(self) -> bool:
        """Check if local LLM server is available."""
        endpoint = f"{self.base_url}/api/tags"
        
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                response = await client.get(endpoint)
                response.raise_for_status()
                return True
            except httpx.HTTPError:
                return False


def get_llm_client() -> LLMClient:
    """
    Factory function to get configured LLM client.
    
    Returns:
        Configured LLM client based on settings
        
    Raises:
        ValueError: If configuration is invalid
    """
    if settings.llm_mode == "external":
        if not settings.external_api_key:
            raise ValueError("EXTERNAL_API_KEY is required for external LLM mode")
        
        return ExternalLLMClient(
            provider=settings.external_api_provider,
            api_key=settings.external_api_key,
            model=settings.external_model,
            timeout=settings.external_api_timeout,
            max_retries=settings.external_api_max_retries
        )
    
    elif settings.llm_mode == "local":
        return LocalLLMClient(
            base_url=settings.local_llm_base_url,
            model=settings.local_model,
            timeout=settings.local_api_timeout
        )
    
    else:
        raise ValueError(f"Invalid LLM mode: {settings.llm_mode}")
