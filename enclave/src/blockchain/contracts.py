"""
Smart Contract Interface and Management
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContractManager:
    """Manages smart contract interactions"""
    
    def __init__(self, blockchain_client):
        self.blockchain_client = blockchain_client
        self.contracts_dir = Path(__file__).parent / "contracts"
        
    def load_contract_artifacts(self, contract_name: str) -> Dict:
        """Load compiled contract artifacts"""
        try:
            abi_file = self.contracts_dir / "compiled" / f"{contract_name}.abi"
            bin_file = self.contracts_dir / "compiled" / f"{contract_name}.bin"
            
            artifacts = {}
            
            if abi_file.exists():
                artifacts['abi'] = json.loads(abi_file.read_text())
            else:
                logger.warning(f"ABI file not found: {abi_file}")
                
            if bin_file.exists():
                artifacts['bytecode'] = bin_file.read_text().strip()
            else:
                logger.warning(f"Bytecode file not found: {bin_file}")
                
            return artifacts
            
        except Exception as e:
            logger.error(f"Error loading contract artifacts for {contract_name}: {e}")
            return {}
            
    def get_lottery_contract_abi(self) -> List:
        """Get the lottery contract ABI"""
        artifacts = self.load_contract_artifacts("Lottery")
        return artifacts.get('abi', [])
        
    def get_lottery_contract_bytecode(self) -> str:
        """Get the lottery contract bytecode"""
        artifacts = self.load_contract_artifacts("Lottery")
        return artifacts.get('bytecode', '')
        
    def estimate_gas(self, contract_function, *args) -> int:
        """Estimate gas for contract function call"""
        try:
            return contract_function(*args).estimate_gas()
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            return 200000  # Default gas limit
            
    def get_contract_events(self, contract, event_name: str, from_block: int = 0) -> List[Dict]:
        """Get contract events"""
        try:
            event_filter = getattr(contract.events, event_name).create_filter(
                fromBlock=from_block
            )
            return event_filter.get_all_entries()
        except Exception as e:
            logger.error(f"Error getting contract events: {e}")
            return []