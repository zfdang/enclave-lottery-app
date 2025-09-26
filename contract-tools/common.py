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
            # getConfig returns 11 values
            publisher_addr, sparsity_addr, operator_addr, publisher_commission, sparsity_commission, min_bet, betting_dur, min_draw_delay, max_draw_delay, min_end_time_ext, min_part = config
            
            # Get current round info (use getRound which returns the LotteryRound struct)
            try:
                current_round_raw = contract.functions.getRound().call()
                # current_round_raw layout follows LotteryRound struct in the contract:
                # [roundId, startTime, endTime, minDrawTime, maxDrawTime, totalPot, participantCount, winner, publisherCommission, sparsityCommission, winnerPrize, state]
                if current_round_raw and len(current_round_raw) >= 12 and current_round_raw[0] > 0:
                    # Normalize to full tuple matching struct order so display code can access all fields
                    current_round = (
                        current_round_raw[0],  # roundId
                        current_round_raw[1],  # startTime
                        current_round_raw[2],  # endTime
                        current_round_raw[3],  # minDrawTime
                        current_round_raw[4],  # maxDrawTime
                        current_round_raw[5],  # totalPot
                        current_round_raw[6],  # participantCount
                        current_round_raw[7],  # winner
                        current_round_raw[8],  # publisherCommission (wei)
                        current_round_raw[9],  # sparsityCommission (wei)
                        current_round_raw[10], # winnerPrize (wei)
                        int(current_round_raw[11]) # state (enum)
                    )
                else:
                    current_round = None
            except Exception:
                current_round = None

            return {
                'is_accessible': True,
                'publisher': publisher_addr,
                'sparsity': sparsity_addr if sparsity_addr != "0x0000000000000000000000000000000000000000" else None,
                'operator': operator_addr if operator_addr != "0x0000000000000000000000000000000000000000" else None,
                'publisher_commission_rate': publisher_commission,
                'sparsity_commission_rate': sparsity_commission,
                'min_bet_wei': min_bet,
                'min_bet_eth': self.w3.from_wei(min_bet, 'ether'),
                'betting_duration': betting_dur,
                'draw_delay': min_draw_delay,
                'max_draw_delay': max_draw_delay,
                'min_end_time_ext': min_end_time_ext,
                'min_participants': min_part,
                'current_round': current_round,
                'error': None
            }
        except Exception as e:
            return {
                'is_accessible': False,
                'error': str(e),
                'publisher': None,
                'sparsity': None,
                'operator': None
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
    admin_config = {}
    if role == "publisher":
        admin_config = load_publisher_config()
    elif role == "sparsity":
        admin_config = load_sparsity_config()
    elif role == "operator":
        from config import load_operator_config
        admin_config = load_operator_config()
    
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
    # Use safe defaults if admin_config is missing keys
    rpc_default = admin_config.get('blockchain', {}).get('rpc_url') if admin_config else None
    pk_default = admin_config.get('blockchain', {}).get('private_key') if admin_config else None
    chain_id_default = admin_config.get('blockchain', {}).get('chain_id') if admin_config else 31337

    parser.add_argument("--rpc-url", default=rpc_default, help="Blockchain RPC URL")
    parser.add_argument("--private-key", default=pk_default, help="Private key")
    parser.add_argument("--chain-id", type=int, default=chain_id_default, help="Chain ID (default: 31337)")
    
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
            if role_filter == 'publisher':
                # Normalize possible None values to empty string before comparing
                pub_addr = (status.get('publisher') or '').lower()
                deployer_addr = (deployment.get('deployer') or '').lower()
                if pub_addr != deployer_addr:
                    continue
            elif role_filter == 'sparsity':
                sparsity_addr = status.get('sparsity', '')
                sparsity_is_set = sparsity_addr and sparsity_addr != '0x0000000000000000000000000000000000000000'
                if not sparsity_is_set:
                    continue
        
        print(f"\n{i}. Contract: {deployment['contract_address']}")
        print(f"   📁 File: {info['file_path']}")
        
        if status.get('is_accessible'):
            # Safe getters with defaults
            publisher_addr = status.get('publisher') or 'Unknown'
            print(f"   📍 Publisher: {publisher_addr}")

            sparsity_status = status.get('sparsity') or "Not set"
            operator_status = status.get('operator') or "Not set"
            print(f"   🔧 Sparsity: {sparsity_status}")
            print(f"   👤 Operator: {operator_status}")

            pub_comm = status.get('publisher_commission_rate')
            spar_comm = status.get('sparsity_commission_rate')
            if pub_comm is not None:
                print(f"   💰 Publisher Commission: {pub_comm / 100}%")
            if spar_comm is not None:
                print(f"   💰 Sparsity Commission: {spar_comm / 100}%")

            # Min bet (ETH)
            min_bet_eth = status.get('min_bet_eth')
            if min_bet_eth is not None:
                print(f"   💸 Min Bet: {min_bet_eth} ETH")
            else:
                print(f"   💸 Min Bet: Unknown")

            # Betting duration in minutes
            betting_duration = status.get('betting_duration', 0)
            print(f"   ⏱️  Betting Duration: {betting_duration // 60} minutes")

            # Draw delay (min/max) and min end time extension
            min_draw = status.get('draw_delay')
            max_draw = status.get('max_draw_delay')
            min_end_ext = status.get('min_end_time_ext')
            if min_draw is not None and max_draw is not None:
                print(f"   ⏳ Draw Delay: {min_draw} - {max_draw} seconds")
            elif min_draw is not None:
                print(f"   ⏳ Draw Delay: {min_draw} seconds")
            if min_end_ext is not None:
                print(f"   🔁 Min End Time Extension: {min_end_ext} seconds")

            # Current round info (normalized to tuple of 6)
            curr = status.get('current_round')
            if curr and isinstance(curr, (list, tuple)) and len(curr) >= 12:
                (round_id, start_time, end_time, min_draw_time, max_draw_time, total_pot, participant_count,
                 winner, pub_comm_wei, spar_comm_wei, winner_prize_wei, state) = curr[:12]
                print(f"   🎯 Current Round: #{round_id}")
                print(f"   👥 Participants: {participant_count}")
                try:
                    pot_eth = w3.from_wei(total_pot, 'ether') if total_pot is not None else '0'
                except Exception:
                    pot_eth = total_pot
                print(f"   💎 Total Pot: {pot_eth} ETH")
                print(f"   🕒 Min Draw Time: {min_draw_time}")
                print(f"   🕒 Max Draw Time: {max_draw_time}")
                print(f"   🏆 Winner: {winner or 'None'}")
                try:
                    pub_comm_eth = w3.from_wei(pub_comm_wei, 'ether') if pub_comm_wei is not None else '0'
                except Exception:
                    pub_comm_eth = pub_comm_wei
                try:
                    spar_comm_eth = w3.from_wei(spar_comm_wei, 'ether') if spar_comm_wei is not None else '0'
                except Exception:
                    spar_comm_eth = spar_comm_wei
                try:
                    winner_prize_eth = w3.from_wei(winner_prize_wei, 'ether') if winner_prize_wei is not None else '0'
                except Exception:
                    winner_prize_eth = winner_prize_wei
                print(f"   💸 Publisher Commission (wei): {pub_comm_wei} ({pub_comm_eth} ETH)")
                print(f"   💸 Sparsity Commission (wei): {spar_comm_wei} ({spar_comm_eth} ETH)")
                print(f"   🏅 Winner Prize (wei): {winner_prize_wei} ({winner_prize_eth} ETH)")
                state_label = {
                    0: 'WAITING',
                    1: 'BETTING',
                    2: 'DRAWING',
                    3: 'COMPLETED',
                    4: 'REFUNDED'
                }.get(int(state), f'UNKNOWN({state})')
                print(f"   🔁 State: {state_label}")
            else:
                print(f"   🎯 Current Round: No active round")
        else:
            print(f"   ❌ Status: Inaccessible ({status['error']})")


def display_contract_details(deployment: Dict[str, Any], status: Dict[str, Any], w3: Web3):
    """Display full contract configuration and current round information.

    deployment: the saved deployment record (from deployment file)
    status: the live status returned by get_contract_status()
    w3: Web3 instance for wei/ether conversions
    """
    print("\n📋 Contract Configuration & Round")
    print("-" * 50)

    contract_address = deployment.get('contract_address')
    deployer = deployment.get('deployer')
    print(f"Contract: {contract_address}")
    if deployer:
        print(f"Deployer: {deployer}")

    if not status or not status.get('is_accessible'):
        print(f"   ❌ Status: Inaccessible ({status.get('error') if status else 'unknown'})")
        return

    # Config fields
    print(f"   📍 Publisher: {status.get('publisher')}")
    print(f"   🔧 Sparsity: {status.get('sparsity') or 'Not set'}")
    print(f"   👤 Operator: {status.get('operator') or 'Not set'}")

    pub_comm = status.get('publisher_commission_rate')
    spar_comm = status.get('sparsity_commission_rate')
    if pub_comm is not None:
        print(f"   💰 Publisher Commission: {pub_comm / 100}%")
    if spar_comm is not None:
        print(f"   💰 Sparsity Commission: {spar_comm / 100}%")

    min_bet_eth = status.get('min_bet_eth')
    if min_bet_eth is not None:
        print(f"   💸 Min Bet: {min_bet_eth} ETH")
    else:
        print(f"   💸 Min Bet: Unknown")

    betting_duration = status.get('betting_duration')
    if betting_duration is not None:
        print(f"   ⏱️  Betting Duration: {betting_duration} seconds ({betting_duration // 60} minutes)")

    min_draw = status.get('draw_delay')
    max_draw = status.get('max_draw_delay')
    if min_draw is not None and max_draw is not None:
        print(f"   ⏳ Draw Delay: {min_draw} - {max_draw} seconds")
    elif min_draw is not None:
        print(f"   ⏳ Draw Delay: {min_draw} seconds")

    min_end_ext = status.get('min_end_time_ext')
    if min_end_ext is not None:
        print(f"   🔁 Min End Time Extension: {min_end_ext} seconds")

    min_part = status.get('min_participants')
    if min_part is not None:
        print(f"   👥 Min Participants: {min_part}")

    # Current round
    curr = status.get('current_round')
    if curr and isinstance(curr, (list, tuple)) and len(curr) >= 12:
        (round_id, start_time, end_time, min_draw_time, max_draw_time, total_pot, participant_count,
         winner, pub_comm_wei, spar_comm_wei, winner_prize_wei, state) = curr[:12]
        print(f"\n   🎯 Current Round: #{round_id}")
        print(f"   🕒 Start Time: {start_time}")
        print(f"   🕒 End Time: {end_time}")
        print(f"   ⏲️  Min Draw Time: {min_draw_time}")
        print(f"   ⏲️  Max Draw Time: {max_draw_time}")
        try:
            pot_eth = w3.from_wei(total_pot, 'ether') if total_pot is not None else '0'
        except Exception:
            pot_eth = total_pot
        print(f"   💎 Total Pot: {pot_eth} ETH")
        print(f"   👥 Participants: {participant_count}")
        print(f"   🏆 Winner: {winner or 'None'}")
        try:
            pub_comm_eth = w3.from_wei(pub_comm_wei, 'ether') if pub_comm_wei is not None else '0'
        except Exception:
            pub_comm_eth = pub_comm_wei
        try:
            spar_comm_eth = w3.from_wei(spar_comm_wei, 'ether') if spar_comm_wei is not None else '0'
        except Exception:
            spar_comm_eth = spar_comm_wei
        try:
            winner_prize_eth = w3.from_wei(winner_prize_wei, 'ether') if winner_prize_wei is not None else '0'
        except Exception:
            winner_prize_eth = winner_prize_wei
        print(f"   💸 Publisher Commission (wei): {pub_comm_wei} ({pub_comm_eth} ETH)")
        print(f"   💸 Sparsity Commission (wei): {spar_comm_wei} ({spar_comm_eth} ETH)")
        print(f"   🏅 Winner Prize (wei): {winner_prize_wei} ({winner_prize_eth} ETH)")
        state_label = {
            0: 'WAITING',
            1: 'BETTING',
            2: 'DRAWING',
            3: 'COMPLETED',
            4: 'REFUNDED'
        }.get(int(state), f'UNKNOWN({state})')
        print(f"   🔁 State: {state_label}")
    else:
        print(f"\n   🎯 Current Round: No active round")

    print("-" * 50)
