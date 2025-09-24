#!/usr/bin/env python3
"""
Automated Lottery Operator Application
Main entry point for the enclave-based lottery operator system
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
from lottery.engine import LotteryEngine
from blockchain.client import BlockchainClient
from utils.config import load_config
from utils.crypto import EnclaveAttestation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LotteryOperatorApp:
    """Automated lottery operator application"""
    
    def __init__(self):
        self.config = load_config()
        self.web_server = None
        self.lottery_engine = None
        self.blockchain_client = None
        self.running = True
        
        # Setup graceful shutdown
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("🎲 Initializing Lottery Operator Application")
        
        # Check if we have operator configuration
        if not self.config.get('blockchain', {}).get('contract_address'):
            logger.info("📍 Contract address not configured")
            logger.info(" We need to get this address from registry node later")
        else:
            logger.info(f"📍 Using contract address: {self.config['blockchain']['contract_address']}")
        
        # Initialize blockchain client with operator role
        try:
            logger.info("🔗 Initializing blockchain client...")
            self.blockchain_client = BlockchainClient(self.config)
            await self.blockchain_client.initialize()
            
            # Verify operator role
            if self.blockchain_client.role != 'operator':
                logger.warning(f"⚠️  Expected operator role, but got: {self.blockchain_client.role}")
                
            logger.info(f"✅ Blockchain client initialized as {self.blockchain_client.role}")
            logger.info(f"📍 Operator address: {self.blockchain_client.account.address}")
            logger.info(f"📄 Contract address: {self.blockchain_client.contract_address}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize blockchain client: {e}")
            raise
        
        # Initialize lottery engine (automated operator)
        try:
            logger.info("🎯 Initializing lottery engine...")
            self.lottery_engine = LotteryEngine(self.blockchain_client, self.config)
            await self.lottery_engine.initialize()
            logger.info("✅ Lottery engine initialized in operator mode")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize lottery engine: {e}")
            raise
        
        # Initialize web server for player interface and status monitoring
        try:
            logger.info("🌐 Initializing web server...")
            self.web_server = LotteryWebServer(
                self.config, 
                self.lottery_engine, 
                self.blockchain_client
            )
            logger.info("✅ Web server initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize web server: {e}")
            raise
        
        logger.info("🎉 Application initialization completed")
        
    async def start(self):
        """Start the lottery operator application"""
        try:
            await self.initialize()
            
            # Generate enclave attestation if enabled
            if self.config.get('enclave', {}).get('attestation_enabled', False):
                try:
                    logger.info("🔐 Generating enclave attestation...")
                    attestation = EnclaveAttestation()
                    attestation_doc = attestation.generate_attestation()
                    logger.info(f"✅ Enclave attestation generated: {attestation_doc[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to generate enclave attestation: {e}")
            else:
                logger.info("ℹ️  Enclave attestation disabled")
            
            tasks = []
            
            # Start lottery engine (automated operator)
            if self.lottery_engine:
                logger.info("🚀 Starting automated lottery operator...")
                engine_task = asyncio.create_task(self.lottery_engine.start())
                tasks.append(engine_task)
                logger.info("✅ Lottery operator started")
            else:
                raise RuntimeError("Lottery engine is required but failed to initialize")
            
            # Start web server for player interface
            if self.web_server:
                server_host = self.config.get('server', {}).get('host', '0.0.0.0')
                server_port = int(self.config.get('server', {}).get('port', 6080))
                
                logger.info(f"🌍 Starting web server on {server_host}:{server_port}...")
                server_task = asyncio.create_task(
                    self.web_server.start(host=server_host, port=server_port)
                )
                tasks.append(server_task)
                logger.info(f"✅ Web server started at http://{server_host}:{server_port}")
            else:
                raise RuntimeError("Web server is required but failed to initialize")
            
            # Display startup summary
            self._display_startup_summary()
            
            # Wait for shutdown signal
            while self.running:
                await asyncio.sleep(1)
            
            logger.info("🛑 Shutdown signal received, stopping application...")
            
        except Exception as e:
            logger.error(f"❌ Error starting application: {e}")
            raise
        finally:
            await self.stop()
            
    async def stop(self):
        """Stop the lottery operator application"""
        logger.info("🛑 Stopping Lottery Operator Application")
        self.running = False
        
        # Stop lottery engine
        if self.lottery_engine:
            try:
                await self.lottery_engine.stop()
                logger.info("✅ Lottery engine stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping lottery engine: {e}")
        
        # Stop web server
        if self.web_server:
            try:
                await self.web_server.stop()
                logger.info("✅ Web server stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping web server: {e}")
        
        logger.info("🎲 Lottery Operator Application stopped successfully")
    
    def _display_startup_summary(self):
        """Display startup summary"""
        logger.info("=" * 60)
        logger.info("🎲 LOTTERY OPERATOR APPLICATION STARTED")
        logger.info("=" * 60)
        
        # Get operator status
        if self.lottery_engine:
            status = self.lottery_engine.get_operator_status()
            current_round = status.get('current_round')
            
            logger.info(f"🎯 Operator Mode: {status.get('mode', 'unknown')}")
            logger.info(f"🔄 Auto Start Rounds: {status.get('auto_start_rounds', False)}")
            logger.info(f"📍 Operator Address: {status.get('operator_address', 'unknown')}")
            logger.info(f"📄 Contract Address: {status.get('contract_address', 'unknown')}")
            
            if current_round:
                logger.info(f"🎲 Current Round: #{current_round['round_id']}")
                logger.info(f"💰 Total Pot: {current_round['total_pot']} ETH")
                logger.info(f"👥 Participants: {current_round['participant_count']}")
                
                if current_round['can_bet']:
                    logger.info(f"⏰ Betting ends in: {current_round['time_until_end']} seconds")
                elif current_round['completed']:
                    logger.info(f"🏆 Round completed. Winner: {current_round.get('winner', 'N/A')}")
                else:
                    logger.info(f"⏱️  Draw in: {current_round['time_until_draw']} seconds")
            else:
                logger.info("🎲 No active round - will start automatically")
        
        # Get contract configuration
        if self.blockchain_client and hasattr(self.blockchain_client, 'contract_config'):
            config = self.blockchain_client.contract_config
            if config:
                logger.info("📋 Contract Configuration:")
                logger.info(f"   💵 Min Bet: {self.blockchain_client.wei_to_eth(config.get('min_bet_amount', 0))} ETH")
                logger.info(f"   💰 Commission: {config.get('commission_rate', 0) / 100}%")
                logger.info(f"   ⏱️  Betting Duration: {config.get('betting_duration', 0)} seconds")
                logger.info(f"   ⏰ Draw Delay: {config.get('draw_delay', 0)} seconds")
        
        logger.info("=" * 60)
        logger.info("🌍 Web Interface: Player betting and operator status available")
        logger.info("🔄 Automated Operation: Rounds will be managed automatically")
        logger.info("🛑 To stop: Send SIGINT (Ctrl+C) or SIGTERM")
        logger.info("=" * 60)


async def main():
    """Main entry point"""
    app = LotteryOperatorApp()
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("🛑 Application interrupted by user")
    except Exception as e:
        logger.error(f"❌ Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

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
        
        # Initialize blockchain client with error handling
        try:
            self.blockchain_client = BlockchainClient(self.config)
            await self.blockchain_client.initialize()
            logger.info("Blockchain client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize blockchain client: {e}")
            logger.info("Application will continue without blockchain functionality")
            self.blockchain_client = None
        
        # Initialize lottery scheduler (may work in offline mode)
        try:
            self.scheduler = LotteryScheduler(self.config, self.blockchain_client)
            logger.info("Lottery scheduler initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize lottery scheduler: {e}")
            self.scheduler = None
        
        # Initialize web server (should work even without blockchain)
        try:
            self.web_server = LotteryWebServer(
                self.config, 
                self.scheduler, 
                self.blockchain_client
            )
            logger.info("Web server initialized")
        except Exception as e:
            logger.error(f"Failed to initialize web server: {e}")
            raise  # Web server is critical, so we still raise this error
        
        logger.info("Application initialization completed")
        
    async def start(self):
        """Start the lottery application"""
        try:
            await self.initialize()
            
            # Generate enclave attestation
            try:
                attestation = EnclaveAttestation()
                attestation_doc = attestation.generate_attestation()
                logger.info(f"Enclave attestation generated: {attestation_doc[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to generate enclave attestation: {e}")
            
            tasks = []
            
            # Start scheduler if available
            if self.scheduler:
                scheduler_task = asyncio.create_task(self.scheduler.start())
                tasks.append(scheduler_task)
                logger.info("Lottery scheduler started")
            else:
                logger.warning("Scheduler not available, running in limited mode")
            
            # Start web server (required)
            if self.web_server:
                server_task = asyncio.create_task(
                    self.web_server.start(
                        host=self.config.get('server', {}).get('host', '0.0.0.0'),
                        port=self.config.get('server', {}).get('port', 6080)
                    )
                )
                tasks.append(server_task)
                logger.info("Web server started")
            else:
                raise RuntimeError("Web server is required but failed to initialize")
            
            logger.info("Lottery Enclave Application started successfully")
            
            # Wait for all available tasks
            if tasks:
                await asyncio.gather(*tasks)
            else:
                logger.error("No tasks to run, application will exit")
            
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