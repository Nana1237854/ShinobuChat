from fastapi import APIRouter

from app.api.v1.routes import auth, conversations, live2d, messages, users, voice

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(live2d.router)
api_router.include_router(voice.router)
