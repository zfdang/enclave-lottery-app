#!/usr/bin/env python3
"""
AWS Nitro Enclave Lottery Application
Main entry point for the enclave lottery system
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Load .env from project root (3 levels up from this file)
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip auto-loading
    pass

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from web_server import LotteryWebServer
from lottery.scheduler import LotteryScheduler
from blockchain.client import BlockchainClient
from utils.config import load_config
from utils.crypto import EnclaveAttestation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LotteryEnclaveApp:
    """Main lottery enclave application"""
    
    def __init__(self):
        self.config = load_config()
        self.web_server = None
        self.scheduler = None
        self.blockchain_client = None
        self.running = True
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing Lottery Enclave Application")
        
        # Initialize blockchain client
        self.blockchain_client = BlockchainClient(self.config)
        await self.blockchain_client.initialize()
        
        # Initialize lottery scheduler
        self.scheduler = LotteryScheduler(self.config, self.blockchain_client)
        
        # Initialize web server
        self.web_server = LotteryWebServer(
            self.config, 
            self.scheduler, 
            self.blockchain_client
        )
        
        logger.info("All components initialized successfully")
        
    async def start(self):
        """Start the lottery application"""
        try:
            await self.initialize()
            
            # Generate enclave attestation
            attestation = EnclaveAttestation()
            attestation_doc = attestation.generate_attestation()
            logger.info(f"Enclave attestation generated: {attestation_doc[:50]}...")
            
            # Start scheduler
            scheduler_task = asyncio.create_task(self.scheduler.start())
            
            # Start web server
            server_task = asyncio.create_task(
                self.web_server.start(
                    host=self.config.get('server', {}).get('host', '0.0.0.0'),
                    port=self.config.get('server', {}).get('port', 8080)
                )
            )
            
            logger.info("Lottery Enclave Application started successfully")
            
            # Wait for both tasks
            await asyncio.gather(scheduler_task, server_task)
            
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            raise
            
    async def stop(self):
        """Stop the lottery application"""
        logger.info("Stopping Lottery Enclave Application")
        self.running = False
        
        if self.web_server:
            await self.web_server.stop()
            
        if self.scheduler:
            await self.scheduler.stop()
            
        if self.blockchain_client:
            await self.blockchain_client.close()
            
        logger.info("Application stopped successfully")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(app.stop())


async def main():
    """Main entry point"""
    global app
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app = LotteryEnclaveApp()
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())