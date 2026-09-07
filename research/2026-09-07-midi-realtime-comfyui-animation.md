# MIDI-controlled realtime ComfyUI animation — research brief

> **Status:** research only (2026-09-07, overnight). Not a Skill, not an ADR, does not touch the
> pipeline spine. Side-project scouting for a **live, MIDI-driven, "old school" (SD1.5/SDXL +
> AnimateDiff + IPAdapter) animation rig** in ComfyUI. Decisions get grilled with Andy in the AM.

## TL;DR

1. **Latent Vision's IPAdapter + AnimateDiff work is an offline batch technique**, not realtime. Its
   core idea — a **per-frame IPAdapter weight schedule** (`IPAdapter Weights` → `IPAdapter Batch`
   with `unfold_batch`) blending N reference images across a 16-frame AnimateDiff context — maps
   *directly* onto "a MIDI CC stream sets the weight per frame". That is the reusable part.
2. **AnimateDiff cannot run per-frame realtime.** It samples a 16-frame context as a block. The
   honest options are:
   - **A. Chunked / beat-quantized AnimateDiff** — AnimateLCM (4–8 steps) renders 16-frame chunks
     back-to-back; MIDI is latched per chunk. Latency ≈ one chunk render (~1–3 s at 512px on a
     4090-class GPU). Old-school tools, literal ask, musically usable if chunk = 1 bar.
   - **B. Per-frame stream (no motion module)** — StreamDiffusion / ComfyStream running SD1.5-LCM
     or SDXL-Turbo img2img at 20–100 fps, with IPAdapter + ControlNet, temporal coherence from
     **StreamV2V** + latent feedback. Truly live; the AnimateDiff "look" is approximated.
   - **C. Live2Diff** — the one research codebase that *is* AnimateDiff-architecture streaming
     (uni-directional temporal attention + KV-cache, SD1.5, ~16 fps @ 512 w/ TensorRT on a 4090).
     Dormant since July 2024, not a ComfyUI node. Reference design, maybe a port target.
3. **MIDI into ComfyUI already exists** in three flavours: **ControlFreak** (MIDI/gamepad → any
   widget, UI-side), **RealtimeNodes + ComfyStream** (per-frame workflow execution loop), and
   **RyanOnTheInside** (MIDI feature extraction → per-frame IPAdapter weights / AnimateDiff
   keyframes — the offline-render bridge for option A). VrchStudio's web-viewer adds OSC + MIDI
   device nodes + a TouchOSC panel. None of this needs TouchDesigner.
4. **Recommendation to grill:** prototype **A and B side by side** on one host — A in plain ComfyUI
   (AnimateLCM + IPAdapter Batch + Weights, MIDI via ControlFreak/RyanOnTheInside), B via
   ComfyStream (Linux) or StreamDiffusion (python, TensorRT). Decide by feel: is "one bar of
   latency" acceptable for the AnimateDiff look, or does it have to be per-frame?

---

## 1. What Latent Vision (Matteo Spinelli / cubiq / matt3o) actually did

**Repo:** `cubiq/ComfyUI_IPAdapter_plus` (6.1k★). **Since 2025-04-14 the repo is "maintenance only"**
— Matteo states he no longer uses ComfyUI as his main gen-AI interface and will only consider
critical fixes. Comfy Org keeps a fork at `comfyorg/comfyui-ipadapter` (194 commits, explicitly forked
from cubiq). Treat IPAdapter_plus as **frozen but stable**; it still installs and runs fine on SD1.5
and SDXL, which is exactly the "old school" stack we want.

**Tutorial videos (Latent Vision channel):**
- Basic usage — `youtu.be/7m9ZZFU3HWo`
- Advanced features — `youtube.com/watch?v=mJQ62ly7jrg`
- Attention masking — `youtube.com/watch?v=vqG1VXKteQg`
- **New IPAdapter features (Apr 2024, introduces `IPAdapter Weights`)** — `youtu.be/_JzDcgKgghY`
- Style & Composition — `youtube.com/watch?v=czcgJnoDVd4`
- **Animation Features (the AnimateDiff one)** — `youtube.com/watch?v=ddYbhv3WgWw`

**The animation technique (from the Animation Features video + README changelog Apr 2024
"IPAdapterWeights refactored, mostly useful for AnimateDiff"):**

