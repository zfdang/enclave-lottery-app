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

from utils.logger import get_logger

logger = get_logger(__name__)


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
        self.rpc_url: str = blockchain_cfg.get("rpc_url", "http://18.144.124.66:8545")
        # per-RPC timeout (seconds) to pass to HTTPProvider to avoid blocking requests
        try:
            self.rpc_timeout: float = float(blockchain_cfg.get("rpc_timeout", 10.0))
        except Exception:
            self.rpc_timeout = 10.0
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
        
        # latest_block is the latest block number from the chain
        self._latest_block: Optional[int] = None
        self._last_seen_block: Optional[int] = None

    def get_last_seen_block(self) -> int:
        """Return the last seen block number (internal sync pointer)."""
        return getattr(self, '_last_seen_block', 0)
    
    async def initialize(self) -> None:
        """Establish the RPC connection and load the contract."""
        # configure provider with a request timeout so synchronous calls don't hang indefinitely
        try:
            self._w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": self.rpc_timeout}))
        except TypeError:
            # older web3 may not accept request_kwargs, fall back to default provider
            logger.debug("HTTPProvider does not accept request_kwargs; falling back without timeout")
            self._w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self._w3.is_connected():  # pragma: no cover - depends on live RPC
            raise ConnectionError(f"Failed to connect to RPC at {self.rpc_url}")

        logger.info("Connected to RPC %s (chain id %s)", self.rpc_url, self.chain_id)
        
        # Verify chain ID matches
        try:
            actual_chain_id = self._w3.eth.chain_id
            if actual_chain_id != self.chain_id:
                logger.warning(f"Chain ID mismatch: expected {self.chain_id}, got {actual_chain_id}")
        except Exception as exc:
            logger.warning(f"Could not verify chain ID: {exc}")
        
        # Log latest block for debugging
        try:
            latest_block = self._w3.eth.block_number
            logger.info(f"Latest block number: {latest_block}")
        except Exception as exc:
            logger.warning(f"Could not get latest block: {exc}")
        
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
        
        logger.info(f"Loaded ABI with {len(self.contract_abi)} items")

        def _build_contract() -> Contract:
            assert self._w3 is not None
            return self._w3.eth.contract(address=self.contract_address, abi=self.contract_abi)

        self._contract = await asyncio.to_thread(_build_contract)
        logger.info("Contract bound at %s", self.contract_address)

        # Build event topic -> ABI map for fast decoding later
        self._event_abi_by_topic: Dict[str, Dict[str, Any]] = {}
        try:
            from eth_utils import event_abi_to_log_topic  # type: ignore
            for item in self.contract_abi or []:
                if item.get("type") == "event":
                    try:
                        topic = event_abi_to_log_topic(item).hex()
                        self._event_abi_by_topic[topic] = item
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.debug("Failed to derive topic for event %s: %s", item.get("name"), exc)
            logger.info("Prepared %d event ABI topics", len(self._event_abi_by_topic))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not prepare event topic map: %s", exc)
        
        # Verify contract exists and has code
        try:
            code = self._w3.eth.get_code(self.contract_address)
            if code == b'\x00' or len(code) == 0:
                logger.error(f"No contract code found at address {self.contract_address}")
                raise ValueError(f"No contract deployed at {self.contract_address}")
            else:
                logger.info(f"Contract verified at {self.contract_address} with {len(code)} bytes of code")
        except Exception as exc:
            logger.error(f"Failed to verify contract at {self.contract_address}: {exc}")
            raise
        
        # Test basic contract call
        try:
            config = await self._call_view("getConfig")
            logger.info(f"Contract config retrieved successfully: publisher={config[0][:10]}..., operator={config[2][:10] if config[2] else 'None'}...")
        except Exception as exc:
            logger.error(f"Failed to call getConfig on contract: {exc}")
            raise

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
            # signed may expose the raw bytes under different attribute names
            raw = None
            for attr in ("rawTransaction", "raw_transaction", "raw", "rawTx"):
                raw = getattr(signed, attr, None)
                if raw is not None:
                    logger.debug("Using signed transaction attribute '%s'", attr)
                    break

            # fallback: if signed itself looks like bytes/hex, try to use it
            if raw is None:
                raw = signed

            # normalize to raw bytes
            if isinstance(raw, str):
                # hex string
                raw_bytes = bytes.fromhex(raw[2:]) if raw.startswith("0x") else bytes.fromhex(raw)
            else:
                raw_bytes = raw

            tx_hash = w3.eth.send_raw_transaction(raw_bytes)
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
                summaries.append(ParticipantSummary(address=address, total_amount=amount))
        return summaries

    async def get_events(self, from_block: int) -> List[BlockchainEvent]:
        w3 = self._ensure_web3()
        self._ensure_contract()  # ensure loaded
        
        logger.info("get_events: start from block %s", from_block)

        def _fetch() -> List[BlockchainEvent]:
            from web3._utils.events import get_event_data  # type: ignore
            collected: List[BlockchainEvent] = []
            
            # get last block number first, then fetch logs from from_block to latest
            try:
                self._latest_block = int(w3.eth.block_number)
            except Exception as exc:
                logger.error("Failed to get latest block number: %s", exc)
                return []
            if from_block > self._latest_block:
                logger.info("Requested block %s is ahead of latest block %s, skip", from_block, self._latest_block)
                return []

            logger.info("Fetching events from block %s to %d for contract %s", from_block, self._latest_block, self.contract_address)
            try:
                filter_params = {
                    "fromBlock": from_block,
                    "toBlock": self._latest_block,
                    "address": self.contract_address,
                }
                raw_logs = w3.eth.get_logs(filter_params)
                logger.info("Fetched %d logs", len(raw_logs))
            except Exception as exc:
                logger.error("Failed to fetch logs: %s", exc)
                return []

            for raw in raw_logs:
                logger.debug("Block %d ...", raw.get("blockNumber"))
                logger.debug("Block %d, Raw log: %s", raw.get("blockNumber"), raw)
                # track the last seen block for future fetches
                self._last_seen_block = raw.get("blockNumber")
                
                topics = [t.hex() if isinstance(t, (bytes, bytearray)) else t for t in raw.get("topics", [])]
                if not topics:
                    logger.debug("Skipping log without topics: %s", raw)
                    continue
                sig = topics[0]
                abi = getattr(self, "_event_abi_by_topic", {}).get(sig)
                if not abi:
                    logger.info("Unknown event topic %s", sig)
                    continue
                logger.debug("Decoding event with topic %s using ABI %s", sig, abi.get("name"))
                try:
                    decoded = get_event_data(w3.codec, abi, raw)
                    block_no = int(decoded["blockNumber"])
                    try:
                        block = w3.eth.get_block(block_no)
                        ts = int(block["timestamp"])
                    except Exception:
                        ts = 0
                    collected.append(
                        BlockchainEvent(
                            name=abi.get("name", "Unknown"),
                            args=dict(decoded["args"]),
                            block_number=block_no,
                            transaction_hash=decoded["transactionHash"].hex(),
                            timestamp=ts,
                        )
                    )
                    logger.debug("Decoded event %s", decoded["args"])
                except Exception as exc:  # pragma: no cover - decode failures
                    logger.info("Failed to decode log %s: %s", raw, exc)
                    continue
    
            # sort by block number, then transaction hash for deterministic order
            collected.sort(key=lambda evt: (evt.block_number, evt.transaction_hash))
            logger.info("Decoded %d events from block %s to %s", len(collected), from_block, self._latest_block)
            return collected

        try:
            # Protect against a permanently blocking thread by bounding the await.
            wait_timeout = max(15.0, float(getattr(self, "rpc_timeout", 10.0)) * 5)
            events: List[BlockchainEvent] = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=wait_timeout)
        except asyncio.TimeoutError:
            logger.warning("get_events timed out after %ss", wait_timeout)
            return []
        if events:
            self._latest_block = max(e.block_number for e in events)
        return events

    async def draw_round(self, round_id: int) -> str:
        return await self._send_transaction("drawWinner")

    async def refund_round(self, round_id: int) -> str:
        return await self._send_transaction("refundRound")

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