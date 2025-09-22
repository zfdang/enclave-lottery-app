# Enclave Lottery App

A secure, decentralized lottery application designed for AWS Nitro Enclaves, featuring real-time draws, ETH betting, blockchain transparency, and comprehensive demonstration modes.

## 🎯 Overview

The Enclave Lottery App is a trustless lottery system that combines the security of AWS Nitro Enclaves with blockchain transparency. This application showcases both traditional development workflows and enclave-based secure execution, with multiple demonstration modes for different use cases.

### Key Features

- 🔒 **Secure Execution**: Designed for AWS Nitro Enclave deployment with complete isolation
- 🐳 **Docker Container Support**: Real container-based demonstration environment
- ⏰ **Configurable Draws**: Automated lottery draws with customizable intervals  
- 💰 **ETH Betting**: Place bets using Ethereum through MetaMask integration
- 🏆 **Winner Takes All**: Single winner receives the entire pot
- 🔍 **Blockchain Transparency**: All results recorded on Ethereum for verification
- 📱 **Real-time Web UI**: Live countdown, betting status, and activity feed
- 🛡️ **Cryptographically Secure**: Provably fair random number generation
- 🎮 **Comprehensive Demos**: Multiple demo modes including Docker container simulation

## 🚀 Quick Start Guide

### One-Command Setup

```bash
# Automatically install all prerequisites (except blockchain)
./scripts/setup_environment.sh
```

### Unified Demo System (Recommended)

```bash
# Launch the comprehensive demo suite
python3 demo.py
```

**Available Demo Modes:**
- **1) Quick Demo (5 min)** - Core functionality showcase with blockchain
- **2) Interactive Demo** - Step-by-step guided experience  
- **3) Technical Demo** - Detailed system analysis including enclave features
- **4) Web Demo** - Launch full web interface with real-time blockchain interaction
- **5) Docker Demo** - Real enclave container environment with blockchain integration
- **6) Exit** - Exit the demo system

### Prerequisites

- Local blockchain running (Anvil, Hardhat, or Ganache) on `http://localhost:8545`
- Python 3.11+ with required dependencies
- Docker 20.10+ (for container demos and enclave builds)
- Node.js 18+ (for frontend builds)
- AWS Nitro CLI (for production enclave deployment)

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   User Browser  │◄──►│ Enclave/Container    │◄──►│ Ethereum Network│
│                 │    │ Environment          │    │                 │
│ - React Frontend│    │ - Lottery Engine     │    │ - Smart Contract│
│ - MetaMask      │    │ - FastAPI Server     │    │ - Result Storage│
│ - WebSocket     │    │ - Blockchain Client  │    │ - Transparency  │
│ - Demo Interface│    │ - Docker Runtime     │    │ - Verification  │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
```

### Demo Architecture

The application provides multiple demonstration environments:

- **Development Mode**: Direct Python execution for development
- **Docker Mode**: Container-based execution simulating enclave isolation
- **Enclave Mode**: Full AWS Nitro Enclave deployment for production

## 📋 Installation & Usage

### Manual Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd enclave-lottery-app
   ```

2. **Install prerequisites**
   ```bash
   ./scripts/setup_environment.sh
   ```

3. **Start local blockchain**
   ```bash
   # Install and start Anvil (recommended)
   curl -L https://foundry.paradigm.xyz | bash
   foundryup
   anvil
   ```

4. **Build the application**
   ```bash
   ```bash
   # Build Docker images and compile contracts
   ./scripts/build_docker.sh
   ```

5. **Build enclave (for production)**
   ```bash
   # Build EIF file for AWS Nitro Enclave deployment
   ./scripts/build_enclave.sh
   ```

6. **Run demonstrations**
   ```bash
   # Launch unified demo system
   python3 demo.py
   
   # Or run specific components
   ./scripts/comprehensive_demo.sh    # Web-based comprehensive demo
   ```

### Quick Demo Examples

#### Docker Demo Experience
```bash
# Select option 5 in demo.py for Docker Demo
python3 demo.py
# ➜ 5) 🐳 Docker Demo - Real enclave container environment

