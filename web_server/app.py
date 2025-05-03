import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from flask import Flask, render_template, request, redirect, url_for
from development.task_manager import load_tasks, update_task

app = Flask(__name__, template_folder='templates')


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, ssl_context=("cert/web_server.crt", "cert/web_server.key"), debug=True)
