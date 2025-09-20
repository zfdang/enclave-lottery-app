# Lottery Enclave - Security Documentation

## Security Overview

For an architectural overview and hands-on demos, see:
- Architecture: `docs/architecture.md`
- Demos: `./demo.sh` (CLI) or `scripts/comprehensive_demo.sh` (web)

The Lottery Enclave implements multiple layers of security to ensure fairness, transparency, and protection against various attack vectors. This document outlines the security architecture, threat model, and implementation details.

## Security Architecture

### 1. AWS Nitro Enclave Foundation

#### Hardware Security Module (HSM)
- **Hardware Root of Trust**: Cryptographic operations backed by AWS Nitro hardware
- **Memory Encryption**: All enclave memory encrypted with ephemeral keys
- **Attestation**: Cryptographic proof of enclave code integrity and identity
- **Isolation**: Complete isolation from host OS and other processes

#### Attestation Process
```
1. Enclave boots with measured code
2. Hardware generates attestation document
3. Document includes:
   - Code measurements (PCR values)
   - Enclave public key
   - Timestamp and nonce
   - Hardware signature
4. Users verify attestation before trusting
```

#### Secure Boot Chain
- **Platform Configuration Registers (PCRs)**: Cryptographic measurements of all code
- **Chain of Trust**: From AWS hardware to application code
- **Tamper Detection**: Any code modification invalidates attestation
- **Version Control**: Each code update generates new measurements

### 2. Cryptographic Security

#### Random Number Generation
```python
# Secure random number generation
import secrets
import hashlib

def generate_secure_random(participants_count: int, timestamp: int) -> int:
    """
    Cryptographically secure random number generation
    Uses hardware entropy + additional entropy sources
    """
    # Primary entropy from hardware
    entropy = secrets.randbits(256)
    
    # Additional entropy from lottery state
    additional_entropy = hashlib.sha256(
        str(timestamp).encode() + 
        str(participants_count).encode()
    ).digest()
    
    # Combine entropy sources
    combined = hashlib.sha256(
        entropy.to_bytes(32, 'big') + additional_entropy
    ).digest()
    
    # Convert to participant index
    return int.from_bytes(combined[:8], 'big') % participants_count
```

#### Encryption Standards
- **TLS 1.3**: All external communication encrypted
- **AES-256-GCM**: Symmetric encryption for data at rest
- **RSA-4096/ECDSA-P256**: Asymmetric encryption and signatures
- **HKDF**: Key derivation for perfect forward secrecy

#### Key Management
- **Ephemeral Keys**: New keys generated for each enclave instance
- **Key Rotation**: Regular rotation of long-term keys
- **Secure Storage**: Keys stored in enclave memory only
- **No Key Persistence**: Keys destroyed on enclave termination

### 3. Network Security

#### VSock Communication
```
Parent Instance ←→ Enclave
        ↑              ↓
    [TLS 1.3]    [VSock+TLS]
        ↑              ↓
   User Browser ←→ Web Server
```

#### TLS Configuration
```python
# TLS context for maximum security
import ssl

def create_secure_context():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    context.check_hostname = False  # Internal communication
    return context
```

#### Network Isolation
- **No Direct Internet**: Enclave has no direct network access
- **VSock Only**: Communication through secure VSock channel
- **Firewall Rules**: Strict iptables rules on host
- **DDoS Protection**: AWS Shield and CloudFlare integration

### 4. Smart Contract Security

#### Contract Audit Points
```solidity
// Security features in Lottery.sol
contract Lottery {
    // Access control
    modifier onlyEnclave() {
        require(msg.sender == enclaveAddress, "Unauthorized");
        _;
    }
    
    // Reentrancy protection
    bool private locked;
    modifier noReentrant() {
        require(!locked, "Reentrant call");
        locked = true;
        _;
        locked = false;
    }
    
    // Input validation
    function recordDraw(uint256 drawId, address winner, uint256 totalPot) 
        external onlyEnclave noReentrant {
        require(drawId > 0, "Invalid draw ID");
        require(winner != address(0), "Invalid winner");
        require(totalPot > 0, "Invalid pot amount");
        // ... implementation
    }
}
```

#### Gas Optimization & Security
- **Fixed Gas Limits**: Prevent gas-based attacks
- **Overflow Protection**: SafeMath for all arithmetic
- **Access Control**: Only enclave can record results
- **Event Logging**: Complete audit trail on blockchain

### 5. Application Security

#### Input Validation
```python
from pydantic import BaseModel, validator
from decimal import Decimal

class BetRequest(BaseModel):
    user_address: str
    amount: Decimal
    
    @validator('user_address')
    def validate_address(cls, v):
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum address')
        return v.lower()
    
    @validator('amount')
    def validate_amount(cls, v):
        if v < Decimal('0.01'):
            raise ValueError('Minimum bet is 0.01 ETH')
        if v > Decimal('10'):
            raise ValueError('Maximum bet is 10 ETH')
        return v
```

#### Rate Limiting
```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove old requests
        user_requests[:] = [req for req in user_requests 
                          if now - req < self.time_window]
        
        if len(user_requests) >= self.max_requests:
            return False
        
        user_requests.append(now)
        return True
```

#### Session Management
- **Stateless Design**: No server-side session storage
- **JWT Tokens**: Signed tokens for authentication
- **Short Expiry**: 15-minute token validity
- **Refresh Mechanism**: Automatic token renewal

### 6. Data Protection