| Node | What it does | Why it matters for MIDI |
|---|---|---|
| `IPAdapter Weights` | Takes a weights string (`"1.0, 0.0"`), `timing` (linear / ease_in / ease_out / ease_in_out / custom / random), `frames`, `start_frame`/`end_frame`, `add_starting_frames`/`add_ending_frames`, `method` (full batch / shift batches / alternate batches), optional image batch. Outputs `weights`, `weights_invert`, `total_frames`, `image_1`, `image_2`. | This **is** a per-frame automation lane. A MIDI CC recorded or streamed per frame is just a `custom` weights list. |
| `IPAdapter Weights From Strategy` | Re-derive the schedule from a saved strategy so two IPAdapters stay in sync. | Same lane, two adapters (e.g. style vs. subject). |
| `IPAdapter Batch` (`unfold_batch=true`) | Applies image *i* of the batch to frame *i* instead of averaging the batch. | The frame↔reference mapping. With AnimateDiff it morphs between references. |
| `IPAdapter Embeds` / `Combine Embeds` / `Weighted Embeds` | Pre-encode references once, mix in embed space. | **Precompute the CLIP-vision embeds for a bank of references; MIDI notes select/blend embeds at zero encode cost.** |
| Weight types (`linear`, `ease in`, `ease out`, `ease in-out`, `reverse in-out`, `weak input/middle/output`, `strong middle`, `style transfer`, `composition`, `style and composition`, `strong style transfer`, `style transfer precise`) | Per-UNet-block weighting. | `style transfer` vs `composition` are two more MIDI-mappable macro knobs. |

Reference examples in the repo: `ipadapter_weights.json`, `ipadapter_weight_types.json`,
`ipadapter_weighted_embeds.json`, `ipadapter_combine_embeds.json`, `ipadapter_faceid_batch.json`, plus
matt3o's OpenArt workflow "IPAdapter 2-reference-images Animation" (batch-unfold morph between two refs).
Community summaries note that unfold-batch IPAdapter "pushes toward realism", so a **keyframe from a
small AnimateDiff run without IPAdapter** is used to anchor style — keep that in mind for chunk seeding.

**Latent Vision's setup is offline:** 16-frame context, AnimateDiff v3 / AnimateLCM motion module,
ControlNet optional, one queue press per clip. Nothing in it is a loop. Everything in it is a
**per-frame parameter schedule**, which is the thing MIDI produces.

## 2. Why AnimateDiff is not per-frame realtime (and what is)

AnimateDiff's motion module is temporal attention **across a context window** (16 frames for v2/v3
and AnimateLCM; **8 for HotshotXL / AnimateDiff-SDXL beta**). ComfyUI-AnimateDiff-Evolved gives
"infinite length" only via **sliding context windows** across a *finite, pre-planned* batch. There is
no streaming/KV-cache mode. So:

- **SD1.5 is the AnimateDiff home.** v3 motion module + AnimateLCM (4–8 steps, cfg 1–2, `lcm`
  sampler, `sgm_uniform`, beta schedule `lcm[100_ots]`) is the fast path. Reported timings for a 16-frame
  AnimateLCM clip: ~21 s for a heavy 5-step vid2vid flow; a lean 512px txt2vid/latent-feedback chunk
  is expected to land in the 1–3 s range on a 4090 (to be measured, not assumed).
- **SDXL AnimateDiff is "beta"** (AnimateDiff-SDXL, HotshotXL) with 8-frame contexts and weaker
  motion. SDXL's strength for a live rig is instead **SDXL-Turbo / Lightning / DMD2 / Hyper-SD** for
  per-frame img2img (option B). Note community reports that Lightning and Hyper-SD are blurry on
  img2img; DMD2 and Turbo/LCM behave better there.
- **Live2Diff (open-mmlab, Jul 2024):** adopts AnimateDiff's architecture, makes temporal attention
  **uni-directional with a warm-up and a multi-timestep KV-cache**, uses StreamDiffusion's stream
  batching. SD1.5, 2 denoise steps: 16.4 fps @ 512² with TensorRT (6.9 without), 12.2 fps @ 768×512.
  Controls: prompt, strength, t-index list. Python 3.10, xformers. **It is the proof that "AnimateDiff
  realtime" is possible; it is not maintained and has no ComfyUI wrapper.** Candidate for a later port
  if option A's chunk latency is unacceptable.
- **StreamDiffusionV2 / Daydream Scope (Nov 2025 →):** the "new school" answer — autoregressive video
  diffusion (StreamDiffusionV2, LongLive, Krea Realtime 14B, RewardForcing, MemFlow) with webcam,
  Spout (Windows), screen-capture inputs. Out of scope for the old-school brief but the obvious
  comparison point once the rig exists.

## 3. Realtime loops that exist today

