"""Shared terminal styling for the fleet CLIs (hoist, fixtures, future Cast...).

One place pins the visual language so every tool colors the same concept the
same way. Colors degrade automatically when output is piped/redirected (rich
detects non-tty), so logs stay clean.
"""

from __future__ import annotations

import sys

from rich.console import Console

console = Console()
err_console = Console(stderr=True)

# The three sharing classes (ADR 0020 §1) each own a color, everywhere:
#   shared-content = green  (one artifact, every Shot uses it)
#   shared-recipe  = cyan   (same settings, content re-made per Shot)
#   per-shot       = yellow (the Shot owes its own input)
CLASS_STYLE = {
    "shared-content": "green",
    "shared-recipe": "cyan",
    "per-shot": "yellow",
}

CODE_STYLE = "bold"          # shot/sequence codes
GATE_STYLE = "bold magenta"  # gate artifacts: Publish p###, Version v###
DIM = "dim"                  # secondary detail (uris, params, template refs)


def cls(sharing_class: str) -> str:
    """The sharing class wrapped in its pinned color (rich markup)."""
    return f"[{CLASS_STYLE.get(sharing_class, 'white')}]{sharing_class}[/]"


def die(message: str, code: int = 1) -> None:
    """Exit with a red-tagged error on stderr (the styled sys.exit('error: ...'))."""
    err_console.print(f"[bold red]error:[/] {message}", highlight=False)
    sys.exit(code)
