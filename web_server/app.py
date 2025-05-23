# app.py (merged: restored all routes + preserved current AI integration)
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import requests

from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, send_from_directory
sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.llm.ai_router import get_router
from scripts.llm.context_loader import build_context_prompt_fragments
from scripts.embedding.rag_loader import load_summaries, EmbedFunction
from chromadb import PersistentClient
from scripts.tasking.task_manager import load_tasks, update_task, create_task, get_task

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

@app.route("/chatlog")
def chatlog():
    root_dir = Path(__file__).resolve().parent.parent
    log_path = root_dir / "memory/chat_logs/2025-05-03.jsonl"
    messages = []
    if log_path.exists():
        with open(log_path, "r") as f:
            for line in f:
                try:
                    messages.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
    return render_template("chatlog.html", messages=messages)

@app.route("/voice/log", methods=["POST"])
def log_voice_interaction():
    data = request.get_json()
    user_text = data.get("user_text")
    cliff_reply = data.get("cliff_reply")
    context_tags = data.get("context_tags", ["voice"])

    if not user_text or not cliff_reply:
        return {"error": "Missing input"}, 400

    log_entries = [
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "role": "user",
            "content": user_text,
            "message_type": "input",
            "context_tags": context_tags
        },
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "role": "cliff",
            "content": cliff_reply,
            "message_type": "response",
            "context_tags": context_tags
        }
    ]

    log_path = Path("memory/chat_logs") / f"{datetime.utcnow().date()}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as f:
        for entry in log_entries:
            f.write(json.dumps(entry) + "\n")

    return {"status": "ok"}, 200

@app.route("/prompt", methods=["POST"])
def handle_prompt():
    data = request.get_json()
    user_input = data.get("input", "")
    reply = f"Echo: {user_input}"
    return jsonify({"response": reply})

@app.route("/chat")
def chat():
    return render_template("chat.html")



# context_loader.py (inside scripts/llm)
from typing import List, Optional

def get_project_context(prompt: str, paths: Optional[List[str]] = None, max_docs: int = 3) -> str:
    """
    Retrieve relevant context using ChromaDB summaries.
    Optionally filter by memory paths or domains.
    """
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    client = chromadb.PersistentClient(path="memory/chroma")
    collection = client.get_or_create_collection(
        name="module_summaries",
        embedding_function=SentenceTransformerEmbeddingFunction()
    )

    filters = {}
    if paths:
        filters["path"] = {"$in": paths}

    try:
        results = collection.query(
            query_texts=[prompt],
            n_results=max_docs,
            where=filters if filters else None
        )

        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs)

    except Exception as e:
        print(f"⚠️ get_project_context failed: {e}")
        return "[No relevant context found.]"


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
        

        data = request.get_json()
        prompt = data.get("prompt", "")
        tone = data.get("tone", "neutral")

        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        # 🧠 Stage 1: Local LLM to classify prompt
        routing = route_context(prompt)
        persona = routing.get("persona", "default")
        suggested_context = routing.get("suggested_context", [])
        emotions_enabled = (tone == "emotional")

        # 🧠 Stage 2: Construct persona system message
        system_message = get_persona_prompt(persona)

        # 🧠 Stage 3: Build contextual memory fragments
        base_context = build_context_prompt_fragments(paths=suggested_context)
        rag_context = get_project_context(prompt, paths=suggested_context)
        status = get_cliff_status()
        status_block = "\n".join(f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in status.items())

        full_context = "\n\n".join([
            "# CLIFF Project Context",
            *base_context[:5],
            f"# Retrieved Summaries (RAG)\n{rag_context}",
            f"# System Runtime Status\n{status_block}"
        ])

        augmented_prompt = f"{full_context}\n\nUser asked:\n{prompt}"
        messages = [system_message, {"role": "user", "content": augmented_prompt}]

        # 🔁 Forward to OpenAI (or fallback) LLM
        start = time.time()
        reply = router.chat(messages, model="gpt-4o")
        end = time.time()

        def count_tokens(text): return len(text.split())
        tokens_in = sum(count_tokens(m["content"]) for m in messages)
        tokens_out = count_tokens(reply)
        latency_ms = int((end - start) * 1000)

        return jsonify({
            "response": reply,
            "model": "gpt-4o",
            "routing": routing,
            "metrics": {
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


    
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
