from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

from .openai_compat import OpenAICompatProvider


_ENV_PATTERN = re.compile(r"\$\{(\w+)\}")


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str


class ProviderRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, ProviderConfig] = {}

    def add(self, cfg: ProviderConfig) -> None:
        key = cfg.name.strip().lower()
        if not key:
            raise ValueError("Provider name cannot be empty.")
        self._items[key] = cfg

    def get(self, name: str) -> ProviderConfig:
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("Missing --provider.")
        if key not in self._items:
            known = ", ".join(sorted(self._items.keys())) or "(none)"
            raise ValueError(f"Unknown provider '{name}'. Known providers: {known}")
        return self._items[key]

    def names(self) -> list[str]:
        return sorted(self._items.keys())


def _expand_env_placeholders(s: str) -> str:
    def repl(m: re.Match) -> str:
        var = m.group(1)
        val = os.getenv(var)
        if not val:
            raise ValueError(f"API key placeholder '${{{var}}}' not found in environment or is empty.")
        return val

    return _ENV_PATTERN.sub(repl, s)


def load_provider_registry(yaml_path: str | Path) -> ProviderRegistry:
    p = Path(yaml_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Config YAML not found: {p}")

    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    providers = data.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("YAML must contain a non-empty 'providers:' mapping.")

    reg = ProviderRegistry()

    for name, cfg in providers.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"providers.{name} must be a mapping/dict.")

        base_url = cfg.get("PYOPENCODE_BASE_URL")
        model = cfg.get("PYOPENCODE_MODEL")
        api_key = cfg.get("PYOPENCODE_API_KEY")

        missing = [k for k, v in {
            "PYOPENCODE_BASE_URL": base_url,
            "PYOPENCODE_MODEL": model,
            "PYOPENCODE_API_KEY": api_key,
        }.items() if not v]
        if missing:
            raise ValueError(f"providers.{name} missing required field(s): {', '.join(missing)}")

        base_url = str(base_url).strip()
        model = str(model).strip()
        api_key = str(api_key).strip()

        if not base_url or not model or not api_key:
            raise ValueError(f"providers.{name} has empty base_url/model/api_key after stripping.")

        api_key = _expand_env_placeholders(api_key)

        if not api_key:
            raise ValueError(f"providers.{name} api_key resolved to empty string.")

        reg.add(ProviderConfig(name=str(name), base_url=base_url, model=model, api_key=api_key))

    return reg


# ---------------------------------------------------------
# 🔥 兼容 AppContext.from_env(...) 的入口
# ---------------------------------------------------------
def resolve_provider(
    provider: Optional[str],
    model: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    yaml_path: Optional[Path] = None,
) -> OpenAICompatProvider:
    """
    Backward-compatible resolver used by AppContext.

    Priority:
      - CLI overrides (model/base_url/api_key)
      - YAML (by provider name)
    """
    if not provider:
        raise RuntimeError("Missing --provider (must match a name in pyopencode.yaml).")

    yaml_path = (yaml_path or Path("pyopencode.yaml")).expanduser().resolve()
    print(f"[pyopencode] provider config: {yaml_path}")
    reg = load_provider_registry(yaml_path)
    cfg = reg.get(provider)

    final_model = model or cfg.model
    final_base_url = base_url or cfg.base_url
    final_api_key = api_key or cfg.api_key

    if not final_model or not final_base_url or not final_api_key:
        raise RuntimeError(f"Incomplete provider config for '{provider}' after overrides.")

    return OpenAICompatProvider(
        model=final_model,
        base_url=final_base_url,
        api_key=final_api_key,
        provider_name=cfg.name,
    )
