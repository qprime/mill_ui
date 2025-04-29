#!/usr/bin/env bash

API_URL="http://localhost:5000"

function usage() {
  echo "Usage: cliff-device-manager [command] [options]"
  echo ""
  echo "Commands:"
  echo "  list                         List all devices"
  echo "  unconfigured                 List unconfigured devices"
  echo "  find-tag <tag>               List devices matching a role_tag"
  echo "  reset                        Reset all devices (CAUTION)"
  echo "  update <id> <key>=<val>      Update a device with a field"
  echo "  register <json-file>         Register a new device using JSON file"
  echo ""
  echo "Example device JSON template:"
  echo '  {'
  echo '    "device_id": "rpi-laser-01",'
  echo '    "type": "Raspberry Pi 4",'
  echo '    "ip_address": "192.168.1.100",'
  echo '    "configured": false,'
  echo '    "role_tags": ["laser", "octoprint"],'
  echo '    "docker_containers": ["octoprint", "camera"],'
  echo '    "notes": "Connected to laser engraver near window"'
  echo '  }'
  echo ""
  echo "To register, save that as device.json and run:"
  echo "  cliff-device-manager register device.json"
}

function list_devices() {
  curl -s "$API_URL/devices" | jq
}

function list_unconfigured() {
  curl -s "$API_URL/query?configured=false" | jq
}

function find_by_tag() {
  local tag="$1"
  curl -s "$API_URL/query?role_tags=${tag}" | jq
}

function reset_devices() {
  read -p "Are you sure you want to reset ALL devices? (y/N): " confirm
  if [[ "$confirm" == "y" ]]; then
    curl -s -X POST "$API_URL/reset"
  else
    echo "Cancelled."
  fi
}

function update_device() {
  local id="$1"
  shift
  local field_pair="$1"
  IFS="=" read -r key val <<< "$field_pair"
  curl -s -X POST "$API_URL/update/$id" \
    -H "Content-Type: application/json" \
    -d "{\"$key\": \"$val\"}" | jq
}

function register_device() {
  local file="$1"
  if [[ -f "$file" ]]; then
    curl -s -X POST "$API_URL/report" \
      -H "Content-Type: application/json" \
      -d @"$file" | jq
  else
    echo "Error: File not found: $file"
  fi
}

function delete_device() {
  local id="$1"
  if [[ -z "$id" ]]; then
    echo "Error: You must provide a device_id to delete"
    return 1
  fi

  read -p "Are you sure you want to delete device '$id'? (y/N): " confirm
  if [[ "$confirm" != "y" ]]; then
    echo "Cancelled."
    return 0
  fi

  all_data=$(curl -s "$API_URL/devices")
  updated_data=$(echo "$all_data" | jq "del(.\"$id\")")

  if [[ "$updated_data" == "$all_data" ]]; then
    echo "Device ID '$id' not found."
    return 1
  fi

  echo "$updated_data" > /tmp/device_inventory.json
  curl -s -X POST "$API_URL/reset" > /dev/null
  curl -s -X POST "$API_URL/report" \
    -H "Content-Type: application/json" \
    -d @"<(
      jq -c 'to_entries | .[] | .value' /tmp/device_inventory.json
    )" > /dev/null

  echo "Device '$id' deleted."
}


case "$1" in
  list) list_devices ;;
  unconfigured) list_unconfigured ;;
  find-tag) shift; find_by_tag "$1" ;;
  reset) reset_devices ;;
  update) shift; update_device "$1" "$2" ;;
  register) shift; register_device "$1" ;;
  *) usage ;;
esac

