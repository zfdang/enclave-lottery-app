"""
Passive lottery operator service for the enclave backend.

This module implements a fully automated operator that monitors the lottery contract
and automatically manages the complete round lifecycle without human intervention.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from blockchain.client import BlockchainClient, BlockchainEvent
from lottery.event_manager import MemoryStore, memory_store
from lottery.models import (
    LotteryRound,
    OperatorStatus,
    ParticipantSummary,
    RoundState,
)

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OperatorSettings:
    """Runtime tunables for the passive operator loop."""

    draw_check_interval: float = 10.0
    draw_retry_delay: float = 45.0
    max_draw_retries: int = 3
    tx_timeout_seconds: int = 180


class PassiveOperator:
    """Passive operator that synchronizes on-chain state into the memory store."""

    def __init__(
        self,
        blockchain_client: BlockchainClient,
        config: Dict[str, Any],
        store: MemoryStore = memory_store,
    ) -> None:
        self._client = blockchain_client
        self._config = config
        self._store = store
        self._settings = self._load_settings(config)

        self._running = False
        self._stop_event = asyncio.Event()
        self._tasks: List[asyncio.Task[Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """Register as listener for blockchain events from EventManager."""
        logger.info("Initializing passive lottery operator")
        # Register to receive blockchain events from EventManager
        self._store.add_listener("blockchain_event", self._on_blockchain_event)
        self._store.update_operator_status(self._apply_initial_status)
        logger.info("Passive lottery operator registered for blockchain events")

    async def start(self) -> None:
        """Start background tasks that keep the store in sync."""
        if self._running:
            logger.warning("Passive operator already running")
            return

        self._running = True
        self._stop_event.clear()
        self._store.update_operator_status(self._mark_running)

        logger.info("Starting passive operator draw loop")
        self._tasks = [
            asyncio.create_task(self._draw_loop(), name="lottery-operator-draw"),
        ]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            raise
        finally:
            await self._shutdown_tasks()
            self._running = False
            self._store.update_operator_status(self._mark_stopped)
            logger.info("Passive operator stopped")

    async def stop(self) -> None:
        """Stop background processing and clean up."""
        if not self._running:
            return

        logger.info("Stopping passive operator")
        self._stop_event.set()
        await self._shutdown_tasks()
        self._running = False
        self._store.update_operator_status(self._mark_stopped)

    async def _shutdown_tasks(self) -> None:
        if not self._tasks:
            return
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_operator_status(self) -> Dict[str, Any]:
        status = self._store.get_operator_status()
        return {
            "is_running": status.is_running,
            "current_round_id": status.current_round_id,
            "last_event_time": status.last_event_time.isoformat() if status.last_event_time else None,
            "last_draw_attempt": status.last_draw_attempt.isoformat() if status.last_draw_attempt else None,
            "consecutive_draw_failures": status.consecutive_draw_failures,
            "max_draw_retries": status.max_draw_retries,
            "scheduled_draw_round_id": status.scheduled_draw_round_id,
            "scheduled_draw_due_at": status.scheduled_draw_due_at,
            "watchdog_last_check": status.watchdog_last_check.isoformat() if status.watchdog_last_check else None,
        }

    def get_status(self) -> Dict[str, Any]:
        status = self.get_operator_status()
        return {
            "status": "running" if status["is_running"] else "stopped",
            "current_round_id": status.get("current_round_id"),
            "auto_create_enabled": False,
            "last_check_time": status.get("watchdog_last_check"),
            "errors": [] if status.get("consecutive_draw_failures", 0) == 0 else [
                {"count": status["consecutive_draw_failures"]}
            ],
        }

    async def force_draw_round(self, round_id: int) -> str:
        current = self._store.get_current_round()
        if not current or current.round_id != round_id:
            raise ValueError(f"Round {round_id} is not active")
        await self._attempt_draw(current, manual=True)
        return f"Draw attempt submitted for round {round_id}"

    async def force_refund_round(self, round_id: int) -> str:
        current = self._store.get_current_round()
        if not current or current.round_id != round_id:
            raise ValueError(f"Round {round_id} is not active")
        await self._attempt_refund(current, manual=True)
        return f"Refund attempt submitted for round {round_id}"

    async def force_create_round(self) -> str:
        raise NotImplementedError("Passive operator does not create rounds on-chain")

    # ------------------------------------------------------------------
    # Event handling (receives events from EventManager)
    # ------------------------------------------------------------------
    def _on_blockchain_event(self, payload: dict | None) -> None:
        """Called by EventManager when a blockchain event occurs."""
        if not payload:
            return
        
        try:
            event = payload.get("event")
            if not event:
                return
            
            # Schedule async event handling
            asyncio.create_task(self._handle_event(event))
        except Exception as exc:
            logger.error("Failed to handle blockchain event: %s", exc)

    async def _draw_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._maybe_handle_draw()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Draw loop error: %s", exc)
            await self._wait_with_stop(self._settings.draw_check_interval)

    async def _handle_event(self, event: BlockchainEvent) -> None:
        logger.info(f"[handle_event] Event: {event.name}, block: {event.block_number}, tx: {event.transaction_hash}, args: {event.args}")
        if event.name == "RoundCreated":
            logger.info(f"[handle_event] Handling RoundCreated event: {event.args}")
            await self._on_round_created(event)
        elif event.name == "RoundStateChanged":
            logger.info(f"[handle_event] Handling RoundStateChanged event: {event.args}")
            await self._on_round_state_changed(event)
        elif event.name == "BetPlaced":
            logger.info(f"[handle_event] Handling BetPlaced event: {event.args}")
            await self._on_bet_placed(event)
        elif event.name == "EndTimeExtended":
            logger.info(f"[handle_event] Handling EndTimeExtended event: {event.args}")
            await self._on_end_time_extended(event)
        elif event.name == "RoundCompleted":
            logger.info(f"[handle_event] Handling RoundCompleted event: {event.args}")
            await self._on_round_completed(event)
        elif event.name == "RoundRefunded":
            logger.info(f"[handle_event] Handling RoundRefunded event: {event.args}")
            await self._on_round_refunded(event)
        elif event.name in {
            "MinBetAmountUpdated",
            "BettingDurationUpdated",
            "MinParticipantsUpdated",
            "OperatorUpdated",
        }:
            logger.info(f"[handle_event] Handling config update event: {event.name}")
            # EventManager will refresh contract config

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    async def _on_round_created(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        logger.info("Round %s created", round_id)
        # Get round data from memory store (updated by EventManager)
        round_data = self._store.get_current_round()
        if round_data and round_data.round_id == round_id:
            self._schedule_draw(round_data.round_id, max(round_data.min_draw_time, int(time.time())))

    async def _on_round_state_changed(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        new_state = RoundState(int(event.args.get("newState", 0)))
        logger.info("Round %s transitioned to %s", round_id, new_state.name)
        # Get round data from memory store (updated by EventManager)
        round_data = self._store.get_current_round()
        if new_state == RoundState.DRAWING and round_data and round_data.round_id == round_id:
            self._schedule_draw(round_data.round_id, max(round_data.min_draw_time, int(time.time())))
        if new_state in {RoundState.COMPLETED, RoundState.REFUNDED}:
            self._store.update_operator_status(self._clear_draw_schedule)

    async def _on_bet_placed(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        player = str(event.args.get("player"))
        logger.debug("Bet placed by %s for round %s", player, round_id)
        # EventManager already adds this to live feed, no additional action needed

    async def _on_end_time_extended(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        new_end_time = int(event.args.get("newEndTime", 0))
        logger.info("Round %s betting end extended to %s", round_id, new_end_time)
        # EventManager refreshes round state, no additional action needed

    async def _on_round_completed(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        winner = str(event.args.get("winner"))
        logger.info("Round %s completed, winner: %s", round_id, winner)
        
        # Clear draw schedule now that round is completed
        self._store.update_operator_status(self._clear_draw_schedule)
        # EventManager handles live feed and history snapshot

    async def _on_round_refunded(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        reason = str(event.args.get("reason", "") or "refunded")
        logger.info("Round %s refunded: %s", round_id, reason)
        
        # Clear draw schedule now that round is refunded
        self._store.update_operator_status(self._clear_draw_schedule)
        # EventManager handles live feed and history snapshot

    # ------------------------------------------------------------------
    # Draw / refund management
    # ------------------------------------------------------------------
    async def _maybe_handle_draw(self) -> None:
        current = self._store.get_current_round()
        if not current:
            return

        now = int(time.time())
        # Contract semantics: operator must call drawWinner when the round
        # is in BETTING state and current time is between min_draw_time and
        # max_draw_time. If the draw window expires, issue a refund.
        logger.info(f"Checking if draw/refund needed for round {current.round_id} in state {current.state.name} at time {now}")
        if current.state == RoundState.BETTING:
            min_draw = int(current.min_draw_time)
            max_draw = int(current.max_draw_time)
            
            # Check if we're before the draw window
            if now < min_draw:
                time_until_draw = min_draw - now
                logger.debug(f"Round {current.round_id}: waiting for draw window (starts in {time_until_draw}s)")
                return
            
            # If we're inside the draw window, attempt the draw.
            if now >= min_draw and now <= max_draw:
                logger.info(f"Round {current.round_id}: inside draw window [{min_draw}, {max_draw}], attempting draw")
                await self._attempt_draw(current)
                return

            # If we've passed the max draw time, issue a refund immediately
            if now > max_draw:
                logger.warning(f"Round {current.round_id}: draw window expired at {max_draw}, attempting refund")
                await self._attempt_refund(current)
                return
        elif current.state in {RoundState.COMPLETED, RoundState.REFUNDED}:
            self._store.update_operator_status(self._clear_draw_schedule)

    async def _attempt_draw(self, round_data: LotteryRound, *, manual: bool = False) -> None:
        logger.info("Attempting draw for round %s", round_data.round_id)
        self._store.update_operator_status(lambda status: status.record_draw_attempt())
        try:
            tx_hash = await self._client.draw_round(round_data.round_id)
            await self._client.wait_for_transaction(tx_hash, timeout=self._settings.tx_timeout_seconds)
            logger.info("Draw transaction sent: %s", tx_hash)
            self._store.update_operator_status(self._reset_draw_failures)
        except Exception as exc:  # pragma: no cover - depends on RPC
            logger.error("Draw attempt failed for round %s: %s", round_data.round_id, exc)
            status = self._store.update_operator_status(lambda s: s.increment_draw_failures())
            next_due = int(time.time() + self._settings.draw_retry_delay)
            self._schedule_draw(round_data.round_id, next_due)
            if status.consecutive_draw_failures >= self._settings.max_draw_retries:
                logger.error(
                    "Maximum draw retries reached for round %s", round_data.round_id
                )

    async def _attempt_refund(self, round_data: LotteryRound, *, manual: bool = False) -> None:
        logger.warning("Attempting refund for round %s", round_data.round_id)
        try:
            tx_hash = await self._client.refund_round(round_data.round_id)
            await self._client.wait_for_transaction(tx_hash, timeout=self._settings.tx_timeout_seconds)
            self._store.update_operator_status(self._clear_draw_schedule)
        except Exception as exc:  # pragma: no cover - depends on RPC
            logger.error("Refund attempt failed for round %s: %s", round_data.round_id, exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _schedule_draw(self, round_id: int, due_at: int) -> None:
        due_at = max(due_at, int(time.time()))
        self._store.update_operator_status(
            lambda status: self._apply_draw_schedule(status, round_id, due_at)
        )

    def _apply_draw_schedule(self, status: OperatorStatus, round_id: int, due_at: int) -> None:
        status.scheduled_draw_round_id = round_id
        status.scheduled_draw_due_at = due_at
        status.max_draw_retries = self._settings.max_draw_retries

    def _clear_draw_schedule(self, status: OperatorStatus) -> None:
        status.scheduled_draw_round_id = None
        status.scheduled_draw_due_at = None
        status.reset_draw_failures()

    def _reset_draw_failures(self, status: OperatorStatus) -> None:
        status.reset_draw_failures()
        status.scheduled_draw_round_id = None
        status.scheduled_draw_due_at = None

    def _apply_initial_status(self, status: OperatorStatus) -> None:
        status.is_running = False
        status.max_draw_retries = self._settings.max_draw_retries

    def _mark_running(self, status: OperatorStatus) -> None:
        status.is_running = True
        status.max_draw_retries = self._settings.max_draw_retries
        status.watchdog_last_check = None

    def _mark_stopped(self, status: OperatorStatus) -> None:
        status.is_running = False
        status.scheduled_draw_round_id = None
        status.scheduled_draw_due_at = None

    async def _wait_with_stop(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    def _load_settings(self, config: Dict[str, Any]) -> OperatorSettings:
        operator_cfg = config.get("operator", {})
        passive_cfg = operator_cfg.get("passive", {})

        def get_value(key: str, default: Any) -> Any:
            if key in passive_cfg:
                return passive_cfg[key]
            return operator_cfg.get(key, default)

        def to_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return float(default)

        def to_int(value: Any, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return int(default)

        return OperatorSettings(
            draw_check_interval=to_float(get_value("draw_check_interval", 10.0), 10.0),
            draw_retry_delay=to_float(get_value("draw_retry_delay", 45.0), 45.0),
            max_draw_retries=to_int(get_value("max_draw_retries", 3), 3),
            tx_timeout_seconds=to_int(get_value("tx_timeout_seconds", 180), 180),
        )


# Backwards compatible alias
AutomatedOperator = PassiveOperator