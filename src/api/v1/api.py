from fastapi import APIRouter

from src.api.v1.endpoints import forex, candlestick

api_router = APIRouter()

# api_router.include_router(users.router, prefix="/users", tags=["users"])  # Temporarily disabled - no User model
api_router.include_router(forex.router, prefix="/forex", tags=["forex"])
api_router.include_router(candlestick.router, prefix="/candlesticks", tags=["candlesticks"])