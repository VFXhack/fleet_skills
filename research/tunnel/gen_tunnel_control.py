#!/usr/bin/env python3
"""Generate looping black/white "spinning tunnel" control frames for QR Code Monster ControlNet.

Procedural, no assets: concentric rings zoom inward (log-radius so they accelerate toward the
centre like a real tunnel), optionally twisted into spiral arms and rotated over time. Every
parameter is chosen so frame N wraps to frame 0 -> pair with AnimateDiff "Looped Uniform"
context (closed_loop=true) for a seamless loop.

    python gen_tunnel_control.py --out tunnel_ctrl --frames 96 --size 512
    python gen_tunnel_control.py --out tunnel_ctrl --mode spiral --arms 3 --twist 2.5
    python gen_tunnel_control.py --out tunnel_ctrl --mode starburst --rings 12 --spokes 16

Drop the output directory into ComfyUI/input/ on the render host; the workflow loads it with
VHS_LoadImages(directory="tunnel_ctrl").
"""
from __future__ import annotations

import argparse
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def tunnel_frame(t: float, *, size: int, rings: float, arms: int, twist: float, spokes: int,
                 mode: str, zoom_cycles: float, spin_cycles: float, hole: float,
                 soft: float, duty: float) -> np.ndarray:
    """t in [0,1) is the loop phase. Returns float32 HxW in [0,1]."""
    h = w = size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    dx, dy = (xs - cx) / (w / 2.0), (ys - cy) / (h / 2.0)
    r = np.sqrt(dx * dx + dy * dy) + 1e-4          # 0 centre .. ~1.41 corners
    a = np.arctan2(dy, dx)                          # -pi..pi

    # zoom: rings move inward as t increases (negative phase). log(r) makes them speed up near
    # the centre — the classic tunnel-flight look. integer cycles keep the loop seamless.
    zoom_phase = -2.0 * math.pi * zoom_cycles * t
    spin_phase = 2.0 * math.pi * spin_cycles * t

    if mode == "rings":
        v = rings * np.log(r) + zoom_phase
    elif mode == "spiral":
        # arms * angle couples rotation into the ring pattern -> spiral arms that appear to
        # corkscrew as they zoom. twist controls how tightly they wind.
        v = rings * np.log(r) + twist * arms * (a + spin_phase) + zoom_phase
    elif mode == "starburst":
        # rings AND spokes: a checker tunnel. spokes rotate, rings zoom.
        v_r = rings * np.log(r) + zoom_phase
        v_a = spokes * (a + spin_phase)
        sq_r = np.sin(v_r)
        sq_a = np.sin(v_a)
        v = None
        field = np.where(sq_r * sq_a > 0.0, 1.0, 0.0).astype(np.float32)
    else:
        raise ValueError(mode)

    if mode != "starburst":
        # duty cycle: fraction of each ring that is white (0.5 = even stripes)
        thresh = math.cos(math.pi * duty)
        field = np.where(np.sin(v) > thresh, 1.0, 0.0).astype(np.float32)

    # black hole in the middle (vanishing point) — QR Monster reads black as "background"
    if hole > 0:
        field = np.where(r < hole, 0.0, field)

    if soft > 0:
        img = Image.fromarray((field * 255).astype(np.uint8))
        img = img.filter(ImageFilter.GaussianBlur(radius=soft))
        field = np.asarray(img).astype(np.float32) / 255.0
    return field


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("tunnel_ctrl"))
    p.add_argument("--frames", type=int, default=96, help="frames in one seamless loop (multiple of 16 ideal)")
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--mode", choices=["rings", "spiral", "starburst"], default="spiral")
    p.add_argument("--rings", type=float, default=6.0, help="ring density (per e-fold of radius)")
    p.add_argument("--arms", type=int, default=2, help="spiral arms (spiral mode)")
    p.add_argument("--twist", type=float, default=1.5, help="spiral tightness (spiral mode)")
    p.add_argument("--spokes", type=int, default=12, help="spokes (starburst mode)")
    p.add_argument("--zoom-cycles", type=float, default=2.0, help="ring cycles that pass per loop (integer = seamless)")
    p.add_argument("--spin-cycles", type=float, default=1.0, help="full rotations per loop (integer = seamless)")
    p.add_argument("--hole", type=float, default=0.06, help="black centre radius (0..1)")
    p.add_argument("--soft", type=float, default=1.0, help="gaussian blur px (0 = hard edges)")
    p.add_argument("--duty", type=float, default=0.5, help="white fraction of each ring (0.3 thin, 0.7 fat)")
    p.add_argument("--invert", action="store_true")
    p.add_argument("--preview", action="store_true", help="also write <out>.mp4 via ffmpeg if available")
    p.add_argument("--fps", type=int, default=12)
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for f in args.out.glob("tunnel_*.png"):
        f.unlink()
    for i in range(args.frames):
        t = i / args.frames
        field = tunnel_frame(t, size=args.size, rings=args.rings, arms=args.arms, twist=args.twist,
                             spokes=args.spokes, mode=args.mode, zoom_cycles=args.zoom_cycles,
                             spin_cycles=args.spin_cycles, hole=args.hole, soft=args.soft, duty=args.duty)
        if args.invert:
            field = 1.0 - field
        Image.fromarray((field * 255).astype(np.uint8)).convert("RGB").save(args.out / f"tunnel_{i:04d}.png")
    print(f"wrote {args.frames} frames -> {args.out}/tunnel_0000.png ..")

    if args.preview:
        ff = shutil.which("ffmpeg")
        if not ff:
            print("ffmpeg not found; skipping preview")
            return
        mp4 = args.out.with_suffix(".mp4")
        subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(args.fps),
                        "-i", str(args.out / "tunnel_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "18", str(mp4)], check=True)
        print(f"preview -> {mp4}")


if __name__ == "__main__":
    main()
