# path: local_services/lab_manager/app.py
# type: web service
# tags: flask, api, inventory, lab
# owner: cliff
# depends_on: memoriesmemory_manager.py
# description: Manages lab device inventory and endpoints for device reporting, querying, and management.

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime
import os
from memories.memory_manager import add_to_domain

app = Flask(__name__)
CORS(app)
DATA_FILE = os.path.expanduser("~/cliff_ai/memorieslab/device_inventory.json")


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            lines = f.readlines()
            return {json.loads(line)["device_id"]: json.loads(line) for line in lines}
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        for device in data.values():
            f.write(json.dumps(device) + "\n")


@app.route("/report", methods=["POST"])
def report():
    device_data = request.json
    device_data["last_seen"] = datetime.utcnow().isoformat()
    all_data = load_data()
    all_data[device_data["device_id"]] = device_data
    save_data(all_data)
    add_to_domain(
        domain="lab",
        text=f"Device reported: {device_data ['device_id']}",
        source="lab_manager",
        tags=["device", "report"],
    )
    return jsonify({"status": "ok", "device": device_data["device_id"]})


@app.route("/devices", methods=["GET"])
def list_devices():
    return jsonify(load_data())


@app.route("/reset", methods=["POST"])
def reset():
    save_data({})
    return jsonify({"status": "inventory reset"})


@app.route("/update/<device_id>", methods=["POST"])
def update_device(device_id):
    new_fields = request.json
    all_data = load_data()
    if device_id not in all_data:
        return jsonify({"error": "Device not found"}), 404
    all_data[device_id].update(new_fields)
    all_data[device_id]["last_updated"] = datetime.utcnow().isoformat()
    save_data(all_data)
    add_to_domain(
        domain="lab",
        text=f"Device updated: {device_id } with fields {list (new_fields .keys ())}",
        source="lab_manager",
        tags=["device", "update"],
    )
    return jsonify({"status": "updated", "device": all_data[device_id]})


@app.route("/query", methods=["GET"])
def query_devices():
    query_params = request.args
    all_data = load_data()
    filtered_devices = []
    for device in all_data.values():
        match = True
        for key, val in query_params.items():
            expected = val.lower()
            actual = str(device.get(key, "")).lower()
            if expected == "false":
                expected = "false"
                actual = str(bool(device.get(key, False))).lower()
            if expected == "true":
                expected = "true"
                actual = str(bool(device.get(key, False))).lower()
            if expected not in actual:
                match = False
                break
        if match:
            filtered_devices.append(device)
    return jsonify(filtered_devices)


@app.route("/delete/<device_id>", methods=["POST"])
def delete_device(device_id):
    all_data = load_data()
    if device_id not in all_data:
        return jsonify({"error": "Device not found"}), 404
    del all_data[device_id]
    save_data(all_data)
    add_to_domain(
        domain="lab",
        text=f"Device deleted: {device_id }",
        source="lab_manager",
        tags=["device", "delete"],
    )
    return jsonify({"status": "deleted", "device": device_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
