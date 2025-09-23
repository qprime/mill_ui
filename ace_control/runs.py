from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from memories.framework import MemoryRegistry
from continuum.context_orchestrator import assemble_context, ContextSpec
from cortex.ai_router import get_router
from cortex.context_manager import load_persona_context
from .model_router import ModelRouter

from .ledger import record_memory_entry, write_summary_file
from .machines import MachineProfile, MachineRegistry
from .models import Brief, Mode, RunRecord, RunStatus, now_ts, path_relative_to
from .operate import OPERATE_ACTIONS, OperateCommand
from .operate_policy import evaluate_command_types
from .markers import ContextRequest, parse_markers
from .telemetry import record_run as telemetry_record_run, record_action as telemetry_record_action

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
        conversation: Optional[List[Dict[str, str]]] = None,
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
            record._conversation = conversation or []
            record.touch(status=RunStatus.RUNNING)
            self._persist_run(record)
            result = self._execute_chat(record)
            record.touch(**result)
            telemetry_data = getattr(record, "_telemetry", None)
            if telemetry_data:
                telemetry_record_run(
                    record,
                    telemetry_data.get("provider", "unknown"),
                    telemetry_data.get("exit_code"),
                    {k: v for k, v in telemetry_data.items() if k not in {"provider", "exit_code"}},
                )
                try:
                    delattr(record, "_telemetry")
                except AttributeError:
                    pass
            self._persist_run(record)
            summary_path = write_summary_file(record, run_dir)
            record_memory_entry(
                self.memory_registry,
                record,
                run_dir=run_dir,
                summary_path=summary_path,
                result_paths=[p for p in (record.artifacts or []) if p],
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
            telemetry_data = getattr(record, "_telemetry", None)
            if telemetry_data:
                telemetry_record_run(
                    record,
                    telemetry_data.get("provider", "unknown"),
                    telemetry_data.get("exit_code"),
                    {k: v for k, v in telemetry_data.items() if k not in {"provider", "exit_code"}},
                )
                try:
                    delattr(record, "_telemetry")
                except AttributeError:
                    pass
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
        telemetry_record_action(
            run_id,
            "push",
            push_proc.returncode == 0,
            {
                "remote": remote,
                "branch": branch,
                "returncode": push_proc.returncode,
            },
        )
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
        telemetry_record_action(
            run_id,
            "commit",
            commit_proc.returncode == 0,
            {
                "returncode": commit_proc.returncode,
                "message": commit_message,
            },
        )
        return {
            "ok": commit_proc.returncode == 0,
            "stdout": commit_proc.stdout,
            "stderr": commit_proc.stderr,
            "log_path": log_path,
            "returncode": commit_proc.returncode,
            "message": commit_message,
        }

    def stage_patch(
        self,
        run_id: str,
        *,
        check_only: bool = False,
    ) -> Dict[str, object]:
        record = self.get_run(run_id)
        if not record.diff_path:
            raise ValueError("patch_missing")
        primary_machine = record.machines[0] if record.machines else "skylink"
        workspace = self._machine_workspace(primary_machine)
        patch_path = (PROJECT_ROOT / record.diff_path).resolve()
        if not patch_path.exists():
            raise FileNotFoundError(str(patch_path))

        logs: List[str] = []

        def _run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace)
            logs.append(
                "".join(
                    [
                        f"$ {' '.join(cmd)}\n",
                        proc.stdout,
                        proc.stderr,
                    ]
                )
            )
            return proc

        rev_proc = _run(["git", "rev-parse", "HEAD"])
        if rev_proc.returncode != 0:
            log_path = self._write_aux_log(self._run_dir(run_id), "stage.log", logs)
            telemetry_record_action(
                run_id,
                "stage",
                False,
                {"check_only": check_only, "error": "rev_parse_failed"},
            )
            return {
                "ok": False,
                "error": "rev_parse_failed",
                "log_path": log_path,
                "returncode": rev_proc.returncode,
            }

        check_proc = _run(["git", "apply", "--check", str(patch_path)])
        if check_proc.returncode != 0:
            log_path = self._write_aux_log(self._run_dir(run_id), "stage.log", logs)
            telemetry_record_action(
                run_id,
                "stage",
                False,
                {"check_only": check_only, "error": "check_failed"},
            )
            return {
                "ok": False,
                "error": "check_failed",
                "log_path": log_path,
                "returncode": check_proc.returncode,
            }

        if not check_only:
            apply_proc = _run(["git", "apply", "--index", str(patch_path)])
            if apply_proc.returncode != 0:
                log_path = self._write_aux_log(self._run_dir(run_id), "stage.log", logs)
                telemetry_record_action(
                    run_id,
                    "stage",
                    False,
                    {"check_only": False, "error": "apply_failed"},
                )
                return {
                    "ok": False,
                    "error": "apply_failed",
                    "log_path": log_path,
                    "returncode": apply_proc.returncode,
                }

        status_proc = _run(["git", "status", "--short"])
        log_path = self._write_aux_log(self._run_dir(run_id), "stage.log", logs)

        if log_path not in record.artifacts:
            record.artifacts.append(log_path)
        self._persist_run(record)
        telemetry_record_action(
            run_id,
            "stage",
            True,
            {"check_only": check_only},
        )

        return {
            "ok": True,
            "log_path": log_path,
            "status_output": status_proc.stdout,
            "workspace": str(workspace),
        }

    def run_commands(
        self,
        run_id: str,
        *,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        record = self.get_run(run_id)
        if not record.commands:
            raise ValueError("no_commands")
        primary_machine = record.machines[0] if record.machines else "skylink"
        workspace = self._machine_workspace(primary_machine)

        logs: List[str] = []
        return_codes: List[int] = []

        def _run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace)
            logs.append(
                "".join(
                    [
                        f"$ {' '.join(cmd)}\n",
                        proc.stdout,
                        proc.stderr,
                    ]
                )
            )
            return proc

        rev_proc = _run(["git", "rev-parse", "HEAD"])
        if rev_proc.returncode != 0:
            log_path = self._write_aux_log(self._run_dir(run_id), "commands.log", logs)
            telemetry_record_action(
                run_id,
                "commands",
                False,
                {"dry_run": dry_run, "error": "rev_parse_failed"},
            )
            return {
                "ok": False,
                "error": "rev_parse_failed",
                "log_path": log_path,
                "returncode": rev_proc.returncode,
            }

        for command in record.commands:
            shell_cmd = command if not dry_run else f"echo DRY-RUN: {command}"
            proc = _run(["bash", "-lc", shell_cmd])
            return_codes.append(proc.returncode)
            if proc.returncode != 0 and not dry_run:
                break

        log_path = self._write_aux_log(self._run_dir(run_id), "commands.log", logs)
        if log_path not in record.artifacts:
            record.artifacts.append(log_path)
        self._persist_run(record)

        ok = all(code == 0 for code in return_codes) or dry_run
        telemetry_record_action(
            run_id,
            "commands",
            ok,
            {"dry_run": dry_run, "returncodes": return_codes},
        )
        return {
            "ok": ok,
            "log_path": log_path,
            "returncodes": return_codes,
            "dry_run": dry_run,
        }

    def run_tests(
        self,
        run_id: str,
        *,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        record = self.get_run(run_id)
        if not record.tests:
            raise ValueError("no_tests")
        primary_machine = record.machines[0] if record.machines else "skylink"
        workspace = self._machine_workspace(primary_machine)

        logs: List[str] = []
        return_codes: List[int] = []

        def _run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace)
            logs.append(
                "".join(
                    [
                        f"$ {' '.join(cmd)}\n",
                        proc.stdout,
                        proc.stderr,
                    ]
                )
            )
            return proc

        rev_proc = _run(["git", "rev-parse", "HEAD"])
        if rev_proc.returncode != 0:
            log_path = self._write_aux_log(self._run_dir(run_id), "tests.log", logs)
            telemetry_record_action(
                run_id,
                "tests",
                False,
                {"dry_run": dry_run, "error": "rev_parse_failed"},
            )
            return {
                "ok": False,
                "error": "rev_parse_failed",
                "log_path": log_path,
                "returncode": rev_proc.returncode,
            }

        for command in record.tests:
            shell_cmd = command if not dry_run else f"echo DRY-RUN: {command}"
            proc = _run(["bash", "-lc", shell_cmd])
            return_codes.append(proc.returncode)
            if proc.returncode != 0 and not dry_run:
                break

        log_path = self._write_aux_log(self._run_dir(run_id), "tests.log", logs)
        if log_path not in record.artifacts:
            record.artifacts.append(log_path)
        self._persist_run(record)

        ok = all(code == 0 for code in return_codes) or dry_run
        telemetry_record_action(
            run_id,
            "tests",
            ok,
            {"dry_run": dry_run, "returncodes": return_codes},
        )
        return {
            "ok": ok,
            "log_path": log_path,
            "returncodes": return_codes,
            "dry_run": dry_run,
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
    def _execute_chat(self, record: RunRecord) -> Dict[str, object]:
        brief = record.brief
        run_dir = self._run_dir(record.id)
        start_ts = time.time()

        base_conversation = []
        for entry in getattr(record, "_conversation", []) or []:
            role = entry.get("role")
            content = entry.get("content")
            if role in {"user", "assistant", "system"} and isinstance(content, str):
                base_conversation.append({"role": role, "content": content})

        router = ModelRouter()
        plans = router.plan_for("chat")
        provider_entries = [
            {
                "name": plan.name,
                "stream": plan.stream,
                "temperature": plan.temperature,
                "model": plan.model,
                "max_prompt_tokens": plan.max_prompt_tokens,
                "max_output_tokens": plan.max_output_tokens,
            }
            for plan in plans
        ]
        primary_plan = plans[0] if plans else None
        provider_name = primary_plan.name if primary_plan else "gpt_api"
        model_name = primary_plan.model if primary_plan and primary_plan.model else "gpt-5"

        prompt_payload: Dict[str, object] = {
            "brief_text": brief.text,
            "mode": "chat",
            "machines": record.machines,
            "tags": record.tags,
        }
        if provider_entries:
            prompt_payload["provider_plan"] = provider_entries
            prompt_payload["provider"] = provider_name

        context_artifact: Optional[str] = None
        context_bundle: Optional[Dict[str, object]] = None
        if brief.context and brief.context.include:
            spec = ContextSpec(
                include_code=brief.context.include_code,
                include_persona=brief.context.include_persona,
                scope=brief.context.scope,
                persona=brief.context.persona,
                persona_category=brief.context.persona_category,
                explicit_files=brief.context.explicit_files,
                focus_files=brief.context.focus_files,
                max_direct_files=brief.context.max_files,
            )
            context_bundle = assemble_context(str(PROJECT_ROOT), spec)
            context_path = run_dir / "context.json"
            context_path.write_text(json.dumps(context_bundle, indent=2), encoding="utf-8")
            context_artifact = str(path_relative_to(PROJECT_ROOT, context_path))
            prompt_payload["context_bundle"] = context_bundle

        prompt_path = run_dir / "prompt.json"
        prompt_path.write_text(json.dumps(prompt_payload, indent=2), encoding="utf-8")
        record.prompt_path = str(path_relative_to(PROJECT_ROOT, prompt_path))

        log_path = run_dir / "chat.log"
        log_path.write_text("", encoding="utf-8")
        record.log_path = str(path_relative_to(PROJECT_ROOT, log_path))

        persona_prompt: Optional[str] = None
        context_opts = getattr(brief, "context", None)
        if context_opts and getattr(context_opts, "include_persona", True) and context_opts.persona:
            try:
                persona_prompt = load_persona_context(context_opts.persona, context_opts.persona_category or "")
            except Exception:
                persona_prompt = None
        if not persona_prompt:
            persona_prompt = (
                "You are ACE, a helpful assistant for the cliff_ai project. Respond conversationally and be concise."
            )

        conversation_messages = list(base_conversation)
        if not conversation_messages or conversation_messages[-1].get("role") != "user" or conversation_messages[-1].get("content") != brief.text:
            conversation_messages.append({"role": "user", "content": brief.text})

        messages = [{"role": "system", "content": persona_prompt}]

        if context_bundle:
            manifest = context_bundle.get("context", {}) if isinstance(context_bundle, dict) else {}
            direct_files = manifest.get("direct_files", []) if isinstance(manifest, dict) else []
            docs_map = manifest.get("docs", {}) if isinstance(manifest, dict) else {}
            tests_map = manifest.get("tests", {}) if isinstance(manifest, dict) else {}
            context_chunks: List[str] = []
            for path in direct_files[:5]:
                file_path = (PROJECT_ROOT / path).resolve()
                if file_path.exists() and file_path.is_file():
                    try:
                        text = file_path.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    snippet = text.strip()
                    if len(snippet) > 2000:
                        snippet = snippet[:2000] + "\n..."
                    context_chunks.append(f"# {path}\n{snippet}")
            summary_lines: List[str] = []
            if context_chunks:
                summary_lines.append("\n\n".join(context_chunks))
            if docs_map:
                summary_lines.append(
                    "Related docs: " + ", ".join(sorted({doc for docs in docs_map.values() for doc in docs}))
                )
            if tests_map:
                summary_lines.append(
                    "Related tests: " + ", ".join(sorted({test for tests in tests_map.values() for test in tests}))
                )
            if summary_lines:
                messages.append({"role": "system", "content": "Project context:\n" + "\n\n".join(summary_lines)})

        messages.extend(conversation_messages)

        router_client = get_router()
        status = RunStatus.SUCCEEDED
        response_text = ""
        error_message: Optional[str] = None
        try:
            response_text = router_client.chat(messages, model=model_name)
        except Exception as exc:  # pragma: no cover - provider failure
            status = RunStatus.FAILED
            error_message = str(exc)
            response_text = f"[error] {error_message}"

        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("USER:\n")
            handle.write(brief.text + "\n\n")
            handle.write("ASSISTANT:\n")
            handle.write(response_text + "\n")

        headline = response_text.splitlines()[0][:160] if response_text else "Chat response"
        conversation_with_reply = conversation_messages + [{"role": "assistant", "content": response_text}]

        conversation_path = run_dir / "conversation.json"
        conversation_path.write_text(json.dumps(conversation_with_reply, indent=2), encoding="utf-8")
        record._conversation = conversation_with_reply

        artifacts = [record.log_path, str(path_relative_to(PROJECT_ROOT, conversation_path))]
        if context_artifact:
            artifacts.append(context_artifact)

        record._telemetry = {
            "provider": provider_name,
            "exit_code": 0 if status == RunStatus.SUCCEEDED else None,
            "duration_ms": int((time.time() - start_ts) * 1000),
            "mode": "chat",
            "model": model_name,
            "error": error_message,
            "conversation_turns": len(conversation_with_reply),
        }

        return {
            "status": status,
            "headline": headline,
            "result_summary": response_text,
            "artifacts": artifacts,
            "log_path": record.log_path,
        }

    def _execute_build(self, record: RunRecord) -> Dict[str, object]:
        brief = record.brief
        start_ts = time.time()
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

        # Optionally assemble and inject project context
        context_artifact: Optional[str] = None
        aggregated_context_docs: List[Dict[str, object]] = []
        delivered_request_meta: List[Dict[str, object]] = []
        if brief.context and brief.context.include:
            spec = ContextSpec(
                include_code=brief.context.include_code,
                include_persona=brief.context.include_persona,
                scope=brief.context.scope,
                persona=brief.context.persona,
                persona_category=brief.context.persona_category,
                explicit_files=brief.context.explicit_files,
                focus_files=brief.context.focus_files,
                max_direct_files=brief.context.max_files,
            )
            bundle = assemble_context(str(PROJECT_ROOT), spec)
            context_path = run_dir / "context.json"
            context_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            context_artifact = str(path_relative_to(PROJECT_ROOT, context_path))
            prompt_payload["context_bundle"] = {
                "spec": bundle.get("spec"),
                "budget": bundle.get("budget"),
                "context": bundle.get("context"),
                "change_set": bundle.get("change_set"),
                "cache_manifest": bundle.get("cache_manifest"),
            }
            context_note_lines = [
                "[context] persona: {}".format((bundle.get("spec") or {}).get("persona")) if bundle.get("spec") else "[context] persona:",
                f"[context] direct_files: {len((bundle.get('context') or {}).get('direct_files', []))}",
                f"[context] neighbors: {len((bundle.get('context') or {}).get('neighbor_files', []))}",
            ]
            prompt_payload["brief_text"] = "\n".join(context_note_lines + ["", brief.text])

        # Routing plan (Codex CLI vs GPT API)
        router = ModelRouter()
        task_type = "build_large" if record.mode == Mode.BUILD else "analyze"
        plans = router.plan_for(task_type)
        primary_provider = plans[0].name if plans else "unknown"
        if plans:
            prompt_payload["provider_plan"] = [
                {
                    "name": plan.name,
                    "stream": plan.stream,
                    "temperature": plan.temperature,
                    "model": plan.model,
                    "max_prompt_tokens": plan.max_prompt_tokens,
                    "max_output_tokens": plan.max_output_tokens,
                }
                for plan in plans
            ]
            prompt_payload["provider"] = plans[0].name

        prompt_path = run_dir / "prompt.json"
        prompt_path.write_text(json.dumps(prompt_payload, indent=2), encoding="utf-8")
        record.prompt_path = str(path_relative_to(PROJECT_ROOT, prompt_path))
        base_payload = deepcopy(prompt_payload)

        combined_output: List[str] = []
        plan_summary: Optional[str] = None
        plan_path: Optional[str] = None
        diff_path: Optional[str] = None
        commands_path: Optional[str] = None
        tests_path: Optional[str] = None
        notes_text: Optional[str] = None
        artifact_set: set[str] = set()
        if context_artifact:
            artifact_set.add(context_artifact)

        commands_list: List[str] = []
        tests_list: List[str] = []
        unresolved_requests: List[ContextRequest] = []
        patch_text: Optional[str] = None

        machines = record.machines or ["skylink"]
        exit_code = 0
        for machine_name in machines:
            profile = self._safe_machine(machine_name)
            workspace_hint = self._machine_workspace(machine_name)
            local_payload = deepcopy(base_payload)
            local_context_docs = deepcopy(aggregated_context_docs)
            attempt = 0
            sections = None

            while attempt < 3:
                attempt += 1
                if local_context_docs:
                    local_payload["context_documents"] = local_context_docs
                output, exit_code = self._invoke_codex(profile, local_payload, run_dir)
                combined_output.append(f"=== MACHINE {machine_name} (exit={exit_code}) ===\n{output}\n")
                sections = parse_markers(output)

                if sections.context_requests and attempt < 3:
                    docs, delivered = self._fulfill_context_requests(
                        sections.context_requests,
                        workspace_hint,
                        run_dir,
                    )
                    if docs:
                        aggregated_context_docs = self._merge_context_documents(aggregated_context_docs, docs)
                        local_context_docs = deepcopy(aggregated_context_docs)
                        delivered_request_meta.extend(delivered)
                        continue
                break

            if sections is None:
                sections = parse_markers("")

            if sections.context_requests:
                unresolved_requests.extend(sections.context_requests)

            if sections.plan and not plan_summary:
                plan_summary = sections.plan.strip()
                plan_path = self._write_plan(run_dir, sections.plan)
                artifact_set.add(plan_path)
            if sections.patch and not patch_text:
                patch_text = sections.patch
                diff_path = self._write_diff(run_dir, patch_text)
            if sections.commands:
                if not commands_list:
                    commands_list = list(sections.commands)
                else:
                    for cmd in sections.commands:
                        if cmd not in commands_list:
                            commands_list.append(cmd)
            if sections.tests:
                if not tests_list:
                    tests_list = list(sections.tests)
                else:
                    for test_cmd in sections.tests:
                        if test_cmd not in tests_list:
                            tests_list.append(test_cmd)
            if sections.artifacts:
                for artifact_entry in sections.artifacts:
                    mirrored = self._mirror_artifact(run_dir, artifact_entry, workspace_hint)
                    if mirrored:
                        artifact_set.add(mirrored)
            if sections.notes and not notes_text:
                notes_text = sections.notes

            if exit_code != 0:
                break

        if aggregated_context_docs:
            docs_path = run_dir / "context_documents.json"
            docs_path.write_text(json.dumps(aggregated_context_docs, indent=2), encoding="utf-8")
            artifact_set.add(str(path_relative_to(PROJECT_ROOT, docs_path)))

        record.commands = commands_list
        record.tests = tests_list
        record.notes = notes_text

        context_meta_entries: List[Dict[str, object]] = delivered_request_meta.copy()
        context_meta_entries.extend(
            {
                "path": req.path,
                "start": req.start,
                "end": req.end,
                "summary": req.summary,
                "status": "pending",
            }
            for req in unresolved_requests
        )
        record.context_requests = context_meta_entries

        if commands_list:
            commands_path = self._write_text_artifact(run_dir, "commands.txt", "\n".join(commands_list) + "\n")
            artifact_set.add(commands_path)
        if tests_list:
            tests_path = self._write_text_artifact(run_dir, "tests.txt", "\n".join(tests_list) + "\n")
            artifact_set.add(tests_path)
        if notes_text:
            notes_path = self._write_text_artifact(run_dir, "notes.txt", notes_text + "\n")
            artifact_set.add(notes_path)

        log_path = self._write_log(run_dir, combined_output)
        record.log_path = log_path

        if exit_code != 0:
            record._telemetry = {
                "provider": primary_provider,
                "exit_code": exit_code,
                "duration_ms": int((time.time() - start_ts) * 1000),
                "context_documents": len(aggregated_context_docs),
                "pending_requests": len(unresolved_requests),
            }
            artifact_list = self._finalize_artifacts(run_dir, artifact_set, diff_path)
            record.diff_path = diff_path
            record.artifacts = artifact_list
            summary = notes_text or _headline_from_output(combined_output)
            if plan_path:
                record.plan_summary = plan_summary
            return {
                "status": RunStatus.FAILED,
                "headline": f"Codex exited {exit_code}",
                "result_summary": summary,
                "plan_summary": plan_summary,
                "diff_path": diff_path,
                "artifacts": artifact_list,
                "log_path": log_path,
            }

        if unresolved_requests:
            record._telemetry = {
                "provider": primary_provider,
                "exit_code": exit_code,
                "duration_ms": int((time.time() - start_ts) * 1000),
                "context_documents": len(aggregated_context_docs),
                "pending_requests": len(unresolved_requests),
            }
            artifact_list = self._finalize_artifacts(run_dir, artifact_set, diff_path)
            record.diff_path = diff_path
            record.artifacts = artifact_list
            return {
                "status": RunStatus.CANCELLED,
                "headline": "Context required",
                "result_summary": "Pending context requests",
                "plan_summary": plan_summary,
                "diff_path": diff_path,
                "artifacts": artifact_list,
                "log_path": log_path,
            }

        if not diff_path and patch_text is None:
            diff_path = self._capture_git_diff(run_dir, record)
            if diff_path:
                artifact_set.add(diff_path)

        artifact_list = self._finalize_artifacts(run_dir, artifact_set, diff_path)

        record.diff_path = diff_path
        record.artifacts = artifact_list
        if plan_path:
            record.plan_summary = plan_summary

        record._telemetry = {
            "provider": primary_provider,
            "exit_code": exit_code,
            "duration_ms": int((time.time() - start_ts) * 1000),
            "context_documents": len(aggregated_context_docs),
            "pending_requests": len(unresolved_requests),
        }
        return {
            "status": RunStatus.SUCCEEDED,
            "headline": "Build run complete",
            "result_summary": notes_text or _headline_from_output(combined_output),
            "plan_summary": plan_summary,
            "diff_path": diff_path,
            "artifacts": artifact_list,
            "log_path": log_path,
        }

    def _execute_operate(self, record: RunRecord, *, operate_action: Optional[str]) -> Dict[str, object]:
        run_dir = self._run_dir(record.id)
        start_ts = time.time()
        provider_name = "operate"
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
            record._telemetry = {
                "provider": provider_name,
                "exit_code": None,
                "duration_ms": int((time.time() - start_ts) * 1000),
                "operate_action": operate_action,
                "command_types": command_types,
                "policy": "escalate",
            }
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
            record._telemetry = {
                "provider": provider_name,
                "exit_code": None,
                "duration_ms": int((time.time() - start_ts) * 1000),
                "operate_action": operate_action,
                "command_types": command_types,
                "policy": "verify",
            }
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
                record._telemetry = {
                    "provider": provider_name,
                    "exit_code": exit_code,
                    "duration_ms": int((time.time() - start_ts) * 1000),
                    "operate_action": operate_action,
                    "command_count": len(commands),
                    "command_types": command_types,
                }
                return {
                    "status": RunStatus.FAILED,
                    "headline": "Operate command failed",
                    "result_summary": f"{machine_name}: command exited {exit_code}",
                    "artifacts": [],
                    "log_path": log_path,
                }

        log_path = self._write_log(run_dir, outputs)
        record.log_path = log_path
        record._telemetry = {
            "provider": provider_name,
            "exit_code": 0,
            "duration_ms": int((time.time() - start_ts) * 1000),
            "operate_action": operate_action,
            "command_count": len(commands),
            "command_types": command_types,
        }
        return {
            "status": RunStatus.SUCCEEDED,
            "headline": headline,
            "result_summary": summary_line or _headline_from_output(outputs),
            "artifacts": [],
            "log_path": log_path,
        }

    def _merge_context_documents(
        self,
        existing: List[Dict[str, object]],
        new_docs: List[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        merged = list(existing)
        seen = {
            (
                doc.get("path"),
                doc.get("start"),
                doc.get("end"),
                bool(doc.get("summary")),
            )
            for doc in merged
        }
        for doc in new_docs:
            key = (
                doc.get("path"),
                doc.get("start"),
                doc.get("end"),
                bool(doc.get("summary")),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(doc)
        return merged

    def _fulfill_context_requests(
        self,
        requests: List[ContextRequest],
        workspace_hint: Path,
        run_dir: Path,
    ) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
        documents: List[Dict[str, object]] = []
        delivered: List[Dict[str, object]] = []
        for request in requests:
            path_token = request.path.strip()
            if not path_token:
                continue
            candidates: List[Path] = []
            candidate_path = Path(path_token)
            if candidate_path.is_absolute():
                candidates.append(candidate_path)
            else:
                if workspace_hint and (workspace_hint / candidate_path).exists():
                    candidates.append(workspace_hint / candidate_path)
                candidates.append(PROJECT_ROOT / candidate_path)
            source = next((candidate for candidate in candidates if candidate.exists()), None)
            if not source or not source.is_file():
                continue

            try:
                text = source.read_text(encoding="utf-8")
            except OSError:
                continue

            lines = text.splitlines()
            start = request.start or 1
            end = request.end or len(lines)
            if start < 1:
                start = 1
            if end < start:
                end = start
            max_lines = 200 if request.summary else 400
            slice_lines = lines[start - 1 : min(end, start - 1 + max_lines)]
            snippet = "\n".join(slice_lines)
            if request.summary and len(slice_lines) == max_lines and (end - start) > max_lines:
                snippet += "\n..."

            doc_entry = {
                "path": path_token,
                "start": request.start,
                "end": request.end,
                "summary": request.summary,
                "content": snippet,
            }
            documents.append(doc_entry)
            delivered.append(
                {
                    "path": path_token,
                    "start": request.start,
                    "end": request.end,
                    "summary": request.summary,
                    "status": "delivered",
                    "chars": len(snippet),
                }
            )
        return documents, delivered

    def _write_text_artifact(self, run_dir: Path, filename: str, content: str) -> str:
        target = run_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _ensure_unique_path(target)
        target.write_text(content, encoding="utf-8")
        return str(path_relative_to(PROJECT_ROOT, target))

    def _invoke_codex(
        self,
        profile: MachineProfile,
        prompt_payload: Dict[str, object],
        run_dir: Path,
    ) -> Tuple[str, int]:
        prompt_json = json.dumps(prompt_payload)
        extra_flags: List[str] = []
        codex_hint = profile.codex_cmd.lower()
        using_proto = "proto" in codex_hint
        if "codex" in codex_hint:
            model = prompt_payload.get("model")
            reasoning = prompt_payload.get("reasoning")
            if model:
                extra_flags.extend([
                    "-m" if using_proto else "--model",
                    str(model),
                ])
            if reasoning:
                if using_proto:
                    extra_flags.extend([
                        "-c",
                        f"model_reasoning_effort={json.dumps(str(reasoning))}",
                    ])
                else:
                    extra_flags.extend(["--reasoning", str(reasoning)])
        cmd, cwd = _codex_command(profile, extra_flags)

        log_path = run_dir / "codex.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(cwd),
                bufsize=1,
            )
        except FileNotFoundError:
            message = f"Codex command not found for machine {profile.name}: {profile.codex_cmd}"
            return message, 1

        try:
            if proc.stdin:
                proc.stdin.write(prompt_json)
                proc.stdin.flush()
                proc.stdin.close()
        except BrokenPipeError:
            pass

        output_chunks: List[str] = []
        try:
            with log_path.open("a", encoding="utf-8") as log_handle:
                if proc.stdout:
                    for line in proc.stdout:
                        output_chunks.append(line)
                        log_handle.write(line)
                        log_handle.flush()
                if proc.stderr:
                    stderr_text = proc.stderr.read()
                    if stderr_text:
                        output_chunks.append(stderr_text)
                        log_handle.write(stderr_text)
                        log_handle.flush()
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        returncode = proc.wait()
        output = "".join(output_chunks).strip()
        return output, returncode

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
            commands=data.get("commands", []),
            tests=data.get("tests", []),
            notes=data.get("notes"),
            context_requests=data.get("context_requests", []),
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
