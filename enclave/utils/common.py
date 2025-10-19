"""Common utility functions for the enclave backend."""

def shorten_eth_address(address: str) -> str:
    """Shorten an Ethereum address for display: '0x123456...abcd'.
    Returns the first 6 and last 4 characters, separated by '...'.
    Handles addresses with or without '0x' prefix.
    """
    if not address:
        return ""
    addr = address.lower()
    if addr.startswith("0x"):
        addr = addr[2:]
    # Always add 0x prefix
    if len(addr) < 10:
        return f"0x{addr}"  # too short to shorten, but ensure 0x
    return f"0x{addr[:6]}...{addr[-4:]}"
