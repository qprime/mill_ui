"""Model routing between Codex CLI and GPT API with fallback handling."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config_store import load_router_config

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older runtimes
    tomllib = None


@dataclass
class ProviderPlan:
    name: str
    stream: bool
    temperature: Optional[float]
    model: Optional[str]
    max_prompt_tokens: Optional[int]
    max_output_tokens: Optional[int]
    metadata: Dict[str, object]


class ModelRouter:
    def __init__(self) -> None:
        self._config, _ = load_router_config()
        self._apply_codex_defaults()

    @property
    def config(self) -> Dict[str, object]:
        return self._config

    def refresh(self) -> None:
        self._config, _ = load_router_config()
        self._apply_codex_defaults()

    def _apply_codex_defaults(self) -> None:
        overrides = _load_codex_cli_overrides()
        if not overrides:
            return
        providers = self._config.setdefault("providers", {})
        codex_settings = providers.setdefault("codex_cli", {})
        for key, value in overrides.items():
            if value is not None and key not in codex_settings:
                codex_settings[key] = value

    def _provider_defaults(self, name: str) -> Dict[str, object]:
        providers = self._config.get("providers", {})
        if name not in providers:
            raise KeyError(f"Unknown provider '{name}'")
        return providers[name]

    def plan_for(self, task_type: str) -> List[ProviderPlan]:
        task_map = self._config.get("task_types", {})
        task_settings = task_map.get(task_type) or task_map.get("analyze") or {}
        primary_provider = task_settings.get("provider", "gpt_api")
        attempts = int(self._config.get("fallback", {}).get("attempts", 0))
        order: Iterable[str] = self._config.get("fallback", {}).get("order", [])

        plans: List[ProviderPlan] = []

        def build_plan(provider_name: str, overrides: Optional[Dict[str, object]]) -> ProviderPlan:
            defaults = self._provider_defaults(provider_name)
            stream = bool(overrides.get("stream", True)) if overrides else True
            temperature = overrides.get("temperature") if overrides and "temperature" in overrides else defaults.get("temperature")
            model = overrides.get("model") if overrides and "model" in overrides else defaults.get("model")
            max_prompt_tokens = overrides.get("max_prompt_tokens") if overrides and "max_prompt_tokens" in overrides else defaults.get("max_prompt_tokens")
            max_output_tokens = overrides.get("max_output_tokens") if overrides and "max_output_tokens" in overrides else defaults.get("max_output_tokens")
            return ProviderPlan(
                name=provider_name,
                stream=stream,
                temperature=temperature if temperature is not None else defaults.get("temperature"),
                model=model,
                max_prompt_tokens=max_prompt_tokens,
                max_output_tokens=max_output_tokens,
                metadata={"overrides": overrides or {}, "defaults": defaults},
            )

        plans.append(build_plan(primary_provider, task_settings))

        if attempts > 0:
            added = 0
            for candidate in order:
                if candidate == primary_provider:
                    continue
                plans.append(build_plan(candidate, {}))
                added += 1
                if added >= attempts:
                    break

        return plans


def default_router() -> ModelRouter:
    return ModelRouter()


def _load_codex_cli_overrides() -> Dict[str, object]:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists() or tomllib is None:
        return {}
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    overrides: Dict[str, object] = {}
    model = data.get("model")
    if isinstance(model, str) and model:
        overrides["model"] = model
    reasoning = data.get("model_reasoning_effort")
    if isinstance(reasoning, str) and reasoning:
        overrides.setdefault("metadata", {})
        overrides["metadata"]["reasoning_effort"] = reasoning
    return overrides
