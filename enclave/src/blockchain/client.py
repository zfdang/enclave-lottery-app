"""
Blockchain Client - Handles all blockchain interactions for role-based lottery system
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

logger = logging.getLogger(__name__)


class BlockchainClient:
    """Handles blockchain operations for the role-based lottery system"""
    
    def __init__(self, config):
        self.config = config
        self.w3: Optional[Web3] = None
        self.contract = None
        self.account = None
        self.role = None  # 'admin', 'operator', or 'player'
        
        # Blockchain configuration
        self.rpc_url = config.get('blockchain', {}).get('rpc_url', 'http://localhost:8545')
        self.chain_id = config.get('blockchain', {}).get('chain_id', 31337)
        self.contract_address = config.get('contract', {}).get('address') or config.get('blockchain', {}).get('contract_address')
        
        # Load contract ABI
        self.contract_abi = config.get('contract', {}).get('abi')
        
        # Load private key from config
        private_key = config.get('blockchain', {}).get('private_key')
        if not private_key:
            raise ValueError("Private key is required for blockchain operations")
            
        self.account = Account.from_key(private_key)
        
        # Determine role from config or contract
        self.role = config.get('operator', {}).get('role', 'operator')
            
    async def initialize(self):
        """Initialize blockchain connection and contract"""
        try:
            # Connect to blockchain network
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                
            # Check connection
            if not self.w3.is_connected():
                raise Exception("Failed to connect to blockchain network")
                
            logger.info(f"Connected to blockchain: {self.rpc_url}")
            logger.info(f"Account address: {self.account.address}")
            logger.info(f"Account role: {self.role}")
            
            # Setup contract interaction
            await self._setup_contract()
            
            # Verify role permissions
            await self._verify_role_permissions()
            
        except Exception as e:
            logger.error(f"Failed to initialize blockchain client: {e}")
            raise
            
    async def _setup_contract(self):
        """Setup smart contract interaction"""
        try:
            if not self.contract_address:
                raise ValueError("Contract address not provided in configuration")
                
            if not self.contract_abi:
                raise ValueError("Contract ABI not found in configuration")
            
            # Create contract instance
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            
            logger.info(f"Contract connected at: {self.contract_address}")
                
        except Exception as e:
            logger.error(f"Error setting up contract: {e}")
            raise
            
    async def _verify_role_permissions(self):
        """Verify account has required permissions for its role"""
        try:
            if not self.contract:
                return
                
            # Get contract configuration
            config = await self._call_contract_function('getConfig')
            admin_addr, operator_addr, _, _, _, _, _ = config
            
            # Verify role permissions
            if self.role == 'admin':
                if self.account.address.lower() != admin_addr.lower():
                    raise ValueError(f"Account {self.account.address} is not the admin")
                    
            elif self.role == 'operator':
                if self.account.address.lower() != operator_addr.lower():
                    raise ValueError(f"Account {self.account.address} is not the operator")
                    
            # Players don't need special verification
            
            logger.info(f"Role permissions verified for {self.role}")
            
        except Exception as e:
            logger.warning(f"Could not verify role permissions: {e}")
            
    async def _call_contract_function(self, function_name: str, *args, **kwargs):
        """Helper to call contract view functions"""
        if not self.contract:
            raise Exception("Contract not initialized")
            
        try:
            function = getattr(self.contract.functions, function_name)
            return function(*args).call()
        except Exception as e:
            logger.error(f"Error calling contract function {function_name}: {e}")
            raise
            
    async def _send_contract_transaction(self, function_name: str, *args, **kwargs):
        """Helper to send contract transactions"""
        if not self.contract:
            raise Exception("Contract not initialized")
            
        try:
            # Get function
            function = getattr(self.contract.functions, function_name)
            
            # Estimate gas
            gas_estimate = function(*args).estimate_gas({'from': self.account.address})
            
            # Build transaction
            txn = function(*args).build_transaction({
                'from': self.account.address,
                'gas': int(gas_estimate * 1.2),  # Add 20% buffer
                'gasPrice': self.w3.to_wei('20', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'chainId': self.chain_id
            })
            
            # Add value if specified
            if 'value' in kwargs:
                txn['value'] = kwargs['value']
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status != 1:
                raise Exception(f"Transaction failed: {tx_hash.hex()}")
                
            return receipt
            
        except Exception as e:
            logger.error(f"Error sending transaction {function_name}: {e}")
            raise
    
    # =============== OPERATOR FUNCTIONS ===============
    
    async def start_new_round(self) -> Dict[str, Any]:
        """Start a new lottery round (operator only)"""
        if self.role != 'operator':
            raise ValueError("Only operator can start new rounds")
            
        try:
            # Check if there's already an active round
            has_active = await self._call_contract_function('hasActiveRound')
            if has_active:
                raise ValueError("Active round already exists")
                
            # Send transaction to start new round
            receipt = await self._send_contract_transaction('startNewRound')
            
            # Get round details from events
            round_created_events = self.contract.events.RoundCreated().process_receipt(receipt)
            if not round_created_events:
                raise Exception("RoundCreated event not found")
                
            event = round_created_events[0]['args']
            
            round_info = {
                'round_id': event['roundId'],
                'start_time': event['startTime'],
                'end_time': event['endTime'],
                'draw_time': event['drawTime'],
                'tx_hash': receipt.transactionHash.hex(),
                'block_number': receipt.blockNumber
            }
            
            logger.info(f"New round started: Round {round_info['round_id']}")
            return round_info
            
        except Exception as e:
            logger.error(f"Error starting new round: {e}")
            raise
    
    async def draw_winner(self, round_id: int) -> Dict[str, Any]:
        """Draw winner for a lottery round (operator only)"""
        if self.role != 'operator':
            raise ValueError("Only operator can draw winners")
            
        try:
            # Check if round can be drawn
            can_draw = await self._call_contract_function('canDrawCurrentRound')
            if not can_draw:
                raise ValueError("Round cannot be drawn yet")
                
            # Send transaction to draw winner
            receipt = await self._send_contract_transaction('drawWinner', round_id)
            
            # Get round completion details from events
            completed_events = self.contract.events.RoundCompleted().process_receipt(receipt)
            if not completed_events:
                raise Exception("RoundCompleted event not found")
                
            event = completed_events[0]['args']
            
            result = {
                'round_id': event['roundId'],
                'winner': event['winner'],
                'total_pot': event['totalPot'],
                'winner_prize': event['winnerPrize'],
                'admin_commission': event['adminCommission'],
                'random_seed': event['randomSeed'],
                'tx_hash': receipt.transactionHash.hex(),
                'block_number': receipt.blockNumber
            }
            
            logger.info(f"Winner drawn for round {round_id}: {result['winner']}")
            return result
            
        except Exception as e:
            logger.error(f"Error drawing winner for round {round_id}: {e}")
            raise
    
    async def cancel_round(self, round_id: int, reason: str) -> Dict[str, Any]:
        """Cancel a lottery round (operator only)"""
        if self.role != 'operator':
            raise ValueError("Only operator can cancel rounds")
            
        try:
            # Send transaction to cancel round
            receipt = await self._send_contract_transaction('cancelRound', round_id, reason)
            
            # Get cancellation details from events
            cancelled_events = self.contract.events.RoundCancelled().process_receipt(receipt)
            if not cancelled_events:
                raise Exception("RoundCancelled event not found")
                
            event = cancelled_events[0]['args']
            
            result = {
                'round_id': event['roundId'],
                'reason': event['reason'],
                'total_refunded': event['totalRefunded'],
                'tx_hash': receipt.transactionHash.hex(),
                'block_number': receipt.blockNumber
            }
            
            logger.info(f"Round {round_id} cancelled: {reason}")
            return result
            
        except Exception as e:
            logger.error(f"Error cancelling round {round_id}: {e}")
            raise
    
    # =============== PLAYER FUNCTIONS ===============
    
    async def place_bet(self, bet_amount: float) -> Dict[str, Any]:
        """Place a bet in the current active round"""
        try:
            # Check if there's an active round
            has_active = await self._call_contract_function('hasActiveRound')
            if not has_active:
                raise ValueError("No active round available")
                
            # Convert bet amount to wei
            bet_wei = self.w3.to_wei(bet_amount, 'ether')
            
            # Send transaction to place bet
            receipt = await self._send_contract_transaction('placeBet', value=bet_wei)
            
            # Get bet details from events
            bet_events = self.contract.events.BetPlaced().process_receipt(receipt)
            if not bet_events:
                raise Exception("BetPlaced event not found")
                
            event = bet_events[0]['args']
            
            result = {
                'round_id': event['roundId'],
                'player': event['player'],
                'amount': event['amount'],
                'new_total': event['newTotal'],
                'timestamp': event['timestamp'],
                'tx_hash': receipt.transactionHash.hex(),
                'block_number': receipt.blockNumber
            }
            
            logger.info(f"Bet placed: {bet_amount} ETH in round {result['round_id']}")
            return result
            
        except Exception as e:
            logger.error(f"Error placing bet: {e}")
            raise
    
    # =============== VIEW FUNCTIONS ===============
    
    async def get_current_round(self) -> Optional[Dict[str, Any]]:
        """Get current active round information"""
        try:
            round_data = await self._call_contract_function('getCurrentRound')
            
            if round_data[0] == 0:  # No active round
                return None
                
            return {
                'round_id': round_data[0],
                'start_time': round_data[1],
                'end_time': round_data[2],
                'draw_time': round_data[3],
                'total_pot': round_data[4],
                'participant_count': round_data[5],
                'winner': round_data[6] if round_data[6] != '0x0000000000000000000000000000000000000000' else None,
                'admin_commission': round_data[7],
                'winner_prize': round_data[8],
                'completed': round_data[9],
                'cancelled': round_data[10],
                'refunded': round_data[11]
            }
            
        except Exception as e:
            logger.error(f"Error getting current round: {e}")
            return None
    
    async def get_round(self, round_id: int) -> Optional[Dict[str, Any]]:
        """Get specific round information"""
        try:
            round_data = await self._call_contract_function('rounds', round_id)
            
            if round_data[0] == 0:  # Round doesn't exist
                return None
                
            return {
                'round_id': round_data[0],
                'start_time': round_data[1],
                'end_time': round_data[2],
                'draw_time': round_data[3],
                'total_pot': round_data[4],
                'participant_count': round_data[5],
                'winner': round_data[6] if round_data[6] != '0x0000000000000000000000000000000000000000' else None,
                'admin_commission': round_data[7],
                'winner_prize': round_data[8],
                'completed': round_data[9],
                'cancelled': round_data[10],
                'refunded': round_data[11]
            }
            
        except Exception as e:
            logger.error(f"Error getting round {round_id}: {e}")
            return None
    
    async def get_player_bet(self, round_id: int, player_address: str) -> int:
        """Get player's bet amount for a specific round"""
        try:
            bet_amount = await self._call_contract_function('getPlayerBet', round_id, player_address)
            return bet_amount
            
        except Exception as e:
            logger.error(f"Error getting player bet: {e}")
            return 0
    
    async def get_round_participants(self, round_id: int) -> List[str]:
        """Get list of participants for a specific round"""
        try:
            participants = await self._call_contract_function('getRoundParticipants', round_id)
            return list(participants)
            
        except Exception as e:
            logger.error(f"Error getting round participants: {e}")
            return []
    
    async def can_draw_current_round(self) -> bool:
        """Check if current round can be drawn"""
        try:
            return await self._call_contract_function('canDrawCurrentRound')
            
        except Exception as e:
            logger.error(f"Error checking if round can be drawn: {e}")
            return False
    
    async def get_contract_config(self) -> Dict[str, Any]:
        """Get contract configuration"""
        try:
            config = await self._call_contract_function('getConfig')
            admin_addr, operator_addr, commission_rate, min_bet, betting_dur, draw_delay, min_part = config
            
            return {
                'admin': admin_addr,
                'operator': operator_addr,
                'commission_rate': commission_rate,
                'min_bet_amount': min_bet,
                'betting_duration': betting_dur,
                'draw_delay': draw_delay,
                'min_participants': min_part
            }
            
        except Exception as e:
            logger.error(f"Error getting contract config: {e}")
            return {}
    
    # =============== EVENT MONITORING ===============
    
    async def listen_for_events(self, event_callback=None):
        """Listen for contract events"""
        if not self.contract:
            return
            
        try:
            # Create event filters
            round_created_filter = self.contract.events.RoundCreated.create_filter(fromBlock='latest')
            bet_placed_filter = self.contract.events.BetPlaced.create_filter(fromBlock='latest')
            round_completed_filter = self.contract.events.RoundCompleted.create_filter(fromBlock='latest')
            
            logger.info("Started listening for contract events")
            
            while True:
                # Check for new events
                for event in round_created_filter.get_new_entries():
                    logger.info(f"Round created: {event['args']}")
                    if event_callback:
                        await event_callback('RoundCreated', event['args'])
                
                for event in bet_placed_filter.get_new_entries():
                    logger.info(f"Bet placed: {event['args']}")
                    if event_callback:
                        await event_callback('BetPlaced', event['args'])
                
                for event in round_completed_filter.get_new_entries():
                    logger.info(f"Round completed: {event['args']}")
                    if event_callback:
                        await event_callback('RoundCompleted', event['args'])
                
                await asyncio.sleep(5)  # Poll every 5 seconds
                
        except Exception as e:
            logger.error(f"Error listening for events: {e}")
    
    # =============== UTILITY FUNCTIONS ===============
    
    def wei_to_eth(self, wei_amount: int) -> float:
        """Convert wei to ETH"""
        return self.w3.from_wei(wei_amount, 'ether')
    
    def eth_to_wei(self, eth_amount: float) -> int:
        """Convert ETH to wei"""
        return self.w3.to_wei(eth_amount, 'ether')
    
    async def get_account_balance(self, address: str = None) -> float:
        """Get account balance in ETH"""
        address = address or self.account.address
        balance_wei = self.w3.eth.get_balance(address)
        return self.wei_to_eth(balance_wei)
            
    async def verify_signature(self, address: str, signature: str) -> bool:
        """Verify wallet signature for authentication"""
        try:
            # Create message to verify (standard message for wallet connection)
            message = f"Connect to Lottery Enclave at {datetime.utcnow().isoformat()}"
            encoded_message = encode_defunct(text=message)
            
            # Recover address from signature
            recovered_address = Account.recover_message(encoded_message, signature=signature)
            
            return recovered_address.lower() == address.lower()
            
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
            
    async def record_lottery_result(self, draw_data: Dict):
        """Record lottery result on blockchain"""
        try:
            if not self.contract:
                logger.warning("No contract available, storing result locally")
                return
                
            # Prepare transaction data
            winner_address = draw_data.get('winner', '0x0000000000000000000000000000000000000000')
            if not winner_address:
                winner_address = '0x0000000000000000000000000000000000000000'
                
            total_pot_wei = self.w3.to_wei(float(draw_data.get('total_pot', 0)), 'ether')
            
            # Build transaction
            transaction = self.contract.functions.recordDraw(
                draw_data['draw_id'],
                winner_address,
                draw_data.get('winning_number', 0),
                total_pot_wei
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.w3.to_wei('20', 'gwei'),
            })
            
            # Sign and send transaction
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"Lottery result recorded on blockchain: {tx_hash.hex()}")
            
        except Exception as e:
            logger.error(f"Error recording lottery result: {e}")
            
    async def get_balance(self, address: str) -> Decimal:
        """Get ETH balance for an address"""
        try:
            if not self.w3:
                return Decimal('0')
                
            balance_wei = self.w3.eth.get_balance(address)
            balance_eth = self.w3.from_wei(balance_wei, 'ether')
            return Decimal(str(balance_eth))
            
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            return Decimal('0')
            
    async def close(self):
        """Close blockchain connection"""
        logger.info("Closing blockchain client")
        # Cleanup if needed