"""Stamp the canonical ADR-0003 project tree (the job-level skeleton).

Episodes/Sequences/Shots below the first Episode are added on demand by later
tools, not at project creation.
"""

from __future__ import annotations

from pathlib import Path

# Job-level directories (ADR 0003).
JOB_DIRS = [
    "_ops/scripts",   # PS1 / automation
    "_ops/logs",      # local run & job logs
    "_ops/config",    # tool config
    "_ops/jobs",      # Flamenco submission files
    "assets",         # job-shared assets — flat, descriptively named
    "editorial",      # Premiere/AE cut assembly (job-wide finishing)
]

# Per-Shot directories (ADR 0003): everything for a Shot lives in its one folder.
SHOT_DIRS = [
    "assets",            # shot-specific input files (flat; Role is metadata, not folder)
    "work/blender",      # .blend + autosave (the .blend Flamenco renders)
    "work/nuke",         # .nk scripts
    "versions/render",   # model takes + seed sweeps  (v###)
    "versions/upscale",  # Topaz / up-res tries
    "versions/comp",     # comp renders
    "publishes",         # internal-promoted takes (p###) — stable, canonical
]

PROJECT_CONTEXT_TEMPLATE = """# CONTEXT.md — {title} ({client_code}/{job_code})

Project-local notes and glossary. Inherits the system ubiquitous language from the
fleet_skills repo's CONTEXT.md; record only project-specific terms and decisions here.

- **Client:** {client_code}
- **Job (Project):** {job_code} — {title}
- **base_path:** fleet:/projects/{client_code}/{job_code}/
- **db_project_id:** {db_project_id}

## Structure (ADR 0003)
`_ops/` (scripts/logs/config/jobs), `assets/` (job-shared, flat), `editorial/`, and per-Episode
`<EPISODE>/<SEQUENCE>/<JOB_SEQ_SHOT>/` with `assets/ work/ versions/ publishes/`.
Episodes/Sequences/Shots are added on demand.
"""


def scaffold_job_tree(job_dir: Path, *, episode: str = "EP01") -> list[Path]:
    """Create the ADR-0003 job skeleton + a first Episode with deliverables/.

    Idempotent (exist_ok). Returns the directories created/ensured.
    """
    created: list[Path] = []
    for rel in JOB_DIRS + [f"{episode}/deliverables"]:
        directory = job_dir / rel
        directory.mkdir(parents=True, exist_ok=True)
        created.append(directory)
    return created


def scaffold_shot_tree(shot_dir: Path) -> list[Path]:
    """Create the ADR-0003 per-Shot skeleton (assets/ work/ versions/ publishes/).

    Idempotent (exist_ok). Returns the directories created/ensured. Intermediate
    Episode/Sequence dirs are made as needed (parents=True).
    """
    created: list[Path] = []
    for rel in SHOT_DIRS:
        directory = shot_dir / rel
        directory.mkdir(parents=True, exist_ok=True)
        created.append(directory)
    return created


def write_project_context(
    job_dir: Path, *, title: str, client_code: str, job_code: str, db_project_id: str
) -> Path:
    path = job_dir / "CONTEXT.md"
    path.write_text(
        PROJECT_CONTEXT_TEMPLATE.format(
            title=title, client_code=client_code, job_code=job_code, db_project_id=db_project_id
        ),
        encoding="utf-8",
    )
    return path
