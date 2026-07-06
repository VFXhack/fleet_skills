"""dispatch — translate a Run's expanded Versions into concrete Runner requests
(the Submitter's DISPATCH step, ADR 0016 tail / ADR 0013).

This increment is DRY-ONLY (Andy's call, Session 13): it resolves, per Version, the
exact request a Runner would receive — the Magnific model + payload — and prints it.
It spends NOTHING and writes NOTHING. Real execution (call the runner → download →
`record_landed_take` → `VersionRecorded` → the Roustabout reacts) is the next
increment, run one Version at a time with Andy watching.

The Version→request translation is proto-Template. A Version carries only ABSTRACT
knobs (`frozen_submission = {cfg, seed, lut, prompt?}`) plus the Run's `model`/`mode`.
A Runner needs a concrete model + payload (`image_url`, `seed`, `resolution`, …). That
knob→slot mapping is exactly what a Spellbook **Template** will own (ADR 0016). Until
it exists, this adapter maps what it CONFIDENTLY can and lists every hole under
`unresolved` — so the dry pass reveals the Template-shaped gap instead of hiding it.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from fleet import db, repository
from fleet.runners.magnific import MODELS
from fleet.style import DIM, console, die

# proto-Template model resolution (SEAM): (run.model, run.mode) -> Magnific model name.
# The Template will own this; here it's an explicit, honest alias table for what we can
# route today. Anything not here routes to "unresolved" rather than guessing.
MODEL_ALIASES: dict[tuple, str] = {
    ("ltx-2", "i2v"): "ltx-2-fast",
    ("minimax", "i2v"): "minimax-live",
    ("seedance-2.0", "i2v"): "seedance-2.0",
    ("seedance-2.0", "t2v"): "seedance-2.0",
}

# Which Roles can supply the single input image, most-specific first (SEAM: Template
# will declare each Role's slot; this is a sensible default ordering for now).
IMAGE_ROLE_PRIORITY = ("Source", "Start-Frame", "Plate", "Reference", "Character-Sheet")

# frozen knobs that map DIRECTLY onto a runner payload field (same name).
PASSTHROUGH_KNOBS = ("seed", "aspect_ratio", "resolution", "duration")


@dataclass
class RunnerRequest:
    """The concrete request a Version would send to a Runner — or a marked
    non-route when we can't map it yet."""
    version_number: int
    routed: bool
    runner: str | None = None
    model_name: str | None = None
    dispatch: str | None = None          # "rest" | "mcp"
    endpoint: str | None = None          # REST path or MCP tool, for display
    payload: dict = field(default_factory=dict)
    unresolved: list = field(default_factory=list)
    reason: str = ""                     # why not routed / notes


