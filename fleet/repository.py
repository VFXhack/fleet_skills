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


def get_look_runs(conn: psycopg.Connection, sequence_id: str) -> list[dict]:
    """The Sequence's Look Runs in chain order (ord) — what Cast clones down."""
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(
        "SELECT id, type, stage, template_ref, model, tier, mode, params, ord "
        "FROM sequence_look_runs WHERE sequence_id = %s ORDER BY ord",
        (sequence_id,),
    ).fetchall()


def get_look_bindings(conn: psycopg.Connection, look_run_id: str) -> list[dict]:
    """A Look Run's input slots (role + sharing class + source), asset detail joined
    in for shared-content display/binding."""
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(
        "SELECT b.id, b.role, b.sharing_class, b.asset_id, b.produced_by_look_run_id, "
        "       a.name AS asset_name, a.resolved_publish_id AS asset_publish_id, "
        "       a.import_uri AS asset_import_uri, a.import_meta AS asset_import_meta "
        "FROM sequence_look_bindings b LEFT JOIN assets a ON a.id = b.asset_id "
        "WHERE b.look_run_id = %s ORDER BY b.role",
        (look_run_id,),
    ).fetchall()


# --- Shot Overrides (ADR 0023): a Shot's local value + shield, one row per
# --- overridden attribute, keyed by stable codes (never look_run_id — a
# --- rebuild-fresh Hoist would orphan it). Cast reads; Hoist clears redundant.

def set_param_override(
    conn: psycopg.Connection, *, sequence_id: str, shot_code: str, run_type: str,
    param_key: str, param_value,
) -> bool:
    """Upsert a param override (cfg -> 4.0). Returns True if a new row was created,
    False if an existing one was updated. Does not commit."""
    updated = conn.execute(
        "UPDATE shot_overrides SET param_value = %s, updated_at = now() "
        "WHERE sequence_id = %s AND shot_code = %s AND run_type = %s AND param_key = %s",
        (Json(param_value), sequence_id, shot_code, run_type, param_key),
    ).rowcount
    if updated:
        return False
    conn.execute(
        "INSERT INTO shot_overrides (sequence_id, shot_code, run_type, param_key, param_value) "
        "VALUES (%s,%s,%s,%s,%s)",
        (sequence_id, shot_code, run_type, param_key, Json(param_value)),
    )
    return True


def set_role_override(
    conn: psycopg.Connection, *, sequence_id: str, shot_code: str, run_type: str,
    role: str, asset_id: str,
) -> bool:
    """Upsert a binding override (Character-Sheet -> the Shot's own Asset).
    Returns True if created, False if updated. Does not commit."""
    updated = conn.execute(
        "UPDATE shot_overrides SET asset_id = %s, updated_at = now() "
        "WHERE sequence_id = %s AND shot_code = %s AND run_type = %s AND role = %s",
        (asset_id, sequence_id, shot_code, run_type, role),
    ).rowcount
    if updated:
        return False
    conn.execute(
        "INSERT INTO shot_overrides (sequence_id, shot_code, run_type, role, asset_id) "
        "VALUES (%s,%s,%s,%s,%s)",
        (sequence_id, shot_code, run_type, role, asset_id),
    )
    return True


def clear_override(
    conn: psycopg.Connection, *, sequence_id: str, shot_code: str, run_type: str,
    param_key: str | None = None, role: str | None = None,
) -> int:
    """Delete one override ("start following the Sequence again"). Exactly one of
    param_key / role. Returns rows removed. Does not commit."""
    if param_key is not None:
        return conn.execute(
            "DELETE FROM shot_overrides WHERE sequence_id=%s AND shot_code=%s "
            "AND run_type=%s AND param_key=%s",
            (sequence_id, shot_code, run_type, param_key),
        ).rowcount
    return conn.execute(
        "DELETE FROM shot_overrides WHERE sequence_id=%s AND shot_code=%s "
        "AND run_type=%s AND role=%s",
        (sequence_id, shot_code, run_type, role),
    ).rowcount


def get_shot_overrides(
    conn: psycopg.Connection, sequence_id: str, shot_code: str | None = None,
) -> list[dict]:
    """A Sequence's overrides (optionally one Shot's), asset name joined in."""
    cur = conn.cursor(row_factory=dict_row)
    sql = (
        "SELECT o.id, o.shot_code, o.run_type, o.param_key, o.param_value, "
        "       o.role, o.asset_id, a.name AS asset_name "
        "FROM shot_overrides o LEFT JOIN assets a ON a.id = o.asset_id "
        "WHERE o.sequence_id = %s"
    )
    params: list = [sequence_id]
    if shot_code is not None:
        sql += " AND o.shot_code = %s"
        params.append(shot_code)
    sql += " ORDER BY o.shot_code, o.run_type, o.param_key NULLS LAST, o.role"
    return cur.execute(sql, params).fetchall()


