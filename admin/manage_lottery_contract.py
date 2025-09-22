#!/usr/bin/env python3
"""
Lottery Contract Management Tool
Admin tool for deploying, querying, and managing lottery contracts
"""

import argparse
import json
import os
import sys
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add src to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "enclave" / "src"))

from web3 import Web3
from eth_account import Account
import solcx

# Import admin config from local config module
sys.path.insert(0, str(Path(__file__).parent))
from config import load_admin_config


class LotteryManager:
    def __init__(self, rpc_url: str, private_key: str, chain_id: int):
        """Initialize the manager with blockchain connection"""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise Exception(f"Failed to connect to blockchain at {rpc_url}")
        
        self.account = Account.from_key(private_key)
        self.chain_id = chain_id
        self.project_root = Path(__file__).parent.parent
        
        # Set default account
        self.w3.eth.default_account = self.account.address
        
        print(f"✅ Connected to blockchain")
        print(f"📍 Admin address: {self.account.address}")
        print(f"💰 Balance: {self.w3.from_wei(self.w3.eth.get_balance(self.account.address), 'ether')} ETH")
    
    def find_deployment_files(self) -> List[str]:
        """Find all deployment*.json files in project, admin folder, and subdirectories"""
        deployment_files = []
        
        # Search patterns - prioritize admin folder
        patterns = [
            str(self.project_root / "admin" / "deployment*.json"),
            str(self.project_root / "deployment*.json"),
            str(self.project_root / "**/deployment*.json"),
        ]
        
        for pattern in patterns:
            files = glob.glob(pattern, recursive=True)
            deployment_files.extend(files)
        
        # Remove duplicates and sort (admin folder first)
        deployment_files = sorted(list(set(deployment_files)), key=lambda x: (not x.startswith(str(self.project_root / "admin")), x))
        
        print(f"🔍 Found {len(deployment_files)} deployment files")
        return deployment_files
    
    def load_deployment_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load deployment information from JSON file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"⚠️  Error loading {file_path}: {e}")
            return None
    
    def get_contract_instance(self, contract_address: str, abi: List[Dict]) -> Any:
        """Create contract instance"""
        return self.w3.eth.contract(address=contract_address, abi=abi)
    
    def query_contract_status(self, contract_address: str, abi: List[Dict]) -> Dict[str, Any]:
        """Query current contract status from blockchain"""
        try:
            contract = self.get_contract_instance(contract_address, abi)
            
            # Get configuration
            config = contract.functions.getConfig().call()
            admin_addr, operator_addr, commission_rate, min_bet, betting_dur, draw_delay, min_part = config
            
            # Get current round info
            try:
                current_round = contract.functions.getCurrentRound().call()
                round_id, start_time, end_time, status, participant_count, total_bets = current_round
            except:
                current_round = None
            
            return {
                'admin': admin_addr,
                'operator': operator_addr if operator_addr != "0x0000000000000000000000000000000000000000" else None,
                'commission_rate': commission_rate,
                'min_bet_wei': min_bet,
                'min_bet_eth': self.w3.from_wei(min_bet, 'ether'),
                'betting_duration': betting_dur,
                'draw_delay': draw_delay,
                'min_participants': min_part,
                'current_round': current_round,
                'is_accessible': True
            }
        except Exception as e:
            return {
                'error': str(e),
                'is_accessible': False
            }
    
    def display_contracts(self, contracts_info: List[Dict[str, Any]]):
        """Display formatted list of contracts"""
        print("\n🎲 Deployed Lottery Contracts")
        print("=" * 50)
        
        if not contracts_info:
            print("No contracts found.")
            return
        
        for i, info in enumerate(contracts_info, 1):
            deployment = info['deployment']
            status = info['status']
            
            print(f"\n{i}. Contract: {deployment['contract_address']}")
            print(f"   📁 File: {info['file_path']}")
            admin_addr = deployment.get('admin_address') or deployment.get('deployer') or 'Unknown'
            print(f"   📍 Admin: {admin_addr}")
            
            if status['is_accessible']:
                operator_status = status['operator'] or "Not set"
                print(f"   👤 Operator: {operator_status}")
                print(f"   💰 Commission: {status['commission_rate'] / 100}%")
                print(f"   💸 Min Bet: {status['min_bet_eth']} ETH")
                print(f"   ⏱️  Betting Duration: {status['betting_duration'] // 60} minutes")
                print(f"   ⏳ Draw Delay: {status['draw_delay']} seconds")
                
                if status['current_round']:
                    round_id, start_time, end_time, round_status, participant_count, total_bets = status['current_round']
                    print(f"   🎯 Current Round: #{round_id} (Status: {round_status})")
                    print(f"   👥 Participants: {participant_count}")
                    print(f"   💎 Total Bets: {self.w3.from_wei(total_bets, 'ether')} ETH")
                else:
                    print(f"   🎯 Current Round: No active round")
            else:
                print(f"   ❌ Status: Inaccessible ({status['error']})")
    
    def set_operator_interactive(self, contracts_info: List[Dict[str, Any]]):
        """Interactive operator setting"""
        if not contracts_info:
            print("❌ No contracts available for operator management")
            return
        
        # Display contracts
        self.display_contracts(contracts_info)
        
        # Get user selection
        try:
            print(f"\nSelect contract (1-{len(contracts_info)}):")
            choice = int(input("Enter number: ")) - 1
            
            if choice < 0 or choice >= len(contracts_info):
                print("❌ Invalid selection")
                return
            
            selected = contracts_info[choice]
            
            if not selected['status']['is_accessible']:
                print("❌ Cannot manage inaccessible contract")
                return
                
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Invalid input or cancelled")
            return
        
        # Get operator address
        try:
            print(f"\nSelected: {selected['deployment']['contract_address']}")
            current_operator = selected['status']['operator']
            if current_operator:
                print(f"Current operator: {current_operator}")
            
            operator_address = input("Enter new operator address: ").strip()
            
            if not operator_address:
                print("❌ No operator address provided")
                return
                
            # Basic validation
            if not operator_address.startswith('0x') or len(operator_address) != 42:
                print("❌ Invalid Ethereum address format")
                return
                
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
            return
        
        # Execute transaction
        try:
            self.set_operator(
                contract_address=selected['deployment']['contract_address'],
                abi=selected['deployment'].get('abi') or self._load_contract_abi(),
                operator_address=operator_address,
                deployment_file=selected['file_path']
            )
        except Exception as e:
            print(f"❌ Failed to set operator: {e}")
    
    def set_operator(self, contract_address: str, abi: List[Dict], operator_address: str, deployment_file: str):
        """Set operator for specific contract"""
        print(f"\n🔧 Setting operator for contract {contract_address}")
        print(f"👤 New operator: {operator_address}")
        
        # Create contract instance
        contract = self.get_contract_instance(contract_address, abi)
        
        # Build transaction
        set_operator_txn = contract.functions.setOperator(operator_address).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })
        
        # Sign and send transaction
        signed_txn = self.w3.eth.account.sign_transaction(set_operator_txn, private_key=self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        print(f"⏳ Transaction sent: {tx_hash.hex()}")
        print("⏳ Waiting for confirmation...")
        
        # Wait for confirmation
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt.status != 1:
            raise Exception("Transaction failed")
        
        print("✅ Operator set successfully!")
        
        # Update deployment file
        self._update_deployment_file(deployment_file, operator_address)
    
    def _update_deployment_file(self, file_path: str, operator_address: str):
        """Update deployment file with new operator address"""
        try:
            deployment_info = self.load_deployment_info(file_path)
            if deployment_info:
                deployment_info['operator_address'] = operator_address
                deployment_info['last_updated'] = int(__import__('time').time())
                
                with open(file_path, 'w') as f:
                    json.dump(deployment_info, f, indent=2)
                
                print(f"📝 Updated deployment file: {file_path}")
        except Exception as e:
            print(f"⚠️  Could not update deployment file: {e}")
    
    def _load_contract_abi(self) -> List[Dict]:
        """Load contract ABI from compiled contract or source"""
        # Try to compile contract to get ABI
        try:
            contract_interface = self.compile_contract()
            return contract_interface['abi']
        except Exception as e:
            print(f"⚠️  Could not load contract ABI: {e}")
            return []
    
    def compile_contract(self) -> Dict[str, Any]:
        """Compile the Lottery.sol contract"""
        print("🔨 Compiling Lottery contract...")
        
        # Path to contract file
        contract_path = Path(__file__).parent.parent / "contracts" / "Lottery.sol"
        
        if not contract_path.exists():
            raise Exception(f"Contract file not found: {contract_path}")
        
        # Install solc if needed
        try:
            solcx.get_installed_solc_versions()
        except:
            print("📦 Installing solc compiler...")
            solcx.install_solc('0.8.19')
        
        # Set solc version
        solcx.set_solc_version('0.8.19')
        
        # Compile the contract
        compiled = solcx.compile_files([str(contract_path)])
        contract_id = list(compiled.keys())[0]
        contract_interface = compiled[contract_id]
        
        print("✅ Contract compiled successfully")
        return contract_interface
    
    def deploy_contract(self, 
                       contract_interface: Dict[str, Any],
                       commission_rate: int,
                       min_bet_amount: float,
                       betting_duration: int,
                       draw_delay: int) -> Dict[str, Any]:
        """Deploy the lottery contract with configuration"""
        
        print("🚀 Deploying Lottery contract...")
        
        # Convert parameters
        min_bet_wei = self.w3.to_wei(min_bet_amount, 'ether')
        
        # Validate parameters
        if commission_rate > 1000:  # Max 10%
            raise ValueError("Commission rate too high (max 10 percent)")
        if betting_duration < 300:  # Min 5 minutes
            raise ValueError("Betting duration too short (min 5 minutes)")
        if draw_delay < 60:  # Min 1 minute
            raise ValueError("Draw delay too short (min 1 minute)")
        
        # Create contract factory
        contract_factory = self.w3.eth.contract(
            abi=contract_interface['abi'],
            bytecode=contract_interface['bin']
        )
        
        # Build constructor transaction
        constructor_txn = contract_factory.constructor(
            commission_rate,
            min_bet_wei,
            betting_duration,
            draw_delay
        ).build_transaction({
            'from': self.account.address,
            'gas': 4000000,  # Adequate gas limit for deployment
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })
        
        # Sign and send transaction
        signed_txn = self.w3.eth.account.sign_transaction(constructor_txn, private_key=self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        print(f"⏳ Waiting for deployment transaction: {tx_hash.hex()}")
        
        # Wait for transaction receipt
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt.status != 1:
            raise Exception("Contract deployment failed")
        
        contract_address = tx_receipt.contractAddress
        print(f"✅ Contract deployed at: {contract_address}")
        
        # Create contract instance
        contract = self.w3.eth.contract(
            address=contract_address,
            abi=contract_interface['abi']
        )
        
        print(f"ℹ️  Contract deployed without operator - use management tool to set operator later")
        
        return {
            'address': contract_address,
            'abi': contract_interface['abi'],
            'contract': contract,
            'tx_hash': tx_hash.hex(),
            'block_number': tx_receipt.blockNumber
        }
    
    def verify_deployment(self, contract_info: Dict[str, Any], expected_params: Dict[str, Any]):
        """Verify the deployed contract configuration"""
        print("🔍 Verifying contract deployment...")
        
        contract = contract_info['contract']
        
        # Get configuration from contract
        config = contract.functions.getConfig().call()
        admin_addr, operator_addr, commission_rate, min_bet, betting_dur, draw_delay, min_part = config
        
        # Verify parameters
        assert admin_addr.lower() == self.account.address.lower(), "Admin address mismatch"
        
        # Operator should always be zero address after deployment
        assert operator_addr == "0x0000000000000000000000000000000000000000", "Operator should not be set during deployment"
        
        assert commission_rate == expected_params['commission_rate'], "Commission rate mismatch"
        assert min_bet == expected_params['min_bet_wei'], "Min bet amount mismatch"
        assert betting_dur == expected_params['betting_duration'], "Betting duration mismatch"
        assert draw_delay == expected_params['draw_delay'], "Draw delay mismatch"
        assert min_part == 2, "Min participants should be 2"
        
        print("✅ Contract configuration verified")
        
        # Display configuration
        print("\n📋 Contract Configuration:")
        print(f"   Admin: {admin_addr}")
        print(f"   Operator: Not set (use management tool to set)")
        print(f"   Commission Rate: {commission_rate / 100}%")
        print(f"   Min Bet Amount: {self.w3.from_wei(min_bet, 'ether')} ETH")
        print(f"   Betting Duration: {betting_dur} seconds ({betting_dur // 60} minutes)")
        print(f"   Draw Delay: {draw_delay} seconds ({draw_delay // 60} minutes)")
        print(f"   Min Participants: {min_part}")
    
    def generate_operator_config(self, contract_info: Dict[str, Any], output_path: str):
        """Generate operator configuration file for enclave application"""
        print("📝 Generating operator configuration file...")
        
        config = {
            "contract": {
                "address": contract_info['address'],
                "abi": contract_info['abi'],
                "deployment_block": contract_info['block_number']
            },
            "blockchain": {
                "rpc_url": str(self.w3.provider.endpoint_uri),
                "chain_id": self.chain_id
            },
            "operator": {
                "role": "operator",
                "auto_start_rounds": True,
                "round_check_interval": 30,  # seconds
                "note": "Operator address must be set via management tool before use"
            }
        }
        
        # Ensure directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:  # Only create directory if path has a directory component
            os.makedirs(output_dir, exist_ok=True)
        
        # Write configuration file
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Operator config saved to: {output_path}")
        print(f"💡 Copy this file to enclave/config/ when starting operator service")
        print(f"⚠️  Remember: Set operator address using management tool before starting operator")
        
        return config


def parse_arguments():
    """Parse command line arguments"""
    # Load admin configuration for defaults
    admin_config = load_admin_config()
    
    parser = argparse.ArgumentParser(description="Manage Lottery contracts - deploy, query, and set operators")
    
    # Blockchain connection
    parser.add_argument("--rpc-url", default=admin_config['blockchain']['rpc_url'], help="Blockchain RPC URL")
    parser.add_argument("--private-key", default=admin_config['blockchain']['private_key'], help="Admin private key")
    parser.add_argument("--chain-id", type=int, default=admin_config['blockchain']['chain_id'], help=f"Chain ID (default: {admin_config['blockchain']['chain_id']})")
    
    # Operation modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--query", action="store_true", help="Query deployed contracts and exit")
    mode_group.add_argument("--set-operator", action="store_true", help="Set operator for a contract")
    mode_group.add_argument("--deploy", action="store_true", help="Deploy new contract")
    mode_group.add_argument("--interactive", action="store_true", default=True, help="Interactive mode (default)")
    
    # Contract configuration
    parser.add_argument("--commission-rate", type=int, default=admin_config['contract']['commission_rate'], help=f"Admin commission rate in basis points (default: {admin_config['contract']['commission_rate']} = {admin_config['contract']['commission_rate']/100}%%)")
    parser.add_argument("--min-bet", type=float, default=admin_config['contract']['min_bet'], help=f"Minimum bet amount in ETH (default: {admin_config['contract']['min_bet']})")
    parser.add_argument("--betting-duration", type=int, default=admin_config['contract']['betting_duration'], help=f"Betting duration in seconds (default: {admin_config['contract']['betting_duration']} = {admin_config['contract']['betting_duration']//60} minutes)")
    parser.add_argument("--draw-delay", type=int, default=admin_config['contract']['draw_delay'], help=f"Draw delay after betting ends in seconds (default: {admin_config['contract']['draw_delay']} = {admin_config['contract']['draw_delay']//60:.1f} minutes)")
    
    # Output configuration
    parser.add_argument("--config-output", default=admin_config['output']['config_output'], help="Output path for operator config")
    parser.add_argument("--deployment-output", default=admin_config['output']['deployment_output'], help="Output path for deployment info")
    
    # Specific contract for set-operator mode
    parser.add_argument("--contract", help="Contract address for set-operator mode")
    
    return parser.parse_args()


def interactive_menu(manager: LotteryManager):
    """Interactive menu system"""
    while True:
        print("\n🎲 Lottery Contract Manager")
        print("=" * 30)
        print("1. Query deployed contracts")
        print("2. Set operator for contract")
        print("3. Deploy new contract")
        print("4. Exit")
        
        try:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                # Query contracts
                contracts_info = query_all_contracts(manager)
                manager.display_contracts(contracts_info)
                
            elif choice == "2":
                # Set operator
                contracts_info = query_all_contracts(manager)
                manager.set_operator_interactive(contracts_info)
                
            elif choice == "3":
                # Deploy new contract
                deploy_new_contract(manager)
                
            elif choice == "4":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid option. Please select 1-4.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def query_all_contracts(manager: LotteryManager) -> List[Dict[str, Any]]:
    """Query all deployed contracts"""
    deployment_files = manager.find_deployment_files()
    contracts_info = []
    
    for file_path in deployment_files:
        deployment_info = manager.load_deployment_info(file_path)
        if deployment_info and 'contract_address' in deployment_info:
            # Load ABI from deployment info or compile contract
            abi = deployment_info.get('abi')
            if not abi:
                try:
                    contract_interface = manager.compile_contract()
                    abi = contract_interface['abi']
                    # Update deployment file with ABI if missing
                    deployment_info['abi'] = abi
                    with open(file_path, 'w') as f:
                        json.dump(deployment_info, f, indent=2)
                except:
                    abi = []
            
            status = manager.query_contract_status(deployment_info['contract_address'], abi)
            
            contracts_info.append({
                'file_path': file_path,
                'deployment': deployment_info,
                'status': status
            })
    
    return contracts_info


def deploy_new_contract(manager: LotteryManager):
    """Deploy new contract using configuration defaults"""
    print("\n🚀 Deploy New Lottery Contract")
    print("=" * 35)
    
    try:
        # Load admin config for deployment parameters
        admin_config = load_admin_config()
        
        # Use configuration defaults directly
        commission_rate = admin_config['contract']['commission_rate']
        min_bet = admin_config['contract']['min_bet']
        betting_duration = admin_config['contract']['betting_duration']
        draw_delay = admin_config['contract']['draw_delay']
        
        print("📋 Using configuration defaults:")
        print(f"   💰 Commission rate: {commission_rate} basis points ({commission_rate/100}%)")
        print(f"   💸 Minimum bet: {min_bet} ETH")
        print(f"   ⏱️  Betting duration: {betting_duration} seconds ({betting_duration//60} minutes)")
        print(f"   ⏳ Draw delay: {draw_delay} seconds ({draw_delay//60:.1f} minutes)")
        
        # Deploy contract
        print("\n🔨 Compiling and deploying contract...")
        contract_interface = manager.compile_contract()
        contract_info = manager.deploy_contract(
            contract_interface=contract_interface,
            commission_rate=commission_rate,
            min_bet_amount=min_bet,
            betting_duration=betting_duration,
            draw_delay=draw_delay
        )
        
        # Verify deployment
        expected_params = {
            'commission_rate': commission_rate,
            'min_bet_wei': manager.w3.to_wei(min_bet, 'ether'),
            'betting_duration': betting_duration,
            'draw_delay': draw_delay
        }
        manager.verify_deployment(contract_info, expected_params)
        
        # Generate operator config
        config_output = admin_config['output']['config_output']
        manager.generate_operator_config(contract_info, config_output)
        
        # Save deployment info to admin folder
        timestamp = int(__import__('time').time())
        deployment_output = f"admin/deployment_{timestamp}.json"
        deployment_info = {
            'contract_address': contract_info['address'],
            'admin_address': manager.account.address,
            'operator_address': None,
            'deployment_tx': contract_info['tx_hash'],
            'deployment_block': contract_info['block_number'],
            'abi': contract_info['abi'],
            'configuration': {
                'commission_rate': commission_rate,
                'min_bet_eth': min_bet,
                'betting_duration_seconds': betting_duration,
                'draw_delay_seconds': draw_delay
            },
            'timestamp': int(__import__('time').time())
        }
        
        # Ensure admin directory exists
        os.makedirs(os.path.dirname(deployment_output), exist_ok=True)
        
        with open(deployment_output, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"✅ Deployment info saved to: {deployment_output}")
        print("\n🎉 Deployment completed successfully!")
        
    except KeyboardInterrupt:
        print("\n❌ Deployment cancelled")
    except Exception as e:
        print(f"❌ Deployment failed: {e}")


def main():
    """Main function"""
    print("🎲 Lottery Contract Management Tool")
    print("=" * 40)
    
    try:
        args = parse_arguments()
        
        # Initialize manager
        manager = LotteryManager(
            rpc_url=args.rpc_url,
            private_key=args.private_key,
            chain_id=args.chain_id
        )
        
        # Handle different modes
        if args.query:
            # Query mode
            contracts_info = query_all_contracts(manager)
            manager.display_contracts(contracts_info)
            
        elif args.set_operator:
            # Set operator mode
            contracts_info = query_all_contracts(manager)
            if args.contract:
                # Specific contract provided
                target_contract = None
                for info in contracts_info:
                    if info['deployment']['contract_address'].lower() == args.contract.lower():
                        target_contract = info
                        break
                
                if not target_contract:
                    print(f"❌ Contract {args.contract} not found in deployment files")
                    return
                
                operator_address = input(f"Enter operator address for {args.contract}: ").strip()
                if operator_address:
                    manager.set_operator(
                        contract_address=target_contract['deployment']['contract_address'],
                        abi=target_contract['deployment'].get('abi') or manager._load_contract_abi(),
                        operator_address=operator_address,
                        deployment_file=target_contract['file_path']
                    )
            else:
                # Interactive selection
                manager.set_operator_interactive(contracts_info)
                
        elif args.deploy:
            # Deploy mode - use existing deployment logic
            deploy_new_contract(manager)
            
        else:
            # Interactive mode (default)
            interactive_menu(manager)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()