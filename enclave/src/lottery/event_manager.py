from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)
"""In-memory state manager for the passive lottery backend."""

from lottery.models import (
    ContractConfig,
    LiveFeedItem,
    LotteryRound,
    OperatorStatus,
    ParticipantSummary,
    RoundSnapshot,
    RoundState,
)

class MemoryStore:
    """Volatile storage for contract state, history, and live feed."""

    def __init__(self, *, feed_capacity: int = 200, history_capacity: int = 200) -> None:
        self._lock = Lock()
        self._listeners: Dict[str, List[Callable[[dict | None], None]]] = defaultdict(list)
        self._feed_capacity = feed_capacity
        self._history_capacity = history_capacity
        self._live_feed: deque[LiveFeedItem] = deque(maxlen=feed_capacity)
        self._history: deque[RoundSnapshot] = deque(maxlen=history_capacity)
        self._participant_summaries: Dict[str, ParticipantSummary] = {}
        self._current_round: Optional[LotteryRound] = None
        self._operator_status = OperatorStatus()
        self._contract_config: Optional[ContractConfig] = None

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------
    def add_listener(self, event_type: str, callback: Callable[[dict | None], None]) -> None:
        with self._lock:
            self._listeners[event_type].append(callback)
            logger.debug(f"[MemoryStore] Adding listener for event_type={event_type}, callback={callback}")

    def _emit(self, event_type: str, payload: dict | None) -> None:
        listeners = list(self._listeners.get(event_type, []))
        for callback in listeners:
            try:
                logger.info("Emitting %s event to listener", event_type)
                callback(payload)
            except Exception as exc:  # pragma: no cover
                logger.error("Listener for %s failed: %s", event_type, exc)

    # ------------------------------------------------------------------
    # Bootstrap helpers
    # ------------------------------------------------------------------
    def bootstrap(
        self,
        *,
        current_round: Optional[LotteryRound],
        participants: Iterable[ParticipantSummary] = (),
        history: Iterable[RoundSnapshot] = (),
        contract_config: Optional[ContractConfig] = None,
    ) -> None:
        with self._lock:
            self._current_round = current_round
            self._participant_summaries = {p.address.lower(): p for p in participants}
            self._history.clear()
            for item in history:
                self._history.append(item)
            self._contract_config = contract_config
            if current_round:
                self._operator_status.current_round_id = current_round.round_id

        if current_round:
            self._emit("round_update", self._serialize_round(current_round))
        self._emit("participants_update", self._serialize_participants())
        self._emit("history_update", self._serialize_history())
        if contract_config:
            self._emit("config_update", self._serialize_config(contract_config))
        logger.info(f"[MemoryStore] Bootstrapped with current_round={current_round}, participants={participants}, contract_config={contract_config}")

    # ------------------------------------------------------------------
    # Round state management
    # ------------------------------------------------------------------
    def set_current_round(self, round_data: Optional[LotteryRound], *, reset_participants: bool = True) -> None:
        with self._lock:
            self._current_round = round_data
            if reset_participants:
                self._participant_summaries = {}
            self._operator_status.current_round_id = (
                round_data.round_id if round_data else None
            )
            self._operator_status.record_event()

            payload = self._serialize_round(round_data) if round_data else None

        self._emit("round_update", payload)
        self._emit("participants_update", self._serialize_participants())
        logger.info(f"[MemoryStore] set_current_round called with round_data={round_data}, reset_participants={reset_participants}")

    def sync_participants(self, summaries: Iterable[ParticipantSummary]) -> None:
        with self._lock:
            self._participant_summaries = {p.address.lower(): p for p in summaries}
        self._emit("participants_update", self._serialize_participants())
        logger.debug(f"[MemoryStore] sync_participants called with {len(list(summaries))} participants")


    def add_live_feed(
        self,
        *,
        event_type: str,
        message: str,
        details: Dict[str, int | str] | None = None,
    ) -> None:
        """Public helper to append a simple live-feed item and emit it.

        This avoids performing other side-effects (history/participants) when
        callers only want to post a short live feed message.
        """
        safe_details = dict(details or {})
        timestamp_val = safe_details.get("timestamp", 0)
        # Convert timestamp to datetime
        if isinstance(timestamp_val, int):
            created_at = datetime.fromtimestamp(timestamp_val) if timestamp_val > 0 else datetime.now()
        else:
            created_at = datetime.now()
        
        feed_item = LiveFeedItem(
            event_type=event_type,
            message=message,
            details=safe_details,
            created_at=created_at,
        )
        with self._lock:
            self._append_feed(feed_item)
            payload = self._serialize_feed_item(feed_item)

        self._emit("live_feed", payload)

    # ------------------------------------------------------------------
    # Configuration and status
    # ------------------------------------------------------------------
    def set_contract_config(self, config: ContractConfig) -> None:
        with self._lock:
            self._contract_config = config
        self._emit("config_update", self._serialize_config(config))
        logger.debug(f"[MemoryStore] set_contract_config: config={config}")

    def get_contract_config(self) -> Optional[ContractConfig]:
        with self._lock:
            return self._contract_config

    def update_operator_status(self, update: Callable[[OperatorStatus], None]) -> OperatorStatus:
        with self._lock:
            update(self._operator_status)
            status_copy = OperatorStatus(
                is_running=self._operator_status.is_running,
                current_round_id=self._operator_status.current_round_id,
                last_event_time=self._operator_status.last_event_time,
                last_draw_attempt=self._operator_status.last_draw_attempt,
                consecutive_draw_failures=self._operator_status.consecutive_draw_failures,
                max_draw_retries=self._operator_status.max_draw_retries,
                scheduled_draw_round_id=self._operator_status.scheduled_draw_round_id,
                scheduled_draw_due_at=self._operator_status.scheduled_draw_due_at,
                watchdog_last_check=self._operator_status.watchdog_last_check,
            )
        self._emit("operator_status", self._serialize_operator_status(status_copy))
        logger.debug(f"[MemoryStore] update_operator_status called with update={update}")
        return status_copy

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_current_round(self) -> Optional[LotteryRound]:
        with self._lock:
            return self._current_round

    def get_participants(self) -> List[ParticipantSummary]:
        with self._lock:
            return sorted(
                self._participant_summaries.values(),
                key=lambda item: item.total_amount,
                reverse=True,
            )

    def get_round_history(self, limit: Optional[int] = None) -> List[RoundSnapshot]:
        with self._lock:
            items = list(self._history)
        if limit is not None:
            return items[-limit:]
        return items

    def get_live_feed(self, limit: Optional[int] = None) -> List[LiveFeedItem]:
        with self._lock:
            items = list(self._live_feed)
        if limit is not None:
            return items[-limit:]
        return items

    def get_operator_status(self) -> OperatorStatus:
        with self._lock:
            return self._operator_status

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _append_history(self, snapshot: RoundSnapshot) -> None:
        self._history.append(snapshot)

    def add_history_snapshot(self, *, event_type: str, details: Dict[str, int | str]) -> None:
        """Public helper to append a RoundSnapshot to history and emit update.

        The EventManager may call this with event args (details) from contract
        events; attempt to normalise common field names and fall back to the
        current round when fields are missing.
        """
        try:
            snapshot_details = dict(details or {})

            def _as_int(value: Any, default: int = 0) -> int:
                if value is None:
                    return default
                try:
                    if isinstance(value, str) and value.startswith("0x"):
                        return int(value, 16)
                    return int(value)
                except Exception:
                    return default

            current_round = self.get_current_round()
            round_id = _as_int(
                snapshot_details.get("roundId")
                or snapshot_details.get("round_id")
                or (current_round.round_id if current_round else 0)
            )
            start_time = _as_int(snapshot_details.get("startTime") or snapshot_details.get("start_time"))
            end_time = _as_int(snapshot_details.get("endTime") or snapshot_details.get("end_time"))
            min_draw_time = _as_int(
                snapshot_details.get("minDrawTime") or snapshot_details.get("min_draw_time")
            )
            max_draw_time = _as_int(
                snapshot_details.get("maxDrawTime") or snapshot_details.get("max_draw_time")
            )
            total_pot = _as_int(
                snapshot_details.get("totalPot")
                or snapshot_details.get("total_pot")
                or snapshot_details.get("total_pot_wei")
                or snapshot_details.get("totalPotWei")
                or snapshot_details.get("totalRefunded")
                or snapshot_details.get("total_refunded")
            )
            participant_count = _as_int(
                snapshot_details.get("participantCount") or snapshot_details.get("participant_count")
            )
            winner = snapshot_details.get("winner")
            if event_type == "RoundRefunded":
                winner = None
            winner_prize = _as_int(
                snapshot_details.get("winnerPrize")
                or snapshot_details.get("winner_prize")
                or snapshot_details.get("winnerPrizeWei")
                or snapshot_details.get("winner_prize_wei")
            )
            publisher_commission = _as_int(
                snapshot_details.get("publisherCommission")
                or snapshot_details.get("publisher_commission")
                or snapshot_details.get("publisherCommissionWei")
                or snapshot_details.get("publisher_commission_wei")
            )
            sparsity_commission = _as_int(
                snapshot_details.get("sparsityCommission")
                or snapshot_details.get("sparsity_commission")
                or snapshot_details.get("sparsityCommissionWei")
                or snapshot_details.get("sparsity_commission_wei")
            )
            # Determine state enum if provided
            state_val = snapshot_details.get("state") or snapshot_details.get("final_state")
            if state_val is None:
                # fallback: completed/refunded based on event_type
                state = RoundState.COMPLETED if event_type == "RoundCompleted" else RoundState.REFUNDED
            else:
                try:
                    # if numeric
                    state = RoundState(int(state_val))
                except Exception:
                    try:
                        state = RoundState[state_val]
                    except Exception:
                        state = RoundState.COMPLETED

            finished_at = _as_int(
                snapshot_details.get("timestamp")
                or snapshot_details.get("finishedAt")
                or snapshot_details.get("finished_at")
            )
            refund_reason = snapshot_details.get("refundReason") or snapshot_details.get("refund_reason")

            if current_round and current_round.round_id == round_id:
                if start_time == 0:
                    start_time = current_round.start_time
                if end_time == 0:
                    end_time = current_round.end_time
                if min_draw_time == 0:
                    min_draw_time = current_round.min_draw_time
                if max_draw_time == 0:
                    max_draw_time = current_round.max_draw_time
                if total_pot == 0:
                    total_pot = current_round.total_pot
                if participant_count == 0:
                    participant_count = current_round.participant_count
                if winner is None and current_round.winner:
                    winner = current_round.winner
                if winner_prize == 0:
                    winner_prize = current_round.winner_prize
                if publisher_commission == 0:
                    publisher_commission = current_round.publisher_commission
                if sparsity_commission == 0:
                    sparsity_commission = current_round.sparsity_commission

            snapshot = RoundSnapshot(
                round_id=round_id,
                start_time=start_time,
                end_time=end_time,
                min_draw_time=min_draw_time,
                max_draw_time=max_draw_time,
                total_pot=total_pot,
                participant_count=participant_count,
                winner=winner,
                winner_prize=winner_prize,
                publisher_commission=publisher_commission,
                sparsity_commission=sparsity_commission,
                state=state,
                finished_at=finished_at,
                refund_reason=refund_reason,
            )
            appended = False
            with self._lock:
                duplicate = False
                for existing in reversed(self._history):
                    if (
                        existing.round_id == snapshot.round_id
                        and existing.state == snapshot.state
                        and existing.finished_at == snapshot.finished_at
                    ):
                        duplicate = True
                        break
                if duplicate:
                    logger.debug("[MemoryStore] duplicate history snapshot for round %s suppressed", round_id)
                else:
                    self._append_history(snapshot)
                    appended = True

            if not appended:
                return

            history_payload = self._serialize_history()

            # Emit an update for listeners
            self._emit("history_update", history_payload)
            logger.info(f"[MemoryStore] added history snapshot for round {round_id}")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[MemoryStore] add_history_snapshot failed: %s", exc)

    def _append_feed(self, item: LiveFeedItem) -> None:
        if item.details is None:
            item.details = {}
        else:
            item.details = dict(item.details)

        recent = list(self._live_feed)[-10:]
        for existing in reversed(recent):
            if (
                existing.event_type == item.event_type
                and existing.message == item.message
                and existing.details == item.details
            ):
                logger.debug("[MemoryStore] duplicate live feed suppressed for event %s", item.event_type)
                return

        self._live_feed.append(item)
        logger.info("[MemoryStore] appended live feed item %s", item.event_type)

    def _serialize_round(self, round_data: Optional[LotteryRound]) -> Optional[dict]:
        if not round_data:
            return None
        return {
            "roundId": round_data.round_id,
            "state": round_data.state.value,
            "stateLabel": round_data.state.name,
            "startTime": round_data.start_time,
            "endTime": round_data.end_time,
            "minDrawTime": round_data.min_draw_time,
            "maxDrawTime": round_data.max_draw_time,
            "totalPotWei": round_data.total_pot,
            "participantCount": round_data.participant_count,
            "winner": round_data.winner,
            "publisherCommissionWei": round_data.publisher_commission,
            "sparsityCommissionWei": round_data.sparsity_commission,
            "winnerPrizeWei": round_data.winner_prize,
        }

    def _serialize_participants(self) -> dict:
        participants = [
            {
                "address": summary.address,
                "totalAmountWei": summary.total_amount,
            }
            for summary in self.get_participants()
        ]
        return {
            "participants": participants,
            "totalParticipants": len(participants),
        }

    def _serialize_history(self) -> dict:
        rounds = [
            {
                "roundId": snapshot.round_id,
                "state": snapshot.state.value,
                "stateLabel": snapshot.state.name,
                "startTime": snapshot.start_time,
                "endTime": snapshot.end_time,
                "minDrawTime": snapshot.min_draw_time,
                "maxDrawTime": snapshot.max_draw_time,
                "totalPotWei": snapshot.total_pot,
                "participantCount": snapshot.participant_count,
                "winner": snapshot.winner,
                "winnerPrizeWei": snapshot.winner_prize,
                "publisherCommissionWei": snapshot.publisher_commission,
                "sparsityCommissionWei": snapshot.sparsity_commission,
                "finishedAt": snapshot.finished_at,
                "refundReason": snapshot.refund_reason,
            }
            for snapshot in self.get_round_history()
        ]
        # sort history by round_id descending
        rounds.sort(key=lambda x: x["roundId"], reverse=True)

        logger.info(f"[MemoryStore] _serialize_history: {len(rounds)} rounds serialized")
        return {"rounds": rounds}

    def _serialize_feed_item(self, item: LiveFeedItem) -> dict:
        return {
            "type": item.event_type,
            "message": item.message,
            "details": item.details,
            "timestamp": item.created_at.isoformat(),
        }

    def _serialize_config(self, config: ContractConfig) -> dict:
        return {
            "publisher": config.publisher_addr,
            "sparsity": config.sparsity_addr,
            "operator": config.operator_addr,
            "publisherCommission": config.publisher_commission,
            "sparsityCommission": config.sparsity_commission,
            "minBet": config.min_bet,
            "bettingDuration": config.betting_duration,
            "minDrawDelay": config.min_draw_delay,
            "maxDrawDelay": config.max_draw_delay,
            "minEndTimeExtension": config.min_end_time_extension,
            "minParticipants": config.min_participants,
        }

    def _serialize_operator_status(self, status: OperatorStatus) -> dict:
        return {
            "isRunning": status.is_running,
            "currentRoundId": status.current_round_id,
            "lastEventTime": status.last_event_time.isoformat() if status.last_event_time else None,
            "lastDrawAttempt": status.last_draw_attempt.isoformat() if status.last_draw_attempt else None,
            "consecutiveDrawFailures": status.consecutive_draw_failures,
            "maxDrawRetries": status.max_draw_retries,
            "scheduledDrawRoundId": status.scheduled_draw_round_id,
            "scheduledDrawDueAt": status.scheduled_draw_due_at,
            "watchdogLastCheck": status.watchdog_last_check.isoformat() if status.watchdog_last_check else None,
        }

    def clear_all_data(self) -> None:
        with self._lock:
            self._current_round = None
            self._participant_summaries = {}
            self._history.clear()
            self._live_feed.clear()
            self._operator_status = OperatorStatus(
                max_draw_retries=self._operator_status.max_draw_retries
            )
            self._contract_config = None
        self._emit("round_update", None)
        self._emit("participants_update", self._serialize_participants())
        self._emit("history_update", self._serialize_history())
        logger.debug("[MemoryStore] clear_all_data called")

    # ------------------------------------------------------------------
    # Runtime resizing helpers
    # ------------------------------------------------------------------
    def set_feed_capacity(self, capacity: int) -> None:
        """Resize the live feed capacity (max entries)."""
        with self._lock:
            if capacity == self._feed_capacity:
                return
            old_items = list(self._live_feed)
            self._live_feed = deque(old_items[-capacity:], maxlen=capacity)
            self._feed_capacity = capacity
        logger.info(f"[MemoryStore] live feed capacity set to {capacity}")

    def set_history_capacity(self, capacity: int) -> None:
        """Resize the round history capacity (max snapshots)."""
        with self._lock:
            if capacity == self._history_capacity:
                return
            old_items = list(self._history)
            self._history = deque(old_items[-capacity:], maxlen=capacity)
            self._history_capacity = capacity
        logger.info(f"[MemoryStore] history capacity set to {capacity}")


