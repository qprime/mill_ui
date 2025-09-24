import tempfile
from pathlib import Path
from unittest.mock import patch

from skills.ace_control.config_store import save_router_config
from skills.ace_control.model_router import ModelRouter


def test_model_router_plan_order():
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp)
        with patch("skills.ace_control.config_store._config_dir", return_value=cache_dir), \
             patch("skills.ace_control.model_router._load_codex_cli_overrides", return_value={}):
            custom_config = {
                "task_types": {
                    "patch_small": {"provider": "gpt_api", "stream": True},
                    "build_large": {"provider": "codex_cli", "stream": True},
                },
                "providers": {
                    "codex_cli": {"temperature": 0.1},
                    "gpt_api": {
                        "model": "gpt-5",
                        "temperature": 0.3,
                        "max_prompt_tokens": 500000,
                        "max_output_tokens": 16000,
                    },
                },
                "fallback": {"attempts": 1, "order": ["codex_cli", "gpt_api"]},
            }
            save_router_config(custom_config)

            router = ModelRouter()
            plans = router.plan_for("patch_small")
            assert plans[0].name == "gpt_api"
            assert plans[0].model == "gpt-5"
            assert plans[0].temperature == 0.3
            assert len(plans) == 2
            assert plans[1].name == "codex_cli"

            build_plans = router.plan_for("build_large")
            assert build_plans[0].name == "codex_cli"
            assert build_plans[0].temperature == 0.1

            default_plans = router.plan_for("unknown_task")
            assert default_plans[0].name in {"gpt_api", "codex_cli"}
