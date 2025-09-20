"""
Enhanced Demo Application for Lottery Enclave
Includes real-time monitoring and interactive features
"""

import sys
import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal
import random

sys.path.append('src')

from web_server import LotteryWebServer
from lottery.engine import LotteryEngine

# Configure beautiful logging
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, '\033[0m')
        record.levelname = f"{color}{record.levelname}\033[0m"
        return super().format(record)

# Setup logging
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

class DemoLotteryApp:
    def __init__(self):
        self.config = {
            'lottery': {
                'draw_interval_minutes': 10,
                'betting_cutoff_minutes': 1,
                'single_bet_amount': '0.01'
            },
            'server': {
                'host': '0.0.0.0',
                'port': 8080,
                'debug': True
            },
            'blockchain': {
                'enabled': False  # Demo mode
            }
        }
        self.lottery_engine = None
        self.web_server = None
        self.demo_users = []
        self.demo_running = False
        
    async def initialize(self):
        """Initialize the demo application"""
        logger.info("🎰 Initializing Lottery System...")
        
        # Create lottery engine
        self.lottery_engine = LotteryEngine(self.config)
        
        # Create initial draw
        draw = self.lottery_engine.create_new_draw()
        self.lottery_engine.current_draw = draw
        logger.info(f"✅ Created initial draw: {draw.draw_id}")
        
        # Create demo users
        self.create_demo_users()
        
        # Setup mock scheduler
        class DemoScheduler:
            def __init__(self, lottery_engine):
                self.lottery_engine = lottery_engine
                
            async def start(self):
                pass
                
            async def stop(self):
                pass
                
            async def get_current_draw(self):
                # Return the draw object for API usage
                return self.lottery_engine.current_draw
                
            async def get_draw_history(self, limit=10):
                return self.lottery_engine.get_draw_history(limit)

            async def get_recent_activities(self, limit=20):
                return self.lottery_engine.get_recent_activities(limit)
                
            async def place_bet(self, user_address, amount, transaction_hash):
                from decimal import Decimal
                return self.lottery_engine.place_bet(
                    user_address,
                    Decimal(str(amount)),
                    transaction_hash
                )

            async def log_activity(self, user_address, activity_type, details):
                self.lottery_engine.log_activity(user_address, activity_type, details)

        class MockBlockchainClient:
            async def verify_signature(self, address: str, signature: str) -> bool:
                return True

            async def verify_transaction(self, tx_hash: str, user_address: str, amount: float) -> bool:
                return True
        
        # Create web server
        demo_scheduler = DemoScheduler(self.lottery_engine)
        self.web_server = LotteryWebServer(self.config, demo_scheduler, MockBlockchainClient())
        
        logger.info("✅ System initialization complete")
        
    def create_demo_users(self):
        """Create demo users for testing"""
        user_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]
        
        for i, name in enumerate(user_names[:5]):
            address = f"0x{'1111' * 9}{i:02d}{'0' * 8}"
            self.demo_users.append({
                'name': name,
                'address': address,
                'balance': round(random.uniform(0.1, 2.0), 3)
            })
        
        logger.info(f"✅ Created {len(self.demo_users)} demo users")
        
    async def start_demo(self):
        """Start the demo application"""
        try:
            # Start web server in the background so we can continue the demo flow
            host = self.config.get('server', {}).get('host', '0.0.0.0')
            port = self.config.get('server', {}).get('port', 8080)
            asyncio.create_task(self.web_server.start(host=host, port=port))
            logger.info(f"🌐 Web server starting at: http://localhost:{port}")
            
            # Start demo scenarios
            self.demo_running = True
            await self.run_demo_scenarios()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received stop signal...")
        except Exception as e:
            logger.error(f"❌ Demo error: {e}")
        finally:
            await self.stop_demo()
    
    async def run_demo_scenarios(self):
        """Run various demo scenarios"""
        logger.info("🎬 Starting demo scenarios...")
        
        # Scenario 1: Show initial state
        await self.show_system_status()
        await asyncio.sleep(2)
        
        # Scenario 2: Simulate user betting
        await self.simulate_betting_phase()
        await asyncio.sleep(3)
        
        # Scenario 3: Show real-time updates
        await self.show_realtime_updates()
        await asyncio.sleep(2)
        
        # Scenario 4: Conduct draw
        await self.conduct_demo_draw()
        await asyncio.sleep(2)
        
        # Scenario 5: Show results
        await self.show_final_results()
        
        # Keep server running for interaction
        logger.info("🎮 Demo server continues running, you can interact via API...")
        logger.info("📡 API endpoints:")
        logger.info("   GET  http://localhost:8080/api/draw/current")
        logger.info("   GET  http://localhost:8080/api/draw/history")
        logger.info("   POST http://localhost:8080/api/bet")
        logger.info("   GET  http://localhost:8080/api/users/stats")
        logger.info("")
        logger.info("Press Ctrl+C to stop demo")
        
        # Keep running
        while self.demo_running:
            await asyncio.sleep(1)
    
    async def show_system_status(self):
        """Show current system status"""
        logger.info("📊 === System Status ===")
        
        draw_info = self.lottery_engine.get_current_draw_info()
        if draw_info:
            logger.info(f"🎲 Current draw: {draw_info['draw_id']}")
            logger.info(f"💰 Prize pool: {draw_info['total_pot']} ETH")
            logger.info(f"👥 Participants: {draw_info['participants']}")
            logger.info(f"⏰ Draw time: {draw_info['draw_time']}")
        
        logger.info("👤 Demo users:")
        for user in self.demo_users:
            logger.info(f"   {user['name']}: {user['address'][:10]}... (Balance: {user['balance']} ETH)")
    
    async def simulate_betting_phase(self):
        """Simulate users placing bets"""
        logger.info("🎯 === Simulated Betting Phase ===")
        
        for i, user in enumerate(self.demo_users):
            if random.random() > 0.3:  # 70% chance to bet
                # Random bet amount (multiple of 0.01)
                bet_count = random.randint(1, 3)
                
                for _ in range(bet_count):
                    bet_info = self.lottery_engine.place_bet(
                        user['address'],
                        self.lottery_engine.single_bet_amount,
                        f"0x{random.randint(10000, 99999):064x}"
                    )
                    
                    if bet_info['success']:
                        logger.info(f"💸 {user['name']} bet {self.lottery_engine.single_bet_amount} ETH")
                        user['balance'] -= float(self.lottery_engine.single_bet_amount)
                    
                    await asyncio.sleep(0.5)  # Simulate time between bets
    
    async def show_realtime_updates(self):
        """Show real-time system updates"""
        logger.info("📈 === Real-time Status Update ===")
        
        draw = self.lottery_engine.current_draw
        if draw:
            logger.info(f"🎰 Draw ID: {draw.draw_id}")
            logger.info(f"💰 Current pool: {draw.total_pot} ETH")
            logger.info(f"🎫 Total tickets: {draw.total_tickets}")
            
            logger.info("🎟️  Bet details:")
            # Aggregate tickets per user
            user_ticket_counts = {}
            for bet in draw.bets:
                user_ticket_counts[bet.user_address] = user_ticket_counts.get(bet.user_address, 0) + len(bet.ticket_numbers)

            for address, tickets in user_ticket_counts.items():
                user_name = next((u['name'] for u in self.demo_users if u['address'] == address), 'Unknown')
                logger.info(f"   {user_name}: {tickets} tickets")
    
    async def conduct_demo_draw(self):
        """Conduct the lottery draw"""
        logger.info("🎊 === Conducting Draw ===")
        
        draw = self.lottery_engine.current_draw
        if not draw or not draw.bets:
            logger.warning("⚠️  No participants, cannot draw")
            return
        
        logger.info("🎲 Selecting a winner...")
        # Close betting before conducting the draw
        self.lottery_engine.close_betting()
        await asyncio.sleep(2)  # Dramatic pause
        
        winner_info = self.lottery_engine.conduct_draw()
        
        if winner_info and winner_info.get('success'):
            winner_name = next((u['name'] for u in self.demo_users if u['address'] == winner_info['winner']), 'Unknown')
            logger.info(f"🏆 Congratulations winner: {winner_name}")
            logger.info(f"📍 Winner address: {winner_info['winner']}")
            logger.info(f"🎫 Winning number: {winner_info['winning_number']}")
            logger.info(f"💰 Prize amount: {winner_info['total_pot']} ETH")
    
    async def show_final_results(self):
        """Show final results and statistics"""
        logger.info("📊 === Final Results ===")
        
        # Show draw history
        history = self.lottery_engine.get_draw_history(5)
        logger.info(f"🏆 Draw history (last {len(history)}):")
        
        for draw in history:
            winner_name = next((u['name'] for u in self.demo_users if u['address'] == draw.get('winner')), 'Unknown')
            logger.info(f"   {draw['draw_id']}: {winner_name} won {draw['total_pot']} ETH")
        
        # Show user statistics
        logger.info("👥 User statistics:")
        for user in self.demo_users:
            stats = self.lottery_engine.get_user_stats(user['address'])
            logger.info(f"   {user['name']}: {stats['total_bets']} bets, {stats['wins']} wins, win rate {stats['win_rate']:.1f}%")
        
        # Show recent activities
        activities = self.lottery_engine.get_recent_activities(10)
        logger.info(f"📝 Recent activities ({len(activities)} items):")
        for activity in activities[-5:]:  # Show last 5
            desc = f"{activity.get('activity_type')}: {activity.get('details')}"
            logger.info(f"   {activity['timestamp'][:19]}: {desc}")
    
    async def stop_demo(self):
        """Stop the demo application"""
        logger.info("🛑 Stopping demo...")
        self.demo_running = False
        
        if self.web_server:
            await self.web_server.stop()
        
        logger.info("✅ Demo stopped")

async def main():
    """Main demo function"""
    demo_app = DemoLotteryApp()
    
    try:
        await demo_app.initialize()
        await demo_app.start_demo()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
