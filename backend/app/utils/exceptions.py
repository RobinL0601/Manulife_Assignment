"""Custom exception classes."""

from typing import Optional


class ContractAnalyzerError(Exception):
    """Base exception for all application errors."""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class JobNotFoundError(ContractAnalyzerError):
    """Raised when a job ID is not found."""
    pass


class JobNotCompletedError(ContractAnalyzerError):
    """Raised when attempting to access results of incomplete job."""
    pass


class InvalidFileError(ContractAnalyzerError):
    """Raised when uploaded file is invalid."""
    pass


class ProcessingError(ContractAnalyzerError):
    """Raised when job processing fails."""
    pass
