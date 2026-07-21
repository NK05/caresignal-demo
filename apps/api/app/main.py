from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.clinician import router as clinician_router
from app.api.demo import router as demo_router
from app.api.patient import router as patient_router
from app.api.system import router as system_router
from app.api.whatsapp import router as whatsapp_router
from app.config import get_settings
from app.database import initialize_database

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.caresignal_auto_bootstrap:
        initialize_database()
    yield


app = FastAPI(
    title="CareSignal API",
    description="Synthetic-data hypertension follow-up workflow prototype.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Demo-Session",
        "X-Demo-Reset-Token",
        "X-Demo-System-Token",
    ],
)

app.include_router(demo_router)
app.include_router(patient_router)
app.include_router(clinician_router)
app.include_router(system_router)
app.include_router(whatsapp_router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "service": "caresignal-api",
        "status": "ok",
        "documentation": "/docs",
    }


@app.get("/api/v1/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "service": "caresignal-api",
        "status": "ok",
        "version": "0.1.0",
        "environment": settings.caresignal_env,
    }
