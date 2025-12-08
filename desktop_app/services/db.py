# careerbuddy/services/db.py
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

DB_FILE = Path(__file__).resolve().parents[2] / "career_buddy.db"

class CareerDB:
    """Typed, context‑managed CRUD layer."""
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

    def list_upcoming_reminders(self, limit: int = 15) -> List[Tuple]:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, title, description, date, time, category
                   FROM reminders
                   WHERE date >= ?
                   ORDER BY date, time
                   LIMIT ?""",
                (today, limit),
            )
            return cur.fetchall()

    def mark_notified(self, reminder_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE reminders SET notified=1 WHERE id=?", (reminder_id,))

    def delete_reminder(self, reminder_id: int) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
