# 配置管理指南 (Configuration Management Guide)

本文档详细说明了 Enclave Lottery App 项目中的配置管理系统。

## 配置系统概述 (Configuration System Overview)

项目采用**三层配置优先级系统**：

1. **硬编码默认值** (Hardcoded Defaults) - 最低优先级
2. **配置文件** (`enclave/config/enclave.conf`) - 中等优先级
3. **环境变量** (Environment Variables) - **最高优先级**

## 配置文件结构 (Configuration File Structure)

### 1. 配置文件 (`enclave/config/enclave.conf`)

这是一个 JSON 格式的配置文件，包含所有默认设置：

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "lottery": {
    "draw_interval_minutes": 5,
    "minimum_interval_minutes": 2,
    "betting_cutoff_minutes": 1,
    "single_bet_amount": "0.01",
    "max_bets_per_user": 10
  },
  "blockchain": {
    "rpc_url": "http://localhost:8545",
    "chain_id": 31337,
    "contract_address": "",
    "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
  },
  "enclave": {
    "vsock_port": 5005,
    "attestation_enabled": false
  }
}
```

### 2. 环境变量文件 (`.env`)

复制 `.env.example` 到 `.env` 并设置实际值：

```bash
cp .env.example .env
```

然后编辑 `.env` 文件设置你的实际配置值。

## 支持的环境变量 (Supported Environment Variables)

### 服务器配置 (Server Configuration)

| 变量名 | 旧变量名 (Legacy) | 描述 | 默认值 |
|--------|------------------|------|--------|
| `SERVER_HOST` | `LOTTERY_SERVER_HOST` | 服务器绑定地址 | `0.0.0.0` |
| `SERVER_PORT` | `LOTTERY_SERVER_PORT` | 服务器端口 | `8080` |

### 彩票配置 (Lottery Configuration)

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `LOTTERY_DRAW_INTERVAL_MINUTES` | 开奖间隔 (分钟) | `5` |
| `LOTTERY_MINIMUM_INTERVAL_MINUTES` | 最小间隔 (分钟) | `2` |
| `LOTTERY_BETTING_CUTOFF_MINUTES` | 投注截止时间 (分钟) | `1` |
| `LOTTERY_SINGLE_BET_AMOUNT` | 单注金额 (ETH) | `0.01` |
| `LOTTERY_MAX_BETS_PER_USER` | 每用户最大投注数 | `10` |

### 区块链配置 (Blockchain Configuration)

| 变量名 | 旧变量名 (Legacy) | 描述 | 默认值 |
|--------|------------------|------|--------|
| `ETHEREUM_RPC_URL` | `BLOCKCHAIN_RPC_URL` | 以太坊 RPC 地址 | `http://localhost:8545` |
| `CHAIN_ID` | `BLOCKCHAIN_CHAIN_ID` | 链 ID | `31337` |
| `CONTRACT_ADDRESS` | `BLOCKCHAIN_CONTRACT_ADDRESS` | 合约地址 | `""` |
| `PRIVATE_KEY` | `BLOCKCHAIN_PRIVATE_KEY` | 私钥 | 测试私钥 |

### Enclave 配置 (Enclave Configuration)

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `ENCLAVE_VSOCK_PORT` | VSock 端口 | `5005` |
| `ENCLAVE_ATTESTATION_ENABLED` | 启用认证 | `false` |

### 前端配置 (Frontend Configuration)

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `REACT_APP_API_URL` | API 地址 | `http://localhost:8080` |
| `REACT_APP_WEBSOCKET_URL` | WebSocket 地址 | `ws://localhost:8080/ws` |

## 配置使用方法 (Configuration Usage)

### 1. 开发环境 (Development Environment)

```bash
# 1. 复制配置模板
cp .env.example .env

# 2. 编辑配置文件
nano .env

# 3. 设置必要的环境变量
export ETHEREUM_RPC_URL="http://localhost:8545"
export PRIVATE_KEY="your_development_private_key"

# 4. 运行应用
python enclave/src/main.py
```

### 2. 生产环境 (Production Environment)

生产环境推荐使用环境变量而不是 `.env` 文件：

```bash
# 设置环境变量
export ETHEREUM_RPC_URL="https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
export PRIVATE_KEY="your_production_private_key"
export SERVER_HOST="0.0.0.0"
export SERVER_PORT="8080"
export ENCLAVE_ATTESTATION_ENABLED="true"

# 运行应用
python enclave/src/main.py
```

### 3. Docker 环境 (Docker Environment)

