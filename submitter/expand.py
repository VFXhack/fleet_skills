"""Submitter EXPAND — turn a Run's typed `spec` into the N Versions it will render
(ADR 0016). Pure: no DB, no side effects — `expand(run)` maps the authoring recipe
(`type` + `spec` + `params`) to a list of Version seeds, each carrying its resolved
`delta` (the swept value for this take) and a `frozen_submission` snapshot (ADR 0007).

This is the isolable core of the Submitter's one job. The DB write (allocate `v###`,
INSERT) lives in writes.py; dispatch to a Runner is a later increment. Keeping expand
a pure function means the whole sweep grammar (ADR 0016) is unit-testable without a
database and reproducible forever.

`spec` conventions (ADR 0016):
  * sweep `values` are stored EXPLICIT — range sugar ({base,count}/{from,to,steps})
    is expanded HERE at submit time, so the Version list never depends on re-deriving
    a range later.
  * `steps`/`count` count DATA POINTS (inclusive endpoints), not intervals.
  * knob addressing is a flat param key the Template exposes (`seed`, `cfg`, …).

frozen_submission is PROVISIONAL for now: params ⊕ the operation identity ⊕ this
version's delta. The *fully* resolved payload (Template prompt pattern → the exact
Comfy/API body) resolves when the Spellbook/Template store exists — marked as a seam.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionSeed:
    """One expanded take, before it gets a `v###` and a DB row.

    stage  — ADR 0003 storage bucket / versions.stage CHECK (render|upscale|comp).
    delta  — the varied value(s) that distinguish this take (e.g. {"seed": 778}).
    frozen_submission — provisional immutable snapshot of what will be sent.
    """
    stage: str
    delta: dict
    frozen_submission: dict


class SpecError(ValueError):
    """The spec is malformed for its run type (the Submitter's own validation of
    spec SHAPE — distinct from the future Template knob-name validation gate)."""


# ---- range sugar → explicit value list (ADR 0016: store EXPLICIT) ---------------

def _seed_values(spec: dict) -> list[int]:
    """seed-sweep seeds: explicit `{seeds:[…]}`, or sugar `{base,count}` (base,
    base+1, …) / `{random,count}`. Returns the resolved explicit list."""
    if "seeds" in spec:
        seeds = spec["seeds"]
        if not isinstance(seeds, list) or not seeds:
            raise SpecError("seed-sweep: `seeds` must be a non-empty list")
        return list(seeds)
    if "base" in spec and "count" in spec:
        base, count = int(spec["base"]), int(spec["count"])
        if count < 1:
            raise SpecError("seed-sweep: `count` must be >= 1")
        return [base + i for i in range(count)]
    raise SpecError("seed-sweep spec needs `seeds:[…]` or `{base,count}`")


def _linspace(lo: float, hi: float, steps: int) -> list[float]:
    """`steps` DATA POINTS inclusive of both endpoints (ADR 0016): 3–4 ×4 =
    [3.0, 3.33, 3.67, 4.0]; ×1 = [lo]."""
    if steps < 1:
        raise SpecError("axis `steps` must be >= 1")
    if steps == 1:
        return [lo]
    return [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]


def _axis_values(axis: dict) -> list:
    """An xy-plot axis: explicit `{knob, values:[…]}` or sugar
    `{knob, from, to, steps}`. Returns the explicit value list."""
    if "values" in axis:
        vals = axis["values"]
        if not isinstance(vals, list) or not vals:
            raise SpecError("axis `values` must be a non-empty list")
        return list(vals)
    if {"from", "to", "steps"} <= set(axis):
        return _linspace(float(axis["from"]), float(axis["to"]), int(axis["steps"]))
    raise SpecError("axis needs `values:[…]` or `{from,to,steps}`")


# ---- per-type expanders: spec → [VersionSeed] -----------------------------------
# Each returns the deltas; frozen_submission is composed centrally in expand().

def _expand_seed_sweep(spec, params):
    return "render", [{"seed": s} for s in _seed_values(spec)]


def _expand_prompt_variation(spec, params):
    knob = spec.get("knob")
    variants = spec.get("variants")
    if not knob or not isinstance(variants, list) or not variants:
        raise SpecError("prompt-variation needs `knob` and non-empty `variants:[{label,value}]`")
    deltas = []
    for v in variants:
        if "value" not in v:
            raise SpecError("each prompt-variation variant needs a `value`")
        d = {knob: v["value"]}
        if "label" in v:
            d["_label"] = v["label"]
        deltas.append(d)
    return "render", deltas


def _expand_xy_plot(spec, params):
    x, y = spec.get("x"), spec.get("y")
    if not isinstance(x, dict) or not isinstance(y, dict):
        raise SpecError("xy-plot needs `x` and `y` axis objects")
    xk, yk = x.get("knob"), y.get("knob")
    if not xk or not yk:
        raise SpecError("xy-plot axes each need a `knob`")
    deltas = []
    for xv in _axis_values(x):          # row-major: y within x
        for yv in _axis_values(y):
            deltas.append({xk: xv, yk: yv})
    return "render", deltas


def _expand_refine(spec, params):
    changes = spec.get("changes", {})
    if not isinstance(changes, dict):
        raise SpecError("refine `changes` must be an object")
    return "render", [dict(changes)]     # a single refined take (1 version)


def _expand_comp(spec, params):
    if "script" not in spec:
        raise SpecError("comp needs a `script` (.nk reference)")
    return "comp", [{"script": spec["script"]}]


def _expand_upscale(spec, params):
    if "model" not in spec:
        raise SpecError("upscale needs a `model`")
    delta = {"model": spec["model"]}
    delta.update(spec.get("params", {}))
    return "upscale", [delta]


def _expand_control_pass(spec, params):
    if "method" not in spec:
        raise SpecError("control-pass needs a `method` (the variant Spell)")
    delta = {"method": spec["method"]}
    delta.update(spec.get("params", {}))
    return "render", [delta]              # 1 → its control Publish (ADR 0017)


EXPANDERS = {
    "seed-sweep": _expand_seed_sweep,
    "prompt-variation": _expand_prompt_variation,
    "xy-plot": _expand_xy_plot,
    "refine": _expand_refine,
    "comp": _expand_comp,
    "upscale": _expand_upscale,
    "control-pass": _expand_control_pass,
}


def expand(*, run_type: str, spec: dict, params: dict) -> list[VersionSeed]:
    """Expand one Run into its Version seeds (ADR 0016). Raises SpecError on a
    malformed spec, KeyError-free unknown-type guard included.

    frozen_submission = params ⊕ delta (delta wins). It's the per-version immutable
    snapshot (ADR 0007); the `_label` sugar key is dropped from the frozen payload
    (it's display-only) but kept in `delta` for provenance.
    """
    expander = EXPANDERS.get(run_type)
    if expander is None:
        raise SpecError(
            f"unknown run type {run_type!r}; expected one of {', '.join(sorted(EXPANDERS))}")
    spec = spec or {}
    params = params or {}
    stage, deltas = expander(spec, params)
    seeds = []
    for delta in deltas:
        payload = {**params, **{k: v for k, v in delta.items() if k != "_label"}}
        seeds.append(VersionSeed(stage=stage, delta=delta, frozen_submission=payload))
    return seeds
