"""add-shot — scaffold a Shot's ADR-0003 tree under its Sequence, ensuring the
Sequence's config row exists in the provenance DB (ADR 0008/0020).

Shots are NOT DB rows — the Episode/Sequence/Shot structure is discovered by
walking the tree (ADR 0003). What add-shot writes to the DB is the *Sequence*
config row (created on the first shot of a new Sequence), and — with --lookdev —
the Sequence's look-dev Shot pointer (ADR 0020 §5).

Order of operations is chosen so a failure leaves nothing dangling:
  1. resolve config + compute codes/paths, validate inputs
  2. refuse if the project isn't registered, or the shot dir exists non-empty
  3. ensure the sequences row (INSERT if absent); set lookdev if asked (uncommitted)
  4. scaffold the shot tree
  5. commit
On any failure after step 3, the DB writes are rolled back and a freshly-created
shot directory is removed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import config, db, naming, repository, scaffold


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="add-shot",
        description="Scaffold a Shot's ADR-0003 tree + ensure its Sequence config (ADR 0020).",
    )
    parser.add_argument("--client", required=True, help="client_code, e.g. WBTV")
    parser.add_argument("--job", required=True, help="job_code (= Project), e.g. AWA")
    parser.add_argument("--sequence", required=True, help="sequence token, e.g. SALEM")
    parser.add_argument("--shot", required=True, help="shot token, e.g. 010")
    parser.add_argument("--episode", default="EP01", help="episode token (default EP01)")
    parser.add_argument("--seq-title", default=None, help="title for the Sequence if it is being created")
    parser.add_argument("--lookdev", action="store_true",
                        help="designate this Shot as the Sequence's look-dev (Target) Shot (ADR 0020)")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen; touch nothing")
    args = parser.parse_args(argv)

    # Validate every code part (no underscores — '_' separates the parts; ADR 0015).
    try:
        for label, value in (
            ("client", args.client), ("job", args.job), ("episode", args.episode),
            ("sequence", args.sequence), ("shot", args.shot),
        ):
            naming.validate_token(label, value)
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    seq_code = naming.sequence_code(args.job, args.episode, args.sequence)
    code = naming.shot_code(args.job, args.episode, args.sequence, args.shot)

    projects_root = Path(config.get_projects_root())
    shot_dir = projects_root / args.client / args.job / args.episode / args.sequence / code

    print(f"sequence_code : {seq_code}")
    print(f"shot_code     : {code}")
    print(f"shot_dir      : {shot_dir}")
    if args.lookdev:
        print(f"lookdev       : YES — will mark {code} as {seq_code}'s look-dev Shot")

    if args.dry_run:
        print("\n[dry-run] would: ensure sequences row, scaffold ADR-0003 shot tree"
              + (", set lookdev_shot_code" if args.lookdev else ""))
        return 0

    if shot_dir.exists() and any(shot_dir.iterdir()):
        sys.exit(f"error: {shot_dir} already exists and is not empty - refusing to overwrite.")

    dir_preexisted = shot_dir.exists()
    conn = db.connect()
    try:
        project = repository.get_project_by_code(conn, args.client, args.job)
        if not project:
            sys.exit(f"error: {args.client}/{args.job} is not registered - run create-project first.")
        project_id = str(project[0])

        sequence_id, seq_created = repository.ensure_sequence(
            conn, project_id=project_id, sequence_code=seq_code, title=args.seq_title
        )

        prev_lookdev = None
        if args.lookdev:
            prev_lookdev = repository.set_lookdev_shot(conn, sequence_id=sequence_id, shot_code=code)

        scaffold.scaffold_shot_tree(shot_dir)

        conn.commit()
    except SystemExit:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        if not dir_preexisted:
            shutil.rmtree(shot_dir, ignore_errors=True)
        raise
    finally:
        conn.close()

    print(f"\nsequence              : {'CREATED' if seq_created else 'reused'} ({seq_code})")
    if args.lookdev:
        if prev_lookdev and prev_lookdev != code:
            print(f"lookdev_shot_code     : {code}  (replaced previous: {prev_lookdev})")
        else:
            print(f"lookdev_shot_code     : {code}")
    print(f"shot tree             : {shot_dir}")
    print(f"\nnext: drop shot inputs in {shot_dir / 'assets'}, or add another shot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
