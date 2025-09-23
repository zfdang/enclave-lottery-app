#!/bin/bash
set -e

# Variables
APP_USER="ec2-user"   # or another user you want to run Anvil as
SERVICE_NAME="anvil"
APP_HOME="/home/${APP_USER}"
FOUNDRY_DIR="${APP_HOME}/.foundry"

# install foundry if not already installed
if [ ! -d "$FOUNDRY_DIR" ]; then
    echo "Foundry not found, installing..."
    sudo -u ${APP_USER} bash -c "curl -L https://foundry.paradigm.xyz | bash"
    sudo -u ${APP_USER} bash -c "${FOUNDRY_DIR}/bin/foundryup"
else
    echo "Foundry already installed, skipping installation."
fi


# Ensure foundry binaries are in PATH for the service
FOUNDRY_BIN="${APP_HOME}/.foundry/bin"

# Create systemd service for Anvil
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<SERVICE_EOF
[Unit]
Description=Anvil local Ethereum testnet
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${APP_HOME}
ExecStart=${FOUNDRY_BIN}/anvil --host 0.0.0.0 --port 8545
Restart=on-failure
Environment=PATH=${FOUNDRY_BIN}:/usr/local/bin:/usr/bin:/bin
StandardOutput=append:${APP_HOME}/anvil.log
StandardError=append:${APP_HOME}/anvil.log

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Reload systemd, enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

# show anvil logs
sudo journalctl -u ${SERVICE_NAME} -f --no-pager &

echo "Anvil should now be running on port 8545"

