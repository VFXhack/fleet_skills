#!/usr/bin/env python3
"""Build the ComfyUI API-format workflow: SD1.5 + AnimateDiff-Evolved (Gen2) + QR Code Monster
ControlNet driven by the B/W tunnel frames + native prompt scheduling between two prompts.

    python build_workflow.py                          # -> tunnel_animatediff_api.json (v3 motion module)
    python build_workflow.py --lcm                    # AnimateLCM variant: 6 steps, cfg 1.5
    python build_workflow.py --frames 64 --width 768 --height 432 --cn-strength 0.9

Node ids / input names were read from the node sources (AnimateDiff-Evolved, VHS, ComfyUI core)
on 2026-09-07. The JSON is API format: submit with submit.py, or drag it onto the ComfyUI canvas
(the frontend lays out API-format graphs).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

STYLE = ("psychedelic, hyperdetailed, glowing, volumetric light, sharp focus, 35mm, "
         "masterpiece, best quality")
PROMPT_A = ("infinite spinning tunnel of neon magenta and cyan fractal rings, kaleidoscopic "
            "corridor, iridescent glass walls, deep vanishing point")
PROMPT_B = ("molten gold and obsidian vortex, swirling liquid metal tunnel, warm amber light, "
            "art deco spiral corridor, deep vanishing point")
NEGATIVE = ("(worst quality, low quality:1.4), blurry, lowres, text, watermark, logo, "
            "deformed, flat, dull, jpeg artifacts")


def build(a: argparse.Namespace) -> dict:
    n: dict[str, dict] = {}

    def add(nid: str, class_type: str, **inputs):
        n[nid] = {"class_type": class_type, "inputs": inputs}
        return nid

    # ---- base model -------------------------------------------------------------------
    add("1", "CheckpointLoaderSimple", ckpt_name=a.ckpt)
    model, clip = ["1", 0], ["1", 1]
    vae = ["1", 2]
    if a.vae:
        add("2", "VAELoader", vae_name=a.vae)
        vae = ["2", 0]
    if a.lcm:
        add("3", "LoraLoader", model=model, clip=clip, lora_name=a.lcm_lora,
            strength_model=1.0, strength_clip=1.0)
        model, clip = ["3", 0], ["3", 1]
    elif a.adapter_lora:
        # v3 domain adapter: recommended 0.6-0.9; lower = more of the base ckpt's look
        add("3", "LoraLoader", model=model, clip=clip, lora_name=a.adapter_lora,
            strength_model=a.adapter_strength, strength_clip=a.adapter_strength)
        model, clip = ["3", 0], ["3", 1]

    # ---- AnimateDiff Gen2 ----------------------------------------------------------------
    add("10", "ADE_LoadAnimateDiffModel", model_name=a.motion_model)
    add("11", "ADE_MultivalDynamic", float_val=a.motion_scale)        # motion amount knob
    add("12", "ADE_ApplyAnimateDiffModel", motion_model=["10", 0], start_percent=0.0,
        end_percent=1.0, scale_multival=["11", 0])
    ctx_class = "ADE_LoopedUniformContextOptions" if a.loop else "ADE_StandardUniformContextOptions"
    ctx = dict(context_length=16, context_stride=1, context_overlap=4, fuse_method="pyramid",
               use_on_equal_length=False, start_percent=0.0, guarantee_steps=1)
    if a.loop:
        ctx["closed_loop"] = True
    add("13", ctx_class, **ctx)
    add("14", "ADE_AnimateDiffSamplingSettings", batch_offset=0, noise_type="FreeNoise",
        seed_gen="comfy", seed_offset=0, adapt_denoise_steps=False)
    add("15", "ADE_UseEvolvedSampling", model=model,
        beta_schedule=("lcm[100_ots]" if a.lcm else "autoselect"),
        m_models=["12", 0], context_options=["13", 0], sample_settings=["14", 0])
    model = ["15", 0]
    if a.freeu:
        add("16", "FreeU_V2", model=model, b1=1.3, b2=1.4, s1=0.9, s2=0.2)
        model = ["16", 0]

    # ---- prompts: A -> B -> A over the loop (native ADE scheduling, lerp in embed space) ----
    last = a.frames - 1
    mid = a.frames // 2
    sched = {0: a.prompt_a, mid: a.prompt_b}
    if a.loop:
        sched[last] = a.prompt_a
    prompts = ",\n".join(f'"{k}": "{v}, {STYLE}"' for k, v in sched.items())
    add("20", "ADE_PromptScheduling", prompts=prompts, clip=clip, print_schedule=False,
        max_length=a.frames, tensor_interp="lerp")
    add("21", "CLIPTextEncode", text=a.negative, clip=clip)

    # ---- QR Code Monster driven by the tunnel frames ------------------------------------
    add("30", "VHS_LoadImages", directory=a.control_dir, image_load_cap=a.frames,
        skip_first_images=0, select_every_nth=1)
    add("31", "ControlNetLoader", control_net_name=a.controlnet)
    add("32", "ControlNetApplyAdvanced", positive=["20", 0], negative=["21", 0],
        control_net=["31", 0], image=["30", 0], strength=a.cn_strength,
        start_percent=0.0, end_percent=a.cn_end)

    # ---- sample -----------------------------------------------------------------------------
    add("40", "EmptyLatentImage", width=a.width, height=a.height, batch_size=a.frames)
    seed = a.seed if a.seed is not None else random.randrange(2**32)
    if a.lcm:
        ks = dict(steps=a.steps or 6, cfg=a.cfg or 1.5, sampler_name="lcm", scheduler="sgm_uniform")
    else:
        ks = dict(steps=a.steps or 22, cfg=a.cfg or 7.5, sampler_name="euler_ancestral", scheduler="normal")
    add("41", "KSampler", model=model, seed=seed, positive=["32", 0], negative=["32", 1],
        latent_image=["40", 0], denoise=1.0, **ks)
    add("42", "VAEDecode", samples=["41", 0], vae=vae)
    add("43", "VHS_VideoCombine", images=["42", 0], frame_rate=a.fps, loop_count=0,
        filename_prefix=a.prefix, format="video/h264-mp4", pingpong=False, save_output=True,
        pix_fmt="yuv420p", crf=19, save_metadata=True, trim_to_audio=False)
    return n


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=None, help="default: tunnel_animatediff_api.json (or _lcm)")
    p.add_argument("--ckpt", default="dreamshaper_8.safetensors")
    p.add_argument("--vae", default="", help="optional external VAE, e.g. vae-ft-mse-840000-ema-pruned.safetensors")
    p.add_argument("--motion-model", default=None, help="default v3_sd15_mm.ckpt (or AnimateLCM_sd15_t2v.ckpt with --lcm)")
    p.add_argument("--adapter-lora", default="v3_sd15_adapter.ckpt", help="v3 domain adapter LoRA; '' to skip")
    p.add_argument("--adapter-strength", type=float, default=0.8)
    p.add_argument("--lcm", action="store_true", help="AnimateLCM: 6 steps / cfg 1.5 / lcm sampler")
    p.add_argument("--lcm-lora", default="AnimateLCM_sd15_t2v_lora.safetensors")
    p.add_argument("--controlnet", default="control_v1p_sd15_qrcode_monster.safetensors")
    p.add_argument("--control-dir", default="tunnel_ctrl", help="folder name under ComfyUI/input/")
    p.add_argument("--cn-strength", type=float, default=0.7)
    p.add_argument("--cn-end", type=float, default=0.8, help="stop ControlNet at this % of steps (frees the tail for detail)")
    p.add_argument("--frames", type=int, default=96)
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--height", type=int, default=512)
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--cfg", type=float, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--motion-scale", type=float, default=1.0, help="Multival scale on the motion module (0.8 calmer, 1.2 wilder)")
    p.add_argument("--no-loop", dest="loop", action="store_false", help="standard (non-looping) context")
    p.add_argument("--no-freeu", dest="freeu", action="store_false")
    p.add_argument("--prompt-a", default=PROMPT_A)
    p.add_argument("--prompt-b", default=PROMPT_B)
    p.add_argument("--negative", default=NEGATIVE)
    p.add_argument("--prefix", default="tunnel/tunnel")
    a = p.parse_args()
    if a.motion_model is None:
        a.motion_model = "AnimateLCM_sd15_t2v.ckpt" if a.lcm else "v3_sd15_mm.ckpt"
    if a.out is None:
        a.out = Path("tunnel_animatediff_lcm_api.json" if a.lcm else "tunnel_animatediff_api.json")
    graph = build(a)
    a.out.write_text(json.dumps(graph, indent=2))
    print(f"{a.out}: {len(graph)} nodes, {a.frames}f {a.width}x{a.height}, motion={a.motion_model}, cn={a.cn_strength}")


if __name__ == "__main__":
    main()
