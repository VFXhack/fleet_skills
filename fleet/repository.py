"""Repository: where the ubiquitous language meets SQL (ADR 0008).

Functions are named for UL nouns/acts and run inside the caller's transaction —
they do NOT commit; the caller decides when to commit or roll back.
"""

from __future__ import annotations

import psycopg


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
    """Return (id, title, lookdev_shot_code, pattern_version) for a Sequence, or None."""
    return conn.execute(
        "SELECT id, title, lookdev_shot_code, pattern_version FROM sequences "
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
