"""hoist — lift an approved look-dev Shot's recipe UP into the Sequence Look
(ADR 0020 §6 / 0021). The producer half of the Hoist/Cast pair: Hoist copies a
recipe up (here); Cast clones it back down per Shot (later).

Publish-driven (ADR 0020 §6): Hoist only ever lifts the recipe behind an approved
**Publish** — never a bare Version. You anchor on a Publish, follow its pointer to
the source Version -> its Run, and lift that Run's recipe (plus the Runs that
produced its shared-recipe inputs) into the Look.

What it does, in order (one transaction — a failure writes nothing):
  1. resolve the Sequence's designated look-dev Shot (errors if none).
  2. pick the anchor Publish: the latest for that Shot, or --publish <n>.
  3. walk the recipe graph from the anchor Run: the anchor + (transitively) the
     Run that produces each shared-recipe input. Demand a sharing class for every
     input Role found (the deliberate gate; class is born HERE, ADR 0020 §6).
  4. rebuild the Look fresh (wipe the prior one) -> a Look Run per graph Run, then
     a Look input per binding, lifted by class:
       shared-content -> mirror the content into a scope='sequence' Asset
       shared-recipe  -> link produced_by_look_run_id to the Run that makes it
       per-shot       -> a bare slot (Cast will demand the Shot's own input)
  5. bump look_version.

To Hoist a take that isn't published yet, `promote` it first — that records the
approval as a Publish (the Version keeps its number; nothing re-renders). Then it
is the latest Publish, or target it with --publish.

The look-dev Shot's now-redundant Overrides are cleared (ADR 0020 §6 / 0023):
every attribute just hoisted (a lifted Run's param keys + input Roles, by
run_type) IS the Look's value now, so that Shot's override rows for them are
deleted — it returns to inheriting. Surgical: overrides on attributes not part
of the hoisted recipe survive, and sibling Shots' Overrides are never touched
(the shield). Hoist never rewrites existing takes (ADR 0013).
"""

from __future__ import annotations

import argparse

from rich import box
from rich.table import Table

from . import db, naming, repository
from .style import CLASS_STYLE, GATE_STYLE, cls, console, die

CLASSES = ("shared-content", "shared-recipe", "per-shot")


