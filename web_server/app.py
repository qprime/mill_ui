import sys
from pathlib import Path
import json
sys.path.append(str(Path(__file__).resolve().parents[1]))

from flask import Flask, render_template, request, redirect, url_for
from development.task_manager import load_tasks, update_task, create_task

app = Flask(__name__, template_folder='templates', static_folder='static')


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
def json_review():
    return render_template("jasonl_review.html")


# 🔽 NEW ROUTES
@app.route("/tasks")
def show_tasks():
    tasks = load_tasks()
    grouped = {}
    for task in tasks:
        grouped.setdefault(task["status"], []).append(task)
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
    print("Resolved path:", log_path)
    messages = []
    if log_path.exists():
        print("✅ File exists!")
        with open(log_path, "r") as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    print("Parsed line:", obj)
                    messages.append(obj)
                except json.JSONDecodeError as e:
                    print("❌ JSON decode error:", e)
    else:
        print("❌ File missing.")
    return render_template("chatlog.html", messages=messages)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, ssl_context=("cert/web_server.crt", "cert/web_server.key"), debug=True)
