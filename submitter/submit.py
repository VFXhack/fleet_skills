"""submit — the Submitter's front door: take ONE already-authored Run by id and
turn it into the Versions it will render (ADR 0016), then dispatch each to a Runner.

The Submitter has exactly one job: submit a validated Run. It does NOT author
(Cast / a future direct-author tool / fixtures make Runs) and it does NOT
orchestrate downstream work (that is the Roustabout, fired by events). So this
tool is deliberately thin:

  1. load the Run (type + spec + params + shot_code) by id
  2. check the validation stamp  ── SEAM: the validator is a separate future tool
  3. EXPAND spec -> N Version rows (this increment)
  4. DISPATCH each Version -> a Runner  ── SEAM: next increment (spends credits /
     hits an external API, so it runs with Andy in the loop, never in self-prove)

One transaction for the expand write. `--dry-run` shows the plan and writes nothing.
"""
from __future__ import annotations

import argparse

from fleet import db
from fleet.style import DIM, console, die
from . import expand as expander
from .writes import write_versions


def check_validated(run: dict) -> tuple[bool, str]:
    """SEAM (Andy's design): a separate `validate` gate stamps a Run at authoring
    time; the Submitter only CHECKS the stamp here. Because Runs are immutable
    (nothing does UPDATE runs; an Override never edits a Run, it re-casts to a new
    run_id) the stamp can never go stale — check once, trust forever.

    The validator tool + its stamp column don't exist yet (they need the Template
    store to validate knob names against). Until then this is a no-op that reports
    the seam, so `submit` never silently implies a check happened that didn't.
    """
    return True, "validation gate not yet enforced (validator is a separate future tool)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="submit",
        description="Submit one authored Run: expand its spec into Versions, then "
                    "dispatch (ADR 0016). Authoring (Cast/direct) makes the Run; this "
                    "submits it.")
    parser.add_argument("run_id", help="the Run's id (uuid) — from cast, or a fixture")
    parser.add_argument("--dry-run", action="store_true",
                        help="show the expansion plan; write nothing")
    args = parser.parse_args(argv)

    conn = db.connect()
    try:
        run = conn.execute(
            "SELECT id, shot_code, type, template_ref, model, tier, mode, params, spec "
            "FROM runs WHERE id = %s", (args.run_id,)
        ).fetchone()
        if run is None:
            die(f"no Run {args.run_id!r} — author it first (e.g. `cast`).")
        cols = ("id", "shot_code", "type", "template_ref", "model", "tier", "mode",
                "params", "spec")
        run = dict(zip(cols, run))

        existing = conn.execute(
            "SELECT count(*) FROM versions WHERE run_id = %s", (args.run_id,)
        ).fetchone()[0]
        if existing:
            die(f"Run already expanded — {existing} Version(s) exist. Expand runs "
                f"once per generation (re-author to make a new one).")

        ok, note = check_validated(run)
        if not ok:
            die(f"Run is not validated: {note}")

        try:
            seeds = expander.expand(
                run_type=run["type"], spec=run["spec"], params=run["params"])
        except expander.SpecError as exc:
            die(f"cannot expand this Run's spec: {exc}")

        _print_plan(run, seeds, note)

        if args.dry_run:
            console.print("[dim]\\[dry-run][/] would write the Versions above; nothing written.")
            return 0

        written = write_versions(conn, run["id"], seeds)
        conn.commit()
    except SystemExit:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    console.print(
        f"\n[bold green]Submitted[/] Run [bold]{run['type']}[/] on "
        f"[bold]{run['shot_code']}[/] -> {len(written)} Version(s): "
        + ", ".join(f"v{n:03d}" for _id, n in written), highlight=False)
    console.print(f"[{DIM}]next (increment 2): dispatch each Version to a Runner "
                  f"— address stays NULL until a take lands (ADR 0013).[/]")
    return 0


def _print_plan(run: dict, seeds, note: str) -> None:
    recipe = " · ".join(x for x in (run["model"], run["tier"], run["mode"]) if x)
    console.print(
        f"Run        : [bold]{run['type']}[/]  [{DIM}]{recipe}[/]\n"
        f"Shot       : [bold]{run['shot_code']}[/]\n"
        f"spec       : {run['spec']}\n"
        f"validation : [{DIM}]{note}[/]\n"
        f"expands to : [bold]{len(seeds)}[/] Version(s)", highlight=False)
    for i, s in enumerate(seeds, start=1):
        console.print(f"   [{DIM}]#{i}[/]  stage={s.stage}  delta={s.delta}",
                      highlight=False)


if __name__ == "__main__":
    raise SystemExit(main())
