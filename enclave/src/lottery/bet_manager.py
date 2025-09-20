"""
Bet Manager - Handles bet validation and management
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from .engine import Bet, LotteryDraw

logger = logging.getLogger(__name__)


class BetManager:
    """Manages betting operations and validation"""
    
    def __init__(self, config):
        self.config = config
        self.min_bet_amount = Decimal(str(config.get('lottery', {}).get('single_bet_amount', '0.01')))
        self.max_bets_per_user = config.get('lottery', {}).get('max_bets_per_user', 100)
        
    def validate_bet_amount(self, amount: Decimal) -> tuple[bool, str]:
        """Validate bet amount"""
        if amount <= 0:
            return False, "Bet amount must be positive"
            
        if amount % self.min_bet_amount != 0:
            return False, f"Bet amount must be multiple of {self.min_bet_amount} ETH"
            
        return True, "Valid"
        
    def validate_user_betting_limit(self, user_address: str, current_draw: LotteryDraw) -> tuple[bool, str]:
        """Check if user has exceeded betting limits"""
        user_bets = [bet for bet in current_draw.bets if bet.user_address == user_address]
        
        if len(user_bets) >= self.max_bets_per_user:
            return False, f"Maximum {self.max_bets_per_user} bets per user allowed"
            
        return True, "OK"
        
    def calculate_ticket_numbers(self, amount: Decimal, start_number: int) -> List[int]:
        """Calculate ticket numbers for a bet"""
        num_tickets = int(amount / self.min_bet_amount)
        return list(range(start_number, start_number + num_tickets))
        
    def get_user_bets(self, user_address: str, current_draw: LotteryDraw) -> List[Bet]:
        """Get all bets for a user in current draw"""
        return [bet for bet in current_draw.bets if bet.user_address == user_address]
        
    def get_user_total_amount(self, user_address: str, current_draw: LotteryDraw) -> Decimal:
        """Get total amount bet by user in current draw"""
        user_bets = self.get_user_bets(user_address, current_draw)
        return sum(bet.amount for bet in user_bets)
        
    def get_user_total_tickets(self, user_address: str, current_draw: LotteryDraw) -> int:
        """Get total number of tickets for user in current draw"""
        user_bets = self.get_user_bets(user_address, current_draw)
        return sum(len(bet.ticket_numbers) for bet in user_bets)
        
    def format_bet_summary(self, bet: Bet) -> Dict:
        """Format bet information for API response"""
        return {
            "bet_id": bet.bet_id,
            "draw_id": bet.draw_id,
            "user_address": bet.user_address,
            "amount": str(bet.amount),
            "ticket_numbers": bet.ticket_numbers,
            "timestamp": bet.timestamp.isoformat(),
            "transaction_hash": bet.transaction_hash
        }