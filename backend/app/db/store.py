"""SQLite 对话持久化"""

import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.models import ChatMessage, SessionInfo
from app.core.logger import logger


class ConversationStore:
    """管理对话历史的 SQLite 存储"""

    def __init__(self, db_path: str = "./data/conversations.db"):
        db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()
        logger.info(f"数据库已初始化: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);
            """)

    def create_session(self, session_id: str) -> None:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)",
                (session_id, now, now),
            )

    def add_message(self, session_id: str, msg: ChatMessage) -> None:
        now = datetime.now().isoformat()
        sources_json = json.dumps(
            [s.model_dump(mode="json") for s in msg.sources]
        ) if msg.sources else None

        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, sources, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, msg.role, msg.content, sources_json, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def get_messages(self, session_id: str, limit: int = 50) -> List[ChatMessage]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content, sources, timestamp FROM messages "
                "WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()

        messages = []
        for row in rows:
            sources = None
            if row["sources"]:
                try:
                    sources = json.loads(row["sources"])
                except json.JSONDecodeError:
                    pass
            messages.append(ChatMessage(
                role=row["role"],
                content=row["content"],
                sources=sources,
                timestamp=datetime.fromisoformat(row["timestamp"]),
            ))
        return messages

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT session_id, created_at, updated_at, "
                "(SELECT COUNT(*) FROM messages WHERE session_id = s.session_id) as msg_count "
                "FROM sessions s WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if not row:
                return None
            return SessionInfo(
                session_id=row["session_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                message_count=row["msg_count"],
            )

    def list_sessions(self, limit: int = 20) -> List[SessionInfo]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT session_id, created_at, updated_at, "
                "(SELECT COUNT(*) FROM messages WHERE session_id = s.session_id) as msg_count "
                "FROM sessions s ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            SessionInfo(
                session_id=row["session_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                message_count=row["msg_count"],
            )
            for row in rows
        ]

    def delete_session(self, session_id: str) -> bool:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return cursor.rowcount > 0
