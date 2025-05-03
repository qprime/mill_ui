import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from development.task_manager import load_tasks


from flask import Flask, render_template

app = Flask(__name__, template_folder='templates')

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/")
def home():
    return "<h1>Welcome to the Cliff AI Control Panel</h1><p><a href='/lab-manager'>Manage Devices</a></p><p><a href='/voice'>Voice Terminal</a></p><p><a href='/jsonl-review'>jsonl review</a></p><p> \
        <a href='/tasks'>task_backlog</a></p>"

@app.route("/lab-manager")
def lab_manager():
    return render_template("lab_manager.html")

@app.route("/voice")
def voice_terminal():
    return render_template("voice_terminal.html")
    
@app.route("/jsonl-review")
def jsonl_review():
    return render_template("jasonl_review.html")

@app.route("/tasks")
def show_tasks():
    tasks = load_tasks()
    grouped = {}
    for task in tasks:
        grouped.setdefault(task["status"], []).append(task)
    return render_template("task_backlog.html", tasks_by_status=grouped)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, ssl_context=("cert/web_server.crt", "cert/web_server.key"), debug=True)
