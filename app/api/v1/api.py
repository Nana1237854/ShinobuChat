from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    characters,
    conversations,
    config,
    live2d,
    memories,
    messages,
    reminders,
    sync,
    skill_market,
    skills,
    todos,
    users,
    voice,
)

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(config.router)
api_router.include_router(skills.router)
api_router.include_router(skill_market.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(memories.router)
api_router.include_router(todos.router)
api_router.include_router(reminders.router)
api_router.include_router(sync.router)
api_router.include_router(characters.router)
api_router.include_router(live2d.router)
api_router.include_router(voice.router)