#### Sensitive Data Handling
```python
import logging
from typing import Any

class SecureLogger:
    @staticmethod
    def log_bet(user_address: str, amount: float):
        # Hash sensitive data for logs
        user_hash = hashlib.sha256(user_address.encode()).hexdigest()[:8]
        logging.info(f"Bet placed: user={user_hash}, amount={amount}")
    
    @staticmethod
    def sanitize_error(error: Exception) -> str:
        # Remove sensitive information from error messages
        error_str = str(error)
        return re.sub(r'0x[a-fA-F0-9]{40}', '0x***', error_str)
```

#### Memory Protection
- **Secure Allocation**: Use secure memory allocation functions
- **Memory Wiping**: Clear sensitive data from memory after use
- **Stack Protection**: Enable stack canaries and ASLR
- **Heap Protection**: Enable heap protection mechanisms

### 7. Threat Model

#### Threat Actors
1. **Malicious Users**: Attempting to cheat or exploit
2. **Host Compromise**: Compromised EC2 instance
3. **Network Attackers**: Man-in-the-middle attacks
4. **Insider Threats**: Malicious operators or developers
5. **State Actors**: Government-level adversaries

#### Attack Vectors & Mitigations

##### Lottery Manipulation
- **Threat**: Predictable random numbers
- **Mitigation**: Hardware RNG + multiple entropy sources
- **Detection**: Blockchain analysis and statistical testing

##### Enclave Compromise
- **Threat**: Modified enclave code
- **Mitigation**: Attestation verification before each interaction
- **Detection**: Continuous attestation monitoring

##### Denial of Service
- **Threat**: Resource exhaustion attacks
- **Mitigation**: Rate limiting, resource quotas, AWS Shield
- **Detection**: Monitoring unusual traffic patterns

##### Smart Contract Attacks
- **Threat**: Reentrancy, overflow, gas attacks
- **Mitigation**: Secure coding practices, formal verification
- **Detection**: Contract monitoring and audit tools

##### Social Engineering
- **Threat**: Phishing attacks targeting users
- **Mitigation**: MetaMask integration, domain verification
- **Detection**: User education and warning systems

### 8. Security Monitoring

#### Real-time Monitoring
```python
import asyncio
import logging
from datetime import datetime, timedelta

class SecurityMonitor:
    def __init__(self):
        self.failed_attempts = defaultdict(int)
        self.suspicious_patterns = []
    
    async def monitor_security_events(self):
        while True:
            try:
                # Check for unusual betting patterns
                await self.detect_unusual_betting()
                
                # Monitor failed authentication attempts
                await self.check_failed_attempts()
                
                # Verify enclave attestation
                await self.verify_attestation()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logging.error(f"Security monitoring error: {e}")
```

#### Audit Logging
```python
class AuditLogger:
    @staticmethod
    def log_security_event(event_type: str, details: dict):
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'details': details,
            'severity': 'HIGH' if 'attack' in event_type else 'INFO'
        }
        
        # Log to secure location
        logging.getLogger('security').info(json.dumps(log_entry))
        
        # Alert if high severity
        if log_entry['severity'] == 'HIGH':
            send_security_alert(log_entry)
```

#### Metrics Collection
- **Performance Metrics**: Response times, throughput, error rates
- **Security Metrics**: Failed logins, unusual patterns, attestation failures
- **Business Metrics**: Betting volume, user activity, draw frequency
- **Infrastructure Metrics**: CPU, memory, network usage

### 9. Incident Response

#### Security Incident Classification
1. **Critical**: Active attack or data breach
2. **High**: Potential security vulnerability
3. **Medium**: Suspicious activity detected
4. **Low**: Security policy violation

#### Response Procedures
```python
class IncidentResponse:
    def handle_critical_incident(self, incident_details: dict):
        # 1. Immediate containment
        self.isolate_affected_systems()
        
        # 2. Evidence preservation
        self.capture_system_state()
        
        # 3. Notification
        self.notify_stakeholders(severity='CRITICAL')
        
        # 4. Investigation
        self.begin_forensic_analysis()
        
        # 5. Recovery
        self.initiate_recovery_procedures()
```

### 10. Compliance & Standards

#### Regulatory Compliance
- **GDPR**: Privacy by design, data minimization
- **SOX**: Financial controls and audit trails
- **AML/KYC**: Anti-money laundering compliance
- **Gaming Regulations**: Jurisdiction-specific requirements

#### Security Standards
- **ISO 27001**: Information security management
- **NIST Cybersecurity Framework**: Comprehensive security controls
- **OWASP Top 10**: Web application security best practices
- **CIS Controls**: Center for Internet Security guidelines

#### Audit Requirements
- **Regular Penetration Testing**: Quarterly external audits
- **Code Reviews**: All changes peer-reviewed
- **Compliance Audits**: Annual third-party audits
- **Vulnerability Assessments**: Monthly automated scans

### 11. Security Best Practices

#### For Operators
1. **Principle of Least Privilege**: Minimal access rights
2. **Defense in Depth**: Multiple security layers
3. **Regular Updates**: Keep all systems patched
4. **Monitoring**: Continuous security monitoring
5. **Training**: Regular security awareness training

#### For Users
1. **Wallet Security**: Use hardware wallets when possible
2. **Verify Domain**: Always check the website URL
3. **Attestation Check**: Verify enclave attestation
4. **Reasonable Limits**: Don't bet more than you can afford
5. **Report Issues**: Report suspicious activity immediately

#### For Developers
1. **Secure Coding**: Follow secure development practices
2. **Code Reviews**: All code must be peer-reviewed
3. **Testing**: Comprehensive security testing
4. **Documentation**: Maintain security documentation
5. **Training**: Stay updated on security best practices