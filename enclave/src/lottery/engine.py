"""
Lottery Engine - Automated operator for managing lottery rounds
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OperatorMode(Enum):
    """Operator operational modes"""
    MANUAL = "manual"           # Manual round management
    AUTOMATIC = "automatic"     # Automatic round management
    SCHEDULED = "scheduled"     # Schedule-based round management


@dataclass
class RoundInfo:
    """Information about a lottery round"""
    round_id: int
    start_time: int
    end_time: int
    draw_time: int
    total_pot: int
    participant_count: int
    winner: Optional[str]
    admin_commission: int
    winner_prize: int
    completed: bool
    cancelled: bool
    refunded: bool
    
    @property
    def start_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.start_time)
    
    @property
    def end_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.end_time)
    
    @property
    def draw_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.draw_time)


@dataclass
class Activity:
    """Represents system activity"""
    activity_id: str
    activity_type: str  # "round_created", "bet_placed", "round_completed", etc.
    details: Dict[str, Any]
    timestamp: datetime


class LotteryEngine:
    """Automated lottery operator engine"""
    
    def __init__(self, blockchain_client, config):
        self.blockchain_client = blockchain_client
        self.config = config
        
        # Current state
        self.current_round: Optional[RoundInfo] = None
        self.round_history: List[RoundInfo] = []
        self.activities: List[Activity] = []
        self.is_running = False
        
        # Operator configuration
        operator_config = config.get('operator', {})
        self.auto_start_rounds = operator_config.get('auto_start_rounds', True)
        self.round_check_interval = operator_config.get('round_check_interval', 30)  # seconds
        self.mode = OperatorMode(operator_config.get('mode', 'automatic'))
        
        # Get contract configuration
        self.contract_config = {}
        
        logger.info(f"Lottery engine initialized in {self.mode.value} mode")
    
    async def initialize(self):
        """Initialize the lottery engine"""
        try:
            # Get contract configuration
            self.contract_config = await self.blockchain_client.get_contract_config()
            
            if self.contract_config:
                logger.info("Contract configuration loaded:")
                logger.info(f"  Admin: {self.contract_config.get('admin')}")
                logger.info(f"  Operator: {self.contract_config.get('operator')}")
                logger.info(f"  Commission Rate: {self.contract_config.get('commission_rate', 0) / 100}%")
                logger.info(f"  Min Bet: {self.blockchain_client.wei_to_eth(self.contract_config.get('min_bet_amount', 0))} ETH")
                logger.info(f"  Betting Duration: {self.contract_config.get('betting_duration', 0)} seconds")
                logger.info(f"  Draw Delay: {self.contract_config.get('draw_delay', 0)} seconds")
            
            # Load current round state
            await self._load_current_round()
            
            logger.info("Lottery engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize lottery engine: {e}")
            raise
    
    async def start(self):
        """Start the automated operator"""
        if self.is_running:
            logger.warning("Lottery engine is already running")
            return
            
        self.is_running = True
        logger.info("Starting automated lottery operator...")
        
        if self.mode == OperatorMode.AUTOMATIC:
            # Start automatic round management
            asyncio.create_task(self._automatic_round_manager())
            
        # Start event monitoring
        asyncio.create_task(self._monitor_blockchain_events())
        
        logger.info("Lottery engine started")
    
    async def stop(self):
        """Stop the automated operator"""
        self.is_running = False
        logger.info("Lottery engine stopped")
    
    async def _load_current_round(self):
        """Load current round state from blockchain"""
        try:
            round_data = await self.blockchain_client.get_current_round()
            
            if round_data and round_data['round_id'] > 0:
                self.current_round = RoundInfo(**round_data)
                logger.info(f"Loaded current round: Round {self.current_round.round_id}")
                self._log_activity("round_loaded", {
                    "round_id": self.current_round.round_id,
                    "status": "active" if not self.current_round.completed else "completed"
                })
            else:
                logger.info("No active round found")
                
        except Exception as e:
            logger.error(f"Error loading current round: {e}")
    
    async def _automatic_round_manager(self):
        """Automatic round management loop"""
        logger.info("Starting automatic round management")
        
        while self.is_running:
            try:
                await self._check_and_manage_rounds()
                await asyncio.sleep(self.round_check_interval)
                
            except Exception as e:
                logger.error(f"Error in automatic round manager: {e}")
                await asyncio.sleep(self.round_check_interval)
    
    async def _check_and_manage_rounds(self):
        """Check and manage current round state"""
        try:
            # Refresh current round state
            await self._load_current_round()
            
            current_time = int(time.time())
            
            if not self.current_round:
                # No active round, start a new one if auto-start is enabled
                if self.auto_start_rounds:
                    logger.info("No active round found, starting new round...")
                    await self.start_new_round()
                return
            
            # Check if current round can be drawn
            if (not self.current_round.completed and 
                not self.current_round.cancelled and 
                current_time >= self.current_round.draw_time):
                
                # Check if round meets minimum requirements
                if self.current_round.participant_count >= self.contract_config.get('min_participants', 2):
                    logger.info(f"Drawing winner for round {self.current_round.round_id}")
                    await self.draw_current_round()
                else:
                    logger.warning(f"Round {self.current_round.round_id} doesn't have enough participants, cancelling...")
                    await self.cancel_current_round("Not enough participants")
            
            # Check if round is completed and we should start a new one
            if (self.current_round.completed or self.current_round.cancelled) and self.auto_start_rounds:
                logger.info("Current round completed, starting new round...")
                await self.start_new_round()
                
        except Exception as e:
            logger.error(f"Error checking and managing rounds: {e}")
    
    async def start_new_round(self) -> Dict[str, Any]:
        """Start a new lottery round"""
        try:
            if self.current_round and not self.current_round.completed and not self.current_round.cancelled:
                raise ValueError("Cannot start new round while another is active")
            
            # Start new round on blockchain
            result = await self.blockchain_client.start_new_round()
            
            # Update local state
            await self._load_current_round()
            
            self._log_activity("round_created", {
                "round_id": result['round_id'],
                "start_time": result['start_time'],
                "end_time": result['end_time'],
                "draw_time": result['draw_time'],
                "tx_hash": result['tx_hash']
            })
            
            logger.info(f"New round started: Round {result['round_id']}")
            return result
            
        except Exception as e:
            logger.error(f"Error starting new round: {e}")
            raise
    
    async def draw_current_round(self) -> Dict[str, Any]:
        """Draw winner for current round"""
        try:
            if not self.current_round:
                raise ValueError("No active round to draw")
            
            # Check if round can be drawn
            can_draw = await self.blockchain_client.can_draw_current_round()
            if not can_draw:
                raise ValueError("Current round cannot be drawn yet")
            
            # Draw winner on blockchain
            result = await self.blockchain_client.draw_winner(self.current_round.round_id)
            
            # Update local state
            await self._load_current_round()
            
            self._log_activity("round_completed", {
                "round_id": result['round_id'],
                "winner": result['winner'],
                "total_pot": self.blockchain_client.wei_to_eth(result['total_pot']),
                "winner_prize": self.blockchain_client.wei_to_eth(result['winner_prize']),
                "admin_commission": self.blockchain_client.wei_to_eth(result['admin_commission']),
                "tx_hash": result['tx_hash']
            })
            
            logger.info(f"Round {result['round_id']} completed. Winner: {result['winner']}")
            return result
            
        except Exception as e:
            logger.error(f"Error drawing current round: {e}")
            raise
    
    async def cancel_current_round(self, reason: str) -> Dict[str, Any]:
        """Cancel current round"""
        try:
            if not self.current_round:
                raise ValueError("No active round to cancel")
            
            # Cancel round on blockchain
            result = await self.blockchain_client.cancel_round(self.current_round.round_id, reason)
            
            # Update local state
            await self._load_current_round()
            
            self._log_activity("round_cancelled", {
                "round_id": result['round_id'],
                "reason": result['reason'],
                "total_refunded": self.blockchain_client.wei_to_eth(result['total_refunded']),
                "tx_hash": result['tx_hash']
            })
            
            logger.info(f"Round {result['round_id']} cancelled: {reason}")
            return result
            
        except Exception as e:
            logger.error(f"Error cancelling current round: {e}")
            raise
    
    async def _monitor_blockchain_events(self):
        """Monitor blockchain events"""
        logger.info("Starting blockchain event monitoring")
        
        async def event_callback(event_type: str, event_data: Dict[str, Any]):
            """Handle blockchain events"""
            try:
                if event_type == 'RoundCreated':
                    self._log_activity("bet_window_opened", {
                        "round_id": event_data['roundId'],
                        "betting_end_time": event_data['endTime']
                    })
                    
                elif event_type == 'BetPlaced':
                    self._log_activity("bet_placed", {
                        "round_id": event_data['roundId'],
                        "player": event_data['player'],
                        "amount": self.blockchain_client.wei_to_eth(event_data['amount']),
                        "new_total": self.blockchain_client.wei_to_eth(event_data['newTotal'])
                    })
                    
                elif event_type == 'RoundCompleted':
                    self._log_activity("winner_selected", {
                        "round_id": event_data['roundId'],
                        "winner": event_data['winner'],
                        "prize": self.blockchain_client.wei_to_eth(event_data['winnerPrize'])
                    })
                    
            except Exception as e:
                logger.error(f"Error handling event {event_type}: {e}")
        
        # Start event monitoring (this will run indefinitely)
        await self.blockchain_client.listen_for_events(event_callback)
    
    def _log_activity(self, activity_type: str, details: Dict[str, Any]):
        """Log activity for tracking"""
        activity = Activity(
            activity_id=f"{activity_type}_{int(time.time() * 1000)}",
            activity_type=activity_type,
            details=details,
            timestamp=datetime.utcnow()
        )
        
        self.activities.append(activity)
        
        # Keep only last 1000 activities
        if len(self.activities) > 1000:
            self.activities = self.activities[-1000:]
    
    # =============== STATUS AND INFORMATION METHODS ===============
    
    def get_current_round_info(self) -> Optional[Dict[str, Any]]:
        """Get current round information"""
        if not self.current_round:
            return None
            
        return {
            "round_id": self.current_round.round_id,
            "start_time": self.current_round.start_time,
            "end_time": self.current_round.end_time,
            "draw_time": self.current_round.draw_time,
            "total_pot": self.blockchain_client.wei_to_eth(self.current_round.total_pot),
            "participant_count": self.current_round.participant_count,
            "winner": self.current_round.winner,
            "completed": self.current_round.completed,
            "cancelled": self.current_round.cancelled,
            "time_until_end": max(0, self.current_round.end_time - int(time.time())),
            "time_until_draw": max(0, self.current_round.draw_time - int(time.time())),
            "can_bet": (not self.current_round.completed and 
                       not self.current_round.cancelled and 
                       int(time.time()) < self.current_round.end_time)
        }
    
    def get_recent_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent activities"""
        recent = self.activities[-limit:] if len(self.activities) > limit else self.activities
        return [
            {
                "activity_id": activity.activity_id,
                "type": activity.activity_type,
                "details": activity.details,
                "timestamp": activity.timestamp.isoformat()
            }
            for activity in reversed(recent)
        ]
    
    def get_operator_status(self) -> Dict[str, Any]:
        """Get operator status information"""
        return {
            "is_running": self.is_running,
            "mode": self.mode.value,
            "auto_start_rounds": self.auto_start_rounds,
            "round_check_interval": self.round_check_interval,
            "current_round": self.get_current_round_info(),
            "operator_address": self.blockchain_client.account.address,
            "contract_address": self.blockchain_client.contract_address,
            "contract_config": self.contract_config
        }
    
    async def get_round_participants(self, round_id: int = None) -> List[str]:
        """Get participants for a round"""
        if round_id is None and self.current_round:
            round_id = self.current_round.round_id
            
        if round_id is None:
            return []
            
        return await self.blockchain_client.get_round_participants(round_id)
    
    async def get_player_bet_amount(self, player_address: str, round_id: int = None) -> float:
        """Get player's bet amount for a round"""
        if round_id is None and self.current_round:
            round_id = self.current_round.round_id
            
        if round_id is None:
            return 0.0
            
        bet_wei = await self.blockchain_client.get_player_bet(round_id, player_address)
        return self.blockchain_client.wei_to_eth(bet_wei)
            
        # Create bet
        bet_id = f"bet_{user_address}_{int(datetime.utcnow().timestamp())}"
        bet = Bet(
            bet_id=bet_id,
            draw_id=self.current_draw.draw_id,
            user_address=user_address,
            amount=amount,
            ticket_numbers=ticket_numbers,
            timestamp=datetime.utcnow(),
            transaction_hash=transaction_hash
        )
        
        # Add bet to current draw
        self.current_draw.bets.append(bet)
        self.current_draw.total_pot += amount
        self.current_draw.total_tickets += num_tickets
        
        # Log activity
        self.log_activity(user_address, "bet", {
            "amount": str(amount),
            "tickets": ticket_numbers,
            "draw_id": self.current_draw.draw_id
        })
        
        logger.info(f"Bet placed: {user_address} - {amount} ETH - tickets {ticket_numbers}")
        
        return {
            "success": True,
            "bet_id": bet_id,
            "ticket_numbers": ticket_numbers,
            "total_pot": str(self.current_draw.total_pot)
        }
        
    def close_betting(self):
        """Close betting for current draw"""
        if self.current_draw and self.current_draw.status == DrawStatus.BETTING:
            self.current_draw.status = DrawStatus.CLOSED
            logger.info(f"Betting closed for draw {self.current_draw.draw_id}")
            
    def conduct_draw(self) -> Dict:
        """Conduct the lottery draw and select winner"""
        if not self.current_draw:
            return {"success": False, "error": "No active draw"}
            
        if self.current_draw.status != DrawStatus.CLOSED:
            return {"success": False, "error": "Draw is not ready"}
            
        if not self.current_draw.bets:
            # No bets placed, cancel draw
            self.current_draw.status = DrawStatus.COMPLETED
            logger.info(f"Draw {self.current_draw.draw_id} completed with no participants")
            return {"success": True, "winner": None, "reason": "No participants"}
            
        # Generate cryptographically secure random number
        max_ticket = self.current_draw.total_tickets
        winning_number = secrets.randbelow(max_ticket) + 1
        
        # Find winner
        winner_address = None
        current_ticket = 0
        
        for bet in self.current_draw.bets:
            current_ticket += len(bet.ticket_numbers)
            if winning_number <= current_ticket:
                winner_address = bet.user_address
                break
                
        # Update draw status
        self.current_draw.status = DrawStatus.DRAWN
        self.current_draw.winner_address = winner_address
        self.current_draw.winning_number = winning_number
        
        # Log winner activity
        if winner_address:
            self.log_activity(winner_address, "win", {
                "amount": str(self.current_draw.total_pot),
                "winning_number": winning_number,
                "draw_id": self.current_draw.draw_id
            })
            
        logger.info(f"Draw completed: {self.current_draw.draw_id}, winner: {winner_address}, "
                   f"winning number: {winning_number}, pot: {self.current_draw.total_pot}")
        
        return {
            "success": True,
            "winner": winner_address,
            "winning_number": winning_number,
            "total_pot": str(self.current_draw.total_pot),
            "draw_id": self.current_draw.draw_id
        }
        
    def complete_draw(self):
        """Complete the current draw and move to history"""
        if self.current_draw:
            self.current_draw.status = DrawStatus.COMPLETED
            self.draw_history.append(self.current_draw)
            logger.info(f"Draw {self.current_draw.draw_id} moved to history")
            self.current_draw = None
            
    def complete_draw_and_start_next(self):
        """
        Complete current draw cycle and automatically start next one.
        
        This implements the 6-step lottery cycle:
        1. ✓ Draw was started (already active)
        2. ✓ Countdown shown, people bet, info displayed (handled by frontend)
        3. ✓ Betting closed when time reached (handled by scheduler)
        4. ✓ Draw conducted, winner determined (already completed)
        5. Save to history and blockchain (this method)
        6. Clear state and start new draw (this method)
        """
        if not self.current_draw:
            logger.warning("No current draw to complete")
            return None
            
        # Save completed draw info before clearing
        completed_draw_info = {
            "draw_id": self.current_draw.draw_id,
            "draw_time": self.current_draw.draw_time.isoformat(),
            "total_pot": str(self.current_draw.total_pot),
            "winner": self.current_draw.winner_address,
            "winning_number": self.current_draw.winning_number,
            "participants": len(self.current_draw.bets),
            "total_tickets": self.current_draw.total_tickets,
            "status": self.current_draw.status.value
        }
        
        # Step 5: Save to history (blockchain recording handled by scheduler)
        self.complete_draw()
        
        # Step 6: Clear state and start new draw automatically
        logger.info("Starting new lottery draw cycle")
        self.current_draw = self.create_new_draw()
        
        logger.info(f"Completed draw cycle. New draw started: {self.current_draw.draw_id}")
        
        return {
            "completed_draw": completed_draw_info,
            "new_draw": self.get_current_draw_info()
        }
            
    def get_current_draw_info(self) -> Optional[Dict]:
        """Get current draw information"""
        if not self.current_draw:
            return None
            
        now = datetime.utcnow()
        return {
            "draw_id": self.current_draw.draw_id,
            "status": self.current_draw.status.value,
            "start_time": self.current_draw.start_time.isoformat(),
            "end_time": self.current_draw.end_time.isoformat(),
            "draw_time": self.current_draw.draw_time.isoformat(),
            "total_pot": str(self.current_draw.total_pot),
            "participants": len(self.current_draw.bets),
            "total_tickets": self.current_draw.total_tickets,
            "time_remaining": max(0, (self.current_draw.draw_time - now).total_seconds()),
            "betting_time_remaining": max(0, (self.current_draw.end_time - now).total_seconds()),
            "minimum_interval_minutes": int(self.minimum_interval_minutes),
            "draw_interval_minutes": int(self.draw_interval_minutes),
        }
        
    def get_draw_history(self, limit: int = 10) -> List[Dict]:
        """Get lottery draw history"""
        history = []
        for draw in self.draw_history[-limit:]:
            history.append({
                "draw_id": draw.draw_id,
                "draw_time": draw.draw_time.isoformat(),
                "total_pot": str(draw.total_pot),
                "winner": draw.winner_address,
                "winning_number": draw.winning_number,
                "participants": len(draw.bets)
            })
        return list(reversed(history))  # Most recent first
        
    def log_activity(self, user_address: str, activity_type: str, details: Dict):
        """Log user activity"""
        activity_id = f"activity_{int(datetime.utcnow().timestamp())}_{len(self.activities)}"
        activity = Activity(
            activity_id=activity_id,
            user_address=user_address,
            activity_type=activity_type,
            details=details,
            timestamp=datetime.utcnow()
        )
        self.activities.append(activity)
        
        # Keep only recent activities (last 100)
        if len(self.activities) > 100:
            self.activities = self.activities[-100:]
            
    def get_recent_activities(self, limit: int = 20) -> List[Dict]:
        """Get recent user activities"""
        activities = []
        for activity in self.activities[-limit:]:
            activities.append({
                "activity_id": activity.activity_id,
                "user_address": activity.user_address,
                "activity_type": activity.activity_type,
                "details": activity.details,
                "timestamp": activity.timestamp.isoformat()
            })
        return list(reversed(activities))  # Most recent first
        
    def get_user_stats(self, user_address: str) -> Dict:
        """Get statistics for a specific user"""
        total_bets = 0
        total_amount = Decimal('0')
        wins = 0
        
        # Check draw history
        for draw in self.draw_history:
            for bet in draw.bets:
                if bet.user_address == user_address:
                    total_bets += 1
                    total_amount += bet.amount
                    
            if draw.winner_address == user_address:
                wins += 1
                
        # Check current draw
        if self.current_draw:
            for bet in self.current_draw.bets:
                if bet.user_address == user_address:
                    total_bets += 1
                    total_amount += bet.amount
                    
        return {
            "total_bets": total_bets,
            "total_amount": str(total_amount),
            "wins": wins,
            "win_rate": wins / max(1, total_bets) * 100
        }