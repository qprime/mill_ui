#!/bin/bash

echo "[Cliff Lab Manager] Starting all core modules..."

# Start device manager (Flask API)
sudo systemctl start cliff-device-manager.service

# Placeholder for future modules
# sudo systemctl start cliff-voice-listener.service
# sudo systemctl start cliff-cli-logger.service

echo "[Cliff Lab Manager] All requested modules started."

