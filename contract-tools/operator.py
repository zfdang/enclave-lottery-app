#!/usr/bin/env python3
"""
Operator Tool
Manage rounds and operator-updatable parameters for the Lottery contract
"""

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any, List

from common import (
    LotteryContractBase,
    create_argument_parser,
    display_contracts_table,
    validate_ethereum_address,
    display_contract_details,
)
from config import load_init_contract_config


class OperatorManager(LotteryContractBase):
    """Operator-specific contract management"""

    def update_min_bet(self, contract_address: str, abi: List[Dict[str, Any]], new_min_bet_wei: int):
        print(f"🔧 Updating min bet amount for {contract_address} to {new_min_bet_wei} wei")
        contract = self.get_contract_instance(contract_address, abi)

        # Ensure only operator can call (contract enforces this); call will fail otherwise
        transaction = contract.functions.updateMinBetAmount(new_min_bet_wei).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })

        tx_hash = self.send_transaction(transaction)
        print(f"✅ Min bet updated. Tx: {tx_hash}")
        return tx_hash

    def update_betting_duration(self, contract_address: str, abi: List[Dict[str, Any]], new_duration_seconds: int):
        print(f"🔧 Updating betting duration for {contract_address} to {new_duration_seconds} seconds")
        contract = self.get_contract_instance(contract_address, abi)

        transaction = contract.functions.updateBettingDuration(new_duration_seconds).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })

        tx_hash = self.send_transaction(transaction)
        print(f"✅ Betting duration updated. Tx: {tx_hash}")
        return tx_hash

    def update_min_participants(self, contract_address: str, abi: List[Dict[str, Any]], new_min_participants: int):
        print(f"🔧 Updating min participants for {contract_address} to {new_min_participants}")
        contract = self.get_contract_instance(contract_address, abi)

        transaction = contract.functions.updateMinParticipants(new_min_participants).build_transaction({
            'from': self.account.address,
            'gas': 100000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })

        tx_hash = self.send_transaction(transaction)
        print(f"✅ Min participants updated. Tx: {tx_hash}")
        return tx_hash

    def start_new_round(self, contract_address: str, abi: List[Dict[str, Any]]):
        print(f"▶️ Starting new round on {contract_address}")
        contract = self.get_contract_instance(contract_address, abi)

        transaction = contract.functions.startNewRound().build_transaction({
            'from': self.account.address,
            'gas': 300000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })

        tx_hash = self.send_transaction(transaction)
        print(f"✅ New round started. Tx: {tx_hash}")
        return tx_hash

    def refund_round(self, contract_address: str, abi: List[Dict[str, Any]]):
        print(f"↩️ Refunding round on {contract_address}")
        contract = self.get_contract_instance(contract_address, abi)

        transaction = contract.functions.refundRound().build_transaction({
            'from': self.account.address,
            'gas': 200000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })

        tx_hash = self.send_transaction(transaction)
        print(f"✅ Round refunded. Tx: {tx_hash}")
        return tx_hash

    def draw_winner(self, contract_address: str, abi: List[Dict[str, Any]]):
        print(f"🎯 Drawing winner on {contract_address}")
        contract = self.get_contract_instance(contract_address, abi)

        transaction = contract.functions.drawWinner().build_transaction({
            'from': self.account.address,
            'gas': 400000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'chainId': self.chain_id
        })

        tx_hash = self.send_transaction(transaction)
        print(f"✅ Draw executed. Tx: {tx_hash}")
        return tx_hash


