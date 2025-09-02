from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Support running via `uvicorn app.main:app` (recommended) and also
# direct script execution `python backend/app/main.py` by ensuring the
# parent (backend) directory is on sys.path for 'app' package imports.
try:
    from app.api.routes import health, awards
    from app.core.config import get_settings
except ModuleNotFoundError:  # pragma: no cover - fallback path adjust
    import sys
    from pathlib import Path

    parent = Path(__file__).resolve().parents[1]
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from app.api.routes import health, awards
    from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.version)

# Basic CORS allowing local dev and docker internal hostnames
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://frontend:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(awards.router)


@app.get("/", summary="Root")
async def root() -> dict[str, str]:
    return {"app": settings.app_name, "version": settings.version}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
