"""create-project — scaffold a new Project (ADR 0003 tree), register it in the
provenance DB (ADR 0008), and write the thin manifest (ADR 0006).

Order of operations is chosen so a failure leaves nothing dangling:
  1. resolve config + compute paths, validate inputs
  2. refuse if the dir exists non-empty or the project is already registered
  3. INSERT the projects row (in a transaction, not yet committed)
  4. scaffold the tree + write manifest + project CONTEXT.md
  5. commit
On any failure after step 3, the DB row is rolled back and a freshly-created job
directory is removed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from . import config, db, manifest as manifest_mod, repository, scaffold

CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_code(label: str, value: str) -> None:
    if not CODE_RE.match(value):
        sys.exit(f"error: {label} '{value}' must match [A-Za-z0-9_-]+")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="create-project",
        description="Scaffold + register a new Fleet Project (ADR 0003/0006/0008).",
    )
    parser.add_argument("--client", required=True, help="client_code, e.g. WBTV")
    parser.add_argument("--job", required=True, help="job_code (= Project), e.g. AWA")
    parser.add_argument("--title", required=True, help="human title, e.g. 'Are We Alone'")
    parser.add_argument("--episode", default="EP01", help="first episode code (default EP01)")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen; touch nothing")
    args = parser.parse_args(argv)

    _validate_code("client", args.client)
    _validate_code("job", args.job)
    _validate_code("episode", args.episode)

    projects_root = Path(config.get_projects_root())
    job_dir = projects_root / args.client / args.job
    base_path = manifest_mod.logical_base_path(args.client, args.job)

    print(f"client_code : {args.client}")
    print(f"job_code    : {args.job}")
    print(f"title       : {args.title}")
    print(f"base_path   : {base_path}")
    print(f"job_dir     : {job_dir}")

    if args.dry_run:
        print("\n[dry-run] would: INSERT projects row, scaffold ADR-0003 tree, write manifest + CONTEXT.md")
        return 0

    if job_dir.exists() and any(job_dir.iterdir()):
        sys.exit(f"error: {job_dir} already exists and is not empty - refusing to overwrite.")

    dir_preexisted = job_dir.exists()
    conn = db.connect()
    try:
        existing = repository.get_project_by_code(conn, args.client, args.job)
        if existing:
            sys.exit(f"error: {args.client}/{args.job} already registered (db_project_id={existing[0]}).")

        db_project_id = repository.create_project(
            conn,
            client_code=args.client,
            job_code=args.job,
            title=args.title,
            base_path=base_path,
        )

        scaffold.scaffold_job_tree(job_dir, episode=args.episode)
        manifest = manifest_mod.build_manifest(
            client_code=args.client,
            job_code=args.job,
            title=args.title,
            db_project_id=db_project_id,
        )
        manifest_mod.write_manifest(job_dir, manifest)
        scaffold.write_project_context(
            job_dir,
            title=args.title,
            client_code=args.client,
            job_code=args.job,
            db_project_id=db_project_id,
        )

        conn.commit()
    except SystemExit:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        if not dir_preexisted:
            shutil.rmtree(job_dir, ignore_errors=True)
        raise
    finally:
        conn.close()

    print(f"\ncreated db_project_id : {db_project_id}")
    print(f"manifest              : {job_dir / 'manifest.json'}")
    print(f"\nnext: add a shot, or drop shared assets in {job_dir / 'assets'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
