#!/bin/bash

# Check if service name and API key are provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <service-name>"
    exit 1
fi

SERVICE_NAME=$1

# Ensure the service file exists
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file ${SERVICE_FILE} does not exist."
    exit 1
fi

# Get the OpenAI API Key from the environment
OPENAI_API_KEY=$(printenv OPENAI_API_KEY)

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set."
    exit 1
fi

# Backup the original service file before making changes
cp "$SERVICE_FILE" "$SERVICE_FILE.bak"

# Insert or update the OPENAI_API_KEY environment variable in the service file
if grep -q "Environment=\"OPENAI_API_KEY=" "$SERVICE_FILE"; then
    # If the key is already in the service file, replace it
    sed -i "s|Environment=\"OPENAI_API_KEY=.*|Environment=\"OPENAI_API_KEY=${OPENAI_API_KEY}\"|" "$SERVICE_FILE"
else
    # If the key is not in the service file, add it under the [Service] section
    sed -i "/\[Service\]/a Environment=\"OPENAI_API_KEY=${OPENAI_API_KEY}\"" "$SERVICE_FILE"
fi

# Reload systemd to apply the changes
sudo systemctl daemon-reload

# Restart the service to apply the new configuration
sudo systemctl restart "$SERVICE_NAME"

# Verify the service status
sudo systemctl status "$SERVICE_NAME"

echo "OPENAI_API_KEY has been injected and the service has been restarted."
