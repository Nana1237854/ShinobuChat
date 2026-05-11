from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.v1.api import api_router
from app.api.v1.routes import live2d as live2d_routes
from app.core.config import settings
from app.db.init_db import init_db

PROTOTYPE_PATH = Path(__file__).resolve().parent.parent / "shinobuchat_prototype.html"


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(live2d_routes.router, prefix="/api")

    @app.on_event("startup")
    async def startup_event() -> None:
        init_db()

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def prototype() -> FileResponse:
        return FileResponse(PROTOTYPE_PATH)

    return app


app = create_app()
