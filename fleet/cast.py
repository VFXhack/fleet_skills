"""cast — stamp a Shot DOWN from its Sequence Look (ADR 0020 §7 / 0021).

The consumer half of the Hoist/Cast pair (foundry sense: cast a copy from the
master mold). For each Look Run of the Sequence, cast clones a real Run for the
target Shot and resolves its inputs by sharing class:

  shared-content  auto-bind the Sequence-scoped Asset (a Shot Override wins:
                  `override set --role ...` re-points the Role to the Shot's own
                  Asset instead)
  shared-recipe   RE-RUN for this Shot: the producing Look Run is cloned too; its
                  per-Shot take, once landed + auto-published no-look (Roustabout,
                  ADR 0018), is bound in on the next `cast` of the same Shot —
                  cast is CONVERGENT: re-running completes what is now possible
                  and never duplicates.
  per-shot        DEMANDED from the operator: --input ROLE='asset name' names the
                  Shot's own Asset; every missing Role is listed in one round.

Shot Overrides (ADR 0023) are read from the store: a param override merges over
the Look Run's params (override wins); a binding override re-points a Role. The
Look's look_version is stamped into each cloned Run (`runs.cast_from`) so a
take's lineage answers "which Look version made this?".

One transaction — a failure writes nothing. Provenance is immutable: casting at
a NEW look_version creates a fresh generation of Runs (siblings re-run forward,
ADR 0013); the old generation's takes are untouched.
"""

from __future__ import annotations

import argparse

from . import db, naming, repository
from .style import DIM, GATE_STYLE, cls, console, die


