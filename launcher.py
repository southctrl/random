import logging
import os
import sys
from fastapi import FastAPI

from core.api import router
from core.api.internal import router as internal_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Expel Discord Controller",
    description="Clean Discord Selfbot using custom headers and WebSocket gateway",
    redoc_url=None,
)

app.include_router(router, prefix="", tags=["discord"])
app.include_router(internal_router, prefix="/api/internal", tags=["internal"])


@app.get("/")
async def root():
    return {
        "service": "Expel Discord Controller",
        "version": "2.0.0",
        "health": "ok",
        "docs": "/docs",
        "routes": "/api/v1"
    }


if __name__ == "__main__":
    import uvicorn

    want_reload = os.environ.get("UVICORN_RELOAD", "").lower() in (
        "1",
        "true",
        "yes",
    )
    
    logger.info("Starting Expel Discord Controller...")
    uvicorn.run(
        "launcher:app",
        host="0.0.0.0",
        port=8000,
        reload=want_reload,
        reload_dirs=[os.path.dirname(__file__)],
        factory=False,
    )