# Features:
# - Automatic Docker image building and container lifecycle
# - Network isolation with blockchain connectivity to host
# - Interactive web interface on http://localhost:8081
# - API endpoint testing and container log viewing
# - One-click cleanup functionality
```

#### Development Mode
```bash
# For development and testing
python3 demo.py
# Interactive lottery simulation with blockchain integration
```

## 📋 Usage

### For Developers & Evaluators

1. **Start with Demos**: Use `python3 demo.py` to explore different demonstration modes
2. **Docker Demo**: Experience enclave-like isolation with container technology
3. **Web Interface**: Access live web UI during demos for real-time interaction
4. **API Testing**: Use built-in API demonstration features to test endpoints
5. **Blockchain Integration**: Observe live blockchain transactions during demos

### For Players (in demo environments)

1. **Connect Wallet**: Click "Connect Wallet" and approve MetaMask connection
2. **Place Bets**: Enter your bet amount (minimum 0.01 ETH) and click "Place Bet"
3. **Watch Countdown**: Monitor the countdown timer to the next draw
4. **View Results**: Check the winner announcement and your betting history
5. **Verify on Blockchain**: All results are recorded on Ethereum for transparency

### For Production Deployment

1. **Deploy Infrastructure**: Follow the deployment guide in `docs/deployment.md`
2. **Build Enclave**: Use `./scripts/build_enclave.sh` to create EIF file
3. **Deploy to AWS**: Upload EIF to AWS and start Nitro Enclave
4. **Monitor System**: Use the provided monitoring dashboards
5. **Verify Attestation**: Regularly check enclave attestation documents

## 📁 Project Structure

```
enclave-lottery-app/
├── demo.py                     # Unified demo system with multiple modes
├── DEMO_GUIDE.md              # Comprehensive demo documentation
├── enclave/                   # Main enclave application
│   ├── src/
│   │   ├── main.py           # Enclave entry point
│   │   ├── web_server.py     # FastAPI web server
│   │   ├── lottery/          # Lottery game logic
│   │   │   ├── engine.py     # Core lottery engine
│   │   │   ├── bet_manager.py# Betting management
│   │   │   └── scheduler.py  # Draw scheduling
│   │   ├── blockchain/       # Ethereum integration
│   │   │   ├── client.py     # Blockchain client
│   │   │   ├── client.py      # Enhanced blockchain client
│   │   │   └── contracts/    # Solidity contracts
│   │   │       └── Lottery.sol
│   │   ├── frontend/         # React application
│   │   │   ├── src/
│   │   │   │   ├── App.tsx   # Main React component
│   │   │   │   └── components/ # UI components
│   │   │   └── public/       # Static assets
│   │   └── utils/            # Utility modules
│   ├── config/
│   │   └── enclave.conf      # Enclave configuration
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile           # Container image definition
├── scripts/                 # Build, deploy, and demo scripts
│   ├── setup_environment.sh # One-command setup
│   ├── build_docker.sh      # Build Docker images
│   ├── build_enclave.sh     # Build EIF file for AWS Nitro
│   └── comprehensive_demo.sh# Web-based demo
├── host-proxy/              # Host communication proxy
├── docs/                    # Documentation
│   ├── architecture.md      # System architecture
│   ├── deployment.md        # Deployment guide
│   ├── DEVELOPMENT.md       # Development workflows
│   └── security.md          # Security documentation
├── .env                     # Environment configuration
└── README.md               # This file
```

## 🔧 Configuration

> 📖 **Complete Configuration Guide**: See [docs/CONFIG.md](docs/CONFIG.md) for comprehensive configuration management documentation.

### Quick Configuration Setup

The application uses a **three-tier configuration system** with the following priority (highest to lowest):

1. **Environment Variables** (highest priority)
2. **Configuration File** (`enclave/config/enclave.conf`) 
3. **Hardcoded Defaults** (lowest priority)

### Environment Variables

Copy the template and customize for your environment:

```bash
# Copy template to create your configuration
cp .env.example .env

# Edit with your actual values
nano .env
```

Example `.env` configuration:

```bash
# Blockchain Configuration (standardized environment variables)
ETHEREUM_RPC_URL=http://localhost:8545       # Ethereum RPC URL
CHAIN_ID=31337                               # Chain ID (31337 for Anvil/Hardhat)
PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3

# Server Configuration
SERVER_HOST=localhost                        # Server bind address
SERVER_PORT=8080                             # Server port

# Lottery Configuration
LOTTERY_DRAW_INTERVAL_MINUTES=5              # Draw interval (minutes)
LOTTERY_BETTING_CUTOFF_MINUTES=1             # Betting cutoff time (minutes)
LOTTERY_SINGLE_BET_AMOUNT=0.01               # Single bet amount (ETH)
LOTTERY_MAX_BETS_PER_USER=10                 # Maximum bets per user

# Enclave Configuration
ENCLAVE_VSOCK_PORT=5005                      # VSock port
ENCLAVE_ATTESTATION_ENABLED=false            # Enable attestation (set to true in production)

