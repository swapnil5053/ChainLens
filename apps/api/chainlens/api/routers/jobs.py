from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from ...db.models import Job
from ...db.session import session_scope
from ..schemas import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID) -> JobResponse:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobResponse(
            job_id=job.id,
            document_id=job.document_id,
            state=job.state,
            progress=job.progress,
            detail=job.detail,
            error=job.error,
            timings_ms=job.timings_ms,
        )
