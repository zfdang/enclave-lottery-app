# Security Overview (Current Passive Deployment)

## Security Overview

Legacy demo references removed. This document now distinguishes between IMPLEMENTED controls and CONCEPTUAL / FUTURE items. Avoid assuming protections that are not present in source code.

Legend:
* ✅ Implemented in code now
* 🧪 Partial / planned (scaffolding or placeholder only)
* 🚧 Conceptual (not implemented)

## Security Architecture

### 1. AWS Nitro Enclave Foundation

#### Hardware Isolation (when deployed in Nitro)
* ✅ Memory isolation & encrypted enclave memory (provided by Nitro platform)
* ✅ Attestation mechanism available (not yet surfaced via public API endpoint)
* 🚧 Automated attestation presentation to users (planned)

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

#### Randomness
Current contract logic determines winner selection on‑chain (draw transaction executes contract RNG / selection). No in‑enclave RNG module exists. Any earlier Python RNG examples have been removed to prevent confusion.

#### Encryption / Transport
* ✅ Client → Backend typically via plain HTTP in dev; production should terminate TLS at a reverse proxy (Nginx / ALB) (operator must configure)
* 🚧 Backend internal TLS context (not currently enabled in code)
* 🚧 Data-at-rest encryption not applicable (no persistent storage)

#### Key Management
* ✅ Operator private key supplied via environment variable (redacted in logs)
* 🚧 Automated rotation (not implemented)
* 🚧 KMS / secret manager integration (deployment-specific outside code)

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
* ✅ Minimal exposed surface (single HTTP/WebSocket port)
* 🚧 Mandatory TLS
* 🚧 DDoS mitigations (infrastructure concern, not code)

### 4. Smart Contract Security

#### Smart Contract (High-Level)
Refer to the Solidity source for actual modifiers and guards. Ensure independent audit before production use.

#### Gas Optimization & Security
- **Fixed Gas Limits**: Prevent gas-based attacks
- **Overflow Protection**: SafeMath for all arithmetic
- **Access Control**: Only enclave can record results
- **Event Logging**: Complete audit trail on blockchain

### 5. Application Security
* ✅ Read endpoints / WebSocket provide round & participant data only
* ✅ Operator actions (draw/refund) require possession of operator private key (not user initiated through backend)
* 🚧 No rate limiting (rely on minimal surface + upstream infra)
* 🚧 No JWT/session auth (not needed for current public read model)
* 🚧 No user bet submission endpoints (users interact directly with contract via wallet)

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

#### Memory / Process
Standard Python process; no special secure wiping implemented. Rely on enclave isolation (if used) + ephemeral container lifecycle.

### 7. Threat Model

#### Threat Actors
1. **Malicious Users**: Attempting to cheat or exploit
2. **Host Compromise**: Compromised EC2 instance
3. **Network Attackers**: Man-in-the-middle attacks
4. **Insider Threats**: Malicious operators or developers
5. **State Actors**: Government-level adversaries

#### Attack Vectors & Mitigations

##### Lottery Manipulation
Mitigation is contract-level randomness design; ensure independent audit. No off-chain RNG component present.

##### Enclave Compromise
- **Threat**: Modified enclave code
- **Mitigation**: Attestation verification before each interaction
- **Detection**: Continuous attestation monitoring

##### Denial of Service
No built-in rate limiting; rely on infrastructure (WAF, proxy) and low compute footprint.

##### Smart Contract Attacks
Require standard Solidity best practices + audit (outside Python scope).

##### Social Engineering
- **Threat**: Phishing attacks targeting users
- **Mitigation**: MetaMask integration, domain verification
- **Detection**: User education and warning systems

### 8. Security Monitoring

#### Real-time Monitoring
Currently no dedicated background security monitor loop; observability is via standard logs. Future monitoring agent can subscribe to the same event bus.

Audit logging: standard application logs only at present.

#### Metrics Collection
- **Performance Metrics**: Response times, throughput, error rates
- **Security Metrics**: Failed logins, unusual patterns, attestation failures
- **Business Metrics**: Betting volume, user activity, draw frequency
- **Infrastructure Metrics**: CPU, memory, network usage

### 9. Incident Response (Conceptual Outline)

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

### 10. Compliance & Standards (Aspirational)

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
Keep wallet software updated; verify contract addresses; be cautious of phishing—attestation UI pending.

#### For Developers
Focus on minimizing new trust surfaces. Prefer on‑chain enforcement to off‑chain logic. Document any added secrets or network egress.

---
This document intentionally prunes prior illustrative code blocks that are not part of the runtime to avoid overclaiming security posture.