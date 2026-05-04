"""API v1 router - imports and includes all route modules"""

from fastapi import APIRouter

from app.api.v1.test import router as test_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.content import router as content_router
from app.api.v1.league import include_all as include_league_routes

# Create the main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(test_router)
api_router.include_router(chatbot_router)
api_router.include_router(content_router)
include_league_routes(api_router)