| Stack | What it is | Platform / GPU | Live param control | Verdict for this rig |
|---|---|---|---|---|
| **ComfyStream** (Livepeer) | ComfyUI custom node + WebRTC server + UI. Runs a ComfyUI **API-format workflow once per video frame**. Workflow must have one `PrimaryInputLoadImage`/`LoadImage` (→ `LoadTensor`) and one `PreviewImage`/`SaveImage` (→ `SaveTensor`). | Tested Ubuntu + RTX 4090, CUDA 12.5, torch 2.5.1. No Windows in docs. | Any node that re-reads state each execution (RealtimeNodes, MIDI nodes) becomes live automatically. | **Best fit for "keep it in ComfyUI"** on a Linux GPU box (Huxley-shaped). Option B host, and the executor for a chunked A if we accept N-frame batches per tick. |
| **ComfyUI-Stream-Pack** (Livepeer) | Planned Foundation / Light / IO nodes for ComfyStream. | — | — | **Empty scaffold** as of this read. Ignore. |
| **StreamDiffusion (daydreamlive fork)** | Pipeline-level realtime SD: SD1.5, SDXL (auto-detect), SD-Turbo, SDXL-Turbo, LCM-LoRA; **ControlNet, IPAdapter incl. FaceID, StreamV2V temporal coherence, TensorRT-first**. 4090 + i9-13900K: SD-Turbo 106 fps txt2img / 94 fps img2img; LCM-LoRA ~38 fps. Runtime prompt/seed updates. | Python/diffusers, Docker. | Python API — trivially wrap `mido`/`python-rtmidi` around it. | **Fastest true-realtime path, outside ComfyUI.** The IPAdapter here is *not* cubiq's node set but the same models. |
| **StreamDiffusionTD** (dotsimulate) | StreamDiffusion inside TouchDesigner. v0.4.0: ControlNet + IPAdapter + StreamV2V + live LoRA weight on TensorRT; SDXL-Turbo native. Hosted version via Daydream. | Local: Windows, Py 3.10/3.11, NDI SDK, NVIDIA. Hosted: anything incl. Apple Silicon. Patreon. | **MIDI is native in TD (MIDI In CHOP → any par).** | Path of least resistance for a *performing* rig on Watts. Costs TD + Patreon; leaves ComfyUI. |
| **Live2Diff** | see §2 | Linux research code | prompt/strength | Reference design. |
| **TouchDiffusion / TDComfyUI / ComfyUI-TD** | TD ↔ ComfyUI bridges (images, video, PLY, audio out of Comfy; `LoadTDImage` in). | — | Data streaming, not parameter push. | Only useful if TD is the front-end anyway. |

## 4. Getting MIDI into ComfyUI

| Package | Mechanism | Live device? | Notes |
|---|---|---|---|
| **`ryanontheinside/ComfyUI_ControlFreak`** | Maps MIDI/gamepad/joystick inputs to **any node widget or UI command** (right-click → Standard Map; `Edit → Controller Mapping`). "Parameters update instantly." Profiles WIP. | Yes (browser Web MIDI) | UI-side: the mapped widget value changes; you still need a queue loop (instant/auto-queue, or ComfyStream) for it to matter. Simplest possible start. |
| **`ryanontheinside/ComfyUI_RealtimeNodes`** | Float/Int/String Control (sine, bounce, random-walk), MotionController, sequences (fwd/rev/pingpong/random), `FPSMonitor`, `SimilarityFilter` (skips redundant frames), `FastWebcamCapture`, `LazyCondition`, full MediaPipe (face/pose/hands/segmentation/gestures). Outputs update **per execution** — designed for ComfyStream's once-per-frame loop. | n/a (values) | The plumbing for option B inside ComfyUI. Author is at Daydream doing realtime diffusion research. |
| **`ryanontheinside/ComfyUI_RyanOnTheInside`** | "Everything-reactivity": MIDI feature extraction (velocity, pitch, note on/off, duration, density, pitch-bend, aftertouch, CC incl. mod/expression/sustain) → **features that drive IPAdapter weights, masks, AnimateDiff keyframes, particles, Flex nodes** per frame. Direct AnimateDiff-Evolved integration. Docs claim both file and "real-time input". | Files yes; live claimed | **The bridge for option A**: record/receive MIDI → per-frame IPAdapter weight list → `IPAdapter Batch`. |
| **`VrchStudio/comfyui-web-viewer`** | MIDI Device nodes, **OSC control nodes** (server IP/port 8000, address path, combined `/xyz` or split `/xyz/x`), TouchOSC panel file, "Auto Switch to Instant Queue and Run Workflow" example, Live Portrait + Gamepad example. | Yes | OSC is the right transport if MIDI originates in Ableton (Max for Live / LiveGrabber → OSC) or TouchDesigner. |
| **Jovimetrix `MIDI READER (JOV)`** | Raw MIDI in: note on, channel, CC number, note, value, normalized value. | Yes | Minimal; fine for a first CC → float. |
| DIY | `python-rtmidi`/`mido` → ComfyUI websocket / `/prompt` API, mutate the API-format JSON per tick. | Yes | What we'd write if none of the above fits the Roustabout later. |

