#!/usr/bin/env python3
"""
Publisher Tool
Contract deployment and sparsity management for lottery contracts
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from common import (
    LotteryContractBase, 
    create_argument_parser, 
    display_contracts_table,
    validate_ethereum_address
)


class PublisherManager(LotteryContractBase):
    """Publisher-specific contract management"""
    
    def deploy_contract(self, 
                       contract_interface: Dict[str, Any],
                       publisher_commission_rate: int,
                       sparsity_commission_rate: int) -> Dict[str, Any]:
        """Deploy the lottery contract with configuration"""
        
        print("🚀 Deploying Lottery contract...")
        
        # Validate parameters
        if publisher_commission_rate > 500:  # Max 5%
            raise ValueError("Publisher commission rate too high (max 5 percent)")
        if sparsity_commission_rate > 500:  # Max 5%
            raise ValueError("Sparsity commission rate too high (max 5 percent)")
        if publisher_commission_rate + sparsity_commission_rate > 1000:  # Max 10% total
            raise ValueError("Total commission rate too high (max 10 percent)")
        
        # Create contract factory
        contract_factory = self.w3.eth.contract(
            abi=contract_interface['abi'],
            bytecode=contract_interface['bin']
        )
        
        # Build constructor transaction
        constructor_txn = contract_factory.constructor(
            publisher_commission_rate,
            sparsity_commission_rate
        ).build_transaction({
            'from': self.account.address,
            'gas': 4000000,  # Adequate gas limit for deployment
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })
        
        # Sign and send transaction
        tx_hash = self.send_transaction(constructor_txn)
        
        # Get deployment receipt
        tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        contract_address = tx_receipt.contractAddress
        
        print(f"✅ Contract deployed at: {contract_address}")
        
        # Create contract info
        contract_info = {
            'contract_address': contract_address,
            'deployer': self.account.address,
            'publisher_address': self.account.address,
            'transaction_hash': tx_hash,
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'timestamp': int(time.time()),
            'abi': contract_interface['abi']
        }
        
        return contract_info

    def verify_deployment(self, contract_info: Dict[str, Any], expected_params: Dict[str, Any]):
        """Verify the deployed contract configuration"""
        print("🔍 Verifying deployment...")
        
        contract_address = contract_info['contract_address']
        abi = contract_info['abi']
        contract = self.get_contract_instance(contract_address, abi)
        
        # Get configuration from contract
        config = contract.functions.getConfig().call()
        publisher_addr, sparsity_addr, operator_addr, publisher_commission, sparsity_commission, min_bet, betting_dur, draw_delay, min_part, sparsity_is_set = config
        
        # Verify parameters
        assert publisher_addr.lower() == self.account.address.lower(), "Publisher address mismatch"
        
        # Sparsity and operator should not be set during deployment
        assert sparsity_addr == "0x0000000000000000000000000000000000000000", "Sparsity should not be set during deployment"
        assert operator_addr == "0x0000000000000000000000000000000000000000", "Operator should not be set during deployment"
        assert not sparsity_is_set, "Sparsity flag should be false during deployment"
        
        assert publisher_commission == expected_params['publisher_commission_rate'], "Publisher commission rate mismatch"
        assert sparsity_commission == expected_params['sparsity_commission_rate'], "Sparsity commission rate mismatch"
        
        print("✅ Contract configuration verified")
        
        # Display configuration
        print("\n📋 Contract Configuration:")
        print(f"   Publisher: {publisher_addr}")
        print(f"   Sparsity: Not set (use setSparsity function)")
        print(f"   Operator: Not set (sparsity will set later)")
        print(f"   Publisher Commission: {publisher_commission / 100}%")
        print(f"   Sparsity Commission: {sparsity_commission / 100}%")
        print(f"   Min Bet Amount: {self.w3.from_wei(min_bet, 'ether')} ETH (operator-managed)")
        print(f"   Betting Duration: {betting_dur} seconds ({betting_dur // 60} minutes) (operator-managed)")
        print(f"   Draw Delay: {draw_delay} seconds ({draw_delay // 60} minutes) (operator-managed)")
        print(f"   Min Participants: {min_part}")

    def save_deployment(self, contract_info: Dict[str, Any], output_path: str):
        """Save deployment information to file"""
        timestamp = int(time.time())
        filename = f"deployment_{timestamp}.json"
        
        # Ensure the output directory exists
        output_dir = Path(output_path).parent if Path(output_path).suffix else Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(contract_info, f, indent=2)
        
        print(f"📝 Deployment saved to: {filepath}")
        return str(filepath)

    def set_sparsity_interactive(self, contracts_info: List[Dict[str, Any]]):
        """Interactive sparsity setting for publisher's contracts"""
        # Filter contracts where current user is publisher and sparsity not set
        publisher_contracts = []
        for info in contracts_info:
            status = info['status']
            deployment = info['deployment']
            
            # Check if current user is publisher and sparsity not set
            if (status['is_accessible'] and 
                status['publisher'] and 
                status['publisher'].lower() == self.account.address.lower() and
                not status['sparsity_set']):
                publisher_contracts.append(info)
        
        if not publisher_contracts:
            print("❌ No contracts found where you are publisher and sparsity is not set")
            return
        
        print(f"\n📋 Your contracts (Publisher) - Sparsity Not Set:")
        for i, info in enumerate(publisher_contracts, 1):
            deployment = info['deployment']
            status = info['status']
            print(f"\n{i}. Contract: {deployment['contract_address']}")
            print(f"   📁 File: {info['file_path']}")
            print(f"   💰 Publisher Commission: {status['publisher_commission_rate'] / 100}%")
            print(f"   💰 Sparsity Commission: {status['sparsity_commission_rate'] / 100}%")
        
        # Get user selection
        while True:
            try:
                choice = input(f"\nSelect contract (1-{len(publisher_contracts)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return
                
                choice = int(choice)
                if 1 <= choice <= len(publisher_contracts):
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {len(publisher_contracts)}")
            except ValueError:
                print("❌ Please enter a valid number or 'q'")
        
        selected = publisher_contracts[choice - 1]
        print(f"\nSelected: {selected['deployment']['contract_address']}")
        
        # Get sparsity address
        sparsity_address = input("Enter sparsity address: ").strip()
        if not validate_ethereum_address(sparsity_address):
            print("❌ Invalid Ethereum address format")
            return
        
        if sparsity_address.lower() == self.account.address.lower():
            print("❌ Sparsity address cannot be the same as publisher address")
            return
        
        # Confirm action
        print(f"\n⚠️  IMPORTANT: This is a ONE-TIME operation!")
        print(f"Contract: {selected['deployment']['contract_address']}")
        print(f"Sparsity: {sparsity_address}")
        print(f"After setting sparsity, you (publisher) will lose control of the contract.")
        
        confirm = input("Type 'YES' to confirm: ").strip()
        if confirm != 'YES':
            print("❌ Operation cancelled")
            return
        
        # Execute sparsity setting
        self.set_sparsity(
            contract_address=selected['deployment']['contract_address'],
            abi=selected['abi'],
            sparsity_address=sparsity_address,
            deployment_file=selected['file_path']
        )

    def set_sparsity(self, contract_address: str, abi: List[Dict[str, Any]], sparsity_address: str, deployment_file: str):
        """Set sparsity address for a contract"""
        print(f"\n🔧 Setting sparsity for contract {contract_address}")
        print(f"👤 New sparsity: {sparsity_address}")
        
        # Get contract instance
        contract = self.get_contract_instance(contract_address, abi)
        
        # Check if sparsity already set
        config = contract.functions.getConfig().call()
        sparsity_is_set = config[9]  # sparsity_is_set is the 10th element
        
        if sparsity_is_set:
            print("❌ Sparsity already set for this contract")
            return
        
        # Build transaction
        transaction = contract.functions.setSparsity(sparsity_address).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })
        
        # Send transaction
        tx_hash = self.send_transaction(transaction)
        print("✅ Sparsity set successfully!")
        
        # Update deployment file
        try:
            with open(deployment_file, 'r') as f:
                deployment_data = json.load(f)
            
            deployment_data['sparsity_address'] = sparsity_address
            deployment_data['sparsity_set_tx'] = tx_hash
            deployment_data['sparsity_set_timestamp'] = int(time.time())
            
            with open(deployment_file, 'w') as f:
                json.dump(deployment_data, f, indent=2)
            
            print(f"📝 Updated deployment file: {deployment_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not update deployment file: {e}")


