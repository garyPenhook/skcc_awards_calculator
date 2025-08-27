# Architecture Overview

## Components
- Backend: FastAPI application (ASGI) with modular structure (api/core/db/models/schemas)
- Frontend: React + TypeScript (Vite) consuming backend REST endpoints
- Database: PostgreSQL (dev fallback: SQLite aiosqlite)
- Infra: Docker Compose orchestrating backend, frontend, db
- CI: GitHub Actions (lint, type check, test, build)

## Flow
Frontend -> `/health` (proxied or direct) -> FastAPI router -> returns JSON status.

## Configuration
Environment variables via `.env` loaded by pydantic-settings. Default DB is SQLite for local simplicity; override with Postgres URL in container.

## Future
- Add Alembic migrations in backend/app/db/migrations
- Add auth (JWT) and user domain modules
- Add caching (Redis) and background task queue (RQ/Celery) as needed

