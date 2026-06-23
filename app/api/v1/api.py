from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    characters,
    conversations,
    config,
    diaries,
    emotion,
    goals,
    interactions,
    live2d,
    memories,
    messages,
    modes,
    persona,
    reminders,
    sync,
    skill_market,
    skills,
    todos,
    users,
    vision,
    voice,
)

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(config.router)
api_router.include_router(skills.router)
api_router.include_router(skill_market.router)
api_router.include_router(persona.router)
api_router.include_router(goals.router)
api_router.include_router(emotion.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(memories.router)
api_router.include_router(todos.router)
api_router.include_router(reminders.router)
api_router.include_router(sync.router)
api_router.include_router(characters.router)
api_router.include_router(live2d.router)
api_router.include_router(voice.router)
api_router.include_router(modes.router)
api_router.include_router(vision.router)
api_router.include_router(diaries.router)
api_router.include_router(interactions.router)