# Frontend Configuration
REACT_APP_API_URL=http://localhost:8080
REACT_APP_WEBSOCKET_URL=ws://localhost:8080/ws
```

**Important Notes:**
- ⚠️ Never commit real private keys to Git repositories
- 🔒 Use secret management services in production
- 📋 Legacy environment variable names are still supported for backward compatibility

### Configuration Migration

The system supports both new standardized and legacy environment variable names:

| New Standard | Legacy | Description |
|-------------|---------|-------------|
| `ETHEREUM_RPC_URL` | `BLOCKCHAIN_RPC_URL` | Ethereum RPC endpoint |
| `CHAIN_ID` | `BLOCKCHAIN_CHAIN_ID` | Blockchain chain ID |
| `PRIVATE_KEY` | `BLOCKCHAIN_PRIVATE_KEY` | Private key for transactions |
| `SERVER_HOST` | `LOTTERY_SERVER_HOST` | Server bind address |
| `SERVER_PORT` | `LOTTERY_SERVER_PORT` | Server port |

### Enclave Configuration

The `enclave/config/enclave.conf` file contains lottery-specific settings:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "lottery": {
    "draw_interval_minutes": 10,
    "betting_cutoff_minutes": 1,
    "single_bet_amount": "0.01",
    "max_bets_per_user": 100
  },
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "chain_id": 31337,
    "contract_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
  },
  "enclave": {
    "vsock_port": 5000,
    "attestation_enabled": true
  }
}
```

## 🛡️ Security

### Enclave Attestation

Before trusting the lottery, users can verify the enclave attestation:

```bash
# Get attestation document
nitro-cli get-attestation-document --enclave-id <enclave-id>

# Verify the document contains expected measurements
# PCR0: 000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
# PCR1: 202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f
# PCR2: 404142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f
```

### Random Number Generation

The lottery uses cryptographically secure random number generation:

1. **Hardware Entropy**: AWS Nitro Enclave hardware random number generator
2. **Additional Entropy**: Combination of timestamp and betting state
3. **Cryptographic Hash**: SHA-256 for combining entropy sources
4. **Verifiable**: All random generation is recorded on blockchain

### Smart Contract Security

- **Access Control**: Only the enclave can record lottery results
- **Reentrancy Protection**: Guards against reentrancy attacks
- **Input Validation**: All inputs are validated and sanitized
- **Gas Optimization**: Fixed gas limits prevent gas-based attacks

## 📊 Monitoring

### Health Checks

- **Application Health**: `GET /health` - Application status
- **Enclave Status**: `nitro-cli describe-enclaves` - Enclave information
- **Blockchain Connection**: Ethereum node connectivity check
- **Database Status**: Application state consistency

### Metrics

- **Performance**: Response times, throughput, error rates
- **Security**: Failed attempts, unusual patterns, attestation status
- **Business**: Betting volume, user activity, draw statistics
- **Infrastructure**: CPU, memory, network usage

### Alerts

- **Critical**: Enclave failures, security breaches
- **High**: Performance degradation, failed draws
- **Medium**: Unusual betting patterns, high error rates
- **Low**: Information updates, maintenance notices

## 🧪 Testing & Development

### Demo Testing

```bash
# Test all demo modes
python3 demo.py

# Test specific components
./scripts/comprehensive_demo.sh  # Web-based demo
```

### Unit Tests

```bash
# Backend tests
cd enclave
python -m pytest tests/ -v

# Frontend tests  
cd enclave/src/frontend
npm test
```

### Build Testing

```bash
# Test Docker build
./scripts/build_docker.sh

# Test enclave build (requires AWS Nitro CLI)
./scripts/build_enclave.sh

# Test with container runtime
docker run --rm -p 8081:8080 enclave-lottery-app:latest
```

### Local Development

```bash
# Development environment setup
cd enclave
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start backend development server
python src/main.py --dev

# Start frontend development server (separate terminal)
cd src/frontend
npm install && npm start
```

## � Deployment Options

### 1. Docker Deployment (Recommended for Testing)

```bash
# Build and run with Docker
./scripts/build_docker.sh
docker run -d --name lottery-app \
  -p 8080:8080 \
  --add-host host.docker.internal:host-gateway \
  -e ETHEREUM_RPC_URL=http://host.docker.internal:8545 \
  -e CONTRACT_ADDRESS=your_contract_address \
  enclave-lottery-app:latest
```

### 2. AWS Nitro Enclave Deployment (Production)

```bash
# Build enclave image file (EIF)
./scripts/build_enclave.sh

# Deploy to AWS EC2 with Nitro Enclave support
sudo nitro-cli run-enclave \
  --eif-path lottery.eif \
  --cpu-count 2 \
  --memory 1024 \
  --enclave-cid 16
```

### 3. Local Development Deployment

```bash
# Direct Python execution
cd enclave
source venv/bin/activate
python src/main.py
```

## 🎮 Demo Modes Explained

