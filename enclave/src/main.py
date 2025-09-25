#!/usr/bin/env python3
"""
Enhanced Automated Lottery Operator Application

Main entry point for the fully automated single-round lottery operator system.
Uses memory-based event storage and automated round management.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

#!/usr/bin/env python3
"""
Enhanced Automated Lottery Operator Application

Main entry point for the fully automated single-round lottery operator system.
Uses memory-based event storage and automated round management.
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

# Ensure package imports work when running this file directly
sys.path.insert(0, str(Path(__file__).parent))

from web_server import LotteryWebServer
from lottery.operator import AutomatedOperator
from lottery.event_manager import memory_store
from blockchain.client import BlockchainClient
from utils.config import load_config
from utils.crypto import EnclaveAttestation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedLotteryOperatorApp:
    """Enhanced automated lottery operator application.

    Responsible for initializing and orchestrating the blockchain client,
    automated operator, and the FastAPI web server. Handles graceful shutdown
    and provides a lightweight startup summary for diagnostics.
    """

    def __init__(self):
        self.config = load_config()
        self.web_server = None
        self.automated_operator = None
        self.blockchain_client = None
        self.running = True

        # Register basic signal handlers
        self._setup_signal_handlers()

        logger.info("🎲 Enhanced Lottery Operator Application initialized")

    def _setup_signal_handlers(self):
        def _handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def _display_config_summary(self):
        """Display key configuration options for diagnostics."""
        logger.info("=" * 60)
        logger.info("📋 CONFIGURATION SUMMARY")
        logger.info("=" * 60)

        blockchain_config = self.config.get('blockchain', {})
        logger.info(f"🔗 RPC URL: {blockchain_config.get('rpc_url', 'Not configured')}")
        logger.info(f"🆔 Chain ID: {blockchain_config.get('chain_id', 'Not configured')}")
        logger.info(f"📄 Contract: {blockchain_config.get('contract_address', 'Not configured')}")
        logger.info(f"👤 Operator: {blockchain_config.get('operator_address', 'Auto-generated')}")

        operator_config = self.config.get('operator', {})
        logger.info(f"🤖 Auto Create Rounds: {operator_config.get('auto_create_rounds', True)}")
        logger.info(f"⏱️  Check Interval: {operator_config.get('check_interval', 30)}s")

        server_config = self.config.get('server', {})
        logger.info(f"🌍 Server Host: {server_config.get('host', '0.0.0.0')}")
        logger.info(f"🔌 Server Port: {server_config.get('port', 6080)}")

        logger.info("=" * 60)

    async def initialize(self):
        """Initialize blockchain client, operator, and web server instances."""
        logger.info("🚀 Initializing Enhanced Lottery Operator Application")

        # Show configuration summary
        self._display_config_summary()

        # Blockchain client
        logger.info("🔗 Initializing blockchain client...")
        self.blockchain_client = BlockchainClient(self.config)
        await self.blockchain_client.initialize()

        # Automated operator
        logger.info("🎯 Initializing automated operator service...")
        self.automated_operator = AutomatedOperator(self.blockchain_client, self.config)
        await self.automated_operator.initialize()

        # Web server
        logger.info("🌐 Initializing enhanced web server...")
        self.web_server = LotteryWebServer(self.config, self.automated_operator, self.blockchain_client)

        logger.info("🎉 Enhanced application initialization completed")

    async def start(self):
        """Start services and run until a shutdown signal is received."""
        try:
            await self.initialize()

            # Optional attestation
            if self.config.get('enclave', {}).get('attestation_enabled', False):
                try:
                    logger.info("🔐 Generating enclave attestation...")
                    att = EnclaveAttestation()
                    _ = att.generate_attestation()
                    logger.info("✅ Enclave attestation generated")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to generate enclave attestation: {e}")

            # Start operator
            if not self.automated_operator:
                raise RuntimeError("Automated operator failed to initialize")

            logger.info("🤖 Starting automated operator service...")
            operator_task = asyncio.create_task(self.automated_operator.start())

            # Start web server
            if not self.web_server:
                raise RuntimeError("Web server failed to initialize")

            server_host = self.config.get('server', {}).get('host', '0.0.0.0')
            server_port = int(self.config.get('server', {}).get('port', 6080))

            logger.info(f"🌍 Starting enhanced web server on {server_host}:{server_port}...")
            try:
                server_task = asyncio.create_task(self.web_server.start(host=server_host, port=server_port))
                # Give the server a moment to attempt bind; if it fails synchronously the task will be done
                await asyncio.sleep(0.2)
                if server_task.done():
                    exc = server_task.exception()
                    if exc:
                        logger.error(f"Web server task failed during startup: {exc}")
                        await self.stop()
                        raise exc
            except Exception as e:
                logger.error(f"Web server failed to start: {e}")
                await self.stop()
                raise

            # Display summary
            self._display_startup_summary()

            # Run until signal
            while self.running:
                await asyncio.sleep(1)

            logger.info("🛑 Shutdown signal received, stopping application...")

        except Exception:
            # Ensure stop is always attempted on any startup error
            await self.stop()
            raise

        finally:
            await self.stop()

    async def stop(self):
        """Stop all services and cleanup resources."""
        if not self.running:
            # Allow multiple calls safely
            pass

        logger.info("🛑 Stopping Enhanced Lottery Operator Application")
        self.running = False

        # Stop operator
        if getattr(self, 'automated_operator', None):
            try:
                await self.automated_operator.stop()
                logger.info("✅ Automated operator service stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping automated operator: {e}")

        # Stop web server
        if getattr(self, 'web_server', None):
            try:
                await self.web_server.stop()
                logger.info("✅ Enhanced web server stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping web server: {e}")

        # Close blockchain client
        if getattr(self, 'blockchain_client', None):
            try:
                await self.blockchain_client.close()
                logger.info("✅ Blockchain client connections closed")
            except Exception as e:
                logger.error(f"❌ Error closing blockchain client: {e}")

        # Clear memory store
        try:
            if hasattr(memory_store, 'clear_all_data'):
                memory_store.clear_all_data()
            elif hasattr(memory_store, 'clear'):
                memory_store.clear()
            logger.info("✅ Memory store cleared")
        except Exception as e:
            logger.error(f"❌ Error clearing memory store: {e}")

        logger.info("🟢 Enhanced Lottery Operator Application stopped successfully")

    def _display_startup_summary(self):
        logger.info("=" * 60)
        logger.info("🔰 ENHANCED LOTTERY OPERATOR APPLICATION STARTED")
        logger.info("=" * 60)

        # Operator status
        try:
            status = self.automated_operator.get_status() if self.automated_operator else {}
            logger.info(f"🤖 Operator Status: {status.get('status')}")
            logger.info(f"🔄 Auto Create Rounds: {status.get('auto_create_enabled')}")
            logger.info(f"📍 Operator Address: {status.get('operator_address')}")
            current_round_id = status.get('current_round_id') or 0
            if current_round_id > 0:
                logger.info(f"🎲 Current Round: #{current_round_id}")
            else:
                logger.info("🎲 No active round - will create automatically")
        except Exception as e:
            logger.warning(f"⚠️  Could not get operator status: {e}")

        # Contract config
        try:
            if self.blockchain_client:
                logger.info(f"💰 Contract Address: {self.blockchain_client.contract_address}")
                logger.info(f"📍 Operator Address: {self.blockchain_client.account.address if self.blockchain_client.account else 'N/A'}")
        except Exception as e:
            logger.warning(f"⚠️  Could not get contract config: {e}")

        # Memory store stats
        try:
            event_count = len(memory_store.events)
            round_count = len(memory_store.rounds)
            bet_count = len(memory_store.bets)
            logger.info(f"💾 Memory Store: {event_count} events, {round_count} rounds, {bet_count} bets")
        except Exception as e:
            logger.warning(f"⚠️  Could not get memory store status: {e}")

        server_config = self.config.get('server', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 6080)

        logger.info("=" * 60)
        logger.info("🌐 SERVER ACCESS")
        logger.info("=" * 60)
        logger.info(f"🏠 Main Interface: http://{host}:{port}")
        logger.info(f"📡 WebSocket API: ws://{host}:{port}/ws/lottery")
        logger.info(f"🔧 API Endpoints: http://{host}:{port}/api/")
        logger.info("=" * 60)

    def _handle_signal(self, signum, frame):
        logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
        self.running = False


async def main():
    """Main entry point for Enhanced Lottery Operator Application"""
    app = EnhancedLotteryOperatorApp()

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, app._handle_signal)
    signal.signal(signal.SIGTERM, app._handle_signal)

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("🛑 Enhanced application interrupted by user")
    except Exception as e:
        logger.error(f"❌ Enhanced application failed: {e}")
        import traceback
        logger.error(f"🔍 Error details: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())