from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.api.routes import api_router
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORSミドルウェアの設定
origins = [
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix=settings.API_V1_STR)

# 静的ファイルの提供
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    # Fallback to current directory static
    if os.path.exists("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")

# ルートディレクトリのHTMLファイルへの直接アクセス
@app.get("/dashboard")
async def dashboard():
    return FileResponse("dashboard.html")

@app.get("/comments")
async def comments():
    return FileResponse("test_comments_v2.html")

@app.get("/trade-review")
async def trade_review():
    return FileResponse("trade_review.html")

@app.get("/patterns")
async def patterns():
    return FileResponse("pattern_dashboard.html")

@app.get("/test-analysis-update")
async def test_analysis_update():
    return FileResponse("test_analysis_update.html")

@app.get("/comment-revision-demo")
async def comment_revision_demo():
    return FileResponse("comment_revision_demo.html")

@app.get("/api-client.js")
async def api_client():
    return FileResponse("api-client.js")

# Test pages routes
@app.get("/test_review.html")
async def test_review():
    return FileResponse("test_review.html")

@app.get("/test_upload.html")
async def test_upload():
    return FileResponse("test_upload.html")

@app.get("/test_history.html")
async def test_history():
    return FileResponse("test_history.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}