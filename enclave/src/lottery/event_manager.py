from __future__ import annotations

from utils.logger import get_logger

logger = get_logger(__name__)
"""In-memory state manager for the passive lottery backend."""
from collections import defaultdict, deque
from threading import Lock
from typing import Callable, Dict, Iterable, List, Optional

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
        self._current_round: Optional[LotteryRound] = None
        self._participant_summaries: Dict[str, ParticipantSummary] = {}
        self._history: deque[RoundSnapshot] = deque(maxlen=history_capacity)
        self._live_feed: deque[LiveFeedItem] = deque(maxlen=feed_capacity)
        self._operator_status = OperatorStatus()
        self._contract_config: Optional[ContractConfig] = None
        self._listeners: Dict[str, List[Callable[[dict | None], None]]] = defaultdict(list)
        self._feed_capacity = feed_capacity
        self._history_capacity = history_capacity

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

    def record_bet(
        self,
        *,
        round_id: int,
        player: str,
        amount: int,
        new_total_pot: int,
        participant_count: int,
    ) -> None:
        player_key = player.lower()
        with self._lock:
            summary = self._participant_summaries.get(player_key)
            if summary is None:
                summary = ParticipantSummary(address=player)
                self._participant_summaries[player_key] = summary
            summary.add_bet(amount)

            if self._current_round and self._current_round.round_id == round_id:
                self._current_round.total_pot = new_total_pot
                self._current_round.participant_count = participant_count

            feed_item = LiveFeedItem(
                event_type="bet_placed",
                message=f"Bet placed by {player[:10]}",
                details={
                    "roundId": round_id,
                    "player": player,
                    "amountWei": amount,
                    "totalPotWei": new_total_pot,
                },
            )
            self._append_feed(feed_item)

            payload = self._serialize_round(self._current_round) if self._current_round else None

        self._emit("round_update", payload)
        self._emit("participants_update", self._serialize_participants())
        self._emit("live_feed", self._serialize_feed_item(feed_item))
        logger.debug(f"[MemoryStore] record_bet: round_id={round_id}, player={player}, amount={amount}, new_total_pot={new_total_pot}, participant_count={participant_count}")

    def record_round_completion(self, snapshot: RoundSnapshot) -> None:
        with self._lock:
            self._append_history(snapshot)
            feed_item = LiveFeedItem(
                event_type="round_completed"
                if snapshot.state.name == "COMPLETED"
                else "round_refunded",
                message=f"Round {snapshot.round_id} {snapshot.state.name.lower()}",
                details={
                    "roundId": snapshot.round_id,
                    "totalPotWei": snapshot.total_pot,
                    "winner": snapshot.winner or "",
                },
            )
            self._append_feed(feed_item)
            self._participant_summaries = {}
            payload_feed = self._serialize_feed_item(feed_item)
        
        self._emit("history_update", self._serialize_history())
        self._emit("participants_update", self._serialize_participants())
        self._emit("live_feed", payload_feed)

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

    def add_operator_alert(
        self,
        *,
        message: str,
        details: Dict[str, int | str],
        severity: str = "error",
    ) -> None:
        feed_item = LiveFeedItem(
            event_type="operator_alert",
            message=message,
            details=details,
            severity=severity,
        )
        with self._lock:
            self._append_feed(feed_item)
        payload = self._serialize_feed_item(feed_item)
        self._emit("live_feed", payload)
        self._emit("operator_alert", payload)
        logger.debug(f"[MemoryStore] add_operator_alert: message={message}, details={details}, severity={severity}")

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

    def _append_feed(self, item: LiveFeedItem) -> None:
        self._live_feed.append(item)

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
        logger.info(f"[MemoryStore] _serialize_history: {len(rounds)} rounds serialized")
        return {"rounds": rounds}

    def _serialize_feed_item(self, item: LiveFeedItem) -> dict:
        return {
            "type": item.event_type,
            "message": item.message,
            "details": item.details,
            "severity": item.severity,
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


import asyncio
from typing import Any, Dict, List, Optional

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

    # Deprecated individual loops removed. Use the combined loop below.

    async def _round_and_participants_loop(self) -> None:
        """Single-interval loop that refreshes the current round and participants.

        Both refreshes run once per configured interval (shared). The
        participants refresh only runs when a current round exists.
        """
        interval = float(self._round_status_interval)
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

        # BetPlaced: roundId (indexed), player (indexed), amount, newTotal, timestamp
        if name == "BetPlaced":
            try:
                round_id = int(args.get("roundId", 0))
                player = args.get("player")
                amount = int(args.get("amount", 0))
                new_total = int(args.get("newTotal", 0))
                # Try to fetch participant_count from current round if available
                participant_count = 0
                current = self.store.get_current_round()
                if current and current.round_id == round_id:
                    participant_count = current.participant_count
                self.store.record_bet(round_id=round_id, player=player, amount=amount, new_total_pot=new_total, participant_count=participant_count)
            except Exception:
                # Fallback to calling record_bet with available fields
                try:
                    self.store.record_bet(round_id=int(args.get("roundId", 0)), player=args.get("player"), amount=int(args.get("amount", 0)), new_total_pot=int(args.get("newTotal", 0)), participant_count=0)
                except Exception:
                    logger.debug("Failed to record BetPlaced event")

        elif name == "RoundCompleted":
            try:
                round_id = int(args.get("roundId", 0))
                winner = args.get("winner")
                total_pot = int(args.get("totalPot", 0))
                winner_prize = int(args.get("winnerPrize", 0))
                publisher_comm = int(args.get("publisherCommission", 0))
                sparsity_comm = int(args.get("sparsityCommission", 0))
                finished_at = int(getattr(evt, "timestamp", 0) or 0)
                # Try to populate start/end/min/max from current round if it matches
                start_time = 0
                end_time = 0
                min_draw = 0
                max_draw = 0
                participant_count = 0
                current = self.store.get_current_round()
                if current and current.round_id == round_id:
                    start_time = current.start_time
                    end_time = current.end_time
                    min_draw = current.min_draw_time
                    max_draw = current.max_draw_time
                    participant_count = current.participant_count

                snapshot = RoundSnapshot(
                    round_id=round_id,
                    start_time=start_time,
                    end_time=end_time,
                    min_draw_time=min_draw,
                    max_draw_time=max_draw,
                    total_pot=total_pot,
                    participant_count=participant_count,
                    winner=winner,
                    winner_prize=winner_prize,
                    publisher_commission=publisher_comm,
                    sparsity_commission=sparsity_comm,
                    state=RoundState.COMPLETED,
                    finished_at=finished_at,
                )
                self.store.record_round_completion(snapshot)
            except Exception as exc:
                logger.debug("Failed to process RoundCompleted: %s", exc)

        elif name == "RoundRefunded":
            try:
                round_id = int(args.get("roundId", 0))
                total_refunded = int(args.get("totalRefunded", 0))
                participant_count = int(args.get("participantCount", 0))
                reason = args.get("reason")
                finished_at = int(getattr(evt, "timestamp", 0) or 0)

                snapshot = RoundSnapshot(
                    round_id=round_id,
                    start_time=0,
                    end_time=0,
                    min_draw_time=0,
                    max_draw_time=0,
                    total_pot=total_refunded,
                    participant_count=participant_count,
                    winner=None,
                    winner_prize=0,
                    publisher_commission=0,
                    sparsity_commission=0,
                    state=RoundState.REFUNDED,
                    finished_at=finished_at,
                    refund_reason=reason,
                )
                self.store.record_round_completion(snapshot)
            except Exception as exc:
                logger.debug("Failed to process RoundRefunded: %s", exc)

        else:
            # Other events: operator/config updates; refresh config/round/participants locally
            if name in ("SparsitySet", "OperatorUpdated", "MinBetAmountUpdated", "BettingDurationUpdated"):
                try:
                    cfg = await self.client.get_contract_config()
                    self.store.set_contract_config(cfg)
                except Exception:
                    pass
            # For bet-related state changes, trigger a local refresh
            if name in ("BetPlaced", "RoundCreated", "EndTimeExtended"):
                try:
                    round_data = await self.client.get_current_round()
                    self.store.set_current_round(round_data, reset_participants=False)
                except Exception:
                    pass
