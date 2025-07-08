from fastapi import APIRouter
from app.api.endpoints import analysis, history, review, comments, trade_review, patterns, learning

api_router = APIRouter()

# Include routers
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(review.router, prefix="/review", tags=["review"])
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(trade_review.router, prefix="/trade-review", tags=["trade-review"])
api_router.include_router(patterns.router, prefix="/patterns", tags=["patterns"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])