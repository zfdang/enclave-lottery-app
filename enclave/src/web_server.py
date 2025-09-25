"""
Enhanced FastAPI Web Server for Automated Lottery System

Provides modern API endpoints for the single-round lottery system with:
- Real-time round information
- Player betting interface  
- Operator status monitoring
- WebSocket live updates
- Memory-based event streaming
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lottery.models import RoundState, LotteryRound, ContractEvent
from lottery.event_manager import memory_store
from lottery.operator import AutomatedOperator
from blockchain.client import BlockchainClient

logger = logging.getLogger(__name__)


# =============== REQUEST/RESPONSE MODELS ===============

class BetRequest(BaseModel):
    """Player bet request"""
    player_address: str
    amount: int  # Amount in wei
    signature: str  # Wallet signature for authentication


class WalletConnectionRequest(BaseModel):
    """Wallet connection request"""
    address: str
    signature: str
    message: Optional[str] = None


class OperatorActionRequest(BaseModel):
    """Manual operator action request"""
    action: str  # 'create_round', 'draw_round', 'refund_round'
    round_id: Optional[int] = None
    reason: Optional[str] = None


# =============== ENHANCED WEB SERVER ===============


class LotteryWebServer:
    """
    Enhanced web server for the automated lottery system.
    
    Provides comprehensive API for:
    - Current round information and real-time updates
    - Player betting interface with wallet integration
    - Operator status and manual overrides
    - System monitoring and health checks
    - WebSocket live event streaming
    """
    
    def __init__(self, config: Dict[str, Any], operator: AutomatedOperator, blockchain_client: BlockchainClient):
        self.config = config
        self.operator = operator
        self.blockchain_client = blockchain_client
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="Automated Lottery System API",
            description="API for single-round lottery with automated operator",
            version="2.0.0"
        )
        
        # WebSocket connections for live updates
        self.websocket_connections: List[WebSocket] = []
        
        # Setup server components
        self._setup_middleware()
        self._setup_routes()
        self._setup_static_files()
        
        logger.info("Enhanced lottery web server initialized")
    def _setup_middleware(self) -> None:
        """Setup CORS and other middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_static_files(self) -> None:
        """Setup static file serving for React frontend"""
        frontend_dist = Path(__file__).parent / "frontend" / "dist"
        
        if frontend_dist.exists():
            # Mount assets directory for JS/CSS files
            assets_dir = frontend_dist / "assets"
            if assets_dir.exists():
                self.app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
                
            # Mount static files
            self.app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")
            
            logger.info(f"Frontend static files mounted from: {frontend_dist}")
        else:
            logger.warning("Frontend dist directory not found - run build script first")
            
    def _setup_routes(self) -> None:
        """Setup all API routes"""
        
        # =============== FRONTEND SERVING ===============
        
        @self.app.get("/")
        async def serve_frontend():
            """Serve the main React frontend"""
            frontend_file = Path(__file__).parent / "frontend" / "dist" / "index.html"
            if frontend_file.exists():
                return HTMLResponse(content=frontend_file.read_text())
            return HTMLResponse(content="<h1>Automated Lottery System - Frontend not built</h1>")
        
        # =============== SYSTEM STATUS ENDPOINTS ===============
        
        @self.app.get("/api/health")
        async def health_check():
            """System health check"""
            blockchain_health = await self.blockchain_client.health_check() if self.blockchain_client else None
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "web_server": True,
                    "operator": self.operator.is_running if self.operator else False,
                    "blockchain": blockchain_health['status'] if blockchain_health else 'unavailable',
                    "memory_store": True
                },
                "version": "2.0.0"
            }
        
        @self.app.get("/api/status")
        async def system_status():
            """Comprehensive system status"""
            operator_status = self.operator.get_operator_status() if self.operator else None
            blockchain_status = self.blockchain_client.get_client_status() if self.blockchain_client else None
            memory_stats = memory_store.get_system_statistics()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "operator": operator_status,
                "blockchain": blockchain_status,
                "memory_store": memory_stats,
                "websocket_connections": len(self.websocket_connections)
            }
        
        @self.app.get("/api/attestation")
        async def get_attestation():
            """Get nitro enclave attestation document (mockup for development)"""
            import base64
            import json
            
            # Mock attestation document structure
            mock_attestation = {
                "module_id": "i-1234567890abcdef0-enc0123456789abcdef",
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "digest": "SHA384",
                "pcrs": {
                    "0": "a" * 96,  # Boot ROM
                    "1": "b" * 96,  # Kernel and bootstrap
                    "2": "c" * 96,  # Application
                    "8": "d" * 96   # Certificate
                },
                "certificate": "-----BEGIN CERTIFICATE-----\nMockCertificateData\n-----END CERTIFICATE-----",
                "cabundle": ["-----BEGIN CERTIFICATE-----\nMockRootCA\n-----END CERTIFICATE-----"],
                "public_key": None,
                "user_data": base64.b64encode(json.dumps({
                    "lottery_contract": self.blockchain_client.contract_address if self.blockchain_client else "0x0000000000000000000000000000000000000000",
                    "operator_address": self.blockchain_client.account.address if self.blockchain_client and self.blockchain_client.account else "0x0000000000000000000000000000000000000000",
                    "enclave_version": "2.0.0",
                    "build_timestamp": "2025-09-25T00:00:00Z"
                }).encode()).decode(),
                "nonce": None
            }
            
            # Base64 encode the entire attestation document (as Nitro Enclaves do)
            attestation_document = base64.b64encode(
                json.dumps(mock_attestation).encode()
            ).decode()
            
            return {
                "attestation_document": attestation_document,
                "attestation_document_b64": attestation_document,  # Alternative field name
                "pcrs": mock_attestation["pcrs"],
                "user_data": mock_attestation["user_data"],
                "timestamp": mock_attestation["timestamp"],
                "verified": True,  # Mock verification status
                "note": "This is a mock attestation for development purposes"
            }
        
        # =============== LOTTERY ROUND ENDPOINTS ===============
        
        @self.app.get("/api/round/status")
        async def get_current_round():
            """Get current active round information"""
            try:
                current_round = memory_store.get_current_round()
                
                if not current_round:
                    return {
                        "round": None,
                        "message": "No active round",
                        "can_bet": False
                    }
                
                # Get current time for calculations
                current_time = int(datetime.now().timestamp())
                
                # Calculate time remaining for betting
                betting_time_remaining = 0
                if current_round.state == RoundState.BETTING and current_round.end_time:
                    betting_time_remaining = max(0, current_round.end_time - current_time)
                
                # Calculate draw window information
                draw_window_start = max(0, current_round.min_draw_time - current_time) if current_round.min_draw_time else 0
                draw_window_end = max(0, current_round.max_draw_time - current_time) if current_round.max_draw_time else 0
                
                return {
                    "round": {
                        "round_id": current_round.round_id,
                        "state": current_round.state.value,
                        "state_name": current_round.state.name,
                        "start_time": current_round.start_time,
                        "end_time": current_round.end_time,
                        "min_draw_time": current_round.min_draw_time,
                        "max_draw_time": current_round.max_draw_time,
                        "total_pot": current_round.total_pot,
                        "participant_count": current_round.participant_count,
                        "participants": current_round.participants,
                        "winner": current_round.winner,
                        "publisher_commission": current_round.publisher_commission,
                        "sparsity_commission": current_round.sparsity_commission,
                        "winner_prize": current_round.winner_prize
                    },
                    "can_bet": current_round.can_bet,
                    "can_draw": current_round.can_draw,
                    "is_finished": current_round.is_finished,
                    "is_active": current_round.is_active,
                    "betting_time_remaining": betting_time_remaining,
                    "draw_window_start": draw_window_start,
                    "draw_window_end": draw_window_end,
                    "current_time": current_time
                }
                
            except Exception as e:
                logger.error(f"Error getting current round: {e}")
                raise HTTPException(status_code=500, detail="Failed to get round information")
        
        @self.app.get("/api/round/participants")
        async def get_round_participants():
            """Get all participants and their bets for the current round"""
            try:
                current_round = memory_store.get_current_round()
                
                if not current_round:
                    return {
                        "round_id": None,
                        "participants": [],
                        "total_participants": 0,
                        "total_bets": 0,
                        "total_bet_amount": 0,
                        "message": "No active round"
                    }
                
                # Get all bets for the current round
                round_bets = memory_store.get_round_bets(current_round.round_id)
                
                # Group bets by player address
                participants_data = {}
                total_bet_amount = 0
                
                for bet in round_bets:
                    player_addr = bet.player_address
                    
                    if player_addr not in participants_data:
                        participants_data[player_addr] = {
                            "address": player_addr,
                            "bets": [],
                            "total_bet_amount": 0,
                            "bet_count": 0,
                            "ticket_numbers": []
                        }
                    
                    # Add bet information
                    bet_info = {
                        "amount": bet.amount,
                        "ticket_numbers": bet.ticket_numbers,
                        "timestamp": bet.timestamp.isoformat()
                    }
                    
                    participants_data[player_addr]["bets"].append(bet_info)
                    participants_data[player_addr]["total_bet_amount"] += bet.amount
                    participants_data[player_addr]["bet_count"] += 1
                    participants_data[player_addr]["ticket_numbers"].extend(bet.ticket_numbers)
                    
                    total_bet_amount += bet.amount
                
                # Convert to list format
                participants_list = list(participants_data.values())
                
                # Sort by total bet amount (descending)
                participants_list.sort(key=lambda x: x["total_bet_amount"], reverse=True)
                
                return {
                    "round_id": current_round.round_id,
                    "round_state": current_round.state.name,
                    "participants": participants_list,
                    "total_participants": len(participants_list),
                    "total_bets": sum(p["bet_count"] for p in participants_list),
                    "total_bet_amount": total_bet_amount,
                    "current_time": int(datetime.now().timestamp())
                }
                
            except Exception as e:
                logger.error(f"Error getting round participants: {e}")
                raise HTTPException(status_code=500, detail="Failed to get participants information")
        
        @self.app.get("/api/history")
        async def get_round_history(limit: int = 50):
            """Get historical rounds with final states, winners, and prizes"""
            try:
                # Validate limit parameter
                if limit <= 0:
                    limit = 50
                elif limit > 200:  # Cap maximum limit
                    limit = 200
                
                # Get round history from memory store
                historical_rounds = memory_store.get_round_history(limit=limit)
                
                # Process each round to extract relevant historical data
                history_data = []
                
                for round_data in historical_rounds:
                    # Calculate derived values
                    total_commission = round_data.publisher_commission + round_data.sparsity_commission
                    
                    # Get bet count for this round
                    round_bets = memory_store.get_round_bets(round_data.round_id)
                    total_bets_placed = len(round_bets)
                    
                    # Format round data for history view
                    round_info = {
                        "round_id": round_data.round_id,
                        "final_state": round_data.state.name,
                        "final_state_value": round_data.state.value,
                        "start_time": round_data.start_time,
                        "end_time": round_data.end_time,
                        "min_draw_time": round_data.min_draw_time,
                        "max_draw_time": round_data.max_draw_time,
                        "total_pot": round_data.total_pot,
                        "participant_count": round_data.participant_count,
                        "total_bets_placed": total_bets_placed,
                        "winner": round_data.winner,
                        "winner_prize": round_data.winner_prize,
                        "publisher_commission": round_data.publisher_commission,
                        "sparsity_commission": round_data.sparsity_commission,
                        "total_commission": total_commission,
                        "is_completed": round_data.state == RoundState.COMPLETED,
                        "is_refunded": round_data.state == RoundState.REFUNDED,
                        "has_winner": round_data.winner is not None
                    }
                    
                    history_data.append(round_info)
                
                # Calculate summary statistics
                total_rounds = len(history_data)
                completed_rounds = len([r for r in history_data if r["is_completed"]])
                refunded_rounds = len([r for r in history_data if r["is_refunded"]])
                total_volume = sum(r["total_pot"] for r in history_data)
                total_prizes_awarded = sum(r["winner_prize"] for r in history_data if r["has_winner"])
                
                return {
                    "rounds": history_data,
                    "summary": {
                        "total_rounds": total_rounds,
                        "completed_rounds": completed_rounds,
                        "refunded_rounds": refunded_rounds,
                        "completion_rate": (completed_rounds / total_rounds * 100) if total_rounds > 0 else 0,
                        "total_volume": total_volume,
                        "total_prizes_awarded": total_prizes_awarded,
                        "average_pot_size": (total_volume / total_rounds) if total_rounds > 0 else 0
                    },
                    "pagination": {
                        "limit": limit,
                        "returned_count": len(history_data)
                    },
                    "timestamp": int(datetime.now().timestamp())
                }
                
            except Exception as e:
                logger.error(f"Error getting round history: {e}")
                raise HTTPException(status_code=500, detail="Failed to get round history")
        
        @self.app.get("/api/contract/config")
        async def get_contract_config():
            """Get lottery contract configuration"""
            try:
                if not self.blockchain_client:
                    raise HTTPException(status_code=503, detail="Blockchain service unavailable")
                
                config = await self.blockchain_client.get_contract_config()
                
                return {
                    "config": config,
                    "contract_address": self.blockchain_client.contract_address,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting contract config: {e}")
                raise HTTPException(status_code=500, detail="Failed to get contract configuration")
        
        
        
        # =============== WEBSOCKET ENDPOINT ===============
        
        @self.app.websocket("/ws/lottery")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time lottery updates"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            logger.info(f"WebSocket client connected. Total connections: {len(self.websocket_connections)}")
            
            try:
                # Send initial state
                current_round = memory_store.get_current_round()
                await websocket.send_text(json.dumps({
                    "type": "initial_state",
                    "data": {
                        "round": current_round.__dict__ if current_round else None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }))
                
                # Keep connection alive and handle messages
                while True:
                    try:
                        data = await websocket.receive_text()
                        message = json.loads(data)
                        
                        # Handle ping/pong
                        if message.get("type") == "ping":
                            await websocket.send_text(json.dumps({"type": "pong"}))
                        
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"WebSocket message error: {e}")
                        break
                        
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
                logger.info(f"WebSocket client disconnected. Remaining connections: {len(self.websocket_connections)}")
        
        # =============== CATCH-ALL ROUTE FOR SPA ===============
        
        @self.app.get("/{file_path:path}")
        async def serve_static_files(file_path: str):
            """Serve static files or fallback to index.html for SPA routes"""
            # Don't intercept API routes
            if file_path.startswith('api') or file_path.startswith('ws'):
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
                elif file_path.endswith(('.jpg', '.jpeg')):
                    content_type = "image/jpeg"

                with open(file_full_path, 'rb') as f:
                    content = f.read()
                return Response(content=content, media_type=content_type)

            # SPA fallback to index.html
            index_file = frontend_dist / "index.html"
            if index_file.exists():
                return HTMLResponse(content=index_file.read_text())
                
            raise HTTPException(status_code=404, detail="Frontend not found")
    
    # =============== WEBSOCKET BROADCASTING ===============
    
    async def broadcast_update(self, message: Dict[str, Any]) -> None:
        """Broadcast update to all connected WebSocket clients"""
        if not self.websocket_connections:
            return
        
        message_str = json.dumps({
            **message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        disconnected = []
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            if websocket in self.websocket_connections:
                self.websocket_connections.remove(websocket)
    
    # =============== SERVER LIFECYCLE ===============
    
    async def start(self, host: str = "0.0.0.0", port: int = 6080) -> None:
        """Start the enhanced web server"""
        import uvicorn
        
        logger.info(f"🌐 Starting enhanced lottery web server on {host}:{port}...")
        
        # Setup event listeners for real-time updates
        self._setup_event_listeners()
        
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        try:
            await server.serve()
        except SystemExit as se:
            # Convert uvicorn's SystemExit to OSError so callers see a bind failure
            logger.error(f"Web server exited during startup with SystemExit: {se}")
            raise OSError(str(se))
        except OSError as e:
            logger.error(f"Failed to start web server on {host}:{port}: {e}")
            # Fail fast: do not attempt fallback ports
            raise
    
    async def stop(self) -> None:
        """Stop the web server gracefully"""
        logger.info("🛑 Stopping enhanced lottery web server...")
        
        # Close all WebSocket connections
        for websocket in self.websocket_connections:
            try:
                await websocket.close(code=1001, reason="Server shutdown")
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
        
        self.websocket_connections.clear()
        logger.info("✅ Web server stopped")
    
    def _setup_event_listeners(self) -> None:
        """Setup event listeners for broadcasting updates"""
        # Add listeners for important events
        memory_store.add_event_listener("RoundCreated", self._on_round_created)
        memory_store.add_event_listener("BetPlaced", self._on_bet_placed)
        memory_store.add_event_listener("RoundCompleted", self._on_round_completed)
        
        logger.debug("WebSocket event listeners configured")
    
    async def _on_round_created(self, event: ContractEvent) -> None:
        """Handle RoundCreated event"""
        await self.broadcast_update({
            "type": "round_created",
            "data": {"round_id": event.args.get("roundId")}
        })
    
    async def _on_bet_placed(self, event: ContractEvent) -> None:
        """Handle BetPlaced event"""
        await self.broadcast_update({
            "type": "bet_placed",
            "data": event.args
        })
    
    async def _on_round_completed(self, event: ContractEvent) -> None:
        """Handle RoundCompleted event"""
        await self.broadcast_update({
            "type": "round_completed",
            "data": event.args
        })