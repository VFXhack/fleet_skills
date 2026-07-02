"""Hoist demo fixture for fleet_test — seed / inspect / reset.

The test case behind the `hoist` tool's proof (Session 11): a look-dev Shot
whose recipe exercises all three sharing classes (ADR 0020 §1), so a Hoist has
one of each to lift:

  SANDBOX_EP01_SALEM_010 (look-dev Shot of sequence SANDBOX_EP01_SALEM)
    control-pass Run (depthcrafter)  <- Source: the shot's own plate
        -> v001 (landed) -> p001  (the depth Publish)
    seed-sweep Run (ltx-2 i2v):
        Character-Sheet -> job Asset 'main character sheet' (Import)
        Depth-Pass      -> shot Asset 'salem 010 depth' pinned to p001
        Lipsync-Dialog  -> shot Asset 'salem 010 dialog' (Import)
        -> v002, v003 (landed); hero v003 promoted -> p002 (latest Publish)

The seed also registers sibling-Shot 020's own per-shot inputs (its plate +
dialog Assets), so a `cast` of SANDBOX_EP01_SALEM_020 has --input material.

Usage (from the repo root, venv python):
  python -m db.fixtures.hoist_demo seed      # insert the fixture (refuses if present)
  python -m db.fixtures.hoist_demo inspect   # dump the Sequence Look Hoist wrote
  python -m db.fixtures.hoist_demo land SANDBOX_EP01_SALEM_020
                                             # simulate farm + Roustabout: land a take for
                                             #   each cast control-pass Run of that Shot
                                             #   with none, and auto-publish it no-look
  python -m db.fixtures.hoist_demo reset     # TRUNCATE every table (fleet_test only)
  python -m db.fixtures.hoist_demo dsn       # print the resolved fleet_test DSN, for
                                             #   $env:FLEET_DB_DSN (test_db.sh dsn twin)

DSN: $FLEET_DB_DSN if set, else ~/.fleet/config.toml [db].dsn with the database
name swapped to fleet_test. seed/reset REFUSE any DSN not targeting fleet_test
(same guard as db/test_db.sh) — this can never touch prod.
"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from fleet.style import DIM, cls, console, die

TEST_DB = "fleet_test"
SHOT = "SANDBOX_EP01_SALEM_010"
SHOT2 = "SANDBOX_EP01_SALEM_020"
SEQ = "SANDBOX_EP01_SALEM"
TABLES = ("deliveries", "publishes", "versions", "bindings", "shot_overrides",
          "sequence_look_bindings", "sequence_look_runs", "sequences",
          "assets", "runs", "events", "projects")


def config_test_dsn() -> str:
    """The fleet_test DSN derived from ~/.fleet/config.toml (env var ignored) —
    what `dsn` prints, so a stale/broken $FLEET_DB_DSN can never echo back."""
    cfg = Path.home() / ".fleet" / "config.toml"
    with cfg.open("rb") as fh:
        dsn = tomllib.load(fh)["db"]["dsn"]
    if "dbname=" in dsn:
        return re.sub(r"dbname=fleet(?![_a-zA-Z])", f"dbname={TEST_DB}", dsn)
    return re.sub(r"/fleet(\?|$)", rf"/{TEST_DB}\1", dsn)


def resolve_dsn() -> str:
    return os.environ.get("FLEET_DB_DSN") or config_test_dsn()


def assert_test(dsn: str) -> str:
    try:
        dbname = psycopg.conninfo.conninfo_to_dict(dsn).get("dbname")
    except psycopg.ProgrammingError as exc:
        sys.exit(f"REFUSING: $FLEET_DB_DSN is not a valid DSN ({exc}). "
                 f"Set it with:  $env:FLEET_DB_DSN = & python -m db.fixtures.hoist_demo dsn")
    if dbname != TEST_DB:
        sys.exit(f"REFUSING: resolved DSN targets dbname={dbname!r}, not {TEST_DB}.")
    return dsn


def cmd_seed() -> None:
    conn = psycopg.connect(assert_test(resolve_dsn()))
    try:
        if conn.execute(
            "SELECT 1 FROM projects WHERE client_code='TEST' AND job_code='SANDBOX'"
        ).fetchone():
            sys.exit("fixture already present — run `reset` first")

        (project_id,) = conn.execute(
            "INSERT INTO projects (client_code, job_code, title, base_path) "
            "VALUES ('TEST','SANDBOX','Hoist proof sandbox','fleet:/projects/TEST/SANDBOX/') "
            "RETURNING id").fetchone()
        conn.execute(
            "INSERT INTO sequences (project_id, sequence_code, title, lookdev_shot_code) "
            "VALUES (%s, %s, 'Salem exteriors', %s)", (project_id, SEQ, SHOT))

        # assets ------------------------------------------------------------
        (char_sheet,) = conn.execute(
            "INSERT INTO assets (project_id, scope, name, import_uri) "
            "VALUES (%s,'job','main character sheet',"
            "'fleet:/projects/TEST/SANDBOX/assets/main_character_sheet.png') RETURNING id",
            (project_id,)).fetchone()
        (plate,) = conn.execute(
            "INSERT INTO assets (project_id, scope, shot_code, name, import_uri) "
            "VALUES (%s,'shot',%s,'salem 010 plate',"
            "'fleet:/projects/TEST/SANDBOX/EP01/SALEM/010/assets/plate.mov') RETURNING id",
            (project_id, SHOT)).fetchone()
        (dialog,) = conn.execute(
            "INSERT INTO assets (project_id, scope, shot_code, name, import_uri) "
            "VALUES (%s,'shot',%s,'salem 010 dialog',"
            "'fleet:/projects/TEST/SANDBOX/EP01/SALEM/010/assets/dialog.wav') RETURNING id",
            (project_id, SHOT)).fetchone()

        # control-pass run: plate -> depth, v001 -> p001 ----------------------
        (cp_run,) = conn.execute(
            "INSERT INTO runs (project_id, shot_code, type, model, params, spec) "
            "VALUES (%s,%s,'control-pass','depthcrafter',%s,%s) RETURNING id",
            (project_id, SHOT, Json({"bw": 20}),
             Json({"method": "depthcrafter-bw20"}))).fetchone()
        conn.execute(
            "INSERT INTO bindings (run_id, asset_id, pinned_import_uri, role) "
            "VALUES (%s,%s,%s,'Source')",
            (cp_run, plate, "fleet:/projects/TEST/SANDBOX/EP01/SALEM/010/assets/plate.mov"))
        (v001,) = conn.execute(
            "INSERT INTO versions (run_id, shot_code, number, stage, frozen_submission, address) "
            "VALUES (%s,%s,1,'render',%s,'huxley:/renders/SANDBOX/SALEM_010/v001_depth.mp4') "
            "RETURNING id",
            (cp_run, SHOT, Json({"method": "depthcrafter-bw20", "bw": 20}))).fetchone()
        (p001,) = conn.execute(
            "INSERT INTO publishes (source_version_id, shot_code, number, path) "
            "VALUES (%s,%s,1,'fleet:/projects/TEST/SANDBOX/EP01/SALEM/010/publishes/p001_depth.mp4') "
            "RETURNING id", (v001, SHOT)).fetchone()
        (depth_asset,) = conn.execute(
            "INSERT INTO assets (project_id, scope, shot_code, name, resolved_publish_id) "
            "VALUES (%s,'shot',%s,'salem 010 depth',%s) RETURNING id",
            (project_id, SHOT, p001)).fetchone()

        # render run: 3-role recipe, v002/v003, hero v003 -> p002 -------------
        (render_run,) = conn.execute(
            "INSERT INTO runs (project_id, shot_code, type, template_ref, model, tier, mode, params, spec) "
            "VALUES (%s,%s,'seed-sweep','spellbook/templates/ltx-i2v-dialog','ltx-2','quality','i2v',%s,%s) "
            "RETURNING id",
            (project_id, SHOT, Json({"cfg": 3.5, "lut": "salem-dusk"}),
             Json({"seeds": [777, 778]}))).fetchone()
        for asset_id, pub, uri, role in (
            (char_sheet, None,
             "fleet:/projects/TEST/SANDBOX/assets/main_character_sheet.png", "Character-Sheet"),
            (depth_asset, p001, None, "Depth-Pass"),
            (dialog, None,
             "fleet:/projects/TEST/SANDBOX/EP01/SALEM/010/assets/dialog.wav", "Lipsync-Dialog"),
        ):
            conn.execute(
                "INSERT INTO bindings (run_id, asset_id, pinned_publish_id, pinned_import_uri, role) "
                "VALUES (%s,%s,%s,%s,%s)", (render_run, asset_id, pub, uri, role))
        last_version = None
        for n, seed in ((2, 777), (3, 778)):
            (last_version,) = conn.execute(
                "INSERT INTO versions (run_id, shot_code, number, stage, delta, frozen_submission, address) "
                "VALUES (%s,%s,%s,'render',%s,%s,%s) RETURNING id",
                (render_run, SHOT, n, Json({"seed": seed}),
                 Json({"prompt": "salem exterior, dusk", "seed": seed}),
                 f"huxley:/renders/SANDBOX/SALEM_010/v00{n}.mp4")).fetchone()
        conn.execute(
            "INSERT INTO publishes (source_version_id, shot_code, number, path) "
            "VALUES (%s,%s,2,'fleet:/projects/TEST/SANDBOX/EP01/SALEM/010/publishes/p002_hero.mp4')",
            (last_version, SHOT))

        # sibling Shot 020's own per-shot inputs, so a `cast` has --input material
        for name, fname in (("salem 020 plate", "plate.mov"), ("salem 020 dialog", "dialog.wav")):
            conn.execute(
                "INSERT INTO assets (project_id, scope, shot_code, name, import_uri) "
                "VALUES (%s,'shot',%s,%s,%s)",
                (project_id, SHOT2, name,
                 f"fleet:/projects/TEST/SANDBOX/EP01/SALEM/020/assets/{fname}"))

        conn.commit()
        print(f"seeded: project TEST/SANDBOX, sequence {SEQ} (look-dev {SHOT})")
        print("  p001 = depth control-pass publish (v001)")
        print("  p002 = hero render publish (v003)  <- latest = default Hoist anchor")
        print(f"  {SHOT2}: own plate + dialog assets registered (cast --input material)")
    finally:
        conn.close()


def cmd_inspect() -> None:
    conn = psycopg.connect(assert_test(resolve_dsn()), row_factory=dict_row)
    try:
        seq = conn.execute(
            "SELECT id, sequence_code, lookdev_shot_code, look_version FROM sequences "
            "WHERE sequence_code=%s", (SEQ,)).fetchone()
        if not seq:
            die("no fixture sequence — run `seed` first")
        console.print(
            f"sequence [bold]{seq['sequence_code']}[/]   "
            f"look_version [bold]{seq['look_version']}[/]   "
            f"look-dev [bold]{seq['lookdev_shot_code']}[/]",
            highlight=False)
        runs = conn.execute(
            "SELECT id, type, stage, template_ref, model, tier, mode, params, ord "
            "FROM sequence_look_runs WHERE sequence_id=%s ORDER BY ord",
            (seq["id"],)).fetchall()
        if not runs:
            console.print("[dim](no Look yet — run hoist)[/]")

        # grouped rows, not a wide table: one header line per Look Run, inputs
        # indented beneath, source detail on its own line so paths never truncate.
        bindings_of = {
            r["id"]: conn.execute(
                "SELECT b.role, b.sharing_class, b.produced_by_look_run_id, "
                "       a.name AS a_name, a.import_uri AS a_uri, a.resolved_publish_id AS a_pub "
                "FROM sequence_look_bindings b LEFT JOIN assets a ON a.id = b.asset_id "
                "WHERE b.look_run_id=%s ORDER BY b.role", (r["id"],)).fetchall()
            for r in runs
        }
        role_w = max((len(b["role"]) for bs in bindings_of.values() for b in bs), default=0)
        for r in runs:
            recipe = " · ".join(x for x in (r["model"], r["tier"], r["mode"]) if x)
            params = " ".join(f"{k}={v}" for k, v in (r["params"] or {}).items())
            head = f"[bold]{r['ord']}  {r['type']}[/]"
            pad = " " * (len(f"{r['ord']}  {r['type']}") + 3)
            console.print()
            console.print(f"{head}   [{DIM}]{recipe}[/]"
                          + (f"   [{DIM}]{params}[/]" if params else ""), highlight=False)
            if r["template_ref"]:
                console.print(f"{pad}[{DIM}]{r['template_ref']}[/]", highlight=False)
            console.print()
            if not bindings_of[r["id"]]:
                console.print("   [dim](no inputs)[/]")
            for b in bindings_of[r["id"]]:
                console.print(f"   {b['role']:<{role_w}}   {cls(b['sharing_class'])}",
                              highlight=False)
                if b["sharing_class"] == "shared-content":
                    console.print(f"       sequence Asset [bold]{b['a_name']!r}[/]", highlight=False)
                    content = b["a_uri"] or f"publish {b['a_pub']}"
                    console.print(f"       [{DIM}]{content}[/]", highlight=False)
                elif b["sharing_class"] == "shared-recipe":
                    src = next((f"re-run Look Run [bold]{x['ord']}[/] ({x['type']}) per Shot"
                                for x in runs
                                if str(x["id"]) == str(b["produced_by_look_run_id"])), "??")
                    console.print(f"       {src}", highlight=False)
                else:
                    console.print("       [dim](each Shot supplies its own)[/]")
        console.print()
        n = conn.execute("SELECT count(*) FROM assets WHERE scope='sequence'").fetchone()
        console.print(f"sequence-scoped assets: [bold]{n['count']}[/]")
    finally:
        conn.close()


def cmd_land(shot_code: str) -> None:
    """Simulate the render farm + the Roustabout for a cast Shot: every cast
    control-pass Run of the Shot that has no versions gets one landed take
    (a fake but addressable render) and its no-look auto-publish (ADR 0018:
    control-pass AND version_count==1 -> auto-publish). Creative runs (the
    seed-sweep) are deliberately NOT touched — picking a take is judgment."""
    conn = psycopg.connect(assert_test(resolve_dsn()), row_factory=dict_row)
    try:
        runs = conn.execute(
            "SELECT r.id, r.type FROM runs r "
            "WHERE r.shot_code=%s AND r.cast_from IS NOT NULL AND r.type='control-pass' "
            "  AND NOT EXISTS (SELECT 1 FROM versions v WHERE v.run_id = r.id) "
            "ORDER BY r.created_at", (shot_code,)).fetchall()
        if not runs:
            die(f"nothing to land: {shot_code} has no cast control-pass Run without "
                f"a take (cast it first, or it already landed)")
        for r in runs:
            v_num = conn.execute(
                "SELECT COALESCE(MAX(number),0)+1 AS n FROM versions WHERE shot_code=%s",
                (shot_code,)).fetchone()["n"]
            vid = conn.execute(
                "INSERT INTO versions (run_id, shot_code, number, stage, frozen_submission, address) "
                "VALUES (%s,%s,%s,'render',%s,%s) RETURNING id",
                (r["id"], shot_code, v_num, Json({"simulated": True}),
                 f"huxley:/renders/SANDBOX/{shot_code}/v{v_num:03d}_depth.mp4"),
            ).fetchone()["id"]
            p_num = conn.execute(
                "SELECT COALESCE(MAX(number),0)+1 AS n FROM publishes WHERE shot_code=%s",
                (shot_code,)).fetchone()["n"]
            conn.execute(
                "INSERT INTO publishes (source_version_id, shot_code, number, path) "
                "VALUES (%s,%s,%s,%s)",
                (vid, shot_code, p_num,
                 f"fleet:/projects/TEST/SANDBOX/EP01/SALEM/020/publishes/p{p_num:03d}_depth.mp4"))
            console.print(
                f"landed [bold]{shot_code}[/] {r['type']}: v{v_num:03d} -> "
                f"auto-published p{p_num:03d} [dim](as the Roustabout would, no-look)[/]",
                highlight=False)
        conn.commit()
        console.print("[dim]next: re-run the same `cast` - it binds what is now possible.[/]")
    finally:
        conn.close()


def cmd_reset() -> None:
    conn = psycopg.connect(assert_test(resolve_dsn()))
    try:
        conn.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE")
        conn.commit()
        print(f"reset OK — {TEST_DB} truncated.")
    finally:
        conn.close()


def cmd_dsn() -> None:
    print(assert_test(config_test_dsn()))


if __name__ == "__main__":
    cmds = {"seed": cmd_seed, "inspect": cmd_inspect, "reset": cmd_reset, "dsn": cmd_dsn}
    if len(sys.argv) == 3 and sys.argv[1] == "land":
        cmd_land(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    else:
        sys.exit(f"usage: python -m db.fixtures.hoist_demo {{{'|'.join(cmds)}}} | land <shot_code>")