# Global singleton used across the backend.
memory_store = MemoryStore()

from blockchain.client import BlockchainClient
from utils.config import load_config


class EventManager:
    """Polls chain state and events and writes into the MemoryStore.

    Responsibilities:
    - Periodically refresh contract config, current round, and participants.
    - Poll eth_getLogs for new events and translate them into live_feed entries
      and round history snapshots.

    This class is intentionally lightweight and in-memory only. It expects an
    initialized BlockchainClient instance (its `initialize()` must have been
    called) and a MemoryStore singleton to write into.
    """

    def __init__(self, client: BlockchainClient, config: Optional[Dict[str, Any]] = None, store: MemoryStore = memory_store) -> None:
        self.client = client
        self.config = config or load_config()
        self.store = store

        em_cfg = self.config.get("event_manager", {})
        self._contract_config_interval = float(em_cfg.get("contract_config_interval_sec", 10.0))
        self._round_and_participants_interval_sec = float(em_cfg.get("round_and_participants_interval_sec", 2.0))
        self._start_block_offset = int(em_cfg.get("start_block_offset", 500))

        self._feed_capacity = int(em_cfg.get("live_feed_max_entries", 1000))
        self._history_capacity = int(em_cfg.get("round_history_max", 100))

        # Event polling state
        self._from_block: Optional[int] = None
        self._tasks: List[asyncio.Task] = []
        self._stop_event = asyncio.Event()

    async def initialize(self) -> None:
        # Ensure client is available and determine initial from_block
        try:
            latest = await self.client.get_latest_block()
        except Exception:
            latest = 0
        start = max(0, latest - self._start_block_offset)
        self._from_block = start

        # Ensure store capacities match config
        try:
            self.store.set_feed_capacity(self._feed_capacity)
            self.store.set_history_capacity(self._history_capacity)
        except Exception:
            pass

    async def start(self) -> None:
        """Create background tasks for polling loops."""
        if self._tasks:
            return
        self._stop_event.clear()
        loop = asyncio.get_running_loop()
        self._tasks = [
            loop.create_task(self._contract_config_loop()),
            loop.create_task(self._round_and_participants_loop()),
            loop.create_task(self._events_loop()),
        ]

    async def stop(self) -> None:
        """Stop background tasks and wait for termination."""
        self._stop_event.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._tasks = []

    async def _contract_config_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                cfg = await self.client.get_contract_config()
                self.store.set_contract_config(cfg)
            except Exception as exc:
                logger.debug("EventManager contract_config_loop error: %s", exc)
            
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._contract_config_interval)
                break
            except asyncio.TimeoutError:
                continue

    async def _round_and_participants_loop(self) -> None:
        """Single-interval loop that refreshes the current round and participants.

        Both refreshes run once per configured interval (shared). The
        participants refresh only runs when a current round exists.
        """
        interval = float(self._round_and_participants_interval_sec)
        while not self._stop_event.is_set():
            try:
                # Refresh round status
                round_data = await self.client.get_current_round()
                self.store.set_current_round(round_data, reset_participants=False)
            except Exception as exc:  # pragma: no cover
                logger.debug("EventManager round refresh error: %s", exc)

            try:
                # Refresh participants if a round is active
                current = self.store.get_current_round()
                if current:
                    summaries = await self.client.get_participant_summaries(current.round_id)
                    self.store.sync_participants(summaries)
            except Exception as exc:  # pragma: no cover
                logger.debug("EventManager participants refresh error: %s", exc)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                continue

    async def _events_loop(self) -> None:
        # Continuously poll for events using the client.get_events(from_block)
        while not self._stop_event.is_set():
            if self._from_block is None:
                try:
                    latest = await self.client.get_latest_block()
                    self._from_block = max(0, latest - self._start_block_offset)
                except Exception:
                    await asyncio.sleep(1.0)
                    continue

            try:
                events = await self.client.get_events(self._from_block)
            except Exception as exc:
                logger.debug("EventManager events_loop get_events error: %s", exc)
                events = []

            if events:
                for evt in events:
                    logger.info("EventManager processing event %s", getattr(evt, 'name', None))
                    try:
                        await self._handle_event(evt)
                    except Exception as exc:
                        logger.debug("EventManager failed to handle event %s: %s", getattr(evt, 'name', None), exc)
                # advance from_block to last seen + 1
                last_block = max(e.block_number for e in events)
                self._from_block = last_block + 1
            else:
                # back off briefly when no events
                await asyncio.sleep(1.0)

            # small sleep to avoid tight loop
            await asyncio.sleep(0.2)

    async def _handle_event(self, evt: Any) -> None:
        name = getattr(evt, "name", "")
        args = getattr(evt, "args", {}) or {}
        logger.info("EventManager handling event %s args=%s", name, args)

        # Emit blockchain event to registered listeners (e.g., operator)
        # Pass the full event object so listeners can access all properties
        self.store._emit("blockchain_event", {
            "event": evt,
            "name": name,
            "args": args,
            "block_number": getattr(evt, "block_number", 0),
            "transaction_hash": getattr(evt, "transaction_hash", ""),
            "timestamp": getattr(evt, "timestamp", 0),
        })

        # For events that should be posted to the live feed, follow the
        # contract event definitions exactly: include each event parameter (as
        # present in args) in the feed.details.
        live_feed_events = {
            "RoundCreated",
            "BetPlaced",
            "RoundCompleted",
            "RoundRefunded",
        }

        if name in live_feed_events:
            try:
                message = f"{name}"
                self.store.add_live_feed(
                    event_type=name,
                    message=message,
                    details=args,
                )
            except Exception as exc:
                logger.debug("Failed to post %s live feed: %s", name, exc)

        else:
            # Other events: operator/config updates
            if name in ("SparsitySet", "OperatorUpdated", "MinBetAmountUpdated", "BettingDurationUpdated"):
                # do nothing
                pass
            # For bet-related state changes
            if name in ("EndTimeExtended", "RoundStateChanged"):
                # do nothing
                pass

        if name in ("RoundCompleted", "RoundRefunded"):
            try:
                self.store.add_history_snapshot(event_type=name, details=dict(args))
            except Exception as exc:
                logger.debug("Failed to append history snapshot for %s: %s", name, exc)
