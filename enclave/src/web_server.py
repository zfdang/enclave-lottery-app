"""
FastAPI Web Server for Lottery Enclave
Serves frontend and provides API endpoints
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BetRequest(BaseModel):
    user_address: str
    amount: float
    transaction_hash: str


class ConnectWalletRequest(BaseModel):
    address: str
    signature: str


class LotteryWebServer:
    """Web server for the lottery application"""
    
    def __init__(self, config, scheduler, blockchain_client):
        self.config = config
        self.scheduler = scheduler
        self.blockchain_client = blockchain_client
        self.app = FastAPI(title="Lottery Enclave API")
        self.websocket_connections: List[WebSocket] = []
        
        self.setup_middleware()
        self.setup_routes()
        self.setup_static_files()
        
    def setup_middleware(self):
        """Setup CORS and other middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, specify allowed origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
    def setup_static_files(self):
        """Setup static file serving for frontend"""
        frontend_dist = Path(__file__).parent / "frontend" / "dist"
        if frontend_dist.exists():
            # Mount assets directory for JS/CSS files
            assets_dir = frontend_dist / "assets"
            if assets_dir.exists():
                self.app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
            
            # Mount the dist directory for other static files (icons, etc.)
            self.app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")
            
    def setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/")
        async def serve_frontend():
            """Serve the main frontend page"""
            frontend_file = Path(__file__).parent / "frontend" / "dist" / "index.html"
            if frontend_file.exists():
                return HTMLResponse(content=frontend_file.read_text())
            return HTMLResponse(content="<h1>Lottery Enclave - Frontend not built</h1>")
            
        @self.app.get("/{file_path:path}")
        async def serve_static_files(file_path: str):
            """Serve static files from frontend dist directory"""
            # Only serve files that don't start with 'api'
            if file_path.startswith('api'):
                raise HTTPException(status_code=404, detail="Not found")
                
            frontend_dist = Path(__file__).parent / "frontend" / "dist"
            file_full_path = frontend_dist / file_path
            
            # Security check: ensure file is within the dist directory
            try:
                file_full_path.resolve().relative_to(frontend_dist.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="Not found")
                
            if file_full_path.exists() and file_full_path.is_file():
                # Determine content type
                content_type = "text/plain"
                if file_path.endswith('.js'):
                    content_type = "application/javascript"
                elif file_path.endswith('.css'):
                    content_type = "text/css"
                elif file_path.endswith('.svg'):
                    content_type = "image/svg+xml"
                elif file_path.endswith('.png'):
                    content_type = "image/png"
                elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                    content_type = "image/jpeg"
                    
                with open(file_full_path, 'rb') as f:
                    content = f.read()
                return Response(content=content, media_type=content_type)
            
            raise HTTPException(status_code=404, detail="Not found")
            
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
            
        @self.app.get("/api/attestation")
        async def get_attestation():
            """Get enclave attestation document"""
            # This would return the actual attestation in production
            return {
                "attestation": "mock_attestation_document",
                "pcrs": {
                    "PCR0": "mock_pcr0_value",
                    "PCR1": "mock_pcr1_value",
                    "PCR2": "mock_pcr2_value"
                }
            }
            
        @self.app.get("/api/draw/current")
        async def get_current_draw():
            """Get current lottery draw information"""
            try:
                current_draw = await self.scheduler.get_current_draw()
                if not current_draw:
                    raise HTTPException(status_code=404, detail="No active draw")
                    
                return {
                    "draw_id": current_draw.draw_id,
                    "start_time": current_draw.start_time.isoformat(),
                    "end_time": current_draw.end_time.isoformat(),
                    "draw_time": current_draw.draw_time.isoformat(),
                    "status": current_draw.status,
                    "total_pot": str(current_draw.total_pot),
                    "participants": len(current_draw.bets),
                    "time_remaining": max(0, (current_draw.draw_time - datetime.utcnow()).total_seconds())
                }
            except Exception as e:
                logger.error(f"Error getting current draw: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
                
        @self.app.get("/api/draw/participants")
        async def get_participants():
            """Get current draw participants"""
            try:
                current_draw = await self.scheduler.get_current_draw()
                if not current_draw:
                    return {"participants": []}
                    
                participants = []
                for bet in current_draw.bets:
                    participants.append({
                        "address": bet.user_address,
                        "amount": str(bet.amount),
                        "tickets": len(bet.ticket_numbers),
                        "timestamp": bet.timestamp.isoformat()
                    })
                    
                return {"participants": participants}
            except Exception as e:
                logger.error(f"Error getting participants: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
                
        @self.app.get("/api/history")
        async def get_lottery_history():
            """Get lottery draw history"""
            try:
                history = await self.scheduler.get_draw_history(limit=10)
                return {"history": history}
            except Exception as e:
                logger.error(f"Error getting history: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
                
        @self.app.get("/api/activities")
        async def get_recent_activities():
            """Get recent user activities"""
            try:
                activities = await self.scheduler.get_recent_activities(limit=20)
                return {"activities": activities}
            except Exception as e:
                logger.error(f"Error getting activities: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
                
        @self.app.post("/api/auth/connect")
        async def connect_wallet(request: ConnectWalletRequest):
            """Connect user wallet"""
            try:
                # Verify wallet signature
                is_valid = await self.blockchain_client.verify_signature(
                    request.address, 
                    request.signature
                )
                
                if not is_valid:
                    raise HTTPException(status_code=400, detail="Invalid signature")
                    
                # Log user connection
                await self.scheduler.log_activity(
                    request.address, 
                    "connect", 
                    {"timestamp": datetime.utcnow().isoformat()}
                )
                
                return {"status": "connected", "address": request.address}
            except Exception as e:
                logger.error(f"Error connecting wallet: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
                
        @self.app.post("/api/bet")
        async def place_bet(request: BetRequest):
            """Place a bet in the current lottery"""
            try:
                # Verify transaction
                is_valid = await self.blockchain_client.verify_transaction(
                    request.transaction_hash,
                    request.user_address,
                    request.amount
                )
                
                if not is_valid:
                    raise HTTPException(status_code=400, detail="Invalid transaction")
                    
                # Place bet
                bet_result = await self.scheduler.place_bet(
                    request.user_address,
                    request.amount,
                    request.transaction_hash
                )
                
                if not bet_result["success"]:
                    raise HTTPException(status_code=400, detail=bet_result["error"])
                    
                # Broadcast update to all connected clients
                await self.broadcast_update({
                    "type": "bet_placed",
                    "data": {
                        "user": request.user_address,
                        "amount": request.amount,
                        "tickets": bet_result["ticket_numbers"]
                    }
                })
                
                return bet_result
            except Exception as e:
                logger.error(f"Error placing bet: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
                
        @self.app.websocket("/ws/lottery")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                while True:
                    # Keep connection alive and handle incoming messages
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                        
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
                    
    async def broadcast_update(self, message: Dict):
        """Broadcast update to all connected WebSocket clients"""
        if not self.websocket_connections:
            return
            
        message_str = json.dumps(message)
        disconnected = []
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                disconnected.append(websocket)
                
        # Remove disconnected clients
        for websocket in disconnected:
            self.websocket_connections.remove(websocket)
            
    async def start(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the web server"""
        import uvicorn
        
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    async def stop(self):
        """Stop the web server"""
        logger.info("Stopping web server")
        # Close all WebSocket connections
        for websocket in self.websocket_connections:
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        self.websocket_connections.clear()