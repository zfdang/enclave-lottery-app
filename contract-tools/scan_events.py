#!/usr/bin/env python3
"""Scan the last N blocks and print decoded Lottery events.

Usage: python3 contract-tools/scan_events.py [--blocks 500]

Reads RPC URL and operator address from contract-tools/init-contract.conf
and loads the contract ABI from out/Lottery.sol/Lottery.json
"""
import json
import argparse
import os
from web3 import Web3
from web3._utils.events import get_event_data

ROOT = os.path.dirname(os.path.dirname(__file__))
CONF_PATH = os.path.join(ROOT, 'contract-tools', 'init-contract.conf')
ABI_PATH = os.path.join(ROOT, 'out', 'Lottery.sol', 'Lottery.json')


def load_config():
    with open(CONF_PATH, 'r') as f:
        text = f.read().strip()
        # file sometimes wrapped in ```properties block - try to strip backticks
        text = text.strip('`\n')
        return json.loads(text)


def load_abi():
    with open(ABI_PATH, 'r') as f:
        data = json.load(f)
        return data.get('abi', data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blocks', '-b', type=int, default=500, help='Number of blocks to scan')
    parser.add_argument('--operator-only', action='store_true', help='Only show events involving the operator address')
    args = parser.parse_args()

    conf = load_config()
    rpc_url = conf['blockchain']['rpc_url']
    operator_addr = conf.get('operator', {}).get('address') or conf.get('blockchain', {}).get('operator_address')
    if operator_addr:
        operator_addr = Web3.to_checksum_address(operator_addr)

    print(f"RPC: {rpc_url}")
    print(f"Operator: {operator_addr}")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print('ERROR: cannot connect to RPC')
        return

    abi = load_abi()
    # build event signature -> event ABI map
    events_by_topic = {}
    for item in abi:
        if item.get('type') == 'event':
            sig = Web3.keccak(text=f"{item['name']}({','.join([i['type'] for i in item['inputs']])})").hex()
            events_by_topic[sig] = item

    latest = w3.eth.block_number
    start = max(0, latest - args.blocks + 1)
    print(f"Scanning blocks {start}..{latest} ({args.blocks} blocks)")

    # fetch logs for the whole range for efficiency
    try:
        logs = w3.eth.get_logs({
            'fromBlock': start,
            'toBlock': latest,
        })
    except Exception as e:
        print('ERROR fetching logs:', e)
        return

    # group logs by block
    logs_by_block = {}
    for l in logs:
        logs_by_block.setdefault(l['blockNumber'], []).append(l)

    for block_num in range(start, latest + 1):
        blk_logs = logs_by_block.get(block_num, [])
        if not blk_logs:
            continue
        blk = w3.eth.get_block(block_num)
        blk_hash = blk['hash'].hex() if isinstance(blk['hash'], (bytes, bytearray)) else str(blk['hash'])
        tx_count = len(blk['transactions']) if 'transactions' in blk else 0
        # human-friendly block header (include timestamp)
        blk_ts = blk.get('timestamp', None)
        try:
            blk_time = Web3.to_datetime(blk_ts).strftime('%Y-%m-%d %H:%M:%S') if blk_ts else 'N/A'
        except Exception:
            # fallback: epoch seconds
            try:
                blk_time = str(int(blk_ts))
            except Exception:
                blk_time = 'N/A'
        print('\n=== Block', block_num, f'hash {blk_hash}', f'txs {tx_count}', f'time {blk_time}', '===')
        for l in blk_logs:
            topic0 = l['topics'][0].hex() if l['topics'] else None
            event_abi = events_by_topic.get(topic0)
            if event_abi:
                try:
                    ev = get_event_data(w3.codec, event_abi, l)
                except Exception as e:
                    print('  - Failed to decode event:', e)
                    print('    raw:', l)
                    continue
                parts = []
                # Check if operator involved
                involved = False
                # prepare formatting helpers
                def fmt_eth(key, val):
                    # convert wei-like amounts to ETH for known keys
                    known = {'amount', 'newTotal', 'totalPot', 'winnerPrize', 'publisherCommission', 'sparsityCommission', 'totalRefunded'}
                    try:
                        if key in known and isinstance(val, (int,)):
                            return str(Web3.from_wei(val, 'ether')) + ' ETH'
                    except Exception:
                        pass
                    return val

                for k, v in ev['args'].items():
                    display_v = fmt_eth(k, v)
                    parts.append(f"{k}={display_v}")
                    try:
                        # consider string-like addresses or bytes
                        if operator_addr:
                            if isinstance(v, (str,)) and Web3.to_checksum_address(v) == operator_addr:
                                involved = True
                            elif hasattr(v, 'hex'):
                                # sometimes addresses are returned as HexBytes
                                try:
                                    possible = Web3.to_checksum_address(v.hex())
                                    if possible == operator_addr:
                                        involved = True
                                except Exception:
                                    pass
                    except Exception:
                        pass
                prefix = ' *OPERATOR* ' if involved else ' '
                # include tx hash and log index
                txh = l.get('transactionHash')
                txh_s = txh.hex() if txh is not None else 'N/A'
                li = l.get('logIndex', 'N/A')
                if args.operator_only and not involved:
                    continue
                print(f"{prefix}{ev['event']} tx={txh_s} logIndex={li} ({', '.join(parts)})")
            else:
                print('  - Unknown event topic', topic0, 'raw topics:', [t.hex() for t in l['topics']])


if __name__ == '__main__':
    main()
