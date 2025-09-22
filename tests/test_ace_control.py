import tempfile
import unittest
from pathlib import Path
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
            "===DIFF===\n--- a/file\n+++ b/file\n+added\n"
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
            "===DIFF===\n--- a\n+++ b\n"
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


if __name__ == "__main__":
    unittest.main()
