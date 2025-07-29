# Cliff AI: Lab Manager - Project Overview

## Purpose
The Lab Manager is a core module within the Cliff AI system. It acts as the centralized inventory and health-tracking brain for all physical devices across the home lab and workshop. It manages information about Raspberry Pis, Odroids, Jetsons, 3D printers, CNCs, IP cameras, and more.

This module allows device state, configuration, metadata, and roles to be logged, queried, updated, and monitored via CLI, text, or eventually, voice interfaces.

---

## Current Architecture

- **Server:** Beelink EQ R6 Mini PC
  - AMD Ryzen 9 6900HX, 24GB DDR5 RAM, 1TB SSD
  - Ubuntu 24.04 LTS

- **Service:**
  - `cliff-device-manager.service`
  - Managed via `systemd`
  - Automatically starts on boot

- **Application:**
  - Flask API (Python 3, lightweight server)
  - Listens on `localhost:5000`

- **Data Storage:**
  - Flat file: `device_inventory.json`
  - Designed for future upgrade to SQLite backend

- **Directory Structure:**
  - `~/cliff_ai/lab_manager/` (source code and runtime)
  - `~/cliff_ai/docs/` (project documentation)

---

## API Endpoints

- `POST /report`
  - Devices self-report their metadata
- `GET /devices`
  - Returns full inventory listing
- `POST /update/<device_id>`
  - Update specific fields on a device
- `POST /reset`
  - Clears entire inventory (confirmation required in CLI)
- `GET /query`
  - Query devices by fields such as `configured`, `role_tags`, etc.

---

## CLI Tools

- **Tool Name:** `cliff-device-manager`
- **Capabilities:**
  - `list` — List all devices
  - `unconfigured` — List devices that are not yet configured
  - `find-tag <tag>` — Find devices by their role tags
  - `register <json-file>` — Add new device by uploading a JSON file
  - `update <device_id> <key>=<value>` — Update device metadata
  - `delete <device_id>` — Safely delete a device with confirmation prompt

- **Notes:**
  - JSON templates provided for easy device registration
  - Designed for simple CLI or SSH-based management across the network

---

## Network Topology

- **Centralized Model:**
  - The Beelink server is the authoritative source of truth
  - All networked devices will periodically report in via lightweight agents

- **Access:**
  - Local CLI on Beelink
  - SSH from any other machine
  - Future integrations: voice queries, dashboard UI, or multimodal interfaces

---

## Next Steps

1. **CLI Archiver System:**
   - Log and structure CLI activity across networked computers
   - Push command logs to the Lab Manager server for time-based, semantic search

2. **Lightweight Node Reporters:**
   - Deploy simple reporting agents on Raspberry Pis, Jetsons, and other devices

3. **Voice and Semantic Queries:**
   - Integrate natural language interface to interact with inventory and logs

4. **Database Upgrade:**
   - Move from JSON to SQLite for better indexing and scalable querying

---

## Project Vision

The Lab Manager is the first core pillar toward building a modular, AI-driven, fully voice-accessible operating system for the user's home lab and workshop. Every interaction with devices, hardware health, or system management will eventually route through or reference this intelligent core.


