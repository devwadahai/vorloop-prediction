"""
WebSocket API for real-time updates.
"""
import asyncio
import json
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, asset: str):
        """Accept and register a new connection."""
        await websocket.accept()
        if asset not in self.active_connections:
            self.active_connections[asset] = set()
        self.active_connections[asset].add(websocket)
        logger.info(f"Client connected for {asset}. Total: {len(self.active_connections[asset])}")
    
    def disconnect(self, websocket: WebSocket, asset: str):
        """Remove a connection."""
        if asset in self.active_connections:
            self.active_connections[asset].discard(websocket)
            logger.info(f"Client disconnected from {asset}. Remaining: {len(self.active_connections[asset])}")
    
    async def broadcast(self, asset: str, message: dict):
        """Broadcast message to all connections for an asset."""
        if asset not in self.active_connections:
            return
        
        dead_connections = set()
        for connection in self.active_connections[asset]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        
        # Clean up dead connections
        self.active_connections[asset] -= dead_connections


manager = ConnectionManager()


@router.websocket("/stream/{asset}")
async def websocket_stream(websocket: WebSocket, asset: str):
    """
    WebSocket endpoint for real-time market data and predictions.
    
    Streams:
    - Price updates (1s)
    - Prediction updates (1m)
    - Market structure updates (1m)
    - Alerts
    """
    await manager.connect(websocket, asset.upper())
    
    try:
        while True:
            # Wait for messages from client (subscriptions, ping, etc.)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif message.get("type") == "subscribe":
                    channels = message.get("channels", [])
                    await websocket.send_json({
                        "type": "subscribed",
                        "channels": channels
                    })
                
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "heartbeat"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, asset.upper())
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, asset.upper())


async def push_price_update(asset: str, price_data: dict):
    """Push price update to all subscribers."""
    await manager.broadcast(asset, {
        "type": "price",
        "data": price_data
    })


async def push_prediction_update(asset: str, prediction: dict):
    """Push prediction update to all subscribers."""
    await manager.broadcast(asset, {
        "type": "prediction",
        "data": prediction
    })


async def push_market_structure_update(asset: str, market_data: dict):
    """Push market structure update to all subscribers."""
    await manager.broadcast(asset, {
        "type": "market_structure",
        "data": market_data
    })


async def push_alert(asset: str, alert: dict):
    """Push alert to all subscribers."""
    await manager.broadcast(asset, {
        "type": "alert",
        "data": alert
    })

