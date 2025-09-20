#!/usr/bin/env python3
"""
Smart Contract Deployment Module for Lottery Enclave
Handles automatic contract deployment when the enclave starts
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from web3 import Web3
from eth_account import Account

logger = logging.getLogger(__name__)


class ContractDeployer:
    """Handles smart contract deployment and verification"""
    
    def __init__(self, web3_instance: Web3, account: Account, config: Dict):
        self.w3 = web3_instance
        self.account = account
        self.config = config
        self.contracts_dir = Path(__file__).parent / "contracts"
        self.compiled_dir = self.contracts_dir / "compiled"
        
    async def ensure_contract_deployed(self, contract_name: str = "Lottery") -> Tuple[str, Dict]:
        """
        Ensure contract is deployed, deploy if necessary
        Returns: (contract_address, contract_abi)
        """
        logger.info(f"Ensuring {contract_name} contract is deployed...")
        
        # Check if contract is already deployed and valid
        existing_address = self.config.get('blockchain', {}).get('contract_address')
        if existing_address:
            abi = self._load_contract_abi(contract_name)
            if await self._verify_contract_deployment(existing_address, abi):
                logger.info(f"Contract already deployed at: {existing_address}")
                return existing_address, abi
            else:
                logger.warning(f"Contract at {existing_address} is invalid, redeploying...")
        
        # Deploy new contract
        return await self.deploy_contract(contract_name)
    
    async def deploy_contract(self, contract_name: str = "Lottery") -> Tuple[str, Dict]:
        """
        Deploy smart contract to blockchain
        Returns: (contract_address, contract_abi)
        """
        logger.info(f"Deploying {contract_name} contract...")
        
        # Load contract artifacts
        bytecode, abi = self._load_contract_artifacts(contract_name)
        
        # Check account balance
        await self._check_deployment_requirements()
        
        # Create contract instance
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Build deployment transaction
        transaction = await self._build_deployment_transaction(contract)
        
        # Sign and send transaction
        signed_txn = self.account.sign_transaction(transaction)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        logger.info(f"Deployment transaction sent: {tx_hash.hex()}")
        
        # Wait for transaction receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status != 1:
            raise Exception(f"Contract deployment failed. Transaction hash: {tx_hash.hex()}")
        
        contract_address = receipt.contractAddress
        logger.info(f"Contract deployed successfully at: {contract_address}")
        logger.info(f"Gas used: {receipt.gasUsed}")
        
        # Save deployment info
        await self._save_deployment_info(contract_address, tx_hash.hex(), receipt.gasUsed, abi)
        
        return contract_address, abi
    
    def _load_contract_artifacts(self, contract_name: str) -> Tuple[str, Dict]:
        """Load contract bytecode and ABI from compiled artifacts"""
        bin_file = self.compiled_dir / f"{contract_name}.bin"
        abi_file = self.compiled_dir / f"{contract_name}.abi"
        
        if not bin_file.exists():
            raise FileNotFoundError(f"Contract bytecode not found: {bin_file}")
            
        if not abi_file.exists():
            raise FileNotFoundError(f"Contract ABI not found: {abi_file}")
        
        # Load bytecode
        bytecode = bin_file.read_text().strip()
        if not bytecode:
            raise ValueError("Contract bytecode is empty")
        
        # Add 0x prefix if not present
        if not bytecode.startswith('0x'):
            bytecode = '0x' + bytecode
            
        # Load ABI
        try:
            abi = json.loads(abi_file.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in ABI file: {e}")
        
        if not abi:
            raise ValueError("Contract ABI is empty")
            
        logger.info(f"Loaded contract artifacts for {contract_name}")
        return bytecode, abi
    
    def _load_contract_abi(self, contract_name: str) -> Dict:
        """Load only the contract ABI"""
        abi_file = self.compiled_dir / f"{contract_name}.abi"
        
        if not abi_file.exists():
            raise FileNotFoundError(f"Contract ABI not found: {abi_file}")
        
        try:
            abi = json.loads(abi_file.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in ABI file: {e}")
            
        return abi
    
    async def _check_deployment_requirements(self):
        """Check if deployment requirements are met"""
        # Check connection
        if not self.w3.is_connected():
            raise Exception("Not connected to blockchain network")
        
        # Check account balance
        balance = self.w3.eth.get_balance(self.account.address)
        balance_eth = self.w3.from_wei(balance, 'ether')
        
        logger.info(f"Deployer account: {self.account.address}")
        logger.info(f"Account balance: {balance_eth} ETH")
        
        if balance == 0:
            raise Exception("Insufficient balance for contract deployment")
        
        # Estimate gas and check if we have enough
        min_balance_wei = self.w3.to_wei('0.01', 'ether')  # Minimum 0.01 ETH
        if balance < min_balance_wei:
            logger.warning(f"Low balance: {balance_eth} ETH. Deployment may fail due to insufficient gas.")
    
    async def _build_deployment_transaction(self, contract) -> Dict:
        """Build deployment transaction with appropriate gas settings"""
        try:
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Build transaction
            transaction = contract.constructor().build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 3000000,  # Generous gas limit for deployment
                'gasPrice': gas_price,
                'chainId': self.w3.eth.chain_id
            })
            
            logger.info(f"Built deployment transaction with gas: {transaction['gas']}, gasPrice: {gas_price}")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to build deployment transaction: {e}")
            raise
    
    async def _verify_contract_deployment(self, address: str, abi: Dict) -> bool:
        """Verify that a contract is properly deployed at the given address"""
        try:
            # Check if address has code
            code = self.w3.eth.get_code(address)
            if code == b'':
                logger.warning(f"No contract code found at address: {address}")
                return False
            
            # Try to create contract instance and call a simple method
            contract = self.w3.eth.contract(address=address, abi=abi)
            
            # Try to call a view function (most contracts have some)
            # This is a basic check - in production, you might want more thorough verification
            logger.info(f"Contract verified at address: {address}")
            return True
            
        except Exception as e:
            logger.warning(f"Contract verification failed for {address}: {e}")
            return False
    
    async def _save_deployment_info(self, contract_address: str, tx_hash: str, gas_used: int, abi: Dict):
        """Save deployment information for future reference"""
        deployment_info = {
            "network": "enclave-local",
            "rpc_url": self.w3.provider.endpoint_uri if hasattr(self.w3.provider, 'endpoint_uri') else "unknown",
            "contract_address": contract_address,
            "deployer": self.account.address,
            "transaction_hash": tx_hash,
            "gas_used": gas_used,
            "chain_id": self.w3.eth.chain_id,
            "deployment_time": self.w3.eth.get_block('latest')['timestamp']
        }
        
        # Save to enclave's data directory
        deployment_file = Path(__file__).parent.parent.parent / "deployment.json"
        try:
            with open(deployment_file, 'w') as f:
                json.dump(deployment_info, f, indent=2)
            logger.info(f"Deployment info saved to: {deployment_file}")
        except Exception as e:
            logger.warning(f"Failed to save deployment info: {e}")
        
        # Also save to config-accessible location
        config_deployment_file = Path("/tmp/enclave_deployment.json")
        try:
            with open(config_deployment_file, 'w') as f:
                json.dump(deployment_info, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save deployment info to config location: {e}")


async def auto_deploy_contracts(w3: Web3, account: Account, config: Dict) -> Tuple[str, Dict]:
    """
    Convenience function for automatic contract deployment during enclave startup
    Returns: (contract_address, contract_abi)
    """
    deployer = ContractDeployer(w3, account, config)
    return await deployer.ensure_contract_deployed()