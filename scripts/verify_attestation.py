#!/usr/bin/env python3
"""Download and perform best-effort verification of an enclave attestation.

This script fetches the JSON returned by the /api/attestation endpoint, decodes
base64 fields (attestation_document and user_data), attempts to parse the
attestation document as JSON (or prints raw bytes), inspects the certificate
and CA bundle returned by the endpoint, and performs a best-effort certificate
chain verification using OpenSSL if available.

Usage:
  python scripts/verify_attestation.py --url http://localhost:6080/api/attestation

The script is intentionally defensive: the exact structure of the attestation
document can vary by provider, so it focuses on decoding, extracting, and
verifying certificates and printing the decoded user_data.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization


def fetch_attestation(url: str, timeout: int = 10) -> Dict[str, Any]:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def b64decode_str(data: Optional[str]) -> Optional[bytes]:
    if not data:
        return None
    try:
        return base64.b64decode(data)
    except Exception:
        return None


def try_parse_json(data: bytes) -> Optional[Dict[str, Any]]:
    try:
        text = data.decode("utf-8")
        return json.loads(text)
    except Exception:
        return None


def try_parse_cbor(data: bytes) -> Optional[Any]:
    """Try to parse bytes as CBOR using cbor2 if available.

    Returns the decoded Python object or None if parsing is not possible.
    """
    try:
        import cbor2  # type: ignore

        try:
            return cbor2.loads(data)
        except Exception:
            return None
    except ImportError:
        # cbor2 not installed; caller can decide how to proceed
        return None


def inspect_certificate(pem_text: str) -> Optional[x509.Certificate]:
    try:
        cert = x509.load_pem_x509_certificate(pem_text.encode("utf-8"))
        return cert
    except Exception:
        return None


def print_cert_info(cert: x509.Certificate) -> None:
    subj = cert.subject.rfc4514_string()
    issuer = cert.issuer.rfc4514_string()
    not_before = cert.not_valid_before
    not_after = cert.not_valid_after
    print(f"  Subject: {subj}")
    print(f"  Issuer:  {issuer}")
    print(f"  Valid:   {not_before.isoformat()} -> {not_after.isoformat()}")


def verify_chain_openssl(leaf_pem: str, cabundle_pems: List[str]) -> bool:
    """Attempt to verify `leaf_pem` against `cabundle_pems` using openssl verify.

    Returns True if verification succeeds, False otherwise or if openssl is
    unavailable or returns non-zero.
    """
    openssl = shutil.which("openssl")
    if not openssl:
        print("OpenSSL not found on PATH; skipping chain verification (install openssl to enable).")
        return False

    with tempfile.TemporaryDirectory() as td:
        leaf_path = f"{td}/leaf.pem"
        cabundle_path = f"{td}/cabundle.pem"
        with open(leaf_path, "w") as f:
            f.write(leaf_pem)
        with open(cabundle_path, "w") as f:
            for pem in cabundle_pems:
                f.write(pem)
                if not pem.endswith("\n"):
                    f.write("\n")

        try:
            # openssl verify -CAfile cabundle.pem leaf.pem
            proc = subprocess.run([openssl, "verify", "-CAfile", cabundle_path, leaf_path], capture_output=True, text=True)
            print(proc.stdout.strip())
            if proc.returncode == 0:
                return True
            else:
                print(proc.stderr.strip())
                return False
        except Exception as exc:
            print(f"OpenSSL verify failed: {exc}")
            return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify enclave attestation from an API endpoint")
    parser.add_argument("--url", default="http://localhost:6080/api/attestation", help="Full URL to the /api/attestation endpoint")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--save", help="Optional path to save the raw attestation document bytes")
    args = parser.parse_args(argv)

    try:
        data = fetch_attestation(args.url, timeout=args.timeout)
    except Exception as exc:
        print(f"Failed to fetch attestation from {args.url}: {exc}")
        return 2

    print("Attestation endpoint response keys:", ", ".join(sorted(data.keys())))

    # Print top-level metadata
    if "timestamp" in data:
        try:
            ts = int(data.get("timestamp"))
            print("Timestamp:", datetime.fromtimestamp(ts / 1000.0).isoformat())
        except Exception:
            print("Timestamp:", data.get("timestamp"))

    print("Verified flag:", data.get("verified"))

    # CABUNDLE and certificate
    certificate_pem = data.get("certificate")
    cabundle = data.get("cabundle") or []
    if isinstance(cabundle, str):
        cabundle = [cabundle]

    if certificate_pem:
        print("\nLeaf certificate:")
        cert = inspect_certificate(certificate_pem)
        if cert:
            print_cert_info(cert)
        else:
            print("  (failed to parse PEM certificate)")
    else:
        print("\nNo certificate present in response")

    if cabundle:
        print(f"\nCA bundle contains {len(cabundle)} entries")
        for idx, pem in enumerate(cabundle):
            print(f" CA[{idx}]:")
            cert = inspect_certificate(pem)
            if cert:
                print_cert_info(cert)
            else:
                print("   (failed to parse PEM)")

    # Attempt chain verification if we have a leaf certificate and cabundle
    chain_ok = False
    if certificate_pem and cabundle:
        print("\nAttempting certificate chain verification with OpenSSL...")
        try:
            chain_ok = verify_chain_openssl(certificate_pem, cabundle)
        except Exception as exc:
            print("Chain verification raised an error:", exc)

    print("Chain verification result:", chain_ok)

    # Decode user_data
    user_data_b64 = data.get("user_data")
    user_bytes = b64decode_str(user_data_b64)
    if user_bytes:
        # Try JSON
        user_json = None
        try:
            user_json = json.loads(user_bytes.decode("utf-8"))
        except Exception:
            pass

        print("\nDecoded user_data:")
        if user_json:
            print(json.dumps(user_json, indent=2))
        else:
            # Print as text or hex
            try:
                print(user_bytes.decode("utf-8"))
            except Exception:
                print(user_bytes.hex())
    else:
        print("\nNo user_data or failed to decode base64 user_data")

    # Decode attestation document
    att_b64 = data.get("attestation_document") or data.get("attestation") or data.get("document")
    att_bytes = b64decode_str(att_b64) if isinstance(att_b64, str) else None
    if att_bytes:
        if args.save:
            try:
                with open(args.save, "wb") as f:
                    f.write(att_bytes)
                print(f"\nSaved raw attestation document to {args.save}")
            except Exception as exc:
                print(f"Failed to save attestation document to {args.save}: {exc}")

        print("\nAttempting to parse attestation document as JSON...")
        parsed = try_parse_json(att_bytes)
        if parsed is not None:
            print("Attestation document parsed as JSON:")
            print(json.dumps(parsed, indent=2))
        else:
            # Try CBOR if JSON parsing failed
            print("JSON parse failed; attempting CBOR parse (if cbor2 is installed)...")
            cbor_parsed = try_parse_cbor(att_bytes)
            if cbor_parsed is not None:
                print("Attestation document parsed as CBOR:")
                try:
                    # Attempt to pretty-print as JSON if possible
                    print(json.dumps(cbor_parsed, indent=2, default=str))
                except Exception:
                    # Fallback to repr
                    print("<CBOR representation failed>")
                    print(repr(cbor_parsed))
            else:
                try:
                    text = att_bytes.decode("utf-8")
                    print("Attestation document (text):")
                    print(text)
                except Exception:
                    print("Attestation document is binary (hex):")
                    print(att_bytes.hex())
    else:
        print("\nNo attestation_document field found or failed to base64-decode it.")

    # PCRs
    pcrs = data.get("pcrs") or {}
    if isinstance(pcrs, dict) and pcrs:
        print("\nPCRs:")
        for k, v in sorted(pcrs.items()):
            print(f"  PCR{k}: {v}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
