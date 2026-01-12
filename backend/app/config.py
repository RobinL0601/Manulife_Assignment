"""Application configuration management via environment variables."""

from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMMode(str, Enum):
    """LLM inference mode."""
    EXTERNAL = "external"
    LOCAL = "local"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application settings
    app_name: str = "Contract Analyzer API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # API settings
    api_v1_prefix: str = "/api/v1"
    max_upload_size_mb: int = 10
    
    # LLM configuration
    llm_mode: LLMMode = LLMMode.EXTERNAL
    
    # External LLM API settings
    external_api_provider: str = "openai"  # openai, anthropic, etc.
    external_api_key: Optional[str] = None
    external_model: str = "gpt-4"
    external_api_timeout: int = 60
    external_api_max_retries: int = 3
    
    # Local LLM settings
    local_llm_base_url: str = "http://localhost:11434"  # Ollama default
    local_model: str = "llama3"
    local_api_timeout: int = 120
    
    # Retrieval settings
    retrieval_top_k: int = 5
    chunk_size: int = 400
    chunk_overlap: int = 100
    
    # Processing settings
    max_concurrent_jobs: int = 5
    job_timeout_seconds: int = 600
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.max_upload_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()
