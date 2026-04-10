"""SQLite 数据库操作"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from models import Message, Session

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else (BASE_DIR / "data" / "topics")
        self.db_path.mkdir(parents=True, exist_ok=True)

    def _get_db_path(self, topic_summary: str) -> Path:
        topic_dir = self.db_path / topic_summary
        topic_dir.mkdir(parents=True, exist_ok=True)
        return topic_dir / "messages.db"

    def init_db(self, topic_summary: str):
        db_path = self._get_db_path(topic_summary)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model_alias TEXT,
                model_name TEXT,
                timestamp TEXT NOT NULL,
                tokens INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                topic TEXT,
                topic_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                current_round INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def save_message(self, topic_summary: str, message: Message):
        db_path = self._get_db_path(topic_summary)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO messages (session_id, role, content, model_alias, model_name, timestamp, tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            message.session_id,
            message.role,
            message.content,
            message.model_alias,
            message.model_name,
            message.timestamp.isoformat(),
            message.tokens
        ))

        conn.commit()
        conn.close()

    def get_messages(self, topic_summary: str, session_id: str) -> List[Message]:
        db_path = self._get_db_path(topic_summary)
        if not db_path.exists():
            return []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, session_id, role, content, model_alias, model_name, timestamp, tokens
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp
        """, (session_id,))

        messages = []
        for row in cursor.fetchall():
            messages.append(Message(
                id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                model_alias=row[4],
                model_name=row[5],
                timestamp=datetime.fromisoformat(row[6]),
                tokens=row[7]
            ))

        conn.close()
        return messages

    def save_session(self, topic_summary: str, session: Session):
        self.init_db(topic_summary)
        db_path = self._get_db_path(topic_summary)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO sessions (id, name, topic, topic_summary, created_at, updated_at, status, current_round)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id,
            session.name,
            session.topic,
            topic_summary,
            session.created_at.isoformat(),
            session.updated_at.isoformat(),
            session.status,
            session.current_round
        ))

        conn.commit()
        conn.close()

    def get_session(self, topic_summary: str, session_id: str) -> Optional[Session]:
        db_path = self._get_db_path(topic_summary)
        if not db_path.exists():
            return None

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, topic, topic_summary, created_at, updated_at, status, current_round
            FROM sessions
            WHERE id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return Session(
                id=row[0],
                name=row[1],
                topic=row[2],
                topic_summary=row[3],
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
                status=row[6],
                current_round=row[7]
            )
        return None

    def update_session_status(self, topic_summary: str, session_id: str, status: str, current_round: Optional[int] = None):
        db_path = self._get_db_path(topic_summary)
        if not db_path.exists():
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if current_round is not None:
            cursor.execute("""
                UPDATE sessions SET status = ?, current_round = ?, updated_at = ?
                WHERE id = ?
            """, (status, current_round, datetime.now().isoformat(), session_id))
        else:
            cursor.execute("""
                UPDATE sessions SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, datetime.now().isoformat(), session_id))

        conn.commit()
        conn.close()

    def update_session_topic(self, topic_summary: str, session_id: str, topic: str):
        """更新session的topic字段"""
        db_path = self._get_db_path(topic_summary)
        if not db_path.exists():
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions SET topic = ?, updated_at = ?
            WHERE id = ?
        """, (topic, datetime.now().isoformat(), session_id))

        conn.commit()
        conn.close()

    def get_total_tokens(self, topic_summary: str, session_id: str) -> int:
        db_path = self._get_db_path(topic_summary)
        if not db_path.exists():
            return 0

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT SUM(tokens) FROM messages
            WHERE session_id = ? AND tokens IS NOT NULL
        """, (session_id,))

        result = cursor.fetchone()[0]
        conn.close()
        return result or 0

    def find_topic_summary_by_session_id(self, session_id: str) -> Optional[str]:
        """通过 session_id 查找对应的 topic_summary"""
        if not self.db_path.exists():
            return None

        for topic_dir in self.db_path.iterdir():
            if topic_dir.is_dir():
                db_path = topic_dir / "messages.db"
                if db_path.exists():
                    try:
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT topic_summary FROM sessions WHERE id = ?
                        """, (session_id,))
                        row = cursor.fetchone()
                        conn.close()
                        if row:
                            return row[0]
                    except sqlite3.Error:
                        continue
        return None


database = Database()
