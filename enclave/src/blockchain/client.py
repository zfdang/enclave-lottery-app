"""
Enhanced Blockchain Client

Handles all blockchain interactions for the automated lottery operator system.
Provides complete integration with the current Lottery.sol contract structure.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, List, Any

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

logger = logging.getLogger(__name__)


class BlockchainClient:
    """
    Enhanced blockchain client for automated lottery operator.
    
    Provides complete integration with Lottery.sol contract:
    - Operator role management with private key handling
    - Full contract interaction (create rounds, draw, refund)
    - Event monitoring and processing
    - Transaction management with proper error handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.w3: Optional[Web3] = None
        self.contract = None
        self.account = None
        self.role = None  # Will be verified as 'operator' after initialization
        
        # Blockchain configuration
        self.rpc_url = config.get('blockchain', {}).get('rpc_url', 'http://localhost:8545')
        self.chain_id = config.get('blockchain', {}).get('chain_id', 31337)
        self.contract_address = config.get('blockchain', {}).get('contract_address')
        
        # Contract ABI path - always use new ABI location
        # This ABI file will be copied by running /scripts/build_docker.sh
        self.contract_abi_path = str(Path(__file__).parent.parent / 'contracts' / 'abi' / 'Lottery.abi')
        
        # Load operator credentials from config
        operator_address = config.get('blockchain', {}).get('operator_address')
        operator_private_key = config.get('blockchain', {}).get('operator_private_key')

        # Initialize operator account from private key
        if operator_private_key:
            self.account = Account.from_key(operator_private_key)
            
            # Verify address matches if provided
            if operator_address and self.account.address.lower() != operator_address.lower():
                logger.error("Operator address does not match private key!")
                raise ValueError("Operator address and private key mismatch")
                
            logger.info("Operator credentials loaded from configuration")
            
        else:
            # Generate temporary account if no private key provided
            self.account = Account.create()
            logger.warning("Generated temporary operator account - this should only happen in development")
            
        logger.info(f"Operator address: {self.account.address}")
        
        # Transaction configuration
        self.gas_price = config.get('blockchain', {}).get('gas_price', '20')  # gwei
        self.gas_multiplier = config.get('blockchain', {}).get('gas_multiplier', 1.2)
        
        # Event monitoring state
        self.last_processed_block = 0
        self.event_filters = {}
        
        logger.info("Enhanced blockchain client initialized")

            
    async def initialize(self) -> None:
        """
        Initialize blockchain connection and contract.
        
        Sets up Web3 connection, loads contract ABI, creates contract instance,
        and verifies operator permissions.
        """
        try:
            # Connect to blockchain network
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                
            # Check connection
            if not self.w3.is_connected():
                raise Exception(f"Failed to connect to blockchain network: {self.rpc_url}")
                
            logger.info(f"✅ Connected to blockchain: {self.rpc_url}")
            logger.info(f"📍 Chain ID: {self.chain_id}")
            logger.info(f"💰 Operator balance: {await self.get_account_balance():.4f} ETH")
            
            if self.contract_address:
                # Setup contract only if address is provided
                await self._setup_contract()
                
                # Verify operator role permissions
                await self._verify_operator_permissions()
                
                logger.info("🎯 Blockchain client fully initialized as operator")
            else:
                logger.warning("⚠️  No contract address provided, running without contract")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize blockchain client: {e}")
            raise
    
    async def _setup_contract(self) -> None:
        """
        Setup smart contract interaction.
        
        Loads contract ABI and creates contract instance for interaction.
        """
        try:
            logger.debug(f"Loading contract ABI from: {self.contract_abi_path}")
            
            # Load contract ABI
            abi_path = Path(self.contract_abi_path)
            if not abi_path.is_file():
                raise FileNotFoundError(f"Contract ABI file not found: {abi_path}")
                
            with open(abi_path, 'r') as f:
                self.contract_abi = json.load(f)
                    
            # Create contract instance
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            
            logger.info(f"📄 Contract connected: {self.contract_address}")
                
        except Exception as e:
            logger.error(f"❌ Error setting up contract: {e}")
            raise
    
    async def _verify_operator_permissions(self) -> None:
        """
        Verify account has operator permissions for the contract.
        
        Checks that the loaded account matches the operator address in the contract.
        """
        try:
            if not self.contract:
                logger.warning("Cannot verify permissions: no contract available")
                return
                
            # Get contract configuration to check operator address
            config = await self._call_contract_function('getConfig')
            
            # Handle both dict and tuple return formats
            if isinstance(config, dict):
                operator_addr = config.get('operatorAddress', config.get('operatorAddr'))
            else:
                # getConfig returns an 11-tuple in the contract; operatorAddr is at index 2
                # (see contracts/Lottery.sol: publisher=0, sparsity=1, operator=2, ...)
                operator_addr = config[2]

            # Show operator address
            logger.info(f"🎯  Contract operator address: {operator_addr}")

            # Normalize operator address from contract and compare defensively
            try:
                operator_addr_normalized = None
                if operator_addr is None:
                    operator_addr_normalized = None
                elif isinstance(operator_addr, str):
                    operator_addr_normalized = operator_addr
                elif isinstance(operator_addr, bytes):
                    operator_addr_normalized = self.w3.to_hex(operator_addr)
                elif isinstance(operator_addr, int):
                    # If contract returned integer, try hex conversion
                    operator_addr_normalized = self.w3.to_hex(operator_addr)
                else:
                    operator_addr_normalized = str(operator_addr)

                if operator_addr_normalized is None:
                    raise ValueError("Operator address not found in contract config")

                # Compare checksum/lowercase variants where possible
                try:
                    acct_addr = self.account.address.lower()
                    op_addr = operator_addr_normalized.lower()
                except Exception:
                    acct_addr = str(self.account.address).lower()
                    op_addr = str(operator_addr_normalized).lower()

                if acct_addr != op_addr:
                    raise ValueError(f"Account {self.account.address} is not the contract operator (expected: {operator_addr_normalized})")

                self.role = 'operator'
                logger.info(f"✅ Operator permissions verified for: {self.account.address}")

            except Exception as e:
                logger.warning(f"⚠️  Could not verify operator permissions: {e}")
                # Don't raise here - allow operation to continue with warning
            
        except Exception as e:
            logger.warning(f"⚠️  Could not verify operator permissions: {e}")
            # Don't raise here - allow operation to continue with warning
            
    async def _call_contract_function(self, function_name: str, *args, **kwargs) -> Any:
        """
        Helper to call contract view functions.
        
        Args:
            function_name: Name of contract function to call
            *args: Function arguments
            **kwargs: Additional options
            
        Returns:
            Function return value
        """
        if not self.contract:
            raise Exception("Contract not initialized")
            
        try:
            function = getattr(self.contract.functions, function_name)
            result = function(*args).call()
            
            logger.debug(f"Contract call {function_name}({args}) -> {type(result)}")
            return result
            
        except Exception as e:
            logger.error(f"Error calling contract function {function_name}: {e}")
            raise
    
    async def _send_contract_transaction(self, function_name: str, *args, **kwargs) -> str:
        """
        Helper to send contract transactions.
        
        Args:
            function_name: Name of contract function to call
            *args: Function arguments
            **kwargs: Transaction options (value, gas, etc.)
            
        Returns:
            Transaction hash as hex string
        """
        if not self.contract:
            raise Exception("Contract not initialized")
            
        try:
            # Get function
            function = getattr(self.contract.functions, function_name)
            
            # Estimate gas
            gas_params = {'from': self.account.address}
            if 'value' in kwargs:
                gas_params['value'] = kwargs['value']
                
            gas_estimate = function(*args).estimate_gas(gas_params)
            
            # Build transaction
            txn = function(*args).build_transaction({
                'from': self.account.address,
                'gas': int(gas_estimate * self.gas_multiplier),
                'gasPrice': self.w3.to_wei(self.gas_price, 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'chainId': self.chain_id
            })
            
            # Add value if specified
            if 'value' in kwargs:
                txn['value'] = kwargs['value']
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            tx_hash_hex = tx_hash.hex()
            logger.info(f"📤 Transaction sent: {function_name} -> {tx_hash_hex}")
            
            return tx_hash_hex
            
        except Exception as e:
            logger.error(f"❌ Error sending transaction {function_name}: {e}")
            raise
    
    async def wait_for_transaction(self, tx_hash: str, timeout: int = 300) -> Dict[str, Any]:
        """
        Wait for transaction confirmation.
        
        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            Transaction receipt
        """
        try:
            logger.debug(f"⏳ Waiting for transaction: {tx_hash}")
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            if receipt.status == 1:
                logger.info(f"✅ Transaction confirmed: {tx_hash}")
            else:
                logger.error(f"❌ Transaction failed: {tx_hash}")
                
            return {
                'status': receipt.status,
                'blockNumber': receipt.blockNumber,
                'transactionHash': receipt.transactionHash.hex(),
                'gasUsed': receipt.gasUsed,
                'logs': receipt.logs
            }
            
        except Exception as e:
            logger.error(f"❌ Error waiting for transaction {tx_hash}: {e}")
            raise
    
    # =============== ENHANCED OPERATOR FUNCTIONS ===============
    
    async def create_round(self) -> str:
        """
        Create a new lottery round (operator only).
        
        Creates a new round using the contract's createRound function.
        The contract will automatically set up timing and state.
        
        Returns:
            Transaction hash
        """
        if self.role != 'operator':
            raise ValueError("Only operator can create new rounds")
            
        try:
            logger.info("🎲 Creating new lottery round...")
            
            # Send transaction to create new round
            tx_hash = await self._send_contract_transaction('createRound')
            
            logger.info(f"✅ Round creation transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Failed to create new round: {e}")
            raise
    
    async def draw_round(self, round_id: Optional[int] = None) -> str:
        """
        Execute draw for the current round (operator only).
        
        Args:
            round_id: Round ID to draw (optional, uses current if not specified)
            
        Returns:
            Transaction hash
        """
        if self.role != 'operator':
            raise ValueError("Only operator can draw rounds")
            
        try:
            logger.info(f"🎯 Drawing lottery round #{round_id or 'current'}...")
            
            # Use drawCurrentRound if no specific round_id provided
            if round_id is None:
                tx_hash = await self._send_contract_transaction('drawCurrentRound')
            else:
                tx_hash = await self._send_contract_transaction('drawRound', round_id)
            
            logger.info(f"✅ Draw transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Failed to draw round: {e}")
            raise
    
    async def refund_round(self, round_id: Optional[int] = None) -> str:
        """
        Refund the current round to all participants (operator only).
        
        Args:
            round_id: Round ID to refund (optional, uses current if not specified)
            
        Returns:
            Transaction hash
        """
        if self.role != 'operator':
            raise ValueError("Only operator can refund rounds")
            
        try:
            logger.info(f"💸 Refunding lottery round #{round_id or 'current'}...")
            
            # Use refundCurrentRound if no specific round_id provided
            if round_id is None:
                tx_hash = await self._send_contract_transaction('refundCurrentRound')
            else:
                tx_hash = await self._send_contract_transaction('refundRound', round_id)
            
            logger.info(f"✅ Refund transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"❌ Failed to refund round: {e}")
            raise
    
    # =============== VIEW FUNCTIONS ===============
    
    async def get_current_round(self) -> Optional[Dict[str, Any]]:
        """
        Get current active round information.
        
        Returns:
            Dictionary with current round data or None if no active round
        """
        try:
            round_data = await self._call_contract_function('getRound')
            
            # getRound returns a 6-tuple: (roundId, state, totalPot, commissionAmount, participants[], winner)
            if round_data[0] == 0:  # No active round (roundId = 0)
                return None
            
            # Get additional timing information
            timing_data = await self._call_contract_function('getRoundTiming')
            
            return {
                'round_id': round_data[0],
                'state': round_data[1],  # RoundState enum value
                'total_pot': round_data[2],
                'commission_amount': round_data[3], 
                'participants': list(round_data[4]),
                'winner': round_data[5] if round_data[5] != '0x0000000000000000000000000000000000000000' else None,
                'created_at': timing_data[0],
                'betting_start_time': timing_data[1],
                'betting_end_time': timing_data[2],
                'draw_time': timing_data[3]
            }
            
        except Exception as e:
            logger.error(f"Error getting current round: {e}")
            return None
    
    async def get_round_state(self) -> int:
        """
        Get current round state.
        
        Returns:
            RoundState enum value (0=WAITING, 1=BETTING, 2=DRAWING, 3=COMPLETED, 4=REFUNDED)
        """
        try:
            return await self._call_contract_function('getState')
        except Exception as e:
            logger.error(f"Error getting round state: {e}")
            return 0
    
    async def get_participants(self) -> List[str]:
        """
        Get list of participants in current round.
        
        Returns:
            List of participant addresses
        """
        try:
            return await self._call_contract_function('getParticipants')
        except Exception as e:
            logger.error(f"Error getting participants: {e}")
            return []
    
    async def get_player_bet(self, player_address: str) -> int:
        """
        Get player's bet amount in current round.
        
        Args:
            player_address: Player's wallet address
            
        Returns:
            Bet amount in wei
        """
        try:
            return await self._call_contract_function('getPlayerBet', player_address)
        except Exception as e:
            logger.error(f"Error getting player bet for {player_address}: {e}")
            return 0
    
    async def can_draw(self, round_id: Optional[int] = None) -> bool:
        """
        Check if a round can be drawn.
        
        Args:
            round_id: Round ID to check (optional, uses current if not specified)
            
        Returns:
            True if round can be drawn, False otherwise
        """
        try:
            if round_id is None:
                return await self._call_contract_function('canDraw')
            else:
                return await self._call_contract_function('canDrawRound', round_id)
        except Exception as e:
            logger.error(f"Error checking if round can be drawn: {e}")
            return False
    
    async def can_refund(self, round_id: Optional[int] = None) -> bool:
        """
        Check if a round can be refunded.
        
        Args:
            round_id: Round ID to check (optional, uses current if not specified)
            
        Returns:
            True if round can be refunded, False otherwise
        """
        try:
            if round_id is None:
                return await self._call_contract_function('canRefund')
            else:
                return await self._call_contract_function('canRefundRound', round_id)
        except Exception as e:
            logger.error(f"Error checking if round can be refunded: {e}")
            return False
    
    async def get_contract_config(self) -> Dict[str, Any]:
        """
        Get contract configuration.
        
        Returns:
            Dictionary containing contract configuration
        """
        try:
            config = await self._call_contract_function('getConfig')
            
            # Map the 11 return values from the contract to named keys.
            # Solidity getConfig() returns in this order:
            # (publisherAddr, sparsityAddr, operatorAddr, publisherCommission,
            #  sparsityCommission, minBet, bettingDur, minDrawDelay, maxDrawDelay,
            #  minEndTimeExt, minPart) - sparsityIsSet removed
            result = {
                'publisher_address': config[0],
                'sparsity_address': config[1],
                'operator_address': config[2],
                'publisher_commission_rate': config[3],
                'sparsity_commission_rate': config[4],
                'min_bet_amount': config[5],
                'betting_duration': config[6],
                'min_draw_delay_after_end': config[7],
                'max_draw_delay_after_end': config[8],
                'min_end_time_extension': config[9],
                'min_participants': config[10]
            }

            return result
            
        except Exception as e:
            logger.error(f"Error getting contract config: {e}")
            return {}
    
    async def get_min_bet_amount(self) -> int:
        """
        Get minimum bet amount.
        
        Returns:
            Minimum bet amount in wei
        """
        try:
            config = await self.get_contract_config()
            return config.get('min_bet_amount', 0)
        except Exception as e:
            logger.error(f"Error getting min bet amount: {e}")
            return 0
    
    # =============== EVENT MONITORING ===============
    
    async def get_recent_events(self, from_block: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent contract events.
        
        Args:
            from_block: Block number to start from (optional)
            
        Returns:
            List of event dictionaries
        """
        if not self.contract:
            return []
            
        try:
            # Use the last processed block if no from_block specified
            start_block = from_block or max(0, self.last_processed_block - 100)
            
            # Get all events from the contract
            events = []
            
            # Event names to monitor
            event_names = [
                'RoundCreated',
                'BetPlaced', 
                'RoundCompleted',
                'RoundRefunded',
                'OperatorChanged',
                'SparsityProviderSet'
            ]
            
            for event_name in event_names:
                try:
                    event_filter = getattr(self.contract.events, event_name)
                    # web3.py v7 uses snake_case kwargs for filters; try both styles defensively
                    try:
                        event_logs = event_filter.create_filter(
                            from_block=start_block,
                            to_block='latest'
                        ).get_all_entries()
                    except TypeError:
                        # Fallback to camelCase for older compatibility
                        event_logs = event_filter.create_filter(
                            fromBlock=start_block,
                            toBlock='latest'
                        ).get_all_entries()
                    
                    for log in event_logs:
                        events.append({
                            'event': event_name,
                            'blockNumber': log['blockNumber'],
                            'transactionHash': log['transactionHash'].hex(),
                            'args': dict(log['args']),
                            'timestamp': datetime.now().timestamp()  # Would need to get from block in production
                        })
                        
                except AttributeError:
                    # Event doesn't exist in ABI
                    continue
                except Exception as e:
                    logger.warning(f"Error getting {event_name} events: {e}")
                    continue
            
            # Update last processed block
            if events:
                self.last_processed_block = max(event['blockNumber'] for event in events)
            
            # Sort by block number
            events.sort(key=lambda x: x['blockNumber'])
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []
    
    async def start_event_monitoring(self, callback=None) -> None:
        """
        Start continuous event monitoring.
        
        Args:
            callback: Optional callback function for event processing
        """
        if not self.contract:
            logger.warning("Cannot start event monitoring: no contract available")
            return
            
        try:
            logger.info("🎧 Starting contract event monitoring...")
            
            while True:
                try:
                    # Get recent events
                    events = await self.get_recent_events()
                    logger.info(f"Fetched {len(events)} new events")
                    # Process each event
                    for event in events:
                        logger.info(f"Event: {event['event']} at block {event['blockNumber']}")
                        if callback:
                            try:
                                await callback(event)
                            except Exception as e:
                                logger.error(f"Event callback error: {e}")
                    
                    # Wait before next check
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Event monitoring error: {e}")
                    await asyncio.sleep(10)  # Wait longer on error
            
        except asyncio.CancelledError:
            logger.info("Event monitoring cancelled")
        except Exception as e:
            logger.error(f"Event monitoring failed: {e}")
    
    def setup_event_filters(self) -> None:
        """
        Setup event filters for monitoring (if needed).
        """
        if not self.contract:
            return
            
        try:
            # Setup filters for real-time monitoring if needed
            # Try to create filters using snake_case, fall back to camelCase
            try:
                self.event_filters = {
                    'RoundCreated': self.contract.events.RoundCreated.create_filter(from_block='latest'),
                    'BetPlaced': self.contract.events.BetPlaced.create_filter(from_block='latest'),
                    'RoundCompleted': self.contract.events.RoundCompleted.create_filter(from_block='latest'),
                    'RoundRefunded': self.contract.events.RoundRefunded.create_filter(from_block='latest')
                }
            except TypeError:
                # Older web3 may expect camelCase
                self.event_filters = {
                    'RoundCreated': self.contract.events.RoundCreated.create_filter(fromBlock='latest'),
                    'BetPlaced': self.contract.events.BetPlaced.create_filter(fromBlock='latest'),
                    'RoundCompleted': self.contract.events.RoundCompleted.create_filter(fromBlock='latest'),
                    'RoundRefunded': self.contract.events.RoundRefunded.create_filter(fromBlock='latest')
                }
            
            logger.debug("Event filters setup complete")
            
        except Exception as e:
            logger.warning(f"Failed to setup event filters: {e}")
    
    # =============== UTILITY FUNCTIONS ===============
    
    def wei_to_eth(self, wei_amount: int) -> float:
        """Convert wei to ETH"""
        return float(self.w3.from_wei(wei_amount, 'ether'))
    
    def eth_to_wei(self, eth_amount: float) -> int:
        """Convert ETH to wei"""
        return self.w3.to_wei(eth_amount, 'ether')
    
    async def get_account_balance(self, address: Optional[str] = None) -> float:
        """
        Get account balance in ETH.
        
        Args:
            address: Address to check (uses operator address if not specified)
            
        Returns:
            Balance in ETH
        """
        address = address or self.account.address
        balance_wei = self.w3.eth.get_balance(address)
        return self.wei_to_eth(balance_wei)
    
    async def get_current_block_number(self) -> int:
        """
        Get current blockchain block number.
        
        Returns:
            Current block number
        """
        try:
            return self.w3.eth.block_number
        except Exception as e:
            logger.error(f"Error getting block number: {e}")
            return 0
    
    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction receipt or None if not found
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return {
                'status': receipt.status,
                'blockNumber': receipt.blockNumber,
                'gasUsed': receipt.gasUsed,
                'transactionHash': receipt.transactionHash.hex()
            }
        except Exception as e:
            logger.error(f"Error getting transaction receipt for {tx_hash}: {e}")
            return None
    
    def format_address(self, address: str) -> str:
        """
        Format address for display (checksummed).
        
        Args:
            address: Ethereum address
            
        Returns:
            Checksummed address
        """
        try:
            return self.w3.to_checksum_address(address)
        except Exception:
            return address
    
    async def verify_signature(self, address: str, signature: str, message: Optional[str] = None) -> bool:
        """
        Verify wallet signature for authentication.
        
        Args:
            address: Wallet address
            signature: Signature to verify
            message: Message that was signed (optional)
            
        Returns:
            True if signature is valid
        """
        try:
            # Use provided message or create default
            message = message or f"Connect to Lottery Enclave at {datetime.utcnow().isoformat()}"
            
            # Create encoded message
            from eth_account.messages import encode_defunct
            encoded_message = encode_defunct(text=message)
            
            # Recover address from signature
            recovered_address = Account.recover_message(encoded_message, signature=signature)
            
            return recovered_address.lower() == address.lower()
            
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
    
    async def close(self) -> None:
        """
        Close blockchain client and cleanup resources.
        """
        logger.info("🔌 Closing blockchain client...")
        
        # Clear event filters
        self.event_filters.clear()
        
        # Reset connection
        self.w3 = None
        self.contract = None
        
        logger.info("✅ Blockchain client closed")
    
    # =============== STATUS AND MONITORING ===============
    
    def get_client_status(self) -> Dict[str, Any]:
        """
        Get comprehensive client status for monitoring.
        
        Returns:
            Dictionary containing client status information
        """
        return {
            'connected': self.w3 is not None and self.w3.is_connected(),
            'contract_available': self.contract is not None,
            'operator_address': self.account.address if self.account else None,
            'operator_role_verified': self.role == 'operator',
            'contract_address': self.contract_address,
            'chain_id': self.chain_id,
            'rpc_url': self.rpc_url,
            'last_processed_block': self.last_processed_block,
            'event_filters_count': len(self.event_filters),
            'gas_price': self.gas_price,
            'gas_multiplier': self.gas_multiplier
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Health check results
        """
        health = {
            'blockchain_connected': False,
            'contract_accessible': False,
            'operator_balance_sufficient': False,
            'operator_permissions_valid': False,
            'current_block': 0,
            'errors': []
        }
        
        try:
            # Check blockchain connection
            if self.w3 and self.w3.is_connected():
                health['blockchain_connected'] = True
                health['current_block'] = await self.get_current_block_number()
            else:
                health['errors'].append('Blockchain not connected')
            
            # Check contract access
            if self.contract:
                try:
                    # Try a simple contract call
                    await self._call_contract_function('getState')
                    health['contract_accessible'] = True
                except Exception as e:
                    health['errors'].append(f'Contract not accessible: {e}')
            else:
                health['errors'].append('Contract not initialized')
            
            # Check operator balance
            try:
                balance = await self.get_account_balance()
                if balance > 0.01:  # At least 0.01 ETH for gas
                    health['operator_balance_sufficient'] = True
                else:
                    health['errors'].append(f'Operator balance too low: {balance:.4f} ETH')
            except Exception as e:
                health['errors'].append(f'Cannot check operator balance: {e}')
            
            # Check operator permissions
            if self.role == 'operator':
                health['operator_permissions_valid'] = True
            else:
                health['errors'].append('Operator permissions not verified')
            
        except Exception as e:
            health['errors'].append(f'Health check error: {e}')
        
        health['status'] = 'healthy' if not health['errors'] else 'degraded'
        return health