"""
Lottery Scheduler - Manages lottery timing and automatic draws
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .engine import LotteryEngine, DrawStatus

logger = logging.getLogger(__name__)


class LotteryScheduler:
    """Manages lottery scheduling and automatic draws"""
    
    def __init__(self, config, blockchain_client):
        self.config = config
        self.blockchain_client = blockchain_client
        self.lottery_engine = LotteryEngine(config)
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the lottery scheduler"""
        self.running = True
        logger.info("Starting lottery scheduler")
        
        # Create initial draw
        self.lottery_engine.current_draw = self.lottery_engine.create_new_draw()
        
        # Start scheduler loop
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        await self.scheduler_task
        
    async def stop(self):
        """Stop the lottery scheduler"""
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Lottery scheduler stopped")
        
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self._check_and_process_draws()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(30)  # Wait longer on error
                
    async def _check_and_process_draws(self):
        """Check and process draw state changes"""
        if not self.lottery_engine.current_draw:
            # Create new draw if none exists
            self.lottery_engine.current_draw = self.lottery_engine.create_new_draw()
            return
            
        now = datetime.utcnow()
        current_draw = self.lottery_engine.current_draw
        
        # Check if betting should be closed
        if (current_draw.status == DrawStatus.BETTING and 
            now >= current_draw.end_time):
            logger.info(f"Closing betting for draw {current_draw.draw_id}")
            self.lottery_engine.close_betting()
            
        # Check if draw should be conducted
        if (current_draw.status == DrawStatus.CLOSED and 
            now >= current_draw.draw_time):
            logger.info(f"Conducting draw {current_draw.draw_id}")
            await self._conduct_draw()
            
    async def _conduct_draw(self):
        """Conduct the lottery draw"""
        try:
            # Conduct draw using lottery engine
            result = self.lottery_engine.conduct_draw()
            
            if result["success"]:
                # Record result on blockchain
                await self._record_draw_on_blockchain(result)
                
                # Complete current draw and prepare for next
                self.lottery_engine.complete_draw()
                
                # Create next draw
                self.lottery_engine.current_draw = self.lottery_engine.create_new_draw()
                
                logger.info(f"Draw completed successfully: {result}")
            else:
                logger.error(f"Draw failed: {result}")
                
        except Exception as e:
            logger.error(f"Error conducting draw: {e}")
            
    async def _record_draw_on_blockchain(self, result):
        """Record draw result on blockchain"""
        try:
            if self.blockchain_client:
                await self.blockchain_client.record_lottery_result({
                    "draw_id": result["draw_id"],
                    "winner": result.get("winner"),
                    "winning_number": result.get("winning_number"),
                    "total_pot": result.get("total_pot"),
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.info(f"Draw result recorded on blockchain: {result['draw_id']}")
        except Exception as e:
            logger.error(f"Error recording draw on blockchain: {e}")
            
    async def get_current_draw(self):
        """Get current lottery draw"""
        return self.lottery_engine.current_draw
        
    async def place_bet(self, user_address: str, amount: float, transaction_hash: str) -> dict:
        """Place a bet in the current lottery"""
        from decimal import Decimal
        return self.lottery_engine.place_bet(
            user_address, 
            Decimal(str(amount)), 
            transaction_hash
        )
        
    async def get_draw_history(self, limit: int = 10):
        """Get lottery draw history"""
        return self.lottery_engine.get_draw_history(limit)
        
    async def get_recent_activities(self, limit: int = 20):
        """Get recent user activities"""
        return self.lottery_engine.get_recent_activities(limit)
        
    async def log_activity(self, user_address: str, activity_type: str, details: dict):
        """Log user activity"""
        self.lottery_engine.log_activity(user_address, activity_type, details)
        
    async def get_user_stats(self, user_address: str):
        """Get user statistics"""
        return self.lottery_engine.get_user_stats(user_address)
        
    def get_next_draw_time(self) -> Optional[datetime]:
        """Get the next draw time"""
        if self.lottery_engine.current_draw:
            return self.lottery_engine.current_draw.draw_time
        return None
        
    def get_betting_end_time(self) -> Optional[datetime]:
        """Get when betting ends for current draw"""
        if self.lottery_engine.current_draw:
            return self.lottery_engine.current_draw.end_time
        return None