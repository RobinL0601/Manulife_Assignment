"""In-memory job storage for MVP."""

from typing import Dict, Optional
from uuid import UUID

from app.core.schemas import Job, JobStatus


class InMemoryJobStore:
    """
    Simple in-memory job store.
    
    For production, replace with Redis, PostgreSQL, or similar persistent store.
    """
    
    def __init__(self):
        """Initialize empty job store."""
        self._jobs: Dict[UUID, Job] = {}
    
    def save_job(self, job: Job) -> UUID:
        """
        Save a job to the store.
        
        Args:
            job: Job instance to save
            
        Returns:
            The job's UUID
        """
        self._jobs[job.job_id] = job
        return job.job_id
    
    def get_job(self, job_id: UUID) -> Optional[Job]:
        """
        Retrieve a job by ID.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Job instance if found, None otherwise
        """
        return self._jobs.get(job_id)
    
    def update_job(self, job_id: UUID, job: Job) -> bool:
        """
        Update an existing job.
        
        Args:
            job_id: Job UUID
            job: Updated job instance
            
        Returns:
            True if job was updated, False if not found
        """
        if job_id not in self._jobs:
            return False
        self._jobs[job_id] = job
        return True
    
    def delete_job(self, job_id: UUID) -> bool:
        """
        Delete a job from the store.
        
        Args:
            job_id: Job UUID
            
        Returns:
            True if job was deleted, False if not found
        """
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        return True
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> list[Job]:
        """
        List all jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of jobs
        """
        jobs = list(self._jobs.values())
        if status:
            jobs = [job for job in jobs if job.status == status]
        return jobs
    
    def count_jobs(self, status: Optional[JobStatus] = None) -> int:
        """
        Count jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            Number of jobs
        """
        if status:
            return len([job for job in self._jobs.values() if job.status == status])
        return len(self._jobs)
    
    def clear(self) -> None:
        """Clear all jobs (for testing)."""
        self._jobs.clear()


# Global store instance
job_store = InMemoryJobStore()
