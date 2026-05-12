from fastapi import APIRouter

from app.api.v1.routes import auth, characters, conversations, memories, messages, sync, todos, users

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(memories.router)
api_router.include_router(todos.router)
api_router.include_router(sync.router)
api_router.include_router(characters.router)
