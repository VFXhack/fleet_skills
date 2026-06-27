"""Manually emit ONE event through the outbox — smoke-test the Roustabout spine
end-to-end before the full Submitter exists.

    python -m submitter.emit_demo version <version_uuid>
    python -m submitter.emit_demo publish <publish_uuid> [--role Hero]

Resolves the Fleet DSN, emits in a single committed transaction; a running
`python -m roustabout.worker` should drain it immediately and log the flow
(barrier / auto-publish-eligibility / chain match, with the stub handlers).
Needs the 0001–0003 migrations applied and a real version/publish row to point at.
"""
from __future__ import annotations

import argparse

import psycopg

from .config import resolve_dsn
from .events import emit_publish_recorded, emit_version_recorded


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit one orchestration event (smoke test).")
    sub = ap.add_subparsers(dest="kind", required=True)

    v = sub.add_parser("version", help="emit VersionRecorded for a versions.id")
    v.add_argument("id")

    p = sub.add_parser("publish", help="emit PublishRecorded for a publishes.id")
    p.add_argument("id")
    p.add_argument("--role", default=None, help="Role/tag for chain matching (e.g. Hero)")

    args = ap.parse_args()

    with psycopg.connect(resolve_dsn()) as conn:
        with conn.transaction():
            if args.kind == "version":
                emit_version_recorded(conn, args.id)
            else:
                emit_publish_recorded(conn, args.id, role=args.role)
    print(f"emitted {args.kind} event for {args.id}")


if __name__ == "__main__":
    main()
