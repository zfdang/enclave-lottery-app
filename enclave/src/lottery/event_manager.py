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
            history_payload = self._serialize_history()

        self._emit("history_update", history_payload)
        self._emit("participants_update", self._serialize_participants())
        self._emit("live_feed", payload_feed)
        logger.debug(f"[MemoryStore] record_round_completion: snapshot={snapshot}")

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
                "betCount": summary.bet_count,
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


# Global singleton used across the backend.
memory_store = MemoryStore()