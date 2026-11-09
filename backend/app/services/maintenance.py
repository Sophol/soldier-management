"""Hourly upkeep, done by one API worker at a time: the activity log older than `audit_retention_years` is removed
(in small batches, so the log stays usable meanwhile) and the Excel files of the background exports are cleared."""

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Setting
from app.services import exports
from app.services.background import db_lock

log = logging.getLogger("maintenance")
BATCH = 5000


def retention_years(db: Session) -> int:
    s = db.get(Setting, "audit_retention_years")
    try:
        return max(int(s.value), 0) if s and s.value not in (None, "") else 0
    except ValueError:
        return 0


def _years_ago(years: int) -> datetime:
    now = datetime.now()
    try:
        return now.replace(year=now.year - years)
    except ValueError:  # 29 February
        return now.replace(year=now.year - years, day=28)


def prune_audit_log(db: Session) -> int:
    """Removes the activity-log rows older than the retention (0 years = keep everything); returns how many."""
    years = retention_years(db)
    if not years:
        return 0
    cutoff = _years_ago(years)
    removed = 0
    while True:
        ids = db.scalars(select(AuditLog.id).where(AuditLog.created_at < cutoff).order_by(AuditLog.id).limit(BATCH)).all()
        if not ids:
            return removed
        db.execute(delete(AuditLog).where(AuditLog.id.in_(ids)))
        db.commit()
        removed += len(ids)


def run_once(db: Session) -> None:
    with db_lock("maintenance") as got:
        if not got:  # another worker is doing it
            return
        if n := prune_audit_log(db):
            log.info("removed %s activity-log rows older than the retention", n)
        if n := exports.remove_old(db):
            log.info("removed %s old Excel export(s)", n)
        db.commit()
