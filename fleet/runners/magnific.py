"""Magnific (formerly Freepik) API runner.

A generic async client over https://api.magnific.com:
  POST /v1/ai/<category>/<slug>            -> { data: { task_id, status, ... } }
  GET  /v1/ai/<category>/<slug>/<task_id>  -> poll until COMPLETED/FAILED
then download the produced asset(s). Models live in the MODELS registry, so adding or
fixing a model is a data entry, not new code.

Auth: header `x-magnific-api-key` (from config: MAGNIFIC_API_KEY or [magnific].api_key).

NOTE: the public docs are unreliable for exact slugs (mid-rebrand Freepik -> Magnific; the
WebFetch'd reference even hallucinates slugs). The MODELS registry below is therefore grounded
in the LIVE API: each slug was confirmed by POSTing an empty payload and reading the API's own
validation response (a real slug 400s on missing fields; a fake slug 404s) — a probe that costs
no credits. To re-probe or extend the registry, see scratchpad/probe_slugs.py.
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .. import config

BASE_URL = "https://api.magnific.com"

# Status strings seen across endpoints (two casings). Upper() then compare.
_TERMINAL_OK = {"COMPLETED"}
_TERMINAL_BAD = {"FAILED", "ERROR"}


@dataclass(frozen=True)
class Model:
    name: str             # friendly name used on the CLI
    category: str         # REST path segment (text-to-image|image-to-video) OR MCP tool family
    slug: str             # REST slug under /v1/ai/<category>/<slug>, or the MCP video_generate slug
    kind: str             # "image" | "video"
    dispatch: str = "rest"        # "rest" (headless api-key) | "mcp" (agent-driven, OAuth)
    needs_image: bool = False     # requires an input image
    image_mode: str = "image_url"  # "reference_images" | "image_url" — how to attach --image
    verified: bool = False         # contract confirmed against the live surface
    notes: str = ""


# Registry. All entries below are VERIFIED against the live API (probed 2026-06-25): the slug
# exists and its required fields were read from the API's own validation response.
#
# NANO BANANA — full set on the API is the two Pro tiers below. There is no `nano-banana-2`
# slug; "Nano Banana Pro" IS the Gemini-3 / "2" generation (pro = full tier, pro-flash = fast).
#
# SEEDANCE 2.0 — slug confirmed via the Magnific MCP catalog (video_models_list, 2026-06-25), but
# the slugs are MCP-ONLY: re-probed all four against REST /v1/ai/{image-to-video,text-to-video,
# video-generator}/<slug> and every one 404s (control nano-banana slug still 400s -> probe valid).
# So these dispatch="mcp": the headless REST runner can't self-serve them; it emits an MCP dispatch
# spec for the agent/Submitter to run through the Magnific MCP `video_generate` tool. See
# scratch_magnific/probe_seedance.py and ADR-0003 hybrid-dispatch decision.
MODELS: dict[str, Model] = {
    "nano-banana-pro-flash": Model(
        name="nano-banana-pro-flash",
        category="text-to-image",
        slug="nano-banana-pro-flash",
        kind="image",
        needs_image=False,
        image_mode="reference_images",
        verified=True,
        notes="Gemini-3 image, fast tier. prompt(req) + aspect_ratio + resolution(1K/2K/4K) + up to 14 reference_images.",
    ),
    "nano-banana-pro": Model(
        name="nano-banana-pro",
        category="text-to-image",
        slug="nano-banana-pro",
        kind="image",
        needs_image=False,
        image_mode="reference_images",
        verified=True,
        notes="Gemini-3 image, full tier (a.k.a. Nano Banana 2). prompt(req) + aspect_ratio + resolution + reference_images.",
    ),
    # --- Confirmed-real image-to-video models (not the Seedance target, but a working video path today) ---
    "minimax-live": Model(
        name="minimax-live",
        category="image-to-video",
        slug="minimax-live",
        kind="video",
        needs_image=True,
        image_mode="image_url",
        verified=True,
        notes="MiniMax i2v. Requires prompt + image_url. Optional aspect_ratio.",
    ),
    "ltx-2-fast": Model(
        name="ltx-2-fast",
        category="image-to-video",
        slug="ltx-2-fast",
        kind="video",
        needs_image=True,
        image_mode="image_url",
        verified=True,
        notes="LTX 2.0 (fast) i2v. Requires prompt + image_url. Optional aspect_ratio, duration.",
    ),
    # --- Seedance 2.0 family: MCP-only (dispatch via Magnific MCP `video_generate`, not REST) ---
    # MCP required inputs: prompt + duration + aspectRatio + resolution (camelCase). t2v by default;
    # optional keyframes.start/end (image), references[] (image/video/character/product/style/audio),
    # cameraMotion vocab, native sound effects. durations 4-15s.
    "seedance-2.0": Model(
        name="seedance-2.0",
        category="video-generator",
        slug="bytedance-seedance-pro-2.0",
        kind="video",
        dispatch="mcp",
        verified=True,
        notes="Seedance 2.0 Pro (SOTA, rank 1). res 4K/1080p/720p/480p. Best overall: realistic, native audio, lipsync, references.",
    ),
    "seedance-2.0-fast": Model(
        name="seedance-2.0-fast",
        category="video-generator",
        slug="bytedance-seedance-fast-2.0",
        kind="video",
        dispatch="mcp",
        verified=True,
        notes="Seedance 2.0 Fast (rank 3). res 720p/480p. Fast drafts with Seedance controls / native audio.",
    ),
    "seedance-2.0-mini": Model(
        name="seedance-2.0-mini",
        category="video-generator",
        slug="bytedance-seedance-mini-2.0",
        kind="video",
        dispatch="mcp",
        verified=True,
        notes="Seedance 2.0 Mini (rank 2, best value). res 720p/480p. Best quality/price for 4-15s with native audio.",
    ),
    "seedance-1.5-pro": Model(
        name="seedance-1.5-pro",
        category="video-generator",
        slug="bytedance-seedance-pro-1.5",
        kind="video",
        dispatch="mcp",
        verified=True,
        notes="Seedance 1.5 Pro. res 1080p/720p/480p/Draft. Older gen; start/end keyframes, sound effects.",
    ),
}


def build_mcp_spec(model: Model, args: argparse.Namespace) -> dict:
    """Build the dispatch spec for an MCP-only model. The headless runner cannot call the
    OAuth MCP surface itself, so it emits this spec for the agent/Submitter to feed into the
    Magnific MCP `video_generate` tool (camelCase fields, slug verbatim)."""
    params: dict = {"slug": model.slug}
    if args.prompt:
        params["prompt"] = args.prompt
    if args.duration is not None:
        params["duration"] = args.duration
    if args.aspect_ratio is not None:
        params["aspectRatio"] = args.aspect_ratio
    if args.resolution is not None:
        params["resolution"] = args.resolution
    if args.image:
        # A start frame goes in keyframes.start; a plain reference image goes in references[].
        params["keyframes"] = {"start": {"type": "image", "url": args.image}}
    for item in args.extra or []:
        key, _, raw = item.partition("=")
        params[key.strip()] = _coerce(raw.strip())
    missing = [f for f in ("prompt", "duration", "aspectRatio", "resolution") if f not in params]
    return {"tool": "video_generate", "model": model.name, "params": params, "missing_required": missing}


def dispatch_mcp(model: Model, args: argparse.Namespace) -> int:
    """Headless runner can't reach the OAuth MCP surface; emit a spec and exit non-zero (2)
    so a caller knows this needs the agent/MCP path rather than REST."""
    import json
    spec = build_mcp_spec(model, args)
    print(f"model    : {model.name}  (MCP-only — slug {model.slug})", file=sys.stderr)
    print("note     : not on the REST API; run via the Magnific MCP `video_generate` tool.", file=sys.stderr)
    if spec["missing_required"]:
        print(f"missing  : required field(s) {spec['missing_required']}", file=sys.stderr)
    print(json.dumps(spec, indent=2))  # spec to stdout for an agent/Submitter to consume
    return 2


def _headers() -> dict:
    return {"x-magnific-api-key": config.get_magnific_api_key()}


def _unwrap(resp_json: dict) -> dict:
    """Endpoints wrap the payload in {"data": {...}}; tolerate either shape."""
    return resp_json.get("data", resp_json) if isinstance(resp_json, dict) else {}


def _image_value(image: str) -> str:
    """A URL passes through; a local file is encoded as a base64 data URI.
    (Data-URI acceptance is UNVERIFIED for video endpoints — confirm live.)"""
    if image.startswith(("http://", "https://")):
        return image
    p = Path(image)
    if not p.exists():
        sys.exit(f"error: --image '{image}' is not a URL or an existing file")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def build_payload(model: Model, args: argparse.Namespace) -> dict:
    payload: dict = {}
    if args.prompt:
        payload["prompt"] = args.prompt
    for field in ("aspect_ratio", "resolution", "duration", "seed"):
        val = getattr(args, field, None)
        if val is not None:
            payload[field] = val
    if args.image:
        value = _image_value(args.image)
        if model.image_mode == "reference_images":
            mime = "image/png"
            if not value.startswith("data:"):
                mime = mimetypes.guess_type(value)[0] or "image/png"
            payload["reference_images"] = [{"image": value, "mime_type": mime}]
        else:
            # Live i2v models expect `image_url` (verified 2026-06-25).
            payload["image_url"] = value
    if args.webhook_url:
        payload["webhook_url"] = args.webhook_url
    for item in args.extra or []:
        key, _, raw = item.partition("=")
        payload[key.strip()] = _coerce(raw.strip())
    return payload


def _coerce(raw: str):
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def submit(model: Model, payload: dict) -> str:
    url = f"{BASE_URL}/v1/ai/{model.category}/{model.slug}"
    resp = requests.post(url, headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    data = _unwrap(resp.json())
    task_id = data.get("task_id") or data.get("id")
    if not task_id:
        sys.exit(f"error: no task_id in response: {resp.text[:300]}")
    return task_id


def poll(model: Model, task_id: str, *, interval: float = 3.0, timeout: float = 900.0) -> dict:
    url = f"{BASE_URL}/v1/ai/{model.category}/{model.slug}/{task_id}"
    deadline = time.monotonic() + timeout
    last = ""
    while True:
        resp = requests.get(url, headers=_headers(), timeout=60)
        resp.raise_for_status()
        data = _unwrap(resp.json())
        status = str(data.get("status", "")).upper()
        if status != last:
            print(f"  status: {status or '(none)'}")
            last = status
        if status in _TERMINAL_OK or status in _TERMINAL_BAD:
            return data
        if time.monotonic() > deadline:
            sys.exit(f"error: timed out after {timeout:.0f}s waiting for task {task_id}")
        time.sleep(interval)


def output_urls(data: dict) -> list[str]:
    """Pull asset URL(s) from a completed task, tolerating field-name variation."""
    for key in ("generated", "urls", "url", "video", "videos", "images", "output"):
        val = data.get(key)
        if isinstance(val, str):
            return [val]
        if isinstance(val, list) and val:
            out = []
            for item in val:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    out.append(item.get("url") or item.get("image") or item.get("video"))
            return [u for u in out if u]
    return []


def download(urls: list[str], out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, url in enumerate(urls):
        ext = Path(url.split("?")[0]).suffix or ".bin"
        dest = out_dir / (f"{stem}{ext}" if len(urls) == 1 else f"{stem}_{i:02d}{ext}")
        with requests.get(url, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
        saved.append(dest)
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magnific-gen",
        description="Generate with a Magnific model (submit -> poll -> download).",
    )
    parser.add_argument("--model", help="model name (see --list-models)")
    parser.add_argument("--prompt", help="text prompt")
    parser.add_argument("--image", help="input/reference image: URL or local file path")
    parser.add_argument("--aspect-ratio", dest="aspect_ratio", help="e.g. 16:9, 1:1")
    parser.add_argument("--resolution", help="e.g. 1K/2K/4K (image) or 480p/720p/1080p (video)")
    parser.add_argument("--duration", type=int, help="video duration (seconds)")
    parser.add_argument("--seed", type=int, help="seed")
    parser.add_argument("--extra", action="append", metavar="KEY=VALUE",
                        help="extra model-specific field (repeatable)")
    parser.add_argument("--webhook-url", dest="webhook_url", help="optional async callback URL")
    parser.add_argument("--out", default="magnific_out", help="output directory (default: ./magnific_out)")
    parser.add_argument("--stem", help="output filename stem (default: <model>_<task_id8>)")
    parser.add_argument("--list-models", action="store_true", help="list known models and exit")
    parser.add_argument("--dry-run", action="store_true", help="print the request and exit")
    args = parser.parse_args(argv)

    if args.list_models:
        for name, m in sorted(MODELS.items()):
            flag = "ok " if m.verified else "?? "
            print(f"  [{flag}] {name:18s} {m.dispatch:4s} {m.category:16s} {m.kind:6s} {m.notes}")
        return 0

    if not args.model:
        parser.error("--model is required (or use --list-models)")
    model = MODELS.get(args.model)
    if model is None:
        sys.exit(f"error: unknown model '{args.model}'. Try --list-models.")
    if model.needs_image and not args.image:
        sys.exit(f"error: model '{model.name}' needs --image")
    if not args.prompt and not args.image:
        sys.exit("error: provide --prompt and/or --image")

    if model.dispatch == "mcp":
        return dispatch_mcp(model, args)

    payload = build_payload(model, args)
    endpoint = f"{BASE_URL}/v1/ai/{model.category}/{model.slug}"
    print(f"model    : {model.name}{'' if model.verified else '  (UNVERIFIED slug)'}")
    print(f"endpoint : POST {endpoint}")
    print(f"payload  : {payload}")

    if args.dry_run:
        print("\n[dry-run] not submitting.")
        return 0

    task_id = submit(model, payload)
    print(f"task_id  : {task_id}")
    data = poll(model, task_id)
    status = str(data.get("status", "")).upper()
    if status in _TERMINAL_BAD:
        sys.exit(f"error: task {status}: {data}")

    urls = output_urls(data)
    if not urls:
        sys.exit(f"error: COMPLETED but no output URL found in: {data}")
    stem = args.stem or f"{model.name}_{task_id[:8]}"
    saved = download(urls, Path(args.out), stem)
    print("\nsaved:")
    for p in saved:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
