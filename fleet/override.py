"""override — declare, list, or clear a Shot's Overrides (ADR 0020 §8 / 0023).

An Override is a Shot's local value for an attribute it inherits from the
Sequence Look, AND a shield: the Shot stops following later Sequence-wide
changes to that attribute. Cast reads this store and applies it (override
wins); a Hoist never disturbs a sibling's Overrides.

Two forms, one row each (ADR 0023):
  param override    override set ... --run-type seed-sweep --param cfg=4.0
  binding override  override set ... --run-type seed-sweep --role Character-Sheet --asset 'my sheet'

`clear` deletes the row — the Shot starts following the Sequence again on its
next Cast. `list` answers "who deviates from the Look?" before a Hoist.

Overrides are keyed by codes (shot_code, run_type) — declaring one does not
require the Look to exist yet, but Cast warns if an override's run_type matches
no Look Run (typo protection).
"""

from __future__ import annotations

import argparse
import json

from rich import box
from rich.table import Table

from . import db, naming, repository
from .style import DIM, console, die


def _parse_param(raw: str) -> tuple[str, object]:
    """KEY=VALUE -> (key, value); the value is JSON if it parses (4.0 -> float,
    true -> bool, [..] -> list), else the literal string (salem-dusk)."""
    if "=" not in raw:
        die(f"--param expects KEY=VALUE, got {raw!r}")
    key, text = raw.split("=", 1)
    key, text = key.strip(), text.strip()
    if not key:
        die(f"--param has an empty KEY in {raw!r}")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = text
    return key, value


def _fmt_value(value) -> str:
    return json.dumps(value) if not isinstance(value, str) else value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="override",
        description="Declare/list/clear a Shot's Overrides — local value + shield (ADR 0023).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(p, need_shot: bool):
        p.add_argument("--client", required=True, help="client_code, e.g. WBTV")
        p.add_argument("--job", required=True, help="job_code (= Project), e.g. AWA")
        p.add_argument("--sequence", required=True, help="sequence token, e.g. SALEM")
        p.add_argument("--episode", default="EP01", help="episode token (default EP01)")
        p.add_argument("--shot", required=need_shot,
                       help="shot token, e.g. 020" + ("" if need_shot else " (list: optional filter)"))

    p_set = sub.add_parser("set", help="declare an override (upserts)")
    add_common(p_set, need_shot=True)
    p_set.add_argument("--run-type", required=True,
                       help="the targeted Look Run's type, e.g. seed-sweep / control-pass")
    p_set.add_argument("--param", metavar="KEY=VALUE",
                       help="param override, e.g. cfg=4.0 (VALUE parsed as JSON, else string)")
    p_set.add_argument("--role", help="binding override: the Role to re-point, e.g. Character-Sheet")
    p_set.add_argument("--asset", help="binding override: the Shot's own Asset (name), bound instead")

    p_list = sub.add_parser("list", help="show who deviates from the Look")
    add_common(p_list, need_shot=False)

    p_clear = sub.add_parser("clear", help="delete an override — follow the Sequence again")
    add_common(p_clear, need_shot=True)
    p_clear.add_argument("--run-type", required=True)
    p_clear.add_argument("--param", metavar="KEY", help="clear this param override")
    p_clear.add_argument("--role", help="clear this binding override")

    args = parser.parse_args(argv)

    tokens = [("client", args.client), ("job", args.job),
              ("episode", args.episode), ("sequence", args.sequence)]
    if args.shot:
        tokens.append(("shot", args.shot))
    for label, value in tokens:
        try:
            naming.validate_token(label, value)
        except ValueError as exc:
            die(str(exc))

    seq_code = naming.sequence_code(args.job, args.episode, args.sequence)
    shot_code = (naming.shot_code(args.job, args.episode, args.sequence, args.shot)
                 if args.shot else None)

    if args.cmd == "set":
        if bool(args.param) == bool(args.role or args.asset):
            die("set takes exactly one form: --param KEY=VALUE, or --role ROLE --asset NAME")
        if args.role and not args.asset or args.asset and not args.role:
            die("a binding override needs both --role and --asset")

    if args.cmd == "clear" and bool(args.param) == bool(args.role):
        die("clear takes exactly one of --param KEY / --role ROLE")

    conn = db.connect()
    try:
        project = repository.get_project_by_code(conn, args.client, args.job)
        if not project:
            die(f"{args.client}/{args.job} is not registered - run create-project first.")
        project_id = str(project[0])
        seq = repository.get_sequence(conn, project_id, seq_code)
        if not seq:
            die(f"no Sequence config for {seq_code} - add a shot or run add-sequence first.")
        sequence_id = str(seq[0])

        if args.cmd == "set":
            if args.param:
                key, value = _parse_param(args.param)
                created = repository.set_param_override(
                    conn, sequence_id=sequence_id, shot_code=shot_code,
                    run_type=args.run_type, param_key=key, param_value=value)
                detail = f"{args.run_type}.{key} = [bold]{_fmt_value(value)}[/]"
            else:
                asset = repository.find_asset_by_name(
                    conn, project_id=project_id, shot_code=shot_code, name=args.asset)
                if not asset:
                    die(f"no Asset named {args.asset!r} for {shot_code} "
                        f"(looked at its shot-scoped assets, then job-scoped).")
                created = repository.set_role_override(
                    conn, sequence_id=sequence_id, shot_code=shot_code,
                    run_type=args.run_type, role=args.role, asset_id=str(asset["id"]))
                detail = (f"{args.run_type}.{args.role} -> [bold]{asset['name']!r}[/] "
                          f"[{DIM}]({asset['scope']} asset)[/]")
            conn.commit()
            verb = "set" if created else "updated"
            console.print(f"[bold green]override {verb}[/] on [bold]{shot_code}[/]: {detail}",
                          highlight=False)
            console.print(f"[{DIM}]local value + shield: this Shot stops following the "
                          f"Sequence for that attribute until you `override clear` it.[/]")

        elif args.cmd == "clear":
            removed = repository.clear_override(
                conn, sequence_id=sequence_id, shot_code=shot_code,
                run_type=args.run_type, param_key=args.param, role=args.role)
            conn.commit()
            attr = f"{args.run_type}.{args.param or args.role}"
            if not removed:
                die(f"{shot_code} has no override on {attr} - nothing to clear "
                    f"(see `override list`).")
            console.print(f"[bold green]override cleared[/] on [bold]{shot_code}[/]: {attr} - "
                          f"the Shot follows the Sequence again on its next Cast.",
                          highlight=False)

        else:  # list
            rows = repository.get_shot_overrides(conn, sequence_id, shot_code)
            scope = shot_code or seq_code
            if not rows:
                console.print(f"[bold]{scope}[/] has no overrides - every Shot follows the Look.",
                              highlight=False)
                return 0
            table = Table(box=box.SIMPLE_HEAVY, pad_edge=False,
                          title=f"overrides - {scope}", title_justify="left")
            table.add_column("Shot", style="bold")
            table.add_column("Look Run")
            table.add_column("attribute")
            table.add_column("local value")
            prev_shot = None
            for r in rows:
                shot = r["shot_code"] if r["shot_code"] != prev_shot else ""
                prev_shot = r["shot_code"]
                if r["param_key"]:
                    attr, val = r["param_key"], _fmt_value(r["param_value"])
                else:
                    attr, val = r["role"], f"{r['asset_name']!r}"
                table.add_row(shot, r["run_type"], attr, f"[yellow]{val}[/]")
            console.print(table)
            console.print(f"[{DIM}]each row = a local value + a shield: Hoist/Cast will not "
                          f"move that Shot off it.[/]")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
