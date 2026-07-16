"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import profiles_router, reports_router, zips_router

app = FastAPI(
    title="Prospector",
    description="Location Intelligence Reports API for franchise development and CRE brokers",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(profiles_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(zips_router, prefix="/api")


@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "name": "Prospector API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