def clear_hoisted_overrides(
    conn: psycopg.Connection, *, sequence_id: str, shot_code: str,
    params_by_type: dict[str, set], roles_by_type: dict[str, set],
) -> int:
    """After a Hoist, delete the look-dev Shot's overrides for the attributes that
    were just lifted (they became the Look's value — redundant; ADR 0020 §6 /
    0023). Surgical: an override on an attribute NOT in the hoisted recipe
    survives. Returns rows removed. Does not commit."""
    removed = 0
    for run_type, keys in params_by_type.items():
        if keys:
            removed += conn.execute(
                "DELETE FROM shot_overrides WHERE sequence_id=%s AND shot_code=%s "
                "AND run_type=%s AND param_key = ANY(%s)",
                (sequence_id, shot_code, run_type, list(keys)),
            ).rowcount
    for run_type, roles in roles_by_type.items():
        if roles:
            removed += conn.execute(
                "DELETE FROM shot_overrides WHERE sequence_id=%s AND shot_code=%s "
                "AND run_type=%s AND role = ANY(%s)",
                (sequence_id, shot_code, run_type, list(roles)),
            ).rowcount
    return removed


# --- Cast (ADR 0020 §7 / 0021): clone the Look DOWN into real Runs for a Shot ---

def find_asset_by_name(
    conn: psycopg.Connection, *, project_id: str, shot_code: str, name: str,
) -> dict | None:
    """Resolve an Asset by name for a Shot's use: the Shot's own (scope='shot')
    asset of that name first, else a job-scoped one. None if neither exists."""
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(
        "SELECT id, scope, name, resolved_publish_id, import_uri FROM assets "
        "WHERE project_id = %s AND name = %s "
        "  AND (scope = 'job' OR (scope = 'shot' AND shot_code = %s)) "
        "ORDER BY (scope = 'shot') DESC LIMIT 1",
        (project_id, name, shot_code),
    ).fetchone()


def get_cast_runs(
    conn: psycopg.Connection, *, shot_code: str, sequence_code: str, look_version: int,
) -> dict[int, dict]:
    """The Shot's existing Cast generation for one look_version, keyed by the Look
    Run ord it was cloned from (the re-cast idempotency check)."""
    cur = conn.cursor(row_factory=dict_row)
    rows = cur.execute(
        "SELECT id, type, params, cast_from FROM runs "
        "WHERE shot_code = %s AND cast_from ->> 'sequence_code' = %s "
        "  AND (cast_from ->> 'look_version')::int = %s",
        (shot_code, sequence_code, look_version),
    ).fetchall()
    return {r["cast_from"]["ord"]: r for r in rows}


def insert_cast_run(
    conn: psycopg.Connection, *, project_id: str, shot_code: str, run_type: str,
    template_ref, model, tier, mode, params, cast_from: dict,
) -> str:
    """Insert one Cast-created Run: a Look Run cloned down for a Shot, with the
    provenance breadcrumb (which Look version made this) in cast_from."""
    row = conn.execute(
        "INSERT INTO runs (project_id, shot_code, type, template_ref, model, tier, "
        "mode, params, cast_from) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (project_id, shot_code, run_type, template_ref, model, tier, mode,
         Json(params or {}), Json(cast_from)),
    ).fetchone()
    return str(row[0])


def insert_binding(
    conn: psycopg.Connection, *, run_id: str, asset_id: str, role: str,
    pinned_publish_id=None, pinned_import_uri: str | None = None,
) -> str:
    """Insert one input binding on a Run (asset->role edge, ADR 0005)."""
    row = conn.execute(
        "INSERT INTO bindings (run_id, asset_id, pinned_publish_id, pinned_import_uri, role) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (run_id, asset_id, pinned_publish_id, pinned_import_uri, role),
    ).fetchone()
    return str(row[0])


def get_binding_for_role(conn: psycopg.Connection, run_id: str, role: str):
    """A Run's existing binding for a Role, or None (the pending-input check)."""
    return conn.execute(
        "SELECT id FROM bindings WHERE run_id = %s AND role = %s", (run_id, role)
    ).fetchone()


def get_latest_run_publish(conn: psycopg.Connection, run_id: str):
    """The latest Publish whose source Version came from this Run — how a completed
    shared-recipe re-run offers its content back to the Cast (ADR 0018 auto-publish
    feeds this). Returns (publish_id, number) or None."""
    return conn.execute(
        "SELECT p.id, p.number FROM publishes p "
        "JOIN versions v ON v.id = p.source_version_id "
        "WHERE v.run_id = %s ORDER BY p.number DESC LIMIT 1",
        (run_id,),
    ).fetchone()


def ensure_shot_asset(
    conn: psycopg.Connection, *, project_id: str, shot_code: str, name: str,
    resolved_publish_id,
) -> str:
    """Get-or-create a scope='shot' Asset wrapping a Publish for binding (the
    fixture's 'salem 010 depth' shape). Reused by (project, shot_code, name) so
    re-casting is idempotent; the content pointer is refreshed. Returns id."""
    existing = conn.execute(
        "SELECT id FROM assets WHERE project_id=%s AND scope='shot' "
        "AND shot_code=%s AND name=%s",
        (project_id, shot_code, name),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE assets SET resolved_publish_id=%s, updated_at=now() WHERE id=%s",
            (resolved_publish_id, existing[0]),
        )
        return str(existing[0])
    row = conn.execute(
        "INSERT INTO assets (project_id, scope, shot_code, name, resolved_publish_id) "
        "VALUES (%s,'shot',%s,%s,%s) RETURNING id",
        (project_id, shot_code, name, resolved_publish_id),
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
