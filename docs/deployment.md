# Lottery Enclave - Deployment Guide

For development and demonstrations, start with the unified demos:
- CLI demo: `./demo.sh`
- Web-centric demo: `scripts/comprehensive_demo.sh`

## Prerequisites

### AWS Account Setup
- AWS account with Nitro Enclave support
- EC2 instances with Nitro Enclave capabilities (M5n, M5dn, R5n, R5dn, C5n, C6i, M6i, R6i)
- IAM permissions for EC2, ECS, and Nitro Enclave operations
- AWS CLI configured with appropriate credentials

### Development Environment
- Docker 20.10 or later
- Docker Compose v2.0 or later
- Node.js 18 or later
- Python 3.11 or later
- Solidity compiler (solc) 0.8.19
- Git for version control

### Network Requirements
- Internet connectivity for package downloads
- Access to Ethereum network (mainnet or testnet)
- Open ports for web interface (default: 6080)

## Local Development Setup

### 1. Clone and Setup
```bash
git clone <repository-url>
cd lottery-app
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Required environment variables:
- `ETHEREUM_RPC_URL`: Ethereum node endpoint
- `PRIVATE_KEY`: Enclave private key (generated automatically)
- `CONTRACT_ADDRESS`: Deployed lottery contract address
- `ENCLAVE_PORT`: Internal enclave communication port (default: 5000)

### 3. Build Development Environment
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Build the application
./scripts/build.sh
```

### 4. Run Locally (Development Mode)
```bash
# Start development server
cd enclave
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py

Or use the demo application:
```bash
python ../demo_app.py
```
```

## Production Deployment

### 1. AWS EC2 Instance Setup

#### Launch Instance
```bash
# Launch EC2 instance with Nitro Enclave support
aws ec2 run-instances \
    --image-id ami-0c02fb55956c7d316 \
    --instance-type m5n.large \
    --enable-enclave \
    --security-group-ids sg-xxxxxxxxx \
    --subnet-id subnet-xxxxxxxxx \
    --key-name your-key-pair
```

#### Install Dependencies
```bash
# Connect to instance
ssh -i your-key.pem ec2-user@<instance-ip>

# Install Docker
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Nitro CLI
wget https://github.com/aws/aws-nitro-enclaves-cli/releases/latest/download/aws-nitro-enclaves-cli.rpm
sudo rpm -i aws-nitro-enclaves-cli.rpm

# Configure enclave allocator
echo 'GRUB_CMDLINE_LINUX="nitro_enclaves.allocator_memory_size_MiB=1024"' | sudo tee -a /etc/default/grub
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo reboot
```

### 2. Deploy Application

#### Transfer Application
```bash
# Copy application to instance
scp -i your-key.pem -r lottery-app ec2-user@<instance-ip>:~/
```

#### Build Production Images
```bash
ssh -i your-key.pem ec2-user@<instance-ip>
cd lottery-app

# Build Docker image
./scripts/build.sh

# Build Enclave Image File (EIF)
./scripts/build_enclave.sh
```

#### Deploy Smart Contracts
```bash
# Deploy contracts to blockchain
./scripts/deploy_contracts.sh
```

#### Start Enclave
```bash
# Start the lottery enclave
./scripts/run_enclave.sh
```

### 3. Production Configuration

#### Systemd Service Setup
```bash
# Create systemd service
sudo cp configs/lottery-enclave.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lottery-enclave
sudo systemctl start lottery-enclave
```

#### Nginx Reverse Proxy
```bash
# Install nginx
sudo yum install -y nginx

# Configure reverse proxy
sudo cp configs/nginx.conf /etc/nginx/conf.d/lottery.conf
sudo systemctl enable nginx
sudo systemctl start nginx
```

#### SSL Certificate
```bash
# Install certbot
sudo yum install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

## Docker Deployment

### 1. Docker Compose Setup
```bash
# Start with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

### 2. Scale Services
```bash
# Scale enclave instances
docker-compose -f docker-compose.prod.yml up -d --scale enclave=3
```

