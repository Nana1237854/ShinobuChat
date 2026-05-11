from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.services.live2d_service import Live2DAssetService

FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent / "frontend" / "shinobu-chat" / "dist"
)
live2d_assets = Live2DAssetService(FRONTEND_DIST)


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

    @app.on_event("startup")
    async def startup_event() -> None:
        init_db()

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/assets/live2d/manifest.auto.json", include_in_schema=False)
    async def live2d_manifest() -> JSONResponse:
        return JSONResponse(live2d_assets.manifest())

    @app.post("/api/v1/live2d/import", tags=["live2d"])
    async def import_live2d(file: UploadFile = File(...)) -> JSONResponse:
        return JSONResponse(await live2d_assets.import_zip(file))

    # Serve frontend static files as catch-all (after API routes)
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )

    return app


app = create_app()
