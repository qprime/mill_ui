# app.py (merged: restored all routes + preserved current AI integration)
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import requests
import uuid

from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, send_from_directory
sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.llm.ai_router import get_router
from scripts.llm.context_loader import build_context_prompt_fragments, load_context_for_persona
from scripts.embedding.rag_loader import load_summaries, EmbedFunction
from chromadb import PersistentClient
from scripts.tasking.task_manager import load_tasks, update_task, create_task, get_task
from scripts.chatting.chat_logger import log_chat_turn

app = Flask(__name__, template_folder='templates', static_folder='static')
router = get_router("openai")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_shell_command():
    import subprocess
    data = request.get_json()
    cmd = data.get("command", "")
    if not cmd:
        return jsonify({"error": "No command provided"}), 400
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard')
def serve_dashboard():
    dashboard_path = os.path.join(app.root_path, 'static/dashboard')
    return send_from_directory(dashboard_path, 'index.html')

@app.route("/lab-manager")
def lab_manager():
    return render_template("lab_manager.html")

@app.route("/voice")
def voice_terminal():
    return render_template("voice_terminal.html")

@app.route("/jsonl-review")
def jsonl_review():
    return render_template("jsonl_review.html")

@app.route("/tasks")
def show_tasks():
    raw_tasks = load_tasks()
    print(f"🔍 Total tasks loaded: {len(raw_tasks)}")

    # Debug all task archive flags
    for t in raw_tasks:
        print(f"  - {t['id']}: archived = {t.get('archived')}")

    # Filter non-archived tasks
    tasks = [t for t in raw_tasks if not str(t.get("archived", "false")).lower() == "true"]

    if not tasks:
        print("⚠️ No tasks passed the archive filter")

    # Sort "planned" tasks by `order`
    for task in tasks:
        if task.get("status") == "planned":
            task.setdefault("order", 0)

    # Group by status
    grouped = {}
    for task in tasks:
        status = task.get("status", "unknown")
        grouped.setdefault(status, []).append(task)

    if "planned" in grouped:
        grouped["planned"].sort(key=lambda t: t.get("order", 0))

    print("🧪 Grouped:")
    for k, v in grouped.items():
        print(f"  - {k}: {len(v)} tasks")

    return render_template("task_backlog.html", tasks_by_status=grouped)



@app.route("/tasks/update", methods=["POST"])
def update_task_status():
    task_id = request.form.get("task_id")
    new_status = request.form.get("new_status")
    if task_id and new_status:
        update_task(task_id, {"status": new_status})
    return redirect(url_for("show_tasks"))

@app.route("/tasks/create", methods=["GET", "POST"])
def create_task_form():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        tags = request.form.get("tags", "").split(",")
        files = request.form.get("files", "").split(",")
        steps = request.form.get("steps", "").split("\n")

        create_task(
            title=title,
            description=description,
            tags=[t.strip() for t in tags if t.strip()],
            files=[f.strip() for f in files if f.strip()],
            steps=[s.strip() for s in steps if s.strip()]
        )
        return redirect(url_for("show_tasks"))

    return render_template("task_create.html")

@app.route("/tasks/edit/<task_id>", methods=["GET", "POST"])
def edit_task(task_id):

    if request.method == "POST":
        updated_data = {
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
            "files": [f.strip() for f in request.form.get("files", "").split(",") if f.strip()],
            "steps": [s.strip() for s in request.form.get("steps", "").split("\n") if s.strip()],
            "updated_at": datetime.utcnow().isoformat()
        }
        update_task(task_id, updated_data)
        return redirect(url_for("show_tasks"))

    task = get_task(task_id)
    return render_template("task_edit.html", task=task)

@app.route("/prompt", methods=["POST"])
def handle_prompt():
    data = request.get_json()
    user_input = data.get("input", "")
    reply = f"Echo: {user_input}"
    return jsonify({"response": reply})

@app.route("/chat")
def chat():
    chat_id = str(uuid.uuid4())
    return render_template("chat.html", chat_id=chat_id)

