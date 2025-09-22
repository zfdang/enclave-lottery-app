#!/usr/bin/env python3
"""
Shared utilities for lottery contract management tools
Common functionality for publisher.py and sparsity.py
"""

import json
import os
import sys
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional

from web3 import Web3
from eth_account import Account
import solcx

# Import admin config from local config module
sys.path.insert(0, str(Path(__file__).parent))
from config import load_publisher_config, load_sparsity_config


def load_generic_config() -> Dict[str, Any]:
    """Load generic configuration with basic defaults"""
    return {
        "blockchain": {
            "rpc_url": "http://localhost:8545",
            "private_key": "0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6",
            "chain_id": 31337
        }
    }


def validate_ethereum_address(address: str) -> bool:
    """Validate Ethereum address format"""
    if not address:
        return False
    
    # Check basic format
    if not address.startswith('0x') or len(address) != 42:
        return False
    
    # Check if it's valid hex
    try:
        int(address[2:], 16)
        return True
    except ValueError:
        return False


class LotteryContractBase:
    """Base class for lottery contract management tools"""
    
    def __init__(self, rpc_url: str, private_key: str, chain_id: int):
        """Initialize the manager with blockchain connection"""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise Exception(f"Failed to connect to blockchain at {rpc_url}")
        
        self.account = Account.from_key(private_key)
        self.chain_id = chain_id
        
        print(f"✅ Connected to blockchain")
        print(f"📍 Account address: {self.account.address}")
        balance = self.w3.eth.get_balance(self.account.address)
        print(f"💰 Balance: {self.w3.from_wei(balance, 'ether')} ETH")

    def get_contract_instance(self, contract_address: str, abi: List[Dict[str, Any]]):
        """Get a contract instance for interaction"""
        return self.w3.eth.contract(address=contract_address, abi=abi)

    def _load_contract_abi(self) -> List[Dict[str, Any]]:
        """Load contract ABI from compiled contract"""
        contract_interface = self.compile_contract()
        return contract_interface['abi']

    def compile_contract(self) -> Dict[str, Any]:
        """Compile the Lottery contract and return interface"""
        # Set up Solidity compiler
        try:
            solcx.install_solc('0.8.19')
        except:
            pass  # Already installed
        
        solcx.set_solc_version('0.8.19')
        
        # Find contract file
        contract_path = Path(__file__).parent.parent / "contracts" / "Lottery.sol"
        if not contract_path.exists():
            raise FileNotFoundError(f"Contract file not found: {contract_path}")
        
        # Compile contract
        result = solcx.compile_files([str(contract_path)], output_values=['abi', 'bin'], optimize=True)
        contract_interface = result[f'{contract_path}:Lottery']
        
        return contract_interface

    def find_deployment_files(self) -> List[Dict[str, Any]]:
        """Find all deployment files and load contract information"""
        deployment_files = []
        
        # Search admin directory first (preferred location)
        admin_dir = Path(__file__).parent
        admin_files = glob.glob(str(admin_dir / "deployment_*.json"))
        
        # Also search in deployments subdirectory
        deployments_dir = admin_dir / "deployments"
        if deployments_dir.exists():
            deployment_subdir_files = glob.glob(str(deployments_dir / "deployment_*.json"))
            admin_files.extend(deployment_subdir_files)

        # Also search in admin/deployments subdirectory (for compatibility)
        admin_deployments_dir = admin_dir / "admin" / "deployments"
        if admin_deployments_dir.exists():
            admin_deployment_files = glob.glob(str(admin_deployments_dir / "deployment_*.json"))
            admin_files.extend(admin_deployment_files)
        
        for file_path in sorted(admin_files, reverse=True):  # Most recent first
            try:
                with open(file_path, 'r') as f:
                    deployment_data = json.load(f)
                
                deployment_files.append({
                    'file_path': file_path,
                    'deployment': deployment_data
                })
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"⚠️  Warning: Could not load {file_path}: {e}")
                continue
        
        return deployment_files

    def get_contract_status(self, contract_address: str, abi: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get current status of a deployed contract"""
        try:
            contract = self.get_contract_instance(contract_address, abi)
            
            # Get configuration
            config = contract.functions.getConfig().call()
            publisher_addr, sparsity_addr, operator_addr, publisher_commission, sparsity_commission, min_bet, betting_dur, draw_delay, min_part, sparsity_is_set = config
            
            # Get current round info
            try:
                current_round = contract.functions.getCurrentRound().call()
                round_id, start_time, end_time, draw_time, total_pot, participant_count, winner, pub_comm, spar_comm, winner_prize, completed, cancelled, refunded = current_round
            except:
                current_round = None
            
            return {
                'is_accessible': True,
                'publisher': publisher_addr,
                'sparsity': sparsity_addr if sparsity_addr != "0x0000000000000000000000000000000000000000" else None,
                'operator': operator_addr if operator_addr != "0x0000000000000000000000000000000000000000" else None,
                'sparsity_set': sparsity_is_set,
                'publisher_commission_rate': publisher_commission,
                'sparsity_commission_rate': sparsity_commission,
                'min_bet_wei': min_bet,
                'min_bet_eth': self.w3.from_wei(min_bet, 'ether'),
                'betting_duration': betting_dur,
                'draw_delay': draw_delay,
                'min_participants': min_part,
                'current_round': current_round[:6] if current_round and current_round[0] > 0 else None,
                'error': None
            }
        except Exception as e:
            return {
                'is_accessible': False,
                'error': str(e),
                'publisher': None,
                'sparsity': None,
                'operator': None,
                'sparsity_set': False
            }

    def query_all_contracts(self) -> List[Dict[str, Any]]:
        """Query all deployed contracts and return their status"""
        deployment_files = self.find_deployment_files()
        
        if not deployment_files:
            print("📭 No deployment files found")
            return []
        
        contracts_info = []
        for info in deployment_files:
            deployment = info['deployment']
            contract_address = deployment['contract_address']
            
            # Load ABI from deployment file or compile fresh
            abi = deployment.get('abi') or self._load_contract_abi()
            
            # Get contract status
            status = self.get_contract_status(contract_address, abi)
            
            contracts_info.append({
                'file_path': info['file_path'],
                'deployment': deployment,
                'status': status,
                'abi': abi
            })
        
        return contracts_info

    def send_transaction(self, transaction_data: Dict[str, Any]) -> str:
        """Send a transaction and wait for confirmation"""
        # Sign transaction
        signed_txn = self.w3.eth.account.sign_transaction(transaction_data, private_key=self.account.key)
        
        # Send transaction
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        print(f"⏳ Transaction sent: {tx_hash.hex()}")
        
        # Wait for confirmation
        print("⏳ Waiting for confirmation...")
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if tx_receipt.status == 1:
            return tx_hash.hex()
        else:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")

    def send_eth(self, to_address: str, amount_eth: float) -> str:
        """Send ETH to an address"""
        if not validate_ethereum_address(to_address):
            raise ValueError("Invalid recipient address")
        
        amount_wei = self.w3.to_wei(amount_eth, 'ether')
        
        # Check balance
        balance = self.w3.eth.get_balance(self.account.address)
        if balance < amount_wei:
            raise ValueError(f"Insufficient balance. Have: {self.w3.from_wei(balance, 'ether')} ETH, Need: {amount_eth} ETH")
        
        # Build transaction
        transaction = {
            'to': to_address,
            'value': amount_wei,
            'gas': 21000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        }
        
        return self.send_transaction(transaction)


def create_argument_parser(tool_name: str, description: str, role: str = None):
    """Create a common argument parser for lottery tools"""
    import argparse
    
    # Load role-specific configuration using dedicated methods
    if role == "publisher":
        admin_config = load_publisher_config()
    elif role == "sparsity":
        admin_config = load_sparsity_config()
    
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {tool_name} --help                    Show this help
  {tool_name}                          Interactive mode
  {tool_name} --query                  Query contracts
        """
    )
    
    print(f"🎲 {description}")
    print("=" * 40)
    
    # Blockchain configuration
    parser.add_argument("--rpc-url", default=admin_config['blockchain']['rpc_url'], help="Blockchain RPC URL")
    parser.add_argument("--private-key", default=admin_config['blockchain']['private_key'], help="Private key")
    parser.add_argument("--chain-id", type=int, default=admin_config['blockchain']['chain_id'], help="Chain ID (default: 31337)")
    
    return parser, admin_config