**Design note:** MIDI has two time scales — **CC = continuous** (weights, denoise, motion scale) and
**notes/program change = discrete events** (switch reference embed, prompt preset, seed). Option A
consumes CC as a *per-frame list latched per chunk*; option B consumes CC *per frame*. Notes should
select from a **precomputed IPAdapter embed bank** (§1) in both.

## 5. Candidate architectures

### A — Chunked AnimateDiff, beat-quantized (the literal ask)
```
MIDI (CC/notes) ─► bridge (rtmidi → per-frame float lists, latched every N frames)
                    │
ComfyUI loop (auto-queue or ComfyStream N-frame tick):
  SD1.5 ckpt + AnimateLCM motion module (4–6 steps, cfg 1.2, lcm / sgm_uniform)
  IPAdapter Batch (unfold) ◄─ IPAdapter Weights(custom = CC lane) ◄─ embed bank ◄─ notes
  ControlNet (optional: depth/openpose from webcam, weight = CC)
  AnimateDiff-Evolved multival (motion scale = CC / velocity)
  latent init = last 4–8 frames of previous chunk (context overlap) + noise
  ─► 16 frames ─► ring buffer ─► NDI/Spout/WebRTC out at 12–16 fps
```
- Latency = chunk render time; **quantize chunk boundaries to bars** and it reads as musical, not
  laggy. Frame count per chunk = frames per bar at the chosen fps (e.g. 16 f @ 120 bpm = 2 s bar @ 8 fps,
  or 32 f @ 16 fps with two overlapping 16-f contexts).
- All Latent Vision techniques apply unchanged. SD1.5 only (SDXL AD is 8-frame beta).
- Risk: seam flicker between chunks — mitigate with context overlap, fixed seed per bar, FreeNoise.

### B — Per-frame stream, coherence by feedback (truly live)
```
webcam / previous output frame ─► img2img (SD1.5-LCM or SDXL-Turbo, 1–4 steps, TensorRT)
   + IPAdapter (weight = CC, embed = note)  + ControlNet (weight = CC)  + StreamV2V feature bank
   ─► 20–60 fps ─► out
```
- ComfyStream (Linux) keeps it in ComfyUI; StreamDiffusion (python) is faster and already ships
  IPAdapter/ControlNet/StreamV2V/TensorRT.
- No motion module: the AnimateDiff "breathing" look is approximated by low-strength feedback +
  StreamV2V. SDXL is viable here.

### C — TouchDesigner front-end (StreamDiffusionTD)
- MIDI native, projector/NDI native, Patreon + Windows. ComfyUI only for offline assets/refs.
- Fastest to a gig; least "ours".

**Recommended first move:** build A and B as two ComfyUI graphs on the same GPU host with the same
embed bank and the same MIDI map, measure chunk latency for A and fps for B, then grill the trade-off.

## 6. Proposed MIDI map (v0, for the grill)

| MIDI | Target | Option |
|---|---|---|
| CC1 (mod wheel) | IPAdapter weight (0–1.2) | A, B |
| CC2 | ControlNet strength | A, B |
| CC7 | denoise / strength (B) · motion scale multival (A) | — |
| CC10 | weight-type crossfade `composition` ↔ `style transfer` (two adapters, `weights_invert`) | A, B |
| Note C2–B2 | select reference embed *n* from bank | A, B |
| Note velocity | blend amount toward new embed | A, B |
| Program change | prompt preset / LoRA | A, B |
| MIDI clock / Link | chunk boundary (bar) | A |
| Sustain (CC64) | freeze seed | A, B |

## 7. Assumptions & open questions (grill list)

Fleet GPU facts live in `~/.claude/CLAUDE.md` on watts, not in this clone — everything above assumes
a 4090-class NVIDIA card. Questions, recommendation first:

1. **Latency contract:** is one bar of latency acceptable (A), or must it be per-frame (B)?
   *Rec: start A; the AnimateDiff look was the point of the ask.*
2. **Host:** Huxley (Linux renderer, ComfyStream-friendly) vs Watts (Windows, StreamDiffusionTD-friendly)?
   *Rec: Huxley for A/B in ComfyUI; keep Watts as the MIDI/OSC sender.*
