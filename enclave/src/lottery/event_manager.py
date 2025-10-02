from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Optional

from utils.logger import get_logger
from utils.common import shorten_eth_address

logger = get_logger(__name__)
"""In-memory state manager for the passive lottery backend."""

from lottery.models import (
    ContractConfig,
    LiveFeedItem,
    LotteryRound,
    ParticipantSummary,
    RoundSnapshot,
    RoundState,
)

class MemoryStore:
    """Volatile storage for contract state, history, and live feed."""

    def __init__(self, *, feed_capacity: int = 100, history_capacity: int = 20) -> None:
        self._lock = Lock()
        self._listeners: Dict[str, List[Callable[[dict | None], None]]] = defaultdict(list)
        self._feed_capacity = feed_capacity
        self._history_capacity = history_capacity
        self._live_feed: deque[LiveFeedItem] = deque(maxlen=feed_capacity)
        self._history: deque[RoundSnapshot] = deque(maxlen=history_capacity)
        self._participant_summaries: Dict[str, ParticipantSummary] = {}
        self._current_round: Optional[LotteryRound] = None
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
        details: Dict[str, int | str] | None = None
    ) -> None:
        """Public helper to append a simple live-feed item and emit it.

        This avoids performing other side-effects (history/participants) when
        callers only want to post a short live feed message.
        """
        safe_details = dict(details or {})
        event_time = safe_details.get("timestamp", 0)
        
        feed_item = LiveFeedItem(
            event_type=event_type,
            message=message,
            details=safe_details,
            event_time=event_time,
        )
        
        logger.info(f"[MemoryStore] add_live_feed called with feed_item: {feed_item}")
        with self._lock:
            self._append_feed(feed_item)
        
        # feed_payload = self._serialize_feed_item(feed_item)
        # logger.info(f"[MemoryStore] Emitting live_feed event: {feed_payload}")

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def add_history_snapshot(self, *, event_type: str, details: Dict[str, int | str]) -> None:
        """Public helper to append a RoundSnapshot to history and emit update.

        Extracts all information from details dict; no fallback to current_round.
        """
        try:
            d = dict(details or {})
            
            # logger.info(f"[MemoryStore] add_history_snapshot called with event_type={event_type}, details={d}")

            def _as_int(value: Any, default: int = 0) -> int:
                if value is None:
                    return default
                try:
                    if isinstance(value, str) and value.startswith("0x"):
                        return int(value, 16)
                    return int(value)
                except Exception:
                    return default

            # Extract required fields
            round_id = _as_int(d.get("roundId", 0))
            participant_count = _as_int(d.get("participantCount", 0))
            total_pot = 0
            finished_at = _as_int(d.get("timestamp", 0))

            # Conditional fields based on event_type
            if event_type == "RoundCompleted":
                winner = d.get("winner")
                winner_prize = _as_int(d.get("winnerPrize", 0))
                refund_reason = None
                total_pot = _as_int(d.get("totalPot", 0))
            else:  # RoundRefunded
                winner = None
                winner_prize = 0
                refund_reason = d.get("reason")
                total_pot = _as_int(d.get("totalRefunded", 0))

            snapshot = RoundSnapshot(
                event_type=event_type,
                round_id=round_id,
                participant_count=participant_count,
                total_pot=total_pot,
                finished_at=finished_at,
                refund_reason=refund_reason,
                winner=winner,
                winner_prize=winner_prize,
            )
            
            with self._lock:
                self._history.append(snapshot)

            logger.info(f"[MemoryStore] Added history snapshot: {snapshot}")
        except Exception as exc:
            logger.error("[MemoryStore] add_history_snapshot failed: %s", exc)

    def _append_feed(self, item: LiveFeedItem) -> None:
        if item.details is None:
            item.details = {}
        else:
            item.details = dict(item.details)

        self._live_feed.append(item)
        logger.info("[MemoryStore] appended live feed item %s:  %s", item.event_type, item.message)

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
                "eventType": snapshot.event_type,
                "roundId": snapshot.round_id,
                "participantCount": snapshot.participant_count,
                "totalPotWei": snapshot.total_pot,
                "finishedAt": snapshot.finished_at,
                "winner": snapshot.winner,
                "winnerPrizeWei": snapshot.winner_prize,
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
            "timestamp": item.event_time,
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

    def clear_all_data(self) -> None:
        with self._lock:
            self._current_round = None
            self._participant_summaries = {}
            self._history.clear()
            self._live_feed.clear()
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
                logger.error("EventManager contract_config_loop error: %s", exc)
            
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
                logger.error("EventManager round refresh error: %s", exc)

            try:
                # Refresh participants if a round is active
                current = self.store.get_current_round()
                if current:
                    summaries = await self.client.get_participant_summaries(current.round_id)
                    self.store.sync_participants(summaries)
            except Exception as exc:  # pragma: no cover
                logger.error("EventManager participants refresh error: %s", exc)

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
                logger.error("EventManager events_loop get_events error: %s", exc)
                events = []

            if events:
                for evt in events:
                    logger.info("EventManager processing event %s", getattr(evt, 'name', None))
                    try:
                        await self._handle_event(evt)
                    except Exception as exc:
                        logger.error("EventManager failed to handle event %s: %s", getattr(evt, 'name', None), exc)
            else:
                # back off briefly when no events
                await asyncio.sleep(1.0)

            # small sleep to avoid tight loop
            self._from_block = self.client.get_last_seen_block() + 1
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
            "RoundStateChanged",
            "BetPlaced",
            "RoundCompleted",
            "RoundRefunded",
        }

        if name in live_feed_events:
            try:
                message = self._generate_event_message(name, args)
                logger.info("Adding live feed event: %s", message)
                # add_live_feed will normalise details and convert timestamps
                self.store.add_live_feed(
                    event_type=name,
                    message=message,
                    details=args
                )
            except Exception as exc:
                logger.error("Failed to add %s live feed: %s", name, exc)

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
                logger.error("Failed to append history snapshot for %s: %s", name, exc)

    def _generate_event_message(self, event_type: str, args: dict | None) -> str:
        """Generate a human-friendly message for live feed entries.

        Keep this function compact and defensive: it should not raise for
        unexpected argument shapes. Return a short text summary suitable for
        the live activity feed.
        """
        a = args or {}
        try:
            if event_type == "RoundCreated":
                rid = a.get("roundId") or a.get("round_id")
                return f"Round {rid} created" if rid is not None else "Round created"

            if event_type == "BetPlaced":
                player = a.get("player") or a.get("from") or a.get("address")
                player = shorten_eth_address(player)
                amount = a.get("amount") or a.get("value") or a.get("betAmount")
                amt_str = f" for {int(amount) / 1e18:.4f} ETH" if amount is not None and str(amount).isdigit() else (f" for {amount}" if amount is not None else "")
                who = player if player else "a player"
                return f"{who} placed a bet{amt_str}"

            if event_type == "RoundCompleted":
                rid = a.get("roundId") or a.get("round_id")
                winner = a.get("winner")
                winner = shorten_eth_address(winner) if winner else "unknown"
                return f"Round {rid} completed - winner: {winner}" if rid is not None else f"Round completed - winner: {winner}"

            if event_type == "RoundRefunded":
                rid = a.get("roundId") or a.get("round_id")
                reason = a.get("reason") or a.get("refundReason")
                if reason:
                    return f"Round {rid} refunded: {reason}"
                return f"Round {rid} refunded" if rid is not None else "Round refunded"

            if event_type == "RoundStateChanged":
                rid = a.get("roundId") or a.get("round_id")
                new_state = a.get("newState")
                new_state_name = RoundState(int(new_state))
                return f"Round {rid} state transitioned to {new_state_name.name}" if rid is not None else f"Round state transitioned to {new_state_name.name}"

            if event_type == "EndTimeExtended":
                rid = a.get("roundId") or a.get("round_id")
                new_end = a.get("newEndTime") or a.get("new_end_time")
                return f"Round {rid} end extended to {new_end}" if rid is not None else "Round end extended"

            # Fallback: present the event name and any obvious identifying field
            rid = a.get("roundId") or a.get("round_id")
            if rid is not None:
                return f"{event_type} for round {rid}"
            player = a.get("player") or a.get("address") or a.get("from")
            if player:
                return f"{event_type} by {player}"
            return event_type
        except Exception:
            # Defensive fallback so message generation never raises
            return event_type
