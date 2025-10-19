"""
Simplified passive lottery operator.

Registers for 'round_update' events from EventManager and checks round state:
- If in draw window (min_draw_time <= now <= max_draw_time): draw the round
- If past draw window (now > max_draw_time) and still betting: refund the round
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

from blockchain.client import BlockchainClient
from lottery.event_manager import MemoryStore, memory_store
from lottery.models import RoundState
from utils.logger import get_logger

logger = get_logger(__name__)


class PassiveOperator:
    """Simplified operator that reacts to round_update events."""

    def __init__(
        self,
        blockchain_client: BlockchainClient,
        config: Dict[str, Any],
        store: MemoryStore = memory_store,
    ) -> None:
        self._client = blockchain_client
        self._config = config
        self._store = store
        self._running = False
        self._tx_timeout = int(config.get("operator", {}).get("tx_timeout_seconds", 180))

    async def initialize(self) -> None:
        """Register for round_update events from EventManager."""
        logger.info("Initializing passive lottery operator")
        self._store.add_listener("round_update", self._on_round_update)
        logger.info("Passive operator registered for round_update events")

    async def start(self) -> None:
        """Mark operator as running."""
        if self._running:
            logger.warning("Passive operator already running")
            return
        self._running = True
        logger.info("Passive operator started")

    async def stop(self) -> None:
        """Stop the operator."""
        if not self._running:
            return
        logger.info("Stopping passive operator")
        self._running = False
        logger.info("Passive operator stopped")

    def get_status(self) -> Dict[str, Any]:
        """Return operator status."""
        current = self._store.get_current_round()
        return {
            "status": "running" if self._running else "stopped",
            "current_round_id": current.round_id if current else None,
        }

    def _on_round_update(self, payload: dict | None) -> None:
        """Called by EventManager when round state is updated."""
        if not payload or not self._running:
            return
        
        try:
            # Payload is the serialized round dict from EventManager
            round_id = payload.get("roundId")
            state = payload.get("state")
            if round_id is None or state is None:
                return
            
            # Schedule async round check
            asyncio.create_task(self._check_round(payload))
        except Exception as exc:
            logger.error("Failed to handle round_update: %s", exc)

    async def _check_round(self, round_dict: dict) -> None:
        """Check round state and take action if needed."""
        try:
            state = RoundState(round_dict.get("state"))
        except (ValueError, TypeError):
            return
        
        if state != RoundState.BETTING:
            return
        
        round_id = round_dict.get("roundId")
        now = int(time.time())
        min_draw = int(round_dict.get("minDrawTime", 0))
        max_draw = int(round_dict.get("maxDrawTime", 0))
        
        logger.info(f"Checking round {round_id}: now={now}, min_draw={min_draw}, max_draw={max_draw}")
        
        # Before draw window - do nothing
        if now < min_draw:
            return
        
        # Inside draw window - attempt draw
        if min_draw <= now <= max_draw:
            logger.info(f"Round {round_id}: in draw window, attempting draw")
            await self._attempt_draw(round_id)
            return
        
        # Past draw window - refund
        if now > max_draw:
            logger.info(f"Round {round_id}: past draw window, attempting refund")
            await self._attempt_refund(round_id)

    async def _attempt_draw(self, round_id: int) -> None:
        """Attempt to draw the round."""
        try:
            tx_hash = await self._client.draw_round(round_id)
            await self._client.wait_for_transaction(tx_hash, timeout=self._tx_timeout)
            logger.info(f"Draw successful for round {round_id}: {tx_hash}")
        except Exception as exc:
            logger.error(f"Draw failed for round {round_id}: {exc}")

    async def _attempt_refund(self, round_id: int) -> None:
        """Attempt to refund the round."""
        try:
            tx_hash = await self._client.refund_round(round_id)
            await self._client.wait_for_transaction(tx_hash, timeout=self._tx_timeout)
            logger.info(f"Refund successful for round {round_id}: {tx_hash}")
        except Exception as exc:
            logger.error(f"Refund failed for round {round_id}: {exc}")