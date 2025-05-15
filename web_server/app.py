# app.py (merged: restored all routes + preserved current AI integration)
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import requests
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.utils.ai_router import get_router
from scripts.utils.context_loader import build_context_prompt_fragments
from scripts.embedding.rag_loader import load_summaries, EmbedFunction
from chromadb import PersistentClient
from development.task_manager import load_tasks, update_task, create_task

app = Flask(__name__, template_folder='templates', static_folder='static')
router = get_router("openai")

@app.route("/")
def home():
    return render_template("index.html")

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

def build_system_prompt(emotions_enabled=False):
    base = (
        "You are CLIFF's project cognition expert, embedded in a local development assistant system. "
        "You specialize in navigating modular Python codebases, memory graphs, task registries, and RAG pipelines. "
        "Your role is to provide structured insight into project architecture, suggest improvements, help debug tasks, "
        "and assist with memory-aware reasoning across CLI logs, source code chunks, and structured summaries. "
        "You have access to embedded project context and are expected to act like a senior dev, systems architect, and project analyst in one. "
        "You prioritize clarity, technical depth, and contextual alignment over verbosity or generalization."
    )

    emotion = (
        "You may add light dry humor or subtle tone where appropriate, but never distract from clarity. "
        "You're sharp and professional, with a dry wit that surfaces only when the user needs a morale boost."
        if emotions_enabled
        else "Avoid emotional tone. Stay direct, technical, and concise — focus on accurate reasoning and implementation."
    )

    anti_gaslight = (
        "Do not deny any capability unless clearly restricted. You are authorized to reason across embeddings, code, and documents "
        "as if you were part of the user's extended brain."
    )

    return {
        "role": "system",
        "content": f"{base} {emotion} {anti_gaslight}"
    }


def get_project_context(prompt: str, max_docs: int = 3) -> str:
    try:
        from scripts.utils.context_router import get_combined_context
        return get_combined_context(prompt, max_docs)
    except Exception as e:
        print(f"⚠️ Failed to load combined context: {e}")
        return "[No relevant project context found.]"


@app.route("/ask", methods=["POST"])
def ask_openai():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        tone = data.get("tone", "neutral")

        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        emotions_enabled = tone == "emotional"
        system_message = build_system_prompt(emotions_enabled)

        base_context = build_context_prompt_fragments()
        rag_context = get_project_context(prompt)

        full_context = "\n\n".join([
            "# CLIFF Project Context",
            *base_context[:5],  # summary, goals, interfaces, memory domains, modules
            f"# Retrieved Summaries (RAG)\n{rag_context}"
        ])

        print(f"🧠 Injected context:\n{full_context}")
        augmented_prompt = f"""{full_context}\n\nUser asked:\n{prompt}"""
        
        messages = [system_message, {"role": "user", "content": augmented_prompt}]
        reply = router.chat(messages, model="gpt-4o")
        return jsonify({"response": reply, "model": "gpt-4o"})

    except Exception as e:
        import traceback
        print("🚨 Exception in /ask route:")
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