def display_contracts_table(contracts_info: List[Dict[str, Any]], w3: Web3, role_filter: str = None):
    """Display contracts in a formatted table, optionally filtered by role"""
    if not contracts_info:
        print("📭 No contracts found")
        return
    
    print(f"\n🎲 Deployed Lottery Contracts")
    print("=" * 50)
    
    for i, info in enumerate(contracts_info, 1):
        deployment = info['deployment']
        status = info['status']
        
        # Apply role filter if specified
        if role_filter:
            if role_filter == 'publisher' and status.get('publisher', '').lower() != deployment.get('deployer', '').lower():
                continue
            elif role_filter == 'sparsity' and not status.get('sparsity_set', False):
                continue
        
        print(f"\n{i}. Contract: {deployment['contract_address']}")
        print(f"   📁 File: {info['file_path']}")
        
        if status['is_accessible']:
            publisher_addr = status['publisher'] or 'Unknown'
            print(f"   📍 Publisher: {publisher_addr}")
            
            sparsity_status = status['sparsity'] or "Not set"
            operator_status = status['operator'] or "Not set"
            print(f"   🔧 Sparsity: {sparsity_status}")
            print(f"   👤 Operator: {operator_status}")
            print(f"   💰 Publisher Commission: {status['publisher_commission_rate'] / 100}%")
            print(f"   💰 Sparsity Commission: {status['sparsity_commission_rate'] / 100}%")
            print(f"   💸 Min Bet: {status['min_bet_eth']} ETH")
            print(f"   ⏱️  Betting Duration: {status['betting_duration'] // 60} minutes")
            print(f"   ⏳ Draw Delay: {status['draw_delay']} seconds")
            
            if status['current_round']:
                round_id, start_time, end_time, draw_time, total_pot, participant_count = status['current_round']
                print(f"   🎯 Current Round: #{round_id}")
                print(f"   👥 Participants: {participant_count}")
                print(f"   💎 Total Pot: {w3.from_wei(total_pot, 'ether')} ETH")
            else:
                print(f"   🎯 Current Round: No active round")
        else:
            print(f"   ❌ Status: Inaccessible ({status['error']})")
