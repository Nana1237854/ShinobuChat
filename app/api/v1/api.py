from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    characters,
    conversations,
    live2d,
    memories,
    messages,
    sync,
    todos,
    users,
    voice,
)

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(memories.router)
api_router.include_router(todos.router)
api_router.include_router(sync.router)
api_router.include_router(characters.router)
api_router.include_router(live2d.router)
api_router.include_router(voice.router)
