"""Shared prompt storage helpers.

DAO over `GlobalModelPreference`, `RagPrompt` and `RagPromptChunk` tables.
No AI provider logic here — only persistence.
"""

from .store import (
    get_active_prompt_chunks,
    get_escalation_policy_prompt,
    get_simple_system_prompt,
    set_escalation_policy_prompt,
    set_simple_system_prompt,
)

__all__ = [
    "get_active_prompt_chunks",
    "get_escalation_policy_prompt",
    "get_simple_system_prompt",
    "set_escalation_policy_prompt",
    "set_simple_system_prompt",
]
