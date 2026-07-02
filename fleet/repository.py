"""Repository: where the ubiquitous language meets SQL (ADR 0008).

Functions are named for UL nouns/acts and run inside the caller's transaction —
they do NOT commit; the caller decides when to commit or roll back.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json


class ProjectExistsError(Exception):
    """A project with the same (client_code, job_code) already exists."""


def get_project_by_code(conn: psycopg.Connection, client_code: str, job_code: str):
    """Return (id, title, status, base_path) for a project, or None."""
    return conn.execute(
        "SELECT id, title, status, base_path FROM projects "
        "WHERE client_code = %s AND job_code = %s",
        (client_code, job_code),
    ).fetchone()


def create_project(
    conn: psycopg.Connection,
    *,
    client_code: str,
    job_code: str,
    title: str,
    base_path: str,
    status: str = "active",
) -> str:
    """Insert a projects row; return its UUID (the db_project_id). Does not commit."""
    try:
        row = conn.execute(
            "INSERT INTO projects (client_code, job_code, title, base_path, status) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (client_code, job_code, title, base_path, status),
        ).fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise ProjectExistsError(
            f"Project {client_code}/{job_code} already exists in the DB."
        ) from exc
    return str(row[0])


def delete_project(conn: psycopg.Connection, db_project_id: str) -> None:
    """Remove a projects row by id. Does not commit. (Used by tests/teardown.)"""
    conn.execute("DELETE FROM projects WHERE id = %s", (db_project_id,))


# --- Sequences (ADR 0020): a Sequence's CONFIG row; its EXISTENCE still comes
# --- from the tree. add-shot ensures one exists on the first shot of a Sequence.

def get_sequence(conn: psycopg.Connection, project_id: str, sequence_code: str):
    """Return (id, title, lookdev_shot_code, look_version) for a Sequence, or None."""
    return conn.execute(
        "SELECT id, title, lookdev_shot_code, look_version FROM sequences "
        "WHERE project_id = %s AND sequence_code = %s",
        (project_id, sequence_code),
    ).fetchone()


def ensure_sequence(
    conn: psycopg.Connection,
    *,
    project_id: str,
    sequence_code: str,
    title: str | None = None,
) -> tuple[str, bool]:
    """Get-or-create the Sequence config row. Returns (sequence_id, created). Does not commit."""
    existing = get_sequence(conn, project_id, sequence_code)
    if existing:
        return str(existing[0]), False
    row = conn.execute(
        "INSERT INTO sequences (project_id, sequence_code, title) VALUES (%s, %s, %s) RETURNING id",
        (project_id, sequence_code, title),
    ).fetchone()
    return str(row[0]), True


def set_sequence_title(conn: psycopg.Connection, *, sequence_id: str, title: str) -> None:
    """Update a Sequence's title. Does not commit."""
    conn.execute(
        "UPDATE sequences SET title = %s, updated_at = now() WHERE id = %s",
        (title, sequence_id),
    )


def set_lookdev_shot(
    conn: psycopg.Connection, *, sequence_id: str, shot_code: str
) -> str | None:
    """Mark a Shot as the Sequence's look-dev Shot (ADR 0020 §5). Returns the
    previous lookdev_shot_code (or None). Does not commit."""
    prev = conn.execute(
        "SELECT lookdev_shot_code FROM sequences WHERE id = %s", (sequence_id,)
    ).fetchone()
    conn.execute(
        "UPDATE sequences SET lookdev_shot_code = %s, updated_at = now() WHERE id = %s",
        (shot_code, sequence_id),
    )
    return prev[0] if prev else None


# --- Sequence Look — Hoist (lift the look-dev Shot's recipe UP; ADR 0020/0021) ---
# The reads Hoist needs from the base spine, plus the writes that build the Look.
# All run inside the caller's transaction (no commit here).

def get_latest_publish(conn: psycopg.Connection, shot_code: str):
    """The most recent Publish (highest p-number) for a Shot — the default anchor
    for a Hoist. Returns (publish_id, p_number, source_version_id, v_number) or None."""
    return conn.execute(
        "SELECT p.id, p.number, p.source_version_id, v.number "
        "FROM publishes p JOIN versions v ON v.id = p.source_version_id "
        "WHERE p.shot_code = %s ORDER BY p.number DESC LIMIT 1",
        (shot_code,),
    ).fetchone()


def get_publish_by_number(conn: psycopg.Connection, shot_code: str, number: int):
    """A specific Publish (p<number>) for a Shot — the --publish override anchor.
    Returns (publish_id, p_number, source_version_id, v_number) or None."""
    return conn.execute(
        "SELECT p.id, p.number, p.source_version_id, v.number "
        "FROM publishes p JOIN versions v ON v.id = p.source_version_id "
        "WHERE p.shot_code = %s AND p.number = %s",
        (shot_code, number),
    ).fetchone()