```bash
# 使用环境变量运行 Docker
docker run -d \
  -p 8080:8080 \
  -e ETHEREUM_RPC_URL="http://host.docker.internal:8545" \
  -e PRIVATE_KEY="your_private_key" \
  enclave-lottery-app
```

## 安全注意事项 (Security Considerations)

### 1. 私钥安全 (Private Key Security)

⚠️ **重要提醒**：

- **永远不要**将真实私钥提交到 Git 仓库
- 生产环境使用 AWS Secrets Manager、HashiCorp Vault 等密钥管理服务
- 开发环境使用测试私钥

```bash
# 好的做法：使用环境变量
export PRIVATE_KEY="$(aws secretsmanager get-secret-value --secret-id prod/lottery/private-key --query SecretString --output text)"

# 不好的做法：硬编码在文件中
PRIVATE_KEY="0x1234567890abcdef..."  # ❌ 危险！
```

### 2. 网络安全 (Network Security)

- RPC URL 应该使用可信的提供商（如 Infura、Alchemy）
- 在生产环境中启用 SSL/TLS
- 限制服务器绑定地址

### 3. 配置文件权限 (File Permissions)

```bash
# 设置正确的文件权限
chmod 600 .env
chmod 644 enclave/config/enclave.conf
```

## 配置验证 (Configuration Validation)

项目会在启动时验证配置：

```python
# 检查必需的配置项
required_configs = [
    'blockchain.rpc_url',
    'blockchain.chain_id',
    'server.host',
    'server.port'
]

# 验证数值范围
assert config['lottery']['draw_interval_minutes'] >= 1
assert config['server']['port'] > 0 and config['server']['port'] < 65536
```

## 故障排除 (Troubleshooting)

### 1. 配置加载失败

```bash
# 检查文件权限
ls -la .env

# 检查文件格式
cat .env | grep -v '^#' | grep '='

# 验证 JSON 格式
python -m json.tool enclave/config/enclave.conf
```

### 2. 环境变量未生效

```bash
# 检查环境变量是否设置
printenv | grep -E "(ETHEREUM|LOTTERY|ENCLAVE)_"

# 检查变量名拼写
echo $ETHEREUM_RPC_URL
```

### 3. 私钥问题

```bash
# 验证私钥格式（应该以 0x 开头，64个十六进制字符）
echo $PRIVATE_KEY | grep -E '^0x[a-fA-F0-9]{64}$'
```

## 迁移指南 (Migration Guide)

从旧的变量名迁移到新的标准名称：

```bash
# 旧配置 → 新配置
BLOCKCHAIN_RPC_URL → ETHEREUM_RPC_URL
BLOCKCHAIN_CHAIN_ID → CHAIN_ID
BLOCKCHAIN_CONTRACT_ADDRESS → CONTRACT_ADDRESS
BLOCKCHAIN_PRIVATE_KEY → PRIVATE_KEY
LOTTERY_SERVER_HOST → SERVER_HOST
LOTTERY_SERVER_PORT → SERVER_PORT
```

**注意**：为了向后兼容，系统仍然支持旧的变量名，但建议迁移到新的标准名称。

## 示例配置 (Example Configurations)

### 本地开发 (Local Development)

```bash
# .env 文件
ETHEREUM_RPC_URL=http://localhost:8545
CHAIN_ID=31337
PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
SERVER_HOST=localhost
SERVER_PORT=8080
LOTTERY_DRAW_INTERVAL_MINUTES=5
```

### 测试网 (Testnet)

```bash
# .env 文件
ETHEREUM_RPC_URL=https://goerli.infura.io/v3/YOUR_PROJECT_ID
CHAIN_ID=5
PRIVATE_KEY=your_testnet_private_key
CONTRACT_ADDRESS=0x1234567890123456789012345678901234567890
LOTTERY_DRAW_INTERVAL_MINUTES=10
```

### 主网 (Mainnet)

```bash
# 环境变量（不要写在文件中）
export ETHEREUM_RPC_URL="https://mainnet.infura.io/v3/YOUR_PROJECT_ID"
export CHAIN_ID="1"
export PRIVATE_KEY="$(aws secretsmanager get-secret-value ...)"
export CONTRACT_ADDRESS="your_deployed_contract_address"
export ENCLAVE_ATTESTATION_ENABLED="true"
export LOTTERY_DRAW_INTERVAL_MINUTES="60"
```

## 更多信息 (More Information)

- [部署指南](deployment.md)
- [安全指南](security.md)
- [开发指南](DEVELOPMENT.md)
- [主 README](../README.md)