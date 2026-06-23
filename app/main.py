import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.error_handlers import app_error_handler
from app.api.v1.api import api_router
from app.api.v1.routes import live2d as live2d_routes
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.init_db import init_db
from app.services.live2d_service import Live2DAssetService

_startup_logger = logging.getLogger("shinobu.startup")


def _check_production_config() -> None:
    warnings: list[str] = []

    if settings.jwt_secret_key == "replace-me-in-prod":
        warnings.append(
            "JWT secret key is still the default value. "
            "Set SC_JWT_SECRET_KEY to a random 64+ character string in .env for production."
        )
    if not settings.config_encryption_key.strip():
        warnings.append(
            "Config encryption key is not set. "
            "Set SC_CONFIG_ENCRYPTION_KEY in .env for production. "
            'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    if settings.cors_allow_origins == ["*"]:
        warnings.append(
            "CORS is configured to allow all origins (*). "
            "Set SC_CORS_ALLOW_ORIGINS to a specific list in .env for production."
        )

    for w in warnings:
        _startup_logger.warning("PRODUCTION WARNING: %s", w)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "shinobu-chat" / "dist"
live2d_assets = Live2DAssetService(FRONTEND_DIST)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(live2d_routes.router, prefix="/api")

    @app.on_event("startup")
    async def startup_event() -> None:
        from app.services.config_service import ConfigService

        ConfigService.validate_encryption_key()
        _check_production_config()
        init_db()

        if settings.reminder_background_enabled:
            import asyncio

            from app.db.session import SessionLocal
            from app.services.mode_service import ModeService
            from app.services.reminder_scheduler_service import ReminderSchedulerService

            async def reminder_loop() -> None:
                while True:
                    try:
                        await asyncio.sleep(settings.reminder_scan_interval_seconds)
                        db = SessionLocal()
                        try:
                            mode_svc = ModeService(db)
                            service = ReminderSchedulerService(db, mode_service=mode_svc)
                            events = service.scan_due_reminders()
                            if events:
                                logger.info(
                                    "Reminder scan produced %d events", len(events)
                                )
                        finally:
                            db.close()
                    except Exception:
                        logger.exception("Reminder background scan failed")

                    # Goal checkin scan
                    try:
                        db2 = SessionLocal()
                        try:
                            from app.services.goal_service import GoalService
                            goal_svc = GoalService(db2)
                            goal_events = goal_svc.scan_due_checkins()
                            if goal_events:
                                logger.info(
                                    "Goal checkin scan produced %d events", len(goal_events)
                                )
                        finally:
                            db2.close()
                    except Exception:
                        logger.exception("Goal checkin background scan failed")

            import logging

            logger = logging.getLogger("shinobu.reminder")
            asyncio.create_task(reminder_loop())

        if settings.diary_auto_generate_enabled:
            import asyncio

            from app.db.session import SessionLocal
            from app.services.diary_scheduler_service import DiarySchedulerService

            async def diary_loop() -> None:
                while True:
                    try:
                        await asyncio.sleep(settings.diary_background_scan_interval_seconds)
                        db = SessionLocal()
                        try:
                            service = DiarySchedulerService(db)
                            generated = service.scan_and_generate()
                            if generated:
                                _startup_logger.info("Auto-diary generated for %d users", generated)
                        finally:
                            db.close()
                    except Exception:
                        _startup_logger.exception("Diary background scan failed")

            asyncio.create_task(diary_loop())

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/assets/live2d/manifest.auto.json", include_in_schema=False)
    async def live2d_manifest() -> JSONResponse:
        return JSONResponse(live2d_assets.manifest())

    @app.post("/api/v1/live2d/import", tags=["live2d"])
    async def import_live2d(file: UploadFile = File(...)) -> JSONResponse:
        return JSONResponse(await live2d_assets.import_zip(file))

    if not (FRONTEND_DIST / "index.html").exists():
        @app.get("/", include_in_schema=False)
        async def frontend_not_built() -> None:
            raise HTTPException(
                status_code=503,
                detail="React frontend is not built. Run `npm run build` in frontend/shinobu-chat.",
            )
    else:
        app.mount(
            "/",
            StaticFiles(directory=FRONTEND_DIST, html=True),
            name="shinobu-chat-frontend",
        )

    return app


app = create_app()