def main():
    """Main function for publisher tool"""
    parser, admin_config = create_argument_parser("publisher.py", "Publisher Tool - Deploy contracts and set sparsity", "publisher")
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--query", action="store_true", help="Query deployed contracts")
    mode_group.add_argument("--deploy", action="store_true", help="Deploy new contract")
    mode_group.add_argument("--set-sparsity", action="store_true", help="Set sparsity for a contract")
    mode_group.add_argument("--interactive", action="store_true", default=True, help="Interactive mode (default)")
    
    # Contract configuration for deployment
    parser.add_argument("--publisher-commission-rate", type=int, default=admin_config['contract'].get('publisher_commission_rate', 200), help="Publisher commission rate in basis points (default: 200 = 2.0%%)")
    parser.add_argument("--sparsity-commission-rate", type=int, default=admin_config['contract'].get('sparsity_commission_rate', 300), help="Sparsity commission rate in basis points (default: 300 = 3.0%%)")
    
    # Output configuration
    parser.add_argument("--deployment-output", default=admin_config['output']['deployment_output'], help="Output path for deployment info")
    
    # Contract selection for sparsity setting
    parser.add_argument("--contract", help="Contract address for set-sparsity mode")
    parser.add_argument("--sparsity", help="Sparsity address to set")
    
    args = parser.parse_args()
    
    try:
        # Initialize manager
        manager = PublisherManager(args.rpc_url, args.private_key, args.chain_id)
        
        if args.query:
            # Query mode
            contracts_info = manager.query_all_contracts()
            display_contracts_table(contracts_info, manager.w3, role_filter='publisher')
            
        elif args.deploy:
            # Deploy mode
            print("\n🚀 Deploying new lottery contract...")
            
            # Use configuration directly
            publisher_commission_rate = args.publisher_commission_rate
            sparsity_commission_rate = args.sparsity_commission_rate
            
            print("📋 Using configuration:")
            print(f"   💰 Publisher commission: {publisher_commission_rate} basis points ({publisher_commission_rate/100}%)")
            print(f"   💰 Sparsity commission: {sparsity_commission_rate} basis points ({sparsity_commission_rate/100}%)")
            
            # Deploy contract
            print("\n🔨 Compiling and deploying contract...")
            contract_interface = manager.compile_contract()
            contract_info = manager.deploy_contract(
                contract_interface=contract_interface,
                publisher_commission_rate=publisher_commission_rate,
                sparsity_commission_rate=sparsity_commission_rate
            )
            
            # Verify deployment
            expected_params = {
                'publisher_commission_rate': publisher_commission_rate,
                'sparsity_commission_rate': sparsity_commission_rate
            }
            manager.verify_deployment(contract_info, expected_params)
            
            # Save deployment record
            deployment_file = manager.save_deployment(contract_info, args.deployment_output)
            
            print(f"\n✅ Deployment completed successfully!")
            print(f"📄 Contract: {contract_info['contract_address']}")
            print(f"📁 Record: {deployment_file}")
            print(f"\n⚠️  Next step: Set sparsity address using --set-sparsity")
            
        elif args.set_sparsity:
            # Set sparsity mode
            contracts_info = manager.query_all_contracts()
            
            if args.contract and args.sparsity:
                # Direct mode with command line arguments
                if not validate_ethereum_address(args.sparsity):
                    print("❌ Invalid sparsity address format")
                    return
                
                # Find contract in deployment files
                target_contract = None
                for info in contracts_info:
                    if info['deployment']['contract_address'].lower() == args.contract.lower():
                        target_contract = info
                        break
                
                if not target_contract:
                    print(f"❌ Contract {args.contract} not found in deployment files")
                    return
                
                # Check if user is publisher
                status = target_contract['status']
                if not status['is_accessible']:
                    print(f"❌ Contract is not accessible: {status['error']}")
                    return
                
                if status['publisher'].lower() != manager.account.address.lower():
                    print(f"❌ You are not the publisher of this contract")
                    return
                
                manager.set_sparsity(
                    contract_address=target_contract['deployment']['contract_address'],
                    abi=target_contract['abi'],
                    sparsity_address=args.sparsity,
                    deployment_file=target_contract['file_path']
                )
            else:
                # Interactive mode
                manager.set_sparsity_interactive(contracts_info)
                
        else:
            # Interactive mode
            while True:
                print("\n🎲 Publisher Tool - Main Menu")
                print("=" * 30)
                print("1. Query contracts (where you are publisher)")
                print("2. Deploy new contract")
                print("3. Set sparsity address")
                print("4. Exit")
                
                choice = input("\nSelect option (1-4): ").strip()
                
                if choice == '1':
                    contracts_info = manager.query_all_contracts()
                    display_contracts_table(contracts_info, manager.w3, role_filter='publisher')
                    
                elif choice == '2':
                    # Interactive deployment
                    print("\n🚀 Deploy New Contract")
                    print("=" * 25)
                    
                    # Use defaults or get user input
                    pub_rate = input(f"Publisher commission rate in basis points (default: 200 = 2%): ").strip()
                    pub_rate = int(pub_rate) if pub_rate else 200
                    
                    spar_rate = input(f"Sparsity commission rate in basis points (default: 300 = 3%): ").strip()
                    spar_rate = int(spar_rate) if spar_rate else 300
                    
                    print(f"\n📋 Configuration Summary:")
                    print(f"   Publisher commission: {pub_rate} basis points ({pub_rate/100}%)")
                    print(f"   Sparsity commission: {spar_rate} basis points ({spar_rate/100}%)")
                    
                    confirm = input("\nDeploy with these settings? (y/N): ").strip().lower()
                    if confirm == 'y':
                        try:
                            contract_interface = manager.compile_contract()
                            contract_info = manager.deploy_contract(
                                contract_interface=contract_interface,
                                publisher_commission_rate=pub_rate,
                                sparsity_commission_rate=spar_rate
                            )
                            
                            expected_params = {
                                'publisher_commission_rate': pub_rate,
                                'sparsity_commission_rate': spar_rate
                            }
                            manager.verify_deployment(contract_info, expected_params)
                            
                            deployment_file = manager.save_deployment(contract_info, args.deployment_output)
                            
                            print(f"\n✅ Deployment completed!")
                            print(f"📄 Contract: {contract_info['contract_address']}")
                            print(f"📁 Record: {deployment_file}")
                            
                        except Exception as e:
                            print(f"❌ Deployment failed: {e}")
                    
                elif choice == '3':
                    contracts_info = manager.query_all_contracts()
                    manager.set_sparsity_interactive(contracts_info)
                    
                elif choice == '4':
                    print("👋 Goodbye!")
                    break
                    
                else:
                    print("❌ Invalid choice. Please select 1-4.")
    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()