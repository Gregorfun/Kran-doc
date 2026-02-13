"""
Job Models
==========

Pydantic models für Job State Machine
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job Status State Machine"""

    UPLOADED = "uploaded"
    TEXTLAYER_CHECK = "textlayer_check"
    OCR = "ocr"
    PARSE = "parse"
    NORMALIZE = "normalize"
    EXTRACT = "extract"
    CHUNK = "chunk"
    EMBED = "embed"
    INDEX = "index"
    DONE = "done"
    FAILED = "failed"


class JobStepResult(BaseModel):
    """Result of a single job step"""

    step: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    method: Optional[str] = None  # docling, unstructured, ocr
    confidence: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    """Job Model"""

    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    input_file: str
    model_name: Optional[str] = None

    # Pipeline steps
    steps: List[JobStepResult] = Field(default_factory=list)

    # Final result
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_step(self, step: str, started_at: Optional[datetime] = None) -> JobStepResult:
        """Add a new step to the job"""
        if started_at is None:
            started_at = datetime.utcnow()

        step_result = JobStepResult(step=step, started_at=started_at)
        self.steps.append(step_result)
        self.updated_at = datetime.utcnow()
        return step_result

    def complete_step(
        self,
        step: str,
        method: Optional[str] = None,
        confidence: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Complete a step"""
        for s in reversed(self.steps):
            if s.step == step and s.finished_at is None:
                s.finished_at = datetime.utcnow()
                if s.started_at:
                    delta = s.finished_at - s.started_at
                    s.duration_ms = int(delta.total_seconds() * 1000)
                s.method = method
                s.confidence = confidence
                s.error = error
                if metadata:
                    s.metadata.update(metadata)
                self.updated_at = datetime.utcnow()
                break

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON storage"""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "input_file": self.input_file,
            "model_name": self.model_name,
            "steps": [
                {
                    "step": s.step,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "duration_ms": s.duration_ms,
                    "method": s.method,
                    "confidence": s.confidence,
                    "error": s.error,
                    "metadata": s.metadata,
                }
                for s in self.steps
            ],
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }
