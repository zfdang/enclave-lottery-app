"""
Automated Lottery Operator Service

This module implements a fully automated operator that monitors the lottery contract
and automatically manages the complete round lifecycle without human intervention.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from lottery.models import LotteryRound, RoundState, ContractConfig, ContractEvent, PlayerBet
from lottery.event_manager import memory_store
from blockchain.client import BlockchainClient

logger = logging.getLogger(__name__)


class AutomatedOperator:
    """
    Fully automated lottery operator service.
    
    This service monitors the lottery contract and automatically:
    - Creates new rounds when no active round exists
    - Monitors round states and transitions
    - Executes draws when conditions are met
    - Handles refunds when necessary
    - Processes all contract events
    
    The operator runs completely autonomously without human intervention.
    """
    
    def __init__(self, blockchain_client: BlockchainClient, config: Dict[str, Any]):
        self.blockchain_client = blockchain_client
        self.config = config
        self.is_running = False
        self._stop_event = asyncio.Event()
        
        # Configuration
        self.auto_create_rounds = config.get('operator', {}).get('auto_create_rounds', True)
        self.round_check_interval = config.get('operator', {}).get('check_interval', 30)  # seconds
        self.max_errors_before_pause = config.get('operator', {}).get('max_errors', 5)
        
        # State tracking
        self.contract_config: Optional[ContractConfig] = None
        self.last_error_time: Optional[datetime] = None
        self.consecutive_errors = 0
        
        logger.info("Automated operator initialized")
    
    async def initialize(self) -> None:
        """
        Initialize the automated operator.
        
        Sets up event listeners, loads contract configuration,
        and prepares for autonomous operation.
        """
        logger.info("Initializing automated operator...")
        
        # Load contract configuration
        try:
            await self._load_contract_config()
            logger.info("Contract configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load contract configuration: {e}")
            raise
        
        # Setup event listeners
        self._setup_event_listeners()
        
        # Initialize operator status
        memory_store.update_operator_status(
            is_running=False,
            auto_create_rounds=self.auto_create_rounds,
            error_count=0,
            total_rounds_managed=0
        )
        
        logger.info("Automated operator initialized successfully")
    
    async def start(self) -> None:
        """
        Start the automated operator.
        
        Begins autonomous operation including:
        - Contract event monitoring
        - Round lifecycle management
        - Automatic round creation and drawing
        """
        if self.is_running:
            logger.warning("Operator is already running")
            return
        
        logger.info("🚀 Starting automated lottery operator...")
        self.is_running = True
        self._stop_event.clear()
        
        # Update status
        memory_store.update_operator_status(is_running=True)
        
        try:
            # Start main operation loop
            await asyncio.gather(
                self._main_operation_loop(),
                self._event_monitoring_loop(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Operator error: {e}")
            raise
        finally:
            self.is_running = False
            memory_store.update_operator_status(is_running=False)
    
    async def stop(self) -> None:
        """
        Stop the automated operator gracefully.
        """
        logger.info("🛑 Stopping automated operator...")
        self.is_running = False
        self._stop_event.set()
        
        # Wait a moment for loops to finish
        await asyncio.sleep(1)
        
        memory_store.update_operator_status(is_running=False)
        logger.info("Automated operator stopped")
    
    async def _main_operation_loop(self) -> None:
        """
        Main operation loop that manages round lifecycle.
        
        This loop runs continuously and:
        - Checks current round status
        - Creates new rounds when needed
        - Executes draws when ready
        - Handles error conditions
        """
        logger.info("Starting main operation loop")
        
        while self.is_running and not self._stop_event.is_set():
            try:
                await self._perform_operator_cycle()
                
                # Reset error count on successful cycle
                if self.consecutive_errors > 0:
                    self.consecutive_errors = 0
                    logger.info("Operator cycle successful, error count reset")
                
            except Exception as e:
                self.consecutive_errors += 1
                self.last_error_time = datetime.now()
                
                logger.error(f"Operator cycle error #{self.consecutive_errors}: {e}")
                memory_store.update_operator_status(error_count=self.consecutive_errors)
                
                # Pause on too many consecutive errors
                if self.consecutive_errors >= self.max_errors_before_pause:
                    pause_duration = min(300, 30 * self.consecutive_errors)  # Max 5 minutes
                    logger.warning(f"Too many errors, pausing for {pause_duration} seconds")
                    await asyncio.sleep(pause_duration)
            
            # Wait before next cycle
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), 
                    timeout=self.round_check_interval
                )
                break  # Stop event was set
            except asyncio.TimeoutError:
                continue  # Normal timeout, continue loop
    
    async def _perform_operator_cycle(self) -> None:
        """
        Perform one complete operator cycle.
        
        Checks contract state and performs necessary actions:
        - Load current round information
        - Create new round if needed
        - Execute draw if ready
        - Handle refunds if required
        """
        logger.debug("Performing operator cycle...")
        
        # Load current round from contract
        current_round = await self._load_current_round()
        
        if current_round is None:
            # No active round - create one if enabled
            if self.auto_create_rounds:
                logger.info("No active round found, creating new round")
                memory_store.add_pending_action("create_new_round")
                await self._create_new_round()
            else:
                logger.debug("No active round, but auto-creation is disabled")
            return
        
        # Update memory store with current round
        memory_store.set_current_round(current_round)
        memory_store.update_operator_status(current_round_id=current_round.round_id)
        
        # Handle round based on state
        if current_round.state == RoundState.WAITING:
            logger.debug(f"Round #{current_round.round_id} is waiting")
            # Round was created but not started - normal state
            
        elif current_round.state == RoundState.BETTING:
            logger.debug(f"Round #{current_round.round_id} is in betting phase")
            # Check if betting should end
            await self._check_betting_end_time(current_round)
            
        elif current_round.state == RoundState.DRAWING:
            logger.info(f"Round #{current_round.round_id} is ready for drawing")
            memory_store.add_pending_action(f"draw_round_{current_round.round_id}")
            await self._execute_draw(current_round)
            
        elif current_round.state == RoundState.COMPLETED:
            logger.info(f"Round #{current_round.round_id} is completed, winner: {current_round.winner}")
            # Create new round after completion
            if self.auto_create_rounds:
                logger.info("Round completed, creating next round")
                memory_store.add_pending_action("create_next_round")
                await self._create_new_round()
            
        elif current_round.state == RoundState.REFUNDED:
            logger.info(f"Round #{current_round.round_id} was refunded")
            # Create new round after refund
            if self.auto_create_rounds:
                logger.info("Round refunded, creating replacement round")
                memory_store.add_pending_action("create_replacement_round")
                await self._create_new_round()
    
    async def _create_new_round(self) -> None:
        """
        Create a new lottery round.
        
        Calls the contract's createRound function and handles the response.
        """
        try:
            logger.info("Creating new lottery round...")
            
            # Call contract function
            tx_hash = await self.blockchain_client.create_round()
            logger.info(f"New round creation transaction: {tx_hash}")
            
            # Wait for transaction confirmation
            receipt = await self.blockchain_client.wait_for_transaction(tx_hash)
            if receipt['status'] == 1:
                logger.info("✅ New round created successfully")
                
                # Update stats
                current_status = memory_store.get_operator_status()
                memory_store.update_operator_status(
                    total_rounds_managed=current_status.total_rounds_managed + 1
                )
                memory_store.remove_pending_action("create_new_round")
                memory_store.remove_pending_action("create_next_round")
                memory_store.remove_pending_action("create_replacement_round")
            else:
                logger.error("❌ New round creation transaction failed")
                
        except Exception as e:
            logger.error(f"Failed to create new round: {e}")
            raise
    
    async def _execute_draw(self, round_data: LotteryRound) -> None:
        """
        Execute the draw for a round in DRAWING state.
        
        Args:
            round_data: LotteryRound object in DRAWING state
        """
        try:
            logger.info(f"Executing draw for round #{round_data.round_id}...")
            
            # Check if we can actually draw
            can_draw = await self.blockchain_client.can_draw(round_data.round_id)
            if not can_draw:
                logger.warning(f"Cannot draw round #{round_data.round_id} yet")
                return
            
            # Call contract function
            tx_hash = await self.blockchain_client.draw_round(round_data.round_id)
            logger.info(f"Draw transaction for round #{round_data.round_id}: {tx_hash}")
            
            # Wait for transaction confirmation
            receipt = await self.blockchain_client.wait_for_transaction(tx_hash)
            if receipt['status'] == 1:
                logger.info(f"✅ Draw executed successfully for round #{round_data.round_id}")
                memory_store.remove_pending_action(f"draw_round_{round_data.round_id}")
            else:
                logger.error(f"❌ Draw transaction failed for round #{round_data.round_id}")
                
        except Exception as e:
            logger.error(f"Failed to execute draw for round #{round_data.round_id}: {e}")
            raise
    
    async def _check_betting_end_time(self, round_data: LotteryRound) -> None:
        """
        Check if betting period should end for a round.
        
        Args:
            round_data: LotteryRound object in BETTING state
        """
        current_time = datetime.now().timestamp()
        
        if current_time >= round_data.betting_end_time:
            logger.info(f"Betting period ended for round #{round_data.round_id}")
            # The contract should automatically transition to DRAWING state
            # We don't need to do anything here - just wait for state change
        else:
            time_remaining = round_data.betting_end_time - current_time
            logger.debug(f"Round #{round_data.round_id} betting ends in {time_remaining:.0f} seconds")
    
    async def _load_current_round(self) -> Optional[LotteryRound]:
        """
        Load current round information from the contract.
        
        Returns:
            LotteryRound object or None if no active round
        """
        try:
            # Get current round from contract
            round_data = await self.blockchain_client.get_current_round()
            
            if round_data is None:
                return None
            
            # Convert to our LotteryRound model
            lottery_round = LotteryRound(
                round_id=round_data['round_id'],
                state=RoundState(round_data['state']),
                total_pot=round_data['total_pot'],
                commission_amount=round_data['commission_amount'],
                participants=round_data['participants'],
                winner=round_data.get('winner'),
                created_at=round_data['created_at'],
                betting_start_time=round_data['betting_start_time'],
                betting_end_time=round_data['betting_end_time'],
                draw_time=round_data['draw_time'],
                winner_ticket=round_data.get('winner_ticket', 0),
                random_seed=round_data.get('random_seed', 0)
            )
            
            return lottery_round
            
        except Exception as e:
            logger.error(f"Failed to load current round: {e}")
            raise
    
    async def _load_contract_config(self) -> None:
        """
        Load contract configuration from blockchain.
        """
        try:
            config_data = await self.blockchain_client.get_contract_config()
            
            # Build ContractConfig strictly from the current Lottery.sol getConfig() mapping.
            # get_contract_config() returns canonical keys derived from the contract:
            # publisher_commission_rate, sparsity_commission_rate, min_bet_amount,
            # betting_duration, min_draw_delay_after_end, max_draw_delay_after_end,
            # min_end_time_extension, etc.
            pub_comm = int(config_data.get('publisher_commission_rate', 0))
            spar_comm = int(config_data.get('sparsity_commission_rate', 0))
            sparsity_addr = config_data.get('sparsity_address', '')

            self.contract_config = ContractConfig(
                min_bet_amount=config_data.get('min_bet_amount', 0),
                publisher_commission_rate=pub_comm,
                sparsity_commission_rate=spar_comm,
                betting_duration=config_data.get('betting_duration', 0),
                min_draw_delay=config_data.get('min_draw_delay_after_end', 0),
                max_draw_delay=config_data.get('max_draw_delay_after_end', 0),
                min_end_time_extension=config_data.get('min_end_time_extension', 0),
                sparsity_address=sparsity_addr,
                publisher_address=config_data.get('publisher_address'),
                operator_address=config_data.get('operator_address'),
                min_participants=int(config_data.get('min_participants'))
            )
            
        except Exception as e:
            logger.error(f"Failed to load contract config: {e}")
            raise
    
    async def _event_monitoring_loop(self) -> None:
        """
        Monitor contract events and process them.
        
        This loop runs continuously to:
        - Listen for new contract events
        - Process and store events
        - Update internal state based on events
        """
        logger.info("Starting event monitoring loop")
        
        while self.is_running and not self._stop_event.is_set():
            try:
                # Get recent events from blockchain
                events = await self.blockchain_client.get_recent_events()
                
                for event in events:
                    await self._process_contract_event(event)
                
            except Exception as e:
                logger.error(f"Event monitoring error: {e}")
                # Don't raise here - keep monitoring running
            
            # Wait before next check
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), 
                    timeout=5  # Check for events every 5 seconds
                )
                break
            except asyncio.TimeoutError:
                continue
    
    async def _process_contract_event(self, event_data: Dict[str, Any]) -> None:
        """
        Process a single contract event.
        
        Args:
            event_data: Raw event data from blockchain client
        """
        try:
            # Convert to ContractEvent model
            event = ContractEvent(
                event_name=event_data['event'],
                block_number=event_data['blockNumber'],
                transaction_hash=event_data['transactionHash'],
                timestamp=datetime.fromtimestamp(event_data.get('timestamp', datetime.now().timestamp())),
                args=event_data['args']
            )
            
            # Store in memory
            memory_store.add_event(event)
            
            # Process specific event types
            await self._handle_specific_event(event)
            
        except Exception as e:
            logger.error(f"Failed to process event: {e}")
    
    async def _handle_specific_event(self, event: ContractEvent) -> None:
        """
        Handle specific event types with custom logic.
        
        Args:
            event: ContractEvent to handle
        """
        if event.event_name == 'RoundCreated':
            round_id = event.args.get('roundId')
            logger.info(f"🎲 Round #{round_id} created")
            
        elif event.event_name == 'BetPlaced':
            player = event.args.get('player')
            round_id = event.args.get('roundId')
            amount = event.args.get('amount')
            
            logger.info(f"💰 Bet placed: {amount} wei by {player} in round #{round_id}")
            
            # Store bet in memory
            bet = PlayerBet(
                player_address=player,
                round_id=round_id,
                amount=amount,
                ticket_numbers=event.args.get('ticketNumbers', []),
                timestamp=event.timestamp
            )
            memory_store.add_player_bet(bet)
            
        elif event.event_name == 'RoundCompleted':
            round_id = event.args.get('roundId')
            winner = event.args.get('winner')
            prize = event.args.get('prize')
            
            logger.info(f"🏆 Round #{round_id} completed! Winner: {winner}, Prize: {prize} wei")
            
        elif event.event_name == 'RoundRefunded':
            round_id = event.args.get('roundId')
            logger.info(f"💸 Round #{round_id} refunded to participants")
    
    def _setup_event_listeners(self) -> None:
        """
        Setup event listeners for memory store events.
        """
        # Add listeners for important events
        memory_store.add_event_listener('RoundCreated', self._on_round_created)
        memory_store.add_event_listener('BetPlaced', self._on_bet_placed)
        memory_store.add_event_listener('RoundCompleted', self._on_round_completed)
        
        logger.debug("Event listeners configured")
    
    def _on_round_created(self, event: ContractEvent) -> None:
        """Event listener for RoundCreated events"""
        round_id = event.args.get('roundId')
        logger.debug(f"Event listener: Round #{round_id} created")
    
    def _on_bet_placed(self, event: ContractEvent) -> None:
        """Event listener for BetPlaced events"""
        round_id = event.args.get('roundId')
        logger.debug(f"Event listener: Bet placed in round #{round_id}")
    
    def _on_round_completed(self, event: ContractEvent) -> None:
        """Event listener for RoundCompleted events"""
        round_id = event.args.get('roundId')
        logger.debug(f"Event listener: Round #{round_id} completed")
    
    # Public API Methods
    def get_operator_status(self) -> Dict[str, Any]:
        """
        Get comprehensive operator status for monitoring.
        
        Returns:
            Dictionary containing operator status and statistics
        """
        status = memory_store.get_operator_status()
        current_round = memory_store.get_current_round()
        
        return {
            'is_running': self.is_running,
            'auto_create_rounds': self.auto_create_rounds,
            'current_round_id': status.current_round_id,
            'total_rounds_managed': status.total_rounds_managed,
            'error_count': status.error_count,
            'last_action_time': status.last_action_time,
            'pending_actions': status.pending_actions,
            'contract_config': asdict(self.contract_config) if self.contract_config else None,
            'current_round': asdict(current_round) if current_round else None,
            'consecutive_errors': self.consecutive_errors,
            'last_error_time': self.last_error_time
        }

    # Compatibility accessor used by startup summary
    def get_status(self) -> Dict[str, Any]:
        """Compatibility wrapper returning operator status in a concise form."""
        status = self.get_operator_status()
        return {
            'status': 'running' if self.is_running else 'stopped',
            'operator_address': self.blockchain_client.account.address if self.blockchain_client and self.blockchain_client.account else None,
            'contract_address': self.blockchain_client.contract_address if self.blockchain_client else None,
            'current_round_id': status.get('current_round_id'),
            'auto_create_enabled': status.get('auto_create_rounds'),
            'last_check_time': status.get('last_action_time'),
            'errors': [] if status.get('error_count', 0) == 0 else [{'count': status.get('error_count')}]
        }
    
    async def force_create_round(self) -> str:
        """
        Force creation of a new round (manual override).
        
        Returns:
            Transaction hash of the create round transaction
        """
        if not self.is_running:
            raise RuntimeError("Operator is not running")
        
        logger.info("Manual round creation requested")
        await self._create_new_round()
        return "Round creation initiated"
    
    async def force_draw_round(self, round_id: int) -> str:
        """
        Force draw of a specific round (manual override).
        
        Args:
            round_id: Round ID to draw
            
        Returns:
            Transaction hash of the draw transaction
        """
        if not self.is_running:
            raise RuntimeError("Operator is not running")
        
        current_round = memory_store.get_round(round_id)
        if current_round is None:
            raise ValueError(f"Round #{round_id} not found")
        
        if current_round.state != RoundState.DRAWING:
            raise ValueError(f"Round #{round_id} is not in DRAWING state")
        
        logger.info(f"Manual draw requested for round #{round_id}")
        await self._execute_draw(current_round)
        return f"Draw initiated for round #{round_id}"