def build_request(run: dict, version: dict, bindings: list[dict]) -> RunnerRequest:
    """Resolve ONE Version into a RunnerRequest. Pure: no I/O, no spend."""
    frozen = version["frozen_submission"] or {}
    num = version["number"]

    model_name = MODEL_ALIASES.get((run["model"], run["mode"]))
    if model_name is None:
        return RunnerRequest(
            version_number=num, routed=False,
            reason=f"no Magnific model for (model={run['model']!r}, mode={run['mode']!r}) "
                   f"— likely a different Runner (e.g. Comfy for depthcrafter), not wired. "
                   f"[SEAM: Template owns model resolution]")
    model = MODELS[model_name]

    payload: dict = {}
    unresolved: list = []

    # prompt — the Template's prompt pattern will supply this; a Version rarely carries it.
    prompt = frozen.get("prompt")
    if prompt:
        payload["prompt"] = prompt
    else:
        unresolved.append("prompt (Template prompt-pattern — not built)")

    # direct passthrough knobs
    for k in PASSTHROUGH_KNOBS:
        if k in frozen:
            payload[k] = frozen[k]

    # input image, if the model needs one
    if model.needs_image:
        uri = None
        chosen_role = None
        by_role = {b["role"]: b["uri"] for b in bindings}
        for role in IMAGE_ROLE_PRIORITY:
            if by_role.get(role):
                uri, chosen_role = by_role[role], role
                break
        if uri:
            slot = "reference_images" if model.image_mode == "reference_images" else "image_url"
            payload[slot] = uri
            payload.setdefault("_image_from_role", chosen_role)
        else:
            unresolved.append("image_url (no image-bearing binding on this Run)")

    # everything else in frozen is an unmapped knob -> passthrough extra, but flagged
    mapped = set(PASSTHROUGH_KNOBS) | {"prompt"}
    extras = {k: v for k, v in frozen.items() if k not in mapped}
    for k, v in extras.items():
        payload[k] = v
    if extras:
        unresolved.append(
            f"knob→slot mapping unverified for: {', '.join(sorted(extras))} "
            f"(passed through as-is until the Template maps them)")

    endpoint = (f"POST /v1/ai/{model.category}/{model.slug}" if model.dispatch == "rest"
                else f"MCP video_generate (slug={model.slug})")
    return RunnerRequest(
        version_number=num, routed=True, runner="magnific", model_name=model_name,
        dispatch=model.dispatch, endpoint=endpoint, payload=payload,
        unresolved=unresolved,
        reason=("MCP-only: an agent runs this via the Magnific MCP tool — the headless "
                "runner cannot (OAuth). [dispatch=mcp]" if model.dispatch == "mcp" else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dispatch",
        description="Resolve an expanded Run's Versions into Runner requests (DRY: "
                    "shows the exact request per Version; spends and writes nothing).")
    parser.add_argument("run_id", help="the Run's id (uuid) — must already be expanded (`submit`)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="(default & only mode this increment) show requests, spend nothing")
    args = parser.parse_args(argv)

    conn = db.connect()
    try:
        run = conn.execute(
            "SELECT id, shot_code, type, model, tier, mode, template_ref FROM runs WHERE id = %s",
            (args.run_id,)).fetchone()
        if run is None:
            die(f"no Run {args.run_id!r}.")
        run = dict(zip(("id", "shot_code", "type", "model", "tier", "mode", "template_ref"), run))

        versions = conn.execute(
            "SELECT number, stage, delta, frozen_submission FROM versions "
            "WHERE run_id = %s ORDER BY number", (args.run_id,)).fetchall()
        if not versions:
            die("this Run has no Versions yet — expand it first: `submit <run_id>`.")
        versions = [dict(zip(("number", "stage", "delta", "frozen_submission"), v)) for v in versions]

        bindings = repository.get_run_bindings(conn, args.run_id)
        requests = [build_request(run, v, bindings) for v in versions]
    finally:
        conn.close()

    _print(run, bindings, requests)
    return 0


def _print(run, bindings, requests) -> None:
    console.print(
        f"Run        : [bold]{run['type']}[/]  [{DIM}]{run['model']} · {run['mode']}[/]\n"
        f"Shot       : [bold]{run['shot_code']}[/]\n"
        f"bindings   : " + (", ".join(f"{b['role']}={b['uri']}" for b in bindings) or "[dim](none)[/]"),
        highlight=False)
    routed = sum(1 for r in requests if r.routed)
    console.print(f"dispatch   : [bold]{routed}/{len(requests)}[/] Version(s) route to a Runner "
                  f"[{DIM}](DRY — nothing sent, nothing spent)[/]\n", highlight=False)
    for r in requests:
        if not r.routed:
            console.print(f"[bold]v{r.version_number:03d}[/]  [yellow]NOT ROUTED[/] — {r.reason}",
                          highlight=False)
            continue
        disp = f"[{'cyan' if r.dispatch=='rest' else 'yellow'}]{r.dispatch}[/]"
        console.print(f"[bold]v{r.version_number:03d}[/]  runner=[bold]{r.runner}[/] "
                      f"model=[bold]{r.model_name}[/] {disp}", highlight=False)
        console.print(f"   {r.endpoint}", highlight=False)
        for k, v in r.payload.items():
            if k == "_image_from_role":
                continue
            tag = f"  [{DIM}](image from Role {r.payload['_image_from_role']})[/]" \
                if k in ("image_url", "reference_images") and "_image_from_role" in r.payload else ""
            console.print(f"     {k}: {v}{tag}", highlight=False)
        if r.reason:
            console.print(f"   [{DIM}]{r.reason}[/]", highlight=False)
        for u in r.unresolved:
            console.print(f"   [yellow]unresolved:[/] {u}", highlight=False)
        console.print()
    console.print(f"[{DIM}]next increment: execute one routed Version for real (you watching) -> "
                  f"download -> record_landed_take -> VersionRecorded -> Roustabout.[/]")


if __name__ == "__main__":
    raise SystemExit(main())
