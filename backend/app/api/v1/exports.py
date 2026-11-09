"""Excel files made in the background: the user's jobs, their state, the file when it is ready."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import ExportJob, User
from app.services import exports
from app.services.common import storage_file

router = APIRouter(prefix="/export-jobs", tags=["export jobs"])


@router.get("")
def my_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    since = datetime.now() - timedelta(hours=exports.KEEP_HOURS)
    jobs = db.scalars(select(ExportJob).where(ExportJob.user_id == user.id, ExportJob.created_at >= since)
                      .order_by(ExportJob.id.desc()).limit(50))
    return [exports.job_dict(j) for j in jobs]


@router.get("/{job_id}")
def job_state(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exports.job_dict(exports.own_job(db, user, job_id))


@router.get("/{job_id}/file")
def job_file(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = exports.own_job(db, user, job_id)
    if job.status != "done" or not job.file_path:
        raise HTTPException(409, "ឯកសារមិនទាន់រួចរាល់")
    return FileResponse(storage_file(job.file_path), filename=job.filename,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
