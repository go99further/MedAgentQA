"""
Legacy aggregate for application models.

This module now proxies to the new `medagent.infrastructure.persistence.db.models` (SQLAlchemy) and
`medagent.interfaces.http.models` (Pydantic) packages. Prefer importing from those packages
directly to make intent explicit.
"""
from warnings import warn

from medagent.interfaces.http.models.chat import ChatRequest, ChatResponse
from medagent.interfaces.http.models.chat_message import (
    ChatMessageBase,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatMessageUpdate,
    ChatSessionSnapshotBase,
    ChatSessionSnapshotCreate,
    ChatSessionSnapshotResponse,
)
from medagent.interfaces.http.models.chat_session import ChatSessionCreate, ChatSessionResponse, ChatSessionUpdate
from medagent.infrastructure.persistence.db.models import (
    ChatMessage,
    ChatSession,
    ChatSessionSnapshot,
    Conversation,
    ConversationHistorySnapshot,
    DialogueType,
    Message,
    User,
)

warn(
    "Importing from `medagent.models` is deprecated. "
    "Use `medagent.infrastructure.persistence.db.models` for database entities and "
    "`medagent.interfaces.http.models` for Pydantic schemas instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    # Pydantic schemas (legacy re-export)
    "ChatRequest",
    "ChatResponse",
    "ChatMessageBase",
    "ChatMessageCreate",
    "ChatMessageUpdate",
    "ChatMessageResponse",
    "ChatSessionSnapshotBase",
    "ChatSessionSnapshotCreate",
    "ChatSessionSnapshotResponse",
    "ChatSessionCreate",
    "ChatSessionUpdate",
    "ChatSessionResponse",
    # SQLAlchemy models
    "ChatMessage",
    "ChatSession",
    "ChatSessionSnapshot",
    "Conversation",
    "ConversationHistorySnapshot",
    "DialogueType",
    "Message",
    "User",
]
