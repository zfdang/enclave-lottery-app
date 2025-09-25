"""
Lottery System Data Models

This module defines the core data structures for the automated lottery system,
matching the Solidity contract structure exactly.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Dict, Any
from datetime import datetime


class RoundState(IntEnum):
    """
    Lottery round states matching the Solidity contract enum.
    These values must match exactly with the contract's RoundState enum.
    """
    WAITING = 0      # Round created, waiting to start betting
    BETTING = 1      # Betting is active
    DRAWING = 2      # Betting ended, preparing for draw
    COMPLETED = 3    # Round completed with winner
    REFUNDED = 4     # Round refunded to participants


@dataclass
class LotteryRound:
    """
    Lottery round data structure matching the Solidity LotteryRound struct.
    
    This mirrors the contract's struct exactly:
    - round_id: Unique identifier for the round
    - state: Current state of the round
    - total_pot: Total amount bet in wei
    - commission_amount: Commission taken in wei  
    - participants: List of participant addresses
    - winner: Winner address (if completed)
    - created_at: Block timestamp when round was created
    - betting_start_time: When betting started
    - betting_end_time: When betting ends
    - draw_time: When draw will occur
    - winner_ticket: Winning ticket number (if completed)
    - random_seed: Random seed used for drawing (if completed)
    """
    round_id: int
    state: RoundState
    total_pot: int = 0
    commission_amount: int = 0
    participants: List[str] = field(default_factory=list)
    winner: Optional[str] = None
    created_at: int = 0
    betting_start_time: int = 0
    betting_end_time: int = 0
    draw_time: int = 0
    winner_ticket: int = 0
    random_seed: int = 0
    
    def __post_init__(self):
        """Ensure participants is a list"""
        if self.participants is None:
            self.participants = []
    
    @property
    def participant_count(self) -> int:
        """Get number of participants"""
        return len(self.participants)
    
    @property
    def is_active(self) -> bool:
        """Check if round is in an active state"""
        return self.state in [RoundState.WAITING, RoundState.BETTING, RoundState.DRAWING]
    
    @property
    def can_bet(self) -> bool:
        """Check if betting is currently allowed"""
        return self.state == RoundState.BETTING
    
    @property
    def can_draw(self) -> bool:
        """Check if round can be drawn"""
        return self.state == RoundState.DRAWING
    
    @property
    def is_finished(self) -> bool:
        """Check if round is finished (completed or refunded)"""
        return self.state in [RoundState.COMPLETED, RoundState.REFUNDED]


@dataclass 
class ContractConfig:
    """
    Contract configuration data matching the getConfig() return values.
    
    This represents the immutable and mutable configuration from the contract:
    - min_bet_amount: Minimum bet amount in wei
    - publisher_commission_rate: Publisher commission rate in basis points
    - sparsity_commission_rate: Sparsity commission rate in basis points
    - betting_duration: Duration of betting period in seconds
    - min_draw_delay: Minimum allowed draw delay
    - max_draw_delay: Maximum allowed draw delay
    - min_end_time_extension: Minimum extension when adding time
    - sparsity_address: Address of the sparsity provider
    - publisher_address: Address of the publisher
    - operator_address: Address of the operator
    - min_participants: Minimum participants required to draw a winner
    """
    min_bet_amount: int
    publisher_commission_rate: int
    sparsity_commission_rate: int
    betting_duration: int
    min_draw_delay: int
    max_draw_delay: int
    min_end_time_extension: int
    sparsity_address: str
    publisher_address: str
    operator_address: str
    min_participants: int


@dataclass
class ContractEvent:
    """
    Generic contract event structure for memory storage.
    
    Stores all relevant event data for processing and history:
    - event_name: Name of the contract event
    - block_number: Block number when event occurred
    - transaction_hash: Transaction hash
    - timestamp: Event timestamp  
    - args: Event arguments as dictionary
    """
    event_name: str
    block_number: int
    transaction_hash: str
    timestamp: datetime
    args: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure args is a dictionary"""
        if self.args is None:
            self.args = {}


@dataclass
class PlayerBet:
    """
    Individual player bet information.
    
    Represents a single bet placed by a player:
    - player_address: Address of the betting player
    - round_id: Round in which bet was placed
    - amount: Bet amount in wei
    - ticket_numbers: List of ticket numbers for this bet
    - timestamp: When bet was placed
    """
    player_address: str
    round_id: int
    amount: int
    ticket_numbers: List[int] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Ensure ticket_numbers is a list"""
        if self.ticket_numbers is None:
            self.ticket_numbers = []


@dataclass
class OperatorStatus:
    """
    Current status of the automated operator.
    
    Provides comprehensive status information for monitoring:
    - is_running: Whether operator is actively running
    - current_round_id: ID of current active round (if any)
    - auto_create_rounds: Whether operator auto-creates new rounds
    - last_action_time: Timestamp of last operator action
    - pending_actions: List of pending actions to perform
    - error_count: Number of recent errors
    - total_rounds_managed: Total rounds managed by this operator
    """
    is_running: bool = False
    current_round_id: Optional[int] = None
    auto_create_rounds: bool = True
    last_action_time: Optional[datetime] = None
    pending_actions: List[str] = field(default_factory=list)
    error_count: int = 0
    total_rounds_managed: int = 0
    
    def __post_init__(self):
        """Ensure pending_actions is a list"""
        if self.pending_actions is None:
            self.pending_actions = []