def _parse_class_map(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated --class Role=CLASS into {role: class}; validate the class."""
    out: dict[str, str] = {}
    for raw in pairs or []:
        if "=" not in raw:
            die(f"--class expects Role=CLASS, got {raw!r}")
        role, klass = raw.split("=", 1)
        role, klass = role.strip(), klass.strip()
        if klass not in CLASSES:
            die(f"class for {role!r} must be one of {CLASSES}, got {klass!r}")
        out[role] = klass
    return out


def _walk_recipe_graph(conn, anchor_run_id, class_map):
    """From the anchor Run, discover the Runs that make up the approved recipe: the
    anchor plus (transitively) the Run producing each *shared-recipe* input. Returns
    (ordered_run_ids, bindings_by_run, unclassified_roles).

    The LIFT descends only through classified shared-recipe edges — a
    shared-content/per-shot input pulls in no producer. But an UNCLASSIFIED
    publish-backed input descends too, for discovery only, so the missing-class
    error lists every Role in one round instead of revealing nested ones (e.g. the
    control-pass 'Source') only after their parent edge is classified. Discovery
    can't pollute the Look: any unclassified Role aborts before the write, and once
    every Role is classified no discovery descent happens."""
    order: list = []
    seen: set = set()
    bindings_by_run: dict = {}
    unclassified: set = set()

    def visit(run_id):
        if run_id in seen:
            return
        seen.add(run_id)
        order.append(run_id)
        bindings = repository.get_run_bindings(conn, run_id)
        bindings_by_run[run_id] = bindings
        for b in bindings:
            cls = class_map.get(b["role"])
            if cls is None:
                unclassified.add(b["role"])
            if (cls == "shared-recipe" or cls is None) and b["pinned_publish_id"]:
                producer = repository.resolve_publish_source_run(conn, b["pinned_publish_id"])
                if producer:
                    visit(producer)

    visit(anchor_run_id)
    return order, bindings_by_run, unclassified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hoist",
        description="Lift the recipe behind an approved Publish up into the Sequence Look (ADR 0020/0021).",
    )
    parser.add_argument("--client", required=True, help="client_code, e.g. WBTV")
    parser.add_argument("--job", required=True, help="job_code (= Project), e.g. AWA")
    parser.add_argument("--sequence", required=True, help="sequence token, e.g. SALEM")
    parser.add_argument("--episode", default="EP01", help="episode token (default EP01)")
    parser.add_argument("--publish", type=int, default=None, metavar="N",
                        help="anchor on Publish p<N> of the look-dev Shot (default: latest Publish)")
    parser.add_argument("--class", dest="classes", action="append", metavar="ROLE=CLASS",
                        help=f"sharing class for an input Role; CLASS in {CLASSES}. Repeatable.")
    parser.add_argument("--dry-run", action="store_true",
                        help="show the anchor + recipe + classification plan; write nothing")
    args = parser.parse_args(argv)

    for label, value in (("client", args.client), ("job", args.job),
                         ("episode", args.episode), ("sequence", args.sequence)):
        try:
            naming.validate_token(label, value)
        except ValueError as exc:
            die(str(exc))

    seq_code = naming.sequence_code(args.job, args.episode, args.sequence)
    class_map = _parse_class_map(args.classes)

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
        if not lookdev_shot_code:
            die(f"{seq_code} has no look-dev Shot - designate one "
                f"(add-shot --lookdev / add-sequence --lookdev) before Hoisting.")

        # 2. anchor Publish: --publish N, else the latest for the look-dev Shot.
        if args.publish is not None:
            anchor = repository.get_publish_by_number(conn, lookdev_shot_code, args.publish)
            if not anchor:
                die(f"{lookdev_shot_code} has no Publish p{args.publish:03d} - "
                    f"check the number (promote a take to create one).")
        else:
            anchor = repository.get_latest_publish(conn, lookdev_shot_code)
            if not anchor:
                die(f"{lookdev_shot_code} has no Publish to Hoist - approve a take first "
                    f"(promote it), then Hoist. Only approved (published) takes can be Hoisted.")
        anchor_publish_id, p_number, _src_version_id, v_number = anchor
        anchor_run_id = repository.resolve_publish_source_run(conn, anchor_publish_id)

        # 3. walk the recipe graph + demand a class for every input Role (the gate).
        run_ids, bindings_by_run, unclassified = _walk_recipe_graph(
            conn, anchor_run_id, class_map)
        if unclassified:
            die(
                "every input Role must be classified before Hoist. Missing --class for: "
                f"[bold]{', '.join(sorted(unclassified))}[/]\n"
                f"  (classes: {', '.join(cls(c) for c in CLASSES)}; re-run with them added)"
            )
        runs = [repository.get_run_for_look(conn, rid) for rid in run_ids]

        anchor_tag = "--publish" if args.publish is not None else "latest"
        console.print(
            f"sequence       : [bold]{seq_code}[/]  "
            f"(look_version {look_version} -> [bold]{look_version + 1}[/])\n"
            f"look-dev Shot  : [bold]{lookdev_shot_code}[/]\n"
            f"anchor Publish : [{GATE_STYLE}]p{p_number:03d}[/] "
            f"(-> v{v_number:03d})  [dim]\\[{anchor_tag}][/]",
            highlight=False)

        plan = Table(box=box.SIMPLE_HEAVY, pad_edge=False)
        plan.add_column("Look Run", style="bold")
        plan.add_column("input Role")
        plan.add_column("sharing class")
        for r in runs:
            detail = " · ".join(x for x in (r["model"], r["mode"]) if x)
            label = f"{r['type']}" + (f"\n[dim]{detail}[/]" if detail else "")
            ordered = sorted(bindings_by_run[r["id"]], key=lambda b: b["role"])
            if not ordered:
                plan.add_row(label, "[dim](no inputs)[/]", "")
            for i, b in enumerate(ordered):
                plan.add_row(label if i == 0 else "", b["role"], cls(class_map[b["role"]]))
            plan.add_section()
        console.print(plan)

        if args.dry_run:
            console.print("[dim]\\[dry-run][/] would rebuild the Look as above; nothing written.")
            return 0

        # ---- WRITE (one txn) ------------------------------------------------
        removed = repository.clear_sequence_look(conn, sequence_id)

        # Pass 1: a Look Run per graph Run, so producer links resolve in pass 2.
        look_run_of: dict = {}
        for ordinal, r in enumerate(runs):
            look_run_of[r["id"]] = repository.insert_look_run(
                conn, sequence_id=sequence_id, run_type=r["type"], stage=r["stage"],
                template_ref=r["template_ref"], model=r["model"], tier=r["tier"],
                mode=r["mode"], params=r["params"], ord=ordinal,
            )

        # Pass 2: a Look input per binding, lifted by class.
        n_inputs = {"shared-content": 0, "shared-recipe": 0, "per-shot": 0}
        seq_assets: set = set()
        for r in runs:
            lrid = look_run_of[r["id"]]
            for b in bindings_by_run[r["id"]]:
                klass = class_map[b["role"]]
                if klass == "shared-content":
                    asset = repository.get_asset(conn, b["asset_id"])
                    pub = b["pinned_publish_id"] or asset["resolved_publish_id"]
                    imp = None if pub else (b["pinned_import_uri"] or asset["import_uri"])
                    seq_asset = repository.ensure_sequence_asset(
                        conn, project_id=project_id, sequence_code=seq_code,
                        name=asset["name"], resolved_publish_id=pub, import_uri=imp,
                        import_meta=asset["import_meta"],
                    )
                    seq_assets.add(seq_asset)
                    repository.insert_look_binding(
                        conn, look_run_id=lrid, role=b["role"],
                        sharing_class="shared-content", asset_id=seq_asset,
                    )
                elif klass == "shared-recipe":
                    if not b["pinned_publish_id"]:
                        die(
                            f"{b['role']} is shared-recipe but its content is not an "
                            f"internal Publish (no producing Run to share). Reclassify it "
                            f"shared-content or per-shot."
                        )
                    producer = look_run_of.get(
                        repository.resolve_publish_source_run(conn, b["pinned_publish_id"]))
                    if not producer:
                        die(
                            f"{b['role']} is shared-recipe but its producing Run is not part "
                            f"of the approved recipe being Hoisted (its Publish must trace back into "
                            f"the anchor's recipe)."
                        )
                    repository.insert_look_binding(
                        conn, look_run_id=lrid, role=b["role"],
                        sharing_class="shared-recipe", produced_by_look_run_id=producer,
                    )
                else:  # per-shot
                    repository.insert_look_binding(
                        conn, look_run_id=lrid, role=b["role"], sharing_class="per-shot",
                    )
                n_inputs[klass] += 1

        # The look-dev Shot's overrides for what was just hoisted are now the
        # Look's own values — clear them (ADR 0020 §6 / 0023). Siblings untouched.
        params_by_type: dict = {}
        roles_by_type: dict = {}
        for r in runs:
            params_by_type.setdefault(r["type"], set()).update((r["params"] or {}).keys())
            roles_by_type.setdefault(r["type"], set()).update(
                b["role"] for b in bindings_by_run[r["id"]])
        cleared = repository.clear_hoisted_overrides(
            conn, sequence_id=sequence_id, shot_code=lookdev_shot_code,
            params_by_type=params_by_type, roles_by_type=roles_by_type)

        new_version = repository.bump_look_version(conn, sequence_id)
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
        f"\n[bold green]Hoisted[/] [bold]{seq_code}[/] from [{GATE_STYLE}]p{p_number:03d}[/] "
        f"-> look_version [bold]{new_version}[/]"
        + (f"  [dim](replaced {removed} prior Look Run(s))[/]" if removed else ""),
        highlight=False)
    console.print(
        f"  Look Runs        : {len(runs)}\n"
        f"  {cls('shared-content')}   : {n_inputs['shared-content']}  "
        f"[dim](+{len(seq_assets)} sequence Asset(s))[/]\n"
        f"  {cls('shared-recipe')}    : {n_inputs['shared-recipe']}\n"
        f"  {cls('per-shot')}         : {n_inputs['per-shot']}",
        highlight=False)
    if cleared:
        console.print(
            f"  cleared          : {cleared} now-redundant override(s) on "
            f"[bold]{lookdev_shot_code}[/] [dim](they became the Look's values - ADR 0023)[/]",
            highlight=False)
    console.print(
        "\n[dim]next: `cast` a sibling Shot from the Look, or re-Hoist to revise. "
        "Sibling Overrides were not touched (the shield).[/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