# context_loader.py (inside scripts/llm)
from typing import List, Optional


def get_cliff_status():
    from flask import request
    import platform

    return {
        "model": "gpt-4o",
        "context_window_tokens": 128000,
        "voice_enabled": True,
        "whisper_endpoint": "https://192.168.0.179:8001/transcribe",
        "tts_enabled": True,
        "rag_enabled": True,
        "active_modules": [
            "code_chunking", "cli_logger", "task_manager", "memory_graph", "voice_pipeline"
        ],
        "ui_mode": "web",  # or "CLI" if you build that later
        "request_ip": request.remote_addr,
        "host": platform.node()
    }

@app.route("/ask", methods=["POST"])
def ask_openai():
    try:
        import time
        from scripts.llm.context_router import route_context
        from scripts.llm.personas import get_persona_prompt
        from scripts.distillation.cleaner import clean_text
        from scripts.distillation.distill_text import distill_text
        from scripts.llm.context_loader import (
            load_context_for_persona,
            get_cliff_status
        )

        data = request.get_json()
        raw_input = data.get("prompt", "")
        tone = data.get("tone", "neutral")
        chat_id = data.get("chat_id")  # Required; injected in JS via data attribute
        print("***Chat_ID: " + chat_id)
        if not raw_input or not chat_id:
            return jsonify({"error": "Missing prompt or chat_id"}), 400

        # 🔍 Clean + Route + Distill Prompt
        cleaned = clean_text(raw_input)
        routing = route_context(cleaned)
        persona = routing.get("persona", "default")
        suggested_context = routing.get("suggested_context", [])

        distilled_result = distill_text(cleaned, {
            "persona": persona,
            "task_type": "specification",
            "tone": tone,
            "urgency": "medium"
        }, strict_mode=True)
        distilled_prompt = distilled_result["distilled_text"]

        # 🎭 Persona + Context
        system_message = get_persona_prompt(persona)
        context_blocks = load_context_for_persona(distilled_prompt, persona, suggested_context, chat_id=chat_id)

        sidecar_context = context_blocks["sidecar"]
        project_memory = context_blocks["memory"]

        # 📊 System Status
        status = get_cliff_status()
        print("[ask_openai] Cliff system status:")
        for k, v in status.items():
            print(f"  {k}: {v}")
        status_block = "\n".join(f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in status.items())

        # 🧠 Final Full Context
        full_context = "\n\n".join([
            "# Recent Conversation (last few turns)",
            sidecar_context or "(No recent interaction yet.)",
            "# Related Project Memory",
            project_memory,
            "# System Runtime Status",
            status_block
        ])

        # 🧑‍💻 Compose Messages + Send
        augmented_prompt = f"{full_context}\n\nUser asked:\n{distilled_prompt}"
        messages = [system_message, {"role": "user", "content": augmented_prompt}]

        start = time.time()
        reply = router.chat(messages, model="gpt-4o")
        end = time.time()

        # ⏱️ Metrics
        def count_tokens(text): return len(text.split())
        tokens_in = sum(count_tokens(m["content"]) for m in messages)
        tokens_out = count_tokens(reply)
        latency_ms = int((end - start) * 1000)

        # 🧾 Logging
        log_chat_turn(
            persona=persona,
            chat_id=chat_id,
            user_input=raw_input,
            cleaned=distilled_result["original_input"]["cleaned_text"],
            distilled=distilled_prompt,
            routing=routing,
            response=reply,
            model="gpt-4o"
        )

        return jsonify({
            "response": reply,
            "rag_empty": project_memory.strip().startswith("⚠️"),
            "model": "gpt-4o",
            "routing": routing,
            "chat_id": chat_id,
            "distilled_input": distilled_prompt,
            "original_input": distilled_result["original_input"]["cleaned_text"],
            "metrics": {
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out
            },
            "debug": {
                "full_context": full_context,
                "distilled_input": distilled_prompt,
                "model": "gpt-4o",
                "routing": routing,
                "metrics": {
                    "latency_ms": latency_ms,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out
                }
            }

        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/chat/<chat_id>/update_summary", methods=["POST"])
def update_summary(chat_id):
    from scripts.chatting.chat_logger import get_chat_log_paths

    new_summary = request.form.get("summary", "")
    persona = "cliff_core"
    paths = get_chat_log_paths(chat_id, persona)
    sidecar_path = paths["sidecar"]

    print(f"[update_summary] Writing summary to: {sidecar_path.resolve()}")
    print(f"[update_summary] Exists? {sidecar_path.exists()}")

    sidecar_path.parent.mkdir(parents=True, exist_ok=True)  # ← fix here

    if sidecar_path.exists():
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[update_summary] Failed to load existing sidecar: {e}")
            data = {"chat_id": chat_id, "turns": []}
    else:
        data = {"chat_id": chat_id, "turns": []}

    data["summary"] = new_summary

    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return jsonify({"status": "ok"})





@app.route("/chat/<chat_id>/update_facts", methods=["POST"])
def update_facts(chat_id):
    from scripts.chatting.chat_logger import get_chat_log_paths

    persona = "cliff_core"  # TODO: make dynamic later
    try:
        facts = json.loads(request.form.get("facts", "{}"))
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid facts JSON"}), 400

    paths = get_chat_log_paths(chat_id, persona)
    sidecar_path = paths["sidecar"]

    print(f"[update_facts] Writing facts to: {sidecar_path.resolve()}")
    print(f"[update_facts] Exists? {sidecar_path.exists()}")

    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    if sidecar_path.exists():
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[update_facts] Failed to load existing sidecar: {e}")
            data = {"chat_id": chat_id, "turns": []}
    else:
        data = {"chat_id": chat_id, "turns": []}

    data["facts"] = facts

    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return jsonify({"status": "ok"})


@app.route("/chat/<chat_id>/sidecar", methods=["GET"])
def get_sidecar_data(chat_id):
    from scripts.chatting.chat_logger import get_chat_log_paths

    persona = "cliff_core"
    paths = get_chat_log_paths(chat_id, persona)
    sidecar_path = paths["sidecar"]

    if not sidecar_path.exists():
        return jsonify({"summary": "", "facts": {}})

    try:
        with open(sidecar_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[get_sidecar_data] Failed to read sidecar: {e}")
        return jsonify({"summary": "", "facts": {}})

    return jsonify({
        "summary": data.get("summary", ""),
        "facts": data.get("facts", {})
    })


    
@app.route("/tasks/archive/<task_id>", methods=["POST"])
def archive_task(task_id):
    update_task(task_id, {
        "archived": True,
        "updated_at": datetime.utcnow().isoformat()
    })
    return redirect(url_for("show_tasks"))

@app.route("/tasks/reorder", methods=["POST"])
def reorder_tasks():
    from development.task_manager import reorder_tasks_by_ids

    data = request.get_json()
    ids = data.get("ids", [])

    if not isinstance(ids, list):
        return jsonify({"error": "Invalid format"}), 400

    reorder_tasks_by_ids(ids)
    return jsonify({"status": "ok"}), 200

@app.route("/voice/speak", methods=["POST"])
def voice_speak():
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "No text provided"}), 400

        # Send to Coqui TTS
        tts_response = requests.post(
            "https://192.168.0.179:5042/speak",
            json={"text": text},
            verify=False  # Only for self-signed local certs
        )

        if tts_response.status_code != 200:
            return jsonify({"error": "TTS server error"}), 500

        # Serve back the WAV audio
        return send_file(BytesIO(tts_response.content), mimetype="audio/wav")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parents[1]
    summary_dir = root_dir / "memory/development/module_summaries"
    print(f"📁 Looking for summaries in: {summary_dir}")
    if not summary_dir.exists():
        print("❌ Summary folder not found.")
    else:
        md_files = list(summary_dir.glob("*.md"))
        print(f"📄 Found {len(md_files)} .md files: {[f.name for f in md_files]}")

    load_summaries()
    app.run(host="0.0.0.0", port=8080, ssl_context=("cert/web_server.crt", "cert/web_server.key"), debug=True)
