"""
Lottery Engine - Core lottery logic and game state management
"""

import asyncio
import logging
import math
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DrawStatus(Enum):
    """Lottery draw status"""
    BETTING = "betting"
    CLOSED = "closed"
    DRAWN = "drawn"
    COMPLETED = "completed"


@dataclass
class Bet:
    """Represents a single bet in the lottery"""
    bet_id: str
    draw_id: str
    user_address: str
    amount: Decimal
    ticket_numbers: List[int]
    timestamp: datetime
    transaction_hash: str


@dataclass
class LotteryDraw:
    """Represents a lottery draw"""
    draw_id: str
    start_time: datetime
    end_time: datetime
    draw_time: datetime
    status: DrawStatus = DrawStatus.BETTING
    bets: List[Bet] = field(default_factory=list)
    total_pot: Decimal = Decimal('0')
    winner_address: Optional[str] = None
    winning_number: Optional[int] = None
    total_tickets: int = 0


@dataclass
class Activity:
    """Represents user activity"""
    activity_id: str
    user_address: str
    activity_type: str  # "join", "bet", "win"
    details: Dict
    timestamp: datetime


class LotteryEngine:
    """Core lottery game engine"""
    
    def __init__(self, config):
        self.config = config
        self.current_draw: Optional[LotteryDraw] = None
        self.draw_history: List[LotteryDraw] = []
        self.activities: List[Activity] = []
        self.next_ticket_number = 1
        
        # Configuration (minutes-based only)
        lot_cfg = config.get('lottery', {})
        # Use minutes exclusively with a sensible default
        self.draw_interval_minutes = lot_cfg.get('draw_interval_minutes', 10)
        self.minimum_interval_minutes = lot_cfg.get('minimum_interval_minutes', 3)
        self.betting_cutoff_minutes = lot_cfg.get('betting_cutoff_minutes', 1)
        self.single_bet_amount = Decimal(str(config.get('lottery', {}).get('single_bet_amount', '0.01')))
        
    def create_new_draw(self) -> LotteryDraw:
        """Create a new lottery draw"""
        now = datetime.utcnow()
        draw_id = f"draw_{int(now.timestamp())}"
        
        # Calculate draw times
        # Rules:
        # 1) Minimum duration: total duration must be at least minimum_interval_minutes
        # 2) Maximum duration: total duration should be shorter than draw_interval_minutes * 2
        # 3) Slot alignment: draw_time minutes must be divisible by draw_interval_minutes (wall-clock slots), seconds=0
        start_time = now
        # Earliest acceptable time based on rule (1)
        earliest = start_time + timedelta(minutes=self.minimum_interval_minutes)

        # Align to next slot boundary at or after 'earliest'
        dt = earliest.replace(second=0, microsecond=0)
        delta = math.ceil(dt.minute * 1.0 / self.draw_interval_minutes) * self.draw_interval_minutes - dt.minute
        dt += timedelta(minutes=delta)
        
        draw_time = dt

        # Betting cutoff remains relative to draw_time
        end_time = draw_time - timedelta(minutes=self.betting_cutoff_minutes)
        
        draw = LotteryDraw(
            draw_id=draw_id,
            start_time=start_time,
            end_time=end_time,
            draw_time=draw_time,
            status=DrawStatus.BETTING
        )
        logger.info(f"Created new draw: {draw_id}, betting ends at {end_time}, draw at {draw_time}")
        return draw
        
    def can_place_bet(self) -> tuple[bool, str]:
        """Check if betting is currently allowed"""
        if not self.current_draw:
            return False, "No active draw"
            
        now = datetime.utcnow()
        
        if self.current_draw.status != DrawStatus.BETTING:
            return False, "Betting is closed for this draw"
            
        if now >= self.current_draw.end_time:
            return False, "Betting period has ended"
            
        return True, "OK"
        
    def place_bet(self, user_address: str, amount: Decimal, transaction_hash: str) -> Dict:
        """Place a bet in the current draw"""
        can_bet, reason = self.can_place_bet()
        if not can_bet:
            return {"success": False, "error": reason}
            
        # Validate bet amount (must be multiple of single bet amount)
        if amount % self.single_bet_amount != 0:
            return {"success": False, "error": f"Bet amount must be multiple of {self.single_bet_amount} ETH"}
            
        # Calculate number of tickets
        num_tickets = int(amount / self.single_bet_amount)
        if num_tickets <= 0:
            return {"success": False, "error": "Invalid bet amount"}
            
        # Generate ticket numbers
        ticket_numbers = []
        for _ in range(num_tickets):
            ticket_numbers.append(self.next_ticket_number)
            self.next_ticket_number += 1
            
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