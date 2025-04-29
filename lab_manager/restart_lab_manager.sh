#!/bin/bash

echo "[Cliff Lab Manager] Restarting device manager service..."

sudo systemctl stop cliff-device-manager.service
sleep 1
sudo systemctl start cliff-device-manager.service

echo "[Cliff Lab Manager] Status:"
sudo systemctl status cliff-device-manager.service --no-pager

echo "[Cliff Lab Manager] Tail logs (Ctrl+C to exit):"
journalctl -u cliff-device-manager.service -f

