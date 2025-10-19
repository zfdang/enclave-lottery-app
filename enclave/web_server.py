"""Passive FastAPI web server for the enclave lottery backend."""

from __future__ import annotations

import asyncio
import base64
import cbor2
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

from cryptography.hazmat.primitives import serialization

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
        tls_keypair: Any,  # TLSKeyPair from utils.crypto
        store: MemoryStore = memory_store,
    ) -> None:
        self.config = config
        self.operator = operator
        self.blockchain_client = blockchain_client
        self.tls_keypair = tls_keypair
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
            """
            Generate a real AWS Nitro Enclave attestation document using aws-nsm-interface.
            
            The attestation includes the TLS public key in user_data, allowing external
            verifiers to confirm the public key comes from a trusted enclave.
            """
            user_data_obj = {
                "operator_address": (self.blockchain_client.get_operator_address()
                                     if self.blockchain_client else None),
                "tls_public_key_hex": self.tls_keypair.get_public_key_hex()
            }
            user_data_bytes = json.dumps(user_data_obj).encode("utf-8")

            try:
                import aws_nsm_interface
            except ImportError as exc:
                logger.error("NSM interface import failed: %s", exc)
                raise HTTPException(status_code=503, detail=f"NSM interface not available: {exc}")

            try:
                # Try opening NSM device; if it fails, fall back to a dummy attestation
                try:
                    nsm_fd = aws_nsm_interface.open_nsm_device()
                except Exception as exc_open:  # pragma: no cover - environment dependent
                    logger.warning("NSM device not available: %s. Returning dummy attestation.", exc_open)
                    # Return a clear dummy attestation object indicating not verified
                    dummy_user_data_b64 = base64.b64encode(user_data_bytes).decode("utf-8")
                    
                    # Create a CBOR-encoded dummy attestation document that matches Nitro format
                    # Get TLS public key in DER format
                    tls_public_key_der = self.tls_keypair.public_key.public_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    
                    # Create dummy PCRs (48 bytes each, all zeros for testing)
                    dummy_pcrs = {i: b'\x00' * 48 for i in range(16)}
                    
                    # Build a dummy attestation document CBOR structure
                    import cbor2
                    dummy_attestation_doc = {
                        "module_id": "i-dummy-enclave-dev",
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                        "digest": "SHA384",
                        "pcrs": dummy_pcrs,
                        "certificate": b"",  # Empty certificate (no real cert in dev mode)
                        "cabundle": [],
                        "public_key": tls_public_key_der,
                        "user_data": user_data_bytes,
                        "nonce": None,
                    }
                    
                    dummy_attestation_cbor = cbor2.dumps(dummy_attestation_doc)
                    
                    return {
                        "attestation_document": base64.b64encode(dummy_attestation_cbor).decode("utf-8"),
                        "pcrs": {str(i): "00" * 48 for i in range(8)},
                        "user_data": dummy_user_data_b64,
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                        "certificate": None,
                        "cabundle": [],
                        "verified": False,
                        "note": "NSM device not available; returned dummy attestation for development/testing",
                    }

                # If we reach here, the NSM device opened successfully
                try:
                    # Get TLS public key in DER format for attestation
                    tls_public_key_der = self.tls_keypair.public_key.public_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    
                    # Get attestation document with user data and TLS public key
                    attestation_response = aws_nsm_interface.get_attestation_doc(
                        file_handle=nsm_fd,
                        user_data=user_data_bytes,
                        nonce=None,
                        public_key=tls_public_key_der,
                    )

                    # attestation_response is a dict, iterate all keys, and log them
                    for key, value in attestation_response.items():
                        if isinstance(value, (bytes, bytearray)):
                            logger.info("Attestation response key '%s': %d bytes", key, len(value))
                        else:
                            logger.info("Attestation response key '%s': %s", key, str(value)[:100])

                    # Extract attestation document (should be bytes)
                    attestation_doc = attestation_response.get("document")
                    if attestation_doc is None:
                        logger.error("No attestation document in response")
                        raise ValueError("No attestation document in response")

                    # Base64 encode the attestation document
                    attestation_document_b64 = base64.b64encode(attestation_doc).decode("utf-8")

                    pcrs_serialized = {}
                    # use describe_pcr(file_handle=nsm_fd, index=i) to list all PCRs
                    for i in range(8):
                        pcr_info = aws_nsm_interface.describe_pcr(file_handle=nsm_fd, index=i)
                        lock_status = pcr_info.get("lock", False)
                        pcr_data = pcr_info.get("data", b"")
                        pcrs_serialized[str(i)] = pcr_data.hex() if isinstance(pcr_data, (bytes, bytearray)) else str(pcr_data)
                        logger.info(
                            "PCR%d: lock=%s, data=%s",
                            i,
                            lock_status,
                            pcr_data.hex() if isinstance(pcr_data, (bytes, bytearray)) else str(pcr_data),
                        )

                    # Extract certificate and CA bundle
                    certificate = attestation_response.get("certificate")
                    if isinstance(certificate, (bytes, bytearray)):
                        certificate = certificate.decode("utf-8", errors="ignore")

                    cabundle = attestation_response.get("cabundle", [])
                    if isinstance(cabundle, (bytes, bytearray)):
                        cabundle = [cabundle.decode("utf-8", errors="ignore")]
                    elif isinstance(cabundle, list):
                        cabundle = [
                            cert.decode("utf-8", errors="ignore") if isinstance(cert, (bytes, bytearray)) else str(cert)
                            for cert in cabundle
                        ]

                    return {
                        "attestation_document": attestation_document_b64,
                        "pcrs": pcrs_serialized,
                        "user_data": base64.b64encode(user_data_bytes).decode("utf-8"),
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                        "certificate": certificate,
                        "cabundle": cabundle,
                        "verified": True,
                        "note": "Real attestation generated via AWS NSM interface",
                    }
                finally:
                    # Always close the NSM device if it was opened
                    try:
                        aws_nsm_interface.close_nsm_device(nsm_fd)
                    except Exception:
                        logger.debug("Failed to close NSM device cleanly", exc_info=True)
            except HTTPException as exc:
                logger.error("HTTP error occurred: %s", exc)
                raise
            except Exception as exc:
                logger.exception("Failed to generate attestation document")
                raise HTTPException(status_code=500, detail=f"Attestation generation failed: {exc}")

        # ------------------------------------------------------------------
        # Key management endpoints
        # ------------------------------------------------------------------
        @self.app.get("/api/get_pub_key")
        async def get_pub_key() -> Dict[str, Any]:
            """Get the TLS public key for encrypting operator private key.
            
            This endpoint returns the SECP384R1 public key that should be used
            to encrypt the operator private key using ECIES before calling
            /api/set_operator_key.
            """
            try:
                key_info = self.tls_keypair.get_key_info()
                return {
                    "public_key_pem": self.tls_keypair.get_public_key_pem(),
                    "public_key_hex": self.tls_keypair.get_public_key_hex(),
                    "curve": key_info["curve"],
                    "key_size": key_info["key_size"],
                    "usage": key_info["usage"],
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                }
            except Exception as exc:
                logger.exception("Failed to get public key")
                raise HTTPException(status_code=500, detail=f"Failed to retrieve public key: {exc}")

        @self.app.post("/api/set_operator_key")
        async def set_operator_key(request: Dict[str, Any]) -> Dict[str, Any]:
            """Inject operator private key after validating address match.
            
            The private key must be encrypted with ECIES using the public key
            from /api/get_pub_key. The decrypted key must match the operator
            address configured in lottery.conf.
            
            This endpoint can only succeed once. Subsequent calls will fail.
            """
            from utils.key_manager import validate_operator_key
            
            # Check if already set
            if self.blockchain_client.is_operator_key_set():
                operator_address = self.blockchain_client.get_operator_address()
                logger.warning("Operator key already set for address %s", operator_address)
                raise HTTPException(
                    status_code=403,
                    detail={
                        "success": False,
                        "error": "Operator key already set. Cannot change once configured.",
                        "operator_address": operator_address,
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    }
                )
            
            # Extract encrypted private key
            encrypted_private_key_b64 = request.get("encrypted_private_key")
            if not encrypted_private_key_b64:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": "Missing required field: encrypted_private_key",
                        "operator_key_set": False,
                    }
                )
            
            # Decode base64
            try:
                encrypted_data = base64.b64decode(encrypted_private_key_b64)
            except Exception as exc:
                logger.error("Failed to decode base64 encrypted data: %s", exc)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": "Invalid base64 encoding",
                        "detail": str(exc),
                        "operator_key_set": False,
                        "message": "You can retry with correct encoding",
                    }
                )
            
            # Decrypt using TLS private key
            try:
                decrypted_bytes = self.tls_keypair.decrypt_ecies(encrypted_data)
                private_key = decrypted_bytes.decode('utf-8').strip()
            except Exception as exc:
                logger.error("Failed to decrypt private key: %s", exc)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": "Failed to decrypt private key",
                        "detail": str(exc),
                        "operator_key_set": False,
                        "message": "You can retry with correct encryption",
                    }
                )
            
            # Get expected operator address from config
            expected_address = self.config.get("blockchain", {}).get("operator_address")
            if not expected_address:
                logger.error("operator_address not configured in lottery.conf")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": "Operator address not configured in lottery.conf",
                    }
                )
            
            # Validate operator key
            is_valid, derived_address, error_msg = validate_operator_key(
                private_key, expected_address
            )
            
            if not is_valid:
                logger.warning("Operator key validation failed: %s", error_msg)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": error_msg.split(":")[0] if ":" in error_msg else error_msg,
                        "detail": error_msg,
                        "expected_address": expected_address,
                        "derived_address": derived_address if derived_address else None,
                        "operator_key_set": False,
                        "message": "The private key does not match the configured operator address. You can retry with correct key.",
                    }
                )
            
            # Set the operator key
            try:
                success = self.blockchain_client.set_operator_key(private_key)
                if not success:
                    # This shouldn't happen as we checked is_operator_key_set above
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "success": False,
                            "error": "Failed to set operator key (already set)"
                        }
                    )
                
                logger.info("Operator key set successfully for address %s", derived_address)
                return {
                    "success": True,
                    "operator_address": derived_address,
                    "message": "Operator key set successfully",
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                }
            except Exception as exc:
                logger.exception("Unexpected error setting operator key")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": "Internal error setting operator key",
                        "detail": str(exc),
                    }
                )

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
                }
                for item in participants
            ]
            logger.info("Serialized %d participants for round %d", len(serialized), current.round_id)
            logger.debug("Participants data: %s", serialized)
            return {
                "round_id": current.round_id,
                "round_state": current.state.name,
                "participants": serialized,
                "total_participants": len(self._store.get_participants()),
                "total_amount_wei": total_amount,
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/api/round/player")
        async def get_player_info(player: Optional[str] = None) -> Dict[str, Any]:
            """Return the total amount (in wei) a given player has bet in the current round and an estimated win rate.

            Query parameter: player (string) - the player's ETH address (required).
            Response: { player, round_id, totalAmountWei, winRate, timestamp }
            """
            if not player:
                raise HTTPException(status_code=400, detail="Missing required query parameter: player")

            current = self._store.get_current_round()
            participants = self._store.get_participants()
            total = 0
            addr_l = player.lower()
            for p in participants:
                if (p.address or "").lower() == addr_l:
                    total = int(p.total_amount)
                    break

            # Compute simple win rate as player's share of the current pot (percentage).
            win_rate = 0.0
            try:
                if current and getattr(current, "total_pot", 0):
                    pot = int(current.total_pot or 0)
                    if pot > 0:
                        win_rate = (float(total) / float(pot)) * 100.0
            except Exception:  # pragma: no cover - defensive
                win_rate = 0.0

            return {
                "player": player,
                "round_id": current.round_id if current else 0,
                "totalAmountWei": total,
                "winRate": win_rate,
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/api/history")
        async def get_round_history(limit: int = 50) -> Dict[str, Any]:
            limit = max(1, min(limit, 200))
            history = self._store.get_round_history(limit=limit)
            rounds = [self._serialize_history_round(item) for item in history]
            # sort rounds by round_id descending (newest first)
            rounds.sort(key=lambda x: x["round_id"], reverse=True)
            return {
                "rounds": rounds,
                "summary": {
                    "total_rounds": len(rounds),
                    "completed_rounds": sum(1 for r in rounds if r["event_type"] == "RoundCompleted"),
                    "refunded_rounds": sum(1 for r in rounds if r["event_type"] == "RoundRefunded"),
                    "total_volume_wei": sum(r["total_pot_wei"] for r in rounds),
                },
                "pagination": {"limit": limit, "returned": len(rounds)},
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/api/activities")
        async def get_live_feed(limit: int = 50) -> Dict[str, Any]:
            limit = max(1, min(limit, 200))
            feed = self._store.get_live_feed(limit=limit)
            # sort feed by roundid (larger first), then timestamp descending (newest first)
            feed = sorted(feed, key=lambda x: (-x.details.get("roundId", 0), -x.event_time))
            # serialize items in feed
            activities = [self._serialize_live_feed_item(item, idx) for idx, item in enumerate(feed)]
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
            "live_feed": [self._serialize_live_feed_item(item, idx) for idx, item in enumerate(reversed(feed))],
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
                # betCount removed; expose total_amount and other aggregates
            }
            for participant in participants
        ]

    def _serialize_history_round(self, snapshot: RoundSnapshot) -> Dict[str, Any]:
        return {
            "event_type": snapshot.event_type,
            "round_id": snapshot.round_id,
            "participant_count": snapshot.participant_count,
            "total_pot_wei": snapshot.total_pot,
            "finished_at": snapshot.finished_at,
            "winner": snapshot.winner,
            "winner_prize_wei": snapshot.winner_prize,
            "refund_reason": snapshot.refund_reason,
        }

    def _serialize_live_feed_item(self, item: LiveFeedItem, index: int) -> Dict[str, Any]:
        activity_id = item.get_item_id()
        return {
            "activity_id": f"{activity_id}",
            "activity_type": item.event_type,
            "details": item.details,
            "message": item.message,
            "timestamp": item.event_time
        }