### Quick Demo (Option 1)
- **Duration**: ~5 minutes
- **Features**: Automated lottery simulation with 5 users, blockchain integration
- **Best for**: Quick functionality overview

### Interactive Demo (Option 2)  
- **Duration**: User-controlled
- **Features**: Step-by-step guided experience with user input
- **Best for**: Understanding game mechanics

### Technical Demo (Option 3)
- **Duration**: ~10 minutes  
- **Features**: Detailed system analysis, enclave features, technical insights
- **Best for**: Technical evaluation and architecture understanding

### Web Demo (Option 4)
- **Duration**: Persistent
- **Features**: Full web interface with real-time updates, MetaMask integration
- **Best for**: End-user experience testing

### Docker Demo (Option 5)  
- **Duration**: User-controlled
- **Features**: Real container environment, network isolation, API testing
- **Best for**: Enclave simulation and container deployment testing

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper tests
4. Follow code standards (PEP 8 for Python, ESLint for TypeScript)
5. Update documentation as needed
6. **Run the test suite (`python3 demo.py` for integration testing)
7. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Getting Started & Support

### Quick Start Checklist

1. ✅ **Setup Environment**: Run `./scripts/setup_environment.sh`
2. ✅ **Start Blockchain**: Launch Anvil with `anvil` command  
3. ✅ **Build Application**: Execute `./scripts/build_docker.sh`
4. ✅ **Run Demo**: Launch `python3 demo.py` and select a demo mode
5. ✅ **Explore Features**: Try Docker Demo (option 5) for full container experience

### Documentation

- 📖 [Demo Guide](DEMO_GUIDE.md) - Comprehensive demo documentation
- 🏗️ [Architecture Guide](docs/architecture.md) - System design and components
- 🚀 [Deployment Guide](docs/deployment.md) - Production deployment instructions
- 🔒 [Security Guide](docs/security.md) - Security features and best practices
- 💻 [Development Guide](docs/DEVELOPMENT.md) - Development workflows and setup

### Troubleshooting

**Common Issues:**

- **Blockchain Connection**: Ensure Anvil is running on `http://localhost:8545`
- **Docker Issues**: Check Docker daemon is running and user has permissions
- **Port Conflicts**: Default ports 8080/8081 should be available
- **Build Failures**: Run `./scripts/setup_environment.sh` to install dependencies

**Getting Help:**

- 🐛 **Issues**: Report bugs and feature requests on GitHub Issues
- 💬 **Discussions**: Join community discussions on GitHub Discussions  
- 🔒 **Security**: Report security issues privately to security@example.com
- 📧 **Contact**: General inquiries to support@example.com

### FAQ

**Q: How do I know the lottery is fair?**
A: The lottery uses cryptographically secure random numbers, runs in isolated containers/enclaves, and records all results on the blockchain for transparency. The demo modes let you verify this behavior.

**Q: What's the difference between Docker Demo and actual AWS Nitro Enclave?**
A: Docker Demo simulates enclave isolation using containers, while AWS Nitro Enclave provides hardware-level isolation. Both run the same lottery code with identical security properties.

**Q: Can I run my own lottery instance?**
A: Yes! The entire system is open source. Use the build scripts and deployment guides to set up your own instance.

**Q: How are gas fees handled?**
A: The lottery contract is optimized for gas efficiency. Users only pay standard Ethereum transaction fees for their bets.

**Q: What blockchain networks are supported?**
A: Currently supports any Ethereum-compatible network. Default setup uses local Anvil for testing.

## 🗺️ Roadmap

### Current Version (1.0)
- ✅ Complete demo system with 5 different modes
- ✅ Docker container simulation of enclave environment  
- ✅ AWS Nitro Enclave build pipeline
- ✅ Blockchain integration with smart contracts
- ✅ React-based web interface
- ✅ Comprehensive documentation

### Version 1.1 (Next Release)
- [ ] Enhanced mobile-responsive interface
- [ ] Multi-token support (USDC, DAI, etc.)
- [ ] Advanced betting strategies
- [ ] Real-time monitoring dashboard
- [ ] Performance optimizations

### Version 1.2 (Future)
- [ ] Cross-chain lottery support
- [ ] DAO governance for lottery parameters
- [ ] Staking rewards for participants
- [ ] Advanced analytics and insights

### Version 2.0 (Long-term)
- [ ] Multi-game platform expansion
- [ ] NFT integration and rewards
- [ ] Social features and referrals
- [ ] Machine learning for fraud detection

---

**🎯 Built with modern technologies:** AWS Nitro Enclaves, Docker, Ethereum, React, FastAPI, and Python

**🔒 Security-first design:** Hardware isolation, blockchain transparency, and cryptographic verification

**🎮 Demo-driven development:** Multiple demonstration modes for comprehensive evaluation