# Deploying the new Flask+HTMX shell

1) Copy `interfaces.zip` into your project and extract:
   ```bash
   cd /home/squinlan/cliff_ai
   unzip -o ~/Downloads/interfaces.zip -d /home/squinlan/cliff_ai
   ```

2) Register blueprints in your Flask app (once):
   ```python
   # app.py or run.py (where you create `app = Flask(__name__)`)
   from interfaces.loader import get_blueprints
   for bp in get_blueprints():
       app.register_blueprint(bp)
   ```

3) Install/update the systemd service:
   ```bash
   sudo cp ~/Downloads/cliff-web-server.fixed.service /etc/systemd/system/cliff-web-server.service
   sudo systemctl daemon-reload
   sudo systemctl restart cliff-web-server
   sudo journalctl -fu cliff-web-server -n 200
   ```
   Or run the helper script:
   ```bash
   bash ~/Downloads/install_or_update_cliff_service.sh
   ```

4) Open the app:
   - Chat shell:      http://<host>:<port>/chat
   - Tasks skeleton:  http://<host>:<port>/tasks

New unified manager
--------------------
Use `python run.py services list` to see registered services.
Examples:
  python run.py services install web
  python run.py services start whisper
  python run.py services status web
