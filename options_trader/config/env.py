"""Small `.env` loader used for local Alpaca credentials.

This supports the common dotenv subset the project needs without adding a
runtime dependency: comments, optional `export`, quoted values, and plain
`KEY=value` lines.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
import os
from pathlib import Path
import re


ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def dotenv_values(path: str | Path = ".env") -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        values[key] = value
    return values


def load_dotenv(
    path: str | Path = ".env",
    *,
    override: bool = False,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    target = os.environ if environ is None else environ
    values = dotenv_values(path)
    for key, value in values.items():
        if override or key not in target:
            target[key] = value
    return values


def environment_with_dotenv(
    env: Mapping[str, str] | None = None,
    dotenv_path: str | Path | None = ".env",
) -> dict[str, str]:
    if env is None:
        if dotenv_path is not None:
            load_dotenv(dotenv_path)
        return dict(os.environ)

    values = dotenv_values(dotenv_path) if dotenv_path is not None else {}
    merged = dict(values)
    merged.update(env)
    return merged


def _parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].lstrip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    if not ENV_KEY_RE.match(key):
        return None
    return key, _parse_dotenv_value(value.strip())


def _parse_dotenv_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        unquoted = value[1:-1]
        if value[0] == '"':
            return (
                unquoted.replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )
        return unquoted
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value
