"""add-sequence — create or update a Sequence's CONFIG (ADR 0008/0020) without
adding a Shot.

`add-shot` already creates the Sequence row on the first shot; this tool manages
the Sequence's config independently: set/update its title, and (re)designate its
look-dev (Target) Shot (ADR 0020 §5). Designating a look-dev VALIDATES that the
Shot's folder exists in the tree first — a look-dev must be a real Shot.

Order of operations (failure leaves nothing dangling — but this tool only writes
to the DB, never the tree):
  1. resolve config + compute codes, validate inputs
  2. refuse if the project isn't registered (or, for --lookdev, the shot has no folder)
  3. ensure the sequences row; apply title / lookdev changes (uncommitted)
  4. commit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, db, naming, repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="add-sequence",
        description="Create/update a Sequence's config: title + look-dev Shot (ADR 0020).",
    )
    parser.add_argument("--client", required=True, help="client_code, e.g. WBTV")
    parser.add_argument("--job", required=True, help="job_code (= Project), e.g. AWA")
    parser.add_argument("--sequence", required=True, help="sequence token, e.g. SALEM")
    parser.add_argument("--episode", default="EP01", help="episode token (default EP01)")
    parser.add_argument("--title", default=None, help="set/update the Sequence title")
    parser.add_argument("--lookdev", default=None, metavar="SHOT",
                        help="shot token to designate as the look-dev Shot, e.g. 030 (its folder must exist)")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen; touch nothing")
    args = parser.parse_args(argv)

    try:
        for label, value in (
            ("client", args.client), ("job", args.job),
            ("episode", args.episode), ("sequence", args.sequence),
        ):
            naming.validate_token(label, value)
        if args.lookdev is not None:
            naming.validate_token("lookdev shot", args.lookdev)
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    seq_code = naming.sequence_code(args.job, args.episode, args.sequence)
    lookdev_code = (
        naming.shot_code(args.job, args.episode, args.sequence, args.lookdev)
        if args.lookdev is not None else None
    )

    print(f"sequence_code : {seq_code}")
    if args.title is not None:
        print(f"title         : {args.title}")
    if lookdev_code:
        print(f"lookdev       : {lookdev_code}")

    if args.dry_run:
        changes = []
        if args.title is not None:
            changes.append("set title")
        if lookdev_code:
            changes.append("set lookdev_shot_code (after checking its folder exists)")
        plan = ", ".join(changes) or "ensure the sequences row exists"
        print(f"\n[dry-run] would: {plan}")
        return 0

    # A look-dev must be a real Shot — its folder has to exist in the tree.
    if lookdev_code:
        projects_root = Path(config.get_projects_root())
        shot_dir = projects_root / args.client / args.job / args.episode / args.sequence / lookdev_code
        if not shot_dir.exists():
            sys.exit(f"error: look-dev shot {lookdev_code} has no folder at {shot_dir} - "
                     f"add it with add-shot first.")

    conn = db.connect()
    try:
        project = repository.get_project_by_code(conn, args.client, args.job)
        if not project:
            sys.exit(f"error: {args.client}/{args.job} is not registered - run create-project first.")
        project_id = str(project[0])

        sequence_id, seq_created = repository.ensure_sequence(
            conn, project_id=project_id, sequence_code=seq_code, title=args.title
        )
        # ensure_sequence only sets title when it CREATES the row; update an existing one:
        if args.title is not None and not seq_created:
            repository.set_sequence_title(conn, sequence_id=sequence_id, title=args.title)

        prev_lookdev = None
        if lookdev_code:
            prev_lookdev = repository.set_lookdev_shot(conn, sequence_id=sequence_id, shot_code=lookdev_code)

        conn.commit()
    except SystemExit:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\nsequence              : {'CREATED' if seq_created else 'updated'} ({seq_code})")
    if args.title is not None:
        print(f"title                 : {args.title}")
    if lookdev_code:
        if prev_lookdev and prev_lookdev != lookdev_code:
            print(f"lookdev_shot_code     : {lookdev_code}  (replaced previous: {prev_lookdev})")
        else:
            print(f"lookdev_shot_code     : {lookdev_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