3. **MIDI source:** hardware controller direct to the host, or Ableton (→ OSC via Max for Live)?
   *Rec: controller direct first; OSC bridge second.*
4. **Base model:** SD1.5 (real AnimateDiff v3/LCM) vs SDXL (Turbo per-frame only)? *Rec: SD1.5 for A.*
5. **Output surface:** NDI/Spout to Resolume/TD, browser WebRTC, or just a window? *Rec: NDI.*
6. **Does this become a Skill / Run type** (a `live-session` Run with its MIDI log as `spec`) or stay
   a lab project outside the spine? *Rec: lab project until it works; log sessions later.*

## 8. Next steps (AM session)

1. Grill §7 one question at a time.
2. On the chosen host: install AnimateDiff-Evolved, IPAdapter_plus, ControlFreak, RealtimeNodes,
   RyanOnTheInside; pull AnimateLCM t2v + SD1.5 ckpt + IPAdapter plus/plus-face models.
3. Build the embed bank graph (8 refs → `IPAdapter Embeds` saved to disk).
4. Build graph A (16-f chunk) and measure render time at 512×512 / 4 steps.
5. Build graph B under ComfyStream (or StreamDiffusion standalone) and measure fps.
6. Wire ControlFreak to CC1/CC2 and a note → embed switch; record a 1-minute test.
7. Decide A/B/C; write the spell.

## Sources

- IPAdapter_plus README & videos — https://github.com/cubiq/ComfyUI_IPAdapter_plus ; Comfy Org fork https://github.com/comfyorg/comfyui-ipadapter ; examples https://github.com/cubiq/ComfyUI_IPAdapter_plus/tree/main/examples ; matt3o OpenArt 2-ref animation https://openart.ai/workflows/matt3o/ipadapter-2-reference-images-animation/p7DemRD5QjLNlLZkYdV4
- Matteo interview (May 2024) https://www.youtube.com/watch?v=tRrzTwhFWXc
- AnimateDiff-Evolved https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved ; AnimateLCM https://huggingface.co/wangfuyun/AnimateLCM ; Inner-Reflections LCM guide https://civitai.com/articles/4138 ; RunComfy AnimateLCM https://www.runcomfy.com/comfyui-workflows/comfyui-animatelcm-workflow
- Live2Diff https://github.com/open-mmlab/Live2Diff ; paper https://arxiv.org/pdf/2407.08701
- ComfyStream https://github.com/livepeer/comfystream ; Stream-Pack https://github.com/livepeer/ComfyUI-Stream-Pack ; Livepeer blog https://blog.livepeer.org/building-real-time-ai-video-effects-with-comfystream/
- StreamDiffusion (daydreamlive) https://github.com/daydreamlive/StreamDiffusion ; StreamDiffusionV2 https://www.emergentmind.com/topics/streamdiffusionv2 ; Daydream Scope launch (Nov 2025) https://www.morningstar.com/news/business-wire/20251106860538/
- StreamDiffusionTD https://dotsimulate.com/docs/streamdiffusiontd ; SDXL+IPAdapter release note https://derivative.ca/community-post/latest-streamdiffusiontd-release-sdxl-and-ipadapters/73236 ; hosted https://daydream.live/streamdiffusiontd ; TouchDiffusion https://github.com/olegchomp/TouchDiffusion
- ControlFreak https://github.com/ryanontheinside/ComfyUI_ControlFreak ; RealtimeNodes https://github.com/ryanontheinside/ComfyUI_RealtimeNodes ; RyanOnTheInside https://github.com/ryanontheinside/ComfyUI_RyanOnTheInside
- VrchStudio web-viewer (MIDI/OSC) https://github.com/VrchStudio/comfyui-web-viewer ; OSC docs https://github.com/VrchStudio/comfyui-web-viewer/blob/main/docs/osc_control_nodes.md ; Jovimetrix MIDI Reader https://www.runcomfy.com/comfyui-nodes/Jovimetrix/MIDI-READER--JOV---
- TD bridges: ComfyUI-TD https://github.com/JiSenHua/ComfyUI-TD ; TDComfyUI https://github.com/olegchomp/TDComfyUI ; ComfyTD deep dive https://alltd.org/comfytd-deep-dive/
- Fast SDXL variants: Hyper-SD https://stable-diffusion-art.com/hyper-sdxl/ ; DMD2 https://sandner.art/distribution-matching-distillation-photorealism-in-lesser-steps-comfyui-workflow-and-lora-solution/
