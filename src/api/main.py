"""FastAPI application for Prospector V1."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat
from src.core.database import (
    async_engine,
    close_checkpointer,
    create_db_and_tables,
    init_checkpointer,
)
from src.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for startup and shutdown."""
    # Startup
    configure_logging()
    logger.info("Prospector API starting up")
    await create_db_and_tables()
    await init_checkpointer()
    yield
    # Shutdown
    await close_checkpointer()
    await async_engine.dispose()


app = FastAPI(
    title="Prospector API",
    description="Location intelligence and site selection API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Prospector API v1", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
