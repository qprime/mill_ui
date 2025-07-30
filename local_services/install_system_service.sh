#!/bin/bash

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <service-name>"
    exit 1
fi

SERVICE_NAME=$1
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file ${SERVICE_FILE} does not exist."
    exit 1
fi

# Pull and clean the OpenAI API Key from the environment (strip whitespace/newlines)
OPENAI_API_KEY="$(printenv OPENAI_API_KEY | tr -d '\r\n[:space:]')"

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set or is blank."
    exit 1
fi

echo "DEBUG: Key is [${OPENAI_API_KEY}] Length=[${#OPENAI_API_KEY}]"
echo -n "$OPENAI_API_KEY" | od -c

sudo cp "$SERVICE_FILE" "$SERVICE_FILE.bak"

if grep -q "Environment=OPENAI_API_KEY=" "$SERVICE_FILE"; then
    sudo sed -i "s|Environment=OPENAI_API_KEY=.*|Environment=OPENAI_API_KEY=${OPENAI_API_KEY}|" "$SERVICE_FILE"
else
    sudo sed -i "/\[Service\]/a Environment=OPENAI_API_KEY=${OPENAI_API_KEY}" "$SERVICE_FILE"
fi

sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME"

echo "OPENAI_API_KEY has been injected and the service has been restarted."
