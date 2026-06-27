"""Roustabout — the deterministic orchestration floor (ADR 0012 / 0018 / 0019).

A thin Python worker: receive orchestration events from the durable `events`
outbox, run pre-wired FLOWS (rule-based, no LLM, no judgment), durably and
idempotently. See README.md.
"""
