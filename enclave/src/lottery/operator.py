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
    RoundSnapshot,
    RoundState,
)

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OperatorSettings:
    """Runtime tunables for the passive operator loop."""

    event_poll_interval: float = 6.0
    state_refresh_interval: float = 30.0
    draw_check_interval: float = 10.0
    event_replay_blocks: int = 500
    draw_retry_delay: float = 45.0
    max_draw_retries: int = 3
    refund_grace_period: float = 120.0
    tx_timeout_seconds: int = 180
    rpc_call_timeout: float = 10.0


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
        self._event_from_block: Optional[int] = None
        self._event_cursor: Optional[Tuple[int, str]] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """Prime the memory store from on-chain state."""
        logger.info("Initializing passive lottery operator")
        await self._bootstrap_store()
        self._store.update_operator_status(self._apply_initial_status)
        logger.info("Passive lottery operator ready")

    async def start(self) -> None:
        """Start background tasks that keep the store in sync."""
        if self._running:
            logger.warning("Passive operator already running")
            return

        self._running = True
        self._stop_event.clear()
        self._store.update_operator_status(self._mark_running)

        logger.info("Starting passive operator loops")
        self._tasks = [
            asyncio.create_task(self._event_loop(), name="lottery-operator-events"),
            asyncio.create_task(self._state_loop(), name="lottery-operator-state"),
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
    # Event loop and state sync
    # ------------------------------------------------------------------
    async def _event_loop(self) -> None:
        if self._event_from_block is None:
            latest_block = await self._client.get_latest_block()
            self._event_from_block = max(latest_block - self._settings.event_replay_blocks, 0)
            logger.info("Starting event sync from block %s (latest: %s, replay: %s)", 
                       self._event_from_block, latest_block, self._settings.event_replay_blocks)

        while not self._stop_event.is_set():
            # Determine the block range to poll
            # if self.client._last_seen_block is None, start from 0; else, start from _last_seen_block + 1
            from_block = 0
            if self._client._last_seen_block is not None:
                from_block = self._client._last_seen_block + 1
            logger.info(f"[event_loop] Polling events from block {from_block}")
            try:
                events = await self._client.get_events(from_block)
                logger.debug(f"[event_loop] Got {len(events)} events from block {from_block}")
                if events:
                    logger.info(f"[event_loop] Processing {len(events)} events from block {from_block}")
                for event in events:
                    cursor = (event.block_number, event.transaction_hash)
                    logger.info(f"[event_loop] Processing event {event.name} at block {event.block_number}, tx {event.transaction_hash}")
                    if self._event_cursor and cursor <= self._event_cursor:
                        logger.debug(f"[event_loop] Skipping already-processed event at cursor {cursor}")
                        continue
                    try:
                        await self._handle_event(event)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        logger.exception("Failed to handle event %s: %s", event.name, exc)
                        self._store.add_operator_alert(
                            message=f"Failed to handle event {event.name}",
                            details={"error": str(exc)[:120]},
                            severity="warning",
                        )
                    self._event_cursor = cursor
                    self._event_from_block = max(self._event_from_block or 0, event.block_number)
            except Exception as exc:  # pragma: no cover - relies on RPC
                logger.exception("Event polling failed: %s", exc)
                self._store.add_operator_alert(
                    message="Blockchain event polling failed",
                    details={"error": str(exc)[:120]},
                    severity="error",
                )
            await self._wait_with_stop(self._settings.event_poll_interval)

    async def _state_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._refresh_round_state()
            except Exception as exc:  # pragma: no cover - depends on RPC
                logger.debug("State refresh failed: %s", exc)
            await self._wait_with_stop(self._settings.state_refresh_interval)

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
            await self._refresh_contract_config()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    async def _on_round_created(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        logger.info("Round %s created", round_id)
        round_data = await self._refresh_round_state()
        if round_data:
            self._schedule_draw(round_data.round_id, max(round_data.min_draw_time, int(time.time())))

    async def _on_round_state_changed(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        new_state = RoundState(int(event.args.get("newState", 0)))
        logger.info("Round %s transitioned to %s", round_id, new_state.name)
        round_data = await self._refresh_round_state(reset_participants=new_state == RoundState.WAITING)
        if new_state == RoundState.DRAWING and round_data:
            self._schedule_draw(round_data.round_id, max(round_data.min_draw_time, int(time.time())))
        if new_state in {RoundState.COMPLETED, RoundState.REFUNDED}:
            self._store.update_operator_status(self._clear_draw_schedule)

    async def _on_bet_placed(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        player = str(event.args.get("player"))
        amount = int(event.args.get("amount", 0))
        new_total = int(event.args.get("newTotal", 0))
        logger.debug("Bet placed by %s for round %s", player, round_id)

        current_round = await self._refresh_round_state(reset_participants=False)
        participants = await self._client.get_participant_summaries(round_id)
        self._store.sync_participants(participants)

        participant_count = len(participants)
        if current_round and current_round.round_id == round_id:
            participant_count = current_round.participant_count

        self._store.record_bet(
            round_id=round_id,
            player=player,
            amount=amount,
            new_total_pot=new_total,
            participant_count=participant_count,
        )

    async def _on_end_time_extended(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        new_end_time = int(event.args.get("newEndTime", 0))
        current = self._store.get_current_round()
        if current and current.round_id == round_id:
            current.end_time = new_end_time
            self._store.set_current_round(current, reset_participants=False)
        else:
            await self._refresh_round_state(reset_participants=False)
        logger.info("Round %s betting end extended to %s", round_id, new_end_time)

    async def _on_round_completed(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        winner = str(event.args.get("winner"))
        total_pot = int(event.args.get("totalPot", 0))
        winner_prize = int(event.args.get("winnerPrize", 0))
        publisher_commission = int(event.args.get("publisherCommission", 0))
        sparsity_commission = int(event.args.get("sparsityCommission", 0))
        timestamp = int(event.timestamp)

        current = self._store.get_current_round()
        snapshot = self._build_snapshot(
            source=current,
            round_id=round_id,
            total_pot=total_pot,
            winner=winner,
            winner_prize=winner_prize,
            publisher_commission=publisher_commission,
            sparsity_commission=sparsity_commission,
            state=RoundState.COMPLETED,
            finished_at=timestamp,
        )

        self._store.record_round_completion(snapshot)
        self._store.set_current_round(None)
        self._store.update_operator_status(self._clear_draw_schedule)
        await self._refresh_round_state()

    async def _on_round_refunded(self, event: BlockchainEvent) -> None:
        round_id = int(event.args.get("roundId", 0))
        total_refunded = int(event.args.get("totalRefunded", 0))
        participant_count = int(event.args.get("participantCount", 0))
        reason = str(event.args.get("reason", "") or "refunded")
        timestamp = int(event.timestamp)

        current = self._store.get_current_round()
        snapshot = self._build_snapshot(
            source=current,
            round_id=round_id,
            total_pot=total_refunded,
            winner=None,
            winner_prize=0,
            publisher_commission=0,
            sparsity_commission=0,
            state=RoundState.REFUNDED,
            finished_at=timestamp,
            refund_reason=reason,
            participant_count_override=participant_count,
        )
        logger.info("Round %s refunded: %s", round_id, reason)

        self._store.record_round_completion(snapshot)
        self._store.set_current_round(None)
        self._store.add_operator_alert(
            message=f"Round {round_id} refunded",
            details={"roundId": str(round_id), "reason": reason[:60]},
            severity="warning",
        )
        self._store.update_operator_status(self._clear_draw_schedule)
        await self._refresh_round_state()

    # ------------------------------------------------------------------
    # Draw / refund management
    # ------------------------------------------------------------------
    async def _maybe_handle_draw(self) -> None:
        current = self._store.get_current_round()
        if not current:
            return

        now = int(time.time())
        if current.state == RoundState.DRAWING:
            status = self._store.get_operator_status()
            if status.scheduled_draw_round_id != current.round_id:
                self._schedule_draw(current.round_id, max(current.min_draw_time, now))
                return

            due_at = status.scheduled_draw_due_at or current.min_draw_time
            if now >= due_at:
                await self._attempt_draw(current)
                return

            refund_deadline = current.max_draw_time + int(self._settings.refund_grace_period)
            if now >= refund_deadline:
                await self._attempt_refund(current)
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
            self._store.add_operator_alert(
                message=f"Draw submitted for round {round_data.round_id}",
                details={"roundId": str(round_data.round_id), "txHash": tx_hash},
                severity="info" if manual else "debug",
            )
        except Exception as exc:  # pragma: no cover - depends on RPC
            logger.error("Draw attempt failed for round %s: %s", round_data.round_id, exc)
            status = self._store.update_operator_status(lambda s: s.increment_draw_failures())
            self._store.add_operator_alert(
                message=f"Draw attempt failed for round {round_data.round_id}",
                details={"roundId": str(round_data.round_id), "error": str(exc)[:120]},
                severity="error",
            )
            next_due = int(time.time() + self._settings.draw_retry_delay)
            self._schedule_draw(round_data.round_id, next_due)
            if status.consecutive_draw_failures >= self._settings.max_draw_retries:
                self._store.add_operator_alert(
                    message="Maximum draw retries reached",
                    details={"roundId": str(round_data.round_id)},
                    severity="error",
                )

    async def _attempt_refund(self, round_data: LotteryRound, *, manual: bool = False) -> None:
        logger.warning("Attempting refund for round %s", round_data.round_id)
        try:
            tx_hash = await self._client.refund_round(round_data.round_id)
            await self._client.wait_for_transaction(tx_hash, timeout=self._settings.tx_timeout_seconds)
            self._store.add_operator_alert(
                message=f"Refund submitted for round {round_data.round_id}",
                details={"roundId": str(round_data.round_id), "txHash": tx_hash},
                severity="warning" if manual else "info",
            )
            self._store.update_operator_status(self._clear_draw_schedule)
        except Exception as exc:  # pragma: no cover - depends on RPC
            logger.error("Refund attempt failed for round %s: %s", round_data.round_id, exc)
            self._store.add_operator_alert(
                message=f"Refund attempt failed for round {round_data.round_id}",
                details={"roundId": str(round_data.round_id), "error": str(exc)[:120]},
                severity="error",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _bootstrap_store(self) -> None:
        config = await self._client.get_contract_config()
        current_round = await self._client.get_current_round()
        participants: List[ParticipantSummary] = []
        if current_round:
            participants = await self._client.get_participant_summaries(current_round.round_id)
        self._store.bootstrap(
            current_round=current_round,
            participants=participants,
            history=(),
            contract_config=config,
        )

    async def _refresh_round_state(self, *, reset_participants: bool = True) -> Optional[LotteryRound]:
        try:
            round_data = await asyncio.wait_for(self._client.get_current_round(), timeout=self._settings.rpc_call_timeout)
        except asyncio.TimeoutError:
            logger.warning("_refresh_round_state: RPC call timed out after %ss", self._settings.rpc_call_timeout)
            return None
        except Exception as exc:
            logger.warning("_refresh_round_state: RPC call failed: %s", exc)
            return None
        if round_data:
            self._store.set_current_round(round_data, reset_participants=reset_participants)
        else:
            self._store.set_current_round(None)
        # dump the current round data for debugging purpose
        logger.info("Current round data: %s", round_data)
        return round_data

    async def _refresh_contract_config(self) -> None:
        config = await self._client.get_contract_config()
        self._store.set_contract_config(config)

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

    def _build_snapshot(
        self,
        *,
        source: Optional[LotteryRound],
        round_id: int,
        total_pot: int,
        winner: Optional[str],
        winner_prize: int,
        publisher_commission: int,
        sparsity_commission: int,
        state: RoundState,
        finished_at: int,
        refund_reason: Optional[str] = None,
        participant_count_override: Optional[int] = None,
    ) -> RoundSnapshot:
        if source and source.round_id == round_id:
            participant_count = participant_count_override or source.participant_count
            return RoundSnapshot(
                round_id=round_id,
                start_time=source.start_time,
                end_time=source.end_time,
                min_draw_time=source.min_draw_time,
                max_draw_time=source.max_draw_time,
                total_pot=total_pot or source.total_pot,
                participant_count=participant_count,
                winner=winner,
                winner_prize=winner_prize,
                publisher_commission=publisher_commission or source.publisher_commission,
                sparsity_commission=sparsity_commission or source.sparsity_commission,
                state=state,
                finished_at=finished_at,
                refund_reason=refund_reason,
            )
        return RoundSnapshot(
            round_id=round_id,
            start_time=0,
            end_time=0,
            min_draw_time=0,
            max_draw_time=0,
            total_pot=total_pot,
            participant_count=participant_count_override or 0,
            winner=winner,
            winner_prize=winner_prize,
            publisher_commission=publisher_commission,
            sparsity_commission=sparsity_commission,
            state=state,
            finished_at=finished_at,
            refund_reason=refund_reason,
        )

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
            event_poll_interval=to_float(get_value("event_poll_interval", 6.0), 6.0),
            state_refresh_interval=to_float(get_value("state_refresh_interval", 30.0), 30.0),
            draw_check_interval=to_float(get_value("draw_check_interval", 10.0), 10.0),
            event_replay_blocks=to_int(get_value("event_replay_blocks", 500), 500),
            draw_retry_delay=to_float(get_value("draw_retry_delay", 45.0), 45.0),
            max_draw_retries=to_int(get_value("max_draw_retries", 3), 3),
            refund_grace_period=to_float(get_value("refund_grace_period", 120.0), 120.0),
            tx_timeout_seconds=to_int(get_value("tx_timeout_seconds", 180), 180),
        )


# Backwards compatible alias
AutomatedOperator = PassiveOperator