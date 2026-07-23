"""Shared database namespace re-exporting SQLModel tables and helpers.

Важно: RAG-модели используют pgvector. Чтобы сервисы, которым RAG не нужен
(например, wa_service), не требовали обязательной зависимости, импорт
этих моделей делается опциональным.
"""

from sqlalchemy.orm import declarative_base
from sqlmodel import SQLModel

# --- Core models that are always available ---
from .models_admin import GlobalModelPreference  # noqa: F401
from .models_chat import ChatMessage  # noqa: F401
from .models_bitrix import BitrixOpenLineBinding, BitrixPortal, BitrixBusinessDayOverride  # noqa: F401
from .models_client import Client, ClientProfile  # noqa: F401
from .models_leads import LeadRecord  # noqa: F401
from .models_fx import FxRate  # noqa: F401
from .models_broadcast import BroadcastCampaign, BroadcastRecipient  # noqa: F401
from .models_ai_memory import AIConversationMemory, AISlotEvent  # noqa: F401
from .models_blog import BlogPost  # noqa: F401
from .session import create_db_and_tables, get_session  # noqa: F401

# --- Optional RAG models (pgvector dependency) ---
_RAG_AVAILABLE = True
try:
    from .models_rag import RagChunk, RagDocument, RagProfile, RagPrompt, RagPromptChunk  # noqa: F401
except Exception:  # pragma: no cover - optional dependency (e.g., pgvector not installed)
    _RAG_AVAILABLE = False
    RagChunk = RagDocument = RagProfile = RagPrompt = RagPromptChunk = None  # type: ignore[misc,assignment]

Base = declarative_base(metadata=SQLModel.metadata)

__all__ = [
    "Base",
    # Admin / Preferences
    "GlobalModelPreference",
    # CRM
    "Client",
    "ClientProfile",
    "ChatMessage",
    # Bitrix
    "BitrixPortal",
    "BitrixBusinessDayOverride",
    "BitrixOpenLineBinding",
    # Leads
    "LeadRecord",
    # Broadcasts
    "BroadcastCampaign",
    "BroadcastRecipient",
    # AI memory
    "AIConversationMemory",
    "AISlotEvent",
    # Blog
    "BlogPost",
    # FX
    "FxRate",
    # Session helpers
    "get_session",
    "create_db_and_tables",
]

# Экспортируем RAG-модели, только если они доступны (pgvector установлен)
if _RAG_AVAILABLE:
    __all__.extend(
        [
            "RagProfile",
            "RagDocument",
            "RagChunk",
            "RagPrompt",
            "RagPromptChunk",
        ]
    )
