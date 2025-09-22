#!/usr/bin/env python3
"""
Sparsity Tool  
Operator management and funding for lottery contracts
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


class SparsityManager(LotteryContractBase):
    """Sparsity-specific contract management"""
    
    def set_operator_interactive(self, contracts_info: List[Dict[str, Any]]):
        """Interactive operator setting for sparsity's contracts"""
        # Filter contracts where current user is sparsity
        sparsity_contracts = []
        for info in contracts_info:
            status = info['status']
            
            # Check if current user is sparsity and sparsity is set
            if (status['is_accessible'] and 
                status['sparsity'] and 
                status['sparsity'].lower() == self.account.address.lower()):
                sparsity_contracts.append(info)
        
        if not sparsity_contracts:
            print("❌ No contracts found where you are set as sparsity")
            return
        
        print(f"\n📋 Your contracts (Sparsity):")
        for i, info in enumerate(sparsity_contracts, 1):
            deployment = info['deployment']
            status = info['status']
            print(f"\n{i}. Contract: {deployment['contract_address']}")
            print(f"   📁 File: {info['file_path']}")
            print(f"   📍 Publisher: {status['publisher']}")
            print(f"   👤 Current Operator: {status['operator'] or 'Not set'}")
            print(f"   💰 Sparsity Commission: {status['sparsity_commission_rate'] / 100}%")
        
        # Get user selection
        while True:
            try:
                choice = input(f"\nSelect contract (1-{len(sparsity_contracts)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return
                
                choice = int(choice)
                if 1 <= choice <= len(sparsity_contracts):
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {len(sparsity_contracts)}")
            except ValueError:
                print("❌ Please enter a valid number or 'q'")
        
        selected = sparsity_contracts[choice - 1]
        print(f"\nSelected: {selected['deployment']['contract_address']}")
        
        # Get operator address
        current_operator = selected['status']['operator']
        if current_operator:
            print(f"Current operator: {current_operator}")
            action = input("Enter 'update' to change operator or 'fund' to send ETH to current operator: ").strip().lower()
            
            if action == 'fund':
                self.fund_operator_interactive(current_operator)
                return
            elif action != 'update':
                print("❌ Invalid action")
                return
        
        operator_address = input("Enter new operator address: ").strip()
        if not validate_ethereum_address(operator_address):
            print("❌ Invalid Ethereum address format")
            return
        
        if operator_address.lower() == self.account.address.lower():
            print("❌ Operator address cannot be the same as sparsity address")
            return
        
        if operator_address.lower() == selected['status']['publisher'].lower():
            print("❌ Operator address cannot be the same as publisher address")
            return
        
        # Confirm action
        print(f"\nContract: {selected['deployment']['contract_address']}")
        print(f"New operator: {operator_address}")
        
        confirm = input("Confirm operator setting? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Operation cancelled")
            return
        
        # Execute operator setting
        self.set_operator(
            contract_address=selected['deployment']['contract_address'],
            abi=selected['abi'],
            operator_address=operator_address,
            deployment_file=selected['file_path']
        )

    def set_operator(self, contract_address: str, abi: List[Dict[str, Any]], operator_address: str, deployment_file: str):
        """Set operator address for a contract"""
        print(f"\n🔧 Setting operator for contract {contract_address}")
        print(f"👤 New operator: {operator_address}")
        
        # Get contract instance
        contract = self.get_contract_instance(contract_address, abi)
        
        # Check if current account is sparsity
        config = contract.functions.getConfig().call()
        sparsity_addr = config[1]  # sparsity is the 2nd element
        
        if sparsity_addr.lower() != self.account.address.lower():
            print("❌ You are not the sparsity for this contract")
            return
        
        # Build transaction
        transaction = contract.functions.setOperator(operator_address).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })
        
        # Send transaction
        tx_hash = self.send_transaction(transaction)
        print("✅ Operator set successfully!")
        
        # Update deployment file
        try:
            with open(deployment_file, 'r') as f:
                deployment_data = json.load(f)
            
            deployment_data['operator_address'] = operator_address
            deployment_data['operator_set_tx'] = tx_hash
            deployment_data['operator_set_timestamp'] = int(time.time())
            
            with open(deployment_file, 'w') as f:
                json.dump(deployment_data, f, indent=2)
            
            print(f"📝 Updated deployment file: {deployment_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not update deployment file: {e}")

    def update_operator(self, contract_address: str, abi: List[Dict[str, Any]], operator_address: str, deployment_file: str):
        """Update operator address for a contract (same as set_operator)"""
        print(f"\n🔧 Updating operator for contract {contract_address}")
        print(f"👤 New operator: {operator_address}")
        
        # Get contract instance
        contract = self.get_contract_instance(contract_address, abi)
        
        # Check if current account is sparsity
        config = contract.functions.getConfig().call()
        sparsity_addr = config[1]  # sparsity is the 2nd element
        
        if sparsity_addr.lower() != self.account.address.lower():
            print("❌ You are not the sparsity for this contract")
            return
        
        # Build transaction
        transaction = contract.functions.updateOperator(operator_address).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })
        
        # Send transaction
        tx_hash = self.send_transaction(transaction)
        print("✅ Operator updated successfully!")
        
        # Update deployment file
        try:
            with open(deployment_file, 'r') as f:
                deployment_data = json.load(f)
            
            deployment_data['operator_address'] = operator_address
            deployment_data['operator_update_tx'] = tx_hash
            deployment_data['operator_update_timestamp'] = int(time.time())
            
            with open(deployment_file, 'w') as f:
                json.dump(deployment_data, f, indent=2)
            
            print(f"📝 Updated deployment file: {deployment_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not update deployment file: {e}")

    def fund_operator_interactive(self, operator_address: str = None):
        """Interactive operator funding"""
        if not operator_address:
            operator_address = input("Enter operator address to fund: ").strip()
            
        if not validate_ethereum_address(operator_address):
            print("❌ Invalid Ethereum address format")
            return
        
        # Get current balance of operator
        operator_balance = self.w3.eth.get_balance(operator_address)
        operator_balance_eth = self.w3.from_wei(operator_balance, 'ether')
        
        print(f"\n💰 Operator Balance:")
        print(f"   Address: {operator_address}")
        print(f"   Current: {operator_balance_eth:.6f} ETH")
        
        # Get funding amount
        while True:
            try:
                amount_str = input("Enter amount to send (ETH): ").strip()
                amount = float(amount_str)
                if amount > 0:
                    break
                else:
                    print("❌ Amount must be positive")
            except ValueError:
                print("❌ Please enter a valid number")
        
        # Check our balance
        our_balance = self.w3.eth.get_balance(self.account.address)
        our_balance_eth = self.w3.from_wei(our_balance, 'ether')
        
        if amount > our_balance_eth:
            print(f"❌ Insufficient balance. You have: {our_balance_eth:.6f} ETH, Need: {amount} ETH")
            return
        
        # Confirm transaction
        print(f"\n💸 Fund Operator:")
        print(f"   From: {self.account.address} ({our_balance_eth:.6f} ETH)")
        print(f"   To: {operator_address} ({operator_balance_eth:.6f} ETH)")
        print(f"   Amount: {amount} ETH")
        print(f"   Estimated gas cost: ~0.0004 ETH")
        
        confirm = input("Send funds? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Transfer cancelled")
            return
        
        # Send ETH
        try:
            tx_hash = self.send_eth(operator_address, amount)
            print(f"✅ Successfully sent {amount} ETH to operator!")
            print(f"📄 Transaction: {tx_hash}")
            
            # Show updated balance
            new_balance = self.w3.eth.get_balance(operator_address)
            new_balance_eth = self.w3.from_wei(new_balance, 'ether')
            print(f"💰 Operator new balance: {new_balance_eth:.6f} ETH")
            
        except Exception as e:
            print(f"❌ Transfer failed: {e}")

    def get_sparsity_contracts(self, contracts_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get contracts where current user is sparsity"""
        sparsity_contracts = []
        for info in contracts_info:
            status = info['status']
            if (status['is_accessible'] and 
                status['sparsity'] and 
                status['sparsity'].lower() == self.account.address.lower()):
                sparsity_contracts.append(info)
        return sparsity_contracts


def main():
    """Main function for sparsity tool"""
    parser, admin_config = create_argument_parser("sparsity.py", "Sparsity Tool - Manage operators and fund operations", "sparsity")
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--query", action="store_true", help="Query contracts where you are sparsity")
    mode_group.add_argument("--set-operator", action="store_true", help="Set operator for a contract")
    mode_group.add_argument("--update-operator", action="store_true", help="Update operator for a contract")
    mode_group.add_argument("--fund-operator", action="store_true", help="Send ETH to operator address")
    mode_group.add_argument("--interactive", action="store_true", default=True, help="Interactive mode (default)")
    
    # Contract and operator selection
    parser.add_argument("--contract", help="Contract address for operator operations")
    parser.add_argument("--operator", help="Operator address to set/update/fund")
    parser.add_argument("--amount", type=float, help="Amount of ETH to send to operator")
    
    args = parser.parse_args()
    
    try:
        # Initialize manager
        manager = SparsityManager(args.rpc_url, args.private_key, args.chain_id)
        
        if args.query:
            # Query mode - show contracts where user is sparsity
            contracts_info = manager.query_all_contracts()
            sparsity_contracts = manager.get_sparsity_contracts(contracts_info)
            
            if not sparsity_contracts:
                print("📭 No contracts found where you are set as sparsity")
            else:
                print(f"\n🎲 Contracts where you are Sparsity")
                print("=" * 40)
                
                for i, info in enumerate(sparsity_contracts, 1):
                    deployment = info['deployment']
                    status = info['status']
                    
                    print(f"\n{i}. Contract: {deployment['contract_address']}")
                    print(f"   📁 File: {info['file_path']}")
                    print(f"   📍 Publisher: {status['publisher']}")
                    print(f"   👤 Operator: {status['operator'] or 'Not set'}")
                    print(f"   💰 Your Commission: {status['sparsity_commission_rate'] / 100}%")
                    print(f"   💸 Min Bet: {status['min_bet_eth']} ETH")
                    
                    if status['current_round']:
                        round_id, start_time, end_time, draw_time, total_pot, participant_count = status['current_round']
                        print(f"   🎯 Current Round: #{round_id}")
                        print(f"   👥 Participants: {participant_count}")
                        print(f"   💎 Total Pot: {manager.w3.from_wei(total_pot, 'ether')} ETH")
                    else:
                        print(f"   🎯 Current Round: No active round")
            
        elif args.set_operator or args.update_operator:
            # Operator setting/updating mode
            contracts_info = manager.query_all_contracts()
            
            if args.contract and args.operator:
                # Direct mode with command line arguments
                if not validate_ethereum_address(args.operator):
                    print("❌ Invalid operator address format")
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
                
                # Check if user is sparsity
                status = target_contract['status']
                if not status['is_accessible']:
                    print(f"❌ Contract is not accessible: {status['error']}")
                    return
                
                if not status['sparsity'] or status['sparsity'].lower() != manager.account.address.lower():
                    print(f"❌ You are not the sparsity of this contract")
                    return
                
                if args.set_operator:
                    manager.set_operator(
                        contract_address=target_contract['deployment']['contract_address'],
                        abi=target_contract['abi'],
                        operator_address=args.operator,
                        deployment_file=target_contract['file_path']
                    )
                else:  # update_operator
                    manager.update_operator(
                        contract_address=target_contract['deployment']['contract_address'],
                        abi=target_contract['abi'],
                        operator_address=args.operator,
                        deployment_file=target_contract['file_path']
                    )
            else:
                # Interactive mode
                manager.set_operator_interactive(contracts_info)
                
        elif args.fund_operator:
            # Fund operator mode
            if args.operator:
                if args.amount:
                    # Direct mode
                    try:
                        tx_hash = manager.send_eth(args.operator, args.amount)
                        print(f"✅ Successfully sent {args.amount} ETH to {args.operator}")
                        print(f"📄 Transaction: {tx_hash}")
                    except Exception as e:
                        print(f"❌ Transfer failed: {e}")
                else:
                    # Interactive funding with specified operator
                    manager.fund_operator_interactive(args.operator)
            else:
                # Fully interactive mode
                manager.fund_operator_interactive()
                
        else:
            # Interactive mode
            while True:
                print("\n🎲 Sparsity Tool - Main Menu")
                print("=" * 30)
                print("1. Query contracts (where you are sparsity)")
                print("2. Set/Update operator")
                print("3. Fund operator")
                print("4. Exit")
                
                choice = input("\nSelect option (1-4): ").strip()
                
                if choice == '1':
                    contracts_info = manager.query_all_contracts()
                    sparsity_contracts = manager.get_sparsity_contracts(contracts_info)
                    
                    if not sparsity_contracts:
                        print("📭 No contracts found where you are set as sparsity")
                    else:
                        display_contracts_table(sparsity_contracts, manager.w3)
                    
                elif choice == '2':
                    contracts_info = manager.query_all_contracts()
                    manager.set_operator_interactive(contracts_info)
                    
                elif choice == '3':
                    manager.fund_operator_interactive()
                    
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