def main():
    parser, admin_config = create_argument_parser("operator.py", "Operator Tool - manage rounds and operator parameters", "operator")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--query", action="store_true", help="Query deployed contracts")
    mode_group.add_argument("--update-min-bet", action="store_true", help="Update minimum bet amount (wei)")
    mode_group.add_argument("--update-betting-duration", action="store_true", help="Update betting duration (seconds)")
    mode_group.add_argument("--update-min-participants", action="store_true", help="Update min participants required")
    mode_group.add_argument("--start-new-round", action="store_true", help="Start new round")
    mode_group.add_argument("--refund-round", action="store_true", help="Refund current round")
    mode_group.add_argument("--draw-winner", action="store_true", help="Draw winner for current round")
    mode_group.add_argument("--interactive", action="store_true", default=True, help="Interactive menu (default)")

    parser.add_argument("--contract", help="Contract address to operate on")
    parser.add_argument("--min-bet", help="Minimum bet in wei (for --update-min-bet)")
    parser.add_argument("--duration", help="Betting duration in seconds (for --update-betting-duration)")
    parser.add_argument("--min-participants", help="Minimum participants (for --update-min-participants)")

    args = parser.parse_args()

    # Initialize manager
    manager = OperatorManager(args.rpc_url, args.private_key, args.chain_id)

    if args.query:
        contracts_info = manager.query_all_contracts()
        display_contracts_table(contracts_info, manager.w3, role_filter='operator')
        return

    # Helper to find target contract record from deployment files
    contracts_info = manager.query_all_contracts()

    def find_contract_record(addr: str):
        for info in contracts_info:
            if info['deployment']['contract_address'].lower() == addr.lower():
                return info
        return None

    def select_contract_interactive():
        """Allow the operator to select a contract from discovered deployment files."""
        if not contracts_info:
            print('❌ No deployment records found')
            return None

        # Prefer contracts where this account is the operator
        operator_addr = manager.account.address.lower()
        operator_contracts = [c for c in contracts_info if c['status'].get('operator') and c['status'].get('operator').lower() == operator_addr]

        choices = operator_contracts if operator_contracts else contracts_info

        print('\nSelect a contract:')
        for i, info in enumerate(choices, start=1):
            dep = info['deployment']
            status = info['status']
            op = status.get('operator') or 'Not set'
            spar = status.get('sparsity') or 'Not set'
            print(f"{i}. {dep['contract_address']}  (operator: {op}, sparsity: {spar})")

        while True:
            sel = input(f"Select contract (1-{len(choices)}) or 'q' to cancel: ").strip()
            if sel.lower() == 'q':
                return None
            try:
                idx = int(sel)
                if 1 <= idx <= len(choices):
                    return choices[idx - 1]
                else:
                    print('❌ Number out of range')
            except ValueError:
                print('❌ Please enter a valid number or q')

    if args.update_min_bet:
        if not args.contract or not args.min_bet:
            print("❌ --contract and --min-bet are required for --update-min-bet")
            return
        rec = find_contract_record(args.contract)
        if not rec:
            print(f"❌ Contract {args.contract} not found in deployment records")
            return
        abi = rec['abi']
        manager.update_min_bet(rec['deployment']['contract_address'], abi, int(args.min_bet))
        return

    if args.update_betting_duration:
        if not args.contract or not args.duration:
            print("❌ --contract and --duration are required for --update-betting-duration")
            return
        rec = find_contract_record(args.contract)
        if not rec:
            print(f"❌ Contract {args.contract} not found in deployment records")
            return
        abi = rec['abi']
        manager.update_betting_duration(rec['deployment']['contract_address'], abi, int(args.duration))
        return

    if args.update_min_participants:
        if not args.contract or not args.min_participants:
            print("❌ --contract and --min-participants are required for --update-min-participants")
            return
        rec = find_contract_record(args.contract)
        if not rec:
            print(f"❌ Contract {args.contract} not found in deployment records")
            return
        abi = rec['abi']
        manager.update_min_participants(rec['deployment']['contract_address'], abi, int(args.min_participants))
        return

    if args.start_new_round:
        if not args.contract:
            print("❌ --contract is required for --start-new-round")
            return
        rec = find_contract_record(args.contract)
        if not rec:
            print(f"❌ Contract {args.contract} not found in deployment records")
            return
        abi = rec['abi']
        manager.start_new_round(rec['deployment']['contract_address'], abi)
        return

    if args.refund_round:
        if not args.contract:
            print("❌ --contract is required for --refund-round")
            return
        rec = find_contract_record(args.contract)
        if not rec:
            print(f"❌ Contract {args.contract} not found in deployment records")
            return
        abi = rec['abi']
        manager.refund_round(rec['deployment']['contract_address'], abi)
        return

    if args.draw_winner:
        if not args.contract:
            print("❌ --contract is required for --draw-winner")
            return
        rec = find_contract_record(args.contract)
        if not rec:
            print(f"❌ Contract {args.contract} not found in deployment records")
            return
        abi = rec['abi']
        manager.draw_winner(rec['deployment']['contract_address'], abi)
        return

    # Interactive menu
    while True:
        print('\n🎲 Operator Tool - Main Menu')
        print('=' * 30)
        print('1. Query contracts (where you are operator)')
        print('2. Update min bet amount')
        print('3. Update betting duration')
        print('4. Update min participants')
        print('5. Start new round')
        print('6. Refund current round')
        print('7. Draw winner')
        print('8. Exit')

        choice = input('\nSelect option (1-8): ').strip()

        if choice == '1':
            contracts_info = manager.query_all_contracts()
            display_contracts_table(contracts_info, manager.w3, role_filter='operator')

        elif choice == '2':
            rec = select_contract_interactive()
            if not rec:
                continue
            new_min = input('New min bet (wei): ').strip()
            try:
                manager.update_min_bet(rec['deployment']['contract_address'], rec['abi'], int(new_min))
            except Exception as e:
                print(f'❌ Failed to update min bet: {e}')

        elif choice == '3':
            rec = select_contract_interactive()
            if not rec:
                continue
            new_dur = input('New betting duration (seconds): ').strip()
            try:
                manager.update_betting_duration(rec['deployment']['contract_address'], rec['abi'], int(new_dur))
            except Exception as e:
                print(f'❌ Failed to update betting duration: {e}')

        elif choice == '4':
            rec = select_contract_interactive()
            if not rec:
                continue
            new_minp = input('New minimum participants: ').strip()
            try:
                manager.update_min_participants(rec['deployment']['contract_address'], rec['abi'], int(new_minp))
            except Exception as e:
                print(f'❌ Failed to update min participants: {e}')

        elif choice == '5':
            rec = select_contract_interactive()
            if not rec:
                continue
            try:
                manager.start_new_round(rec['deployment']['contract_address'], rec['abi'])
            except Exception as e:
                print(f'❌ Failed to start new round: {e}')

        elif choice == '6':
            rec = select_contract_interactive()
            if not rec:
                continue
            try:
                manager.refund_round(rec['deployment']['contract_address'], rec['abi'])
            except Exception as e:
                print(f'❌ Failed to refund round: {e}')

        elif choice == '7':
            rec = select_contract_interactive()
            if not rec:
                continue
            try:
                manager.draw_winner(rec['deployment']['contract_address'], rec['abi'])
            except Exception as e:
                print(f'❌ Failed to draw winner: {e}')

        elif choice == '8':
            break

        else:
            print('❌ Invalid option')


if __name__ == '__main__':
    main()
