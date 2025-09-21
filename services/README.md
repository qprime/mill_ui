# Services CLI

Owner path: services/

## 1. What this is

Services manages systemd integration for the cliff stack, bundling unit files and a CLI to control them.
It centralises how background daemons are installed, started, and inspected.

## 2. When to use it

- List or control cliff services on a development or production host.
- Install or update systemd unit files after changing service configurations.
- Add new long-running processes to the deployment footprint.

## 3. How to run

Call the `services` CLI through `run.py` (or invoke the module directly) with explicit scopes.

```bash
python run.py services list
python run.py services install web --scope system
python run.py services restart web
sudo ./services/install_system_service.sh web
```

## 4. Inputs & outputs (for AI & humans)

- `services/service_registry.json` — declared services, unit filenames, and scopes.
- `services/*.service` — templated systemd unit files synced by the CLI.
- `services/cli_archiver/` — helper code referenced by service units.
- `web/cliff_server/cert/` — TLS assets consumed by the web service unit.

## 5. Public surface

- `services.cli.api(argv=None)` — command dispatcher returning systemd exit codes.
- `services.registry.load(path=None)` — load and validate the service registry JSON.
- `services.cli._install(service, scope)` — copy unit files and reload systemd daemons.
- `services.install_system_service.sh` — shell helper for manual installs.

## 6. Invariants & guardrails

- Registry IDs must stay unique and match the `ServiceRegistry` lookup keys.
- Unit files live under `services/` and are copied verbatim; keep them deterministic.
- System-level installs require root privileges; respect the `scope` declared in the registry.
- CLI commands forward exit codes from `systemctl`; do not swallow failures.

## 7. Extension points

- Add new services by dropping a unit file and extending `service_registry.json`.
- Augment helper code under `services/cli_archiver` when the CLI needs new behaviour.
- Document new operations here and update the sweeper specification.
- Wire monitoring or health checks by adding custom `systemctl` subcommands to the CLI.

## 8. AI reading order

- `services/cli.py` — CLI implementation over systemctl.
- `services/registry.py` — Registry dataclasses and loader.
- `services/service_registry.json` — Declared service inventory.
- `services/install_system_service.sh` — Convenience wrapper for installing units.
- `services/cliff-web-server.service` — Example unit wiring for the Flask app.
