"""
Standalone configuration for testing without blockchain
"""

import sys
import os
sys.path.append('src')

from web_server import LotteryWebServer
from lottery.engine import LotteryEngine
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Test configuration
    config = {
        'lottery': {
            'draw_interval_minutes': 10,
            'betting_cutoff_minutes': 1,
            'single_bet_amount': '0.01'
        },
        'server': {
            'host': '0.0.0.0',
            'port': 5000,
            'debug': True
        },
        'blockchain': {
            'enabled': False  # Disable blockchain for standalone mode
        }
    }
    
    logger.info("Starting lottery engine...")
    lottery_engine = LotteryEngine(config)
    
    # Create initial draw
    draw = lottery_engine.create_new_draw()
    lottery_engine.current_draw = draw
    logger.info(f"Created initial draw: {draw.draw_id}")
    
    # Add some test bets
    test_addresses = [
        '0x1111111111111111111111111111111111111111',
        '0x2222222222222222222222222222222222222222',
        '0x3333333333333333333333333333333333333333'
    ]
    
    for i, addr in enumerate(test_addresses):
        bet_info = lottery_engine.place_bet(
            addr, 
            lottery_engine.single_bet_amount, 
            f'0x{i:064x}'
        )
        logger.info(f"Placed test bet for {addr[:8]}...: {bet_info}")
    
    logger.info("Starting web server...")
    try:
        # Create a mock scheduler for standalone mode
        class MockScheduler:
            def __init__(self, lottery_engine):
                self.lottery_engine = lottery_engine
            
            async def start(self):
                pass
            
            async def stop(self):
                pass
                
            async def get_current_draw(self):
                return self.lottery_engine.get_current_draw_info()
                
            async def get_draw_history(self, limit=10):
                return self.lottery_engine.get_draw_history(limit)
        
        mock_scheduler = MockScheduler(lottery_engine)
        web_server = LotteryWebServer(config, mock_scheduler, None)  # No blockchain client
        
        # Start server
        await web_server.start()
        
        logger.info("🎉 Lottery application is running!")
        logger.info("Open http://localhost:5000 in your browser")
        logger.info("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await web_server.stop()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
