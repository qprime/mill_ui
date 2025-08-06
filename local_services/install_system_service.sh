#!/bin/bash

# Usage: ./install_system_service.sh cliff-whisper
SERVICE_NAME=$1

if [ -z "$SERVICE_NAME" ]; then
  echo "Usage: $0 <service-name>"
  exit 1
fi

# Check if the source service file exists (in current directory)
if [ ! -f "$SERVICE_NAME.service" ]; then
  echo "Error: Local service file $SERVICE_NAME.service not found."
  exit 1
fi

# Install the service file
sudo cp "$SERVICE_NAME.service" /etc/systemd/system/

# Reload systemd and enable the service
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service"
sudo systemctl restart "$SERVICE_NAME.service"

echo "✅ Installed and started $SERVICE_NAME.service"
