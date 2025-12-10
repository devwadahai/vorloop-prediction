"""
Crypto Prediction Engine - FastAPI Application
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from core.config import settings
from api.routes import router as api_router
from api.websocket import router as ws_router
from services.data_service import DataService
from services.model_service import ModelService
from services.prediction_tracker import PredictionTracker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    logger.info(f"Starting {settings.app_name}...")
    
    # Initialize services
    app.state.data_service = DataService()
    app.state.model_service = ModelService()
    app.state.prediction_tracker = PredictionTracker(data_service=app.state.data_service)
    
    # Load models
    await app.state.model_service.load_models()
    
    # Start background tasks
    if settings.enable_websocket:
        app.state.data_task = asyncio.create_task(
            app.state.data_service.start_streaming()
        )
    
    # Start prediction validation loop
    app.state.tracker_task = asyncio.create_task(
        app.state.prediction_tracker.start_validation_loop()
    )
    
    logger.info("Application started successfully")
    logger.info("📊 Prediction tracking enabled - validations will run automatically")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    
    # Stop tracker
    app.state.prediction_tracker.stop()
    if hasattr(app.state, 'tracker_task'):
        app.state.tracker_task.cancel()
        try:
            await app.state.tracker_task
        except asyncio.CancelledError:
            pass
    
    if hasattr(app.state, 'data_task'):
        app.state.data_task.cancel()
        try:
            await app.state.data_task
        except asyncio.CancelledError:
            pass
    
    await app.state.data_service.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="Next-generation crypto prediction terminal API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/ws")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.model_version,
        "environment": settings.environment,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )

