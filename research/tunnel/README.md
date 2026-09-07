# tunnel — SD1.5 AnimateDiff × QR Code Monster "psychedelic spinning tunnel" (crawl phase)

> **Status:** lab project, 2026-09-07. Crawl step of crawl/walk/run: a solid, fast-but-not-realtime
> AnimateDiff graph on **Huxley** with the current AnimateDiff-Evolved (Gen2) controls. No MIDI, no
> realtime yet — those are the walk/run steps (see `../2026-09-07-midi-realtime-comfyui-animation.md`).

**The idea:** a procedurally generated **black/white spinning-tunnel image sequence** drives the
**QR Code Monster** ControlNet, while **prompt scheduling** travels between two prompts (neon fractal
tunnel → molten gold vortex → back). AnimateDiff's motion module keeps it temporally coherent, the
control frames force the tunnel geometry, and the loop closes on itself.

## Files

| file | what |
|---|---|
| `gen_tunnel_control.py` | Generates the seamless-loop B/W control frames (`rings` / `spiral` / `starburst`). numpy + Pillow only. |
| `build_workflow.py` | Emits the ComfyUI **API-format** workflow JSON from CLI knobs. |
| `tunnel_animatediff_api.json` | Default build: **v3 motion module**, 96 f, 512², 22 steps, cfg 7.5. |
| `tunnel_animatediff_lcm_api.json` | `--lcm` build: **AnimateLCM**, 6 steps, cfg 1.5 (≈4× faster, softer). |
| `submit.py` | POSTs a workflow to `http://<host>:8188/prompt`, polls history, prints output files. Stdlib only. |

## The graph (18 nodes)

```
CheckpointLoaderSimple ─► LoraLoader (v3 adapter 0.8) ─► ADE_UseEvolvedSampling ─► FreeU_V2 ─► KSampler ─► VAEDecode ─► VHS_VideoCombine (mp4)
                                                   ▲ m_models        ▲ context        ▲ sample_settings
                    ADE_LoadAnimateDiffModel(v3) ─► ADE_ApplyAnimateDiffModel ◄─ ADE_MultivalDynamic (motion scale)
                                                   ADE_LoopedUniformContextOptions (16 / overlap 4 / closed_loop)
                                                   ADE_AnimateDiffSamplingSettings (FreeNoise)
ADE_PromptScheduling ("0": A, "48": B, "95": A) ─┐
CLIPTextEncode (negative) ───────────────────────┼─► ControlNetApplyAdvanced (QR Monster, 0.7, 0→0.8) ─► KSampler
VHS_LoadImages (input/tunnel_ctrl, 96 frames) ───┘
EmptyLatentImage 512×512 × 96 ─────────────────────────────────────────────────────────────────► KSampler
```

"Latest controls" in use: Gen2 Apply/Use-Evolved-Sampling nodes, **FreeNoise** across context
windows, **Looped Uniform** context with `closed_loop` for a seamless loop, native **Prompt
Scheduling** (lerp in embedding space, no FizzNodes dependency), **Multival** motion scale,
**v3 motion module + domain-adapter LoRA**, **FreeU_V2**, `ControlNetApplyAdvanced` with an
end-percent so the last 20 % of steps are free to add detail. Reference numbers cross-checked
against nerdyrodent's QR-Monster AnimateDiff workflows (CN 0.45–0.9, cfg 7.5, 22–25 steps, FreeU).

## Huxley setup (one time)

1. **Custom nodes** (ComfyUI Manager or `git clone` into `custom_nodes/`):
   - `Kosinkadink/ComfyUI-AnimateDiff-Evolved`
   - `Kosinkadink/ComfyUI-VideoHelperSuite` (needs ffmpeg on PATH for mp4)
2. **Models** (filenames are the builder defaults; override with flags if yours differ):

   | path under `ComfyUI/models/` | file | source |
   |---|---|---|
   | `checkpoints/` | `dreamshaper_8.safetensors` (any good SD1.5 ckpt; not an inpainting/SDXL one) | civitai |
   | `animatediff_models/` | `v3_sd15_mm.ckpt` | HF `guoyww/animatediff` |
   | `loras/` | `v3_sd15_adapter.ckpt` | HF `guoyww/animatediff` |
   | `animatediff_models/` | `AnimateLCM_sd15_t2v.ckpt` (only for `--lcm`) | HF `wangfuyun/AnimateLCM` |
   | `loras/` | `AnimateLCM_sd15_t2v_lora.safetensors` (only for `--lcm`) | HF `wangfuyun/AnimateLCM` |
   | `controlnet/` | `control_v1p_sd15_qrcode_monster.safetensors` (**v1** — nerdyrodent reports it beats v2 with AnimateDiff; v2 is `..._v2.safetensors`) | HF `monster-labs/control_v1p_sd15_qrcode_monster` |

   AnimateDiff-Evolved also accepts motion models in `custom_nodes/ComfyUI-AnimateDiff-Evolved/models/`.
3. **Control frames:** generate and copy into ComfyUI's input dir:
   ```bash
   python gen_tunnel_control.py --out tunnel_ctrl --frames 96 --size 512 --mode spiral
   cp -r tunnel_ctrl  <ComfyUI>/input/tunnel_ctrl
   ```
   (`--preview` writes `tunnel_ctrl.mp4` next to it if ffmpeg is present — worth a look first.)

## Run

```bash
python build_workflow.py                       # writes tunnel_animatediff_api.json
python submit.py tunnel_animatediff_api.json --host huxley:8188
# output: <ComfyUI>/output/tunnel/tunnel_00001.mp4
```
Or drag the JSON onto the ComfyUI canvas (the frontend lays out API-format graphs) and queue it.
The existing comfy-runner at `W:\Projects\ComfyUI_Tools` takes API-format JSON too.

Quick iterations without rebuilding: `--set 41.seed=7 --set 32.strength=0.85 --set 11.float_val=1.2`.

## Knobs that matter (in the order to turn them)

| knob | where | start | effect |
|---|---|---|---|
| control pattern | `gen_tunnel_control.py --mode/--rings/--arms/--twist/--duty` | spiral, 6, 2, 1.5, 0.5 | the geometry the whole clip obeys |
| ControlNet strength | `--cn-strength` (node 32) | 0.7 | 0.45 = suggestion, 0.9 = literal tunnel |
| ControlNet end | `--cn-end` | 0.8 | lower → freer detail in late steps |
| motion scale | `--motion-scale` (node 11) | 1.0 | 0.8 calmer, 1.2 wilder |
| adapter LoRA | `--adapter-strength` | 0.8 | lower → more of the checkpoint's own look |
| prompts | `--prompt-a/--prompt-b` | neon fractal / molten gold | schedule is A@0 → B@mid → A@end |
| length | `--frames` (multiples of 16) | 96 | 96 f @ 12 fps = 8 s loop |
| speed | `--lcm` | off | 22 steps → 6 steps |

Expected cost on a 4090-class card (to be measured): v3 build ≈ 2–4 min for 96 f @ 512²; LCM
build well under a minute.

## Walk / run ladder (each is one flag or one node away)

1. **Latent upscale pass** (nerdyrodent pattern): `LatentUpscaleBy 1.25` → second KSampler at denoise 0.6 with the same ControlNet.
2. **ContextRef / NaiveReuse** (`ADE_ContextExtras_*`) for stronger cross-window consistency on long clips.
3. **FreeInit** (`ADE_IterationOptsFreeInit`) for cleaner motion at the cost of 2–3× time.
4. **Per-frame value schedules:** `ADE_ValueScheduling` → `ADE_MultivalDynamicFloats` into `scale_multival`, so motion amount follows a curve. *This is the slot a MIDI CC lane will plug into.*
5. **IPAdapter Batch + IPAdapter Weights** (Latent Vision technique) to morph between reference images instead of, or on top of, prompt travel.
6. **Chunked / realtime** — see the research brief.
