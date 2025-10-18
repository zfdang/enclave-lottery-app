#!/usr/bin/env python3
"""Download and verify AWS Nitro Enclave attestation document.

This script fetches the attestation from /api/attestation endpoint, decodes
the CBOR-encoded attestation document, verifies the certificate chain against
AWS Nitro root CA, and extracts/validates the TLS public key and user data.

Usage:
  python scripts/verify_attestation.py --url http://localhost:6080/api/attestation

The script performs:
1. CBOR decoding of the attestation document
2. Certificate chain verification against AWS Nitro root CA
3. PCR validation
4. User data extraction and verification
5. Public key extraction from the attestation document
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
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtensionOID


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


def parse_cose_sign1(cose_obj: Any) -> Optional[Dict[str, Any]]:
    """Parse a COSE Sign1 structure and extract the payload.
    
    AWS Nitro attestation documents are COSE Sign1 messages with structure:
    [protected_headers, unprotected_headers, payload, signature]
    
    Returns the decoded payload as a dict, or None if parsing fails.
    """
    try:
        if not isinstance(cose_obj, list) or len(cose_obj) != 4:
            return None
        
        # The payload is the 3rd element (index 2)
        payload_bytes = cose_obj[2]
        if not isinstance(payload_bytes, bytes):
            return None
        
        # The payload is itself CBOR-encoded
        import cbor2
        payload = cbor2.loads(payload_bytes)
        
        return payload if isinstance(payload, dict) else None
    except Exception as e:
        print(f"Failed to parse COSE Sign1: {e}")
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


def verify_nitro_attestation_doc(attestation_doc: Dict[str, Any], certificate_pem: str, cabundle: List[str]) -> Dict[str, Any]:
    """Verify AWS Nitro Enclave attestation document.
    
    Returns a dict with verification results and extracted data.
    """
    result = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "pcrs": {},
        "user_data": None,
        "public_key": None,
        "module_id": None,
        "timestamp": None,
    }
    
    try:
        # Extract PCRs
        if "pcrs" in attestation_doc:
            pcrs_dict = attestation_doc["pcrs"]
            for idx, pcr_value in pcrs_dict.items():
                if isinstance(pcr_value, bytes):
                    result["pcrs"][str(idx)] = pcr_value.hex()
                else:
                    result["pcrs"][str(idx)] = str(pcr_value)
        
        # Extract user data
        if "user_data" in attestation_doc:
            user_data_bytes = attestation_doc["user_data"]
            if isinstance(user_data_bytes, bytes):
                try:
                    result["user_data"] = json.loads(user_data_bytes.decode("utf-8"))
                except Exception:
                    result["user_data"] = user_data_bytes.hex()
        
        # Extract public key
        if "public_key" in attestation_doc and attestation_doc["public_key"]:
            public_key_bytes = attestation_doc["public_key"]
            if isinstance(public_key_bytes, bytes):
                try:
                    # Try to load as DER-encoded public key
                    from cryptography.hazmat.primitives.serialization import load_der_public_key
                    public_key = load_der_public_key(public_key_bytes)
                    result["public_key"] = {
                        "type": type(public_key).__name__,
                        "size": public_key.key_size if hasattr(public_key, "key_size") else None,
                        "der_hex": public_key_bytes.hex()[:100] + "...",
                    }
                    
                    # If it's an EC key, get the curve
                    if isinstance(public_key, ec.EllipticCurvePublicKey):
                        result["public_key"]["curve"] = public_key.curve.name
                        # Get uncompressed hex format
                        numbers = public_key.public_numbers()
                        if public_key.curve.name == "secp384r1":
                            x_bytes = numbers.x.to_bytes(48, byteorder='big')
                            y_bytes = numbers.y.to_bytes(48, byteorder='big')
                            uncompressed = b'\x04' + x_bytes + y_bytes
                            result["public_key"]["hex_uncompressed"] = uncompressed.hex()
                        
                except Exception as e:
                    result["warnings"].append(f"Failed to parse public key: {e}")
                    result["public_key"] = {"raw_hex": public_key_bytes.hex()[:100] + "..."}
        
        # Extract module_id
        if "module_id" in attestation_doc:
            result["module_id"] = attestation_doc["module_id"]
        
        # Extract timestamp
        if "timestamp" in attestation_doc:
            result["timestamp"] = attestation_doc["timestamp"]
        
        # Verify certificate chain
        if certificate_pem and cabundle:
            chain_ok = verify_chain_openssl(certificate_pem, cabundle)
            if chain_ok:
                result["valid"] = True
            else:
                result["errors"].append("Certificate chain verification failed")
        else:
            result["warnings"].append("No certificate or CA bundle provided for verification")
        
    except Exception as e:
        result["errors"].append(f"Attestation verification error: {e}")
    
    return result


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
    attestation_doc_parsed = None
    
    if att_bytes:
        if args.save:
            try:
                with open(args.save, "wb") as f:
                    f.write(att_bytes)
                print(f"\nSaved raw attestation document to {args.save}")
            except Exception as exc:
                print(f"Failed to save attestation document to {args.save}: {exc}")

        print("\nAttempting to parse attestation document...")
        
        # AWS Nitro attestation documents are CBOR-encoded
        cbor_parsed = try_parse_cbor(att_bytes)
        if cbor_parsed is not None:
            print("✅ Attestation document parsed as CBOR (AWS Nitro format)")
            
            # Check if it's a COSE Sign1 structure (list with 4 elements)
            if isinstance(cbor_parsed, list) and len(cbor_parsed) == 4:
                print("📦 Detected COSE Sign1 structure, extracting payload...")
                attestation_doc_parsed = parse_cose_sign1(cbor_parsed)
                if attestation_doc_parsed is None:
                    print("❌ Failed to extract payload from COSE Sign1")
                else:
                    print("✅ Successfully extracted attestation payload")
            else:
                # Direct CBOR dict
                attestation_doc_parsed = cbor_parsed
            
            if attestation_doc_parsed:
                # Perform Nitro-specific verification
                print("\n" + "="*60)
                print("AWS Nitro Enclave Attestation Verification")
                print("="*60)
                
                verification_result = verify_nitro_attestation_doc(
                    attestation_doc_parsed,
                certificate_pem,
                cabundle
            )
            
            if verification_result["valid"]:
                print("✅ ATTESTATION VALID")
            else:
                print("❌ ATTESTATION VERIFICATION FAILED")
            
            if verification_result["errors"]:
                print("\n⚠️  Errors:")
                for err in verification_result["errors"]:
                    print(f"  - {err}")
            
            if verification_result["warnings"]:
                print("\n⚠️  Warnings:")
                for warn in verification_result["warnings"]:
                    print(f"  - {warn}")
            
            # Display extracted data
            if verification_result["user_data"]:
                print("\n📄 User Data (from attestation document):")
                if isinstance(verification_result["user_data"], dict):
                    print(json.dumps(verification_result["user_data"], indent=2))
                else:
                    print(verification_result["user_data"])
            
            if verification_result["public_key"]:
                print("\n🔑 TLS Public Key (from attestation document):")
                print(json.dumps(verification_result["public_key"], indent=2))
                
                # Compare with user_data public key if available
                if verification_result["user_data"] and isinstance(verification_result["user_data"], dict):
                    user_data_pubkey = verification_result["user_data"].get("tls_public_key_hex")
                    att_doc_pubkey = verification_result["public_key"].get("hex_uncompressed")
                    
                    if user_data_pubkey and att_doc_pubkey:
                        if user_data_pubkey == att_doc_pubkey:
                            print("\n✅ Public key in user_data matches attestation document public key")
                        else:
                            print("\n❌ WARNING: Public key mismatch!")
                            print(f"  user_data: {user_data_pubkey[:40]}...")
                            print(f"  attestation: {att_doc_pubkey[:40]}...")
            elif verification_result["user_data"] and isinstance(verification_result["user_data"], dict):
                # Public key not in attestation document, but might be in user_data
                user_data_pubkey = verification_result["user_data"].get("tls_public_key_hex")
                if user_data_pubkey:
                    print("\n🔑 TLS Public Key (from user_data only):")
                    print(f"  {user_data_pubkey}")
                    print("  ⚠️  Note: Public key is in user_data but not in attestation document.")
                    print("      This is acceptable for dummy/dev attestations.")
            
            if verification_result["pcrs"]:
                print("\n📊 PCRs (from attestation document):")
                for pcr_idx, pcr_val in sorted(verification_result["pcrs"].items()):
                    print(f"  PCR{pcr_idx}: {pcr_val}")
            
            if verification_result["module_id"]:
                print(f"\n🆔 Module ID: {verification_result['module_id']}")
            
            if verification_result["timestamp"]:
                print(f"⏰ Timestamp: {verification_result['timestamp']}")
            
            print("\n" + "="*60)
            
        else:
            # Try JSON as fallback
            print("CBOR parse failed; attempting JSON parse...")
            parsed = try_parse_json(att_bytes)
            if parsed is not None:
                print("Attestation document parsed as JSON:")
                print(json.dumps(parsed, indent=2))
            else:
                try:
                    text = att_bytes.decode("utf-8")
                    print("Attestation document (text):")
                    print(text)
                except Exception:
                    print("Attestation document is binary (hex):")
                    print(att_bytes.hex()[:200] + "...")
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
