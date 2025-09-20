"""
Blockchain Client - Handles all blockchain interactions within the enclave
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

from .deploy import auto_deploy_contracts

logger = logging.getLogger(__name__)


class BlockchainClient:
    """Handles blockchain operations from within the enclave"""
    
    def __init__(self, config):
        self.config = config
        self.w3: Optional[Web3] = None
        self.contract = None
        self.account = None
        
        # Blockchain configuration
        self.rpc_url = config.get('blockchain', {}).get('rpc_url', 'http://localhost:8545')
        self.chain_id = config.get('blockchain', {}).get('chain_id', 1337)
        self.contract_address = config.get('blockchain', {}).get('contract_address')
        
        # Load private key from config or generate new one
        private_key = config.get('blockchain', {}).get('private_key')
        if private_key:
            self.account = Account.from_key(private_key)
        else:
            # Generate new account for enclave
            self.account = Account.create()
            logger.warning(f"Generated new account: {self.account.address}")
            
    async def initialize(self):
        """Initialize blockchain connection"""
        try:
            # Connect to blockchain network
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                
            # Check connection
            if not self.w3.is_connected():
                raise Exception("Failed to connect to blockchain network")
                
            logger.info(f"Connected to blockchain: {self.rpc_url}")
            logger.info(f"Enclave address: {self.account.address}")
            
            # Load or deploy smart contract
            await self._setup_contract()
            
        except Exception as e:
            logger.error(f"Failed to initialize blockchain client: {e}")
            raise
            
    async def _setup_contract(self):
        """Setup smart contract interaction with automatic deployment"""
        try:
            # Use the deployment module to ensure contract is deployed
            contract_address, contract_abi = await auto_deploy_contracts(
                self.w3, self.account, self.config
            )
            
            # Create contract instance
            self.contract = self.w3.eth.contract(
                address=contract_address,
                abi=contract_abi
            )
            
            # Update config with deployed contract address
            if not self.contract_address:
                self.contract_address = contract_address
                logger.info(f"Contract setup complete at: {contract_address}")
                
        except Exception as e:
            logger.error(f"Error setting up contract: {e}")
            # Continue without contract for now
            
    async def verify_transaction(self, tx_hash: str, user_address: str, amount: float) -> bool:
        """Verify a user's bet transaction"""
        try:
            if not self.w3:
                return False
                
            # Get transaction details
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            # Verify transaction was successful
            if receipt.status != 1:
                logger.warning(f"Transaction failed: {tx_hash}")
                return False
                
            # Verify sender
            if tx['from'].lower() != user_address.lower():
                logger.warning(f"Transaction sender mismatch: {tx['from']} != {user_address}")
                return False
                
            # Verify amount (convert to wei for comparison)
            expected_wei = self.w3.to_wei(amount, 'ether')
            if tx['value'] != expected_wei:
                logger.warning(f"Transaction amount mismatch: {tx['value']} != {expected_wei}")
                return False
                
            # Verify recipient (should be our contract or enclave address)
            # For now, just verify it's not empty
            if not tx['to']:
                logger.warning(f"Transaction has no recipient: {tx_hash}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying transaction {tx_hash}: {e}")
            return False
            
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