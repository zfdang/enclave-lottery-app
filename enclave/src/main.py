#!/usr/bin/env python3
"""
Passive Lottery Operator Application

Entry point for the enclave lottery backend running in passive mode.
Coordinates the blockchain client, passive operator, and FastAPI server.
"""

import asyncio
from utils.logger import get_logger
import signal
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

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
from blockchain.client import BlockchainClient
from lottery.event_manager import memory_store
from lottery.operator import PassiveOperator
from utils.config import load_config
from utils.crypto import EnclaveAttestation, TLSKeyPair
from lottery.event_manager import EventManager

logger = get_logger(__name__)


class PassiveLotteryOperatorApp:
    """Coordinator for the passive lottery backend services.

    Initializes the blockchain client, passive operator, and FastAPI server,
    manages lifecycle events, and emits basic diagnostic summaries.
    """

    def __init__(self) -> None:
        self.config = load_config()
        self.web_server: Optional[LotteryWebServer] = None
        self.operator: Optional[PassiveOperator] = None
        self.blockchain_client: Optional[BlockchainClient] = None
        self.tls_keypair: Optional[TLSKeyPair] = None
        self._operator_task: Optional[asyncio.Task[Any]] = None
        self._server_task: Optional[asyncio.Task[Any]] = None
        self.running = True
        self._stopping = False
        self._stopped = False

        self._setup_signal_handlers()
        logger.info("🎲 Passive Lottery Operator Application initialized")

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _display_config_summary(self) -> None:
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
        passive_cfg = operator_config.get('passive', {})
        logger.info(
            "🤖 Passive poll intervals: events=%ss, state=%ss, draw=%ss",
            passive_cfg.get('event_poll_interval', operator_config.get('event_poll_interval', 6.0)),
            passive_cfg.get('state_refresh_interval', operator_config.get('state_refresh_interval', 30.0)),
            passive_cfg.get('draw_check_interval', operator_config.get('draw_check_interval', 10.0)),
        )
        logger.info(
            "⏱️  Draw retry delay: %ss (max retries %s)",
            passive_cfg.get('draw_retry_delay', operator_config.get('draw_retry_delay', 45.0)),
            passive_cfg.get('max_draw_retries', operator_config.get('max_draw_retries', 3)),
        )

        server_config = self.config.get('server', {})
        logger.info(f"🌍 Server Host: {server_config.get('host', '0.0.0.0')}")
        logger.info(f"🔌 Server Port: {server_config.get('port', 6080)}")

        logger.info("=" * 60)

    async def initialize(self) -> None:
        """Initialize blockchain client, operator, and web server instances."""
        logger.info("🚀 Initializing Passive Lottery Operator Application")

        # Show configuration summary
        self._display_config_summary()

        # Generate TLS key pair for secure operator key injection
        logger.info("🔐 Generating TLS SECP384R1 key pair for secure key injection...")
        self.tls_keypair = TLSKeyPair()
        logger.info("✅ TLS key pair generated successfully")

        # Blockchain client
        logger.info("🔗 Initializing blockchain client...")
        self.blockchain_client = BlockchainClient(self.config)
        await self.blockchain_client.initialize()

        # Passive operator
        logger.info("🎯 Initializing passive operator service...")
        # Initialize EventManager which will keep the memory store up-to-date
        self.event_manager = EventManager(self.blockchain_client, self.config)
        await self.event_manager.initialize()

        self.operator = PassiveOperator(self.blockchain_client, self.config)
        await self.operator.initialize()

        # Web server
        logger.info("🌐 Initializing web server...")
        self.web_server = LotteryWebServer(
            self.config, 
            self.operator, 
            self.blockchain_client,
            self.tls_keypair
        )

        logger.info("🎉 Passive application initialization completed")

    async def start(self) -> None:
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
                except Exception as exc:  # pragma: no cover - hardware specific
                    logger.warning(f"⚠️  Failed to generate enclave attestation: {exc}")

            if not self.operator:
                raise RuntimeError("Passive operator failed to initialize")

            logger.info("🤖 Starting passive operator service...")
            # Start event manager first so the store is actively refreshed
            try:
                await self.event_manager.start()
            except Exception:
                logger.warning("EventManager failed to start; continuing")
            self._operator_task = asyncio.create_task(self.operator.start())

            if not self.web_server:
                raise RuntimeError("Web server failed to initialize")

            server_host = self.config.get('server', {}).get('host', '0.0.0.0')
            server_port = int(self.config.get('server', {}).get('port', 6080))

            logger.info(f"🌍 Starting web server on {server_host}:{server_port}...")
            try:
                self._server_task = asyncio.create_task(
                    self.web_server.start(host=server_host, port=server_port)
                )
                await asyncio.sleep(0.2)
                if self._server_task.done():
                    exc = self._server_task.exception()
                    if exc:
                        logger.error(f"Web server task failed during startup: {exc}")
                        raise exc
            except Exception as exc:
                logger.error(f"Web server failed to start: {exc}")
                raise

            self._display_startup_summary()

            while self.running:
                await asyncio.sleep(1)

            logger.info("🛑 Shutdown signal received, stopping application...")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop all services and cleanup resources."""
        if self._stopping or self._stopped:
            return

        self._stopping = True
        logger.info("🛑 Stopping Passive Lottery Operator Application")
        self.running = False

        # Stop operator
        if self.operator:
            try:
                await self.operator.stop()
                logger.info("✅ Passive operator service stopped")
            except Exception as exc:
                logger.error(f"❌ Error stopping passive operator: {exc}")
        if self._operator_task:
            try:
                await self._operator_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover - diagnostic
                logger.debug(f"Operator task exited with error: {exc}")
            self._operator_task = None

        # Stop web server
        if self.web_server:
            try:
                await self.web_server.stop()
                logger.info("✅ Web server stopped")
            except Exception as exc:
                logger.error(f"❌ Error stopping web server: {exc}")
        if self._server_task:
            if not self._server_task.done():
                self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover - diagnostic
                logger.debug(f"Web server task exited with error: {exc}")
            self._server_task = None

        # Close blockchain client
        if self.blockchain_client:
            try:
                await self.blockchain_client.close()
                logger.info("✅ Blockchain client connections closed")
            except Exception as exc:
                logger.error(f"❌ Error closing blockchain client: {exc}")

        # Stop event manager if running
        if hasattr(self, 'event_manager') and self.event_manager:
            try:
                await self.event_manager.stop()
                logger.info("✅ Event manager stopped")
            except Exception as exc:
                logger.error(f"❌ Error stopping event manager: {exc}")

        # Clear memory store
        try:
            if hasattr(memory_store, 'clear_all_data'):
                memory_store.clear_all_data()
            elif hasattr(memory_store, 'clear'):
                memory_store.clear()
            logger.info("✅ Memory store cleared")
        except Exception as exc:
            logger.error(f"❌ Error clearing memory store: {exc}")

        logger.info("🟢 Passive Lottery Operator Application stopped successfully")
        self._stopping = False
        self._stopped = True

    def _display_startup_summary(self) -> None:
        logger.info("=" * 60)
        logger.info("🔰 PASSIVE LOTTERY OPERATOR APPLICATION STARTED")
        logger.info("=" * 60)

        # Operator status
        try:
            status = self.operator.get_status() if self.operator else {}
            status_dict = status if isinstance(status, dict) else getattr(status, '__dict__', {})
            logger.info(f"🤖 Operator Status: {status_dict.get('status')}")
            current_round_id = status_dict.get('current_round_id') or 0
            if current_round_id:
                logger.info(f"🎲 Current Round: #{current_round_id}")
            else:
                logger.info("🎲 No active round detected yet")
            errors = status_dict.get('errors') or []
            if errors:
                logger.info(f"⚠️ Pending operator errors: {errors}")
        except Exception as exc:
            logger.warning(f"⚠️  Could not get operator status: {exc}")

        # Contract config
        try:
            if self.blockchain_client:
                logger.info(f"💰 Contract Address: {self.blockchain_client.contract_address}")
                operator_address = (
                    self.blockchain_client.account.address
                    if getattr(self.blockchain_client, 'account', None)
                    else 'N/A'
                )
                logger.info(f"📍 Operator Address: {operator_address}")
        except Exception as exc:
            logger.warning(f"⚠️  Could not get contract config: {exc}")

        # Memory store stats
        try:
            current_round = memory_store.get_current_round()
            history_len = len(memory_store.get_round_history())
            participant_len = len(memory_store.get_participants())
            feed_len = len(memory_store.get_live_feed())
            logger.info(
                "💾 Memory Store: current round=%s, history=%s entries, participants=%s, feed=%s",
                current_round.round_id if current_round else "none",
                history_len,
                participant_len,
                feed_len,
            )
        except Exception as exc:
            logger.warning(f"⚠️  Could not get memory store status: {exc}")

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

    def _handle_signal(self, signum, frame) -> None:  # pragma: no cover - signal handler
        logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
        self.running = False


async def main() -> None:
    """Main entry point for the passive lottery backend."""
    app = PassiveLotteryOperatorApp()

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("🛑 Passive application interrupted by user")
    except Exception as exc:
        logger.error(f"❌ Passive application failed: {exc}")
        logger.error(f"🔍 Error details: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())