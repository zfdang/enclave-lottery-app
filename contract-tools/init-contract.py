#!/usr/bin/env python3
"""
init-contract.py

Deploy Lottery contract, set sparsity and operator, and display contract details.

Uses PublisherManager and SparsityManager from contract-tools to perform actions.
"""
import json
import time
import sys
from pathlib import Path

# Ensure local contract-tools directory is on sys.path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

from publisher import PublisherManager
from sparsity import SparsityManager
from common import validate_ethereum_address, create_argument_parser
from config import load_publisher_config, load_sparsity_config, load_init_contract_config
import argparse

# Defaults will be loaded from publisher.conf and sparsity.conf when available
SPARSITY_ADDR = None
OPERATOR_ADDR = None


def main():
    # Use shared argument parser and admin config loader but prefer init-contract.conf
    parser, admin_config = create_argument_parser('init-contract.py', 'Automated contract init script', 'publisher')

    # Load init-contract defaults (optional)
    init_conf = load_init_contract_config()

    # Override some parser defaults with init_conf values if present
    default_rpc = init_conf.get('blockchain', {}).get('rpc_url') or admin_config['blockchain'].get('rpc_url')
    default_chain = init_conf.get('blockchain', {}).get('chain_id') or admin_config['blockchain'].get('chain_id')
    default_private = init_conf.get('publisher', {}).get('private_key') or admin_config['blockchain'].get('private_key')

    # Set parser defaults for blockchain args (they were added by create_argument_parser)
    parser.set_defaults(rpc_url=default_rpc, private_key=default_private, chain_id=default_chain)

    parser.add_argument('--output', default=init_conf.get('output', {}).get('deployment_output', 'deployments'))
    parser.add_argument('--publisher-commission', type=int, default=init_conf.get('contract', {}).get('publisher_commission_rate', admin_config['contract'].get('publisher_commission_rate', 200)))
    parser.add_argument('--sparsity-commission', type=int, default=init_conf.get('contract', {}).get('sparsity_commission_rate', admin_config['contract'].get('sparsity_commission_rate', 300)))
    parser.add_argument('--sparsity-addr', help='Sparsity address (overrides config)', default=init_conf.get('sparsity', {}).get('address'))
    parser.add_argument('--operator-addr', help='Operator address (overrides config)', default=init_conf.get('operator', {}).get('address'))

    args = parser.parse_args()

    # Gather addresses and keys from CLI args or init_conf
    sparsity_addr = args.sparsity_addr
    operator_addr = args.operator_addr

    # If operator isn't provided, fall back to common example operator
    if not operator_addr:
        operator_addr = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266'

    # Validate addresses
    if sparsity_addr and not validate_ethereum_address(sparsity_addr):
        raise SystemExit('Invalid sparsity address')
    if operator_addr and not validate_ethereum_address(operator_addr):
        raise SystemExit('Invalid operator address')

    print('Using RPC:', args.rpc_url)

    # Instantiate publisher manager (deployer) using provided private key (from CLI or init_conf)
    publisher_pk = args.private_key
    if not publisher_pk:
        raise SystemExit('Publisher private key not provided; please provide --private-key or set it in init-contract.conf under publisher.private_key')

    pub = PublisherManager(args.rpc_url, publisher_pk, args.chain_id)

    print('Compiling contract...')
    contract_interface = pub.compile_contract()

    # Deploy
    info = pub.deploy_contract(
        contract_interface=contract_interface,
        publisher_commission_rate=args.publisher_commission,
        sparsity_commission_rate=args.sparsity_commission
    )

    # Save deployment file
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    deployment_file = output_dir / f'deployment_{timestamp}.json'
    with open(deployment_file, 'w') as f:
        json.dump(info, f, indent=2)

    print('\nDeployed contract at', info['contract_address'])

    # Verify deployment
    expected = {
        'publisher_commission_rate': args.publisher_commission,
        'sparsity_commission_rate': args.sparsity_commission
    }
    pub.verify_deployment(info, expected)

    # Set sparsity via publisher manager
    # Determine final sparsity address to use
    final_sparsity = sparsity_addr or init_conf.get('sparsity', {}).get('address') or '0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f'
    print('\nSetting sparsity to', final_sparsity)
    pub.set_sparsity(
        contract_address=info['contract_address'],
        abi=info['abi'],
        sparsity_address=final_sparsity,
        deployment_file=str(deployment_file)
    )

    # Now set operator using SparsityManager (must use sparsity private key)
    # For simplicity assume operator private key is same as the one in enclave.conf's operator_private_key
    # But here we'll instantiate sparsity manager using the same RPC and assume caller will pass the sparsity's private key
    # For convenience in local dev we'll prompt for sparsity private key
    # Try to obtain sparsity private key from sparsity.conf or prompt
    # Try to obtain sparsity private key from init_conf or prompt
    sparsity_pk = init_conf.get('sparsity', {}).get('private_key')
    if not sparsity_pk:
        sparsity_pk = input('\nEnter sparsity private key to set operator (or press enter to skip): ').strip() or None

    if sparsity_pk:
        spars = SparsityManager(args.rpc_url, sparsity_pk, args.chain_id)
        print('\nSetting operator to', operator_addr)
        # We need ABI to send transaction
        spars.set_operator(
            contract_address=info['contract_address'],
            abi=info['abi'],
            operator_address=operator_addr,
            deployment_file=str(deployment_file)
        )
    else:
        print('Skipping operator set; please run sparsity.py --set-operator later using sparsity account')

    # Show contract details
    print('\nFetching contract details...')
    pub.verify_deployment(info, expected)
    # Load contract instance and print getConfig
    contract = pub.get_contract_instance(info['contract_address'], info['abi'])
    cfg = contract.functions.getConfig().call()
    print('\nContract getConfig():')
    print(cfg)

    print('\nInitialization complete')


if __name__ == "__main__":
    main()
