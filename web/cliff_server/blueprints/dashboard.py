"""Dashboard and static UI blueprint."""

from flask import Blueprint, render_template, send_from_directory, current_app
import os

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def home():
    return render_template("index.html")

@dashboard_bp.route("/dashboard")
def serve_dashboard():
    dashboard_path = os.path.join(current_app.root_path, 'static/dashboard')
    return send_from_directory(dashboard_path, 'index.html')

@dashboard_bp.route("/lab-manager")
def lab_manager():
    return render_template("lab_manager.html")

@dashboard_bp.route("/jsonl-review")
def jsonl_review():
    return render_template("jsonl_review.html")