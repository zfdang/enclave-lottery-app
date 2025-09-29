"""Passive FastAPI web server for the enclave lottery backend."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from blockchain.client import BlockchainClient
from lottery.event_manager import MemoryStore, memory_store
from lottery.models import (
    LiveFeedItem,
    LotteryRound,
    ParticipantSummary,
    RoundSnapshot,
)
from lottery.operator import PassiveOperator

from utils.logger import get_logger

logger = get_logger(__name__)


class WalletConnectRequest(BaseModel):
    address: str
    signature: str
    message: Optional[str] = None


class BetRecordRequest(BaseModel):
    user_address: str
    amount: Optional[float] = None
    transaction_hash: Optional[str] = None
    draw_id: Optional[int] = None


class VerifyBetRequest(BaseModel):
    user_address: str
    transaction_hash: str
    draw_id: Optional[int] = None


class LotteryWebServer:
    """HTTP and WebSocket gateway for the passive lottery backend."""

    def __init__(
        self,
        config: Dict[str, Any],
        operator: PassiveOperator,
        blockchain_client: BlockchainClient,
        store: MemoryStore = memory_store,
    ) -> None:
        self.config = config
        self.operator = operator
        self.blockchain_client = blockchain_client
        self._store = store

        self.app = FastAPI(
            title="Enclave Lottery API",
            description="Passive backend API surface for the enclave-hosted lottery",
            version="3.0.0",
        )

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._broadcast_queue: Optional[asyncio.Queue[Tuple[str, Dict[str, Any] | None]]] = None
        self._broadcast_task: Optional[asyncio.Task[None]] = None
        self._ws_lock: Optional[asyncio.Lock] = None
        self._listeners_registered = False
        self._websockets: Set[WebSocket] = set()

        self._setup_middleware()
        self._setup_static_files()
        self._setup_routes()

    # ------------------------------------------------------------------
    # FastAPI scaffolding
    # ------------------------------------------------------------------
    def _setup_middleware(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_static_files(self) -> None:
        frontend_dist = Path(__file__).parent / "frontend" / "dist"
        if frontend_dist.exists():
            assets_dir = frontend_dist / "assets"
            if assets_dir.exists():
                self.app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
            self.app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")
            logger.info("Frontend static assets mounted from %s", frontend_dist)
        else:
            logger.info("Frontend build directory not found; API-only mode")

    def _setup_routes(self) -> None:  # noqa: C901 - routing setup intentionally verbose
        @self.app.get("/")
        async def serve_frontend() -> HTMLResponse:
            frontend_file = Path(__file__).parent / "frontend" / "dist" / "index.html"
            if not frontend_file.exists():
                return HTMLResponse("<h1>Lottery frontend not built</h1>")
            return HTMLResponse(frontend_file.read_text())

        # ------------------------------------------------------------------
        # Health & status
        # ------------------------------------------------------------------
        @self.app.get("/api/health")
        async def health_check() -> Dict[str, Any]:
            blockchain_health: Dict[str, Any] | None = None
            if self.blockchain_client:
                try:
                    blockchain_health = await self.blockchain_client.health_check()
                except Exception as exc:  # pragma: no cover - diagnostic path
                    logger.warning("Blockchain health probe failed: %s", exc)
                    blockchain_health = {"status": "error", "detail": str(exc)}

            operator_state = self.operator.get_status() if self.operator else {}
            current_round = self._store.get_current_round()
            return {
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "web": True,
                    "operator": operator_state.get("status", "unknown"),
                    "blockchain": blockchain_health or {"status": "unavailable"},
                    "store": {"round": current_round.round_id if current_round else 0},
                },
            }

        @self.app.get("/api/status")
        async def system_status() -> Dict[str, Any]:
            current_round = self._store.get_current_round()
            participants = self._store.get_participants()
            history = self._store.get_round_history(limit=5)
            operator_status = self.operator.get_status() if self.operator else {}
            blockchain_status = self.blockchain_client.get_client_status() if self.blockchain_client else {}
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "round": self._serialize_round(current_round),
                "participants": self._serialize_participants(participants),
                "recent_history": [self._serialize_history_round(item) for item in history],
                "operator": operator_status,
                "blockchain": blockchain_status,
                "websocket_connections": len(self._websockets),
            }

        @self.app.get("/api/attestation")
        async def get_attestation() -> Dict[str, Any]:
            payload = {
                "module_id": "i-1234567890abcdef0-enc0123456789abcdef",
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "digest": "SHA384",
                "pcrs": {str(idx): "a" * 96 for idx in (0, 1, 2, 8)},
                "certificate": "-----BEGIN CERTIFICATE-----\nMockCertificateData\n-----END CERTIFICATE-----",
                "cabundle": ["-----BEGIN CERTIFICATE-----\nMockRootCA\n-----END CERTIFICATE-----"],
                "public_key": None,
                "user_data": base64.b64encode(
                    json.dumps(
                        {
                            "lottery_contract": self.blockchain_client.contract_address if self.blockchain_client else None,
                            "operator_address": self.blockchain_client.account.address if self.blockchain_client and self.blockchain_client.account else None,
                            "enclave_version": "3.0.0",
                            "build_timestamp": datetime.utcnow().isoformat(),
                        }
                    ).encode("utf-8")
                ).decode("utf-8"),
                "nonce": None,
            }
            encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
            return {
                "attestation_document": encoded,
                "pcrs": payload["pcrs"],
                "user_data": payload["user_data"],
                "timestamp": payload["timestamp"],
                "verified": True,
                "note": "Mock attestation for development purposes only",
            }

        # ------------------------------------------------------------------
        # Lottery state
        # ------------------------------------------------------------------
        @self.app.get("/api/round/status")
        async def get_round_status() -> Dict[str, Any]:
            current = self._store.get_current_round()
            response = self._serialize_round(current)
            response.setdefault("participants", [item.address for item in self._store.get_participants()])
            return response

        @self.app.get("/api/round/participants")
        async def get_round_participants(limit: int = 200) -> Dict[str, Any]:
            current = self._store.get_current_round()
            participants = self._store.get_participants()
            if current is None:
                return {
                    "round_id": 0,
                    "participants": [],
                    "total_participants": 0,
                    "total_amount_wei": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            if limit > 0:
                participants = participants[:limit]
            total_amount = sum(p.total_amount for p in participants)
            serialized = [
                {
                    "address": item.address,
                    "totalAmountWei": item.total_amount,
                    "betCount": item.bet_count,
                }
                for item in participants
            ]
            return {
                "round_id": current.round_id,
                "round_state": current.state.name,
                "participants": serialized,
                "total_participants": len(self._store.get_participants()),
                "total_amount_wei": total_amount,
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/api/history")
        async def get_round_history(limit: int = 50) -> Dict[str, Any]:
            limit = max(1, min(limit, 200))
            history = self._store.get_round_history(limit=limit)
            rounds = [self._serialize_history_round(item) for item in history]
            return {
                "rounds": rounds,
                "summary": {
                    "total_rounds": len(rounds),
                    "completed_rounds": sum(1 for r in rounds if r["final_state"] == "COMPLETED"),
                    "refunded_rounds": sum(1 for r in rounds if r["final_state"] == "REFUNDED"),
                    "total_volume_wei": sum(r["total_pot_wei"] for r in rounds),
                },
                "pagination": {"limit": limit, "returned": len(rounds)},
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/api/activities")
        async def get_live_feed(limit: int = 50) -> Dict[str, Any]:
            limit = max(1, min(limit, 200))
            feed = self._store.get_live_feed(limit=limit)
            activities = [self._serialize_activity(item, idx) for idx, item in enumerate(reversed(feed))]
            return {"activities": activities}

        @self.app.get("/api/contract/config")
        async def get_contract_config() -> Dict[str, Any]:
            store_config = self._store.get_contract_config()
            if store_config is None:
                if not self.blockchain_client:
                    raise HTTPException(status_code=503, detail="Blockchain client unavailable")
                store_config = await self.blockchain_client.get_contract_config()
                self._store.set_contract_config(store_config)
            return {
                "config": {
                    "publisherAddr": store_config.publisher_addr,
                    "sparsityAddr": store_config.sparsity_addr,
                    "operatorAddr": store_config.operator_addr,
                    "publisherCommission": store_config.publisher_commission,
                    "sparsityCommission": store_config.sparsity_commission,
                    "minBet": store_config.min_bet,
                    "bettingDuration": store_config.betting_duration,
                    "minDrawDelay": store_config.min_draw_delay,
                    "maxDrawDelay": store_config.max_draw_delay,
                    "minEndTimeExtension": store_config.min_end_time_extension,
                    "minParticipants": store_config.min_participants,
                },
                "contract_address": self.blockchain_client.contract_address if self.blockchain_client else None,
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/api/contract/address")
        async def get_contract_address() -> Dict[str, Any]:
            if not self.blockchain_client:
                raise HTTPException(status_code=503, detail="Blockchain client unavailable")
            return {
                "contract_address": self.blockchain_client.contract_address,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # ------------------------------------------------------------------
        # Compatibility stubs for legacy front-end calls
        # ------------------------------------------------------------------
        @self.app.post("/api/auth/connect")
        async def connect_wallet(request: WalletConnectRequest) -> Dict[str, Any]:
            logger.info("Wallet connected: %s", request.address)
            return {"status": "connected", "address": request.address}

        @self.app.post("/api/bet")
        async def record_bet(request: BetRecordRequest) -> Dict[str, Any]:
            logger.debug("Received bet webhook: %s", request.dict())
            return {"status": "accepted", "transaction_hash": request.transaction_hash}

        @self.app.post("/api/verify-bet")
        async def verify_bet(request: VerifyBetRequest) -> Dict[str, Any]:
            logger.debug("Verify bet request: %s", request.dict())
            return {"status": "verified", "transaction_hash": request.transaction_hash}

        # ------------------------------------------------------------------
        # WebSocket endpoint
        # ------------------------------------------------------------------
        @self.app.websocket("/ws/lottery")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            if self._ws_lock is None:
                self._ws_lock = asyncio.Lock()
            async with self._ws_lock:
                self._websockets.add(websocket)
            logger.info("WebSocket client connected (%s total)", len(self._websockets))
            try:
                await websocket.send_json({"type": "snapshot", "payload": await self._build_initial_snapshot()})
                while True:
                    try:
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.debug("WebSocket receive error: %s", exc)
                        break
            finally:
                async with self._ws_lock:
                    self._websockets.discard(websocket)
                logger.info("WebSocket client disconnected (%s remaining)", len(self._websockets))

        # ------------------------------------------------------------------
        # SPA fallback
        # ------------------------------------------------------------------
        @self.app.get("/{file_path:path}")
        async def serve_static_files(file_path: str) -> Response:
            if file_path.startswith("api") or file_path.startswith("ws"):
                raise HTTPException(status_code=404, detail="Not found")
            frontend_dist = Path(__file__).parent / "frontend" / "dist"
            requested = (frontend_dist / file_path).resolve()
            try:
                requested.relative_to(frontend_dist.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="Not found")
            if requested.is_file():
                content_type = "text/plain"
                if file_path.endswith(".js"):
                    content_type = "application/javascript"
                elif file_path.endswith(".css"):
                    content_type = "text/css"
                elif file_path.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif file_path.endswith(".png"):
                    content_type = "image/png"
                elif file_path.endswith((".jpg", ".jpeg")):
                    content_type = "image/jpeg"
                return Response(content=requested.read_bytes(), media_type=content_type)
            index = frontend_dist / "index.html"
            if index.exists():
                return HTMLResponse(index.read_text())
            raise HTTPException(status_code=404, detail="Frontend not found")

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    async def start(self, host: str = "0.0.0.0", port: int = 6080) -> None:
        import uvicorn

        logger.info("Starting passive lottery web server on %s:%s", host, port)
        self._loop = asyncio.get_running_loop()
        if self._broadcast_queue is None:
            self._broadcast_queue = asyncio.Queue()
        if self._ws_lock is None:
            self._ws_lock = asyncio.Lock()
        self._register_store_listeners()
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_loop(), name="lottery-web-broadcast")

        config = uvicorn.Config(self.app, host=host, port=port, log_level="info", access_log=True)
        server = uvicorn.Server(config)
        try:
            await server.serve()
        finally:
            logger.info("Passive lottery web server stopped")

    async def stop(self) -> None:
        logger.info("Stopping passive lottery web server")
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None
        if self._ws_lock is None:
            self._ws_lock = asyncio.Lock()
        async with self._ws_lock:
            for websocket in list(self._websockets):
                try:
                    await websocket.close(code=1001, reason="Server shutdown")
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("Error closing websocket: %s", exc)
            self._websockets.clear()

    # ------------------------------------------------------------------
    # Store listeners & broadcasting
    # ------------------------------------------------------------------
    def _register_store_listeners(self) -> None:
        if self._listeners_registered:
            return
        for event in (
            "round_update",
            "participants_update",
            "history_update",
            "live_feed",
            "config_update",
            "operator_status",
            "operator_alert",
        ):
            self._store.add_listener(event, lambda payload, evt=event: self._enqueue_broadcast(evt, payload))
        self._listeners_registered = True

    def _enqueue_broadcast(self, event_type: str, payload: Dict[str, Any] | None) -> None:
        if not self._broadcast_queue or not self._loop:
            return
        try:
            self._loop.call_soon_threadsafe(self._broadcast_queue.put_nowait, (event_type, payload))
            # show logger.info
            logger.info("Enqueued broadcast for %s", event_type)
        except RuntimeError:  # pragma: no cover - loop already closing
            logger.debug("Failed to enqueue broadcast for %s", event_type)

    async def _broadcast_loop(self) -> None:
        assert self._broadcast_queue is not None
        while True:
            try:
                event_type, payload = await self._broadcast_queue.get()
                await self._broadcast_to_clients(event_type, payload)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Broadcast loop error: %s", exc)

    async def _broadcast_to_clients(self, event_type: str, payload: Dict[str, Any] | None) -> None:
        if self._ws_lock is None:
            self._ws_lock = asyncio.Lock()
        message = {"type": event_type, "payload": payload, "timestamp": datetime.utcnow().isoformat()}
        async with self._ws_lock:
            if not self._websockets:
                return
            to_remove: List[WebSocket] = []
            for websocket in self._websockets:
                try:
                    await websocket.send_json(message)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("WebSocket send failed: %s", exc)
                    to_remove.append(websocket)
            for websocket in to_remove:
                self._websockets.discard(websocket)

    async def _build_initial_snapshot(self) -> Dict[str, Any]:
        current = self._store.get_current_round()
        participants = self._store.get_participants()
        history = self._store.get_round_history(limit=10)
        feed = self._store.get_live_feed(limit=20)
        operator_status = self.operator.get_status() if self.operator else {}
        config = self._store.get_contract_config()
        return {
            "round": self._serialize_round(current),
            "participants": self._serialize_participants(participants),
            "history": [self._serialize_history_round(item) for item in history],
            "live_feed": [self._serialize_activity(item, idx) for idx, item in enumerate(reversed(feed))],
            "operator": operator_status,
            "config": {
                "publisherAddr": config.publisher_addr if config else None,
                "sparsityAddr": config.sparsity_addr if config else None,
                "operatorAddr": config.operator_addr if config else None,
            },
        }

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def _serialize_round(self, round_data: Optional[LotteryRound]) -> Dict[str, Any]:
        if round_data is None:
            return {
                "round_id": 0,
                "state": 0,
                "state_name": "waiting",
                "state_label": "WAITING",
            }
        return {
            "round_id": round_data.round_id,
            "state": round_data.state.value,
            "state_name": round_data.state.name.lower(),
            "state_label": round_data.state.name,
            "status": round_data.state.name.lower(),
            "start_time": round_data.start_time,
            "end_time": round_data.end_time,
            "min_draw_time": round_data.min_draw_time,
            "max_draw_time": round_data.max_draw_time,
            "total_pot": round_data.total_pot,
            "participant_count": round_data.participant_count,
            "winner": round_data.winner,
            "publisher_commission": round_data.publisher_commission,
            "sparsity_commission": round_data.sparsity_commission,
            "winner_prize": round_data.winner_prize,
        }

    def _serialize_participants(self, participants: Iterable[ParticipantSummary]) -> List[Dict[str, Any]]:
        return [
            {
                "address": participant.address,
                "totalAmountWei": participant.total_amount,
                "betCount": participant.bet_count,
            }
            for participant in participants
        ]

    def _serialize_history_round(self, snapshot: RoundSnapshot) -> Dict[str, Any]:
        return {
            "round_id": snapshot.round_id,
            "final_state": snapshot.state.name,
            "start_time": snapshot.start_time,
            "end_time": snapshot.end_time,
            "min_draw_time": snapshot.min_draw_time,
            "max_draw_time": snapshot.max_draw_time,
            "total_pot_wei": snapshot.total_pot,
            "participant_count": snapshot.participant_count,
            "winner": snapshot.winner,
            "winner_prize_wei": snapshot.winner_prize,
            "publisher_commission_wei": snapshot.publisher_commission,
            "sparsity_commission_wei": snapshot.sparsity_commission,
            "finished_at": snapshot.finished_at,
            "refund_reason": snapshot.refund_reason,
        }

    def _serialize_activity(self, item: LiveFeedItem, index: int) -> Dict[str, Any]:
        # Ensure user_address is always a string for the frontend.
        # Prefer explicit player addresses, then winner, then fall back to a readable round id or 'system'.
        user_val = item.details.get("player") or item.details.get("winner")
        if not user_val:
            # Prefer roundId when no participant address is present; coerce to string for consistency
            round_id = item.details.get("roundId")
            user_val = f"round:{round_id}" if round_id is not None else "system"
        # Final coercion to string to avoid runtime errors like `address.slice is not a function` in the UI
        user_address_str = str(user_val)

        return {
            "activity_id": f"{item.created_at.isoformat()}-{index}",
            "user_address": user_address_str,
            "activity_type": self._map_feed_type(item.event_type),
            "details": item.details,
            "message": item.message,
            "severity": item.severity,
            "timestamp": item.created_at.isoformat(),
        }

    def _map_feed_type(self, event_type: str) -> str:
        if event_type == "bet_placed":
            return "bet"
        if event_type == "round_completed":
            return "win"
        if event_type == "operator_alert":
            return "system"
        return event_type