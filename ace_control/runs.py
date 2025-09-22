from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from memories.framework import MemoryRegistry

from .ledger import record_memory_entry, write_summary_file
from .machines import MachineProfile, MachineRegistry
from .models import Brief, Mode, RunRecord, RunStatus, now_ts, path_relative_to
from .operate import OPERATE_ACTIONS, OperateCommand
from .operate_policy import evaluate_command_types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = PROJECT_ROOT / "runs"


class RunManager:
    def __init__(
        self,
        *,
        runs_root: Path | None = None,
        machine_registry: MachineRegistry | None = None,
        memory_registry: MemoryRegistry | None = None,
    ):
        self.runs_root = runs_root or RUNS_ROOT
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.machine_registry = machine_registry or MachineRegistry()
        self.memory_registry = memory_registry or MemoryRegistry()

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------
    def start_run(
        self,
        brief: Brief,
        *,
        operate_action: Optional[str] = None,
    ) -> RunRecord:
        routed_mode = self._resolve_mode(brief, operate_action)
        run_id = self._generate_id()
        created = now_ts()
        record = RunRecord(
            id=run_id,
            brief=brief,
            mode=routed_mode,
            machines=list(brief.machines or ["skylink"]),
            status=RunStatus.PENDING,
            created_at=created,
            updated_at=created,
            tags=list(brief.tags),
        )
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._persist_run(record)

        if routed_mode == Mode.IDEATE:
            record.headline = "Ideation captured"
            record.result_summary = brief.text
            record.touch(status=RunStatus.SUCCEEDED)
            self._persist_run(record)
            summary_path = write_summary_file(record, run_dir)
            record_memory_entry(
                self.memory_registry,
                record,
                run_dir=run_dir,
                summary_path=summary_path,
                result_paths=[],
            )
            return record

        try:
            record.touch(status=RunStatus.RUNNING)
            self._persist_run(record)
            if routed_mode == Mode.OPERATE:
                result = self._execute_operate(record, operate_action=operate_action)
            else:
                result = self._execute_build(record)
            record.touch(**result)
        except Exception as exc:  # pragma: no cover - defensive
            record.touch(status=RunStatus.FAILED, headline="Run failed", result_summary=str(exc))
        finally:
            self._persist_run(record)

        summary_path = write_summary_file(record, run_dir)
        artifact_paths = [record.diff_path] if record.diff_path else []
        artifact_paths.extend(record.artifacts)
        record_memory_entry(
            self.memory_registry,
            record,
            run_dir=run_dir,
            summary_path=summary_path,
            result_paths=[p for p in artifact_paths if p],
        )
        return record

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def list_runs(self, *, limit: int = 20) -> List[RunRecord]:
        runs: List[RunRecord] = []
        for manifest_path in sorted(self.runs_root.glob("*/run.json"), reverse=True):
            try:
                runs.append(self._load_manifest(manifest_path))
            except Exception:
                continue
        return runs[:limit]

    def get_run(self, run_id: str) -> RunRecord:
        manifest = self._manifest_path(run_id)
        if not manifest.exists():
            raise FileNotFoundError(f"Run {run_id} not found")
        return self._load_manifest(manifest)

    def update_status(
        self,
        run_id: str,
        *,
        status: RunStatus,
        headline: Optional[str] = None,
        result_summary: Optional[str] = None,
    ) -> RunRecord:
        record = self.get_run(run_id)
        record.touch(status=status, headline=headline, result_summary=result_summary)
        self._persist_run(record)
        return record

    def push_run(
        self,
        run_id: str,
        *,
        remote: str = "origin",
        branch: Optional[str] = None,
    ) -> Dict[str, object]:
        record = self.get_run(run_id)
        if record.mode != Mode.BUILD:
            raise ValueError("push_supported_for_build_runs_only")
        primary_machine = record.machines[0] if record.machines else "skylink"
        workspace = self._machine_workspace(primary_machine)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace {workspace} not found for machine {primary_machine}")

        logs: List[str] = []
        if branch is None:
            branch_proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=workspace,
            )
            logs.append(
                "".join(
                    [
                        "$ git rev-parse --abbrev-ref HEAD\n",
                        branch_proc.stdout,
                        branch_proc.stderr,
                    ]
                )
            )
            if branch_proc.returncode != 0:
                log_path = self._write_aux_log(self._run_dir(run_id), "push.log", logs)
                return {
                    "ok": False,
                    "error": "branch_resolution_failed",
                    "log_path": log_path,
                    "stdout": branch_proc.stdout,
                    "stderr": branch_proc.stderr,
                }
            branch = branch_proc.stdout.strip()

        push_cmd = ["git", "push", remote]
        if branch:
            push_cmd.append(branch)

        push_proc = subprocess.run(
            push_cmd,
            capture_output=True,
            text=True,
            cwd=workspace,
        )
        logs.append(
            "".join(
                [
                    f"$ {' '.join(push_cmd)}\n",
                    push_proc.stdout,
                    push_proc.stderr,
                ]
            )
        )
        log_path = self._write_aux_log(self._run_dir(run_id), "push.log", logs)
        return {
            "ok": push_proc.returncode == 0,
            "remote": remote,
            "branch": branch,
            "stdout": push_proc.stdout,
            "stderr": push_proc.stderr,
            "log_path": log_path,
            "returncode": push_proc.returncode,
        }

    def commit_run(
        self,
        run_id: str,
        *,
        message: Optional[str] = None,
        add_all: bool = True,
    ) -> Dict[str, object]:
        record = self.get_run(run_id)
        if record.mode != Mode.BUILD:
            raise ValueError("commit_supported_for_build_runs_only")
        primary_machine = record.machines[0] if record.machines else "skylink"
        workspace = self._machine_workspace(primary_machine)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace {workspace} not found for machine {primary_machine}")

        logs: List[str] = []
        if add_all:
            add_proc = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True,
                text=True,
                cwd=workspace,
            )
            logs.append(
                "".join(
                    [
                        "$ git add -A\n",
                        add_proc.stdout,
                        add_proc.stderr,
                    ]
                )
            )
        commit_message = message or f"Ace run {run_id}"
        commit_cmd = ["git", "commit", "-m", commit_message]
        commit_proc = subprocess.run(
            commit_cmd,
            capture_output=True,
            text=True,
            cwd=workspace,
        )
        logs.append(
            "".join(
                [
                    f"$ {' '.join(commit_cmd)}\n",
                    commit_proc.stdout,
                    commit_proc.stderr,
                ]
            )
        )
        log_path = self._write_aux_log(self._run_dir(run_id), "commit.log", logs)
        return {
            "ok": commit_proc.returncode == 0,
            "stdout": commit_proc.stdout,
            "stderr": commit_proc.stderr,
            "log_path": log_path,
            "returncode": commit_proc.returncode,
            "message": commit_message,
        }

    def get_run_file(self, run_id: str, rel_path: str) -> Path:
        if not rel_path:
            raise FileNotFoundError("Empty path")
        run_dir = self._run_dir(run_id).resolve()
        target = (PROJECT_ROOT / rel_path).resolve()
        if not target.exists():
            raise FileNotFoundError(rel_path)
        try:
            if not target.is_relative_to(run_dir):  # type: ignore[attr-defined]
                raise FileNotFoundError(rel_path)
        except AttributeError:
            from os.path import commonpath

            if commonpath([str(run_dir), str(target)]) != str(run_dir):
                raise FileNotFoundError(rel_path)
        return target

    def log_event_stream(
        self,
        run_id: str,
        *,
        poll_interval: float = 2.0,
        heartbeat_interval: float = 10.0,
    ) -> Iterator[str]:
        """Yield Server-Sent Event payloads for the run's log file."""

        last_payload: Optional[str] = None
        idle_time = 0.0
        while True:
            log_text = ""
            record: Optional[RunRecord]
            try:
                record = self.get_run(run_id)
            except FileNotFoundError:
                record = None

            log_path: Optional[Path] = None
            if record and record.log_path:
                try:
                    log_path = self.get_run_file(run_id, record.log_path)
                except FileNotFoundError:
                    log_path = None
            fallback = self._run_dir(run_id) / "codex.log"
            if not log_path and fallback.exists():
                log_path = fallback
            if log_path and log_path.exists():
                log_text = log_path.read_text(encoding="utf-8")

            if log_text != last_payload:
                event_data = json.dumps({"text": log_text})
                yield _format_sse_event("log", event_data)
                last_payload = log_text
                idle_time = 0.0
            else:
                idle_time += poll_interval
                if idle_time >= heartbeat_interval:
                    yield _format_sse_event("heartbeat", '"ping"')
                    idle_time = 0.0

            if record and record.status not in {RunStatus.PENDING, RunStatus.RUNNING}:
                if idle_time >= heartbeat_interval * 2:
                    yield _format_sse_event("heartbeat", '"complete"')
                    break

            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _execute_build(self, record: RunRecord) -> Dict[str, object]:
        brief = record.brief
        run_dir = self._run_dir(record.id)
        prompt_payload: Dict[str, object] = {
            "brief_text": brief.text,
            "mode": "build",
            "machines": record.machines,
            "tags": record.tags,
            "plan_preference": brief.plan_preview.value,
        }
        steering: Dict[str, str] = {}
        if brief.model:
            prompt_payload["model"] = brief.model
            steering["model_hint"] = brief.model
        if brief.reasoning:
            prompt_payload["reasoning"] = brief.reasoning
            steering["reasoning_hint"] = brief.reasoning
        if steering:
            prompt_payload["steering"] = steering
        if brief.notes:
            prompt_payload["notes"] = brief.notes

        prompt_path = run_dir / "prompt.json"
        prompt_path.write_text(json.dumps(prompt_payload, indent=2), encoding="utf-8")
        record.prompt_path = str(path_relative_to(PROJECT_ROOT, prompt_path))

        combined_output: List[str] = []
        plan_summary: Optional[str] = None
        plan_path: Optional[str] = None
        diff_path: Optional[str] = None
        artifact_set: set[str] = set()

        machines = record.machines or ["skylink"]
        for machine_name in machines:
            profile = self._safe_machine(machine_name)
            workspace_hint = self._machine_workspace(machine_name)
            output, rc = self._invoke_codex(profile, prompt_payload, run_dir)
            combined_output.append(f"=== MACHINE {machine_name} (exit={rc}) ===\n{output}\n")
            sections = _parse_markers(output)
            if sections.plan and not plan_summary:
                plan_summary = sections.plan.strip()
                plan_path = self._write_plan(run_dir, sections.plan)
                artifact_set.add(plan_path)
            if sections.diff and not diff_path:
                diff_path = self._write_diff(run_dir, sections.diff)
            if sections.artifacts:
                for artifact_entry in sections.artifacts:
                    mirrored = self._mirror_artifact(run_dir, artifact_entry, workspace_hint)
                    if mirrored:
                        artifact_set.add(mirrored)
            if rc != 0:
                log_path = self._write_log(run_dir, combined_output)
                record.log_path = log_path
                artifact_list = self._finalize_artifacts(run_dir, artifact_set, diff_path)
                record.diff_path = diff_path
                record.artifacts = artifact_list
                summary = sections.notes or "\n".join(output.splitlines()[:5])
                if plan_path:
                    record.plan_summary = plan_summary
                return {
                    "status": RunStatus.FAILED,
                    "headline": f"Codex exited {rc}",
                    "result_summary": summary,
                    "plan_summary": plan_summary,
                    "diff_path": diff_path,
                    "artifacts": artifact_list,
                    "log_path": log_path,
                }

        log_path = self._write_log(run_dir, combined_output)
        record.log_path = log_path

        if not diff_path:
            diff_path = self._capture_git_diff(run_dir, record)
        if diff_path:
            artifact_set.add(diff_path)

        artifact_list = self._finalize_artifacts(run_dir, artifact_set, diff_path)

        record.diff_path = diff_path
        record.artifacts = artifact_list
        if plan_path:
            record.plan_summary = plan_summary

        return {
            "status": RunStatus.SUCCEEDED,
            "headline": "Build run complete",
            "result_summary": _headline_from_output(combined_output),
            "plan_summary": plan_summary,
            "diff_path": diff_path,
            "artifacts": artifact_list,
            "log_path": log_path,
        }

    def _execute_operate(self, record: RunRecord, *, operate_action: Optional[str]) -> Dict[str, object]:
        run_dir = self._run_dir(record.id)
        commands: List[List[str]]
        command_types: List[str] = []
        if operate_action and operate_action in OPERATE_ACTIONS:
            command = OPERATE_ACTIONS[operate_action]
            commands = command.commands
            headline = command.title
            command_types.append(f"operate_action.{operate_action}")
        elif record.brief.text.strip() in OPERATE_ACTIONS:
            command = OPERATE_ACTIONS[record.brief.text.strip()]
            commands = command.commands
            headline = command.title
            command_types.append(f"operate_action.{record.brief.text.strip()}")
        else:
            commands = [["bash", "-lc", record.brief.text]]
            headline = f"Operate: {record.brief.text[:60]}"
            command_types.append("operate_action.freeform")

        def _command_type(cmd: List[str]) -> str:
            if not cmd:
                return "command.unknown"
            primary = Path(cmd[0]).name if cmd[0] else ""
            if primary in {"bash", "sh", "zsh"}:
                return "command.shell"
            if primary:
                return f"command.{primary}"
            return "command.unknown"

        command_types.extend(_command_type(cmd) for cmd in commands)

        policy_decision = evaluate_command_types(command_types)
        if policy_decision.is_escalate:
            message = (
                "Operate command blocked by policy: "
                f"{', '.join(policy_decision.command_types)}"
            )
            return {
                "status": RunStatus.FAILED,
                "headline": "Operate command blocked",
                "result_summary": message,
                "artifacts": [],
                "log_path": None,
            }

        if policy_decision.is_verify:
            plan_body = "\n".join(" ".join(cmd) for cmd in commands)
            plan_path = self._write_plan(run_dir, plan_body or "Commands pending verification")
            message = (
                "Operate command requires verification per policy: "
                f"{', '.join(policy_decision.command_types)}"
            )
            return {
                "status": RunStatus.CANCELLED,
                "headline": "Verification required",
                "result_summary": message,
                "plan_summary": "Commands pending verification",
                "diff_path": None,
                "artifacts": [plan_path],
                "log_path": None,
            }

        outputs: List[str] = []
        summary_line: Optional[str] = None
        machines = record.machines or ["skylink"]
        for machine_name in machines:
            profile = self._safe_machine(machine_name)
            machine_chunks: List[str] = []
            exit_code = 0
            for cmd in commands:
                body, rc = self._exec_on_machine(profile, cmd)
                machine_chunks.append(f"$ {_format_cmd(cmd)}\n{body}\n")
                if summary_line is None:
                    summary_line = _headline_from_output([body])
                if rc != 0:
                    exit_code = rc
                    break
            outputs.append(
                "\n".join(
                    [f"=== MACHINE {machine_name} (exit={exit_code}) ==="] + machine_chunks
                )
            )
            if exit_code != 0:
                log_path = self._write_log(run_dir, outputs)
                record.log_path = log_path
                return {
                    "status": RunStatus.FAILED,
                    "headline": "Operate command failed",
                    "result_summary": f"{machine_name}: command exited {exit_code}",
                    "artifacts": [],
                    "log_path": log_path,
                }

        log_path = self._write_log(run_dir, outputs)
        record.log_path = log_path
        return {
            "status": RunStatus.SUCCEEDED,
            "headline": headline,
            "result_summary": summary_line or _headline_from_output(outputs),
            "artifacts": [],
            "log_path": log_path,
        }

    def _invoke_codex(
        self,
        profile: MachineProfile,
        prompt_payload: Dict[str, object],
        run_dir: Path,
    ) -> Tuple[str, int]:
        prompt_json = json.dumps(prompt_payload)
        extra_flags: List[str] = []
        codex_hint = profile.codex_cmd.lower()
        if "codex" in codex_hint:
            model = prompt_payload.get("model")
            reasoning = prompt_payload.get("reasoning")
            if model:
                extra_flags.extend(["--model", str(model)])
            if reasoning:
                extra_flags.extend(["--reasoning", str(reasoning)])
        cmd, cwd = _codex_command(profile, extra_flags)
        try:
            result = subprocess.run(
                cmd,
                input=prompt_json,
                capture_output=True,
                text=True,
                cwd=str(cwd),
            )
            output = result.stdout + ("\n" + result.stderr if result.stderr else "")
            return output.strip(), result.returncode
        except FileNotFoundError:
            message = f"Codex command not found for machine {profile.name}: {profile.codex_cmd}"
            return message, 1

    def _exec_on_machine(self, profile: MachineProfile, cmd: List[str]) -> Tuple[str, int]:
        if profile.type == "ssh" and profile.host:
            workspace = profile.workspace or "."
            remote_cmd = f"cd {shlex.quote(workspace)} && { _format_cmd(cmd) }"
            argv = ["ssh", "-T", profile.host, "bash", "-lc", remote_cmd]
            proc = subprocess.run(argv, capture_output=True, text=True)
        elif profile.type == "docker" and profile.host:
            formatted = profile.host.format(cmd=_format_cmd(cmd), workspace=profile.workspace)
            argv = ["bash", "-lc", formatted]
            proc = subprocess.run(argv, capture_output=True, text=True)
        else:
            workspace_path = Path(profile.workspace).expanduser()
            if not workspace_path.exists():
                workspace_path = PROJECT_ROOT
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace_path)
        body = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        return body, proc.returncode

    def _mirror_artifact(
        self,
        run_dir: Path,
        artifact_entry: str,
        workspace_hint: Optional[Path],
    ) -> Optional[str]:
        artifact_entry = artifact_entry.strip()
        if not artifact_entry:
            return None

        raw_path = Path(artifact_entry)
        candidates: List[Path] = []
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            if workspace_hint and workspace_hint.exists():
                candidates.append(workspace_hint / raw_path)
            candidates.append(PROJECT_ROOT / raw_path)
            candidates.append(run_dir / raw_path)
        source = next((candidate for candidate in candidates if candidate.exists()), None)
        if not source:
            return None

        artifacts_root = run_dir / "artifacts"
        artifacts_root.mkdir(parents=True, exist_ok=True)
        if raw_path.is_absolute():
            relative_target = Path(source.name)
        else:
            relative_target = _sanitize_relative(raw_path) or Path(source.name)
        destination = artifacts_root / relative_target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = _ensure_unique_path(destination)

        try:
            if source.is_dir():
                try:
                    os.symlink(source, destination, target_is_directory=True)
                except OSError:
                    shutil.copytree(source, destination)
            else:
                try:
                    os.symlink(source, destination)
                except OSError:
                    shutil.copy2(source, destination)
        except Exception:
            return None
        return str(path_relative_to(PROJECT_ROOT, destination))

    def _finalize_artifacts(
        self,
        run_dir: Path,
        artifact_set: Iterable[str],
        diff_path: Optional[str],
    ) -> List[str]:
        cleaned = sorted({artifact for artifact in artifact_set if artifact})
        if diff_path:
            cleaned = sorted({*cleaned, diff_path})
        if cleaned:
            artifacts_path = run_dir / "artifacts.json"
            artifacts_path.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
        return cleaned

    def _write_log(self, run_dir: Path, chunks: Iterable[str]) -> str:
        log_path = run_dir / "codex.log"
        log_path.write_text("\n".join(chunks), encoding="utf-8")
        return str(path_relative_to(PROJECT_ROOT, log_path))

    def _write_diff(self, run_dir: Path, body: str) -> str:
        diff_path = run_dir / "diff.patch"
        diff_path.write_text(body, encoding="utf-8")
        return str(path_relative_to(PROJECT_ROOT, diff_path))

    def _write_plan(self, run_dir: Path, body: str) -> str:
        plan_path = run_dir / "plan.txt"
        plan_path.write_text(body.strip() + "\n", encoding="utf-8")
        return str(path_relative_to(PROJECT_ROOT, plan_path))

    def _write_aux_log(self, run_dir: Path, filename: str, chunks: Iterable[str]) -> str:
        log_path = run_dir / filename
        log_path.write_text("\n".join(chunks), encoding="utf-8")
        return str(path_relative_to(PROJECT_ROOT, log_path))

    def _capture_git_diff(self, run_dir: Path, record: RunRecord) -> Optional[str]:
        primary_machine = record.machines[0] if record.machines else "skylink"
        workspace = self._machine_workspace(primary_machine)
        try:
            proc = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                cwd=workspace,
            )
        except Exception:
            return None
        if proc.stdout.strip():
            return self._write_diff(run_dir, proc.stdout)
        return None

    def _persist_run(self, record: RunRecord) -> None:
        run_dir = self._run_dir(record.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._manifest_path(record.id)
        manifest.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

    def _load_manifest(self, path: Path) -> RunRecord:
        data = json.loads(path.read_text(encoding="utf-8"))
        brief = Brief.from_dict(data["brief"])
        record = RunRecord(
            id=data["id"],
            brief=brief,
            mode=Mode(data["mode"]),
            machines=data.get("machines", ["skylink"]),
            status=RunStatus(data.get("status", "pending")),
            created_at=data.get("created_at", now_ts()),
            updated_at=data.get("updated_at", now_ts()),
            headline=data.get("headline"),
            result_summary=data.get("result_summary"),
            plan_summary=data.get("plan_summary"),
            tags=data.get("tags", []),
            artifacts=data.get("artifacts", []),
            diff_path=data.get("diff_path"),
            prompt_path=data.get("prompt_path"),
            log_path=data.get("log_path"),
        )
        return record

    def _manifest_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run.json"

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def _machine_workspace(self, machine_name: str) -> Path:
        profile = self._safe_machine(machine_name)
        workspace = Path(profile.workspace).expanduser()
        if not workspace.exists():
            return PROJECT_ROOT
        return workspace

    def _safe_machine(self, machine_name: str) -> MachineProfile:
        try:
            return self.machine_registry.get(machine_name)
        except KeyError:
            return MachineProfile(name=machine_name)

    def _generate_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def _resolve_mode(self, brief: Brief, operate_action: Optional[str]) -> Mode:
        if brief.mode != Mode.AUTO:
            return brief.mode
        text = brief.text.lower()
        if operate_action:
            return Mode.OPERATE
        if any(keyword in text for keyword in ["status", "show", "list", "uptime", "cpu", "disk", "logs"]):
            return Mode.OPERATE
        if any(keyword in text for keyword in ["deploy", "install package", "restart"]):
            return Mode.OPERATE
        return Mode.BUILD

    @staticmethod
    def plan_outline(brief: Brief) -> List[str]:
        sentences = [s.strip() for s in brief.text.split(".") if s.strip()]
        if not sentences:
            sentences = [brief.text.strip()]
        outline = []
        for idx, sentence in enumerate(sentences, start=1):
            outline.append(f"Step {idx}: {sentence}")
        return outline


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _codex_command(profile: MachineProfile, extra_flags: Optional[List[str]] = None) -> Tuple[List[str], Path]:
    extra_flags = extra_flags or []
    tokens = shlex.split(profile.codex_cmd) + extra_flags
    workspace = profile.workspace or "."
    if profile.type == "ssh" and profile.host:
        remote_cmd = f"cd {shlex.quote(workspace)} && {shlex.join(tokens)}"
        return ["ssh", "-T", profile.host, "bash", "-lc", remote_cmd], PROJECT_ROOT
    if profile.type == "docker" and profile.host:
        formatted = profile.host.format(cmd=shlex.join(tokens), workspace=workspace)
        return ["bash", "-lc", formatted], PROJECT_ROOT
    workspace_path = Path(profile.workspace).expanduser()
    if not workspace_path.exists():
        workspace_path = PROJECT_ROOT
    return tokens, workspace_path


class _MarkerSections:
    def __init__(self, plan: Optional[str], diff: Optional[str], artifacts: List[str], notes: Optional[str]):
        self.plan = plan
        self.diff = diff
        self.artifacts = artifacts
        self.notes = notes


def _parse_markers(output: str) -> _MarkerSections:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("===") and stripped.endswith("==="):
            marker = stripped.strip("=").strip()
            current = marker
            sections[current] = []
            continue
        if current:
            sections[current].append(line)
    plan = "\n".join(sections.get("PLAN", [])).strip() if "PLAN" in sections else None
    diff = "\n".join(sections.get("DIFF", [])).strip() if "DIFF" in sections else None
    art_lines = [line.strip() for line in sections.get("ARTIFACTS", []) if line.strip()]
    notes = "\n".join(sections.get("NOTES", [])).strip() if "NOTES" in sections else None
    return _MarkerSections(plan=plan, diff=diff, artifacts=art_lines, notes=notes)


def _headline_from_output(chunks: Iterable[str]) -> str:
    for chunk in chunks:
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        for line in lines:
            if line and not line.startswith("==="):
                return line[:160]
    return ""


def _format_cmd(cmd: List[str]) -> str:
    return shlex.join(cmd)


def _sanitize_relative(path: Path) -> Path:
    parts = [part for part in path.parts if part not in ("..", ".")]
    return Path(*parts) if parts else Path()


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    base = path
    counter = 1
    while path.exists() and counter < 100:
        path = base.with_name(f"{base.stem}_{counter}{base.suffix}")
        counter += 1
    if path.exists():
        path = base.with_name(f"{base.stem}_{uuid.uuid4().hex[:6]}{base.suffix}")
    return path


def _format_sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
