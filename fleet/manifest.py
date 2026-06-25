"""The thin per-Project Manifest (ADR 0006). Matches schemas/manifest.schema.json.

Holds only identity + logical base_path + the db_project_id pointer. No provenance
(that lives in the DB), no structural enumeration (discovered by walking the tree).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

MANIFEST_VERSION = 1


def logical_base_path(client_code: str, job_code: str) -> str:
    """Platform-neutral root stored in the manifest (resolved per-machine elsewhere)."""
    return f"fleet:/projects/{client_code}/{job_code}/"


def build_manifest(
    *,
    client_code: str,
    job_code: str,
    title: str,
    db_project_id: str,
    status: str = "active",
    created: date | None = None,
) -> dict:
    stamp = (created or date.today()).isoformat()
    return {
        "manifest_version": MANIFEST_VERSION,
        "client_code": client_code,
        "job_code": job_code,
        "title": title,
        "status": status,
        "base_path": logical_base_path(client_code, job_code),
        "created": stamp,
        "updated": stamp,
        "db_project_id": db_project_id,
    }


def write_manifest(job_dir: Path, manifest: dict) -> Path:
    path = job_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
