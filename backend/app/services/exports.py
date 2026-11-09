"""Excel files made in the background (ExportJob): with hundreds of thousands of soldiers a file takes minutes, longer
than a request may last. The page asks for the file, follows the job, and downloads it when it is ready."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ExportJob, User
from app.services import background

log = logging.getLogger("exports")

FOLDER = "exports"
KEEP_HOURS = 24  # a file can be downloaded again during that time, then it is removed
STALE_HOURS = 3  # a job still unfinished after that was cut short (the API restarted)
MAX_UNFINISHED_PER_USER = 3
UNFINISHED = ("queued", "running")


def job_dict(job: ExportJob) -> dict:
    return {"id": job.id, "kind": job.kind, "title": job.title, "filename": job.filename, "status": job.status,
            "size": job.size, "error": job.error, "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None}


def start(db: Session, user: User, kind: str, title: str, filename: str,
          build: Callable[[Session, User], BytesIO]) -> ExportJob:
    """Queues build(db, user) -> the .xlsx content; returns the job at once (status "queued")."""
    recent = datetime.now() - timedelta(hours=STALE_HOURS)
    unfinished = db.scalar(select(func.count(ExportJob.id)).where(
        ExportJob.user_id == user.id, ExportJob.status.in_(UNFINISHED), ExportJob.created_at >= recent))
    if unfinished >= MAX_UNFINISHED_PER_USER:
        raise HTTPException(429, "អ្នកមានឯកសារ Excel កំពុងរៀបចំច្រើនពេកហើយ — សូមរង់ចាំឲ្យរួចសិន")
    job = ExportJob(user_id=user.id, kind=kind, title=title[:200], filename=filename[:200], status="queued",
                    created_at=datetime.now())
    db.add(job)
    db.commit()
    job_id, user_id = job.id, user.id

    def run(bg: Session):
        j = bg.get(ExportJob, job_id)
        j.status = "running"
        bg.commit()
        try:
            content = build(bg, bg.get(User, user_id)).getvalue()
            rel = f"{FOLDER}/{job_id}.xlsx"
            path = settings.storage_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            j.status, j.file_path, j.size = "done", rel, len(content)
        except HTTPException as e:
            bg.rollback()
            j.status, j.error = "failed", str(e.detail)[:500]
        except Exception:
            bg.rollback()
            log.exception("export job %s failed", job_id)
            j.status, j.error = "failed", "មានបញ្ហាពេលរៀបចំឯកសារ — សូមព្យាយាមម្ដងទៀត ឬចម្រាញ់ទិន្នន័យឲ្យតិចជាងនេះ"
        j.finished_at = datetime.now()
        bg.commit()

    background.submit(background.exports, run, f"export job {job_id}")
    return job


def own_job(db: Session, user: User, job_id: int) -> ExportJob:
    job = db.get(ExportJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "រកមិនឃើញឯកសារ")
    if job.status in UNFINISHED and job.created_at < datetime.now() - timedelta(hours=STALE_HOURS):
        job.status, job.error, job.finished_at = "failed", "ការរៀបចំត្រូវបានរំខាន — សូមនាំចេញម្ដងទៀត", datetime.now()
        db.commit()
    return job


def remove_old(db: Session) -> int:
    """Removes the jobs (and their files) older than KEEP_HOURS."""
    cutoff = datetime.now() - timedelta(hours=KEEP_HOURS)
    old = db.execute(select(ExportJob.id, ExportJob.file_path).where(ExportJob.created_at < cutoff)).all()
    for _, rel in old:
        if rel:
            (settings.storage_path / rel).unlink(missing_ok=True)
    if old:
        db.execute(delete(ExportJob).where(ExportJob.id.in_([i for i, _ in old])))
    return len(old)
