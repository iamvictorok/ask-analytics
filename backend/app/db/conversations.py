"""Conversation persistence — CRUD for conversations and messages.

All queries are scoped by user_id for data isolation.
Uses raw SQL matching the project's existing pattern (no ORM models).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

logger = logging.getLogger("dhis2_analyst.conversations")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


async def create_conversation(
    session, user_id: str, title: str = "New chat"
) -> dict:
    """Create a new conversation and return its metadata."""
    conv_id = _new_id()
    now = _now_iso()
    logger.info("conversation_create_start", extra={"user_id": user_id, "title": title, "conv_id": conv_id})
    await session.execute(
        text("""
            INSERT INTO conversations (id, user_id, title, created_at, updated_at)
            VALUES (:id, :user_id, :title, :created_at, :updated_at)
        """),
        {
            "id": conv_id,
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        },
    )
    await session.commit()
    logger.info("conversation_create_success", extra={"user_id": user_id, "conv_id": conv_id})
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


async def list_conversations(
    session, user_id: str, limit: int = 50
) -> list[dict]:
    """List conversations for a user, most recent first."""
    logger.info("conversation_list_start", extra={"user_id": user_id, "limit": limit})
    result = await session.execute(
        text("""
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE user_id = :user_id
            ORDER BY updated_at DESC
            LIMIT :lim
        """),
        {"user_id": user_id, "lim": limit},
    )
    conversations = [
        {"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]}
        for r in result.fetchall()
    ]
    logger.info("conversation_list_success", extra={"user_id": user_id, "count": len(conversations)})
    return conversations


async def get_conversation(session, conv_id: str, user_id: str) -> dict | None:
    """Get a single conversation if owned by user_id."""
    logger.info("conversation_get_start", extra={"conv_id": conv_id, "user_id": user_id})
    result = await session.execute(
        text("""
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE id = :id AND user_id = :user_id
        """),
        {"id": conv_id, "user_id": user_id},
    )
    row = result.fetchone()
    if not row:
        logger.info("conversation_get_not_found", extra={"conv_id": conv_id, "user_id": user_id})
        return None
    logger.info("conversation_get_success", extra={"conv_id": conv_id, "user_id": user_id})
    return {"id": row[0], "title": row[1], "created_at": row[2], "updated_at": row[3]}


async def delete_conversation(session, conv_id: str, user_id: str) -> bool:
    """Delete a conversation and its messages (CASCADE). Returns True if deleted."""
    logger.info("conversation_delete_start", extra={"conv_id": conv_id, "user_id": user_id})
    result = await session.execute(
        text("DELETE FROM conversations WHERE id = :id AND user_id = :user_id"),
        {"id": conv_id, "user_id": user_id},
    )
    await session.commit()
    success = result.rowcount > 0
    logger.info("conversation_delete_complete", extra={"conv_id": conv_id, "user_id": user_id, "success": success})
    return success


async def update_title(
    session, conv_id: str, user_id: str, title: str
) -> bool:
    """Rename a conversation. Returns True if updated."""
    logger.info("conversation_rename_start", extra={"conv_id": conv_id, "user_id": user_id, "new_title": title})
    result = await session.execute(
        text("""
            UPDATE conversations SET title = :title, updated_at = :now
            WHERE id = :id AND user_id = :user_id
        """),
        {"title": title, "now": _now_iso(), "id": conv_id, "user_id": user_id},
    )
    await session.commit()
    success = result.rowcount > 0
    logger.info("conversation_rename_complete", extra={"conv_id": conv_id, "user_id": user_id, "success": success})
    return success


async def add_message(
    session,
    conv_id: str,
    role: str,
    content: str,
    artefacts: dict | None = None,
) -> dict:
    """Insert a message and touch the parent conversation's updated_at."""
    msg_id = _new_id()
    now = _now_iso()
    artefacts_str = json.dumps(artefacts) if artefacts else None

    logger.info(
        "message_add_start",
        extra={
            "conv_id": conv_id,
            "msg_id": msg_id,
            "role": role,
            "has_artefacts": artefacts is not None,
        },
    )

    await session.execute(
        text("""
            INSERT INTO messages (id, conversation_id, role, content, artefacts, created_at)
            VALUES (:id, :conv_id, :role, :content, :artefacts, :created_at)
        """),
        {
            "id": msg_id,
            "conv_id": conv_id,
            "role": role,
            "content": content,
            "artefacts": artefacts_str,
            "created_at": now,
        },
    )
    await session.execute(
        text("UPDATE conversations SET updated_at = :now WHERE id = :conv_id"),
        {"now": now, "conv_id": conv_id},
    )
    await session.commit()
    logger.info("message_add_success", extra={"conv_id": conv_id, "msg_id": msg_id, "role": role})
    return {
        "id": msg_id,
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "artefacts": artefacts,
        "created_at": now,
    }


async def get_messages(session, conv_id: str, user_id: str) -> list[dict]:
    """Get all messages for a conversation, with ownership check."""
    logger.info("messages_get_start", extra={"conv_id": conv_id, "user_id": user_id})
    # Verify ownership first
    owner = await session.execute(
        text("SELECT 1 FROM conversations WHERE id = :id AND user_id = :user_id"),
        {"id": conv_id, "user_id": user_id},
    )
    if not owner.fetchone():
        logger.warning("messages_get_denied", extra={"conv_id": conv_id, "user_id": user_id})
        return []

    result = await session.execute(
        text("""
            SELECT id, role, content, artefacts, created_at
            FROM messages
            WHERE conversation_id = :conv_id
            ORDER BY created_at ASC
        """),
        {"conv_id": conv_id},
    )
    messages = []
    for r in result.fetchall():
        art = r[3]
        if art and isinstance(art, str):
            try:
                art = json.loads(art)
            except (json.JSONDecodeError, TypeError):
                art = None
        messages.append({
            "id": r[0],
            "role": r[1],
            "content": r[2],
            "artefacts": art,
            "created_at": r[4],
        })
    logger.info("messages_get_success", extra={"conv_id": conv_id, "user_id": user_id, "message_count": len(messages)})
    return messages
