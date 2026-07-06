"""submit_demo — author ONE bare, unexpanded Run so `submit` has something to chew on
(the parallel to emit_demo.py). A TEST stand-in for authoring: it inserts a Run with
a real `spec` and NO versions on the fixture's shot 020, then prints its id and the
ready `submit` command.

Why this exists: the real authoring tools don't thread `spec` yet — a `cast` Run has
`spec = '{}'` (see HANDOFF Session-13 open item). Until that authoring slice lands,
this is how you hand `submit` a spec-bearing Run to drive. fleet_test only.

    python -m submitter.submit_demo                 # seed-sweep (3 seeds) -> 3 versions
    python -m submitter.submit_demo control-pass    # -> 1 version
    python -m submitter.submit_demo xy-plot         # 2x4 grid -> 8 versions
"""
from __future__ import annotations

import sys

import psycopg
from psycopg.types.json import Json

from db.fixtures.hoist_demo import assert_test, resolve_dsn, cmd_seed, SHOT2

DEMOS = {
    "seed-sweep": dict(
        template_ref="spellbook/templates/ltx-i2v", model="ltx-2", tier="quality",
        mode="i2v", params={"cfg": 3.5, "lut": "salem-dusk"}, spec={"seeds": [900, 901, 902]}),
    "control-pass": dict(
        template_ref=None, model="depthcrafter", tier=None, mode=None,
        params={"bw": 20}, spec={"method": "depthcrafter-bw20", "params": {"bw": 20}}),
    "xy-plot": dict(
        template_ref="spellbook/templates/ltx-i2v", model="ltx-2", tier="quality",
        mode="i2v", params={"lut": "salem-dusk"},
        spec={"x": {"knob": "lora", "values": [0.2, 0.8]},
              "y": {"knob": "cfg", "from": 3, "to": 4, "steps": 4}}),
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    kind = argv[0] if argv else "seed-sweep"
    if kind not in DEMOS:
        sys.exit(f"unknown demo {kind!r}; choose one of: {', '.join(DEMOS)}")
    d = DEMOS[kind]

    conn = psycopg.connect(assert_test(resolve_dsn()))
    try:
        proj = conn.execute(
            "SELECT id FROM projects WHERE client_code='TEST' AND job_code='SANDBOX'"
        ).fetchone()
        if proj is None:
            print("fixture project missing — seeding it first…")
            conn.close()
            cmd_seed()
            conn = psycopg.connect(assert_test(resolve_dsn()))
            proj = conn.execute(
                "SELECT id FROM projects WHERE client_code='TEST' AND job_code='SANDBOX'"
            ).fetchone()
        project_id = proj[0]

        run_id = conn.execute(
            "INSERT INTO runs (project_id, shot_code, type, template_ref, model, tier, "
            "mode, params, spec) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (project_id, SHOT2, kind, d["template_ref"], d["model"], d["tier"],
             d["mode"], Json(d["params"]), Json(d["spec"]))).fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    print(f"authored a bare {kind} Run on {SHOT2} (spec={d['spec']}, 0 versions)")
    print(f"\n  run_id = {run_id}\n")
    print("drive the Submitter:")
    print(f"  submit {run_id} --dry-run")
    print(f"  submit {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