def get_run_for_look(conn: psycopg.Connection, run_id: str) -> dict | None:
    """One Run's authoring recipe, shaped for a Look Run. `stage` (which lives on
    versions, not runs) is derived from the run's first version, default 'render'."""
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(
        """
        SELECT r.id, r.type,
               COALESCE((SELECT v.stage FROM versions v WHERE v.run_id = r.id
                         ORDER BY v.created_at LIMIT 1), 'render') AS stage,
               r.template_ref, r.model, r.tier, r.mode, r.params
        FROM runs r WHERE r.id = %s
        """,
        (run_id,),
    ).fetchone()


def get_run_bindings(conn: psycopg.Connection, run_id: str) -> list[dict]:
    """A Run's input bindings (asset->role edges, ADR 0005). Dict rows."""
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(
        "SELECT id, asset_id, pinned_publish_id, pinned_import_uri, role "
        "FROM bindings WHERE run_id = %s ORDER BY created_at, id",
        (run_id,),
    ).fetchall()


def resolve_publish_source_run(conn: psycopg.Connection, publish_id: str):
    """publish -> source Version -> the run_id that produced it (the producer link a
    shared-recipe Look input needs). None if the publish is unknown."""
    row = conn.execute(
        "SELECT v.run_id FROM publishes p JOIN versions v ON v.id = p.source_version_id "
        "WHERE p.id = %s",
        (publish_id,),
    ).fetchone()
    return row[0] if row else None


def get_asset(conn: psycopg.Connection, asset_id: str) -> dict | None:
    """An Asset row (dict) — used to mirror its content into a Sequence-scoped Asset."""
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(
        "SELECT id, scope, shot_code, sequence_code, name, resolved_publish_id, "
        "import_uri, import_meta FROM assets WHERE id = %s",
        (asset_id,),
    ).fetchone()


def ensure_sequence_asset(
    conn: psycopg.Connection, *, project_id: str, sequence_code: str, name: str,
    resolved_publish_id=None, import_uri: str | None = None, import_meta=None,
) -> str:
    """Get-or-create a `scope='sequence'` Asset mirroring a piece of content for the
    whole Sequence — the home of a shared-content Look input (ADR 0020 §4). The file
    still lives flat in <Job>/assets/; 'sequence' is a binding scope, not a folder.
    Reused by (project, sequence_code, name) so re-hoist is idempotent. Returns id."""
    existing = conn.execute(
        "SELECT id FROM assets WHERE project_id=%s AND scope='sequence' "
        "AND sequence_code=%s AND name=%s",
        (project_id, sequence_code, name),
    ).fetchone()
    if existing:
        return str(existing[0])
    row = conn.execute(
        "INSERT INTO assets (project_id, scope, sequence_code, name, "
        "resolved_publish_id, import_uri, import_meta) "
        "VALUES (%s,'sequence',%s,%s,%s,%s,%s) RETURNING id",
        (project_id, sequence_code, name, resolved_publish_id, import_uri,
         Json(import_meta) if import_meta is not None else None),
    ).fetchone()
    return str(row[0])


def clear_sequence_look(conn: psycopg.Connection, sequence_id: str) -> int:
    """Drop the Sequence's current Look (Look Runs cascade to Look inputs) so Hoist
    rebuilds it fresh. Returns the number of Look Runs removed."""
    return conn.execute(
        "DELETE FROM sequence_look_runs WHERE sequence_id = %s", (sequence_id,)
    ).rowcount


def insert_look_run(
    conn: psycopg.Connection, *, sequence_id: str, run_type: str, stage: str,
    template_ref, model, tier, mode, params, ord: int,
) -> str:
    """Insert one Look Run (a Run-shaped authoring recipe minus per-Shot content)."""
    row = conn.execute(
        "INSERT INTO sequence_look_runs "
        "(sequence_id, type, stage, template_ref, model, tier, mode, params, ord) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (sequence_id, run_type, stage, template_ref, model, tier, mode,
         Json(params or {}), ord),
    ).fetchone()
    return str(row[0])


def insert_look_binding(
    conn: psycopg.Connection, *, look_run_id: str, role: str, sharing_class: str,
    asset_id=None, produced_by_look_run_id=None,
) -> str:
    """Insert one Look input (a Look Run's input slot, tagged by sharing class). The
    DB CHECK enforces source==class (asset / producer / neither)."""
    row = conn.execute(
        "INSERT INTO sequence_look_bindings "
        "(look_run_id, role, sharing_class, asset_id, produced_by_look_run_id) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (look_run_id, role, sharing_class, asset_id, produced_by_look_run_id),
    ).fetchone()
    return str(row[0])


def bump_look_version(conn: psycopg.Connection, sequence_id: str) -> int:
    """Each Hoist bumps the Sequence's look_version (ADR 0020 §7). Returns the new value."""
    row = conn.execute(
        "UPDATE sequences SET look_version = look_version + 1, updated_at = now() "
        "WHERE id = %s RETURNING look_version",
        (sequence_id,),
    ).fetchone()
    return row[0]
