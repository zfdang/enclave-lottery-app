"""
Memory-Based Event Management System

This module provides in-memory storage and management of lottery events and rounds.
All data is stored in memory and will be lost on application restart, as per requirements.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from threading import Lock
from collections import defaultdict

from lottery.models import (
    LotteryRound, 
    ContractEvent, 
    PlayerBet, 
    RoundState,
    OperatorStatus
)

logger = logging.getLogger(__name__)


class MemoryEventStore:
    """
    In-memory storage for all lottery events and data.
    
    This class manages all lottery-related data in memory:
    - Contract events history
    - Round information and history
    - Player bets and statistics
    - Operator status and actions
    
    Note: All data is volatile and will be lost on application restart.
    """
    
    def __init__(self):
        self._lock = Lock()
        
        # Event storage
        self._events: List[ContractEvent] = []
        self._events_by_name: Dict[str, List[ContractEvent]] = defaultdict(list)
        
        # Round storage  
        self._rounds: Dict[int, LotteryRound] = {}
        self._current_round_id: Optional[int] = None
        
        # Player bet storage
        self._player_bets: Dict[str, List[PlayerBet]] = defaultdict(list)
        self._round_bets: Dict[int, List[PlayerBet]] = defaultdict(list)
        
        # Operator status
        self._operator_status = OperatorStatus()
        
        # Event listeners
        self._event_listeners: Dict[str, List[Callable]] = defaultdict(list)
        
        logger.info("Memory event store initialized")
    
    # Event Management
    def add_event(self, event: ContractEvent) -> None:
        """
        Add a new contract event to memory storage.
        
        Args:
            event: ContractEvent to store
        """
        with self._lock:
            self._events.append(event)
            self._events_by_name[event.event_name].append(event)
            
            logger.debug(f"Added event: {event.event_name} at block {event.block_number}")
            
            # Notify listeners
            self._notify_listeners(event.event_name, event)
    
    def get_events(self, event_name: Optional[str] = None, limit: Optional[int] = None) -> List[ContractEvent]:
        """
        Retrieve events from memory storage.
        
        Args:
            event_name: Filter by specific event name (optional)
            limit: Maximum number of events to return (optional)
            
        Returns:
            List of ContractEvent objects
        """
        with self._lock:
            if event_name:
                events = self._events_by_name.get(event_name, [])
            else:
                events = self._events.copy()
            
            # Sort by block number (newest first)
            events.sort(key=lambda e: e.block_number, reverse=True)
            
            if limit:
                events = events[:limit]
                
            return events
    
    def get_recent_events(self, minutes: int = 60) -> List[ContractEvent]:
        """
        Get events from the last N minutes.
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            List of recent ContractEvent objects
        """
        cutoff_time = datetime.now().timestamp() - (minutes * 60)
        
        with self._lock:
            recent_events = [
                event for event in self._events
                if event.timestamp.timestamp() > cutoff_time
            ]
            
            return sorted(recent_events, key=lambda e: e.block_number, reverse=True)
    
    # Round Management
    def set_current_round(self, round_data: LotteryRound) -> None:
        """
        Set the current active round.
        
        Args:
            round_data: LotteryRound object representing current round
        """
        with self._lock:
            self._rounds[round_data.round_id] = round_data
            self._current_round_id = round_data.round_id
            
            logger.info(f"Set current round: #{round_data.round_id} (state: {round_data.state.name})")
    
    def get_current_round(self) -> Optional[LotteryRound]:
        """
        Get the current active round.
        
        Returns:
            Current LotteryRound or None if no active round
        """
        with self._lock:
            if self._current_round_id is not None:
                return self._rounds.get(self._current_round_id)
            return None
    
    def get_round(self, round_id: int) -> Optional[LotteryRound]:
        """
        Get a specific round by ID.
        
        Args:
            round_id: Round identifier
            
        Returns:
            LotteryRound or None if not found
        """
        with self._lock:
            return self._rounds.get(round_id)
    
    def get_round_history(self, limit: Optional[int] = None) -> List[LotteryRound]:
        """
        Get historical rounds.
        
        Args:
            limit: Maximum number of rounds to return (optional)
            
        Returns:
            List of LotteryRound objects sorted by round_id descending
        """
        with self._lock:
            rounds = list(self._rounds.values())
            rounds.sort(key=lambda r: r.round_id, reverse=True)
            
            if limit:
                rounds = rounds[:limit]
                
            return rounds
    
    def update_round_state(self, round_id: int, new_state: RoundState) -> bool:
        """
        Update the state of a specific round.
        
        Args:
            round_id: Round identifier
            new_state: New RoundState
            
        Returns:
            True if updated successfully, False if round not found
        """
        with self._lock:
            if round_id in self._rounds:
                old_state = self._rounds[round_id].state
                self._rounds[round_id].state = new_state
                
                logger.info(f"Round #{round_id} state changed: {old_state.name} → {new_state.name}")
                return True
            
            logger.warning(f"Attempted to update non-existent round #{round_id}")
            return False
    
    # Player Bet Management
    def add_player_bet(self, bet: PlayerBet) -> None:
        """
        Add a player bet to memory storage.
        
        Args:
            bet: PlayerBet object to store
        """
        with self._lock:
            self._player_bets[bet.player_address].append(bet)
            self._round_bets[bet.round_id].append(bet)
            
            logger.debug(f"Added bet: {bet.amount} wei from {bet.player_address} for round #{bet.round_id}")
    
    def get_player_bets(self, player_address: str, round_id: Optional[int] = None) -> List[PlayerBet]:
        """
        Get all bets for a specific player.
        
        Args:
            player_address: Player's wallet address
            round_id: Filter by specific round (optional)
            
        Returns:
            List of PlayerBet objects
        """
        with self._lock:
            player_bets = self._player_bets.get(player_address, [])
            
            if round_id is not None:
                player_bets = [bet for bet in player_bets if bet.round_id == round_id]
            
            return player_bets.copy()
    
    def get_round_bets(self, round_id: int) -> List[PlayerBet]:
        """
        Get all bets for a specific round.
        
        Args:
            round_id: Round identifier
            
        Returns:
            List of PlayerBet objects
        """
        with self._lock:
            return self._round_bets.get(round_id, []).copy()
    
    def get_player_statistics(self, player_address: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a player.
        
        Args:
            player_address: Player's wallet address
            
        Returns:
            Dictionary containing player statistics
        """
        with self._lock:
            player_bets = self._player_bets.get(player_address, [])
            
            if not player_bets:
                return {
                    'total_bets': 0,
                    'total_amount': 0,
                    'rounds_participated': 0,
                    'average_bet': 0,
                    'first_bet_time': None,
                    'last_bet_time': None
                }
            
            total_amount = sum(bet.amount for bet in player_bets)
            unique_rounds = set(bet.round_id for bet in player_bets)
            bet_times = [bet.timestamp for bet in player_bets]
            
            return {
                'total_bets': len(player_bets),
                'total_amount': total_amount,
                'rounds_participated': len(unique_rounds),
                'average_bet': total_amount // len(player_bets) if player_bets else 0,
                'first_bet_time': min(bet_times),
                'last_bet_time': max(bet_times)
            }
    
    # Operator Status Management
    def update_operator_status(self, **kwargs) -> None:
        """
        Update operator status fields.
        
        Args:
            **kwargs: Fields to update on OperatorStatus
        """
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._operator_status, key):
                    setattr(self._operator_status, key, value)
                else:
                    logger.warning(f"Unknown operator status field: {key}")
            
            # Always update last action time
            self._operator_status.last_action_time = datetime.now()
    
    def get_operator_status(self) -> OperatorStatus:
        """
        Get current operator status.
        
        Returns:
            Copy of current OperatorStatus
        """
        with self._lock:
            # Return a copy to prevent external modification
            status = OperatorStatus(
                is_running=self._operator_status.is_running,
                current_round_id=self._operator_status.current_round_id,
                auto_create_rounds=self._operator_status.auto_create_rounds,
                last_action_time=self._operator_status.last_action_time,
                pending_actions=self._operator_status.pending_actions.copy(),
                error_count=self._operator_status.error_count,
                total_rounds_managed=self._operator_status.total_rounds_managed
            )
            return status
    
    def add_pending_action(self, action: str) -> None:
        """
        Add a pending action for the operator.
        
        Args:
            action: Description of the pending action
        """
        with self._lock:
            if action not in self._operator_status.pending_actions:
                self._operator_status.pending_actions.append(action)
                logger.debug(f"Added pending action: {action}")
    
    def remove_pending_action(self, action: str) -> None:
        """
        Remove a completed action from pending list.
        
        Args:
            action: Description of the completed action
        """
        with self._lock:
            if action in self._operator_status.pending_actions:
                self._operator_status.pending_actions.remove(action)
                logger.debug(f"Completed action: {action}")
    
    # Event Listeners
    def add_event_listener(self, event_name: str, callback: Callable[[ContractEvent], None]) -> None:
        """
        Add a listener for specific contract events.
        
        Args:
            event_name: Name of event to listen for
            callback: Function to call when event occurs
        """
        with self._lock:
            self._event_listeners[event_name].append(callback)
            logger.debug(f"Added listener for {event_name} events")
    
    def _notify_listeners(self, event_name: str, event: ContractEvent) -> None:
        """
        Notify all listeners of a new event (internal use).
        
        Args:
            event_name: Name of the event
            event: ContractEvent that occurred
        """
        listeners = self._event_listeners.get(event_name, [])
        for callback in listeners:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event listener error for {event_name}: {e}")
    
    # Statistics and Reporting
    def get_system_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive system statistics.
        
        Returns:
            Dictionary containing system-wide statistics
        """
        with self._lock:
            current_round = self.get_current_round()
            
            stats = {
                'total_events': len(self._events),
                'total_rounds': len(self._rounds),
                'total_players': len(self._player_bets),
                'total_bets': sum(len(bets) for bets in self._player_bets.values()),
                'operator_status': self.get_operator_status().__dict__,
                'current_round': current_round.__dict__ if current_round else None,
                'event_types': list(self._events_by_name.keys()),
                'recent_activity': len(self.get_recent_events(60))  # Last hour
            }
            
            # Calculate total volume
            total_volume = 0
            for round_bets in self._round_bets.values():
                total_volume += sum(bet.amount for bet in round_bets)
            stats['total_volume_wei'] = total_volume
            
            return stats

    # Compatibility properties for diagnostics
    @property
    def events(self) -> List[ContractEvent]:
        with self._lock:
            return list(self._events)

    @property
    def rounds(self) -> Dict[int, LotteryRound]:
        with self._lock:
            return dict(self._rounds)

    @property
    def bets(self) -> Dict[int, List[PlayerBet]]:
        with self._lock:
            return dict(self._round_bets)
    
    def clear_all_data(self) -> None:
        """
        Clear all stored data (for testing or reset).
        
        Warning: This will permanently delete all in-memory data!
        """
        with self._lock:
            self._events.clear()
            self._events_by_name.clear()
            self._rounds.clear()
            self._player_bets.clear()
            self._round_bets.clear()
            self._current_round_id = None
            self._operator_status = OperatorStatus()
            self._event_listeners.clear()
            
            logger.warning("All memory data cleared!")


# Global instance for application-wide use
memory_store = MemoryEventStore()