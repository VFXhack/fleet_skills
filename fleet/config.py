"""Fleet config resolution: the Postgres DSN + per-machine real paths.

Resolution order (see db/README.md, ADR 0002, ADR 0008):
  1. environment variable
  2. ~/.fleet/config.toml

The config file is per-machine and never committed (it holds the DB password).
"""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

CONFIG_PATH = Path.home() / ".fleet" / "config.toml"


@lru_cache(maxsize=1)
def _load() -> dict:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as fh:
            return tomllib.load(fh)
    return {}


def _resolve(env_var: str, *toml_keys: str) -> str | None:
    val = os.environ.get(env_var)
    if val:
        return val
    node: object = _load()
    for key in toml_keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, str) else None


def get_dsn() -> str:
    """Postgres DSN for the provenance core on Mckenna."""
    dsn = _resolve("FLEET_DB_DSN", "db", "dsn")
    if not dsn:
        raise RuntimeError(
            f"No Postgres DSN. Set FLEET_DB_DSN or add [db].dsn to {CONFIG_PATH}."
        )
    return dsn


def get_projects_root() -> str:
    """Real root that logical base_path (fleet:/projects/<client>/<job>/) resolves
    to on THIS machine (e.g. \\\\huxley\\io_common\\projects on Watts)."""
    root = _resolve("FLEET_PROJECTS_ROOT", "paths", "projects_root")
    if not root:
        raise RuntimeError(
            f"No projects_root. Set FLEET_PROJECTS_ROOT or add [paths].projects_root to {CONFIG_PATH}."
        )
    return root
