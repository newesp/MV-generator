from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


class JobStore:
    """Small in-memory job store for local MVP workflows."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = Lock()

    def create_job(self, workflow: str, message: str = "") -> dict:
        now = _utc_now()
        job_id = str(uuid4())
        job = {
            "job_id": job_id,
            "workflow": workflow,
            "status": "pending",
            "stage": "queued",
            "progress": 0.0,
            "message": message,
            "artifacts": {},
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._jobs[job_id] = job
        return deepcopy(job)

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def update_job(self, job_id: str, **changes) -> dict:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Unknown job_id: {job_id}")
            job = self._jobs[job_id]
            artifacts = changes.pop("artifacts", None)
            if artifacts:
                job.setdefault("artifacts", {}).update(artifacts)
            job.update(changes)
            job["updated_at"] = _utc_now()
            return deepcopy(job)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
