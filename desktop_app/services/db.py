# careerbuddy/services/db.py
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

DB_FILE = Path(__file__).resolve().parents[2] / "career_buddy.db"


class CareerDB:
    """Typed, context-managed CRUD layer."""
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self._init_schema()

    # --------------------------------------------------------------
    from contextlib import contextmanager

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --------------------------------------------------------------
    def _init_schema(self) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs(
                    id INTEGER PRIMARY KEY,
                    company TEXT,
                    role TEXT,
                    status TEXT,
                    link TEXT,
                    notes TEXT,
                    date_added TEXT
                );
                CREATE TABLE IF NOT EXISTS notes(
                    id INTEGER PRIMARY KEY,
                    content TEXT
                );
                CREATE TABLE IF NOT EXISTS settings(
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS files(
                    id INTEGER PRIMARY KEY,
                    filename TEXT,
                    original_name TEXT,
                    category TEXT,
                    date_added TEXT
                );
                CREATE TABLE IF NOT EXISTS reminders(
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    date TEXT,
                    time TEXT,
                    category TEXT,
                    notified INTEGER DEFAULT 0
                );

                -- ---------------------------
                -- AI: conversations + memory
                -- ---------------------------
                CREATE TABLE IF NOT EXISTS ai_conversations(
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS ai_messages(
                    id INTEGER PRIMARY KEY,
                    conversation_id INTEGER,
                    ts TEXT,
                    role TEXT,
                    content TEXT,
                    FOREIGN KEY(conversation_id) REFERENCES ai_conversations(id)
                );

                CREATE TABLE IF NOT EXISTS ai_memories(
                    id INTEGER PRIMARY KEY,
                    ts TEXT,
                    type TEXT,
                    content TEXT,
                    importance INTEGER DEFAULT 5,
                    pinned INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS ai_summaries(
                    id INTEGER PRIMARY KEY,
                    scope TEXT,
                    ts TEXT,
                    summary_text TEXT
                );
                """
            )
            cur.execute("SELECT COUNT(*) FROM notes")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO notes (content) VALUES ('')")

    # --------------------------------------------------------------
    # ----- Jobs ---------------------------------------------------
    def add_job(
        self,
        company: str,
        role: str,
        status: str,
        link: str = "",
        notes: str = "",
        date_added: Optional[str] = None,
    ) -> int:
        date_added = date_added or datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO jobs
                   (company, role, status, link, notes, date_added)
                   VALUES (?,?,?,?,?,?)""",
                (company, role, status, link, notes, date_added),
            )
            return cur.lastrowid

    def get_all_jobs(self) -> List[Tuple]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, company, role, status, notes, date_added
                   FROM jobs ORDER BY date_added DESC"""
            )
            return cur.fetchall()

    def get_jobs_by_status(self, status: str) -> List[Tuple]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, company, role, status, notes, date_added
                   FROM jobs WHERE status=? ORDER BY date_added DESC""",
                (status,),
            )
            return cur.fetchall()

    def update_job_status(self, job_id: int, new_status: str) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))

    def delete_job(self, job_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    def edit_job(
        self,
        job_id: int,
        company: str,
        role: str,
        status: str,
        notes: str,
        link: str = "",
    ) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE jobs
                   SET company=?, role=?, status=?, notes=?, link=?
                   WHERE id=?""",
                (company, role, status, notes, link, job_id),
            )

    # --------------------------------------------------------------
    # ----- Notes ---------------------------------------------------
    def load_notes(self) -> str:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT content FROM notes WHERE id=1")
            row = cur.fetchone()
            return row[0] if row else ""

    def save_notes(self, content: str) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE notes SET content=? WHERE id=1", (content,))

    # --------------------------------------------------------------
    # ----- Files ---------------------------------------------------
    def add_file(
        self,
        filename: str,
        original_name: str,
        category: str,
        date_added: Optional[str] = None,
    ) -> int:
        date_added = date_added or datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO files
                   (filename, original_name, category, date_added)
                   VALUES (?,?,?,?)""",
                (filename, original_name, category, date_added),
            )
            return cur.lastrowid

    def list_files(self, category: Optional[str] = None) -> List[Tuple]:
        with self._conn() as conn:
            cur = conn.cursor()
            if category and category != "All":
                cur.execute(
                    """SELECT id, filename, original_name, category, date_added
                       FROM files WHERE category=? ORDER BY date_added DESC""",
                    (category,),
                )
            else:
                cur.execute(
                    """SELECT id, filename, original_name, category, date_added
                       FROM files ORDER BY date_added DESC"""
                )
            return cur.fetchall()

    def delete_file(self, file_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM files WHERE id=?", (file_id,))

    # --------------------------------------------------------------
    # ----- Reminders -----------------------------------------------
    def add_reminder(
        self,
        title: str,
        description: str,
        date: str,
        time: str,
        category: str,
    ) -> int:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO reminders
                   (title, description, date, time, category)
                   VALUES (?,?,?,?,?)""",
                (title, description, date, time, category),
            )
            return cur.lastrowid

    def list_reminders_for_date(self, date: str) -> List[Tuple]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, title, description, date, time, category
                FROM reminders
                WHERE date = ?
                ORDER BY time""",
                (date,),
            )
            return cur.fetchall()

    def update_reminder(
        self,
        reminder_id: int,
        title: str,
        description: str,
        date: str,
        time: str,
        category: str,
    ) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE reminders
                SET title=?, description=?, date=?, time=?, category=?
                WHERE id=?""",
                (title, description, date, time, category, reminder_id),
            )

    def mark_notified(self, reminder_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE reminders SET notified=1 WHERE id=?", (reminder_id,))

    def delete_reminder(self, reminder_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))

    # --------------------------------------------------------------
    # ----- AI: conversations, messages, memory ---------------------
    def ai_create_conversation(self, title: str = "New chat") -> int:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ai_conversations (title, created_at) VALUES (?, ?)",
                (title, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            return cur.lastrowid

    def ai_list_conversations(self, limit: int = 50) -> List[Tuple]:
        # Keep signature stable; limit is capped by caller as needed
        limit = int(limit)
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, created_at FROM ai_conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()

    def ai_add_message(self, conversation_id: int, role: str, content: str) -> int:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ai_messages (conversation_id, ts, role, content) VALUES (?, ?, ?, ?)",
                (int(conversation_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), role, content),
            )
            return cur.lastrowid

    def ai_get_messages(self, conversation_id: int, limit: int = 30) -> List[Tuple]:
        """Returns a list of (role, content, ts) ordered oldest->newest for last N messages."""
        limit = int(limit)
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT role, content, ts
                FROM ai_messages
                WHERE conversation_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(conversation_id), limit),
            )
            rows = cur.fetchall()
            return list(reversed(rows))

    def ai_add_memory(self, mem_type: str, content: str, importance: int = 5, pinned: int = 0) -> int:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ai_memories (ts, type, content, importance, pinned) VALUES (?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(mem_type), str(content), int(importance), int(pinned)),
            )
            return cur.lastrowid

    def ai_list_memories(self, pinned_first: bool = True, limit: int = 200) -> List[Tuple]:
        limit = int(limit)
        with self._conn() as conn:
            cur = conn.cursor()
            if pinned_first:
                cur.execute(
                    """
                    SELECT id, ts, type, content, importance, pinned
                    FROM ai_memories
                    ORDER BY pinned DESC, importance DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, ts, type, content, importance, pinned
                    FROM ai_memories
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            return cur.fetchall()

    def ai_search_memories(self, query: str, limit: int = 30) -> List[Tuple]:
        q = f"%{(query or '').strip()}%"
        limit = int(limit)
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, ts, type, content, importance, pinned
                FROM ai_memories
                WHERE content LIKE ?
                ORDER BY pinned DESC, importance DESC, id DESC
                LIMIT ?
                """,
                (q, limit),
            )
            return cur.fetchall()

    def ai_set_memory_pinned(self, memory_id: int, pinned: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE ai_memories SET pinned=? WHERE id=?", (int(pinned), int(memory_id)))

    def ai_delete_memory(self, memory_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM ai_memories WHERE id=?", (int(memory_id),))

    def ai_get_latest_summary(self, scope: str = "global") -> str:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT summary_text FROM ai_summaries WHERE scope=? ORDER BY id DESC LIMIT 1",
                (str(scope),),
            )
            row = cur.fetchone()
            return row[0] if row else ""

    def ai_set_summary(self, scope: str, summary_text: str) -> int:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ai_summaries (scope, ts, summary_text) VALUES (?, ?, ?)",
                (str(scope), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(summary_text)),
            )
            return cur.lastrowid
