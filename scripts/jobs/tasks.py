"""
Job Tasks
=========

Asynchrone Tasks für RQ Worker
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from scripts.jobs.models import Job, JobStatus

logger = logging.getLogger(__name__)


class JobStorage:
    """Simple JSON-based job storage"""

    def __init__(self, jobs_dir: Optional[Path] = None):
        if jobs_dir is None:
            from config.settings import settings

            jobs_dir = settings.output_dir / "jobs"

        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def save_job(self, job: Job) -> None:
        """Save job to JSON file"""
        job_file = self.jobs_dir / f"{job.job_id}.json"
        try:
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(job.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save job {job.job_id}: {e}")

    def load_job(self, job_id: str) -> Optional[Job]:
        """Load job from JSON file"""
        job_file = self.jobs_dir / f"{job_id}.json"
        if not job_file.exists():
            return None

        try:
            with open(job_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse datetime fields
            if data.get("created_at"):
                data["created_at"] = datetime.fromisoformat(data["created_at"])
            if data.get("updated_at"):
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])

            for step in data.get("steps", []):
                if step.get("started_at"):
                    step["started_at"] = datetime.fromisoformat(step["started_at"])
                if step.get("finished_at"):
                    step["finished_at"] = datetime.fromisoformat(step["finished_at"])

            return Job(**data)
        except Exception as e:
            logger.error(f"Failed to load job {job_id}: {e}")
            return None

    def list_jobs(self, limit: int = 100) -> list[Dict[str, Any]]:
        """List recent jobs"""
        jobs = []
        for job_file in sorted(self.jobs_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    jobs.append(data)
            except Exception as e:
                logger.error(f"Failed to load job file {job_file}: {e}")
        return jobs


# Global storage instance
_storage = JobStorage()


def create_job(input_file: str, model_name: Optional[str] = None) -> Job:
    """Create a new job"""
    job_id = str(uuid.uuid4())
    now = datetime.utcnow()

    job = Job(
        job_id=job_id,
        status=JobStatus.UPLOADED,
        created_at=now,
        updated_at=now,
        input_file=input_file,
        model_name=model_name,
    )

    _storage.save_job(job)
    return job


def get_job(job_id: str) -> Optional[Job]:
    """Get job by ID"""
    return _storage.load_job(job_id)


def update_job(job: Job) -> None:
    """Update job"""
    job.updated_at = datetime.utcnow()
    _storage.save_job(job)


# ============================================================
# Pipeline Tasks
# ============================================================


def process_pipeline_task(job_id: str) -> Dict[str, Any]:
    """
    Main pipeline task that processes a document through all stages

    This is called by RQ worker
    """
    logger.info(f"Starting pipeline for job {job_id}")

    job = get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}

    try:
        # Textlayer check
        job.status = JobStatus.TEXTLAYER_CHECK
        job.add_step("textlayer_check")
        update_job(job)

        has_text = _check_textlayer(job.input_file)
        job.complete_step("textlayer_check", confidence=1.0 if has_text else 0.0)

        # OCR if needed
        if not has_text:
            job.status = JobStatus.OCR
            job.add_step("ocr")
            update_job(job)

            _run_ocr(job.input_file)
            job.complete_step("ocr", method="tesseract", confidence=0.8)

        # Parse
        job.status = JobStatus.PARSE
        job.add_step("parse")
        update_job(job)

        parsed_data = _parse_document(job.input_file, job.model_name)
        job.complete_step("parse", method="docling", confidence=0.9)

        # Normalize
        job.status = JobStatus.NORMALIZE
        job.add_step("normalize")
        update_job(job)

        normalized_data = _normalize_data(parsed_data)
        job.complete_step("normalize", confidence=1.0)

        # Extract
        job.status = JobStatus.EXTRACT
        job.add_step("extract")
        update_job(job)

        extracted = _extract_entities(normalized_data)
        job.complete_step("extract", confidence=0.85)

        # Chunk
        job.status = JobStatus.CHUNK
        job.add_step("chunk")
        update_job(job)

        chunks = _create_chunks(normalized_data)
        job.complete_step("chunk", metadata={"chunk_count": len(chunks)})

        # Embed
        job.status = JobStatus.EMBED
        job.add_step("embed")
        update_job(job)

        embeddings = _create_embeddings(chunks)
        job.complete_step("embed", method="sentence-transformers", confidence=1.0)

        # Index
        job.status = JobStatus.INDEX
        job.add_step("index")
        update_job(job)

        _index_to_qdrant(chunks, embeddings, job.model_name)
        job.complete_step("index", metadata={"indexed_count": len(chunks)})

        # Done
        job.status = JobStatus.DONE
        job.result = {"chunks": len(chunks), "model": job.model_name, "file": job.input_file}
        update_job(job)

        logger.info(f"Pipeline completed for job {job_id}")
        return {"status": "success", "job_id": job_id}

    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
        job.status = JobStatus.FAILED
        job.error = str(e)
        update_job(job)
        return {"status": "error", "error": str(e)}


# ============================================================
# Helper Functions (minimal stubs, reuse existing logic)
# ============================================================


def _check_textlayer(file_path: str) -> bool:
    """Check if PDF has text layer"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        if len(reader.pages) > 0:
            text = reader.pages[0].extract_text()
            return len(text.strip()) > 50
    except Exception:
        pass
    return False


def _run_ocr(file_path: str) -> None:
    """Run OCR on PDF"""
    # Reuse existing ocr_processor if available
    try:
        from scripts.ocr_processor import process_pdf_ocr

        process_pdf_ocr(file_path)
    except Exception as e:
        logger.warning(f"OCR processing failed: {e}")


def _parse_document(file_path: str, model_name: Optional[str]) -> Dict[str, Any]:
    """Parse document"""
    # Reuse existing parsers
    return {"text": "parsed content", "pages": []}


def _normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize parsed data"""
    return data


def _extract_entities(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract entities (codes, references, etc.)"""
    return data


def _create_chunks(data: Dict[str, Any]) -> list:
    """Create chunks for indexing"""
    return []


def _create_embeddings(chunks: list) -> list:
    """Create embeddings"""
    return []


def _index_to_qdrant(chunks: list, embeddings: list, collection: Optional[str]) -> None:
    """Index to Qdrant"""
    pass
