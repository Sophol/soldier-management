import logging
import threading
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import conscripts, decisions, documents, exports, master, records, reports, soldiers, system
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.services import maintenance

log = logging.getLogger("decisions")


def _apply_due_once() -> None:
    db = SessionLocal()
    try:
        if n := decisions.apply_due(db):
            log.info("applied %s decision(s) that came into effect", n)
        db.commit()
    except Exception:  # never let the job die: try again at the next run
        db.rollback()
        log.exception("applying decisions that came into effect failed")
    finally:
        db.close()


def _apply_due_loop(stop: threading.Event) -> None:
    """Approved decisions with a future effective date change the soldiers' records on that date."""
    while True:
        _apply_due_once()
        if stop.wait(settings.DECISION_APPLY_MINUTES * 60):
            return


def _maintenance_loop(stop: threading.Event) -> None:
    """The activity-log retention and the old Excel exports (services/maintenance.py), every MAINTENANCE_MINUTES."""
    wait = 60  # the first run a minute after the start, then every MAINTENANCE_MINUTES
    while not stop.wait(wait):
        wait = settings.MAINTENANCE_MINUTES * 60
        db = SessionLocal()
        try:
            maintenance.run_once(db)
        except Exception:
            db.rollback()
            logging.getLogger("maintenance").exception("maintenance failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop = threading.Event()
    if settings.DECISION_APPLY_MINUTES > 0:
        threading.Thread(target=_apply_due_loop, args=(stop,), name="apply-due-decisions", daemon=True).start()
    if settings.MAINTENANCE_MINUTES > 0:
        threading.Thread(target=_maintenance_loop, args=(stop,), name="maintenance", daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="Soldier Management API", version="1.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

api = APIRouter(prefix="/api/v1")
for module in (system, master, soldiers, documents, decisions, records, conscripts, reports, exports):
    api.include_router(module.router)
app.include_router(api)


@app.get("/api/health", tags=["health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "version": app.version}
