# interfaces/ — Pluggable App Framework (Chat + Tasks wired)

## Layout
- `interfaces/app.py` — Flask app factory (`create_app`)
- `interfaces/app_registry.py` — registers app manifests
- `interfaces/apps/<app>/manifest.py` — per-app blueprint registration
- `interfaces/services/` — pure business logic (no Flask)
- `interfaces/adapters/api/` — JSON API endpoints
- `interfaces/adapters/web/` — HTML/HTMX endpoints
- `interfaces/templates/` — small, modular Jinja templates

## Run (dev)
```bash
pip install flask
export FLASK_APP=interfaces.app:create_app
flask run --port 8080
# or:
python -m interfaces.app
```

## Test
### Chat (web)
Open http://localhost:8080/chat and send a message.
### Chat (API)
```bash
curl -s -X POST http://localhost:8080/api/chat/ask \
  -H 'Content-Type: application/json' \
  -d '{"input":"Hello"}'
```
### Tasks (web)
Open http://localhost:8080/tasks
### Tasks (API)
```bash
curl -s -X POST http://localhost:8080/api/tasks/call \
  -H 'Content-Type: application/json' \
  -d '{"action":"get_active_grouped"}'
```

## Notes
- Adapters normalize `message|input -> input` before calling `services.chat.chat_reply`.
- Services call into your existing `cortex/*` and `memories/*` modules unchanged.
- Add new apps by creating `interfaces/apps/<name>/manifest.py` and corresponding adapters/services.
