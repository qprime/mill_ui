from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from memories.framework import MemoryRegistry

from .ledger import record_memory_entry, write_summary_file
from .machines import MachineRegistry, MachineProfile
from .models import Brief, Mode, RunRecord, RunStatus, now_ts, path_relative_to
from .operate import OPERATE_ACTIONS, OperateCommand

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _execute_build(self, record: RunRecord) -> Dict[str, object]:
        brief = record.brief
        run_dir = self._run_dir(record.id)
        prompt_payload = {
            "brief_text": brief.text,
            "mode": "build",
            "machines": record.machines,
            "tags": record.tags,
            "plan_preference": brief.plan_preview.value,
        }
        if brief.model:
            prompt_payload["model"] = brief.model
        if brief.reasoning:
            prompt_payload["reasoning"] = brief.reasoning
        if brief.notes:
            prompt_payload["notes"] = brief.notes

        prompt_path = run_dir / "prompt.json"
        prompt_path.write_text(json.dumps(prompt_payload, indent=2), encoding="utf-8")
        record.prompt_path = str(path_relative_to(PROJECT_ROOT, prompt_path))

        combined_output: List[str] = []
        plan_summary: Optional[str] = None
        plan_path: Optional[str] = None
        diff_path: Optional[str] = None
        artifacts: List[str] = []

        for machine_name in record.machines:
            profile = self._safe_machine(machine_name)
            output, rc = self._invoke_codex(profile, prompt_payload, run_dir)
            combined_output.append(f"=== MACHINE {machine_name} (exit={rc}) ===\n{output}\n")
            sections = _parse_markers(output)
            if sections.plan and not plan_summary:
                plan_summary = sections.plan.strip()
                plan_path = self._write_plan(run_dir, sections.plan)
                artifacts.append(plan_path)
            if sections.diff and not diff_path:
                diff_path = self._write_diff(run_dir, sections.diff)
            if sections.artifacts:
                artifacts.extend(sections.artifacts)
            if rc != 0:
                log_path = self._write_log(run_dir, combined_output)
                record.log_path = log_path
                artifacts = sorted(set(artifacts))
                record.diff_path = diff_path
                record.artifacts = artifacts
                summary = sections.notes or "\n".join(output.splitlines()[:5])
                if plan_path:
                    record.plan_summary = plan_summary
                return {
                    "status": RunStatus.FAILED,
                    "headline": f"Codex exited {rc}",
                    "result_summary": summary,
                    "plan_summary": plan_summary,
                    "diff_path": diff_path,
                    "artifacts": artifacts,
                    "log_path": log_path,
                }

        log_path = self._write_log(run_dir, combined_output)
        record.log_path = log_path

        if not diff_path:
            diff_path = self._capture_git_diff(run_dir, record)
            if diff_path:
                artifacts.append(diff_path)

        artifacts = sorted(set(artifacts))

        if artifacts:
            artifacts_path = run_dir / "artifacts.json"
            artifacts_path.write_text(json.dumps(artifacts, indent=2), encoding="utf-8")

        record.diff_path = diff_path
        record.artifacts = artifacts
        if plan_path:
            record.plan_summary = plan_summary

        return {
            "status": RunStatus.SUCCEEDED,
            "headline": "Build run complete",
            "result_summary": _headline_from_output(combined_output),
            "plan_summary": plan_summary,
            "diff_path": diff_path,
            "artifacts": artifacts,
            "log_path": log_path,
        }

    def _execute_operate(self, record: RunRecord, *, operate_action: Optional[str]) -> Dict[str, object]:
        run_dir = self._run_dir(record.id)
        commands: List[List[str]]
        if operate_action and operate_action in OPERATE_ACTIONS:
            command = OPERATE_ACTIONS[operate_action]
            commands = command.commands
            headline = command.title
        elif record.brief.text.strip() in OPERATE_ACTIONS:
            command = OPERATE_ACTIONS[record.brief.text.strip()]
            commands = command.commands
            headline = command.title
        else:
            commands = [["bash", "-lc", record.brief.text]]
            headline = f"Operate: {record.brief.text[:60]}"

        outputs: List[str] = []
        for cmd in commands:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self._machine_workspace(record.machines[0]),
                )
                body = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
                outputs.append(f"$ {' '.join(cmd)}\n{body}\n")
                if proc.returncode != 0:
                    raise RuntimeError(f"Command {' '.join(cmd)} exited {proc.returncode}")
            except Exception as exc:
                log_path = self._write_log(run_dir, outputs)
                record.log_path = log_path
                return {
                    "status": RunStatus.FAILED,
                    "headline": "Operate command failed",
                    "result_summary": str(exc),
                    "artifacts": [],
                    "log_path": log_path,
                }
        log_path = self._write_log(run_dir, outputs)
        record.log_path = log_path
        return {
            "status": RunStatus.SUCCEEDED,
            "headline": headline,
            "result_summary": _headline_from_output(outputs),
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
        cmd, cwd = _codex_command(profile)
        try:
            result = subprocess.run(
                cmd,
                input=prompt_json,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                shell=isinstance(cmd, str),
            )
            output = result.stdout + ("\n" + result.stderr if result.stderr else "")
            return output.strip(), result.returncode
        except FileNotFoundError:
            message = f"Codex command not found for machine {profile.name}: {profile.codex_cmd}"
            return message, 1

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
        # very light heuristic
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


def _codex_command(profile: MachineProfile) -> Tuple[object, Path]:
    workspace = Path(profile.workspace).expanduser()
    if profile.type == "ssh" and profile.host:
        remote_cmd = f"cd {profile.workspace} && {profile.codex_cmd}"
        cmd = f"ssh {profile.host} '{remote_cmd}'"
        return cmd, PROJECT_ROOT
    if profile.type == "docker" and profile.host:
        docker_cmd = profile.host.format(cmd=profile.codex_cmd, workspace=profile.workspace)
        return docker_cmd, PROJECT_ROOT
    return profile.codex_cmd, (workspace if workspace.exists() else PROJECT_ROOT)


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
