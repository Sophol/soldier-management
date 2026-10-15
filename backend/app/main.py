from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import conscripts, decisions, documents, master, records, reports, soldiers, system
from app.core.config import settings
from app.core.database import engine

app = FastAPI(title="Soldier Management API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

api = APIRouter(prefix="/api/v1")
for module in (system, master, soldiers, documents, decisions, records, conscripts, reports):
    api.include_router(module.router)
app.include_router(api)


@app.get("/api/health", tags=["health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
