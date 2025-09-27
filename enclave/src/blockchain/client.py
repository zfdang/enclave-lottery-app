"""Blockchain client for the passive lottery operator."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from eth_account import Account
from web3 import Web3
from web3.contract import Contract

from lottery.models import ContractConfig, LotteryRound, ParticipantSummary, RoundState

logger = logging.getLogger(__name__)


@dataclass
class BlockchainEvent:
    """Lightweight representation of an on-chain event."""

    name: str
    args: Dict[str, Any]
    block_number: int
    transaction_hash: str
    timestamp: int


class BlockchainClient:
    """Async-friendly wrapper around web3.py for lottery operations."""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

        blockchain_cfg = config.get("blockchain", {})
        self.rpc_url: str = blockchain_cfg.get("rpc_url", "http://localhost:8545")
        self.chain_id: int = int(blockchain_cfg.get("chain_id", 31337))
        self.contract_address: Optional[str] = blockchain_cfg.get("contract_address")

        self._w3: Optional[Web3] = None
        self._contract: Optional[Contract] = None
        self.contract_abi: Optional[List[Dict[str, Any]]] = None

        private_key = blockchain_cfg.get("operator_private_key")
        self.account = Account.from_key(private_key) if private_key else None
        if self.account:
            logger.info("Operator account loaded: %s", self.account.address)

        gas_price_setting = blockchain_cfg.get("gas_price")
        self._gas_price_override: Optional[int] = None
        if gas_price_setting:
            try:
                self._gas_price_override = Web3.to_wei(Decimal(str(gas_price_setting)), "gwei")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Unable to parse gas price '%s': %s", gas_price_setting, exc)

        self._gas_multiplier = float(blockchain_cfg.get("gas_multiplier", 1.15))
        self._latest_block: Optional[int] = None

    async def initialize(self) -> None:
        """Establish the RPC connection and load the contract."""
        self._w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self._w3.is_connected():  # pragma: no cover - depends on live RPC
            raise ConnectionError(f"Failed to connect to RPC at {self.rpc_url}")

        logger.info("Connected to RPC %s (chain id %s)", self.rpc_url, self.chain_id)
        await self._load_contract()

    async def close(self) -> None:
        """Tear down references; HTTP provider closes automatically."""
        self._contract = None
        self._w3 = None

    async def _load_contract(self) -> None:
        if not self.contract_address:
            logger.warning("No contract address configured; blockchain operations disabled")
            return

        abi_path = self._resolve_abi_path()
        logger.info("Loading Lottery ABI from %s", abi_path)
        with abi_path.open("r", encoding="utf-8") as handle:
            self.contract_abi = json.load(handle)

        def _build_contract() -> Contract:
            assert self._w3 is not None
            return self._w3.eth.contract(address=self.contract_address, abi=self.contract_abi)

        self._contract = await asyncio.to_thread(_build_contract)
        logger.info("Contract bound at %s", self.contract_address)

    def _resolve_abi_path(self) -> Path:
        """Resolve the ABI path based on known locations."""
        search_roots = [
            Path(__file__).parent.parent / "contracts" / "abi" / "Lottery.abi",
        ]

        for candidate in search_roots:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError("Lottery ABI file not found in expected locations")

    def _ensure_contract(self) -> Contract:
        if not self._contract:
            raise RuntimeError("Contract not initialised")
        return self._contract

    def _ensure_web3(self) -> Web3:
        if not self._w3:
            raise RuntimeError("Web3 provider not initialised")
        return self._w3

    async def _call_view(self, function_name: str, *args) -> Any:
        contract = self._ensure_contract()

        def _call():
            return getattr(contract.functions, function_name)(*args).call()

        return await asyncio.to_thread(_call)

    async def _send_transaction(self, function_name: str, *args, value: int = 0) -> str:
        if not self.account:
            raise ValueError("Operator account not configured")

        contract = self._ensure_contract()
        w3 = self._ensure_web3()

        def _send() -> str:
            tx_function = getattr(contract.functions, function_name)(*args)
            gas_estimate = tx_function.estimate_gas({"from": self.account.address, "value": value})
            gas_price = self._gas_price_override or w3.eth.gas_price
            txn = tx_function.build_transaction(
                {
                    "from": self.account.address,
                    "value": value,
                    "gas": int(gas_estimate * self._gas_multiplier),
                    "gasPrice": gas_price,
                    "nonce": w3.eth.get_transaction_count(self.account.address),
                    "chainId": self.chain_id,
                }
            )
            signed = self.account.sign_transaction(txn)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            return tx_hash.hex()

        tx_hash = await asyncio.to_thread(_send)
        logger.info("Sent transaction %s for %s", tx_hash, function_name)
        return tx_hash

    async def get_contract_config(self) -> ContractConfig:
        raw = await self._call_view("getConfig")
        return ContractConfig(
            publisher_addr=self._select(raw, "publisherAddr", 0),
            sparsity_addr=self._select(raw, "sparsityAddr", 1),
            operator_addr=self._select(raw, "operatorAddr", 2),
            publisher_commission=int(self._select(raw, "publisherCommission", 3)),
            sparsity_commission=int(self._select(raw, "sparsityCommission", 4)),
            min_bet=int(self._select(raw, "minBet", 5)),
            betting_duration=int(self._select(raw, "bettingDur", 6)),
            min_draw_delay=int(self._select(raw, "minDrawDelay", 7)),
            max_draw_delay=int(self._select(raw, "maxDrawDelay", 8)),
            min_end_time_extension=int(self._select(raw, "minEndTimeExt", 9)),
            min_participants=int(self._select(raw, "minPart", 10)),
        )

    async def get_current_round(self) -> Optional[LotteryRound]:
        raw = await self._call_view("getRound")
        round_id = int(self._select(raw, "roundId", 0))

        winner = self._select(raw, "winner", 7)
        if isinstance(winner, str) and winner.lower() == "0x0000000000000000000000000000000000000000":
            winner = None

        # log the raw round data for debugging purpose
        logger.info("Current round raw data: %s", raw)
        return LotteryRound(
            round_id=round_id,
            start_time=int(self._select(raw, "startTime", 1)),
            end_time=int(self._select(raw, "endTime", 2)),
            min_draw_time=int(self._select(raw, "minDrawTime", 3)),
            max_draw_time=int(self._select(raw, "maxDrawTime", 4)),
            total_pot=int(self._select(raw, "totalPot", 5)),
            participant_count=int(self._select(raw, "participantCount", 6)),
            winner=winner,
            publisher_commission=int(self._select(raw, "publisherCommission", 8)),
            sparsity_commission=int(self._select(raw, "sparsityCommission", 9)),
            winner_prize=int(self._select(raw, "winnerPrize", 10)),
            state=RoundState(int(self._select(raw, "state", 11))),
        )

    async def get_participant_summaries(self, round_id: int) -> List[ParticipantSummary]:
        if round_id == 0:
            return []

        addresses: Iterable[str] = await self._call_view("getParticipants")
        summaries: List[ParticipantSummary] = []
        for address in addresses:
            amount = int(await self._call_view("getBetAmount", address))
            if amount > 0:
                summaries.append(ParticipantSummary(address=address, total_amount=amount, bet_count=1))
        return summaries

    async def get_events(self, from_block: int) -> List[BlockchainEvent]:
        contract = self._ensure_contract()
        w3 = self._ensure_web3()
        event_names = [
            "RoundCreated",
            "RoundStateChanged",
            "BetPlaced",
            "EndTimeExtended",
            "RoundCompleted",
            "RoundRefunded",
            "MinBetAmountUpdated",
            "BettingDurationUpdated",
            "MinParticipantsUpdated",
        ]

        def _fetch() -> List[BlockchainEvent]:
            collected: List[BlockchainEvent] = []
            for name in event_names:
                event_klass = getattr(contract.events, name, None)
                if not event_klass:
                    continue
                try:
                    logs = []
                    event_obj = None
                    try:
                        if callable(event_klass):
                            event_obj = event_klass()
                    except Exception:
                        event_obj = None

                    # Try createFilter on the instance first
                    if event_obj is not None and hasattr(event_obj, 'createFilter'):
                        event_filter = event_obj.createFilter(fromBlock=from_block, toBlock="latest")
                        logs = event_filter.get_all_entries()
                    elif hasattr(event_klass, 'createFilter'):
                        event_filter = event_klass.createFilter(fromBlock=from_block, toBlock="latest")
                        logs = event_filter.get_all_entries()
                    else:
                        # Fallback: use w3.eth.get_logs and try to decode using processLog if available
                        if not hasattr(w3.eth, 'get_logs'):
                            logger.warning("No compatible event log API available for %s", name)
                            continue
                        filter_params = {"fromBlock": from_block, "toBlock": "latest", "address": self.contract_address}
                        try:
                            raw_logs = w3.eth.get_logs(filter_params)
                        except Exception as exc:
                            logger.warning("Event fetch fallback failed for %s: %s", name, exc)
                            continue
                        decoded = []
                        try:
                            if event_obj is None and callable(event_klass):
                                try:
                                    event_obj = event_klass()
                                except Exception:
                                    event_obj = None
                            if event_obj is not None and hasattr(event_obj, 'processLog'):
                                for raw in raw_logs:
                                    try:
                                        processed = event_obj.processLog(raw)
                                        decoded.append(processed)
                                    except Exception:
                                        decoded.append(raw)
                                logs = decoded
                            else:
                                logs = list(raw_logs)
                        except Exception:
                            logs = list(raw_logs)
                except ValueError as exc:
                    logger.warning("Event fetch failed for %s: %s", name, exc)
                    continue
                for log in logs:
                    # Only process logs that have 'args' (decoded events)
                    if "args" not in log:
                        continue
                    block_number = log["blockNumber"]
                    block = w3.eth.get_block(block_number)
                    collected.append(
                        BlockchainEvent(
                            name=name,
                            args=dict(log["args"]),
                            block_number=block_number,
                            transaction_hash=log["transactionHash"].hex(),
                            timestamp=int(block["timestamp"]),
                        )
                    )
            collected.sort(key=lambda evt: (evt.block_number, evt.transaction_hash))
            return collected

        events = await asyncio.to_thread(_fetch)
        if events:
            self._latest_block = max(event.block_number for event in events)
        return events

    async def draw_round(self, round_id: int) -> str:
        return await self._send_transaction("drawWinner", round_id)

    async def refund_round(self, round_id: int) -> str:
        return await self._send_transaction("refundRound", round_id)

    async def wait_for_transaction(self, tx_hash: str, timeout: int = 180) -> Dict[str, Any]:
        w3 = self._ensure_web3()

        def _wait():
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return {
                "status": int(receipt["status"]),
                "blockNumber": int(receipt["blockNumber"]),
                "transactionHash": receipt["transactionHash"].hex(),
                "gasUsed": int(receipt["gasUsed"]),
            }

        return await asyncio.to_thread(_wait)

    async def get_block_timestamp(self, block_number: int) -> int:
        w3 = self._ensure_web3()

        def _fetch() -> int:
            block = w3.eth.get_block(block_number)
            return int(block["timestamp"])

        return await asyncio.to_thread(_fetch)

    async def get_latest_block(self) -> int:
        if self._latest_block is not None:
            return self._latest_block
        w3 = self._ensure_web3()

        def _fetch() -> int:
            return int(w3.eth.block_number)

        self._latest_block = await asyncio.to_thread(_fetch)
        return self._latest_block

    async def health_check(self) -> Dict[str, Any]:
        try:
            latest_block = await self.get_latest_block()
            return {"status": "healthy", "latestBlock": latest_block}
        except Exception as exc:  # pragma: no cover - health failures are diagnostic
            logger.exception("Blockchain health check failed")
            return {"status": "error", "detail": str(exc)}

    def get_client_status(self) -> Dict[str, Any]:
        return {
            "rpcUrl": self.rpc_url,
            "chainId": self.chain_id,
            "contract": self.contract_address,
            "operator": self.account.address if self.account else None,
        }

    @staticmethod
    def _select(mapping_or_tuple: Any, key: str, index: int) -> Any:
        if isinstance(mapping_or_tuple, dict):
            if key in mapping_or_tuple:
                return mapping_or_tuple[key]
        return mapping_or_tuple[index]