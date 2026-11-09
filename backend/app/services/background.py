"""Work done after the response: Excel files too large to make within a request, dashboard figures counted again,
the hourly maintenance. The API runs several workers (processes): a MySQL named lock makes sure only one of them
does a given piece of work at a time."""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha1

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine

log = logging.getLogger("background")

# Excel files: two at a time per worker, the others wait their turn (each one reads the whole list)
exports = ThreadPoolExecutor(max_workers=2, thread_name_prefix="export")
# dashboard figures: one at a time per worker
counts = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dashboard")


def lock_name(name: str) -> str:
    """MySQL lock names are at most 64 characters."""
    return name if len(name) <= 64 else f"{name[:20]}:{sha1(name.encode()).hexdigest()}"


@contextmanager
def db_lock(name: str, wait_seconds: int = 0):
    """Yields True when this process holds the lock `name` (released at the end), False when another one still holds
    it after `wait_seconds`. The lock has its own connection (a MySQL lock belongs to the connection that took it),
    so the work inside may commit as it likes."""
    name = lock_name(name)
    with engine.connect() as conn:
        got = conn.execute(text("SELECT GET_LOCK(:n, :w)"), {"n": name, "w": wait_seconds}).scalar() == 1
        try:
            yield got
        finally:
            if got:
                conn.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": name})


# tests: the work is done at once in this session (theirs is one transaction that the pool's connections cannot see)
inline_session: Callable[[], Session] | None = None


def submit(pool: ThreadPoolExecutor, fn: Callable[[Session], None], what: str) -> None:
    """Runs fn(db) in the pool with its own session; an error is logged, never raised."""
    if inline_session is not None:
        db = inline_session()
        fn(db)
        db.commit()
        return

    def run():
        db = SessionLocal()
        try:
            fn(db)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("%s failed", what)
        finally:
            db.close()
    pool.submit(run)
