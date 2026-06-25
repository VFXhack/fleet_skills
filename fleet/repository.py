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
