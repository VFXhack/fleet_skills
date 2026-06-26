"""Runners — provider-specific backends the Submitter dispatches to (CONTEXT.md "Runner").

Each runner adapts one provider's API (Magnific, fal, Comfy, ...) behind a common shape:
submit a job, await the result, return the produced asset(s). For now they can also be
driven directly from the CLI for model exploration; provenance recording (Run/Version ->
Postgres) is layered on by the Submitter later.
"""
