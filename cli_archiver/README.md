# 🧾 Cliff AI — CLI Archiver

The CLI Archiver module captures and stores shell command history from multiple machines. This data becomes part of Cliff AI’s long-term memory, enabling context-aware reasoning about past work, automation patterns, and productivity insights.

---

## 📁 Structure

| File / Folder              | Purpose                                                  |
|----------------------------|----------------------------------------------------------|
| `cliff_cli_logger.py`      | CLI logger client script for capturing and sending logs |
| `server/app.py`            | Flask server receiving log entries from multiple hosts  |
| `server/cli_log_store.py`  | Persistent log handler and storage backend               |

---

## 🧠 Memory Output

Log entries are written in `.jsonl` format to:

- `memory/cliff_state/cli_logs.jsonl`

Each entry includes:
- Timestamp
- Command string
- Hostname or machine ID
- Optional session or project context

---

## 🌐 API Endpoints (Server)

- `POST /log`: Receives new CLI command log entries
- `GET /logs`: Returns recent or filtered CLI logs
- `GET /stats`: (Planned) Return usage stats or timeline summaries

---

## 🛠️ Usage

### Run the Logger
```bash
python cli_archiver/cliff_cli_logger.py


🔮 Planned Features

    Semantic log tagging (auto-detect project/intent)

    Visualization of shell session timelines

    Integration with task manager for CLI-derived task suggestions


---