## Kubernetes Deployment

### 1. Prepare Kubernetes Manifests
```bash
# Apply Kubernetes configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### 2. Monitor Deployment
```bash
# Check pod status
kubectl get pods -n lottery-enclave

# View logs
kubectl logs -f deployment/lottery-enclave -n lottery-enclave
```

## Monitoring Setup

### 1. CloudWatch Integration
```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
sudo rpm -U amazon-cloudwatch-agent.rpm

# Configure CloudWatch
sudo cp configs/cloudwatch-config.json /opt/aws/amazon-cloudwatch-agent/etc/
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json -s
```

### 2. Application Monitoring
```bash
# Setup Prometheus monitoring
docker run -d \
    --name prometheus \
    -p 9090:9090 \
    -v $(pwd)/configs/prometheus.yml:/etc/prometheus/prometheus.yml \
    prom/prometheus

# Setup Grafana dashboard
docker run -d \
    --name grafana \
    -p 3000:3000 \
    grafana/grafana
```

## Security Configuration

### 1. Firewall Setup
```bash
# Configure iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT    # SSH
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT    # HTTP
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT   # HTTPS
sudo iptables -A INPUT -j DROP                        # Drop all other traffic
sudo service iptables save
```

### 2. Enclave Security
```bash
# Verify enclave attestation
nitro-cli describe-enclaves
nitro-cli get-attestation-document --enclave-id <enclave-id>
```

## Backup and Recovery

### 1. Automated Backups
```bash
# Create backup script
cp scripts/backup.sh /etc/cron.daily/lottery-backup
chmod +x /etc/cron.daily/lottery-backup
```

### 2. Database Backup
```bash
# Backup application state
./scripts/backup.sh --type full --destination s3://your-backup-bucket
```

### 3. Disaster Recovery
```bash
# Restore from backup
./scripts/restore.sh --source s3://your-backup-bucket --date 2024-01-01
```

## Performance Tuning

### 1. Instance Optimization
```bash
# Optimize instance performance
echo 'net.core.rmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv4.tcp_rmem = 4096 65536 16777216' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 2. Enclave Memory Allocation
```bash
# Increase enclave memory
sudo sed -i 's/allocator_memory_size_MiB=1024/allocator_memory_size_MiB=2048/' /etc/default/grub
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo reboot
```

## Troubleshooting

### Common Issues

#### Enclave Fails to Start
```bash
# Check enclave status
nitro-cli describe-enclaves

# View enclave logs
nitro-cli console --enclave-id <enclave-id>

# Check system resources
free -m
df -h
```

#### Network Connectivity Issues
```bash
# Test network connectivity
curl -I http://localhost:6080/health

# Check enclave networking
sudo netstat -tlnp | grep 6080
```

#### Smart Contract Deployment Fails
```bash
# Check Ethereum connection
curl -X POST -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    $ETHEREUM_RPC_URL

# Verify contract bytecode
solc --version
solc contracts/Lottery.sol --bin --abi
```

### Log Analysis
```bash
# Application logs
tail -f /var/log/lottery-enclave.log

# System logs
journalctl -u lottery-enclave -f

# Docker logs
docker logs -f lottery-enclave
```

### Performance Monitoring
```bash
# Monitor resource usage
htop
iotop
nethogs

# Enclave metrics
nitro-cli get-enclave-measurements --enclave-id <enclave-id>
```

## Maintenance

### Regular Maintenance Tasks
1. **Security Updates**: Apply OS and package updates monthly
2. **Certificate Renewal**: Automated with certbot
3. **Log Rotation**: Configure with logrotate
4. **Backup Verification**: Test backup restoration monthly
5. **Performance Review**: Monitor metrics and optimize quarterly

### Update Procedures
1. **Application Updates**: Deploy new versions using blue-green deployment
2. **Security Patches**: Apply critical patches immediately
3. **Infrastructure Updates**: Coordinate with AWS maintenance windows