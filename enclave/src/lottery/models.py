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

    event_type: str
    round_id: int
    participant_count: int
    total_pot: int
    finished_at: int
    winner: Optional[str]
    winner_prize: int
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