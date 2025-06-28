from fastapi import APIRouter

from src.api.v1.endpoints import users, forex

api_router = APIRouter()

api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(forex.router, prefix="/forex", tags=["forex"])