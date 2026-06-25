# ADR 0002 — Project store on Huxley, with a platform-neutral `base_path`

**Status:** Accepted
**Date:** 2026-06-24

## Context
Projects historically lived on the internal SSD of **Watts** (Andy's Windows workstation),
mirrored to **Leary** when mobile. That made the workstation the source of truth, forced the
`.blend` to be shipped to the renderer for every render, and left no authoritative copy. The
Fleet is also mixed-OS (Watts = Windows 11, Huxley = Unix, Ramdass = macOS) and joined over
Tailscale at 10GbE, so no single literal path string (`D:\…` or `/…`) is valid on every machine.

Two options were weighed:
- **A. Keep Projects local on Watts `D:`** — fastest possible editing; but multiple copies,
  manual mirroring to Leary, and the file-transfer dance to get each render onto Huxley.
- **B. A canonical Fleet Project store on Huxley** — one authoritative copy every machine
  reaches; the renderer (Huxley) gets local-disk access; scales to Leary, Mckenna, and future
  Ramdass/Hermes. Cost: workstations edit over the network.

The deciding constraint was video-editing throughput: the Watts↔Huxley link is **10GbE** and
edits are **4K ProRes**, which that link sustains comfortably — removing A's only real advantage.

## Decision
- The **canonical Project store lives on Huxley** (the big-storage renderer), served to the rest
  of the Fleet over Tailscale/10GbE. There is **one** authoritative copy — not a per-workstation
  original plus mirrors.
- A Project's **`base_path` is stored platform-neutral in the Manifest** — a logical root +
  project slug — and **resolved to a real path per-machine** (UNC/drive-letter on Windows, POSIX
  mount on Unix, mount on macOS). The Manifest never stores a raw OS-specific path as the source
  of truth.

## Consequences
- The renderer reads Projects with local disk access; the per-render file-transfer problem largely
  disappears.
- Every machine needs a small, one-time resolver config mapping the logical root → its real mount.
- Workstation editing now depends on the network link being healthy (acceptable at 10GbE for ProRes).
- Still to finalize (does not block this decision): the exact Huxley store path, the Windows mount
  form (UNC via Tailscale vs. mapped drive letter), and the project-slug format.

## Why an ADR
Where every Project physically lives, and how its path is addressed, is load-bearing for the
Manifest, the Submitter, and every Skill that touches files. It reverses expensively (re-homing all
projects, rewriting paths) and is surprising without context — a future reader would assume
"projects live on the workstation." That's the bar.
