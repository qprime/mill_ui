#!/bin/bash
set -x
# Usage: ./install_system_service.sh <service-name> [--key|-k]
SERVICE_NAME=$1
INJECT_KEY=false

# Parse the optional key flag
if [[ "$2" == "--key" || "$2" == "-k" ]]; then
  INJECT_KEY=true
fi

if [ -z "$SERVICE_NAME" ]; then
  echo "Usage: $0 <service-name> [--key|-k]"
  exit 1
fi

if [ ! -f "$SERVICE_NAME.service" ]; then
  echo "Error: Local service file $SERVICE_NAME.service not found."
  exit 1
fi

TMP_SERVICE=$(mktemp)
cp "$SERVICE_NAME.service" "$TMP_SERVICE"

if $INJECT_KEY; then
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set!"
    echo "Export it in your shell before running this script."
    rm "$TMP_SERVICE"
    exit 1
  fi

  # Print the key (for debug; comment out if you don't want to expose in logs)
  echo "OPENAI_API_KEY (from environment): $OPENAI_API_KEY"

  # Insert the Environment line after WorkingDirectory (if present), else after [Service]
  if grep -q '^WorkingDirectory=' "$TMP_SERVICE"; then
    sed -i "/^WorkingDirectory=/a Environment=OPENAI_API_KEY=$OPENAI_API_KEY" "$TMP_SERVICE"
  else
    sed -i "/^\[Service\]/a Environment=OPENAI_API_KEY=$OPENAI_API_KEY" "$TMP_SERVICE"
  fi

  echo "🔑 Injected OPENAI_API_KEY into $SERVICE_NAME.service"
fi

# Install the (possibly modified) service file
sudo cp "$TMP_SERVICE" /etc/systemd/system/"$SERVICE_NAME.service"
rm "$TMP_SERVICE"

sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service"
sudo systemctl restart "$SERVICE_NAME.service"

echo "✅ Installed and started $SERVICE_NAME.service"
