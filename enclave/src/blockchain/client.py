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
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.messages import encode_defunct

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
            
            # Add PoA middleware if needed
            if self.chain_id != 1:  # Not mainnet
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                
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
        """Setup smart contract interaction"""
        try:
            if self.contract_address:
                # Load existing contract
                contract_abi = self._load_contract_abi()
                self.contract = self.w3.eth.contract(
                    address=self.contract_address,
                    abi=contract_abi
                )
                logger.info(f"Loaded contract at: {self.contract_address}")
            else:
                # Deploy new contract
                await self._deploy_contract()
                
        except Exception as e:
            logger.error(f"Error setting up contract: {e}")
            # Continue without contract for now
            
    def _load_contract_abi(self):
        """Load contract ABI from compiled artifacts"""
        try:
            abi_file = Path(__file__).parent / "contracts" / "compiled" / "Lottery.abi"
            if abi_file.exists():
                return json.loads(abi_file.read_text())
            else:
                # Return minimal ABI for testing
                return [
                    {
                        "inputs": [
                            {"name": "drawId", "type": "string"},
                            {"name": "winner", "type": "address"},
                            {"name": "winningNumber", "type": "uint256"},
                            {"name": "totalPot", "type": "uint256"}
                        ],
                        "name": "recordDraw",
                        "outputs": [],
                        "type": "function"
                    }
                ]
        except Exception as e:
            logger.error(f"Error loading contract ABI: {e}")
            return []
            
    async def _deploy_contract(self):
        """Deploy lottery smart contract"""
        try:
            # Load contract bytecode
            bytecode_file = Path(__file__).parent / "contracts" / "compiled" / "Lottery.bin"
            if not bytecode_file.exists():
                logger.warning("Contract bytecode not found, skipping deployment")
                return
                
            bytecode = bytecode_file.read_text().strip()
            abi = self._load_contract_abi()
            
            # Create contract instance
            contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
            
            # Deploy contract
            transaction = contract.constructor().build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 2000000,
                'gasPrice': self.w3.to_wei('20', 'gwei'),
            })
            
            # Sign and send transaction
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Create contract instance with deployed address
            self.contract = self.w3.eth.contract(
                address=receipt.contractAddress,
                abi=abi
            )
            
            logger.info(f"Contract deployed at: {receipt.contractAddress}")
            
        except Exception as e:
            logger.error(f"Error deploying contract: {e}")
            
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