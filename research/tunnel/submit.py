#!/usr/bin/env python3
"""Submit an API-format workflow to a ComfyUI server and wait for the output.

    python submit.py tunnel_animatediff_api.json --host huxley:8188
    python submit.py tunnel_animatediff_api.json --host huxley:8188 --set 41.seed=1234 --set 32.strength=0.85

--set patches any node input before submit (node_id.input=value; numbers auto-typed).
Stdlib only: no requests dependency, runs from any fleet host with python3.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path


def coerce(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(v.lower(), v)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("workflow", type=Path)
    p.add_argument("--host", default="127.0.0.1:8188")
    p.add_argument("--set", action="append", default=[], metavar="NODE.INPUT=VALUE")
    p.add_argument("--timeout", type=int, default=3600)
    a = p.parse_args()

    graph = json.loads(a.workflow.read_text())
    for s in a.set:
        key, _, val = s.partition("=")
        nid, _, inp = key.partition(".")
        graph[nid]["inputs"][inp] = coerce(val)

    base = f"http://{a.host}"
    body = json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode()
    req = urllib.request.Request(f"{base}/prompt", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        resp = json.load(r)
    if resp.get("node_errors"):
        print(json.dumps(resp["node_errors"], indent=2), file=sys.stderr)
        sys.exit(1)
    pid = resp["prompt_id"]
    print(f"queued {pid} on {a.host}")

    t0 = time.time()
    while time.time() - t0 < a.timeout:
        with urllib.request.urlopen(f"{base}/history/{pid}") as r:
            hist = json.load(r)
        if pid in hist:
            st = hist[pid].get("status", {})
            if st.get("status_str") == "error":
                print(json.dumps(st, indent=2), file=sys.stderr)
                sys.exit(2)
            outs = hist[pid].get("outputs", {})
            for nid, o in outs.items():
                for k in ("gifs", "images", "videos"):
                    for f in o.get(k, []):
                        print(f"[{nid}] {f.get('subfolder','')}/{f.get('filename')}")
            print(f"done in {time.time()-t0:.0f}s")
            return
        time.sleep(3)
    print("timeout", file=sys.stderr)
    sys.exit(3)


if __name__ == "__main__":
    main()
