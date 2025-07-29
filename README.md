# 🧠 Cliff AI

Cliff AI is a modular, voice-driven personal assistant framework for system automation, memory, and contextual intelligence.

## Project Structure
| Folder         | Description (what belongs here / what doesn't)                 |
|----------------|---------------------------------------------------------------|
| context/       | Shared schemas, generated context, config. No outputs/logs.    |
| local_services/| systemd service files & scripts for local daemons. No user data|
| memory/        | All persistent memory (JSONL logs, embeddings, schemas, etc).  |
| personas/      | Persona configs/prompts, role definitions. No scripts.         |
| pipelines/     | Data/image/text processing pipelines. No UI/web code.          |
| scripts/       | Utilities, CLI tools, batch jobs. No long-lived services.      |
| web/           | Web UI, Flask server, templates, static assets.                |

## Quickstart
[insert setup instructions]

## Policies
- Every subfolder: minimal README.md
- No artifacts/output in code folders—use memory/ or output/
- All configs in configs/ or named config/