def _parse_inputs(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated --input ROLE=NAME into {role: asset_name}."""
    out: dict[str, str] = {}
    for raw in pairs or []:
        if "=" not in raw:
            die(f"--input expects ROLE='asset name', got {raw!r}")
        role, name = raw.split("=", 1)
        out[role.strip()] = name.strip()
    return out


def _pin(asset: dict) -> tuple:
    """An Asset's content pin for a binding: (pinned_publish_id, pinned_import_uri).
    Publish wins if the Asset resolves to one; else its import URI."""
    pub = asset.get("resolved_publish_id") or asset.get("asset_publish_id")
    uri = None if pub else (asset.get("import_uri") or asset.get("asset_import_uri"))
    return pub, uri


def _complete_shared_recipe(conn, *, project_id, shot_code, shot_token, look_runs,
                            bindings_of, run_id_by_ord):
    """Bind every shared-recipe Role whose producer (this Shot's own re-run) has
    published; report the rest as waiting. Idempotent — the convergence step both
    first cast and every re-cast end with. Returns (bound, waiting) lists."""
    ord_of_look_run = {str(lr["id"]): lr["ord"] for lr in look_runs}
    bound, waiting = [], []
    for lr in look_runs:
        consumer_run_id = run_id_by_ord[lr["ord"]]
        for b in bindings_of[lr["ord"]]:
            if b["sharing_class"] != "shared-recipe":
                continue
            if repository.get_binding_for_role(conn, consumer_run_id, b["role"]):
                continue  # already bound (a prior cast converged this Role)
            producer_ord = ord_of_look_run[str(b["produced_by_look_run_id"])]
            producer_run_id = run_id_by_ord[producer_ord]
            publish = repository.get_latest_run_publish(conn, producer_run_id)
            if publish:
                publish_id, p_number = publish
                asset_id = repository.ensure_shot_asset(
                    conn, project_id=project_id, shot_code=shot_code,
                    name=f"{shot_token.lower()} {b['role'].lower()} (cast)",
                    resolved_publish_id=publish_id)
                repository.insert_binding(
                    conn, run_id=consumer_run_id, asset_id=asset_id,
                    role=b["role"], pinned_publish_id=publish_id)
                bound.append((lr, b, p_number))
            else:
                producer = next(x for x in look_runs if x["ord"] == producer_ord)
                waiting.append((lr, b, producer))
    return bound, waiting


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cast",
        description="Cast a Shot from its Sequence Look — clone the Look Runs down, "
                    "resolve inputs by sharing class, honor Shot Overrides (ADR 0020/0021/0023).",
    )
    parser.add_argument("--client", required=True, help="client_code, e.g. WBTV")
    parser.add_argument("--job", required=True, help="job_code (= Project), e.g. AWA")
    parser.add_argument("--sequence", required=True, help="sequence token, e.g. SALEM")
    parser.add_argument("--shot", required=True, help="shot token, e.g. 020")
    parser.add_argument("--episode", default="EP01", help="episode token (default EP01)")
    parser.add_argument("--input", dest="inputs", action="append", metavar="ROLE=NAME",
                        help="satisfy a per-shot Role with the Shot's own Asset (by name). Repeatable.")
    parser.add_argument("--dry-run", action="store_true",
                        help="show the cast plan; write nothing")
    args = parser.parse_args(argv)

    for label, value in (("client", args.client), ("job", args.job),
                         ("episode", args.episode), ("sequence", args.sequence),
                         ("shot", args.shot)):
        try:
            naming.validate_token(label, value)
        except ValueError as exc:
            die(str(exc))

    seq_code = naming.sequence_code(args.job, args.episode, args.sequence)
    shot_code = naming.shot_code(args.job, args.episode, args.sequence, args.shot)
    inputs = _parse_inputs(args.inputs)

    conn = db.connect()
    try:
        project = repository.get_project_by_code(conn, args.client, args.job)
        if not project:
            die(f"{args.client}/{args.job} is not registered - run create-project first.")
        project_id = str(project[0])

        seq = repository.get_sequence(conn, project_id, seq_code)
        if not seq:
            die(f"no Sequence config for {seq_code} - add a shot or run add-sequence first.")
        sequence_id, lookdev_shot_code, look_version = str(seq[0]), seq[2], seq[3]

        look_runs = repository.get_look_runs(conn, sequence_id)
        if not look_runs:
            die(f"{seq_code} has no Look yet - develop the look on its look-dev Shot, "
                f"promote a take, then hoist. Cast clones the Look; there is nothing to clone.")
        bindings_of = {lr["ord"]: repository.get_look_bindings(conn, lr["id"])
                       for lr in look_runs}
        look_types = {lr["type"] for lr in look_runs}

        # Shot Overrides (ADR 0023): param map + role map, keyed by run_type.
        param_ov: dict[str, dict] = {}
        role_ov: dict[str, dict] = {}
        for o in repository.get_shot_overrides(conn, sequence_id, shot_code):
            if o["run_type"] not in look_types:
                console.print(f"[yellow]warning:[/] override targets run_type "
                              f"{o['run_type']!r} which is not in the Look "
                              f"({', '.join(sorted(look_types))}) - ignored. Typo?",
                              highlight=False)
                continue
            if o["param_key"]:
                param_ov.setdefault(o["run_type"], {})[o["param_key"]] = o["param_value"]
            else:
                role_ov.setdefault(o["run_type"], {})[o["role"]] = o

        console.print(
            f"sequence   : [bold]{seq_code}[/]  [{DIM}](look_version {look_version})[/]\n"
            f"cast Shot  : [bold]{shot_code}[/]"
            + (f"  [{DIM}](the look-dev Shot - it inherits from the Look it was "
               f"Hoisted from)[/]" if shot_code == lookdev_shot_code else ""),
            highlight=False)

        existing = repository.get_cast_runs(
            conn, shot_code=shot_code, sequence_code=seq_code, look_version=look_version)

        if existing:
            # Already cast at this look_version -> converge only (idempotent).
            console.print(f"[{DIM}]already Cast at look_version {look_version} "
                          f"({len(existing)} Run(s) exist) - completing pending inputs only.[/]")
            if args.dry_run:
                console.print("[dim]\\[dry-run][/] would check/bind pending shared-recipe inputs.")
                return 0
            run_id_by_ord = {o: str(r["id"]) for o, r in existing.items()}
            bound, waiting = _complete_shared_recipe(
                conn, project_id=project_id, shot_code=shot_code, shot_token=args.shot,
                look_runs=look_runs, bindings_of=bindings_of, run_id_by_ord=run_id_by_ord)
            conn.commit()
            _report_convergence(bound, waiting)
            return 0

        # ---- first cast at this look_version: resolve every input up front ----
        plan = []           # (look_run, [(binding, resolution_markup)], params, ov_keys)
        missing: list = []  # per-shot Roles still owed
        bad_inputs: list = []
        for lr in look_runs:
            resolutions = []
            for b in bindings_of[lr["ord"]]:
                ov = role_ov.get(lr["type"], {}).get(b["role"])
                if b["sharing_class"] == "shared-content":
                    if b["role"] in inputs:
                        bad_inputs.append(
                            (b["role"], "shared-content - inherited from the Sequence; "
                             "to use this Shot's own, `override set --role`"))
                    if ov:
                        resolutions.append((b, f"[yellow]OVERRIDE[/] -> own Asset "
                                               f"[bold]{ov['asset_name']!r}[/]", ov))
                    else:
                        resolutions.append((b, f"sequence Asset [bold]{b['asset_name']!r}[/]", None))
                elif b["sharing_class"] == "per-shot":
                    name = inputs.get(b["role"])
                    if name is None:
                        missing.append(b["role"])
                        resolutions.append((b, "[red]MISSING[/]", None))
                    else:
                        asset = repository.find_asset_by_name(
                            conn, project_id=project_id, shot_code=shot_code, name=name)
                        if asset is None:
                            bad_inputs.append(
                                (b["role"], f"no Asset named {name!r} for {shot_code}"))
                            resolutions.append((b, "[red]UNKNOWN ASSET[/]", None))
                        else:
                            resolutions.append(
                                (b, f"own Asset [bold]{asset['name']!r}[/]", dict(asset)))
                else:  # shared-recipe
                    resolutions.append(
                        (b, f"re-run for this Shot [{DIM}](binds when its take "
                            f"lands + publishes)[/]", None))
            params = dict(lr["params"] or {})
            ov_keys = set(param_ov.get(lr["type"], {}))
            params.update(param_ov.get(lr["type"], {}))
            plan.append((lr, resolutions, params, ov_keys))

        unknown_roles = set(inputs) - {b["role"] for bs in bindings_of.values() for b in bs}
        for role in sorted(unknown_roles):
            bad_inputs.append((role, "not an input Role of any Look Run"))

        _print_plan(plan)

        if missing:
            die("this Shot still owes its per-shot inputs. Missing --input for: "
                f"[bold]{', '.join(sorted(set(missing)))}[/]\n"
                f"  (name the Shot's own Assets: --input Role='asset name'; "
                f"register them first if needed)")
        if bad_inputs:
            die("bad --input / Role usage:\n" + "\n".join(
                f"  [bold]{role}[/]: {why}" for role, why in bad_inputs))

        if args.dry_run:
            console.print("[dim]\\[dry-run][/] would cast the Shot as above; nothing written.")
            return 0

        # ---- WRITE (one txn) ------------------------------------------------
        run_id_by_ord: dict[int, str] = {}
        for lr, resolutions, params, _ov in plan:
            run_id = repository.insert_cast_run(
                conn, project_id=project_id, shot_code=shot_code, run_type=lr["type"],
                template_ref=lr["template_ref"], model=lr["model"], tier=lr["tier"],
                mode=lr["mode"], params=params,
                cast_from={"sequence_code": seq_code, "look_version": look_version,
                           "ord": lr["ord"]},
            )
            run_id_by_ord[lr["ord"]] = run_id
            for b, _markup, resolved in resolutions:
                if b["sharing_class"] == "shared-recipe":
                    continue  # bound by convergence once the re-run publishes
                if b["sharing_class"] == "shared-content" and resolved is None:
                    asset_id = str(b["asset_id"])
                    pub, uri = _pin(b)
                else:  # an override's or --input's own Asset
                    asset = repository.get_asset(conn, str(resolved["asset_id"])) \
                        if "asset_id" in resolved else resolved
                    asset_id = str(asset["id"])
                    pub, uri = _pin(asset)
                repository.insert_binding(conn, run_id=run_id, asset_id=asset_id,
                                          role=b["role"], pinned_publish_id=pub,
                                          pinned_import_uri=uri)

        bound, waiting = _complete_shared_recipe(
            conn, project_id=project_id, shot_code=shot_code, shot_token=args.shot,
            look_runs=look_runs, bindings_of=bindings_of, run_id_by_ord=run_id_by_ord)
        conn.commit()
    except SystemExit:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    n_ov = sum(len(v) for v in param_ov.values()) + sum(len(v) for v in role_ov.values())
    console.print(
        f"\n[bold green]Cast[/] [bold]{shot_code}[/] from [bold]{seq_code}[/] "
        f"look_version [bold]{look_version}[/] -> {len(run_id_by_ord)} Run(s)"
        + (f"  [yellow]({n_ov} override(s) honored)[/]" if n_ov else ""),
        highlight=False)
    _report_convergence(bound, waiting)
    return 0


def _print_plan(plan) -> None:
    """Grouped rows (the Session-11 `inspect` style): one header per cloned Run,
    inputs indented beneath, long detail on its own line."""
    for lr, resolutions, params, ov_keys in plan:
        recipe = " · ".join(x for x in (lr["model"], lr["tier"], lr["mode"]) if x)
        shown = " ".join(
            f"[yellow]{k}={v} (override)[/]" if k in ov_keys else f"{k}={v}"
            for k, v in params.items())
        console.print()
        console.print(f"[bold]{lr['ord']}  {lr['type']}[/]   [{DIM}]{recipe}[/]"
                      + (f"   {shown}" if shown else ""), highlight=False)
        if not resolutions:
            console.print("   [dim](no inputs)[/]")
        role_w = max((len(b["role"]) for b, _m, _r in resolutions), default=0)
        for b, markup, _resolved in resolutions:
            console.print(f"   {b['role']:<{role_w}}   {cls(b['sharing_class'])}   {markup}",
                          highlight=False)
    console.print()


def _report_convergence(bound, waiting) -> None:
    for lr, b, p_number in bound:
        console.print(
            f"  [bold green]bound[/] {b['role']} on Run {lr['ord']} ({lr['type']}) "
            f"<- this Shot's own [{GATE_STYLE}]p{p_number:03d}[/]", highlight=False)
    for lr, b, producer in waiting:
        console.print(
            f"  [yellow]waiting[/] {b['role']} on Run {lr['ord']} ({lr['type']}) "
            f"<- Run {producer['ord']} ({producer['type']}) must land a take and "
            f"publish for this Shot first", highlight=False)
    if waiting:
        console.print(f"\n[{DIM}]next: run the producer(s) (the Roustabout auto-publishes "
                      f"control-pass takes no-look), then re-run the same `cast` - it is "
                      f"convergent: it only binds what is newly possible.[/]")


if __name__ == "__main__":
    raise SystemExit(main())
