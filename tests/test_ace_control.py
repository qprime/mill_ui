import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    import flask  # noqa: F401
    FLASK_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - dependency optional in tests
    FLASK_AVAILABLE = False

from ace_control import Brief, MachineProfile, MachineRegistry, RunManager, RunStatus
from memories.framework import MemoryRegistry


class AceControlRunManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        workspace = base / "workspace"
        workspace.mkdir()

        machines_path = base / "machines.json"
        registry = MachineRegistry(path=machines_path)
        registry.replace_all([MachineProfile(name="skylink", workspace=str(workspace))])

        memory_registry = MemoryRegistry(root=base / "memories")
        self.manager = RunManager(
            runs_root=base / "runs",
            machine_registry=registry,
            memory_registry=memory_registry,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _start_build_run(self, output: str = "", rc: int = 0) -> object:
        with patch.object(self.manager, "_invoke_codex", return_value=(output, rc)):
            with patch.object(self.manager, "_capture_git_diff", return_value=None):
                brief = Brief.from_dict({
                    "mode": "build",
                    "text": "Test build",
                    "machines": ["skylink"],
                })
                return self.manager.start_run(brief)

    def test_build_run_writes_plan_and_artifacts(self) -> None:
        output = (
            "===PLAN===\nPlan step\n"
            "===PATCH===\n--- a/file\n+++ b/file\n+added\n"
            "===ARTIFACTS===\nartifacts/output.log\n"
            "===NOTES===\nAll good\n"
        )
        record = self._start_build_run(output=output)

        run_dir = self.manager._run_dir(record.id)
        self.assertTrue((run_dir / "plan.txt").exists())
        self.assertTrue((run_dir / "diff.patch").exists())
        self.assertTrue((run_dir / "codex.log").exists())
        self.assertTrue((run_dir / "summary.json").exists())
        self.assertTrue((run_dir / "artifacts.json").exists())
        self.assertEqual(record.plan_summary.strip(), "Plan step")
        self.assertIsNotNone(record.diff_path)
        self.assertTrue(any(Path(path).name == "plan.txt" for path in record.artifacts))

        index_file = self.manager.memory_registry.index_path
        self.assertTrue(index_file.exists())
        ledger_lines = index_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertTrue(any(record.id in line for line in ledger_lines))

    def test_push_run_executes_git_commands(self) -> None:
        record = self._start_build_run(output="")

        calls = []

        class DummyProc:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_run(cmd, capture_output=False, text=False, cwd=None, **kwargs):
            calls.append((cmd, cwd))
            if isinstance(cmd, list) and cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return DummyProc(stdout="main\n")
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return DummyProc(stdout="pushed\n", returncode=0)
            return DummyProc()

        with patch("ace_control.runs.subprocess.run", side_effect=fake_run):
            result = self.manager.push_run(record.id)

        self.assertTrue(result["ok"])
        self.assertEqual(result["branch"], "main")
        self.assertTrue(Path(result["log_path"]).exists())
        self.assertTrue(any(isinstance(cmd, list) and cmd[:2] == ["git", "push"] for cmd, _ in calls))

    def test_operate_run_failure_returns_error(self) -> None:
        class DummyProc:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def failing_run(cmd, capture_output=False, text=False, cwd=None, **kwargs):
            return DummyProc(stdout="ignored", stderr="boom", returncode=1)

        with patch("ace_control.runs.subprocess.run", side_effect=failing_run):
            brief = Brief.from_dict({
                "mode": "operate",
                "text": "echo 'hi'",
                "machines": ["skylink"],
            })
            record = self.manager.start_run(brief)

        self.assertEqual(record.status, RunStatus.FAILED)
        self.assertIn("exited 1", record.result_summary or "")
        self.assertIsNotNone(record.log_path)
        self.assertTrue(Path(record.log_path).exists())

    def test_ideate_chat_run_invokes_router(self) -> None:
        class DummyRouter:
            def __init__(self):
                self.called = False

            def chat(self, messages, model):
                self.called = True
                self.messages = messages
                self.model = model
                return "Hello there!"

        dummy_router = DummyRouter()
        plan = SimpleNamespace(
            name="gpt_api",
            stream=True,
            temperature=0.2,
            model="gpt-5",
            max_prompt_tokens=500000,
            max_output_tokens=16000,
        )
        brief = Brief.from_dict({
            "mode": "ideate",
            "text": "Hello!",
            "machines": ["skylink"],
            "context": {"include": False},
        })
        with patch("ace_control.runs.ModelRouter.plan_for", return_value=[plan]):
            with patch("ace_control.runs.get_router", return_value=dummy_router):
                record = self.manager.start_run(brief)

        self.assertEqual(record.status, RunStatus.SUCCEEDED)
        self.assertIn("Hello there!", record.result_summary or "")
        self.assertTrue(dummy_router.called)
        self.assertEqual(dummy_router.messages[1]["content"], "Hello!")

    def test_build_run_handles_context_requests(self) -> None:
        workspace = Path(self.manager.machine_registry.get("skylink").workspace)
        target_file = workspace / "sample.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("""def hello():\n    return 'hi'\n""", encoding="utf-8")

        first_output = """===CONTEXT_REQUESTS===\nREAD sample.py lines=1-2\n"""
        second_output = (
            "===PLAN===\nPlan after context\n"
            "===PATCH===\n--- a/sample.py\n+++ b/sample.py\n@@\n-def hello():\n-    return 'hi'\n+def hello():\n+    return 'hello'\n"
        )

        with patch.object(
            self.manager,
            "_invoke_codex",
            side_effect=[(first_output, 0), (second_output, 0)],
        ):
            with patch.object(self.manager, "_capture_git_diff", return_value=None):
                brief = Brief.from_dict({
                    "mode": "build",
                    "text": "Update greeting",
                    "machines": ["skylink"],
                    "context": {"include": True},
                })
                record = self.manager.start_run(brief)

        run_dir = self.manager._run_dir(record.id)
        context_docs = run_dir / "context_documents.json"
        self.assertTrue(context_docs.exists())
        delivered = [entry for entry in record.context_requests if entry.get("status") == "delivered"]
        pending = [entry for entry in record.context_requests if entry.get("status") == "pending"]
        self.assertTrue(delivered)
        self.assertFalse(pending)
        self.assertEqual(record.status, RunStatus.SUCCEEDED)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed")
class AceControlAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        workspace = base / "workspace"
        workspace.mkdir()

        machines_path = base / "machines.json"
        registry = MachineRegistry(path=machines_path)
        registry.replace_all([MachineProfile(name="skylink", workspace=str(workspace))])

        memory_registry = MemoryRegistry(root=base / "memories")
        self.manager = RunManager(
            runs_root=base / "runs",
            machine_registry=registry,
            memory_registry=memory_registry,
        )

        import interfaces.adapters.api.ace_api as ace_api

        self._ace_api = ace_api
        self._original_manager = ace_api._RUN_MANAGER
        ace_api._RUN_MANAGER = self.manager

        from interfaces.app import create_app

        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self) -> None:
        self._ace_api._RUN_MANAGER = self._original_manager
        self._tmp.cleanup()

    def test_api_plan_gating_returns_outline(self) -> None:
        response = self.client.post(
            "/ace/runs",
            json={"brief": {"mode": "auto", "text": "Plan this work.", "plan_preview": "show"}},
        )
        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertEqual(body["status"], "plan_required")
        self.assertTrue(body["plan_outline"])

    def test_api_run_stream_and_artifacts(self) -> None:
        output = (
            "===PLAN===\nOutline\n"
            "===PATCH===\n--- a\n+++ b\n"
            "===ARTIFACTS===\nartifacts/out.log\n"
        )
        with patch.object(self.manager, "_invoke_codex", return_value=(output, 0)):
            with patch.object(self.manager, "_capture_git_diff", return_value=None):
                brief = Brief.from_dict({
                    "mode": "build",
                    "text": "API build",
                    "machines": ["skylink"],
                })
                record = self.manager.start_run(brief)

        stream_resp = self.client.get(f"/ace/runs/{record.id}/stream")
        self.assertEqual(stream_resp.status_code, 200)
        self.assertIn("MACHINE", stream_resp.get_data(as_text=True))

        artifacts_resp = self.client.get(f"/ace/runs/{record.id}/artifacts")
        self.assertEqual(artifacts_resp.status_code, 200)
        payload = artifacts_resp.get_json()
        self.assertEqual(payload["diff_path"], record.diff_path)

        plan_path = next(path for path in record.artifacts if path.endswith("plan.txt"))
        plan_resp = self.client.get(
            f"/ace/runs/{record.id}/file",
            query_string={"path": plan_path},
        )
        self.assertEqual(plan_resp.status_code, 200)
        self.assertIn("Outline", plan_resp.get_data(as_text=True))

    def test_api_stage_patch(self) -> None:
        output = (
            "===PLAN===\nOutline\n"
            "===PATCH===\n--- a\n+++ b\n"
        )
        with patch.object(self.manager, "_invoke_codex", return_value=(output, 0)):
            with patch.object(self.manager, "_capture_git_diff", return_value=None):
                brief = Brief.from_dict({
                    "mode": "build",
                    "text": "Stage build",
                    "machines": ["skylink"],
                })
                record = self.manager.start_run(brief)

        class DummyProc:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        calls = []

        def fake_run(cmd, capture_output=False, text=False, cwd=None, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["git", "rev-parse"]:
                return DummyProc(stdout="abc123\n")
            if cmd[:2] == ["git", "apply"]:
                return DummyProc(stdout="", stderr="", returncode=0)
            if cmd[:2] == ["git", "status"]:
                return DummyProc(stdout=" M sample.py\n")
            return DummyProc()

        with patch("ace_control.runs.subprocess.run", side_effect=fake_run):
            resp = self.client.post(f"/ace/runs/{record.id}/stage", json={})

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(Path(payload["log_path"]))
        self.assertTrue(any(cmd[:2] == ["git", "apply"] for cmd in calls))

    def test_api_run_commands(self) -> None:
        output = (
            "===PLAN===\nOutline\n"
            "===PATCH===\n--- a\n+++ b\n"
            "===COMMANDS===\nmake lint\n"
        )
        with patch.object(self.manager, "_invoke_codex", return_value=(output, 0)):
            with patch.object(self.manager, "_capture_git_diff", return_value=None):
                brief = Brief.from_dict({
                    "mode": "build",
                    "text": "Commands build",
                    "machines": ["skylink"],
                })
                record = self.manager.start_run(brief)

        executed = []

        class DummyProc:
            def __init__(self, stdout="", stderr="", returncode=0):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        def fake_run(cmd, capture_output=False, text=False, cwd=None, **kwargs):
            executed.append(cmd)
            if cmd[:2] == ["git", "rev-parse"]:
                return DummyProc(stdout="abc123\n")
            return DummyProc(stdout="done\n")

        with patch("ace_control.runs.subprocess.run", side_effect=fake_run):
            resp = self.client.post(f"/ace/runs/{record.id}/commands", json={"dry_run": True})

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(any(cmd[:2] == ["bash", "-lc"] for cmd in executed))

    def test_router_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ace_control.config_store._config_dir", return_value=Path(tmp)):
                response = self.client.get("/ace/config/router")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["source"], "default")
                self.assertIn("task_types", payload["config"])

                update = {
                    "task_types": {
                        "experimental": {"provider": "gpt_api", "stream": True}
                    }
                }
                put_resp = self.client.put("/ace/config/router", json=update)
                self.assertEqual(put_resp.status_code, 200)
                updated = put_resp.get_json()["config"]
                self.assertIn("experimental", updated["task_types"])

                saved = Path(tmp) / "router_config.json"
                self.assertTrue(saved.exists())

    def test_budget_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ace_control.config_store._config_dir", return_value=Path(tmp)):
                response = self.client.get("/ace/config/budget")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["source"], "default")
                self.assertIn("focus_history", payload["config"])

                update = {"focus_history": 7}
                put_resp = self.client.put("/ace/config/budget", json=update)
                self.assertEqual(put_resp.status_code, 200)
                updated = put_resp.get_json()["config"]
                self.assertEqual(updated["focus_history"], 7)

                saved = Path(tmp) / "ace_budgets.json"
                self.assertTrue(saved.exists())


if __name__ == "__main__":
    unittest.main()
