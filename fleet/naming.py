"""Code construction for the Project spine (ADR 0015).

A Shot code is `JOB_EP_SEQ_SHOT` (e.g. `AWA_EP01_SALEM_010`); a Sequence code is
its `JOB_EP_SEQ` prefix (e.g. `AWA_EP01_SALEM`, ADR 0020). Because `_` is the
SEPARATOR between parts, the parts themselves must not contain `_` — otherwise a
code can't be parsed back to its coordinates.
"""

from __future__ import annotations

import re

# Parts may NOT contain '_' (it separates the parts) — hyphens/alphanumerics only.
TOKEN_RE = re.compile(r"^[A-Za-z0-9-]+$")


def validate_token(label: str, value: str) -> None:
    """Raise ValueError if a code part isn't a clean, underscore-free token."""
    if not TOKEN_RE.match(value):
        raise ValueError(
            f"{label} '{value}' must match [A-Za-z0-9-]+ "
            f"(no underscores — '_' separates the parts of a shot code)"
        )


def sequence_code(job: str, episode: str, sequence: str) -> str:
    """`JOB_EP_SEQ` — the Sequence's code (ADR 0020)."""
    return f"{job}_{episode}_{sequence}"


def shot_code(job: str, episode: str, sequence: str, shot: str) -> str:
    """`JOB_EP_SEQ_SHOT` — the Shot's code = its folder name (ADR 0015)."""
    return f"{job}_{episode}_{sequence}_{shot}"
