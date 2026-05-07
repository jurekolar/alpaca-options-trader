"""TOML config loader."""

from __future__ import annotations

from pathlib import Path
import tomllib

from options_trader.config.models import BotConfig


DEFAULT_CONFIG_PATH = Path("config/default.toml")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> BotConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return BotConfig.from_mapping(data)

