"""Core data models for the passive lottery backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Dict, Optional


class RoundState(IntEnum):
    """Lottery round states as defined in the current Solidity contract."""

    WAITING = 0
    BETTING = 1
    DRAWING = 2
    COMPLETED = 3
    REFUNDED = 4


@dataclass
class LotteryRound:
    """Snapshot of the on-chain `LotteryRound` struct."""

    round_id: int
    start_time: int
    end_time: int
    min_draw_time: int
    max_draw_time: int
    total_pot: int
    participant_count: int
    winner: Optional[str]
    publisher_commission: int
    sparsity_commission: int
    winner_prize: int
    state: RoundState


@dataclass
class ContractConfig:
    """Normalized result of `Lottery.getConfig()`."""

    publisher_addr: str
    sparsity_addr: str
    operator_addr: str
    publisher_commission: int
    sparsity_commission: int
    min_bet: int
    betting_duration: int
    min_draw_delay: int
    max_draw_delay: int
    min_end_time_extension: int
    min_participants: int


@dataclass
class ParticipantSummary:
    """Aggregated statistics for a participant in the active round."""

    address: str
    total_amount: int = 0
    

@dataclass
class RoundSnapshot:
    """Historical record of a completed or refunded round."""

    round_id: int
    start_time: int
    end_time: int
    min_draw_time: int
    max_draw_time: int
    total_pot: int
    participant_count: int
    winner: Optional[str]
    winner_prize: int
    publisher_commission: int
    sparsity_commission: int
    state: RoundState
    finished_at: int
    refund_reason: Optional[str] = None


@dataclass
class LiveFeedItem:
    """Entry pushed to the frontend activity feed."""

    event_type: str
    message: str
    details: Dict[str, int | str]
    event_time: timestamp
    
    def get_item_id(self) -> str:
        round_id = self.details.get("roundId", 0)
        timestamp = self.event_time
        event_type = self.event_type
        return f"{round_id}-{timestamp}-{event_type}"


@dataclass
class OperatorStatus:
    """Operational metrics for the passive operator loop."""

    is_running: bool = False
    current_round_id: Optional[int] = None
    last_event_time: Optional[datetime] = None
    last_draw_attempt: Optional[datetime] = None
    consecutive_draw_failures: int = 0
    max_draw_retries: int = 3
    scheduled_draw_round_id: Optional[int] = None
    scheduled_draw_due_at: Optional[int] = None
    watchdog_last_check: Optional[datetime] = None

    def record_event(self) -> None:
        self.last_event_time = datetime.utcnow()

    def record_draw_attempt(self) -> None:
        self.last_draw_attempt = datetime.utcnow()

    def reset_draw_failures(self) -> None:
        self.consecutive_draw_failures = 0

    def increment_draw_failures(self) -> None:
        self.consecutive_draw_failures += 1