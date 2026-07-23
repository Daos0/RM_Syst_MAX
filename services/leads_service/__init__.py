"""Leads service package: core logic and FastAPI app."""

from __future__ import annotations

from .service import get_lead, intake_lead, parse_text  # noqa: F401

__all__ = ["intake_lead", "parse_text", "get_lead"]
