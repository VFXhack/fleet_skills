"""Fleet production tooling.

Shared building blocks for the pipeline:
  - config      : resolve the Postgres DSN + per-machine paths (ADR 0002/0008)
  - db          : open a connection to the provenance core on Mckenna
  - repository  : where the ubiquitous language meets SQL (ADR 0008)
  - manifest    : the thin per-Project map header (ADR 0006)
  - scaffold    : stamp the canonical ADR-0003 project tree
  - cli         : the create-project entrypoint
"""

__version__ = "0.1.0"
